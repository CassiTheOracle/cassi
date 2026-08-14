/**
 * VENDORED TYPE STUB — mirrors `mini-helix/mini-helix-runner.js`. Runtime
 * function `createMiniHelixSession` throws until the real runner lands at P3
 * (`@cassicore/mini-helix`). Self-contained: supporting MiniHelix surfaces are
 * inlined locally (structurally compatible with the mini-helix-types stub).
 */
import type { ILogger, IEventBus } from '@cassicore/foundation'

/** Minimal model handle acquired via `handleFactory`. */
interface ModelHandle {
  readonly provider: string
  readonly model: string
  release(): void
}

/** Tool definition in Anthropic schema format. */
export interface MiniHelixToolDef {
  name: string
  description: string
  input_schema: Record<string, unknown>
}

/** Result of executing a mini-Helix tool handler. */
export interface MiniHelixToolResult {
  content: string
  done?: boolean
  pause?: boolean
  metadata?: Record<string, unknown>
}

export type MiniHelixToolHandler = (
  args: Record<string, unknown>,
) => MiniHelixToolResult | Promise<MiniHelixToolResult>

/** Complete tool package: definition + handler. */
export interface MiniHelixTool {
  def: MiniHelixToolDef
  handler: MiniHelixToolHandler
}

export type MiniHelixConsumer = 'corpus' | 'brainstem'

/** Configuration for a mini-Helix session. */
export interface MiniHelixConfig {
  consumer: MiniHelixConsumer
  systemPrompt: string
  sessionId: string
  constellationId: string
  maxIterationsPerCycle: number
  maxTokens: number
  cycleTimeoutMs: number
  modelTier: string
  modelName?: string
}

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
  iteration: number
  totalToolCalls: number
  totalLLMCalls: number
  totalTokens: number
  completedCycles: number
  currentCycleDurationMs: number
  totalDurationMs: number
}

export interface MiniHelixResult {
  summary: string
  status: MiniHelixStatus
  toolCalls: number
  llmCalls: number
  tokenUsage: { input: number; output: number; total: number }
  cycles: number
  durationMs: number
}

/** The mini-Helix session interface. */
export interface MiniHelixSession {
  run(userMessage?: string): Promise<MiniHelixResult>
  cancel(): void
  pause(): void
  resume(): void
  shutdown(): Promise<void>
  getProgress(): MiniHelixProgress
  getStatus(): MiniHelixStatus
  updateSystemPrompt(prompt: string): void
  injectMessage(message: { role: string; content: unknown }): void
}

/** Dependencies for creating a mini-Helix session. */
export interface MiniHelixDeps {
  logger: ILogger
  eventBus?: IEventBus
  handleFactory: (config: { tier: string; purpose: string; sessionId: string }) => Promise<ModelHandle>
}

/**
 * Create a mini-Helix session with the given tools and configuration.
 *
 * @param tools - Purpose-built tool set (Corpus: ~18 tools, Brainstem: 8 tools)
 * @param config - Session configuration (merged with consumer defaults)
 * @param deps - Dependencies (logger, eventBus, handleFactory)
 */
export function createMiniHelixSession(
  tools: MiniHelixTool[],
  config: MiniHelixConfig,
  deps: MiniHelixDeps,
): MiniHelixSession {
  throw new Error('not connected (lands at P3 @cassicore/mini-helix)')
}
