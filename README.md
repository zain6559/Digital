# Noor OS

Noor OS is a local-first agentic control plane with a FastAPI backend, Next.js sci-fi dashboard, spatial memory realms, browser automation with human-in-the-loop safeguards, and an Android ADB-over-Wi-Fi mobile bridge.

## Critical self-critique and enhanced blueprint

The initial architecture was intentionally broad. The implementation hardens it in several ways:

- **Mobile streaming latency:** raw WebSocket frame forwarding can stutter under LAN jitter, so the bridge exposes adaptive telemetry, bitrate/FPS controls, and a decoupled input channel. The backend is structured so WebRTC or scrcpy H.264 forwarding can replace MJPEG-like frame transport without changing the UI contract.
- **Agent race conditions:** all tasks flow through a coordinator, policy gate, task registry, and serialized event bus. Risky actions enter `requires_confirmation` instead of running concurrently.
- **Browser-account safety:** Noor OS does not implement CAPTCHA bypass, anti-bot evasion, or covert automation. Playwright runs in persistent, user-visible profiles with rate limits and checkpoint detection.
- **Vector-memory sprawl:** memories are assigned to spatial realms by semantic keywords and deterministic coordinates, giving stable 3D layouts while supporting future embedding-based clustering.
- **WebGL rendering drops:** the frontend separates the Three.js sphere, React Flow graph, and memory realm canvas into focused components using bounded node counts, CSS GPU transforms, and state stores.
- **Operational resilience:** service health checks, migration bootstrap, Docker Compose, and a one-click launcher are included.

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
- Qdrant: http://localhost:6333

## Safety model

High-risk actions such as public posting, destructive file operations, shell execution, mobile input injection, and account changes require explicit policy approval. The browser engine pauses for login, MFA, CAPTCHA, and suspicious-activity checkpoints.
