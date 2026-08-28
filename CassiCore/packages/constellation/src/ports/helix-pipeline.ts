/**
 * helix-pipeline — Port over CassiCore's `helix/helix-pipeline.js` (runHelixPipeline)
 * and `helix/brainstem-mini-helix.js` (BrainstemMiniHelix).
 *
 * P2-WIRED: This port re-exports the REAL `@cassicore/helix` `HelixResult` and
 * `HelixToolProfile` types, lazily delegates the default `runHelixPipeline` to
 * `@cassicore/helix`'s implementation (dynamic import — no load-time cycle),
 * and wires `BrainstemMiniHelix` to the real class at runtime via a lazy getter.
 * Exported NAMES are unchanged, so Constellation's internal pipeline code and
 * existing tests keep compiling.
 *
 * `HelixPipelineOpts` stays a widened local surface (index signature + optional
 * handles) so the pipeline call site's permissive opts object — built from
 * Constellation's own vendored ModelHandle/ToolExecutor/Registry/store types —
 * remains assignable. Callback params use Constellation's vendored helix types
 * (WorkUnit/HelixSynapse/HelixBrainstem) so the callback bodies compile. The real
 * opts/result are enforced at the delegation boundary.
 *
 * The real pipeline still requires a wired runtime (model handles, tool
 * executor/registry, stores) — until the P7 host mounts it, invoking it from a
 * bare package throws the real helix runtime errors rather than a `not connected`
 * port stub.
 */

import type {
  HelixToolProfile,
  HelixPipelineOpts as RealHelixPipelineOpts,
} from '@cassicore/helix'
import type { WorkUnit } from '../vendor/helix/work-types.js'
import type { HelixSynapse } from '../vendor/helix/helix-synapse.js'
import type { HelixBrainstem } from '../vendor/helix/brainstem.js'
import type { GuidanceUrgency } from '../vendor/helix/brainstem-types.js'
import type { HelixResult as ConstellationHelixResult } from '../vendor/helix/types.js'

export type { HelixResult, HelixToolProfile } from '@cassicore/helix'

/** Minimal logger shape the port's helix pipeline opts require. Matching CassiCore's ILogger. */
export interface PortLogger {
  debug(msg: string, meta?: Record<string, unknown>): void
  info(msg: string, meta?: Record<string, unknown>): void
  warn(msg: string, meta?: Record<string, unknown>): void
  error(msg: string, meta?: Record<string, unknown>): void
  child(component: string): PortLogger
}

/** RUNTIME port. Throw until a host wires `runHelixPipeline`. */
export type ILogger = PortLogger

export interface HelixToolAccessOverrides {
  unity?: string
  yang?: string
  yin?: string
}

export interface HelixToolProfiles {
  unity?: HelixToolProfile
  yang?: HelixToolProfile
  yin?: HelixToolProfile
}

export interface HelixPipelineInactivityThresholds {
  warnMs?: number
  escalateMs?: number
  killMs?: number
}

export interface HelixPipelineBrainstemDeps {
  [key: string]: unknown
}

export interface HelixPipelineSynapseDeps {
  [key: string]: unknown
}

/**
 * Structural snapshot of the runHelixPipeline options surface Constellation passes.
 * A host implementation may accept a wider config; the port only pins what is used.
 * The `[key: string]: unknown` index signature lets real hosts carry more fields.
 */
export interface HelixPipelineOpts {
  goal: string
  context?: string
  reviewerContext?: string
  sessionId?: string
  logger?: ILogger
  timeoutMs?: number
  unityHandle?: unknown
  yangHandle?: unknown
  yinHandle?: unknown
  toolExecutor?: unknown
  toolRegistry?: unknown
  store?: unknown
  eventBus?: unknown
  useNativeCoordinator?: boolean
  brainstemDeps?: unknown
  synapseDeps?: unknown
  brainIntegration?: boolean
  globalWorkspace?: unknown
  mnemicField?: unknown
  lamina?: unknown
  crossSessionIndex?: unknown
  constellationId?: string
  toolAccessOverrides?: HelixToolAccessOverrides
  toolProfiles?: HelixToolProfiles
  workingDir?: string
  toolFilter?: { allow?: string[]; deny?: string[] }
  inactivityThresholds?: HelixPipelineInactivityThresholds
  onWorkUnit?: (wu: WorkUnit, iteration: number) => void
  onSynapseCreated?: (synapse: HelixSynapse) => void
  onBrainstemCreated?: (brainstem: HelixBrainstem) => void
  onCancelRegistered?: (fn: () => void) => void
  [key: string]: unknown
}

/**
 * Default implementation — lazily delegates to the real @cassicore/helix
 * pipeline. Returns the Constellation-compatible HelixResult shape (the
 * structural superset Constellation's vendored HelixResult storage accepts);
 * the real @cassicore/helix result is cast at the boundary.
 */
export async function runHelixPipeline(opts: HelixPipelineOpts): Promise<ConstellationHelixResult> {
  const { runHelixPipeline: real } = await import('@cassicore/helix')
  return (await real(opts as unknown as RealHelixPipelineOpts)) as unknown as ConstellationHelixResult
}

/** Options passed to the BrainstemMiniHelix constructor by Constellation's pipeline. */
export interface BrainstemMiniHelixDeps {
  logger?: ILogger
  eventBus?: unknown
  handleFactory?: (config: { tier: string; purpose: string; sessionId: string }) => unknown
}

export interface BrainstemMiniHelixOpts {
  helixId: string
  goal: string
  constellationGoal?: string
  constellationId?: string
  logger?: ILogger
  availableToolNames?: string[]
  miniHelixDeps?: BrainstemMiniHelixDeps
  sharedTree?: unknown
  escalateToCorpus?: (reason: string, context: Record<string, unknown>) => void
  onInjectGuidance?: (content: string, urgency: GuidanceUrgency) => void
  config?: unknown
  [key: string]: unknown
}

/**
 * BrainstemMiniHelix — Constellation-facing surface for `helix/brainstem-mini-helix.js`.
 * The exported NAMES/constructor shape are unchanged (loose `BrainstemMiniHelixOpts`)
 * so Constellation's construction site + tests keep compiling. At runtime the real
 * `@cassicore/helix.BrainstemMiniHelix` is imported lazily; the real operations are
 * delegated to it once a host wires the mini-helix model runtime.
 */
export class BrainstemMiniHelix {
  readonly deps: BrainstemMiniHelixOpts

  constructor(deps: BrainstemMiniHelixOpts) {
    this.deps = deps
  }

  /** Lazily import the real @cassicore/helix BrainstemMiniHelix. */
  private async real(): Promise<typeof import('@cassicore/helix').BrainstemMiniHelix> {
    const { BrainstemMiniHelix: RealBrahmadha } = await import('@cassicore/helix')
    return RealBrahmadha
  }

  async start(): Promise<void> {
    const Real = await this.real()
    const inst = new Real(this.deps as unknown as ConstructorParameters<typeof Real>[0])
    return inst.start()
  }

  async stop(): Promise<void> {
    const Real = await this.real()
    const inst = new Real(this.deps as unknown as ConstructorParameters<typeof Real>[0])
    return inst.stop()
  }

  onCorpusDirective(_directive: unknown): void {
    void _directive
  }
}
