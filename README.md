# Chatterless

A self-hosted AI chat app for your [Featherless.ai](https://featherless.ai) models — a personal ChatGPT/Kimi/Claude-style interface you own, installable on Android as a PWA.

## Features

- **Chat with any Featherless model** — model list pulled live from the API, or enter custom model IDs
- **Streaming replies** — tokens appear live as the model generates
- **Markdown + code rendering** — GFM tables, syntax highlighting, copy buttons on code blocks
- **Saveable chats** — everything persisted in SQLite (auto-titled from your first message)
- **Archive & pin** — keep the sidebar clean, pin important chats
- **File uploads** — attach any file type (up to 10 MB per file) to messages
- **Shareable chats** — generate a read-only public link for any chat
- **Import/export** — download all chats as JSON, import them anywhere
- **Customizable** — dark/light theme, custom model list, per-chat system prompt & model
- **PWA** — install to your Android home screen, works like a native app
- **Server-side API key** — your Featherless key never reaches the browser

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
export FEATHERLESS_API_KEY="sk-..."   # or set it in Settings inside the app
.venv/bin/python app.py
```

Then open <http://localhost:5000>.

## Android access

1. Run the app on a host reachable from your phone (e.g. a Pi/VPS on your LAN, behind a reverse proxy with HTTPS).
2. Open the site in Chrome, tap **Install app** (or "Add to Home screen").
3. It launches fullscreen like a native app, and your chats sync across every device that points at the same server.

> The dev server binds to `127.0.0.1` only. Use a proper WSGI server (gunicorn/waitress) and a reverse proxy for real deployments, and put auth in front of it — anyone who can reach the app can use your API key.

## Data

Chats, messages, settings and uploaded files live in `data/` (`chat.db` + `uploads/`). Back up that folder to back up everything. Set `CHAT_DB` / `UPLOAD_DIR` env vars to relocate.

## Project layout

```
app.py               # Flask app factory + share route
chat_app/db.py       # SQLite storage layer
chat_app/api.py      # REST API + Featherless streaming proxy
templates/           # index.html (app), share.html (public view)
static/              # CSS, JS, PWA manifest, service worker, icon
```
