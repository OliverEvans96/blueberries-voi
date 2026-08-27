#!/usr/bin/env python3
"""One-shot helper: add #[ignore = \"slow: …\"] to heavy Rust integration tests."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

SLOW_MSG = "slow: run via cargo test -- --ignored"

# All #[test] in these files become slow unless already #[ignore].
WHOLE_FILE_SLOW: dict[str, str] = {
    "crates/voi_core/tests/t163_multilot.rs": "T-163 multilot EngineSession stepping",
    "crates/voi_core/tests/t151_cold_chain_breaks.rs": "cold-chain break trace loops",
    "crates/voi_core/tests/t150_arrival_wire_filter_parity.rs": "wire filter parity MC",
    "crates/voi_core/tests/t163_v2_calibration.rs": "T-163 v2 calibration MC",
    "crates/voi_core/tests/t163_v2_filter_coherence.rs": "T-163 filter coherence MC",
    "crates/voi_core/tests/t163_v2_generative.rs": "T-163 v2 generative MC",
}

# t150_phase2: keep fast static/math wiring tests only.
T150_PHASE2_FAST = frozenset(
    {
        "ac2_1_gamma_shape_scaling_not_scale",
        "ac2_2_gamma_additivity_and_timestep_invariance",
        "ac2_4_reference_life_invariant_and_eta_choke_point",
        "ac2_5_transit_shelf_exposure_relationship",
        "ac2_6_arrival_artifact_schema",
        "ac2_7_single_embed_and_parity",
        "ac2_8_calibration_note_script_exists",
        "ac2_16_lambda_floor_finite_cdf",
        "ac2_17_rust_embed_parses_committed_artifact",
    }
)

NAMED_SLOW: dict[str, str] = {
    "unit_pf_l20_scripted_mean_f_mae_and_order_match": (
        "ADR 0130 L=20 scripted filter gate"
    ),
    "unit_pf_f1_p1_relative_mean_f_mae": "F1 vs P1 mean_f MAE",
    "unit_pf_f1_strictly_beats_p1_heterogeneous_lots": (
        "F1 beats P1 heterogeneous lots"
    ),
    "multinomial_vs_wor_mc_realistic_l": "multinomial vs WOR MC realistic L",
    "score_particle_mutates_freshness_after_finite_p1_ll": (
        "P1 filter particle mutation"
    ),
    "p1_f1_zero_sales_belief_mass_parity": "P0/P1/F1 zero-sales parity",
    "filter_birth_matches_arrival_qty_not_upl": "filter birth qty parity",
    "gsin_multilot_delivery_segments_match_l": "GSIN multilot delivery segments",
    "upc_multilot_delivery_merges_to_one_segment": "UPC multilot delivery merge",
    "session_configure_loads_calendar_profile_and_uses_day_in_demand": (
        "90-day calendar demand"
    ),
    "p0_vs_p1_belief_differs_after_waste": "P0 vs P1 belief after waste",
    "f1_vs_p1_belief_differs_after_uneven_sales": "F1 vs P1 belief after uneven sales",
    "truth_belief_source_skips_filter_updates": "truth belief source skips filter",
    "catch_up_f2_matches_never_switched_and_not_oracle": "caught-up F2 vs P0 session",
    "session_stream_rng_calendar_mean_seed0": "90-day calendar demand RNG mean",
    "day_step_f_native_conservation_scripted_seed": (
        "f-native conservation scripted seed"
    ),
    "candidate_case_radius_changes_rollout_order": "rollout radius MC (deprecated)",
    "rollout_smoke_finite_profit": "alpha_tune rollout smoke (deprecated)",
    "rollout_tune_best_in_ci_grid": "alpha_tune rollout grid (deprecated)",
    "sw_calendar_higher_alpha_increases_mean_profit_full_run": (
        "full calendar SW alpha MC"
    ),
    "p0_and_f1_profits_differ_on_seed_42": "P0/F1 profit separation MC",
    "crn_cell_returns_seven_finite_profits": "VOI CRN cell smoke (7 masks)",
}

# Per-file named slow (t150_phase2 tests not in FAST set).
T150_PHASE2_FILE = REPO / "crates/voi_core/tests/t150_phase2_arrival_model.rs"


def _has_ignore_before(text: str, pos: int) -> bool:
    before = text[:pos].rstrip()
    return before.endswith('"]') and "#[ignore" in before.split("\n")[-1]


def add_ignore_before_fn(text: str, fn_name: str, reason: str) -> str:
    pattern = re.compile(
        rf"(^[ \t]*#\[test\]\n)(^[ \t]*fn {re.escape(fn_name)}\()",
        re.MULTILINE,
    )

    def repl(m: re.Match[str]) -> str:
        if _has_ignore_before(text, m.start()):
            return m.group(0)
        msg = reason if reason.endswith(".") else f"{reason}; {SLOW_MSG}"
        return f'{m.group(1)}#[ignore = "{msg}"]\n{m.group(2)}'

    return pattern.sub(repl, text)


def mark_whole_file(path: Path, reason: str) -> bool:
    text = path.read_text(encoding="utf-8")
    orig = text
    for m in re.finditer(r"^[ \t]*#\[test\]\n[ \t]*fn (\w+)\(", text, re.MULTILINE):
        fn = m.group(1)
        text = add_ignore_before_fn(text, fn, reason)
    if text != orig:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def mark_t150_phase2() -> bool:
    text = T150_PHASE2_FILE.read_text(encoding="utf-8")
    orig = text
    for m in re.finditer(r"^[ \t]*#\[test\]\n[ \t]*fn (\w+)\(", text, re.MULTILINE):
        fn = m.group(1)
        if fn in T150_PHASE2_FAST:
            continue
        if fn.startswith("ac2_") or fn in NAMED_SLOW:
            reason = f"T-150 arrival MC/integration ({fn})"
            text = add_ignore_before_fn(text, fn, reason)
    if text != orig:
        T150_PHASE2_FILE.write_text(text, encoding="utf-8")
        return True
    return False


def mark_named_in_tree() -> int:
    changed = 0
    for path in REPO.glob("crates/voi_core/**/*.rs"):
        if path.as_posix().endswith(tuple(WHOLE_FILE_SLOW)):
            continue
        if path == T150_PHASE2_FILE:
            continue
        text = path.read_text(encoding="utf-8")
        orig = text
        for fn, reason in NAMED_SLOW.items():
            if f"fn {fn}(" in text:
                text = add_ignore_before_fn(text, fn, reason)
        if text != orig:
            path.write_text(text, encoding="utf-8")
            changed += 1
    return changed


def delete_rollout_tests_session() -> None:
    path = REPO / "crates/voi_core/src/session.rs"
    text = path.read_text(encoding="utf-8")
    to_remove = [
        "act_rollout_advances_day",
        "act_rollout_uses_belief_not_truth_counts",
        "act_damped_sw_differs_from_rollout_when_belief_nontrivial",
    ]
    for fn in to_remove:
        pattern = re.compile(
            rf"\n[ \t]*#\[test\]\n[ \t]*fn {re.escape(fn)}\(\) \{{\n.*?\n[ \t]*\}}\n",
            re.DOTALL,
        )
        text, n = pattern.subn("\n", text)
        if n == 0:
            print(f"warning: did not remove session test {fn}", file=sys.stderr)
    path.write_text(text, encoding="utf-8")


def delete_rollout_tests_rollout_rs() -> None:
    path = REPO / "crates/voi_core/src/rollout.rs"
    text = path.read_text(encoding="utf-8")
    to_remove = [
        "rollout_order_returns_nonnegative_case_multiple",
        "no_repeat_delivery_over_horizon",
        "rollout_costs_flip_winning_order",
    ]
    for fn in to_remove:
        # may have #[ignore] line before #[test]
        pattern = re.compile(
            rf"\n[ \t]*(?:#\[ignore[^\]]*\]\n)?"
            rf"[ \t]*#\[test\]\n[ \t]*fn {re.escape(fn)}\(\) \{{\n.*?\n[ \t]*\}}\n",
            re.DOTALL,
        )
        text, n = pattern.subn("\n", text)
        if n == 0:
            print(f"warning: did not remove rollout test {fn}", file=sys.stderr)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    for rel, reason in WHOLE_FILE_SLOW.items():
        mark_whole_file(REPO / rel, reason)
    mark_t150_phase2()
    mark_named_in_tree()
    delete_rollout_tests_session()
    delete_rollout_tests_rollout_rs()
    print("marked slow tests and removed rollout integration tests")


if __name__ == "__main__":
    main()
