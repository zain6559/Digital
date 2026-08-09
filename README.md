# Noor OS

Noor OS is a small local-first control-plane prototype: a FastAPI backend, a Next.js dashboard, an in-memory spatial memory index, a conservative browser search helper, a grid-based vision fallback, and an optional Android ADB command bridge.

It is not a conscious system, not a general autonomous operator, and not a multimodal image-understanding model. The current implementation favors explicit safety checks, event logging, and testable behavior over broad claims.

## What is implemented

- **Coordinator:** receives commands, evaluates policy risk, chooses a simple route, executes it, publishes events, and records task episodes.
- **Policy gate:** classifies requests using intent, context, action class, and confidence. High-risk user-visible or destructive actions pause for confirmation.
- **Memory:** stores memories in realms, prevents exact duplicate records, ranks search across title/content/tags, and keeps deterministic spatial coordinates.
- **Browser helper:** performs a rate-limited DuckDuckGo HTML search through Playwright when browser automation is enabled. It does not bypass login, CAPTCHA, or anti-bot controls.
- **Vision fallback:** validates frame metadata and returns a 3x3 grid target estimate from directional words. It does not identify visual objects without a real multimodal adapter.
- **Mobile bridge:** builds constrained ADB commands for device scan, tap, text, and wake actions. It validates arguments, times out hung commands, and reports failures explicitly.
- **WebSocket event bus:** publishes bounded event history to allowed origins configured by environment variables.
- **Health endpoint:** reports backend status, safe-default feature flags, persistence-file status, and bounded history limits. It is a readiness signal for the local service, not an external dependency monitor.
- **Cognitive core:** stores validated evidence, revisable beliefs, world relations, goals, predictions, outcome errors, learning statistics, and bounded autonomy ticks in checksum-backed JSON persistence with backup recovery. It is still bounded operational state, not consciousness.


## Release candidate operating notes

- Browser automation, mobile ADB control, and cloud LLM fallback are disabled by default in `.env.example` and must be explicitly enabled for local use.
- If port 8000 is already in use, set `NOOR_BACKEND_PORT` before starting, for example `NOOR_BACKEND_PORT=8765 python start.py --mode local`. Local startup checks for an occupied backend port before launching services; Docker maps the configured host port to the same configured container port.
- WebSocket replay is bounded, and allowed origins default to local frontend origins only.
- WebSocket connections without an allowed `Origin` header are rejected by default.
- Cognitive state writes use a lock, fsynced temp-file replacement, checksum validation, and a backup file for recovery from corrupted primary state.
- The cognitive/operational core is inspectable prototype state: evidence, beliefs, plans, actions, skills, procedures, benchmarks, and debug traces are stored for audit, not as claims of consciousness or general autonomy.
- See `FINAL_RELEASE_REPORT.md` for the final release-candidate limits and verification scope.

## Quick start

```bash
cp .env.example .env
python start.py --mode docker
```

For local development:

```bash
python start.py --mode local
```

## Services

- Backend: http://localhost:8000
- Frontend: http://localhost:3000
- API docs: http://localhost:8000/docs

## Safety model

Defaults are intentionally conservative. Browser and mobile automation are disabled by default and can be enabled by configuration. CORS and WebSocket origins default to localhost frontend origins. Public posting and destructive operations should remain behind explicit confirmation and additional application-specific checks.
