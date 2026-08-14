/**
 * helix-pipeline — Port over CassiCore's `helix/helix-pipeline.js` (runHelixPipeline)
 * and `helix/brainstem-mini-helix.js` (BrainstemMiniHelix).
 *
 * These are deep CassiCore daemon integrations (the full helix pipeline: work-stream,
 * coordinator, posture-runner, brainstem, synapse, conductor, telemetry, and the
 * mini-helix runner + brainstem-tools). Vendoring them would drag dozens of daemon-critical
 * runtime modules into a standalone package. Instead this port declares the exact surface
 * Constellation uses and throws `not connected` until a host wires a real implementation —
 * making future ohmypi adaptation a wiring problem, not a surgery problem.
 *
 * The result type is the vendored `helix/types.js` `HelixResult` so Constellation's pipeline
 * code type-checks against the same shape the real daemon produces. Self-contained: depends
 * only on vendored helix type stubs and built-ins.
 */

import type { HelixResult } from '../vendor/helix/types.js'
import type { WorkUnit } from '../vendor/helix/work-types.js'
import type { HelixSynapse } from '../vendor/helix/helix-synapse.js'
import type { HelixBrainstem } from '../vendor/helix/brainstem.js'
import type { GuidanceUrgency } from '../vendor/helix/brainstem-types.js'

export type { HelixResult }

export type HelixToolProfile = 'implementation' | 'review' | 'readonly' | 'full' | string

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

/** Default implementation — the pipeline is a required host integration. */
export function runHelixPipeline(_opts: HelixPipelineOpts): Promise<HelixResult> {
  return Promise.reject(
    new Error('[constellation] helix-pipeline not connected — wire runHelixPipeline in the host'),
  )
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
 * Runtime stub class for `helix/brainstem-mini-helix.js`'s `BrainstemMiniHelix`.
 * Emits NO runtime surface until a host wires a real implementation: constructing it is
 * allowed (so module wiring does not throw at import time), but every operational method
 * throws `not connected`.
 */
export class BrainstemMiniHelix {
  readonly deps: BrainstemMiniHelixOpts

  constructor(deps: BrainstemMiniHelixOpts) {
    this.deps = deps
  }

  start(): Promise<void> {
    return Promise.reject(
      new Error('[constellation] BrainstemMiniHelix not connected — wire a real implementation in the host'),
    )
  }

  stop(): Promise<void> {
    return Promise.reject(
      new Error('[constellation] BrainstemMiniHelix not connected — wire a real implementation in the host'),
    )
  }

  onCorpusDirective(_directive: unknown): void {
    throw new Error(
      '[constellation] BrainstemMiniHelix not connected — wire a real implementation in the host',
    )
  }
}
