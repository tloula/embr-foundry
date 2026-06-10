# embr-foundry

A deliberately minimal Python web app whose primary goal is to **prove environment-variable injection works on a new PaaS platform**. It has:

- A single root page with a simple chat UI backed by an LLM.
- A text-embeddings panel to validate an embedding model (vector dims + cosine similarity).
- An env-var dump in the UI (⚠ intentionally insecure — testing only).

## Stack

- [uv](https://docs.astral.sh/uv/) for project & dependency management
- FastAPI + uvicorn
- Plain HTML + vanilla JS frontend
- The official [`openai`](https://github.com/openai/openai-python) SDK, pointed at
  embr's injected OpenAI-compatible Foundry endpoint

## Environment variables

embr injects these from the bound Foundry deployment. The endpoint is the
OpenAI-compatible route (`.../openai/v1`), used as-is by the `openai` SDK — no
api-version, no endpoint juggling.

Chat:

| Var | Purpose |
| --- | --- |
| `CHAT_AI_ENDPOINT` | OpenAI-compatible endpoint, e.g. `https://<resource>.services.ai.azure.com/openai/v1` |
| `CHAT_AI_API_KEY` | API key |
| `CHAT_AI_MODEL` | Model/deployment name |

Embeddings (powers the **Text embeddings** panel):

| Var | Purpose |
| --- | --- |
| `EMBED_AI_ENDPOINT` | Same OpenAI-compatible endpoint shape as `CHAT_AI_ENDPOINT` |
| `EMBED_AI_API_KEY` | API key |
| `EMBED_AI_MODEL` | Embedding model/deployment name (e.g. `text-embedding-3-small`) |

Agent backend (**future, not implemented**):

| Var | Purpose |
| --- | --- |
| `SUPPORT_AI_ENDPOINT` | AI Projects endpoint |
| `SUPPORT_AI_IDENTITY_CLIENT_ID` | Managed identity client id |
| `SUPPORT_AI_AGENT_ID` | Agent id |

See [`.env.example`](.env.example).

## Run locally

```sh
uv sync

# Provide credentials (PowerShell example)
$env:CHAT_AI_ENDPOINT="https://your-resource.services.ai.azure.com/openai/v1"
$env:CHAT_AI_API_KEY="your-api-key"
$env:CHAT_AI_MODEL="gpt-4o-mini"

uv run uvicorn app.main:app --reload
```

Open http://localhost:8000. The app boots and shows the env-var dump even **without** AI credentials; the chat box only errors when you actually send a message.

## Run with Docker

```sh
docker build -t embr-foundry .
docker run --rm -p 8000:8000 \
  -e CHAT_AI_ENDPOINT=... \
  -e CHAT_AI_API_KEY=... \
  -e CHAT_AI_MODEL=... \
  embr-foundry
```

The container honors a `PORT` env var if the platform injects one (defaults to `8000`).

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| GET | `/` | Chat page + env-var dump |
| GET | `/api/env` | All env vars as JSON, with values masked when var name contains `KEY` (testing only) |
| POST | `/api/chat` | `{ "message": "...", "history": [...] }` → `{ "reply": "..." }` |
| POST | `/api/embed` | `{ "text": "...", "compare": "..."? }` → vector `dimensions`, `norm`, `preview`, and `similarity` when `compare` is given |
| GET | `/health` | Liveness probe |

## Architecture / extending to agents

`app/ai.py` is a tiny wrapper exposing `chat(messages)` and `embed(inputs)` over
the `openai` SDK; `app/main.py` is just the FastAPI web layer. To add a Foundry
**agent** backend later:

1. Add deps: `uv add azure-ai-projects azure-identity`.
2. Build the client with a managed identity and fetch the agent, e.g.:

   ```python
   from azure.ai.projects import AIProjectClient
   from azure.identity import ManagedIdentityCredential

   project = AIProjectClient(
       endpoint=os.environ["SUPPORT_AI_ENDPOINT"],
       credential=ManagedIdentityCredential(client_id=os.environ["SUPPORT_AI_IDENTITY_CLIENT_ID"]),
   )
   agent = project.agents.get_agent(agent_id=os.environ["SUPPORT_AI_AGENT_ID"])
   ```

3. Add a route (or branch `chat`) that drives the agent. The web layer only needs
   a function returning a reply string.

## ⚠ Security note

`/api/env` and the UI expose environment variable values, with masking only for
names containing `KEY`. This is intentional for validating platform env-var
injection and must **never** be enabled in a real environment.

## Troubleshooting: PaaS build fails with `invalid peer certificate: UnknownIssuer`

If a PaaS builder (e.g. Azure Oryx) runs `uv sync` and fails to download wheels
from `files.pythonhosted.org` with `invalid peer certificate: UnknownIssuer`,
the build environment is behind a TLS-intercepting proxy whose CA is trusted by
the OS/pip store but **not** by uv's bundled certificate roots.

This repo sets `native-tls = true` under `[tool.uv]` in `pyproject.toml`, which
tells uv to use the OS certificate store (matching pip's behavior). Keep that
setting; without it the build fails on the first uncached wheel. Equivalent
alternatives if needed: set `UV_NATIVE_TLS=1` in the build environment, or pass
`uv sync --native-tls`.

