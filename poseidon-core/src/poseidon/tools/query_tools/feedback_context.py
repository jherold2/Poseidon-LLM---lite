import logging
from pathlib import Path
from typing import List, Optional

from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS

# --- Logging setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

VECTORSTORE_DIR = Path("vectorstores/task_feedback")

def load_feedback_db():
    """
    Load the FAISS vector store built by task_feedback_ingestor.py.
    Raises a clear error if not built yet.
    """
    if not VECTORSTORE_DIR.exists():
        raise FileNotFoundError(
            f"❌ Vector store not found at {VECTORSTORE_DIR}. "
            "Run task_feedback_ingestor.py first to build it."
        )
    logger.info(f"📂 Loading vector store from {VECTORSTORE_DIR}...")
    embeddings = OpenAIEmbeddings()
    return FAISS.load_local(str(VECTORSTORE_DIR), embeddings, allow_dangerous_deserialization=True)

def query_feedback_context(
    query: str,
    k: int = 5,
    filters: Optional[dict] = None
) -> List[dict]:
    """
    Query the task feedback vector store for contextually similar past responses.

    Args:
        query (str): The natural language query (e.g., "What did Alex say about dashboard tasks?")
        k (int): Number of top results to return
        filters (dict): Optional metadata filters (future-proofed if you store metadata in FAISS)

    Returns:
        List[dict]: A list of matched feedback entries with their text and similarity score
    """
    db = load_feedback_db()

    logger.info(f"🔎 Searching feedback store for: '{query}' (top {k})")
    results = db.similarity_search_with_score(query, k=k, filter=filters) if filters else db.similarity_search_with_score(query, k=k)

    parsed_results = []
    for doc, score in results:
        parsed_results.append({
            "score": float(score),
            "text": doc.page_content
        })
        logger.debug(f"💡 Match (score={score:.4f}): {doc.page_content[:120]}...")

    logger.info(f"✅ Retrieved {len(parsed_results)} contextual feedback records.")
    return parsed_results

if __name__ == "__main__":
    # Example usage
    examples = query_feedback_context("status updates on Q3 dashboard", k=3)
    for ex in examples:
        print(f"[Score: {ex['score']:.4f}] {ex['text']}\n")
