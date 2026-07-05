import os
import logging
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# 1. Resolve absolute paths for Cognee storage
app_dir = Path(__file__).parent.resolve()
backend_dir = app_dir.parent.resolve()

system_dir = backend_dir / ".cognee_system"
data_dir = backend_dir / ".cognee_data"

# 2. Configure Cognee environment variables BEFORE importing cognee
os.environ["ENABLE_BACKEND_ACCESS_CONTROL"] = "false"
os.environ["SYSTEM_ROOT_DIRECTORY"] = str(system_dir)
os.environ["DATA_ROOT_DIRECTORY"] = str(data_dir)
os.environ["COGNEE_SKIP_CONNECTION_TEST"] = "true"

from app.config import settings

# Configure LLM dynamically
if settings.LLM_PROVIDER == "ollama":
    os.environ["LLM_PROVIDER"] = "ollama"
    os.environ["LLM_MODEL"] = settings.OLLAMA_MODEL
    
    # Correctly format endpoint for Ollama OpenAI compatibility
    endpoint = settings.OLLAMA_API_URL
    if not endpoint.endswith("/v1"):
        endpoint = f"{endpoint.rstrip('/')}/v1"
    os.environ["LLM_ENDPOINT"] = endpoint
    os.environ["LLM_API_KEY"] = "ollama"
else:
    # Use Gemini
    os.environ["LLM_PROVIDER"] = "gemini"
    model = settings.GEMINI_MODEL
    if not model.startswith("gemini/"):
        model = f"gemini/{model}"
    os.environ["LLM_MODEL"] = model
    os.environ["LLM_API_KEY"] = settings.GEMINI_API_KEY
    os.environ["GEMINI_API_KEY"] = settings.GEMINI_API_KEY

# Use FastEmbed locally for embeddings to prevent Gemini 404/quota exceptions
os.environ["EMBEDDING_PROVIDER"] = "fastembed"
os.environ["EMBEDDING_MODEL"] = "BAAI/bge-small-en-v1.5"
os.environ["EMBEDDING_DIMENSIONS"] = "384"

# Now safely import cognee
import cognee
from cognee.modules.search.types import SearchType


async def init_cognee():
    """
    Initialize Cognee, making sure storage directories exist and migrations are applied.
    """
    logger.info("Initializing Cognee Knowledge Graph system...")
    try:
        system_dir.mkdir(parents=True, exist_ok=True)
        data_dir.mkdir(parents=True, exist_ok=True)
        # Create databases folder explicitly to prevent sqlite3 file open errors
        (system_dir / "databases").mkdir(parents=True, exist_ok=True)
        logger.info(f"Cognee system root resolved: {system_dir}")
        logger.info(f"Cognee data root resolved: {data_dir}")
        
        # Explicitly run database migrations
        logger.info("Running Cognee database migrations...")
        await cognee.run_migrations()
        logger.info("Cognee database migrations applied successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Cognee storage or run migrations: {e}", exc_info=True)


async def ingest_document_to_cognee(
    document_id: str,
    document_type: str,
    fields: List[Dict[str, Any]],
    raw_ocr_text: str
):
    """
    Ingest a document's structured fields and raw OCR text into the Cognee Knowledge Graph.
    """
    logger.info(f"[{document_id}] Ingesting document to Cognee knowledge graph...")
    try:
        # Reformat document details into a readable textual payload
        fields_str = "\n".join([f"- {f.get('name')}: {f.get('value')}" for f in fields])
        document_payload = (
            f"Document ID: {document_id}\n"
            f"Document Type: {document_type}\n"
            f"Extracted Structured Fields:\n{fields_str}\n"
            f"Raw OCR Text Snippet:\n{raw_ocr_text[:1500]}"
        )
        
        # Add to Cognee memory
        await cognee.add(document_payload)
        logger.info(f"[{document_id}] Added payload to Cognee. Running cognify...")
        
        # Build the knowledge graph
        await cognee.cognify()
        logger.info(f"[{document_id}] Cognee cognify complete. Graph constructed.")
    except Exception as e:
        logger.error(f"[{document_id}] Cognee ingestion failed: {e}", exc_info=True)


async def search_cognee_knowledge_graph(query_text: str) -> List[str]:
    """
    Search the Cognee Knowledge Graph for the given query text.
    """
    logger.info(f"Querying Cognee knowledge graph for: '{query_text}'")
    try:
        results = await cognee.search(
            query_text=query_text,
            query_type=SearchType.GRAPH_COMPLETION
        )
        logger.info(f"Cognee search returned {len(results)} results.")
        
        # Ensure result formats are serializable lists of strings
        serializable_results = []
        for res in results:
            if isinstance(res, dict):
                # If Cognee returns a dict containing an answer
                serializable_results.append(res.get("response", str(res)))
            elif hasattr(res, "response"):
                serializable_results.append(getattr(res, "response"))
            else:
                serializable_results.append(str(res))
        return serializable_results
    except Exception as e:
        logger.error(f"Cognee search failed: {e}", exc_info=True)
        return [f"Search error: {str(e)}"]
