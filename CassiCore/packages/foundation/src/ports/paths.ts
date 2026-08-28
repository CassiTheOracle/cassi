/**
 * paths.ts — Parameterized CassiCore path resolution port.
 *
 * Extracted from `core/utils/paths.ts` in the D: repo into `@cassicore/foundation` as a port.
 * All components MUST use these helpers instead of computing `~/.cassicore/...` themselves.
 * This avoids the old bug where `--no-persist` mutated `process.env.HOME`, silently redirecting
 * every store to a temp directory.
 *
 * The data-dir root is now injectable: a host (or any module) may call `setRootResolver()` to
 * override where CassiCore's data lives. The default resolver preserves the current resolution
 * order exactly:
 *   1. CASSICORE_HOME env var          (explicit override)
 *   2. CASSICORE_DATA_DIR env var      (legacy / test compat)
 *   3. ~/.cassicore                    (default)
 *
 * (The `--no-persist` flag sets CASSICORE_HOME to a temp dir instead of mutating HOME.)
 */

import fs from 'node:fs'
import path from 'node:path'
import os from 'node:os'
import { fileURLToPath } from 'node:url'


/**
 * Injectable resolver for the root of all CassiCore data (e.g. `~/.cassicore`).
 * Default impl is `envRootResolver`, preserving the exact current behavior.
 */
export interface CassiCoreRootResolver {
  /** Root of all CassiCore data, e.g. ~/.cassicore — injectable base dir */
  getCassiCoreHome(): string
}

// Default impl — preserves the current resolution order exactly:
//   1. process.env.CASSICORE_HOME  2. process.env.CASSICORE_DATA_DIR  3. path.join(os.homedir(), '.cassicore')
export const envRootResolver: CassiCoreRootResolver = {
  getCassiCoreHome(): string {
    return (
      process.env.CASSICORE_HOME ||
      process.env.CASSICORE_DATA_DIR ||
      path.join(os.homedir(), '.cassicore')
    )
  },
}

let rootResolver: CassiCoreRootResolver = envRootResolver

/** Override the CassiCore root resolver (host wiring; default is the env-based one). */
export function setRootResolver(r: CassiCoreRootResolver): void {
  rootResolver = r
}

/**
 * Returns the CassiCore home directory (e.g. `~/.cassicore`).
 * This is the root of all CassiCore-specific data.
 */
export function getCassiCoreHome(): string {
  return rootResolver.getCassiCoreHome()
}

/**
 * Returns the CassiCore data directory (e.g. `~/.cassicore/data`).
 * This is where SQLite databases, ledgers, and other data files live.
 */
export function getDataDir(): string {
  return path.join(getCassiCoreHome(), 'data')
}

/**
 * Returns the CassiCore credentials directory (e.g. `~/.cassicore/credentials`).
 */
export function getCredentialsDir(): string {
  return path.join(getCassiCoreHome(), 'credentials')
}

/**
 * Returns the CassiCore artifacts directory (e.g. `~/.cassicore/artifacts`).
 */
export function getArtifactsDir(): string {
  return path.join(getCassiCoreHome(), 'artifacts')
}

/**
 * Returns the CassiCore config file path (e.g. `~/.cassicore/config.json`).
 */
export function getConfigPath(): string {
  return path.join(getCassiCoreHome(), 'config.json')
}

/**
 * Returns the CassiCore PID file path (e.g. `~/.cassicore/daemon.pid`).
 */
export function getPidFilePath(): string {
  return path.join(getCassiCoreHome(), 'daemon.pid')
}

/**
 * Returns the CassiCore admin socket path (e.g. `~/.cassicore/admin.sock`).
 */
export function getAdminSocketPath(): string {
  return path.join(getCassiCoreHome(), 'admin.sock')
}

/**
 * Returns the CassiCore env file path (e.g. `~/.cassicore/.env`).
 */
export function getEnvFilePath(): string {
  return path.join(getCassiCoreHome(), '.env')
}

/**
 * getRepoRoot(): walks up from this file to the dir whose package.json name is
 * 'cassicore' | '@cassicore/core'.
 *
 * NOTE: the original walk-up from core/utils/paths.ts assumed a specific depth
 * (core/utils/ → two levels up). In the port it re-derives from src/ports/
 * (or dist/ports/). Behavior is "closest ancestor package with the cassicore
 * name or, failing that, two levels up" — kept as-is, with the depth-provenance
 * comment updated for the new location.
 */
let _repoRoot: string | null = null
export function getRepoRoot(): string {
  if (_repoRoot) return _repoRoot
  const here = path.dirname(fileURLToPath(import.meta.url))
  // This file lives at src/ports/paths.ts (or dist/ports/paths.js)
  // Walk up to find the directory containing package.json
  let dir = here
  for (let i = 0; i < 5; i++) {
    const parent = path.dirname(dir)
    if (parent === dir) break
    dir = parent
    try {
      const pkgPath = path.join(dir, 'package.json')
      const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf8'))
      if (pkg.name === 'cassicore' || pkg.name === '@cassicore/core') {
        _repoRoot = dir
        return dir
      }
    } catch { /* not the right level */ }
  }
  // Fallback: assume two levels up from src/ports/
  _repoRoot = path.resolve(here, '../..')
  return _repoRoot
}
