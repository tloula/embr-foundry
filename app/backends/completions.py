"""Completions backend using azure-ai-inference.

Wraps :class:`azure.ai.inference.ChatCompletionsClient` with key-based auth.
Configuration comes entirely from environment variables, and the underlying
client is constructed lazily on first use so that missing credentials surface
as a readable error instead of breaking app startup.
"""

from __future__ import annotations

import os

from .base import BackendError, Message, resolve_api_version


class ChatCompletionsBackend:
    """Chat backend backed by an Azure AI Inference completions endpoint."""

    name = "completions"

    def __init__(self) -> None:
        self._client = None  # built lazily in _get_client()

    def _get_client(self):
        if self._client is not None:
            return self._client

        endpoint = os.environ.get("CHAT_AI_ENDPOINT")
        api_key = os.environ.get("CHAT_AI_API_KEY")
        missing = [
            name
            for name, value in (("CHAT_AI_ENDPOINT", endpoint), ("CHAT_AI_API_KEY", api_key))
            if not value
        ]
        if missing:
            raise BackendError(
                "Completions backend is not configured. Missing env vars: "
                + ", ".join(missing)
            )

        # Imported here so the dependency is only required when the backend runs.
        from azure.ai.inference import ChatCompletionsClient
        from azure.core.credentials import AzureKeyCredential

        # The OpenAI-compatible /openai/v1 route requires api-version=preview;
        # other routes use the SDK default. An explicit override always wins.
        client_kwargs = {}
        api_version = resolve_api_version(endpoint, os.environ.get("CHAT_AI_API_VERSION"))
        if api_version:
            client_kwargs["api_version"] = api_version

        self._client = ChatCompletionsClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(api_key),
            **client_kwargs,
        )
        return self._client

    def chat(self, messages: list[Message]) -> str:
        model = os.environ.get("CHAT_AI_MODEL")
        if not model:
            raise BackendError(
                "Completions backend is not configured. Missing env var: CHAT_AI_MODEL"
            )

        client = self._get_client()
        try:
            response = client.complete(model=model, messages=messages)
        except Exception as exc:  # noqa: BLE001 - surface as readable error
            raise BackendError(f"Chat request failed: {exc}") from exc

        try:
            return response.choices[0].message.content or ""
        except (AttributeError, IndexError) as exc:
            raise BackendError(f"Unexpected response shape: {exc}") from exc
