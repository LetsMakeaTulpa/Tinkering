import json
import os
import sqlite3
import time
import uuid

DB_PATH = os.environ.get("CHAT_DB", os.path.join(os.path.dirname(__file__), "..", "data", "chat.db"))
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.join(os.path.dirname(__file__), "..", "data", "uploads"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS chats (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT 'New chat',
    model TEXT NOT NULL DEFAULT '',
    system_prompt TEXT NOT NULL DEFAULT '',
    archived INTEGER NOT NULL DEFAULT 0,
    pinned INTEGER NOT NULL DEFAULT 0,
    share_id TEXT UNIQUE,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    chat_id TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    attachments TEXT NOT NULL DEFAULT '[]',
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_id);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def _connect():
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    with _connect() as conn:
        conn.executescript(SCHEMA)
        if get_setting("theme") is None:
            set_setting("theme", json.dumps("dark"))
        if get_setting("models") is None:
            set_setting("models", json.dumps([]))


def now():
    return time.time()


def new_id():
    return uuid.uuid4().hex


# ---------- settings ----------

def get_setting(key):
    with _connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return json.loads(row["value"]) if row else None


def set_setting(key, value):
    with _connect() as conn:
        conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, json.dumps(value)),
        )


def delete_setting(key):
    with _connect() as conn:
        conn.execute("DELETE FROM settings WHERE key = ?", (key,))


# ---------- chats ----------

def list_chats(archived=None):
    with _connect() as conn:
        if archived is None:
            rows = conn.execute(
                "SELECT * FROM chats ORDER BY pinned DESC, updated_at DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM chats WHERE archived = ? ORDER BY pinned DESC, updated_at DESC",
                (1 if archived else 0,),
            ).fetchall()
        return [_chat_dict(r) for r in rows]


def create_chat(title="New chat", model="", system_prompt=""):
    chat_id = new_id()
    ts = now()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO chats(id, title, model, system_prompt, created_at, updated_at) VALUES(?,?,?,?,?,?)",
            (chat_id, title, model, system_prompt, ts, ts),
        )
    return get_chat(chat_id)


def get_chat(chat_id):
    with _connect() as conn:
        row = conn.execute("SELECT * FROM chats WHERE id = ?", (chat_id,)).fetchone()
        return _chat_dict(row) if row else None


def update_chat(chat_id, **fields):
    allowed = {"title", "model", "system_prompt", "archived", "pinned"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return get_chat(chat_id)
    sets = ", ".join(f"{k} = ?" for k in updates)
    with _connect() as conn:
        conn.execute(
            f"UPDATE chats SET {sets}, updated_at = ? WHERE id = ?",
            (*updates.values(), now(), chat_id),
        )
    return get_chat(chat_id)


def touch_chat(chat_id):
    with _connect() as conn:
        conn.execute("UPDATE chats SET updated_at = ? WHERE id = ?", (now(), chat_id))


def delete_chat(chat_id):
    with _connect() as conn:
        conn.execute("DELETE FROM chats WHERE id = ?", (chat_id,))


# ---------- share ----------

def share_chat(chat_id):
    share_id = new_id()[:12]
    with _connect() as conn:
        conn.execute("UPDATE chats SET share_id = ? WHERE id = ?", (share_id, chat_id))
    return share_id


def unshare_chat(chat_id):
    with _connect() as conn:
        conn.execute("UPDATE chats SET share_id = NULL WHERE id = ?", (chat_id,))


def get_chat_by_share(share_id):
    with _connect() as conn:
        row = conn.execute("SELECT * FROM chats WHERE share_id = ?", (share_id,)).fetchone()
        return _chat_dict(row) if row else None


# ---------- messages ----------

def add_message(chat_id, role, content, attachments=None):
    msg_id = new_id()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO messages(id, chat_id, role, content, attachments, created_at) VALUES(?,?,?,?,?,?)",
            (msg_id, chat_id, role, content, json.dumps(attachments or []), now()),
        )
        conn.execute("UPDATE chats SET updated_at = ? WHERE id = ?", (now(), chat_id))
    return get_message(msg_id)


def get_message(msg_id):
    with _connect() as conn:
        row = conn.execute("SELECT * FROM messages WHERE id = ?", (msg_id,)).fetchone()
        return _msg_dict(row) if row else None


def list_messages(chat_id):
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM messages WHERE chat_id = ? ORDER BY created_at ASC", (chat_id,)
        ).fetchall()
        return [_msg_dict(r) for r in rows]


def update_message(msg_id, content=None, attachments=None):
    with _connect() as conn:
        if content is not None:
            conn.execute("UPDATE messages SET content = ? WHERE id = ?", (content, msg_id))
        if attachments is not None:
            conn.execute(
                "UPDATE messages SET attachments = ? WHERE id = ?",
                (json.dumps(attachments), msg_id),
            )


def delete_message(msg_id):
    with _connect() as conn:
        conn.execute("DELETE FROM messages WHERE id = ?", (msg_id,))


def _chat_dict(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "model": row["model"],
        "system_prompt": row["system_prompt"],
        "archived": bool(row["archived"]),
        "pinned": bool(row["pinned"]),
        "share_id": row["share_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _msg_dict(row):
    return {
        "id": row["id"],
        "chat_id": row["chat_id"],
        "role": row["role"],
        "content": row["content"],
        "attachments": json.loads(row["attachments"]),
        "created_at": row["created_at"],
    }
