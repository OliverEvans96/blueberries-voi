"""FastAPI ASGI app: HTTP sessions over EngineSession (Snapshot / DayDelta).

Routes match T-049 Interfaces. Responses are ADR 0100 wire dicts only — no
ViewModel, PnL, economics, ghost, or heatmap. Matplotlib is never imported.

CORS (ADR 0108 / T-073): local-dev Vite origins only —
``http://localhost:5173`` and ``http://127.0.0.1:5173``. Production CDN /
auth CORS is out of scope.
"""

from __future__ import annotations

import uuid
from typing import Any

import numpy as np
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from blueberries_voi.model.abdella import ShipmentTrace
from blueberries_voi.sim.shipments import ensure_demo_shipments
from blueberries_voi.simulator.session import EngineSession

# In-process session store (local dev only; no TTL / multi-tenant isolation).
_SESSIONS: dict[str, EngineSession] = {}

# Local Vite → API (ADR 0108); production origins are out of scope for T-073.
_LOCAL_VITE_ORIGINS: tuple[str, ...] = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)

app = FastAPI(
    title="blueberries-voi interactive API",
    description=(
        "Development host for EngineSession (ADR 0102). "
        "In-process sessions; not production multi-tenant."
    ),
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(_LOCAL_VITE_ORIGINS),
    allow_methods=["*"],
    allow_headers=["*"],
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


class SetObsScenarioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    obs_scenario: str


class FlatBelief(BaseModel):
    """Flat L / L*K / K belief buffers on the wire (ADR 0100)."""

    model_config = ConfigDict(extra="forbid")

    L: int
    K: int
    lot_counts: list[float]
    age_marginals: list[float]
    tau_grid: list[float]


class Snapshot(BaseModel):
    """Cold Snapshot (init / reset) — same keys as golden fixtures."""

    model_config = ConfigDict(extra="allow")

    seq: int
    episode_day: int
    belief: FlatBelief
    applied_config: dict[str, Any] = Field(default_factory=dict)
    history: list[Any] = Field(default_factory=list)
    live_lots: list[Any] = Field(default_factory=list)
    pipeline: list[Any] = Field(default_factory=list)


class DayDelta(BaseModel):
    """Hot DayDelta (step / act / step_n element)."""

    model_config = ConfigDict(extra="allow")

    seq: int
    episode_day: int
    day: dict[str, Any]
    drop_oldest: bool
    belief: FlatBelief | None = None
    live_lots: list[Any] = Field(default_factory=list)
    pipeline: list[Any] = Field(default_factory=list)


class StepNResponse(BaseModel):
    """Framed ``{deltas: DayDelta[]}`` for step_n (ADR 0100 / 0102)."""

    model_config = ConfigDict(extra="forbid")

    deltas: list[DayDelta]


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


def _as_shipment_trace(item: Any, *, index: int) -> ShipmentTrace:
    """Normalize dict / ShipmentTrace / duck-typed traces to local ShipmentTrace.

    Duck-typing avoids intermittent 422s under xdist when the same dataclass is
    loaded via distinct module objects (``isinstance`` fails across identities).
    """
    if isinstance(item, ShipmentTrace):
        return item
    # Attribute-shaped traces (demo fixture under dual class identity).
    if not isinstance(item, dict) and all(
        hasattr(item, name)
        for name in ("shipment_id", "times_d", "temps_c", "duration_d")
    ):
        try:
            return ShipmentTrace(
                shipment_id=str(item.shipment_id),
                times_d=np.asarray(item.times_d, dtype=float),
                temps_c=np.asarray(item.temps_c, dtype=float),
                duration_d=float(item.duration_d),
            )
        except (TypeError, ValueError) as exc:
            msg = f"shipments[{index}] invalid: {exc}"
            raise HTTPException(
                status_code=422,
                detail=_error_body(error_type="validation_error", message=msg),
            ) from exc
    if not isinstance(item, dict):
        msg = f"shipments[{index}] must be an object or ShipmentTrace"
        raise HTTPException(
            status_code=422,
            detail=_error_body(error_type="validation_error", message=msg),
        )
    try:
        return ShipmentTrace(
            shipment_id=str(item["shipment_id"]),
            times_d=np.asarray(item["times_d"], dtype=float),
            temps_c=np.asarray(item["temps_c"], dtype=float),
            duration_d=float(item["duration_d"]),
        )
    except KeyError as exc:
        msg = f"shipments[{index}] missing field {exc.args[0]!r}"
        raise HTTPException(
            status_code=422,
            detail=_error_body(error_type="validation_error", message=msg),
        ) from exc
    except (TypeError, ValueError) as exc:
        msg = f"shipments[{index}] invalid: {exc}"
        raise HTTPException(
            status_code=422,
            detail=_error_body(error_type="validation_error", message=msg),
        ) from exc


def _hydrate_shipments(raw: Any) -> list[ShipmentTrace]:
    if not isinstance(raw, list) or not raw:
        msg = "config['shipments'] must be a non-empty list"
        raise HTTPException(
            status_code=422,
            detail=_error_body(error_type="validation_error", message=msg),
        )
    return [_as_shipment_trace(item, index=i) for i, item in enumerate(raw)]


def _config_with_shipments(config: dict[str, Any]) -> dict[str, Any]:
    """Demo-hydrate missing/empty shipments at the API edge (ADR 0107)."""
    cfg = ensure_demo_shipments(dict(config))
    # Always normalize so demo fixtures survive dual ShipmentTrace identities.
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


@app.post("/sessions/{session_id}/init", response_model=Snapshot)
def init_session(session_id: str, body: InitRequest) -> dict[str, Any]:
    session = _get_session(session_id)
    cfg = _config_with_shipments(body.config)
    return dict(session.init(cfg, seed=body.seed))


@app.post("/sessions/{session_id}/step", response_model=DayDelta)
def step_session(session_id: str, body: StepRequest) -> dict[str, Any]:
    session = _get_session(session_id)
    return dict(session.step(body.order_qty))


@app.post("/sessions/{session_id}/step_n", response_model=StepNResponse)
def step_n_session(session_id: str, body: StepNRequest) -> dict[str, Any]:
    session = _get_session(session_id)
    deltas = session.step_n(body.orders)
    return {"deltas": [dict(d) for d in deltas]}


@app.post("/sessions/{session_id}/reset", response_model=Snapshot)
def reset_session(session_id: str, body: ResetRequest) -> dict[str, Any]:
    session = _get_session(session_id)
    cfg = None if body.config is None else _config_with_shipments(body.config)
    return dict(session.reset(cfg, seed=body.seed))


@app.post("/sessions/{session_id}/act", response_model=DayDelta)
def act_session(session_id: str, body: ActRequest) -> dict[str, Any]:
    session = _get_session(session_id)
    return dict(session.act(policy=body.policy, **dict(body.budgets)))


@app.post("/sessions/{session_id}/set_obs_scenario", response_model=Snapshot)
def set_obs_scenario_session(
    session_id: str,
    body: SetObsScenarioRequest,
) -> dict[str, Any]:
    session = _get_session(session_id)
    return dict(session.set_obs_scenario(body.obs_scenario))
