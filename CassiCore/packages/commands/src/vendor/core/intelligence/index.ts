/**
 * P7-DEFERRED type-only vendor — core/intelligence/index.ts IntelligenceLayer.
 *
 * The full `core/intelligence/index.ts` `IntelligenceLayer` aggregate interface
 * (the daemon's composed brain-region surface, ~30 members) is not exported by
 * any single landed package — the P5 brain-region packages each own individual
 * modules. `commands.ts` uses the type only (truthiness checks on a handful of
 * members; it never instantiates or traverses it), so this declares a faithful
 * consumer-facing subset.
 *
 * Re-point to the host's (or owning package's) canonical IntelligenceLayer type
 * when it publishes; delete this vendor then.
 */
export interface IntelligenceLayer {
  memory: unknown
  continuity: unknown
  recover: unknown
  reflect: unknown
  thinker: unknown
  dialectic: unknown
  aiScientist: unknown
  ruleEnforcer: unknown
  subconscious: unknown
  contextManager: unknown
  helix: unknown
  constellation: unknown
  selfHealer: unknown
  aiEngineer: unknown
  consequenceEstimator: unknown
  trustLedger: unknown
  permissionOracle: unknown
  thoughtObserver: unknown
  cognitiveBridge: unknown
  improvementOrchestrator: unknown
  smartRules: unknown
  reflex: unknown
  dreamer: unknown
  meditation?: unknown
  heart: unknown
  cortex?: unknown
  lamina?: unknown
  audit?: unknown
  reverie?: unknown
  contextRepo?: unknown
}
