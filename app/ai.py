"""Tiny OpenAI-SDK wrappers over embr's injected Foundry endpoint.

embr binds a Foundry deployment and injects its OpenAI-compatible ``/openai/v1``
endpoint and API key as environment variables. That route is plain OpenAI, so a
client is just ``OpenAI(base_url=<endpoint>, api_key=<key>)`` — no api-version or
endpoint juggling — and the same client shape serves both chat and embeddings.

To add a Foundry *agent* backend later, swap in ``azure-ai-projects`` with a
``ManagedIdentityCredential`` (see README); the web layer only needs the two
functions below.
"""

from __future__ import annotations

import os
from functools import lru_cache

from openai import OpenAI

Message = dict[str, str]


@lru_cache(maxsize=None)
def _client(prefix: str) -> OpenAI:
    endpoint = os.environ.get(f"{prefix}_ENDPOINT")
    api_key = os.environ.get(f"{prefix}_API_KEY")
    if not endpoint or not api_key:
        raise RuntimeError(f"Missing {prefix}_ENDPOINT and/or {prefix}_API_KEY")
    return OpenAI(base_url=endpoint, api_key=api_key)


def chat(messages: list[Message]) -> str:
    """Return the assistant's reply for a conversation."""
    response = _client("CHAT_AI").chat.completions.create(
        model=os.environ["CHAT_AI_MODEL"],
        messages=messages,
    )
    return response.choices[0].message.content or ""


def embed(inputs: list[str]) -> list[list[float]]:
    """Return one embedding vector per input string, in input order."""
    response = _client("EMBED_AI").embeddings.create(
        model=os.environ["EMBED_AI_MODEL"],
        input=inputs,
    )
    return [item.embedding for item in response.data]
