# src/utils/cache.py
import os
import sqlite3
import json
from datetime import datetime, timedelta


DEFAULT_CACHE_DIR = os.environ.get(
    "POSEIDON_CACHE_DIR",
    os.path.join(os.environ.get("POSEIDON_ROOT", "/opt/poseidon"), "poseidon-cda/data/cache"),
)
DEFAULT_DB_PATH = os.path.join(DEFAULT_CACHE_DIR, "conversation_cache.db")


class ConversationCache:
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    prompt TEXT,
                    response TEXT,
                    timestamp TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS query_cache (
                    key TEXT PRIMARY KEY,
                    result TEXT,
                    timestamp TEXT
                )
            """)
            conn.commit()

    # --- Conversation methods ---
    def add_entry(self, session_id: str, prompt: str, response: dict):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO conversations (session_id, prompt, response, timestamp) VALUES (?, ?, ?, ?)",
                (session_id, prompt, json.dumps(response), datetime.now().isoformat())
            )
            conn.commit()

    def get_history(self, session_id: str, time_window_hours: int = 24) -> list:
        cutoff = (datetime.now() - timedelta(hours=time_window_hours)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT prompt, response FROM conversations WHERE session_id = ? AND timestamp >= ? ORDER BY timestamp",
                (session_id, cutoff)
            )
            return [{"prompt": row[0], "response": json.loads(row[1])} for row in cursor.fetchall()]

    def clear_old_entries(self, days_old: int = 7):
        cutoff = (datetime.now() - timedelta(days=days_old)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM conversations WHERE timestamp < ?", (cutoff,))
            conn.commit()

    # --- Query cache methods ---
    def cache_query(self, query_key: str, result: dict):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO query_cache (key, result, timestamp) VALUES (?, ?, ?)",
                (query_key, json.dumps(result), datetime.now().isoformat())
            )
            conn.commit()

    def get_query(self, query_key: str) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT result FROM query_cache WHERE key = ?", (query_key,))
            result = cursor.fetchone()
            return json.loads(result[0]) if result else None
