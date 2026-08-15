# T-110 tests

- `tests/test_t110_engine_session_rust.py`: mock `_core.PyEngineSession` under `BLUEBERRIES_VOI_BACKEND=rust` — init/step/reset/act hit the fake; `step_n` one crossing; python backend does not construct PyO3.
