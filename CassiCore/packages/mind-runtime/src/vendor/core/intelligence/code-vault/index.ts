/**
 * Code Vault — Topology-aware code storage for non-CassiCore projects.
 *
 * Each vault instance manages code for external projects that agents work on.
 * Uses its own MnemicField database (code-vault.db) so external code is
 * isolated from CassiCore's memory space while getting the same topology
 * features: kindling, potentiation, co-change clustering, consolidation.
 *
 * Database: ~/.cassicore/data/code-vault.db
 */

import fs from 'node:fs'
import path from 'node:path'
import type { ILogger } from '@cassicore/foundation'
import { MnemicField, CodeStore, CodeIngestor } from '@cassicore/mnemic-field'
import type { Engram, Changeset, ChangesetCreate, LuminalSet, KindlingOptions } from '@cassicore/mnemic-field'
import type { IngestOptions, IngestResult } from '@cassicore/mnemic-field'
import { getDataDir } from '@cassicore/foundation'

export class CodeVault {
  private field: MnemicField
  private store: CodeStore
  private logger: ILogger

  constructor(logger: ILogger, dbPath?: string) {
    this.logger = logger.child ? logger.child('code-vault') : logger
    const resolvedPath = dbPath ?? path.join(getDataDir(), 'code-vault.db')
    const dir = path.dirname(resolvedPath)
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })

    this.field = new MnemicField(logger, resolvedPath)
    this.store = new CodeStore(this.field, logger)
    this.logger.info('CodeVault initialized', { dbPath: resolvedPath })
  }

  /** Get the underlying CodeStore for direct operations. */
  getStore(): CodeStore { return this.store }

  /** Get the underlying MnemicField for topology operations. */
  getField(): MnemicField { return this.field }

  /** Store or update a source file. */
  writeFile(
    filePath: string,
    content: string,
    options?: { language?: string; buildable?: boolean; embedding?: Float32Array | number[] | null },
  ): { engram: Engram; created: boolean } {
    return this.store.storeFile(filePath, content, options)
  }

  /** Read a source file by path. */
  readFile(filePath: string): Engram | null {
    return this.store.getFileByPath(filePath)
  }

  /** List all source file paths. */
  listFiles(): Array<{ id: string; filePath: string }> {
    return this.store.listSourceFilePaths()
  }

  /** Remove a source file. */
  removeFile(filePath: string): boolean {
    return this.store.removeFile(filePath)
  }

  /** Create a changeset for atomic multi-file changes. */
  createChangeset(input: ChangesetCreate): Changeset {
    return this.store.createChangeset(input)
  }

  /** Write a file within an active changeset. */
  writeFileInChangeset(
    changesetId: string,
    filePath: string,
    content: string,
  ): { engram: Engram; operation: 'create' | 'modify' | 'delete' } {
    return this.store.writeFileInChangeset(changesetId, filePath, content)
  }

  /** Commit a changeset. */
  commitChangeset(id: string): Changeset | null {
    return this.store.commitChangeset(id)
  }

  /** Rollback a changeset. */
  rollbackChangeset(id: string): number {
    return this.store.rollbackChangeset(id)
  }

  /** Ingest a project's source tree into the vault. */
  async ingest(options: IngestOptions): Promise<IngestResult> {
    const ingestor = new CodeIngestor(this.store, this.logger)
    return ingestor.ingest(options)
  }

  /** Kindle: find code files related to a query via topology-aware activation. */
  kindle(embedding: number[] | null, textQuery: string | null, options?: KindlingOptions): LuminalSet {
    return this.field.kindle(embedding, textQuery, options)
  }

  /** Run consolidation (potentiation recomputation, clustering). */
  async consolidate() {
    return this.field.consolidate()
  }

  /** Stats: source file count + field stats. */
  stats() {
    return {
      sourceFileCount: this.store.sourceFileCount(),
      fieldStats: this.field.stats(),
    }
  }

  close(): void {
    this.field.close()
    this.logger.info('CodeVault closed')
  }
}
