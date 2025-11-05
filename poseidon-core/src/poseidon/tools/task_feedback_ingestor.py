import os
import json
import logging
from pathlib import Path
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

DEFAULT_JSONL_PATH = Path("poseidon-cda/data/task_responses.jsonl")
VECTORSTORE_DIR = Path("poseidon-cda/vectorstores/task_feedback")
VECTORSTORE_DIR.parent.mkdir(parents=True, exist_ok=True)

def ingest_feedback(jsonl_path=DEFAULT_JSONL_PATH):
    if not jsonl_path.exists():
        logger.warning(f"⚠️ No response file found at {jsonl_path}")
        return

    logger.info("📥 Loading task response logs...")
    docs = []
    with jsonl_path.open() as f:
        for line in f:
            try:
                data = json.loads(line)
                if data.get("response"):
                    docs.append(data)
            except json.JSONDecodeError:
                logger.warning("⚠️ Skipping malformed line in JSONL file.")

    if not docs:
        logger.warning("⚠️ No valid documents to ingest.")
        return

    texts = [
        f"On {d['timestamp']}, {d['sender']} responded to '{d['subject']}' with: {d['response']}"
        for d in docs
    ]
    logger.info(f"🧠 Building embeddings for {len(texts)} responses...")

    try:
        embeddings = OpenAIEmbeddings()
        db = FAISS.from_texts(texts, embeddings)
        db.save_local(str(VECTORSTORE_DIR))
        logger.info(f"✅ Vector store saved to {VECTORSTORE_DIR}")
    except Exception as e:
        logger.exception(f"❌ Failed to build vector store: {e}")

if __name__ == "__main__":
    ingest_feedback()
