# unitary-canvas（幺正画布）

> Most AI-canvas automations break on five things: config rehydration, DOM-detection lies, ACL walls, stale IPs, and encoding traps. This repo documents all of them — with working code.

Open toolchain for localizing, automating and remotely driving a Tauri-based AI canvas app: protocol gateway (OpenAI-image ⇄ ComfyUI /prompt), CDP asset-injection shim, localStorage migration, and a battle-tested agent playbook.

**仓库名取义**：幺正 = unitary（量子幺正算符），品牌 Logo 概念即
「幺正指针矩阵」——圆形指针单元阵列，所有指针角度自画外同一中心辐射。

| | |
|---|---|
| License | [AGPL-3.0](LICENSE)（允许商用；修改与网络服务化须同样开源，见下方边界说明） |
| 本仓库覆盖范围 | 仅原创工具链与文档；**画布本体 exe 不在本仓库**，见 [DISCLAIMER](DISCLAIMER.md) |
| 目标用户 | 想让 AI Agent 全自动部署/驱动本地 AI 画布的人 |

## 这是什么

一套让 **AI Agent（而非人类）** 完成画布部署与操控的完整工具链：

```
画布(UI) ──OpenAI图像协议──> protocol-gateway(:8190) ──/prompt工作流──> ComfyUI(:8189)
   ▲                                                             
   └──────────── CDP :9223 ←── shim(运行态补丁) / cdp工具(自动化) ── 宿主Agent
```

- **protocol-gateway**：把画布的图像生成请求翻译成 ComfyUI 工作流（含异步任务晋升）
- **rename-shim**：CDP Fetch 拦截式运行态资产补丁（零文件改动、秒级回退）
- **cdp 工具**：Agent 操控画布的全套驱动（求值/截图/点击/批跑/落盘检测）

## 文档地图（Agent 按此顺序读）

| 文件 | 用途 |
|---|---|
| [`docs/AGENT-INSTALL.md`](docs/AGENT-INSTALL.md) | 从零到全链路跑通的安装序列（含每步验证点） |
| [`docs/AGENT-CDP-CONTROL.md`](docs/AGENT-CDP-CONTROL.md) | 外部 Agent 经 CDP 操控 VM 内画布的完整模式与坑位 |
| [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) | **20 条已知坑位总目**（症状→根因→正解→验证），出错先查这里 |
| [`docs/COMPATIBILITY.md`](docs/COMPATIBILITY.md) | 版本指纹、副本校验流程、兼容性部署原则 |
| [`docs/KNOWLEDGE-MAP.md`](docs/KNOWLEDGE-MAP.md) | 经验归集体系：知识分层、蒸馏流程、溯源规则 |
| [`specimens/registry.json`](specimens/registry.json) | 二进制参考标本登记（本体不入库，萃取知识入库） |

## 快速开始（给 Agent 的一句话任务书）

> 读 docs/AGENT-INSTALL.md，按步骤 1-6 执行，每步过验证点；
> 任何异常先查 docs/TROUBLESHOOTING.md 的症状索引；完成后跑第 3 节
> 冒烟清单并向用户回报逐项勾选结果。

## 设计原则

1. **VM 内安装画布，宿主只跑算力与工具**——爆炸半径隔离，快照可回滚
2. **运行态改写 > 文件改写**——CDP 拦截优先，禁改闭源二进制（已证伪路径见坑位表 P-20）
3. **只认末端产物**——自动化成败判定以落盘文件为准，不轻信 DOM/日志
4. **知识持续蒸馏**——每次排障产出回流 TROUBLESHOOTING，见 KNOWLEDGE-MAP

## AGPL-3.0 边界说明（重要）

本仓库代码以 **AGPL-3.0** 授权：允许任何商用（含商用你的部署服务），唯一义务是
公开你对本仓库代码的修改（含通过网络提供服务而不分发二进制的场景，AGPL §13）。
两条边界防止误伤：

1. **不传染画布本体**：本仓库工具经 CDP/配置与用户自备的画布应用**进程间通信**，
   属于 aggregation 而非衍生作品——画布应用、其配置、以及你生成的图像内容
   均不受本 License 约束。
2. **不分发改写产物**：补丁资产（改写后的前端 bundle 等）由 `build_patched.py`
   在**用户本机、从用户自备副本就地生成**，本仓库不含、也不分发任何厂商二进制
   或其改写版本。

## FAQ

**Q: 为什么不直接提供画布 exe？**
A: 版权与再分发风险（见 [DISCLAIMER](DISCLAIMER.md)）。本仓库提供标本登记表与解析指引；用户自备副本，脚本做哈希校验后本地打补丁。

**Q: 商用需要付费吗？**
A: 不需要。AGPL-3.0 允许任何商用，唯一义务是开源你对本仓库代码的修改。
