/**
 * paths — Port over CassiCore's `core/utils/paths.js` (getDataDir / getCassiCoreHome).
 *
 * CassiCore hardcodes `~/.cassicore`. For standalone + plugin use, this port makes the
 * data root injectable while defaulting to the same `~/.cassicore` behavior, so existing
 * stores keep their on-disk layout when the host does not configure a root.
 *
 * Self-contained: depends only on Node builtins. No imports from CassiCore.
 */

import path from 'node:path'
import os from 'node:os'

let _dataDirRoot: string | null = null

/**
 * Resolve the configured home root (override → CASSICORE_HOME → CASSICORE_DATA_DIR → ~/.cassicore).
 */
export function getCassiCoreHome(customRoot?: string): string {
  if (customRoot) return customRoot
  return _dataDirRoot ?? process.env.CASSICORE_HOME
    ?? process.env.CASSICORE_DATA_DIR
    ?? path.join(os.homedir(), '.cassicore')
}

/**
 * Return the CassiCore data directory (`~/.cassicore/data` by default).
 */
export function getDataDir(customRoot?: string): string {
  return path.join(getCassiCoreHome(customRoot), 'data')
}

/**
 * Override the data root at runtime (plugin/host wiring).
 * Pass `undefined`/`null` to reset to the environment/default behavior.
 */
export function setDataDirRoot(root: string | null): void {
  _dataDirRoot = root
}
