/**
 * Self-Improvement Loop — Type Definitions
 *
 * Types shared across the improvement orchestrator, gate, journal,
 * scenario generator, and scenario store.
 */

import type { ScenarioResult, WorkflowScenario } from '../../testing/verification/scenario-types.js'

export type AdaptationType =
  | 'strategy_swap'
  | 'provider_preference'
  | 'parameter_tune'
  | 'behavior_nudge'
  | 'code_patch'


/** How the improvement gate executes verification */
export type GateMode = 'sync' | 'async'

/** Outcome of the gate evaluation */
export type GateVerdict = 'passed' | 'failed' | 'skipped' | 'timeout'

/** Final verdict for an improvement attempt */
export type ImprovementVerdict = 'confirmed' | 'reverted' | 'inconclusive'

/** How much trust to place in a proposal source */
export type ImprovementProposalClass = 'experiment' | 'heuristic' | 'repair' | 'audit'

/** Whether an entry was actually verified or merely queued/audited */
export type ImprovementVerificationStatus = 'verified' | 'unverified'

/** What initiated the improvement proposal */
export type ImprovementTrigger =
  | 'adaptive'
  | 'ai-engineer'
  | 'ai-scientist'
  | 'anomaly'
  | 'correlator'
  | 'manual'
  | 'counter-hypothesis'


/** A proposed change from any cognitive module */
export interface ImprovementEvidence {
  targetMetric?: string
  baseline?: number
  expectedDelta?: number
  observedDelta?: number
  dataPoints?: number
  sampleSize?: number
  evidenceWindow?: string
  pValue?: number
  effectSize?: number
  notes?: string[]
}

export interface ImprovementProposal {
  id: string
  trigger: ImprovementTrigger
  /** Module that proposed the change */
  source: string
  /** Broad trust class for the proposal source */
  proposalClass?: ImprovementProposalClass
  /** Human-readable hypothesis */
  hypothesis: string
  /** What type of change this is */
  adaptation: AdaptationType
  /** The actual parameter changes */
  config: Record<string, unknown>
  /** Stable key used for deduping repeated proposals */
  dedupeKey?: string
  /** Risk assessment */
  riskLevel: 'low' | 'moderate' | 'high'
  /** Confidence in the hypothesis (0-1) */
  confidence: number
  /** Structured evidence explaining why this is likely to help */
  evidence?: ImprovementEvidence
  /** Targeted verification scenarios to run, when available */
  verificationScenarios?: string[]
  /** Quality score assigned by the orchestrator on intake */
  qualityScore?: number
  /** Unix ms when proposed */
  timestamp: number
}


/** Result of the verification gate evaluation */
export interface GateResult {
  proposalId: string
  mode: GateMode
  verdict: GateVerdict
  /** Scenario results BEFORE the adaptation was applied */
  beforeResults: ScenarioResult[]
  /** Scenario results AFTER the adaptation was applied (present if gate completed) */
  afterResults: ScenarioResult[]
  /** Scenario names that were passing before but failing after */
  regressions: string[]
  /** Scenario names that improved after the adaptation */
  improvements: string[]
  durationMs: number
}


/** Persistent record of an improvement attempt */
export interface ImprovementEntry {
  id: string
  proposalId: string
  trigger: ImprovementTrigger
  source: string
  proposalClass: ImprovementProposalClass
  hypothesis: string
  adaptation: AdaptationType
  config: Record<string, unknown>
  dedupeKey?: string
  confidence: number
  qualityScore: number
  evidence?: ImprovementEvidence
  gateMode: GateMode
  gateVerdict: GateVerdict
  verificationStatus: ImprovementVerificationStatus
  regressions: string[]
  improvements: string[]
  verdict: ImprovementVerdict
  revertReason?: string
  learnings: string[]
  createdAt: number
  concludedAt?: number
}


/** Aggregated journal statistics for meta-learning */
export interface JournalStats {
  total: number
  verified: number
  unverified: number
  confirmed: number
  reverted: number
  inconclusive: number
  revertRate: number
  /** Breakdown by trigger source */
  byTrigger: Record<string, { total: number; verified: number; unverified: number; confirmed: number; reverted: number; revertRate: number }>
  /** Breakdown by adaptation type */
  byAdaptationType: Record<string, { total: number; verified: number; unverified: number; confirmed: number; reverted: number; revertRate: number }>
}


/** Metadata for a persisted scenario */
export interface StoredScenario {
  id: string
  name: string
  description: string
  definition: WorkflowScenario
  /** What triggered this scenario's creation */
  triggerType: 'anomaly' | 'hypothesis' | 'counter-hypothesis' | 'trust' | 'repair' | 'manual' | 'hardcoded'
  /** Reference to the source signal that generated this scenario */
  triggerId?: string
  tags: string[]
  runCount: number
  passCount: number
  lastRunAt?: number
  lastPassAt?: number
  /** Marked stale after N consecutive passes with no regressions */
  stale: boolean
  createdAt: number
}


export interface ImprovementConfig {
  /** Master enable switch */
  enabled: boolean
  /** Default gate mode: sync blocks until verified, async applies then checks */
  gateMode: GateMode
  /** How long async mode waits before checking (ms) */
  asyncRevertWindowMs: number
  /** Whether low-risk proposals can use async even in sync-default mode */
  lowRiskAsyncAllowed: boolean
  /** Max proposals to process per orchestrator cycle */
  maxConcurrentProposals: number
  /** Timeout for each scenario run during gate evaluation (ms) */
  scenarioTimeoutMs: number
  /** CycleHook cadence for meta-learning pass (default: 10) */
  metaLearningCadence: number
  /** Minimum journal entries before meta-learning kicks in */
  minJournalEntries: number
  /** Minimum confidence to accept a proposal */
  confidenceThreshold: number
  /** Minimum orchestrator quality score to queue a proposal */
  proposalQualityThreshold: number
  /** Minimum sample size/data points for evidence-bearing proposals */
  minEvidenceDataPoints: number
  /** Drop repeated proposals with the same dedupe key inside this window */
  dedupeWindowMs: number
  /** Consecutive passes before marking a scenario as stale */
  stalenessThreshold: number
}

export const DEFAULT_IMPROVEMENT_CONFIG: ImprovementConfig = {
  enabled: true,
  gateMode: 'sync',
  asyncRevertWindowMs: 30_000,
  lowRiskAsyncAllowed: true,
  maxConcurrentProposals: 1,
  scenarioTimeoutMs: 120_000,
  metaLearningCadence: 10,
  minJournalEntries: 5,
  confidenceThreshold: 0.6,
  proposalQualityThreshold: 0.5,
  minEvidenceDataPoints: 3,
  dedupeWindowMs: 60 * 60_000,
  stalenessThreshold: 10,
}
