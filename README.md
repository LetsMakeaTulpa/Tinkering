# Tinkering
Nope

## Flask Hello, World!

A minimal Flask web app that serves `Hello, World!` on the root URL (`/`).

### Run it

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
```

Then open <http://localhost:5000> — you should see `Hello, World!`.

The app binds to `0.0.0.0` and respects the `PORT` environment variable (defaults to `5000`).
