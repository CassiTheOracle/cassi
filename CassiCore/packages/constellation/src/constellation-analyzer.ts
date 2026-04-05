/**
 * ConstellationAnalyzer — Cross-store analysis engine for completed Constellation sessions.
 *
 * Queries helix.db (work stream, tool calls, events) and constellation.db (Corpus decisions,
 * branch lifecycle, dialectic) to produce a structured diagnosis report with timing
 * breakdown, Corpus health assessment, phase detection, and known failure pattern detection.
 *
 * Design:
 *   - All queries are read-only (opens both databases in read mode)
 *   - No LLM required — rule-based diagnosis engine
 *   - Gracefully handles missing stores (e.g. older sessions before stores were wired)
 *   - Three depth modes: 'summary' | 'timeline' | 'full'
 */

import Database from 'better-sqlite3'
import path from 'node:path'
import fs from 'node:fs'

import { getDataDir } from '../../utils/paths.js'


// Public Types

export type AnalysisDepth = 'summary' | 'timeline' | 'full'

export type CorpusHealth = 'dead' | 'degraded' | 'healthy'

export interface ConstellationAnalysis {
  /** Session identity */
  session: {
    id: string
    helixSessionId: string | null
    goal: string
    status: string
    startedAt: number
    completedAt: number | null
    durationMs: number
    durationFormatted: string
  }

  /** Corpus activity assessment */
  corpus: {
    health: CorpusHealth
    sweepCount: number
    interventionCount: number
    spawnDecisionCount: number
    totalTokens: number
    planStatus: string
    corpusDecisions: CorpusDecisionSummary[]
    diagnosis: string
  }

  /** Per-branch analysis */
  branches: BranchAnalysis[]

  /** Provider errors observed during the run */
  providerIssues: ProviderIssue[]

  /** Top-level diagnosis */
  diagnosis: {
    primaryIssue: string | null
    secondaryIssues: string[]
    recommendations: string[]
    patterns: DetectedPattern[]
  }

  /** Timing summary */
  timing: {
    totalMinutes: number
    longestGapSeconds: number
    medianGapSeconds: number
    gapsOver60s: number
    gapsOver300s: number
    iterationsTotal: number
  }

  /** Full iteration timeline — only present at 'timeline' or 'full' depth */
  timeline?: TimelineEntry[]

  /** Raw constellation store data — only present at 'full' depth */
  constellationStore?: {
    corpusDecisions: RawCorpusDecision[]
    branchLifecycle: RawBranchLifecycleEvent[]
    dialecticCheckpoints: RawDialecticCheckpoint[]
    trainingSignals: RawTrainingSignal[]
    blackboardArchives: RawBlackboardArchive[]
  }

  /** Topology spatial dynamics — present when topology was active during the run */
  topology?: TopologySpatialAnalysis

  /** Metadata */
  meta: {
    helixDbFound: boolean
    constellationDbFound: boolean
    constellationSessionFound: boolean
    analysisDepth: AnalysisDepth
    analyzedAt: number
  }
}

export interface BranchAnalysis {
  helixSessionId: string
  status: string
  durationMs: number
  durationFormatted: string
  iterationCount: number
  toolCallCount: number
  toolBreakdown: Record<string, number>
  nudgeCount: number
  nudgeHighSeverityCount: number
  nudges: NudgeSummary[]
  filesCreated: number
  filesModified: number
  phases: Phase[]
  idleGaps: {
    count: number
    maxSeconds: number
    medianSeconds: number
    over60s: number
    over300s: number
  }
  roles: {
    unityCompletedAt: number | null
    yangCompletedAt: number | null
    yinCompletedAt: number | null
  }
}

export interface NudgeSummary {
  severity: string
  from: string
  preview: string
  timestamp: number
  time: string
}

export interface Phase {
  name: string
  label: string
  iterationStart: number
  iterationEnd: number
  durationMinutes: number
  startTime: string
  endTime: string
  dominantTool: string
  toolCounts: Record<string, number>
}

export interface ProviderIssue {
  provider: string
  model: string
  errorType: string
  count: number
  firstSeen: string
  lastSeen: string
}

export interface DetectedPattern {
  name: string
  severity: 'critical' | 'warning' | 'info'
  description: string
  evidence: string
}

export interface CorpusDecisionSummary {
  type: string
  helixId: string | null
  confidence: number | null
  timestamp: number
  time: string
}

export interface TimelineEntry {
  iteration: number
  time: string
  timestamp: number
  gapSeconds: number
  reasoning: string
  phase: string
  toolCounts: Record<string, number>
}


/**
 * Topology Spatial Dynamics — post-mortem analysis of how Helix sessions
 * moved, clustered, and interacted in the topology space during a run.
 */
export interface TopologySpatialAnalysis {
  /** Whether topology was active during this run */
  enabled: boolean
  /** Total topology ticks (gravity updates) */
  totalTicks: number
  /** Final cluster count */
  clusterCount: number
  /** Final link count */
  linkCount: number
  /** Number of topology events persisted */
  eventCount: number
  /** Per-cluster metrics at completion */
  clusters: ClusterMetric[]
  /** Link formation/dissolution dynamics from events */
  linkDynamics: {
    formationRate: number
    dissolutionRate: number
    averageLifetimeTicks: number
  }
  /** Spatial convergence — did branches cluster over time? */
  convergence: {
    /** Average pairwise distance at completion (lower = more converged) */
    averageDistance: number
    /** Fraction of branches that ended up in a cluster */
    clusterCoverage: number
    /** Whether branches showed meaningful spatial convergence */
    converged: boolean
  }
  /** Topology-specific patterns detected */
  patterns: TopologyPattern[]
}

export interface ClusterMetric {
  clusterId: string
  memberCount: number
  mergeDepth: string
  averageInternalDistance: number
  stabilityScore: number
  ticksStable: number
}

export interface TopologyPattern {
  name: string
  severity: 'info' | 'warning' | 'critical'
  description: string
  evidence: string
}


// Internal raw types
interface RawCorpusDecision {
  id: number
  decision_type: string
  helix_id: string | null
  confidence: number | null
  timestamp: number
}

interface RawBranchLifecycleEvent {
  id: number
  helix_id: string
  event_type: string
  metrics_json: string
  timestamp: number
}

interface RawDialecticCheckpoint {
  id: number
  messages_json: string
  convergence_points_json: string
  tensions_json: string
  stats_json: string
  checkpoint_at: number
}

interface RawTrainingSignal {
  id: number
  signal_type: string
  source_helix_id: string | null
  quality_score: number | null
  extracted_at: number
}

interface RawBlackboardArchive {
  id: number
  helix_id: string | null
  plan_json: string | null
  report_json: string | null
  archived_at: number
}


// Helpers

function openReadOnly(dbPath: string): Database.Database | null {
  try {
    if (!fs.existsSync(dbPath)) return null
    return new Database(dbPath, { readonly: true, fileMustExist: true })
  } catch {
    return null
  }
}

function formatDuration(ms: number): string {
  const totalSecs = Math.floor(ms / 1000)
  const h = Math.floor(totalSecs / 3600)
  const m = Math.floor((totalSecs % 3600) / 60)
  const s = totalSecs % 60
  if (h > 0) return `${h}h ${m}m ${s}s`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

/**
 * @dep callers: flushPhase (core/intelligence/constellation/constellation-analyzer.ts), analyzeConstellation (core/intelligence/constellation/constellation-analyzer.ts)
 * @dep module: Constellation
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString('en-US', { hour12: false })
}

function median(values: number[]): number {
  if (values.length === 0) return 0
  const sorted = [...values].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 === 0
    ? Math.round((sorted[mid - 1] + sorted[mid]) / 2)
    : sorted[mid]
}


// Phase Detector

/**
 * Groups iterations into semantic phases based on dominant tool activity.
 * Uses a sliding window to detect transitions between exploration, creation, testing, etc.
 */
function detectPhases(workUnits: WorkUnitRow[], toolCalls: ToolCallRow[]): Phase[] {
  if (workUnits.length === 0) return []

  // Build per-iteration tool call counts
  const iterToolMap = new Map<number, Record<string, number>>()
  for (const wu of workUnits) {
    const iter = wu.iteration ?? 0
    if (!iterToolMap.has(iter)) iterToolMap.set(iter, {})
  }

  // Group tool calls by iteration (approximate by timestamp window)
  for (let i = 0; i < workUnits.length; i++) {
    const wu = workUnits[i]
    const nextWu = workUnits[i + 1]
    const startTs = wu.timestamp
    const endTs = nextWu?.timestamp ?? wu.timestamp + 300_000
    const iter = wu.iteration ?? 0
    const counts: Record<string, number> = {}

    for (const tc of toolCalls) {
      if (tc.timestamp >= startTs && tc.timestamp < endTs) {
        counts[tc.tool_name] = (counts[tc.tool_name] ?? 0) + 1
      }
    }
    iterToolMap.set(iter, counts)
  }

  // Classify each iteration
  const classifyIter = (counts: Record<string, number>): string => {
    const total = Object.values(counts).reduce((a, b) => a + b, 0)
    if (total === 0) return 'idle'
    const readCount = counts['read_file'] ?? 0
    const writeCount = counts['write_file'] ?? 0
    const testCount = counts['run_tests'] ?? 0
    const shellCount = counts['shell_exec'] ?? 0

    if (readCount / total > 0.6) return 'explore'
    if (writeCount > 0 && writeCount >= readCount) return 'create'
    if (testCount > 0) return 'test'
    if (shellCount > 0) return 'shell'
    if (readCount > 0) return 'review'
    return 'other'
  }

  const PHASE_LABELS: Record<string, string> = {
    explore: 'Exploration (reading codebase)',
    create: 'File Creation',
    test: 'Test Execution',
    shell: 'Shell/Build Operations',
    review: 'Review/Validation',
    idle: 'Idle',
    other: 'Mixed',
  }

  // Group consecutive same-classification iterations into phases
  const phases: Phase[] = []
  let currentPhaseType: string | null = null
  let currentStart: WorkUnitRow | null = null
  let currentIterStart = 0
  let currentTools: Record<string, number> = {}

  const flushPhase = (endWu: WorkUnitRow, iterEnd: number) => {
    if (!currentPhaseType || !currentStart) return
    const durationMs = endWu.timestamp - currentStart.timestamp
    phases.push({
      name: currentPhaseType,
      label: PHASE_LABELS[currentPhaseType] ?? currentPhaseType,
      iterationStart: currentIterStart,
      iterationEnd: iterEnd,
      durationMinutes: Math.round(durationMs / 60_000 * 10) / 10,
      startTime: formatTime(currentStart.timestamp),
      endTime: formatTime(endWu.timestamp),
      dominantTool: Object.entries(currentTools).sort((a, b) => b[1] - a[1])[0]?.[0] ?? 'none',
      toolCounts: { ...currentTools },
    })
    currentTools = {}
  }

  for (let i = 0; i < workUnits.length; i++) {
    const wu = workUnits[i]
    const iter = wu.iteration ?? i + 1
    const counts = iterToolMap.get(iter) ?? {}
    const phaseType = classifyIter(counts)

    // Merge tool counts
    for (const [tool, cnt] of Object.entries(counts)) {
      currentTools[tool] = (currentTools[tool] ?? 0) + cnt
    }

    if (currentPhaseType === null) {
      currentPhaseType = phaseType
      currentStart = wu
      currentIterStart = iter
    } else if (phaseType !== currentPhaseType) {
      // Allow 1-iteration transitions before declaring a new phase
      flushPhase(wu, iter - 1)
      currentPhaseType = phaseType
      currentStart = wu
      currentIterStart = iter
    }
  }

  // Flush last phase
  if (currentStart && workUnits.length > 0) {
    const lastWu = workUnits[workUnits.length - 1]
    flushPhase({ ...lastWu, timestamp: lastWu.timestamp + 60_000 }, (lastWu.iteration ?? workUnits.length))
  }

  return phases
}


// Pattern Detector

function detectPatterns(
  analysis: Omit<ConstellationAnalysis, 'diagnosis' | 'meta'>,
  meta: ConstellationAnalysis['meta'],
): DetectedPattern[] {
  const patterns: DetectedPattern[] = []
  const corpus = analysis.corpus
  const timing = analysis.timing
  const branch = analysis.branches[0]

  // Pattern 1: Corpus Brain-Dead
  if (corpus.health === 'dead') {
    patterns.push({
      name: 'corpus_brain_dead',
      severity: 'critical',
      description: 'Corpus never completed an LLM call — ran as a plain Helix with no strategic oversight.',
      evidence: `0 tokens, 0 sweeps, 0 interventions. Plan status: "${corpus.planStatus}". ` +
        'Root cause: CentralizedProvider.inner not exposing inner provider for setBackgroundOnly, ' +
        'or model routing to blocked/failing provider.',
    })
  }

  // Pattern 2: Dependency Resolution Loop
  if (branch) {
    const shellPhases = branch.phases.filter(p => p.name === 'shell')
    const totalShellIter = shellPhases.reduce((sum, p) => sum + (p.iterationEnd - p.iterationStart + 1), 0)
    if (totalShellIter >= 15) {
      patterns.push({
        name: 'dep_resolution_loop',
        severity: 'warning',
        description: 'Agent spent an excessive number of iterations on shell/build operations.',
        evidence: `${totalShellIter} iterations in shell phases across ${shellPhases.length} phase(s). ` +
          'Typically indicates npm/tsc fix loop without strategic intervention to break it.',
      })
    }
  }

  // Pattern 3: High Idle Percentage
  if (timing.iterationsTotal > 0 && timing.longestGapSeconds > 300) {
    patterns.push({
      name: 'high_idle_time',
      severity: 'warning',
      description: 'Long idle gaps between iterations indicate provider latency or contention.',
      evidence: `Longest gap: ${timing.longestGapSeconds}s. ` +
        `${timing.gapsOver300s} gap(s) > 5 minutes, ${timing.gapsOver60s} gap(s) > 1 minute.`,
    })
  }

  // Pattern 4: Context Thrashing (excessive reads)
  if (branch) {
    const readCount = branch.toolBreakdown['read_file'] ?? 0
    const totalCalls = branch.toolCallCount
    if (totalCalls > 20 && readCount / totalCalls > 0.55) {
      patterns.push({
        name: 'context_thrashing',
        severity: 'warning',
        description: 'Over 55% of tool calls were read_file, suggesting context loss between iterations.',
        evidence: `${readCount} read_file calls out of ${totalCalls} total (${Math.round(readCount / totalCalls * 100)}%). ` +
          'Agent may be re-reading files already in context due to context window pressure.',
      })
    }
  }

  // Pattern 5: ConstellationStore Never Opened (no persistent data)
  if (!meta.constellationSessionFound) {
    patterns.push({
      name: 'store_not_wired',
      severity: 'warning',
      description: 'No ConstellationStore record found — session predates store wiring or daemon restarted mid-run.',
      evidence: 'constellation.db has no entry for this session ID. ' +
        'Corpus tree, branch assessments, and interventions are not persisted.',
    })
  }

  // Pattern 6: Reviewer Escalations
  if (branch && branch.nudgeHighSeverityCount >= 2) {
    patterns.push({
      name: 'reviewer_escalations',
      severity: 'info',
      description: 'Reviewers escalated to high-severity nudges multiple times — branch was repeatedly idle or stuck.',
      evidence: `${branch.nudgeHighSeverityCount} high-severity nudges out of ${branch.nudgeCount} total.`,
    })
  }

  return patterns
}


// Row Types (for SQLite queries)

interface WorkUnitRow {
  id: number
  msg_type: string
  from_role: string | null
  content: string
  timestamp: number
  iteration: number | null
  reasoning: string | null
}

interface ToolCallRow {
  id: number
  tool_name: string
  from_role: string | null
  timestamp: number
}

interface HelixEventRow {
  type: string
  entity: string | null
  message: string
  timestamp: number
}

interface HelixSessionRow {
  id: string
  goal: string
  status: string
  model: string | null
  provider: string | null
  created_at: number
  completed_at: number | null
}


// Main Analyzer

export async function analyzeConstellation(
  constellationSessionId: string,
  depth: AnalysisDepth = 'summary',
): Promise<ConstellationAnalysis> {
  const dataDir = getDataDir()
  const helixDbPath = path.join(dataDir, 'helix.db')
  const constellationDbPath = path.join(dataDir, 'constellation.db')

  const helixDb = openReadOnly(helixDbPath)
  const constDb = openReadOnly(constellationDbPath)

  try {
    // Constellation sessions use helix session IDs like:
    //   helix-constellation-<jobId>-<suffix>
    let helixSessionId: string | null = null
    let helixSession: HelixSessionRow | null = null

    if (helixDb) {
      // Try direct match first
      const directMatch = helixDb.prepare(
        `SELECT id, goal, status, model, provider, created_at, completed_at
         FROM helix_sessions WHERE id = ?`,
      ).get(constellationSessionId) as HelixSessionRow | undefined ?? null

      if (directMatch) {
        helixSession = directMatch
        helixSessionId = directMatch.id
      } else {
        // Try pattern match (constellation session IDs contain the jobId)
        const shortId = constellationSessionId.replace(/^constellation-/, '')
        const patternMatch = helixDb.prepare(
          `SELECT id, goal, status, model, provider, created_at, completed_at
           FROM helix_sessions WHERE id LIKE ? ORDER BY created_at DESC LIMIT 1`,
        ).get(`%${shortId}%`) as HelixSessionRow | undefined ?? null

        if (patternMatch) {
          helixSession = patternMatch
          helixSessionId = patternMatch.id
        }
      }
    }

    let constSession: any = null
    let constBranches: any[] = []
    let corpusDecisions: RawCorpusDecision[] = []
    let branchLifecycle: RawBranchLifecycleEvent[] = []
    let dialecticCheckpoints: RawDialecticCheckpoint[] = []
    let trainingSignals: RawTrainingSignal[] = []
    let blackboardArchives: RawBlackboardArchive[] = []

    if (constDb) {
      constSession = constDb.prepare(
        `SELECT * FROM constellation_sessions WHERE id = ?`,
      ).get(constellationSessionId) ?? null

      if (constSession) {
        constBranches = constDb.prepare(
          `SELECT * FROM constellation_branches WHERE session_id = ? ORDER BY created_at`,
        ).all(constellationSessionId) as any[]

        corpusDecisions = constDb.prepare(
          `SELECT id, decision_type, helix_id, confidence, timestamp
           FROM corpus_decisions WHERE session_id = ? ORDER BY timestamp`,
        ).all(constellationSessionId) as RawCorpusDecision[]

        branchLifecycle = constDb.prepare(
          `SELECT id, helix_id, event_type, metrics_json, timestamp
           FROM branch_lifecycle_events WHERE session_id = ? ORDER BY timestamp`,
        ).all(constellationSessionId) as RawBranchLifecycleEvent[]

        dialecticCheckpoints = constDb.prepare(
          `SELECT id, messages_json, convergence_points_json, tensions_json, stats_json, checkpoint_at
           FROM constellation_dialectic WHERE session_id = ? ORDER BY checkpoint_at`,
        ).all(constellationSessionId) as RawDialecticCheckpoint[]

        trainingSignals = constDb.prepare(
          `SELECT id, signal_type, source_helix_id, quality_score, extracted_at
           FROM training_signals WHERE session_id = ? ORDER BY quality_score DESC`,
        ).all(constellationSessionId) as RawTrainingSignal[]

        blackboardArchives = constDb.prepare(
          `SELECT id, helix_id, plan_json, report_json, archived_at
           FROM blackboard_archives WHERE session_id = ? ORDER BY archived_at`,
        ).all(constellationSessionId) as RawBlackboardArchive[]
      }
    }

    const branches: BranchAnalysis[] = []

    if (helixDb && helixSessionId) {
      const workUnits: WorkUnitRow[] = (helixDb.prepare(
        `SELECT id, msg_type, from_role, content, timestamp,
                json_extract(content, '$.workUnit.iteration') as iteration,
                json_extract(content, '$.workUnit.reasoning') as reasoning
         FROM helix_work_stream
         WHERE session_id = ? AND msg_type = 'work_unit'
         ORDER BY timestamp`,
      ).all(helixSessionId) as WorkUnitRow[])

      const nudges: WorkUnitRow[] = (helixDb.prepare(
        `SELECT id, msg_type, from_role, content, timestamp,
                NULL as iteration, NULL as reasoning
         FROM helix_work_stream
         WHERE session_id = ? AND msg_type = 'nudge'
         ORDER BY timestamp`,
      ).all(helixSessionId) as WorkUnitRow[])

      const toolCalls: ToolCallRow[] = (helixDb.prepare(
        `SELECT id, tool_name, from_role, timestamp
         FROM helix_tool_calls WHERE session_id = ? ORDER BY timestamp`,
      ).all(helixSessionId) as ToolCallRow[])

      const events: HelixEventRow[] = (helixDb.prepare(
        `SELECT type, entity, message, timestamp FROM helix_events
         WHERE session_id = ? ORDER BY timestamp`,
      ).all(helixSessionId) as HelixEventRow[])

      // Compute gaps between work units
      const gaps: number[] = []
      for (let i = 1; i < workUnits.length; i++) {
        gaps.push((workUnits[i].timestamp - workUnits[i - 1].timestamp) / 1000)
      }

      // Tool breakdown
      const toolBreakdown: Record<string, number> = {}
      for (const tc of toolCalls) {
        toolBreakdown[tc.tool_name] = (toolBreakdown[tc.tool_name] ?? 0) + 1
      }

      // Role completion times
      const rolesCompleted = {
        unityCompletedAt: events.find(e => e.type === 'helix:role:completed' && e.entity === 'unity')?.timestamp ?? null,
        yangCompletedAt: events.find(e => e.type === 'helix:role:completed' && e.entity === 'yang')?.timestamp ?? null,
        yinCompletedAt: events.find(e => e.type === 'helix:role:completed' && e.entity === 'yin')?.timestamp ?? null,
      }

      // Parse nudges
      const nudgeSummaries: NudgeSummary[] = nudges.map(n => {
        let parsed: any = {}
        try { parsed = JSON.parse(n.content) } catch { /* ignore */ }
        return {
          severity: parsed?.nudge?.severity ?? 'low',
          from: parsed?.nudge?.from ?? (n.from_role ?? 'unknown'),
          preview: (parsed?.nudge?.content ?? '').slice(0, 150),
          timestamp: n.timestamp,
          time: formatTime(n.timestamp),
        }
      })

      // Count files created/modified from tool calls
      const writeCalls = toolCalls.filter(tc => tc.tool_name === 'write_file')
      const filesCreated = writeCalls.length  // approximate

      // Phase detection
      const phases = detectPhases(workUnits, toolCalls)

      // Session start/end
      const startTs = helixSession?.created_at ?? workUnits[0]?.timestamp ?? Date.now()
      const endTs = helixSession?.completed_at
        ?? events.find(e => e.type === 'helix:completed')?.timestamp
        ?? workUnits[workUnits.length - 1]?.timestamp
        ?? Date.now()
      const durationMs = endTs - startTs

      branches.push({
        helixSessionId,
        status: helixSession?.status ?? 'unknown',
        durationMs,
        durationFormatted: formatDuration(durationMs),
        iterationCount: workUnits.length,
        toolCallCount: toolCalls.length,
        toolBreakdown,
        nudgeCount: nudges.length,
        nudgeHighSeverityCount: nudgeSummaries.filter(n => n.severity === 'high').length,
        nudges: nudgeSummaries,
        filesCreated,
        filesModified: writeCalls.length,
        phases,
        idleGaps: {
          count: gaps.length,
          maxSeconds: gaps.length > 0 ? Math.round(Math.max(...gaps)) : 0,
          medianSeconds: median(gaps),
          over60s: gaps.filter(g => g > 60).length,
          over300s: gaps.filter(g => g > 300).length,
        },
        roles: rolesCompleted,
      })
    }

    const sweepCount = constSession?.sweep_count ?? 0
    const interventionCount = corpusDecisions.filter(d => d.decision_type === 'intervention').length
    const spawnDecisionCount = corpusDecisions.filter(d => d.decision_type === 'spawn_evaluation').length
    const totalTokens = constSession?.tokens_used ?? 0
    const planStatus = constSession ? (constSession.status ?? 'unknown') : 'not_recorded'

    let corpusHealth: CorpusHealth
    let corpusDiagnosis: string
    if (totalTokens === 0 && sweepCount === 0) {
      corpusHealth = 'dead'
      corpusDiagnosis = 'Corpus never completed an LLM call. The Constellation ran as a plain Helix with no Corpus oversight. ' +
        'Check provider routing: CentralizedProvider.inner bug may prevent setBackgroundOnly from firing, ' +
        'or the model was directed to a provider that rejects premium models.'
    } else if (sweepCount > 0 && interventionCount === 0 && spawnDecisionCount === 0) {
      corpusHealth = 'degraded'
      corpusDiagnosis = `Corpus made ${sweepCount} sweep(s) but never intervened or spawned new branches. ` +
        'The Corpus LLM was reachable but did not act on what it observed. ' +
        'Consider tuning intervention thresholds or checking if the task was too simple for multi-branch.'
    } else {
      corpusHealth = 'healthy'
      corpusDiagnosis = `Corpus made ${sweepCount} sweeps, ${interventionCount} interventions, ${spawnDecisionCount} spawn decisions.`
    }

    const branch = branches[0]
    const totalMinutes = branch ? Math.round(branch.durationMs / 60_000 * 10) / 10 : 0

    const timing = {
      totalMinutes,
      longestGapSeconds: branch?.idleGaps.maxSeconds ?? 0,
      medianGapSeconds: branch?.idleGaps.medianSeconds ?? 0,
      gapsOver60s: branch?.idleGaps.over60s ?? 0,
      gapsOver300s: branch?.idleGaps.over300s ?? 0,
      iterationsTotal: branch?.iterationCount ?? 0,
    }

    // Since we don't have a provider error DB, we detect from nudge content
    const providerIssues: ProviderIssue[] = []
    if (branch) {
      const errorNudges = branch.nudges.filter(n => n.preview.toLowerCase().includes('idle'))
      if (errorNudges.length > 0 && corpusHealth === 'dead') {
        providerIssues.push({
          provider: 'github-copilot',
          model: 'claude-opus-4.6',
          errorType: 'backgroundOnly_bypass — premium model sent to wrong provider',
          count: errorNudges.length,
          firstSeen: errorNudges[0].time,
          lastSeen: errorNudges[errorNudges.length - 1].time,
        })
      }
    }

    const corpusDecisionSummaries: CorpusDecisionSummary[] = corpusDecisions.map(d => ({
      type: d.decision_type,
      helixId: d.helix_id,
      confidence: d.confidence,
      timestamp: d.timestamp,
      time: formatTime(d.timestamp),
    }))

    const sessionStartedAt = helixSession?.created_at
      ?? (branch ? branch.durationMs > 0 ? Date.now() - branch.durationMs : Date.now() : Date.now())
    const sessionCompletedAt = helixSession?.completed_at ?? null
    const sessionDurationMs = sessionCompletedAt
      ? sessionCompletedAt - sessionStartedAt
      : (branch?.durationMs ?? 0)

    const partialAnalysis: Omit<ConstellationAnalysis, 'diagnosis' | 'meta'> = {
      session: {
        id: constellationSessionId,
        helixSessionId,
        goal: helixSession?.goal ?? constSession?.goal ?? 'unknown',
        status: constSession?.status ?? helixSession?.status ?? 'unknown',
        startedAt: sessionStartedAt,
        completedAt: sessionCompletedAt,
        durationMs: sessionDurationMs,
        durationFormatted: formatDuration(sessionDurationMs),
      },
      corpus: {
        health: corpusHealth,
        sweepCount,
        interventionCount,
        spawnDecisionCount,
        totalTokens,
        planStatus,
        corpusDecisions: corpusDecisionSummaries,
        diagnosis: corpusDiagnosis,
      },
      branches,
      providerIssues,
      timing,
    }

    const meta = {
      helixDbFound: helixDb !== null,
      constellationDbFound: constDb !== null,
      constellationSessionFound: constSession !== null,
      analysisDepth: depth,
      analyzedAt: Date.now(),
    }
    const patterns = detectPatterns(partialAnalysis, meta)

    const primaryIssue = patterns.find(p => p.severity === 'critical')?.description
      ?? patterns.find(p => p.severity === 'warning')?.description
      ?? null

    const secondaryIssues = patterns
      .filter(p => p.description !== primaryIssue)
      .map(p => p.description)

    const recommendations = generateRecommendations(patterns, partialAnalysis)

    let timeline: TimelineEntry[] | undefined
    if ((depth === 'timeline' || depth === 'full') && branch) {
      if (helixDb && helixSessionId) {
        const workUnitsForTimeline: WorkUnitRow[] = (helixDb.prepare(
          `SELECT id, msg_type, from_role, content, timestamp,
                  json_extract(content, '$.workUnit.iteration') as iteration,
                  json_extract(content, '$.workUnit.reasoning') as reasoning
           FROM helix_work_stream
           WHERE session_id = ? AND msg_type = 'work_unit'
           ORDER BY timestamp`,
        ).all(helixSessionId) as WorkUnitRow[])

        const toolCallsForTimeline: ToolCallRow[] = (helixDb.prepare(
          `SELECT id, tool_name, from_role, timestamp
           FROM helix_tool_calls WHERE session_id = ? ORDER BY timestamp`,
        ).all(helixSessionId) as ToolCallRow[])

        const phases = detectPhases(workUnitsForTimeline, toolCallsForTimeline)

        // Build phase lookup by iteration
        const getPhaseForIter = (iter: number): string => {
          for (const p of phases) {
            if (iter >= p.iterationStart && iter <= p.iterationEnd) return p.label
          }
          return 'unknown'
        }

        timeline = workUnitsForTimeline.map((wu, i) => {
          const prevTs = workUnitsForTimeline[i - 1]?.timestamp
          const gapSeconds = prevTs ? Math.round((wu.timestamp - prevTs) / 1000) : 0
          const iter = wu.iteration ?? i + 1

          // Get tool calls in this iteration window
          const nextTs = workUnitsForTimeline[i + 1]?.timestamp
          const iterToolCounts: Record<string, number> = {}
          for (const tc of toolCallsForTimeline) {
            if (tc.timestamp >= wu.timestamp && (!nextTs || tc.timestamp < nextTs)) {
              iterToolCounts[tc.tool_name] = (iterToolCounts[tc.tool_name] ?? 0) + 1
            }
          }

          return {
            iteration: iter,
            time: formatTime(wu.timestamp),
            timestamp: wu.timestamp,
            gapSeconds,
            reasoning: (wu.reasoning ?? '').slice(0, 120),
            phase: getPhaseForIter(iter),
            toolCounts: iterToolCounts,
          }
        })
      }
    }

    const result: ConstellationAnalysis = {
      ...partialAnalysis,
      diagnosis: {
        primaryIssue,
        secondaryIssues,
        recommendations,
        patterns,
      },
      meta,
    }

    if (timeline !== undefined) result.timeline = timeline

    // Topology spatial dynamics analysis (uses persisted topology snapshots + events)
    if (constDb && constSession) {
      const topoAnalysis = analyzeTopology(constDb, constellationSessionId)
      if (topoAnalysis) {
        result.topology = topoAnalysis

        // Merge topology patterns into main diagnosis patterns
        for (const tp of topoAnalysis.patterns) {
          if (tp.severity === 'warning' || tp.severity === 'critical') {
            patterns.push({
              name: `topology_${tp.name}`,
              severity: tp.severity,
              description: tp.description,
              evidence: tp.evidence,
            })
          }
        }

        // Re-generate recommendations with topology patterns included
        result.diagnosis.recommendations = generateRecommendations(patterns, partialAnalysis)
      }
    }

    if (depth === 'full') {
      result.constellationStore = {
        corpusDecisions,
        branchLifecycle,
        dialecticCheckpoints,
        trainingSignals,
        blackboardArchives,
      }
    }

    return result
  } finally {
    helixDb?.close()
    constDb?.close()
  }
}


/**
 * Analyze topology spatial dynamics from persisted tree snapshot and events.
 * WHY: Topology data was ephemeral before the persistence layer was added.
 * Now that snapshots and events are stored, we can analyze how branches
 * moved, clustered, and interacted after the run completes.
 */
function analyzeTopology(
  constDb: InstanceType<typeof Database>,
  constellationSessionId: string,
): TopologySpatialAnalysis | undefined {
  // Read tree snapshot to get final topology state
  const sessionRow = constDb.prepare(
    `SELECT tree_snapshot_json FROM constellation_sessions WHERE id = ?`,
  ).get(constellationSessionId) as { tree_snapshot_json: string | null } | undefined

  let topology: any = null
  if (sessionRow?.tree_snapshot_json) {
    try {
      const tree = JSON.parse(sessionRow.tree_snapshot_json)
      topology = tree.topology
    } catch {
      // Malformed JSON — skip
    }
  }

  // Read topology events for dynamics analysis
  const topologyEvents = constDb.prepare(
    `SELECT type, entity, message, data_json, timestamp
     FROM constellation_events
     WHERE session_id = ? AND type LIKE 'topology:%'
     ORDER BY timestamp`,
  ).all(constellationSessionId) as Array<{
    type: string
    entity: string | null
    message: string
    data_json: string | null
    timestamp: number
  }>

  // If no topology data at all, topology wasn't active
  if (!topology && topologyEvents.length === 0) return undefined

  const eventCount = topologyEvents.length
  const updateEvents = topologyEvents.filter(e => e.type === 'topology:updated')

  // Parse final snapshot data
  const positions: any[] = topology?.positions ?? []
  const links: any[] = topology?.links ?? []
  const clusters: any[] = topology?.clusters ?? []
  const distances: Record<string, Record<string, number>> = topology?.distances ?? {}
  const tickCount = topology?.tickCount ?? 0

  // Compute cluster metrics
  const clusterMetrics: ClusterMetric[] = clusters.map((c: any) => ({
    clusterId: c.clusterId,
    memberCount: c.members?.length ?? 0,
    mergeDepth: c.effectiveMergeDepth ?? 'shallow',
    averageInternalDistance: c.averageInternalDistance ?? 0,
    stabilityScore: c.stabilityScore ?? 0,
    ticksStable: c.ticksStable ?? 0,
  }))

  // Compute link dynamics from events
  const linkFormed = topologyEvents.filter(e => e.type === 'topology:link_formed').length
  const linkDissolved = topologyEvents.filter(e => e.type === 'topology:link_dissolved').length
  const totalTopologyTime = updateEvents.length > 1
    ? (updateEvents[updateEvents.length - 1].timestamp - updateEvents[0].timestamp) / 1000
    : 0
  const formationRate = totalTopologyTime > 0 ? linkFormed / totalTopologyTime : 0
  const dissolutionRate = totalTopologyTime > 0 ? linkDissolved / totalTopologyTime : 0

  // Average link lifetime (estimated from tick count and current link count)
  const avgLifetime = links.length > 0
    ? links.reduce((sum: number, l: any) => sum + (l.stabilityTicks ?? 0), 0) / links.length
    : 0

  // Compute spatial convergence
  const distanceValues: number[] = []
  for (const outerKey of Object.keys(distances)) {
    for (const innerKey of Object.keys(distances[outerKey])) {
      if (outerKey !== innerKey) {
        distanceValues.push(distances[outerKey][innerKey])
      }
    }
  }
  const averageDistance = distanceValues.length > 0
    ? distanceValues.reduce((a, b) => a + b, 0) / distanceValues.length
    : 0

  const totalBranches = positions.length
  const clusteredBranches = new Set(clusters.flatMap((c: any) => c.members ?? []))
  const clusterCoverage = totalBranches > 0 ? clusteredBranches.size / totalBranches : 0

  // Detect topology-specific patterns
  const topoPatterns: TopologyPattern[] = []

  // Pattern: No topology ticks
  if (tickCount === 0 && positions.length > 0) {
    topoPatterns.push({
      name: 'topology_inactive',
      severity: 'warning',
      description: 'Topology was initialized but never ticked — no spatial coordination occurred.',
      evidence: `${positions.length} positions registered, 0 ticks processed.`,
    })
  }

  // Pattern: No clusters formed
  if (tickCount > 5 && clusters.length === 0 && positions.length >= 2) {
    topoPatterns.push({
      name: 'no_clustering',
      severity: 'info',
      description: 'No clusters formed despite multiple branches — branches worked on distinct topics.',
      evidence: `${tickCount} ticks, ${positions.length} branches, 0 clusters. Average distance: ${averageDistance.toFixed(2)}.`,
    })
  }

  // Pattern: High link churn
  if (linkFormed > 0 && dissolutionRate > formationRate * 0.5) {
    topoPatterns.push({
      name: 'link_churn',
      severity: 'warning',
      description: 'High link dissolution rate — branches repeatedly approached then diverged.',
      evidence: `${linkFormed} links formed, ${linkDissolved} dissolved. Formation: ${formationRate.toFixed(3)}/s, Dissolution: ${dissolutionRate.toFixed(3)}/s.`,
    })
  }

  // Pattern: Single mega-cluster (all branches in one cluster)
  if (clusters.length === 1 && clusterCoverage > 0.8) {
    topoPatterns.push({
      name: 'mega_cluster',
      severity: 'warning',
      description: 'All branches converged into a single cluster — goal decomposition may be too narrow.',
      evidence: `${clusteredBranches.size}/${totalBranches} branches in cluster "${clusters[0].clusterId}". Average distance: ${averageDistance.toFixed(2)}.`,
    })
  }

  // Pattern: Good spatial diversity
  if (clusters.length >= 2 && clusterCoverage > 0.6) {
    topoPatterns.push({
      name: 'good_spatial_diversity',
      severity: 'info',
      description: 'Branches formed multiple distinct clusters — goal was well-decomposed across different aspects.',
      evidence: `${clusters.length} clusters covering ${Math.round(clusterCoverage * 100)}% of branches.`,
    })
  }

  // Pattern: Unstable clusters (low stability score)
  const unstableClusters = clusterMetrics.filter(c => c.stabilityScore < 0.3 && c.ticksStable < 3)
  if (unstableClusters.length > 0) {
    topoPatterns.push({
      name: 'unstable_clusters',
      severity: 'info',
      description: 'Some clusters were unstable — branches were still in flux when the run completed.',
      evidence: `${unstableClusters.length} cluster(s) with stability < 0.3: ${unstableClusters.map(c => c.clusterId).join(', ')}.`,
    })
  }

  return {
    enabled: true,
    totalTicks: tickCount,
    clusterCount: clusters.length,
    linkCount: links.length,
    eventCount,
    clusters: clusterMetrics,
    linkDynamics: {
      formationRate,
      dissolutionRate,
      averageLifetimeTicks: avgLifetime,
    },
    convergence: {
      averageDistance,
      clusterCoverage,
      converged: clusterCoverage > 0.5 && averageDistance < 2.0,
    },
    patterns: topoPatterns,
  }
}


function generateRecommendations(
  patterns: DetectedPattern[],
  analysis: Omit<ConstellationAnalysis, 'diagnosis' | 'meta'>,
): string[] {
  const recs: string[] = []

  for (const pattern of patterns) {
    switch (pattern.name) {
      case 'corpus_brain_dead':
        recs.push(
          'Verify CentralizedProvider.inner exposes the inner provider (fixed in recent commit).',
          'Check model routing: Corpus should use copilot-sdk/claude-opus-4.6, not github-copilot.',
          'After a daemon restart, re-run the constellation — the wiring is done at boot.',
        )
        break
      case 'dep_resolution_loop':
        recs.push(
          'Add a Corpus intervention threshold for shell-heavy iterations: if shell% > 50% for 10+ iterations, intervene.',
          'Consider pre-validating package.json changes in the goal context before the agent starts.',
        )
        break
      case 'high_idle_time':
        recs.push(
          `Median gap of ${analysis.timing.medianGapSeconds}s suggests provider throughput contention. Consider switching to a faster model for worker slots.`,
          'Check if multiple constellations or other heavy jobs are running concurrently.',
        )
        break
      case 'context_thrashing':
        recs.push(
          'Increase context retention between iterations in the posture runner to avoid redundant reads.',
          'Consider using GitNexus for structural lookups instead of read_file for previously-seen files.',
        )
        break
      case 'store_not_wired':
        recs.push(
          'ConstellationStore is now wired at daemon boot — this will be fixed in future runs.',
          'If analyzing an older session, some data (Corpus tree, branch assessments) will not be available.',
        )
        break
      case 'reviewer_escalations':
        recs.push(
          'High-severity reviewer nudges indicate the agent went idle. Tighten idle detection or lower the escalation threshold.',
        )
        break
      case 'topology_topology_inactive':
        recs.push(
          'Topology was initialized but never ran. Verify embedding service is available and digests are being published.',
        )
        break
      case 'topology_link_churn':
        recs.push(
          'High link dissolution suggests branches are exploring neighboring topics then diverging. Consider using tighter link thresholds or longer stability requirements.',
        )
        break
      case 'topology_mega_cluster':
        recs.push(
          'All branches converged into one cluster. Consider decomposing the goal into more distinct sub-tasks, or increasing repulsion strength to encourage spatial diversity.',
        )
        break
    }
  }

  // Dedup
  return [...new Set(recs)]
}
