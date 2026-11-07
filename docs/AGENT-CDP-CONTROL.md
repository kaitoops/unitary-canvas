# AGENT-CDP：外部 Agent 操控 VM 内画布手册

> 读者：运行在**宿主机**上的 AI Agent，需要通过 CDP 远程驱动运行在
> **Hyper-V VM 内**的画布应用。全部经验来自真实运行，每条坑都踩过。

## 1. 连接建立

### 1.1 找到 VM 与 CDP 端点

```powershell
# 宿主上执行，免凭据。IP 每次重启/恢复都变，必须动态解析：
$ip = (Get-VM "CanvasVM").NetworkAdapters[0].IPAddresses[0]
curl http://"$ip`:9223/json/list      # 页面 target 列表
```

- 页面 target 特征：`url` 含 `tauri.localhost`
- `webSocketDebuggerUrl` 即操纵入口

### 1.2 会话模式

```python
import json, urllib.request, websocket

with urllib.request.urlopen(f"http://{VM_IP}:9223/json/list") as r:
    pages = json.loads(r.read().decode())
target = next(p for p in pages if "tauri.localhost" in p["url"])
ws = websocket.create_connection(target["webSocketDebuggerUrl"],
                                 timeout=15, suppress_origin=True)

def ev(expr):  # 万能求值
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                        "params": {"expression": expr,
                                   "returnByValue": True,
                                   "awaitPromise": True}}))
    while True:
        m = json.loads(ws.recv())
        if m.get("id") == 1:
            return m["result"]
```

## 2. 常用操纵模式（附真实参数）

| 目的 | CDP 方法 | 要点 |
|---|---|---|
| 执行 JS | `Runtime.evaluate` | `awaitPromise:true` 必加，否则 async 结果丢失 |
| 强制刷新 | `Page.reload` `{"ignoreCache":true}` | 资产更新后必须 ignoreCache |
| 截图 | `Page.captureScreenshot` | 返回 base64 PNG，直接落盘即可 |
| 点击 | JS `element.click()` 优先 | 坐标点击用 `Input.dispatchMouseEvent`（CSS 坐标，非截图像素） |
| 填提示词 | `execCommand("insertText")` | 见 §3.2，React 受控组件直接改 value 无效 |
| 资产拦截 | `Fetch.enable` + `Fetch.fulfillRequest` | shim 核心模式，见 §4 |

## 3. 应用内操作的正确姿势（血泪坑位表）

### 3.1 localStorage：必须绕过应用的 Storage 包装

画布对 `window.localStorage` 做了代理包装，**直接写会被过滤/回写**。
正解：用 iframe 取原始 Storage：

```js
var f = document.createElement("iframe");
f.style.display = "none";
document.documentElement.appendChild(f);
var raw = f.contentWindow.localStorage;   // ← 原始 Storage，绕过包装
raw.setItem(key, value);
f.remove();
```

另注意：Tauri 磁盘缓存（`Documents/API settings storage/`）会反向
水合，覆盖 localStorage 的 API 配置——配置注入前先处理磁盘缓存，
或用「劫持内置条目」方案避开。

### 3.2 contenteditable 提示词输入

```js
el.focus();
document.execCommand("insertText", false, prompt);  // 触发 React onChange
```

`el.innerText = ...` 或直接改 textContent **不触发**框架状态更新。

### 3.3 注入样式/节点的自愈

React 重渲染会重挂容器，吹掉外部注入的样式与节点。正解：
**1 秒间隔自愈重挂**（幂等检查后再补），且验收要等 ≥20 秒稳定期，
加载初期的样式丢失是正常现象，不是失效。

### 3.4 完成检测：认落盘，不认 DOM（铁律）

生成完成的判定**只认末端产物**——VM 磁盘目录
`Documents\QiaodouCache\images\` 出现新 PNG（全尺寸 ~1MB/张）：

- 节点内渲染走 `asset.localhost` 文件引用 + blob 变体，DOM 轮询不可靠；
- 桌宠动画是 spritesheet，会被误判为「新图」。

```powershell
# VM 端轮询（经 PS Direct 触发或常驻）
Get-ChildItem "$env:USERPROFILE\Documents\QiaodouCache\images" -Filter *.png
```

### 3.5 PS Direct 的会话边界

`Invoke-Command -VMName` 跑在**非交互会话**：
- 枚举不到交互桌面的窗口（MainWindowHandle 恒空）
- 改原生窗口属性（WM_SETICON 等）必须经**计划任务在交互会话执行**
  （`schtasks /Run`，任务 XML 带 `/IT` 交互标记）

### 3.6 跨工具编码（Windows 特供坑）

PowerShell 5.1 读无 BOM UTF-8 按 GBK 解码 → 乱码仍以 [200] 发出。
跨工具交接文件统一 **UTF-8 with BOM**（Python 用 `utf-8-sig`），
或干脆全 ASCII。批跑成败只认结构化状态码，「无异常」≠成功。

## 4. 运行态资产替换（Fetch 拦截 shim）模式

```python
# 1) 附着页面 target 后：
ws.send(json.dumps({"id":1,"method":"Fetch.enable","params":{"patterns":[
    {"urlPattern":"http://tauri.localhost/*","requestStage":"Request"}]}}))
# 2) 收到 Fetch.requestPaused → 命中替换表则
#    Fetch.fulfillRequest(body=base64(新资产))，否则 Fetch.continueRequest
# 3) 页面 reload 后生效；shim 常驻进程启动时缓存资产字节——
#    重建资产后必须重启 shim
```

适用场景：不改 VM 内任何文件、可秒级回退的运行态改写。持久层
（标题/图标）不在此列——原生窗口标题走 Tauri `__TAURI__.window`
 setTitle（若 ACL 放行），窗口图标被 ACL 拦时走 §3.5 的 Win32 路线。

## 5. 安全边界

- CDP 9223 = 完全控制权，**只暴露在 VM 内部 vSwitch**，禁止端口转发到外网；
- shim/网关绑定 0.0.0.0 时确保宿主防火墙规则仅限 vSwitch 网段；
- localStorage 里可能有 API key 类值，注入脚本输出不要回显全量。
