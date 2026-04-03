/**
 * WorkflowDefinitionStore — SQLite persistence for workflow definitions.
 *
 * Stores workflow definition metadata (id, name, version, description, tags)
 * and the serialized node graph structure. Supports versioning, tagging,
 * and enabling/disabling definitions.
 *
 * Schema:
 *   workflow_definitions — one row per (id, version) pair
 *   workflow_def_tags    — many-to-many tag relationships
 *   def_schema_version   — migration tracking
 *
 * Uses the same database as WorkflowStore (workflows.db) to keep all
 * workflow data colocated. Separate migration tracking avoids conflicts.
 */

import Database from 'better-sqlite3'
import * as fs from 'node:fs'
import * as path from 'node:path'
import type { ILogger } from '../../types/interfaces.js'
import type {
  StoredWorkflowDefinition,
  SerializedNodeGraph,
  IWorkflowDefinitionStore,
} from '../../types/workflow.js'
import { getDataDir } from '../utils/paths.js'

const DEF_SCHEMA_VERSION = 1
const DB_FILENAME = 'workflows.db'

interface DefRow {
  id: string
  name: string
  version: string
  description: string | null
  node_graph_json: string
  enabled: number
  created_at: string
  updated_at: string
}

interface TagRow {
  def_id: string
  def_version: string
  tag: string
}

export class WorkflowDefinitionStore implements IWorkflowDefinitionStore {
  private db: InstanceType<typeof Database>
  private stmts!: ReturnType<WorkflowDefinitionStore['prepareStatements']>

  private constructor(dbPath: string, private logger: ILogger) {
    this.db = new Database(dbPath)
    this.db.pragma('journal_mode = WAL')
    this.db.pragma('synchronous = NORMAL')
    this.db.pragma('foreign_keys = ON')
    this.db.pragma('busy_timeout = 5000')
    this.migrate()
    this.stmts = this.prepareStatements()
  }

  /** Factory method — creates data directory, opens DB, runs migrations. */
  static open(logger: ILogger, dataDir?: string): WorkflowDefinitionStore {
    const dir = dataDir ?? getDataDir()
    fs.mkdirSync(dir, { recursive: true })
    const dbPath = path.join(dir, DB_FILENAME)
    return new WorkflowDefinitionStore(dbPath, logger.child('workflow-def-store'))
  }

  /** Open with an explicit DB path (useful for testing). */
  static openAt(dbPath: string, logger: ILogger): WorkflowDefinitionStore {
    return new WorkflowDefinitionStore(dbPath, logger.child('workflow-def-store'))
  }

  // Public API

  /** Save or update a workflow definition. Tags are replaced entirely on update. */
  save(def: StoredWorkflowDefinition): void {
    const txn = this.db.transaction(() => {
      this.stmts.upsertDef.run({
        id: def.id,
        name: def.name,
        version: def.version,
        description: def.description ?? null,
        node_graph_json: JSON.stringify(def.nodeGraph),
        enabled: def.enabled ? 1 : 0,
      })

      // Replace tags
      this.stmts.deleteTags.run(def.id, def.version)
      for (const tag of def.tags) {
        this.stmts.insertTag.run(def.id, def.version, tag)
      }
    })
    txn()
  }

  /** Load the latest version of a definition by id. */
  load(id: string): StoredWorkflowDefinition | undefined {
    const row = this.stmts.loadLatest.get(id) as DefRow | undefined
    if (!row) return undefined
    return this.rowToDef(row)
  }

  /** Load a specific version of a definition. */
  loadVersion(id: string, version: string): StoredWorkflowDefinition | undefined {
    const row = this.stmts.loadVersion.get(id, version) as DefRow | undefined
    if (!row) return undefined
    return this.rowToDef(row)
  }

  /** List definitions, optionally filtered. */
  list(opts?: {
    tag?: string
    enabled?: boolean
    limit?: number
  }): StoredWorkflowDefinition[] {
    const limit = opts?.limit ?? 50
    let rows: DefRow[]

    if (opts?.tag && opts?.enabled !== undefined) {
      rows = this.stmts.listByTagAndEnabled.all(opts.tag, opts.enabled ? 1 : 0, limit) as DefRow[]
    } else if (opts?.tag) {
      rows = this.stmts.listByTag.all(opts.tag, limit) as DefRow[]
    } else if (opts?.enabled !== undefined) {
      rows = this.stmts.listByEnabled.all(opts.enabled ? 1 : 0, limit) as DefRow[]
    } else {
      rows = this.stmts.listAll.all(limit) as DefRow[]
    }

    return rows.map((r) => this.rowToDef(r))
  }

  /** List all versions of a definition. */
  listVersions(id: string): StoredWorkflowDefinition[] {
    const rows = this.stmts.listVersions.all(id) as DefRow[]
    return rows.map((r) => this.rowToDef(r))
  }

  /** Delete a definition (all versions, or a specific version). */
  delete(id: string, version?: string): boolean {
    const txn = this.db.transaction(() => {
      if (version) {
        this.stmts.deleteTags.run(id, version)
        return this.stmts.deleteVersion.run(id, version).changes > 0
      } else {
        this.stmts.deleteAllTags.run(id)
        return this.stmts.deleteAll.run(id).changes > 0
      }
    })
    return txn()
  }

  /** Get aggregate stats. */
  stats(): { total: number; enabled: number; disabled: number; uniqueIds: number } {
    const row = this.stmts.stats.get() as {
      total: number
      enabled: number
      disabled: number
      unique_ids: number
    }
    return {
      total: row.total,
      enabled: row.enabled,
      disabled: row.disabled,
      uniqueIds: row.unique_ids,
    }
  }

  /** Close the database connection. */
  close(): void {
    this.db.close()
  }

  // Internal

  private rowToDef(row: DefRow): StoredWorkflowDefinition {
    let nodeGraph: SerializedNodeGraph
    try {
      nodeGraph = JSON.parse(row.node_graph_json)
    } catch {
      nodeGraph = { entryNodeId: '', nodes: [] }
    }

    // Load tags
    const tagRows = this.stmts.loadTags.all(row.id, row.version) as TagRow[]
    const tags = tagRows.map((t) => t.tag)

    return {
      id: row.id,
      name: row.name,
      version: row.version,
      description: row.description ?? undefined,
      nodeGraph,
      tags,
      enabled: row.enabled === 1,
      createdAt: row.created_at,
      updatedAt: row.updated_at,
    }
  }

  private migrate(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS def_schema_version (
        version INTEGER PRIMARY KEY
      );
    `)

    const row = this.db.prepare('SELECT version FROM def_schema_version LIMIT 1').get() as
      | { version: number }
      | undefined
    const current = row?.version ?? 0

    if (current < 1) {
      this.db.exec(`
        CREATE TABLE IF NOT EXISTS workflow_definitions (
          id                TEXT NOT NULL,
          name              TEXT NOT NULL,
          version           TEXT NOT NULL,
          description       TEXT,
          node_graph_json   TEXT NOT NULL DEFAULT '{"entryNodeId":"","nodes":[]}',
          enabled           INTEGER NOT NULL DEFAULT 1,
          created_at        TEXT NOT NULL DEFAULT (datetime('now')),
          updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
          PRIMARY KEY (id, version)
        );

        CREATE TABLE IF NOT EXISTS workflow_def_tags (
          def_id      TEXT NOT NULL,
          def_version TEXT NOT NULL,
          tag         TEXT NOT NULL,
          PRIMARY KEY (def_id, def_version, tag),
          FOREIGN KEY (def_id, def_version) REFERENCES workflow_definitions(id, version) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_workflow_defs_name
          ON workflow_definitions (name);
        CREATE INDEX IF NOT EXISTS idx_workflow_defs_enabled
          ON workflow_definitions (enabled);
        CREATE INDEX IF NOT EXISTS idx_workflow_def_tags_tag
          ON workflow_def_tags (tag);
      `)

      this.db.prepare('DELETE FROM def_schema_version').run()
      this.db.prepare('INSERT INTO def_schema_version (version) VALUES (?)').run(DEF_SCHEMA_VERSION)
      this.logger.info('Workflow definition store schema v1 created')
    }
  }

  private prepareStatements() {
    return {
      upsertDef: this.db.prepare(`
        INSERT INTO workflow_definitions (id, name, version, description, node_graph_json, enabled)
        VALUES (@id, @name, @version, @description, @node_graph_json, @enabled)
        ON CONFLICT (id, version) DO UPDATE SET
          name = @name,
          description = @description,
          node_graph_json = @node_graph_json,
          enabled = @enabled,
          updated_at = datetime('now')
      `),

      loadLatest: this.db.prepare(`
        SELECT * FROM workflow_definitions WHERE id = ? ORDER BY version DESC LIMIT 1
      `),

      loadVersion: this.db.prepare(`
        SELECT * FROM workflow_definitions WHERE id = ? AND version = ?
      `),

      listAll: this.db.prepare(`
        SELECT DISTINCT d.*
        FROM workflow_definitions d
        ORDER BY d.updated_at DESC LIMIT ?
      `),

      listByTag: this.db.prepare(`
        SELECT DISTINCT d.*
        FROM workflow_definitions d
        JOIN workflow_def_tags t ON d.id = t.def_id AND d.version = t.def_version
        WHERE t.tag = ?
        ORDER BY d.updated_at DESC LIMIT ?
      `),

      listByEnabled: this.db.prepare(`
        SELECT * FROM workflow_definitions WHERE enabled = ?
        ORDER BY updated_at DESC LIMIT ?
      `),

      listByTagAndEnabled: this.db.prepare(`
        SELECT DISTINCT d.*
        FROM workflow_definitions d
        JOIN workflow_def_tags t ON d.id = t.def_id AND d.version = t.def_version
        WHERE t.tag = ? AND d.enabled = ?
        ORDER BY d.updated_at DESC LIMIT ?
      `),

      listVersions: this.db.prepare(`
        SELECT * FROM workflow_definitions WHERE id = ? ORDER BY version DESC
      `),

      deleteTags: this.db.prepare(`
        DELETE FROM workflow_def_tags WHERE def_id = ? AND def_version = ?
      `),

      deleteAllTags: this.db.prepare(`
        DELETE FROM workflow_def_tags WHERE def_id = ?
      `),

      insertTag: this.db.prepare(`
        INSERT OR IGNORE INTO workflow_def_tags (def_id, def_version, tag) VALUES (?, ?, ?)
      `),

      loadTags: this.db.prepare(`
        SELECT * FROM workflow_def_tags WHERE def_id = ? AND def_version = ?
      `),

      deleteVersion: this.db.prepare(`
        DELETE FROM workflow_definitions WHERE id = ? AND version = ?
      `),

      deleteAll: this.db.prepare(`
        DELETE FROM workflow_definitions WHERE id = ?
      `),

      stats: this.db.prepare(`
        SELECT
          COALESCE(COUNT(*), 0) as total,
          COALESCE(SUM(CASE WHEN enabled = 1 THEN 1 ELSE 0 END), 0) as enabled,
          COALESCE(SUM(CASE WHEN enabled = 0 THEN 1 ELSE 0 END), 0) as disabled,
          COALESCE(COUNT(DISTINCT id), 0) as unique_ids
        FROM workflow_definitions
      `),
    }
  }
}
