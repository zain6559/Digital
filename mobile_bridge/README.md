# Noor Mobile Bridge

A small ADB-over-Wi-Fi helper used by Noor OS. It supports discovery/status, Android 11+ wireless pairing, persistent connect, and safe input commands through the backend policy layer.

```bash
python -m noor_mobile_bridge.cli discover
python -m noor_mobile_bridge.cli pair --host 192.168.1.20 --port 37123 --code 123456
python -m noor_mobile_bridge.cli connect --host 192.168.1.20 --port 5555
```
