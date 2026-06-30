import uuid
import logging

import streamlit as st
from dotenv import load_dotenv

load_dotenv(override=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("streamlit-ui")

st.set_page_config(page_title="Compliance QA Pipeline", page_icon="🛡️", layout="wide")

st.title("Compliance QA Pipeline")
st.caption("Submit a YouTube video URL to run the compliance audit workflow.")

with st.sidebar:
    st.header("Configuration")
    video_url = st.text_input(
        "Video URL",
        value="",
        help="Paste a YouTube video URL to analyze.",
    )
    run_button = st.button("Run Audit", type="primary")

if run_button:
    if not video_url.strip():
        st.error("Please provide a video URL.")
        st.stop()

    initial_inputs = {
        "video_url": video_url.strip(),
        "video_id": f"video_{uuid.uuid4().hex[:8]}",
        "compliance_results": [],
        "errors": [],
    }

    st.session_state["last_inputs"] = initial_inputs

    with st.spinner("Running compliance workflow..."):
        try:
            from backend.src.graph.workflow import app as workflow_app

            final_state = workflow_app.invoke(initial_inputs)
            st.session_state["last_result"] = final_state
            st.success("Audit completed.")
        except Exception as exc:
            logger.exception("Workflow execution failed")
            st.session_state["last_result"] = {
                "errors": [str(exc)],
                "final_status": "FAIL",
                "final_report": "Workflow execution failed.",
            }
            st.error(f"Workflow error: {exc}")

if "last_inputs" in st.session_state:
    st.subheader("Latest request")
    st.json(st.session_state["last_inputs"])

if "last_result" in st.session_state:
    result = st.session_state["last_result"]
    st.subheader("Audit result")

    st.metric("Status", result.get("final_status", "UNKNOWN"))
    st.write(result.get("final_report", "No report generated."))

    errors = result.get("errors", [])
    if errors:
        st.warning("Errors")
        for error in errors:
            st.write(f"- {error}")

    compliance_results = result.get("compliance_results", [])
    if compliance_results:
        st.subheader("Compliance findings")
        for item in compliance_results:
            with st.expander(f"{item.get('severity', 'UNKNOWN')} - {item.get('category', 'General')}"):
                st.write(item.get("description", "No description available."))
    else:
        st.info("No compliance findings were returned.")

    with st.expander("Raw workflow state"):
        st.json(result)
