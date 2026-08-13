"""Local-dev ASGI host wrapping ``EngineSession`` (ADR 0102 / T-050).

Install the optional ``[api]`` extra (FastAPI + httpx) to serve interactive
session routes. Session store is an in-process dict keyed by ``session_id`` —
no TTL / eviction; **not** production multi-tenant.

Entry: ``blueberries_voi.api:app``.
"""

from __future__ import annotations

from blueberries_voi.api.app import app

__all__ = ["app"]
