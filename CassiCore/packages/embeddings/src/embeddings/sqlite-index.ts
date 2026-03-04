import Database from 'better-sqlite3';
import path from 'path';
import fs from 'fs';
import type { ILogger } from '../../../types/interfaces.js';

export interface VectorHit {
  id: string;
  score: number;
  meta?: any;
}

export class SqliteVectorIndex {
  private db?: Database.Database;
  private logger: ILogger;
  private table = 'vector_index';

  constructor(logger: ILogger, opts?: { dbPath?: string }) {
    this.logger = logger.child?.('vector-index') ?? logger;
    const homedir = process.env.HOME || require('os').homedir();
    const dbPath = opts?.dbPath ?? path.join(homedir!, '.cassicore', 'data', 'vectors.db');

    try {
      const dir = path.dirname(dbPath);
      if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
      this.db = new Database(dbPath);
      this.db.pragma('busy_timeout = 5000');
      this.db.exec(`
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS ${this.table} (
          id TEXT PRIMARY KEY,
          vec TEXT NOT NULL,
          meta TEXT,
          ts INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_vector_ts ON ${this.table}(ts);
      `);
      this.logger.info('SqliteVectorIndex: initialized', { dbPath });
    } catch (err) {
      this.logger.warn('SqliteVectorIndex: failed to initialize', { error: String(err) });
      this.db = undefined;
    }
  }

  addVector(id: string, vector: number[], meta?: any): void {
    if (!this.db) return;
    try {
      this.db.prepare(`INSERT OR REPLACE INTO ${this.table} (id, vec, meta, ts) VALUES (?, ?, ?, ?)`)
        .run(id, JSON.stringify(vector), meta ? JSON.stringify(meta) : null, Date.now());
    } catch (err) {
      this.logger.warn('SqliteVectorIndex: failed to add vector', { id, error: String(err) });
    }
  }

  removeVector(id: string): void {
    if (!this.db) return;
    try { this.db.prepare(`DELETE FROM ${this.table} WHERE id = ?`).run(id); } catch (err) { this.logger.warn('SqliteVectorIndex: failed to remove vector', { id, error: String(err) }); }
  }

  query(vector: number[], topK = 10): VectorHit[] {
    if (!this.db) return [];
    try {
      const rows = this.db.prepare(`SELECT id, vec, meta FROM ${this.table}`).all() as any[];
      const out: VectorHit[] = [];
      for (const r of rows) {
        try {
          const vec = JSON.parse(r.vec) as number[];
          const score = this.cosineSimilarity(vector, vec);
          out.push({ id: r.id, score, meta: r.meta ? JSON.parse(r.meta) : undefined });
        } catch (err) { /* skip malformed */ }
      }
      return out.sort((a,b) => b.score - a.score).slice(0, topK);
    } catch (err) {
      this.logger.warn('SqliteVectorIndex: query failed', { error: String(err) });
      return [];
    }
  }

  listAll(): { id: string; meta?: any }[] {
    if (!this.db) return [];
    try {
      const rows = this.db.prepare(`SELECT id, meta FROM ${this.table} ORDER BY ts DESC`).all() as any[];
      return rows.map(r => ({ id: r.id, meta: r.meta ? JSON.parse(r.meta) : undefined }));
    } catch (err) {
      this.logger.warn('SqliteVectorIndex: listAll failed', { error: String(err) });
      return [];
    }
  }

  close(): void {
    try { this.db?.close(); } catch (err) { this.logger.debug('SqliteVectorIndex: close failed', { error: String(err) }); }
  }

  private cosineSimilarity(a: number[] | null, b: number[] | null): number {
    if (!a || !b || a.length !== b.length) return 0;
    let dot = 0, ma = 0, mb = 0;
    for (let i = 0; i < a.length; i++) {
      dot += (a[i] || 0) * (b[i] || 0);
      ma += (a[i] || 0) * (a[i] || 0);
      mb += (b[i] || 0) * (b[i] || 0);
    }
    if (ma === 0 || mb === 0) return 0;
    return dot / (Math.sqrt(ma) * Math.sqrt(mb));
  }
}
