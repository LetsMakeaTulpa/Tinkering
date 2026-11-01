"""Turn raw bytes into clean markdown an LLM can read, plus metadata."""

import io

import trafilatura


def extract(body: bytes, content_type: str, url: str) -> tuple[str, str, dict]:
    """Return (title, markdown, meta)."""
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct == "application/pdf" or body[:5] == b"%PDF-":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(body))
        pages = [f"<!-- page {i + 1} -->\n{p.extract_text() or ''}" for i, p in enumerate(reader.pages)]
        info = reader.metadata or {}
        return (info.get("/Title") or "").strip(), "\n\n".join(pages), {"pages": len(reader.pages), "format": "pdf"}
    text = body.decode("utf-8", errors="replace")
    if ct.startswith("text/html") or "<html" in text[:2000].lower():
        md = trafilatura.extract(text, url=url, output_format="markdown", include_links=True, include_tables=True,
                                 favor_recall=True) or ""
        meta_obj = trafilatura.extract_metadata(text, default_url=url)
        meta = {}
        if meta_obj:
            meta = {k: v for k, v in {"author": meta_obj.author, "date": meta_obj.date, "sitename": meta_obj.sitename,
                                      "description": meta_obj.description}.items() if v}
        title = (meta_obj.title if meta_obj else "") or ""
        return title, md, {**meta, "format": "html"}
    return "", text, {"format": ct or "text"}
