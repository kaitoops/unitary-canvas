# COMPATIBILITY：版本兼容清单与标本指纹

> Agent 部署前必读。补丁工具对版本敏感——先核对指纹再动手。

## 1. 已验证版本矩阵

| 组件 | 版本 | 指纹 | 状态 |
|---|---|---|---|
| 画布本体 | V3.5.1 (maicanvas_v351_cdp) | 资产表 `index-KvvDjpOW.js` / `index-bbxvj1En.css`（以 `specimens/registry.json` 登记的 sha256 为准） | ✅ 全链路验证 |
| ComfyUI | 宿主 :8189，Qwen-Image-2.1 turbo + qwen3vl_8b | `/system_stats` 可达 | ✅ |
| 协议网关 | :8190 | `/v1/models` | ✅ |
| Python | 3.11+，websocket-client | `import websocket` | ✅ |

## 2. 版本敏感点（升级画布必查）

1. **资产文件名哈希变化** → shim 的 ASSETS 表需更新（`fetch_assets.py` 重新提取）
2. **段表结构**（151 项定制封装）→ 若上游换打包器，离线路线仍证伪，维持运行态拦截
3. **invoke 契约名**（16 处）→ 保护清单自动跳过，升级后 diff 检查保护串是否位移
4. **localStorage schema**（ensureDefaultModels 条目结构）→ 变化则 config-inject 需适配
5. **ACL 能力清单** → setTitle 若被收紧，原生标题路线回退到 Win32（P-12 同族）

## 3. 副本获取与校验流程（Agent 执行序列）

```text
1. 用户自备画布副本（渠道合规自担，见 DISCLAIMER.md）
2. Get-FileHash <exe> -Algorithm SHA256
3. 与 specimens/registry.json 登记值比对：
   一致   → 继续
   不一致 → 停。差异版本需先走「版本敏感点」逐项评估，
            不允许对未知版本盲跑补丁
4. 提取运行态资产：画布运行中经 CDP 拉取
   http://tauri.localhost/assets/... （fetch_assets.py）
5. 生成补丁资产（build_patched.py）→ shim 部署
```

## 4. 兼容性部署原则

- **运行态优先**：所有改写走 CDP Fetch 拦截，不碰 VM 内文件、不碰 exe（离线改写已证伪，见 TROUBLESHOOTING P-20）
- **可回退**：任一补丁层（shim/注入脚本）停止即回原版；localStorage 迁移保留旧键
- **最小知识假设**：Agent 不需要理解 exe 内部结构即可完成部署——理解内部结构只在重构工作线需要，届时按 `specimens/registry.json` 的 extraction_checklist 走
