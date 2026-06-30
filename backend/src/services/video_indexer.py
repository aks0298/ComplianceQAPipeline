import logging
import os
import uuid
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
import yt_dlp
from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer

try:
    from supabase import create_client
except ImportError:  # pragma: no cover - optional dependency
    create_client = None

logger = logging.getLogger("video-indexer")


class VideoIndexerService:
    def __init__(self):
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
        self.supabase_bucket = os.getenv("SUPABASE_BUCKET", "videos")
        self.supabase_client = None
        if self.supabase_url and self.supabase_key and create_client:
            self.supabase_client = create_client(self.supabase_url, self.supabase_key)

        self.qdrant_url = os.getenv("QDRANT_URL")
        self.qdrant_api_key = os.getenv("QDRANT_API_KEY")
        self.qdrant_collection = os.getenv("QDRANT_COLLECTION_NAME", "compliance-documents")
        self.qdrant_client = None
        if self.qdrant_url:
            self.qdrant_client = QdrantClient(url=self.qdrant_url, api_key=self.qdrant_api_key)
            self._ensure_collection_exists()

        self.embedding_model = self._init_embedding_model()
        self.deepgram_api_key = os.getenv("DEEPGRAM_API_KEY")
        self.deepgram_model = os.getenv("DEEPGRAM_MODEL", "nova-2")

    def _init_embedding_model(self) -> Optional[SentenceTransformer]:
        try:
            return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        except Exception as exc:  # pragma: no cover - depends on model download
            logger.warning("Embedding model is unavailable: %s", exc)
            return None

    def _ensure_collection_exists(self) -> None:
        if not self.qdrant_client:
            return
        try:
            collections = self.qdrant_client.get_collections().collections
            existing_names = {collection.name for collection in collections}
            if self.qdrant_collection not in existing_names:
                self.qdrant_client.create_collection(
                    collection_name=self.qdrant_collection,
                    vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE),
                )
        except Exception as exc:  # pragma: no cover - external service dependency
            logger.warning("Qdrant collection setup skipped: %s", exc)

    def download_youtube_video(self, url: str, output_path: str = "temp_video.mp4") -> str:
        """Downloads a YouTube video to a local file."""
        logger.info("Downloading YouTube video: %s", url)

        ydl_opts = {
            "format": "best",
            "outtmpl": output_path,
            "quiet": False,
            "no_warnings": False,
            "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            logger.info("Download complete.")
            return output_path
        except Exception as exc:
            raise Exception(f"YouTube download failed: {exc}") from exc

    def upload_video(self, video_path: str, file_name: Optional[str] = None, video_name: Optional[str] = None) -> str:
        """Uploads a local file to Supabase Storage and returns its public URL."""
        if not self.supabase_client:
            raise RuntimeError("Supabase client is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")

        target_name = file_name or video_name or os.path.basename(video_path)
        logger.info("Uploading file %s to Supabase storage", video_path)

        with open(video_path, "rb") as video_file:
            self.supabase_client.storage.from_(self.supabase_bucket).upload(
                target_name,
                video_file,
                file_options={"content-type": "video/mp4"},
            )

        return self.supabase_client.storage.from_(self.supabase_bucket).get_public_url(target_name)

    def extract_video_insights(self, storage_path: str) -> Dict[str, Any]:
        """Transcribes a video from Supabase storage using Deepgram and indexes the text in Qdrant."""
        if not storage_path:
            raise ValueError("A storage path or public URL is required")

        media_url = storage_path if self._is_url(storage_path) else self._resolve_public_url(storage_path)
        transcript = self._transcribe_with_deepgram(media_url)
        self._index_transcript_to_qdrant(transcript, {"source_url": media_url})

        return {
            "transcript": transcript,
            "ocr_text": [],
            "video_url": media_url,
            "video_metadata": {
                "duration": None,
                "platform": "youtube",
                "source": media_url,
            },
        }

    def extract_data(self, raw_insights: Dict[str, Any]) -> Dict[str, Any]:
        """Parses the insights into the state payload expected by the graph."""
        metadata = raw_insights.get("video_metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}

        return {
            "transcript": raw_insights.get("transcript", ""),
            "ocr_text": raw_insights.get("ocr_text", []),
            "video_metadata": {
                **metadata,
                "platform": metadata.get("platform", "youtube"),
                "source": raw_insights.get("video_url") or metadata.get("source"),
            },
        }

    def _resolve_public_url(self, storage_path: str) -> str:
        if not self.supabase_client:
            return storage_path
        return self.supabase_client.storage.from_(self.supabase_bucket).get_public_url(storage_path)

    def _is_url(self, value: str) -> bool:
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"}

    def _transcribe_with_deepgram(self, media_url: str) -> str:
        if not self.deepgram_api_key:
            logger.warning("DEEPGRAM_API_KEY is not configured. Returning an empty transcript.")
            return ""

        try:
            response = requests.post(
                "https://api.deepgram.com/v1/listen",
                headers={"Authorization": f"Token {self.deepgram_api_key}"},
                json={"url": media_url, "model": self.deepgram_model},
                timeout=180,
            )
            response.raise_for_status()
            payload = response.json()
            channels = payload.get("results", {}).get("channels", [])
            if not channels:
                return ""
            alternatives = channels[0].get("alternatives", [])
            if not alternatives:
                return ""
            return alternatives[0].get("transcript", "").strip()
        except requests.RequestException as exc:
            logger.warning("Deepgram transcription failed: %s", exc)
            return ""

    def _index_transcript_to_qdrant(self, transcript: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        if not transcript or not self.qdrant_client or not self.embedding_model:
            return

        chunks = self._chunk_text(transcript)
        if not chunks:
            return

        vectors = self.embedding_model.encode(chunks, convert_to_numpy=True, normalize_embeddings=True)
        points = []
        for index, chunk in enumerate(chunks):
            points.append(
                models.PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vectors[index].tolist(),
                    payload={
                        "text": chunk,
                        "source": metadata or {},
                    },
                )
            )

        self.qdrant_client.upsert(collection_name=self.qdrant_collection, points=points)

    def _chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        if not text:
            return []

        words = text.split()
        if len(words) <= chunk_size:
            return [text]

        chunks: List[str] = []
        start = 0
        while start < len(words):
            end = min(start + chunk_size, len(words))
            chunk = " ".join(words[start:end])
            chunks.append(chunk)
            if end == len(words):
                break
            start = max(0, end - overlap)
        return chunks