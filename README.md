# embr-foundry

A deliberately minimal Python web app whose primary goal is to **prove environment-variable injection works on a new PaaS platform**. It has:

- A single root page with a simple chat UI backed by an LLM.
- An env-var dump in the UI (⚠ intentionally insecure — testing only).
- A pluggable backend design so an Azure AI **agent** backend can be added later without touching the web layer.

## Stack

- [uv](https://docs.astral.sh/uv/) for project & dependency management
- FastAPI + uvicorn
- Plain HTML + vanilla JS frontend
- `azure-ai-inference` (`ChatCompletionsClient` + `AzureKeyCredential`)

## Environment variables

Backend selection:

| Var | Default | Purpose |
| --- | --- | --- |
| `CHAT_BACKEND` | `completions` | Which backend to use: `completions` or `agent` |

Completions backend (`azure-ai-inference`):

| Var | Purpose |
| --- | --- |
| `CHAT_AI_ENDPOINT` | Inference endpoint URL |
| `CHAT_AI_API_KEY` | API key |
| `CHAT_AI_MODEL` | Model/deployment name |

Agent backend (**future, not implemented** — reserved so the platform can inject them now):

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
$env:CHAT_AI_ENDPOINT="https://your-resource.services.ai.azure.com/models"
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
| GET | `/api/env` | All env vars as JSON (testing only) |
| POST | `/api/chat` | `{ "message": "...", "history": [...] }` → `{ "reply": "..." }` |
| GET | `/healthz` | Liveness probe |

## Architecture / extending to agents

The web layer (`app/main.py`) depends only on the `ChatBackend` interface in
`app/backends/base.py` and resolves a concrete backend via `get_backend()`
(keyed on `CHAT_BACKEND`). To add the agent backend later:

1. Add deps: `uv add azure-ai-projects azure-identity`.
2. Implement `chat()` in `app/backends/agent.py` (a documented stub today) using
   `AIProjectClient` + `ManagedIdentityCredential`.
3. Set `CHAT_BACKEND=agent`.

No web-layer changes are required.

## ⚠ Security note

`/api/env` and the UI expose **all** environment variable values, including
secrets. This is intentional for validating platform env-var injection and must
**never** be enabled in a real environment.
