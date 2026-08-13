"""Exact sequential-WOR sales/waste likelihood + diagnostic mean-field tools.

Shared filter density matching ``allocate_sales`` (sequential WOR product) plus
independent Binomial waste via ``death_prob_survival_ratio``. Production particle
weights use ``log_p_sales_waste_given_ages`` (ADR 0105). ``mean_field_update`` /
exact-joint helpers remain for diagnostic and legacy Stage C evidence only —
not on the production closed-loop path.
"""

from __future__ import annotations

from blueberries_voi.model import (
    death_prob_survival_ratio,
    picking_weights,
)

from . import sequential_wor as _sequential_wor
from .exact_likelihood import (
    log_p_sales_waste_given_ages,
    log_p_sales_waste_multinomial_given_ages,
)
from .mean_field_diag import (
    MF_MAX_SWEEPS,
    exact_joint_update,
    induced_joint_from_marginals,
    joint_kl,
    joint_total_variation,
    marginal_kl,
    marginal_total_variation,
    marginals_from_joint,
    max_pairwise_mutual_information,
    mean_field_update,
)
from .sequential_wor import (
    sequential_wor_composition_prob,
    sequential_wor_composition_probs,
)
from .survival import survival_weighted_on_hand

# Re-exported for import-identity AC (T-020).
__all__ = [
    "MF_MAX_SWEEPS",
    "death_prob_survival_ratio",
    "exact_joint_update",
    "induced_joint_from_marginals",
    "joint_kl",
    "joint_total_variation",
    "log_p_sales_waste_given_ages",
    "log_p_sales_waste_multinomial_given_ages",
    "marginal_kl",
    "marginal_total_variation",
    "marginals_from_joint",
    "max_pairwise_mutual_information",
    "mean_field_update",
    "picking_weights",
    "sequential_wor_composition_prob",
    "sequential_wor_composition_probs",
    "survival_weighted_on_hand",
]

# AST scanners (test_sequential_wor_numpy) parse Path(module.__file__) looking for
# a top-level ``def sequential_wor_composition_probs``. Point ``__file__`` at the
# implementation leaf that defines it (façade pattern for package split; ADR 0118).
__file__ = _sequential_wor.__file__
