/**
 * Mini-Helix Types — Lightweight single-posture Helix sessions
 *
 * Mini-Helix sessions are purpose-built agent loops for Constellation
 * infrastructure components (Corpus, Brainstem) that need structured
 * tool-calling but not the full Helix overhead.
 *
 * Key differences from full Helix:
 *   - Single Unity posture (no reviewers, no dialectic)
 *   - Purpose-built tool sets (not the full registry)
 *   - No Phase Zero context distillation
 *   - Reduced checkpointing (explicit save points only)
 *   - Shares parent's ModelPool via handleFactory
 *   - Supports LLM-driven pause/resume (Corpus self-drives its cadence)
 *
 * Two consumers:
 *   Corpus:     Self-driving analysis loop. Starts at constellation boot,
 *               uses tools to analyze tree state, sends directives, then
 *               calls pause_until_trigger to sleep. Resumes on safety-net
 *               events (cascades, stuck branches, tensions, escalations).
 *
 *   Brainstem:  Sidecar observer. Constellation-managed lifecycle (1:1 default
 *               with parent Helix, can be overridden). Uses tools to read
 *               the parent's work stream, annotate, guide, and self-organize.
 */

import type { ILogger, IEventBus } from '../types/interfaces.js'
import type { ModelHandle } from '@cassicore/model-pool/types'
import type { Message, ContentBlock } from '../types/runtime.js'


// Tool Definition (matches provider tool schema format)

/**
 * Tool definition in Anthropic schema format — same as CompletionOpts.tools.
 * Mini-Helix tools are self-contained: definition + handler in one package.
 */
export interface MiniHelixToolDef {
  name: string
  description: string
  input_schema: Record<string, unknown>
}

/**
 * Result of executing a mini-Helix tool handler.
 */
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

/**
 * Tool handler function signature. Receives parsed arguments, returns result.
 */
export type MiniHelixToolHandler = (
  args: Record<string, unknown>,
) => MiniHelixToolResult | Promise<MiniHelixToolResult>

/**
 * Complete tool package: definition + handler.
 */
export interface MiniHelixTool {
  def: MiniHelixToolDef
  handler: MiniHelixToolHandler
}


// Configuration

/**
 * Mini-Helix consumer type. Controls default behavior and logging.
 */
export type MiniHelixConsumer = 'corpus' | 'brainstem'

/**
 * Configuration for a mini-Helix session.
 */
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
    modelTier: 'qwenMax',       // Qwen3 Max via alibaba-coding
  },
  brainstem: {
    maxIterationsPerCycle: 30,
    maxTokens: 1024,
    cycleTimeoutMs: 90_000,
    modelTier: 'background', // GPT-5-Mini via github-copilot
  },
}


// Dependencies

/**
 * Dependencies for creating a mini-Helix session.
 */
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

/**
 * Status of a mini-Helix session.
 */
export type MiniHelixStatus =
  | 'idle'       // Created but not started
  | 'running'    // Currently executing a tool-call cycle
  | 'paused'     // LLM called pause_until_trigger (Corpus) or externally paused
  | 'completed'  // Finished (signal_done called or consumer shut down)
  | 'error'      // Failed with an error
  | 'cancelled'  // Externally cancelled

/**
 * Progress snapshot for observability.
 */
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

/**
 * Result of a mini-Helix session.
 */
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

/**
 * The mini-Helix session interface.
 *
 * Lifecycle:
 *   1. Create via factory
 *   2. Call run() — starts the tool-calling loop
 *   3. Loop continues until:
 *      a. LLM calls signal_done → status = 'completed'
 *      b. LLM calls pause_until_trigger → status = 'paused'
 *      c. Max iterations reached → status = 'completed'
 *      d. Timeout → status = 'error'
 *      e. cancel() called → status = 'cancelled'
 *   4. When paused, call resume() to start a new cycle
 *   5. Call shutdown() for final cleanup
 */
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
