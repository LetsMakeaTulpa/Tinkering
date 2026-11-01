"""One function — `complete(task_type, messages)` — for every model call in the app.

It picks models from routes.yaml (or an explicit override), tries them in order until one works, and logs every
attempt to the model_calls table so you can see exactly which model said what, with which prompt.
"""

import time
from dataclasses import dataclass

import httpx
import yaml
from sqlalchemy.orm import Session

from ..config import settings
from ..models import ModelCall


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str
    call_id: str


class LLMError(Exception):
    pass


def _openai_compatible(provider: str) -> tuple[str, str] | None:
    return {
        "featherless": (settings.featherless_base_url, settings.featherless_api_key),
        "openrouter": ("https://openrouter.ai/api/v1", settings.openrouter_api_key),
        "openai": ("https://api.openai.com/v1", settings.openai_api_key),
        "ollama": (settings.ollama_base_url, "ollama"),
    }.get(provider)


def provider_ready(provider: str) -> bool:
    if provider == "anthropic":
        return bool(settings.anthropic_api_key)
    cfg = _openai_compatible(provider)
    return bool(cfg and cfg[0] and cfg[1])


def load_routes() -> dict:
    with open(settings.routes_file) as f:
        return yaml.safe_load(f)


def candidates(task_type: str, override: str | None = None) -> list[str]:
    if override:
        return [override]
    routes = load_routes()
    return routes.get("routes", {}).get(task_type) or routes.get("default", [])


async def _call(provider: str, model: str, messages: list[dict], params: dict) -> tuple[str, dict]:
    async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=15)) as client:
        if provider == "anthropic":
            system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
            body = {"model": model, "max_tokens": params.get("max_tokens", 4096),
                    "messages": [m for m in messages if m["role"] != "system"], **({"system": system} if system else {})}
            if "temperature" in params:
                body["temperature"] = params["temperature"]
            r = await client.post("https://api.anthropic.com/v1/messages", json=body,
                                  headers={"x-api-key": settings.anthropic_api_key, "anthropic-version": "2023-06-01"})
            r.raise_for_status()
            d = r.json()
            text = "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
            u = d.get("usage", {})
            return text, {"prompt_tokens": u.get("input_tokens"), "completion_tokens": u.get("output_tokens")}
        base, key = _openai_compatible(provider)
        r = await client.post(f"{base.rstrip('/')}/chat/completions",
                              json={"model": model, "messages": messages, **params},
                              headers={"Authorization": f"Bearer {key}"})
        if r.status_code >= 400:
            raise LLMError(f"{r.status_code}: {r.text[:500]}")
        d = r.json()
        u = d.get("usage") or {}
        return d["choices"][0]["message"].get("content") or "", u


async def complete(db: Session, task_type: str, messages: list[dict], *, project_id: str | None = None,
                   task_run_id: str | None = None, model: str | None = None, **params) -> LLMResult:
    errors = []
    for ref in candidates(task_type, model):
        provider, _, model_id = ref.partition(":")
        if not provider_ready(provider):
            errors.append(f"{ref}: provider not configured")
            continue
        started = time.monotonic()
        call = ModelCall(project_id=project_id, task_run_id=task_run_id, task_type=task_type, provider=provider,
                         model=model_id, messages=messages, params=params, status="ok")
        try:
            text, usage = await _call(provider, model_id, messages, params)
            call.response = text
            call.prompt_tokens, call.completion_tokens = usage.get("prompt_tokens"), usage.get("completion_tokens")
        except Exception as e:  # noqa: BLE001 — log and fall back to the next model
            call.status, call.error = "error", f"{type(e).__name__}: {e}"
            errors.append(f"{ref}: {call.error}")
        call.latency_ms = int((time.monotonic() - started) * 1000)
        db.add(call)
        db.commit()
        if call.status == "ok":
            return LLMResult(call.response, provider, model_id, call.id)
    raise LLMError("All models failed — " + " | ".join(errors))
