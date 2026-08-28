/**
 * Coordination store-port for the Mnemic Field (P4 — propose only, NO hook implementation).
 *
 * The overhaul session plans to re-wire Mnemic Field's SQLite/LMDB as a journal
 * with MindFieldEncoder-style hooks at store/update/delete/connect/spike/
 * consolidate. Per the agreed boundary-first default (CASSI-MIND-PLAN §7), THIS
 * package lands first and the overhaul session adds its journal hooks BEHIND
 * this port LATER — without touching `MnemicField` internals.
 *
 * The default implementation is the current MnemicField DB-backed store (SQLite
 * + LMDB behind it). The `onWrite` observer seam is a transactional write
 * observer intended as the future MindFieldEncoder hook target; it is left
 * UNOCCUPIED in P4. Do not wire it to anything until the overhaul session
 * provides the encoder.
 */
import type {
  Engram,
  EngramCreate,
  EngramUpdate,
  MnemicSynapse,
  SynapseCreate,
  SpikeCreate,
  ActivationSpike,
} from '../types.js'
import type { ConsolidationOptions, ConsolidationResult } from '../consolidation.js'

/** The MnemicField store surface — default impl = the current DB-backed store. */
export interface MnemicFieldStore {
  store(input: EngramCreate): Engram
  get(id: string): Engram | null
  update(id: string, update: EngramUpdate): Engram | null
  delete(id: string): boolean
  connect(input: SynapseCreate): MnemicSynapse
  disconnect(sourceId: string, targetId: string, edgeType: string): boolean
  spike(input: SpikeCreate): ActivationSpike
  consolidate(options?: ConsolidationOptions): Promise<ConsolidationResult>

  /**
   * Transactional write observer seam — the future MindFieldEncoder hook target.
   * P4 ships the interface + default; the journal hooks are the overhaul
   * session's follow-up. Leave UNOCCUPIED until then.
   */
  onWrite?: (op: 'store' | 'update' | 'delete' | 'connect' | 'disconnect' | 'spike', record: unknown) => void
}
