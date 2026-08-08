#!/usr/bin/env python3
import argparse, os, shutil, subprocess, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def run(cmd, cwd=ROOT, check=True):
    print(f"[noor] $ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=cwd, check=check)

def wait_http(url, seconds=60):
    end = time.time() + seconds
    while time.time() < end:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status < 500:
                    return True
        except Exception:
            time.sleep(2)
    return False

def ensure_env():
    env = ROOT / '.env'
    if not env.exists():
        env.write_text((ROOT / '.env.example').read_text())
        print('[noor] created .env from .env.example')

def docker_mode():
    if not shutil.which('docker'):
        raise SystemExit('Docker is required for --mode docker')
    ensure_env()
    run(['docker','compose','up','-d','--build'])
    print('[noor] waiting for backend health')
    if not wait_http('http://localhost:8000/health', 120):
        raise SystemExit('Backend health check failed')
    print('[noor] Noor OS is online: frontend=http://localhost:3000 backend=http://localhost:8000/docs')

def local_mode():
    ensure_env()
    if not shutil.which('python') and not shutil.which('python3'):
        raise SystemExit('Python is required')
    if not shutil.which('npm'):
        raise SystemExit('npm is required')
    run([sys.executable,'-m','pip','install','-r','backend/requirements.txt'])
    run(['npm','install'], cwd=ROOT/'frontend')
    backend = subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--reload','--host','0.0.0.0','--port','8000'], cwd=ROOT/'backend')
    frontend = subprocess.Popen(['npm','run','dev'], cwd=ROOT/'frontend')
    try:
        while True:
            time.sleep(1)
            if backend.poll() is not None or frontend.poll() is not None:
                raise SystemExit('A Noor OS service exited')
    except KeyboardInterrupt:
        backend.terminate(); frontend.terminate()

if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--mode', choices=['docker','local'], default='docker')
    args=p.parse_args()
    docker_mode() if args.mode=='docker' else local_mode()
