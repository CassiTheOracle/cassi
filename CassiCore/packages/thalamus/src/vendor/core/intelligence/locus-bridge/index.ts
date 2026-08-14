/**
 * VENDORED — faithful type surface of `core/intelligence/locus-bridge/index.ts`.
 * Consumed by @cassicore/thalamus index.ts as `LocusBridge` (type-only).
 *
 * Self-contained stub: declares the `LocusBridge` class type with the focus-slot
 * read surface used by the consumer. Re-point to `@cassicore/lamina` when that
 * package lands (P5 repoint log).
 */
import type { BridgeFocus } from './types.js'

/** Attentional workspace bridge — sparks are scored against focus slots (type surface). */
export declare class LocusBridge {
  /** Current focus slots (sparks that won workspace positions). */
  getFoci(): BridgeFocus[]
}
