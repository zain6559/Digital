import argparse, subprocess, shutil, sys

def adb_cmd(args):
    adb=shutil.which('adb')
    if not adb: raise SystemExit('adb executable not found')
    p=subprocess.run([adb]+args, text=True, capture_output=True)
    print(p.stdout, end=''); print(p.stderr, end='', file=sys.stderr); raise SystemExit(p.returncode)
def main():
    p=argparse.ArgumentParser(prog='noor-mobile'); sub=p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('discover'); pair=sub.add_parser('pair'); pair.add_argument('--host', required=True); pair.add_argument('--port', required=True); pair.add_argument('--code', required=True)
    con=sub.add_parser('connect'); con.add_argument('--host', required=True); con.add_argument('--port', default='5555')
    sub.add_parser('status'); sub.add_parser('disconnect')
    a=p.parse_args()
    if a.cmd=='discover' or a.cmd=='status': adb_cmd(['devices','-l'])
    if a.cmd=='pair': adb_cmd(['pair',f'{a.host}:{a.port}',a.code])
    if a.cmd=='connect': adb_cmd(['connect',f'{a.host}:{a.port}'])
    if a.cmd=='disconnect': adb_cmd(['disconnect'])
if __name__=='__main__': main()
