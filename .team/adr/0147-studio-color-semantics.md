# ADR 0147: Studio color semantics (belief / truth / forecast)

**Status:** ACCEPTED  
**Date:** 2026-08-25  
**Scope:** `web/` Studio embed only (not VitePress docs theme)

## Context

Studio charts and chrome mixed several ad-hoc hues for the same roles:

- Belief used yellow (`#e6b800`) in histograms and MAE tables while heatmaps already used green (`#2f5d4a`).
- Truth overlays used blue (`#2563eb`) in secondary histograms while trajectories used orange (`#f97316`).
- Truth UI chrome used burgundy (`#8a2f1f`) disconnected from chart truth orange.
- Forecast/demand charts fell back to generic blue accent (`#2563eb`) instead of the existing sales blue (`#3d7ea6`).

This made belief vs truth vs forecast hard to read at a glance and broke cross-chart consistency.

## Decision

Introduce semantic CSS custom properties on `.bv-studio` and align chart palettes to them:

| Token | Value | Role |
|-------|-------|------|
| `--belief` | `#2f5d4a` | Belief mass, MAE chrome, arrival prior |
| `--belief-soft` | `#9bbf9a` | Soft belief fills |
| `--truth` | `#f97316` | Truth trajectories and histogram bars |
| `--truth-strong` | `#c2410c` | Truth toggle, chips, cross markers |
| `--truth-sold` | `#0891b2` | Sold terminal dots |
| `--truth-spoiled` | `#c026d3` | Spoiled terminal dots |
| `--forecast` | `#3d7ea6` | Demand/sales forecast lines (alias of `--sales`) |
| `--forecast-band` | `color-mix(...)` | Forecast confidence bands |

Backward-compat chart aliases: `--chart-accent`, `--chart-band`, `--chart-muted`, `--chart-ink`.

Export matching constants from `beliefFreshnessPalette.ts` for SVG fills that cannot read CSS vars at build time.

Retire `#e6b800`, `#2563eb` (as truth), and `#8a2f1f` from belief/truth chart and UI paths. Vitest guard enforces this.

Freshness histogram draw order: belief bars first, truth bars on top (higher opacity).

## Consequences

- Studio embed patch bump (`web/package.json`) — publishable `dist-lib` CSS changed.
- Docs VitePress theme unchanged.
- OKLab separation tests updated: sold cyan vs truth orange instead of vs blue.

## Alternatives considered

- Keep yellow belief bars for contrast — rejected; green belief is the user-approved direction and matches heatmaps.
- Use blue for truth histogram — rejected; orange truth is consistent with trajectory overlay palette (ADR heatmap design).
