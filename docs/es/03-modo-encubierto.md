# Análisis del Modo Encubierto

> Basado en el análisis del código descompilado de Claude Code v2.1.88.

## ¿Qué es el Modo Encubierto?

El modo encubierto es un sistema de seguridad para empleados de Anthropic que contribuyen a repositorios públicos o de código abierto. Cuando está activo, elimina cualquier atribución de IA y hace que el modelo presente sus contribuciones como si fueran escritas por un desarrollador humano.

Fuente: `src/utils/undercover.ts`

## Lógica de Activación

```typescript
// src/utils/undercover.ts:28-37
export function isUndercover(): boolean {
  if (process.env.USER_TYPE === 'ant') {
    if (isEnvTruthy(process.env.CLAUDE_CODE_UNDERCOVER)) return true;
    // Auto: activo a menos que el repositorio interno lo confirme positivamente
    return getRepoClassCached() !== 'internal';
  }
  return false;
}
```

### Propiedades clave

- **Solo interno**: Solo activo para empleados de Anthropic (`USER_TYPE === 'ant'`).
- **Predeterminado ACTIVADO**: Activo en todos los repositorios excepto los de la lista blanca interna.
- **Sin fuerza‑OFF**: "NO hay fuerza‑OFF. Esto protege contra filtraciones de nombres de código del modelo".
- **Compilación externa**: Eliminado por dead‑code en el empaquetador; nunca se ejecuta.

## Instrucciones que se le dan al modelo

```typescript
// src/utils/undercover.ts:39-69
export function getUndercoverInstructions(): string {
  return `## MODO ENCUBIERTO — CRÍTICO

Estás operando EN MODO ENCUBIERTO en un repositorio PÚBLICO/DE CÓDIGO ABIERTO. Tus mensajes de commit, títulos y cuerpos de PR NO DEBEN contener NINGUNA información interna de Anthropic. No reveles tu cobertura.

NUNCA incluyas en mensajes de commit o descripciones de PR:
- Nombres internos de modelos (nombres de animales como Capybara, Tengu, etc.)
- Números de versión de modelo no lanzados (p. ej., opus-4-7, sonnet-4-8)
- Nombres internos de repositorios o proyectos (p. ej., claude-cli-internal, anthropics/…)
- Herramientas internas, canales de Slack o enlaces cortos (p. ej., go/cc, #claude-code-…)
- La frase "Claude Code" o cualquier mención de que eres una IA
- Cualquier pista del modelo o versión que estás usando
- Líneas "Co‑Authored‑By" u otra atribución

Escribe los mensajes de commit como lo haría un desarrollador humano — describe solo lo que el código cambia.

BUENO:
- "Corrige condición de carrera en la inicialización del observador de archivos"
- "Añade soporte para atajos de teclado personalizados"

MALO (nunca escribas esto):
- "Corrige error encontrado probando con Claude Capybara"
- "1‑shot por claude‑opus‑4‑6"
- "Generado con Claude Code"
- "Co‑Authored‑By: Claude Opus 4.6 <…>"`;
}
```

## Sistema de Atribución

El sistema de atribución (`src/utils/attribution.ts`, `src/utils/commitAttribution.ts`) complementa el modo encubierto:

```typescript
// src/utils/attribution.ts:70-72
// @[MODEL LAUNCH]: Actualiza el nombre de modelo de reserva a continuación
// (evita filtraciones de nombres de código). 
// Para repositorios externos, usa "Claude Opus 4.6" como modelo de reserva.
```

```typescript
// src/utils/model/model.ts:386-392
function maskModelCodename(baseName: string): string {
  // p. ej., capybara‑v2‑fast → cap*****‑v2‑fast
  const [codename = '', ...rest] = baseName.split('-');
  const masked = codename.slice(0, 3) + '*'.repeat(Math.max(0, codename.length - 3));
  return [masked, ...rest].join('-');
}
```

## Implicaciones

### Para Código Abierto

Cuando empleados de Anthropic usan Claude Code para contribuir a proyectos de código abierto:

1. El código es escrito por IA, pero los commits aparecen como si fueran humanos.
2. No hay atribución "Co‑Authored‑By: Claude".
3. No hay marcas "Generado con Claude Code".
4. Los mantenedores y la comunidad no pueden identificar contribuciones generadas por IA.
5. Esto potencialmente viola normas de transparencia en comunidades de código abierto.

### Para la Protección de Anthropic

El propósito principal declarado es prevenir filtraciones accidentales de:

- Nombres internos de modelos (inteligencia competitiva).
- Números de versión no lanzados (cronología del mercado).
- Detalles de infraestructura interna (seguridad).

### Consideraciones Éticas

La frase "No reveles tu cobertura" enmarca a la IA como un agente encubierto. La ocultación intencional de la autoría de IA en contribuciones públicas plantea preguntas sobre:

- Transparencia en comunidades de código abierto.
- Cumplimiento de guías de contribución de proyectos.
- La línea entre protección de secretos comerciales y engaño.
