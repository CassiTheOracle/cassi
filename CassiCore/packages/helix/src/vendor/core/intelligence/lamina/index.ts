/**
 * VENDORED TYPE STUB — mirrors `lamina/index.js` `LaminaField` surface (the
 * CAS-edited, tool-writable memory-block facade). Helix consumes `LaminaField`
 * as a type and reads/replaces labeled blocks. Structurally compatible with the
 * local `LaminaField` declared in the helix-goal-lamina vendor stub. The full
 * runtime class lives in the daemon.
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

/** CAS edit for `replace`/`rethink` — expected contentHash guards concurrent writers. */
export interface LaminaContentPatch {
  content: string
  reason?: string
  expectedHash?: string
  [key: string]: unknown
}

export interface LaminaReadResult {
  content: string
  contentHash: string
  [key: string]: unknown
}

export interface LaminaField {
  ensure(opts: LaminaEnsureOpts, owner?: string): unknown
  rethink(label: string, patch: LaminaContentPatch, owner?: string, scope?: LaminaScope): unknown
  read(label: string, scope?: LaminaScope): LaminaReadResult | undefined
  replace(label: string, patch: LaminaContentPatch | string, owner?: string, scope?: LaminaScope): unknown
  append(label: string, content: string, owner?: string, scope?: LaminaScope): unknown
  [key: string]: unknown
}
