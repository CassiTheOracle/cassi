/**
 * Dialectic Engine Types — Clean, composable reasoning interface
 *
 * The dialectic engine runs three postures (Yang, Yin, Unity) in a
 * specific data flow:
 *
 *   Input → Yang ∥ Yin (parallel, independent work) → Unity (arbitration)
 *
 * Yang and Yin each independently reason about (or work on) the input.
 * Unity reviews both approaches and selects:
 *   - Option A: Yang's approach
 *   - Option B: Yin's approach
 *   - Option C: A custom synthesis combining the best of both
 *
 * The selected version becomes the final output.
 *
 * Two operating levels:
 *   1. String reasoning (no tools): Yang/Yin produce reasoned responses
 *   2. Tool-using workflow: Yang/Yin work the problem with tools
 */

import type { IProvider } from './runtime.js'

// Engine Configuration ──────────────────────────────────────────

export interface DialecticEngineConfig {
  /** Max Yang expansion branches (default: 3) */
  maxBranches: number
  /** Yang temperature — higher = more creative (default: 0.8) */
  yangTemperature: number
  /** Yin temperature — lower = more grounded (default: 0.3) */
  yinTemperature: number
  /** Unity temperature — balanced arbitration (default: 0.4) */
  unityTemperature: number
  /** Default model spec (e.g., 'gpt-4o') */
  model: string
  /** Max tokens for each posture's response */
  maxTokens: number
  /** Timeout per posture in ms (default: 30000) */
  postureTimeoutMs: number
}

// Reason Options (per-call overrides) ───────────────────────────

export interface ReasonOptions {
  /** Extra context to include (memories, conversation, instructions, etc.) */
  context?: string
  /** Model override for this call (applies to all postures) */
  model?: string
  /** Per-posture model overrides */
  models?: {
    yang?: string
    yin?: string
    unity?: string
  }
  /** Provider override for this call */
  provider?: IProvider
  /** Max Yang branches (overrides config) */
  maxBranches?: number
  /** AbortSignal for cancellation */
  signal?: AbortSignal
  /** Operating mode */
  mode?: DialecticMode
}

export type DialecticMode =
  | 'parallel'      // Yang ∥ Yin → Unity (default, 3 calls)
  | 'consolidated'  // Single call for all three (fast path, 1 call)

// Yang Output ───────────────────────────────────────────────────

export type YangBranchType =
  | 'alternative_interpretation'
  | 'edge_case'
  | 'cross_domain'
  | 'what_if'
  | 'assumption_challenge'

export interface YangBranch {
  type: YangBranchType
  content: string
  confidence: number  // 0-1
  novelty: number     // 0-1
}

export interface YangApproach {
  /** Yang's recommended response/approach to the input */
  response: string
  /** Supporting expansion branches */
  branches: YangBranch[]
  /** Execution metadata */
  meta: {
    latencyMs: number
    model?: string
  }
}

// Yin Output ────────────────────────────────────────────────────

export type YinBaselineType =
  | 'grounding'
  | 'constraint'
  | 'reality_check'
  | 'prioritization'
  | 'risk_assessment'

export interface YinBaseline {
  type: YinBaselineType
  content: string
  confidence: number    // 0-1
  relevance: number     // 0-1
}

export interface YinCritique {
  /** Which Yang branch this critiques (by index) */
  yangBranchIndex: number
  valid: boolean
  critique: string
  action: 'surface' | 'compress' | 'discard'
}

export interface YinApproach {
  /** Yin's recommended response/approach to the input */
  response: string
  /** Grounding baselines */
  baselines: YinBaseline[]
  /** Critiques of Yang's branches (populated by Unity or post-analysis) */
  critiques: YinCritique[]
  /** Execution metadata */
  meta: {
    latencyMs: number
    model?: string
  }
}

// Unity Output ──────────────────────────────────────────────────

export type UnitySelection = 'A' | 'B' | 'C'

export interface UnityDecision {
  /** Which option was selected */
  selected: UnitySelection
  /** The final output — the selected/synthesized response */
  output: string
  /** Why this option was selected */
  reasoning: string
  /** Comparison assessment */
  comparison: {
    /** Strengths of Yang's approach */
    yangStrengths: string
    /** Weaknesses of Yang's approach */
    yangWeaknesses: string
    /** Strengths of Yin's approach */
    yinStrengths: string
    /** Weaknesses of Yin's approach */
    yinWeaknesses: string
  }
  /** If C was selected, what was combined from each */
  synthesis?: {
    fromYang: string
    fromYin: string
    novel: string
  }
  /** Confidence in the selection (0-1) */
  confidence: number
  /** Execution metadata */
  meta: {
    latencyMs: number
    model?: string
  }
}

// Signal (optional dialectic insight) ───────────────────────────

export type DialecticSignalType =
  | 'edge_case'
  | 'alternative'
  | 'assumption'
  | 'connection'
  | 'contradiction'
  | 'convergence'
  | 'tension'
  | 'gap'

export interface DialecticEngineSignal {
  type: DialecticSignalType
  content: string
  confidence: number  // 0-1
  urgency: 'immediate' | 'background'
}

// Structured Result ─────────────────────────────────────────────

export interface DialecticStructuredResult {
  /** The final output string — same as what reason() returns */
  output: string

  /** Yang's independent approach (Option A) */
  yang: YangApproach

  /** Yin's independent approach (Option B) */
  yin: YinApproach

  /** Unity's arbitration decision */
  unity: UnityDecision

  /** Optional dialectic signal (insight for the caller) */
  signal: DialecticEngineSignal | null

  /** Quality metrics */
  quality: {
    /** How well the dialectic process worked (0-1) */
    dialecticQuality: number
    /** Tension between Yang and Yin (0-1, higher = more diverse) */
    tension: number
    /** Agreement between Yang and Yin (0-1) */
    agreement: number
  }

  /** Overall execution metadata */
  meta: {
    totalLatencyMs: number
    /** Which mode was used */
    mode: DialecticMode
  }
}

// Engine Interface ──────────────────────────────────────────────

export interface IDialecticEngine {
  /** Wire an LLM provider */
  setProvider(provider: IProvider): void

  /** String in → string out. The headline API. */
  reason(input: string, opts?: ReasonOptions): Promise<string>

  /** Full structured breakdown for training data, debugging, inspection */
  reasonStructured(input: string, opts?: ReasonOptions): Promise<DialecticStructuredResult>
}
