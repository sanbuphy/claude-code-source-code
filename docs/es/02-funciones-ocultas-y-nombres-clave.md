# Funciones Ocultas y Nombres Clave de Modelos

> Basado en el análisis del código descompilado de Claude Code v2.1.88.

## Sistema de Nombres Clave de Modelos

Anthropic utiliza **nombres de animales** como códigos internos para sus modelos. Estos nombres están fuertemente protegidos para evitar filtraciones en versiones externas.

### Nombres Clave Conocidos

| Código | Rol | Evidencia |
|--------|-----|-----------|
| **Tengu** (天狗) | Prefijo de productos/telemetría, posiblemente un modelo | Usado como prefijo `tengu_*` para más de 250 eventos de analítica y banderas de características |
| **Capybara** | Modelo de la serie Sonnet, actualmente en la versión v8 | `capybara-v2-fast[1m]`, parches de prompts para problemas de comportamiento en v8 |
| **Fennec** (耳廓狐) | Predecesor de Opus 4.6 | Migración: `fennec-latest` → `opus` |
| **Numbat** (袋食蚁兽) | Próximo modelo en lanzamiento | Comentario: "Remove this section when we launch numbat" |

### Protección de Nombres Clave

El modo **undercover** lista explícitamente los nombres protegidos:

```typescript
// src/utils/undercover.ts:48-49
NEVER include in commit messages or PR descriptions:
- Internal model codenames (animal names like Capybara, Tengu, etc.)
- Unreleased model version numbers (e.g., opus-4-7, sonnet-4-8)
```

El sistema de compilación usa `scripts/excluded-strings.txt` para escanear posibles filtraciones. Algunas especies están codificadas mediante `String.fromCharCode()` para evitar activar la detección:

```typescript
// src/buddy/types.ts:10-13
// One species name collides with a model-codename canary in excluded-strings.txt.
// The check greps build output (not source), so runtime-constructing the value keeps
// the literal out of the bundle while the check stays armed for the actual codename.
```

La especie que colisiona es **capybara** — tanto una mascota como un nombre clave de modelo.

### Problemas de Comportamiento de Capybara (v8)

1. **Falsa activación de secuencia de parada** (~10% de ocurrencia cuando `<functions>` está al final del prompt)
2. **Resultado de herramienta vacío genera salida nula**
3. **Sobre‑comentado** — requiere parches anti‑comentario dedicados
4. **Alta tasa de falsos reclamos**: v8 tiene una tasa del 29‑30% vs 16.7% en v4
5. **Verificación insuficiente** — necesita un "contrapeso de exhaustividad"

## Convención de Nombres de Banderas de Funcionalidad

Todas las banderas de características usan el prefijo `tengu_` seguido de pares de palabras aleatorias para ocultar su propósito:

| Bandera | Propósito |
|--------|-----------|
| `tengu_onyx_plover` | Auto Dream (consolidación de memoria en segundo plano) |
| `tengu_coral_fern` | Funcionalidad de hoja de ruta (`memdir`) |
| `tengu_moth_copse` | Otro interruptor de hoja de ruta |
| `tengu_herring_clock` | Memoria de equipo |
| `tengu_passport_quail` | Funcionalidad de ruta |
| `tengu_slate_thimble` | Otro interruptor de hoja de ruta |
| `tengu_sedge_lantern` | Resumen de ausencia (`Away Summary`) |
| `tengu_frond_boric` | Desactivación de analítica |
| `tengu_amber_quartz_disabled` | Desactivación de modo de voz |
| `tengu_amber_flint` | Equipos de agentes |
| `tengu_hive_evidence` | Agente de verificación |

El patrón aleatorio (adjetivo/material + naturaleza/objeto) impide que observadores externos infieran el propósito de la bandera solo con su nombre.

## Diferencias Internas vs Externas para el Usuario

Los empleados de Anthropic (`USER_TYPE === 'ant'`) reciben un trato significativamente mejor:

| Dimensión | Usuarios Externos | Internos (ant) |
|-----------|-------------------|----------------|
| Estilo de salida | "Ser extra conciso" | "Errar por ofrecer más explicación" |
| Mitigación de falsos reclamos | Ninguna | Parches dedicados para Capybara v8 |
| Anclajes de longitud numérica | Ninguno | "≤25 palabras entre herramientas, ≤100 palabras final" |
| Agente de verificación | Ninguno | Requerido para cambios no triviales |
| Guía de comentarios | Genérica | Prompt anti‑sobre‑comentario dedicado |
| Corrección proactiva | Ninguna | "Si el usuario tiene una idea equivocada, dilo" |

## Acceso a Herramientas Internas

Los usuarios internos disponen de herramientas no disponibles externamente:

- `REPLTool` — modo REPL
- `SuggestBackgroundPRTool` — sugerencias de PR en segundo plano
- `TungstenTool` — panel de monitoreo de rendimiento
- `VerifyPlanExecutionTool` — verificación de ejecución de planes
- Anidamiento de agentes (agentes que generan agentes)

## Comandos Ocultos

| Comando | Estado | Descripción |
|---------|--------|-------------|
| `/btw` | Activo | Hacer preguntas laterales sin interrumpir |
| `/stickers` | Activo | Ordenar stickers de Claude Code (abre navegador) |
| `/thinkback` | Activo | Reseña del año 2025 |
| `/effort` | Activo | Configurar nivel de esfuerzo del modelo |
| `/good-claude` | Stub | Marcador oculto |
| `/bughunter` | Stub | Marcador oculto |
