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
empty 200). They must be reached via an Azure OpenAI route. This backend accepts
whatever shape the platform injects:

  - ``<resource>/openai/v1``                      OpenAI-compatible route (model in
                                                   body; requires api-version=preview)
  - ``<resource>/openai/deployments/<name>``      classic AOAI route (model in path)
  - ``<resource>/models`` or bare resource base   derived to ``/openai/deployments/<model>``

Environment variables:
  - EMBED_AI_ENDPOINT      resource endpoint in any of the shapes above
  - EMBED_AI_API_KEY       API key
  - EMBED_AI_MODEL         embedding deployment name (e.g. text-embedding-3-small)
  - EMBED_AI_API_VERSION   optional API version override (defaults to ``preview``
                           for ``/openai/v1`` endpoints)
"""

from __future__ import annotations

import os

from .base import BackendError, resolve_api_version


def _resolve_embeddings_endpoint(raw: str, model: str | None) -> tuple[str, bool]:
    """Return ``(endpoint, send_model_in_body)`` for the configured value.

    ``send_model_in_body`` is True only for the OpenAI-compatible ``/openai/v1``
    route, which identifies the deployment via the request body; the classic
    ``/openai/deployments/<name>`` routes carry it in the URL path. The SDK
    appends ``/embeddings`` to whatever endpoint it is given.
    """
    base = raw.rstrip("/")
    # OpenAI-compatible v1 route -> deployment is named in the request body.
    if "/openai/v1" in base:
        if not model:
            raise BackendError(
                "Embeddings backend is not configured. Missing env var: EMBED_AI_MODEL"
            )
        return base, True
    # Already a full classic deployment path -> use as-is (model in path).
    if "/openai/deployments/" in base:
        return base, False
    # Strip the unified inference suffix to get the bare resource base.
    if base.endswith("/models"):
        base = base[: -len("/models")]
    if not model:
        raise BackendError(
            "Embeddings backend is not configured. Missing env var: EMBED_AI_MODEL"
        )
    return f"{base}/openai/deployments/{model}", False


class EmbeddingsBackend:
    """Embeddings backend backed by an Azure AI Inference embeddings endpoint."""

    name = "embeddings"

    def __init__(self) -> None:
        self._client = None  # built lazily in _get_client()
        self._send_model_in_body = False

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
        resolved_endpoint, self._send_model_in_body = _resolve_embeddings_endpoint(
            endpoint, model
        )

        # /openai/v1 endpoints require api-version=preview; others use the SDK
        # default. An explicit EMBED_AI_API_VERSION override always wins.
        client_kwargs = {}
        api_version = resolve_api_version(resolved_endpoint, os.environ.get("EMBED_AI_API_VERSION"))
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
        client = self._get_client()
        # The /openai/v1 route names the deployment in the body; classic routes
        # carry it in the URL path, so the model kwarg is omitted there.
        embed_kwargs: dict[str, object] = {"input": inputs}
        if self._send_model_in_body:
            embed_kwargs["model"] = os.environ.get("EMBED_AI_MODEL")
        try:
            response = client.embed(**embed_kwargs)
        except Exception as exc:  # noqa: BLE001 - surface as readable error
            raise BackendError(f"Embedding request failed: {exc}") from exc

        try:
            ordered = sorted(response.data, key=lambda item: item.index)
            return [list(item.embedding) for item in ordered]
        except (AttributeError, TypeError) as exc:
            raise BackendError(f"Unexpected response shape: {exc}") from exc
