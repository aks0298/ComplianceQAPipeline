import glob
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from langchain_community.document_loaders import PyPDFLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

load_dotenv(override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger("indexer")


def index_docs():
    """
    Reads all PDF files from backend/data,
    splits them into chunks,
    generates embeddings,
    and indexes them into Qdrant.
    """

    current_dir = Path(__file__).resolve().parent
    data_folder = (current_dir / "../../backend/data").resolve()

    logger.info("=" * 60)
    logger.info("Environment Configuration Check:")
    logger.info(
        f"GOOGLE_API_KEY : {'Loaded' if os.getenv('GOOGLE_API_KEY') else 'Not Found'}"
    )
    logger.info(f"GEMINI_CHAT_MODEL : {os.getenv('GEMINI_CHAT_MODEL')}")
    logger.info(
        f"EMBEDDING_MODEL : {os.getenv('EMBEDDING_MODEL', 'sentence-transformers/all-MiniLM-L6-v2')}"
    )
    logger.info(f"QDRANT_URL : {os.getenv('QDRANT_URL')}")
    logger.info(f"QDRANT_COLLECTION_NAME : {os.getenv('QDRANT_COLLECTION_NAME')}")
    logger.info(f"SUPABASE_URL : {os.getenv('SUPABASE_URL')}")
    logger.info(f"SUPABASE_BUCKET_NAME : {os.getenv('SUPABASE_BUCKET_NAME')}")
    logger.info("=" * 60)

    required_env_vars = [
        "GOOGLE_API_KEY",
        "GEMINI_CHAT_MODEL",
        "EMBEDDING_MODEL",
        "QDRANT_URL",
        "QDRANT_API_KEY",
        "QDRANT_COLLECTION_NAME",
    ]

    missing = [var for var in required_env_vars if not os.getenv(var)]

    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}"
        )

    try:
        logger.info("Initializing embeddings...")

        embeddings = HuggingFaceEmbeddings(
            model_name=os.getenv(
                "EMBEDDING_MODEL",
                "sentence-transformers/all-MiniLM-L6-v2",
            )
        )

        logger.info("Connecting to Qdrant...")

        client = QdrantClient(
            url=os.getenv("QDRANT_URL"),
            api_key=os.getenv("QDRANT_API_KEY"),
        )

        collection_name = os.getenv("QDRANT_COLLECTION_NAME")

        existing = [
            c.name for c in client.get_collections().collections
        ]

        if collection_name not in existing:
            logger.info(
                f"Collection '{collection_name}' not found. Creating..."
            )

            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=384,
                    distance=Distance.COSINE,
                ),
            )

            logger.info("Collection created successfully.")

        vector_store = QdrantVectorStore(
            client=client,
            collection_name=collection_name,
            embedding=embeddings,
        )

        logger.info("Qdrant initialized successfully.")

    except Exception:
        logger.exception("Failed to initialize Qdrant.")
        raise

    pdf_files = glob.glob(str(data_folder / "*.pdf"))

    if not pdf_files:
        logger.warning(f"No PDF files found in {data_folder}")
        return

    logger.info(f"Found {len(pdf_files)} PDF files.")

    all_splits = []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=150,
    )

    for pdf in pdf_files:

        try:
            logger.info(f"Processing: {pdf}")

            loader = PyPDFLoader(pdf)
            docs = loader.load()

            splits = splitter.split_documents(docs)

            for split in splits:
                split.metadata["source"] = Path(pdf).name

            all_splits.extend(splits)

            logger.info(
                f"{Path(pdf).name} -> {len(splits)} chunks"
            )

        except Exception:
            logger.exception(f"Failed to process {pdf}")

    if not all_splits:
        logger.warning("No document chunks generated.")
        return

    logger.info("=" * 60)
    logger.info(f"Total chunks generated : {len(all_splits)}")
    logger.info(
        f"Uploading to collection : {collection_name}"
    )

    try:

        vector_store.add_documents(all_splits)

        logger.info("=" * 60)
        logger.info("Document indexing completed successfully.")
        logger.info(
            f"Indexed {len(all_splits)} chunks into '{collection_name}'."
        )
        logger.info("=" * 60)

    except Exception:
        logger.exception("Failed to upload documents to Qdrant.")
        raise


if __name__ == "__main__":
    index_docs()