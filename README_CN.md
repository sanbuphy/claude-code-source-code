# Claude Code 架构学习与研究

> **导读**：本项目是一个关于 CLI Agent 架构的学习研究仓库。所有内容均基于互联网上公开的资料与讨论整理而成，特别参考了目前非常受欢迎的 CLI Agent `claude-code` 的相关公开信息。我们的初衷是帮助大家更好地理解和使用 Agent 技术，未来也会持续推出更多关于 Agent 架构解析与实践的探讨内容，感谢各位的关注与支持！

> **免责声明**: 本仓库内容仅用于技术研究和科研爱好者交流学习参考，**严禁任何个人、机构及组织将其用于商业用途、盈利性活动、非法用途及其他未经授权的场景。** 若内容涉及侵犯您的合法权益、知识产权或存在其他侵权问题，请及时联系我们，我们将第一时间核实并予以删除处理。


**语言**: [English](README.md) | **中文** | [한국어](README_KR.md) | [日本語](README_JA.md)

---

## 目录

- [深度分析文档 (`docs/`)](#深度分析文档-docs) — 遥测、模型代号、卧底模式、远程控制、未来路线图
- [目录参考](#目录参考) — 代码结构树
- [架构概览](#架构概览) — 入口 → 查询引擎 → 工具/服务/状态
- [工具系统与权限架构](#工具系统与权限架构) — 40+ 工具、权限流、子代理
- [12 个渐进式安全带机制](#12-个渐进式安全带机制-harness-mechanisms) — Claude Code 如何在代理循环上构建生产特性

---

## 深度分析文档 (`docs/`)

基于网络公开资料与社区讨论整理的 Claude Code v2.1.88 分析报告，中英双语。

```
docs/
├── en/                                        # English
│   ├── [01-telemetry-and-privacy.md]          # Telemetry & Privacy — what's collected, why you can't opt out
│   ├── [02-hidden-features-and-codenames.md]  # Codenames (Capybara/Tengu/Numbat), feature flags, internal vs external
│   ├── [03-undercover-mode.md]                # Undercover Mode — hiding AI authorship in open-source repos
│   ├── [04-remote-control-and-killswitches.md]# Remote Control — managed settings, killswitches, model overrides
│   └── [05-future-roadmap.md]                 # Future Roadmap — Numbat, KAIROS, voice mode, unreleased tools
│
├── ja/                                        # 日本語
│   ├── [01-テレメトリとプライバシー.md]          # テレメトリとプライバシー — 収集項目、無効化不可の理由
│   ├── [02-隠し機能とコードネーム.md]           # 隠し機能 — モデルコードネーム、feature flag、内部/外部ユーザーの違い
│   ├── [03-アンダーカバーモード.md]             # アンダーカバーモード — オープンソースでのAI著作隠匿
│   ├── [04-リモート制御とキルスイッチ.md]       # リモート制御 — 管理設定、キルスイッチ、モデルオーバーライド
│   └── [05-今後のロードマップ.md]               # 今後のロードマップ — Numbat、KAIROS、音声モード、未公開ツール
│
├── ko/                                        # 한국어
│   ├── [01-텔레메트리와-프라이버시.md]          # 텔레메트리 및 프라이버시 — 수집 항목, 비활성화 불가 이유
│   ├── [02-숨겨진-기능과-코드네임.md]          # 숨겨진 기능 — 모델 코드네임, feature flag, 내부/외부 사용자 차이
│   ├── [03-언더커버-모드.md]                   # 언더커버 모드 — 오픈소스에서 AI 저작 은폐
│   ├── [04-원격-제어와-킬스위치.md]            # 원격 제어 — 관리 설정, 킬스위치, 모델 오버라이드
│   └── [05-향후-로드맵.md]                     # 향후 로드맵 — Numbat, KAIROS, 음성 모드, 미공개 도구
│
└── zh/                                        # 中文
    ├── [01-遥测与隐私分析.md]                    # 遥测与隐私 — 收集了什么，为什么无法退出
    ├── [02-隐藏功能与模型代号.md]                # 隐藏功能 — 模型代号，feature flag，内外用户差异
    ├── [03-卧底模式分析.md]                     # 卧底模式 — 在开源项目中隐藏 AI 身份
    ├── [04-远程控制与紧急开关.md]                # 远程控制 — 托管设置，紧急开关，模型覆盖
    └── [05-未来路线图.md]                       # 未来路线图 — Numbat，KAIROS，语音模式，未上线工具
```

> 点击文件名即可跳转到对应报告。

| # | 主题 | 核心发现 | 链接 |
|---|------|---------|------|
| 01 | **遥测与隐私** | 双层分析管道（1P, Datadog）。环境指纹、进程指标、每个事件携带会话/用户 ID。**没有面向用户的退出开关**。`OTEL_LOG_TOOL_DETAILS=1` 可记录完整工具输入。 | [EN](docs/en/01-telemetry-and-privacy.md) · [中文](docs/zh/01-遥测与隐私分析.md) |
| 02 | **隐藏功能与代号** | 动物代号体系（Capybara v8, Tengu, Fennec→Opus 4.6, **Numbat** 下一代）。Feature flag 用随机词对掩盖用途。内部用户获得更好的 prompt 和验证代理。隐藏命令：`/btw`、`/stickers`。 | [EN](docs/en/02-hidden-features-and-codenames.md) · [中文](docs/zh/02-隐藏功能与模型代号.md) |
| 03 | **卧底模式** | 官方员工在公开仓库自动进入卧底模式。模型指令："**不要暴露你的掩护身份**" — 剥离所有 AI 归属，commit 看起来像人类写的。**没有强制关闭选项。** | [EN](docs/en/03-undercover-mode.md) · [中文](docs/zh/03-卧底模式分析.md) |
| 04 | **远程控制与 Killswitch** | 每小时轮询 `/api/claude_code/settings`。危险变更弹出阻塞对话框 — **拒绝 = 程序退出**。6+ 紧急开关（绕过权限、快速模式、语音模式、分析 sink）。GrowthBook 可无同意改变任何用户行为。 | [EN](docs/en/04-remote-control-and-killswitches.md) · [中文](docs/zh/04-远程控制与紧急开关.md) |
| 05 | **未来路线图** | **Numbat** 代号确认。Opus 4.7 / Sonnet 4.8 开发中。**KAIROS** = 完全自主代理模式，心跳 `<tick>`、推送通知、PR 订阅。语音模式（push-to-talk）已就绪。发现 17 个未上线工具。 | [EN](docs/en/05-future-roadmap.md) · [中文](docs/zh/05-未来路线图.md) |

---

## 版权与免责声明

```
本仓库仅用于技术研究和教育目的。严禁商业使用。

如果您是版权所有者并认为本仓库内容侵犯了您的权利，
请联系仓库所有者立即删除。
```

---

## 统计数据

| 项目 | 数量 |
|------|------|
| 文件 (.ts/.tsx) | ~1,884 |
| 行数 | ~512,664 |
| 最大单文件 | `query.ts` (~785KB) |
| 内置工具 | ~40+ |
| 斜杠命令 | ~80+ |
| 依赖 (node_modules) | ~192 个包 |
| 运行时 | Bun（编译为 Node.js >= 18 bundle）|

---

## 代理模式

```text
                    核心循环
                    ========

    用户 --> messages[] --> Claude API --> 响应
                                          |
                                stop_reason == "tool_use"?
                               /                          \
                             是                           否
                              |                             |
                        执行工具                        返回文本
                        追加 tool_result
                        循环回退 -----------------> messages[]


    这就是最小的代理循环。Claude Code 在此循环上
    包裹了生产级线束：权限、流式传输、并发、
    压缩、子代理、持久化和 MCP。
```

---

## 目录参考

```text
src/
├── main.tsx                 # REPL 引导程序，4,683 行
├── QueryEngine.ts           # SDK/headless 查询生命周期引擎
├── query.ts                 # 主代理循环 (785KB，最大文件)
├── Tool.ts                  # 工具接口 + buildTool 工厂
├── Task.ts                  # 任务类型、ID、状态基类
├── tools.ts                 # 工具注册、预设、过滤
├── commands.ts              # 斜杠命令定义
├── context.ts               # 用户输入上下文
├── cost-tracker.ts          # API 成本累积
├── setup.ts                 # 首次运行设置流程
│
├── bridge/                  # Claude Desktop / 远程桥接
│   ├── bridgeMain.ts        #   会话生命周期管理器
│   ├── bridgeApi.ts         #   HTTP 客户端
│   ├── bridgeConfig.ts      #   连接配置
│   ├── bridgeMessaging.ts   #   消息中继
│   ├── sessionRunner.ts     #   进程生成
│   ├── jwtUtils.ts          #   JWT 刷新
│   ├── workSecret.ts        #   认证令牌
│   └── capacityWake.ts      #   基于容量的唤醒
│
├── cli/                     # CLI 基础设施
│   ├── handlers/            #   命令处理器
│   └── transports/          #   I/O 传输 (stdio, structured)
│
├── commands/                # ~80 个斜杠命令
│   ├── agents/              #   代理管理
│   ├── compact/             #   上下文压缩
│   ├── config/              #   设置管理
│   ├── help/                #   帮助显示
│   ├── login/               #   身份验证
│   ├── mcp/                 #   MCP 服务器管理
│   ├── memory/              #   记忆系统
│   ├── plan/                #   计划模式
│   ├── resume/              #   会话恢复
│   ├── review/              #   代码审查
│   └── ...                  #   还有 70+ 个命令
│
├── components/              # React/Ink 终端 UI
│   ├── design-system/       #   可重用 UI 原语
│   ├── messages/            #   消息渲染
│   ├── permissions/         #   权限对话框
│   ├── PromptInput/         #   输入字段 + 建议
│   ├── LogoV2/              #   品牌 + 欢迎屏幕
│   ├── Settings/            #   设置面板
│   ├── Spinner.tsx          #   加载指示器
│   └── ...                  #   还有 40+ 个组件组
│
├── entrypoints/             # 应用入口点
│   ├── cli.tsx              #   CLI 主程序 (版本、帮助、守护进程)
│   ├── sdk/                 #   Agent SDK (类型、会话)
│   └── mcp.ts               #   MCP 服务器入口
│
├── hooks/                   # React hooks
│   ├── useCanUseTool.tsx    #   权限检查
│   ├── useReplBridge.tsx    #   网桥连接
│   ├── notifs/              #   通知 hooks
│   └── toolPermission/      #   工具权限处理程序
│
├── services/                # 业务逻辑层
│   ├── api/                 #   Claude API 客户端
│   │   ├── claude.ts        #     流式 API 调用
│   │   ├── errors.ts        #     错误分类
│   │   └── withRetry.ts     #     重试逻辑
│   ├── analytics/           #   遥测 + GrowthBook
│   ├── compact/             #   上下文压缩
│   ├── mcp/                 #   MCP 连接管理
│   ├── tools/               #   工具执行引擎
│   │   ├── StreamingToolExecutor.ts  # 并行工具运行器
│   │   └── toolOrchestration.ts      # 批处理编排
│   ├── plugins/             #   插件加载器
│   └── settingsSync/        #   跨设备设置同步
│
├── state/                   # 应用状态
│   ├── AppStateStore.ts     #   Store 定义
│   └── AppState.tsx         #   React provider + hooks
│
├── tasks/                   # 任务实现
│   ├── LocalShellTask/      #   Bash 命令执行
│   ├── LocalAgentTask/      #   子代理执行
│   ├── RemoteAgentTask/     #   通过网桥连接远程代理
│   ├── InProcessTeammateTask/ # 进程内队友
│   └── DreamTask/           #   后台思考
│
├── tools/                   # 40+ 工具实现
│   ├── AgentTool/           #   子代理生成 + fork
│   ├── BashTool/            #   Shell 命令执行
│   ├── FileReadTool/        #   文件读取 (PDF, 图像等)
│   ├── FileEditTool/        #   字符串替换编辑
│   ├── FileWriteTool/       #   完整文件创建
│   ├── GlobTool/            #   文件模式搜索
│   ├── GrepTool/            #   内容搜索 (ripgrep)
│   ├── WebFetchTool/        #   HTTP 获取
│   ├── WebSearchTool/       #   Web 搜索
│   ├── MCPTool/             #   MCP 工具包装器
│   ├── SkillTool/           #   技能调用
│   ├── AskUserQuestionTool/ #   用户交互
│   └── ...                  #   还有 30+ 个工具
│
├── types/                   # 类型定义
│   ├── message.ts           #   消息辨识联合类型
│   ├── permissions.ts       #   权限类型
│   ├── tools.ts             #   工具进度类型
│   └── ids.ts               #   带有品牌的 ID 类型
│
├── utils/                   # 工具函数（最大目录）
│   ├── permissions/         #   权限规则引擎
│   ├── messages/            #   消息格式化
│   ├── model/               #   模型选择逻辑
│   ├── settings/            #   设置管理
│   ├── sandbox/             #   沙盒运行时适配器
│   ├── hooks/               #   Hook 执行
│   ├── memory/              #   记忆系统工具
│   ├── git/                 #   Git 操作
│   ├── github/              #   GitHub API
│   ├── bash/                #   Bash 执行辅助函数
│   ├── swarm/               #   多代理集群
│   ├── telemetry/           #   遥测报告
│   └── ...                  #   还有 30+ 个工具组
│
└── vendor/                  # 原生模块存根
    ├── audio-capture-src/   #   音频输入
    ├── image-processor-src/ #   图像处理
    ├── modifiers-napi-src/  #   原生修饰符
    └── url-handler-src/     #   URL 处理
```

---

## 架构概览

```text
┌─────────────────────────────────────────────────────────────────────┐
│                         入口层                                      │
│  cli.tsx ──> main.tsx ──> REPL.tsx (交互式)                        │
│                     └──> QueryEngine.ts (headless/SDK)              │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       查询引擎                                      │
│  submitMessage(prompt) ──> AsyncGenerator<SDKMessage>               │
│    │                                                                │
│    ├── fetchSystemPromptParts()    ──> 组装系统提示词               │
│    ├── processUserInput()          ──> 处理 /命令                   │
│    ├── query()                     ──> 主代理循环                   │
│    │     ├── StreamingToolExecutor ──> 并行工具执行                  │
│    │     ├── autoCompact()         ──> 上下文压缩                   │
│    │     └── runTools()            ──> 工具编排                     │
│    └── yield SDKMessage            ──> 流式传输给消费者             │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                 ▼
┌──────────────────┐ ┌─────────────────┐ ┌──────────────────┐
│     工具系统     │ │     服务层      │ │      状态层      │
│                  │ │                 │ │                  │
│ 工具接口         │ │ api/claude.ts   │ │ AppState Store   │
│  ├─ call()       │ │  API 客户端     │ │  ├─ permissions  │
│  ├─ validate()   │ │ compact/        │ │  ├─ fileHistory  │
│  ├─ checkPerms() │ │  自动压缩       │ │  ├─ agents       │
│  ├─ render()     │ │ mcp/            │ │  └─ fastMode     │
│  └─ prompt()     │ │  MCP 协议       │ │                  │
│                  │ │ analytics/      │ │ React Context    │
│ 40+ 内置工具:    │ │  遥测           │ │  ├─ useAppState  │
│  ├─ BashTool     │ │ tools/          │ │  └─ useSetState  │
│  ├─ FileRead     │ │  执行器         │ │                  │
│  ├─ FileEdit     │ │ plugins/        │ └──────────────────┘
│  ├─ Glob/Grep    │ │  加载器         │
│  ├─ AgentTool    │ │ settingsSync/   │
│  ├─ WebFetch     │ │  跨设备同步     │
│  └─ MCPTool      │ │ oauth/          │
│                  │ │  认证流程       │
└──────────────────┘ └─────────────────┘
              │                │
              ▼                ▼
┌──────────────────┐ ┌─────────────────┐
│     任务系统     │ │     桥接层      │
│                  │ │                 │
│ 任务类型:        │ │ bridgeMain.ts   │
│  ├─ local_bash   │ │  会话管理       │
│  ├─ local_agent  │ │ bridgeApi.ts    │
│  ├─ remote_agent │ │  HTTP 客户端    │
│  ├─ in_process   │ │ workSecret.ts   │
│  ├─ dream        │ │  认证令牌       │
│  └─ workflow     │ │ sessionRunner   │
│                  │ │  进程生成       │
│ ID: 前缀+8字符   │ └─────────────────┘
│  b=bash a=agent  │
│  r=remote t=team │
└──────────────────┘
```

---

## 数据流：单个查询生命周期

```text
 用户输入 (提示词 / 斜杠命令)
     │
     ▼
 processUserInput()                ← 解析 /命令，构建 UserMessage
     │
     ▼
 fetchSystemPromptParts()          ← 工具 → 提示词部分，CLAUDE.md 记忆
     │
     ▼
 recordTranscript()                ← 将用户消息持久化到磁盘 (JSONL)
     │
     ▼
 ┌─→ normalizeMessagesForAPI()     ← 剥离仅 UI 使用的字段，需要时进行压缩
 │   │
 │   ▼
 │   Claude API (流式)             ← 带有工具 + 系统提示词的 POST /v1/messages
 │   │
 │   ▼
 │   流事件                        ← message_start → content_block_delta → message_stop
 │   │
 │   ├─ 文本块 ──────────────────→ 传递给消费者 (SDK / REPL)
 │   │
 │   └─ tool_use 块?
 │       │
 │       ▼
 │   StreamingToolExecutor         ← 划分：并发安全 vs 串行
 │       │
 │       ▼
 │   canUseTool()                  ← 权限检查 (钩子 + 规则 + UI 提示)
 │       │
 │       ├─ 拒绝 ────────────────→ 追加 tool_result(error)，继续循环
 │       │
 │       └─ 允许
 │           │
 │           ▼
 │       tool.call()               ← 执行工具 (Bash, Read, Edit 等)
 │           │
 │           ▼
 │       追加 tool_result          ← 推入 messages[]，recordTranscript()
 │           │
 └─────────┘                       ← 循环回到 API 调用
     │
     ▼ (stop_reason != "tool_use")
 生成结果消息                      ← 最终文本、使用情况、成本、session_id
```

---

## 工具系统与权限架构

```text
                    工具接口
                    ==============

    buildTool(definition) ──> Tool<Input, Output, Progress>

    每个工具都实现：
    ┌────────────────────────────────────────────────────────┐
    │  生命周期                                              │
    │  ├── validateInput()      → 尽早拒绝无效参数           │
    │  ├── checkPermissions()   → 工具特定的授权检查         │
    │  └── call()               → 执行并返回结果             │
    │                                                        │
    │  能力特性                                              │
    │  ├── isEnabled()          → 功能开关检查               │
    │  ├── isConcurrencySafe()  → 是否可并行运行？           │
    │  ├── isReadOnly()         → 是否无副作用？             │
    │  ├── isDestructive()      → 是否为不可逆操作？         │
    │  └── interruptBehavior()  → 拦截还是阻塞等待用户？     │
    │                                                        │
    │  渲染 (React/Ink)                                      │
    │  ├── renderToolUseMessage()     → 输入显示             │
    │  ├── renderToolResultMessage()  → 输出显示             │
    │  ├── renderToolUseProgressMessage() → 加载状态/进度    │
    │  └── renderGroupedToolUse()     → 并行工具组显示       │
    │                                                        │
    │  面向 AI                                               │
    │  ├── prompt()             → 提供给 LLM 的工具描述      │
    │  ├── description()        → 动态描述                   │
    │  └── mapToolResultToAPI() → 格式化为 API 响应          │
    └────────────────────────────────────────────────────────┘
```

### 完整工具清单

```text
    文件操作                 搜索与发现                执行
    ═════════════════        ══════════════════════     ══════════
    FileReadTool             GlobTool                  BashTool
    FileEditTool             GrepTool                  PowerShellTool
    FileWriteTool            ToolSearchTool
    NotebookEditTool                                   交互
                                                       ═══════════
    网络与请求              代理与任务                AskUserQuestionTool
    ════════════════        ══════════════════        BriefTool
    WebFetchTool             AgentTool
    WebSearchTool            SendMessageTool           计划与工作流
                             TeamCreateTool            ════════════════════
    MCP 协议                 TeamDeleteTool            EnterPlanModeTool
    ══════════════           TaskCreateTool            ExitPlanModeTool
    MCPTool                  TaskGetTool               EnterWorktreeTool
    ListMcpResourcesTool     TaskUpdateTool            ExitWorktreeTool
    ReadMcpResourceTool      TaskListTool              TodoWriteTool
                             TaskStopTool
                             TaskOutputTool            系统
                                                       ════════
                             技能与扩展                ConfigTool
                             ═════════════════════     SkillTool
                             SkillTool                 ScheduleCronTool
                             LSPTool                   SleepTool
                                                       TungstenTool
```

---

## 权限系统

```text
    工具调用请求
          │
          ▼
    ┌─ validateInput() ──────────────────────────────────┐
    │  在任何权限检查之前拒绝无效的输入                  │
    └────────────────────┬───────────────────────────────┘
                         │
                         ▼
    ┌─ PreToolUse Hooks (调用前钩子) ────────────────────┐
    │  用户定义的 shell 命令 (settings.json hooks)       │
    │  可以：批准、拒绝或修改输入                        │
    └────────────────────┬───────────────────────────────┘
                         │
                         ▼
    ┌─ 权限规则 (Permission Rules) ──────────────────────┐
    │  alwaysAllowRules:  匹配工具名/模式 → 自动允许     │
    │  alwaysDenyRules:   匹配工具名/模式 → 自动拒绝     │
    │  alwaysAskRules:    匹配工具名/模式 → 总是询问     │
    │  来源：设置、CLI 参数、会话决策                    │
    └────────────────────┬───────────────────────────────┘
                         │
                    没有规则匹配？
                         │
                         ▼
    ┌─ 交互式提示 (Interactive Prompt) ──────────────────┐
    │  用户看到工具名称 + 输入参数                       │
    │  选项：允许一次 / 总是允许 / 拒绝                  │
    └────────────────────┬───────────────────────────────┘
                         │
                         ▼
    ┌─ checkPermissions() ───────────────────────────────┐
    │  工具特定的逻辑 (例如：路径沙盒检查)               │
    └────────────────────┬───────────────────────────────┘
                         │
                    已批准 → tool.call()
```

---

## 子代理与多代理架构

```text
                        主代理 (MAIN AGENT)
                        ==========
                            │
            ┌───────────────┼───────────────┐
            ▼               ▼               ▼
     ┌──────────────┐ ┌──────────┐ ┌──────────────┐
     │  FORK 代理   │ │ 远程代理 │ │ 进程内队友   │
     │              │ │          │ │              │
     │ Fork 进程    │ │ 网桥会话 │ │ 同一进程     │
     │ 共享缓存     │ │ 完全隔离 │ │ 异步上下文   │
     │ 全新 msgs[]  │ │          │ │ 共享状态     │
     └──────────────┘ └──────────┘ └──────────────┘

    生成模式 (SPAWN MODES):
    ├─ default    → 进程内，共享对话
    ├─ fork       → 子进程，全新的 messages[]，共享文件缓存
    ├─ worktree   → 隔离的 git worktree + fork
    └─ remote     → 通过网桥连接到 Claude Code Remote / 容器

    通信机制:
    ├─ SendMessageTool     → 代理间消息传递
    ├─ TaskCreate/Update   → 共享任务看板
    └─ TeamCreate/Delete   → 团队生命周期管理

    集群模式 (SWARM MODE，特性受限):
    ┌─────────────────────────────────────────────┐
    │  领导代理 (Lead Agent)                      │
    │    ├── 队友 A ──> 认领任务 1                │
    │    ├── 队友 B ──> 认领任务 2                │
    │    └── 队友 C ──> 认领任务 3                │
    │                                             │
    │  共享：任务看板、消息收件箱                 │
    │  隔离：messages[]、文件缓存、cwd            │
    └─────────────────────────────────────────────┘
```

---

## 上下文管理 (压缩系统)

```text
    上下文窗口预算
    ═════════════════════

    ┌─────────────────────────────────────────────────────┐
    │  系统提示词 (工具、权限、CLAUDE.md)                 │
    │  ══════════════════════════════════════════════      │
    │                                                     │
    │  对话历史                                           │
    │  ┌─────────────────────────────────────────────┐    │
    │  │ [旧消息的压缩摘要]                           │    │
    │  │ ═══════════════════════════════════════════  │    │
    │  │ [compact_boundary 标记]                      │    │
    │  │ ─────────────────────────────────────────── │    │
    │  │ [最近的消息 — 完整保真度]                    │    │
    │  │ user → assistant → tool_use → tool_result   │    │
    │  └─────────────────────────────────────────────┘    │
    │                                                     │
    │  当前轮次 (用户 + 助手响应)                         │
    └─────────────────────────────────────────────────────┘

    三种压缩策略:
    ├─ autoCompact     → 当 token 数量超过阈值时触发
    │                     通过紧凑的 API 调用总结旧消息
    ├─ snipCompact     → 移除僵尸消息和过时标记
    │                     (HISTORY_SNIP feature flag)
    └─ contextCollapse → 重构上下文以提高效率
                         (CONTEXT_COLLAPSE feature flag)

    压缩流程:
    messages[] ──> getMessagesAfterCompactBoundary()
                        │
                        ▼
                  旧消息 ──> Claude API (总结) ──> 压缩摘要
                        │
                        ▼
                  [摘要] + [compact_boundary] + [最近的消息]
```

---

## MCP (模型上下文协议) 集成

```text
    ┌─────────────────────────────────────────────────────────┐
    │                  MCP 架构                                │
    │                                                         │
    │  MCPConnectionManager.tsx                               │
    │    ├── 服务器发现 (来自 settings.json 的配置)           │
    │    │     ├── stdio  → 生成子进程                        │
    │    │     ├── sse    → HTTP EventSource                  │
    │    │     ├── http   → 流式 HTTP                         │
    │    │     ├── ws     → WebSocket                         │
    │    │     └── sdk    → 进程内传输                        │
    │    │                                                    │
    │    ├── 客户端生命周期                                   │
    │    │     ├── connect → initialize → list tools          │
    │    │     ├── 通过 MCPTool 包装器调用工具                │
    │    │     └── disconnect / 带有退避的重连                │
    │    │                                                    │
    │    ├── 身份验证                                         │
    │    │     ├── OAuth 2.0 流程 (McpOAuthConfig)            │
    │    │     ├── 跨应用访问 (XAA / SEP-990)                 │
    │    │     └── 通过 headers 传递 API key                  │
    │    │                                                    │
    │    └── 工具注册                                         │
    │          ├── mcp__<server>__<tool> 命名约定             │
    │          ├── 来自 MCP 服务器的动态 schema               │
    │          ├── 权限透传给 Claude Code                     │
    │          └── 资源列表 (ListMcpResourcesTool)            │
    │                                                         │
    └─────────────────────────────────────────────────────────┘
```

---

## 桥接层 (Claude Desktop / Remote)

```text
    Claude Desktop / Web / Cowork          Claude Code CLI
    ══════════════════════════            ═════════════════

    ┌───────────────────┐                 ┌──────────────────┐
    │  桥接客户端       │  ←─ HTTP ──→   │  bridgeMain.ts   │
    │  (Desktop App)    │                 │                  │
    └───────────────────┘                 │  会话管理器      │
                                          │  ├── 生成 CLI    │
    协议:                                 │  ├── 轮询状态    │
    ├─ JWT 身份验证                       │  ├── 中继消息    │
    ├─ 工作密钥交换                       │  └── 容量唤醒    │
    ├─ 会话生命周期                       │                  │
    │  ├── create                         │  退避策略:       │
    │  ├── run                            │  ├─ 连接: 2s→2m  │
    │  └─ stop                            │  └─ 生成: 500ms→30s│
    └─ 令牌刷新调度器                     └──────────────────┘
```

---

## 会话持久化

```text
    会话存储
    ══════════════

    ~/.claude/projects/<hash>/sessions/
    └── <session-id>.jsonl           ← 仅追加日志
        ├── {"type":"user",...}
        ├── {"type":"assistant",...}
        ├── {"type":"progress",...}
        └── {"type":"system","subtype":"compact_boundary",...}

    恢复流程:
    getLastSessionLog() ──> 解析 JSONL ──> 重建 messages[]
         │
         ├── --continue     → cwd 中的最后一次会话
         ├── --resume <id>  → 特定会话
         └── --fork-session → 新 ID，复制历史记录

    持久化策略:
    ├─ 用户消息  → 阻塞等待写入 (用于崩溃恢复)
    ├─ 助手消息  → 即发即弃 (保持顺序的队列)
    ├─ 进度      → 内联写入 (在下一次查询时去重)
    └─ 刷新      → 在生成结果时 / cowork 急切刷新
```

---

## 功能开关系统 (Feature Flag)

```text
    死代码消除 (Bun 编译时)
    ══════════════════════════════════════════

    feature('FLAG_NAME')  ──→  true  → 包含在包中
                           ──→  false → 从包中剥离

    标志 (在源码中观察到):
    ├─ COORDINATOR_MODE      → 多代理协调器
    ├─ HISTORY_SNIP          → 激进的历史修剪
    ├─ CONTEXT_COLLAPSE      → 上下文重构
    ├─ DAEMON                → 后台守护进程 worker
    ├─ AGENT_TRIGGERS        → cron/远程触发器
    ├─ AGENT_TRIGGERS_REMOTE → 远程触发器支持
    ├─ MONITOR_TOOL          → MCP 监控工具
    ├─ WEB_BROWSER_TOOL      → 浏览器自动化
    ├─ VOICE_MODE            → 语音输入/输出
    ├─ TEMPLATES             → 任务分类器
    ├─ EXPERIMENTAL_SKILL_SEARCH → 技能发现
    ├─ KAIROS                → 推送通知、文件发送
    ├─ PROACTIVE             → 睡眠工具、主动行为
    ├─ OVERFLOW_TEST_TOOL    → 测试工具
    ├─ TERMINAL_PANEL        → 终端捕获
    ├─ WORKFLOW_SCRIPTS      → 工作流工具
    ├─ CHICAGO_MCP           → 计算机使用 MCP
    ├─ DUMP_SYSTEM_PROMPT    → 提示词提取 (仅限 ant)
    ├─ UDS_INBOX             → 对等发现
    ├─ ABLATION_BASELINE     → 实验消融
    └─ UPGRADE_NOTICE        → 升级通知

    运行时门控:
    ├─ process.env.USER_TYPE === 'ant'  → 内部功能
    └─ GrowthBook feature flags         → 运行时的 A/B 实验
```

---

## 状态管理

```text
    ┌──────────────────────────────────────────────────────────┐
    │                  AppState Store                           │
    │                                                          │
    │  AppState {                                              │
    │    toolPermissionContext: {                              │
    │      mode: PermissionMode,           ← default/plan等   │
    │      additionalWorkingDirectories,                        │
    │      alwaysAllowRules,               ← 自动批准          │
    │      alwaysDenyRules,                ← 自动拒绝          │
    │      alwaysAskRules,                 ← 总是提示          │
    │      isBypassPermissionsModeAvailable                    │
    │    },                                                    │
    │    fileHistory: FileHistoryState,    ← 撤销快照          │
    │    attribution: AttributionState,    ← 提交跟踪          │
    │    verbose: boolean,                                     │
    │    mainLoopModel: string,           ← 活动模型          │
    │    fastMode: FastModeState,                              │
    │    speculation: SpeculationState                          │
    │  }                                                       │
    │                                                          │
    │  React 集成:                                             │
    │  ├── AppStateProvider   → 通过 createContext 创建 store   │
    │  ├── useAppState(sel)   → 基于选择器的订阅               │
    │  └── useSetAppState()   → immer 风格的更新函数           │
    └──────────────────────────────────────────────────────────┘
```

---

## 12 个渐进式安全带机制 (Harness Mechanisms)

该架构展示了生产级 AI 代理除了基本循环之外，所需的 12 层渐进式机制：

```text
    s01  核心循环 (THE LOOP)  "一个循环 + Bash 就是你所需要的全部"
         query.ts: 调用 Claude API 的 while-true 循环，
         检查 stop_reason，执行工具，追加结果。

    s02  工具调度 (TOOL DISPATCH) "添加一个工具 = 添加一个处理程序"
         Tool.ts + tools.ts: 每个工具都注册到调度映射中。
         循环保持不变。buildTool() 工厂提供安全的默认值。

    s03  计划 (PLANNING)      "没有计划的代理会迷失方向"
         EnterPlanModeTool/ExitPlanModeTool + TodoWriteTool:
         先列出步骤，然后执行。使完成率翻倍。

    s04  子代理 (SUB-AGENTS)  "拆分大任务；每个子任务清理上下文"
         AgentTool + forkSubagent.ts: 每个子代获得全新的 messages[]，
         保持主对话的干净。

    s05  按需知识 (KNOWLEDGE) "需要时加载知识"
         SkillTool + memdir/: 通过 tool_result 注入，而不是系统提示词。
         按目录延迟加载 CLAUDE.md 文件。

    s06  上下文压缩 (COMPRESSION) "上下文满了；腾出空间"
         services/compact/: 三层策略：
         autoCompact (总结) + snipCompact (修剪) + contextCollapse

    s07  持久化任务 (TASKS)   "大目标 → 小任务 → 磁盘"
         TaskCreate/Update/Get/List: 基于文件的任务图，
         具有状态跟踪、依赖关系和持久性。

    s08  后台任务 (BACKGROUND) "后台执行慢操作；代理继续思考"
         DreamTask + LocalShellTask: 守护线程运行命令，
         完成后注入通知。

    s09  代理团队 (TEAMS)     "一个人做太大 → 委派给队友"
         TeamCreate/Delete + InProcessTeammateTask: 
         具有异步邮箱的持久队友。

    s10  团队协议 (PROTOCOLS) "共享通信规则"
         SendMessageTool: 一种请求-响应模式驱动
         代理之间的所有协商。

    s11  自主代理 (AUTONOMOUS) "队友自己扫描并认领任务"
         coordinator/coordinatorMode.ts: 空闲循环 + 自动认领，
         不需要领导来分配每个任务。

    s12  工作树隔离 (WORKTREE) "每个人在自己的目录中工作"
         EnterWorktreeTool/ExitWorktreeTool: 任务管理目标，
         工作树管理目录，由 ID 绑定。
```

---

## 关键设计模式

| 模式 | 位置 | 目的 |
|---------|-------|---------|
| **AsyncGenerator 流式传输** | `QueryEngine`, `query()` | 从 API 到消费者的全链路流式传输 |
| **构建器 + 工厂 (Builder + Factory)** | `buildTool()` | 为工具定义提供安全的默认值 |
| **品牌类型 (Branded Types)** | `SystemPrompt`, `asSystemPrompt()` | 防止字符串/数组混淆 |
| **功能开关 + DCE** | 来自 `bun:bundle` 的 `feature()` | 编译时死代码消除 |
| **辨识联合 (Discriminated Unions)** | `Message` 类型 | 类型安全的消息处理 |
| **观察者 + 状态机** | `StreamingToolExecutor` | 工具执行生命周期跟踪 |
| **快照状态 (Snapshot State)** | `FileHistoryState` | 文件操作的撤销/重做 |
| **环形缓冲区 (Ring Buffer)** | 错误日志 | 长会话的有限内存 |
| **即发即弃写入 (Fire-and-Forget)** | `recordTranscript()` | 保持顺序的非阻塞持久化 |
| **延迟 Schema (Lazy Schema)** | `lazySchema()` | 延迟 Zod schema 评估以提高性能 |
| **上下文隔离 (Context Isolation)** | `AsyncLocalStorage` | 共享进程中每个代理的上下文 |

---

## 许可证

本仓库内容仅用于技术研究和教育目的。知识产权归原公司所有，若有侵权请联系删除。
