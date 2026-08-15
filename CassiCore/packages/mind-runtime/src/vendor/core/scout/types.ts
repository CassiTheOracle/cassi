/**
 * Scout Module Types
 *
 * Types for the pre-turn search agent that gathers context before the main
 * model processes each turn. The scout uses a cheap/fast model with read-only
 * tools to find relevant code, memory, and documentation, then injects the
 * results so the main model starts informed.
 */

import type { ToolCall, ToolResult } from '@cassicore/tools'

// Configuration

export interface ScoutConfig {
  /** Enable the Scout module */
  enabled: boolean

  /** LLM provider for the scout (e.g., 'github-copilot') */
  providerId: string

  /** Model name (e.g., 'gpt-5-mini') */
  model: string

  /** Temperature for scout inference (lower = more deterministic) */
  temperature: number

  /** Max output tokens per scout inference call */
  maxTokens: number

  /** Max tool call rounds per turn (each round = one LLM call that may use tools) */
  maxToolRounds: number

  /** Wall time limit for the entire scout phase (ms) */
  timeoutMs: number

  /** Max characters of context to inject into the main model's turn */
  maxContextChars: number

  /** Number of recent conversation messages to show the scout (for context) */
  historyTailSize: number

  /** Enable skip heuristic (avoid scouting on trivial messages) */
  skipHeuristic: boolean

  /** Timeout per individual tool execution (ms) */
  toolTimeoutMs: number

  /** Allowed tool names (supports MCP prefix matching) */
  allowedTools: string[]

  /** Minimum scout result length to inject (chars) — skip injection for empty results */
  minResultLength: number
}

// Scout Execution Results

export interface ScoutToolExecution {
  /** Tool call sent to executor */
  call: ToolCall

  /** Result from executor */
  result: ToolResult

  /** Time taken to execute (ms) */
  durationMs: number
}

export interface ScoutResult {
  /** Whether the scout ran or was skipped */
  status: 'completed' | 'skipped' | 'error' | 'timeout'

  /** The gathered context summary (to inject into the main model) */
  context: string

  /** Individual tool executions performed */
  toolExecutions: ScoutToolExecution[]

  /** Total duration of the scout phase (ms) */
  durationMs: number

  /** Reason for skipping (if status === 'skipped') */
  skipReason?: string

  /** Error message (if status === 'error') */
  error?: string

  /** Number of LLM inference rounds used */
  roundsUsed: number

  /** Total tokens consumed by the scout */
  tokensUsed: number
}

// Scout Cache

export interface ScoutCacheEntry {
  /** The message content that was scouted */
  messageHash: string

  /** Cached scout result */
  result: ScoutResult

  /** When this entry was cached */
  cachedAt: number

  /** TTL for this entry (ms) */
  ttlMs: number
}
