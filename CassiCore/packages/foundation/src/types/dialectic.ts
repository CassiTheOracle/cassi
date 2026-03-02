/**
 * Dialectic Intelligence Types — Yang (expansion), Yin (refinement), Serenity (mediation)
 */

import type { Message } from "./runtime.js";

// ─── Execution Modes ────────────────────────────────────────────────────────

export type DialecticMode = 'sequential' | 'parallel' | 'adaptive';

export interface AdaptiveConfig {
  complexityThreshold: number;  // Above this, use sequential
  qualityThreshold: number;     // Below this, use sequential  
  historyWindowSize: number;    // Turns to look back for quality metrics
}

// ─── Yang Observer ──────────────────────────────────────────────────────────

export interface YangBranch {
  id: string;
  type: 'alternative_interpretation' | 'edge_case' | 'cross_domain' | 'what_if' | 'assumption_challenge';
  content: string;
  confidence: number;  // 0-1
  noveltyScore: number; // 0-1, higher = more novel
}

export interface YangOutput {
  branches: YangBranch[];
  meta: {
    expansionTemperature: number;
    generationTimeMs: number;
    inputTokens: number;
    outputTokens: number;
  };
}

export interface IYangObserver {
  readonly name: 'yang';
  observe(sessionId: string, userMessage: string, context: YangContext, opts?: { model?: string; provider?: import('./runtime.js').IProvider }): Promise<YangOutput>;
}

export interface YangContext {
  recentMemories: string[];
  availableTools: string[];
  sessionHistory: Message[];
  /**
   * A short, human-readable guide describing the current task for this turn.
   * This should be placed at the top of the observer's prompt/context so
   * that both Yang and Yin align on the immediate objective.
   */
  taskGuide?: string;
  /**
   * Subconscious-derived patterns detected in the conversation.
   * Provided by the Subconscious module for enhanced context.
   */
  subconsciousPatterns?: Array<{
    type: string;
    confidence: number;
    evidence: string[];
  }>;
  /**
   * Subconscious-derived intent classification.
   */
  subconsciousIntent?: {
    type: string;
    confidence: number;
  };
  /**
   * Subconscious-detected anomalies (repetition, confusion, stuck states).
   */
  subconsciousAnomalies?: Array<{
    category: string;
    severity: string;
  }>;
}

export interface IYinObserver {
  readonly name: 'yin';
  /**
   * Observe now receives the Dialectic context so that Yin can see the same
   * brief task guide that Yang received at the top of its context.
   */
  observe(sessionId: string, userMessage: string, yangOutput: YangOutput, context?: YangContext, opts?: { model?: string; provider?: import('./runtime.js').IProvider }): Promise<YinOutput>;
}

// ─── Yin Observer ───────────────────────────────────────────────────────────

export type YinAction = 'surface' | 'ignore' | 'refine';

export interface YinCritique {
  yangBranchId: string;
  valid: boolean;
  essence?: string;        // compressed version if valid
  critique: string;        // why valid or why invalid
  relevance: number;       // 0-1
  action: YinAction;
}

export interface YinOutput {
  critiques: YinCritique[];
  meta: {
    compressionRatio: number;
    processingTimeMs: number;
    inputTokens: number;
    outputTokens: number;
  };
}

export interface IYinObserver {
  readonly name: 'yin';
  // Sequential mode: critique Yang's branches
  observe(sessionId: string, userMessage: string, yangOutput: YangOutput): Promise<YinOutput>;
  // Parallel mode: generate baseline + self-critique independently
  observeWithBaseline(sessionId: string, userMessage: string, context: YangContext, opts?: { model?: string; provider?: import('./runtime.js').IProvider }): Promise<YinBaselineOutput>;
}

/**
 * YinBaselineOutput — For parallel mode where Yin runs independently
 * Yin generates its own baseline analysis + self-critique without Yang's output
 */
export interface YinBaselineBranch {
  id: string;
  type: 'grounding' | 'constraint' | 'reality_check' | 'prioritization' | 'risk_assessment';
  content: string;
  confidence: number;
  relevanceScore: number;
}

export interface YinBaselineOutput {
  baselineBranches: YinBaselineBranch[];
  selfCritiques: YinCritique[];  // Yin's critique of its own baseline
  meta: {
    compressionRatio: number;
    processingTimeMs: number;
    inputTokens: number;
    outputTokens: number;
    relativeTiming: 'before-yang' | 'after-yang' | 'concurrent';
  };
}

// ─── Serenity ───────────────────────────────────────────────────────────

export type SignalType = 'edge_case' | 'alternative' | 'assumption' | 'connection' | 'contradiction' | 'convergence' | 'tension' | 'gap';
export type Urgency = 'immediate' | 'background';

export interface DialecticSignal {
  type: SignalType;
  content: string;
  confidence: number;      // 0-1
  sourceBranches: string[]; // yang branch IDs
  urgency: Urgency;
}

export interface Synthesis {
  hasSignal: boolean;
  signal?: DialecticSignal;
  branchesConsidered: number;
  branchesSurfaced: number;
}

export interface SerenityOutput {
  synthesis: Synthesis;
  meta: {
    dialecticQuality: number;  // 0-1, measure of yang/yin interplay
    processingTimeMs: number;
    inputTokens: number;
    outputTokens: number;
  };
}

// Legacy aliases — main-branch code references these
export type SynthesizerOutput = SerenityOutput;

export interface ISynthesizer {
  readonly name: 'synthesizer';
  synthesize(
    sessionId: string,
    userMessage: string,
    yangOutput: YangOutput,
    yinOutput: YinOutput,
    relevantMemories: string[]
  ): Promise<SynthesizerOutput>;
}

export interface ISerenity {
  readonly name: 'serenity';
  // Sequential synthesis (Yang → Yin → Serenity)
  synchronize(
    sessionId: string,
    userMessage: string,
    yangOutput: YangOutput,
    yinOutput: YinOutput,
    relevantMemories: string[],
    opts?: { model?: string; provider?: import('./runtime.js').IProvider }
  ): Promise<SerenityOutput>;
  // Parallel dual synthesis (Yang + Yin → Serenity)
  synthesizeDual(
    sessionId: string,
    input: DualSynthesisInput,
    relevantMemories: string[],
    opts?: { model?: string; provider?: import('./runtime.js').IProvider }
  ): Promise<SerenityOutput>;
}

/**
 * DualSynthesisInput — For parallel mode where Serenity synthesizes
 * both Yang's expansion and Yin's independent baseline
 */
export interface DualSynthesisInput {
  yang: {
    branches: YangBranch[];
    meta: YangOutput['meta'];
    perspective: 'expansive';
  };
  yin: {
    baselineBranches: YinBaselineBranch[];
    critiques: YinCritique[];
    meta: YinBaselineOutput['meta'];
    perspective: 'constrained';
  };
  userMessage: string;
  context: YangContext;
}

/**
 * ParallelConfig — Configuration for parallel dialectic execution
 */
export interface ParallelConfig {
  maxWaitMs: number;              // Max wait time for parallel observers
  partialResultsOnFailure: boolean; // Return partial results if one observer fails
  observerTimeoutMs: number;      // Timeout per observer
  synchronization: 'wait-for-both' | 'best-effort';
}

/**
 * ParallelDialecticResult — Result from parallel execution mode
 */
export interface ParallelDialecticResult extends DialecticResult {
  level: number;                  // Recursive depth level (0 = top-level)
  executionMode: 'parallel' | 'sequential';
  
  // Timing breakdown
  timing: {
    yangDuration: number;
    yinDuration: number;
    serenityDuration: number;
    totalParallelTime: number;
    firstCompletion: 'yang' | 'yin';
  };
  
  // Quality metrics
  quality: {
    yangYinAgreement: number;     // 0-1, how much they agree
    dialecticTension: number;     // 0-1, diversity of thought
    synthesisConfidence: number;  // Serenity's confidence
  };
}

// ─── Unified Dialectic System ───────────────────────────────────────────────
// ORDER: Yang (expansion) → Yin (refinement) → Serenity (mediation)
// Note: In parallel mode, Yang + Yin run concurrently

export interface DialecticResult {
  sessionId: string;
  turnId: string;
  timestamp: number;
  yang: YangOutput;                    // Expansion
  yin: YinOutput | YinBaselineOutput;  // Refinement (sequential or parallel baseline)
  serenity: SerenityOutput;            // Mediation
  signalInjected: boolean;
  totalLatencyMs: number;
  totalCostUsd: number;
}

export interface IDialecticSystem {
  processTurn(
    sessionId: string,
    turnId: string,
    userMessage: string,
    context: YangContext,
    opts?: { 
      providers?: { yang?: any; yin?: any; serenity?: any };
      mode?: 'sequential' | 'parallel' | 'adaptive';
      signal?: AbortSignal;
    }
  ): Promise<DialecticResult | ParallelDialecticResult>;
}

// ─── WebSocket Stream Events ────────────────────────────────────────────────

export type DialecticStage = 'start' | 'yang' | 'yin' | 'serenity' | 'complete' | 'error';

export interface DialecticStreamEvent {
  timestamp: number;
  turnId: string;
  stage: DialecticStage;
  data?: YangOutput | YinOutput | YinBaselineOutput | SerenityOutput | { error: string } | { taskGuide: string } | { mode: string } | null;
}

// ─── Persistence ────────────────────────────────────────────────────────────

export interface DialecticPersistence {
  save(result: DialecticResult): Promise<void>;
  getRecent(sessionId: string, limit?: number): Promise<DialecticResult[]>;
  getStats(sessionId: string): Promise<{
    totalTurns: number;
    signalsGenerated: number;
    signalsInjected: number;
    avgLatencyMs: number;
    totalCostUsd: number;
  }>;
}
