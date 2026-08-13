"""FastAPI ASGI app: HTTP sessions over EngineSession (Snapshot / DayDelta).

Routes match T-049 Interfaces. Responses are ADR 0098 wire dicts only — no
ViewModel, PnL, economics, ghost, or heatmap. Matplotlib is never imported.
"""

from __future__ import annotations

import uuid
from typing import Any

import numpy as np
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field

from blueberries_voi.model.abdella import ShipmentTrace
from blueberries_voi.simulator.session import EngineSession

# In-process session store (local dev only; no TTL / multi-tenant isolation).
_SESSIONS: dict[str, EngineSession] = {}

app = FastAPI(
    title="blueberries-voi interactive API",
    description=(
        "Development host for EngineSession (ADR 0100). "
        "In-process sessions; not production multi-tenant."
    ),
    version="0.1.0",
)


class InitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    config: dict[str, Any]
    seed: int | None = None


class StepRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_qty: int


class StepNRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    orders: list[int]


class ResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    config: dict[str, Any] | None = None
    seed: int | None = None


class ActRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy: str | None = None
    budgets: dict[str, Any] = Field(default_factory=dict)


def _error_body(*, error_type: str, message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"type": error_type, "message": message}}


def _get_session(session_id: str) -> EngineSession:
    session = _SESSIONS.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=404,
            detail=_error_body(
                error_type="not_found",
                message=f"unknown session_id {session_id!r}",
            ),
        )
    return session


def _hydrate_shipments(raw: Any) -> list[ShipmentTrace]:
    if not isinstance(raw, list) or not raw:
        msg = "config['shipments'] must be a non-empty list"
        raise HTTPException(
            status_code=422,
            detail=_error_body(error_type="validation_error", message=msg),
        )
    out: list[ShipmentTrace] = []
    for i, item in enumerate(raw):
        if isinstance(item, ShipmentTrace):
            out.append(item)
            continue
        if not isinstance(item, dict):
            msg = f"shipments[{i}] must be an object or ShipmentTrace"
            raise HTTPException(
                status_code=422,
                detail=_error_body(error_type="validation_error", message=msg),
            )
        try:
            out.append(
                ShipmentTrace(
                    shipment_id=str(item["shipment_id"]),
                    times_d=np.asarray(item["times_d"], dtype=float),
                    temps_c=np.asarray(item["temps_c"], dtype=float),
                    duration_d=float(item["duration_d"]),
                )
            )
        except KeyError as exc:
            msg = f"shipments[{i}] missing field {exc.args[0]!r}"
            raise HTTPException(
                status_code=422,
                detail=_error_body(error_type="validation_error", message=msg),
            ) from exc
        except (TypeError, ValueError) as exc:
            msg = f"shipments[{i}] invalid: {exc}"
            raise HTTPException(
                status_code=422,
                detail=_error_body(error_type="validation_error", message=msg),
            ) from exc
    return out


def _config_with_shipments(config: dict[str, Any]) -> dict[str, Any]:
    cfg = dict(config)
    cfg["shipments"] = _hydrate_shipments(cfg.get("shipments"))
    return cfg


@app.post("/sessions")
def create_session() -> dict[str, str]:
    session_id = uuid.uuid4().hex
    _SESSIONS[session_id] = EngineSession()
    return {"session_id": session_id}


@app.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: str) -> Response:
    if session_id not in _SESSIONS:
        raise HTTPException(
            status_code=404,
            detail=_error_body(
                error_type="not_found",
                message=f"unknown session_id {session_id!r}",
            ),
        )
    del _SESSIONS[session_id]
    return Response(status_code=204)


@app.post("/sessions/{session_id}/init")
def init_session(session_id: str, body: InitRequest) -> dict[str, Any]:
    session = _get_session(session_id)
    cfg = _config_with_shipments(body.config)
    return dict(session.init(cfg, seed=body.seed))


@app.post("/sessions/{session_id}/step")
def step_session(session_id: str, body: StepRequest) -> dict[str, Any]:
    session = _get_session(session_id)
    return dict(session.step(body.order_qty))


@app.post("/sessions/{session_id}/step_n")
def step_n_session(session_id: str, body: StepNRequest) -> dict[str, Any]:
    session = _get_session(session_id)
    deltas = session.step_n(body.orders)
    return {"deltas": [dict(d) for d in deltas]}


@app.post("/sessions/{session_id}/reset")
def reset_session(session_id: str, body: ResetRequest) -> dict[str, Any]:
    session = _get_session(session_id)
    cfg = None if body.config is None else _config_with_shipments(body.config)
    return dict(session.reset(cfg, seed=body.seed))


@app.post("/sessions/{session_id}/act")
def act_session(session_id: str, body: ActRequest) -> dict[str, Any]:
    session = _get_session(session_id)
    return dict(session.act(policy=body.policy, **dict(body.budgets)))
