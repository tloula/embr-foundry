# embr-foundry

A deliberately minimal Python web app whose primary goal is to **prove environment-variable injection works on a new PaaS platform**. It has:

- A single root page with a simple chat UI backed by an LLM.
- A text-embeddings panel to validate an embedding model (vector dims + cosine similarity).
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
| `CHAT_AI_ENDPOINT` | Inference endpoint URL. Accepts the OpenAI-compatible `/openai/v1` route (e.g. `https://<resource>.services.ai.azure.com/openai/v1`) or the unified `/models` route. Do **not** use the Foundry project endpoint (`.../api/projects/<name>`) here — that's for the agent backend and causes `API version not supported`. |
| `CHAT_AI_API_KEY` | API key |
| `CHAT_AI_MODEL` | Model/deployment name |
| `CHAT_AI_API_VERSION` | Optional. Overrides the API version. Unnecessary normally: the backend auto-selects `api-version=preview` for `/openai/v1` and the SDK default for `/models`. |

Embeddings (`azure-ai-inference` `EmbeddingsClient`) — powers the **Text embeddings** panel:

| Var | Purpose |
| --- | --- |
| `EMBED_AI_ENDPOINT` | Same endpoint shapes as `CHAT_AI_ENDPOINT`. The backend routes automatically: `/openai/v1` is used as-is (deployment sent in the body); `/openai/deployments/<name>` is used as-is (deployment in the path); a `/models` (or bare resource) base is derived to `/openai/deployments/<EMBED_AI_MODEL>`, since AOAI embedding deployments aren't served by `/models`. |
| `EMBED_AI_API_KEY` | API key |
| `EMBED_AI_MODEL` | Embedding model/deployment name (e.g. `text-embedding-3-small`) |
| `EMBED_AI_API_VERSION` | Optional API version override (unnecessary; `preview` is auto-selected for `/openai/v1`). |

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
| GET | `/api/env` | All env vars as JSON (testing only) |
| POST | `/api/chat` | `{ "message": "...", "history": [...] }` → `{ "reply": "..." }` |
| POST | `/api/embed` | `{ "text": "...", "compare": "..."? }` → vector `dimensions`, `norm`, `preview`, and `similarity` when `compare` is given |
| GET | `/health` | Liveness probe |

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

