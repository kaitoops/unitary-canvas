#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Resolve the canvas VM CDP endpoint without hardcoding an IP.

The VM takes a new DHCP address after every restore/saved-state resume.
A stale constant makes CDP tools attach to nothing and the rename shim
fail silently (see docs/TROUBLESHOOTING.md).

Resolution order: $CANVAS_VM_IP > 127.0.0.1:9223 (host portproxy) >
Hyper-V Get-VM running adapter IPv4 > FALLBACK.
Each candidate is validated with GET /json/version, not just TCP connect.
"""
import json
import os
import re
import subprocess
import time
import urllib.request

FALLBACK = "127.0.0.1"
CDP_PORT = 9223
TTL = 60

_cache = {"host": None, "ts": 0.0}

_PS = (
    "$vm = Get-VM | Where-Object {$_.State -eq 'Running'} | Select-Object -First 1;"
    "if ($vm) { ($vm | Get-VMNetworkAdapter).IPAddresses |"
    " Where-Object {$_ -match '^\\d+\\.\\d+\\.\\d+\\.\\d+$'} | Select-Object -First 1 }"
)


def _alive(ip, timeout=2.0):
    url = "http://%s:%d/json/version" % (ip, CDP_PORT)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def _from_hyperv():
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", _PS],
            capture_output=True, text=True, timeout=25,
        ).stdout
    except Exception:
        return None
    for line in out.splitlines():
        s = line.strip()
        if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", s):
            return s
    return None


def vm_ip(force=False):
    if not force and _cache["host"] and time.time() - _cache["ts"] < TTL:
        return _cache["host"]

    cands = []
    env = os.environ.get("CANVAS_VM_IP", "").strip()
    if env:
        cands.append(env)
    cands.append("127.0.0.1")
    found = _from_hyperv()
    if found:
        cands.append(found)
    cands.append(FALLBACK)

    for ip in cands:
        if _alive(ip):
            _cache.update(host=ip, ts=time.time())
            return ip

    _cache.update(host=FALLBACK, ts=time.time())
    return FALLBACK


def cdp_host():
    return "%s:%d" % (vm_ip(), CDP_PORT)


def vm_state():
    """Best-effort VM state for diagnostics: Running / Saved / Off / unknown."""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "(Get-VM | Select-Object -First 1).State"],
            capture_output=True, text=True, timeout=20,
        ).stdout.strip()
        return out or "unknown"
    except Exception:
        return "unknown"


if __name__ == "__main__":
    host = cdp_host()
    print(host)
    if not _alive(host.split(":")[0]):
        print("WARN: %s not reachable; VM state=%s" % (host, vm_state()))
