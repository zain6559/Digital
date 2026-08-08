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
- **Cognitive core:** stores validated evidence, revisable beliefs, world relations, goals, predictions, outcome errors, learning statistics, and bounded autonomy ticks in JSON persistence. It is still a prototype, not consciousness.

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

Defaults are intentionally conservative. Browser and mobile automation can be disabled by configuration. CORS and WebSocket origins default to localhost frontend origins. Public posting and destructive operations should remain behind explicit confirmation and additional application-specific checks.
