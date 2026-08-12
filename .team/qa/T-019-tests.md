# T-019 test map (RED)

STATUS: PASS — sim emits `pack_date` on delivery; Stage A F2a contracts.

## Coverage of acceptance criteria

- Delivery DayLog emits real `pack_date` →
  `tests/test_pack_date_emit.py::test_delivery_daylog_emits_real_pack_date`
  → also tightened
  `tests/test_sim.py::test_daylog_receipt_metadata_delivery_vs_none`
  — PASS
- Non-delivery leaves `pack_date` None (FIL-08) →
  `tests/test_pack_date_emit.py::test_non_delivery_daylog_pack_date_remains_none`
  — PASS
- CRN-stable pack_date sequence →
  `tests/test_pack_date_emit.py::test_pack_date_crn_stable_across_identical_runs`
  — PASS (non-vacuous: at least one real pack_date)
- F2a mask observes sim pack_date; P0/P1 UNOBSERVED →
  `tests/test_pack_date_emit.py::test_f2a_mask_observes_sim_pack_date_p0_p1_do_not`
  — PASS
- Sim→F2a birth prior narrower than cold Abdella →
  `tests/test_pack_date_emit.py::test_f2a_birth_prior_from_sim_daylog_narrower_than_cold`
  — PASS
- Stage A F2a contracts under smoke →
  `tests/test_pack_date_emit.py::test_stage_a_f2a_contracts_when_pack_date_emitted`
  — PASS (`contracted=True`)


## Not covered by tests

- Full republish of `experiments/m15_stage_a_result.md` — implementer / verifier
  after GREEN; unit smoke asserts contraction only
- Backlog / changelog resolve — post-GREEN (verifier + changelog skill)
- Exact episode calendar epoch for synthetic pack_date — open in spec; tests
  lock presence, CRN stability, mask projection, and Stage A contraction
