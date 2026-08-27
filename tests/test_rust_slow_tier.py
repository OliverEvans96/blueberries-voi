"""Static guard for Rust slow tier (#[ignore]) inventory."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]

# Named contract tests that must stay in the slow (ignored) tier.
_REQUIRED_IGNORED = frozenset(
    {
        "clean_chain_phi_bar_moments",
        "ac2_11a_empirical_ladder_tracking_mae",
        "unit_pf_l20_scripted_mean_f_mae_and_order_match",
    }
)

# Rollout MC tests removed per user directive — must not reappear in default tier.
_REMOVED_ROLLOUT = frozenset(
    {
        "rollout_costs_flip_winning_order",
        "act_rollout_uses_belief_not_truth_counts",
        "act_damped_sw_differs_from_rollout_when_belief_nontrivial",
    }
)


def _list_tests(*extra: str) -> set[str]:
    proc = subprocess.run(
        [
            "cargo",
            "test",
            "--release",
            "--locked",
            "-p",
            "voi_core",
            "-p",
            "voi_py",
            "--",
            "--list",
            *extra,
        ],
        cwd=_REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    names: set[str] = set()
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("running") or line.endswith(":"):
            continue
        # Format: "test_name: test" or "crate::module::test_name: test"
        m = re.match(r"(?:[\w:]+::)?([\w]+):\s*test$", line)
        if m:
            names.add(m.group(1))
    return names


def test_rust_slow_tier_counts_in_expected_band() -> None:
    """Default tier skips heavy tests; slow tier retains scientific contracts."""
    all_tests = _list_tests()
    ignored = _list_tests("--ignored")
    default = all_tests - ignored
    assert 180 <= len(default) <= 250, f"default tier count {len(default)} outside band"
    assert 50 <= len(ignored) <= 120, f"ignored tier count {len(ignored)} outside band"
    assert default.isdisjoint(ignored)


def test_named_contract_tests_in_ignored_tier() -> None:
    ignored = _list_tests("--ignored")
    missing = _REQUIRED_IGNORED - ignored
    assert not missing, f"contract tests must be #[ignore] slow tier: {sorted(missing)}"


def test_removed_rollout_tests_not_in_default_tier() -> None:
    default = _list_tests()
    present = _REMOVED_ROLLOUT & default
    assert not present, (
        "deprecated rollout tests must be deleted or ignored: "
        f"{sorted(present)}"
    )
