/**
 * SessionResultStore — Persistent storage for completed agent session results
 *
 * Stores structured results from Lumen, Dyad, Helix, Flux, and subagent sessions
 * to enable discovery and retrieval throughout the session lifecycle.
 *
 * Design goals:
 * - Fast lookup by parent session, tags, or full-text search
 * - Persistent across daemon restarts (SQLite-backed)
 * - Lightweight: stores summaries and references, not full transcripts
 */

import type { ILogger } from '@cassicore/foundation'
import type { Database } from 'better-sqlite3'
import type { MnemicField } from '@cassicore/mnemic-field'
import type { EngramCreate } from '@cassicore/mnemic-field'

export interface SessionResult {
  sessionId: string
  parentSessionId: string | null
  type: 'lumen' | 'dyad' | 'helix' | 'flux' | 'subagent'
  
  // Lifecycle
  startedAt: number
  completedAt: number
  status: 'completed' | 'failed' | 'timeout' | 'cancelled'
  
  // Core results
  summary: string
  decisions: Array<{
    text: string
    confidence: number
    timestamp: number
  }>
  artifacts: Array<{
    path: string
    operation: 'created' | 'modified' | 'deleted'
    description?: string
  }>
  learnings: string[]
  
  // Metrics
  iterations: number
  tokensUsed: {
    input: number
    output: number
    total: number
  }
  
  // Relationships
  relatedSessions: string[]
  tags: string[]
}

export interface SessionResultFilters {
  types?: Array<'lumen' | 'dyad' | 'helix' | 'flux' | 'subagent'>
  status?: Array<'completed' | 'failed' | 'timeout' | 'cancelled'>
  tags?: string[]
  timeRange?: {
    start: number
    end: number
  }
  parentSessionId?: string
}

export interface SearchResult {
  result: SessionResult
  score: number
  matchedFields: string[]
}

export class SessionResultStore {
  private readonly results = new Map<string, SessionResult>()
  private readonly byParent = new Map<string, Set<string>>()
  private readonly byTag = new Map<string, Set<string>>()
  private readonly db?: Database
  private readonly logger: ILogger
  private mnemicField?: MnemicField

  constructor(logger: ILogger, db?: Database, mnemicField?: MnemicField) {
    this.logger = logger.child?.('session-result-store') ?? logger
    this.db = db
    this.mnemicField = mnemicField
    
    if (db) {
      this.initTables()
    }
  }

  setMnemicField(field: MnemicField): void {
    this.mnemicField = field
  }

  private initTables(): void {
    this.db!.exec(`
      CREATE TABLE IF NOT EXISTS session_results (
        sessionId TEXT PRIMARY KEY,
        parentSessionId TEXT,
        type TEXT NOT NULL,
        startedAt INTEGER NOT NULL,
        completedAt INTEGER NOT NULL,
        status TEXT NOT NULL,
        summary TEXT NOT NULL,
        decisions TEXT NOT NULL,
        artifacts TEXT NOT NULL,
        learnings TEXT NOT NULL,
        iterations INTEGER NOT NULL,
        tokensInput INTEGER NOT NULL,
        tokensOutput INTEGER NOT NULL,
        tokensTotal INTEGER NOT NULL,
        relatedSessions TEXT NOT NULL,
        tags TEXT NOT NULL,
        searchVector TEXT
      )
    `)
    
    // Full-text search index
    this.db!.exec(`
      CREATE VIRTUAL TABLE IF NOT EXISTS session_results_fts USING fts5(
        sessionId,
        summary,
        decisions,
        learnings,
        tags,
        content='session_results',
        content_rowid='rowid'
      )
    `)
    
    // Indexes for common queries
    this.db!.exec(`
      CREATE INDEX IF NOT EXISTS idx_parent_session ON session_results(parentSessionId);
      CREATE INDEX IF NOT EXISTS idx_status ON session_results(status);
      CREATE INDEX IF NOT EXISTS idx_type ON session_results(type);
      CREATE INDEX IF NOT EXISTS idx_completed_at ON session_results(completedAt);
    `)
  }

  /**
   * Store a session result
   */
  async store(result: SessionResult): Promise<void> {
    // In-memory storage
    this.results.set(result.sessionId, result)
    
    // Update parent index
    if (result.parentSessionId) {
      if (!this.byParent.has(result.parentSessionId)) {
        this.byParent.set(result.parentSessionId, new Set())
      }
      this.byParent.get(result.parentSessionId)!.add(result.sessionId)
    }
    
    // Update tag indexes
    for (const tag of result.tags) {
      if (!this.byTag.has(tag)) {
        this.byTag.set(tag, new Set())
      }
      this.byTag.get(tag)!.add(result.sessionId)
    }
    
    // Persist to database if available
    if (this.db) {
      this.storeToDb(result)
    }
    this.writeReplayEngram(result)
    
    this.logger.debug('Stored result for session', { 
      sessionId: result.sessionId, 
      type: result.type,
      status: result.status 
    })
  }

  private storeToDb(result: SessionResult): void {
    const stmt = this.db!.prepare(`
      INSERT OR REPLACE INTO session_results (
        sessionId, parentSessionId, type, startedAt, completedAt, status,
        summary, decisions, artifacts, learnings,
        iterations, tokensInput, tokensOutput, tokensTotal,
        relatedSessions, tags, searchVector
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `)
    
    stmt.run(
      result.sessionId,
      result.parentSessionId,
      result.type,
      result.startedAt,
      result.completedAt,
      result.status,
      result.summary,
      JSON.stringify(result.decisions),
      JSON.stringify(result.artifacts),
      JSON.stringify(result.learnings),
      result.iterations,
      result.tokensUsed.input,
      result.tokensUsed.output,
      result.tokensUsed.total,
      JSON.stringify(result.relatedSessions),
      JSON.stringify(result.tags),
      // Search vector: concatenation of searchable fields
      `${result.summary} ${result.decisions.map(d => d.text).join(' ')} ${result.learnings.join(' ')} ${result.tags.join(' ')}`
    )
  }

  private writeReplayEngram(result: SessionResult): void {
    if (!this.mnemicField) return
    try {
      const resultId = `session_result:${result.sessionId}`
      this.ensureReplaySession(result.sessionId, result.parentSessionId, result.startedAt)
      this.upsertReplayEngram({
        id: resultId,
        content: JSON.stringify({
          summary: result.summary,
          decisions: result.decisions,
          artifacts: result.artifacts,
          learnings: result.learnings,
          status: result.status,
          type: result.type,
          iterations: result.iterations,
          tokensUsed: result.tokensUsed,
        }),
        nodeType: 'outcome',
        t: result.completedAt,
        createdAt: new Date(result.completedAt).toISOString(),
        tags: ['session-replay', 'session-result', result.type, result.status, ...result.tags],
        provenance: 'session-result-store',
        metadata: {
          sessionId: result.sessionId,
          parentSessionId: result.parentSessionId,
          type: result.type,
          status: result.status,
          startedAt: result.startedAt,
          completedAt: result.completedAt,
          relatedSessions: result.relatedSessions,
        },
      })
      this.mnemicField.connect({ sourceId: resultId, targetId: `session:${result.sessionId}`, edgeType: 'part_of' })
      if (result.parentSessionId && this.mnemicField.get(`session:${result.parentSessionId}`)) {
        this.mnemicField.connect({ sourceId: `session:${result.sessionId}`, targetId: `session:${result.parentSessionId}`, edgeType: 'spawned_from' })
      }
    } catch (err) {
      this.logger.warn('SessionResultStore replay engram write failed', { sessionId: result.sessionId, error: String(err) })
    }
  }

  private ensureReplaySession(sessionId: string, parentSessionId: string | null, startedAt: number): void {
    if (!this.mnemicField || this.mnemicField.get(`session:${sessionId}`)) return
    this.upsertReplayEngram({
      id: `session:${sessionId}`,
      content: JSON.stringify({ sessionId, parentSessionId, source: 'session-result-store' }),
      nodeType: 'session',
      t: startedAt,
      createdAt: new Date(startedAt).toISOString(),
      tags: ['session-replay', 'session-result-session-stub'],
      provenance: 'session-result-store',
      metadata: { sessionId, parentSessionId, source: 'session-result-store' },
    })
  }

  private upsertReplayEngram(input: EngramCreate): void {
    if (!this.mnemicField || !input.id) return
    const existing = this.mnemicField.get(input.id)
    if (existing) {
      this.mnemicField.update(input.id, {
        content: input.content,
        nodeType: input.nodeType,
        t: input.t,
        tags: input.tags,
        metadata: input.metadata,
      })
      return
    }
    this.mnemicField.store(input)
  }

  /**
   * Get results for all child sessions of a parent
   */
  async getByParent(parentSessionId: string): Promise<SessionResult[]> {
    // Check in-memory cache first
    const childIds = this.byParent.get(parentSessionId)
    if (childIds) {
      const results = Array.from(childIds)
        .map(id => this.results.get(id))
        .filter((r): r is SessionResult => r !== undefined)
      
      if (results.length > 0) {
        return results.sort((a, b) => b.completedAt - a.completedAt)
      }
    }
    
    // Fall back to database
    if (this.db) {
      const stmt = this.db!.prepare(`
        SELECT * FROM session_results 
        WHERE parentSessionId = ? 
        ORDER BY completedAt DESC
      `)
      
      return (stmt.all(parentSessionId) as any[]).map(row => this.rowToResult(row))
    }
    
    return []
  }

  /**
   * Search for results by query and filters
   */
  async search(query: string, filters?: SessionResultFilters): Promise<SearchResult[]> {
    const results = await this.getAll(filters)
    
    if (!query) {
      return results.map(r => ({ result: r, score: 1.0, matchedFields: [] }))
    }
    
    const queryTerms = query.toLowerCase().split(/\s+/).filter(Boolean)
    const scored: SearchResult[] = []
    
    for (const result of results) {
      const { score, matchedFields } = this.scoreResult(result, queryTerms)
      if (score > 0) {
        scored.push({ result, score, matchedFields })
      }
    }
    
    return scored.sort((a, b) => b.score - a.score)
  }

  private scoreResult(result: SessionResult, terms: string[]): { score: number; matchedFields: string[] } {
    let score = 0
    const matchedFields: string[] = []
    
    const checkField = (text: string, fieldName: string, weight: number) => {
      const lower = text.toLowerCase()
      for (const term of terms) {
        if (lower.includes(term)) {
          score += weight
          if (!matchedFields.includes(fieldName)) {
            matchedFields.push(fieldName)
          }
        }
      }
    }
    
    checkField(result.summary, 'summary', 3.0)
    checkField(result.decisions.map(d => d.text).join(' '), 'decisions', 2.0)
    checkField(result.learnings.join(' '), 'learnings', 1.5)
    checkField(result.tags.join(' '), 'tags', 1.0)
    checkField(result.artifacts.map(a => a.path).join(' '), 'artifacts', 1.0)
    
    return { score, matchedFields }
  }

  /**
   * Get all results matching filters
   */
  async getAll(filters?: SessionResultFilters): Promise<SessionResult[]> {
    let results = Array.from(this.results.values())
    
    // Apply filters
    if (filters) {
      if (filters.types) {
        results = results.filter(r => filters.types!.includes(r.type))
      }
      if (filters.status) {
        results = results.filter(r => filters.status!.includes(r.status))
      }
      if (filters.tags) {
        results = results.filter(r => 
          filters.tags!.some(tag => r.tags.includes(tag))
        )
      }
      if (filters.timeRange) {
        results = results.filter(r =>
          r.completedAt >= filters.timeRange!.start &&
          r.completedAt <= filters.timeRange!.end
        )
      }
      if (filters.parentSessionId) {
        results = results.filter(r => r.parentSessionId === filters.parentSessionId)
      }
    }
    
    // Sort by completion time (most recent first)
    return results.sort((a, b) => b.completedAt - a.completedAt)
  }

  /**
   * Get a single result by session ID
   */
  async getById(sessionId: string): Promise<SessionResult | undefined> {
    return this.results.get(sessionId)
  }

  /**
   * Get timeline of results for a session (including related sessions)
   */
  async getTimeline(sessionId: string): Promise<SessionResult[]> {
    const result = await this.getById(sessionId)
    if (!result) return []
    
    const timeline = [result]
    
    // Add related sessions
    for (const relatedId of result.relatedSessions) {
      const related = await this.getById(relatedId)
      if (related) {
        timeline.push(related)
      }
    }
    
    // Add parent and siblings
    if (result.parentSessionId) {
      const siblings = await this.getByParent(result.parentSessionId)
      timeline.push(...siblings)
    }
    
    // Sort by start time
    return timeline.sort((a, b) => a.startedAt - b.startedAt)
  }

  /**
   * Get summary statistics
   */
  getStats(): SessionResultStats {
    const results = Array.from(this.results.values())
    
    return {
      total: results.length,
      byType: this.countByField(results, 'type'),
      byStatus: this.countByField(results, 'status'),
      totalTokens: results.reduce((sum, r) => sum + r.tokensUsed.total, 0),
      totalIterations: results.reduce((sum, r) => sum + r.iterations, 0),
    }
  }

  private countByField(results: SessionResult[], field: keyof SessionResult): Record<string, number> {
    const counts: Record<string, number> = {}
    for (const result of results) {
      const value = String(result[field])
      counts[value] = (counts[value] || 0) + 1
    }
    return counts
  }

  private rowToResult(row: any): SessionResult {
    return {
      sessionId: row.sessionId,
      parentSessionId: row.parentSessionId,
      type: row.type,
      startedAt: row.startedAt,
      completedAt: row.completedAt,
      status: row.status,
      summary: row.summary,
      decisions: JSON.parse(row.decisions),
      artifacts: JSON.parse(row.artifacts),
      learnings: JSON.parse(row.learnings),
      iterations: row.iterations,
      tokensUsed: {
        input: row.tokensInput,
        output: row.tokensOutput,
        total: row.tokensTotal,
      },
      relatedSessions: JSON.parse(row.relatedSessions),
      tags: JSON.parse(row.tags),
    }
  }
}

export interface SessionResultStats {
  total: number
  byType: Record<string, number>
  byStatus: Record<string, number>
  totalTokens: number
  totalIterations: number
}
