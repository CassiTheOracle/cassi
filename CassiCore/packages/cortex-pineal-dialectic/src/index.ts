/**
 * @cassicore/cortex-pineal-dialectic — package barrel.
 *
 * Re-exports the three mirrored subdir surfaces: the six-region cortical field,
 * the pineal identity module, and the dialectic reasoning system (P5-A table
 * §3/§C P7 note). Preserves every export name the host and inbound consumers
 * typecheck against.
 */

// Cortex — six-region field + barrel
export { CorticalField } from './cortex/index.js'
export type { CortexStats, SignalSearchOpts, OscillationHistoryEntry } from './cortex/index.js'
export { Region, TractEngine, CortexSession, Commissure } from './cortex/index.js'
export { createConsolidationBridge, signalToEngram } from './cortex/mnemic-bridge.js'
export type { ConsolidationTarget } from './cortex/mnemic-bridge.js'
export { oscillate } from './cortex/dynamics.js'
export {
  createSignal, computeActivation, attendSignal,
  transitionState, meetsConsolidationCriteria, deriveSignal,
} from './cortex/signal.js'
export type {
  CorticalSignal, SignalInput, SignalType, SignalState,
  RegionConfig, RegionInfo, Tract, TractConfig, TractFilter, TractTransform,
  CorticalFieldConfig, CorticalFieldSnapshot,
  CortexSessionConfig, CortexSessionSnapshot, CommissureConfig,
  OscillationResult, ConsolidationCallback,
} from './cortex/types.js'
export {
  SYSTEM_REGIONS, SYSTEM_TRACTS, ACTIVATION_DEFAULTS,
  CONSOLIDATION_DEFAULTS, SESSION_DEFAULTS, COMMISSURE_DEFAULTS,
  SIGNAL_TYPES,
} from './cortex/types.js'
export type { Affect, AffectState } from './cortex/types.js'

// Pineal — registry-discovered identity module + facet/skill surface
export { PinealModule, buildPinealMetadata } from './pineal/index.js'
export { FacetManager } from './pineal/facet.js'
export { PinealAssembler } from './pineal/assembler.js'
export type {
  Facet, FacetInput, FacetUpdate, FacetQuery, Domain, DomainStats,
  PinealSnapshot, SkillSummary,
} from './pineal/types.js'
export {
  DOMAINS, DOMAIN_INITIAL_CONVICTION, REINFORCEMENT_RATE,
  CHANNEL_PREFIXES, channelFromSessionId,
} from './pineal/types.js'

// Dialectic — explicit DialecticSystem + voice factories
export { DialecticSystem, createDialecticSystem } from './dialectic/index.js'
export { ConsolidatedDialecticProcessor, createConsolidatedDialecticProcessor } from './dialectic/consolidated-processor.js'
export { DialecticEngine, createDialecticEngine } from './dialectic/engine.js'
export { YangObserver, createYangObserver } from './dialectic/yang.js'
export { YinObserver, createYinObserver } from './dialectic/yin.js'
export { Serenity, createSerenity } from './dialectic/serenity.js'
export { formatDialecticAsThoughts } from './dialectic/thought-formatter.js'
