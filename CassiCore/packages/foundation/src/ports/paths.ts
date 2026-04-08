/**
 * paths.ts — Centralized path resolution for CassiCore.
 *
 * All components MUST use these helpers instead of computing
 * `~/.cassicore/...` themselves. This avoids the old bug where
 * `--no-persist` mutated `process.env.HOME`, silently redirecting
 * every store to a temp directory.
 *
 * Resolution order for the CassiCore home directory:
 *   1. CASSICORE_HOME env var          (explicit override)
 *   2. CASSICORE_DATA_DIR env var      (legacy / test compat)
 *   3. ~/.cassicore                    (default)
 *
 * The `--no-persist` flag now sets CASSICORE_HOME to a temp dir
 * instead of mutating HOME.
 */

import fs from 'node:fs'
import path from 'node:path'
import os from 'node:os'
import { fileURLToPath } from 'node:url'


/**
 * Returns the CassiCore home directory (e.g. `~/.cassicore`).
 * This is the root of all CassiCore-specific data.
 */
export function getCassiCoreHome(): string {
  return (
    process.env.CASSICORE_HOME ||
    process.env.CASSICORE_DATA_DIR ||
    path.join(os.homedir(), '.cassicore')
  )
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
 * Returns the CassiCore repository root (the directory containing package.json).
 * Derived from this file's location: core/utils/paths.ts → repo root is two levels up.
 */
let _repoRoot: string | null = null
export function getRepoRoot(): string {
  if (_repoRoot) return _repoRoot
  const here = path.dirname(fileURLToPath(import.meta.url))
  // This file lives at core/utils/paths.ts (or dist/core/utils/paths.js)
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
  // Fallback: assume two levels up from core/utils/
  _repoRoot = path.resolve(here, '../..')
  return _repoRoot
}
