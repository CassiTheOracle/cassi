/**
 * Hook that subscribes to the daemon's cognitive SSE event stream
 * (/events/stream) and dispatches typed callbacks.
 *
 * Handles automatic reconnection with exponential back-off.
 */

import { useEffect, useRef, useCallback } from 'react'
import { useDaemon } from './use-daemon.js'
import type {
  CognitiveEvent,
  ThinkerActivityPayload,
  ThinkerInsightPayload,
  DialecticSignalPayload,
  AutonomyConfirmationPayload,
  MemoryInjectedPayload,
  ScoutStartedPayload,
  ScoutCompletedPayload,
  ScoutSkippedPayload,
  TeamActivityPayload,
  DaemonRestartingPayload,
  DaemonResumedPayload,
} from '../types/index.js'

export interface CognitiveEventHandlers {
  onThinkerActive?: (payload: ThinkerActivityPayload) => void
  onThinkerIdle?: (payload: ThinkerActivityPayload) => void
  onThinkerInsight?: (payload: ThinkerInsightPayload) => void
  onDialecticSignal?: (payload: DialecticSignalPayload) => void
  onAutonomyConfirmation?: (payload: AutonomyConfirmationPayload) => void
  onMemoryInjected?: (payload: MemoryInjectedPayload) => void
  onScoutStarted?: (payload: ScoutStartedPayload) => void
  onScoutCompleted?: (payload: ScoutCompletedPayload) => void
  onScoutSkipped?: (payload: ScoutSkippedPayload) => void
  onTeamActivity?: (type: string, payload: TeamActivityPayload) => void
  onDaemonRestarting?: (payload: DaemonRestartingPayload) => void
  onDaemonResumed?: (payload: DaemonResumedPayload) => void
  onConnected?: () => void
  onDisconnected?: (err?: Error) => void
}

const TEAM_EVENT_TYPES = new Set([
  'team:created', 'team:started', 'team:paused', 'team:resumed',
  'team:completed', 'team:failed', 'team:cancelled', 'team:checkpoint',
  'team:checkpoint:approved', 'team:checkpoint:rejected',
  'team:checkpoint:auto_approved',
])

export function useCognitiveEvents(
  sessionId: string | undefined,
  handlers: CognitiveEventHandlers,
): void {
  const client = useDaemon()
  const handlersRef = useRef(handlers)
  handlersRef.current = handlers

  const dispatch = useCallback((event: CognitiveEvent) => {
    const h = handlersRef.current
    const payload = event as Record<string, unknown>

    switch (event.type) {
      case 'thinker:active':
        h.onThinkerActive?.(payload as unknown as ThinkerActivityPayload)
        break
      case 'thinker:idle':
        h.onThinkerIdle?.(payload as unknown as ThinkerActivityPayload)
        break
      case 'thinker:insight':
        h.onThinkerInsight?.(payload as unknown as ThinkerInsightPayload)
        break
      case 'dialectic:signal':
        h.onDialecticSignal?.(payload as unknown as DialecticSignalPayload)
        break
      case 'autonomy:confirmation_requested':
        h.onAutonomyConfirmation?.(payload as unknown as AutonomyConfirmationPayload)
        break
      case 'memory:injected':
        h.onMemoryInjected?.(payload as unknown as MemoryInjectedPayload)
        break
      case 'scout:started':
        h.onScoutStarted?.(payload as unknown as ScoutStartedPayload)
        break
      case 'scout:completed':
        h.onScoutCompleted?.(payload as unknown as ScoutCompletedPayload)
        break
      case 'scout:skipped':
        h.onScoutSkipped?.(payload as unknown as ScoutSkippedPayload)
        break
      case 'daemon:restarting':
        h.onDaemonRestarting?.(payload as unknown as DaemonRestartingPayload)
        break
      case 'daemon:resumed':
        h.onDaemonResumed?.(payload as unknown as DaemonResumedPayload)
        break
      default:
        if (TEAM_EVENT_TYPES.has(event.type)) {
          h.onTeamActivity?.(event.type, payload as unknown as TeamActivityPayload)
        }
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    let cancelled = false
    let backoff = 1000
    const MAX_BACKOFF = 30_000

    async function subscribe() {
      while (!cancelled) {
        try {
          const stream = await client.subscribeEvents(sessionId, controller.signal)
          backoff = 1000
          handlersRef.current.onConnected?.()

          // Read timeout: if no event (including heartbeat pings) arrives
          // within 60s, the connection is likely dead. The server sends
          // `: ping` every 15s, so 60s gives 4 missed heartbeats as margin.
          const READ_TIMEOUT_MS = 60_000
          let lastEventAt = Date.now()

          for await (const event of stream) {
            if (cancelled) break
            lastEventAt = Date.now()
            dispatch(event)

            // Check if we've gone too long without any data
            // (the for-await-of blocks, so this catches half-open connections
            // only when a new event finally arrives after a long gap)
          }

          // Stream ended cleanly (server closed or EOF)
        } catch (err: unknown) {
          // Log the actual error for debuggability instead of swallowing
          const reason = err instanceof Error ? err.message : String(err)
          if (!cancelled && reason !== 'The operation was aborted') {
            console.warn('[cognitive-events] SSE stream error:', reason) // contributing:ignore - TUI client error logging
          }
        }

        if (cancelled) break
        handlersRef.current.onDisconnected?.()
        await new Promise((r) => setTimeout(r, backoff))
        backoff = Math.min(backoff * 2, MAX_BACKOFF)
      }
    }

    subscribe()

    return () => {
      cancelled = true
      controller.abort()
    }
  }, [client, sessionId, dispatch])
}
