"""Yaozheng rename shim: CDP Fetch interception serving brand-free assets.

Attaches to the canvas page target, intercepts all http://tauri.localhost/*
requests, fulfills the patched assets (bundle/css/html) and continues
everything else. Survives page reloads; reconnects if the target restarts.

Run:  python rename_shim.py   (logs to shim.log)
"""
import base64
import json
import os
import sys
import time
import urllib.request
import websocket

CDP_HOST = "127.0.0.1:9223"  # fallback; auto-discovered at startup
VM_NAME = os.environ.get("YZ_VM_NAME", "canvas-vm")  # Hyper-V VM name for IP discovery
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shim.log")
WORKDIR = os.path.dirname(os.path.abspath(__file__))


def discover_vm_ip():
    """Resolve the canvas VM IP via host Hyper-V (no credentials needed).

    The VM's DHCP address churns between reboots (172.26/27/28.x observed);
    a stale CDP_HOST silently disables interception, so resolve it fresh.
    """
    global CDP_HOST
    try:
        import subprocess
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             '(Get-VM "%s").NetworkAdapters[0].IPAddresses[0]' % VM_NAME],
            capture_output=True, text=True, timeout=30).stdout.strip()
        if out and out.count(".") == 3:
            CDP_HOST = "%s:9223" % out
            log("CDP_HOST auto-discovered: %s" % CDP_HOST)
            return
    except Exception as e:
        log("ip discover failed (%s), fallback %s" % (e, CDP_HOST))

ASSETS = {
    "/": ("index_yz.html", "text/html; charset=utf-8"),
    "/index.html": ("index_yz.html", "text/html; charset=utf-8"),
    "/assets/index-KvvDjpOW.js": ("bundle_yz.js", "text/javascript; charset=utf-8"),
    "/assets/index-bbxvj1En.css": ("style_yz.css", "text/css; charset=utf-8"),
}

def log(msg):
    line = "%s %s" % (time.strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

BODIES = {}
for url_path, (fname, mime) in ASSETS.items():
    raw = open(os.path.join(WORKDIR, fname), "rb").read()
    BODIES[url_path] = (base64.b64encode(raw).decode("ascii"), mime, len(raw))
    log("loaded %s -> %s (%d bytes)" % (url_path, fname, len(raw)))

discover_vm_ip()

def get_target():
    try:
        pages = json.loads(urllib.request.urlopen(
            "http://%s/json/list" % CDP_HOST, timeout=5).read().decode())
    except Exception as e:
        log("target list error: %s" % e)
        return None
    for p in pages:
        if "tauri.localhost" in p.get("url", ""):
            return p
    return None

def serve_session(target):
    ws = websocket.create_connection(target["webSocketDebuggerUrl"],
                                    timeout=60, suppress_origin=True)
    mid = [0]

    def rpc(method, params):
        mid[0] += 1
        ws.send(json.dumps({"id": mid[0], "method": method,
                            "params": params}))

    rpc("Fetch.enable", {"patterns": [
        {"urlPattern": "http://tauri.localhost/*", "requestStage": "Request"}]})
    log("attached + Fetch.enabled on %s" % target.get("url"))
    ws.settimeout(15)
    served = continued = 0
    while True:
        try:
            m = json.loads(ws.recv())
        except websocket.WebSocketTimeoutException:
            continue
        except Exception as e:
            log("ws closed: %s" % e)
            ws.close()
            return served, continued
        if m.get("method") != "Fetch.requestPaused":
            continue
        p = m["params"]
        url = p.get("request", {}).get("url", "")
        path = url.split("tauri.localhost", 1)[-1].split("?")[0]
        entry = BODIES.get(path) or BODIES.get(path.rstrip("/") or "/")
        try:
            if entry:
                b64, mime, _n = entry
                rpc("Fetch.fulfillRequest", {
                    "requestId": p["requestId"],
                    "responseCode": 200,
                    "responseHeaders": [
                        {"name": "Content-Type", "value": mime},
                        {"name": "Cache-Control", "value": "no-store"},
                        {"name": "Access-Control-Allow-Origin", "value": "*"},
                    ],
                    "body": b64,
                })
                served += 1
                if served % 5 == 1:
                    log("served %s (%d total)" % (path, served))
            else:
                rpc("Fetch.continueRequest", {"requestId": p["requestId"]})
                continued += 1
        except Exception as e:
            log("respond error on %s: %s" % (path, e))
            try:
                rpc("Fetch.continueRequest", {"requestId": p["requestId"]})
            except Exception:
                pass

def main():
    log("=== yaozheng rename shim start (pid %d) ===" % os.getpid())
    idle = 0
    while True:
        t = get_target()
        if not t:
            idle += 1
            if idle % 12 == 1:
                log("waiting for canvas target...")
            time.sleep(5)
            continue
        idle = 0
        served, continued = serve_session(t)
        log("session ended (served=%d continued=%d), reattaching..." %
            (served, continued))
        time.sleep(2)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("shim stopped by user")
