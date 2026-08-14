/**
 * VENDORED TYPE STUB — mirrors `mnemic-field/cortex.js` (CassiCore) type surface.
 * The full `Cortex` runtime is a heavier CassiCore module (SQLite-backed); the type surface
 * used by the vendored `graph-attn-propagator.ts` and constellation code is declared here.
 */
import type { Engram, MnemicSynapse, SpikeCreate, ActivationSpike } from './types.js'
import type Database from 'better-sqlite3'

export interface OrphanDistribution {
  byNodeType: Array<{ nodeType: string; count: number }>
  byProvenance: Array<{ provenance: string; count: number }>
  total: number
}

export interface OrphanSample {
  id: string
  content: string
  nodeType: string
  potentiation: number
  tags: string
  provenance: string
}

export interface Cortex {
  getEngram(id: string): Engram | null
  recordSpike(input: SpikeCreate): ActivationSpike
  getNeighborSynapses(engramId: string, direction?: 'outgoing' | 'incoming' | 'all'): MnemicSynapse[]
  orphanDistribution(): OrphanDistribution
  countMissingEmbeddings(): number
  getDatabase(): Database.Database
  sampleOrphans(limit?: number): OrphanSample[]
  orphanCount(): number
  orphanTagDistribution(limit?: number): Array<{ tag: string; count: number }>
  assignToNucleus(engramIds: string[], nucleusId: string): number
  [key: string]: unknown
}

export type { Engram, MnemicSynapse, SpikeCreate, ActivationSpike } from './types.js'
