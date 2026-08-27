# Window service-level ordering (ADR 0151)

Window **service-level** controllers invert a joint no-stockout objective over the
protection window: find the smallest order quantity whose probability of zero
missed demand across the window meets `alpha`, then damp with `rho`.

## `sla_mc` vs `sla_pb`

| Arm | Mechanism | Role |
|-----|-----------|------|
| `sla_mc` | CRN Monte Carlo paths via `protection_sim` | Oracle reference |
| `sla_pb` | Poisson-binomial supply + day-joint product | Fast path |

ρ under SLA is a deliberate service-for-waste trade (not Nahmias base-stock correction).

## In the code

| Piece | Location |
|-------|----------|
| Protection simulator | `crates/voi_core/src/protection_sim.rs` |
| MC / PB order rules | `sla_mc_order_f_belief`, `sla_pb_order_f_belief` |
| Session `act` arms | `crates/voi_core/src/session.rs` |

See also [ordering rule](./ordering-rule.md) and [protection demand](./protection-demand.md).
