/**
 * @cassicore/mind-runtime — bin entry (`cassi-mind`).
 *
 * Stands up the focused mind runtime: boots the retained mind (field + intelligence +
 * tools) and the narrow localhost channel, then stays alive until SIGINT/SIGTERM or
 * a `POST /v1/shutdown`. The ohmypi spine spawns this (detached) when `CASSI_MIND_URL`
 * is unset; non-interactive hosts use hub `start`.
 */

import { createMindRuntime } from './boot.js'
import { MindChannelServer } from './channel/server.js'

export async function main(): Promise<void> {
  const quiet = process.env.CASSI_MIND_QUIET === '1'
  const runtime = await createMindRuntime({
    // Same explicit opt-in the spine uses; the spawned child inherits the env.
    // Default remains off and therefore bit-identical/no-socket.
    fieldTelemetry: process.env.CASSI_THALAMUS_FIELD_SHADOW === '1',
  })

  let shutdownRequested = false
  const server = new MindChannelServer(runtime, {
    token: runtime.config.token,
    onShutdown: async () => {
      if (!quiet) runtime.logger.info('graceful shutdown requested via /v1/shutdown')
      await finish()
    },
  })

  const finish = async (): Promise<void> => {
    if (shutdownRequested) return
    shutdownRequested = true
    await server.close()
    await runtime.close()
  }

  const port = await server.listen()

  if (!quiet) {
    runtime.logger.info('CassiCore mind runtime online', {
      home: runtime.config.homePath,
      port,
      token: runtime.config.token ? 'set' : 'none',
    })
  }

  let shuttingDown = false
  const onSignal = async (signal: string): Promise<void> => {
    if (shuttingDown) return
    shuttingDown = true
    if (!quiet) runtime.logger.info(`received ${signal}, shutting down`)
    await finish()
    process.exit(0)
  }
  process.on('SIGINT', () => void onSignal('SIGINT'))
  process.on('SIGTERM', () => void onSignal('SIGTERM'))

  // Keep alive until the channel closes (either /v1/shutdown or a signal).
  await new Promise<void>((resolve) => {
    server.onClosed(() => resolve())
  })
}

// Run only when invoked directly (not imported by tests).
const isMain = process.argv[1] && import.meta.url.endsWith(new URL(process.argv[1]).pathname ?? '')
if (isMain) {
  main().catch((err) => {
    console.error('cassi-mind failed to start:', err)
    process.exit(1)
  })
}
