# ENG-01 dual-mode readiness — Definition of done

STATUS: APPROVED  
DATE: 2026-08-13  
TICKETS: T-070–T-075  
ADRS: 0107–0108

## Checklist

- [x] ADR 0107 / 0108 accepted; plan `ENG-01-readiness.md` maps T-070–T-075
- [x] Demo hydrate at API + Pyodide worker/RPC edges (T-071); EngineSession stays strict
- [x] Vite serves worker + local wheel; worker honors `wheelUrl` (T-072)
- [x] CORSMiddleware for local Vite → API (T-073)
- [x] Studio footer/env/errors for live adapters (T-074)
- [x] Live HTTP + live Pyodide smoke evidence PASS (`.team/qa/T-075-smoke.md`)
- [x] Agents did **not** merge to `main` / force-push

## Non-goals (explicit)

- Live edits to GitHub Actions workflow files (human / privileged)
- Production deploy / CDN hosting
- Citeable science VOI headlines
- Arrival-only filter stream (T-067–T-069 / ADR 0105–0106)

## Needs-human (optional follow-ups)

- Publish / symlink Release + CI workflows from `packaging/github-workflows/` (existing T-046 needs-human)
- Consider lazy-importing `pyarrow` out of the default simulator import path so browser Pyodide need not load pyarrow
- Human merge of readiness tip to `main` when ready
