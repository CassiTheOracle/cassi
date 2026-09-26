/**
 * VENDORED TYPE STUB — mirrors `context-repo/projection.js` (CassiCore) type surface.
 * `EngramLike` is the structural engram shape a ContextRepo projection consumes.
 */
export interface EngramLike {
  id: string
  content: string
  potentiation?: number
  createdAt?: number
  type?: string
  [key: string]: unknown
}

export type Projection = unknown
