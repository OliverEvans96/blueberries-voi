# T-097 — acceptance criteria → tests (RED)

## Coverage of acceptance criteria

- `EngineSession.act(policy="damped_sw" | "sw")` returns a DayDelta (same top-level
  shape as `step`) without `unknown policy`
  → `tests/test_t097_act_damped_sw.py::test_act_damped_sw_aliases_return_day_delta`
  (params: `damped_sw`, `sw`, `Damped_SW`, `SW`)
  — currently failing: `ValueError: unknown policy '...'; use 'constant' or 'rollout'`

- For `damped_sw` / `sw`, order selection uses `DampedSurvivalWeightedPolicy` with
  `alpha`/`rho` from budgets when provided; defaults **alpha=0.9**, **rho=0.8**
  → `…::test_act_damped_sw_uses_default_alpha_0_9_and_rho_0_8`
  — currently failing: unknown policy before construction
  → `…::test_act_damped_sw_honours_alpha_rho_budget_overrides`
  — currently failing: unknown policy before construction
  → `…::test_act_rollout_base_uses_same_alpha_rho_defaults_and_overrides`
  — currently failing: rollout still builds `ConstantOrderPolicy(0)` (no SW spy hits)

- `act(policy="rollout" | "ctl" | "rollout_order")` calls `rollout_order` with
  `base_policy` an instance of `DampedSurvivalWeightedPolicy` (not
  `ConstantOrderPolicy(0)`), same alpha/rho defaults/overrides
  → `…::test_act_rollout_base_policy_is_damped_sw_not_constant_zero`
  (params: `rollout`, `ctl`, `rollout_order`)
  — currently failing: `base_policy` is `ConstantOrderPolicy`
  → `…::test_act_rollout_base_uses_same_alpha_rho_defaults_and_overrides`
  — currently failing: no `DampedSurvivalWeightedPolicy` construction on rollout

- Existing `constant` / `const` / `fixed` with `order_qty` / `q` still works;
  unknown policy `ValueError` mentions allowed names including `damped_sw` and
  `rollout`
  → `…::test_act_constant_aliases_still_honour_order_qty` — currently **passing**
  (regression lock)
  → `…::test_act_unknown_policy_error_mentions_damped_sw_and_rollout`
  — currently failing: message is `use 'constant' or 'rollout'` (no `damped_sw`)

- Budget overrides `H`, `n_rollout_paths`, `candidate_case_radius`, `n_particles`
  continue to update session dials and affect rollout
  → `…::test_act_budget_overrides_update_session_dials_and_rollout_kwargs`
  — currently **passing** (existing dial path); stays green while base policy changes

- ASGI `POST .../act` with `{ "policy": "damped_sw", "budgets": { "alpha": 0.9,
  "rho": 0.8 } }` returns 200 + DayDelta JSON
  → `…::test_asgi_act_damped_sw_with_alpha_rho_budgets_returns_200_day_delta`
  — currently failing: server raises `ValueError: unknown policy 'damped_sw'`

- Packaging/worker smoke / allowlist copy must accept `damped_sw` (no stale
  “constant or rollout only”)
  → `…::test_worker_smoke_policy_surfaces_accept_damped_sw_when_listing_act_policies`
  — currently failing: offender
  `src/blueberries_voi/simulator/session.py` (`use 'constant' or 'rollout'`)

## Not covered by tests

- TypeScript `ActOpts` / MockAdapter / studio UI — out of scope (T-098–T-100).
- ModelParams-from-sliders, decide-only peek, Rung-0 on `act` — out of scope.
- Exact unknown-policy wording beyond requiring substrings `damped_sw` and
  `rollout` — implementer may list aliases; verify by string contains.
- Full verify/CI coverage gate — verifier owns once GREEN.

## RED evidence

```bash
cd /home/oliver/blog/blueberries-voi/.worktrees/T-097-qa
uv sync --all-extras --python 3.11
uv run pytest tests/test_t097_act_damped_sw.py --no-cov -q
```

Result (qa tip): **13 failed, 4 passed** in ~4.6s.

Failure reasons (right-cause summary):

| Failure class | Cause |
|---------------|--------|
| damped_sw / sw aliases + alpha/rho spies + ASGI | `unknown policy`; only constant/rollout known |
| rollout base isinstance | `base_policy` is `ConstantOrderPolicy` |
| unknown-policy message / worker allowlist scan | stale `use 'constant' or 'rollout'` copy |

Passed (intentional locks): three constant aliases; budget dials → `rollout_order` kwargs.
