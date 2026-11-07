# AGENT-INSTALL：Agent 安装部署手册

> **本手册的读者是 AI Agent**（Claude / WorkBuddy / TRAE / 任何可执行
> PowerShell 与 Python 的自动化体），不是人类新手。行文按「可直接照做
> 的操作序列 + 每步验证点」组织。人类用户可把本文件直接投喂给 Agent。

## 0. 架构总览

```
┌─────────────────────── Windows 宿主机 ───────────────────────┐
│                                                              │
│  幺正工具链（本仓库）                                          │
│  ├─ protocol-gateway/gateway.py   :8190  OpenAI 图像协议 ⇄    │
│  │                                        ComfyUI /prompt 工作流 │
│  ├─ rename-shim/rename_shim.py    CDP Fetch 拦截 → 补丁资产    │
│  └─ cdp_eval.py / cdp_ui.py       CDP 驱动 / UI 自动化        │
│                                                              │
│  ComfyUI :8189（含 Qwen-Image-2.1 / Qwen3-VL-8B 模型）        │
│                                                              │
│  ┌──────────── Hyper-V VM（推荐安装位）──────────┐            │
│  │  画布本体 exe（用户自备副本，含 CDP 变体启动）    │            │
│  │  CDP 端口 :9223  ←──── 本仓库全部工具的操纵面    │            │
│  └────────────────────────────────────────────┘            │
└──────────────────────────────────────────────────────────────┘
```

三条网络边：`宿主→VM:9223`（CDP 操纵）、`画布→宿主:8190`（生成协议）、
`网关→宿主:8189`（ComfyUI 工作流）。

## 1. 前置条件清单

| 项 | 要求 | 验证命令 |
|---|---|---|
| 宿主 OS | Windows 10/11，管理员 | — |
| Hyper-V | 已启用，建有内部 vSwitch | `Get-VM` |
| VM | Windows 10/11 guest，2C/4G 起 | `Get-VM <name> | Select State` |
| Python | 3.11+，`websocket-client` 已装 | `python -c "import websocket"` |
| ComfyUI | 宿主 :8189，含 Qwen-Image-2.1 turbo + qwen3vl_8b | `curl http://127.0.0.1:8189/system_stats` |
| 画布副本 | 用户自备，版本见 COMPATIBILITY.md | `Get-FileHash` |

## 2. 安装序列（按序执行，每步有验证）

### 步骤 1：准备 VM

```powershell
# 建议专用 VM；已有则跳过。网络用内部 vSwitch + NAT。
New-VM -Name "CanvasVM" -MemoryStartupBytes 4GB -Generation 2
```

**验证**：`Get-VM CanvasVM` State=Running，guest 内可 ping 宿主。

### 步骤 2：部署画布本体（用户自备副本）

1. 在 VM 内安装画布本体（渠道自担，参考 DISCLAIMER.md）。
2. 用本仓库 `scripts/make-cdp-launcher.ps1` 生成 CDP 变体启动方式
   （核心：为 exe 追加 `--remote-debugging-port=9223`）。
3. **验证**：VM 内启动后，宿主执行
   `curl http://<VM_IP>:9223/json/version` 返回 JSON。
   `<VM_IP>` 获取方法见第 3 节。

### 步骤 3：VM IP 自动发现（重要基建）

VM 的 DHCP 地址**每次重启/恢复都会变**。所有工具必须动态解析，禁止硬编码：

```powershell
# 宿主上免凭据解析（Hyper-V 管理员权限）：
(Get-VM "CanvasVM").NetworkAdapters[0].IPAddresses[0]
```

本仓库的 `rename_shim.py` / `gen_batch.py` 已内置此发现逻辑，
CDP_HOST 常量仅作 fallback。**自己写工具时照抄此模式**——
CDP_HOST 过期的症状是「拦截/连接静默失效、页面回原版、无任何报错」。

### 步骤 4：启动协议网关

```bash
python protocol-gateway/gateway.py        # 监听 0.0.0.0:8190
curl http://127.0.0.1:8190/v1/models      # 验证：返回模型 JSON
```

网关把画布的 OpenAI 风格图像请求翻译成 ComfyUI `/prompt` 工作流。
实现细节与已知坑见 `docs/GATEWAY-NOTES.md`。

### 步骤 5：画布内接入网关（配置注入）

画布有两道硬编码防护，直接「新增自定义模型」会被静默丢弃：

1. `ensureDefaultModels` 启动时用内置列表重建，新 id 不收；
2. Tauri 磁盘缓存 `Documents/API settings storage/api-settings-cache.json`
   会反向水合覆盖 localStorage。

**正解（照做，勿自创）**：劫持**内置模型条目**的 url 字段指向
`http://<宿主IP>:8190`，并保持 `*_api_configs_revision` 原值不变。
本仓库 `tools/config-inject.js` 已实现（CDP 执行一次即可持久）。

**验证**：画布内用默认「GPT Image 2」节点出一张图，
图片落盘 `Documents\QiaodouCache\images\`。

### 步骤 6（可选）：品牌补丁 shim

```bash
python tools/build_patched.py && python rename-shim/rename_shim.py
```

shim 经 CDP Fetch 拦截在运行态替换资产，VM 零改动、可回退
（停 shim + 强刷 = 原版）。构建依赖从运行中画布提取的 live 资产，
提取方法见 COMPATIBILITY.md。

## 3. 全链路冒烟测试（Agent 验收清单）

```text
[ ] Get-VM 状态 Running
[ ] curl http://<VM_IP>:9223/json/version → JSON
[ ] curl http://127.0.0.1:8189/system_stats → JSON
[ ] curl http://127.0.0.1:8190/v1/models → JSON
[ ] CDP eval: document.title 符合预期
[ ] 画布内创建绘画节点 → 生成 → QiaodouCache\images 出现新 PNG
[ ] （若装 shim）Page.reload 后品牌资产为补丁版
```

任一项失败，按 `docs/TROUBLESHOOTING.md` 对号入座（共 12 个已知坑，
含「出纯噪声图」「配置注入被回写」「PS Direct 看不到交互窗口」等）。
