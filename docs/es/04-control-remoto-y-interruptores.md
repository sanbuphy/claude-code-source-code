# Control Remoto y Killswitches

> Basado en el análisis del código descompilado de Claude Code v2.1.88.

## Visión General

Claude Code implementa múltiples mecanismos de control remoto que permiten a Anthropic (y a administradores empresariales) modificar el comportamiento sin el consentimiento explícito del usuario.

## 1. Configuraciones Administradas Remotamente

### Arquitectura

Cada sesión elegible obtiene configuraciones de:

```typescript
GET /api/claude_code/settings
```

Fuente: `src/services/remoteManagedSettings/index.ts:105-107`

### Comportamiento de Sondeo

```typescript
const SETTINGS_TIMEOUT_MS = 10000;
const DEFAULT_MAX_RETRIES = 5;
const POLLING_INTERVAL_MS = 60 * 60 * 1000; // 1 hora
```

Las configuraciones se consultan cada hora, con hasta 5 reintentos ante fallos.

### Elegibilidad

- Usuarios de consola (API key): todos elegibles
- Usuarios OAuth: solo suscriptores Enterprise/C4E y Team

### Diálogo de Aceptar o Morir

Cuando las configuraciones remotas contienen cambios "peligrosos", se muestra un diálogo bloqueante:

```typescript
export function handleSecurityCheckResult(result: SecurityCheckResult): boolean {
  if (result === 'rejected') {
    gracefulShutdownSync(1);  // Salir con código 1
    return false;
  }
  return true;
}
```

Los usuarios que rechazan las configuraciones remotas hacen que la aplicación **se termine forzosamente**. Las únicas opciones son: aceptar la configuración remota o Claude Code se cierra.

### Degradación Elegante

Si el servidor remoto no está disponible, se usan configuraciones en caché del disco:

```typescript
if (cachedSettings) {
  logForDebugging('Remote settings: Using stale cache after fetch failure');
  setSessionCache(cachedSettings);
  return cachedSettings;
}
```

Una vez aplicadas, persisten incluso cuando el servidor está caído.

## 2. Killswitches de Banderas de Funcionalidad

Varias funcionalidades pueden desactivarse remotamente mediante banderas de GrowthBook:

### Killswitch de Permisos de Bypass

```typescript
// src/utils/permissions/bypassPermissionsKillswitch.ts
// Verifica una puerta de Statsig para desactivar permisos de bypass
```

### Circuit Breaker del Modo Automático

```typescript
// src/utils/permissions/autoModeState.ts
// Estado autoModeCircuitBroken previene re‑entrada al modo automático
```

### Killswitch de Modo Rápido

```typescript
// src/utils/fastMode.ts
// Obtiene de /api/claude_code_penguin_mode
// Puede desactivar permanentemente el modo rápido para un usuario
```

### Killswitch del Sink de Analítica

```typescript
const SINK_KILLSWITCH_CONFIG_NAME = 'tengu_frond_boric';
```

Puede detener toda la salida de analítica de forma remota.

### Killswitch de Equipos de Agentes

```typescript
// src/utils/agentSwarmsEnabled.ts
// Requiere variable de entorno y la puerta de GrowthBook 'tengu_amber_flint'
```

### Killswitch de Modo de Voz

```typescript
// src/voice/voiceModeEnabled.ts:21
// 'tengu_amber_quartz_disabled' — apagado de emergencia para modo de voz
```

## 3. Sistema de Sobrescritura de Modelo

Anthropic puede sobrescribir remotamente qué modelo usan los empleados internos:

```typescript
// src/utils/model/antModels.ts:32-33
// @[MODEL LAUNCH]: Actualiza tengu_ant_model_override con nuevos modelos solo para ant
```

El flag `tengu_ant_model_override` puede:

- Establecer modelo predeterminado
- Establecer nivel de esfuerzo predeterminado
- Añadir al prompt del sistema
- Definir alias de modelo personalizados

## 4. Modo Pingüino

El estado del modo rápido se obtiene de un endpoint dedicado:

```typescript
// src/utils/fastMode.ts
// GET /api/claude_code_penguin_mode
// Si la API indica desactivado, se desactiva permanentemente para el usuario
```

Bandera de feature `tengu_penguins_off` y `tengu_marble_sandcastle` controlan la disponibilidad.

## Resumen

| Mecanismo | Alcance | Consentimiento del Usuario |
|-----------|---------|----------------------------|
| Configuraciones administradas | Enterprise/Team | Aceptar o salir |
| Banderas de GrowthBook | Todos los usuarios | Ninguno |
| Killswitches | Todos los usuarios | Ninguno |
| Sobrescritura de modelo | Interno (ant) | Ninguno |
| Control de modo rápido | Todos los usuarios | Ninguno |

La infraestructura de control remoto es extensa y opera mayormente sin visibilidad ni consentimiento del usuario. Los administradores empresariales pueden imponer políticas que los usuarios no pueden anular, y Anthropic puede cambiar remotamente el comportamiento para cualquier usuario mediante banderas de características.
