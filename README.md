# Tinkering

## Featherless Chat

A self-hosted ChatGPT/Claude-style chat app for your [featherless.ai](https://featherless.ai) models. It installs on Android as an app (PWA) and keeps your chats on your own server, so your phone and computer see the same history.

### Features

- **Any Featherless model.** Searchable picker over the full model list, with favourites, or type any model id. Works with any OpenAI-compatible API (OpenRouter, a local llama.cpp/vLLM server, etc.) by changing the base URL.
- **Streaming replies** with a Stop button, Markdown, code highlighting with copy buttons, and collapsible reasoning for `<think>` models such as DeepSeek-R1 and QwQ.
- **Message tools.** Edit and resend, regenerate (keeps every version, switch with ‹ ›), fork a chat from any message, delete, copy.
- **Saved chats.** Every chat is saved automatically. You can search titles and contents, rename, pin, move to folders, **archive**, and delete.
- **File uploads (any type).**
  - Text and code files, PDF and DOCX: the text is extracted and sent to the model.
  - Images: sent in the standard OpenAI image format. Only vision-capable models can read them, and I haven't confirmed which Featherless models (if any) accept images.
  - Anything else: stored and downloadable, but the model only sees its name and type, and the app tells you so.
  - Add files with the 📎 button, by pasting, or by drag-and-drop.
- **Per-chat settings.** System prompt, temperature, top-p, top-k, min-p, max tokens, repetition/presence/frequency penalties, seed, stop sequences, a cap on how many past messages are sent, and raw extra request JSON.
- **Presets.** Save a system prompt, model and settings as a reusable assistant (similar to custom GPTs or Claude Projects). Start new chats from it, or make your current settings the default for new chats.
- **Customisation.** Theme, accent colour, font, font size, chat width, greeting, Enter-key behaviour, title style (first words or AI-generated), show or hide reasoning, and a **custom CSS** box to restyle anything.
- **Share and export.** Public read-only share links (can be revoked), export a chat as Markdown or JSON, back up everything, and import.
- **Android.** Installs to the home screen and runs full-screen. The back button closes menus and dialogs instead of leaving the app. The app appears in Android's share sheet, so text shared to it opens as a new message.

### Run it locally

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
APP_PASSWORD=choose-one FEATHERLESS_API_KEY=your-key .venv/bin/python app.py
```

Open <http://localhost:5000>. You can also skip `FEATHERLESS_API_KEY` and paste the key in **Settings** instead.

### Use it on your Android phone

The phone needs to reach the server. Pick one of these:

1. **Your own PC plus [Tailscale](https://tailscale.com)** (free and private). Install Tailscale on the PC and the phone, run the app on the PC, then open `http://<pc-tailscale-name>:5000` on the phone.
2. **A cloud host** such as Render, Railway, Fly.io or a VPS, using the included `Dockerfile`:
   - Mount a persistent volume at `/data`, or you will lose your chats on every redeploy.
   - Set `APP_PASSWORD`. Set `COOKIE_SECURE=1` if the host serves HTTPS (they all do).

```bash
docker build -t featherless-chat .
docker run -p 8000:8000 -v fc-data:/data -e APP_PASSWORD=... -e FEATHERLESS_API_KEY=... featherless-chat
```

Then open the URL in **Chrome on Android** and tap **⋮ → Add to Home screen / Install app**. Installing needs HTTPS, or `localhost`. A plain `http://` Tailscale address still works in the browser, and Chrome's "Add to Home screen" gives you a shortcut. To get a full install over Tailscale, run `tailscale serve` to get an HTTPS address.

### Configuration

| Env var | Default | Purpose |
|---|---|---|
| `APP_PASSWORD` | *(none)* | Login password. **Set this if the app is reachable from outside your machine.** |
| `FEATHERLESS_API_KEY` | *(none)* | API key. A key set in Settings overrides this. |
| `FEATHERLESS_BASE_URL` | `https://api.featherless.ai/v1` | Any OpenAI-compatible endpoint. |
| `DATA_DIR` | `./data` | SQLite database and uploaded files. Back this up. |
| `COOKIE_SECURE` | off | Set to `1` when serving over HTTPS. |
| `MAX_UPLOAD_MB` | `50` | Upload size limit. |
| `SECRET_KEY` | auto-generated in `DATA_DIR` | Session signing key. |

### Notes and limits

- The app is single-user: one password, one set of chats.
- Images only work with vision-capable models. A text-only model will return an error.
- Featherless limits how many requests you can run at once, depending on your plan. Pressing Stop frees your slot immediately. AI-generated titles use one extra request per new chat; the default title style (first words) doesn't.
- A reply that is still streaming when you close the app on your phone is cut off at that point. Your own message is already saved.
- Share links are public to anyone who has the URL. They show the chat as it is now (later changes included) and hide reasoning.
