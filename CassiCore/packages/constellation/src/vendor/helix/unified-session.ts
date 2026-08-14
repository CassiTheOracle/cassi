/**
 * VENDORED TYPE STUB — mirrors `helix/unified-session.js` (CassiCore) type surface.
 * The `UnifiedSession` runtime class lives in the daemon; the type surface Constellation
 * reads (HelixSession/HelixResult/HelixProgress + supporting dialectic/work-stream types)
 * is declared here against the vendored `work-types.ts`.
 */
import type { WorkUnit, Nudge, Refinement, Guidance } from './work-types.js'

export interface Finding {
  id: string
  source: 'yang' | 'yin'
  type: 'observation' | 'insight' | 'concern'
  content: string
  confidence: number
  references?: string[]
  timestamp: number
}

export interface Challenge {
  id: string
  source: 'yang' | 'yin'
  targetFindingId: string
  content: string
  severity: 'low' | 'medium' | 'high'
  timestamp: number
}

export interface Concession {
  id: string
  source: 'yang' | 'yin'
  targetChallengeId: string
  content: string
  timestamp: number
}

export interface ExecutiveSummary {
  synthesis: string
  agreementLevel: number
  requiresIntervention: boolean
  urgency: 'low' | 'medium' | 'high'
  keyFindings: string[]
  unresolvedChallenges: string[]
}

export interface HelixSessionConfig {
  mode: 'dialectic' | 'pipeline' | 'adaptive'
  goal: string
  context?: string
  sessionId?: string
  parentSessionId?: string
  jobId?: string
  workerDirective?: string
  reviewerDirectives?: { yang: string; yin: string }
  mentorDirective?: string
  maxIterations: number
  convergenceThreshold: number
  timeoutMs: number
  toolAccess: 'read-only' | 'read-write' | 'none'
  allowedTools?: string[]
  attentionEmbedding?: Float32Array
  [key: string]: unknown
}

export interface HelixResult {
  conclusion: string
  confidence: number
  workUnits: WorkUnit[]
  refinements: Refinement[]
  findings: Finding[]
  challenges: Challenge[]
  concessions: Concession[]
  synthesis: string
  filesModified: string[]
  tokenUsage: {
    unity: number
    yang: number
    yin: number
    mentor: number
    total: number
  }
  durationMs: number
  [key: string]: unknown
}

export interface HelixSession {
  run(): Promise<HelixResult>
  cancel(): boolean
  pause(): void
  resume(): void
  getProgress(): HelixProgress
  [key: string]: unknown
}

export interface HelixProgress {
  status: 'running' | 'paused' | 'completed' | 'cancelled' | 'error'
  mode: 'dialectic' | 'pipeline' | 'adaptive'
  iteration: number
  maxIterations: number
  postures: {
    unity: PostureProgress
    yang: PostureProgress
    yin: PostureProgress
    mentor: PostureProgress
  }
  workStream: WorkStreamStats
  dialectic: DialecticStats
  convergenceLevel: number
}

export interface PostureProgress {
  state: 'idle' | 'active' | 'completed' | 'error'
  iterationCount: number
  toolCallCount: number
  tokensUsed: number
  lastToolName?: string
  lastToolTimestamp?: number
  error?: string
}

export interface WorkStreamStats {
  workUnits: number
  workUnitsReviewed: number
  workUnitsUnreviewed: number
  nudges: { low: number; high: number; acknowledged: number }
  refinements: number
  guidance: number
}

export interface DialecticStats {
  findings: number
  challenges: number
  concessions: number
  investigationRequests: number
  executiveInjections: number
}

export interface UnifiedChannel {
  submitWork(unit: WorkUnit): void
  reviewWork(nudge: Nudge): void
  refineWork(refinement: Refinement): void
  injectGuidance(guidance: Guidance): void
  getWorkUnit(id: string): WorkUnit | undefined
  getUnreviewedWork(): WorkUnit[]
  getPendingForWorkUnit(workUnitId: string): Nudge[]
  getAllWorkUnits(): WorkUnit[]
  getAllNudges(): Nudge[]
  getAllRefinements(): Refinement[]
  getWorkStreamStats(): WorkStreamStats
  postFinding(finding: Finding): void
  postChallenge(challenge: Challenge): void
  postConcession(concession: Concession): void
  getFindingsBySource(source: 'yang' | 'yin'): Finding[]
  getChallengesTo(target: 'yang' | 'yin'): Challenge[]
  getAllFindings(): Finding[]
  getAllChallenges(): Challenge[]
  getAllConcessions(): Concession[]
  getDialecticStats(): DialecticStats
  buildExecutiveSummary(): ExecutiveSummary
}
