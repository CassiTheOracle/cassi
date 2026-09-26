/**
 * Scenario Store — SQLite-backed persistent registry of verification scenarios.
 *
 * Stores both hardcoded scenarios (from the scenarios/ directory) and
 * generated scenarios (from the ScenarioGenerator). Tracks execution
 * stats for staleness detection and meta-learning.
 */

import type Database from 'better-sqlite3'
import type { ILogger } from '@cassicore/foundation'
import type { WorkflowScenario } from '../verification/scenario-types.js'
import type { StoredScenario } from '../../intelligence/improvement/types.js'
import { scenarios as hardcodedScenarios } from './index.js'

export class ScenarioStore {
  private readonly logger: ILogger
  private db?: Database.Database
  /** In-memory cache of all scenarios (hardcoded + persisted) */
  private cache = new Map<string, StoredScenario>()

  constructor(logger: ILogger) {
    this.logger = logger.child?.('scenario-store') ?? logger
  }


  initialize(db: Database.Database): void {
    this.db = db
    this.initSchema()
    this.loadHardcoded()
    this.loadPersisted()
    this.logger.info('Initialized', { total: this.cache.size })
  }

  private initSchema(): void {
    if (!this.db) return

    this.db.exec(`
      CREATE TABLE IF NOT EXISTS scenario_store (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        description TEXT,
        definition_json TEXT NOT NULL,
        trigger_type TEXT NOT NULL DEFAULT 'hardcoded',
        trigger_id TEXT,
        tags_json TEXT NOT NULL DEFAULT '[]',
        run_count INTEGER NOT NULL DEFAULT 0,
        pass_count INTEGER NOT NULL DEFAULT 0,
        last_run_at INTEGER,
        last_pass_at INTEGER,
        stale INTEGER NOT NULL DEFAULT 0,
        created_at INTEGER NOT NULL
      );

      CREATE INDEX IF NOT EXISTS idx_ss_name ON scenario_store(name);
      CREATE INDEX IF NOT EXISTS idx_ss_trigger ON scenario_store(trigger_type);
      CREATE INDEX IF NOT EXISTS idx_ss_stale ON scenario_store(stale);
    `)
  }

  /** Load hardcoded scenarios into cache (not persisted to SQLite) */
  private loadHardcoded(): void {
    for (const [name, scenario] of Object.entries(hardcodedScenarios)) {
      this.cache.set(name, {
        id: `hardcoded-${name}`,
        name,
        description: scenario.description,
        definition: scenario,
        triggerType: 'hardcoded',
        tags: ['hardcoded'],
        runCount: 0,
        passCount: 0,
        stale: false,
        createdAt: 0,
      })
    }
  }

  /** Load persisted scenarios from SQLite into cache */
  private loadPersisted(): void {
    if (!this.db) return

    try {
      const rows = this.db.prepare('SELECT * FROM scenario_store').all() as any[]
      for (const row of rows) {
        try {
          const stored = this.rowToStored(row)
          this.cache.set(stored.name, stored)
        } catch { /* skip malformed rows */ }
      }
    } catch (err) {
      this.logger.warn('Failed to load persisted scenarios', { error: String(err) })
    }
  }


  /** Add or update a scenario in the store */
  add(scenario: WorkflowScenario, meta: {
    triggerType: StoredScenario['triggerType']
    triggerId?: string
    tags?: string[]
  }): StoredScenario {
    const id = `gen-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
    const stored: StoredScenario = {
      id,
      name: scenario.name,
      description: scenario.description,
      definition: scenario,
      triggerType: meta.triggerType,
      triggerId: meta.triggerId,
      tags: meta.tags ?? [],
      runCount: 0,
      passCount: 0,
      stale: false,
      createdAt: Date.now(),
    }

    this.cache.set(scenario.name, stored)
    this.persist(stored)
    this.logger.info('Scenario added', { name: scenario.name, trigger: meta.triggerType })
    return stored
  }

  /** Get a scenario by name */
  get(name: string): StoredScenario | undefined {
    return this.cache.get(name)
  }

  /** Get all scenarios */
  getAll(): StoredScenario[] {
    return Array.from(this.cache.values())
  }

  /** Get scenarios filtered by criteria */
  filter(opts: {
    triggerType?: StoredScenario['triggerType']
    stale?: boolean
    tags?: string[]
    minRuns?: number
  } = {}): StoredScenario[] {
    let results = Array.from(this.cache.values())

    if (opts.triggerType !== undefined) {
      results = results.filter(s => s.triggerType === opts.triggerType)
    }
    if (opts.stale !== undefined) {
      results = results.filter(s => s.stale === opts.stale)
    }
    if (opts.tags && opts.tags.length > 0) {
      results = results.filter(s => opts.tags!.some(t => s.tags.includes(t)))
    }
    if (opts.minRuns !== undefined) {
      results = results.filter(s => s.runCount >= opts.minRuns!)
    }

    return results
  }

  /** Get scenario definitions suitable for the gate (non-stale, active) */
  getForGate(): WorkflowScenario[] {
    return this.filter({ stale: false }).map(s => s.definition)
  }


  /** Record a scenario run result */
  recordRun(name: string, passed: boolean): void {
    const stored = this.cache.get(name)
    if (!stored) return

    stored.runCount++
    stored.lastRunAt = Date.now()
    if (passed) {
      stored.passCount++
      stored.lastPassAt = Date.now()
    }

    // Persist update
    if (this.db && stored.triggerType !== 'hardcoded') {
      try {
        this.db.prepare(`
          UPDATE scenario_store
          SET run_count = ?, pass_count = ?, last_run_at = ?, last_pass_at = ?
          WHERE name = ?
        `).run(stored.runCount, stored.passCount, stored.lastRunAt, stored.lastPassAt ?? null, name)
      } catch { /* best effort */ }
    }
  }

  /** Mark a scenario as stale (always passes, not catching regressions) */
  markStale(name: string): void {
    const stored = this.cache.get(name)
    if (!stored) return

    stored.stale = true

    if (this.db && stored.triggerType !== 'hardcoded') {
      try {
        this.db.prepare('UPDATE scenario_store SET stale = 1 WHERE name = ?').run(name)
      } catch { /* best effort */ }
    }

    this.logger.info('Scenario marked stale', { name })
  }

  /** Detect scenarios that should be marked stale (N consecutive passes) */
  detectStaleness(threshold: number): string[] {
    const staleNames: string[] = []

    for (const stored of this.cache.values()) {
      if (stored.stale) continue
      if (stored.runCount < threshold) continue
      // If pass rate is 100% over threshold runs, it's stale
      if (stored.passCount >= stored.runCount && stored.runCount >= threshold) {
        this.markStale(stored.name)
        staleNames.push(stored.name)
      }
    }

    return staleNames
  }

  /** Remove a scenario from the store */
  remove(name: string): boolean {
    const stored = this.cache.get(name)
    if (!stored) return false
    // Don't allow removing hardcoded scenarios
    if (stored.triggerType === 'hardcoded') return false

    this.cache.delete(name)
    if (this.db) {
      try {
        this.db.prepare('DELETE FROM scenario_store WHERE name = ?').run(name)
      } catch { /* best effort */ }
    }
    return true
  }


  private persist(stored: StoredScenario): void {
    if (!this.db) return
    if (stored.triggerType === 'hardcoded') return

    try {
      this.db.prepare(`
        INSERT OR REPLACE INTO scenario_store
          (id, name, description, definition_json, trigger_type, trigger_id,
           tags_json, run_count, pass_count, last_run_at, last_pass_at,
           stale, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      `).run(
        stored.id,
        stored.name,
        stored.description,
        JSON.stringify(stored.definition),
        stored.triggerType,
        stored.triggerId ?? null,
        JSON.stringify(stored.tags),
        stored.runCount,
        stored.passCount,
        stored.lastRunAt ?? null,
        stored.lastPassAt ?? null,
        stored.stale ? 1 : 0,
        stored.createdAt,
      )
    } catch (err) {
      this.logger.error('Failed to persist scenario', { name: stored.name, error: String(err) })
    }
  }

  private rowToStored(row: any): StoredScenario {
    return {
      id: row.id,
      name: row.name,
      description: row.description ?? '',
      definition: JSON.parse(row.definition_json),
      triggerType: row.trigger_type,
      triggerId: row.trigger_id ?? undefined,
      tags: JSON.parse(row.tags_json || '[]'),
      runCount: row.run_count ?? 0,
      passCount: row.pass_count ?? 0,
      lastRunAt: row.last_run_at ?? undefined,
      lastPassAt: row.last_pass_at ?? undefined,
      stale: row.stale === 1,
      createdAt: row.created_at,
    }
  }
}
