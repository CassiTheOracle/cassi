/**
 * VENDORED TYPE STUB — mirrors `mnemic-field/self-model/self-model-field.js` (CassiCore).
 * Surface used by meditation/self-modeling-synthesis + the vendored runtime.
 */
import type { Engram, EngramType, FieldStats } from '../types.js'

export interface StoreOptions {
  tags?: string[]
  ttlMs?: number
  [key: string]: unknown
}

export interface PatternMetadata {
  category?: string
  occurrences?: string[]
  [key: string]: unknown
}

export interface WeaknessMetadata {
  [key: string]: unknown
}

export interface SelfModelField {
  stats(): FieldStats & { selfModelTypes: Record<string, number> }
  list(nodeType?: EngramType, limit?: number): Engram[]
  getDependencyGraph(): Array<{ module: Engram; dependsOn: Engram[] }>
  get(id: string): Engram | undefined
  update(id: string, patch: Partial<Engram> & Record<string, unknown>): Engram | null
  storePattern(name: string, description: string, metadata: PatternMetadata, options?: StoreOptions): Engram
  storeWeakness(name: string, description: string, metadata: WeaknessMetadata, options?: StoreOptions): Engram
  storePrinciple(name: string, description: string, options?: StoreOptions): Engram
  [key: string]: unknown
}
