/**
 * VENDORED TYPE STUB — mirrors `core/intelligence/cortex/index.js` `CorticalField`
 * surface consumed by subconscious (`signal` at runtime on an injected field;
 * the field itself is host-wired). Re-point to `@cassicore/cortex` at P5-A
 * (§P5b table §A2.2). Type-only — no runtime impl reproduced here.
 */

/** Shape of a cortical signal the subconscious writes via `field.signal(region, input)`. */
export interface SignalInput {
  type: string
  content: string
  author?: string
  sessionId?: string
  salience?: number
  valence?: number
  tags?: string[]
  [key: string]: unknown
}

/** Result of a cortical signal write. */
export interface CorticalSignal {
  id: string
  region: string
  type: string
  content: string
  author: string
  salience: number
  createdAt: string
  [key: string]: unknown
}

/**
 * Faithful `CorticalField` surface — the method subconscious consumes
 * (signal) plus minimal structural compatibility for the broader field class.
 */
export interface CorticalField {
  signal(regionName: string, input: SignalInput): CorticalSignal
  [key: string]: unknown
}
