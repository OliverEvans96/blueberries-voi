"""Inference section doc figure renderers."""

from __future__ import annotations

from .belief_wire import render as render_belief_wire
from .birth_freshness import render as render_birth_freshness

__all__ = ["render_belief_wire", "render_birth_freshness"]
