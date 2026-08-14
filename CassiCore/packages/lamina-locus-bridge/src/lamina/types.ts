/**
 * Lamina types.
 *
 * A Lamina is a labeled, char-limited, tool-editable memory block — the
 * "small, pinned, intentionally-edited working context" primitive that sits
 * alongside Cortex (ephemeral) and Mnemic Field (topological).
 *
 * Naming follows the brain-anatomy convention (cortical laminae — labeled,
 * layered, addressable sheets). A Lamina is NOT an engram; it is structured,
 * label-addressable, and writable by tools with optimistic concurrency
 * control via content_hash (CAS).
 */

import type { Provenance } from '../../vendor/core/runtime/audit/index.js'

/** Optional scope discriminator — null means "global to all sessions". */
export type LaminaScope =
  | { kind: 'global' }
  | { kind: 'session'; sessionId: string }
  | { kind: 'channel'; channel: string }
  | { kind: 'agent'; agentId: string }

export interface Lamina {
  id: string
  /** Stable label, e.g. 'active-task', 'user-model', 'open-hypotheses' */
  label: string
  content: string
  /** SHA-256 of `content`. Used as the CAS token for optimistic edits. */
  contentHash: string
  /** Maximum byte length for the content. Edits that exceed reject. */
  charLimit: number
  /** Free-form description of what this lamina is for. */
  description: string | null
  /** Owner — primary, reverie, pineal, helix, meditation, etc. */
  owner: string
  /** True = only the owner may rethink (replace whole content). Append/replace are still tool-allowed. */
  ownerExclusive: boolean
  /** When set, only the owner can do ANY mutation. Used for Pineal mirror laminae. */
  readOnly: boolean
  scope: LaminaScope
  tags: string[]
  /** Provenance of the most recent mutation. */
  lastWriteProvenance: Provenance | null
  pinned: boolean
  createdAt: string
  updatedAt: string
  version: number
}

export interface LaminaCreate {
  label: string
  content?: string
  charLimit?: number
  description?: string | null
  owner: string
  ownerExclusive?: boolean
  readOnly?: boolean
  scope?: LaminaScope
  tags?: string[]
  pinned?: boolean
}

export interface LaminaReplace {
  /** CAS — must match current contentHash, else throws. Pass `null` to force-overwrite (caller accepts data loss). */
  expectedHash: string | null
  content: string
  reason?: string
  /** When true, bypass owner-exclusive guard (pass through after auth check). */
  asOwner?: boolean
}

export interface LaminaAppend {
  content: string
  /** Optional separator inserted only when current content is non-empty. Default: '\n'. */
  separator?: string
  reason?: string
}

export interface LaminaRethink {
  /** Replace the whole content. Owner-exclusive on owner-exclusive laminae. */
  content: string
  reason: string
}

export interface LaminaQuery {
  owner?: string
  scope?: LaminaScope
  tags?: string[]
  pinned?: boolean
  label?: string
  /** When set with kind=session, also return globals + matching session laminae. */
  matchScope?: LaminaScope
  limit?: number
}

/** Structured error thrown on CAS conflict — the agent can re-read and retry. */
export class LaminaCasConflict extends Error {
  readonly code = 'LAMINA_CAS_CONFLICT' as const
  constructor(
    public readonly label: string,
    public readonly currentHash: string,
    public readonly expectedHash: string | null,
    public readonly currentContent: string,
  ) {
    super(`CAS conflict on lamina '${label}': expected ${expectedHash ?? 'null'}, got ${currentHash}`)
  }
}

/** Structured error thrown when a write would exceed charLimit. */
export class LaminaOverflow extends Error {
  readonly code = 'LAMINA_OVERFLOW' as const
  constructor(
    public readonly label: string,
    public readonly attemptedSize: number,
    public readonly limit: number,
  ) {
    super(`Lamina '${label}' overflow: attempted ${attemptedSize} bytes, limit ${limit}`)
  }
}

/** Structured error thrown when an unauthorized agent tries to mutate. */
export class LaminaAuthorityError extends Error {
  readonly code = 'LAMINA_AUTHORITY' as const
  constructor(
    public readonly label: string,
    public readonly action: string,
    public readonly callerAgentId: string,
    public readonly ownerAgentId: string,
  ) {
    super(`Agent '${callerAgentId}' lacks authority to ${action} lamina '${label}' (owner: ${ownerAgentId})`)
  }
}

export const DEFAULT_CHAR_LIMIT = 8_000
