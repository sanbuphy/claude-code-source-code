# Análisis de Telemetría y Privacidad

> Basado en el análisis del código descompilado de Claude Code v2.1.88.

## Visión General

Claude Code implementa una canalización de analítica de dos niveles que recopila una gran cantidad de metadatos del entorno y del uso. Aunque no hay evidencia de registro de pulsaciones de teclas o exfiltración de código fuente, la amplitud de la recolección y la imposibilidad de desactivarla completamente generan preocupaciones legítimas de privacidad.

## Arquitectura de la Canalización de Datos

### Registro de Primera Parte (1P)

- **Endpoint**: `https://api.anthropic.com/api/event_logging/batch`
- **Protocolo**: OpenTelemetry con Protocol Buffers
- **Tamaño del lote**: Hasta 200 eventos por lote, enviados cada 10 segundos
- **Reintentos**: Retroceso cuadrático, hasta 8 intentos, persistidos en disco para mayor durabilidad
- **Almacenamiento**: Eventos fallidos guardados en `~/.claude/telemetry/`

Fuente: `src/services/analytics/firstPartyEventLoggingExporter.ts`

### Registro de Terceros (Datadog)

- **Endpoint**: `https://http-intake.logs.us5.datadoghq.com/api/v2/logs`
- **Alcance**: Limitado a 64 tipos de eventos preaprobados
- **Token**: `pubbbf48e6d78dae54bceaa4acf463299bf`

Fuente: `src/services/analytics/datadog.ts`

## Qué Se Recopila

### Huella del Entorno

Cada evento lleva estos metadatos (`src/services/analytics/metadata.ts:417-452`):

```
- plataforma, plataforma cruda, arquitectura, versión de node
- tipo de terminal
- gestores de paquetes e intérpretes instalados
- detección de CI/CD, metadatos de GitHub Actions
- versión de WSL, distribución de Linux, versión del kernel
- tipo de VCS (sistema de control de versiones)
- versión y tiempo de compilación de Claude Code
- entorno de despliegue
```

### Métricas del Proceso (`metadata.ts:457-467`)

```
- tiempo de actividad, rss, heapTotal, heapUsed
- uso de CPU y porcentaje
- arreglos de memoria y asignaciones externas
```

### Seguimiento de Usuario (`metadata.ts:472-496`)

```
- modelo en uso
- ID de sesión, ID de usuario, ID de dispositivo
- UUID de cuenta, UUID de organización
- nivel de suscripción (max, pro, enterprise, team)
- hash de la URL remota del repositorio (SHA256, primeros 16 caracteres)
- tipo de agente, nombre del equipo, ID de sesión padre
```

### Registro de Entradas de Herramientas

Las entradas de herramientas se truncan por defecto:

```
- Cadenas: truncadas a 512 caracteres, mostradas como 128 + elipsis
- JSON: limitado a 4 096 caracteres
- Arreglos: máximo 20 ítems
- Objetos anidados: máximo 2 niveles de profundidad
```

Fuente: `metadata.ts:236-241`

Sin embargo, cuando se establece `OTEL_LOG_TOOL_DETAILS=1`, **se registran las entradas completas de las herramientas**.

Fuente: `metadata.ts:86-88`

### Seguimiento de Extensiones de Archivo

Los comandos Bash que involucran `rm, mv, cp, touch, mkdir, chmod, chown, cat, head, tail, sort, stat, diff, wc, grep, rg, sed` extraen y registran las extensiones de los argumentos de archivo.

Fuente: `metadata.ts:340-412`

## El Problema de la Desactivación

La canalización de registro de primera parte **no puede desactivarse** para usuarios directos de la API de Anthropic.

```typescript
// src/services/analytics/firstPartyEventLogger.ts:141-144
export function is1PEventLoggingEnabled(): boolean {
  return !isAnalyticsDisabled()
}
```

`isAnalyticsDisabled()` solo devuelve true para:
- Entornos de prueba
- Proveedores de nube de terceros (Bedrock, Vertex)
- Desactivación global de telemetría (no expuesta en la UI de configuración)

No existe **ninguna configuración visible para el usuario** que desactive el registro de eventos de primera parte.

## Pruebas A/B de GrowthBook

Los usuarios se asignan a grupos de experimento mediante GrowthBook sin consentimiento explícito. El sistema envía atributos de usuario que incluyen:

```
- id, sessionId, deviceID
- plataforma, organizationUUID, subscriptionType
```

Fuente: `src/services/analytics/growthbook.ts`

## Principales Conclusiones

1. **Volumen**: Se recogen cientos de eventos por sesión.
2. **Sin opción de exclusión**: Los usuarios de la API directa no pueden desactivar el registro de primera parte.
3. **Persistencia**: Los eventos fallidos se guardan en disco y se reintentan de forma agresiva.
4. **Compartición con terceros**: Los datos se envían a Datadog.
5. **Puerta trasera de detalle de herramientas**: `OTEL_LOG_TOOL_DETAILS=1` habilita el registro completo de entradas.
6. **Huella del repositorio**: Las URLs de los repositorios se hash y se envían para correlación en el servidor.
