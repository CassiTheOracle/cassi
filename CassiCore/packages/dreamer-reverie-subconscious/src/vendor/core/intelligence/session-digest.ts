/**
 * VENDORED TYPE STUB — mirrors `core/intelligence/session-digest.js` surface
 * (`SessionDigestStore`, `SessionDigest`, `DigestOptions`). Subconscious only
 * holds/references the injected store by type. Re-point to its owning package
 * at P7 (§P5b table §A2.2 / Open Flag 3). Type-only — no runtime impl.
 */

/** A session digest summary. */
export interface SessionDigest {
  sessionId: string
  summary: string
  siblingBlocks: string[]
  updatedAt: string
  [key: string]: unknown
}

/** Options for composing a session digest. */
export interface DigestOptions {
  maxDepth?: number
  maxSiblings?: number
  [key: string]: unknown
}

/**
 * Faithful `SessionDigestStore` surface — subconscious only holds the injected
 * store by type; an open index signature covers the broader class.
 */
export interface SessionDigestStore {
  [key: string]: unknown
}
