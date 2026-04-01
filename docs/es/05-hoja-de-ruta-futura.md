# Hoja de Ruta Futura — Lo que Revela el Código Fuente

> Basado en el análisis del código descompilado de Claude Code v2.1.88.

## 1. Próximo Modelo: Numbat

La evidencia más concreta del próximo lanzamiento de modelo:

```typescript
// src/constants/prompts.ts:402
// @[MODEL LAUNCH]: Remove this section when we launch numbat.
```

**Numbat** (袋食蚁兽) es el nombre en clave de un modelo próximo. El comentario indica que la sección de eficiencia de salida se revisará cuando Numbat se lance, sugiriendo un mejor control de salida nativa.

### Números de Versión Futuras

```typescript
// src/utils/undercover.ts:49
- Unreleased model version numbers (e.g., opus-4-7, sonnet-4-8)
```

**Opus 4.7** y **Sonnet 4.8** están en desarrollo.

### Cadena de Evolución de Nombres en Clave

```
Fennec (耳廓狐) → Opus 4.6 → [Numbat?]
Capybara (水豚) → Sonnet v8 → [?]
Tengu (天狗) → prefijo telemetry/product
```

La migración de Fennec a Opus está documentada:

```typescript
// src/migrations/migrateFennecToOpus.ts:7-11
// fennec-latest → opus
// fennec-latest[1m] → opus[1m]
// fennec-fast-latest → opus[1m] + fast mode
```

### Checklist "MODEL LAUNCH"

El código contiene más de 20 marcadores `@[MODEL LAUNCH]` que enumeran todo lo que debe actualizarse:

- Nombres de modelo predeterminados (`FRONTIER_MODEL_NAME`)
- IDs de familia de modelo
- Fechas de corte de conocimiento
- Tablas de precios
- Configuraciones de ventana de contexto
- Flags de soporte de modo de pensamiento
- Mapeos de nombres para la UI
- Scripts de migración

## 2. KAIROS — Modo Agente Autónomo

La mayor característica no lanzada, KAIROS transforma Claude Code de un asistente reactivo a un agente autónomo proactivo.

### Prompt del Sistema (extractos)

```typescript
// src/constants/prompts.ts:860-913

You are running autonomously.
You will receive <tick> prompts that keep you alive between turns.
If you have nothing useful to do, call SleepTool.
Bias toward action — read files, make changes, commit without asking.

## Terminal focus
- Unfocused: The user is away. Lean heavily into autonomous action.
- Focused: The user is watching. Be more collaborative.
```

### Herramientas Asociadas

| Tool               | Feature Flag                | Purpose                                   |
|--------------------|----------------------------|-------------------------------------------|
| SleepTool          | KAIROS / PROACTIVE         | Controlar el ritmo entre acciones autónomas |
| SendUserFileTool   | KAIROS                     | Enviar archivos proactivamente al usuario |
| PushNotificationTool | KAIROS / KAIROS_PUSH_NOTIFICATION | Enviar notificaciones push a dispositivos del usuario |
| SubscribePRTool    | KAIROS_GITHUB_WEBHOOKS     | Suscribirse a eventos de PR en GitHub |
| BriefTool          | KAIROS_BRIEF               | Actualizaciones de estado proactivas |

### Comportamiento

- Operan sobre prompts de latido `<tick>`
- Ajustan la autonomía según el foco del terminal
- Pueden hacer commits, push y decisiones de forma independiente
- Envían notificaciones y actualizaciones de estado proactivas
- Monitorean PRs de GitHub para cambios

## 3. Modo de Voz

La entrada de voz push‑to‑talk está totalmente implementada pero protegida por el flag `VOICE_MODE`.

```typescript
// src/voice/voiceModeEnabled.ts
// Conecta al endpoint WebSocket voice_stream de Anthropic
// Usa modelos respaldados por conversation_engine para speech‑to‑text
// Hold‑to‑talk: mantener la tecla para grabar, soltar para enviar
```

- Solo OAuth (no API key, Bedrock o Vertex)
- Usa mTLS para conexiones WebSocket
- Killswitch: `tengu_amber_quartz_disabled`

## 4. Herramientas No Lanzadas

Herramientas encontradas en el código pero aún no habilitadas para usuarios externos:

| Tool                | Feature Flag               | Description                                 |
|---------------------|----------------------------|---------------------------------------------|
| **WebBrowserTool**  | `WEB_BROWSER_TOOL`         | Automatización de navegador integrada (código en clave: bagel) |
| **TerminalCaptureTool** | `TERMINAL_PANEL`      | Captura y monitorización del panel de terminal |
| **WorkflowTool**    | `WORKFLOW_SCRIPTS`         | Ejecutar scripts de flujo de trabajo predefinidos |
| **MonitorTool**     | `MONITOR_TOOL`             | Monitorización del sistema y procesos |
| **SnipTool**        | `HISTORY_SNIP`             | Recorte y truncado del historial de conversación |
| **ListPeersTool**   | `UDS_INBOX`                | Descubrimiento de pares mediante sockets Unix |
| **RemoteTriggerTool** | `AGENT_TRIGGERS_REMOTE` | Activación remota de agentes |
| **TungstenTool**    | ant‑only                   | Panel interno de monitoreo de rendimiento |
| **VerifyPlanExecutionTool** | `VERIFY_PLAN` env | Verificación de ejecución de planes |
| **OverflowTestTool** | `OVERFLOW_TEST_TOOL`      | Pruebas de desbordamiento de contexto |
| **SubscribePRTool** | `KAIROS_GITHUB_WEBHOOKS`  | Suscripciones a webhooks de PR en GitHub |

## 5. Modo Coordinador

Sistema de coordinación multi‑agente:

```typescript
// src/coordinator/coordinatorMode.ts
// Feature flag: COORDINATOR_MODE
```

Permite la ejecución de tareas coordinadas entre varios agentes con estado compartido y mensajería.

## 6. Sistema Buddy (Mascotas Virtuales)

El sistema completo de compañeros virtuales está implementado pero aún no lanzado:

- **18 especies**: pato, ganso, blob, gato, dragón, pulpo, búho, pingüino, tortuga, caracol, fantasma, ajolote, capibara, cactus, robot, conejo, hongo, chonk
- **5 niveles de rareza**: Común (60 %), Poco común (25 %), Raro (10 %), Épico (4 %), Legendario (1 %)
- **7 sombreros**: corona, sombrero de copa, hélice, halo, mago, beanie, tinyduck
- **5 estadísticas**: DEBUGGING, PATIENCE, CHAOS, WISDOM, SNARK
- **1 % de probabilidad de brillo**: variante Sparkle de cualquier especie
- **Generación determinista**: basada en el hash del ID de usuario

Fuente: `src/buddy/`

## 7. Tarea Dream

Sub‑agente de consolidación de memoria en segundo plano:

```typescript
// src/tasks/DreamTask/
// Funcionalidad auto‑dream que trabaja en segundo plano
// Controlada por la bandera de feature 'tengu_onyx_plover'
```

Permite que la IA procese y consolide memorias de forma autónoma durante periodos de inactividad.

## Resumen: Las Tres Direcciones

1. **Nuevos Modelos**: Numbat (próximo), Opus 4.7, Sonnet 4.8 en desarrollo
2. **Agente Autónomo**: Modo KAIROS — operación sin supervisión, acciones proactivas, notificaciones push
3. **Multimodal**: Entrada de voz lista, herramienta de navegador esperando, automatización de flujos de trabajo en camino

Claude Code está evolucionando de un **asistente de codificación** a un **agente de desarrollo autónomo siempre activo**.
