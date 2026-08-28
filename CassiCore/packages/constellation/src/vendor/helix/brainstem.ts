/**
 * VENDORED TYPE STUB — mirrors `helix/brainstem.js`. Surface: HelixBrainstem.
 * The full `HelixBrainstem` runtime class lives in the daemon; only the method surface
 * the constellation pipeline and cross-helix dialectic use is declared here.
 */
import type { WorkUnit } from './work-types.js'

export interface HelixBrainstem {
  onWorkUnit(wu: WorkUnit, iteration: number): void
  stop(): Promise<void> | void
  onCorpusDirective(directive: unknown): void
  [key: string]: unknown
}
