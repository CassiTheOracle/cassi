/**
 * VENDORED TYPE STUB — mirrors `cortex/index.js`. Surface: CorticalField + the
 * affect/signal surface the meditation runner reads.
 */
import type { Affect } from '../mnemic-field/types.js'

export interface CorticalField {
  getAffectState(): Affect | null
  signal(region: string, signal: Record<string, unknown>): unknown
  [key: string]: unknown
}
