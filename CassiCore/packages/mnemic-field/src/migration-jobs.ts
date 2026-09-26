import { randomUUID } from 'node:crypto'
import Database from 'better-sqlite3'
import type { ChunkedMigrationPhase } from './migrate-memory.js'

export type MigrationJobStatus = 'pending' | 'running' | 'completed' | 'failed' | 'paused'

export interface MigrationJobSpec {
  sourceDbPath: string
  migrateArchives: boolean
  includeArchived: boolean
  inferSynapses: boolean
  enableMicroChunking: boolean
  useLocalEmbeddings: boolean
  memoryLimit?: number
  archiveLimit?: number
  archiveLinkLimit?: number
  microChunkTokenTarget?: number
}

export interface MigrationJobRecord extends MigrationJobSpec {
  id: string
  status: MigrationJobStatus
  phase: ChunkedMigrationPhase
  migratedMemories: number
  migratedArchives: number
  createdSynapses: number
  createdFragments: number
  nextMemoryOffset: number
  nextArchiveOffset: number
  nextLinkOffset: number
  errorText: string | null
  createdAt: string
  updatedAt: string
  completedAt: string | null
}

function rowToJob(row: Record<string, unknown>): MigrationJobRecord {
  return {
    id: row.id as string,
    status: row.status as MigrationJobStatus,
    phase: (row.phase as ChunkedMigrationPhase) ?? 'memories',
    sourceDbPath: row.source_db_path as string,
    migrateArchives: !!row.migrate_archives,
    includeArchived: !!row.include_archived,
    inferSynapses: !!row.infer_synapses,
    enableMicroChunking: !!row.enable_micro_chunking,
    useLocalEmbeddings: !!row.use_local_embeddings,
    memoryLimit: row.memory_limit as number | null ?? undefined,
    archiveLimit: row.archive_limit as number | null ?? undefined,
    archiveLinkLimit: row.archive_link_limit as number | null ?? undefined,
    microChunkTokenTarget: row.micro_chunk_token_target as number | null ?? undefined,
    migratedMemories: row.migrated_memories as number,
    migratedArchives: row.migrated_archives as number,
    createdSynapses: row.created_synapses as number,
    createdFragments: row.created_fragments as number,
    nextMemoryOffset: row.next_memory_offset as number,
    nextArchiveOffset: row.next_archive_offset as number,
    nextLinkOffset: row.next_link_offset as number,
    errorText: row.error_text as string | null,
    createdAt: row.created_at as string,
    updatedAt: row.updated_at as string,
    completedAt: row.completed_at as string | null,
  }
}

export class MigrationJobStore {
  constructor(private db: Database.Database) {}

  create(spec: MigrationJobSpec): MigrationJobRecord {
    const now = new Date().toISOString()
    const id = randomUUID()
    this.db.prepare(`
      INSERT INTO migration_jobs (
        id, status, phase, source_db_path, migrate_archives, include_archived,
        infer_synapses, enable_micro_chunking, use_local_embeddings,
        memory_limit, archive_limit, archive_link_limit, micro_chunk_token_target,
        migrated_memories, migrated_archives, created_synapses, created_fragments,
        next_memory_offset, next_archive_offset, next_link_offset,
        error_text, created_at, updated_at, completed_at
      ) VALUES (
        @id, 'pending', 'memories', @source_db_path, @migrate_archives, @include_archived,
        @infer_synapses, @enable_micro_chunking, @use_local_embeddings,
        @memory_limit, @archive_limit, @archive_link_limit, @micro_chunk_token_target,
        0, 0, 0, 0,
        0, 0, 0,
        NULL, @created_at, @updated_at, NULL
      )
    `).run({
      id,
      source_db_path: spec.sourceDbPath,
      migrate_archives: spec.migrateArchives ? 1 : 0,
      include_archived: spec.includeArchived ? 1 : 0,
      infer_synapses: spec.inferSynapses ? 1 : 0,
      enable_micro_chunking: spec.enableMicroChunking ? 1 : 0,
      use_local_embeddings: spec.useLocalEmbeddings ? 1 : 0,
      memory_limit: spec.memoryLimit ?? null,
      archive_limit: spec.archiveLimit ?? null,
      archive_link_limit: spec.archiveLinkLimit ?? null,
      micro_chunk_token_target: spec.microChunkTokenTarget ?? null,
      created_at: now,
      updated_at: now,
    })
    return this.get(id)!
  }

  get(id: string): MigrationJobRecord | null {
    const row = this.db.prepare(`SELECT * FROM migration_jobs WHERE id = ?`).get(id) as Record<string, unknown> | undefined
    return row ? rowToJob(row) : null
  }

  list(limit = 20): MigrationJobRecord[] {
    const rows = this.db.prepare(`SELECT * FROM migration_jobs ORDER BY created_at DESC LIMIT ?`).all(limit) as Record<string, unknown>[]
    return rows.map(rowToJob)
  }

  updateProgress(id: string, patch: Partial<MigrationJobRecord>): MigrationJobRecord | null {
    const current = this.get(id)
    if (!current) return null
    const next = { ...current, ...patch, updatedAt: new Date().toISOString() }
    this.db.prepare(`
      UPDATE migration_jobs SET
        status = @status,
        phase = @phase,
        migrated_memories = @migrated_memories,
        migrated_archives = @migrated_archives,
        created_synapses = @created_synapses,
        created_fragments = @created_fragments,
        next_memory_offset = @next_memory_offset,
        next_archive_offset = @next_archive_offset,
        next_link_offset = @next_link_offset,
        error_text = @error_text,
        updated_at = @updated_at,
        completed_at = @completed_at
      WHERE id = @id
    `).run({
      id,
      status: next.status,
      phase: next.phase,
      migrated_memories: next.migratedMemories,
      migrated_archives: next.migratedArchives,
      created_synapses: next.createdSynapses,
      created_fragments: next.createdFragments,
      next_memory_offset: next.nextMemoryOffset,
      next_archive_offset: next.nextArchiveOffset,
      next_link_offset: next.nextLinkOffset,
      error_text: next.errorText,
      updated_at: next.updatedAt,
      completed_at: next.completedAt,
    })
    return this.get(id)
  }
}
