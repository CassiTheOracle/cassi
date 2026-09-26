/**
 * Session Store Extensions for Branching Conversations
 * 
 * Extends the base SessionStore to support tree-based conversation history.
 * Provides serialization/deserialization of conversation trees.
 */

import type { Database } from 'better-sqlite3'
import type { MnemicField } from '@cassicore/mnemic-field'
import type { EngramCreate } from '@cassicore/mnemic-field'
import type { BranchingSession } from './types.js'
import type { SerializedConversationTree } from './types.js'

/**
 * Extended session row for tree-based history.
 */
export interface BranchingSessionRow {
  id: string
  channel_id: string
  sender_id: string
  /** Tree structure serialized as JSON */
  tree_json: string
  config_json: string
  token_count: number
  created_at: number
  last_active_at: number
}

/**
 * Session store with branching conversation support.
 * 
 * This extends the base SessionStore schema to store conversation trees
 * instead of linear history arrays.
 */
export class BranchingSessionStore {
  private db: Database
  private mnemicField?: MnemicField
   
  constructor(db: Database, mnemicField?: MnemicField) {
    this.db = db
    this.mnemicField = mnemicField
    this.migrate()
  }

  setMnemicField(field: MnemicField): void {
    this.mnemicField = field
  }
  
  /**
   * Run migrations for branching conversation support.
   */
  private migrate(): void {
    // Check if branching sessions table exists
    const tableExists = this.db
      .prepare(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='branching_sessions'"
      )
      .get()
    
    if (!tableExists) {
      // Create new table for branching sessions
      this.db.exec(`
        CREATE TABLE branching_sessions (
          id             TEXT PRIMARY KEY,
          channel_id     TEXT NOT NULL,
          sender_id      TEXT NOT NULL,
          tree_json      TEXT NOT NULL DEFAULT '{}',
          config_json    TEXT NOT NULL DEFAULT '{}',
          token_count    INTEGER NOT NULL DEFAULT 0,
          created_at     INTEGER NOT NULL,
          last_active_at INTEGER NOT NULL
        );
        
        CREATE INDEX idx_branching_sessions_sender
          ON branching_sessions (channel_id, sender_id);
        
        CREATE INDEX idx_branching_sessions_last_active
          ON branching_sessions (last_active_at);
      `)
    }
  }
  
  /**
   * Save a branching session.
   */
  save(session: BranchingSession): void {
    // Serialize tree structure
    const treeData: SerializedConversationTree = {
      turnTree: Object.fromEntries(session.turnTree.entries()),
      branches: Object.fromEntries(session.branches.entries()),
      rootTurnId: session.rootTurnId,
      activeBranchId: session.activeBranchId,
      schemaVersion: 1,
    }
    
    this.db
      .prepare(`
        INSERT INTO branching_sessions
          (id, channel_id, sender_id, tree_json, config_json, token_count, created_at, last_active_at)
        VALUES
          (@id, @channel_id, @sender_id, @tree_json, @config_json, @token_count, @created_at, @last_active_at)
        ON CONFLICT(id) DO UPDATE SET
          tree_json      = excluded.tree_json,
          config_json    = excluded.config_json,
          token_count    = excluded.token_count,
          last_active_at = excluded.last_active_at
      `)
      .run({
        id: session.id,
        channel_id: session.channelId,
        sender_id: session.senderId,
        tree_json: JSON.stringify(treeData),
        config_json: JSON.stringify(session.config),
        token_count: session.tokenCount,
        created_at: session.createdAt.getTime(),
        last_active_at: session.lastActiveAt.getTime(),
      })
    this.writeReplayEngrams(session, treeData)
  }
  
  /**
   * Load a branching session.
   */
  load(sessionId: string): BranchingSession | undefined {
    const row = this.db
      .prepare('SELECT * FROM branching_sessions WHERE id = ?')
      .get(sessionId) as BranchingSessionRow | undefined
    
    if (!row) {
      return undefined
    }
    
    // Deserialize tree structure
    const treeData: SerializedConversationTree = JSON.parse(row.tree_json)
    
    const session: BranchingSession = {
      id: row.id,
      channelId: row.channel_id,
      senderId: row.sender_id,
      turnTree: new Map(Object.entries(treeData.turnTree)),
      rootTurnId: treeData.rootTurnId,
      branches: new Map(Object.entries(treeData.branches)),
      activeBranchId: treeData.activeBranchId,
      config: JSON.parse(row.config_json),
      createdAt: new Date(row.created_at),
      lastActiveAt: new Date(row.last_active_at),
      tokenCount: row.token_count,
    }
    
    return session
  }
  
  /**
   * Find session by sender.
   */
  findBySender(channelId: string, senderId: string): BranchingSession | undefined {
    const row = this.db
      .prepare(`
        SELECT * FROM branching_sessions
        WHERE channel_id = ? AND sender_id = ?
        ORDER BY last_active_at DESC
        LIMIT 1
      `)
      .get(channelId, senderId) as BranchingSessionRow | undefined
    
    if (!row) {
      return undefined
    }
    
    const treeData: SerializedConversationTree = JSON.parse(row.tree_json)
    
    const session: BranchingSession = {
      id: row.id,
      channelId: row.channel_id,
      senderId: row.sender_id,
      turnTree: new Map(Object.entries(treeData.turnTree)),
      rootTurnId: treeData.rootTurnId,
      branches: new Map(Object.entries(treeData.branches)),
      activeBranchId: treeData.activeBranchId,
      config: JSON.parse(row.config_json),
      createdAt: new Date(row.created_at),
      lastActiveAt: new Date(row.last_active_at),
      tokenCount: row.token_count,
    }
    
    return session
  }
  
  /**
   * List all branching sessions.
   */
  listAll(): BranchingSession[] {
    const rows = this.db
      .prepare("SELECT * FROM branching_sessions ORDER BY last_active_at DESC")
      .all() as BranchingSessionRow[]
    
    return rows.map(row => {
      const treeData: SerializedConversationTree = JSON.parse(row.tree_json)
      
      return {
        id: row.id,
        channelId: row.channel_id,
        senderId: row.sender_id,
        turnTree: new Map(Object.entries(treeData.turnTree)),
        rootTurnId: treeData.rootTurnId,
        branches: new Map(Object.entries(treeData.branches)),
        activeBranchId: treeData.activeBranchId,
        config: JSON.parse(row.config_json),
        createdAt: new Date(row.created_at),
        lastActiveAt: new Date(row.last_active_at),
        tokenCount: row.token_count,
      }
    })
  }
  
  /**
   * Remove a session.
   */
  remove(sessionId: string): void {
    this.db
      .prepare('DELETE FROM branching_sessions WHERE id = ?')
      .run(sessionId)
    this.removeReplaySession(sessionId)
  }
  
  /**
   * Prune old sessions.
   */
  prune(maxAgeDays: number): number {
    const cutoff = Date.now() - maxAgeDays * 24 * 60 * 60 * 1000
    const staleIds = this.db
      .prepare('SELECT id FROM branching_sessions WHERE last_active_at < ?')
      .all(cutoff) as Array<{ id: string }>
    const result = this.db
      .prepare('DELETE FROM branching_sessions WHERE last_active_at < ?')
      .run(cutoff)
    for (const row of staleIds) this.removeReplaySession(row.id)
    
    return result.changes
  }

  private writeReplayEngrams(session: BranchingSession, treeData: SerializedConversationTree): void {
    if (!this.mnemicField) return
    try {
      const sessionId = `session:${session.id}`
      this.removeReplaySession(session.id)
      this.upsertReplayEngram({
        id: sessionId,
        content: JSON.stringify({
          channelId: session.channelId,
          senderId: session.senderId,
          rootTurnId: session.rootTurnId,
          activeBranchId: session.activeBranchId,
          branches: treeData.branches,
          config: session.config,
          startedAt: session.createdAt.toISOString(),
          lastActiveAt: session.lastActiveAt.toISOString(),
        }),
        nodeType: 'session',
        t: session.createdAt.getTime(),
        createdAt: session.createdAt.toISOString(),
        tags: ['session-replay', 'branching-session', session.channelId],
        provenance: 'branching-session-store',
        metadata: {
          sessionId: session.id,
          channelId: session.channelId,
          senderId: session.senderId,
          activeBranchId: session.activeBranchId,
          rootTurnId: session.rootTurnId,
          tokenCount: session.tokenCount,
          branchCount: session.branches.size,
        },
      })

      for (const [turnId, node] of session.turnTree) {
        const replayTurnId = this.replayTurnId(session.id, turnId)
        const timestamp = new Date(node.message.timestamp)
        this.upsertReplayEngram({
          id: replayTurnId,
          content: JSON.stringify({
            turnId,
            message: node.message,
            children: node.children,
            depth: node.depth,
          }),
          nodeType: 'episode',
          t: timestamp.getTime(),
          createdAt: timestamp.toISOString(),
          tags: ['session-replay', 'branching-turn', node.message.role, node.message.branchPath ?? 'unscoped'],
          provenance: 'branching-session-store',
          metadata: {
            sessionId: session.id,
            turnId,
            parentTurnId: node.message.parentTurnId,
            branchPath: node.message.branchPath,
            branchIndex: node.message.branchIndex,
            depth: node.depth,
          },
        })
        this.mnemicField.connect({ sourceId: replayTurnId, targetId: sessionId, edgeType: 'part_of' })
        if (node.message.parentTurnId) {
          this.mnemicField.connect({
            sourceId: replayTurnId,
            targetId: this.replayTurnId(session.id, node.message.parentTurnId),
            edgeType: 'spawned_from',
          })
        }
      }

      for (const branch of session.branches.values()) {
        for (let i = 1; i < branch.turnIds.length; i++) {
          this.mnemicField.connect({
            sourceId: this.replayTurnId(session.id, branch.turnIds[i - 1]),
            targetId: this.replayTurnId(session.id, branch.turnIds[i]),
            edgeType: 'temporal_neighbor',
            metadata: { branchId: branch.id },
          })
        }
      }
    } catch (err) {
      // Branch replay is a secondary index; legacy tree_json remains authoritative on failure.
      void err
    }
  }

  private removeReplaySession(sessionId: string): void {
    if (!this.mnemicField) return
    try {
      for (const turn of this.mnemicField.getEngramsByIdPrefix(`turn:${sessionId}:`, { limit: 10_000 })) {
        this.mnemicField.delete(turn.id)
      }
      this.mnemicField.delete(`session:${sessionId}`)
    } catch (err) {
      void err
    }
  }

  private replayTurnId(sessionId: string, turnId: string): string {
    return `turn:${sessionId}:${turnId}`
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
}
