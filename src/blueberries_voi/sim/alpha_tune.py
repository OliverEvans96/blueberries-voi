"""CTL-03 simulation-tuned α grid search (T-029).

Tuned α values are written under ``experiments/`` and/or ``figures/m2/``
(see ``DEFAULT_TUNED_ALPHA_PATH`` once implemented). This module is the thin
sim helper for α tuning; policies stay in ``controller/`` (no matplotlib / FS
writers there). Experiment CLIs may live under ``experiments/``.
"""

from __future__ import annotations

# Intentionally empty until implementer lands T-029 API
# (tune_alpha_grid, load/save table, ladder profit gate).
__all__: list[str] = []
