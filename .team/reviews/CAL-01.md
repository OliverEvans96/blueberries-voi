# CAL-01 — Definition of done (calendar realism)

STATUS: APPROVED  
DATE: 2026-08-13  
TICKETS: T-077–T-087 (close-out **T-088**; Wave 0 architect **T-076**)  
ADRS: 0109–0113 (ACCEPTED)

CAL-01 calendar realism is **complete pending human merge** to `main`. Agents did
**not** merge to `main`; landing on the parent branch is a human decision.

## Definition of done checklist

- [x] Track A–C implement tips complete for **T-077–T-087** (OrderSchedule, FreshNet
      demand product, episode/controllers, CRN day demand, Snapshot/web next-order and
      demand UI).
- [x] ADRs **0109–0113** ACCEPTED (MWF base case, calendar demand, OrderSchedule API,
      FreshNet derived product, track ownership).
- [x] Client-voice changelog: new Mon/Wed/Fri delivery + calendar demand base case;
      prior daily / i.i.d. citeable VOI numbers require regeneration.
- [x] VOI / CRN smoke under MWF + demand profile green (see `.team/qa/T-088.md`).
- [x] FIL-13 measured-L remotesure note recorded (no joint-production reopen).
- [x] Plan `.team/plans/CAL-01-calendar-realism.md` marked COMPLETE pending human merge.
- [x] Backlog CAL-01 closeout pending human merge; T-071 xdist flake note retained.
- [x] Agents did **not** merge to `main` / force-push / edit `.github/workflows/`.

## Non-goals (binding — asserted)

- [x] **Not** reopening X-06 (cadence as VOI axis) or VOI-02 honesty arms.
- [x] **Not** full overnight production VOI grid / citeable regen in this milestone.
- [x] **Not** FreshNet two-stage latent recovery as production prior.
- [x] **Not** collapsing physics to weekly ticks.
- [x] **Not** reopening joint / `K^L` production filter (FIL-13 remotesure only).

## Non-claims

CAL-01 does **not** claim citeable science VOI under the new base case until a fresh
production regeneration lands. Prior daily / i.i.d. VOI headlines are obsolete for
citation. Measured filter L under the old cadence/demand may be stale — remotesure
before citing L-dependent filter claims.
