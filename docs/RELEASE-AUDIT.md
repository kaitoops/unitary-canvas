# 发布前合规审计报告（2026-11-07）

> 结论先行：**本仓库可以按 AGPL-3.0 发布**。未发现任何厂商二进制、
> 厂商代码拷贝或厂商资产的再分发；残余的厂商内部命名均为
> 「事实性标识符」（不受版权保护的 short phrases），且是工具运转所必需。

---

## 1. 核验问题：本仓库是否完全不受麻衣画布原版协议限制？

判定框架：原版应用的 EULA 只约束「原版二进制及其衍生品」。
本仓库要过三道关：①不含原版二进制 ②不含原版受版权保护的表达（代码/美术/文本拷贝）
③不诱导用户违反 EULA（我们只指导用户处理**自备副本**，改写发生在本机、不二次分发）。

### 1.1 全仓文件清单核验

| 类别 | 结果 |
|---|---|
| 二进制文件 | **0 个**（仅 LICENSE 一份非 py/md/json 文本；无 exe/dll/png/ico） |
| 厂商代码拷贝 | **0 处**（所有 .py 均为本轮会话原创；改写资产 bundle_yz.js 等**不在仓库内**，由用户本机脚本生成） |
| 厂商美术/文案拷贝 | **0 处** |
| 品牌 token 残留 | 28 处，**全部为事实性标识符**（见 1.2 分类） |

### 1.2 品牌 token 残留分类（28 处）

| 位置 | 数量 | 性质 | 处置 |
|---|---|---|---|
| `tools/build_patched.py` 替换规则 | 18 | **映射事实**：`旧名→新名` 替换对是工具的功能输入，非受保护表达；单独的词/短语不构成版权客体 | 保留（工具必需） |
| `specimens/registry.json` + `docs/COMPATIBILITY.md` | 6 | **标本指纹**：版本号、进程名（maicanvas_v351_cdp）、invoke 命令名（run_qiaodoumay_cli）——逆向产物中的事实性描述 | 保留（登记表功能必需） |
| `docs/TROUBLESHOOTING.md` / `AGENT-*.md` | 4 | 同上，坑位描述中的事实性进程名/缓存目录名 | 保留 |
| `tools/gateway.py` docstring | 1 | 旧注释提法 | **已改为中性表述** ✅ |

### 1.3 商标维度说明

品牌词残留属于**描述性使用**（nominative fair use：说明工具作用于哪个程序），
不是商标性使用（未用其名命名本项目、未暗示背书）。项目自身命名已全链
`yaozheng/unitary` 化（见 1.4）。商标风险等级：低；如原厂提出异议，
改注释措辞即可，无结构性风险。

## 2. 重构率论证

- **全链命名重构完成**（2026-11-07 R1-A/R1.3 两轮）：`qiaodoumayi/Qiaodoumayi/QIAODOUMAYI/qdmy/桥豆/麻衣 → yaozhengdugui/YaozhengDugui/YAOZHENGDUGUI/yz/幺正`
  - 运行态 bundle/CSS/HTML：旧形态 = 0，`yaozhengdugui` = 73 处
  - localStorage：109 键迁移至新前缀（旧键保留为回退副本，在用户 VM 内，不入库）
  - 原生窗口标题/图标：已改写（WM_SETICON + setTitle）
- **仓库代码零拷贝**：六件工具均为原创实现；`build_patched.py` 只含替换规则表
  （数据），不含任何厂商代码片段。
- **R2 保留项**（存在于用户 VM 运行态、不在本仓库）：invoke 命令名 16 处、
  Codex 桥接串、exe 明文区、guest 目录名——这些是 JS↔Rust 契约，改名=断链，
  属**用户本地运行态**的兼容性保留，不影响本仓库的独立版权地位。

## 3. 敏感信息清零记录（本次审计同步完成）

| 泄漏点 | 内容 | 处置 |
|---|---|---|
| `tools/gen_batch_v3.py:118` | **VM 管理员密码明文** | ✅ 已改为环境变量 `YZ_VM_PASS`（高危） |
| `tools/gen_batch_v3.py` | VM 名 / 内部路径 `C:\HyperV\...` | ✅ 参数化为 `YZ_VM_NAME` / `YZ_WAIT_PS1` |
| `tools/rename_shim.py` | VM 名硬编码 | ✅ 参数化为 `YZ_VM_NAME` |
| `tools/cdp_eval.py` / `cdp_ui.py` / `gen_batch_v3.py` | VM DHCP IP 硬编码 | ✅ 改 `127.0.0.1` 占位 + 自动发现 |
| `tools/gateway.py` | 宿主内网 IP | ✅ 改 `127.0.0.1` 占位 + 注释说明 |
| 全仓 | 用户名/主机名/盘符 | ✅ 扫描清零 |

注：`rename_shim.py` 注释中的 "172.26/27/28.x observed" 为 DHCP 漂移现象描述，
不含当前可用地址，保留。

## 4. 发布清单（剩余动作）

- [x] LICENSE = AGPL-3.0 官方全文（gnu.org 原样下载）
- [x] PolyForm 旧许可文件已删除
- [x] README：描述文案 A 落定 + AGPL 边界说明 + FAQ
- [x] 敏感信息清零 + 六件工具语法校验通过（py_compile / ast）
- [ ] 首次 push 前：`git init` + 确认 `.gitignore` 排除 `*.log`、`shim.log`、`__pycache__`
- [ ] GitHub About 栏粘贴 REPO-BRIEF.md 第二节文案 A
