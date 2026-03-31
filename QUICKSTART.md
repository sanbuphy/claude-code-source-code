# Quick Start — Building from Source

> **TL;DR**: A full rebuild requires **Bun** (not Node.js) for its compile-time
> intrinsics (`feature()`, `MACRO`, `bun:bundle`). A best-effort build with
> esbuild gets ~95% there but needs manual fixes for ~108 feature-gated modules.

## Option A: Run the pre-built CLI (Recommended)

The npm package already contains a compiled `cli.js`:

```bash
cd /path/to/parent/            # where package.json and cli.js live
node cli.js --version           # → 2.1.88 (Claude Code)
node cli.js -p "Hello Claude"   # Non-interactive mode

# Or install globally:
npm install -g .
claude --version
```

**Authentication required**: Set `ANTHROPIC_API_KEY` or run `node cli.js login`.

## Option B: Build from Source (Best Effort)

### Prerequisites

```bash
node --version   # >= 18
npm --version    # >= 9
```

### Steps

```bash
cd claude-code-2.1.88/

# 1. Install build dependency
npm install --save-dev esbuild

# 2. Run the build script
node scripts/build.mjs

# 3. If successful, run the output:
node dist/cli.js --version
```

### What the Build Script Does

| Phase | Action |
|-------|--------|
| **1. Copy** | `src/` → `build-src/` (original untouched) |
| **2. Transform** | `feature('X')` → `false` (enables dead code elimination) |
| **2b. Transform** | `MACRO.VERSION` → `'2.1.88'` (compile-time version injection) |
| **2c. Transform** | `import from 'bun:bundle'` → stub import |
| **3. Entry** | Create wrapper that injects MACRO globals |
| **4. Bundle** | esbuild with iterative stub creation for missing modules |

### Known Issues

The source code uses **Bun compile-time intrinsics** that cannot be fully replicated with esbuild:

1. **`feature('FLAG')` from `bun:bundle`** — Bun resolves this at compile time to `true`/`false` and eliminates dead branches. Our transform replaces with `false`, but esbuild still resolves `require()` inside those branches.

2. **`MACRO.X`** — Bun's `--define` replaces these at compile time. We use string replacement, which works for most cases but can miss edge cases in complex expressions.

3. **108 missing modules** — These are feature-gated internal modules (daemon, bridge assistant, context collapse, etc.) that don't exist in the published source. They're normally dead-code-eliminated by Bun but esbuild can't eliminate them because the `require()` calls are still syntactically present.

4. **`bun:ffi`** — Used for native proxy support. Stubbed out.

5. **TypeScript `import type` from generated files** — Some generated type files are not in the published source.

### To Fix Remaining Issues

```bash
# 1. Check what's still missing:
npx esbuild build-src/entry.ts --bundle --platform=node \
  --packages=external --external:'bun:*' \
  --log-level=error --log-limit=0 --outfile=/dev/null 2>&1 | \
  grep "Could not resolve" | sort -u

# 2. Create stubs for each missing module in build-src/src/:
#    For JS/TS: create file exporting empty functions
#    For text: create empty file

# 3. Re-run:
node scripts/build.mjs
```

## Option C: Build with Bun (Full Rebuild — Requires Internal Access)

```bash
# Install Bun
curl -fsSL https://bun.sh/install | bash

# The real build uses Bun's bundler with compile-time feature flags:
# bun build src/entrypoints/cli.tsx \
#   --define:feature='(flag) => flag === "SOME_FLAG"' \
#   --define:MACRO.VERSION='"2.1.88"' \
#   --target=bun \
#   --outfile=dist/cli.js

# However, the internal build configuration is not included in the
# published package. You'd need access to Anthropic's internal repo.
```

## Project Structure

```
claude-code-2.1.88/
├── src/                  # Original TypeScript source (1,884 files, 512K LOC)
├── stubs/                # Build stubs for Bun compile-time intrinsics
│   ├── bun-bundle.ts     #   feature() stub → always returns false
│   ├── macros.ts         #   MACRO version constants
│   └── global.d.ts       #   Global type declarations
├── scripts/
│   └── build.mjs         # Build script (esbuild-based)
├── node_modules/         # 192 npm dependencies
├── vendor/               # Native module source stubs
├── build-src/            # Created by build script (transformed copy)
└── dist/                 # Build output (created by build script)
```
