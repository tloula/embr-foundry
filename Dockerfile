# syntax=docker/dockerfile:1

FROM python:3.12-slim AS base

# Install uv (copied from the official distroless image).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Install dependencies first (better layer caching).
COPY pyproject.toml ./
RUN uv sync --no-install-project --no-dev

# Copy the application source.
COPY app ./app

# Install the project itself.
RUN uv sync --no-dev

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

# PaaS platforms typically inject PORT; default to 8000 locally.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
