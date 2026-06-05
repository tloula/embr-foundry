"""Agent backend (FUTURE - not implemented yet).

This is an intentional stub that documents the seam for a future Azure AI
Projects agent backend. It implements the :class:`ChatBackend` interface but
raises :class:`NotImplementedError` from :meth:`chat`.

When ready to implement, add ``azure-ai-projects`` and ``azure-identity`` to the
project dependencies and flesh out the methods below. The intended shape is::

    from azure.ai.projects import AIProjectClient
    from azure.identity import ManagedIdentityCredential

    project_client = AIProjectClient(
        endpoint=os.environ["SUPPORT_AI_ENDPOINT"],
        credential=ManagedIdentityCredential(
            client_id=os.environ["SUPPORT_AI_IDENTITY_CLIENT_ID"],
        ),
    )
    agent = project_client.agents.get_agent(
        agent_id=os.environ["SUPPORT_AI_AGENT_ID"],
    )
    # ... create thread, post message, run agent, return reply ...

Reserved environment variables:
  - SUPPORT_AI_ENDPOINT
  - SUPPORT_AI_IDENTITY_CLIENT_ID
  - SUPPORT_AI_AGENT_ID
"""

from __future__ import annotations

from .base import Message


class AgentBackend:
    """Placeholder for the future Azure AI Projects agent backend."""

    name = "agent"

    def chat(self, messages: list[Message]) -> str:
        raise NotImplementedError(
            "The agent backend is not implemented yet. Set CHAT_BACKEND=completions, "
            "or implement AgentBackend using azure-ai-projects + azure-identity."
        )
