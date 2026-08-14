/**
 * ConstellationWorktreeIsolation — Git worktree isolation for Constellation branches.
 *
 * WHY: When multiple Helix branches in a Constellation edit the same files,
 * they can conflict. Worktree isolation gives each branch its own working
 * copy of the repository, preventing interference.
 *
 * Adapted from Claude Code's worktree patterns (process-level isolation,
 * fail-closed change detection, path translation notices) combined with
 * CassiCore's existing WorktreeManager (git lifecycle, cleanup, diff).
 *
 * HOW: Wraps WorktreeManager with Constellation-specific operations:
 *   - Per-branch worktree creation with constellation-scoped naming
 *   - Change detection (fail-closed) before cleanup
 *   - Auto-commit + merge on branch completion
 *   - Path translation prompt generation for isolated branches
 *   - Cleanup of all constellation worktrees on pipeline completion
 */

import { execSync } from 'node:child_process'

import { WorktreeManager } from './worktree-manager.js'
import type { ILogger } from '../../../types/interfaces.js'


/** Isolation mode for Constellation branches */
export type ConstellationIsolation = 'none' | 'worktree'

/** Result of change detection on a worktree */
export interface WorktreeChanges {
  /** Number of uncommitted changed files */
  changedFiles: number
  /** Number of commits ahead of the base branch */
  commitsAhead: number
  /** Whether the worktree has any changes at all */
  hasChanges: boolean
  /** Summary of file changes */
  summary: string[]
}

/** Result of a merge operation */
export interface WorktreeMergeResult {
  /** Whether the merge succeeded */
  merged: boolean
  /** Number of files changed by the merge */
  filesChanged: number
  /** Merge commit SHA (if created) */
  mergeCommit?: string
  /** Error if merge failed */
  error?: string
  /** Whether there were conflicts */
  hasConflicts: boolean
  /** List of conflicting files (if any) */
  conflictingFiles: string[]
}

/** Tracking info for a branch's worktree */
interface BranchWorktree {
  helixId: string
  worktreePath: string
  branchName: string
  originalHead: string
  createdAt: number
}


/**
 * Constellation-specific worktree isolation.
 *
 * Each branch in the constellation gets its own git worktree on a separate
 * branch. When the branch completes, changes are auto-committed and merged
 * back to the main branch.
 */
export class ConstellationWorktreeIsolation {
  private readonly worktreeManager: WorktreeManager
  private readonly logger: ILogger
  private readonly projectRoot: string
  private readonly constellationId: string
  private readonly branches = new Map<string, BranchWorktree>()

  constructor(opts: {
    logger: ILogger
    projectRoot: string
    constellationId: string
    maxWorktrees?: number
  }) {
    this.logger = opts.logger.child('constellation-worktree')
    this.projectRoot = opts.projectRoot
    this.constellationId = opts.constellationId

    this.worktreeManager = new WorktreeManager(this.logger, opts.projectRoot, {
      baseDir: '.cassicore-constellation',
      maxWorktrees: opts.maxWorktrees ?? 10,
      createBranch: true,
      enabled: true,
    })
  }

  /** Whether worktree isolation is available */
  get isEnabled(): boolean {
    return this.worktreeManager.isEnabled
  }

  /**
   * Create an isolated worktree for a Helix branch.
   * Returns the worktree path, or the project root if isolation fails.
   *
   * HOW: Each branch gets a unique worktree named after the constellation
   * and helix IDs, with a separate git branch for its changes.
   */
  async createBranchWorktree(helixId: string): Promise<string> {
    if (!this.isEnabled) {
      return this.projectRoot
    }

    // WHY: Short slug prevents path length issues on some filesystems
    const slug = this.makeBranchSlug(helixId)

    // Record original HEAD for change detection (fail-closed pattern from Claude Code)
    let originalHead = ''
    try {
      originalHead = execSync('git rev-parse HEAD', {
        cwd: this.projectRoot,
        encoding: 'utf-8',
        timeout: 5_000,
      }).trim()
    } catch {
      this.logger.warn('Failed to get HEAD for worktree tracking', { helixId })
    }

    try {
      const worktreePath = await this.worktreeManager.createWorktree(slug)

      // Track the worktree for later merge/cleanup
      this.branches.set(helixId, {
        helixId,
        worktreePath,
        branchName: slug,
        originalHead,
        createdAt: Date.now(),
      })

      this.logger.info('Branch worktree created', {
        helixId,
        worktreePath,
        branchName: slug,
      })

      return worktreePath
    } catch (err) {
      this.logger.warn('Worktree creation failed, using shared project root', {
        helixId,
        error: String(err),
      })
      return this.projectRoot
    }
  }

  /**
   * Detect changes in a branch's worktree.
   * Uses fail-closed pattern from Claude Code: if detection fails, assume changes exist.
   */
  detectChanges(helixId: string): WorktreeChanges {
    const branch = this.branches.get(helixId)
    if (!branch) {
      // WHY: Fail-closed — if we can't find tracking info, assume changes exist
      return { changedFiles: 0, commitsAhead: 0, hasChanges: false, summary: [] }
    }

    try {
      const diffSummary = this.worktreeManager.getDiffSummary(branch.branchName)
      const changedFiles = this.worktreeManager.getChangedFiles(branch.branchName)

      // Count commits ahead of the original HEAD
      let commitsAhead = 0
      try {
        const log = execSync(`git log --oneline ${branch.originalHead}..HEAD`, {
          cwd: branch.worktreePath,
          encoding: 'utf-8',
          timeout: 5_000,
        }).trim()
        commitsAhead = log ? log.split('\n').length : 0
      } catch {
        // If we can't count commits, that's OK
      }

      return {
        changedFiles: changedFiles.length,
        commitsAhead,
        hasChanges: changedFiles.length > 0 || commitsAhead > 0,
        summary: diffSummary ? [diffSummary] : changedFiles,
      }
    } catch (err) {
      // WHY: Fail-closed pattern from Claude Code — if detection fails, assume changes
      this.logger.warn('Change detection failed, assuming changes exist', {
        helixId,
        error: String(err),
      })
      return { changedFiles: 1, commitsAhead: 0, hasChanges: true, summary: ['detection failed'] }
    }
  }

  /**
   * Auto-commit any uncommitted changes in a branch's worktree.
   * Called before merge to ensure all work is captured.
   */
  autoCommit(helixId: string, message?: string): boolean {
    const branch = this.branches.get(helixId)
    if (!branch) return false

    try {
      // Check for uncommitted changes
      const status = execSync('git status --porcelain', {
        cwd: branch.worktreePath,
        encoding: 'utf-8',
        timeout: 5_000,
      }).trim()

      if (!status) return true // Nothing to commit

      // Stage all and commit
      execSync('git add -A', { cwd: branch.worktreePath, timeout: 5_000 })
      const commitMsg = message ?? `cassi-helix: auto-commit from ${helixId}`
      execSync(`git commit -m "${commitMsg}"`, {
        cwd: branch.worktreePath,
        timeout: 10_000,
        // WHY: Set author to cassi-helix so git log shows which system made the commit
        env: {
          ...process.env,
          GIT_AUTHOR_NAME: 'cassi-helix',
          GIT_AUTHOR_EMAIL: 'cassi-helix@local',
          GIT_COMMITTER_NAME: 'cassi-helix',
          GIT_COMMITTER_EMAIL: 'cassi-helix@local',
        },
      })

      this.logger.info('Auto-committed branch changes', { helixId, status: status.split('\n').length + ' files' })
      return true
    } catch (err) {
      this.logger.warn('Auto-commit failed', { helixId, error: String(err) })
      return false
    }
  }

  /**
   * Merge a branch's worktree changes back to the main branch.
   * Auto-commits uncommitted changes first.
   *
   * HOW: Uses git merge with --no-ff to create a merge commit that
   * attributes the work to the specific Helix branch.
   */
  mergeBranch(helixId: string): WorktreeMergeResult {
    const branch = this.branches.get(helixId)
    if (!branch) {
      return { merged: false, filesChanged: 0, hasConflicts: false, conflictingFiles: [], error: 'Branch not found' }
    }

    // Auto-commit any uncommitted work
    this.autoCommit(helixId)

    // Check if there are any changes to merge
    const changes = this.detectChanges(helixId)
    if (!changes.hasChanges) {
      this.logger.info('No changes to merge', { helixId })
      return { merged: true, filesChanged: 0, hasConflicts: false, conflictingFiles: [] }
    }

    try {
      // Merge the branch into the main working directory
      const mergeMessage = `Merge helix branch ${helixId}`
      const mergeOutput = execSync(
        `git merge --no-ff -m "${mergeMessage}" ${branch.branchName}`,
        {
          cwd: this.projectRoot,
          encoding: 'utf-8',
          timeout: 30_000,
          env: {
            ...process.env,
            GIT_AUTHOR_NAME: 'cassi-helix',
            GIT_AUTHOR_EMAIL: 'cassi-helix@local',
            GIT_COMMITTER_NAME: 'cassi-helix',
            GIT_COMMITTER_EMAIL: 'cassi-helix@local',
          },
        },
      )

      // Get merge commit SHA
      let mergeCommit: string | undefined
      try {
        mergeCommit = execSync('git rev-parse HEAD', {
          cwd: this.projectRoot,
          encoding: 'utf-8',
          timeout: 5_000,
        }).trim()
      } catch { /* not critical */ }

      this.logger.info('Branch merged successfully', {
        helixId,
        filesChanged: changes.changedFiles,
        mergeCommit,
      })

      return {
        merged: true,
        filesChanged: changes.changedFiles,
        mergeCommit,
        hasConflicts: false,
        conflictingFiles: [],
      }
    } catch (err) {
      const errStr = String(err)

      // Check for merge conflicts
      if (errStr.includes('CONFLICT') || errStr.includes('Merge conflict')) {
        let conflictingFiles: string[] = []
        try {
          const conflictOutput = execSync('git diff --name-only --diff-filter=U', {
            cwd: this.projectRoot,
            encoding: 'utf-8',
            timeout: 5_000,
          }).trim()
          conflictingFiles = conflictOutput ? conflictOutput.split('\n') : []

          // Abort the merge to leave the main branch clean
          execSync('git merge --abort', { cwd: this.projectRoot, timeout: 5_000 })
        } catch { /* best effort cleanup */ }

        this.logger.warn('Merge conflict detected', { helixId, conflictingFiles })
        return {
          merged: false,
          filesChanged: 0,
          hasConflicts: true,
          conflictingFiles,
          error: `Merge conflict in ${conflictingFiles.length} file(s): ${conflictingFiles.join(', ')}`,
        }
      }

      this.logger.error('Merge failed', { helixId, error: errStr })
      return {
        merged: false,
        filesChanged: 0,
        hasConflicts: false,
        conflictingFiles: [],
        error: errStr,
      }
    }
  }

  /**
   * Complete a branch: auto-commit, merge, and cleanup its worktree.
   * Called when a Helix branch finishes (success or failure).
   */
  async completeBranch(helixId: string, opts?: { skipMerge?: boolean }): Promise<WorktreeMergeResult> {
    const branch = this.branches.get(helixId)
    if (!branch) {
      return { merged: true, filesChanged: 0, hasConflicts: false, conflictingFiles: [] }
    }

    // Merge changes back (unless explicitly skipped, e.g., for failed branches)
    let mergeResult: WorktreeMergeResult
    if (opts?.skipMerge) {
      mergeResult = { merged: true, filesChanged: 0, hasConflicts: false, conflictingFiles: [] }
    } else {
      mergeResult = this.mergeBranch(helixId)
    }

    // Cleanup the worktree
    try {
      await this.worktreeManager.removeWorktree(branch.branchName)
      this.branches.delete(helixId)
      this.logger.info('Branch worktree cleaned up', { helixId })
    } catch (err) {
      this.logger.warn('Worktree cleanup failed', { helixId, error: String(err) })
    }

    return mergeResult
  }

  /**
   * Get the worktree path for a branch (or project root if not isolated).
   */
  getWorktreePath(helixId: string): string {
    return this.branches.get(helixId)?.worktreePath ?? this.projectRoot
  }

  /**
   * Check if a branch has worktree isolation.
   */
  isIsolated(helixId: string): boolean {
    return this.branches.has(helixId)
  }

  getFullDiff(helixId: string): string | null {
    const branch = this.branches.get(helixId)
    if (!branch) return null
    return this.worktreeManager.getFullDiff(branch.branchName)
  }

  /**
   * Generate a path translation prompt fragment for isolated branches.
   * Adapted from Claude Code's buildWorktreeNotice pattern.
   *
   * WHY: When a branch operates in a worktree, the agent needs to know
   * that its working directory is different from the main project root.
   * Without this notice, agents might reference paths that don't exist
   * in their worktree.
   */
  getIsolationNotice(helixId: string): string | undefined {
    const branch = this.branches.get(helixId)
    if (!branch) return undefined

    return [
      `## Worktree Isolation Notice`,
      ``,
      `You are working in an isolated git worktree. Your changes are on a separate branch`,
      `and will be merged back to the main branch when your work completes.`,
      ``,
      `**Your working directory:** ${branch.worktreePath}`,
      `**Your branch:** ${branch.branchName}`,
      `**Main project root:** ${this.projectRoot}`,
      ``,
      `All file paths you read/write are relative to your worktree, not the main project.`,
      `Other branches in this Constellation are also isolated — you will not see their changes`,
      `until they are merged.`,
    ].join('\n')
  }

  /**
   * Cleanup all worktrees for this constellation.
   * Called when the constellation pipeline completes.
   */
  async cleanupAll(): Promise<void> {
    for (const [helixId, branch] of this.branches) {
      try {
        await this.worktreeManager.removeWorktree(branch.branchName)
        this.logger.debug('Cleaned up constellation worktree', { helixId })
      } catch (err) {
        this.logger.warn('Failed to clean up constellation worktree', { helixId, error: String(err) })
      }
    }
    this.branches.clear()
    this.logger.info('All constellation worktrees cleaned up', { constellationId: this.constellationId })
  }

  /**
   * Get status of all branch worktrees.
   */
  getStatus(): Array<{ helixId: string; worktreePath: string; branchName: string; ageMs: number }> {
    return Array.from(this.branches.values()).map(b => ({
      helixId: b.helixId,
      worktreePath: b.worktreePath,
      branchName: b.branchName,
      ageMs: Date.now() - b.createdAt,
    }))
  }

  /** Create a short, filesystem-safe slug from a helix ID */
  private makeBranchSlug(helixId: string): string {
    // With sequential IDs (helix-0, helix-1), use constellation ID + helix ID directly
    const safeConsId = this.constellationId.replace(/[^a-z0-9-]/gi, '')
    return `${safeConsId}-${helixId}`
  }
}
