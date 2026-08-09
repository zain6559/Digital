#!/usr/bin/env python3
"""Cross-platform Noor OS launcher."""
from __future__ import annotations

import argparse
import importlib.metadata
import os
import platform
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Callable, Iterable

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"
BACKEND = ROOT / "backend"

CommandResolver = Callable[[str], str | None]


def log(message: str) -> None:
    print(f"[noor] {message}", flush=True)


def format_cmd(cmd: Iterable[object]) -> str:
    return " ".join(str(part) for part in cmd)


def run(cmd: list[str], cwd: Path = ROOT, check: bool = True, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    log(f"$ {format_cmd(cmd)}")
    try:
        return subprocess.run(cmd, cwd=cwd, check=check, env=env)
    except FileNotFoundError as exc:
        raise SystemExit(f"Command not found: {cmd[0]}. Ensure it is installed and available in PATH.") from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"Command failed with exit code {exc.returncode}: {format_cmd(cmd)}") from exc


def resolve_command(name: str, resolver: CommandResolver | None = None, is_windows: bool | None = None) -> str | None:
    resolver = resolver or shutil.which
    is_windows = (os.name == "nt") if is_windows is None else is_windows
    base = Path(name).name
    if Path(name).parent != Path('.'):
        return resolver(name)
    candidates = [base]
    if is_windows:
        candidates = [f"{base}.cmd", f"{base}.exe", base]
    elif base in {"npm", "node", "npx"}:
        candidates = [base, f"{base}.sh"]
    for candidate in candidates:
        found = resolver(candidate)
        if found:
            return found
    return None


def command_output(cmd: list[str]) -> str:
    try:
        out = subprocess.run(cmd, text=True, capture_output=True, check=False, timeout=8)
    except Exception as exc:
        return f"unavailable ({exc})"
    text = (out.stdout or out.stderr).strip().splitlines()
    return text[0] if text else f"exit {out.returncode}"


def ensure_node_tools() -> tuple[str, str]:
    node = resolve_command("node")
    npm = resolve_command("npm")
    if not node or not npm:
        log("Node.js/npm was not found.")
        log("Install Node.js LTS and ensure npm is available in PATH.")
        log("Verify with:\n        node --version\n        npm --version")
        missing = ", ".join(name for name, value in (("node", node), ("npm", npm)) if not value)
        raise SystemExit(f"Missing required command(s): {missing}")
    return node, npm


def print_diagnostics(node: str | None = None, npm: str | None = None) -> None:
    log(f"Platform: {platform.system() or sys.platform} {platform.release()} ({platform.machine()})")
    log(f"Python: {sys.version.split()[0]} at {sys.executable}")
    if node:
        log(f"Node: {command_output([node, '--version'])} at {node}")
    if npm:
        log(f"npm: {command_output([npm, '--version'])} at {npm}")


def wait_http(url: str, seconds: int = 60) -> bool:
    end = time.time() + seconds
    last = "not checked"
    while time.time() < end:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status < 500:
                    return True
                last = f"HTTP {r.status}"
        except Exception as exc:
            last = str(exc)
        time.sleep(2)
    print(f"[noor] health check failed for {url}: {last}", file=sys.stderr)
    return False


def ensure_env() -> dict[str, str]:
    env_file = ROOT / ".env"
    example = ROOT / ".env.example"
    if not env_file.exists():
        if not example.exists():
            raise SystemExit("Missing .env and .env.example; create configuration before starting")
        env_file.write_text(example.read_text(), encoding="utf-8")
        log("created .env from .env.example")
    env = os.environ.copy()
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    return env


def require(name: str, hint: str) -> str:
    found = resolve_command(name)
    if not found:
        raise SystemExit(hint)
    return found


def _backend_host_port(env: dict[str, str] | None = None) -> tuple[str, str]:
    source = env or os.environ
    return source.get("NOOR_BACKEND_HOST", "0.0.0.0"), source.get("NOOR_BACKEND_PORT", "8000")


def assert_free_port(host: str, port: str) -> None:
    bind_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    try:
        port_number = int(port)
    except ValueError:
        raise SystemExit(f"Invalid NOOR_BACKEND_PORT={port!r}; expected an integer TCP port.")
    if not 1 <= port_number <= 65535:
        raise SystemExit(f"Invalid NOOR_BACKEND_PORT={port!r}; expected a TCP port from 1 to 65535.")
    try:
        with socket.create_connection((bind_host, port_number), timeout=0.5):
            raise SystemExit(f"Backend port {port} is already in use on {bind_host}. Stop the existing service or run with NOOR_BACKEND_PORT=<free-port>.")
    except (ConnectionRefusedError, OSError):
        return


def python_dependencies_ready(requirements: Path = BACKEND / "requirements.txt") -> bool:
    for raw in requirements.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        name = line.split("==", 1)[0].split("[", 1)[0].strip()
        try:
            importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            return False
    return True


def ensure_python_dependencies() -> None:
    if python_dependencies_ready():
        log("Python dependencies: ready")
        return
    log("Installing missing Python dependencies...")
    run([sys.executable, "-m", "pip", "install", "-r", "backend/requirements.txt"])


def frontend_dependencies_ready(frontend: Path | None = None) -> bool:
    frontend = frontend or FRONTEND
    next_bin = frontend / "node_modules" / ".bin" / ("next.cmd" if os.name == "nt" else "next")
    return (frontend / "node_modules").is_dir() and next_bin.exists()


def ensure_frontend_dependencies(npm: str) -> None:
    if frontend_dependencies_ready():
        log("Frontend dependencies: ready")
        return
    log("Installing frontend dependencies...")
    install = "ci" if (FRONTEND / "package-lock.json").exists() else "install"
    run([npm, install], cwd=FRONTEND)


def docker_mode() -> None:
    docker = require("docker", "Docker is required for --mode docker")
    env = ensure_env()
    run([docker, "compose", "up", "-d", "--build"], env=env)
    _host, port = _backend_host_port(env)
    log(f"waiting for backend health on port {port}")
    if not wait_http(f"http://localhost:{port}/health", 120):
        run([docker, "compose", "logs", "--tail", "80"], check=False, env=env)
        raise SystemExit("Backend health check failed; recent logs printed above")
    log(f"online: frontend=http://localhost:3000 backend=http://localhost:{port}/docs")


def terminate(children: list[subprocess.Popen]) -> None:
    for proc in children:
        if proc.poll() is None:
            if os.name == "nt":
                proc.terminate()
            else:
                os.killpg(proc.pid, signal.SIGTERM)
    deadline = time.time() + 8
    for proc in children:
        if proc.poll() is None:
            try:
                proc.wait(max(0.1, deadline - time.time()))
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    proc.kill()
                else:
                    os.killpg(proc.pid, signal.SIGKILL)
    for proc in children:
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            pass


def popen(cmd: list[str], cwd: Path, env: dict[str, str]) -> subprocess.Popen:
    log(f"$ {format_cmd(cmd)}")
    kwargs = {"cwd": cwd, "env": env}
    if os.name != "nt":
        kwargs["start_new_session"] = True
    else:
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
    return subprocess.Popen(cmd, **kwargs)


def local_mode() -> None:
    env = ensure_env()
    node, npm = ensure_node_tools()
    print_diagnostics(node, npm)
    ensure_python_dependencies()
    ensure_frontend_dependencies(npm)
    host, port = _backend_host_port(env)
    assert_free_port(host, port)
    backend = popen([sys.executable, "-m", "uvicorn", "app.main:app", "--reload", "--host", host, "--port", port], BACKEND, env)
    children = [backend]
    if not wait_http(f"http://localhost:{port}/health", 90):
        terminate(children)
        raise SystemExit("Backend did not become healthy; frontend was not started.")
    log("Backend: ready")
    frontend = popen([npm, "run", "dev"], FRONTEND, env)
    children.append(frontend)
    log(f"online: frontend=http://localhost:3000 backend=http://localhost:{port}/docs")

    def stop(_sig=None, _frame=None) -> None:
        log("stopping services...")
        terminate(children)
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while True:
        time.sleep(1)
        exited = [p for p in children if p.poll() is not None]
        if exited:
            code = exited[0].returncode
            terminate(children)
            raise SystemExit(f"A Noor OS service exited unexpectedly with code {code}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["docker", "local"], default="docker")
    args = parser.parse_args()
    docker_mode() if args.mode == "docker" else local_mode()
