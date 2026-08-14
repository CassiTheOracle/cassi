/**
 * VENDORED TYPE STUB — mirrors `mini-helix/mini-helix-types.js`. Surface:
 * MiniHelixTool, MiniHelixToolDef, MiniHelixToolResult, MiniHelixSession,
 * MiniHelixDeps, MiniHelixConfig, MiniHelixToolHandler. Self-contained: imports
 * only from `@cassicore/foundation`; supporting `ModelHandle` inlined locally.
 */
import type { ILogger, IEventBus, Message } from '@cassicore/foundation'

/** Minimal `ModelHandle` — the pool handle acquired via `handleFactory`. */
export interface ModelHandle {
  readonly provider: string
  readonly model: string
  stream(messages: Message[], opts: Record<string, unknown>): AsyncIterable<{
    type: string
    text?: string
    tokensUsed?: number
    tokenBreakdown?: { input: number; output: number }
    error?: string
    toolCall?: { id: string; name: string; input: Record<string, unknown> }
  }>
  release(): void
}


// Tool Definition (matches provider tool schema format)

export interface MiniHelixToolDef {
  name: string
  description: string
  input_schema: Record<string, unknown>
}

export interface MiniHelixToolResult {
  /** Human-readable content returned to the LLM */
  content: string
  /** If true, the runner should stop iterating (signal_done) */
  done?: boolean
  /** If true, the runner should pause until externally resumed */
  pause?: boolean
  /** Optional structured metadata (not sent to LLM) */
  metadata?: Record<string, unknown>
}

export type MiniHelixToolHandler = (
  args: Record<string, unknown>,
) => MiniHelixToolResult | Promise<MiniHelixToolResult>

export interface MiniHelixTool {
  def: MiniHelixToolDef
  handler: MiniHelixToolHandler
}


// Configuration

export type MiniHelixConsumer = 'corpus' | 'brainstem'

export interface MiniHelixConfig {
  /** What this mini-Helix is for */
  consumer: MiniHelixConsumer
  /** The goal / system prompt for the LLM */
  systemPrompt: string
  /** Session ID (for logging and event attribution) */
  sessionId: string
  /** Parent constellation ID */
  constellationId: string
  /** Max tool-call iterations per run cycle. Default: 50 (Corpus), 30 (Brainstem) */
  maxIterationsPerCycle: number
  /** Max tokens per LLM response. Default: 2048 */
  maxTokens: number
  /** Overall timeout for a single run cycle in ms. Default: 120_000 */
  cycleTimeoutMs: number
  /** Model tier to request from the pool. Default varies by consumer. */
  modelTier: string
  /** Model name to request (optional — tier is used for handle acquisition) */
  modelName?: string
}

/** Defaults per consumer type */
export const MINI_HELIX_DEFAULTS: Record<MiniHelixConsumer, Partial<MiniHelixConfig>> = {
  corpus: {
    maxIterationsPerCycle: 50,
    maxTokens: 2048,
    cycleTimeoutMs: 120_000,
    modelTier: 'qwenMax',
  },
  brainstem: {
    maxIterationsPerCycle: 30,
    maxTokens: 1024,
    cycleTimeoutMs: 90_000,
    modelTier: 'background',
  },
}


// Dependencies

export interface MiniHelixDeps {
  /** Logger instance */
  logger: ILogger
  /** Optional event bus for emitting lifecycle events */
  eventBus?: IEventBus
  /**
   * Factory to acquire a model handle from the parent's pool.
   * Same factory used by the constellation pipeline for full Helix sessions.
   */
  handleFactory: (config: { tier: string; purpose: string; sessionId: string }) => Promise<ModelHandle>
}


// Session Interface

export type MiniHelixStatus =
  | 'idle'
  | 'running'
  | 'paused'
  | 'completed'
  | 'error'
  | 'cancelled'

export interface MiniHelixProgress {
  status: MiniHelixStatus
  consumer: MiniHelixConsumer
  sessionId: string
  /** Current iteration within the active cycle */
  iteration: number
  /** Total tool calls made across all cycles */
  totalToolCalls: number
  /** Total LLM calls made across all cycles */
  totalLLMCalls: number
  /** Total tokens consumed (input + output) */
  totalTokens: number
  /** Number of completed run cycles */
  completedCycles: number
  /** Duration of current/last cycle (ms) */
  currentCycleDurationMs: number
  /** Total active duration (ms) */
  totalDurationMs: number
}

export interface MiniHelixResult {
  /** Summary of what the session accomplished */
  summary: string
  /** Final status */
  status: MiniHelixStatus
  /** Total tool calls */
  toolCalls: number
  /** Total LLM calls */
  llmCalls: number
  /** Token usage */
  tokenUsage: {
    input: number
    output: number
    total: number
  }
  /** Number of run cycles completed */
  cycles: number
  /** Total duration (ms) */
  durationMs: number
}

export interface MiniHelixSession {
  /** Start or resume the tool-calling loop. Resolves when cycle ends. */
  run(userMessage?: string): Promise<MiniHelixResult>
  /** Cancel the current cycle. Safe to call from any state. */
  cancel(): void
  /** Pause the session externally (Brainstem lifecycle management). */
  pause(): void
  /** Resume a paused session. Only valid when status === 'paused'. */
  resume(): void
  /** Final shutdown — releases resources, no restart possible. */
  shutdown(): Promise<void>
  /** Get current progress snapshot. */
  getProgress(): MiniHelixProgress
  /** Get current status. */
  getStatus(): MiniHelixStatus
  /** Update the system prompt (e.g., when Corpus state changes). */
  updateSystemPrompt(prompt: string): void
  /** Add a message to the conversation history (e.g., inject context). */
  injectMessage(message: Message): void
}
