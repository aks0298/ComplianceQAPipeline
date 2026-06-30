import operator
from typing import Annotated,List,Dict,Optional,Any,TypedDict

#schema 

class ComplianceIssue(TypedDict):
    category: str #eg: "Privacy Violation"
    description: str #violation description
    severity: str #warning 
    timestamp: Optional[str] #timestamp of the violation

class VideoAuditState(TypedDict):
    '''
    defines the data schema for the video audit state, which includes the video ID, a list of compliance issues, and an optional summary of the audit findings.
    '''
    #input
    video_url: str #video url
    video_id: str #video id

    #extraction data
    local_file_path:Optional[str]
    video_metadata: Dict[str,Any]
    transcript: Optional[str] #transcript of the video
    ocr_text: Optional[str] #text extracted from the video using OCR

    #analysis output
    #list off oll the compliance found by ai
    compliance_results:Annotated[List[ComplianceIssue], operator.add] 

    #final output
    final_status: str
    final_report:str

    #system errors
    errors: Annotated[List[str], operator.add]
