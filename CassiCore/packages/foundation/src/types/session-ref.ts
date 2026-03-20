/**
 * SessionRef — token-efficient hierarchical references into session history.
 *
 * Each session gets a short auto-assigned label (S0, S1, S2 …) stored in a
 * mapping table alongside the full session ID.  The compact ref format uses
 * the label instead of the session ID so agents can cite history cheaply.
 *
 * Format:  S{n}#M{msg}[.B{block}[.P{para}]]
 *
 * Examples:
 *   S0#M0           → session 0, message 0 (all blocks)
 *   S0#M1.B0        → session 0, message 1, block 0 (all paragraphs)
 *   S1#M3.B0.P2     → session 1, message 3, block 0, paragraph 2
 */


/** Parsed compact reference — uses the short label, NOT the session ID. */
export interface SessionRef {
  /** Short label, e.g. "S0", "S12". */
  label: string
  msgIdx: number
  blockIdx?: number
  paraIdx?: number
}

/** A single indexed entry from the session message history. */
export interface IndexEntry {
  /** Short label for compact citations. */
  label: string
  /** Full session ID (for internal lookups). */
  sessionId: string
  msgIdx: number
  role: 'user' | 'assistant' | 'system'
  blockIdx: number
  blockType: 'text' | 'tool_use' | 'tool_result'
  paraIdx: number | null
  content: string
  meta: Record<string, unknown> | null
  /** Pre-formatted compact ref string. */
  ref: string
}

/** Search result from the session index FTS. */
export interface IndexSearchResult {
  entry: IndexEntry
  /** FTS rank score (lower = more relevant). */
  rank: number
  /**
   * Character offset of the first match within entry.content.
   * Derived from SQLite FTS5 highlight() — used for centered display windowing
   * so long tool_result / text blocks show the relevant portion rather than
   * the start of the content.
   */
  matchOffset?: number
}

/** Stats for a session's index. */
export interface IndexStats {
  label: string
  sessionId: string
  messageCount: number
  blockCount: number
  paragraphCount: number
}


/**
 * Regex for the compact ref format:
 *   S{n}#M{msg}[.B{block}[.P{para}]]
 *
 * Capture groups:
 *   1 = label number  (e.g. "0", "12")
 *   2 = msgIdx
 *   3 = "B" sentinel  (optional)
 *   4 = blockIdx      (optional)
 *   5 = "P" sentinel  (optional)
 *   6 = paraIdx       (optional)
 */
const REF_RE = /^S(\d+)#M(\d+)(?:\.(B)(\d+)(?:\.(P)(\d+))?)?$/

/**
 * Parse a compact session ref string into its components.
 *
 * @throws {Error} if the ref format is invalid
 */
export function parseSessionRef(ref: string): SessionRef {
  const m = ref.match(REF_RE)
  if (!m) {
    throw new Error(`Invalid session ref: "${ref}". Expected format: S{n}#M{n}[.B{n}[.P{n}]]`)
  }

  const result: SessionRef = {
    label: `S${m[1]}`,
    msgIdx: parseInt(m[2], 10),
  }

  if (m[3] === 'B') {
    result.blockIdx = parseInt(m[4], 10)
  }

  if (m[5] === 'P') {
    if (result.blockIdx === undefined) {
      throw new Error(`Invalid session ref: "${ref}". Cannot specify P{n} without B{n}`)
    }
    result.paraIdx = parseInt(m[6], 10)
  }

  return result
}

/**
 * Format a SessionRef into the compact string representation.
 *
 * @throws {Error} if paraIdx is set without blockIdx
 */
export function formatSessionRef(ref: SessionRef): string {
  if (ref.paraIdx !== undefined && ref.blockIdx === undefined) {
    throw new Error('Cannot format SessionRef with paraIdx but no blockIdx')
  }

  let s = `${ref.label}#M${ref.msgIdx}`
  if (ref.blockIdx !== undefined) {
    s += `.B${ref.blockIdx}`
  }
  if (ref.paraIdx !== undefined) {
    s += `.P${ref.paraIdx}`
  }
  return s
}
