/**
 * SQLite Session Store Implementation
 * 
 * Production-ready SQLite storage for sessions
 */

import { mkdirSync } from 'node:fs';
import { join, dirname } from 'node:path';

import Database from 'better-sqlite3';

import { StoreError } from '../types.js';

import type {
  SessionState,
  SessionFilter,
  ISessionStore,
  ILogger
} from '../types.js';

export interface SQLiteStoreOptions {
  dbPath: string;
  logger?: ILogger;
  walMode?: boolean;
}

/**
 * SQLite implementation of ISessionStore
 */
export class SQLiteSessionStore implements ISessionStore {
  private db: Database.Database | null = null;
  private logger?: ILogger;
  private preparedStatements: Map<string, Database.Statement> = new Map();
  
  constructor(private options: SQLiteStoreOptions) {
    this.logger = options.logger;
  }
  
  /**
   * Initialize the database (create tables, etc.)
   */
  async initialize(): Promise<void> {
    try {
      // Ensure directory exists
      const dir = dirname(this.options.dbPath);
      mkdirSync(dir, { recursive: true });
      
      // Open database
      this.db = new Database(this.options.dbPath);
      
      // Enable WAL mode for better concurrency (optional)
      if (this.options.walMode !== false) {
        this.db.pragma('journal_mode = WAL');
      }

      // Set busy timeout to prevent lock contention
      this.db.pragma('busy_timeout = 5000');
      
      // Create tables
      this.createTables();
      
      // Prepare statements
      this.prepareStatements();
      
      this.logger?.info('SQLite session store initialized', {
        path: this.options.dbPath,
        walMode: this.options.walMode !== false
      });
      
    } catch (error) {
      throw new StoreError('Failed to initialize SQLite store', { cause: error });
    }
  }
  
  /**
   * Load session by ID
   */
  async load(sessionId: string): Promise<SessionState | null> {
    this.ensureInitialized();
    
    try {
      const stmt = this.preparedStatements.get('load');
      const row = stmt?.get(sessionId) as { data: string } | undefined;
      
      if (!row) return null;
      
      return this.deserialize(row.data);
      
    } catch (error) {
      this.logger?.error('Failed to load session', { sessionId, error });
      throw new StoreError(`Failed to load session ${sessionId}`, { cause: error });
    }
  }
  
  /**
   * Save session
   */
  async save(session: SessionState): Promise<void> {
    this.ensureInitialized();
    
    try {
      const stmt = this.preparedStatements.get('save');
      const data = this.serialize(session);
      
      stmt?.run(
        session.id,
        session.channelId,
        session.senderId,
        data,
        session.lastActiveAt
      );
      
    } catch (error) {
      this.logger?.error('Failed to save session', { sessionId: session.id, error });
      throw new StoreError(`Failed to save session ${session.id}`, { cause: error });
    }
  }
  
  /**
   * Delete session
   */
  async delete(sessionId: string): Promise<void> {
    this.ensureInitialized();
    
    try {
      const stmt = this.preparedStatements.get('delete');
      stmt?.run(sessionId);
      
    } catch (error) {
      this.logger?.error('Failed to delete session', { sessionId, error });
      throw new StoreError(`Failed to delete session ${sessionId}`, { cause: error });
    }
  }
  
  /**
   * List sessions with optional filter
   */
  async list(filter?: SessionFilter): Promise<SessionState[]> {
    this.ensureInitialized();
    
    try {
      let query = 'SELECT data FROM sessions WHERE 1=1';
      const params: (string | number)[] = [];
      
      if (filter?.channelId) {
        query += ' AND channel_id = ?';
        params.push(filter.channelId);
      }
      
      if (filter?.senderId) {
        query += ' AND sender_id = ?';
        params.push(filter.senderId);
      }
      
      if (filter?.olderThan) {
        query += ' AND updated_at < ?';
        params.push(filter.olderThan);
      }
      
      if (filter?.newerThan) {
        query += ' AND updated_at > ?';
        params.push(filter.newerThan);
      }
      
      query += ' ORDER BY updated_at DESC';
      
      if (filter?.limit) {
        query += ' LIMIT ?';
        params.push(filter.limit);
        
        if (filter.offset) {
          query += ' OFFSET ?';
          params.push(filter.offset);
        }
      }
      
      const stmt = this.db!.prepare(query);
      const rows = stmt.all(...params) as { data: string }[];
      
      return rows.map(row => this.deserialize(row.data));
      
    } catch (error) {
      this.logger?.error('Failed to list sessions', { filter, error });
      throw new StoreError('Failed to list sessions', { cause: error });
    }
  }
  
  /**
   * Close database connection
   */
  async close(): Promise<void> {
    if (this.db) {
      this.db.close();
      this.db = null;
      this.preparedStatements.clear();
      this.logger?.info('SQLite session store closed');
    }
  }
  
  /**
   * Clear all sessions
   */
  async clear(): Promise<void> {
    this.ensureInitialized();
    
    try {
      this.db!.exec('DELETE FROM sessions');
      this.logger?.info('All sessions cleared');
    } catch (error) {
      throw new StoreError('Failed to clear sessions', { cause: error });
    }
  }
  
  /**
   * Get session count
   */
  async count(): Promise<number> {
    this.ensureInitialized();
    
    const result = this.db!.prepare('SELECT COUNT(*) as count FROM sessions').get() as { count: number };
    return result.count;
  }
  
  /**
   * Find session by channel and sender
   */
  async findBySender(channelId: string, senderId: string): Promise<SessionState | null> {
    this.ensureInitialized();
    
    try {
      const stmt = this.preparedStatements.get('findBySender');
      const row = stmt?.get(channelId, senderId) as { data: string } | undefined;
      
      if (!row) return null;
      
      return this.deserialize(row.data);
      
    } catch (error) {
      this.logger?.error('Failed to find session by sender', { channelId, senderId, error });
      throw new StoreError('Failed to find session', { cause: error });
    }
  }
  
  // Private Methods
  
  private ensureInitialized(): void {
    if (!this.db) {
      throw new StoreError('Store not initialized. Call initialize() first.');
    }
  }
  
  private createTables(): void {
    // Migrate from legacy table name if it exists
    const legacyTable = this.db!.prepare(
      "SELECT name FROM sqlite_master WHERE type='table' AND name='sessions_v2'"
    ).get() as { name: string } | undefined;
    
    if (legacyTable) {
      this.db!.exec(`ALTER TABLE sessions_v2 RENAME TO sessions`);
      // Recreate indexes with new table name
      this.db!.exec(`
        DROP INDEX IF EXISTS idx_channel_sender;
        DROP INDEX IF EXISTS idx_updated;
        CREATE INDEX IF NOT EXISTS idx_sessions_channel_sender 
        ON sessions(channel_id, sender_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_updated 
        ON sessions(updated_at);
      `);
    }
    
    this.db!.exec(`
      CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        channel_id TEXT NOT NULL,
        sender_id TEXT NOT NULL,
        data TEXT NOT NULL,
        updated_at INTEGER NOT NULL
      );
      
      CREATE INDEX IF NOT EXISTS idx_sessions_channel_sender 
      ON sessions(channel_id, sender_id);
      
      CREATE INDEX IF NOT EXISTS idx_sessions_updated 
      ON sessions(updated_at);
    `);
  }
  
  private prepareStatements(): void {
    this.preparedStatements.set('load', this.db!.prepare(
      'SELECT data FROM sessions WHERE id = ?'
    ));
    
    this.preparedStatements.set('save', this.db!.prepare(
      `INSERT OR REPLACE INTO sessions 
       (id, channel_id, sender_id, data, updated_at)
       VALUES (?, ?, ?, ?, ?)`
    ));
    
    this.preparedStatements.set('delete', this.db!.prepare(
      'DELETE FROM sessions WHERE id = ?'
    ));
    
    this.preparedStatements.set('findBySender', this.db!.prepare(
      'SELECT data FROM sessions WHERE channel_id = ? AND sender_id = ?'
    ));
  }
  
  private serialize(session: SessionState): string {
    // Use versioned envelope for forward compatibility
    return JSON.stringify({
      _serializerVersion: 2,
      _extras: {},
      ...session,
    });
  }
  
  private deserialize(data: string): SessionState {
    const parsed = JSON.parse(data);
    // Strip envelope fields if present (v2+), pass through raw (v1)
    if (parsed._serializerVersion) {
      const { _serializerVersion, _extras, ...rest } = parsed;
      return rest as SessionState;
    }
    return parsed as SessionState;
  }
}

/**
 * Create store with default path
 */
export function createDefaultSQLiteStore(
  baseDir: string,
  logger?: ILogger
): SQLiteSessionStore {
  return new SQLiteSessionStore({
    dbPath: join(baseDir, 'sessions.db'),
    logger,
    walMode: true
  });
}
