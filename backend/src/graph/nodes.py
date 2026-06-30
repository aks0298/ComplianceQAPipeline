import json
import os
import logging
import re
from typing import Dict, Any, List, Optional
from xmlrpc import client

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage
from qdrant_client import QdrantClient

from backend.src.graph.states import VideoAuditState, ComplianceIssue


#importing services
from backend.src.services.video_indexer import VideoIndexerService
#configure the logger

logger=logging.getLogger("brand-guardian")

#node1:indexer

def index_video_node(state: VideoAuditState) -> Dict[str,Any]:
    '''
    Download the youtube video from the url
    uploads to the cloud storage and returns the video id and url

    '''

    video_url=(state.get("video_url") or "").strip()
    video_id_input=state.get("video_id","vid_demo")

    logging.info(f"Indexing video: {video_url} with id: {video_id_input}")

    local_filename="temp_audit_video.mp4"

    if not video_url or ("youtube.com" not in video_url and "youtu.be" not in video_url):
        logger.error("Invalid or missing video URL for indexing")
        return {
            "video_id": video_id_input,
            "errors": ["Invalid video url. Only youtube videos are supported."],
            "final_status": "FAIL",
            "transcript": "",
            "ocr_text": [],
            "video_metadata": {"platform": "youtube"},
        }

    try:
        vi_service=VideoIndexerService()

        local_path=vi_service.download_youtube_video(video_url,output_path=local_filename)
        storage_path = vi_service.upload_video(local_path,file_name=f"{video_id_input}.mp4")

        logger.info(f"Video uploaded to Supabase: {storage_path}")

        if os.path.exists(local_path):
            os.remove(local_path)
            logger.info(f"Temporary video file {local_path} deleted.")
        
        raw_insights=vi_service.extract_video_insights(storage_path)
        clean_data=vi_service.extract_data(raw_insights)

        logger.info(f"Video insights extracted for video id: {video_id_input}")
        return {
            **clean_data,
            "video_id": video_id_input,
            "errors": [],
        }
    except Exception as e:
        logger.error(f"Error in index_video_node: {str(e)}")
        return {
            "video_id": video_id_input,
            "errors": [str(e)],
            "final_status": "FAIL",
            "transcript": "",
            "ocr_text": [],
            "video_metadata": {"platform": "youtube"},
        }


#node 2;

def audio_content_node(state: VideoAuditState) -> Dict[str,Any]:
    '''
    performs retrieval of the audio content from the video and returns the transcript and ocr text
    '''

    logger.info(f"Starting audio content extraction for video id: {state.get('video_id')}")

    transcript=state.get("transcript","")
    if not transcript:
        logger.info("Transcript not found in state, performing audio extraction.")
        return{
            "final_status":"Fail",
            "final_report":"audit skipped beacuse video processing failed"
        }
    
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0.0)

    embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2")

    client = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY"))

    vector_store = QdrantVectorStore(
    client=client,
    collection_name=os.getenv("QDRANT_COLLECTION_NAME"),
    embedding=embeddings)    


    ocr_text=state.get("ocr_text",[])
    query_text=f"{transcript} {' '.join(ocr_text)}"

    docs=vector_store.similarity_search(query_text, k=5)
    retrieved_rules="\n\n".join([doc.page_content for doc in docs])

    system_prompt=f"""
        you are a senoir brand compliance auditor.
        OFFICIAL RULES AND REGULATIONS:
        {retrieved_rules}
        INSTRUCTIONS:
        1. Analyze the Transcript and oct tecxt below
        2. Identify any potential compliance issues based on the official rules and regulations provided.
        3. Return strictly json in the following format:
        {{
        "compliance_results": [
        {{
        "category": "Claim Validation",
        "severity": "CRITICAL",
        "description": "Explanation of the violation..."
        }}
    ],
        "status": "FAIL",
        "final_report": "Summary of findings..."
        }}
        Return ONLY valid JSON.

        Do not use markdown.
        Do not wrap the JSON inside ``` blocks.
        Do not add explanations.
        if no compliance issues are found, set "status" to "PASS" and "compliance_results" to [].
        """
    user_message=f"""
        VIDEO_METADATA:{state.get("video_metadata",{})}
        TRANSCRIPT:{transcript}
        OCR_TEXT:{ocr_text}

        """
    
    try:
        response=llm.invoke([SystemMessage(content=system_prompt),
                    HumanMessage(content=user_message)])
        content=response.content
        if not isinstance(content, str):
            content = str(content)
        if "```" in content:
            match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
            if match:
                content = match.group(1).strip()
            else:
                logger.warning("No JSON block found in the LLM response.")
        audit_data=json.loads(content.strip())

        return{
            "compliance_results":audit_data.get("compliance_results",[]),
            "final_status":audit_data.get("status","FAIL"),
            "final_report":audit_data.get("final_report","")
        }
    except Exception as e:
        logger.error(f"Error in audio_content_node: {str(e)}")
        logger.error(f"LLM response content: {response.content if 'response' in locals() else 'No response'}")

        return {
            "errors": [str(e)],
            "final_status": "FAIL",
            "final_report": "Error during compliance analysis."
        }
    
    


        



