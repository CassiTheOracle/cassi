/**
 * VENDOR TYPE STUB — `core/intelligence/mnemic-field/edge-relators.ts`
 *
 * Type-only placeholder for the `PhrasePrototypeSet` surface consumed by the P1 live-set
 * (`phrases/phrase-prototypes.ts`). Self-contained; builtin types only; no runtime.
 * Re-pointed to `@cassicore/mnemic-field` at P4.
 */

/** A set of phrase prototypes keyed by relation label. */
export interface PhrasePrototypeSet {
  phrases: Record<string, string[]>
  labels: string[]
}
