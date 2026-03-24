/**
 * GlobalBlackboardRegistry — Persistent, named Blackboard store.
 *
 * Manages named Blackboard instances that survive across Lumen/Dyad sessions
 * and optionally persist to disk across daemon restarts.
 *
 * Named boards follow conventions (not enforced):
 *   project:{name}   — long-running project workspaces
 *   analysis:{name}  — analysis result caches
 *   coord:{name}     — coordination workspaces
 *
 * Persist: boards with persist=true are saved to {persistDir}/{name}.json
 * Default persist directory: ~/.cassicore/blackboards/
 */

import fs from 'node:fs'
import path from 'node:path'
import { homedir } from 'node:os'
import type { ILogger } from '../../../types/interfaces.js'
import type { BlackboardChannel, BlackboardEntry, BlackboardState } from '../../../types/flux-team.js'
import type {
  PaginatedResult,
  ChannelSearchOptions,
  ScratchpadSearchOptions,
  ToolLogSearchOptions,
  ArtifactSearchOptions,
  PlanSearchOptions,
  ReportSearchOptions,
  CrossBoardSearchOptions,
  CrossBoardSearchResult,
  ChangeWindow,
  BlackboardWatchResult,
  SearchableBoard,
} from '../../../types/blackboard-search.js'
import type {
  FluxScratchpadEntry,
  FluxToolRecord,
  ArtifactEntry,
  PlanStep,
  ReportSection,
} from '../../../types/flux-team.js'
import type { BlackboardSummary } from './blackboard.js'
import { Blackboard } from './blackboard.js'


export interface GlobalBlackboardEntry {
  name: string
  blackboard: Blackboard
  createdAt: number
  lastActivity: number
  persist: boolean
}


export class GlobalBlackboardRegistry {
  private readonly boards = new Map<string, GlobalBlackboardEntry>()
  private readonly logger: ILogger
  private readonly persistDir: string

  constructor(logger: ILogger, persistDir?: string) {
    this.logger = logger.child('global-blackboard-registry')
    this.persistDir = persistDir ?? path.join(homedir(), '.cassicore', 'blackboards')
  }


  /**
   * Get an existing Blackboard by name, or create a new one.
   *
   * @param name - Board name (e.g. "project:my-project")
   * @param opts - Options for the new board
   * @returns The Blackboard instance
   */
  getOrCreate(name: string, opts?: { persist?: boolean }): Blackboard {
    const existing = this.boards.get(name)
    if (existing) {
      existing.lastActivity = Date.now()
      return existing.blackboard
    }

    const bb = new Blackboard(this.logger, name)
    const entry: GlobalBlackboardEntry = {
      name,
      blackboard: bb,
      createdAt: Date.now(),
      lastActivity: Date.now(),
      persist: opts?.persist ?? false,
    }

    this.boards.set(name, entry)
    this.logger.info('Global blackboard created', { name, persist: entry.persist })
    return bb
  }

  /**
   * Get an existing Blackboard by name.
   *
   * @param name - Board name
   * @returns The Blackboard instance or undefined
   */
  get(name: string): Blackboard | undefined {
    const entry = this.boards.get(name)
    if (entry) {
      entry.lastActivity = Date.now()
      return entry.blackboard
    }
    return undefined
  }

  /**
   * List all known boards with metadata.
   *
   * @returns Array of board metadata (no Blackboard instance)
   */
  list(): Array<{ name: string; createdAt: number; lastActivity: number; persist: boolean }> {
    return Array.from(this.boards.values()).map(e => ({
      name: e.name,
      createdAt: e.createdAt,
      lastActivity: e.lastActivity,
      persist: e.persist,
    }))
  }

  /**
   * Delete a board.
   *
   * @param name - Board name
   * @returns true if the board existed and was deleted
   */
  delete(name: string): boolean {
    const existed = this.boards.has(name)
    if (existed) {
      this.boards.delete(name)
      this.logger.info('Global blackboard deleted', { name })
      // Also remove persisted file
      try {
        const filePath = this.boardPath(name)
        if (fs.existsSync(filePath)) {
          fs.rmSync(filePath)
        }
      } catch (err) {
        this.logger.warn('Failed to remove persisted blackboard file', { name, error: String(err) })
      }
    }
    return existed
  }

  /**
   * Get a snapshot of a named board.
   *
   * @param name - Board name
   * @returns BlackboardState snapshot or null if not found
   */
  getSnapshot(name: string): BlackboardState | null {
    const entry = this.boards.get(name)
    if (!entry) return null
    return entry.blackboard.getSnapshot()
  }

  /**
   * Get a compact summary of a named board.
   */
  getSummary(name: string): BlackboardSummary | null {
    const entry = this.boards.get(name)
    if (!entry) return null
    return entry.blackboard.getSummary()
  }

  /**
   * Get entries from a single channel of a named board, with optional limit.
   */
  getChannelEntries(name: string, channel: BlackboardChannel, limit?: number): BlackboardEntry[] | null {
    const entry = this.boards.get(name)
    if (!entry) return null
    return entry.blackboard.getChannelEntries(channel, limit)
  }

  // ── Search pass-through methods ──

  /** Search channel entries on a named board. */
  searchChannel(name: string, opts: ChannelSearchOptions = {}): PaginatedResult<BlackboardEntry> | null {
    const entry = this.boards.get(name)
    if (!entry) return null
    entry.lastActivity = Date.now()
    return entry.blackboard.searchChannel(opts)
  }

  /** Search scratchpad entries on a named board. */
  searchScratchpad(name: string, opts: ScratchpadSearchOptions = {}): PaginatedResult<FluxScratchpadEntry> | null {
    const entry = this.boards.get(name)
    if (!entry) return null
    entry.lastActivity = Date.now()
    return entry.blackboard.searchScratchpad(opts)
  }

  /** Search tool log records on a named board. */
  searchToolLog(name: string, opts: ToolLogSearchOptions = {}): PaginatedResult<FluxToolRecord> | null {
    const entry = this.boards.get(name)
    if (!entry) return null
    entry.lastActivity = Date.now()
    return entry.blackboard.searchToolLog(opts)
  }

  /** Search artifact entries on a named board. */
  searchArtifacts(name: string, opts: ArtifactSearchOptions = {}): PaginatedResult<ArtifactEntry> | null {
    const entry = this.boards.get(name)
    if (!entry) return null
    entry.lastActivity = Date.now()
    return entry.blackboard.searchArtifacts(opts)
  }

  /** Search plan steps on a named board. */
  searchPlan(name: string, opts: PlanSearchOptions = {}): PaginatedResult<PlanStep> | null {
    const entry = this.boards.get(name)
    if (!entry) return null
    entry.lastActivity = Date.now()
    return entry.blackboard.searchPlan(opts)
  }

  /** Search report sections on a named board. */
  searchReport(name: string, opts: ReportSearchOptions = {}): PaginatedResult<ReportSection> | null {
    const entry = this.boards.get(name)
    if (!entry) return null
    entry.lastActivity = Date.now()
    return entry.blackboard.searchReport(opts)
  }

  /** Cross-board unified search on a named board. */
  searchAll(name: string, opts: CrossBoardSearchOptions): CrossBoardSearchResult | null {
    const entry = this.boards.get(name)
    if (!entry) return null
    entry.lastActivity = Date.now()
    return entry.blackboard.searchAll(opts)
  }

  /** Get accumulated changes since a timestamp on a named board. */
  watch(
    name: string,
    window: ChangeWindow,
    boards?: SearchableBoard[],
    includeContent?: boolean,
  ): BlackboardWatchResult | null {
    const entry = this.boards.get(name)
    if (!entry) return null
    entry.lastActivity = Date.now()
    return entry.blackboard.buildWatchResult(name, window, boards, includeContent)
  }

  /**
   * Persist a named board to disk.
   *
   * @param name - Board name
   */
  async save(name: string): Promise<void> {
    const entry = this.boards.get(name)
    if (!entry) throw new Error(`Board not found: ${name}`)

    const snapshot = entry.blackboard.getSnapshot()
    const filePath = this.boardPath(name)

    // Ensure directory exists
    await fs.promises.mkdir(path.dirname(filePath), { recursive: true })
    await fs.promises.writeFile(filePath, JSON.stringify(snapshot, null, 2), 'utf8')

    this.logger.debug('Global blackboard saved', { name, filePath })
  }

  /**
   * Load a persisted board from disk.
   *
   * @param name - Board name
   * @returns true if the board was loaded successfully
   */
  async load(name: string): Promise<boolean> {
    const filePath = this.boardPath(name)
    if (!fs.existsSync(filePath)) return false

    try {
      const raw = await fs.promises.readFile(filePath, 'utf8')
      const snapshot: BlackboardState = JSON.parse(raw)

      const bb = new Blackboard(this.logger, name)
      bb.restoreFromSnapshot(snapshot)

      const entry: GlobalBlackboardEntry = {
        name,
        blackboard: bb,
        createdAt: snapshot.createdAt,
        lastActivity: snapshot.lastActivityAt,
        persist: true,
      }

      this.boards.set(name, entry)
      this.logger.info('Global blackboard loaded from disk', { name })
      return true
    } catch (err) {
      this.logger.error('Failed to load persisted blackboard', { name, error: String(err) })
      return false
    }
  }

  /**
   * Load all persisted boards from the persist directory.
   * Called at daemon startup.
   */
  async loadAll(): Promise<void> {
    try {
      if (!fs.existsSync(this.persistDir)) return

      const files = await fs.promises.readdir(this.persistDir)
      const jsonFiles = files.filter(f => f.endsWith('.json'))

      await Promise.all(jsonFiles.map(async (file) => {
        const name = file.slice(0, -5) // strip .json
        try {
          await this.load(name)
        } catch (err) {
          this.logger.warn('Failed to load blackboard during startup', { name, error: String(err) })
        }
      }))

      if (jsonFiles.length > 0) {
        this.logger.info('Global blackboards loaded', { count: jsonFiles.length })
      }
    } catch (err) {
      this.logger.warn('Failed to scan blackboard persist directory', { error: String(err) })
    }
  }


  private boardPath(name: string): string {
    // Sanitize name to a safe filename (replace / and : with -)
    const safeName = name.replace(/[/:]/g, '-').replace(/[^a-zA-Z0-9_.\-]/g, '_')
    return path.join(this.persistDir, `${safeName}.json`)
  }
}
