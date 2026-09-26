/**
 * ConstellationLiveState + ConstellationRegistry.
 *
 * Tracks running Constellations so other subsystems (meditation, orchestrator,
 * admin API) can observe live Corpus tree state.
 *
 * NOTE: The InjectionSource path that used to surface Corpus state directly
 * into the main session's turn context has been deleted along with the
 * InjectionAggregator. If/when re-introduced, it should publish through
 * GlobalWorkspace/Thalamus instead.
 */

import type { ICorpusTree, CorpusTreeSnapshot, CrossHelixPattern, CorpusIntervention, BranchHealthStatus, ExternalCorpusState, ExternalCorpusSnapshot, CorpusDirective } from './corpus-types.js'
import type { TopologySnapshot } from './topology/topology-types.js'


/** Minimal interface for a running Constellation's live state */
export interface ConstellationLiveState {
  constellationId: string
  goal: string
  getTreeSnapshot(): CorpusTreeSnapshot
  getCrossPatterns(): CrossHelixPattern[]
  getInterventions(): CorpusIntervention[]
  getBranchAssessments(): Array<{ helixId: string; status: BranchHealthStatus; rollingScore: number; dominantPattern: string }>

  /** Live CorpusTree reference for real-time observation (e.g. MnemicBridge polling). */
  getTree?(): ICorpusTree

  /** Live topology snapshot — positions, links, clusters. Undefined if topology is disabled. */
  getTopologySnapshot?(): TopologySnapshot | undefined

  // External Corpus Protocol — optional, present when Corpus is wired
  corpus?: {
    assume(agentId: string, heartbeatTimeoutMs?: number): { assumed: boolean; snapshot: ExternalCorpusSnapshot | null; error?: string }
    release(reason?: string): { released: boolean; error?: string }
    isExternallyAssumed(): boolean
    getExternalState(): ExternalCorpusState
    getExternalSnapshot(): ExternalCorpusSnapshot
    getLocusSnapshot(): import('./locus/locus-types.js').LocusSnapshot | undefined
    getLocusMemories(): import('./locus/memory-types.js').LocusMemoryEntry[] | undefined
    externalDirective(directive: Omit<CorpusDirective, 'timestamp'>): { sent: boolean; error?: string }
    externalSpawnDecide(requestId: string, approved: boolean, reason: string, modifiedGoal?: string): { decided: boolean; error?: string }
    externalSynthesis(content: string, priority?: number, tags?: string[]): { posted: boolean; error?: string }
  }
}


/**
 * Registry of active Constellations.
 * The admin API registers/unregisters Constellations as they start/stop.
 */
export class ConstellationRegistry {
  private active = new Map<string, ConstellationLiveState>()

  register(state: ConstellationLiveState): void {
    this.active.set(state.constellationId, state)
  }

  unregister(constellationId: string): void {
    this.active.delete(constellationId)
  }

  getAll(): ConstellationLiveState[] {
    return [...this.active.values()]
  }

  get size(): number {
    return this.active.size
  }
}
