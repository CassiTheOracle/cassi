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

export interface RegionConfig {
  capacity: number
  defaultDecayRate: number
  description?: string
}

export const SYSTEM_REGIONS: Record<string, RegionConfig> = {
  sensory:     { capacity: 100, defaultDecayRate: 0.3,  description: 'Raw observations and input' },
  association: { capacity: 50,  defaultDecayRate: 0.1,  description: 'Pattern recognition and synthesis' },
  executive:   { capacity: 15,  defaultDecayRate: 0.05, description: 'Active goals and decisions' },
  motor:       { capacity: 75,  defaultDecayRate: 0.15, description: 'Actions planned and executed' },
  limbic:      { capacity: 30,  defaultDecayRate: 0.1,  description: 'Threat detection and concerns' },
  monitor:     { capacity: 20,  defaultDecayRate: 0.1,  description: 'Self-observation and metacognition' },
}

export const SYSTEM_REGION_NAMES = Object.keys(SYSTEM_REGIONS)

export interface TractFilter {
  types?: SignalType[]
  minSalience?: number
  tags?: string[]
  minActivation?: number
}

export interface TractTransform {
  activationScale?: number
  addTags?: string[]
  typeOverride?: SignalType
}

export interface TractConfig {
  strength?: number
  filter?: TractFilter
  transform?: TractTransform
  refractory?: number
}

export interface Tract {
  id: string
  from: string
  to: string
  strength: number
  filter?: TractFilter
  transform?: TractTransform
  refractory: number
  lastFired: number
}

export const SYSTEM_TRACTS: Array<{ from: string; to: string; config: TractConfig }> = [
  {
    from: 'sensory', to: 'association',
    config: { strength: 0.8, filter: { minSalience: 0.3 } },
  },
  {
    from: 'association', to: 'executive',
    config: { strength: 0.7, filter: { minSalience: 0.5 } },
  },
  {
    from: 'executive', to: 'motor',
    config: { strength: 0.9, filter: { types: ['decision'] } },
  },
  {
    from: 'motor', to: 'sensory',
    config: { strength: 0.5, filter: { types: ['action'] } },
  },
  {
    from: 'limbic', to: 'executive',
    config: { strength: 0.85, filter: { minSalience: 0.6 } },
  },
  {
    from: 'monitor', to: 'limbic',
    config: { strength: 0.7, filter: { types: ['anomaly'] } },
  },
  {
    from: 'association', to: 'limbic',
    config: { strength: 0.6, filter: { types: ['concern'] } },
  },
]

export const ACTIVATION_DEFAULTS = {
  attentionBoost: 0.15,
  activeThreshold: 0.3,
  fadingThreshold: 0.05,
  defaultDecayRate: 0.1,
  defaultSalience: 0.5,
  defaultConfidence: 0.5,
  defaultRefractory: 1000,
  tickIntervalMs: 30_000,
} as const

export const CONSOLIDATION_DEFAULTS = {
  salienceMin: 0.5,
  referenceCountMin: 3,
  bindingCountMin: 2,
} as const

export interface RegionInfo {
  name: string
  isSystem: boolean
  config: RegionConfig
  signalCount: number
  activeCount: number
}

export interface OscillationResult {
  decayed: number
  pruned: number
  consolidated: number
  bound: number
  durationMs: number
}

export interface RegionSnapshot {
  name: string
  config: RegionConfig
  signals: CorticalSignal[]
}

export interface CorticalFieldSnapshot {
  regions: RegionSnapshot[]
  tracts: Tract[]
  timestamp: number
}

export type ConsolidationCallback = (signal: CorticalSignal) => void

export interface CorticalFieldConfig {
  tickIntervalMs?: number
  onConsolidate?: ConsolidationCallback
}

export interface CortexSessionConfig {
  workingMemoryCapacity?: number
}

export const SESSION_DEFAULTS = {
  workingMemoryCapacity: 7,
} as const

export interface CortexSessionSnapshot {
  sessionId: string
  workingMemory: string[]
  timestamp: number
}

export interface CommissureConfig {
  maxPropagationsPerSecond?: number
}

export const COMMISSURE_DEFAULTS = {
  maxPropagationsPerSecond: 10,
} as const
