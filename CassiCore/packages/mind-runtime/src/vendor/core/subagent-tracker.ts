/**
 * SubagentTracker — Tracks status of spawned subagents across the system.
 *
 * Listens to bus events (spawned, started, completed, failed) and maintains
 * an in-memory registry of subagent status. Provides APIs for querying
 * subagent state and results.
 *
 * Events tracked:
 *   - subagent:spawned  → status: 'pending'
 *   - subagent:started  → status: 'running'
 *   - subagent:completed → status: 'completed', stores result
 *   - subagent:failed   → status: 'failed', stores error
 */

import type { IEventBus, ILogger } from '@cassicore/foundation'

export type SubagentStatus = 'pending' | 'running' | 'completed' | 'failed' | 'timeout'

export interface SubagentInfo {
  runId: string
  sessionKey: string
  parentSessionId: string
  label: string
  model?: string
  status: SubagentStatus
  task: string
  createdAt: Date
  startedAt?: Date
  completedAt?: Date
  result?: string
  error?: string
  durationMs?: number
  tokensUsed?: number
  timeoutSeconds: number
}

export interface SubagentTracker {
  /** Get all tracked subagents */
  list(): SubagentInfo[]
  /** Get subagent by runId */
  get(runId: string): SubagentInfo | undefined
  /** Get subagents for a parent session */
  getByParent(parentSessionId: string): SubagentInfo[]
  /** Get subagent result (only if completed) */
  getResult(runId: string): { result?: string; error?: string; durationMs?: number } | undefined
  /** Clean up old entries (keeps last N or within time window) */
  prune(maxAgeMs?: number, maxEntries?: number): number
  /** Stop listening to events */
  stop(): void
}

interface SubagentTrackerOptions {
  bus: IEventBus
  logger: ILogger
  maxTracked?: number        // Max subagents to track (default: 1000)
  defaultMaxAgeMs?: number   // Default prune age (default: 24h)
}

export function createSubagentTracker(opts: SubagentTrackerOptions): SubagentTracker {
  const { bus, logger, maxTracked = 1000, defaultMaxAgeMs = 24 * 60 * 60 * 1000 } = opts

  const subagents = new Map<string, SubagentInfo>()
  const sessionKeyToRunId = new Map<string, string>()

  let offSpawned: (() => void) | undefined
  let offStarted: (() => void) | undefined
  let offCompleted: (() => void) | undefined
  let offFailed: (() => void) | undefined

  // Handler for subagent:spawned
  const onSpawned = (e: any) => {
    try {
      const { runId, childSessionId, parentSessionId, label, task, model, timeoutSeconds } = e as {
        runId: string
        childSessionId: string
        parentSessionId: string
        label: string
        task?: string
        model?: string
        timeoutSeconds?: number
      }

      if (!runId || !childSessionId) return

      const info: SubagentInfo = {
        runId,
        sessionKey: childSessionId,
        parentSessionId,
        label: label || 'unnamed',
        model,
        status: 'pending',
        task: task || '',
        createdAt: new Date(e.timestamp || Date.now()),
        timeoutSeconds: timeoutSeconds || 300,
      }

      subagents.set(runId, info)
      sessionKeyToRunId.set(childSessionId, runId)

      // Prune if we're over the limit
      if (subagents.size > maxTracked) {
        pruneOldest(subagents.size - maxTracked)
      }

      logger.debug(`Tracked spawn: ${runId} (${label})`)
    } catch (err) {
      logger.warn(`Error handling spawned event: ${String(err)}`)
    }
  }

  // Handler for subagent:started
  const onStarted = (e: any) => {
    try {
      const { runId, sessionId } = e as { runId?: string; sessionId?: string }
      const targetRunId = runId || (sessionId ? sessionKeyToRunId.get(sessionId) : undefined)
      if (!targetRunId) return

      const info = subagents.get(targetRunId)
      if (info) {
        info.status = 'running'
        info.startedAt = new Date(e.timestamp || Date.now())
      }
    } catch (err) {
      logger.warn(`Error handling started event: ${String(err)}`)
    }
  }

  // Handler for subagent:completed
  const onCompleted = (e: any) => {
    try {
      const { runId, sessionId, result, durationMs, tokensUsed } = e as {
        runId?: string
        sessionId?: string
        result?: string
        durationMs?: number
        tokensUsed?: number
      }
      const targetRunId = runId || (sessionId ? sessionKeyToRunId.get(sessionId) : undefined)
      if (!targetRunId) return

      const info = subagents.get(targetRunId)
      if (info) {
        info.status = 'completed'
        info.result = result
        info.durationMs = durationMs
        info.tokensUsed = tokensUsed
        info.completedAt = new Date(e.timestamp || Date.now())
      }

      logger.debug(`Completed: ${targetRunId}`)
    } catch (err) {
      logger.warn(`Error handling completed event: ${String(err)}`)
    }
  }

  // Handler for subagent:failed
  const onFailed = (e: any) => {
    try {
      const { runId, sessionId, error } = e as {
        runId?: string
        sessionId?: string
        error?: string
      }
      const targetRunId = runId || (sessionId ? sessionKeyToRunId.get(sessionId) : undefined)
      if (!targetRunId) return

      const info = subagents.get(targetRunId)
      if (info) {
        info.status = error?.includes('timed out') ? 'timeout' : 'failed'
        info.error = error
        info.completedAt = new Date(e.timestamp || Date.now())
      }

      logger.debug(`Failed: ${targetRunId}`)
    } catch (err) {
      logger.warn(`Error handling failed event: ${String(err)}`)
    }
  }

  // Prune oldest N entries
  function pruneOldest(count: number) {
    const entries = Array.from(subagents.entries())
    entries.sort((a, b) => a[1].createdAt.getTime() - b[1].createdAt.getTime())
    for (let i = 0; i < count && i < entries.length; i++) {
      const [runId, info] = entries[i]
      subagents.delete(runId)
      sessionKeyToRunId.delete(info.sessionKey)
    }
  }

  // Wire up event listeners
  if (bus && typeof (bus as any).on === 'function') {
    try {
      ;(bus as any).on('subagent:spawned', onSpawned)
      ;(bus as any).on('subagent:started', onStarted)
      ;(bus as any).on('subagent:completed', onCompleted)
      ;(bus as any).on('subagent:failed', onFailed)

      offSpawned = () => { try { (bus as any).off?.('subagent:spawned', onSpawned) } catch {} }
      offStarted = () => { try { (bus as any).off?.('subagent:started', onStarted) } catch {} }
      offCompleted = () => { try { (bus as any).off?.('subagent:completed', onCompleted) } catch {} }
      offFailed = () => { try { (bus as any).off?.('subagent:failed', onFailed) } catch {} }

      logger.info('Started and listening for subagent events')
    } catch (err) {
      logger.warn(`Failed to attach to bus: ${String(err)}`)
    }
  }

  return {
    list(): SubagentInfo[] {
      return Array.from(subagents.values()).sort(
        (a, b) => b.createdAt.getTime() - a.createdAt.getTime()
      )
    },

    get(runId: string): SubagentInfo | undefined {
      return subagents.get(runId)
    },

    getByParent(parentSessionId: string): SubagentInfo[] {
      return this.list().filter(s => s.parentSessionId === parentSessionId)
    },

    getResult(runId: string): { result?: string; error?: string; durationMs?: number } | undefined {
      const info = subagents.get(runId)
      if (!info) return undefined
      if (info.status !== 'completed' && info.status !== 'failed' && info.status !== 'timeout') {
        return undefined
      }
      return {
        result: info.result,
        error: info.error,
        durationMs: info.durationMs,
      }
    },

    prune(maxAgeMs = defaultMaxAgeMs, maxEntries?: number): number {
      const cutoff = Date.now() - maxAgeMs
      let removed = 0

      for (const [runId, info] of subagents) {
        if (info.createdAt.getTime() < cutoff) {
          subagents.delete(runId)
          sessionKeyToRunId.delete(info.sessionKey)
          removed++
        }
      }

      if (maxEntries && subagents.size > maxEntries) {
        const toRemove = subagents.size - maxEntries
        pruneOldest(toRemove)
        removed += toRemove
      }

      return removed
    },

    stop() {
      try { offSpawned?.() } catch {}
      try { offStarted?.() } catch {}
      try { offCompleted?.() } catch {}
      try { offFailed?.() } catch {}
      subagents.clear()
      sessionKeyToRunId.clear()
      logger.info('Stopped')
    },
  }
}
