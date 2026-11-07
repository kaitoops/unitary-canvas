#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Canvas-ComfyUI protocol gateway.

Translates OpenAI-style requests from the canvas UI into ComfyUI
/prompt workflow submissions on the local host ComfyUI (port 8189).

Endpoints:
  GET  /v1/models                 -> model list (connection test)
  POST /v1/images/generations     -> Qwen-Image-2.1 turbo T2I (sync, b64_json)
  POST /v1/images/edits           -> Qwen-Image-Edit-2511 I2I (sync, b64_json)
  POST /v1/video/generations      -> MiniMax H3 Director t2v (async task)
  GET  /v1/tasks/{id}             -> task status {status, progress, video_url}
  GET  /files/{name}              -> serve generated files (CORS enabled)
  POST /v1/chat/completions       -> minimal canned chat reply

Run:  python gateway.py   (listens 0.0.0.0:8190)
"""
import base64
import json
import os
import re
import sys
import threading
import time
import traceback
import urllib.parse
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST_PORT = 8190
COMFY = "http://127.0.0.1:8189"
SELF_URL = "http://127.0.0.1:8190"  # set to the host IP visible from the VM canvas

HERE = os.path.dirname(os.path.abspath(__file__))
FILES_DIR = os.path.join(HERE, "gateway_files")
os.makedirs(FILES_DIR, exist_ok=True)

LOG_LOCK = threading.Lock()
LOG_PATH = os.path.join(HERE, "gateway.log")


def log(msg):
    line = "[%s] %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    with LOG_LOCK:
        try:
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass
    print(line, flush=True)


def comfy_post(path, payload, timeout=30):
    req = urllib.request.Request(
        COMFY + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def comfy_get(path, timeout=15):
    with urllib.request.urlopen(COMFY + path, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def comfy_history(prompt_id):
    try:
        return comfy_get("/history/%s" % prompt_id)
    except Exception:
        return {}


def comfy_view_bytes(filename, subfolder, ftype):
    q = urllib.parse.urlencode(
        {"filename": filename, "subfolder": subfolder or "", "type": ftype or "output"}
    )
    with urllib.request.urlopen(COMFY + "/view?" + q, timeout=60) as r:
        return r.read()


def wait_history(prompt_id, timeout_sec, poll=2.0, progress_cb=None):
    """Poll /history until the prompt finishes. Returns outputs dict or None."""
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        h = comfy_history(prompt_id)
        entry = h.get(prompt_id)
        if entry:
            status = entry.get("status", {})
            if status.get("completed"):
                return entry.get("outputs", {})
            st = status.get("status_str")
            if st in ("error", "failed"):
                return None
        if progress_cb:
            try:
                q = comfy_get("/queue")
                running = [x[1] for x in q.get("queue_running", [])]
                progress_cb("running" if prompt_id in running else "queued")
            except Exception:
                pass
        time.sleep(poll)
    return None


# --------------------------------------------------------------------------
# Qwen-Image-2.1 turbo T2I graph
# --------------------------------------------------------------------------

QWEN_T2I = {
    "unet": "qwen_image_2.1_turbo_int8_convrot.safetensors",
    "clip": "qwen3.5_9b_qwen_image_2.1_pe_t2i.int8_convrot.safetensors",
    "vae": "qwen_image_2.1_vae_bf16.safetensors",
    "steps": 8,
    "cfg": 1.0,
    "sampler": "euler",
    "scheduler": "simple",
}


# Qwen-Image-2.1 turbo T2I graph, mirrors the official ComfyUI template
# (image_qwen_image_2_1_turbo_t2i.json subgraph, minus the prompt enhancer).
# Official wiring: QwenImage21Cache(UNET) -> CFGGuider(cfg=1) ->
# SamplerCustomAdvanced(RandomNoise, KSamplerSelect(euler), ManualSigmas,
# EmptyLatentImage). Text encoder clip is qwen3vl_8b; the pe_t2i clip in the
# template belongs to the (skipped) prompt-enhancer LLM.
TURBO_SIGMAS = ("1.0, 0.978453, 0.95418, 0.926626, 0.89508, "
                "0.845148, 0.704534, 0.414568, 0")


def build_t2i_graph(prompt, negative, width, height, seed):
    return {
        "1": {"class_type": "UNETLoader",
              "inputs": {"unet_name": QWEN_T2I["unet"], "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader",
              "inputs": {"clip_name": "qwen3vl_8b_int8_convrot.safetensors",
                         "type": "qwen_image", "device": "default"}},
        "3": {"class_type": "VAELoader",
              "inputs": {"vae_name": QWEN_T2I["vae"]}},
        "4": {"class_type": "QwenImage21Cache",
              "inputs": {"model": ["1", 0], "device": "auto", "dtype": "default"}},
        "5": {"class_type": "TextEncodeQwenImage21",
              "inputs": {"clip": ["2", 0], "prompt": prompt,
                         "negative_prompt": negative or "",
                         "resolution": min(width, height)}},
        "6": {"class_type": "CFGGuider",
              "inputs": {"model": ["4", 0], "positive": ["5", 0],
                         "negative": ["5", 1], "cfg": 1.0}},
        "7": {"class_type": "RandomNoise",
              "inputs": {"noise_seed": seed}},
        "8": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "9": {"class_type": "ManualSigmas", "inputs": {"sigmas": TURBO_SIGMAS}},
        "10": {"class_type": "EmptyLatentImage",
               "inputs": {"width": width, "height": height, "batch_size": 1}},
        "11": {"class_type": "SamplerCustomAdvanced",
               "inputs": {"noise": ["7", 0], "guider": ["6", 0],
                          "sampler": ["8", 0], "sigmas": ["9", 0],
                          "latent_image": ["10", 0]}},
        "12": {"class_type": "VAEDecode",
               "inputs": {"samples": ["11", 0], "vae": ["3", 0]}},
        "13": {"class_type": "SaveImage",
               "inputs": {"images": ["12", 0], "filename_prefix": "gateway/t2i"}},
    }


# --------------------------------------------------------------------------
# MiniMax H3 Director t2v graph (proven end-to-end 2026-11-06)
# --------------------------------------------------------------------------

H3_T2V_TIMELINE_TEMPLATE = None


def build_t2v_graph(prompt, width, height, frames, fps, seed, filename_prefix):
    # timeline JSON string: same patch logic as the proven e2e script
    d = {
        "width": width, "height": height,
        "totalFrames": frames, "frameRate": fps,
        "refMaxSize": max(width, height),
        "global": {"taskType": "t2v", "prompt": prompt},
        "output": {"mode": "fixed", "width": width, "height": height,
                   "longEdge": max(width, height)},
        "segments": [{"start": 0, "length": frames, "frameCount": frames,
                      "durationSec": round(frames / fps, 4), "prompt": prompt}],
        "gen": {"defaultFrameCount": frames},
    }
    timeline = json.dumps(d, ensure_ascii=False, separators=(",", ":"))
    return {
        "1": {"class_type": "UNETLoader",
              "inputs": {"unet_name": "minimax_h3_fl2va_pruned_int8_convrot.safetensors",
                         "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader",
              "inputs": {"clip_name": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
                         "type": "minimax", "device": "default"}},
        "3": {"class_type": "VAELoader",
              "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
        "4": {"class_type": "VAELoader",
              "inputs": {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"}},
        "0": {"class_type": "LoraLoaderModelOnly",
              "inputs": {"model": ["1", 0],
                         "lora_name": "minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors",
                         "strength_model": 1.0}},
        "5": {"class_type": "MiniMaxH3Director",
              "inputs": {"model": ["0", 0], "video_vae": ["3", 0], "audio_vae": ["4", 0],
                         "clip": ["2", 0], "task_type": "t2v", "global_prompt": prompt,
                         "bd_grp_sample": "sample", "cfg": 1.0, "seed": seed,
                         "frame_rate": fps, "width": width, "height": height,
                         "ref_max_size": max(width, height), "total_frames": frames,
                         "timeline_data": timeline, "bd_grp_advanced": "advanced",
                         "steps": 8, "sampler": "res_multistep", "scheduler": "simple",
                         "shift_video": 12.0, "shift_audio": 3.0,
                         "bd_grp_perf": "perf", "clear_vram_between_segments": True,
                         "export_source_images": False}},
        "6": {"class_type": "CreateVideo",
              "inputs": {"images": ["5", 0], "fps": ["5", 2], "audio": ["5", 1],
                         "bit_depth": 8}},
        "7": {"class_type": "SaveVideo",
              "inputs": {"video": ["6", 0], "filename_prefix": filename_prefix,
                         "format": "auto", "codec": "auto"}},
    }


# --------------------------------------------------------------------------
# Task store for async video jobs
# --------------------------------------------------------------------------

TASKS = {}
TASKS_LOCK = threading.Lock()


def set_task(task_id, **kw):
    with TASKS_LOCK:
        t = TASKS.setdefault(task_id, {"status": "queued", "progress": 0})
        t.update(kw)
        return t


def image_task_runner(task_id, graph):
    """Background T2I job: submit, poll, store b64 result on the task."""
    return _image_finish_task(task_id, None, graph, 900)


def _image_finish_task(task_id, prompt_id, graph, timeout_sec):
    try:
        set_task(task_id, status="processing", progress=10)
        if not prompt_id:
            resp = comfy_post("/prompt", {"prompt": graph,
                                          "client_id": "protocol-gateway"})
            prompt_id = resp.get("prompt_id")
            set_task(task_id, prompt_id=prompt_id, progress=20)
        outputs = wait_history(prompt_id, timeout_sec)
        if not outputs:
            set_task(task_id, status="failed",
                     error="ComfyUI job failed or timed out")
            return
        data = []
        for _nid, out in outputs.items():
            for f in out.get("images", []):
                b = comfy_view_bytes(f["filename"], f.get("subfolder"),
                                     f.get("type", "output"))
                data.append({"b64_json": base64.b64encode(b).decode("ascii")})
        if not data:
            set_task(task_id, status="failed", error="no image in outputs")
            return
        set_task(task_id, status="completed", progress=100, data=data)
        log("image task %s completed (%d img)" % (task_id, len(data)))
    except Exception as e:
        log("image task %s exception: %s" % (task_id, e))
        set_task(task_id, status="failed", error=str(e))


def video_task_runner(task_id, graph):
    try:
        set_task(task_id, status="running", progress=5)
        resp = comfy_post("/prompt", {"prompt": graph, "client_id": "protocol-gateway"})
        prompt_id = resp.get("prompt_id")
        set_task(task_id, prompt_id=prompt_id, progress=10)
        outputs = wait_history(
            prompt_id, 1500,
            progress_cb=lambda s: set_task(task_id, status=s, progress=15),
        )
        if outputs is None:
            set_task(task_id, status="failed",
                     error="ComfyUI job failed or timed out")
            return
        # find a video file in outputs
        for _nid, out in outputs.items():
            for key in ("videos", "gifs", "video", "images"):
                for f in out.get(key, []) or []:
                    if f.get("type") == "output" or key != "images":
                        data = comfy_view_bytes(
                            f["filename"], f.get("subfolder"), f.get("type", "output")
                        )
                        local = os.path.join(FILES_DIR, "%s_%s" % (task_id, f["filename"]))
                        with open(local, "wb") as fh:
                            fh.write(data)
                        url = "%s/files/%s_%s" % (SELF_URL, task_id, f["filename"])
                        set_task(task_id, status="completed", progress=100,
                                 video_url=url, file=local)
                        log("task %s completed -> %s" % (task_id, url))
                        return
        set_task(task_id, status="failed", error="no video file in outputs")
    except Exception as e:
        log("task %s exception: %s\n%s" % (task_id, e, traceback.format_exc()))
        set_task(task_id, status="failed", error=str(e))


# --------------------------------------------------------------------------
# Request parsing helpers
# --------------------------------------------------------------------------

def parse_size(size, default=1024):
    """Map canvas size hints to (width, height) rounded to /16."""
    if not size:
        return default, default
    s = str(size).strip()
    m = re.match(r"^(\d{2,5})\s*[xX\*]\s*(\d{2,5})$", s)
    if m:
        w, h = int(m.group(1)), int(m.group(2))
    elif s in ("1K", "1k"):
        w, h = 1024, 1024
    elif s in ("2K", "2k"):
        w, h = 2048, 2048
    elif s in ("480P", "480p"):
        w, h = 832, 480
    elif s in ("720P", "720p"):
        w, h = 1280, 720
    elif s in ("1080P", "1080p"):
        w, h = 1920, 1088
    else:
        w, h = default, default
    r = lambda x: max(64, min(2048, (int(x) + 15) // 16 * 16))
    return r(w), r(h)


def parse_duration(duration, default_sec=4.0):
    m = re.search(r"(\d+(?:\.\d+)?)", str(duration or ""))
    sec = float(m.group(1)) if m else default_sec
    sec = max(1.0, min(10.0, sec))
    frames = int(round(sec * 24.0))
    return max(17, min(145, frames)), 24.0


# --------------------------------------------------------------------------
# HTTP handler
# --------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    server_version = "CanvasGateway/1.0"

    def log_message(self, fmt, *args):
        log("%s %s" % (self.address_string(), fmt % args))

    # -- plumbing ----------------------------------------------------------
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods",
                         "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers",
                         "Authorization, Content-Type")

    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def _read_json(self):
        try:
            return json.loads(self._read_body().decode("utf-8"))
        except Exception:
            return {}

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    # -- routes -------------------------------------------------------------
    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/v1/models":
            return self._send(200, {
                "object": "list",
                "data": [
                    {"id": "qwen-image-2.1-turbo", "object": "model",
                     "owned_by": "comfy-local"},
                    {"id": "qwen-image-edit-2511", "object": "model",
                     "owned_by": "comfy-local"},
                    {"id": "h3-director-t2v", "object": "model",
                     "owned_by": "comfy-local"},
                ],
            })
        m = re.match(r"^/v1/tasks/([\w-]+)$", path)
        if not m:
            m = re.match(r"^/v1/images/tasks/([\w-]+)$", path)
        if m:
            with TASKS_LOCK:
                t = dict(TASKS.get(m.group(1)) or {})
            if not t:
                return self._send(404, {"status": "failed", "error": "unknown task"})
            return self._send(200, t)
        if path.startswith("/files/"):
            name = os.path.basename(urllib.parse.unquote(path[len("/files/"):]))
            fp = os.path.join(FILES_DIR, name)
            if not os.path.isfile(fp):
                return self._send(404, {"error": "not found"})
            ctype = "video/mp4" if name.endswith(".mp4") else (
                "image/png" if name.endswith(".png") else "application/octet-stream")
            with open(fp, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self._cors()
            self.end_headers()
            self.wfile.write(body)
            return
        return self._send(404, {"error": "not found: %s" % path})

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        try:
            if path == "/v1/images/generations":
                return self.handle_images_generations()
            if path == "/v1/images/edits":
                return self.handle_images_edits()
            if path == "/v1/video/generations":
                return self.handle_video_generations()
            if path == "/v1/chat/completions":
                return self.handle_chat()
            return self._send(404, {"error": "not found: %s" % path})
        except Exception as e:
            log("ERROR %s: %s\n%s" % (path, e, traceback.format_exc()))
            return self._send(500, {"error": {"message": str(e)}})

    # -- image T2I -----------------------------------------------------------
    def handle_images_generations(self):
        # async mode: canvas retries with ?async=true after a ~45s sync
        # timeout, then polls /v1/images/tasks/{id}
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        async_mode = "async" in q
        body = self._read_json()
        prompt = (body.get("prompt") or "").strip()
        if not prompt:
            return self._send(400, {"error": {"message": "prompt required"}})
        w, h = parse_size(body.get("size"))
        seed = int(body.get("seed") or uuid.uuid4().int & 0x7FFFFFFF)
        n = int(body.get("n") or 1)
        graph = build_t2i_graph(prompt, body.get("negative_prompt") or "", w, h, seed)
        log("T2I %dx%d n=%d async=%s prompt=%r" % (w, h, n, async_mode,
                                                   prompt[:80]))
        if async_mode:
            task_id = uuid.uuid4().hex[:16]
            set_task(task_id, status="queued", progress=0, kind="image")
            th = threading.Thread(target=image_task_runner,
                                  args=(task_id, graph), daemon=True)
            th.start()
            return self._send(200, {"id": task_id, "task_id": task_id,
                                    "taskId": task_id, "status": "queued",
                                    "progress": 0})
        try:
            resp = comfy_post("/prompt", {"prompt": graph,
                                          "client_id": "protocol-gateway"})
        except Exception as e:
            return self._send(502, {"error": {"message": "ComfyUI submit failed: %s" % e}})
        prompt_id = resp.get("prompt_id")
        # bounded wait for small/fast jobs; if not done, promote to a task so
        # the canvas can poll /v1/tasks or /v1/images/tasks
        outputs = wait_history(prompt_id, 40)
        if not outputs:
            task_id = uuid.uuid4().hex[:16]
            set_task(task_id, status="processing", progress=30,
                     prompt_id=prompt_id, kind="image")
            th = threading.Thread(target=_image_finish_task,
                                  args=(task_id, prompt_id, None, 900),
                                  daemon=True)
            th.start()
            return self._send(200, {"id": task_id, "task_id": task_id,
                                    "taskId": task_id, "status": "processing",
                                    "progress": 30})
        data = []
        for _nid, out in outputs.items():
            for f in out.get("images", []):
                b = comfy_view_bytes(f["filename"], f.get("subfolder"),
                                     f.get("type", "output"))
                data.append({"b64_json": base64.b64encode(b).decode("ascii")})
        return self._send(200, {"created": int(time.time()), "data": data})

    # -- image I2I (multipart) ------------------------------------------------
    def handle_images_edits(self):
        ctype = self.headers.get("Content-Type", "")
        mm = re.search(r"boundary=([^;]+)", ctype)
        if not mm:
            return self._send(400, {"error": {"message": "multipart required"}})
        boundary = mm.group(1).encode("utf-8")
        raw = self._read_body()
        parts = raw.split(b"--" + boundary)
        prompt, image_bytes = "", None
        for p in parts:
            if b"Content-Disposition" not in p:
                continue
            head, _, val = p.partition(b"\r\n\r\n")
            val = val.rsplit(b"\r\n", 1)[0]
            name_m = re.search(rb'name="([^"]*)"', head)
            name = name_m.group(1).decode() if name_m else ""
            if name == "prompt":
                prompt = val.decode("utf-8", "replace").strip()
            elif name in ("image", "image[]"):
                if val[:4] not in (b"",):
                    image_bytes = val
        if not prompt or not image_bytes:
            return self._send(400, {"error": {"message":
                "prompt and image required (got prompt=%s, image=%s)" %
                (bool(prompt), bool(image_bytes))}})
        # upload image into ComfyUI input dir via /upload/image
        b64img = base64.b64encode(image_bytes).decode("ascii")
        upname = "gateway_edit_%d.png" % int(time.time() * 1000)
        boundary2 = "----GwBoundary%s" % uuid.uuid4().hex[:8]
        mp = (
            ("--%s\r\nContent-Disposition: form-data; name=\"image\"; "
             "filename=\"%s\"\r\nContent-Type: image/png\r\n\r\n") % (boundary2, upname)
        ).encode() + image_bytes + (
            ("\r\n--%s\r\nContent-Disposition: form-data; "
             "name=\"overwrite\"\r\n\r\ntrue\r\n--%s--\r\n") % (boundary2, boundary2)
        ).encode()
        req = urllib.request.Request(
            COMFY + "/upload/image", data=mp, method="POST",
            headers={"Content-Type": "multipart/form-data; boundary=" + boundary2})
        with urllib.request.urlopen(req, timeout=60) as r:
            up = json.loads(r.read().decode())
        sub = up.get("subfolder", "")
        img_ref = up["name"] if not sub else "%s/%s" % (sub, up["name"])

        seed = uuid.uuid4().int & 0x7FFFFFFF
        graph = {
            "1": {"class_type": "UNETLoader",
                  "inputs": {"unet_name": "qwen_image_edit_2511_int8_convrot.safetensors",
                             "weight_dtype": "default"}},
            "2": {"class_type": "CLIPLoader",
                  "inputs": {"clip_name": "qwen3.5_9b_qwen_image_2.1_pe_i2i.int8_convrot.safetensors",
                             "type": "qwen_image", "device": "default"}},
            "3": {"class_type": "VAELoader",
                  "inputs": {"vae_name": "qwen_image_2.1_vae_bf16.safetensors"}},
            "4": {"class_type": "CFGNorm", "inputs": {"model": ["1", 0], "strength": 1.0}},
            "5": {"class_type": "LoadImage", "inputs": {"image": img_ref}},
            "6": {"class_type": "TextEncodeQwenImageEditPlus",
                  "inputs": {"clip": ["2", 0], "prompt": prompt,
                             "negative_prompt": "", "images": [["5", 0]],
                             "vae": ["3", 0]}},
            "7": {"class_type": "KSampler",
                  "inputs": {"model": ["4", 0], "seed": seed, "steps": 8, "cfg": 1.0,
                             "sampler_name": "euler", "scheduler": "simple",
                             "denoise": 1.0, "positive": ["6", 0],
                             "negative": ["6", 1], "latent_image": ["6", 2]}},
            "8": {"class_type": "VAEDecode",
                  "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
            "9": {"class_type": "SaveImage",
                  "inputs": {"images": ["8", 0], "filename_prefix": "gateway/edit"}},
        }
        log("I2I edit prompt=%r img=%s (%d bytes)" % (prompt[:80], img_ref,
                                                      len(image_bytes)))
        try:
            resp = comfy_post("/prompt", {"prompt": graph,
                                          "client_id": "protocol-gateway"})
        except Exception as e:
            return self._send(502, {"error": {"message": "ComfyUI submit failed: %s" % e}})
        outputs = wait_history(resp.get("prompt_id"), 900)
        if not outputs:
            return self._send(504, {"error": {"message": "generation timeout/failed"}})
        data = []
        for _nid, out in outputs.items():
            for f in out.get("images", []):
                b = comfy_view_bytes(f["filename"], f.get("subfolder"),
                                     f.get("type", "output"))
                data.append({"b64_json": base64.b64encode(b).decode("ascii")})
        return self._send(200, {"created": int(time.time()), "data": data})

    # -- video T2V (async task) ------------------------------------------------
    def handle_video_generations(self):
        body = self._read_json()
        prompt = (body.get("prompt") or "").strip()
        if not prompt:
            return self._send(400, {"error": {"message": "prompt required"}})
        w, h = parse_size(body.get("size"), default=512)
        if (w, h) == (1024, 1024):  # square default makes no sense for video
            w, h = 512, 288
        if body.get("size") in ("720P", "720p", "1080P", "1080p", "480P", "480p"):
            w, h = parse_size(body.get("size"))
            if h > w:
                w, h = h, w
        frames, fps = parse_duration(body.get("duration"))
        seed = uuid.uuid4().int & 0x7FFFFFFF
        task_id = uuid.uuid4().hex[:16]
        prefix = "video/gw_%s" % task_id
        graph = build_t2v_graph(prompt, w, h, frames, fps, seed, prefix)
        log("T2V %dx%d %d frames prompt=%r" % (w, h, frames, prompt[:80]))
        set_task(task_id, status="queued", progress=0, prompt_id=None)
        th = threading.Thread(target=video_task_runner, args=(task_id, graph),
                              daemon=True)
        th.start()
        return self._send(200, {"id": task_id, "task_id": task_id,
                                "taskId": task_id, "status": "queued",
                                "progress": 0})

    # -- minimal chat ------------------------------------------------------------
    def handle_chat(self):
        body = self._read_json()
        model = body.get("model") or "gateway-local"
        reply = ("[protocol-gateway] This is a local ComfyUI bridge. "
                 "Chat is not bridged; use built-in text-to-image / "
                 "text-to-video features with models qwen-image-2.1-turbo "
                 "or h3-director-t2v.")
        return self._send(200, {
            "id": "chatcmpl-gw-%s" % uuid.uuid4().hex[:8],
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": reply},
            }],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0,
                      "total_tokens": 0},
        })


def main():
    srv = ThreadingHTTPServer(("0.0.0.0", HOST_PORT), Handler)
    log("protocol gateway listening on 0.0.0.0:%d (self-url %s, comfy %s)"
        % (HOST_PORT, SELF_URL, COMFY))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
