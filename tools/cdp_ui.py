#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CDP UI driver for the VM canvas: synthetic mouse/keyboard + DOM queries.

Usage:
  python cdp_ui.py viewport
  python cdp_ui.py dblclick X Y
  python cdp_ui.py click X Y
  python cdp_ui.py type 'text'
  python cdp_ui.py key Enter
  python cdp_eval.py-style JS via:  python cdp_ui.py js '<expr>'
  python cdp_ui.py leaves           # dump visible leaf texts
"""
import json
import sys
import time
import urllib.request

import websocket

CDP_HOST = "127.0.0.1:9223"  # set to your canvas VM IP


class Ui:
    def __init__(self):
        with urllib.request.urlopen(
            "http://%s/json/list" % CDP_HOST, timeout=8
        ) as r:
            pages = json.loads(r.read().decode())
        self.ws = websocket.create_connection(
            pages[0]["webSocketDebuggerUrl"], timeout=30, suppress_origin=True
        )
        self.mid = 0

    def _send(self, method, params):
        self.mid += 1
        self.ws.send(json.dumps({"id": self.mid, "method": method,
                                 "params": params}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get("id") == self.mid:
                return m

    def js(self, expr, timeout=30):
        self.ws.settimeout(timeout)
        m = self._send("Runtime.evaluate",
                       {"expression": expr, "returnByValue": True,
                        "awaitPromise": True})
        r = m.get("result", {})
        exc = r.get("exceptionDetails")
        if exc:
            return {"ok": False, "exception": exc.get("exception", {}).get(
                "description", str(exc))[:400]}
        val = r.get("result", {})
        return {"ok": True, "value": val.get("value")}

    def _mouse(self, mtype, x, y, **kw):
        p = {"type": mtype, "x": x, "y": y}
        p.update(kw)
        self._send("Input.dispatchMouseEvent", p)

    def click(self, x, y):
        self._mouse("mouseMoved", x, y)
        time.sleep(0.05)
        self._mouse("mousePressed", x, y, button="left", clickCount=1)
        self._mouse("mouseReleased", x, y, button="left", clickCount=1)

    def dblclick(self, x, y):
        self.click(x, y)
        time.sleep(0.08)
        self._mouse("mousePressed", x, y, button="left", clickCount=2)
        self._mouse("mouseReleased", x, y, button="left", clickCount=2)

    def type(self, text):
        for ch in text:
            self._send("Input.dispatchKeyEvent",
                       {"type": "keyDown", "text": ch,
                        "unmodifiedText": ch})
            self._send("Input.dispatchKeyEvent",
                       {"type": "keyUp", "text": ch,
                        "unmodifiedText": ch})
            time.sleep(0.012)

    def key(self, name):
        codes = {"Enter": ("\r", "Enter"), "Escape": ("", "Escape"),
                 "Backspace": ("", "Backspace")}
        text, key = codes.get(name, ("", name))
        d = {"type": "keyDown", "key": key, "windowsVirtualKeyCode": 0}
        if text:
            d["text"] = text
        self._send("Input.dispatchKeyEvent", d)
        self._send("Input.dispatchKeyEvent",
                   {"type": "keyUp", "key": key,
                    "windowsVirtualKeyCode": 0})

    def leaves(self):
        r = self.js(
            "(()=>{const a=Array.from(document.querySelectorAll("
            "'div,span,li,a,button'));const o=[];a.forEach((e,i)=>{"
            "if(e.children.length===0){const s=(e.textContent||'').trim();"
            "const rc=e.getBoundingClientRect();"
            "if(s&&s.length<24&&rc.width>0)o.push(s+' @'+Math.round("
            "rc.x+rc.width/2)+','+Math.round(rc.y+rc.height/2))}});"
            "return o.join(' | ')})()")
        return r


def main():
    ui = Ui()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "leaves"
    if cmd == "viewport":
        print(json.dumps(ui.js("window.innerWidth+'x'+window.innerHeight")))
    elif cmd == "dblclick":
        ui.dblclick(int(sys.argv[2]), int(sys.argv[3]))
        print("dblclicked")
    elif cmd == "click":
        ui.click(int(sys.argv[2]), int(sys.argv[3]))
        print("clicked")
    elif cmd == "type":
        ui.type(sys.argv[2])
        print("typed")
    elif cmd == "key":
        ui.key(sys.argv[2])
        print("keyed")
    elif cmd == "js":
        print(json.dumps(ui.js(sys.argv[2], timeout=90), ensure_ascii=False))
    elif cmd == "leaves":
        print(ui.leaves()["value"])
    elif cmd == "wait":
        time.sleep(float(sys.argv[2]))
        print("waited")
    ui.ws.close()


if __name__ == "__main__":
    main()
