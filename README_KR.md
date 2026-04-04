# Claude Code 아키텍처 학습 및 연구

> **소개**: 이 프로젝트는 CLI Agent 아키텍처에 대한 학습 및 연구 저장소입니다. 모든 자료는 전적으로 인터넷에 공개된 정보와 토론을 바탕으로 정리되었으며, 특히 현재 매우 인기 있는 CLI Agent인 `claude-code`와 관련된 공개 정보를 참고했습니다. 저희의 목적은 개발자들이 Agent 기술을 더 잘 이해하고 활용할 수 있도록 돕는 것입니다. 앞으로도 Agent 아키텍처와 관련된 더 많은 통찰과 실용적인 토론 콘텐츠를 지속적으로 공유할 예정입니다. 여러분의 관심과 성원에 감사드립니다!

> **면책 조항**: 본 저장소의 콘텐츠는 기술 연구, 학습, 교육 목적의 교류를 위해서만 제공됩니다. **상업적 사용은 엄격히 금지됩니다.** 어떠한 개인, 기관, 단체도 이 콘텐츠를 상업적 목적, 영리 활동, 불법 활동 또는 기타 무단 사용에 활용할 수 없습니다. 본 콘텐츠가 귀하의 법적 권리, 지적 재산권 또는 기타 이익을 침해하는 경우, 연락 주시면 즉시 확인 후 삭제 조치하겠습니다.


**언어**: [English](README.md) | [中文](README_CN.md) | **한국어** | [日本語](README_JA.md)

---

## 목차

- [심층 분석 보고서 (`docs/`)](#심층-분석-보고서-docs) — 텔레메트리, 코드네임, 언더커버 모드, 원격 제어, 향후 로드맵
- [디렉터리 참조](#디렉터리-참조) — 코드 구조 트리
- [아키텍처 개요](#아키텍처-개요) — 진입점 → 쿼리 엔진 → 도구/서비스/상태
- [도구 시스템 및 권한 아키텍처](#도구-시스템-및-권한-아키텍처) — 40+ 도구, 권한 흐름, 서브 에이전트
- [12가지 점진적 안전 장치](#12가지-점진적-안전-장치-the-12-progressive-harness-mechanisms) — Claude Code가 에이전트 루프에 프로덕션 기능을 구현하는 방법

---

## 도구 시스템 및 권한 아키텍처

```text
                    도구 인터페이스
                    ==============

    buildTool(definition) ──> Tool<Input, Output, Progress>

    모든 도구는 다음을 구현합니다:
    ┌────────────────────────────────────────────────────────┐
    │  수명주기 (LIFECYCLE)                                  │
    │  ├── validateInput()      → 잘못된 인수 조기 거부      │
    │  ├── checkPermissions()   → 도구별 권한 검사           │
    │  └── call()               → 실행 및 결과 반환          │
    │                                                        │
    │  기능 (CAPABILITIES)                                   │
    │  ├── isEnabled()          → 기능 플래그 확인           │
    │  ├── isConcurrencySafe()  → 병렬 실행 가능 여부?       │
    │  ├── isReadOnly()         → 부작용(side effects) 없음? │
    │  ├── isDestructive()      → 되돌릴 수 없는 작업?       │
    │  └── interruptBehavior()  → 취소 또는 사용자 대기?     │
    │                                                        │
    │  렌더링 (RENDERING - React/Ink)                        │
    │  ├── renderToolUseMessage()     → 입력 표시            │
    │  ├── renderToolResultMessage()  → 출력 표시            │
    │  ├── renderToolUseProgressMessage() → 스피너/상태 표시 │
    │  └── renderGroupedToolUse()     → 병렬 도구 그룹 표시  │
    │                                                        │
    │  AI 연동 (AI FACING)                                   │
    │  ├── prompt()             → LLM용 도구 설명            │
    │  ├── description()        → 동적 설명                  │
    │  └── mapToolResultToAPI() → API 응답용 포맷팅          │
    └────────────────────────────────────────────────────────┘
```

### 전체 도구 인벤토리

```text
    파일 작업                 검색 및 탐색               실행
    ═════════════════        ══════════════════════     ══════════
    FileReadTool             GlobTool                  BashTool
    FileEditTool             GrepTool                  PowerShellTool
    FileWriteTool            ToolSearchTool
    NotebookEditTool                                   상호작용
                                                       ═══════════
    웹 및 네트워크           에이전트 / 작업           AskUserQuestionTool
    ════════════════        ══════════════════        BriefTool
    WebFetchTool             AgentTool
    WebSearchTool            SendMessageTool           계획 및 워크플로우
                             TeamCreateTool            ════════════════════
    MCP 프로토콜             TeamDeleteTool            EnterPlanModeTool
    ══════════════           TaskCreateTool            ExitPlanModeTool
    MCPTool                  TaskGetTool               EnterWorktreeTool
    ListMcpResourcesTool     TaskUpdateTool            ExitWorktreeTool
    ReadMcpResourceTool      TaskListTool              TodoWriteTool
                             TaskStopTool
                             TaskOutputTool            시스템
                                                       ════════
                             스킬 및 확장              ConfigTool
                             ═════════════════════     SkillTool
                             SkillTool                 ScheduleCronTool
                             LSPTool                   SleepTool
                                                       TungstenTool
```

---

## 권한 시스템

```text
    도구 호출 요청
          │
          ▼
    ┌─ validateInput() ──────────────────────────────────┐
    │  권한 검사 전 유효하지 않은 입력 조기 거부         │
    └────────────────────┬───────────────────────────────┘
                         │
                         ▼
    ┌─ PreToolUse Hooks (도구 사용 전 훅) ───────────────┐
    │  사용자 정의 쉘 명령 (settings.json hooks)         │
    │  가능 작업: 승인, 거부 또는 입력 수정              │
    └────────────────────┬───────────────────────────────┘
                         │
                         ▼
    ┌─ Permission Rules (권한 규칙) ─────────────────────┐
    │  alwaysAllowRules:  도구 이름/패턴 일치 → 자동 승인│
    │  alwaysDenyRules:   도구 이름/패턴 일치 → 자동 거부│
    │  alwaysAskRules:    도구 이름/패턴 일치 → 항상 확인│
    │  출처: 설정, CLI 인수, 세션 내 결정                │
    └────────────────────┬───────────────────────────────┘
                         │
                    일치하는 규칙 없음?
                         │
                         ▼
    ┌─ Interactive Prompt (대화형 프롬프트) ─────────────┐
    │  사용자가 도구 이름 + 입력값 확인                  │
    │  옵션: 한 번 허용 / 항상 허용 / 거부               │
    └────────────────────┬───────────────────────────────┘
                         │
                         ▼
    ┌─ checkPermissions() ───────────────────────────────┐
    │  도구별 특수 로직 (예: 경로 샌드박스 검사)         │
    └────────────────────┬───────────────────────────────┘
                         │
                    승인됨 → tool.call()
```

---

## 서브 에이전트 및 다중 에이전트 아키텍처

```text
                        메인 에이전트
                        ==========
                            │
            ┌───────────────┼───────────────┐
            ▼               ▼               ▼
     ┌──────────────┐ ┌──────────┐ ┌──────────────┐
     │ 포크 에이전트│ │ 원격 에이전트│ │ 프로세스 내 동료│
     │ (FORK)       │ │ (REMOTE)   │ │ (IN-PROCESS)   │
     │ 프로세스 포크│ │ 브릿지 세션│ │ 동일 프로세스  │
     │ 캐시 공유    │ │ 완전 격리  │ │ 비동기 컨텍스트│
     │ 새 msgs[]    │ │            │ │ 상태 공유      │
     └──────────────┘ └──────────┘ └──────────────┘

    생성 모드 (SPAWN MODES):
    ├─ default    → 프로세스 내, 대화 공유
    ├─ fork       → 자식 프로세스, 새로운 messages[], 파일 캐시 공유
    ├─ worktree   → 격리된 git worktree + fork
    └─ remote     → Claude Code Remote / 컨테이너로의 브릿지 연결

    통신 메커니즘 (COMMUNICATION):
    ├─ SendMessageTool     → 에이전트 간 메시지 전달
    ├─ TaskCreate/Update   → 공유 작업 보드(task board)
    └─ TeamCreate/Delete   → 팀 수명주기 관리

    스웜 모드 (SWARM MODE, 기능 플래그로 제어됨):
    ┌─────────────────────────────────────────────┐
    │  리더 에이전트 (Lead Agent)                 │
    │    ├── 동료 A ──> 작업 1 할당               │
    │    ├── 동료 B ──> 작업 2 할당               │
    │    └── 동료 C ──> 작업 3 할당               │
    │                                             │
    │  공유: 작업 보드, 메시지 수신함             │
    │  격리: messages[], 파일 캐시, cwd           │
    └─────────────────────────────────────────────┘
```

---

## 컨텍스트 관리 (압축 시스템)

```text
    컨텍스트 창 예산 (CONTEXT WINDOW BUDGET)
    ══════════════════════════════════════

    ┌─────────────────────────────────────────────────────┐
    │  시스템 프롬프트 (도구, 권한, CLAUDE.md)            │
    │  ══════════════════════════════════════════════      │
    │                                                     │
    │  대화 기록 (Conversation History)                   │
    │  ┌─────────────────────────────────────────────┐    │
    │  │ [이전 메시지들의 압축된 요약]                │    │
    │  │ ═══════════════════════════════════════════  │    │
    │  │ [compact_boundary 마커]                      │    │
    │  │ ─────────────────────────────────────────── │    │
    │  │ [최근 메시지 — 원본 그대로 유지]             │    │
    │  │ user → assistant → tool_use → tool_result   │    │
    │  └─────────────────────────────────────────────┘    │
    │                                                     │
    │  현재 턴 (사용자 + 어시스턴트 응답)                 │
    └─────────────────────────────────────────────────────┘

    3가지 압축 전략:
    ├─ autoCompact     → 토큰 수가 임계값을 초과할 때 트리거됨
    │                     압축 API 호출을 통해 이전 메시지 요약
    ├─ snipCompact     → 불필요한 메시지와 오래된 마커 제거
    │                     (HISTORY_SNIP 기능 플래그)
    └─ contextCollapse → 효율성을 위해 컨텍스트 재구성
                         (CONTEXT_COLLAPSE 기능 플래그)

    압축 흐름 (COMPACTION FLOW):
    messages[] ──> getMessagesAfterCompactBoundary()
                        │
                        ▼
                  이전 메시지 ──> Claude API (요약) ──> 압축된 요약
                        │
                        ▼
                  [요약] + [compact_boundary] + [최근 메시지]
```

---

## MCP (Model Context Protocol) 통합

```text
    ┌─────────────────────────────────────────────────────────┐
    │                  MCP 아키텍처                            │
    │                                                         │
    │  MCPConnectionManager.tsx                               │
    │    ├── 서버 검색 (settings.json 구성 기반)              │
    │    │     ├── stdio  → 자식 프로세스 생성                │
    │    │     ├── sse    → HTTP EventSource                  │
    │    │     ├── http   → 스트리밍 HTTP                     │
    │    │     ├── ws     → WebSocket                         │
    │    │     └── sdk    → 프로세스 내 전송                  │
    │    │                                                    │
    │    ├── 클라이언트 수명주기                              │
    │    │     ├── connect → initialize → list tools          │
    │    │     ├── MCPTool 래퍼를 통한 도구 호출              │
    │    │     └── 백오프(backoff)가 포함된 연결 해제 / 재연결│
    │    │                                                    │
    │    ├── 인증 (Authentication)                            │
    │    │     ├── OAuth 2.0 흐름 (McpOAuthConfig)            │
    │    │     ├── 교차 앱 액세스 (XAA / SEP-990)             │
    │    │     └── 헤더를 통한 API 키 전달                    │
    │    │                                                    │
    │    └── 도구 등록 (Tool Registration)                    │
    │          ├── mcp__<server>__<tool> 명명 규칙            │
    │          ├── MCP 서버로부터 동적 스키마(schema) 수신    │
    │          ├── Claude Code로 권한 통과(passthrough)       │
    │          └── 리소스 목록화 (ListMcpResourcesTool)       │
    │                                                         │
    └─────────────────────────────────────────────────────────┘
```

---

## 브릿지 레이어 (Claude Desktop / Remote)

```text
    Claude Desktop / Web / Cowork          Claude Code CLI
    ══════════════════════════            ═════════════════

    ┌───────────────────┐                 ┌──────────────────┐
    │  브릿지 클라이언트│  ←─ HTTP ──→   │  bridgeMain.ts   │
    │  (Desktop App)    │                 │                  │
    └───────────────────┘                 │  세션 관리자     │
                                          │  ├── CLI 스폰    │
    프로토콜 (PROTOCOL):                  │  ├── 상태 폴링   │
    ├─ JWT 인증                           │  ├── 메시지 릴레이│
    ├─ Work secret 교환                   │  └── 용량 웨이크 │
    ├─ 세션 수명주기                      │                  │
    │  ├── create                         │  백오프(Backoff):│
    │  ├── run                            │  ├─ 연결: 2s→2m  │
    │  └─ stop                            │  └─ 생성: 500ms→30s│
    └─ 토큰 새로고침 스케줄러             └──────────────────┘
```

---

## 세션 영속성 (Session Persistence)

```text
    세션 스토리지 (SESSION STORAGE)
    ═════════════════════════════

    ~/.claude/projects/<hash>/sessions/
    └── <session-id>.jsonl           ← 추가 전용(append-only) 로그
        ├── {"type":"user",...}
        ├── {"type":"assistant",...}
        ├── {"type":"progress",...}
        └── {"type":"system","subtype":"compact_boundary",...}

    복구 흐름 (RESUME FLOW):
    getLastSessionLog() ──> JSONL 파싱 ──> messages[] 재구성
         │
         ├── --continue     → 현재 작업 디렉터리의 마지막 세션
         ├── --resume <id>  → 특정 세션
         └── --fork-session → 새 ID, 기록 복사

    영속성 전략 (PERSISTENCE STRATEGY):
    ├─ 사용자 메시지 → 쓰기 대기 (충돌 복구를 위한 블로킹)
    ├─ 어시스턴트 메시지 → 비동기 전송 (순서가 유지되는 큐)
    ├─ 진행 상태     → 인라인 쓰기 (다음 쿼리 시 중복 제거)
    └─ 플러시(Flush) → 결과 반환 시 / cowork 즉시 플러시
```

---

## 기능 플래그 시스템 (Feature Flag System)

```text
    데드 코드 제거 (Bun 컴파일 시점)
    ══════════════════════════════

    feature('FLAG_NAME')  ──→  true  → 번들에 포함됨
                           ──→  false → 번들에서 제거됨

    플래그 목록 (소스에서 관찰됨):
    ├─ COORDINATOR_MODE      → 다중 에이전트 코디네이터
    ├─ HISTORY_SNIP          → 공격적인 기록 다듬기
    ├─ CONTEXT_COLLAPSE      → 컨텍스트 재구성
    ├─ DAEMON                → 백그라운드 데몬 워커
    ├─ AGENT_TRIGGERS        → 크론(cron)/원격 트리거
    ├─ AGENT_TRIGGERS_REMOTE → 원격 트리거 지원
    ├─ MONITOR_TOOL          → MCP 모니터링 도구
    ├─ WEB_BROWSER_TOOL      → 브라우저 자동화
    ├─ VOICE_MODE            → 음성 입력/출력
    ├─ TEMPLATES             → 작업 분류기
    ├─ EXPERIMENTAL_SKILL_SEARCH → 스킬 탐색
    ├─ KAIROS                → 푸시 알림, 파일 전송
    ├─ PROACTIVE             → 수면 도구, 선제적 행동
    ├─ OVERFLOW_TEST_TOOL    → 테스트 도구
    ├─ TERMINAL_PANEL        → 터미널 캡처
    ├─ WORKFLOW_SCRIPTS      → 워크플로우 도구
    ├─ CHICAGO_MCP           → 컴퓨터 사용 MCP
    ├─ DUMP_SYSTEM_PROMPT    → 프롬프트 추출 (내부 전용)
    ├─ UDS_INBOX             → 피어 탐색
    ├─ ABLATION_BASELINE     → 실험 제거(ablation)
    └─ UPGRADE_NOTICE        → 업그레이드 알림

    런타임 게이트 (RUNTIME GATES):
    ├─ process.env.USER_TYPE === 'ant'  → 내부 기능
    └─ GrowthBook feature flags         → 런타임 A/B 실험
```

---

## 상태 관리 (State Management)

```text
    ┌──────────────────────────────────────────────────────────┐
    │                  AppState Store                           │
    │                                                          │
    │  AppState {                                              │
    │    toolPermissionContext: {                              │
    │      mode: PermissionMode,           ← default/plan 등  │
    │      additionalWorkingDirectories,                        │
    │      alwaysAllowRules,               ← 자동 승인         │
    │      alwaysDenyRules,                ← 자동 거부         │
    │      alwaysAskRules,                 ← 항상 확인         │
    │      isBypassPermissionsModeAvailable                    │
    │    },                                                    │
    │    fileHistory: FileHistoryState,    ← 실행 취소 스냅샷  │
    │    attribution: AttributionState,    ← 커밋 추적         │
    │    verbose: boolean,                                     │
    │    mainLoopModel: string,           ← 활성 모델         │
    │    fastMode: FastModeState,                              │
    │    speculation: SpeculationState                          │
    │  }                                                       │
    │                                                          │
    │  React 통합:                                             │
    │  ├── AppStateProvider   → createContext를 통해 스토어 생성│
    │  ├── useAppState(sel)   → 선택자(selector) 기반 구독     │
    │  └── useSetAppState()   → immer 스타일 업데이트 함수     │
    └──────────────────────────────────────────────────────────┘
```

---

## 12가지 점진적 안전 장치 (The 12 Progressive Harness Mechanisms)

이 아키텍처는 기본 루프 외에 프로덕션 AI 에이전트 하니스에 필요한 12계층의 점진적 메커니즘을 보여줍니다. 각 메커니즘은 이전 메커니즘을 기반으로 구축됩니다:

```text
    s01  핵심 루프 (THE LOOP)  "하나의 루프와 Bash면 충분하다"
         query.ts: Claude API를 호출하는 while-true 루프,
         stop_reason을 확인하고, 도구를 실행하며 결과를 추가합니다.

    s02  도구 디스패치 (TOOL DISPATCH) "도구 추가 = 핸들러 하나 추가"
         Tool.ts + tools.ts: 모든 도구가 디스패치 맵에 등록됩니다.
         루프는 동일하게 유지됩니다. buildTool() 팩토리가 안전한 기본값을 제공합니다.

    s03  계획 (PLANNING)      "계획 없는 에이전트는 표류한다"
         EnterPlanModeTool/ExitPlanModeTool + TodoWriteTool:
         단계를 먼저 나열한 다음 실행합니다. 완료율을 두 배로 높입니다.

    s04  서브 에이전트 (SUB-AGENTS)  "큰 작업을 나누고 하위 작업마다 컨텍스트를 정리한다"
         AgentTool + forkSubagent.ts: 각 하위 에이전트는 새로운 messages[]를 가져,
         메인 대화를 깨끗하게 유지합니다.

    s05  온디맨드 지식 (KNOWLEDGE) "필요할 때 지식을 로드한다"
         SkillTool + memdir/: 시스템 프롬프트가 아닌 tool_result를 통해 주입합니다.
         디렉터리별로 CLAUDE.md 파일을 지연 로드(lazy load)합니다.

    s06  컨텍스트 압축 (COMPRESSION) "컨텍스트가 꽉 차면 공간을 확보한다"
         services/compact/: 3계층 전략:
         autoCompact (요약) + snipCompact (자르기) + contextCollapse

    s07  영구 작업 (TASKS)   "큰 목표 → 작은 작업 → 디스크"
         TaskCreate/Update/Get/List: 파일 기반의 작업 그래프(Task graph)로,
         상태 추적, 종속성 및 영속성을 갖습니다.

    s08  백그라운드 작업 (BACKGROUND) "백그라운드에서 느린 작업 실행; 에이전트는 계속 생각한다"
         DreamTask + LocalShellTask: 데몬 스레드가 명령을 실행하고,
         완료 시 알림을 주입합니다.

    s09  에이전트 팀 (TEAMS)     "혼자 하기엔 너무 크다 → 동료에게 위임한다"
         TeamCreate/Delete + InProcessTeammateTask: 
         비동기 메일박스를 가진 영구적인 동료 에이전트들.

    s10  팀 프로토콜 (PROTOCOLS) "공유된 통신 규칙"
         SendMessageTool: 하나의 요청-응답 패턴이
         에이전트 간의 모든 협상을 주도합니다.

    s11  자율 에이전트 (AUTONOMOUS) "동료들이 스스로 작업을 스캔하고 청구한다"
         coordinator/coordinatorMode.ts: 유휴 루프(Idle cycle) + 자동 할당,
         리더가 모든 작업을 일일이 할당할 필요가 없습니다.

    s12  작업 트리 격리 (WORKTREE) "각자 자신의 디렉터리에서 작업한다"
         EnterWorktreeTool/ExitWorktreeTool: 작업은 목표를 관리하고,
         작업 트리는 디렉터리를 관리하며, ID로 연결됩니다.
```

---

## 핵심 디자인 패턴 (Key Design Patterns)

| 패턴 | 위치 | 목적 |
|---------|-------|---------|
| **AsyncGenerator 스트리밍** | `QueryEngine`, `query()` | API에서 소비자로 이어지는 전체 체인 스트리밍 |
| **빌더 + 팩토리 (Builder + Factory)** | `buildTool()` | 도구 정의를 위한 안전한 기본값 제공 |
| **브랜드 타입 (Branded Types)** | `SystemPrompt`, `asSystemPrompt()` | 문자열/배열 혼동 방지 |
| **기능 플래그 + DCE** | `bun:bundle`의 `feature()` | 컴파일 시점 데드 코드 제거(DCE) |
| **구별된 유니온 (Discriminated Unions)** | `Message` 타입 | 타입 안전성이 보장되는 메시지 처리 |
| **옵저버 + 상태 머신** | `StreamingToolExecutor` | 도구 실행 수명주기 추적 |
| **스냅샷 상태 (Snapshot State)** | `FileHistoryState` | 파일 작업의 실행 취소/다시 실행 |
| **링 버퍼 (Ring Buffer)** | 에러 로그 | 긴 세션을 위한 제한된 메모리 사용 |
| **발사 후 망각 (Fire-and-Forget)** | `recordTranscript()` | 순서가 유지되는 논블로킹 영속화 |
| **지연 스키마 (Lazy Schema)** | `lazySchema()` | 성능 향상을 위한 Zod 스키마 지연 평가 |
| **컨텍스트 격리 (Context Isolation)** | `AsyncLocalStorage` | 공유 프로세스 내 각 에이전트별 컨텍스트 |

---

## 데이터 흐름: 단일 쿼리 수명주기

```text
 사용자 입력 (프롬프트 / 슬래시 명령)
     │
     ▼
 processUserInput()                ← /명령어 파싱, UserMessage 생성
     │
     ▼
 fetchSystemPromptParts()          ← 도구 → 프롬프트 섹션, CLAUDE.md 메모리
     │
     ▼
 recordTranscript()                ← 사용자 메시지를 디스크에 영속화 (JSONL)
     │
     ▼
 ┌─→ normalizeMessagesForAPI()     ← UI 전용 필드 제거, 필요시 압축 수행
 │   │
 │   ▼
 │   Claude API (스트리밍)         ← 도구 + 시스템 프롬프트와 함께 POST /v1/messages
 │   │
 │   ▼
 │   스트림 이벤트                 ← message_start → content_block_delta → message_stop
 │   │
 │   ├─ 텍스트 블록 ──────────────→ 소비자(SDK / REPL)에게 전달
 │   │
 │   └─ tool_use 블록?
 │       │
 │       ▼
 │   StreamingToolExecutor         ← 분할: 동시성 안전(concurrent-safe) vs 직렬(serial)
 │       │
 │       ▼
 │   canUseTool()                  ← 권한 검사 (훅 + 규칙 + UI 프롬프트)
 │       │
 │       ├─ 거부 ────────────────→ tool_result(error) 추가, 루프 계속
 │       │
 │       └─ 허용
 │           │
 │           ▼
 │       tool.call()               ← 도구 실행 (Bash, Read, Edit 등)
 │           │
 │           ▼
 │       tool_result 추가          ← messages[]에 푸시, recordTranscript()
 │           │
 └─────────┘                       ← API 호출로 루프 복귀
     │
     ▼ (stop_reason != "tool_use")
 결과 메시지 생성                  ← 최종 텍스트, 사용량, 비용, session_id
```

---

## 심층 분석 보고서 (`docs/`)

인터넷에 공개된 자료와 커뮤니티 토론을 바탕으로 정리된 Claude Code v2.1.88 분석 보고서. 영어/중국어/한국어/일본어 4개 국어 제공.

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

> 파일명을 클릭하면 해당 보고서로 이동합니다.

| # | 주제 | 핵심 발견 | 링크 |
|---|------|----------|------|
| 01 | **텔레메트리 및 프라이버시** | 이중 분석 파이프라인 (1P, Datadog). 환경 핑거프린트, 프로세스 메트릭, 모든 이벤트에 세션/사용자 ID 포함. **사용자 대상 비활성화 설정 없음.** `OTEL_LOG_TOOL_DETAILS=1`로 전체 도구 입력 기록 가능. | [EN](docs/en/01-telemetry-and-privacy.md) · [한국어](docs/ko/01-텔레메트리와-프라이버시.md) · [中文](docs/zh/01-遥测与隐私分析.md) |
| 02 | **숨겨진 기능과 코드네임** | 동물 코드네임 체계 (Capybara v8, Tengu, Fennec→Opus 4.6, **Numbat** 차기). Feature flag에 무작위 단어 조합으로 목적 난독화. 내부 사용자는 더 나은 프롬프트와 검증 에이전트 제공. 숨겨진 명령어: `/btw`, `/stickers`. | [EN](docs/en/02-hidden-features-and-codenames.md) · [한국어](docs/ko/02-숨겨진-기능과-코드네임.md) · [中文](docs/zh/02-隐藏功能与模型代号.md) |
| 03 | **언더커버 모드** | 공식 직원은 공개 저장소에서 자동으로 언더커버 모드 진입. 모델 지시: **"정체를 들키지 마라"** — 모든 AI 저작 표시를 제거하고, 사람이 작성한 것처럼 커밋. **강제 비활성화 옵션 없음.** | [EN](docs/en/03-undercover-mode.md) · [한국어](docs/ko/03-언더커버-모드.md) · [中文](docs/zh/03-卧底模式分析.md) |
| 04 | **원격 제어 및 킬스위치** | 1시간마다 `/api/claude_code/settings` 폴링. 위험 변경 시 차단 다이얼로그 — **거부 = 앱 종료**. 6개 이상 킬스위치 (권한 우회, fast 모드, 음성 모드, 분석 싱크). GrowthBook으로 동의 없이 사용자 동작 변경 가능. | [EN](docs/en/04-remote-control-and-killswitches.md) · [한국어](docs/ko/04-원격-제어와-킬스위치.md) · [中文](docs/zh/04-远程控制与紧急开关.md) |
| 05 | **향후 로드맵** | **Numbat** 코드네임 확인. Opus 4.7 / Sonnet 4.8 개발 중. **KAIROS** = 완전 자율 에이전트 모드, `<tick>` 하트비트, 푸시 알림, PR 구독. 음성 모드(push-to-talk) 준비 완료. 미공개 도구 17개 발견. | [EN](docs/en/05-future-roadmap.md) · [한국어](docs/ko/05-향후-로드맵.md) · [中文](docs/zh/05-未来路线图.md) |

---

## 저작권 및 면책 조항

```text
본 저장소는 기술 연구 및 교육 목적으로만 제공됩니다. 상업적 사용은 금지됩니다.

저작권자로서 본 저장소 콘텐츠가 귀하의 권리를 침해한다고 판단되는 경우,
저장소 소유자에게 연락 주시면 즉시 삭제하겠습니다.
```

---

## 통계

| 항목 | 수량 |
|------|------|
| 파일 (.ts/.tsx) | ~1,884 |
| 라인 수 | ~512,664 |
| 최대 단일 파일 | `query.ts` (~785KB) |
| 내장 도구 | ~40개 이상 |
| 슬래시 명령 | ~80개 이상 |
| 의존성 (node_modules) | ~192개 패키지 |
| 런타임 | Bun (Node.js >= 18 번들로 컴파일) |

---

## 에이전트 모드

```
                    코어 루프
                    ========

    사용자 --> messages[] --> Claude API --> 응답
                                          |
                                stop_reason == "tool_use"?
                               /                          \
                             예                           아니오
                              |                             |
                        도구 실행                        텍스트 반환
                        tool_result 추가
                        루프 재진입 -----------------> messages[]


    이것이 최소 에이전트 루프이다. Claude Code는 이 루프 위에
    프로덕션급 하니스를 래핑한다: 권한, 스트리밍, 동시성,
    압축, 서브에이전트, 영속화 및 MCP.
```

---

## 디렉터리 참조

```
src/
├── main.tsx                 # REPL 부트스트랩, 4,683줄
├── QueryEngine.ts           # SDK/headless 쿼리 라이프사이클 엔진
├── query.ts                 # 메인 에이전트 루프 (785KB, 최대 파일)
├── Tool.ts                  # 도구 인터페이스 + buildTool 팩토리
├── Task.ts                  # 태스크 타입, ID, 상태 베이스 클래스
├── tools.ts                 # 도구 등록, 프리셋, 필터링
├── commands.ts              # 슬래시 명령 정의
├── context.ts               # 사용자 입력 컨텍스트
├── cost-tracker.ts          # API 비용 누적
├── setup.ts                 # 최초 실행 설정 플로우
│
├── bridge/                  # Claude Desktop / 원격 브릿지
│   ├── bridgeMain.ts        #   세션 라이프사이클 매니저
│   ├── bridgeApi.ts         #   HTTP 클라이언트
│   ├── bridgeConfig.ts      #   연결 설정
│   ├── bridgeMessaging.ts   #   메시지 릴레이
│   ├── sessionRunner.ts     #   프로세스 스폰
│   ├── jwtUtils.ts          #   JWT 갱신
│   ├── workSecret.ts        #   인증 토큰
│   └── capacityWake.ts      #   용량 기반 웨이크
│
├── cli/                     # CLI 인프라
│   ├── handlers/            #   명령 핸들러
│   └── transports/          #   I/O 전송 (stdio, structured)
│
├── commands/                # ~80개 슬래시 명령
├── components/              # React/Ink 터미널 UI
├── entrypoints/             # 앱 진입점
├── hooks/                   # React hooks
├── services/                # 비즈니스 로직 레이어
├── state/                   # 앱 상태
├── tasks/                   # 태스크 구현
├── tools/                   # 40개 이상 도구 구현
├── types/                   # 타입 정의
├── utils/                   # 유틸리티 (최대 디렉터리)
└── vendor/                  # 네이티브 모듈 스텁
```

---

## 아키텍처 개요

```
┌─────────────────────────────────────────────────────────────────────┐
│                         진입 레이어                                  │
│  cli.tsx ──> main.tsx ──> REPL.tsx (인터랙티브)                     │
│                     └──> QueryEngine.ts (headless/SDK)              │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       쿼리 엔진                                      │
│  submitMessage(prompt) ──> AsyncGenerator<SDKMessage>               │
│    ├── fetchSystemPromptParts()    ──> 시스템 프롬프트 조립          │
│    ├── processUserInput()          ──> /명령 처리                    │
│    ├── query()                     ──> 메인 에이전트 루프            │
│    │     ├── StreamingToolExecutor ──> 병렬 도구 실행               │
│    │     ├── autoCompact()         ──> 컨텍스트 압축                │
│    │     └── runTools()            ──> 도구 오케스트레이션           │
│    └── yield SDKMessage            ──> 소비자에게 스트리밍           │
└──────────────────────────────┬──────────────────────────────────────┘
```

---

## 라이선스

본 저장소 콘텐츠는 기술 연구 및 교육 목적으로만 제공됩니다. 지적 재산권은 원 회사에 귀속됩니다. 권리 침해가 있는 경우 삭제를 위해 연락 주시기 바랍니다.
