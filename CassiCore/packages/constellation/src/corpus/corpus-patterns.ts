/**
 * Pattern Detector — Cross-branch pattern detection for the Corpus organizer.
 *
 * Extracted from corpus.ts to improve modularity and testability.
 * Detects patterns like conflict, redundancy, divergence, and cascade failure
 * across multiple Helix branches.
 */

import type { ILogger, IEventBus } from '../../../../types/interfaces.js'
import type {
  ICorpusTree,
  CorpusProcessedState,
  CrossHelixPattern,
  BranchAssessment,
} from '../corpus-types.js'
import type { TopologyGraph } from '../topology/topology-graph.js'


/**
 * PatternDetector — Detects cross-branch patterns in a Constellation.
 *
 * Reads from the shared CorpusTree and processed state to detect patterns
 * like conflict (file overlap), redundancy (duplicate approaches), cascade
 * failure, and asymmetric progress.
 */
export class PatternDetector {
  private tree: ICorpusTree
  private state: CorpusProcessedState
  private topology?: TopologyGraph
  private eventBus?: IEventBus
  private logger: ILogger

  constructor(deps: {
    tree: ICorpusTree
    state: CorpusProcessedState
    topology?: TopologyGraph
    eventBus?: IEventBus
    logger: ILogger
  }) {
    this.tree = deps.tree
    this.state = deps.state
    this.topology = deps.topology
    this.eventBus = deps.eventBus
    this.logger = deps.logger.child('PatternDetector')
  }

  /**
   * Detect cross-branch patterns.
   *
   * Scans for:
   * 1. Conflict — file overlap between branches
   * 2. Asymmetric progress — one branch lagging behind siblings
   * 3. Cascade failure — multiple branches failing simultaneously
   * 4. Convergence — multiple branches showing strong progress
   * 5. Topology-enhanced patterns — redundancy and cluster-based conflict escalation
   *
   * @returns New patterns detected this sweep (de-duplicated against existing)
   */
  detect(): CrossHelixPattern[] {
    const patterns: CrossHelixPattern[] = []
    const assessments = Array.from(this.state.branchAssessments.values())
    const branches = this.tree.getAllBranches()

    // 1. Conflict: filesModified Set intersection across branches
    this.detectFileConflicts(assessments, patterns)

    // 2. Asymmetric progress: one branch has 3+ more steps than sibling
    this.detectAsymmetricProgress(branches, patterns)

    // 3. Cascade failure: 2+ branches 'failed'/'struggling' created within 30s
    this.detectCascadeFailure(branches, patterns)

    // 4. Convergence: 2+ branches with dominantPattern 'implementation' and rollingScore > 0.7
    this.detectConvergence(assessments, patterns)

    // 5. Topology-enhanced pattern detection
    this.detectTopologyPatterns(patterns)

    // De-duplicate against existing patterns (5-minute window prevents spam)
    const newPatterns = this.deduplicatePatterns(patterns)

    // Prune old patterns to prevent unbounded growth (keep last 50)
    if (this.state.crossPatterns.length > 50) {
      this.state.crossPatterns = this.state.crossPatterns.slice(-50)
    }

    return newPatterns
  }

  /**
   * Detect file conflicts between branches.
   * Branches modifying the same files may be creating conflicting changes.
   */
  private detectFileConflicts(
    assessments: BranchAssessment[],
    patterns: CrossHelixPattern[],
  ): void {
    for (let i = 0; i < assessments.length; i++) {
      for (let j = i + 1; j < assessments.length; j++) {
        const a = assessments[i]
        const b = assessments[j]
        const intersection = new Set(
          [...a.filesModified].filter((x) => b.filesModified.has(x))
        )
        if (intersection.size > 0) {
          patterns.push({
            type: 'conflict',
            helixIds: [a.helixId, b.helixId],
            severity: 'high',
            description: `Branches ${a.helixId} and ${b.helixId} may be modifying the same work units`,
            detectedAt: Date.now(),
            actedUpon: false,
          })
        }
      }
    }
  }

  /**
   * Detect asymmetric progress between sibling branches.
   * One branch lagging significantly behind siblings with low scores.
   */
  private detectAsymmetricProgress(
    branches: ReturnType<ICorpusTree['getAllBranches']>,
    patterns: CrossHelixPattern[],
  ): void {
    for (const branch of branches) {
      if (!branch.parentId) continue
      const siblings = branches.filter(
        (b) => b.parentId === branch.parentId && b.helixId !== branch.helixId
      )
      for (const sibling of siblings) {
        const diff = branch.steps.length - sibling.steps.length
        if (diff >= 3) {
          const siblingAssessment = this.state.branchAssessments.get(sibling.helixId)
          if (siblingAssessment && siblingAssessment.rollingScore < 0.5) {
            patterns.push({
              type: 'asymmetric-progress',
              helixIds: [branch.helixId, sibling.helixId],
              severity: 'medium',
              description: `${sibling.helixId} is lagging behind ${branch.helixId} with low scores`,
              detectedAt: Date.now(),
              actedUpon: false,
            })
          }
        }
      }
    }
  }

  /**
   * Detect cascade failure — multiple branches failing within a short window.
   */
  private detectCascadeFailure(
    branches: ReturnType<ICorpusTree['getAllBranches']>,
    patterns: CrossHelixPattern[],
  ): void {
    const strugglingBranches = branches.filter(
      (b) => b.status === 'failed' || this.state.branchAssessments.get(b.helixId)?.status === 'struggling'
    )
    if (strugglingBranches.length >= 2) {
      const timestamps = strugglingBranches.map((b) => b.createdAt).sort((a, b) => a - b)
      if (timestamps[timestamps.length - 1] - timestamps[0] < 30000) {
        patterns.push({
          type: 'cascade-failure',
          helixIds: strugglingBranches.map((b) => b.helixId),
          severity: 'critical',
          description: `Multiple branches failing within 30 seconds: ${strugglingBranches.map((b) => b.helixId).join(', ')}`,
          detectedAt: Date.now(),
          actedUpon: false,
        })
      }
    }
  }

  /**
   * Detect convergence — multiple branches showing strong implementation progress.
   */
  private detectConvergence(
    assessments: BranchAssessment[],
    patterns: CrossHelixPattern[],
  ): void {
    const highPerformingImpls = assessments.filter(
      (a) => a.dominantPattern === 'implementation' && a.rollingScore > 0.7
    )
    if (highPerformingImpls.length >= 2) {
      patterns.push({
        type: 'convergence',
        helixIds: highPerformingImpls.map((a) => a.helixId),
        severity: 'low',
        description: `Multiple branches showing strong implementation progress`,
        detectedAt: Date.now(),
        actedUpon: false,
      })
    }
  }

  /**
   * Detect topology-enhanced patterns.
   *
   * Uses spatial clustering to detect redundancy (branches in same cluster with
   * similar approaches) and escalate conflict severity when conflicting branches
   * are clustered together.
   */
  private detectTopologyPatterns(patterns: CrossHelixPattern[]): void {
    if (!this.topology?.enabled) return

    const snapshot = this.topology.getSnapshot()

    // Redundancy: branches in the same cluster with same approach
    for (const cluster of snapshot.clusters) {
      if (cluster.members.length < 2) continue
      const clusterAssessments = cluster.members
        .map(id => this.state.branchAssessments.get(id))
        .filter((a): a is BranchAssessment => !!a)

      // Group by dominant approach
      const byApproach = new Map<string, BranchAssessment[]>()
      for (const a of clusterAssessments) {
        const key = String(a.dominantPattern)
        const existing = byApproach.get(key) ?? []
        existing.push(a)
        byApproach.set(key, existing)
      }

      for (const [approach, group] of byApproach) {
        if (group.length >= 2 && approach !== 'none') {
          patterns.push({
            type: 'redundancy',
            helixIds: group.map(a => a.helixId),
            severity: 'medium',
            description: `Topology cluster "${cluster.clusterId}" contains ${group.length} branches with approach "${approach}" — possible redundancy`,
            suggestedAction: 'Consider merging or redirecting one branch to a different aspect',
            detectedAt: Date.now(),
            actedUpon: false,
          })
        }
      }
    }

    // Escalate conflict severity when conflicting branches are in the same cluster
    for (const pattern of patterns) {
      if (pattern.type === 'conflict' && pattern.severity !== 'critical') {
        const [idA, idB] = pattern.helixIds
        if (idA && idB && this.topology.areInSameCluster(idA, idB)) {
          pattern.severity = 'critical'
          pattern.description += ' (topology confirms: branches are in same cluster — high collision risk)'
        }
      }
    }
  }

  /**
   * De-duplicate patterns against existing patterns.
   * Prevents pattern spam across sweeps with a 5-minute window.
   */
  private deduplicatePatterns(patterns: CrossHelixPattern[]): CrossHelixPattern[] {
    const now = Date.now()
    const newPatterns: CrossHelixPattern[] = []

    for (const pattern of patterns) {
      const isDuplicate = this.state.crossPatterns.some(
        (existing) =>
          existing.type === pattern.type &&
          existing.helixIds.length === pattern.helixIds.length &&
          existing.helixIds.every((id) => pattern.helixIds.includes(id)) &&
          now - existing.detectedAt < 300_000 // 5-minute window
      )
      if (!isDuplicate) {
        newPatterns.push(pattern)
        this.state.crossPatterns.push(pattern)
        this.emitEvent('corpus:pattern', {
          type: pattern.type,
          helixIds: pattern.helixIds,
          severity: pattern.severity,
        })
      }
    }

    return newPatterns
  }

  private emitEvent(type: string, data: Record<string, unknown>): void {
    this.eventBus?.emit({
      type: type as any,
      ...data,
    } as any)
  }
}