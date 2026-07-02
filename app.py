from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

load_dotenv(override=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("compliance-web")

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(title="Compliance QA Pipeline", version="1.0.0")
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR), html=False), name="static")


class AuditRequest(BaseModel):
    video_url: str = Field(min_length=1)


def _is_youtube_url(video_url: str) -> bool:
    normalized = video_url.strip().lower()
    return "youtube.com" in normalized or "youtu.be" in normalized


def _count_words(text: str) -> int:
    return len([part for part in text.split() if part.strip()])


def _preview_text(text: str, limit: int = 280) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: limit - 3].rstrip()}..."


def _build_timeline(initial_inputs: Dict[str, Any], final_state: Dict[str, Any]) -> List[Dict[str, str]]:
    transcript = (final_state.get("transcript") or "").strip()
    findings = final_state.get("compliance_results") or []
    errors = final_state.get("errors") or []
    video_metadata = final_state.get("video_metadata") or {}
    final_status = (final_state.get("final_status") or "UNKNOWN").upper()

    stages: List[Dict[str, str]] = [
        {
            "title": "Video URL received",
            "status": "success",
            "detail": initial_inputs["video_url"],
        }
    ]

    if errors and final_status == "FAIL" and not transcript:
        stages.append(
            {
                "title": "Workflow stopped during indexing",
                "status": "error",
                "detail": "; ".join(errors),
            }
        )
        return stages

    stages.extend(
        [
            {
                "title": "Video downloaded",
                "status": "success" if video_metadata.get("source") else "warning",
                "detail": "YouTube media was downloaded and prepared for analysis."
                if video_metadata.get("source")
                else "The workflow did not return a media source URL.",
            },
            {
                "title": "Video uploaded",
                "status": "success" if video_metadata.get("source") else "warning",
                "detail": video_metadata.get("source", "No public storage URL was returned."),
            },
            {
                "title": "Transcript extracted",
                "status": "success" if transcript else "warning",
                "detail": (
                    f"{_count_words(transcript)} words captured from the audio track."
                    if transcript
                    else "No transcript was produced, so downstream analysis had less context."
                ),
            },
            {
                "title": "Compliance analysis completed",
                "status": "success" if final_status == "PASS" else "warning" if final_status == "FAIL" else "info",
                "detail": (
                    f"{len(findings)} finding(s) returned. Final status: {final_status}."
                    if findings
                    else f"No findings were returned. Final status: {final_status}."
                ),
            },
        ]
    )

    if errors:
        stages.append(
            {
                "title": "Warnings captured",
                "status": "warning",
                "detail": "; ".join(errors),
            }
        )

    return stages


def _build_response(initial_inputs: Dict[str, Any], final_state: Dict[str, Any]) -> Dict[str, Any]:
    transcript = (final_state.get("transcript") or "").strip()
    findings = final_state.get("compliance_results") or []
    errors = final_state.get("errors") or []
    video_metadata = final_state.get("video_metadata") or {}
    final_status = (final_state.get("final_status") or "UNKNOWN").upper()
    final_report = final_state.get("final_report") or "No report was returned."

    return {
        "request": initial_inputs,
        "summary": {
            "video_id": initial_inputs["video_id"],
            "final_status": final_status,
            "final_report": final_report,
            "finding_count": len(findings),
            "has_transcript": bool(transcript),
            "transcript_words": _count_words(transcript),
            "source_url": video_metadata.get("source"),
            "platform": video_metadata.get("platform", "youtube"),
        },
        "timeline": _build_timeline(initial_inputs, final_state),
        "findings": findings,
        "transcript_preview": _preview_text(transcript),
        "errors": errors,
        "raw_state": final_state,
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/api/audit")
def audit_video(payload: AuditRequest) -> JSONResponse:
    video_url = payload.video_url.strip()
    if not _is_youtube_url(video_url):
        raise HTTPException(status_code=400, detail="Please provide a valid YouTube URL.")

    initial_inputs = {
        "video_url": video_url,
        "video_id": f"video_{uuid.uuid4().hex[:8]}",
        "compliance_results": [],
        "errors": [],
    }

    logger.info("Running audit for video url: %s", video_url)

    try:
        from backend.src.graph.workflow import app as workflow_app

        final_state = workflow_app.invoke(initial_inputs)
    except Exception as exc:
        logger.exception("Workflow execution failed")
        final_state = {
            "video_url": video_url,
            "video_id": initial_inputs["video_id"],
            "compliance_results": [],
            "errors": [str(exc)],
            "final_status": "FAIL",
            "final_report": "Workflow execution failed.",
            "video_metadata": {"platform": "youtube"},
            "transcript": "",
            "ocr_text": [],
        }

    return JSONResponse(_build_response(initial_inputs, final_state))


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
