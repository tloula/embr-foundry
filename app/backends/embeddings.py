"""Text embeddings backend using azure-ai-inference.

Wraps :class:`azure.ai.inference.EmbeddingsClient` with key-based auth. Mirrors
the completions backend: configuration comes entirely from environment variables
and the underlying client is constructed lazily on first use, so missing
credentials surface as a readable error instead of breaking app startup.

This is a separate seam from :class:`ChatBackend` because embeddings have a
different shape (text in, vectors out) and are selected directly rather than via
``CHAT_BACKEND``.

Endpoint routing note: unlike chat completions, Azure OpenAI embedding
deployments are *not* served by the unified ``/models`` inference route on a
Foundry/AI Services resource (that route mistranslates the call and returns an
empty 200). They must be reached via the Azure OpenAI route
``<resource>/openai/deployments/<deployment>/embeddings``. To keep
``EMBED_AI_ENDPOINT`` symmetric with ``CHAT_AI_ENDPOINT`` (both pointing at the
same ``.../models`` base), this backend derives the correct embeddings URL from
the base endpoint plus the deployment name. A fully-qualified
``.../openai/deployments/<name>`` endpoint is also accepted as-is.

Environment variables:
  - EMBED_AI_ENDPOINT      resource endpoint (same ``.../models`` base as chat),
                           or a full ``.../openai/deployments/<name>`` URL
  - EMBED_AI_API_KEY       API key
  - EMBED_AI_MODEL         embedding deployment name (e.g. text-embedding-3-small)
  - EMBED_AI_API_VERSION   optional API version override
"""

from __future__ import annotations

import os

from .base import BackendError


def _resolve_embeddings_endpoint(raw: str, model: str | None) -> str:
    """Derive the Azure OpenAI embeddings endpoint from the configured value.

    Accepts either the shared ``.../models`` resource base (preferred, symmetric
    with chat) or a fully-qualified ``.../openai/deployments/<name>`` URL. The
    SDK appends ``/embeddings`` to whatever endpoint it is given.
    """
    base = raw.rstrip("/")
    # Already a full deployment path -> use as-is.
    if "/openai/deployments/" in base:
        return base
    # Strip the unified inference suffix to get the bare resource base.
    if base.endswith("/models"):
        base = base[: -len("/models")]
    if not model:
        raise BackendError(
            "Embeddings backend is not configured. Missing env var: EMBED_AI_MODEL"
        )
    return f"{base}/openai/deployments/{model}"


class EmbeddingsBackend:
    """Embeddings backend backed by an Azure AI Inference embeddings endpoint."""

    name = "embeddings"

    def __init__(self) -> None:
        self._client = None  # built lazily in _get_client()

    def _get_client(self):
        if self._client is not None:
            return self._client

        endpoint = os.environ.get("EMBED_AI_ENDPOINT")
        api_key = os.environ.get("EMBED_AI_API_KEY")
        missing = [
            name
            for name, value in (("EMBED_AI_ENDPOINT", endpoint), ("EMBED_AI_API_KEY", api_key))
            if not value
        ]
        if missing:
            raise BackendError(
                "Embeddings backend is not configured. Missing env vars: "
                + ", ".join(missing)
            )

        # Imported here so the dependency is only required when the backend runs.
        from azure.ai.inference import EmbeddingsClient
        from azure.core.credentials import AzureKeyCredential

        model = os.environ.get("EMBED_AI_MODEL")
        resolved_endpoint = _resolve_embeddings_endpoint(endpoint, model)

        # Optional override; if unset the SDK default api-version is used.
        client_kwargs = {}
        api_version = os.environ.get("EMBED_AI_API_VERSION")
        if api_version:
            client_kwargs["api_version"] = api_version

        self._client = EmbeddingsClient(
            endpoint=resolved_endpoint,
            credential=AzureKeyCredential(api_key),
            **client_kwargs,
        )
        return self._client

    def embed(self, inputs: list[str]) -> list[list[float]]:
        """Return one embedding vector per input string, in input order."""
        # The deployment is encoded in the resolved endpoint path, so the model
        # need not be sent in the request body.
        client = self._get_client()
        try:
            response = client.embed(input=inputs)
        except Exception as exc:  # noqa: BLE001 - surface as readable error
            raise BackendError(f"Embedding request failed: {exc}") from exc

        try:
            ordered = sorted(response.data, key=lambda item: item.index)
            return [list(item.embedding) for item in ordered]
        except (AttributeError, TypeError) as exc:
            raise BackendError(f"Unexpected response shape: {exc}") from exc
