# T-134 test map (RED → GREEN)

| AC | Test |
|----|------|
| AC-1a | `t134_arrival_f::session_passes_precomputed_delivery_f` |
| AC-1b | `t134_arrival_f::voi_passes_precomputed_delivery_f` (source guard) |
| AC-2a | `shipments::mod21_demo_shipments_product_mix` |
| AC-2b | `shipments::truth_birth_from_trace_matches_age_to_f` |
| AC-3 | `t134_arrival_f::filter_birth_f2_dirac_from_age_at_receipt` |
| AC-4a | `session::parse_shipments_hydrates_from_arrival_product` |
| AC-4b | `session::parse_shipments_defaults_to_abdella_all_demo_mix`, `session::rpc_default_shipments_when_none_sent` |
