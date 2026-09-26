/**
 * TYPE STUB — Dream Engine (core/intelligence/memory-bridge/dream-engine.ts).
 *
 * Faithful type surface for the symbols mnemic-field consumes: `DreamEngine`
 * (type-only) + `DreamResult`. Re-point to the owning package at P5 via the
 * repoint log; no runtime implementation is reproduced here (the consumers
 * import it as a type only).
 */
import type { ILogger } from '@cassicore/foundation'

/** Result of a dreaming cycle. */
export interface DreamResult {
  /** Engrams selected as dream seeds */
  seedCount: number
  /** Feature fingerprints computed */
  fingerprintsComputed: number
  /** Engram pairs with significant feature overlap */
  discoveries: Array<{ sourceId: string; targetId: string; sharedFeatureCount: number }>
  /** Synapses actually created (after dedup with existing) */
  synapsesCreated: number
  /** Total duration in ms */
  durationMs: number
}

/**
 * DreamEngine — discovers hidden connections during consolidation.
 * (Type stub only; the runtime impl lives in the P5-owned memory-bridge path.)
 */
export declare class DreamEngine {
  constructor(cortex: unknown, vindexProvider: unknown, logger: ILogger, config?: unknown)
  dream(): Promise<DreamResult>
}
