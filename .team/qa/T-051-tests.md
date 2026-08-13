## Coverage of acceptance criteria

- Contract tests call HTTP `init` / `step` / `step_n` / `reset` / `act` via ASGI
  TestClient and validate responses with the same schema helpers as T-045
  → `tests/test_t051_api_contract.py::test_http_init_validates_with_t045_schema_helpers`
  → `tests/test_t051_api_contract.py::test_http_step_validates_with_t045_schema_helpers`
  → `tests/test_t051_api_contract.py::test_http_reset_validates_with_t045_schema_helpers`
  → `tests/test_t051_api_contract.py::test_http_act_validates_with_t045_schema_helpers`
  → `tests/test_t051_api_contract.py::test_http_step_n_three_orders_returns_three_validated_deltas`
  — currently **green** on T-050 tip (validators from T-045; ASGI from T-050)

- At least one test compares HTTP DayDelta/Snapshot shapes to golden fixtures
  (schema parity; key sets + belief flat lengths)
  → `tests/test_t051_api_contract.py::test_http_snapshot_shape_matches_golden_key_sets_and_belief_lengths`
  → `tests/test_t051_api_contract.py::test_http_day_delta_shape_matches_golden_key_sets_and_belief_lengths`
  → also step_n element parity in
    `test_http_step_n_three_orders_returns_three_validated_deltas`
  — currently **green** on T-050 tip (golden recipe seed 42)

- Tests assert forbidden presentation keys are absent from every interactive
  response
  → `tests/test_t051_api_contract.py::test_every_interactive_http_response_omits_presentation_keys`
  — currently **green** on T-050 tip

- `step_n` with three orders returns three deltas (or framed list length 3)
  → `tests/test_t051_api_contract.py::test_http_step_n_three_orders_returns_three_validated_deltas`
  — currently **green** on T-050 tip

- Failure path: bad session id → 404; malformed step body → 4xx
  → `tests/test_t051_api_contract.py::test_http_unknown_session_id_returns_404`
  → `tests/test_t051_api_contract.py::test_http_malformed_step_body_returns_4xx`
  → `tests/test_t051_api_contract.py::test_http_step_wrong_type_order_qty_returns_4xx`
  — currently **green** on T-050 tip

- OpenAPI describes the same schemas as golden fixtures (ADR 0100 §3; T-050
  deferred “OpenAPI schema field parity vs goldens” to T-051)
  → `tests/test_t051_api_contract.py::test_openapi_declares_snapshot_schema_matching_golden_keys`
  — currently failing: init 200 schema is `additionalProperties: true` with no
    Snapshot properties
  → `tests/test_t051_api_contract.py::test_openapi_declares_day_delta_schema_matching_golden_keys`
  — currently failing: step 200 schema is bare object (no DayDelta properties)
  → `tests/test_t051_api_contract.py::test_openapi_step_n_response_schema_frames_day_delta_list`
  — currently failing: step_n 200 schema has no `deltas` property

- `uv run pytest` for these tests passes
  — not a RED criterion here (implement + verifier gate). Verify by green
    `tests/test_t051_api_contract.py` after OpenAPI response models land.

## Not covered by tests

- Browser worker / Pyodide FFI (T-047) — out of scope.
- UI wiring (T-057) — out of scope.
- Exact byte equality of HTTP vs golden is optional per T-045/T-051; tests lock
  key sets + belief lengths (live tip currently matches bytes under seed 42, but
  that is not asserted).
