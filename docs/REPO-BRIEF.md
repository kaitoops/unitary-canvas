# 仓库说明与 License 决策稿（供修改选用）

> 状态：**已定稿（2026-11-07）**：AGPL-3.0 + 描述文案 A。本文件留作决策记录，发布时可删或移入 docs/internal/。

---

## 一、License 决策：GPL-3.0 vs AGPL-3.0

前提变更：项目定位从「严格禁商用」调整为「允许商用、但要求衍生/改造同样开源」（copyleft）。
两个候选都是 OSI 认可的真开源协议，**都允许商用**，核心差异只有一条：

> **AGPL-3.0 = GPL-3.0 + 第 13 条「网络交互即分发」**。
> 谁把本项目的修改版放到服务器上通过网络提供服务（哪怕一行代码都不下载分发），
> 就必须向网络使用者提供其修改版的完整源码。GPL-3.0 则只在「分发二进制」时触发。

### 逐组件匹配分析

| 本仓库组件 | 形态 | GPL-3.0 下的漏洞 | AGPL-3.0 下的结果 |
|---|---|---|---|
| `tools/gateway.py` 协议网关 | **常驻网络服务**（HTTP 0.0.0.0:8190） | 有人拿去改改、包装成云端生图 SaaS 收费，不分发二进制 → **零开源义务** | 必须向其服务用户提供修改版源码 |
| `tools/rename_shim.py` 拦截 shim | 本机常驻代理 | 同上（本地代理也可被 SaaS 化） | 同上，闭环 |
| `tools/cdp_eval.py / cdp_ui.py / gen_batch_v3.py` | 本地脚本 | 被改造进商业 Agent 产品且不分发 → 无义务 | 网络可交互场景下有义务 |
| `docs/`、`specimens/` | 文档/数据 | — | — |

**结论建议：AGPL-3.0**。理由：本项目的核心原创物（协议网关）天然是网络服务形态，
AGPL 正是为堵「SaaS 白嫖不开源」设计的；选 GPL-3.0 等于对网关最常见的滥用形态（云端化）零防御。

### 两条必须写进 README 的边界说明（防误伤）

1. **对闭源 exe 的边界**：本仓库代码通过 CDP/配置与用户自备的画布 exe 交互，
   属于**进程间通信（aggregation）**，不构成衍生作品——GPL/AGPL 的 copyleft **不会传染**到
   画布本体 exe，也不要求用户的画布配置、生成内容开源。
2. **对补丁产物的边界**：`build_patched.py` 生成的改写资产（bundle_yz.js 等）是
   **在用户本机、从用户自备副本就地生成**的，本仓库不分发任何改写后的厂商二进制。

### 选 GPL-3.0 的合理场景（如你更在意这些）

- 希望下游（含商业公司）能把工具链**嵌入他们自己的 Agent 框架**而不被传染顾虑劝退，扩大采用面；
- 不在乎网关被云端化——因为本项目卖点在「经验文档 + 标本知识」而非网关本身。

### 裁定栏（请修改）

- [x] **AGPL-3.0** ✅ 已执行：LICENSE 即官方全文

- 选定后同步修改：README 徽标行、DISCLAIMER.md 第 2 节、删除旧 `LICENSE.md`（PolyForm 废弃）。
  双文本已从 gnu.org 官方源原样下载（GPL 35,149 B / AGPL 34,523 B），无需再校对。

---

## 二、仓库一句话描述（GitHub About 字段，≤350 字符，任选或改写）

**A（工具链定位，推荐）**
> Open toolchain for localizing, automating and remotely driving a Tauri-based AI canvas app: protocol gateway (OpenAI-image ⇄ ComfyUI /prompt), CDP asset-injection shim, localStorage migration, and a battle-tested agent playbook. AGPL-3.0.

**B（端到端管线定位）**
> Unitary Canvas toolkit — run your local ComfyUI behind an OpenAI-compatible gateway, batch-generate images through a real canvas UI via CDP, with full troubleshooting knowledge base (20+ pitfalls) for agent-driven setup.

**C（重构研究定位）**
> Reverse-engineering-to-rebuild toolkit for a Tauri canvas app: binary specimen registry, runtime asset patching via CDP Fetch interception, native window (title/icon) rebranding, and VM deployment runbooks.

**中文备用（放 README 首屏或 Release 说明）**
> 幺正画布（Unitary Canvas）工具链：本地 ComfyUI 的 OpenAI 协议网关、CDP 运行时资产注入、批量生图自动化与避坑手册。AGPL-3.0 开源，画布本体由用户自备。

---

## 三、README 首段（三选一或改写）

**V1 简洁型**
> **unitary-canvas** — Agent-friendly toolchain for a local AI canvas: OpenAI-protocol gateway over ComfyUI, CDP runtime patching, batch image generation, and a distilled "don't step on this" playbook from real deployments.

**V2 主张型**
> Most AI-canvas automations break on five things: config rehydration, DOM-detection lies, ACL walls, stale IPs, and encoding traps. This repo documents all of them — with working code.

**V3 中英双语型**
> **幺正画布工具链 / unitary-canvas**: drive a local Tauri canvas app with agents — protocol gateway, CDP shim, batch pipelines, and a complete troubleshooting knowledge base. The canvas binary is NOT included; bring your own copy.

---

## 四、GitHub Topics 建议

`comfyui` `openai-api` `cdp` `chrome-devtools-protocol` `tauri` `agent-tools` `image-generation` `reverse-engineering` `local-llm` `automation`

---

## 五、易被提问的点（预置 FAQ，可进 README）

**Q: 为什么不直接放画布 exe？**
A: 版权与再分发风险。本仓库提供标本登记表（specimens/registry.json）与解析指引，用户自备副本，脚本做哈希校验后本地打补丁。

**Q: AGPL 会传染到我的画布/生成图吗？**
A: 不会。见上文边界说明 1、2。

**Q: 商用要付费吗？**
A: 不需要。AGPL-3.0 允许任何商用，唯一义务是公开你对本仓库代码的修改（含网络服务场景）。
