/**
 * VENDORED TYPE STUB — mirrors `context-distiller.js` `ContextDistiller`
 * surface. Helix calls `distill()` during Phase Zero context distillation.
 * Self-contained: supporting opts/result types inlined locally.
 */
import type { ILogger, Message } from '@cassicore/foundation'

export interface DistillContextOpts {
  /** The goal for the spawned agent/team */
  goal: string
  /** Explicit context from the caller */
  context?: string
  /** Session ID to pull conversation history from the prompt log */
  parentSessionId?: string
  /** Pre-fetched conversation history (alternative to parentSessionId) */
  parentHistory?: Message[]
  /** Max tokens for the distilled context block (default: 2000) */
  tokenBudget?: number
  /** Session ID for budget scoping of the LLM distillation call */
  sessionId?: string
  /** Job ID for model directive routing */
  jobId?: string
  /** MCP tool name that triggered the spawn (e.g., 'flux_team'). */
  spawnToolName?: string
  /** Artifact namespace for file sharing context injection. */
  artifactNamespace?: string
}

export interface DistilledContext {
  /** Goal with context prepended (combined single string) */
  enrichedGoal: string
  /** Just the distilled context block (no goal) — for callers that keep goal separate */
  distilledContext: string
  /** Individual sections for inspection/logging */
  sections: {
    recentExchange?: string
    plan?: string
    background?: string
    memoryContext?: string
    fileArtifacts?: string
  }
  /** Estimated tokens in the injected context (not counting goal) */
  contextTokenEstimate: number
  /** Time taken for distillation in ms */
  durationMs: number
}

export interface ContextDistiller {
  distill(opts: DistillContextOpts): Promise<DistilledContext>
  [key: string]: unknown
}
