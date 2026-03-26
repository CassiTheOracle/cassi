/**
 * Collect Thoughts Tool Types — Axon
 *
 * Type definitions for the collect_thoughts tool — a bidirectional
 * intelligence exchange where each thinking step is enriched with signals,
 * memory context, peer activity, and guidance from the Synapse cognitive layer.
 *
 * Neural metaphor:
 *   Axon  — the structured thought chain (this tool's session/tree)
 *   Synapse — fires guidance at junctions between thoughts
 *   Dendrites — memory, signals, peers feeding into each step
 */

import type { CognitiveSignal, SignalKind } from '../core/intelligence/thought-observer.js'
import type { ResonancePattern } from '../core/intelligence/cognitive-bridge.js'

// ─── Tool Result ──────────────────────────────────────────────────────────

/** The enriched result returned from each collect_thoughts tool call. */
export interface CollectThoughtsResult {
  /** Metadata about the recorded step */
  step: {
    number: number
    of: number
    recorded: true
    isRevision: boolean
    branchId: string
  }

  /** Cognitive signals extracted from this thought step */
  signals: CognitiveSignal[]

  /** Related context from memory + archive search (max 5, ≤200 chars each) */
  relatedContext: string[]

  /** Signals from peer sessions via CognitiveBridge */
  peerSignals: CognitiveSignal[]

  /** Cross-session patterns (convergence or tension) */
  resonance: Array<{
    kind: 'resonance' | 'tension'
    summary: string
    confidence: number
  }>

  /** Per-posture guidance from Synapse LLM */
  synapse: SynapseGuidance | null

  /** Strategic guidance injected by Brainstem (null until Phase 3c) */
  constellationGuidance: string | null

  /** Current state of the axon (thought tree) */
  tree: {
    totalSteps: number
    activeBranch: string
    branches: string[]
    revisionsCount: number
  }

  /** Shared tree awareness: which postures have contributed and how many steps each */
  contributors: Record<string, number>

  /** Budget metadata for the model to be aware of */
  meta: {
    synapseCallsRemaining: number
    nextSynapseEligible: string   // e.g., "step 6" or "next revision"
    /** Whether the Synapse LLM was invoked on this step */
    synapseFired: boolean
    /** Synapse LLM call latency in ms (0 if not fired) */
    synapseLatencyMs: number
  }
}

// ─── Synapse Types ────────────────────────────────────────────────────────

/** Output shape from a Synapse LLM call */
export interface SynapseGuidance {
  /** 1-2 sentence observation about the current reasoning */
  observation: string
  /** Suggest an alternative reasoning path, or null */
  branchSuggestion: string | null
  /** Pitfall warning, or null */
  risk: string | null
}

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
  energy?: string
  /** Whether this step is a revision */
  isRevision?: boolean
  /** Which step is being reconsidered */
  revisesStep?: number
}

// ─── Configuration ────────────────────────────────────────────────────────

/** Configuration for the collect_thoughts tool and its cognitive layers */
export interface CollectThoughtsConfig {
  /** Maximum Synapse LLM calls per axon session. Default: 5 */
  maxSynapseCalls: number
  /** Minimum signal confidence to trigger Synapse. Default: 0.7 */
  synapseSignalThreshold: number
  /** Fire Synapse every N steps (periodic check-in). Default: 3 */
  synapseInterval: number
  /** Model tier for Synapse LLM calls. Default: 'fast' */
  synapseModelTier: string
  /** Max output tokens for Synapse. Default: 200 */
  synapseMaxTokens: number
  /** Timeout for Synapse LLM calls in ms. Default: 3000 */
  synapseTimeoutMs: number
  /** Max memory search results per step. Default: 3 */
  maxMemoryResults: number
  /** Max archive search results per step. Default: 2 */
  maxArchiveResults: number
  /** Max peer signals returned per step. Default: 5 */
  maxPeerSignals: number
  /** Whether Synapse is enabled. Default: true */
  synapseEnabled: boolean
}

/** Default configuration values */
export const DEFAULT_COLLECT_THOUGHTS_CONFIG: CollectThoughtsConfig = {
  maxSynapseCalls: 5,
  synapseSignalThreshold: 0.7,
  synapseInterval: 3,
  synapseModelTier: 'fast',
  synapseMaxTokens: 200,
  synapseTimeoutMs: 3_000,
  maxMemoryResults: 3,
  maxArchiveResults: 2,
  maxPeerSignals: 5,
  synapseEnabled: true,
}

// ─── Internal Session State ───────────────────────────────────────────────

/** Per-session state tracked by the tool handler between calls — the axon session */
export interface AxonSessionState {
  /** Axon session ID (maps to BranchingConversation session) */
  axonSessionId: string
  /** CassiCore session ID that owns this thought chain */
  ownerSessionId: string
  /** Step number → BranchingConversation turn ID mapping */
  stepToTurnId: Map<number, string>
  /** Running count of revisions */
  revisionsCount: number
  /** Remaining Synapse budget */
  synapseBudget: number
  /** All signals extracted during this session, by step */
  signalsByStep: Map<number, CognitiveSignal[]>
  /** Created timestamp */
  createdAt: number
  /** Shared tree awareness: which postures have contributed and how many steps each */
  contributors: Map<string, number>
}

// ─── Tool Input ───────────────────────────────────────────────────────────

/** Input parameters for the collect_thoughts tool call */
export interface CollectThoughtsInput {
  /** Current thought — what you're considering, your hypothesis, analysis, or conclusion */
  thought: string
  /** Step number in the thought chain */
  step: number
  /** Estimated total steps (adjustable as thinking evolves) */
  estimated_steps: number
  /** Whether more thinking is needed after this step */
  continue_thinking: boolean
  /** Whether this revises a previous step */
  is_revision?: boolean
  /** Which step is being reconsidered */
  revises_step?: number
  /** Create a branch from this step number */
  branch_from_step?: number
  /** Branch identifier */
  branch_id?: string
  /** Dynamic extension — more steps needed than originally estimated */
  needs_more_steps?: boolean
  /** Resume a previous axon session */
  session_id?: string
  /** Posture energy for Synapse guidance adaptation (expansive/contractive/unifying/neutral) */
  posture_energy?: 'expansive' | 'contractive' | 'unifying' | 'neutral'
}
