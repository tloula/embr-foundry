"""FastAPI app: a single chat page, a text-embeddings panel, and an env-var dump.

This is a deliberately minimal demo for validating environment-variable injection
on the embr PaaS platform. embr injects an OpenAI-compatible Foundry endpoint and
key, which :mod:`app.ai` turns into chat and embedding calls.

NOTE: ``/api/env`` returns ALL environment variables (values included). This is
intentionally insecure and exists only to validate env-var injection. Do not
deploy this to a real/production environment.
"""

from __future__ import annotations

import math
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from . import ai

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="embr-foundry", version="0.1.0")


class ChatRequest(BaseModel):
    message: str
    # Optional prior turns; each item is {"role": ..., "content": ...}.
    history: list[ai.Message] = []


class EmbedRequest(BaseModel):
    text: str
    # Optional second text; when present a cosine similarity is returned so the
    # embedding model can be sanity-checked with a single request.
    compare: str | None = None


@app.get("/")
def root() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/env")
def list_env() -> JSONResponse:
    """Return all environment variables (values included) for injection testing."""
    return JSONResponse({"env": dict(sorted(os.environ.items()))})


@app.post("/api/chat")
def chat(req: ChatRequest) -> JSONResponse:
    messages: list[ai.Message] = [*req.history, {"role": "user", "content": req.message}]
    try:
        return JSONResponse({"reply": ai.chat(messages)})
    except Exception as exc:  # noqa: BLE001 - surface as a readable error
        return JSONResponse({"error": str(exc)}, status_code=503)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


@app.post("/api/embed")
def embed(req: EmbedRequest) -> JSONResponse:
    """Embed text with the configured model; optionally compare two strings."""
    inputs = [req.text]
    compare = (req.compare or "").strip()
    if compare:
        inputs.append(compare)

    try:
        vectors = ai.embed(inputs)
    except Exception as exc:  # noqa: BLE001 - surface as a readable error
        return JSONResponse({"error": str(exc)}, status_code=503)

    primary = vectors[0]
    result: dict[str, object] = {
        "model": os.environ.get("EMBED_AI_MODEL"),
        "dimensions": len(primary),
        "norm": math.sqrt(sum(v * v for v in primary)),
        "preview": primary[:8],
    }
    if len(vectors) > 1:
        result["compareText"] = compare
        result["similarity"] = _cosine(primary, vectors[1])
    return JSONResponse(result)


@app.get("/health")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
