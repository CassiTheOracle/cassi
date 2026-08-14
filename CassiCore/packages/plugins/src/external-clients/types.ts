/**
 * Shared types for external editor client integrations.
 *
 * These types define the contract between CassiCore and external
 * coding agents (OpenCode, Claude Code, Cursor, Windsurf, etc.)
 * for thalamus-based context curation.
 */

import type { CurationConfig, CurationMeta } from '../../intelligence/thalamus/types.js'

/** Lightweight message digest for index-only curation (preserves AI SDK types). */
export interface ExternalMessageDigest {
  index: number
  role: string
  text: string
  chars: number
  toolName?: string
  toolCallId?: string
  isToolResult?: boolean
}

/** Gap annotation for a span of messages omitted by curation. */
export interface CurationGap {
  start: number
  end: number
  count: number
  /** Human-readable summary of what was omitted. */
  summary: string
}

/** Result of index-only thalamus curation — tells the caller which messages to keep. */
export interface ExternalCurationResult {
  /** Indices of messages to keep (ascending order). */
  kept: number[]
  /** Gap annotations for omitted spans. */
  gaps: CurationGap[]
  /** System-level context strings to inject (from cognitive modules). */
  systemContext: string[]
  /** Estimated token count for curated context (chars / 4). Use for overflow detection. */
  estimatedTokens?: number
  /** Total character count of curated messages + system context. */
  estimatedChars?: number
  meta: CurationMeta & {
    /** Whether curation was actually applied (false = passthrough). */
    applied: boolean
  }
}

/** Configuration for external client curation requests. */
export interface ExternalCurateRequest {
  sessionId: string
  /** Lightweight digests — no full message objects cross the wire. */
  digests: ExternalMessageDigest[]
  /** The current user query for relevance scoring. */
  query: string
  /** Optional char budget override (computed from model context limit). */
  charBudget?: number
  /** Optional curation config overrides. */
  config?: Partial<CurationConfig>
  /** Client identifier (e.g., 'opencode', 'cursor'). */
  clientId?: string
}
