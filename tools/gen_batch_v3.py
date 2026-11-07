#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Batch-generate 10 icon candidates (v3).

Detection moved OFF the DOM: after CDP submit, poll the VM-side
QiaodouCache\\images dir (via PS Direct waiter) for a new PNG. Robust
against pet spritesheets / blob urls / asset-protocol quirks.
"""
import json
import os
import subprocess
import time
import urllib.request

import websocket

CDP_HOST = "127.0.0.1:9223"  # placeholder; auto-discovered at startup (see below)

# Deployment parameters — override via environment variables. NOTHING
# site-specific is hardcoded (no IPs, VM names, usernames or passwords).
ENV_VM_NAME = os.environ.get("YZ_VM_NAME", "canvas-vm")
ENV_VM_USER = os.environ.get("YZ_VM_USER", "wb")
ENV_VM_PASS = os.environ.get("YZ_VM_PASS", "")  # supply your own credential
ENV_WAIT_PS1 = os.environ.get("YZ_WAIT_PS1", "wait-image.ps1")


def discover_vm_ip():
    """Resolve the canvas VM IP via host Hyper-V (no credentials needed)."""
    global CDP_HOST
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         '(Get-VM "%s").NetworkAdapters[0].IPAddresses[0]' % ENV_VM_NAME],
        capture_output=True, text=True, timeout=30).stdout.strip()
    if out and out.count(".") == 3:
        CDP_HOST = "%s:9223" % out
OUT = os.path.dirname(os.path.abspath(__file__))
NODE_CENTER = [479, 425]
WAIT_PS1 = os.path.join(OUT, ENV_WAIT_PS1) if not os.path.isabs(ENV_WAIT_PS1) else ENV_WAIT_PS1

PROMPTS = [
    ("cand01_pointer_matrix", "极简扁平应用图标：一个整齐的圆形指针矩阵，四行四列共十六个圆形表盘单元，每个单元只有一根细长指针，没有刻度没有数字，所有指针的角度都从画面左下角外侧一个隐形中心点辐射而出，指向各自的位置，整体形成平滑旋转的向量场，紫蓝渐变霓虹发光，深色近黑圆角方形底，矢量极简风格，无文字，高对比度"),
    ("cand02_pointer_matrix_dense", "极简扁平应用图标：五行五列的圆形指针单元矩阵，每个圆形单元内一根发光细指针，所有指针围绕画面左下角外侧同一个隐形中心呈放射状取向，角度随位置平滑变化，如量子幺正演化的相位场，紫蓝渐变发光线条，深色圆角方形底，扁平矢量，无文字，无时钟刻度，极简高对比"),
    ("cand03_pointer_matrix_sparse", "极简扁平应用图标：三行三列九个较大的圆形表盘单元，每个圆内只有一根指针，指针全部指向画面左下角稍远处同一个中心点方向偏转各自的角度，旋转对称和谐统一，象征幺正矩阵，紫蓝渐变霓虹，深色近黑圆角方形底，矢量极简，无文字，无刻度"),
    ("cand04_pointer_field_glow", "极简扁平应用图标：圆形指针单元组成的方阵，每个单元是简单的圆形加一根指针，指针方向由画面左下角外侧一个共同中心决定，形成从左下向右上流动旋转的相位场，微弱光晕，紫蓝渐变，深色圆角方形底，极简扁平矢量风格，无文字，高对比"),
    ("cand05_pointer_matrix_hue", "极简扁平应用图标：四行四列圆形指针矩阵，每个圆形单元一根细指针，指针角度全部由画面左下角外一个隐形中心辐射决定，指针颜色按角度从紫到蓝渐变映射，形成彩虹相位环图案，深色圆角方形底，矢量扁平，无文字，无时钟刻度"),
    ("cand06_u_orbit", "极简扁平应用图标：发光的字母U由量子轨道环构成，一颗电子在环上，一条正弦波穿过U形，紫蓝渐变霓虹，深色圆角方形底，矢量风格，无文字，高对比度"),
    ("cand07_psi_wave", "极简扁平应用图标：发光的psi波函数符号，笔画由流动的粒子轨迹构成，量子力学主题，紫蓝渐变霓虹发光，深色近黑圆角方形底，扁平矢量，无文字，高对比"),
    ("cand08_linked_rings", "极简扁平应用图标：两个发光圆环相扣如链，粒子沿环流动保持能量守恒，象征幺正变换的可逆性，紫蓝渐变，深色圆角方形底，极简矢量，无文字"),
    ("cand09_vector_rotation", "极简扁平应用图标：抽象三维坐标系中一组等长发光箭头整体旋转排列，向量矩阵旋转对称，量子态空间美学，紫蓝渐变霓虹，深色圆角方形底，扁平矢量，无文字"),
    ("cand10_interference", "极简扁平应用图标：同心圆波纹干涉图案，中心一点，波纹由内向外扩散形成优美莫尔条纹，量子干涉之美，紫蓝渐变发光线条，深色圆角方形底，极简矢量，无文字"),
]

JS_PANEL_OPEN = "(function(){return !!document.querySelector('button.yaozhengdugui-gen-submit')})()"

JS_SET_PROMPT = """
(function(p){
  var el=Array.from(document.querySelectorAll("div[contenteditable=true]")).find(function(e){
    var r=e.getBoundingClientRect(); return r.width>300&&r.y>450;
  });
  if(!el)return "no-input";
  el.focus();
  var sel=window.getSelection(); sel.removeAllRanges();
  var range=document.createRange(); range.selectNodeContents(el); sel.addRange(range);
  document.execCommand("insertText",false,p);
  return (el.textContent||"").length;
})("%s")
"""

JS_CLICK_SUBMIT = """
(function(){
  var b=document.querySelector("button.yaozhengdugui-gen-submit");
  if(!b)return "no-btn";
  if(b.disabled)return "disabled";
  b.click(); return "clicked";
})()
"""


def get_ws():
    with urllib.request.urlopen("http://%s/json/list" % CDP_HOST, timeout=5) as r:
        pages = json.loads(r.read().decode())
    for p in pages:
        if p.get("type") == "page":
            return websocket.create_connection(p["webSocketDebuggerUrl"],
                                               timeout=30, suppress_origin=True)
    raise RuntimeError("no page")


_id = [0]


def ev(ws, expr, timeout=30):
    _id[0] += 1
    ws.send(json.dumps({"id": _id[0], "method": "Runtime.evaluate",
                        "params": {"expression": expr, "returnByValue": True,
                                   "awaitPromise": True}}))
    ws.settimeout(timeout)
    deadline = time.time() + timeout
    while time.time() < deadline:
        m = json.loads(ws.recv())
        if m.get("id") == _id[0]:
            res = m.get("result", {})
            if res.get("exceptionDetails"):
                return {"err": str(res["exceptionDetails"])[:200]}
            return res.get("result", {}).get("value")
    return {"err": "timeout"}


def click_node(ws):
    x, y = NODE_CENTER
    for t, kw in (("mousePressed", {"button": "left", "clickCount": 1}),
                  ("mouseReleased", {"button": "left", "clickCount": 1})):
        p = {"type": t, "x": x, "y": y}
        p.update(kw)
        ws.send(json.dumps({"id": _id[0] + 1000, "method": "Input.dispatchMouseEvent",
                            "params": p}))
        _id[0] += 1


def vm_now_iso():
    """Clock-sync probe via PS Direct; credentials come from the environment."""
    r = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-Command",
         '$cred = New-Object PSCredential("%s", (ConvertTo-SecureString '
         '"%s" -AsPlainText -Force));'
         'Invoke-Command -VMName "%s" -Credential $cred -ScriptBlock '
         '{ (Get-Date).AddSeconds(2).ToString("o") } -ErrorAction Stop'
         % (ENV_VM_USER, ENV_VM_PASS, ENV_VM_NAME)],
        capture_output=True, text=True, timeout=90)
    return r.stdout.strip()


def wait_new_image(iso, timeout=200):
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", WAIT_PS1, "-iso", iso],
            capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except subprocess.TimeoutExpired:
        return "TIMEOUT"


def main():
    ws = get_ws()
    results = []
    for name, prompt in PROMPTS:
        print("=== %s ===" % name, flush=True)
        if ev(ws, JS_PANEL_OPEN) is not True:
            click_node(ws)
            time.sleep(1.5)
            if ev(ws, JS_PANEL_OPEN) is not True:
                print("  !! panel closed, skip", flush=True)
                results.append((name, "panel-fail"))
                continue
        n = ev(ws, JS_SET_PROMPT % prompt.replace('\\', '\\\\').replace('"', '\\"'))
        if not isinstance(n, int) or n < 20:
            print("  !! prompt fail:", n, flush=True)
            results.append((name, "prompt-fail"))
            continue
        c = ev(ws, JS_CLICK_SUBMIT)
        print("  prompt %d chars, submit -> %s" % (n, c), flush=True)
        if c != "clicked":
            results.append((name, "submit-" + str(c)))
            continue
        t0 = time.time()
        ans = wait_new_image(vm_now_iso())
        print("  vm-wait -> %s (%.0fs)" % (ans, time.time() - t0), flush=True)
        results.append((name, ans))
        time.sleep(3)
    print("RESULTS " + json.dumps(results, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    try:
        discover_vm_ip()
    except Exception as _e:
        print("ip discover failed, fallback CDP_HOST:", _e)
    main()
