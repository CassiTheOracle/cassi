/**
 * @cassicore/foundation — Shared substrate for the CassiCore modular workspace.
 *
 * Re-exports the live type surface, system settings, phrase prototypes, the
 * BaseCognitiveModule cluster, and the paths port. Downstream packages import
 * this single package instead of re-vendoring the common types/settings.
 *
 * Note on overlapping names: several symbols are declared in more than one
 * type file (e.g. `PluginManifest`/`PluginStatus` in both interfaces.ts and
 * plugin.ts; `DialecticMode`/`YangBranch`/`YinCritique` in both dialectic.ts
 * and dialectic-engine.ts). They are re-exported once (see below) so the barrel
 * has a single declaration site for each. Where the shapes genuinely differ
 * (dialectic vs dialectic-engine), the engine-flavored variant is exposed under
 * an `Engine*` alias (see the dialectic-engine block).
 */

// types/ — full surface (collision-free files)
export * from './types/runtime.js'
export * from './types/intelligence.js'
export * from './types/model-routing.js'
export * from './types/flux-team.js'
export * from './types/workflow.js'
export * from './types/blackboard-search.js'
export * from './types/cassi-agent.js'
export * from './types/collect-thoughts.js'
export * from './types/event-query.js'
export * from './types/plugin.js'
export * from './types/replay.js'
export * from './types/session-ref.js'
export * from './types/trace.js'
export * from './types/worker-messages.js'
export * from './types/events.js'
export * from './types/execution-backend.js'

// types/interfaces.ts — re-export its unique members; PluginStatus/PluginManifest
// are provided by plugin.js (identical shapes).
export type {
  IEventBus,
  ILogger,
  IConfig,
  IPluginHost,
  WiringDependencies,
  ThinkerDeferredWiring,
  IntelligenceModule,
} from './types/interfaces.js'

// types/dialectic.ts — canonical source for the shared dialectic symbols.
export * from './types/dialectic.js'

// types/dialectic-engine.ts — unique members (DialecticMode/YangBranch/YinCritique
// also declared in dialectic.ts but with DIFFERENT shapes — dialectic-engine adds
// the 'consolidated' mode and a `novelty` branch field). The un-prefixed names are
// dialectic.ts's (via the `export *` above); engine-flavored variants are exposed
// under aliases so the dialectic RUNTIME (engine.ts) can reference them.
export type {
  DialecticEngineConfig,
  ReasonOptions,
  YangBranchType,
  YangApproach,
  YinBaselineType,
  YinBaseline,
  YinApproach,
  UnitySelection,
  UnityDecision,
  DialecticSignalType,
  DialecticEngineSignal,
  DialecticStructuredResult,
  IDialecticEngine,
  DialecticMode as EngineDialecticMode,
  YangBranch as EngineYangBranch,
  YinCritique as EngineYinCritique,
} from './types/dialectic-engine.js'

// config/
export * from './config/system-settings.js'

// phrases/
export * from './phrases/phrase-prototypes.js'

// base/ — BaseCognitiveModule cluster (ModuleModelConfig + DEFAULT_MODULE_MODEL_CONFIG
// re-exported by cognitive-module.ts; inference helpers included).
export * from './base/cognitive-module.js'
export * from './base/model-config.js'
export * from './base/inference.js'

// ports/
export * from './ports/paths.js'
