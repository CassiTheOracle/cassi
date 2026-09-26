/**
 * Spark Extractor — Extracts proposals from BranchDigest changes
 *
 * Each Corpus sweep, the SparkExtractor compares the current digest
 * for each branch against the previous one and produces Sparks for
 * any meaningful changes: new findings, new blockers, decisions,
 * quality trajectory shifts, etc.
 *
 * These Sparks are the raw input to the Locus — the "unconscious"
 * proposals that compete for workspace access.
 */

import type { ILogger } from '../vendor/types/interfaces.js'
import type { BranchDigest, CrossHelixPattern } from '../corpus-types.js'
import type { Spark, SparkType } from './locus-types.js'

let sparkCounter = 0
function nextSparkId(): string {
  return `spark-${++sparkCounter}-${Date.now().toString(36)}`
}


export interface SparkExtractorDeps {
  logger: ILogger
}

export class SparkExtractor {
  private previousDigests = new Map<string, DigestFingerprint>()
  private logger: ILogger

  constructor(deps: SparkExtractorDeps) {
    this.logger = deps.logger.child?.('spark-extractor') ?? deps.logger
  }

  /**
   * Extract Sparks from current digests by diffing against previous state.
   * Also accepts cross-branch patterns (which become tension/convergence sparks).
   *
   * Returns all new Sparks for this sweep. The KindlingEngine will score
   * and filter them.
   */
  extract(
    currentDigests: BranchDigest[],
    crossPatterns?: CrossHelixPattern[],
  ): Spark[] {
    const sparks: Spark[] = []
    const now = Date.now()

    for (const digest of currentDigests) {
      const prev = this.previousDigests.get(digest.helixId)
      const current = this.fingerprint(digest)

      if (!prev) {
        this.previousDigests.set(digest.helixId, current)
        continue
      }

      // New key findings
      const newFindings = this.diffArrays(prev.keyFindings, current.keyFindings)
      for (const finding of newFindings) {
        sparks.push(this.createSpark(
          digest.helixId, finding, 'discovery', digest, now,
        ))
      }

      // New blockers
      const newBlockers = this.diffArrays(prev.blockers, current.blockers)
      for (const blocker of newBlockers) {
        sparks.push(this.createSpark(
          digest.helixId, blocker, 'blocker', digest, now,
        ))
      }

      // New decisions
      const newDecisions = this.diffArrays(prev.decisions, current.decisions)
      for (const decision of newDecisions) {
        sparks.push(this.createSpark(
          digest.helixId, decision, 'decision', digest, now,
        ))
      }

      // Quality trajectory jump — a breakthrough
      const scoreDelta = digest.rollingScore - (prev.rollingScore ?? 0)
      if (scoreDelta > 0.15) {
        sparks.push(this.createSpark(
          digest.helixId,
          `Quality breakthrough: score jumped ${scoreDelta.toFixed(2)} (${prev.rollingScore?.toFixed(2)} → ${digest.rollingScore.toFixed(2)})`,
          'breakthrough',
          digest,
          now,
        ))
      }

      this.previousDigests.set(digest.helixId, current)
    }

    // Cross-branch patterns become tension/convergence sparks
    if (crossPatterns) {
      for (const pattern of crossPatterns) {
        if (pattern.actedUpon) continue

        const type: SparkType = (pattern.type === 'convergence')
          ? 'convergence'
          : 'tension'

        sparks.push({
          sparkId: nextSparkId(),
          sourceHelixId: pattern.helixIds[0] ?? 'corpus',
          content: pattern.description,
          type,
          luminance: { novelty: 0, urgency: 0, crossRelevance: 0, qualityDelta: 0, composite: 0 },
          sparkedAt: now,
          sourceGoal: `Cross-branch pattern: ${pattern.type}`,
          relevantFiles: [],
        })
      }
    }

    if (sparks.length > 0) {
      this.logger.info('Sparks extracted', {
        count: sparks.length,
        byType: this.countByType(sparks),
      })
    }

    return sparks
  }

  /**
   * Remove tracking for a deregistered Helix.
   */
  removeHelix(helixId: string): void {
    this.previousDigests.delete(helixId)
  }

  /**
   * Reset all state (for testing).
   */
  reset(): void {
    this.previousDigests.clear()
    sparkCounter = 0
  }

  // --- Private ---

  private createSpark(
    helixId: string,
    content: string,
    type: SparkType,
    digest: BranchDigest,
    now: number,
  ): Spark {
    return {
      sparkId: nextSparkId(),
      sourceHelixId: helixId,
      content,
      type,
      luminance: { novelty: 0, urgency: 0, crossRelevance: 0, qualityDelta: 0, composite: 0 },
      sparkedAt: now,
      sourceGoal: digest.goalSummary,
      relevantFiles: digest.filesActive.slice(0, 10),
    }
  }

  /**
   * Build a fingerprint of digest fields for change detection.
   */
  private fingerprint(digest: BranchDigest): DigestFingerprint {
    return {
      keyFindings: [...(digest.keyFindings || [])],
      blockers: [...(digest.blockers || [])],
      decisions: [...(digest.allDecisions || [])],
      discoveries: [...(digest.allDiscoveries || [])],
      rollingScore: digest.rollingScore,
      approach: digest.approach,
    }
  }

  /**
   * Find new items in `current` that weren't in `previous`.
   */
  private diffArrays(previous: string[], current: string[]): string[] {
    const prevSet = new Set(previous)
    return current.filter(item => !prevSet.has(item))
  }

  private countByType(sparks: Spark[]): Record<string, number> {
    const counts: Record<string, number> = {}
    for (const spark of sparks) {
      counts[spark.type] = (counts[spark.type] || 0) + 1
    }
    return counts
  }
}


/**
 * Internal fingerprint for tracking digest state between sweeps.
 */
interface DigestFingerprint {
  keyFindings: string[]
  blockers: string[]
  decisions: string[]
  discoveries: string[]
  rollingScore: number
  approach: string
}
