"""Modal batch map for notebook 13 and lgtin_upc_diag (optional extra).

Build artifacts locally before ``modal run`` — see README.md in this directory.
"""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

try:
    import modal
except ImportError as exc:  # pragma: no cover - optional extra
    msg = "Install modal: pip install 'blueberries-voi[modal]'"
    raise SystemExit(msg) from exc

_REPO = Path(__file__).resolve()
for _depth in range(2, -1, -1):
    if _depth < len(_REPO.parents):
        _candidate = _REPO.parents[_depth]
        if (_candidate / "src" / "blueberries_voi").is_dir():
            _REPO = _candidate
            break
else:
    _REPO = Path(__file__).resolve().parent

_PKG_SRC = _REPO / "src" / "blueberries_voi"
_DATA_DIR = _REPO / "data"


def _repo_relative_path(env_key: str, default: Path) -> Path:
    raw = os.environ.get(env_key)
    path = Path(raw) if raw else default
    if not path.is_absolute():
        path = (_REPO / path).resolve()
    return path


_WHEEL = _repo_relative_path("BLUEBERRIES_VOI_WHEEL", _REPO / "dist" / "wheel")
if _WHEEL.is_dir():
    _wheel_files = sorted(_WHEEL.glob("blueberries_voi_core-*.whl"))
    if not _wheel_files:
        _wheel_files = sorted(_WHEEL.glob("*.whl"))
    WHEEL_PATH = (
        _wheel_files[-1]
        if _wheel_files
        else (_REPO / "dist" / "blueberries_voi_core.whl")
    )
else:
    WHEEL_PATH = _WHEEL

_LGTIN_BIN = _repo_relative_path(
    "LGTIN_UPC_DIAG_BIN",
    _REPO / "target" / "release" / "examples" / "lgtin_upc_diag",
)
_TUNED_ALPHA = _REPO / "experiments" / "tuned_alpha.json"
_TUNED_ALPHA_F3 = _REPO / "experiments" / "tuned_alpha_f3_filtered.json"
_REMOTE_TUNED_ALPHA = "/experiments/tuned_alpha.json"
_REMOTE_TUNED_ALPHA_F3 = "/experiments/tuned_alpha_f3_filtered.json"

_WHEEL_REMOTE = f"/tmp/{WHEEL_PATH.name}"

_base_image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "numpy>=2.4.6", "scipy>=1.17.1", "pyarrow>=25.0.1"
)
if modal.is_local():
    image = _base_image.add_local_dir(
        str(_PKG_SRC), remote_path="/pkg/blueberries_voi", copy=True
    )
    image = image.add_local_dir(str(_DATA_DIR), remote_path="/data", copy=True)
    image = image.add_local_file(str(WHEEL_PATH), _WHEEL_REMOTE, copy=True)
    if _LGTIN_BIN.is_file():
        image = image.add_local_file(
            str(_LGTIN_BIN), "/usr/local/bin/lgtin_upc_diag", copy=True
        )
    if _TUNED_ALPHA.is_file():
        image = image.add_local_file(str(_TUNED_ALPHA), _REMOTE_TUNED_ALPHA, copy=True)
    if _TUNED_ALPHA_F3.is_file():
        image = image.add_local_file(
            str(_TUNED_ALPHA_F3), _REMOTE_TUNED_ALPHA_F3, copy=True
        )
    image = image.run_commands(
        f"pip install {_WHEEL_REMOTE}",
        (
            'python -c "import importlib.util, shutil; from pathlib import Path; '
            "spec = importlib.util.find_spec('blueberries_voi._core'); "
            "assert spec is not None and spec.origin; "
            "dest = Path('/pkg/blueberries_voi') / Path(spec.origin).name; "
            'shutil.copy2(spec.origin, dest)"'
        ),
    ).env(
        {
            "PYTHONPATH": "/pkg",
            "BLUEBERRIES_VOI_BACKEND": "rust",
            "LGTIN_UPC_DIAG_BIN": "/usr/local/bin/lgtin_upc_diag",
            "BLUEBERRIES_VOI_TUNED_ALPHA": _REMOTE_TUNED_ALPHA,
            "BLUEBERRIES_VOI_TUNED_ALPHA_F3": _REMOTE_TUNED_ALPHA_F3,
        }
    )
else:
    image = _base_image.env(
        {
            "PYTHONPATH": "/pkg",
            "BLUEBERRIES_VOI_BACKEND": "rust",
            "LGTIN_UPC_DIAG_BIN": "/usr/local/bin/lgtin_upc_diag",
            "BLUEBERRIES_VOI_TUNED_ALPHA": _REMOTE_TUNED_ALPHA,
            "BLUEBERRIES_VOI_TUNED_ALPHA_F3": _REMOTE_TUNED_ALPHA_F3,
        }
    )

app = modal.App("blueberries-voi-batch", image=image)


@app.function(timeout=600, cpu=1.0)
def nb13_shard(
    seed: int,
    channel: dict[str, object],
    n_days: int,
    job_index: int = -1,
) -> dict[str, Any]:
    from blueberries_voi.experiments.batch_progress import log_nb13_done, log_nb13_start
    from blueberries_voi.experiments.filter_accuracy import run_seed_channel

    idx = job_index if job_index >= 0 else None
    t0 = log_nb13_start(seed, channel, job_index=idx)
    result = run_seed_channel(seed, channel, n_days=n_days)
    elapsed = log_nb13_done(seed, channel, t0, job_index=idx)
    result["_elapsed_s"] = elapsed
    return result


@app.function(timeout=600, cpu=1.0)
def lgtin_shard(regime_index: int, seed_index: int) -> dict[str, Any]:
    from blueberries_voi.experiments.lgtin_upc import run_regime_seed

    return run_regime_seed(regime_index, seed_index)


@app.function(timeout=600, cpu=1.0)
def voi_profit_shard(
    seed: int,
    channel_dict: dict[str, object],
    budgets_dict: dict[str, Any],
) -> dict[str, Any]:
    from blueberries_voi.experiments.voi_profit import run_seed_channel_profit

    return run_seed_channel_profit(seed, channel_dict, **budgets_dict)


@app.function(timeout=600, cpu=1.0)
def voi_oracle_profit_shard(
    seed: int,
    budgets_dict: dict[str, Any],
) -> dict[str, Any]:
    from blueberries_voi.experiments.voi_profit import run_seed_oracle_profit

    return run_seed_oracle_profit(seed, **budgets_dict)


@app.function(timeout=600, cpu=1.0)
def channel_joint_shard(
    seed: int,
    channel_dict: dict[str, object],
    budgets_dict: dict[str, Any],
) -> dict[str, Any]:
    from blueberries_voi.experiments.batch_progress import (
        log_channel_joint_done,
        log_channel_joint_start,
    )
    from blueberries_voi.experiments.channel_joint import run_seed_channel_joint

    t0 = log_channel_joint_start(seed, channel_dict)
    result = run_seed_channel_joint(seed, channel_dict, **budgets_dict)
    elapsed = log_channel_joint_done(seed, channel_dict, t0)
    result["_elapsed_s"] = elapsed
    return result


@app.function(timeout=600, cpu=1.0)
def rollout_eval_shard(
    seed: int,
    arm_id: str,
    alpha: float,
    rho: float,
    budgets_dict: dict[str, Any],
) -> dict[str, Any]:
    from blueberries_voi.experiments.rollout_bakeoff import run_rollout_eval

    return run_rollout_eval(seed, arm_id, alpha, rho, **budgets_dict)


@app.function(timeout=600, cpu=1.0)
def controller_bakeoff_shard(
    seed: int,
    arm_id: str,
    rho: float,
    budgets_dict: dict[str, Any],
) -> dict[str, Any]:
    from blueberries_voi.experiments.controller_bakeoff import run_controller_eval

    kw = dict(budgets_dict)
    kw.pop("rho", None)
    belief_world = str(kw.pop("belief_world", "oracle"))
    return run_controller_eval(
        seed,
        arm_id,
        float(rho),
        belief_world=belief_world,
        **kw,
    )


@app.function(timeout=600, cpu=1.0)
def damped_sw_soo_shard(job: dict[str, Any]) -> dict[str, Any]:
    from blueberries_voi.experiments.damped_sw_soo import run_soo_shard

    return run_soo_shard(job)


@app.local_entrypoint()
def nb13(
    out: str = "nb13_channel_rows.json",
    days: int = 30,
) -> None:
    from blueberries_voi.experiments.batch_progress import log_grid_progress, log_line
    from blueberries_voi.experiments.filter_accuracy import (
        DEFAULT_SEEDS,
        merge_channel_rows,
        nb13_job_grid_with_f3,
    )

    grid = nb13_job_grid_with_f3(seeds=DEFAULT_SEEDS)
    total = len(grid)
    log_line(
        f"nb13 Modal run: {total} jobs "
        f"(36 factorial + {total - 36} F3), days={days}, n_rollout_paths=0"
    )
    wall_t0 = time.perf_counter()
    handles = [
        nb13_shard.spawn(seed, ch.__dict__, days, job_index=i)
        for i, (seed, ch) in enumerate(grid)
    ]
    shards: list[dict[str, Any]] = []
    completed = 0
    slowest: tuple[float, int, str] = (0.0, -1, "")
    with ThreadPoolExecutor(max_workers=min(32, total)) as pool:
        futs = {pool.submit(h.get): i for i, h in enumerate(handles)}
        for fut in as_completed(futs):
            shard = fut.result()
            elapsed = float(shard.pop("_elapsed_s", 0.0))
            job_i = futs[fut]
            seed_i, _ch = grid[job_i]
            key = shard.get("key", "?")
            if elapsed > slowest[0]:
                slowest = (elapsed, int(seed_i), str(key))
            shards.append(shard)
            completed += 1
            log_grid_progress(completed, total)
    rows = merge_channel_rows(shards)
    out_path = Path(out)
    out_path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    shards_path = out_path.with_name(out_path.stem + "_shards.json")
    shards_path.write_text(json.dumps(shards) + "\n", encoding="utf-8")
    wall = time.perf_counter() - wall_t0
    log_line(
        f"nb13 Modal wall-clock_s={wall:.1f} wrote {out} ({len(rows)} rows) "
        f"and {shards_path.name} slowest seed={slowest[1]} channel={slowest[2]} "
        f"elapsed_s={slowest[0]:.1f}"
    )


@app.local_entrypoint()
def lgtin(out: str = "lgtin_upc_sharded.json") -> None:
    from blueberries_voi.experiments.lgtin_upc import (
        lgtin_job_grid,
        merge_lgtin_diag_rows,
    )

    shards = list(lgtin_shard.starmap(lgtin_job_grid()))
    rows = merge_lgtin_diag_rows(shards)
    Path(out).write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(rows)} rows)")
