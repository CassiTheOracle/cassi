/**
 * Code Analysis Module — Barrel export
 *
 * New analysis capabilities inspired by Tempograph and SSP:
 *  - Dead code detection
 *  - Hotspot analysis (size × complexity × coupling)
 *  - Git cochange correlation
 *  - One-shot context assembly (prepare_context)
 *  - Task specificity scoring (adaptive context gating)
 *  - Context feedback tracking (Bayesian learning)
 *  - Schema introspection (self-documenting internal stores)
 *  - GitNexus auto-reindex bridge
 */

// Types
export type {
  DeadCodeResult, DeadCodeOptions,
  HotspotResult, HotspotOptions,
  CochangeResult, CochangeOptions,
  PreparedContext, PreparedFile, PrepareContextOptions,
  SpecificityScore, SpecificitySignal,
  ContextFeedbackRecord,
  DatabaseSchema, TableSchema, SchemaIntrospectionResult,
} from './types.js'

// Analyzers
export { analyzeDeadCode } from './dead-code-analyzer.js'
export { analyzeHotspots } from './hotspot-analyzer.js'
export { analyzeCochange, invalidateCochangeCache } from './cochange-analyzer.js'
export { prepareContext, extractKeywords } from './context-assembler.js'
export { scoreSpecificity } from './specificity-scorer.js'
export { ContextFeedbackTracker } from './feedback-tracker.js'
export { introspectSchemas } from './schema-introspector.js'

// GitNexus bridge
export {
  isIndexFresh,
  ensureFreshIndex,
  reindex,
  withAutoReindex,
  invalidateStalenessCache,
} from './gitnexus-bridge.js'
