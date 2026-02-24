/**
 * spawn-subagent-impl.ts — Real subagent spawning implementation for CassiCore.
 *
 * This module provides the actual spawn function that:
 * - Creates a child session with parent reference
 * - Stores the session in SessionStore
 * - Emits events for tracking
 * - Runs the subagent task through the TurnPipeline
 * - Returns runId and sessionKey
 */

import type { ISessionManager, Session, InboundMessage, Message } from '../../../types/runtime.js'
import type { IEventBus, ILogger } from '../../../types/interfaces.js'
import type { SessionStore } from '../../session-store.js'
import type { TurnPipeline } from '../../turn-pipeline.js'
import { randomUUID } from 'node:crypto'

export interface SpawnSubagentOptions {
  task: string
  label: string
  model: string
  timeoutSeconds: number
  parentSessionId: string
}

export interface SpawnSubagentResult {
  runId: string
  sessionKey: string
}

export interface SubagentSpawnContext {
  sessionManager: ISessionManager
  sessionStore?: SessionStore
  bus: IEventBus
  logger: ILogger
  /** Lazy getter for pipeline - needed because tools are registered before pipeline is created */
  getPipeline: () => TurnPipeline
}

/**
 * Creates a real spawn function for subagents.
 *
 * Usage:
 *   const spawnFn = createSubagentSpawnFunction({ sessionManager, sessionStore, bus, logger, pipeline })
 *   const result = await spawnFn({ task, label, model, timeoutSeconds, parentSessionId })
 */
export function createSubagentSpawnFunction(ctx: SubagentSpawnContext): (opts: SpawnSubagentOptions) => Promise<SpawnSubagentResult> {
  return async (opts: SpawnSubagentOptions): Promise<SpawnSubagentResult> => {
    const { task, label, model, timeoutSeconds, parentSessionId } = opts
    const { sessionManager, sessionStore, bus, logger, getPipeline } = ctx

    // Generate IDs
    const runId = randomUUID()
    const childSessionId = `subagent:${parentSessionId}:${runId}`

    // Get parent session to inherit config
    const parentSession = sessionManager.get(parentSessionId)
    if (!parentSession) {
      throw new Error(`Parent session ${parentSessionId} not found`)
    }

    // Create child session config (inherit from parent but allow model override)
    const childConfig = {
      ...parentSession.config,
      model: model || parentSession.config.model,
    }

    // Create the child session directly (bypass getOrCreate to use our specific ID)
    const now = new Date()
    const childSession: Session = {
      id: childSessionId,
      channelId: 'subagent', // Special channel for subagents
      senderId: parentSessionId, // Use parent as sender for tracking
      createdAt: now,
      lastActiveAt: now,
      history: [],
      tokenCount: 0,
      config: childConfig,
    }

    // Store in session manager's internal map (access private field via any cast)
    const sessionsMap = (sessionManager as any).sessions as Map<string, Session>
    sessionsMap.set(childSessionId, childSession)

    // Also update sender index
    const senderKey = `subagent:${parentSessionId}`
    const senderIndex = (sessionManager as any).senderIndex as Map<string, string>
    senderIndex.set(senderKey, childSessionId)

    // Persist to disk if store available
    if (sessionStore) {
      sessionStore.save(childSession)
    }

    // Emit spawn event
    bus.emit({
      type: 'subagent:spawned',
      parentSessionId,
      childSessionId,
      runId,
      label,
      timestamp: now,
    })

    logger.info(`[spawn-subagent] Spawned ${label} (${runId}) for parent ${parentSessionId}`)

    // Start the subagent task asynchronously (fire-and-forget)
    runSubagentTask({
      runId,
      childSessionId,
      task,
      label,
      timeoutSeconds,
      ctx,
    })

    return {
      runId,
      sessionKey: childSessionId,
    }
  }
}

interface RunSubagentTaskOptions {
  runId: string
  childSessionId: string
  task: string
  label: string
  timeoutSeconds: number
  ctx: SubagentSpawnContext
}

/**
 * Run the subagent task asynchronously.
 * This runs in the background and completes independently of the spawning turn.
 */
async function runSubagentTask(opts: RunSubagentTaskOptions): Promise<void> {
  const { runId, childSessionId, task, label, timeoutSeconds, ctx } = opts
  const { bus, logger, getPipeline } = ctx

  // Get pipeline lazily at execution time (after daemon has fully started)
  const pipeline = getPipeline()
  if (!pipeline) {
    throw new Error('Pipeline not available - daemon may not be fully started')
  }

  const startTime = Date.now()

  // Emit start event
  bus.emit({
    type: 'subagent:started',
    runId,
    sessionId: childSessionId,
    timestamp: new Date(),
  })

  try {
    // Create timeout promise
    const timeoutMs = timeoutSeconds * 1000
    const timeoutPromise = new Promise<never>((_, reject) => {
      setTimeout(() => reject(new Error(`Subagent ${label} timed out after ${timeoutSeconds}s`)), timeoutMs)
    })

    // Build the inbound message for the subagent task
    const inbound: InboundMessage = {
      id: randomUUID(),
      sessionId: childSessionId,
      channelId: 'subagent',
      senderId: childSessionId,
      content: task,
      timestamp: new Date(),
    }

    // Run the turn with timeout race
    const result = await Promise.race([
      pipeline.process(inbound),
      timeoutPromise,
    ])

    const durationMs = Date.now() - startTime

    // Emit completion event
    bus.emit({
      type: 'subagent:completed',
      runId,
      sessionId: childSessionId,
      result: result.response,
      durationMs,
      timestamp: new Date(),
    })

    logger.info(`[spawn-subagent] Completed ${label} (${runId}) in ${durationMs}ms`)

  } catch (err) {
    const durationMs = Date.now() - startTime
    const errorMsg = String(err)

    // Emit failure event
    bus.emit({
      type: 'subagent:failed',
      runId,
      sessionId: childSessionId,
      error: errorMsg,
      timestamp: new Date(),
    })

    logger.error(`[spawn-subagent] Failed ${label} (${runId}): ${errorMsg}`)

    // Store error in session history
    const session = ctx.sessionManager.get(childSessionId)
    if (session) {
      const errorMessage: Message = {
        role: 'assistant',
        content: `[Subagent ${label} failed: ${errorMsg}]`,
      }
      session.history.push(errorMessage)
      ctx.sessionStore?.save(session)
    }
  }
}
