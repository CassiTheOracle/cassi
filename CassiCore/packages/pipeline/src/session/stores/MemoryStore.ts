/**
 * In-Memory Session Store
 * 
 * For testing and development - sessions are lost on restart
 */

import type {
  SessionState,
  SessionFilter,
  ISessionStore,
  StoreError,
  ILogger
} from '../types.js';

export interface MemoryStoreOptions {
  logger?: ILogger;
  maxSize?: number;  // Max number of sessions to keep
}

/**
 * In-memory implementation of ISessionStore
 */
export class MemorySessionStore implements ISessionStore {
  private sessions = new Map<string, SessionState>();
  private maxSize: number;
  private logger?: ILogger;
  
  constructor(options: MemoryStoreOptions = {}) {
    this.maxSize = options.maxSize ?? 1000;
    this.logger = options.logger;
  }
  
  /**
   * Load session by ID
   */
  async load(sessionId: string): Promise<SessionState | null> {
    return this.sessions.get(sessionId) ?? null;
  }
  
  /**
   * Save session
   */
  async save(session: SessionState): Promise<void> {
    // Enforce max size (LRU eviction)
    if (this.sessions.size >= this.maxSize && !this.sessions.has(session.id)) {
      this.evictLRU();
    }
    
    this.sessions.set(session.id, { ...session });
  }
  
  /**
   * Delete session
   */
  async delete(sessionId: string): Promise<void> {
    this.sessions.delete(sessionId);
  }
  
  /**
   * List sessions with optional filter
   */
  async list(filter?: SessionFilter): Promise<SessionState[]> {
    let results = Array.from(this.sessions.values());
    
    // Apply filters
    if (filter?.channelId) {
      results = results.filter(s => s.channelId === filter.channelId);
    }
    
    if (filter?.senderId) {
      results = results.filter(s => s.senderId === filter.senderId);
    }
    
    if (filter?.olderThan) {
      results = results.filter(s => s.lastActiveAt < filter.olderThan!);
    }
    
    if (filter?.newerThan) {
      results = results.filter(s => s.lastActiveAt > filter.newerThan!);
    }
    
    // Sort by lastActiveAt desc
    results.sort((a, b) => b.lastActiveAt - a.lastActiveAt);
    
    // Apply limit/offset
    if (filter?.offset) {
      results = results.slice(filter.offset);
    }
    
    if (filter?.limit) {
      results = results.slice(0, filter.limit);
    }
    
    return results;
  }
  
  /**
   * Clear all sessions
   */
  async clear(): Promise<void> {
    this.sessions.clear();
    this.logger?.info('All sessions cleared from memory');
  }
  
  /**
   * Get session count
   */
  async count(): Promise<number> {
    return this.sessions.size;
  }
  
  /**
   * Check if session exists
   */
  has(sessionId: string): boolean {
    return this.sessions.has(sessionId);
  }
  
  /**
   * Get all session IDs
   */
  keys(): string[] {
    return Array.from(this.sessions.keys());
  }
  
  /**
   * Evict least recently used session
   */
  private evictLRU(): void {
    let oldest: SessionState | null = null;
    let oldestId: string | null = null;
    
    for (const [id, session] of this.sessions) {
      if (!oldest || session.lastActiveAt < oldest.lastActiveAt) {
        oldest = session;
        oldestId = id;
      }
    }
    
    if (oldestId) {
      this.sessions.delete(oldestId);
      this.logger?.debug('Evicted LRU session', { sessionId: oldestId });
    }
  }
}

/**
 * Create memory store for testing
 */
export function createTestStore(logger?: ILogger): MemorySessionStore {
  return new MemorySessionStore({ logger, maxSize: 100 });
}
