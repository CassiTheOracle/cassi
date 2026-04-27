import fs from 'node:fs'
import path from 'node:path'
import type { ILogger } from '../../../../types/interfaces.js'
import type { KnowledgeField } from './knowledge-field.js'
import type {
  KnowledgeIngestResult,
  KnowledgeIngestOptions,
  PaperMetadata,
  TechniqueMetadata,
} from './types.js'

interface PaperJson {
  title: string
  abstract: string
  authors?: string[]
  year?: number
  venue?: string
  doi?: string
  url?: string
  citationCount?: number
  techniques?: TechniqueJson[]
}

interface TechniqueJson {
  name: string
  description: string
  domain?: string
  hyperparameters?: Record<string, unknown>
  failureModes?: string[]
  implementationNotes?: string
  benchmarks?: Array<{
    dataset: string
    score: number
    baseline?: number
    metric: string
  }>
}

/**
 * KnowledgeIngestor — batch ingestion for research papers and techniques.
 *
 * Reads JSON files from a directory, creates paper/technique engrams,
 * and links them via synapses (paper introduces technique, etc.).
 */
export class KnowledgeIngestor {
  private field: KnowledgeField
  private logger: ILogger

  constructor(field: KnowledgeField, logger: ILogger) {
    this.field = field
    this.logger = logger.child ? logger.child('knowledge-ingestor') : logger
  }

  /**
   * Ingest all .json files from a directory.
   */
  async ingestFromDirectory(
    dir: string,
    options?: KnowledgeIngestOptions,
  ): Promise<KnowledgeIngestResult> {
    const start = Date.now()
    const files = this.collectJsonFiles(dir)
    this.logger.info('Starting knowledge ingestion', { dir, files: files.length })

    let papersCreated = 0
    let techniquesCreated = 0
    let findingsCreated = 0
    let algorithmsCreated = 0
    let benchmarksCreated = 0
    let synapsesCreated = 0

    for (const file of files) {
      try {
        const raw = fs.readFileSync(file, 'utf8')
        const data = JSON.parse(raw) as PaperJson | PaperJson[]
        const papers = Array.isArray(data) ? data : [data]

        for (const paper of papers) {
          const result = await this.ingestPaper(paper, options)
          papersCreated += result.papersCreated
          techniquesCreated += result.techniquesCreated
          findingsCreated += result.findingsCreated
          algorithmsCreated += result.algorithmsCreated
          benchmarksCreated += result.benchmarksCreated
          synapsesCreated += result.synapsesCreated
        }
      } catch (err) {
        this.logger.warn('Failed to ingest file', { file, error: String(err) })
      }
    }

    const durationMs = Date.now() - start
    this.logger.info('Knowledge ingestion complete', {
      papersCreated, techniquesCreated, findingsCreated,
      algorithmsCreated, benchmarksCreated, synapsesCreated, durationMs,
    })

    return {
      papersCreated, techniquesCreated, findingsCreated,
      algorithmsCreated, benchmarksCreated, synapsesCreated, durationMs,
    }
  }

  private async ingestPaper(
    paper: PaperJson,
    options?: KnowledgeIngestOptions,
  ): Promise<KnowledgeIngestResult> {
    let papersCreated = 0
    let techniquesCreated = 0
    let findingsCreated = 0
    let algorithmsCreated = 0
    let benchmarksCreated = 0
    let synapsesCreated = 0

    // Skip by year
    if (options?.minYear && (paper.year ?? 0) < options.minYear) {
      return { papersCreated, techniquesCreated, findingsCreated, algorithmsCreated, benchmarksCreated, synapsesCreated, durationMs: 0 }
    }

    // Check existing
    if (options?.skipExisting !== false) {
      const existing = this.field.findPaperByTitle(paper.title)
      if (existing) {
        return { papersCreated, techniquesCreated, findingsCreated, algorithmsCreated, benchmarksCreated, synapsesCreated, durationMs: 0 }
      }
    }

    // Generate embedding if provider available
    let embedding: number[] | null = null
    if (options?.embeddingProvider) {
      embedding = await options.embeddingProvider(`${paper.title} ${paper.abstract}`)
    }

    const metadata: PaperMetadata = {
      authors: paper.authors ?? [],
      year: paper.year ?? 0,
      venue: paper.venue ?? 'unknown',
      doi: paper.doi,
      url: paper.url,
      citationCount: paper.citationCount,
      knowledgeType: 'paper',
    }

    const paperEngram = this.field.storePaper(paper.title, paper.abstract, metadata, { embedding: embedding ?? undefined })
    papersCreated++

    // Ingest techniques
    const techniqueIds: string[] = []
    for (const tech of paper.techniques ?? []) {
      const techMeta: TechniqueMetadata = {
        domain: tech.domain ?? 'general',
        hyperparameters: tech.hyperparameters ?? {},
        failureModes: tech.failureModes ?? [],
        implementationNotes: tech.implementationNotes ?? '',
        sourcePaperId: paperEngram.id,
        benchmarks: tech.benchmarks ?? [],
        knowledgeType: 'technique',
      }

      let techEmbedding: number[] | null = null
      if (options?.embeddingProvider) {
        techEmbedding = await options.embeddingProvider(`${tech.name} ${tech.description}`)
      }

      const techEngram = this.field.storeTechnique(tech.name, tech.description, techMeta, {
        embedding: techEmbedding ?? undefined,
        tags: [tech.domain ?? 'general'],
      })
      techniquesCreated++
      techniqueIds.push(techEngram.id)

      // Paper introduces technique
      if (options?.createSynapses !== false) {
        try {
          this.field.connect(paperEngram.id, techEngram.id, 'led_to', 0.9)
          synapsesCreated++
        } catch { /* may already exist */ }
      }

      // Benchmarks as separate engrams
      for (const bench of tech.benchmarks ?? []) {
        const benchEngram = this.field.storeBenchmark(
          `${tech.name} on ${bench.dataset}`,
          `Score: ${bench.score}${bench.baseline !== undefined ? ` (baseline: ${bench.baseline})` : ''} using metric ${bench.metric}`,
          { dataset: bench.dataset, metric: bench.metric, stateOfTheArt: bench.score, baseline: bench.baseline ?? 0, year: paper.year ?? 0, knowledgeType: 'benchmark' },
        )
        benchmarksCreated++

        if (options?.createSynapses !== false) {
          try {
            this.field.connect(techEngram.id, benchEngram.id, 'used_in_task', 0.7)
            synapsesCreated++
          } catch { /* may already exist */ }
        }
      }
    }

    // Update paper with technique IDs
    if (techniqueIds.length > 0) {
      this.field.update(paperEngram.id, {
        metadata: { ...paperEngram.metadata, techniqueIds },
      })
    }

    return {
      papersCreated, techniquesCreated, findingsCreated,
      algorithmsCreated, benchmarksCreated, synapsesCreated,
      durationMs: 0,
    }
  }

  private collectJsonFiles(dir: string): string[] {
    const result: string[] = []
    try {
      const entries = fs.readdirSync(dir, { withFileTypes: true })
      for (const entry of entries) {
        if (entry.isFile() && entry.name.endsWith('.json')) {
          result.push(path.join(dir, entry.name))
        }
      }
    } catch {
      // directory may not exist
    }
    return result.sort()
  }
}
