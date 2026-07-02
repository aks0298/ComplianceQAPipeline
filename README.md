# Compliance QA Pipeline

A YouTube compliance audit app with a FastAPI backend and a chat-style JavaScript frontend.

## What it does

- Accepts a YouTube video URL from the user.
- Downloads and uploads the media when configured.
- Extracts transcript data and indexes it into Qdrant.
- Retrieves relevant rule snippets from Qdrant.
- Uses Gemini to return a structured compliance report.
- Presents the useful workflow states in a ChatGPT-like interface.

## Project layout

- `app.py` serves the FastAPI API and the static frontend.
- `frontend/index.html`, `frontend/styles.css`, and `frontend/app.js` implement the web UI.
- `main.py` runs the CLI simulation against the LangGraph workflow.
- `backend/src/graph/` contains the workflow and node logic.
- `backend/src/services/video_indexer.py` handles video download, upload, and transcription.
- `backend/scripts/index_documents.py` indexes the PDF rule documents into Qdrant.

## Required environment variables

- `GOOGLE_API_KEY`
- `QDRANT_URL`
- `QDRANT_API_KEY`
- `QDRANT_COLLECTION_NAME`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY` or `SUPABASE_ANON_KEY`
- `SUPABASE_BUCKET`
- `DEEPGRAM_API_KEY`
- `DEEPGRAM_MODEL`

If `DEEPGRAM_API_KEY` is missing, transcript extraction will return an empty transcript.
If Supabase is not configured, video upload will fail during the indexing step.

## Install

```bash
uv sync
```

If you are using a virtual environment manually, install the project dependencies with your preferred package manager and make sure the `.env` file is present at the project root.

## Index the rule documents

Before running the audit, index the PDFs in `backend/data` into Qdrant:

```bash
python backend/scripts/index_documents.py
```

## Run the web app

```bash
python app.py
```

Then open:

```bash
http://127.0.0.1:8000
```

## Run the CLI simulation

```bash
python main.py
```

## Notes

- The current workflow only supports YouTube URLs.
- The audit result is only as good as the indexed rule corpus in Qdrant.
- The frontend shows only the useful workflow states, not the noisy raw library logs.
