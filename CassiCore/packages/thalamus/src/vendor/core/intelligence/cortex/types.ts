/**
 * VENDORED — temporary type surface of `core/intelligence/cortex/types.ts`.
 * Consumed by @cassicore/thalamus types.ts as `CorticalSignal`, `SignalType`,
 * `Affect` (type-only).
 *
 * `Affect` / `AffectState` are re-exported verbatim from
 * `@cassicore/mnemic-field` (the published P4 package), mirroring the D:
 * source (`export type { Affect, AffectState } from '../mnemic-field/types.js'`).
 * Re-point the whole file to `@cassicore/cortex-pineal-dialectic` when that
 * package lands (P5-A turn 2).
 */
import type { Affect, AffectState } from '@cassicore/mnemic-field'

export type { Affect, AffectState }

export const SIGNAL_TYPES = [
  'perception', 'association', 'concern', 'decision',
  'action', 'request', 'anomaly', 'insight',
] as const

export type SignalType = typeof SIGNAL_TYPES[number]

export type SignalState = 'active' | 'fading' | 'consolidated' | 'decayed'

export interface CorticalSignal {
  id: string
  region: string
  type: SignalType
  content: string
  structured?: Record<string, unknown>

  author: string
  source?: string
  sessionId?: string

  salience: number
  activation: number
  valence: number
  confidence: number

  tags: string[]
  bindings: string[]
  sourceSignals: string[]

  createdAt: number
  lastAttended: number
  decayRate: number
  state: SignalState
  consolidatedAt?: number
}
