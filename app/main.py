"""FastAPI app: single chat page, env-var dump, and a chat API.

The web layer depends only on the :class:`ChatBackend` interface; the concrete
backend is selected via the ``CHAT_BACKEND`` environment variable.

NOTE: ``/api/env`` returns ALL environment variables (values included). This is
intentionally insecure and exists only to validate env-var injection on a new
PaaS platform. Do not deploy this to a real/production environment.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from .backends import BackendError, get_backend
from .backends.base import Message

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="embr-foundry", version="0.1.0")


class ChatRequest(BaseModel):
    message: str
    # Optional prior turns; each item is {"role": ..., "content": ...}.
    history: list[Message] = []


@app.get("/")
def root() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/env")
def list_env() -> JSONResponse:
    """Return all environment variables.

    Intentionally exposes values for platform injection testing only.
    """
    env = dict(sorted(os.environ.items()))
    return JSONResponse({"backend": os.environ.get("CHAT_BACKEND", "completions"), "env": env})


@app.post("/api/chat")
def chat(req: ChatRequest) -> JSONResponse:
    messages: list[Message] = [*req.history, {"role": "user", "content": req.message}]
    try:
        backend = get_backend()
        reply = backend.chat(messages)
    except BackendError as exc:
        return JSONResponse({"error": str(exc)}, status_code=503)
    except NotImplementedError as exc:
        return JSONResponse({"error": str(exc)}, status_code=501)
    return JSONResponse({"reply": reply})


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
