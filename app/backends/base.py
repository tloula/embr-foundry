"""Backend abstraction and factory.

Defines the :class:`ChatBackend` interface that the web layer talks to, plus a
:func:`get_backend` factory that selects a concrete implementation based on the
``CHAT_BACKEND`` environment variable.

Add a new backend by:
  1. Implementing :class:`ChatBackend` in a new module under ``app/backends``.
  2. Registering it in :data:`_BACKENDS` below.
"""

from __future__ import annotations

import os
from typing import Protocol, runtime_checkable

# A chat message is a simple role/content dict, e.g.
#   {"role": "user", "content": "hello"}
Message = dict[str, str]


class BackendError(RuntimeError):
    """Raised when a backend is misconfigured or a request fails.

    The web layer turns this into a readable HTTP error rather than a 500, so
    that the app (and its env-var dump) stays usable even when AI credentials
    are absent.
    """


@runtime_checkable
class ChatBackend(Protocol):
    """Minimal interface every chat backend must implement."""

    #: Human-readable backend name, surfaced in the UI/diagnostics.
    name: str

    def chat(self, messages: list[Message]) -> str:
        """Return the assistant's reply for the given conversation."""
        ...


def get_backend(name: str | None = None) -> ChatBackend:
    """Return a chat backend instance.

    Selection order: explicit ``name`` argument, else the ``CHAT_BACKEND``
    environment variable, else ``"completions"``.
    """
    selected = (name or os.environ.get("CHAT_BACKEND") or "completions").strip().lower()

    factory = _BACKENDS.get(selected)
    if factory is None:
        valid = ", ".join(sorted(_BACKENDS))
        raise BackendError(
            f"Unknown CHAT_BACKEND '{selected}'. Valid options: {valid}."
        )
    return factory()


def _make_completions_backend() -> ChatBackend:
    # Imported lazily so a missing/optional backend dependency never breaks
    # app startup or the env-var dump.
    from .completions import ChatCompletionsBackend

    return ChatCompletionsBackend()


def _make_agent_backend() -> ChatBackend:
    from .agent import AgentBackend

    return AgentBackend()


#: Registry of available backends keyed by ``CHAT_BACKEND`` value.
_BACKENDS: dict[str, callable] = {
    "completions": _make_completions_backend,
    "agent": _make_agent_backend,
}
