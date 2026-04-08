import { createHash, randomUUID } from 'node:crypto'
import type Database from 'better-sqlite3'
import type { ILogger } from '../../../types/interfaces.js'
import type { MnemicField } from './index.js'
import type {
  Engram, EngramCreate,
  Changeset, ChangesetCreate, ChangesetFile, ChangesetFileOperation,
  ChangesetStatus, SourceFileMetadata, SynapseCreate,
} from './types.js'

function sha256(content: string): string {
  return createHash('sha256').update(content, 'utf8').digest('hex')
}

function rowToChangeset(row: Record<string, unknown>): Changeset {
  return {
    id: row.id as string,
    description: row.description as string,
    authorSessionId: (row.author_session_id as string) || null,
    authorAgentId: (row.author_agent_id as string) || null,
    parentChangesetId: (row.parent_changeset_id as string) || null,
    status: row.status as ChangesetStatus,
    buildVerified: !!(row.build_verified as number),
    fileCount: row.file_count as number,
    createdAt: row.created_at as string,
    committedAt: (row.committed_at as string) || null,
    metadata: row.metadata ? JSON.parse(row.metadata as string) : {},
  }
}

function rowToChangesetFile(row: Record<string, unknown>): ChangesetFile {
  return {
    changesetId: row.changeset_id as string,
    engramId: row.engram_id as string,
    previousChecksum: (row.previous_checksum as string) || null,
    previousContent: (row.previous_content as string) || null,
    operation: row.operation as ChangesetFileOperation,
  }
}

export class CodeStore {
  private field: MnemicField
  private db: Database.Database
  private logger: ILogger
  private stmts: ReturnType<typeof this.prepareStatements>

  constructor(field: MnemicField, logger: ILogger) {
    this.field = field
    this.db = field.getCortex().getDatabase()
    this.logger = logger.child ? logger.child('code-store') : logger
    this.stmts = this.prepareStatements()
    this.logger.info('CodeStore initialized')
  }

  private prepareStatements() {
    return {
      getFileByPath: this.db.prepare(`
        SELECT * FROM engrams
        WHERE node_type = 'source_file'
        AND json_extract(metadata, '$.filePath') = ?
      `),
      listSourceFiles: this.db.prepare(`
        SELECT * FROM engrams
        WHERE node_type = 'source_file'
        ORDER BY json_extract(metadata, '$.filePath')
      `),
      listSourceFilePaths: this.db.prepare(`
        SELECT id, json_extract(metadata, '$.filePath') as file_path
        FROM engrams
        WHERE node_type = 'source_file'
        ORDER BY file_path
      `),
      countSourceFiles: this.db.prepare(`
        SELECT COUNT(*) as count FROM engrams WHERE node_type = 'source_file'
      `),
      insertChangeset: this.db.prepare(`
        INSERT INTO changesets (id, description, author_session_id, author_agent_id, parent_changeset_id, status, file_count, created_at, metadata)
        VALUES (@id, @description, @author_session_id, @author_agent_id, @parent_changeset_id, 'pending', 0, @created_at, @metadata)
      `),
      getChangeset: this.db.prepare(`SELECT * FROM changesets WHERE id = ?`),
      updateChangesetStatus: this.db.prepare(`
        UPDATE changesets SET status = @status, committed_at = @committed_at WHERE id = @id
      `),
      updateChangesetFileCount: this.db.prepare(`
        UPDATE changesets SET file_count = (
          SELECT COUNT(*) FROM changeset_files WHERE changeset_id = @id
        ) WHERE id = @id
      `),
      markChangesetVerified: this.db.prepare(`
        UPDATE changesets SET status = 'verified', build_verified = 1 WHERE id = ?
      `),
      insertChangesetFile: this.db.prepare(`
        INSERT OR REPLACE INTO changeset_files (changeset_id, engram_id, previous_checksum, previous_content, operation)
        VALUES (@changeset_id, @engram_id, @previous_checksum, @previous_content, @operation)
      `),
      getChangesetFiles: this.db.prepare(`
        SELECT * FROM changeset_files WHERE changeset_id = ?
      `),
      latestCommittedAt: this.db.prepare(`
        SELECT MAX(committed_at) as latest FROM changesets WHERE status IN ('committed', 'verified')
      `),
      listChangesets: this.db.prepare(`
        SELECT * FROM changesets ORDER BY created_at DESC LIMIT ?
      `),
      lastVerifiedChangeset: this.db.prepare(`
        SELECT * FROM changesets WHERE status = 'verified' ORDER BY committed_at DESC LIMIT 1
      `),
    }
  }

  getFileByPath(filePath: string): Engram | null {
    const row = this.stmts.getFileByPath.get(filePath) as Record<string, unknown> | undefined
    if (!row) return null
    return this.field.get(row.id as string)
  }

  listSourceFiles(): Engram[] {
    const rows = this.stmts.listSourceFiles.all() as Record<string, unknown>[]
    return rows.map(row => this.field.get(row.id as string)!).filter(Boolean)
  }

  listSourceFilePaths(): Array<{ id: string; filePath: string }> {
    const rows = this.stmts.listSourceFilePaths.all() as Array<{ id: string; file_path: string }>
    return rows.map(r => ({ id: r.id, filePath: r.file_path }))
  }

  sourceFileCount(): number {
    const row = this.stmts.countSourceFiles.get() as { count: number }
    return row.count
  }

  /**
   * Store a source file as an engram. If it already exists (by path), updates it.
   * Returns the engram and whether it was created (true) or updated (false).
   */
  storeFile(
    filePath: string,
    content: string,
    options?: {
      language?: string
      buildable?: boolean
      embedding?: Float32Array | number[] | null
      changesetId?: string
    },
  ): { engram: Engram; created: boolean } {
    const checksum = sha256(content)
    const existing = this.getFileByPath(filePath)

    const metadata: SourceFileMetadata = {
      filePath,
      language: options?.language ?? this.inferLanguage(filePath),
      checksum,
      sizeBytes: Buffer.byteLength(content, 'utf8'),
      changesetId: options?.changesetId ?? null,
      buildable: options?.buildable ?? this.isBuildable(filePath),
    }

    if (existing) {
      const updated = this.field.update(existing.id, {
        content,
        metadata: metadata as unknown as Record<string, unknown>,
        accessedAt: new Date().toISOString(),
        ...(options?.embedding ? { embedding: options.embedding } : {}),
      })
      return { engram: updated ?? existing, created: false }
    }

    const pathSegments = filePath.split('/').filter(Boolean)
    const engram = this.field.store({
      content,
      nodeType: 'source_file',
      tags: ['source', metadata.language, ...pathSegments.slice(0, -1)],
      provenance: 'codebase',
      metadata: metadata as unknown as Record<string, unknown>,
      embedding: options?.embedding ?? undefined,
    })

    return { engram, created: true }
  }

  /**
   * Remove a source file engram by path.
   */
  removeFile(filePath: string): boolean {
    const existing = this.getFileByPath(filePath)
    if (!existing) return false
    return this.field.delete(existing.id)
  }

  createChangeset(input: ChangesetCreate): Changeset {
    const id = input.id ?? randomUUID()
    const now = new Date().toISOString()

    this.stmts.insertChangeset.run({
      id,
      description: input.description,
      author_session_id: input.authorSessionId ?? null,
      author_agent_id: input.authorAgentId ?? null,
      parent_changeset_id: input.parentChangesetId ?? null,
      created_at: now,
      metadata: JSON.stringify(input.metadata ?? {}),
    })

    return this.getChangeset(id)!
  }

  getChangeset(id: string): Changeset | null {
    const row = this.stmts.getChangeset.get(id) as Record<string, unknown> | undefined
    return row ? rowToChangeset(row) : null
  }

  listChangesets(limit = 20): Changeset[] {
    const rows = this.stmts.listChangesets.all(limit) as Record<string, unknown>[]
    return rows.map(rowToChangeset)
  }

  /**
   * Record a file change within a changeset. Snapshots the previous state for rollback.
   */
  recordFileChange(
    changesetId: string,
    engramId: string,
    operation: ChangesetFileOperation,
    previousContent?: string | null,
    previousChecksum?: string | null,
  ): void {
    this.stmts.insertChangesetFile.run({
      changeset_id: changesetId,
      engram_id: engramId,
      previous_checksum: previousChecksum ?? null,
      previous_content: previousContent ?? null,
      operation,
    })
    this.stmts.updateChangesetFileCount.run({ id: changesetId })
  }

  getChangesetFiles(changesetId: string): ChangesetFile[] {
    const rows = this.stmts.getChangesetFiles.all(changesetId) as Record<string, unknown>[]
    return rows.map(rowToChangesetFile)
  }

  /**
   * Commit a changeset: mark it as committed with a timestamp.
   */
  commitChangeset(id: string): Changeset | null {
    this.stmts.updateChangesetStatus.run({
      id,
      status: 'committed',
      committed_at: new Date().toISOString(),
    })
    return this.getChangeset(id)
  }

  /**
   * Mark a changeset as verified (build succeeded).
   */
  verifyChangeset(id: string): Changeset | null {
    this.stmts.markChangesetVerified.run(id)
    return this.getChangeset(id)
  }

  /**
   * Mark a changeset as failed.
   */
  failChangeset(id: string): Changeset | null {
    this.stmts.updateChangesetStatus.run({
      id,
      status: 'failed',
      committed_at: null,
    })
    return this.getChangeset(id)
  }

  /**
   * Rollback a changeset: restore all files to their previous content.
   * Returns the number of files restored.
   */
  rollbackChangeset(changesetId: string): number {
    const files = this.getChangesetFiles(changesetId)
    let restored = 0

    const tx = this.db.transaction(() => {
      for (const cf of files) {
        if (cf.operation === 'create') {
          this.field.delete(cf.engramId)
          restored++
        } else if (cf.operation === 'modify' && cf.previousContent !== null) {
          const engram = this.field.get(cf.engramId)
          if (engram) {
            const metadata = engram.metadata as Record<string, unknown>
            this.field.update(cf.engramId, {
              content: cf.previousContent,
              metadata: {
                ...metadata,
                checksum: cf.previousChecksum ?? sha256(cf.previousContent),
                sizeBytes: Buffer.byteLength(cf.previousContent, 'utf8'),
              },
            })
            restored++
          }
        } else if (cf.operation === 'delete' && cf.previousContent !== null) {
          const engram = this.field.get(cf.engramId)
          if (!engram) {
            this.field.store({
              id: cf.engramId,
              content: cf.previousContent,
              nodeType: 'source_file',
              provenance: 'codebase',
              metadata: { checksum: cf.previousChecksum },
            })
            restored++
          }
        }
      }

      this.stmts.updateChangesetStatus.run({
        id: changesetId,
        status: 'failed',
        committed_at: null,
      })
    })

    tx()
    this.logger.info('Rolled back changeset', { changesetId, restored })
    return restored
  }

  /**
   * Write a file within a changeset context. Creates the engram if new,
   * updates if existing, and records the change in the changeset.
   */
  writeFileInChangeset(
    changesetId: string,
    filePath: string,
    content: string,
    options?: {
      language?: string
      buildable?: boolean
      embedding?: Float32Array | number[] | null
    },
  ): { engram: Engram; operation: ChangesetFileOperation } {
    const existing = this.getFileByPath(filePath)
    const operation: ChangesetFileOperation = existing ? 'modify' : 'create'

    const previousContent = existing?.content ?? null
    const previousChecksum = existing
      ? (existing.metadata as unknown as SourceFileMetadata).checksum ?? null
      : null

    const { engram } = this.storeFile(filePath, content, {
      ...options,
      changesetId,
    })

    this.recordFileChange(changesetId, engram.id, operation, previousContent, previousChecksum)

    return { engram, operation }
  }

  /**
   * Delete a file within a changeset context.
   */
  deleteFileInChangeset(changesetId: string, filePath: string): boolean {
    const existing = this.getFileByPath(filePath)
    if (!existing) return false

    this.recordFileChange(
      changesetId, existing.id, 'delete',
      existing.content,
      (existing.metadata as unknown as SourceFileMetadata).checksum ?? null,
    )

    return this.field.delete(existing.id)
  }

  /**
   * Get the latest committed_at timestamp across all committed/verified changesets.
   * Used by the supervisor to determine if extraction is needed.
   */
  latestCommittedAt(): string | null {
    const row = this.stmts.latestCommittedAt.get() as { latest: string | null }
    return row.latest
  }

  /**
   * Get the most recently verified changeset (last known good build).
   */
  lastVerifiedChangeset(): Changeset | null {
    const row = this.stmts.lastVerifiedChangeset.get() as Record<string, unknown> | undefined
    return row ? rowToChangeset(row) : null
  }

  /**
   * Create import synapses between source file engrams based on import statements.
   */
  connectImports(sourceEngramId: string, targetEngramId: string, importCount = 1): void {
    const weight = Math.min(1.0, 0.3 + importCount * 0.1)
    this.field.connect({
      sourceId: sourceEngramId,
      targetId: targetEngramId,
      edgeType: 'imports',
      weight,
    })
  }

  /**
   * Create co-change synapses between files that are frequently modified together.
   */
  connectCoChanged(engramIdA: string, engramIdB: string, coChangeCount: number): void {
    const weight = Math.min(1.0, 0.2 + coChangeCount * 0.05)
    this.field.connect({
      sourceId: engramIdA,
      targetId: engramIdB,
      edgeType: 'co_changed',
      weight,
    })
  }

  private inferLanguage(filePath: string): string {
    if (filePath.endsWith('.ts') || filePath.endsWith('.tsx')) return 'typescript'
    if (filePath.endsWith('.js') || filePath.endsWith('.jsx')) return 'javascript'
    if (filePath.endsWith('.json')) return 'json'
    if (filePath.endsWith('.yaml') || filePath.endsWith('.yml')) return 'yaml'
    if (filePath.endsWith('.md')) return 'markdown'
    if (filePath.endsWith('.css') || filePath.endsWith('.scss')) return 'css'
    if (filePath.endsWith('.html')) return 'html'
    if (filePath.endsWith('.sh') || filePath.endsWith('.bash')) return 'shell'
    if (filePath.endsWith('.go')) return 'go'
    return 'unknown'
  }

  private isBuildable(filePath: string): boolean {
    return filePath.endsWith('.ts') || filePath.endsWith('.tsx')
  }
}
