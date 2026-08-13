/**
 * VENDORED TYPE STUB — mirrors `lamina/index.js`. Surface: LaminaField + the ensure/rethink
 * read/replace method surface the constellation helix-goal-lamina code calls.
 */
export interface LaminaScope {
  kind: 'global' | 'session' | 'channel' | 'agent'
  sessionId?: string
  channel?: string
  agentId?: string
  [key: string]: unknown
}

export interface LaminaEnsureOpts {
  label: string
  description?: string
  owner?: string
  ownerExclusive?: boolean
  charLimit?: number
  content?: string
  scope?: LaminaScope
  [key: string]: unknown
}

export interface LaminaContentPatch {
  content: string
  reason?: string
  expectedHash?: string
  [key: string]: unknown
}

export interface LaminaReadResult {
  content: string
  contentHash?: string
  [key: string]: unknown
}

export interface LaminaField {
  ensure(opts: LaminaEnsureOpts, owner?: string): unknown
  rethink(label: string, patch: LaminaContentPatch, owner?: string, scope?: LaminaScope): unknown
  read(label: string, scope?: LaminaScope): LaminaReadResult | null
  replace(label: string, patch: LaminaContentPatch, owner?: string, scope?: LaminaScope): unknown
  [key: string]: unknown
}
