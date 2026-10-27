import json
import os
import re
import time
import uuid

import requests
from flask import (
    Blueprint,
    Response,
    jsonify,
    request,
    send_from_directory,
    stream_with_context,
)

from . import db

FEATHERLESS_BASE = "https://api.featherless.ai/v1"
MAX_BODY = 10 * 1024 * 1024

api = Blueprint("api", __name__, url_prefix="/api")


def _featherless_key():
    return os.environ.get("FEATHERLESS_API_KEY", "") or db.get_setting("api_key") or ""


def _featherless_headers():
    key = _featherless_key()
    if not key:
        return None
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


# ---------- settings ----------

@api.get("/settings")
def get_settings():
    return jsonify({"theme": db.get_setting("theme"), "models": db.get_setting("models")})


@api.post("/settings")
def save_settings():
    data = request.get_json(force=True)
    for key in ("theme", "models"):
        if key in data:
            db.set_setting(key, data[key])
    if "api_key" in data:
        if data["api_key"]:
            db.set_setting("api_key", data["api_key"])
        else:
            db.delete_setting("api_key")
    return jsonify({"ok": True, "api_key_set": bool(_featherless_key())})


@api.get("/status")
def status():
    return jsonify({"api_key_set": bool(_featherless_key())})


# ---------- models ----------

@api.get("/models")
def list_models():
    headers = _featherless_headers()
    if not headers:
        return jsonify({"error": "no_api_key"}), 401
    try:
        r = requests.get(f"{FEATHERLESS_BASE}/models", headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()
        models = [
            m["id"] for m in data.get("data", []) if isinstance(m, dict) and m.get("id")
        ]
        return jsonify({"models": sorted(models)})
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 502


# ---------- chats ----------

@api.get("/chats")
def chats_index():
    archived = request.args.get("archived")
    if archived is not None:
        archived = archived.lower() in ("1", "true", "yes")
    return jsonify(db.list_chats(archived))


@api.post("/chats")
def chats_create():
    data = request.get_json(silent=True) or {}
    chat = db.create_chat(
        title=data.get("title") or "New chat",
        model=data.get("model") or "",
        system_prompt=data.get("system_prompt") or "",
    )
    return jsonify(chat), 201


@api.get("/chats/<chat_id>")
def chats_show(chat_id):
    chat = db.get_chat(chat_id)
    if not chat:
        return jsonify({"error": "not_found"}), 404
    chat["messages"] = db.list_messages(chat_id)
    return jsonify(chat)


@api.patch("/chats/<chat_id>")
def chats_update(chat_id):
    if not db.get_chat(chat_id):
        return jsonify({"error": "not_found"}), 404
    data = request.get_json(force=True)
    chat = db.update_chat(chat_id, **data)
    return jsonify(chat)


@api.delete("/chats/<chat_id>")
def chats_destroy(chat_id):
    db.delete_chat(chat_id)
    return jsonify({"ok": True})


# ---------- messages ----------

@api.post("/chats/<chat_id>/messages")
def messages_create(chat_id):
    if not db.get_chat(chat_id):
        return jsonify({"error": "not_found"}), 404
    data = request.get_json(force=True)
    msg = db.add_message(
        chat_id,
        data.get("role") or "user",
        data.get("content") or "",
        data.get("attachments") or [],
    )
    return jsonify(msg), 201


@api.delete("/messages/<msg_id>")
def messages_destroy(msg_id):
    db.delete_message(msg_id)
    return jsonify({"ok": True})


# ---------- share ----------

@api.post("/chats/<chat_id>/share")
def chats_share(chat_id):
    if not db.get_chat(chat_id):
        return jsonify({"error": "not_found"}), 404
    share_id = db.share_chat(chat_id)
    return jsonify({"share_id": share_id})


@api.delete("/chats/<chat_id>/share")
def chats_unshare(chat_id):
    db.unshare_chat(chat_id)
    return jsonify({"ok": True})


# ---------- files ----------

@api.post("/files")
def files_upload():
    if "file" not in request.files:
        return jsonify({"error": "no_file"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "no_file"}), 400
    f.seek(0, os.SEEK_END)
    size = f.tell()
    f.seek(0)
    if size > MAX_BODY:
        return jsonify({"error": "too_large", "max": MAX_BODY}), 413
    file_id = uuid.uuid4().hex
    safe_ext = os.path.splitext(f.filename)[1][:16]
    stored_name = file_id + safe_ext
    os.makedirs(db.UPLOAD_DIR, exist_ok=True)
    f.save(os.path.join(db.UPLOAD_DIR, stored_name))
    attachment = {
        "id": file_id,
        "name": f.filename,
        "size": size,
        "mime": f.mimetype or "application/octet-stream",
    }
    return jsonify(attachment), 201


@api.get("/files/<file_id>/<name>")
def files_download(file_id, name):
    if not re.fullmatch(r"[0-9a-f]{32}(\.[A-Za-z0-9._-]{1,15})?", file_id):
        return jsonify({"error": "bad_id"}), 400
    matches = [fn for fn in os.listdir(db.UPLOAD_DIR) if fn.startswith(file_id)]
    if not matches:
        return jsonify({"error": "not_found"}), 404
    return send_from_directory(db.UPLOAD_DIR, matches[0], as_attachment=True)


# ---------- export / import ----------

@api.get("/export")
def export_all():
    payload = {
        "chats": db.list_chats(None),
        "messages": {c["id"]: db.list_messages(c["id"]) for c in db.list_chats(None)},
        "settings": {
            k: db.get_setting(k)
            for k in ("theme", "models")
        },
    }
    return Response(
        json.dumps(payload, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=chats-export.json"},
    )


@api.post("/import")
def import_all():
    data = request.get_json(force=True)
    if not isinstance(data, dict):
        return jsonify({"error": "bad_format"}), 400
    chats = data.get("chats", [])
    messages_by_chat = data.get("messages", {})
    imported = 0
    for c in chats:
        if not isinstance(c, dict):
            continue
        chat = db.create_chat(
            c.get("title") or "Imported chat",
            c.get("model") or "",
            c.get("system_prompt") or "",
        )
        for m in messages_by_chat.get(c.get("id"), []):
            if isinstance(m, dict) and m.get("role"):
                db.add_message(chat["id"], m["role"], m.get("content") or "", m.get("attachments") or [])
        imported += 1
    return jsonify({"imported": imported})


# ---------- completion (streaming proxy) ----------

@api.post("/chats/<chat_id>/complete")
def complete(chat_id):
    chat = db.get_chat(chat_id)
    if not chat:
        return jsonify({"error": "not_found"}), 404
    headers = _featherless_headers()
    if not headers:
        return jsonify({"error": "no_api_key"}), 401
    data = request.get_json(force=True)
    model = data.get("model") or chat["model"]
    if not model:
        return jsonify({"error": "no_model"}), 400
    if data.get("save_user_message"):
        db.add_message(chat_id, "user", data.get("user_content") or "", data.get("attachments") or [])
    history = [
        {"role": m["role"], "content": m["content"]} for m in db.list_messages(chat_id)
    ]
    payload = {
        "model": model,
        "messages": (
            ([{"role": "system", "content": chat["system_prompt"]}] if chat["system_prompt"] else [])
            + history
        ),
        "stream": True,
        "temperature": data.get("temperature", 0.7),
        "max_tokens": data.get("max_tokens", 2048),
    }
    db.update_chat(chat_id, model=model)

    upstream = requests.post(
        f"{FEATHERLESS_BASE}/chat/completions",
        headers=headers,
        json=payload,
        stream=True,
        timeout=(10, 120),
    )
    if upstream.status_code != 200:
        body = upstream.text[:500]
        return Response(json.dumps({"error": body}), status=502, mimetype="application/json")

    full_text = []
    chat_id_ref = chat_id
    model_ref = model

    def generate():
        try:
            for line in upstream.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue
                chunk_data = line[5:].strip()
                if chunk_data == "[DONE]":
                    break
                try:
                    chunk = json.loads(chunk_data)
                except json.JSONDecodeError:
                    continue
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                token = delta.get("content") or ""
                if token:
                    full_text.append(token)
                yield f"data: {json.dumps({'token': token})}\n\n"
            yield "data: [DONE]\n\n"
        finally:
            upstream.close()
            text = "".join(full_text)
            if text:
                assistant = db.add_message(chat_id_ref, "assistant", text)
                emit = json.dumps({"final": {"id": assistant["id"], "content": text, "model": model_ref}})
                yield f"data: {emit}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")
