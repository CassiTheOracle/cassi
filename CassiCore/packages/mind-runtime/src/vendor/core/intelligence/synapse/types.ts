/**
 * Synapse Types — Per-Posture Guidance Brain
 *
 * The Synapse sits at the junction between a posture's thinking and the
 * intelligence layer. It receives a thought from the axon (collect_thoughts),
 * processes it through an LLM with energy-adaptive prompting, and transmits
 * guidance back.
 */

import type { CognitiveSignal } from '../thought-observer.js'
import type { ResonancePattern } from '../cognitive-bridge.js'
import type { ILogger } from '@cassicore/foundation'


/** Configuration for the Synapse per-posture guidance brain */
export interface SynapseConfig {
  /** Maximum Synapse LLM calls per axon session. Default: 5 */
  maxCallsPerSession: number
  /** Minimum signal confidence to trigger Synapse. Default: 0.7 */
  signalThreshold: number
  /** Fire Synapse every N steps (periodic check-in). Default: 3 */
  interval: number
  /** Model tier for Synapse LLM calls. Default: 'qwenPlus' */
  modelTier: string
  /** Max output tokens for Synapse. Default: 500 (increased for richer output) */
  maxTokens: number
  /** Timeout for Synapse LLM calls in ms. Default: 5000 (increased for quality) */
  timeoutMs: number
  /** Whether Synapse is enabled. Default: true */
  enabled: boolean
  /** Whether to broadcast guidance to Global Workspace. Default: true */
  broadcastToWorkspace: boolean
  /** Whether to track guidance effectiveness. Default: true */
  trackEffectiveness: boolean
  /** Whether to use Thalamus-curated context when available. Default: true */
  useCuratedContext: boolean
}

/** Default Synapse configuration values — GWT-aware */
export const DEFAULT_SYNAPSE_CONFIG: SynapseConfig = {
   maxCallsPerSession: 8,
   signalThreshold: 0.7,
   interval: 3,
   modelTier: 'qwenPlus',
   maxTokens: 500,
   timeoutMs: 5_000,
   enabled: true,
   broadcastToWorkspace: true,
   trackEffectiveness: true,
   useCuratedContext: true,
}


/** Energy level of the posture — affects prompt tone */
export type PostureEnergy = 'expansive' | 'contractive' | 'unifying' | 'neutral'

/** Context passed to the Synapse for guidance generation */
export interface SynapseContext {
  /** Compressed tree summary of the axon session so far */
  tree: string
  /** The current thinking step */
  currentStep: { number: number; content: string }
  /** Cognitive signals extracted from all steps */
  signals: CognitiveSignal[]
  /** Memory/archive context surfaced during enrichment */
  relatedMemory: string[]
  /** Signals from peer sessions */
  peerSignals: CognitiveSignal[]
  /** Cross-session resonance/tension patterns */
  resonance: ResonancePattern[]
  /** Posture energy, if in Constellation context */
  energy?: PostureEnergy
  /** Whether this step is a revision */
  isRevision?: boolean
  /** Which step is being reconsidered */
  revisesStep?: number
  /** Thalamus-curated context (replaces raw tree when available) */
  curatedContext?: string
  /** Global workspace state — what's currently in focus */
  workspaceFocus?: string
  /** Previous guidance for this session (for continuity) */
  previousGuidance?: SynapseGuidance[]
}


/** Guidance type — what kind of guidance the Synapse is providing */
export type GuidanceType = 'observation' | 'branch' | 'risk' | 'synthesis' | 'focus' | 'correction'

/** Output shape from a Synapse LLM call — GWT-aware with structured output */
export interface SynapseGuidance {
  /** Type of guidance being provided */
  type: GuidanceType
  /** 1-2 sentence observation about the current thinking */
  observation: string
  /** Suggest an alternative thinking path, or null */
  branchSuggestion: string | null
  /** Pitfall warning, or null */
  risk: string | null
  /** Synthesis of multiple perspectives, or null */
  synthesis: string | null
  /** What the posture should focus on next, or null */
  focusSuggestion: string | null
  /** Correction to previous reasoning, or null */
  correction: string | null
  /** Confidence in this guidance (0-1) */
  confidence: number
  /** Which posture this guidance is targeted at */
  targetPosture?: string
  /** Session ID for tracking */
  sessionId: string
  /** Step number this guidance was generated for */
  stepNumber: number
}


/** Tracking data for guidance effectiveness */
export interface GuidanceEffectiveness {
  /** The guidance that was provided */
  guidance: SynapseGuidance
  /** Whether the posture followed the guidance */
  followed: boolean
  /** Whether following the guidance led to better outcomes */
  helpful: boolean | null
  /** Time between guidance and outcome */
  outcomeDelayMs: number
  /** Posture that received the guidance */
  posture: string
}


/** Result of evaluating whether Synapse should fire */
export interface SynapseGatingResult {
  /** Whether the Synapse should fire */
  shouldFire: boolean
  /** Reason for the decision (for debugging/metrics) */
  reason: string
}


/** Dependencies required by the Synapse — GWT-aware */
export interface SynapseDeps {
  /** LLM provider for generating guidance */
  llm: {
    complete(opts: {
      prompt: string
      modelTier: string
      maxTokens: number
      timeoutMs: number
    }): Promise<{ content: string; truncated?: boolean }>
  }
  /** Logger for operations */
  logger: ILogger
  /** Global Workspace — for broadcasting guidance to all cognitive modules */
  globalWorkspace?: {
    submit(entry: { type: string; content: string; source: string; priority?: number }): void
  }
  /** Thalamus — for context curation */
  thalamus?: {
    curate(sessionId: string, messages: unknown[], opts?: unknown): { messages: unknown[]; meta: unknown }
  }
  /** Cortex — for storing guidance in working memory */
  cortex?: {
    signal(region: string, type: string, content: string, opts?: { tags?: string[]; salience?: number }): void
  }
}
