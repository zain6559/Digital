import os
import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import start


def test_windows_resolves_npm_cmd_first():
    seen = []
    def resolver(name):
        seen.append(name)
        return f"C:/nodejs/{name}" if name == "npm.cmd" else None
    assert start.resolve_command("npm", resolver=resolver, is_windows=True) == "C:/nodejs/npm.cmd"
    assert seen[0] == "npm.cmd"


def test_windows_npm_missing_but_npm_cmd_present_works():
    def resolver(name):
        return "C:/nodejs/npm.cmd" if name == "npm.cmd" else None
    assert start.resolve_command("npm", resolver=resolver, is_windows=True).endswith("npm.cmd")


def test_missing_node_or_npm_has_clear_message(monkeypatch, capsys):
    monkeypatch.setattr(start, "resolve_command", lambda name: None)
    with pytest.raises(SystemExit) as exc:
        start.ensure_node_tools()
    output = capsys.readouterr().out
    assert "Node.js/npm was not found" in output
    assert "node --version" in output
    assert "Missing required command" in str(exc.value)


def test_frontend_dependencies_ready_skips_install(tmp_path, monkeypatch):
    frontend = tmp_path / "frontend"
    bin_dir = frontend / "node_modules" / ".bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / ("next.cmd" if os.name == "nt" else "next")).write_text("")
    monkeypatch.setattr(start, "FRONTEND", frontend)
    called = []
    monkeypatch.setattr(start, "run", lambda *a, **k: called.append((a, k)))
    start.ensure_frontend_dependencies("npm")
    assert called == []


def test_frontend_dependencies_missing_installs(tmp_path, monkeypatch):
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "package-lock.json").write_text("{}")
    monkeypatch.setattr(start, "FRONTEND", frontend)
    called = []
    monkeypatch.setattr(start, "run", lambda cmd, cwd=start.ROOT, check=True, env=None: called.append((cmd, cwd)))
    start.ensure_frontend_dependencies("npm.cmd")
    assert called == [(["npm.cmd", "ci"], frontend)]


def test_python_dependencies_ready_skips_pip(tmp_path, monkeypatch):
    req = tmp_path / "requirements.txt"
    req.write_text("pytest==8.3.4\n")
    monkeypatch.setattr(start, "python_dependencies_ready", lambda: True)
    called = []
    monkeypatch.setattr(start, "run", lambda *a, **k: called.append((a, k)))
    start.ensure_python_dependencies()
    assert called == []


def test_backend_port_occupied_fails_clearly():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    port = sock.getsockname()[1]
    try:
        with pytest.raises(SystemExit) as exc:
            start.assert_free_port("0.0.0.0", str(port))
        assert "already in use" in str(exc.value)
    finally:
        sock.close()


def test_backend_healthy_starts_frontend(monkeypatch):
    monkeypatch.setattr(start, "ensure_env", lambda: {"NOOR_BACKEND_HOST": "127.0.0.1", "NOOR_BACKEND_PORT": "9000"})
    monkeypatch.setattr(start, "ensure_node_tools", lambda: ("node", "npm"))
    monkeypatch.setattr(start, "print_diagnostics", lambda *a: None)
    monkeypatch.setattr(start, "ensure_python_dependencies", lambda: None)
    monkeypatch.setattr(start, "ensure_frontend_dependencies", lambda npm: None)
    monkeypatch.setattr(start, "assert_free_port", lambda h, p: None)
    calls = []
    class Proc:
        def __init__(self): self.returncode = None
        def poll(self): return None
    def fake_popen(cmd, cwd, env):
        calls.append(cmd)
        return Proc()
    monkeypatch.setattr(start, "popen", fake_popen)
    monkeypatch.setattr(start, "wait_http", lambda url, seconds=60: True)
    def fake_sleep(_):
        raise KeyboardInterrupt
    monkeypatch.setattr(start.time, "sleep", fake_sleep)
    monkeypatch.setattr(start, "terminate", lambda children: None)
    with pytest.raises(KeyboardInterrupt):
        start.local_mode()
    assert len(calls) == 2
    assert calls[1][:3] == ["npm", "run", "dev"]


def test_backend_unhealthy_does_not_start_frontend(monkeypatch):
    monkeypatch.setattr(start, "ensure_env", lambda: {"NOOR_BACKEND_HOST": "127.0.0.1", "NOOR_BACKEND_PORT": "9001"})
    monkeypatch.setattr(start, "ensure_node_tools", lambda: ("node", "npm"))
    monkeypatch.setattr(start, "print_diagnostics", lambda *a: None)
    monkeypatch.setattr(start, "ensure_python_dependencies", lambda: None)
    monkeypatch.setattr(start, "ensure_frontend_dependencies", lambda npm: None)
    monkeypatch.setattr(start, "assert_free_port", lambda h, p: None)
    calls = []
    class Proc:
        def poll(self): return None
    monkeypatch.setattr(start, "popen", lambda cmd, cwd, env: calls.append(cmd) or Proc())
    monkeypatch.setattr(start, "wait_http", lambda url, seconds=60: False)
    monkeypatch.setattr(start, "terminate", lambda children: None)
    with pytest.raises(SystemExit) as exc:
        start.local_mode()
    assert "frontend was not started" in str(exc.value)
    assert len(calls) == 1


def test_terminate_cleans_children(monkeypatch):
    events = []
    class Proc:
        pid = 12345
        def __init__(self): self.alive = True
        def poll(self): return None if self.alive else 0
        def terminate(self): events.append("terminate"); self.alive = False
        def kill(self): events.append("kill"); self.alive = False
        def wait(self, timeout=None): events.append("wait"); return 0
    monkeypatch.setattr(start.os, "name", "nt", raising=False)
    start.terminate([Proc()])
    assert "terminate" in events
    assert "wait" in events
