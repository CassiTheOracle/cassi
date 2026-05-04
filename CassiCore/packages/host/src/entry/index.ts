/**
 * index.ts — CassiCore entry point.
 *
 * Determines the run mode and dispatches accordingly:
 *
 *   Default (no flags)        → Supervisor mode: spawn daemon-main as a child
 *                               process with IPC heartbeat monitoring.
 *   --start-stop              → One-shot mode: run daemon-main directly in
 *                               this process (start → ready → stop).
 *   --agent-mode / --run-once → Direct mode: run daemon-main in-process for
 *                               ephemeral agent workloads.
 *
 * The old --stay-up, --no-exit, --foreground, --daemon flags are removed.
 * The daemon now stays up by default.
 */

process.title = 'cassi:super'

import { Supervisor } from './supervisor.js'
import { rootLogger } from '../logger.js'

const logger = rootLogger.child('super')

// Simple argv helpers
const argv = process.argv.slice(2)
function hasFlag(name: string) { return argv.includes(name) }

// Modes that require running the daemon in-process (no supervisor)
const directMode =
  hasFlag('--start-stop') ||
  hasFlag('--agent-mode') ||
  hasFlag('--ephemeral') ||
  hasFlag('--run-once') ||
  hasFlag('--no-persist') ||
  hasFlag('--exit-after-startup') ||
  !!argv.find(a => a.startsWith('--agent-request-file') || a.startsWith('--agent-request'))

if (directMode) {
  // Direct mode: import and run daemon-main in this process.
  // We do a dynamic import so the supervisor code path doesn't pay
  // for loading the full daemon when it just needs to fork().
  await import('./daemon-main.js')
} else {
  // Supervisor mode: fork daemon-main as a child process with
  // IPC heartbeat monitoring and automatic restart.
  const supervisor = new Supervisor()

  const shutdown = async (signal: string) => {
    await supervisor.stop(signal)
  }

  process.on('SIGTERM', () => void shutdown('SIGTERM'))
  process.on('SIGINT', () => void shutdown('SIGINT'))

  try {
    await supervisor.start()
  } catch (err) {
    logger.error('Supervisor fatal error', { error: String(err) })
    process.exit(1)
  }
}
