/**
 * Memory Bridge — connects LARQL-style residual stream injection with Mnemic Field.
 *
 * Architecture: Memory-Augmented Transformer
 *   residual[L] = residual[L-1] + attn_delta + ffn_delta + memory_delta
 *
 * Key insight from LARQL research: Phase transition at L24-L26 where answer crystallizes.
 * Memory injection complements model knowledge at this critical point.
 *
 * Components:
 *   - MemoryDeltaInjector: Main integration class
 *   - LuminalProjectionEngine: Projects memories to hidden space
 *   - PortalBridge: Connects LARQL features to Mnemic Field engrams
 *   - ResonantAffectEngine: Derives emotional affect from model/memory resonance
 */

export { MemoryDeltaInjector } from './memory-delta-injector.js'
export { LuminalProjectionEngine } from './luminal-projection.js'
export { PortalBridge, PORTAL_BRIDGE_DEFAULTS } from './portal-bridge.js'
export { ResonantAffectEngine, RESONANT_AFFECT_DEFAULTS } from './resonant-affect.js'
export { DreamEngine, DREAM_DEFAULTS } from './dream-engine.js'

export type {
  MemoryInjectionConfig,
  MemoryDelta,
  MemoryContribution,
  MemoryKindlingResult,
  BoundaryResidual,
  FeatureEngramPortal,
  UnifiedTraceNode,
  UnifiedTrace,
  ProjectionMatrix,
  ProjectionGradientRequest,
  MemoryBridgeStats,
  PortalDiscoveryConfig,
} from './types.js'

export type {
  ResonantAffectSignal,
  ResonanceMeasurements,
  ResonantAffectConfig,
} from './resonant-affect.js'

export type {
  DreamResult,
  DreamDiscovery,
  DreamConfig,
  VindexGateKnnProvider,
} from './dream-engine.js'

export { MEMORY_INJECTION_DEFAULTS } from './types.js'

/**
 * Create a memory bridge instance with standard configuration.
 *
 * Usage:
 *   const bridge = createMemoryBridge(mnemicField, 768, 2560, logger)
 *   const result = bridge.kindleForInjection("What did we decide about migrations?")
 *   const delta = bridge.getDeltaForLayer(result, 25)
 *   // Inject delta.vector into residual stream
 */
import type { MnemicField } from '@cassicore/mnemic-field'
import type { ILogger } from '@cassicore/foundation'
import { MemoryDeltaInjector } from './memory-delta-injector.js'
import type { MemoryInjectionConfig } from './types.js'

export function createMemoryBridge(
  mnemicField: MnemicField,
  embeddingDim: number,
  hiddenDim: number,
  logger: ILogger,
  config?: Partial<MemoryInjectionConfig>,
): MemoryDeltaInjector {
  return new MemoryDeltaInjector(
    mnemicField,
    embeddingDim,
    hiddenDim,
    logger,
    config,
  )
}