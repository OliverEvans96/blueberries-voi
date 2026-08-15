"""JSON RPC mirror of the Pyodide worker edge (T-047 / ADR 0098).

One bound ``EngineSession`` answers ``init`` / ``step`` / ``step_n`` / ``reset`` /
``act``. Payloads cross the boundary as ``json.dumps`` strings (no deep toJs,
no nested PyProxy). Default budgets are dialed ``DEMO_BUDGETS`` (≤200 / H≤7 /
paths≤2 / radius≤1) — not the full production particle count.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from blueberries_voi.sim.shipments import ensure_demo_shipments
from blueberries_voi.simulator import DEMO_BUDGETS, EngineSession

if TYPE_CHECKING:
    from blueberries_voi.model.abdella import ShipmentTrace

_RPC_METHODS = frozenset({"init", "step", "step_n", "reset", "act", "set_obs_scenario"})

# Single bound session — mirrors the one EngineSession held by the worker.
_SESSION = EngineSession()


def dumps_payload(obj: Any) -> str:
    """Serialise a Snapshot / DayDelta / envelope via ``json.dumps`` (ADR 0098)."""
    return json.dumps(obj)


def prepare_demo_config(
    config: dict[str, Any],
    *,
    shipments: list[ShipmentTrace] | None = None,
) -> dict[str, Any]:
    """Attach injectable shipments and clamp dialed demo budgets into ``config``."""
    out = dict(config)
    if shipments is not None:
        out["shipments"] = list(shipments)
    out = ensure_demo_shipments(out)
    # Dial demo budgets (≤ ADR 0099 caps); never silently use full production N.
    for key, cap in DEMO_BUDGETS.items():
        if key not in out:
            out[key] = int(cap)
        else:
            out[key] = min(int(out[key]), int(cap))
    return out


def _ok(req_id: str, result: Any) -> str:
    return dumps_payload({"id": req_id, "ok": True, "result": result})


def _err(req_id: str, err_type: str, message: str) -> str:
    return dumps_payload(
        {
            "id": req_id,
            "ok": False,
            "error": {"type": err_type, "message": message},
        }
    )


def _dispatch(method: str, params: dict[str, Any]) -> Any:
    if method == "init":
        config = ensure_demo_shipments(dict(params.get("config") or {}))
        seed = params.get("seed")
        return _SESSION.init(config, seed=None if seed is None else int(seed))
    if method == "step":
        return _SESSION.step(int(params["order_qty"]))
    if method == "step_n":
        orders = list(params.get("orders") or [])
        return _SESSION.step_n([int(q) for q in orders])
    if method == "reset":
        raw_config = params.get("config")
        seed = params.get("seed")
        return _SESSION.reset(
            None if raw_config is None else ensure_demo_shipments(dict(raw_config)),
            seed=None if seed is None else int(seed),
        )
    if method == "act":
        policy = params.get("policy")
        overrides = {k: v for k, v in params.items() if k not in {"policy"}}
        return _SESSION.act(policy=policy, **overrides)
    if method == "set_obs_scenario":
        return _SESSION.set_obs_scenario(params["obs_scenario"])
    msg = f"unknown method {method!r}"
    raise ValueError(msg)


def handle_rpc(request: dict[str, Any] | str) -> str:
    """Handle one worker-shaped request; return a JSON string response.

    Request:  ``{id, method, params}``
    Response: ``{id, ok: true, result}`` | ``{id, ok: false, error: {type, message}}``
    """
    if isinstance(request, str):
        try:
            request = json.loads(request)
        except json.JSONDecodeError as exc:
            return _err("", "JSONDecodeError", str(exc))
    if not isinstance(request, dict):
        return _err("", "TypeError", "request must be a mapping or JSON object string")

    req_id = str(request.get("id", ""))
    method = request.get("method")
    params = request.get("params") or {}
    if not isinstance(params, dict):
        return _err(req_id, "TypeError", "params must be an object")
    if not isinstance(method, str) or method not in _RPC_METHODS:
        return _err(
            req_id,
            "UnknownMethod",
            f"unknown method {method!r}; expected one of {sorted(_RPC_METHODS)}",
        )
    try:
        result = _dispatch(method, params)
    except Exception as exc:
        return _err(req_id, type(exc).__name__, str(exc))
    return _ok(req_id, result)


__all__ = [
    "DEMO_BUDGETS",
    "dumps_payload",
    "handle_rpc",
    "prepare_demo_config",
]
