import fs from 'node:fs'
import path from 'node:path'
import { execSync } from 'node:child_process'
import type { ILogger } from '../../../types/interfaces.js'
import type { CodeStore } from './code-store.js'
import type { Engram } from './types.js'

export interface IngestOptions {
  rootDir: string
  include?: string[]
  exclude?: string[]
  embeddingProvider?: (text: string) => Promise<number[] | null>
  batchSize?: number
}

export interface IngestResult {
  filesIngested: number
  filesUpdated: number
  filesSkipped: number
  importSynapsesCreated: number
  coChangeSynapsesCreated: number
  durationMs: number
}

const DEFAULT_INCLUDE = ['src/**/*.ts', 'core/**/*.ts', 'types/**/*.ts', 'workers/**/*.ts']
const DEFAULT_EXCLUDE = [
  'node_modules', 'dist', '**/__tests__/**', '**/*.test.ts',
  '**/branching-conversation/**',
]

/**
 * Walks a source tree and ingests files into the CodeStore as source_file engrams.
 * Parses import statements to create `imports` synapses and analyzes git history
 * for `co_changed` synapses.
 */
export class CodeIngestor {
  private codeStore: CodeStore
  private logger: ILogger

  constructor(codeStore: CodeStore, logger: ILogger) {
    this.codeStore = codeStore
    this.logger = logger.child ? logger.child('code-ingestor') : logger
  }

  async ingest(options: IngestOptions): Promise<IngestResult> {
    const start = Date.now()
    const rootDir = path.resolve(options.rootDir)

    this.logger.info('Starting codebase ingestion', { rootDir })

    const files = this.collectFiles(rootDir, options.include, options.exclude)
    this.logger.info('Collected source files', { count: files.length })

    let filesIngested = 0
    let filesUpdated = 0
    let filesSkipped = 0
    const engramsByPath = new Map<string, Engram>()

    const batchSize = options.batchSize ?? 50
    for (let i = 0; i < files.length; i += batchSize) {
      const batch = files.slice(i, i + batchSize)

      for (const absPath of batch) {
        const relPath = path.relative(rootDir, absPath)
        try {
          const content = fs.readFileSync(absPath, 'utf8')

          let embedding: number[] | null = null
          if (options.embeddingProvider) {
            embedding = await options.embeddingProvider(content)
          }

          const { engram, created } = this.codeStore.storeFile(relPath, content, {
            embedding: embedding ?? undefined,
          })

          engramsByPath.set(relPath, engram)

          if (created) filesIngested++
          else filesUpdated++
        } catch (err) {
          this.logger.warn('Failed to ingest file', { path: relPath, error: String(err) })
          filesSkipped++
        }
      }

      if (i + batchSize < files.length) {
        this.logger.debug('Ingestion progress', {
          processed: Math.min(i + batchSize, files.length),
          total: files.length,
        })
      }
    }

    const importSynapsesCreated = this.createImportSynapses(rootDir, engramsByPath)
    const coChangeSynapsesCreated = this.createCoChangeSynapses(rootDir, engramsByPath)

    const durationMs = Date.now() - start
    this.logger.info('Codebase ingestion complete', {
      filesIngested, filesUpdated, filesSkipped,
      importSynapsesCreated, coChangeSynapsesCreated, durationMs,
    })

    return {
      filesIngested, filesUpdated, filesSkipped,
      importSynapsesCreated, coChangeSynapsesCreated, durationMs,
    }
  }

  private collectFiles(
    rootDir: string,
    include?: string[],
    exclude?: string[],
  ): string[] {
    const patterns = include ?? DEFAULT_INCLUDE
    const excludePatterns = exclude ?? DEFAULT_EXCLUDE
    const result: string[] = []

    const walkDir = (dir: string) => {
      let entries: fs.Dirent[]
      try {
        entries = fs.readdirSync(dir, { withFileTypes: true })
      } catch {
        return
      }

      for (const entry of entries) {
        const fullPath = path.join(dir, entry.name)
        const relPath = path.relative(rootDir, fullPath)

        if (this.matchesAny(relPath, excludePatterns)) continue

        if (entry.isDirectory()) {
          walkDir(fullPath)
        } else if (entry.isFile() && this.matchesAny(relPath, patterns)) {
          result.push(fullPath)
        }
      }
    }

    walkDir(rootDir)
    return result.sort()
  }

  private matchesAny(filePath: string, patterns: string[]): boolean {
    for (const pattern of patterns) {
      if (this.matchGlob(filePath, pattern)) return true
    }
    return false
  }

  /**
   * Simple glob matcher supporting ** and * patterns.
   */
  private matchGlob(filePath: string, pattern: string): boolean {
    if (!pattern.includes('*')) {
      return filePath.includes(pattern)
    }

    const regexStr = pattern
      .replace(/\./g, '\\.')
      .replace(/\*\*\//g, '(.+/)?')
      .replace(/\*\*/g, '.*')
      .replace(/(?<!\.)(\*)/g, '[^/]*')

    return new RegExp(`^${regexStr}$`).test(filePath)
  }

  /**
   * Parse import statements from TypeScript files and create `imports` synapses.
   */
  private createImportSynapses(
    rootDir: string,
    engramsByPath: Map<string, Engram>,
  ): number {
    let created = 0

    for (const [filePath, engram] of engramsByPath) {
      const imports = this.parseImports(engram.content, filePath, rootDir)

      for (const importedPath of imports) {
        const targetEngram = engramsByPath.get(importedPath)
        if (targetEngram && targetEngram.id !== engram.id) {
          try {
            this.codeStore.connectImports(engram.id, targetEngram.id)
            created++
          } catch {
            // synapse may already exist
          }
        }
      }
    }

    this.logger.debug('Import synapses created', { count: created })
    return created
  }

  /**
   * Extract import paths from TypeScript source and resolve them to relative file paths.
   */
  parseImports(content: string, filePath: string, rootDir: string): string[] {
    const importRegex = /(?:import|export)\s+(?:type\s+)?(?:\{[^}]*\}|[^;'"]+)\s+from\s+['"]([^'"]+)['"]/g
    const results: string[] = []
    let match: RegExpExecArray | null

    while ((match = importRegex.exec(content)) !== null) {
      const specifier = match[1]
      if (!specifier.startsWith('.')) continue

      const dirOfFile = path.dirname(filePath)
      let resolved = path.normalize(path.join(dirOfFile, specifier))

      // ESM .js → .ts resolution
      if (resolved.endsWith('.js')) {
        resolved = resolved.slice(0, -3) + '.ts'
      }

      // Try with .ts extension if no extension
      if (!path.extname(resolved)) {
        resolved += '.ts'
      }

      // Verify the resolved path exists as an engram path (relative to rootDir)
      results.push(resolved)
    }

    return results
  }

  /**
   * Analyze git history to find files frequently changed together,
   * then create `co_changed` synapses.
   */
  private createCoChangeSynapses(
    rootDir: string,
    engramsByPath: Map<string, Engram>,
  ): number {
    let coChangeData: Map<string, Map<string, number>>
    try {
      coChangeData = this.analyzeGitCoChanges(rootDir, engramsByPath)
    } catch (err) {
      this.logger.warn('Git co-change analysis failed', { error: String(err) })
      return 0
    }

    let created = 0
    const minCoChanges = 3

    for (const [fileA, partners] of coChangeData) {
      const engramA = engramsByPath.get(fileA)
      if (!engramA) continue

      for (const [fileB, count] of partners) {
        if (count < minCoChanges) continue
        const engramB = engramsByPath.get(fileB)
        if (!engramB || engramB.id === engramA.id) continue

        try {
          this.codeStore.connectCoChanged(engramA.id, engramB.id, count)
          created++
        } catch {
          // synapse may already exist
        }
      }
    }

    this.logger.debug('Co-change synapses created', { count: created })
    return created
  }

  /**
   * Use git log to find files changed together in commits within the last 6 months.
   */
  private analyzeGitCoChanges(
    rootDir: string,
    engramsByPath: Map<string, Engram>,
  ): Map<string, Map<string, number>> {
    const coChanges = new Map<string, Map<string, number>>()
    const knownPaths = new Set(engramsByPath.keys())

    const gitLog = execSync(
      'git log --since="6 months ago" --name-only --pretty=format:"---" --diff-filter=ACMR',
      { cwd: rootDir, encoding: 'utf8', maxBuffer: 50 * 1024 * 1024 },
    )

    const commits = gitLog.split('---').filter(Boolean)

    for (const commit of commits) {
      const files = commit.trim().split('\n').filter(f => f.trim() && knownPaths.has(f.trim()))

      for (let i = 0; i < files.length; i++) {
        for (let j = i + 1; j < files.length; j++) {
          const a = files[i].trim()
          const b = files[j].trim()

          if (!coChanges.has(a)) coChanges.set(a, new Map())
          if (!coChanges.has(b)) coChanges.set(b, new Map())

          coChanges.get(a)!.set(b, (coChanges.get(a)!.get(b) ?? 0) + 1)
          coChanges.get(b)!.set(a, (coChanges.get(b)!.get(a) ?? 0) + 1)
        }
      }
    }

    return coChanges
  }
}
