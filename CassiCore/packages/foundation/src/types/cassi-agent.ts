/**
 * CassiAgent — Shared type definitions for posture runners across all agent systems.
 *
 * Postures are behavioral modes within a CassiAgent, not agents themselves.
 * These interfaces define the common contract that all posture runners share,
 * enabling the BasePostureRunner abstraction layer.
 *
 * Design principle: Extract shared shapes, preserve semantic differences.
 * - BasePosture captures the posture configuration all systems use
 * - InferenceResult and ParsedToolCall eliminate duplicate local interfaces
 * - IAgentStore defines the minimal store contract shared by all agent stores
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
  /** Reasoning/thinking content accumulated during streaming — required by DeepSeek and other thinking-mode providers */
  reasoningContent?: string
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
 * Used by BasePostureRunner to persist tool calls and events without
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
 * Base constructor options shared by both LumenPostureRunner and DyadPostureRunner.
 * Each system extends this with its own channel and role-specific options.
 */
export interface BasePostureRunnerOpts<TPosture extends BasePosture = BasePosture> {
  posture: TPosture
  handle: import('../vendor/core/model-pool/types.js').ModelHandle
  logger: import('./interfaces.js').ILogger
  sessionId?: string
  toolExecutor?: import('../vendor/core/tools/executor.js').ToolExecutor
  toolRegistry?: import('../vendor/core/tools/registry.js').ToolRegistry
  store?: IAgentStore
  planHandler?: import('../vendor/core/intelligence/flux-team/plan-handler.js').PlanHandler
  blackboard?: import('../vendor/core/intelligence/flux-team/blackboard.js').Blackboard
  onActivity?: () => void
  modelDirective?: import('./model-routing.js').IModelDirective
  handleFactory?: (config: import('./model-routing.js').ModelConfig) => Promise<import('../vendor/core/model-pool/types.js').ModelHandle>
  eventBus?: import('./interfaces.js').IEventBus
  jobId?: string
  postureSlot?: string
  moduleDebugSessionId?: string
}


/**
 * Agent session state for pause/resume infrastructure.
 */
export type PostureRunnerState = 'running' | 'paused' | 'concluded' | 'cancelled' | 'errored'


/**
 * Serializable snapshot of an agent session's state.
 * Used for pause/resume, debugging, and observability.
 */
export interface PostureSnapshot {
  state: PostureRunnerState
  iterationCount: number
  toolCallCount: number
  tokensUsed: number
  messageCount: number
  pausedAt?: number
  resumedAt?: number
}


/**
 * Interface for pausable agent sessions.
 * Implemented by BasePostureRunner and propagated through pipeline orchestrators.
 */
export interface PausablePostureRunner {
  pause(): void
  resume(): void
  isPaused(): boolean
  getState(): PostureRunnerState
  getSessionSnapshot(): PostureSnapshot
}
