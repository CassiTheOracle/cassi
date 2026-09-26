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

import { MODEL_DEFAULTS, getModelSpec } from '@cassicore/foundation'
import { generateShortId, generateReadableId } from '../vendor/core/utils/ids.js'

import type { IEventBus, ILogger } from "@cassicore/foundation"
import type { ISessionManager, Session, Message } from "@cassicore/foundation"
import type { SessionStore } from '../ports/session-store.js'
import type { TurnPipeline } from '../ports/turn-pipeline.js'

interface SessionPipelineLike {
  processTurn(
    sessionId: string,
    content: string,
    options?: {
      channelId?: string
      senderId?: string
      signal?: AbortSignal
      model?: string
    },
  ): Promise<{ response: string; sessionId: string; model?: string; tokensUsed?: number; durationMs?: number }>
}


export interface SpawnSubagentOptions {
  task: string
  label: string
  model?: string
  providerId?: string
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
  /** Lazy getter for active turn runner - needed because tools are registered before pipeline is created */
  getPipeline: () => TurnPipeline | SessionPipelineLike
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

    try {
      // Generate IDs
      const runId = generateShortId(4)
      const childSessionId = `sub:${parentSessionId.split(':').pop()}:${runId}`

      // Get parent session to inherit config
      logger.info(`[spawn-subagent] Spawning subagent ${label}. Parent session: ${parentSessionId}`)
      const parentSession = sessionManager.get(parentSessionId)
      
      if (!parentSession) {
        logger.warn(`[spawn-subagent] Parent session ${parentSessionId} not found. Proceeding with default config fallback.`)
      }

      const parentConfig = parentSession?.config || {
        model: getModelSpec('agent'),
        thinking: 'high'
      }

      // Create child session config (inherit from parent but allow model/provider override)
      const parentModel = parentConfig.model
      function deriveFinalModel(optsModel?: string, parentModel?: string, providerId?: string) {
        if (optsModel) {
          if (optsModel.includes('/')) return optsModel
          if (providerId) return `${providerId}/${optsModel}`
          return optsModel
        }
        if (providerId) {
          if (parentModel && parentModel.includes('/')) {
            const modelPart = parentModel.split('/').slice(1).join('/')
            return `${providerId}/${modelPart}`
          }
          return `${providerId}/${parentModel || MODEL_DEFAULTS.agent.model}`
        }
        return parentModel || getModelSpec('agent')
      }

      const finalModel = deriveFinalModel(model, parentModel, opts.providerId)

      const childConfig = {
        ...parentConfig,
        model: finalModel,
        providerId: opts.providerId ?? parentConfig.providerId,
        providerModel: finalModel && finalModel.includes('/') ? finalModel.split('/').slice(1).join('/') : undefined,
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
        task,
        model: finalModel,
        timeoutSeconds,
        timestamp: now,
      })

      logger.info(`[spawn-subagent] Successfully spawned ${label} (${runId}) for parent ${parentSessionId}`)

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
    } catch (err) {
      logger.error(`[spawn-subagent] CRITICAL ERROR during spawn: ${String(err)}`)
      throw err; // Re-throw to be caught by tool handler
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

    // Run the turn with timeout race
    const result = await Promise.race([
      typeof (pipeline as SessionPipelineLike).processTurn === 'function'
        ? (pipeline as SessionPipelineLike).processTurn(childSessionId, task, {
            channelId: 'subagent',
            senderId: childSessionId,
          })
        : (pipeline as TurnPipeline).process({
            id: generateShortId(8),
            sessionId: childSessionId,
            channelId: 'subagent',
            senderId: childSessionId,
            content: task,
            timestamp: new Date(),
          }),
      timeoutPromise,
    ])

    const durationMs = Date.now() - startTime
    const rAny: any = result as any

    // Emit completion event with telemetry
    const childSess = ctx.sessionManager.get(childSessionId)
    const sessionModel = childSess?.config?.model
    bus.emit({
      type: 'subagent:completed',
      runId,
      sessionId: childSessionId,
      result: rAny.response,
      durationMs,
      tokensUsed: rAny.tokensUsed ?? 0,
      model: rAny.model ?? sessionModel ?? undefined,
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
