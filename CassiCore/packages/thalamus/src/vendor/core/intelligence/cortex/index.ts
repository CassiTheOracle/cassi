/**
 * VENDORED — temporary type surface of `core/intelligence/cortex/index.ts`.
 * Consumed by @cassicore/thalamus index.ts as `CorticalField` (type-only).
 *
 * `CorticalField` is the six-region cortical field surface. Thalamus holds it as a
 * class type and calls a small read surface (`readActive`, `getAffectState`,
 * `getSession`). Only those members are declared here (faithful to the D: class).
 * Re-point to `@cassicore/cortex-pineal-dialectic` when that package lands (P5-A turn 2).
 */
import type { Affect } from '@cassicore/mnemic-field'
import type { CorticalSignal } from './types.js'

/** A session's working-memory window (type surface). */
export interface CortexSession {
  /** Signals currently in session working memory. */
  getWorkingMemory(): CorticalSignal[]
}

/** The six-region cortical field surface (type surface). */
export declare class CorticalField {
  /** Read recently-active signals, optionally for a session. */
  readActive(opts?: { limit?: number; sessionId?: string }): CorticalSignal[]
  /** Current layered affect state, if a register is wired. */
  getAffectState(): Affect | undefined
  /** A session's working-memory window, if present. */
  getSession(sessionId: string): CortexSession | undefined
}
