/**
 * Per-Helix-session worktree isolation. Each session gets its own git worktree
 * + branch under `<repo>/.worktrees/<sessionId>/`. On close, the branch is
 * merged back into main; conflicts surface as dialectic inputs (a feature).
 */

import path from 'node:path'

import type { ILogger } from '@cassicore/foundation'
import type { ContextRepoFs } from './fs.js'

export interface WorktreeHandle {
  sessionId: string
  branch: string
  path: string
}

export class WorktreeManager {
  private active = new Map<string, WorktreeHandle>()

  constructor(
    private readonly fs: ContextRepoFs,
    private readonly logger: ILogger,
  ) {}

  /** Open or attach to an existing worktree for a Helix session. */
  open(sessionId: string): WorktreeHandle {
    const existing = this.active.get(sessionId)
    if (existing) return existing
    this.fs.init()
    const branch = `helix/${sessionId}`
    const dir = this.fs.createWorktree(branch, sessionId)
    const handle = { sessionId, branch, path: dir }
    this.active.set(sessionId, handle)
    this.logger.info?.('[context-repo] worktree opened', { sessionId, dir })
    return handle
  }

  /** Close a worktree and merge its branch back into main. */
  close(sessionId: string): { merged: boolean; conflicts: string[] } {
    const handle = this.active.get(sessionId)
    if (!handle) return { merged: false, conflicts: [] }
    let result = { merged: true, conflicts: [] as string[] }
    try {
      const merge = this.fs.mergeBranch(handle.branch, `merge: ${handle.branch}`)
      if (!merge.ok) {
        this.logger.warn?.('[context-repo] worktree merge had conflicts', {
          sessionId,
          conflicts: merge.conflicts,
        })
        result = { merged: false, conflicts: merge.conflicts }
      }
    } finally {
      this.fs.removeWorktree(sessionId)
      this.active.delete(sessionId)
    }
    return result
  }

  list(): WorktreeHandle[] {
    return [...this.active.values()]
  }

  pathFor(sessionId: string): string | null {
    return this.active.get(sessionId)?.path ?? null
  }

  /** Return the absolute scratch path for a session (creates the dir if missing). */
  scratchPath(sessionId: string): string {
    const handle = this.open(sessionId)
    return path.join(handle.path, 'sessions', sessionId)
  }
}
