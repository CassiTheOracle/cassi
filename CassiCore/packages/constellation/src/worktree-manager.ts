/**
 * WorktreeManager — Git worktree lifecycle management for team agent isolation.
 *
 * When a team is created, the WorktreeManager creates a git worktree so the
 * team's agents operate on an isolated copy of the repo. This prevents
 * concurrent teams from interfering with each other's file changes or git state.
 *
 * Lifecycle:
 *   1. createWorktree(teamId) — creates `.cassicore-teams/<teamId>` worktree
 *   2. getWorktreePath(teamId) — returns the worktree path for tool execution
 *   3. removeWorktree(teamId) — cleans up after team completion
 *   4. cleanup() — removes orphaned worktrees from crashed teams
 *
 * Worktrees are created from the current HEAD on a new branch `team/<teamId>`.
 * All tool execution for team agents uses the worktree path as workingDir.
 */

import { execSync, type ExecSyncOptions } from 'node:child_process'
import { existsSync, mkdirSync, rmSync, readFileSync, appendFileSync } from 'node:fs'
import { join, resolve } from 'node:path'

import type { ILogger } from '../../../types/interfaces.js'

// Configuration

export interface WorktreeManagerConfig {
  /** Base directory for worktrees, relative to project root. Default: '.cassicore-teams' */
  baseDir?: string
  /** Maximum concurrent worktrees. Default: 5 */
  maxWorktrees?: number
  /** Whether to create a new branch for each worktree. Default: true */
  createBranch?: boolean
  /** Whether worktree isolation is enabled. Default: true */
  enabled?: boolean
}

const DEFAULT_CONFIG: Required<WorktreeManagerConfig> = {
  baseDir: '.cassicore-teams',
  maxWorktrees: 5,
  createBranch: true,
  enabled: true,
}

// WorktreeManager

export class WorktreeManager {
  private readonly logger: ILogger
  private readonly config: Required<WorktreeManagerConfig>
  private readonly projectRoot: string

  /** Active worktrees: teamId → absolute path */
  private readonly activeWorktrees = new Map<string, string>()

  /** Whether the project is a git repo */
  private readonly isGitRepo: boolean

  constructor(logger: ILogger, projectRoot: string, config?: WorktreeManagerConfig) {
    this.logger = logger.child('worktree-mgr')
    this.projectRoot = resolve(projectRoot)
    this.config = { ...DEFAULT_CONFIG, ...config }

    // Check if we're in a git repo
    this.isGitRepo = this.checkGitRepo()

    if (!this.isGitRepo && this.config.enabled) {
      this.logger.warn('[worktree-mgr] Not a git repository — worktree isolation disabled')
      this.config.enabled = false
    }
  }


  /**
   * Whether worktree isolation is available and enabled.
   */
  get isEnabled(): boolean {
    return this.config.enabled && this.isGitRepo
  }

  /**
   * Create a worktree for a team.
   * Returns the absolute path to the worktree, or the project root if
   * worktree creation fails (graceful degradation).
   */
  async createWorktree(teamId: string): Promise<string> {
    if (!this.isEnabled) {
      this.logger.debug('[worktree-mgr] Worktrees disabled, using project root', { teamId })
      return this.projectRoot
    }

    // Check max worktrees limit
    if (this.activeWorktrees.size >= this.config.maxWorktrees) {
      this.logger.warn('[worktree-mgr] Max worktrees reached, using project root', {
        teamId,
        activeCount: this.activeWorktrees.size,
        maxWorktrees: this.config.maxWorktrees,
      })
      return this.projectRoot
    }

    // Check if worktree already exists for this team
    if (this.activeWorktrees.has(teamId)) {
      const existing = this.activeWorktrees.get(teamId)!
      this.logger.debug('[worktree-mgr] Worktree already exists', { teamId, path: existing })
      return existing
    }

    const sanitizedId = this.sanitizeTeamId(teamId)
    const worktreePath = join(this.projectRoot, this.config.baseDir, sanitizedId)
    const branchName = `team/${sanitizedId}`

    try {
      // Ensure base directory exists
      const baseDir = join(this.projectRoot, this.config.baseDir)
      if (!existsSync(baseDir)) {
        mkdirSync(baseDir, { recursive: true })
      }

      // Ensure .gitignore includes our worktree directory
      this.ensureGitignore()

      // Create the worktree
      const execOpts: ExecSyncOptions = {
        cwd: this.projectRoot,
        stdio: 'pipe',
        timeout: 30_000,
      }

      if (this.config.createBranch) {
        // Create worktree with a new branch from HEAD
        execSync(
          `git worktree add "${worktreePath}" -b "${branchName}" HEAD`,
          execOpts,
        )
      } else {
        // Create detached worktree from HEAD
        execSync(
          `git worktree add --detach "${worktreePath}" HEAD`,
          execOpts,
        )
      }

      this.activeWorktrees.set(teamId, worktreePath)

      this.logger.info('[worktree-mgr] Worktree created', {
        teamId,
        path: worktreePath,
        branch: this.config.createBranch ? branchName : 'detached',
      })

      return worktreePath
    } catch (err) {
      this.logger.error('[worktree-mgr] Failed to create worktree — falling back to project root', {
        teamId,
        error: String(err),
      })
      return this.projectRoot
    }
  }

  /**
   * Get the worktree path for a team.
   * Returns the project root if no worktree exists.
   */
  getWorktreePath(teamId: string): string {
    return this.activeWorktrees.get(teamId) ?? this.projectRoot
  }

  /**
   * Check whether a specific team has an active worktree.
   */
  hasWorktree(teamId: string): boolean {
    return this.activeWorktrees.has(teamId)
  }

  /**
   * Remove a team's worktree and optionally its branch.
   */
  async removeWorktree(teamId: string): Promise<void> {
    const worktreePath = this.activeWorktrees.get(teamId)
    if (!worktreePath) {
      this.logger.debug('[worktree-mgr] No worktree to remove', { teamId })
      return
    }

    const sanitizedId = this.sanitizeTeamId(teamId)
    const branchName = `team/${sanitizedId}`

    try {
      const execOpts: ExecSyncOptions = {
        cwd: this.projectRoot,
        stdio: 'pipe',
        timeout: 30_000,
      }

      // Remove the worktree
      execSync(`git worktree remove "${worktreePath}" --force`, execOpts)

      // Remove the branch if we created one
      if (this.config.createBranch) {
        try {
          execSync(`git branch -D "${branchName}"`, execOpts)
        } catch {
          // Branch may not exist or may have already been cleaned up
          this.logger.debug('[worktree-mgr] Branch cleanup skipped', { branchName })
        }
      }

      this.activeWorktrees.delete(teamId)

      this.logger.info('[worktree-mgr] Worktree removed', {
        teamId,
        path: worktreePath,
      })
    } catch (err) {
      this.logger.error('[worktree-mgr] Failed to remove worktree', {
        teamId,
        path: worktreePath,
        error: String(err),
      })

      // Force-remove the directory if git worktree remove failed
      try {
        rmSync(worktreePath, { recursive: true, force: true })
        // Prune stale worktree references
        execSync('git worktree prune', {
          cwd: this.projectRoot,
          stdio: 'pipe',
          timeout: 10_000,
        })
        this.activeWorktrees.delete(teamId)
        this.logger.info('[worktree-mgr] Force-removed worktree directory', { teamId })
      } catch (forceErr) {
        this.logger.error('[worktree-mgr] Force removal also failed', {
          teamId,
          error: String(forceErr),
        })
      }
    }
  }

  /**
   * Get a diff summary between a team's worktree and the main tree.
   * Returns a git diff stat string, or null if no worktree exists.
   */
  getDiffSummary(teamId: string): string | null {
    const worktreePath = this.activeWorktrees.get(teamId)
    if (!worktreePath) return null

    try {
      const diff = execSync('git diff --stat HEAD', {
        cwd: worktreePath,
        stdio: 'pipe',
        timeout: 10_000,
      }).toString().trim()

      return diff || null
    } catch {
      return null
    }
  }

  /**
   * Get the full diff between a team's worktree and the main branch HEAD.
   */
  getFullDiff(teamId: string): string | null {
    const worktreePath = this.activeWorktrees.get(teamId)
    if (!worktreePath) return null

    try {
      return execSync('git diff HEAD', {
        cwd: worktreePath,
        stdio: 'pipe',
        timeout: 30_000,
      }).toString()
    } catch {
      return null
    }
  }

  /**
   * Get list of changed files in a team's worktree.
   */
  getChangedFiles(teamId: string): string[] {
    const worktreePath = this.activeWorktrees.get(teamId)
    if (!worktreePath) return []

    try {
      const output = execSync('git diff --name-only HEAD', {
        cwd: worktreePath,
        stdio: 'pipe',
        timeout: 10_000,
      }).toString().trim()

      return output ? output.split('\n') : []
    } catch {
      return []
    }
  }

  /**
   * Re-register an existing worktree for a restored team.
   * Called during daemon restart to reconnect in-memory tracking with
   * worktree directories that survived the restart on disk.
   *
   * Returns true if the worktree was found on disk and re-registered,
   * false if the directory no longer exists.
   */
  reRegisterWorktree(teamId: string): boolean {
    if (!this.isEnabled) return false

    // Already tracked
    if (this.activeWorktrees.has(teamId)) return true

    const sanitizedId = this.sanitizeTeamId(teamId)
    const worktreePath = join(this.projectRoot, this.config.baseDir, sanitizedId)

    if (existsSync(worktreePath)) {
      this.activeWorktrees.set(teamId, worktreePath)
      this.logger.debug('[worktree-mgr] Re-registered worktree for restored team', {
        teamId,
        path: worktreePath,
      })
      return true
    }

    this.logger.debug('[worktree-mgr] Worktree directory missing for restored team', {
      teamId,
      expectedPath: worktreePath,
    })
    return false
  }

  /**
   * Clean up orphaned worktrees from previous daemon runs.
   * Should be called during daemon startup.
   */
  cleanup(): void {
    if (!this.isEnabled) return

    const baseDir = join(this.projectRoot, this.config.baseDir)
    if (!existsSync(baseDir)) return

    try {
      // Prune stale git worktree references
      execSync('git worktree prune', {
        cwd: this.projectRoot,
        stdio: 'pipe',
        timeout: 10_000,
      })

      this.logger.info('[worktree-mgr] Pruned stale worktree references')
    } catch (err) {
      this.logger.warn('[worktree-mgr] Failed to prune worktrees', {
        error: String(err),
      })
    }
  }

  /**
   * Get the count of active worktrees.
   */
  get activeCount(): number {
    return this.activeWorktrees.size
  }

  /**
   * List all active worktrees with their team IDs and paths.
   */
  listActive(): Array<{ teamId: string; path: string }> {
    return [...this.activeWorktrees.entries()].map(([teamId, path]) => ({
      teamId,
      path,
    }))
  }


  private checkGitRepo(): boolean {
    try {
      execSync('git rev-parse --is-inside-work-tree', {
        cwd: this.projectRoot,
        stdio: 'pipe',
        timeout: 5_000,
      })
      return true
    } catch {
      return false
    }
  }

  /**
   * Ensure the worktree base directory is in .gitignore.
   */
  private ensureGitignore(): void {
    const gitignorePath = join(this.projectRoot, '.gitignore')
    const pattern = this.config.baseDir

    try {
      if (existsSync(gitignorePath)) {
        const content = readFileSync(gitignorePath, 'utf8')
        if (!content.includes(pattern)) {
          appendFileSync(gitignorePath, `\n# CassiCore team worktrees\n${pattern}/\n`)
          this.logger.debug('[worktree-mgr] Added worktree dir to .gitignore')
        }
      }
    } catch {
      // Non-fatal — the directory still works without being gitignored
    }
  }

  /**
   * Sanitize team ID for use in filesystem paths and branch names.
   */
  private sanitizeTeamId(teamId: string): string {
    return teamId.replace(/[^a-zA-Z0-9_-]/g, '-')
  }
}
