/** Git-backed projection of Cassi's working memory — fs primitive, projector, worktrees, writeback. */

import { ContextRepoFs } from './fs.js'
import { Projector, type EngramLike, type MnemicReader } from './projection.js'
import { WorktreeManager } from './worktrees.js'
import { Writeback, type WritebackTarget } from './writeback.js'
import { DEFAULT_CONTEXT_REPO_CONFIG, type ContextRepoConfig } from './types.js'

import type { ILogger } from '@cassicore/foundation'
import type { IEventBus } from '@cassicore/foundation'
import type { LaminaField } from '@cassicore/lamina-locus-bridge'

export class ContextRepo {
  readonly fs: ContextRepoFs
  readonly worktrees: WorktreeManager
  private cfg: ContextRepoConfig
  private projector: Projector
  private writeback?: Writeback
  private logger: ILogger

  constructor(logger: ILogger, projectPath: string, config?: Partial<ContextRepoConfig>) {
    this.cfg = { ...DEFAULT_CONTEXT_REPO_CONFIG, ...config }
    this.logger = logger
    this.fs = new ContextRepoFs(logger, projectPath, this.cfg.rootDir)
    this.projector = new Projector(this.fs, logger, this.cfg)
    this.worktrees = new WorktreeManager(this.fs, logger)
    if (this.cfg.enabled) this.fs.init()
  }

  setConfig(cfg: Partial<ContextRepoConfig>): void {
    this.cfg = { ...this.cfg, ...cfg }
    this.projector = new Projector(this.fs, this.logger, this.cfg)
  }

  /** Phase 3.1 safety net — wipe and re-init. */
  rebuild(): void { this.fs.rebuild() }

  /** Phase 3.2 — project state. Call from Meditation. */
  project(opts: { lamina?: LaminaField; mnemic?: MnemicReader; identity?: string }) {
    return this.projector.project(opts)
  }

  /** Phase 3.4 — wire writeback target and run scans. */
  configureWriteback(target: WritebackTarget, logger: ILogger): Writeback {
    this.writeback = new Writeback(this.fs, target, logger)
    return this.writeback
  }

  scanWriteback() {
    return this.writeback?.scan() ?? { engrams: 0, skills: 0, system: 0 }
  }

  /** Start a periodic scan loop. Returns a dispose function.
   * Uses setTimeout (not setInterval) to prevent pile-up when scans are slow. */
  startScanLoop(intervalMs = 30_000): () => void {
    let active = true
    let timer: NodeJS.Timeout
    const schedule = () => {
      if (!active) return
      timer = setTimeout(() => {
        try {
          const result = this.scanWriteback()
          if (result.engrams + result.skills + result.system > 0) {
            this.logger.info?.('[context-repo] writeback scan', result)
          }
        } catch (err) {
          this.logger.debug?.('[context-repo] writeback scan error', { error: String(err) })
        }
        schedule()
      }, intervalMs)
    }
    schedule()
    return () => { active = false; clearTimeout(timer) }
  }

  /** Subscribe to meditation:stopped to auto-project after each session. */
  subscribeToEventBus(eventBus: IEventBus, mnemic?: MnemicReader): void {
    eventBus.on('meditation:stopped' as any, () => {
      this.logger.info?.('[context-repo] auto-projecting after meditation')
      this.project({ mnemic })
    })
  }

  // Phase 3.3 — worktree convenience

  openWorktree(sessionId: string) { return this.worktrees.open(sessionId) }
  closeWorktree(sessionId: string) { return this.worktrees.close(sessionId) }
}

export { ContextRepoFs, Projector, WorktreeManager, Writeback }
export type { EngramLike, MnemicReader, WritebackTarget }
export type { ContextRepoConfig, ContextEntity, ContextFrontmatter, RepoStats } from './types.js'
