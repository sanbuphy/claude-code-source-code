# Claude Code v2.1.88 源码深度分析

> 基于 2026-03-31 泄露的 TypeScript 源码，从产品设计和技术原理两个维度逐模块分析。
> 源码来自 `sanbuphy/claude-code-source-code`，版本 v2.1.88。

---

## 目录

1. [架构总览](#架构总览)
2. [核心引擎](#核心引擎)
   - [query/ — LLM 查询引擎](#query--llm-查询引擎)
   - [tools/ — 工具系统](#tools--工具系统)
   - [coordinator/ — 多 Agent 编排](#coordinator--多-agent-编排)
   - [hooks/ — Hook 系统](#hooks--hook-系统)
   - [state/ — 状态管理](#state--状态管理)
   - [tasks/ — 任务系统](#tasks--任务系统)
3. [UI 与交互](#ui-与交互)
   - [ink/ — 自定义终端渲染引擎](#ink--自定义终端渲染引擎)
   - [components/ — React 终端 UI 组件](#components--react-终端-ui-组件)
   - [screens/ — 屏幕/页面](#screens--屏幕页面)
   - [commands/ — 斜杠命令系统](#commands--斜杠命令系统)
   - [keybindings/ — 快捷键系统](#keybindings--快捷键系统)
   - [vim/ — Vim 模式](#vim--vim-模式)
   - [outputStyles/ — 输出样式](#outputstyles--输出样式)
   - [voice/ — 语音模式](#voice--语音模式)
4. [服务与基础设施](#服务与基础设施)
   - [services/api — API 通信层](#servicesapi--api-通信层)
   - [services/mcp — MCP 协议客户端](#servicesmcp--mcp-协议客户端)
   - [services/oauth — OAuth 认证](#servicesoauth--oauth-认证)
   - [services/compact — 上下文压缩](#servicescompact--上下文压缩)
   - [services/lsp — 语言服务器协议](#serviceslsp--语言服务器协议)
   - [services/extractMemories — 自动记忆提取](#servicesextractmemories--自动记忆提取)
   - [services/teamMemorySync — 团队记忆同步](#servicesteammemorysync--团队记忆同步)
   - [services/SessionMemory — 会话记忆](#servicessessionmemory--会话记忆)
   - [services/AgentSummary — 子 Agent 进度摘要](#servicesagentsummary--子-agent-进度摘要)
   - [services/PromptSuggestion + speculation — 推测执行](#servicespromptsuggestion--speculation--推测执行)
   - [services/policyLimits — 企业策略限制](#servicespolicylimits--企业策略限制)
   - [services/compact 其他子系统](#servicescompact-其他子系统)
   - [services/autoDream — 后台记忆整合](#servicesautodream--后台记忆整合)
   - [services/MagicDocs — 自动文档维护](#servicesmagicdocs--自动文档维护)
   - [services/tips — 提示调度](#servicestips--提示调度)
   - [bridge/ — IDE 集成桥接](#bridge--ide-集成桥接)
   - [server/ — Direct Connect 服务端](#server--direct-connect-服务端)
   - [remote/ — 远程会话管理](#remote--远程会话管理)
   - [plugins/ — 插件系统](#plugins--插件系统)
   - [skills/ — 技能系统](#skills--技能系统)
   - [schemas/ — Schema 定义](#schemas--schema-定义)
   - [entrypoints/ — 入口点](#entrypoints--入口点)
5. [辅助模块](#辅助模块)
   - [bootstrap/ — 启动引导](#bootstrap--启动引导)
   - [cli/ — CLI 框架](#cli--cli-框架)
   - [constants/ — 常量与 Feature Flags](#constants--常量与-feature-flags)
   - [context/ — React 上下文](#context--react-上下文)
   - [types/ — 类型系统](#types--类型系统)
   - [utils/ — 工具函数](#utils--工具函数)
   - [migrations/ — 迁移系统](#migrations--迁移系统)
   - [memdir/ — 记忆目录](#memdir--记忆目录)
   - [native-ts/ — 原生 TS 实现](#native-ts--原生-ts-实现)
   - [upstreamproxy/ — 上游代理](#upstreamproxy--上游代理)
   - [buddy/ — 宠物伴侣系统](#buddy--宠物伴侣系统)
   - [assistant/ — 远程会话历史](#assistant--远程会话历史)
6. [系统提示词组装](#系统提示词组装)
7. [Feature Flags 完整列表](#feature-flags-完整列表)
8. [跨模块依赖图](#跨模块依赖图)
9. [核心设计理念总结](#核心设计理念总结)

---

## 架构总览

| 维度 | 数据 |
|------|------|
| 代码量 | ~1,900 文件，512K+ 行 TypeScript |
| 运行时 | Bun |
| 终端 UI | React + 深度定制 Ink |
| CLI 框架 | Commander.js |
| Schema | Zod v4 |
| 布局引擎 | 自研 Yoga-layout TS 移植 |
| Feature Flag | GrowthBook（89 个编译时开关） |
| 认证 | OAuth 2.0 + JWT + macOS Keychain |
| 遥测 | OpenTelemetry + gRPC + BigQuery |
| 协议 | MCP SDK、LSP |

**技术栈选择的核心逻辑**：Bun 提供快速启动和编译时特性门控（`feature()` → dead code elimination）；React + Ink 让终端 UI 达到 Web 级组件化；Zod 统一输入验证和 SDK 类型生成。

---

## 核心引擎

### query/ — LLM 查询引擎

**产品设计意图**：解决"一次用户输入到完整任务完成"的全生命周期管理。用户说一句话，后面可能经历 LLM 响应 → 工具调用 → 再响应 → 再调用，循环数十次。query 模块是这个循环的心脏。

**技术架构**：

核心是 `query.ts` 里的 `queryLoop()` —— 一个 `while(true)` 的 AsyncGenerator 循环，每次迭代代表一次"LLM 请求 + 工具执行"。

关键数据结构：
- **`State`** — 每次循环迭代的可变状态包（messages、toolUseContext、autoCompactTracking 等）
- **`QueryConfig`** (`config.ts`) — 入口快照一次的不可变配置（sessionId、feature gates）
- **`QueryDeps`** (`deps.ts`) — 依赖注入容器（callModel、microcompact、autocompact、uuid）
- **`BudgetTracker`** (`tokenBudget.ts`) — token 预算追踪器

**单次迭代的完整流程**：

```
1. applyToolResultBudget → 压缩历史工具输出
2. snipCompact → 裁剪超长历史
3. microcompact → 微压缩
4. contextCollapse → 上下文折叠
5. autocompact → 自动压缩（token 超阈值时）
6. callModel (streaming) → 调 Claude API
7. 收集 assistantMessages 和 toolUseBlocks
8. StreamingToolExecutor 并行执行工具
9. handleStopHooks → 执行停止钩子
10. 决定 continue/return
```

**Continue 状态机** —— 7+ 种 continue 原因：

| 原因 | 含义 |
|------|------|
| `reactive_compact_retry` | prompt 太长，压缩后重试 |
| `collapse_drain_retry` | context collapse 释放空间后重试 |
| `max_output_tokens_recovery` | 输出截断，注入续写 prompt |
| `max_output_tokens_escalate` | 从 8k 升级到 64k 重试 |
| `stop_hook_blocking` | stop hook 报错，注入错误让模型修正 |
| `token_budget_continuation` | 还有预算，nudge 让模型继续 |

**有趣的设计决策**：
- `feature('XXX')` 来自 `bun:bundle`，是编译时常量，用于 dead code elimination
- Memory prefetch 在迭代开始时 fire-and-forget，在工具执行后 consume —— 利用模型流式输出的时间窗口做预加载
- `QueryEngine` 类是 SDK/headless 路径的封装，拥有完整对话生命周期

---

### tools/ — 工具系统

**产品设计意图**：将"Claude 能做什么"具象化为结构化的工具定义。每个工具 = 一个独立能力单元。

**核心类型 `Tool`**（约 700 行，35+ 方法/属性）：

```typescript
type Tool<Input, Output, Progress> = {
  name: string
  inputSchema: ZodType          // 输入验证
  call()                        // 执行逻辑
  checkPermissions()            // 权限检查
  description()                 // 给模型看的描述
  prompt()                      // 工具的 system prompt 部分
  isConcurrencySafe()           // 能否并行执行
  isReadOnly()                  // 是否只读
  isDestructive()               // 是否不可逆
  shouldDefer?                  // 是否延迟加载 schema
  renderToolUseMessage()        // UI：工具调用
  renderToolResultMessage()     // UI：工具结果
  // ... 更多
}
```

**60+ 工具分类**：

| 类别 | 工具 |
|------|------|
| 文件操作 | Read、Edit、Write、Glob、Grep、NotebookEdit |
| 执行 | Bash、REPL（ant-only） |
| 网络 | WebFetch、WebSearch |
| Agent | AgentTool、SendMessage、TaskCreate/Update/Get/List/Stop |
| 团队 | TeamCreate/Delete |
| MCP | MCPTool（动态代理 MCP server 工具） |
| 元工具 | ToolSearch（延迟加载 schema）、EnterPlanMode、ExitPlanMode、Skill |

**工具执行编排**（`toolOrchestration.ts`）：
- `partitionToolCalls()` 将调用分批：连续的 `isConcurrencySafe=true` 工具并行，其他串行
- 默认并发上限 10

**StreamingToolExecutor**：在模型流式输出时就开始执行工具（不等流完），通过 TrackedTool 队列管理。

**ToolSearch 延迟加载**：标记 `shouldDefer: true` 的工具初始 prompt 只发名称不发 schema，模型通过 ToolSearch 搜索获取完整 schema 后才能调用，节省 prompt token。

---

### coordinator/ — 多 Agent 编排

**产品设计意图**：让 Claude Code 从"一个 agent"升级为"一个协调者 + N 个 worker 并行"。

**核心设计**：只有 `coordinatorMode.ts` 一个文件（~370 行），**协调逻辑完全通过 system prompt 注入，不是硬编码的编排引擎**。

```
协调者模式 = 特殊 system prompt + 工具限制 + worker 上下文注入
```

`getCoordinatorSystemPrompt()` 返回 ~300 行详细 prompt，教模型如何做协调者：
- 任务工作流：Research → Synthesis → Implementation → Verification
- Worker prompt 写作规范（自包含、写清 "done" 标准）
- 并发管理（只读任务并行，写任务按文件区域串行）
- Continue vs Spawn 决策矩阵

**设计哲学**：没有状态机、没有 DAG、没有 workflow engine —— 全靠 prompt engineering 驱动编排。Worker 结果通过 XML `<task-notification>` 注入为 user message。

---

### hooks/ — Hook 系统

**产品设计意图**：让用户和插件能在生命周期关键点注入自定义逻辑。

**两层架构**：

**A. 生命周期 Hook**（20+ 种事件）：

| 事件 | 时机 |
|------|------|
| PreToolUse / PostToolUse | 工具执行前/后 |
| Stop / SubagentStop | 模型停止响应 |
| SessionStart / SessionEnd | 会话开始/结束 |
| PreCompact / PostCompact | 压缩前/后 |
| PermissionDenied / PermissionRequest | 权限被拒/请求 |
| UserPromptSubmit | 用户提交输入 |
| FileChanged / CwdChanged | 文件/目录变更 |
| TaskCreated / TaskCompleted | 任务创建/完成 |

Hook 是用户定义的 shell 命令，通过 spawn 执行，stdin 传入 JSON，stdout 返回 JSON。支持 matcher 模式匹配（如 `Bash(git *)`）和异步模式。

**B. 权限决策系统**（`useCanUseTool`）：

决策链：规则匹配 → handler 分派（interactive/coordinator/swarmWorker）→ ML 分类器（auto-mode）→ PreToolUse hook

**有趣细节**：
- Bash 工具在权限请求前预先启动分类器检查（speculative），利用等待时间并行化
- 多个决策来源（hook、分类器、UI）race，谁先到用谁

---

### state/ — 状态管理

**产品设计意图**：在高度异步的系统中维护一致的全局状态。

**Store** — 35 行的极简状态容器（`Object.is` 判等 + `Set<Listener>` 通知），没有 middleware、没有 devtools。

**AppState** — ~450 行的巨型状态类型，用 `DeepImmutable<>` 包裹，涵盖：权限规则、后台任务、MCP 连接、插件状态、推测执行、团队上下文、消息收件箱、Computer Use 状态、UI 状态等。

**设计决策**：
- 巨型单 store 而非拆分 —— 简化跨切面读取
- 子 agent 的 `setAppState` 可设为 no-op（防污染），但 `setAppStateForTasks` 始终连接根 store
- function updater 模式强制不可变更新

---

### tasks/ — 任务系统

**产品设计意图**：让后台工作可见、可管理。

**7 种任务类型**：

| 类型 | 用途 |
|------|------|
| `LocalShellTask` | 后台 shell 命令 |
| `LocalAgentTask` | 子 agent |
| `RemoteAgentTask` | 远程 agent（CCR） |
| `InProcessTeammateTask` | 进程内 teammate |
| `LocalWorkflowTask` | 工作流任务 |
| `MonitorMcpTask` | MCP 监控 |
| `DreamTask` | 记忆整理（auto-dream） |

**LocalMainSessionTask**：用户 Ctrl+B 后台化当前查询时创建，有独立 transcript 文件，实时更新 progress，完成后通过 `<task-notification>` 通知。

---

## UI 与交互

### ink/ — 自定义终端渲染引擎

**产品设计意图**：在终端实现类浏览器的渲染引擎，支持全屏、文本选择、鼠标交互、硬件滚动。

**这不是对 Ink 库的简单使用，而是深度 fork/重写的终端渲染引擎。**

**渲染管线**：

```
React 组件树 → reconciler.ts (React Reconciler) → dom.ts (自定义 DOM)
  → Yoga 布局引擎 (layout/) → renderer.ts → render-node-to-output.ts
    → screen.ts (字符级缓冲区) → log-update.ts (diff 算法)
      → optimizer.ts (patch 合并) → terminal.ts (ANSI 写入)
```

**关键技术**：
- **双缓冲帧系统** — frontFrame/backFrame，16ms/帧（60fps 目标）
- **字符级 Screen 缓冲区** — 每 cell 存储字符、样式、宽度、超链接。`CharPool`/`StylePool`/`HyperlinkPool` 做字符串 interning，节省内存并加速 diff（整数比较替代字符串比较）
- **自定义 DOM** — 7 种节点类型，每个带 Yoga 布局节点、scroll 状态、事件处理器
- **DECSTBM 硬件滚动** — ScrollBox 只滚动时用终端硬件指令替代重绘，一条指令替代 O(rows×cols) 重写
- **Alt Screen 模式** — 进入备用屏幕缓冲区，退出时恢复主屏幕（ctrl+o 看 transcript 时主对话不丢失的原因）
- **文本选择系统** — 鼠标拖拽选择，支持 word/line 模式（双击/三击），处理滚动时选区超出视口的边界
- **光标声明系统** — 组件可声明光标位置，用于 CJK IME 预编辑文本显示
- **帧性能追踪** — 每帧记录各阶段耗时和 yoga 缓存命中次数

---

### components/ — React 终端 UI 组件

**核心组件**：
- **FullscreenLayout** — 三区布局：可滚动区(消息) + 底部固定区(prompt) + 模态层
- **VirtualMessageList** — 虚拟滚动，只渲染可见区域
- **PromptInput/** — 20+ 文件：输入框、footer、模式指示器、自动补全、语音指示器
- **StructuredDiff** — 文件编辑 diff 可视化
- **design-system/** — Dialog、Pane、Tabs、ProgressBar 等基础 UI 原语

所有组件经过 **React Compiler** 编译，自动细粒度 memoization。

---

### screens/ — 屏幕/页面

三个独立应用模式：

1. **REPL.tsx** — 主交互界面（~700+ 行导入），管理对话流、权限、命令队列、成本追踪、语音集成、团队协作
2. **Doctor.tsx** — 诊断屏幕，检查环境、keybinding、MCP、沙盒、版本（类似 `flutter doctor`）
3. **ResumeConversation.tsx** — 会话恢复，支持跨项目恢复、worktree 状态恢复

---

### commands/ — 斜杠命令系统

**四种命令来源**：bundled skills → builtin plugin skills → skill dir → workflows → plugin → COMMANDS()

**命令类型**：`prompt`（注入对话）、`local`（本地执行）、`local-jsx`（渲染 React UI）

**完整命令分类（~80+ 命令）**：

| 类别 | 命令 |
|------|------|
| 会话管理 | /clear, /compact, /resume, /session, /rename, /export, /copy, /rewind, /tag |
| 开发工具 | /commit, /diff, /review, /ultrareview, /security-review, /bughunter, /plan, /autofix-pr, /pr_comments, /issue |
| 配置 | /config, /model, /theme, /color, /output-style, /vim, /keybindings, /permissions, /hooks, /sandbox-toggle, /effort, /fast |
| MCP/插件 | /mcp, /plugin, /reload-plugins, /skills |
| 认证 | /login, /logout, /oauth-refresh, /install-github-app, /install-slack-app |
| 诊断 | /doctor, /help, /cost, /usage, /stats, /status, /context, /files |
| 实验性 | /bridge, /voice, /buddy, /workflows, /proactive, /ultraplan |
| 内部 | /good-claude, /btw, /stickers, /ant-trace, /debug-tool-call |

**有趣细节**：
- `/insights` 命令用 lazy shim（113KB 3200 行，实际调用才 import）
- `getDynamicSkills()` 在文件操作过程中发现新 skill（匹配 `paths` glob 后才可见）

---

### keybindings/ — 快捷键系统

完整可自定义快捷键系统，支持：
- **17 个上下文**（Global/Chat/Autocomplete/Settings/Confirmation 等）
- **Chord 序列**（如 `ctrl+x ctrl+k`，1 秒超时）
- **热重载**（`~/.claude/keybindings.json` 文件监听）
- **平台自适应**（Windows 无 VT mode 时降级绑定）
- **保留键**（`ctrl+c`/`ctrl+d` 用时间双击检测，不可重绑）

---

### vim/ — Vim 模式

教科书级有限状态机实现：
- 4 个纯函数文件：`transitions.ts`（状态转移表）、`motions.ts`（光标移动）、`operators.ts`（delete/change/yank）、`textObjects.ts`（iw/aw/i"/a( 等）
- 支持：操作符+motion 组合、计数前缀、文本对象、f/F/t/T、dot repeat、寄存器、缩进、替换
- `MAX_VIM_COUNT = 10000` 防止 `99999dd`

---

### outputStyles/ — 输出样式

极简实现（98 行）：扫描 `.claude/output-styles/*.md`，解析 frontmatter，文件内容作为 system prompt 注入。`keep-coding-instructions` 标志控制是否保留默认编码规范。

---

### voice/ — 语音模式

**Hold-to-talk 语音输入**，需 `VOICE_MODE` feature flag。

**架构**：
- WebSocket 连接 Anthropic `voice_stream` 端点（Deepgram 后端）
- 二进制音频帧 + JSON 控制消息
- Hold 检测：bare-char 绑定需 5 次连续快速按键才激活（避免误触），修饰键组合首次即可
- 三级超时 finalize：正常 → 1.5s 无数据 → 5s 兜底
- 支持 20+ 种语言，可从系统 locale 自动检测
- Feature flag 做编译时 DCE：外部构建不含语音代码

---

## 服务与基础设施

### services/api — API 通信层

封装与 Anthropic API 的所有交互。`queryModelWithStreaming` 是核心函数。`withRetry` 提供指数退避重试。`errors.ts` 解析 `prompt_too_long` 错误中的 token gap 数值，用于 compact 的精确裁剪。

---

### services/mcp — MCP 协议客户端

完整 MCP 客户端，支持 4 种传输层：Stdio、SSE、StreamableHTTP、WebSocket。

**关键组件**：
- `client.ts` — 核心，100+ imports
- `MCPConnectionManager.tsx` — React Context，管理所有连接生命周期
- `xaa.ts` — Cross-App Access，实现 RFC 8693 Token Exchange + RFC 7523 JWT Bearer Grant
- 二进制 blob 自动持久化到磁盘、图片自动缩放下采样

---

### services/oauth — OAuth 认证

处理 Claude.ai 和 Console 两套 OAuth 流程，支持 PKCE (S256)、本地回调监听。URL 参数 `code=true` 触发 Claude Max 升级提示——产品增长策略直接写在代码里。

---

### services/compact — 上下文压缩

Claude Code 能处理超长会话的核心能力。**五层压缩体系**：

| 层级 | 机制 | 说明 |
|------|------|------|
| 1. API Microcompact | 服务端 | `clear_tool_uses` 清除旧工具结果、`clear_thinking` 清除旧思考块 |
| 2. Client Microcompact | 时间维度 | 只清除可压缩工具（Read/Bash/Grep/Glob）的输出 |
| 3. Context Collapse | 上下文折叠 | 折叠冗余上下文 |
| 4. Auto Compact | 全量压缩 | fork 子 agent 生成摘要替换原始消息 |
| 5. Reactive Compact | PTL 重试 | 按 API round group 从头部丢弃 |

**自动触发**：阈值 = 有效窗口 - 13000 buffer tokens。连续失败 3 次后 circuit breaker（BQ 数据：曾有 session 连续失败 3272 次浪费 250K API 调用/天）。

**Post-compact 恢复**：最多恢复 5 个最近读过的文件（各限 5000 token），Skill 重注入有独立预算（25000 token，每个限 5000）。

---

### services/lsp — 语言服务器协议

连接外部 LSP 服务器（TypeScript、Python 等），获取代码诊断信息。`passiveFeedback.ts` 将诊断转换为 attachment 被动注入上下文。

---

### services/extractMemories — 自动记忆提取

每次对话结束（无工具调用的最终响应）时，fork 主对话（共享 prompt cache），以子 agent 身份运行，自动提取记忆写入 `~/.claude/projects/<path>/memory/`。

工具限制：只能用 Read/Grep/Glob/只读Bash + Edit/Write（限 memory 目录）。

---

### services/teamMemorySync — 团队记忆同步

按 git repo 隔离的组织级记忆同步。Pull: server wins per-key。Push: 增量上传（content hash diff）。删除不传播。上传前 `secretScanner.ts` 扫描敏感信息。

---

### services/SessionMemory — 会话记忆

后台周期性运行的 markdown 文件，记录当前会话关键信息。forked subagent 模式，GrowthBook feature gate 控制。与 compact 协作：压缩时同步 last summarized message id。

---

### services/AgentSummary — 子 Agent 进度摘要

coordinator 模式下，每 30 秒 fork 子 agent 生成 3-5 词进度摘要（如 "Reading runAgent.ts"）。工具全部 deny 但不清空数组（否则 bust prompt cache）。

---

### services/PromptSuggestion + speculation — 推测执行

用户还没输入时，预测下一步并提前在 overlay 文件系统上执行。最多 20 轮、100 条消息。写入工具在 overlay 目录执行，读工具访问真实文件系统。

---

### services/policyLimits — 企业策略限制

从 API 获取组织级策略限制。**Fail-open 设计**：API 挂了不阻塞用户。ETag 缓存 + 每小时后台轮询。

---

### services/autoDream — 后台记忆整合

类似"做梦"——累积足够会话后自动整合记忆。三级门控：① 时间门（≥24h）② 会话门（≥5 个 session）③ 锁（无其他进程在整合）。

---

### services/MagicDocs — 自动文档维护

检测到 `# MAGIC DOC: [title]` 标记的 markdown 后，后台自动用对话内容更新。

---

### services/tips — 提示调度

spinner 等待时显示使用提示。LRU 策略（选最久没显示的），支持 context-aware 过滤。

---

### bridge/ — IDE 集成桥接（Remote Control）

让用户通过 `claude remote-control` 从 Claude.ai Web UI 远程操作本地 CLI。

**两代架构并存**：
1. **Env-based (v1)** — 通过 Environments API poll/dispatch
2. **Env-less (v2)** — 直连 session-ingress 层（无环境 API 开销）

默认 32 个 session 的 spawn 池。SIGTERM→SIGKILL 30 秒宽限期。JWT 自动刷新 + Trusted Device Token。

---

### server/ — Direct Connect 服务端

允许外部客户端通过 WebSocket 直连 Claude Code 实例（不经 CCR 基础设施）。

---

### remote/ — 远程会话管理

CCR 远程会话的客户端。WebSocket 订阅 + HTTP POST 发送。5 次重连，4001 (session not found) 有限重试（compaction 期间可能暂时找不到），4003 (unauthorized) 立即放弃。

---

### plugins/ — 插件系统

内置插件定义层。ID 格式 `{name}@builtin`，可提供 skills + hooks + MCP servers。`bundled/index.ts` 当前为空（为将来迁移的脚手架）。

---

### skills/ — 技能系统

**三种来源**：

| 来源 | 说明 |
|------|------|
| Bundled Skills | 编译到二进制，所有用户可用 |
| Disk Skills | `~/.claude/skills/` + `.claude/skills/` + plugin 目录 |
| MCP Skills | MCP 服务器提供 |

Bundled skills 支持 `files` 属性（首次调用时解压到磁盘），memoize Promise 确保并发安全。

---

### schemas/ — Schema 定义

提取 hook 相关 Zod schema 到独立文件，打破循环依赖。四种 hook 类型：Command、Prompt、HTTP、Agent。25 种事件类型。

---

### entrypoints/ — 入口点

**cli.tsx** — bootstrap 入口，按顺序检查快速路径：
1. `--version` → 零 import 直接打印
2. `--dump-system-prompt` → 输出渲染后的 system prompt（ant-only）
3. `remote-control` → bridge 模式
4. `daemon` → daemon 主进程
5. `ps`/`logs`/`attach`/`kill` → 后台 session 管理

**`ABLATION_BASELINE`**：内部实验用，一键关闭所有增强功能用于 A/B 对比。

**mcp.ts** — Claude Code 自身作为 MCP 服务器运行（服务名 `claude/tengu`），暴露内置工具给外部客户端。

---

## 辅助模块

### bootstrap/ — 启动引导

**Import DAG 叶节点** —— 不允许导入其他业务模块（ESLint 规则 `bootstrap-isolation` 强制），所有模块反向依赖它。

~80 个字段的 `State` 单例，包含会话标识、成本计量、模型控制、遥测实例。

**Prompt cache 优化**：`afkModeHeaderLatched`、`fastModeHeaderLatched` 等全部采用 **sticky-on latch** 模式——一旦触发就保持，避免 beta header 翻转导致 prompt cache 失效。

---

### cli/ — CLI 框架

| 组件 | 职责 |
|------|------|
| `print.ts` | `--print` 非交互式单次查询 |
| `structuredIO.ts` | SDK/JSON 模式 I/O 桥接 |
| `handlers/` | 子命令处理器 |
| `transports/` | HybridTransport、SSE、WebSocket、CCR Client |

---

### constants/ — 常量与 Feature Flags

**Beta Headers**（16 个）：

| 常量 | 用途 |
|------|------|
| `INTERLEAVED_THINKING_BETA_HEADER` | 交错思考 |
| `CONTEXT_1M_BETA_HEADER` | 1M 上下文 |
| `CONTEXT_MANAGEMENT_BETA_HEADER` | 上下文管理 |
| `WEB_SEARCH_BETA_HEADER` | 网页搜索 |
| `FAST_MODE_BETA_HEADER` | 快速模式 |
| `TOKEN_EFFICIENT_TOOLS_BETA_HEADER` | 工具 token 压缩 |
| `ADVISOR_BETA_HEADER` | Advisor 工具 |
| ... | ... |

完整 Feature Flags 见[下文](#feature-flags-完整列表)。

**系统提示词组装**（`prompts.ts`）见[下文](#系统提示词组装)。

---

### context/ — React 上下文

React Context Provider 集合：消息邮箱（Agent 间通信）、语音状态、帧率追踪、模态框、通知系统等。

---

### types/ — 类型系统

**Permission Modes**：`acceptEdits` | `bypassPermissions` | `default` | `dontAsk` | `plan` | `auto` | `bubble`

**Permission 决策三态**：`allow`（可携带 `updatedInput`）、`ask`（可携带 `pendingClassifierCheck`）、`deny`（必须含 `decisionReason`）

**Yolo Classifier** 结果含两阶段：`stage1` (fast XML) 和 `stage2` (thinking)，各有独立 usage/duration。

---

### utils/ — 工具函数

最大模块（400+ 文件），按子目录组织：

| 子目录 | 职责 |
|--------|------|
| `bash/` | Shell 命令解析（tree-sitter AST、heredoc） |
| `model/` | 模型配置、别名、Bedrock/Vertex 适配 |
| `permissions/` | 权限实现（YOLO 分类器、路径校验） |
| `settings/` | 分层设置（user/project/local/flag/policy/MDM） |
| `hooks/` | Hook 执行引擎 |
| `plugins/` | 插件系统（marketplace、版本、block list） |
| `swarm/` | Agent Swarm（tmux/iTerm/in-process 后端） |
| `computerUse/` | Computer Use |
| `secureStorage/` | macOS Keychain / fallback |
| `telemetry/` | OTel、BigQuery、Perfetto |

---

### migrations/ — 迁移系统

9 个幂等迁移函数，主要是模型名称迁移链：

```
Fennec → Opus → Opus[1m]
Sonnet[1m] → Sonnet 4.5 → Sonnet 4.6
```

---

### memdir/ — 记忆目录

**四类记忆**：`user`（用户画像）、`feedback`（行为反馈）、`project`（项目状态）、`reference`（外部资源指针）

**路径**：`~/.claude/projects/{sanitized-git-root}/memory/`

**关键机制**：`findRelevantMemories()` 用 Sonnet 侧查询从 frontmatter 描述中选择最多 5 个相关记忆——不暴力加载全部，平衡上下文消耗和相关性。

安全性：`autoMemoryDirectory` 不接受 `projectSettings` 来源（防恶意仓库指定 `~/.ssh`）。

---

### native-ts/ — 原生 TS 实现

三个原本依赖 Rust/C++ NAPI 模块的纯 TS 重写：

| 模块 | 替代 | 说明 |
|------|------|------|
| yoga-layout | Yoga (C++) | Flexbox 引擎 TS 移植，覆盖 Ink 使用的子集 |
| color-diff | syntect (Rust) | highlight.js 替代，延迟加载（190+ 语言 ~50MB） |
| file-index | nucleo (Rust) | fzf-v2 风格评分（边界加分、驼峰加分、连续加分），4ms 时间片异步索引构建 |

---

### upstreamproxy/ — 上游代理

**专为 CCR 容器设计**。启动流程：读 session token → `prctl` 禁止 ptrace → 下载 CA 证书 → 启动 CONNECT→WebSocket relay → 删除 token 文件。

Relay 实现：本地 TCP → HTTP CONNECT → protobuf → WebSocket tunnel（因 GKE L7 不支持原生 CONNECT）。

**Fail-open**：任何步骤出错降级为禁用代理。

---

### buddy/ — 宠物伴侣系统

彩蛋功能，需 `feature('BUDDY')` 启用。18 种物种、6 种眼睛、帽子、5 种稀有度。Mulberry32 伪随机生成。物种名用 `String.fromCharCode` 编码——因为有物种名与模型代号碰撞，构建流程会 grep 检查代号泄露。

---

### assistant/ — 远程会话历史

远程会话历史拉取（CCR 场景），通过 OAuth 认证访问 `/v1/sessions/{id}/events`，分页获取。

---

## 系统提示词组装

`getSystemPrompt()` 是核心入口，分静态/动态两段：

**静态部分**（跨组织可缓存，`scope: 'global'`）：

| 顺序 | Section | 内容 |
|------|---------|------|
| 1 | Intro | 身份声明 + 安全指令 |
| 2 | System | 系统行为（Markdown、权限模式、hook） |
| 3 | DoingTasks | 编码规范（最小复杂度、安全） |
| 4 | Actions | 可逆/不可逆操作风险控制 |
| 5 | UsingYourTools | 工具使用指南（优先专用工具、并行） |
| 6 | ToneAndStyle | 风格约束 |
| 7 | OutputEfficiency | 输出效率 |

**`SYSTEM_PROMPT_DYNAMIC_BOUNDARY`** — 静态/动态分隔标记

**动态部分**（session-specific，registry 管理）：

| Section | 内容 |
|---------|------|
| session_guidance | Ask 工具、Agent 工具、Skill、验证代理 |
| memory | MEMORY.md 内容 |
| env_info | OS、shell、git、日期 |
| language | 语言偏好 |
| output_style | 自定义样式 |
| mcp_instructions | MCP 服务器指令（**uncached**，因可热连接） |
| token_budget | Token 预算提示 |
| brief | Brief 模式（Kairos） |

---

## Feature Flags 完整列表

共 **89 个**编译时开关，按领域分类：

### 核心功能
`BASH_CLASSIFIER`, `TRANSCRIPT_CLASSIFIER`, `TREE_SITTER_BASH`, `TOKEN_BUDGET`, `FORK_SUBAGENT`, `VERIFICATION_AGENT`, `BUILTIN_EXPLORE_PLAN_AGENTS`, `COORDINATOR_MODE`, `ULTRAPLAN`, `ULTRATHINK`

### 上下文管理
`CACHED_MICROCOMPACT`, `REACTIVE_COMPACT`, `CONTEXT_COLLAPSE`, `HISTORY_SNIP`, `COMPACTION_REMINDERS`

### 记忆系统
`EXTRACT_MEMORIES`, `TEAMMEM`, `MEMORY_SHAPE_TELEMETRY`, `AGENT_MEMORY_SNAPSHOT`

### 自治/主动模式
`PROACTIVE`, `KAIROS`, `KAIROS_BRIEF`, `KAIROS_CHANNELS`, `KAIROS_DREAM`, `KAIROS_GITHUB_WEBHOOKS`, `KAIROS_PUSH_NOTIFICATION`, `BG_SESSIONS`

### 远程/桥接
`BRIDGE_MODE`, `CCR_AUTO_CONNECT`, `CCR_MIRROR`, `CCR_REMOTE_SETUP`, `DIRECT_CONNECT`, `SSH_REMOTE`, `BYOC_ENVIRONMENT_RUNNER`, `SELF_HOSTED_RUNNER`

### UI/交互
`BUDDY`, `VOICE_MODE`, `AUTO_THEME`, `TERMINAL_PANEL`, `HISTORY_PICKER`, `MESSAGE_ACTIONS`, `QUICK_SEARCH`, `NATIVE_CLIPBOARD_IMAGE`, `STREAMLINED_OUTPUT`

### 技能/插件
`EXPERIMENTAL_SKILL_SEARCH`, `SKILL_IMPROVEMENT`, `WORKFLOW_SCRIPTS`, `MCP_SKILLS`, `MCP_RICH_OUTPUT`, `HOOK_PROMPTS`, `RUN_SKILL_GENERATOR`

### 安全/合规
`NATIVE_CLIENT_ATTESTATION`, `ANTI_DISTILLATION_CC`, `POWERSHELL_AUTO_MODE`

### 遥测/内部
`SLOW_OPERATION_LOGGING`, `ENHANCED_TELEMETRY_BETA`, `PERFETTO_TRACING`, `SHOT_STATS`, `DUMP_SYSTEM_PROMPT`, `ABLATION_BASELINE`, `PROMPT_CACHE_BREAK_DETECTION`

### 平台/环境
`DAEMON`, `NEW_INIT`, `LODESTONE`, `TORCH`, `CHICAGO_MCP`, `UDS_INBOX`, `AGENT_TRIGGERS`, `AGENT_TRIGGERS_REMOTE`

### 设置同步
`DOWNLOAD_USER_SETTINGS`, `UPLOAD_USER_SETTINGS`, `FILE_PERSISTENCE`

### 其他
`AWAY_SUMMARY`, `BUILDING_CLAUDE_APPS`, `WEB_BROWSER_TOOL`, `MONITOR_TOOL`, `REVIEW_ARTIFACT`, `TEMPLATES`, `HARD_FAIL`, `UNATTENDED_RETRY`, `SUMMARIZE_CONNECTOR_TEXT`

---

## 跨模块依赖图

```
用户输入 → QueryEngine.submitMessage()
              ↓
         query.ts queryLoop()  ← BudgetTracker
              ↓
    ┌─── callModel (streaming) ──── services/api ──── Anthropic API
    │         ↓
    │  StreamingToolExecutor
    │    ↓
    │  toolOrchestration.ts ──── partitionToolCalls()
    │    ↓
    │  useCanUseTool ──── hooks/toolPermission ──── ML Classifier
    │    ↓
    │  Tool.call() ──── 60+ 具体工具实现
    │    ↓
    │  PostToolUse hooks
    │
    └── handleStopHooks()
              ↓
         extractMemories (fork) ──── memdir/
              ↓
         SessionMemory (fork) ──── services/SessionMemory
              ↓
         PromptSuggestion/speculation (fork)
              ↓
         AppState ──── state/store.ts
              ↓
         tasks/ ──── 7 种后台任务类型
              ↓
         UI: ink/ → components/ → screens/REPL.tsx

entrypoints/cli.tsx
  ├→ bootstrap/state.ts (DAG leaf)
  ├→ init.ts → services/{analytics, oauth, policyLimits, lsp, mcp}
  ├→ bridge/ → remote/ → server/
  └→ main.tsx → screens/REPL.tsx
```

---

## 核心设计理念总结

1. **AsyncGenerator everywhere** — query、工具执行、hook 执行全部用 AsyncGenerator，统一流式处理和中断语义

2. **编译时特性门控** — 89 个 `feature()` 开关 + Bun 的 dead code elimination，外部构建物理不含内部代码

3. **协调不靠代码靠 prompt** — coordinator 模式没有编排引擎，全靠精心设计的 ~300 行 system prompt

4. **fail-closed 默认** — 工具默认不并发安全、不只读、不安全，需要显式声明

5. **五层压缩体系** — snip → microcompact → context collapse → autocompact → reactive compact，保证 context 不溢出

6. **Forked Agent 模式** — compact、extractMemories、SessionMemory、AgentSummary、speculation 全部 fork 主对话共享 prompt cache

7. **bootstrap isolation** — 全局状态是 import DAG 叶节点，ESLint 规则强制，杜绝循环依赖

8. **Prompt cache 是一等公民** — 系统提示词静态/动态分段、beta header sticky latch、工具 schema 延迟加载，所有设计围绕减少 cache bust

9. **性能是一等公民** — 字符串 interning、DECSTBM 硬件滚动、blit 优化、帧时间追踪、yoga 缓存命中追踪

10. **React 渲染终端** — 不是"使用 Ink"，而是自定义终端渲染引擎，保留 React reconciler 接口但重写了整个管线
