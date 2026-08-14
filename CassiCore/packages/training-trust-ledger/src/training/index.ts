/**
 * Training Warehouse — Module index.
 *
 * Orchestrates the training warehouse lifecycle:
 * - Initialize store (training.db)
 * - Run ingest from operational DBs
 * - Run LLM tagging
 * - Query / search / export
 *
 * This is the single entry point for the rest of the daemon.
 */

import * as path from 'node:path'
import * as fs from 'node:fs'
import type { ILogger } from '@cassicore/foundation'
import { TrainingStore } from './training-store.js'
import { TrainingIngest, type IngestOptions, type IngestResult } from './training-ingest.js'
import { TrainingTagger, type TaggerLLM, type TaggerOptions, type TaggerBatchResult } from './training-tagger.js'
import { TrainingReader, type SearchFilters, type ExportFilters, type ChunkSearchResult, type ObjectSearchResult } from './training-reader.js'
import type { TrainingWarehouseStats, TrainingExample } from './training-types.js'

// WAREHOUSE CLASS

export interface TrainingWarehouseConfig {
  /** Directory for training.db. Defaults to `<dataDir>/training`. */
  dataDir: string
  /** Paths to operational databases for ingest. */
  sources?: {
    memoryDbPath?: string
    lumenDbPath?: string
    dyadDbPath?: string
    constellationDbPath?: string
  }
}

export class TrainingWarehouse {
  readonly store: TrainingStore
  readonly ingest: TrainingIngest
  readonly tagger: TrainingTagger
  readonly reader: TrainingReader
  private readonly logger: ILogger
  private readonly config: TrainingWarehouseConfig

  constructor(config: TrainingWarehouseConfig, logger: ILogger) {
    this.config = config
    this.logger = logger.child('training-warehouse')

    this.store = new TrainingStore(config.dataDir, logger)
    this.ingest = new TrainingIngest(this.store, logger)
    this.tagger = new TrainingTagger(this.store, logger)
    this.reader = new TrainingReader(this.store, logger)

    this.logger.info('Training warehouse ready', { dataDir: config.dataDir })
  }

  // INGEST

  /**
   * Run a full ingest pass across all configured source databases.
   * Idempotent: uses checkpoints to only process new data.
   */
  runIngest(opts: IngestOptions = {}): IngestResult[] {
    if (!this.config.sources) {
      this.logger.warn('No source databases configured for ingest')
      return []
    }
    return this.ingest.ingestAll(this.config.sources, opts)
  }

  /**
   * Auto-detect source database paths from a standard CassiCore data directory.
   */
  static detectSources(dataDir: string): TrainingWarehouseConfig['sources'] {
    const sources: TrainingWarehouseConfig['sources'] = {}

    const memoryPath = path.join(dataDir, 'memory.db')
    if (fs.existsSync(memoryPath)) sources.memoryDbPath = memoryPath

    const lumenPath = path.join(dataDir, 'lumen.db')
    if (fs.existsSync(lumenPath)) sources.lumenDbPath = lumenPath

    const dyadPath = path.join(dataDir, 'dyad.db')
    if (fs.existsSync(dyadPath)) sources.dyadDbPath = dyadPath

    const constellationPath = path.join(dataDir, 'constellation.db')
    if (fs.existsSync(constellationPath)) sources.constellationDbPath = constellationPath

    return sources
  }

  // TAGGING

  /**
   * Run LLM tagging on untagged objects.
   * Requires a TaggerLLM implementation to be provided.
   */
  async runTagging(
    llm: TaggerLLM,
    scope: 'chunk' | 'message' | 'turn' | 'session' = 'message',
    opts: TaggerOptions = {},
  ): Promise<TaggerBatchResult> {
    return this.tagger.tagBatch(llm, scope, opts)
  }

  // SEARCH

  /** Full-text search over chunks. */
  searchChunks(query: string, filters?: SearchFilters): ChunkSearchResult[] {
    return this.reader.searchChunks(query, filters)
  }

  /** Filtered search over objects with labels and quality. */
  searchObjects(filters?: SearchFilters): ObjectSearchResult[] {
    return this.reader.searchObjects(filters)
  }

  /** Resolve a ref key or object ID to full detail. */
  resolve(refKeyOrId: string) {
    return this.reader.resolve(refKeyOrId)
  }

  // EXPORT

  /** Assemble training examples for JSONL export. */
  assembleExamples(filters?: ExportFilters): TrainingExample[] {
    return this.reader.assembleExamples(filters)
  }

  /** Export examples as JSONL string. */
  exportJsonl(filters?: ExportFilters): string {
    const examples = this.assembleExamples(filters)
    return examples.map(e => JSON.stringify(e)).join('\n')
  }

  /** Export examples to a file. */
  exportToFile(filePath: string, filters?: ExportFilters): number {
    const jsonl = this.exportJsonl(filters)
    fs.writeFileSync(filePath, jsonl, 'utf-8')
    const count = jsonl.split('\n').filter(l => l.trim()).length
    this.logger.info('Exported training examples', { path: filePath, count })
    return count
  }

  // ANALYTICS

  /** Get warehouse stats. */
  getStats(): TrainingWarehouseStats {
    return this.reader.getStats()
  }

  /** Get label distribution. */
  getLabelDistribution(namespace?: string) {
    return this.reader.getLabelDistribution(namespace)
  }

  /** Get quality distribution for a metric. */
  getQualityDistribution(metric: string) {
    return this.reader.getQualityDistribution(metric)
  }

  /** Get annotation run summary. */
  getAnnotationSummary() {
    return this.reader.getAnnotationSummary()
  }

  // LIFECYCLE

  /** Close the warehouse database. */
  close(): void {
    this.store.close()
  }
}

// Re-exports for convenience
export { TrainingStore } from './training-store.js'
export { TrainingIngest } from './training-ingest.js'
export { TrainingTagger } from './training-tagger.js'
export { TrainingReader } from './training-reader.js'
export type { TaggerLLM, TaggerOptions, TaggerBatchResult } from './training-tagger.js'
export type { IngestOptions, IngestResult } from './training-ingest.js'
export type { SearchFilters, ExportFilters, ChunkSearchResult, ObjectSearchResult } from './training-reader.js'
export { SdkTagger } from './sdk-tagger.js'
export type { SdkTaggerOptions, SdkTaggerResult } from './sdk-tagger.js'
export { BackgroundTaggerWorker } from './background-tagger-worker.js'
export * from './training-types.js'
