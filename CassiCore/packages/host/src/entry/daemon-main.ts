/**
 * daemon-main.ts — Actual daemon process entry point.
 *
 * When running under the supervisor (normal mode), this is fork()'d as a
 * child process.  The supervisor sends heartbeat pings over IPC; we reply
 * with pongs that include basic health metrics.
 *
 * When running standalone (--start-stop, or directly via `cassicore run`),
 * this is loaded directly without a supervisor.
 */

process.title = 'cassi:daemon'

import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

import { Daemon } from '../daemon.js'
import { rootLogger } from '../logger.js'

const logger = rootLogger.child('daemon-main')

const argv = process.argv.slice(2)
function hasFlag(name: string) { return argv.includes(name) }
function getArg(name: string): string | undefined {
  const eq = argv.find(a => a.startsWith(`${name}=`))
  if (eq) return eq.split('=')[1]
  const idx = argv.indexOf(name)
  if (idx >= 0 && idx < argv.length - 1) return argv[idx + 1]
  return undefined
}

const startStop = hasFlag('--start-stop')
const agentMode = hasFlag('--agent-mode') || hasFlag('--ephemeral')
const runOnce = hasFlag('--run-once')
const agentRequestFile = getArg('--agent-request-file') || getArg('--agent-request')
const maxRequests = Number(getArg('--max-requests') || (runOnce ? '1' : '0')) || 0
const idleTimeoutMs = Number(getArg('--idle-timeout-ms') || '5000')
const noPersist = hasFlag('--no-persist')
const exitAfterStartup = hasFlag('--exit-after-startup')
const supervisorMode = hasFlag('--supervisor')

if (noPersist) {
  const tmpBase = fs.mkdtempSync(path.join(os.tmpdir(), 'cassicore-'))
  // Use CASSICORE_HOME instead of mutating HOME — mutating HOME silently
  // redirects ALL path resolution (credentials, sockets, configs) and can
  // cause sessions to vanish when the temp dir is cleaned up.
  process.env.CASSICORE_HOME = tmpBase
}

// When fork()'d by the supervisor, process.send is available.
// Respond to heartbeat pings so the supervisor knows we're alive.
let eventLoopLagMs = 0
let lagTimer: ReturnType<typeof setInterval> | undefined

function startEventLoopLagMeasurement() {
  let lastTick = Date.now()
  lagTimer = setInterval(() => {
    const now = Date.now()
    // interval is 1000ms; any excess is event-loop lag
    eventLoopLagMs = Math.max(0, now - lastTick - 1000)
    lastTick = now
  }, 1000)
  lagTimer.unref()
}

if (typeof process.send === 'function') {
  startEventLoopLagMeasurement()

  process.on('message', (msg: any) => {
    if (msg?.type === 'heartbeat:ping') {
      process.send!({
        type: 'heartbeat:pong',
        ts: msg.ts,
        health: {
          memoryMb: Math.round(process.memoryUsage().heapUsed / 1024 / 1024),
          eventLoopLagMs,
        },
      })
    }
    if (msg?.type === 'shutdown') {
      void daemon.stop()
    }
  })
}

const daemon = new Daemon()

;(async () => {
  try {
    const info = await daemon.start()

    // Ready output — if running under a supervisor, send via IPC;
    // otherwise print to stdout for CI/scripts.
    const ready = {
      status: 'started' as const,
      pid: info?.pid || process.pid,
      admin: info?.admin ?? null,
    }

    if (typeof process.send === 'function') {
      process.send({ type: 'ready', ...ready })
    } else {
      // WHY: When spawned via spawn() (compiled mode), there's no IPC channel.
      // The supervisor reads stdout for JSON lines with { status: 'started' }.
      // We must write raw JSON to stdout — the structured logger output isn't
      // parseable as JSON by the supervisor's detection logic.
      process.stdout.write(JSON.stringify(ready) + '\n')
      logger.info('Daemon ready', { pid: info?.pid || process.pid, admin: info?.admin ?? null })
    }

    // --exit-after-startup: validate startup then exit immediately
    if (exitAfterStartup) {
      await daemon.stop()
      return
    }

    if (supervisorMode) {
      return
    }

    // --start-stop: start, emit ready, then shut down
    if (startStop) {
      await daemon.stop()
      return
    }

    // --agent-request-file: process a single request file then exit
    if (agentRequestFile) {
      try {
        const raw = fs.readFileSync(agentRequestFile, 'utf8')
        const body = JSON.parse(raw)
        const messages = body?.messages || []
        const content = messages.length > 0 ? messages[messages.length - 1].content : (body?.content || '')
        const model = body?.model || undefined

        const { randomUUID } = await import('node:crypto')
        const sessionId = `provider-${randomUUID()}`

        // Use SessionPipeline instead of TurnPipeline
        const result = await (daemon as any).sessionPipeline.processTurn(sessionId, content, {
          channelId: 'channel:cli',
          senderId: 'agent',
          model,
        })

        const out = {
          status: 'completed',
          pid: info?.pid || process.pid,
          admin: info?.admin ?? null,
          requestFile: agentRequestFile,
          response: {
            content: result.response,
            model: result.model,
            tokensUsed: result.tokensUsed,
            durationMs: result.durationMs,
          },
          sessionId: result.sessionId,
        }
        logger.info('Agent request completed', out)
      } catch (err) {
        logger.info('Agent request processing failed', { error: String(err) })
        process.exit(1)
      }

      try { await daemon.stop() } catch (err) {
        logger.error('Error during shutdown', { error: String(err) })
        process.exit(1)
      }
      return
    }

    // --agent-mode + --max-requests: stay up until N requests or idle timeout
    if (agentMode && maxRequests > 0) {
      let processed = 0
      let lastActivity = Date.now()

      const onTurnEnd = (e: any) => {
        processed++
        lastActivity = Date.now()
        if (processed >= maxRequests) {
          logger.info('Processed max requests', { processed, pid: info?.pid || process.pid })
          setImmediate(() => { void daemon.stop() })
        }
      }

      daemon.bus.on('turn:end', onTurnEnd)

      const watcher = setInterval(() => {
        if (Date.now() - lastActivity > idleTimeoutMs) {
          logger.info('Idle timeout reached', { idleMs: idleTimeoutMs, pid: info?.pid || process.pid })
          daemon.bus.off('turn:end', onTurnEnd)
          clearInterval(watcher)
          void daemon.stop()
        }
      }, Math.max(1000, Math.min(5000, Math.floor(idleTimeoutMs / 2))))

      return // keep running
    }

    // Default: stay up indefinitely (daemon mode).
    // Nothing to do — Node.js will keep running due to active handles
    // (HTTP server, event bus timers, worker processes, etc.).

  } catch (err) {
    logger.error('Fatal startup error', { error: String(err) })
    process.exit(1)
  }
})()
