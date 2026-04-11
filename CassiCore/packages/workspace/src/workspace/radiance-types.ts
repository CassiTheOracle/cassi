/**
 * Radiance Loop Types — Workspace feedback and self-observation.
 *
 * Completes the Global Workspace Theory cycle: after the workspace broadcasts
 * to all modules, modules respond with their most relevant context, an LLM
 * observer reads the response pattern, and its observations re-enter the
 * workspace as signals. The loop self-regulates through surprise-gating:
 * the observer only fires when the response pattern departs from expectation.
 *
 * See docs/designs/radiance-loop.md for the full design document.
 */

import type { CognitiveSignal, SignalType } from './cognitive-signal.js'


// Response Channel — what modules return after receiving a broadcast

/**
 * What a module did with the broadcast content.
 * Adapted from Constellation's RadianceResponseType.
 */
export type ResponseDisposition =
  | 'convergent'     // Module's context aligns with / supports the broadcast
  | 'divergent'      // Module's context contradicts or complicates the broadcast
  | 'lateral'        // Module's context is related but unexpected — a tangential connection
  | 'silent'         // Module has nothing relevant (absence is informative)

/**
 * A module's response to a workspace broadcast.
 * Returned by modules that subscribe to the response channel.
 */
export interface WorkspaceResponse {
  /** Which module produced this response */
  source: string
  /** How the module's context relates to the broadcast */
  disposition: ResponseDisposition
  /** The relevant context the module wants to surface (may be empty for 'silent') */
  content: string
  /** Confidence in the response's relevance (0-1) */
  confidence: number
  /** Signal type of the returned context */
  type: SignalType
  /** When this response was produced */
  respondedAt: number
  /** Optional metadata for downstream tracing */
  metadata?: Record<string, unknown>
}


// Response Collector — aggregated view of how the system responded

/**
 * Summary of a single module's participation in the response cycle.
 */
export interface ModuleResponseSummary {
  source: string
  disposition: ResponseDisposition
  contentPreview: string
  confidence: number
  type: SignalType
  /** Was this module expected to respond? (from ExpectationModel) */
  wasExpected: boolean
}

/**
 * The shape of the system's collective response to a broadcast.
 * This is the raw material the observer sees.
 */
export interface ResponsePattern {
  /** The broadcast signals that triggered this response cycle */
  broadcastSignals: Array<{
    signalId: string
    source: string
    type: SignalType
    contentPreview: string
    luminance: number
  }>
  /** All module responses received */
  responses: ModuleResponseSummary[]
  /** Modules that were expected to respond but didn't */
  unexpectedSilences: string[]
  /** Modules that responded unexpectedly */
  unexpectedResponses: string[]
  /** Count of convergent responses */
  convergentCount: number
  /** Count of divergent responses */
  divergentCount: number
  /** Count of lateral (unexpected connection) responses */
  lateralCount: number
  /** Count of silent responses */
  silentCount: number
  /** Total registered response modules */
  totalModules: number
  /** When this pattern was assembled */
  timestamp: number
}


// Expectation Model — learned baseline for surprise detection

/**
 * Per-module expectation: how this module typically responds.
 */
export interface ModuleExpectation {
  source: string
  /** How often this module responds (vs. staying silent). 0-1 */
  responseRate: number
  /** Distribution of dispositions when it does respond */
  dispositionRates: Record<ResponseDisposition, number>
  /** Signal types this module typically responds to */
  respondedToTypes: Partial<Record<SignalType, number>>
  /** Total observations used to build this expectation */
  observationCount: number
}

/**
 * Result of comparing a ResponsePattern against learned expectations.
 */
export interface SurpriseAssessment {
  /** Overall surprise score (0-1). Higher = more unexpected. */
  composite: number
  /** Per-module surprise contributions */
  perModule: Array<{
    source: string
    surprise: number
    reason: string
  }>
  /** Whether the surprise threshold was met (observer should fire) */
  shouldObserve: boolean
  /** What aspect of the pattern was most surprising */
  dominantSurprise: 'silence' | 'convergence' | 'divergence' | 'lateral' | 'mixed' | 'none'
}


// Observer Output — what the LLM observer produces

/**
 * Categories of metacognitive observation the observer can make.
 */
export type ObservationType =
  | 'convergence'     // Multiple modules agree — confidence signal
  | 'tension'         // Modules contradict — dialectic opportunity
  | 'novelty'         // Unexpected connection detected
  | 'absence'         // Expected response missing — knowledge gap or genuine novelty
  | 'self-reference'  // Response pattern references the system's own processing
  | 'integration'     // Observer synthesized multiple response threads

/**
 * A structured observation from the Workspace Observer.
 * Posted as a CognitiveSignal to the workspace and a CorticalSignal to the Monitor region.
 */
export interface ObservationSignal {
  /** What kind of observation this is */
  observationType: ObservationType
  /** Human-readable description of the observation */
  narrative: string
  /** Confidence in the observation (0-1) */
  confidence: number
  /** Which module responses contributed to this observation */
  contributingSources: string[]
  /** The surprise assessment that triggered this observation */
  surpriseScore: number
  /** Whether this observation references the system's own processing */
  isSelfReferential: boolean
}


// Observer Configuration

/**
 * Configuration for the Radiance Loop.
 */
export interface RadianceLoopConfig {
  /** Whether the radiance loop is active. Default: false (opt-in) */
  enabled: boolean
  /** Minimum surprise score (0-1) to trigger the observer. Default: 0.3 */
  surpriseThreshold: number
  /** Maximum time (ms) to wait for module responses after broadcast. Default: 5000 */
  responseWindowMs: number
  /** Minimum number of response cycles before the expectation model starts scoring. Default: 10 */
  warmupCycles: number
  /** Bayesian learning rate for the expectation model. Default: 0.1 */
  learningRate: number
  /** Model tier for the observer LLM. Default: 'background' */
  observerModelTier: string
  /** Maximum observer iterations per cycle. Default: 3 */
  maxObserverIterations: number
  /** Whether to post observations to the Cortex Monitor region. Default: true */
  postToMonitor: boolean
  /** Whether to submit observations to the GlobalWorkspace. Default: true */
  submitToWorkspace: boolean
}

export const DEFAULT_RADIANCE_LOOP_CONFIG: RadianceLoopConfig = {
  enabled: false,
  surpriseThreshold: 0.3,
  responseWindowMs: 5_000,
  warmupCycles: 10,
  learningRate: 0.1,
  observerModelTier: 'background',
  maxObserverIterations: 3,
  postToMonitor: true,
  submitToWorkspace: true,
}


// Response Handler signature — what modules register to participate

/**
 * A response handler that modules register with the workspace.
 * Receives the broadcast signals and returns relevant context (or null for silence).
 */
export type WorkspaceResponseHandler = (
  broadcastSignals: CognitiveSignal[],
) => Promise<WorkspaceResponse | null> | WorkspaceResponse | null
