# TROUBLESHOOTING：已知坑位总目（Agent 机读优先）

> 归集自 EB 协议条款（G40-G45）、LL 台账（LL-47~50）、工作日志与实证记录。
> **每条格式固定：症状 → 根因 → 正解 → 验证**。Agent 部署遇错时，
> 先按症状关键词在本表检索，禁止在未查表的情况下自创方案。
> 条目 ID 稳定可引用（P-xx），新增坑追加到表尾并保留 ID 单调递增。

## A. 连接与链路

### P-01 CDP 连接静默失效（最高频）
- **症状**：拦截/改写/自动化全部失效，页面回原版，**无任何报错**
- **根因**：VM DHCP 每次重启/恢复换址，硬编码 CDP_HOST 过期
- **正解**：启动时 `(Get-VM "CanvasVM").NetworkAdapters[0].IPAddresses[0]` 动态解析，常量仅 fallback
- **验证**：`curl http://<IP>:9223/json/version` 返回 JSON

### P-02 PS Direct 看不到交互桌面窗口
- **症状**：`Invoke-Command -VMName` 里 `MainWindowHandle` 恒空、窗口操作无效
- **根因**：PS Direct 跑在非交互会话，与登录桌面隔离
- **正解**：窗口级操作走 VM 内计划任务在交互会话执行（schtasks，任务带 /IT）
- **验证**：任务日志出现目标 hwnd

## B. 配置注入（画布 API 接入）

### P-03 新增自定义模型条目静默消失
- **症状**：注入的模型配置刷新后不见
- **根因**：`ensureDefaultModels` 启动用内置列表重建，未知名 id 被丢弃
- **正解**：劫持**内置条目**的 url 字段指向网关（不改 id 集合）
- **验证**：刷新后节点模型名仍在，出图走网关日志

### P-04 配置注入被磁盘缓存打回
- **症状**：localStorage 改了又「自己变回去」
- **根因**：Tauri 磁盘缓存 `Documents/API settings storage/api-settings-cache.json` 反向水合；且 revision 不匹配会触发重置
- **正解**：①修磁盘缓存本体（IP 等三处）②保持 `*_api_configs_revision` 原值不动 ③首次水合丢劫持属预期，**重施一次即持久**（哨兵机制）
- **验证**：重启画布后配置仍在

### P-05 localStorage 直接写无效
- **症状**：eval 写入成功、读回却是旧值
- **根因**：应用对 window.localStorage 做了代理包装
- **正解**：iframe `contentWindow.localStorage` 原始 Storage 绕过
- **验证**：raw 写入 + 应用层读取双向通过

## C. 生成管线

### P-06 出图是纯噪声
- **症状**：工作流跑通但图全噪
- **根因**：手搭工作流编码器接线错（clip 应接 `qwen3vl_8b`，非 enhancer LLM）
- **正解**：**抄官方模板 subgraph 接线**，禁凭 object_info 手搭
- **验证**：首图非噪声

### P-07 节点报错：参数名不存在
- **症状**：KSamplerSelect 等报未知输入
- **根因**：参数名是 `sampler_name` 不是 `sampler`
- **正解**：以官方模板 actual key 为准

### P-08 同步生图 45 秒超时
- **症状**：网关同步响应超时
- **根因**：画布同步等待上限 45s
- **正解**：超时晋升任务制——返回 task id，画布转 `?async=true` 轮询 `/v1/images/tasks/{id}`

### P-09 完成检测误判（三重干扰）
- **症状**：把桌宠动画当新图 / 永远检测不到图
- **根因**：节点渲染走 `asset.localhost` 文件引用 + blob URL；桌宠是 spritesheet
- **正解**：**铁律——只认末端产物**：轮询 VM 磁盘 `Documents\QiaodouCache\images\` 新增 PNG
- **验证**：10/10 批跑零误判

### P-10 提示词填不进去
- **症状**：改了输入框但提交时为空
- **根因**：contenteditable 受控组件，直接改 DOM 不触发框架状态
- **正解**：`el.focus(); document.execCommand("insertText", false, text)`
- **附注**：生成面板会自动关闭，每轮需重新点开节点

## D. 原生窗口层（Tauri）

### P-11 改 document.title 后原生标题栏不变
- **症状**：网页标题变了，任务栏/标题栏没变
- **根因**：Tauri 原生标题来自内嵌 tauri.conf.json，document.title 不传播
- **正解**：`__TAURI__.window.getCurrentWindow().setTitle(...)`（注入脚本 500ms 重试至 IPC 就绪）

### P-12 setIcon 报 ACL not allowed
- **症状**：`plugin:window|set_icon` 被拒
- **根因**：exe 能力清单编译期固化，运行时改不了；`Image.fromBytes` 同因被裁（缺 image-png feature）
- **正解**：VM 交互会话 Win32 `WM_SETICON`（LoadImage **LR_SHARED**，句柄进程退出不失效）+ 启动脚本挂钩持久化

### P-13 进程名精确匹配落空
- **症状**：Get-Process 找不到目标进程
- **根因**：实际进程名带后缀（`maicanvas_v351_cdp`）
- **正解**：通配匹配 + 以监听端口（netstat 找 9223 属主）反查为准

## E. 工程纪律（批跑/写入）

### P-14 批跑串数据
- **根因**：共享工作区复用（查询/输出/临时文件混用）
- **正解**：按会话全链路隔离（含 $env:TEMP 请求体临时文件）；覆盖前比对 mtime+sha256；落盘用临时文件+原子替换

### P-15 乱码 + 假成功
- **根因**：PS5.1 把无 BOM UTF-8 按 GBK 解码，乱码仍以 [200] 发出；try-catch 对非 200 静默
- **正解**：跨工具文件统一 UTF-8+BOM（`utf-8-sig`）；成败只认结构化状态码，4xx 立停

### P-16 注入样式反复丢失
- **症状**：改好的样式过一会儿没了
- **根因**：React 重渲染重挂容器
- **正解**：1s 间隔幂等自愈重挂；**验收等 ≥20s 稳定期**——加载初期样式被吹属正常
- **附注**：实测 `justifyContent` 在 React 重挂窗口期会呈现「设上即消失」假象，稳定期后自愈接管

## F. 品牌替换线（资产补丁）

### P-17 标题替换不生效
- **根因**：HTML 实体编码（`&#26725;…`），明文规则匹配不到
- **正解**：实体串与明文串都进替换表

### P-18 混种词残留
- **症状**：替换后出现混合形态（短词先于长词替换所致）
- **正解**：替换规则**最长匹配优先排序**

### P-19 改了不该改的契约串
- **根因**：功能串与显示串同形（如 `version:"V.3.5.1"` 既是显示也是导出格式）
- **正解**：精确上下文规则（如 `children:"V.3.5.1"`）；维护**保护清单**：invoke 命令名、Codex 双拷贝串、localStorage 键 schema

### P-20 shim 改了资产却不生效
- **根因**：shim 启动时缓存资产字节；exe 内嵌资产是定制封装（151 项段表）非标准 brotli，**离线改 exe 路线证伪**
- **正解**：重建资产后**必须重启 shim**；改写一律走运行态拦截，不走 exe 文件

## G. 二进制补丁与改名线（R2）

### P-21 Codex 粘贴说明逐字校验失败
- **根因**：桥接指令串（instructionFormat）存在**双源**——JS bundle 一份 + exe 内 Rust 原生区一份；Rust 串带长度头，只能**等长 UTF-8 替换**
- **正解**：双源统一用同一**等长句**（本仓实践：16 汉字变 16 汉字）；JS 侧可任意改，exe 侧必须等长、len 头不动

### P-22 刷新后页面回到原版
- **根因**：画布启动的初始资产请求落在 shim 断线重连空窗（attach 之前），原版资源直达
- **正解**：确认 shim.log 出现 `attached` 后手动 `Page.reload`（ignoreCache）；验收前必查

### P-23 exe 停机改名三个坑
- **进程名精确匹配**：`v351` 与 `v351_cdp` 两代并存，`Get-Process v351` 匹配不到 `_cdp` 变体
- **Move-Item 覆盖已存在目标被拒**：先 `Remove-Item` 再 `Move-Item`
- **计划任务间接引用**：任务指向 cmd/脚本时改名无需动任务本身，直接引用 exe 的脚本才要改
- **正解**：改名前 grep 全宿主+VM 文本文件盘点引用链；改名与补丁同一停机窗口一次做完
