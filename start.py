#!/usr/bin/env python3
import argparse, os, shutil, signal, subprocess, sys, time, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def run(cmd,cwd=ROOT,check=True):
    print(f"[noor] $ {' '.join(map(str,cmd))}", flush=True); return subprocess.run(cmd,cwd=cwd,check=check)
def wait_http(url,seconds=60):
    end=time.time()+seconds; last='not checked'
    while time.time()<end:
        try:
            with urllib.request.urlopen(url,timeout=2) as r:
                if r.status<500: return True
                last=f'HTTP {r.status}'
        except Exception as exc: last=str(exc); time.sleep(2)
    print(f'[noor] health check failed for {url}: {last}', file=sys.stderr); return False
def ensure_env():
    env=ROOT/'.env'; example=ROOT/'.env.example'
    if not env.exists():
        if not example.exists(): raise SystemExit('Missing .env and .env.example; create configuration before starting')
        env.write_text(example.read_text()); print('[noor] created .env from .env.example')
def require(name, hint):
    if not shutil.which(name): raise SystemExit(hint)
def _backend_host_port():
    return os.environ.get('NOOR_BACKEND_HOST','0.0.0.0'), os.environ.get('NOOR_BACKEND_PORT','8000')
def docker_mode():
    require('docker','Docker is required for --mode docker'); ensure_env(); run(['docker','compose','up','-d','--build'])
    _host, port = _backend_host_port()
    print(f'[noor] waiting for backend health on port {port}')
    if not wait_http(f'http://localhost:{port}/health',120):
        run(['docker','compose','logs','--tail','80'],check=False); raise SystemExit('Backend health check failed; recent logs printed above')
    print(f'[noor] online: frontend=http://localhost:3000 backend=http://localhost:{port}/docs')
def terminate(children):
    for proc in children:
        if proc.poll() is None: proc.terminate()
    deadline=time.time()+8
    for proc in children:
        if proc.poll() is None:
            try: proc.wait(max(0.1,deadline-time.time()))
            except subprocess.TimeoutExpired: proc.kill()
def local_mode():
    ensure_env(); require('npm','npm is required for --mode local')
    run([sys.executable,'-m','pip','install','-r','backend/requirements.txt']); run(['npm','install'],cwd=ROOT/'frontend')
    host, port = _backend_host_port()
    children=[subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--reload','--host',host,'--port',port],cwd=ROOT/'backend'), subprocess.Popen(['npm','run','dev'],cwd=ROOT/'frontend')]
    def stop(_sig=None,_frame=None): print('\n[noor] stopping services...', flush=True); terminate(children); sys.exit(0)
    signal.signal(signal.SIGTERM, stop); signal.signal(signal.SIGINT, stop)
    while True:
        time.sleep(1)
        exited=[p for p in children if p.poll() is not None]
        if exited:
            code=exited[0].returncode; terminate(children); raise SystemExit(f'A Noor OS service exited unexpectedly with code {code}. If backend failed to bind, set NOOR_BACKEND_PORT to a free port.')
if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--mode',choices=['docker','local'],default='docker'); args=p.parse_args(); docker_mode() if args.mode=='docker' else local_mode()
