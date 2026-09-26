/**
 * CorpusTree — Shared Thought Tree for Constellation-level reasoning
 *
 * The CorpusTree is the shared data structure that connects child Helix
 * Brainstems to the Corpus and to each other. It serves three purposes:
 *
 * 1. **Branch tracking**: Brainstems push annotations into their branch,
 *    and the Corpus reads from it to detect cross-branch patterns.
 *
 * 2. **Peer awareness**: Brainstems publish digests (compact summaries)
 *    and create/contribute to shared topic nodes. Other Brainstems read
 *    these for stigmergic self-organization — no central relay needed.
 *
 * 3. **Self-awareness**: Strategy retrospectives, effectiveness tracking,
 *    and an elevated pattern library enable the constellation to learn
 *    what works and propagate successful strategies.
 *
 * Named after the corpus callosum — the nerve fiber tract connecting
 * brain hemispheres, enabling coordinated thought across regions.
 */

import type { ILogger } from './vendor/types/interfaces.js'
import type {
  ICorpusTree,
  CorpusBranch,
  CorpusStep,
  CorpusTreeSnapshot,
  CorpusBranchSnapshot,
  BranchDigest,
  TopicNode,
  TopicContribution,
  StrategyRetrospective,
  ElevatedPattern,
  EffectivenessRecord,
} from './corpus-types.js'
import type { BrainstemAnnotation } from './vendor/helix/brainstem-types.js'


/**
 * CorpusTree — Shared Thought Tree for the Constellation.
 *
 * Child Helix Brainstems push annotations and digests into it.
 * The Corpus and peer Brainstems read from it.
 * The tree is the single source of truth for what every Helix is doing.
 */
export class CorpusTree implements ICorpusTree {
  private branches: Map<string, CorpusBranch>
  private digests: Map<string, BranchDigest>
  private topics: Map<string, TopicNode>
  private retrospectives: StrategyRetrospective[]
  private elevatedPatterns: ElevatedPattern[]
  private effectivenessRecords: EffectivenessRecord[]
  private topicIdCounter: number
  private patternIdCounter: number
  private logger: ILogger
  onPatternElevated?: (pattern: ElevatedPattern) => void

  constructor(logger: ILogger) {
    this.branches = new Map()
    this.digests = new Map()
    this.topics = new Map()
    this.retrospectives = []
    this.elevatedPatterns = []
    this.effectivenessRecords = []
    this.topicIdCounter = 0
    this.patternIdCounter = 0
    this.logger = logger.child('CorpusTree')
  }

  // Branch Management (existing)

  /**
   * Register a new branch when a Helix starts.
   * Throws if helixId is already registered.
   */
  registerBranch(
    helixId: string,
    goal: string,
    depth: number,
    parentId?: string
  ): void {
    if (this.branches.has(helixId)) {
      throw new Error(`Branch already registered for helix: ${helixId}`)
    }

    const branch: CorpusBranch = {
      helixId,
      goal,
      depth,
      parentId,
      steps: [],
      status: 'active',
      createdAt: Date.now(),
    }

    this.branches.set(helixId, branch)
    this.logger.info('Branch registered', {
      helixId,
      goal,
      depth,
      parentId,
    })
  }

  /**
   * Push an annotation into a Helix's branch.
   * Auto-registers the branch with goal='unknown' depth=0 if not registered yet (defensive).
   */
  pushAnnotation(helixId: string, annotation: BrainstemAnnotation, toolCalls?: Array<{ name: string; args: string }>): void {
    let branch = this.branches.get(helixId)

    if (!branch) {
      // Defensive auto-registration
      branch = {
        helixId,
        goal: 'unknown',
        depth: 0,
        steps: [],
        status: 'active',
        createdAt: Date.now(),
      }
      this.branches.set(helixId, branch)
      this.logger.warn('Branch auto-registered on pushAnnotation', {
        helixId,
        annotationWorkUnitId: annotation.workUnitId,
      })
    }

    const step: CorpusStep = {
      annotation,
      pushedAt: Date.now(),
      toolCalls,
    }

    branch.steps.push(step)
    this.logger.debug('Annotation pushed to branch', {
      helixId,
      workUnitId: annotation.workUnitId,
      score: annotation.score,
      stepCount: branch.steps.length,
    })
  }

  /**
   * Mark a branch as completed/cancelled/failed.
   * No-op if branch doesn't exist.
   */
  closeBranch(
    helixId: string,
    status: 'completed' | 'cancelled' | 'failed'
  ): void {
    const branch = this.branches.get(helixId)

    if (!branch) {
      this.logger.warn('closeBranch called for non-existent branch', {
        helixId,
        status,
      })
      return
    }

    branch.status = status
    branch.closedAt = Date.now()

    this.logger.info('Branch closed', {
      helixId,
      status,
      stepCount: branch.steps.length,
      durationMs: branch.closedAt - branch.createdAt,
    })

    // When a branch completes successfully, check if its strategies
    // should be elevated to the pattern library
    if (status === 'completed') {
      this.evaluateForPatternElevation(helixId)
    }
  }

  /**
   * Read a single branch.
   */
  getBranch(helixId: string): CorpusBranch | undefined {
    return this.branches.get(helixId)
  }

  /**
   * Read all branches.
   */
  getAllBranches(): CorpusBranch[] {
    return Array.from(this.branches.values())
  }

  /**
   * Count unprocessed steps across all branches (relative to given cursors).
   */
  pendingStepCount(cursors: Map<string, number>): number {
    let total = 0

    for (const branch of this.branches.values()) {
      const cursor = cursors.get(branch.helixId) ?? 0
      const pending = branch.steps.length - cursor
      if (pending > 0) {
        total += pending
      }
    }

    return total
  }

  /**
   * Total steps across all branches.
   */
  totalStepCount(): number {
    let total = 0
    for (const branch of this.branches.values()) {
      total += branch.steps.length
    }
    return total
  }

  /**
   * Number of active branches.
   */
  activeBranchCount(): number {
    let count = 0
    for (const branch of this.branches.values()) {
      if (branch.status === 'active') {
        count++
      }
    }
    return count
  }


  // Branch Digests — Peer Awareness

  /**
   * Update a branch's digest (compact summary of its current state).
   * Called by the Brainstem every N work units.
   */
  updateDigest(helixId: string, digest: BranchDigest): void {
    this.digests.set(helixId, digest)
    this.logger.debug('Digest updated', {
      helixId,
      approach: digest.approach,
      progress: digest.progress.toFixed(2),
      filesActive: digest.filesActive.length,
      keyFindings: digest.keyFindings.length,
    })
  }

  /**
   * Get all digests except the caller's own, for peer awareness.
   * Returns the full set — no truncation. With 128k context windows
   * and a 16k working budget, full digests for all branches are affordable.
   */
  getDigestsExcluding(helixId: string): BranchDigest[] {
    const result: BranchDigest[] = []
    for (const [id, digest] of this.digests) {
      if (id !== helixId) {
        result.push(digest)
      }
    }
    return result
  }

  /**
   * Get all digests for all branches.
   */
  getAllDigests(): BranchDigest[] {
    return Array.from(this.digests.values())
  }

  /**
   * Get the digest for a specific branch.
   */
  getDigestFor(helixId: string): BranchDigest | undefined {
    return this.digests.get(helixId)
  }

  /**
   * Lightweight update — sets only liveStreamSnippet on an existing digest.
   * Called on every Unity stream chunk. O(1) map lookup + field set, no recomputation.
   * No-op if no digest exists yet for this branch.
   */
  updateLiveStreamSnippet(helixId: string, snippet: string): void {
    const digest = this.digests.get(helixId)
    if (!digest) return
    digest.liveStreamSnippet = snippet
  }

  /**
   * Get digests filtered by relevance to the requesting branch.
   * Relevance is determined by file overlap and goal keyword similarity.
   * Returns all relevant digests — no artificial token cap.
   *
   * Relevance scoring:
   * - File overlap: +2 per shared active file
   * - Same parent: +1 (siblings are likely related)
   * - Active status: +1 (prefer live branches)
   * - Keyword overlap: +1 per shared keyword in goal
   *
   * Returns all digests with relevance > 0, sorted by relevance descending.
   * If no digests have relevance > 0, returns all peer digests (full awareness).
   */
  getRelevantDigests(helixId: string): BranchDigest[] {
    const myDigest = this.digests.get(helixId)
    const myBranch = this.branches.get(helixId)
    const peerDigests = this.getDigestsExcluding(helixId)

    if (!myDigest || peerDigests.length === 0) {
      return peerDigests
    }

    const myFiles = new Set(myDigest.filesActive)
    const myKeywords = this.extractKeywords(myBranch?.goal ?? myDigest.goalSummary)

    const scored = peerDigests.map((digest) => {
      let relevance = 0

      // File overlap: +2 per shared active file
      for (const file of digest.filesActive) {
        if (myFiles.has(file)) {
          relevance += 2
        }
      }

      // Same parent: +1
      const peerBranch = this.branches.get(digest.helixId)
      if (myBranch?.parentId && peerBranch?.parentId === myBranch.parentId) {
        relevance += 1
      }

      // Active status: +1
      if (peerBranch?.status === 'active') {
        relevance += 1
      }

      // Keyword overlap: +1 per shared keyword
      const peerKeywords = this.extractKeywords(digest.goalSummary)
      for (const kw of peerKeywords) {
        if (myKeywords.has(kw)) {
          relevance += 1
        }
      }

      return { digest, relevance }
    })

    // Return all with relevance > 0, sorted descending. Fall back to all peers.
    const relevant = scored
      .filter((s) => s.relevance > 0)
      .sort((a, b) => b.relevance - a.relevance)
      .map((s) => s.digest)

    return relevant.length > 0 ? relevant : peerDigests
  }


  // Topic Nodes — Stigmergic Coordination

  /**
   * Create a new shared topic node. Returns the topic ID.
   * Topics are created by Brainstems when they detect cross-cutting concerns.
   */
  createTopic(name: string, createdBy: string, contribution: TopicContribution): string {
    const id = `topic-${++this.topicIdCounter}-${Date.now()}`

    const topic: TopicNode = {
      id,
      name,
      contributions: [contribution],
      tensionFlag: false,
      relatedFiles: [...contribution.files],
      createdAt: Date.now(),
      createdBy,
      lastContributionAt: Date.now(),
    }

    this.topics.set(id, topic)
    this.logger.info('Topic created', {
      topicId: id,
      name,
      createdBy,
      files: contribution.files.length,
    })

    return id
  }

  /**
   * Add a contribution to an existing topic.
   * Auto-detects tension if the new contribution's approach conflicts
   * with existing contributions.
   */
  contributeTopic(topicId: string, contribution: TopicContribution): void {
    const topic = this.topics.get(topicId)
    if (!topic) {
      this.logger.warn('contributeTopic called for non-existent topic', { topicId })
      return
    }

    topic.contributions.push(contribution)
    topic.lastContributionAt = Date.now()

    // Merge new files into the topic's relatedFiles
    for (const file of contribution.files) {
      if (!topic.relatedFiles.includes(file)) {
        topic.relatedFiles.push(file)
      }
    }

    // Detect tension: if approaches differ among contributors
    this.detectTopicTension(topic)

    this.logger.debug('Topic contribution added', {
      topicId,
      topicName: topic.name,
      helixId: contribution.helixId,
      contributionCount: topic.contributions.length,
      tensionFlag: topic.tensionFlag,
    })
  }

  /**
   * Find topics relevant to a set of files and goal keywords.
   * Returns topics that share files or have keyword overlap in the name.
   */
  findRelatedTopics(files: string[], goalKeywords: string[]): TopicNode[] {
    const fileSet = new Set(files)
    const keywordSet = new Set(goalKeywords.map((k) => k.toLowerCase()))

    const scored = Array.from(this.topics.values()).map((topic) => {
      let relevance = 0

      // File overlap
      for (const file of topic.relatedFiles) {
        if (fileSet.has(file)) {
          relevance += 2
        }
      }

      // Keyword overlap in topic name
      const topicWords = topic.name.toLowerCase().split(/\s+/)
      for (const word of topicWords) {
        if (keywordSet.has(word)) {
          relevance += 1
        }
      }

      // Tension bonus — tensions are more important to see
      if (topic.tensionFlag) {
        relevance += 1
      }

      return { topic, relevance }
    })

    return scored
      .filter((s) => s.relevance > 0)
      .sort((a, b) => b.relevance - a.relevance)
      .map((s) => s.topic)
  }

  /**
   * Get all topic nodes.
   */
  getAllTopics(): TopicNode[] {
    return Array.from(this.topics.values())
  }


  // Self-Awareness — Retrospectives, Patterns, Effectiveness

  /**
   * Record a strategy retrospective (why an approach changed).
   * This builds the constellation's self-awareness log.
   */
  recordRetrospective(helixId: string, retrospective: StrategyRetrospective): void {
    this.retrospectives.push(retrospective)
    this.logger.info('Strategy retrospective recorded', {
      helixId,
      from: retrospective.fromApproach,
      to: retrospective.toApproach,
      trigger: retrospective.trigger,
      scoreAtChange: retrospective.scoreAtChange.toFixed(2),
    })
  }

  /**
   * Get all retrospectives across the constellation.
   */
  getAllRetrospectives(): StrategyRetrospective[] {
    return [...this.retrospectives]
  }

  /**
   * Elevate a successful pattern to the constellation-level pattern library.
   * Other branches (current and future) can reference these patterns.
   */
  elevatePattern(pattern: ElevatedPattern): void {
    this.elevatedPatterns.push(pattern)
    this.logger.info('Pattern elevated to library', {
      id: pattern.id,
      sourceHelixId: pattern.sourceHelixId,
      approach: pattern.approach,
      achievedScore: pattern.achievedScore.toFixed(2),
    })
    // Fire callback for persistence
    this.onPatternElevated?.(pattern)
  }

  /**
   * Get all elevated patterns (constellation knowledge).
   */
  getElevatedPatterns(): ElevatedPattern[] {
    return [...this.elevatedPatterns]
  }

  /**
   * Record an effectiveness measurement for a self-org adjustment.
   */
  recordEffectiveness(record: EffectivenessRecord): void {
    this.effectivenessRecords.push(record)
    this.logger.debug('Effectiveness recorded', {
      helixId: record.helixId,
      type: record.adjustmentType,
      improvement: record.improvement.toFixed(3),
      effective: record.effective,
    })
  }

  /**
   * Get all effectiveness records.
   */
  getEffectivenessRecords(): EffectivenessRecord[] {
    return [...this.effectivenessRecords]
  }

  /**
   * Get effectiveness stats by adjustment type — supports constellation-level
   * learning about which self-org strategies actually work.
   */
  getEffectivenessStats(): Map<string, { total: number; effective: number; avgImprovement: number }> {
    const stats = new Map<string, { total: number; effective: number; totalImprovement: number }>()

    for (const record of this.effectivenessRecords) {
      const existing = stats.get(record.adjustmentType) ?? { total: 0, effective: 0, totalImprovement: 0 }
      existing.total++
      if (record.effective) existing.effective++
      existing.totalImprovement += record.improvement
      stats.set(record.adjustmentType, existing)
    }

    const result = new Map<string, { total: number; effective: number; avgImprovement: number }>()
    for (const [type, data] of stats) {
      result.set(type, {
        total: data.total,
        effective: data.effective,
        avgImprovement: data.total > 0 ? data.totalImprovement / data.total : 0,
      })
    }
    return result
  }


  // Snapshot

  /**
   * Serializable snapshot of the full tree for progress reporting.
   * Includes all shared thought tree state: digests, topics,
   * retrospectives, patterns, and effectiveness records.
   */
  getSnapshot(): CorpusTreeSnapshot {
    const branches: CorpusBranchSnapshot[] = []

    for (const branch of this.branches.values()) {
      const stepCount = branch.steps.length
      const scores = branch.steps.map((s) => s.annotation.score)
      const averageScore =
        scores.length > 0
          ? scores.reduce((a, b) => a + b, 0) / scores.length
          : 0

      const latestStep =
        stepCount > 0 ? branch.steps[stepCount - 1] : undefined

      branches.push({
        helixId: branch.helixId,
        goal: branch.goal,
        depth: branch.depth,
        parentId: branch.parentId,
        status: branch.status,
        stepCount,
        latestScore: latestStep?.annotation.score,
        latestAnnotation: latestStep?.annotation.annotation,
        latestPattern: latestStep?.annotation.pattern,
        averageScore,
        createdAt: branch.createdAt,
        closedAt: branch.closedAt,
        digest: this.digests.get(branch.helixId),
      })
    }

    return {
      branches,
      totalSteps: this.totalStepCount(),
      activeBranches: this.activeBranchCount(),
      snapshotAt: Date.now(),
      digests: Array.from(this.digests.values()),
      topics: this.getAllTopics(),
      retrospectives: this.getAllRetrospectives(),
      elevatedPatterns: this.getElevatedPatterns(),
      effectivenessRecords: this.getEffectivenessRecords(),
    }
  }


  // Internal Helpers

  /**
   * Extract simple keywords from a goal string for relevance matching.
   */
  private extractKeywords(goal: string): Set<string> {
    const stopWords = new Set([
      'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
      'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
      'should', 'may', 'might', 'shall', 'can', 'need', 'must', 'ought',
      'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from', 'as',
      'into', 'through', 'during', 'before', 'after', 'above', 'below',
      'and', 'but', 'or', 'nor', 'not', 'so', 'yet', 'both', 'either',
      'neither', 'each', 'every', 'all', 'any', 'few', 'more', 'most',
      'other', 'some', 'such', 'no', 'only', 'own', 'same', 'than',
      'too', 'very', 'just', 'because', 'if', 'when', 'where', 'how',
      'what', 'which', 'who', 'whom', 'this', 'that', 'these', 'those',
      'it', 'its', 'they', 'them', 'their', 'we', 'us', 'our', 'i', 'me', 'my',
    ])

    return new Set(
      goal
        .toLowerCase()
        .split(/[^a-z0-9_-]+/)
        .filter((w) => w.length > 2 && !stopWords.has(w))
    )
  }

  /**
   * Detect tension within a topic node.
   * Tension = different approaches among contributors to the same topic.
   */
  private detectTopicTension(topic: TopicNode): void {
    if (topic.contributions.length < 2) return

    const approaches = new Set(topic.contributions.map((c) => c.approach))

    // If there are conflicting implementation approaches, flag tension
    const conflictingApproaches = ['implementation', 'revision', 'debugging']
    const hasConflicting = conflictingApproaches.filter((a) =>
      approaches.has(a as any)
    )

    if (hasConflicting.length >= 2 || approaches.size >= 3) {
      const contributors = [...new Set(topic.contributions.map((c) => c.helixId))]
      if (contributors.length >= 2) {
        topic.tensionFlag = true
        topic.tensionDescription =
          `Contributors ${contributors.join(', ')} have different approaches: ` +
          `${[...approaches].join(', ')}`
      }
    }
  }

  /**
   * When a branch completes successfully, evaluate whether its strategies
   * should be elevated to the constellation pattern library.
   *
   * Criteria for elevation:
   * - Branch had a rolling score > 0.7 in its final steps
   * - Branch's retrospectives show at least one successful strategy change
   * - The strategy hasn't already been elevated
   */
  private evaluateForPatternElevation(helixId: string): void {
    const branch = this.branches.get(helixId)
    const digest = this.digests.get(helixId)
    if (!branch || !digest) return

    // Check final quality
    const recentSteps = branch.steps.slice(-5)
    if (recentSteps.length === 0) return

    const avgRecentScore =
      recentSteps.reduce((sum, s) => sum + s.annotation.score, 0) / recentSteps.length

    if (avgRecentScore < 0.7) return

    // Check for successful retrospectives
    const branchRetros = this.retrospectives.filter(
      (r) => r.helixId === helixId && r.wasEffective === true
    )

    if (branchRetros.length > 0) {
      const pattern: ElevatedPattern = {
        id: `pattern-${++this.patternIdCounter}-${Date.now()}`,
        sourceHelixId: helixId,
        approach: digest.approach,
        description:
          `${digest.approach} approach with score ${avgRecentScore.toFixed(2)}. ` +
          `Key findings: ${digest.keyFindings.slice(0, 3).join('; ')}. ` +
          `Successful strategy changes: ${branchRetros.map((r) => `${r.fromApproach}→${r.toApproach}`).join(', ')}.`,
        applicableContext: digest.goalSummary,
        achievedScore: avgRecentScore,
        relevantFiles: digest.filesActive,
        supportingRetrospectives: branchRetros.map(
          (r) => `${r.fromApproach}→${r.toApproach}: ${r.reason}`
        ),
        elevatedAt: Date.now(),
        referenceCount: 0,
      }

      this.elevatePattern(pattern)
    }
  }
}
