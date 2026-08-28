/**
 * ErrorLearner — Unified Error Pattern Reflection and Recovery Module
 *
 * Merges Reflect (persistent error pattern storage) and Recover (in-memory
 * recovery pattern matching + orchestration) into a single intelligence module.
 *
 * This unified approach:
 * - Stores error patterns persistently in SQLite (from Reflect)
 * - Maintains in-memory recovery patterns and attempt tracking (from Recover)
 * - Integrates with Subconscious observer through legacy event emission
 * - Provides both IReflect and IRecover contracts for backward compatibility
 */

import { EventEmitter } from 'events';
import fs from 'fs';
import { createRequire } from 'node:module';
import path from 'path';

import { BaseCognitiveModule } from '../base/cognitive-module.js';
import { TTLCache } from '@cassicore/utils';
import { getModelSpec } from '@cassicore/foundation';

import type { IReflect, IRecover, RecoveryPattern, RecoveryStrategy, ReflectionPattern } from '@cassicore/foundation';
import type { ILogger, IEventBus } from '@cassicore/foundation';

const _require = createRequire(import.meta.url);

let Database: any;
try {
  Database = _require('better-sqlite3');
} catch (e) {
  try {
    Database = _require('sqlite3').verbose();
  } catch (e2) {
    Database = null;
  }
}

/**
 * ErrorLearner — Unified error pattern learning and recovery
 *
 * Implements both IReflect (persistence) and IRecover (recovery orchestration)
 * interfaces to provide a seamless migration path from separate Reflect/Recover
 * modules.
 */
export class ErrorLearner extends BaseCognitiveModule implements IReflect, IRecover {
  readonly name = 'error-learner';
  readonly priority = 70; // Reflect's priority

  private dbPath: string;
  private db: any = null;
  private isBetter: boolean = false;

  // Recovery state (from Recover)
  private patterns: RecoveryPattern[] = [];
  private attempts: TTLCache<string, number> = new TTLCache({ maxSize: 500, ttlMs: 60 * 60 * 1000 }); // 1 hour TTL
  private emitter = new EventEmitter();

  /**
   * Create an ErrorLearner
   * @param logger ILogger implementation
   * @param dbPath optional path to sqlite db
   */
  constructor(logger: ILogger, dbPath?: string) {
    super(logger);
    this.logger = logger.child('error-learner');
    const home = process.env.HOME || process.env.USERPROFILE || '.';
    this.dbPath = dbPath || path.join(home, '.cassicore', 'data', 'system-state.db');
    this.ensureDbDir();
    this.initDb();

    // Initialize default recovery patterns
    this.patterns = [
      { errorPattern: 'rate_limit', strategy: 'retry-with-backoff', maxAttempts: 3 },
      { errorPattern: 'timeout', strategy: 'retry', maxAttempts: 2 },
      { errorPattern: 'model_unavailable', strategy: 'fallback-model', fallbackModel: getModelSpec('fallback'), maxAttempts: 1 },
    ];
  }

  async init(): Promise<void> {
    await super.init();
    this.logger.info('ErrorLearner: initialized', {
      patterns: this.patterns.length,
      dbPath: this.dbPath,
      hasDb: !!this.db
    });
  }

  async start(): Promise<void> {
    await super.start();
    this.logger.info('ErrorLearner: started');
  }

  async stop(): Promise<void> {
    this.attempts.clear();
    try {
      if (this.db && this.isBetter) {
        this.db.close();
      }
    } catch {}
    await super.stop();
    this.logger.info('ErrorLearner: stopped');
  }

  // Database Setup (from Reflect)

  private ensureDbDir(): void {
    const dir = path.dirname(this.dbPath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
  }

  private initDb(): void {
    if (!Database) {
      this.logger.warn('ErrorLearner: no sqlite driver available');
      return;
    }

    try {
      this.db = new Database(this.dbPath);
      this.isBetter = true;

      // Main patterns table with additional columns for recovery
      this.db.exec(`
        CREATE TABLE IF NOT EXISTS patterns (
          id TEXT PRIMARY KEY,
          pattern TEXT NOT NULL,
          category TEXT NOT NULL,
          fix TEXT,
          context TEXT,
          occurrences INTEGER DEFAULT 1,
          resolved BOOLEAN DEFAULT 0,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          -- Recovery-specific columns
          strategy TEXT,
          max_attempts INTEGER DEFAULT 3,
          fallback_model TEXT
        )
      `);

      // Full-text search for semantic lookup
      this.db.exec(`
        CREATE VIRTUAL TABLE IF NOT EXISTS patterns_fts USING fts5(
          pattern,
          category,
          fix,
          content='patterns',
          content_rowid='rowid'
        )
      `);

      // Triggers to keep FTS index in sync
      this.db.exec(`
        CREATE TRIGGER IF NOT EXISTS patterns_fts_insert AFTER INSERT ON patterns BEGIN
          INSERT INTO patterns_fts(rowid, pattern, category, fix)
          VALUES (new.rowid, new.pattern, new.category, new.fix);
        END;
        CREATE TRIGGER IF NOT EXISTS patterns_fts_delete AFTER DELETE ON patterns BEGIN
          INSERT INTO patterns_fts(patterns_fts, rowid, pattern, category, fix)
          VALUES ('delete', old.rowid, old.pattern, old.category, old.fix);
        END;
        CREATE TRIGGER IF NOT EXISTS patterns_fts_update AFTER UPDATE ON patterns BEGIN
          INSERT INTO patterns_fts(patterns_fts, rowid, pattern, category, fix)
          VALUES ('delete', old.rowid, old.pattern, old.category, old.fix);
          INSERT INTO patterns_fts(rowid, pattern, category, fix)
          VALUES (new.rowid, new.pattern, new.category, new.fix);
        END;
      `);

      // Recovery outcomes for learning
      this.db.exec(`
        CREATE TABLE IF NOT EXISTS recovery_outcomes (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          pattern_id TEXT NOT NULL,
          strategy TEXT NOT NULL,
          success BOOLEAN NOT NULL,
          context TEXT,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY (pattern_id) REFERENCES patterns(id)
        )
      `);

      this.db.exec(`
        CREATE INDEX IF NOT EXISTS idx_patterns_category ON patterns(category);
        CREATE INDEX IF NOT EXISTS idx_patterns_resolved ON patterns(resolved);
        CREATE INDEX IF NOT EXISTS idx_outcomes_pattern ON recovery_outcomes(pattern_id);
      `);
    } catch (err) {
      this.logger.error('ErrorLearner: failed to init db', { error: String(err) });
      this.db = null;
    }
  }

  // IReflect Implementation (from Reflect)

  /**
   * Add a new error/success pattern
   */
  async add(entry: { pattern: string; category: string; fix?: string; context?: string }): Promise<string> {
    if (!this.db) {
      this.logger.debug('ErrorLearner: no db, skipping add');
      return this.hashId(entry.pattern);
    }

    const id = this.hashId(entry.pattern);

    try {
      const existing = this.db.prepare('SELECT id, occurrences FROM patterns WHERE id = ?').get(id);

      if (existing) {
        this.db.prepare(
          'UPDATE patterns SET occurrences = occurrences + 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?'
        ).run(id);
      } else {
        this.db.prepare(
          `INSERT INTO patterns (id, pattern, category, fix, context, occurrences, resolved)
           VALUES (?, ?, ?, ?, ?, 1, 0)`
        ).run(id, entry.pattern, entry.category, entry.fix ?? null, entry.context ?? null);
      }

      // Emit legacy event for Subconscious integration
      this.emitSubconsciousLearning(entry.category, entry.pattern);

      // Emit typed event for observability
      this.eventBus?.emit({
        type: 'error-learner:pattern_stored',
        pattern: entry.pattern,
        category: entry.category,
        occurrences: existing ? existing.occurrences + 1 : 1,
        timestamp: new Date()
      } as any);

      return id;
    } catch (err) {
      this.logger.error('ErrorLearner: add failed', { error: String(err) });
      return id;
    }
  }

  /**
   * Search for known patterns
   */
  async search(query: string, limit: number = 10): Promise<ReflectionPattern[]> {
    if (!this.db) return [];

    try {
      // Hybrid search: FTS for relevance + exact matches.
      // Sanitize query for FTS5: wrap in double quotes for phrase matching
      // and escape internal quotes to prevent column filter injection
      // (e.g., "activity:" being interpreted as a column reference).
      const sanitizedQuery = '"' + query.replace(/"/g, '""') + '"'

      let ftsResults: Array<{ id: string; pattern: string; category: string; fix: string | null; occurrences: number; resolved: number; created_at: string }> = []
      try {
        ftsResults = this.db.prepare(
          `SELECT p.id, p.pattern, p.category, p.fix, p.occurrences, p.resolved, p.created_at
           FROM patterns_fts fts
           JOIN patterns p ON p.rowid = fts.rowid
           WHERE patterns_fts MATCH ?
           ORDER BY rank
           LIMIT ?`
        ).all(sanitizedQuery, limit);
      } catch (ftsErr) {
        // FTS5 query may still fail on edge cases — fall through to LIKE search
        this.logger.debug('ErrorLearner: FTS search failed, falling back to LIKE', { error: String(ftsErr) });
      }

      const likeResults: Array<{ id: string; pattern: string; category: string; fix: string | null; occurrences: number; resolved: number; created_at: string }> =
        this.db.prepare(
          `SELECT id, pattern, category, fix, occurrences, resolved, created_at
           FROM patterns
           WHERE pattern LIKE ? OR category LIKE ?
           LIMIT ?`
        ).all(`%${query}%`, `%${query}%`, limit);

      const seen = new Set<string>();
      const combined: ReflectionPattern[] = [];

      for (const row of [...ftsResults, ...likeResults]) {
        if (seen.has(row.id)) continue;
        seen.add(row.id);
        combined.push({
          id: row.id,
          pattern: row.pattern,
          category: row.category,
          fix: row.fix ?? undefined,
          occurrences: row.occurrences,
          resolved: !!row.resolved,
          createdAt: new Date(row.created_at)
        });
        if (combined.length >= limit) break;
      }

      return combined;
    } catch (err) {
      this.logger.error('ErrorLearner: search failed', { error: String(err) });
      return [];
    }
  }

  /**
   * Resolve a pattern (mark as fixed)
   */
  async resolve(id: string, fix: string): Promise<void> {
    if (!this.db) return;

    try {
      this.db.prepare(
        'UPDATE patterns SET resolved = 1, fix = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?'
      ).run(fix, id);
    } catch (err) {
      this.logger.error('ErrorLearner: resolve failed', { error: String(err) });
    }
  }

  /**
   * Get unresolved patterns
   */
  async unresolved(limit: number = 20): Promise<ReflectionPattern[]> {
    if (!this.db) return [];

    try {
      const rows: Array<{ id: string; pattern: string; category: string; fix: string | null; occurrences: number; resolved: number; created_at: string }> =
        this.db.prepare(
          `SELECT id, pattern, category, fix, occurrences, resolved, created_at
           FROM patterns
           WHERE resolved = 0
           ORDER BY occurrences DESC, created_at DESC
           LIMIT ?`
        ).all(limit);

      return rows.map(row => ({
        id: row.id,
        pattern: row.pattern,
        category: row.category,
        fix: row.fix ?? undefined,
        occurrences: row.occurrences,
        resolved: !!row.resolved,
        createdAt: new Date(row.created_at)
      }));
    } catch (err) {
      this.logger.error('ErrorLearner: unresolved query failed', { error: String(err) });
      return [];
    }
  }

  /**
   * Generate a deterministic hash ID for a pattern
   */
  hashId(input: string): string {
    // Simple FNV-1a hash — not cryptographic, just for dedup
    let h = 2166136261 >>> 0;
    for (let i = 0; i < input.length; i++) {
      h ^= input.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return `p_${(h >>> 0).toString(16)}`;
  }

  // IRecover Implementation (from Recover)

  /**
   * Register a recovery pattern
   */
  register(pattern: RecoveryPattern): void {
    this.patterns.push(pattern);
    this.logger.debug('ErrorLearner: registered recovery pattern', { pattern: pattern.errorPattern });
  }

  /**
   * Attempt recovery for an error. Returns strategy used or null if no match.
   */
  async handleError(error: Error, context: Record<string, unknown>): Promise<RecoveryStrategy | null> {
    const message = (error && error.message) ? error.message : String(error);
    const pluginId = context.pluginId as string | undefined;

    // Find best match: exact substring first, then regex if pattern starts and ends with /
    for (const p of this.patterns) {
      try {
        const pat = p.errorPattern;
        let matched = false;

        if (pat.startsWith('/') && pat.endsWith('/')) {
          const body = pat.slice(1, -1);
          const re = new RegExp(body, 'i');
          matched = re.test(message);
        } else {
          matched = message.toLowerCase().includes(pat.toLowerCase());
        }

        if (!matched) continue;

        const key = `${p.errorPattern}:${context['pluginId'] ?? 'global'}`;
        const cur = this.attempts.get(key) ?? 0;

        if (cur >= p.maxAttempts) {
          this.logger.warn('ErrorLearner: max recovery attempts reached', {
            pattern: p.errorPattern,
            attempts: cur,
            maxAttempts: p.maxAttempts
          });

          // Emit exhausted event
          this.eventBus?.emit({
            type: 'error-learner:recovery_exhausted',
            pattern: p.errorPattern,
            context: JSON.stringify(context),
            timestamp: new Date()
          } as any);

          // Emit legacy pattern for Subconscious
          this.emitSubconsciousPattern(p.errorPattern, 'exhausted', cur, p.maxAttempts, context);

          // Emit plugin:stopped-style event
          this.eventBus?.emit({
            type: 'plugin:stopped',
            pluginId: String(context['pluginId'] ?? 'unknown'),
            reason: 'max-restarts'
          } as any);

          return null;
        }

        this.attempts.set(key, cur + 1);

        this.logger.info('ErrorLearner: applying recovery strategy', {
          pattern: p.errorPattern,
          strategy: p.strategy,
          attempt: cur + 1,
          maxAttempts: p.maxAttempts
        });

        // Implement strategy actions
        if (p.strategy === 'retry-with-backoff') {
          this.eventBus?.emit({
            type: 'plugin:restarted',
            pluginId: String(context['pluginId'] ?? 'unknown'),
            attempt: cur + 1
          } as any);
        } else if (p.strategy === 'fallback-model') {
          this.eventBus?.emit({
            type: 'worker:message',
            pluginId: String(context['pluginId'] ?? 'unknown'),
            payload: { action: 'fallback-model', model: p.fallbackModel }
          } as any);
        }

        // Emit typed event
        this.eventBus?.emit({
          type: 'error-learner:recovery_attempted',
          pattern: p.errorPattern,
          strategy: p.strategy,
          attempt: cur + 1,
          maxAttempts: p.maxAttempts,
          timestamp: new Date()
        } as any);

        // Emit legacy pattern for Subconscious
        this.emitSubconsciousPattern(p.errorPattern, p.strategy, cur + 1, p.maxAttempts, context);

        return p.strategy;
      } catch (err) {
        // Continue to next pattern
        continue;
      }
    }

    // No match
    return null;
  }

  /**
   * Record a successful recovery
   */
  async recordSuccess(errorPattern: string, strategy: RecoveryStrategy): Promise<void> {
    this.logger.info('ErrorLearner: recovery succeeded', {
      pattern: errorPattern,
      strategy
    });

    // Clear attempt counters for this pattern
    for (const k of Array.from(this.attempts.keys())) {
      if (k.startsWith(`${errorPattern}:`)) {
        this.attempts.delete(k);
      }
    }

    // Persist success to database
    if (this.db) {
      const patternId = this.hashId(errorPattern);
      try {
        this.db.prepare(
          `INSERT INTO recovery_outcomes (pattern_id, strategy, success, context)
           VALUES (?, ?, 1, ?)`
        ).run(patternId, strategy, JSON.stringify({ timestamp: new Date() }));
      } catch (err) {
        this.logger.debug('ErrorLearner: failed to record success', { error: String(err) });
      }
    }

    // Also store as a resolved pattern
    await this.add({
      pattern: errorPattern,
      category: 'recovery_success',
      fix: strategy,
      context: JSON.stringify({ strategy, timestamp: new Date() })
    });
  }

  // Subconscious Integration — Legacy Event Emission

  /**
   * Emit subconscious:learning event (legacy format for Subconscious integration)
   */
  private emitSubconsciousLearning(category: string, pattern: string): void {
    if (!this.eventBus) return;

    try {
      this.eventBus.emit({
        type: 'subconscious:learning' as any,
        learning: {
          summary: `Error pattern detected: ${category} — ${pattern}`,
          confidence: 0.7,
          patterns: [pattern],
          timestamp: new Date()
        },
        timestamp: new Date()
      });
    } catch (err) {
      this.logger.debug('ErrorLearner: failed to emit subconscious:learning', { error: String(err) });
    }
  }

  /**
   * Emit subconscious:pattern event (legacy format for Subconscious integration)
   */
  private emitSubconsciousPattern(errorPattern: string, strategy: string, attempts: number, maxAttempts: number, context?: Record<string, unknown>): void {
    if (!this.eventBus) return;

    try {
      this.eventBus.emit({
        type: 'subconscious:pattern' as any,
        sessionId: context?.sessionId as string | undefined,
        pattern: {
          pattern: `Recovery applied: ${strategy} for ${errorPattern}`,
          confidence: 0.8,
          evidence: [`attempt ${attempts}/${maxAttempts}`]
        },
        timestamp: new Date()
      });
    } catch (err) {
      this.logger.debug('ErrorLearner: failed to emit subconscious:pattern', { error: String(err) });
    }
  }

  // Event Subscriptions

  /**
   * Register event subscriptions (called by BaseCognitiveModule)
   */
  protected registerSubscriptions(): void {
    // Subscribe to plugin crashes
    this.subscribe('plugin:crashed' as any, async (event: any) => {
      const { pluginId, error, crashCount } = event;

      // Store the crash pattern
      await this.add({
        pattern: error || 'Plugin crashed',
        category: 'plugin_crash',
        context: JSON.stringify({ pluginId, crashCount })
      });

      // Attempt recovery
      const errorObj = new Error(error || 'Plugin crashed');
      await this.handleError(errorObj, { pluginId, crashCount });
    });

    // Subscribe to consciousness observations (from Subconscious)
    this.subscribe('consciousness:observation' as any, async (event: any) => {
      const observation = event.observation;
      if (!observation) return;

      // Check if observation matches known patterns
      const patterns = await this.search(observation.summary || '', 5);

      if (patterns.length > 0) {
        // Known pattern detected — emit learning event
        this.logger.debug('ErrorLearner: observation matches known patterns', {
          count: patterns.length,
          categories: patterns.map(p => p.category)
        });

        // Already handled by add() which emits the learning event
      } else if (observation.severity === 'high' || observation.severity === 'critical') {
        // New significant pattern — store it
        await this.add({
          pattern: observation.summary,
          category: observation.category || 'anomaly',
          context: JSON.stringify(observation)
        });
      }
    });

    this.logger.debug('ErrorLearner: registered event subscriptions');
  }

  // Public API (extensions beyond IReflect/IRecover)

  /**
   * Capture a crash directly (used by crash handler)
   */
  async captureCrash(pluginId: string, error: string, crashCount: number): Promise<void> {
    await this.add({
      pattern: error,
      category: 'plugin_crash',
      context: JSON.stringify({ pluginId, crashCount, timestamp: new Date() })
    });
  }

  /**
   * Get recovery statistics
   */
  getStats(): { patterns: number; attempts: number; dbConnected: boolean } {
    return {
      patterns: this.patterns.length,
      attempts: this.attempts.size,
      dbConnected: !!this.db
    };
  }
}

/**
 * Factory function for creating ErrorLearner instances
 * @dep callers: createIntelligence (core/intelligence/index.ts), createModule (tests/recover.test.ts), createModule (tests/reflect.test.ts)
 * @dep module: Tests
 * @dep risk: LOW | 3 callers, 0 flows, 1 module
 */
export function createErrorLearner(logger: ILogger, dbPath?: string): ErrorLearner {
  return new ErrorLearner(logger, dbPath);
}
