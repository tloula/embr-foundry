"""Text embeddings backend using azure-ai-inference.

Wraps :class:`azure.ai.inference.EmbeddingsClient` with key-based auth. Mirrors
the completions backend: configuration comes entirely from environment variables
and the underlying client is constructed lazily on first use, so missing
credentials surface as a readable error instead of breaking app startup.

This is a separate seam from :class:`ChatBackend` because embeddings have a
different shape (text in, vectors out) and are selected directly rather than via
``CHAT_BACKEND``.

Environment variables:
  - EMBED_AI_ENDPOINT      models inference endpoint, ending in ``/models``
  - EMBED_AI_API_KEY       API key
  - EMBED_AI_MODEL         embedding model/deployment name
  - EMBED_AI_API_VERSION   optional API version override
"""

from __future__ import annotations

import os

from .base import BackendError


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

        # Optional override; if unset the SDK default is used (fine for /models).
        client_kwargs = {}
        api_version = os.environ.get("EMBED_AI_API_VERSION")
        if api_version:
            client_kwargs["api_version"] = api_version

        self._client = EmbeddingsClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(api_key),
            **client_kwargs,
        )
        return self._client

    def embed(self, inputs: list[str]) -> list[list[float]]:
        """Return one embedding vector per input string, in input order."""
        model = os.environ.get("EMBED_AI_MODEL")
        if not model:
            raise BackendError(
                "Embeddings backend is not configured. Missing env var: EMBED_AI_MODEL"
            )

        client = self._get_client()
        try:
            response = client.embed(model=model, input=inputs)
        except Exception as exc:  # noqa: BLE001 - surface as readable error
            raise BackendError(f"Embedding request failed: {exc}") from exc

        try:
            ordered = sorted(response.data, key=lambda item: item.index)
            return [list(item.embedding) for item in ordered]
        except (AttributeError, TypeError) as exc:
            raise BackendError(f"Unexpected response shape: {exc}") from exc
