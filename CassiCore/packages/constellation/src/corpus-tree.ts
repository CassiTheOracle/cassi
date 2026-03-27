/**
 * CorpusTree — Shared data structure for Constellation-level reasoning
 *
 * The CorpusTree is the shared data structure that connects child Helix
 * Brainstems to the Corpus. Brainstems push annotations into their branch,
 * and the Corpus reads from it to detect cross-branch patterns.
 *
 * Named after the corpus callosum — the nerve fiber tract connecting
 * brain hemispheres, enabling coordinated thought across regions.
 */

import type { ILogger } from '../../../types/interfaces.js'
import type {
  ICorpusTree,
  CorpusBranch,
  CorpusStep,
  CorpusTreeSnapshot,
  CorpusBranchSnapshot,
} from './corpus-types.js'
import type { BrainstemAnnotation } from '../helix/brainstem-types.js'

/**
 * CorpusTree — Shared reasoning tree for the Constellation.
 *
 * Child Helix Brainstems push annotations into it. The Corpus reads it.
 * The tree is the single source of truth for what every Helix is doing.
 */
export class CorpusTree implements ICorpusTree {
  private branches: Map<string, CorpusBranch>
  private logger: ILogger

  constructor(logger: ILogger) {
    this.branches = new Map()
    this.logger = logger.child('CorpusTree')
  }

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
  pushAnnotation(helixId: string, annotation: BrainstemAnnotation): void {
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

  /**
   * Serializable snapshot of the full tree for progress reporting.
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
      })
    }

    return {
      branches,
      totalSteps: this.totalStepCount(),
      activeBranches: this.activeBranchCount(),
      snapshotAt: Date.now(),
    }
  }
}
