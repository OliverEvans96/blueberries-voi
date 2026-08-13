"""Shared synthetic ASN calendar epoch for episode day indices (T-019)."""

from __future__ import annotations

from datetime import date

# Receipt day = epoch + episode day index; pack_date = receipt - round(tau_in).
# Deterministic under CRN; Abdella traces do not ship real ASN calendars.
_EPISODE_CALENDAR_EPOCH: date = date(2024, 1, 1)

__all__ = ["_EPISODE_CALENDAR_EPOCH"]
