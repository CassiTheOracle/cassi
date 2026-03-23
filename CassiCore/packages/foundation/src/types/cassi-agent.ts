/**
 * CassiAgent — Shared type definitions for Lumen and Dyad agent sessions.
 *
 * These interfaces define the common contract that both agent systems share,
 * enabling the BaseAgentSession abstraction layer.
 *
 * Design principle: Extract shared shapes, preserve semantic differences.
 * - BasePosture captures the identical posture interface both systems use
 * - InferenceResult and ParsedToolCall eliminate duplicate local interfaces
 * - IAgentStore defines the minimal store contract shared by LumenStore and DyadStore
 */

import type { ContentBlock } from './runtime.js'


/**
 * Base posture configuration shared by both Lumen and Dyad postures.
 * Both LumenPosture and DyadPosture have identical shapes — this captures it.
 */
export interface BasePosture {
  name: string
  systemPrompt: string
  temperature: number
  slotName: string
  toolAccess: 'read-only' | 'read-only+memory' | 'full'
  maxIterations: number
}


/**
 * Result from a single streaming inference call.
 * Both Lumen and Dyad define this identically (Lumen adds optional tokenBreakdown).
 */
export interface InferenceResult {
  contentBlocks: ContentBlock[]
  tokensUsed: number
  hasToolUse: boolean
  /** Detailed token breakdown — available when the provider reports it */
  tokenBreakdown?: {
    input: number
    output: number
    cacheRead: number
    cacheWrite: number
  }
}


/**
 * Parsed tool call extracted from inference content blocks.
 * Identical in both Lumen and Dyad.
 */
export interface ParsedToolCall {
  id: string
  name: string
  input: Record<string, unknown>
}


/**
 * Minimal store interface satisfied by both LumenStore and DyadStore.
 * Used by BaseAgentSession to persist tool calls and events without
 * coupling to either store's full interface.
 */
export interface IAgentStore {
  saveToolCall(
    sessionId: string,
    agentLabel: string,
    toolName: string,
    callId: string,
    isMeta: boolean,
    input: unknown,
    result: string,
    isError: boolean,
    durationMs: number,
    iteration: number,
  ): void

  appendEvent?(
    sessionId: string,
    eventType: string,
    agentLabel: string,
    message: string,
    data?: unknown,
  ): void
}


/**
 * Base constructor options shared by both LumenAgentSession and DyadAgentSession.
 * Each system extends this with its own channel and role-specific options.
 */
export interface BaseAgentSessionOpts<TPosture extends BasePosture = BasePosture> {
  posture: TPosture
  handle: import('../core/model-pool/types.js').ModelHandle
  logger: import('./interfaces.js').ILogger
  sessionId?: string
  toolExecutor?: import('../core/tools/executor.js').ToolExecutor
  toolRegistry?: import('../core/tools/registry.js').ToolRegistry
  store?: IAgentStore
  planHandler?: import('../core/intelligence/flux-team/plan-handler.js').PlanHandler
  blackboard?: import('../core/intelligence/flux-team/blackboard.js').Blackboard
  onActivity?: () => void
  modelDirective?: import('./model-routing.js').IModelDirective
  handleFactory?: (config: import('./model-routing.js').ModelConfig) => Promise<import('../core/model-pool/types.js').ModelHandle>
  eventBus?: import('./interfaces.js').IEventBus
  jobId?: string
  postureSlot?: string
  moduleDebugSessionId?: string
}
