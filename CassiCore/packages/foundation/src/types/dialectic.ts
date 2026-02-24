/**
 * Dialectic Intelligence Types — Yang (expansion), Yin (refinement), Synthesizer (mediation)
 */

import type { Message } from "./runtime.js";

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
  observe(sessionId: string, userMessage: string, context: YangContext): Promise<YangOutput>;
}

export interface YangContext {
  recentMemories: string[];
  availableTools: string[];
  sessionHistory: Message[];
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
  observe(sessionId: string, userMessage: string, yangOutput: YangOutput): Promise<YinOutput>;
}

// ─── Synthesizer ────────────────────────────────────────────────────────────

export type SignalType = 'edge_case' | 'alternative' | 'assumption' | 'connection' | 'contradiction';
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

export interface SynthesizerOutput {
  synthesis: Synthesis;
  meta: {
    dialecticQuality: number;  // 0-1, measure of yang/yin interplay
    processingTimeMs: number;
    inputTokens: number;
    outputTokens: number;
  };
}

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

// ─── Unified Dialectic System ───────────────────────────────────────────────
// ORDER: Yin (refinement) → Yang (expansion) → Synthesizer (mediation)

export interface DialecticResult {
  sessionId: string;
  turnId: string;
  timestamp: number;
  yin: YinOutput;      // First: refinement/grounding
  yang: YangOutput;    // Second: expansion within constraints
  synthesizer: SynthesizerOutput;  // Third: mediation
  signalInjected: boolean;
  totalLatencyMs: number;
  totalCostUsd: number;
}

export interface IDialecticSystem {
  processTurn(
    sessionId: string,
    turnId: string,
    userMessage: string,
    context: YangContext
  ): Promise<DialecticResult>;
}

// ─── WebSocket Stream Events ────────────────────────────────────────────────

export type DialecticStage = 'start' | 'yang' | 'yin' | 'synthesizer' | 'complete' | 'error';

export interface DialecticStreamEvent {
  timestamp: number;
  turnId: string;
  stage: DialecticStage;
  data?: YangOutput | YinOutput | SynthesizerOutput | { error: string } | null;
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
