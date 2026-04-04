# Claude Code アーキテクチャ学習と研究

> **はじめに**: このプロジェクトは、CLI Agent アーキテクチャに関する学習および研究用のリポジトリです。すべての資料は、インターネット上で公開されている情報や議論のみに基づいてまとめられており、特に現在非常に人気のある CLI Agent `claude-code` に関する公開情報を参考にしています。私たちの目的は、開発者が Agent 技術をより深く理解し、活用できるように支援することです。今後も Agent アーキテクチャに関する洞察や実践的な議論を継続的に共有していく予定です。皆様のご関心とご支援に感謝いたします！

> **免責事項**: 本リポジトリのコンテンツは技術研究、学習、教育目的の交流のためにのみ提供されます。**商用利用は厳禁です。** いかなる個人、機関、団体も、本コンテンツを商業目的、営利活動、違法行為、その他の無許可の用途に使用することはできません。本コンテンツがお客様の法的権利、知的財産権、その他の利益を侵害する場合は、ご連絡いただければ直ちに確認・削除いたします。


**言語**: [English](README.md) | [中文](README_CN.md) | [한국어](README_KR.md) | **日本語**

---

## 目次

- [詳細分析レポート (`docs/`)](#詳細分析レポート-docs) — テレメトリ、コードネーム、アンダーカバーモード、リモート制御、今後のロードマップ
- [ディレクトリ参照](#ディレクトリ参照) — コード構造ツリー
- [アーキテクチャ概要](#アーキテクチャ概要) — エントリポイント → クエリエンジン → ツール/サービス/状態
- [ツールシステムと権限アーキテクチャ](#ツールシステムと権限アーキテクチャ) — 40+ ツール、権限フロー、サブエージェント
- [12の段階的ハーネスメカニズム](#12の段階的ハーネスメカニズム-the-12-progressive-harness-mechanisms) — Claude Code がエージェントループにプロダクション機能を実装する方法

---

## ツールシステムと権限アーキテクチャ

```text
                    ツールインターフェース
                    ==============

    buildTool(definition) ──> Tool<Input, Output, Progress>

    各ツールは以下を実装します:
    ┌────────────────────────────────────────────────────────┐
    │  ライフサイクル (LIFECYCLE)                            │
    │  ├── validateInput()      → 不正な引数を早期に拒否     │
    │  ├── checkPermissions()   → ツール固有の権限チェック   │
    │  └── call()               → 実行して結果を返す         │
    │                                                        │
    │  機能 (CAPABILITIES)                                   │
    │  ├── isEnabled()          → 機能フラグの確認           │
    │  ├── isConcurrencySafe()  → 並列実行可能か？           │
    │  ├── isReadOnly()         → 副作用がないか？           │
    │  ├── isDestructive()      → 元に戻せない操作か？       │
    │  └── interruptBehavior()  → キャンセルまたはユーザー待機？ │
    │                                                        │
    │  レンダリング (RENDERING - React/Ink)                  │
    │  ├── renderToolUseMessage()     → 入力表示             │
    │  ├── renderToolResultMessage()  → 出力表示             │
    │  ├── renderToolUseProgressMessage() → スピナー/状態表示 │
    │  └── renderGroupedToolUse()     → 並列ツールグループ表示 │
    │                                                        │
    │  AI 連携 (AI FACING)                                   │
    │  ├── prompt()             → LLM 向けツール説明         │
    │  ├── description()        → 動的な説明                 │
    │  └── mapToolResultToAPI() → API 応答用フォーマット     │
    └────────────────────────────────────────────────────────┘
```

### 完全なツールインベントリ

```text
    ファイル操作              検索と検出                 実行
    ═════════════════        ══════════════════════     ══════════
    FileReadTool             GlobTool                  BashTool
    FileEditTool             GrepTool                  PowerShellTool
    FileWriteTool            ToolSearchTool
    NotebookEditTool                                   対話
                                                       ═══════════
    Web とネットワーク        エージェント / タスク     AskUserQuestionTool
    ════════════════        ══════════════════        BriefTool
    WebFetchTool             AgentTool
    WebSearchTool            SendMessageTool           計画とワークフロー
                             TeamCreateTool            ════════════════════
    MCP プロトコル           TeamDeleteTool            EnterPlanModeTool
    ══════════════           TaskCreateTool            ExitPlanModeTool
    MCPTool                  TaskGetTool               EnterWorktreeTool
    ListMcpResourcesTool     TaskUpdateTool            ExitWorktreeTool
    ReadMcpResourceTool      TaskListTool              TodoWriteTool
                             TaskStopTool
                             TaskOutputTool            システム
                                                       ════════
                             スキルと拡張機能          ConfigTool
                             ═════════════════════     SkillTool
                             SkillTool                 ScheduleCronTool
                             LSPTool                   SleepTool
                                                       TungstenTool
```

---

## 権限システム

```text
    ツール呼び出しリクエスト
          │
          ▼
    ┌─ validateInput() ──────────────────────────────────┐
    │  権限チェックの前に無効な入力を早期に拒否          │
    └────────────────────┬───────────────────────────────┘
                         │
                         ▼
    ┌─ PreToolUse Hooks (ツール使用前フック) ────────────┐
    │  ユーザー定義のシェルコマンド (settings.json hooks)│
    │  可能な操作: 承認、拒否、または入力の変更          │
    └────────────────────┬───────────────────────────────┘
                         │
                         ▼
    ┌─ Permission Rules (権限ルール) ────────────────────┐
    │  alwaysAllowRules:  ツール名/パターン一致 → 自動承認 │
    │  alwaysDenyRules:   ツール名/パターン一致 → 自動拒否 │
    │  alwaysAskRules:    ツール名/パターン一致 → 常に確認 │
    │  ソース: 設定、CLI 引数、セッション内の決定        │
    └────────────────────┬───────────────────────────────┘
                         │
                    一致するルールなし？
                         │
                         ▼
    ┌─ Interactive Prompt (対話型プロンプト) ────────────┐
    │  ユーザーがツール名 + 入力値を確認                 │
    │  オプション: 1回許可 / 常に許可 / 拒否             │
    └────────────────────┬───────────────────────────────┘
                         │
                         ▼
    ┌─ checkPermissions() ───────────────────────────────┐
    │  ツール固有のロジック (例: パスサンドボックスの確認) │
    └────────────────────┬───────────────────────────────┘
                         │
                    承認済み → tool.call()
```

---

## サブエージェントとマルチエージェントアーキテクチャ

```text
                        メインエージェント
                        ==========
                            │
            ┌───────────────┼───────────────┐
            ▼               ▼               ▼
     ┌──────────────┐ ┌──────────┐ ┌──────────────┐
     │ フォークエージェント │ リモートエージェント │ プロセス内チームメイト│
     │ (FORK)       │ │ (REMOTE)   │ │ (IN-PROCESS)   │
     │ プロセスフォーク │ ブリッジセッション │ 同一プロセス   │
     │ キャッシュ共有 │ 完全隔離   │ 非同期コンテキスト │
     │ 新規 msgs[]  │ │            │ 状態共有         │
     └──────────────┘ └──────────┘ └──────────────┘

    生成モード (SPAWN MODES):
    ├─ default    → プロセス内、会話を共有
    ├─ fork       → 子プロセス、新しい messages[]、ファイルキャッシュを共有
    ├─ worktree   → 隔離された git worktree + fork
    └─ remote     → Claude Code Remote / コンテナへのブリッジ接続

    通信メカニズム (COMMUNICATION):
    ├─ SendMessageTool     → エージェント間のメッセージ伝達
    ├─ TaskCreate/Update   → 共有タスクボード
    └─ TeamCreate/Delete   → チームのライフサイクル管理

    スウォームモード (SWARM MODE、機能フラグで制御):
    ┌─────────────────────────────────────────────┐
    │  リーダーエージェント (Lead Agent)          │
    │    ├── チームメイト A ──> タスク 1 を担当   │
    │    ├── チームメイト B ──> タスク 2 を担当   │
    │    └── チームメイト C ──> タスク 3 を担当   │
    │                                             │
    │  共有: タスクボード、メッセージ受信トレイ   │
    │  隔離: messages[]、ファイルキャッシュ、cwd  │
    └─────────────────────────────────────────────┘
```

---

## コンテキスト管理 (圧縮システム)

```text
    コンテキストウィンドウ予算 (CONTEXT WINDOW BUDGET)
    ══════════════════════════════════════

    ┌─────────────────────────────────────────────────────┐
    │  システムプロンプト (ツール、権限、CLAUDE.md)       │
    │  ══════════════════════════════════════════════      │
    │                                                     │
    │  会話履歴 (Conversation History)                    │
    │  ┌─────────────────────────────────────────────┐    │
    │  │ [過去のメッセージの圧縮要約]                 │    │
    │  │ ═══════════════════════════════════════════  │    │
    │  │ [compact_boundary マーカー]                  │    │
    │  │ ─────────────────────────────────────────── │    │
    │  │ [最近のメッセージ — 元のまま保持]            │    │
    │  │ user → assistant → tool_use → tool_result   │    │
    │  └─────────────────────────────────────────────┘    │
    │                                                     │
    │  現在のターン (ユーザー + アシスタントの応答)       │
    └─────────────────────────────────────────────────────┘

    3つの圧縮戦略:
    ├─ autoCompact     → トークン数がしきい値を超えた時にトリガー
    │                     圧縮 API 呼び出しを通じて過去のメッセージを要約
    ├─ snipCompact     → 不要なメッセージと古いマーカーを削除
    │                     (HISTORY_SNIP 機能フラグ)
    └─ contextCollapse → 効率化のためにコンテキストを再構築
                         (CONTEXT_COLLAPSE 機能フラグ)

    圧縮フロー (COMPACTION FLOW):
    messages[] ──> getMessagesAfterCompactBoundary()
                        │
                        ▼
                  過去のメッセージ ──> Claude API (要約) ──> 圧縮要約
                        │
                        ▼
                  [要約] + [compact_boundary] + [最近のメッセージ]
```

---

## MCP (Model Context Protocol) 統合

```text
    ┌─────────────────────────────────────────────────────────┐
    │                  MCP アーキテクチャ                      │
    │                                                         │
    │  MCPConnectionManager.tsx                               │
    │    ├── サーバー検出 (settings.json の設定に基づく)      │
    │    │     ├── stdio  → 子プロセスを生成                  │
    │    │     ├── sse    → HTTP EventSource                  │
    │    │     ├── http   → ストリーミング HTTP               │
    │    │     ├── ws     → WebSocket                         │
    │    │     └── sdk    → プロセス内転送                    │
    │    │                                                    │
    │    ├── クライアントライフサイクル                       │
    │    │     ├── connect → initialize → list tools          │
    │    │     ├── MCPTool ラッパーを通じたツール呼び出し     │
    │    │     └── バックオフ (backoff) 付きの切断 / 再接続   │
    │    │                                                    │
    │    ├── 認証 (Authentication)                            │
    │    │     ├── OAuth 2.0 フロー (McpOAuthConfig)          │
    │    │     ├── クロスアプリアクセス (XAA / SEP-990)       │
    │    │     └── ヘッダーを通じた API キーの受け渡し        │
    │    │                                                    │
    │    └── ツール登録 (Tool Registration)                   │
    │          ├── mcp__<server>__<tool> 命名規則             │
    │          ├── MCP サーバーからの動的スキーマ (schema) 受信 │
    │          ├── Claude Code への権限パススルー (passthrough) │
    │          └── リソースのリスト化 (ListMcpResourcesTool)  │
    │                                                         │
    └─────────────────────────────────────────────────────────┘
```

---

## ブリッジレイヤー (Claude Desktop / Remote)

```text
    Claude Desktop / Web / Cowork          Claude Code CLI
    ══════════════════════════            ═════════════════

    ┌───────────────────┐                 ┌──────────────────┐
    │  ブリッジクライアント│  ←─ HTTP ──→   │  bridgeMain.ts   │
    │  (Desktop App)    │                 │                  │
    └───────────────────┘                 │  セッション管理者│
                                          │  ├── CLI 生成    │
    プロトコル (PROTOCOL):                │  ├── 状態ポーリング│
    ├─ JWT 認証                           │  ├── メッセージリレー│
    ├─ Work secret 交換                   │  └── 容量ウェイク│
    ├─ セッションライフサイクル           │                  │
    │  ├── create                         │  バックオフ(Backoff):│
    │  ├── run                            │  ├─ 接続: 2s→2m  │
    │  └─ stop                            │  └─ 生成: 500ms→30s│
    └─ トークン更新スケジューラー         └──────────────────┘
```

---

## セッションの永続性 (Session Persistence)

```text
    セッションストレージ (SESSION STORAGE)
    ═════════════════════════════

    ~/.claude/projects/<hash>/sessions/
    └── <session-id>.jsonl           ← 追記専用 (append-only) ログ
        ├── {"type":"user",...}
        ├── {"type":"assistant",...}
        ├── {"type":"progress",...}
        └── {"type":"system","subtype":"compact_boundary",...}

    復元フロー (RESUME FLOW):
    getLastSessionLog() ──> JSONL パース ──> messages[] 再構築
         │
         ├── --continue     → 現在の作業ディレクトリの最後のセッション
         ├── --resume <id>  → 特定のセッション
         └── --fork-session → 新しい ID、履歴をコピー

    永続性戦略 (PERSISTENCE STRATEGY):
    ├─ ユーザーメッセージ → 書き込み待機 (クラッシュ復旧のためのブロッキング)
    ├─ アシスタントメッセージ → 非同期送信 (順序が保持されるキュー)
    ├─ 進行状態     → インライン書き込み (次のクエリ時に重複排除)
    └─ フラッシュ(Flush) → 結果返却時 / cowork の即時フラッシュ
```

---

## 機能フラグシステム (Feature Flag System)

```text
    デッドコードの削除 (Bun コンパイル時)
    ══════════════════════════════

    feature('FLAG_NAME')  ──→  true  → バンドルに含まれる
                           ──→  false → バンドルから削除される

    フラグ一覧 (ソース内で確認):
    ├─ COORDINATOR_MODE      → マルチエージェントコーディネーター
    ├─ HISTORY_SNIP          → 積極的な履歴のトリミング
    ├─ CONTEXT_COLLAPSE      → コンテキストの再構築
    ├─ DAEMON                → バックグラウンドデーモンワーカー
    ├─ AGENT_TRIGGERS        → cron/リモートトリガー
    ├─ AGENT_TRIGGERS_REMOTE → リモートトリガーのサポート
    ├─ MONITOR_TOOL          → MCP モニタリングツール
    ├─ WEB_BROWSER_TOOL      → ブラウザ自動化
    ├─ VOICE_MODE            → 音声入力/出力
    ├─ TEMPLATES             → タスク分類器
    ├─ EXPERIMENTAL_SKILL_SEARCH → スキル探索
    ├─ KAIROS                → プッシュ通知、ファイル送信
    ├─ PROACTIVE             → スリープツール、先行的な行動
    ├─ OVERFLOW_TEST_TOOL    → テストツール
    ├─ TERMINAL_PANEL        → ターミナルキャプチャ
    ├─ WORKFLOW_SCRIPTS      → ワークフローツール
    ├─ CHICAGO_MCP           → コンピューター使用 MCP
    ├─ DUMP_SYSTEM_PROMPT    → プロンプト抽出 (内部専用)
    ├─ UDS_INBOX             → ピア探索
    ├─ ABLATION_BASELINE     → 実験的アブレーション (ablation)
    └─ UPGRADE_NOTICE        → アップグレード通知

    ランタイムゲート (RUNTIME GATES):
    ├─ process.env.USER_TYPE === 'ant'  → 内部機能
    └─ GrowthBook feature flags         → ランタイムの A/B 実験
```

---

## 状態管理 (State Management)

```text
    ┌──────────────────────────────────────────────────────────┐
    │                  AppState Store                           │
    │                                                          │
    │  AppState {                                              │
    │    toolPermissionContext: {                              │
    │      mode: PermissionMode,           ← default/plan など│
    │      additionalWorkingDirectories,                        │
    │      alwaysAllowRules,               ← 自動承認          │
    │      alwaysDenyRules,                ← 自動拒否          │
    │      alwaysAskRules,                 ← 常に確認          │
    │      isBypassPermissionsModeAvailable                    │
    │    },                                                    │
    │    fileHistory: FileHistoryState,    ← 元に戻すスナップショット│
    │    attribution: AttributionState,    ← コミット追跡      │
    │    verbose: boolean,                                     │
    │    mainLoopModel: string,           ← アクティブなモデル │
    │    fastMode: FastModeState,                              │
    │    speculation: SpeculationState                          │
    │  }                                                       │
    │                                                          │
    │  React 統合:                                             │
    │  ├── AppStateProvider   → createContext を通じてストア作成│
    │  ├── useAppState(sel)   → セレクタ (selector) ベースの購読│
    │  └── useSetAppState()   → immer スタイルの更新関数       │
    └──────────────────────────────────────────────────────────┘
```

---

## 12の段階的ハーネスメカニズム (The 12 Progressive Harness Mechanisms)

このアーキテクチャは、基本的なループを超えて、プロダクション AI エージェントのハーネスに必要な 12 の段階的なメカニズムを示しています。各メカニズムは前のものを基盤として構築されます:

```text
    s01  コアループ (THE LOOP)  "一つのループと Bash があれば十分"
         query.ts: Claude API を呼び出す while-true ループ、
         stop_reason を確認し、ツールを実行して結果を追加します。

    s02  ツールディスパッチ (TOOL DISPATCH) "ツールの追加 = ハンドラーの追加"
         Tool.ts + tools.ts: すべてのツールがディスパッチマップに登録されます。
         ループは同一に保たれます。buildTool() ファクトリが安全なデフォルト値を提供します。

    s03  計画 (PLANNING)      "計画のないエージェントは漂流する"
         EnterPlanModeTool/ExitPlanModeTool + TodoWriteTool:
         ステップを先にリストアップしてから実行します。完了率を2倍に高めます。

    s04  サブエージェント (SUB-AGENTS)  "大きなタスクを分割し、サブタスクごとにコンテキストを整理する"
         AgentTool + forkSubagent.ts: 各サブエージェントは新しい messages[] を持ち、
         メインの会話をクリーンに保ちます。

    s05  オンデマンドの知識 (KNOWLEDGE) "必要な時に知識をロードする"
         SkillTool + memdir/: システムプロンプトではなく tool_result を通じて注入します。
         ディレクトリごとに CLAUDE.md ファイルを遅延ロード (lazy load) します。

    s06  コンテキスト圧縮 (COMPRESSION) "コンテキストがいっぱいになったらスペースを確保する"
         services/compact/: 3層の戦略:
         autoCompact (要約) + snipCompact (切り取り) + contextCollapse

    s07  永続的なタスク (TASKS)   "大きな目標 → 小さなタスク → ディスク"
         TaskCreate/Update/Get/List: ファイルベースのタスクグラフ (Task graph) で、
         状態追跡、依存関係、および永続性を持ちます。

    s08  バックグラウンドタスク (BACKGROUND) "バックグラウンドで遅い操作を実行; エージェントは考え続ける"
         DreamTask + LocalShellTask: デーモンスレッドがコマンドを実行し、
         完了時に通知を注入します。

    s09  エージェントチーム (TEAMS)     "一人でやるには大きすぎる → チームメイトに委任する"
         TeamCreate/Delete + InProcessTeammateTask: 
         非同期メールボックスを持つ永続的なチームメイトエージェント。

    s10  チームプロトコル (PROTOCOLS) "共有された通信ルール"
         SendMessageTool: 一つのリクエスト-レスポンスパターンが
         エージェント間のすべての交渉を主導します。

    s11  自律型エージェント (AUTONOMOUS) "チームメイトが自らタスクをスキャンして要求する"
         coordinator/coordinatorMode.ts: アイドルループ (Idle cycle) + 自動割り当て、
         リーダーがすべてのタスクを一つ一つ割り当てる必要はありません。

    s12  ワークツリーの隔離 (WORKTREE) "各自が自分のディレクトリで作業する"
         EnterWorktreeTool/ExitWorktreeTool: タスクは目標を管理し、
         ワークツリーはディレクトリを管理し、ID で結び付けられます。
```

---

## 主要なデザインパターン (Key Design Patterns)

| パターン | 場所 | 目的 |
|---------|-------|---------|
| **AsyncGenerator ストリーミング** | `QueryEngine`, `query()` | API からコンシューマーに至る全チェーンのストリーミング |
| **ビルダー + ファクトリ (Builder + Factory)** | `buildTool()` | ツール定義のための安全なデフォルト値の提供 |
| **ブランドタイプ (Branded Types)** | `SystemPrompt`, `asSystemPrompt()` | 文字列/配列の混同を防止 |
| **機能フラグ + DCE** | `bun:bundle` の `feature()` | コンパイル時のデッドコード削除 (DCE) |
| **判別可能なユニオン (Discriminated Unions)** | `Message` タイプ | 型安全性が保証されるメッセージ処理 |
| **オブザーバー + ステートマシン** | `StreamingToolExecutor` | ツール実行のライフサイクル追跡 |
| **スナップショット状態 (Snapshot State)** | `FileHistoryState` | ファイル操作の元に戻す/やり直し |
| **リングバッファ (Ring Buffer)** | エラーログ | 長いセッションのための制限付きメモリ使用 |
| **撃ちっ放し (Fire-and-Forget)** | `recordTranscript()` | 順序が保持されるノンブロッキングな永続化 |
| **遅延スキーマ (Lazy Schema)** | `lazySchema()` | パフォーマンス向上のための Zod スキーマ遅延評価 |
| **コンテキストの隔離 (Context Isolation)** | `AsyncLocalStorage` | 共有プロセス内の各エージェントごとのコンテキスト |

---

## データフロー: 単一クエリのライフサイクル

```text
 ユーザー入力 (プロンプト / スラッシュコマンド)
     │
     ▼
 processUserInput()                ← /コマンドのパース、UserMessage の作成
     │
     ▼
 fetchSystemPromptParts()          ← ツール → プロンプトセクション、CLAUDE.md メモリ
     │
     ▼
 recordTranscript()                ← ユーザーメッセージをディスクに永続化 (JSONL)
     │
     ▼
 ┌─→ normalizeMessagesForAPI()     ← UI 専用フィールドを削除、必要に応じて圧縮を実行
 │   │
 │   ▼
 │   Claude API (ストリーミング)   ← ツール + システムプロンプトと共に POST /v1/messages
 │   │
 │   ▼
 │   ストリームイベント            ← message_start → content_block_delta → message_stop
 │   │
 │   ├─ テキストブロック ────────→ コンシューマー (SDK / REPL) に伝達
 │   │
 │   └─ tool_use ブロック?
 │       │
 │       ▼
 │   StreamingToolExecutor         ← 分割: 並行処理安全 (concurrent-safe) vs 直列 (serial)
 │       │
 │       ▼
 │   canUseTool()                  ← 権限チェック (フック + ルール + UI プロンプト)
 │       │
 │       ├─ 拒否 ────────────────→ tool_result(error) を追加、ループを継続
 │       │
 │       └─ 許可
 │           │
 │           ▼
 │       tool.call()               ← ツールの実行 (Bash, Read, Edit など)
 │           │
 │           ▼
 │       tool_result 追加          ← messages[] にプッシュ、recordTranscript()
 │           │
 └─────────┘                       ← API 呼び出しにループで戻る
     │
     ▼ (stop_reason != "tool_use")
 結果メッセージの生成              ← 最終テキスト、使用量、コスト、session_id
```

---

## 詳細分析レポート (`docs/`)

インターネット上で公開されている資料やコミュニティの議論をもとに整理した Claude Code v2.1.88 分析レポート。英語/中国語/韓国語/日本語の4言語で提供。

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

> ファイル名をクリックすると該当レポートに移動します。

| # | テーマ | 主要発見 | リンク |
|---|--------|---------|------|
| 01 | **テレメトリとプライバシー** | 二層分析パイプライン（1P、Datadog）。環境フィンガープリント、プロセスメトリクス、全イベントにセッション/ユーザーID。**ユーザー向け無効化設定なし。** `OTEL_LOG_TOOL_DETAILS=1` で全ツール入力記録可能。 | [EN](docs/en/01-telemetry-and-privacy.md) · [日本語](docs/ja/01-テレメトリとプライバシー.md) |
| 02 | **隠し機能とコードネーム** | 動物コードネーム体系（Capybara v8、Tengu、Fennec→Opus 4.6、**Numbat** 次期）。Feature flagにランダム単語ペアで目的を難読化。内部ユーザーは優遇プロンプトと検証エージェントを利用可能。隠しコマンド: `/btw`、`/stickers`。 | [EN](docs/en/02-hidden-features-and-codenames.md) · [日本語](docs/ja/02-隠し機能とコードネーム.md) |
| 03 | **アンダーカバーモード** | 公式社員は公開リポジトリで自動的にアンダーカバーモードに突入。モデルへの指示: **「正体を明かすな」** — 全AI帰属表示を除去し、人間が書いたようにコミット。**強制無効化オプションなし。** | [EN](docs/en/03-undercover-mode.md) · [日本語](docs/ja/03-アンダーカバーモード.md) |
| 04 | **リモート制御とキルスイッチ** | 1時間ごとに `/api/claude_code/settings` をポーリング。危険な変更時にブロッキングダイアログ — **拒否＝アプリ終了**。6以上のキルスイッチ（パーミッションバイパス、Fastモード、音声モード、分析シンク）。GrowthBookで同意なくユーザー動作変更可能。 | [EN](docs/en/04-remote-control-and-killswitches.md) · [日本語](docs/ja/04-リモート制御とキルスイッチ.md) |
| 05 | **今後のロードマップ** | **Numbat** コードネーム確認。Opus 4.7 / Sonnet 4.8開発中。**KAIROS** ＝ 完全自律エージェントモード、`<tick>`ハートビート、プッシュ通知、PR購読。音声モード（push-to-talk）準備完了。未公開ツール17個発見。 | [EN](docs/en/05-future-roadmap.md) · [日本語](docs/ja/05-今後のロードマップ.md) |

---

## 著作権および免責事項

```text
本リポジトリは技術研究および教育目的でのみ提供されます。商用利用は禁止です。

著作権者として本リポジトリのコンテンツがお客様の権利を侵害すると判断される場合は、
リポジトリ所有者にご連絡いただければ直ちに削除いたします。
```

---

## 統計

| 項目 | 数量 |
|------|------|
| ファイル (.ts/.tsx) | 約1,884 |
| 行数 | 約512,664 |
| 最大単一ファイル | `query.ts`（約785KB） |
| 組込ツール | 約40以上 |
| スラッシュコマンド | 約80以上 |
| 依存関係 (node_modules) | 約192パッケージ |
| ランタイム | Bun（Node.js >= 18バンドルにコンパイル） |

---

## エージェントモード

```
                    コアループ
                    ========

    ユーザー --> messages[] --> Claude API --> レスポンス
                                          |
                                stop_reason == "tool_use"?
                               /                          \
                             はい                         いいえ
                              |                             |
                        ツール実行                      テキスト返却
                        tool_result追加
                        ループ再突入 -----------------> messages[]


    これが最小のエージェントループである。Claude Codeはこのループの上に
    プロダクショングレードのハーネスをラップする: 権限、ストリーミング、
    並行性、圧縮、サブエージェント、永続化、MCP。
```

---

## ディレクトリ参照

```
src/
├── main.tsx                 # REPLブートストラップ、4,683行
├── QueryEngine.ts           # SDK/headlessクエリライフサイクルエンジン
├── query.ts                 # メインエージェントループ（785KB、最大ファイル）
├── Tool.ts                  # ツールインターフェース + buildToolファクトリ
├── Task.ts                  # タスクタイプ、ID、状態ベースクラス
├── tools.ts                 # ツール登録、プリセット、フィルタリング
├── commands.ts              # スラッシュコマンド定義
├── context.ts               # ユーザー入力コンテキスト
├── cost-tracker.ts          # APIコスト累積
├── setup.ts                 # 初回実行セットアップフロー
│
├── bridge/                  # Claude Desktop / リモートブリッジ
│   ├── bridgeMain.ts        #   セッションライフサイクルマネージャ
│   ├── bridgeApi.ts         #   HTTPクライアント
│   ├── bridgeConfig.ts      #   接続設定
│   ├── bridgeMessaging.ts   #   メッセージリレー
│   ├── sessionRunner.ts     #   プロセススポーン
│   ├── jwtUtils.ts          #   JWTリフレッシュ
│   ├── workSecret.ts        #   認証トークン
│   └── capacityWake.ts      #   容量ベースウェイク
│
├── cli/                     # CLIインフラ
│   ├── handlers/            #   コマンドハンドラ
│   └── transports/          #   I/Oトランスポート（stdio, structured）
│
├── commands/                # 約80スラッシュコマンド
├── components/              # React/InkターミナルUI
├── entrypoints/             # アプリエントリポイント
├── hooks/                   # React hooks
├── services/                # ビジネスロジック層
├── state/                   # アプリ状態
├── tasks/                   # タスク実装
├── tools/                   # 40以上のツール実装
├── types/                   # 型定義
├── utils/                   # ユーティリティ（最大ディレクトリ）
└── vendor/                  # ネイティブモジュールスタブ
```

---

## アーキテクチャ概要

```
┌─────────────────────────────────────────────────────────────────────┐
│                         エントリ層                                   │
│  cli.tsx ──> main.tsx ──> REPL.tsx（インタラクティブ）               │
│                     └──> QueryEngine.ts（headless/SDK）              │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       クエリエンジン                                  │
│  submitMessage(prompt) ──> AsyncGenerator<SDKMessage>               │
│    ├── fetchSystemPromptParts()    ──> システムプロンプト組立        │
│    ├── processUserInput()          ──> /コマンド処理                 │
│    ├── query()                     ──> メインエージェントループ      │
│    │     ├── StreamingToolExecutor ──> 並列ツール実行               │
│    │     ├── autoCompact()         ──> コンテキスト圧縮             │
│    │     └── runTools()            ──> ツールオーケストレーション    │
│    └── yield SDKMessage            ──> コンシューマにストリーミング  │
└──────────────────────────────┬──────────────────────────────────────┘
```

---

## ライセンス

本リポジトリのコンテンツは技術研究および教育目的でのみ提供されます。知的財産権は元の会社に帰属します。権利侵害がある場合は、削除のためご連絡ください。
