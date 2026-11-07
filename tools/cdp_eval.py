#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reusable CDP evaluator for the canvas page (canvas VM, port 9223).

Usage:
  python cdp_eval.py '<js expression>'          # sync eval (auto-await promise)
  python cdp_eval.py --file script.js          # eval contents of a JS file
  python cdp_eval.py --raw '<js expression>'   # no awaitPromise, returnByValue
"""
import json
import sys
import urllib.request
import websocket  # pip package: websocket-client

CDP_HOST = "127.0.0.1:9223"  # set to your canvas VM IP


def get_page_ws():
    with urllib.request.urlopen(
        "http://%s/json/list" % CDP_HOST, timeout=5
    ) as r:
        targets = json.loads(r.read().decode("utf-8"))
    for t in targets:
        if t.get("type") == "page":
            return t["webSocketDebuggerUrl"]
    raise RuntimeError("no page target found: %r" % targets)


def eval_js(expr, timeout=30):
    ws_url = get_page_ws()
    ws = websocket.create_connection(
        ws_url, timeout=timeout, suppress_origin=True
    )
    try:
        ws.send(
            json.dumps(
                {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": expr,
                        "returnByValue": True,
                        "awaitPromise": True,
                    },
                }
            )
        )
        deadline = time.time() + timeout
        while time.time() < deadline:
            msg = json.loads(ws.recv())
            if msg.get("id") == 1:
                return msg
        raise TimeoutError("CDP eval timeout")
    finally:
        ws.close()


import time  # noqa: E402  (used inside eval_js)

if __name__ == "__main__":
    args = sys.argv[1:]
    raw = "--raw" in args
    if raw:
        args.remove("--raw")
    if args and args[0] == "--file":
        with open(args[1], "r", encoding="utf-8") as f:
            expr = f.read()
    else:
        expr = args[0]
    resp = eval_js(expr, timeout=90)
    result = resp.get("result", {})
    if "exceptionDetails" in resp.get("result", {}):
        # exceptionDetails lives at top level of the response result dict
        pass
    exc = result.get("exceptionDetails")
    out = {"ok": exc is None, "value": result.get("result", {}).get("value")}
    if exc:
        out["exception"] = exc
    sys.stdout.buffer.write(
        json.dumps(out, ensure_ascii=False, indent=1).encode("utf-8")
    )
    sys.stdout.buffer.write(b"\n")
