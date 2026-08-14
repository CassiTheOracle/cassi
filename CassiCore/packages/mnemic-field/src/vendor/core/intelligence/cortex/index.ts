/**
 * TYPE STUB — core/intelligence/cortex/index.ts.
 *
 * Faithful type surface for the symbol mnemic-field consumes: `CorticalField`
 * (type-only; index.ts stores it and calls `.signal('sensory', …)`). Re-point to
 * the owning package at P5 via the repoint log.
 */
import type { ILogger } from '@cassicore/foundation'

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

export interface SignalInput {
  type: SignalType
  content: string
  structured?: Record<string, unknown>
  author: string
  source?: string
  sessionId?: string
  salience?: number
  valence?: number
  confidence?: number
  tags?: string[]
  sourceSignals?: string[]
  decayRate?: number
}

export interface CorticalFieldConfig {
  capacity?: number
  defaultDecayRate?: number
}

/**
 * CorticalField — active cortices / signal regions.
 * (Type stub only; the runtime impl lives in the P5-owned cortex path.)
 */
export declare class CorticalField {
  constructor(logger: ILogger, config?: CorticalFieldConfig)
  signal(regionName: string, input: SignalInput): CorticalSignal
}
