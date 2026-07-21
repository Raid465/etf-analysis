import sqlite3
import json
import time
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "cache.db")
CACHE_TTL = 86400  # 24 hours


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cache (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            created_at REAL NOT NULL
        )
    """)
    conn.commit()
    return conn


def get(key: str):
    conn = get_connection()
    row = conn.execute("SELECT value, created_at FROM cache WHERE key = ?", (key,)).fetchone()
    conn.close()
    if row is None:
        return None
    value, created_at = row
    if time.time() - created_at > CACHE_TTL:
        delete(key)
        return None
    return json.loads(value)


def set(key: str, data):
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO cache (key, value, created_at) VALUES (?, ?, ?)",
        (key, json.dumps(data), time.time()),
    )
    conn.commit()
    conn.close()


def delete(key: str):
    conn = get_connection()
    conn.execute("DELETE FROM cache WHERE key = ?", (key,))
    conn.commit()
    conn.close()
