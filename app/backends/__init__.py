"""Pluggable AI chat backends.

The web layer depends only on the :class:`ChatBackend` protocol defined in
``base.py`` and obtains a concrete instance via :func:`get_backend`. This keeps
the FastAPI routes decoupled from any specific Azure client, so new backends
(e.g. the future agent backend) can be added without touching the web layer.
"""

from .base import ChatBackend, BackendError, get_backend

__all__ = ["ChatBackend", "BackendError", "get_backend"]
