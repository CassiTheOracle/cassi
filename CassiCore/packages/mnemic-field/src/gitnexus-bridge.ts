/**
 * GitNexus ↔ Mnemic Field Bridge
 *
 * Bidirectional integration between the GitNexus code knowledge graph
 * and the mnemic field's topology. When the GitNexus index is refreshed,
 * this bridge creates `contains_symbol` synapses from source_file engrams
 * to represent the structural relationships (functions, classes, exports)
 * within each file.
 *
 * This means kindling activation that hits a source file can spread
 * to related files via symbol-level connections, and vice versa.
 */

import { readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'
import { execSync } from 'node:child_process'
import type { ILogger } from '@cassicore/foundation'
import type { CodeStore } from './code-store.js'
import type { MnemicField } from './index.js'

interface GitNexusSymbol {
  uid: string
  name: string
  kind: string
  file: string
  line?: number
}

interface BridgeResult {
  synapsesCreated: number
  filesLinked: number
  durationMs: number
}

/**
 * Synchronize GitNexus symbol data into the mnemic field as synapses.
 *
 * For each source_file engram, queries GitNexus for symbols defined in that file
 * and creates cross-file `contains_symbol` synapses where one file's symbol
 * is referenced by another file.
 */
export class GitNexusBridge {
  private field: MnemicField
  private codeStore: CodeStore
  private logger: ILogger
  private repoRoot: string

  constructor(field: MnemicField, codeStore: CodeStore, logger: ILogger, repoRoot: string) {
    this.field = field
    this.codeStore = codeStore
    this.logger = logger.child ? logger.child('gitnexus-bridge') : logger
    this.repoRoot = repoRoot
  }

  /**
   * Sync symbol relationships from GitNexus into mnemic field synapses.
   * Reads the GitNexus graph data and creates `contains_symbol` edges
   * between files that share symbol references.
   */
  sync(): BridgeResult {
    const start = Date.now()

    const metaPath = join(this.repoRoot, '.gitnexus', 'meta.json')
    if (!existsSync(metaPath)) {
      this.logger.debug('GitNexus index not found, skipping bridge sync')
      return { synapsesCreated: 0, filesLinked: 0, durationMs: Date.now() - start }
    }

    // Get all source file engrams indexed by path
    const filePaths = this.codeStore.listSourceFilePaths()
    const engramByPath = new Map<string, string>()
    for (const fp of filePaths) {
      engramByPath.set(fp.filePath, fp.id)
    }

    if (engramByPath.size === 0) {
      return { synapsesCreated: 0, filesLinked: 0, durationMs: Date.now() - start }
    }

    // Query GitNexus for cross-file symbol references
    const crossFileRefs = this.queryCrossFileReferences()

    let synapsesCreated = 0
    const linkedFiles = new Set<string>()

    for (const ref of crossFileRefs) {
      const sourceEngramId = engramByPath.get(ref.sourceFile)
      const targetEngramId = engramByPath.get(ref.targetFile)

      if (!sourceEngramId || !targetEngramId) continue
      if (sourceEngramId === targetEngramId) continue

      try {
        this.field.connect({
          sourceId: sourceEngramId,
          targetId: targetEngramId,
          edgeType: 'contains_symbol',
          weight: Math.min(1.0, 0.3 + ref.referenceCount * 0.05),
        })
        synapsesCreated++
        linkedFiles.add(ref.sourceFile)
        linkedFiles.add(ref.targetFile)
      } catch {
        // Synapse may already exist (idempotent on PK conflict)
      }
    }

    const durationMs = Date.now() - start
    this.logger.info('GitNexus bridge sync complete', {
      synapsesCreated,
      filesLinked: linkedFiles.size,
      durationMs,
    })

    return { synapsesCreated, filesLinked: linkedFiles.size, durationMs }
  }

  /**
   * Spike source_file engrams when GitNexus symbols in those files are queried.
   * Call this after a GitNexus symbol lookup to propagate activation.
   */
  spikeFilesForSymbols(filePaths: string[], taskContext?: string): number {
    let spiked = 0
    for (const fp of filePaths) {
      const engram = this.codeStore.getFileByPath(fp)
      if (!engram) continue
      try {
        this.field.spike({
          engramId: engram.id,
          magnitude: 0.5,
          taskContext,
          outcome: 'unknown',
        })
        spiked++
      } catch { /* non-fatal */ }
    }
    return spiked
  }

  /**
   * Query GitNexus for cross-file symbol references using the graph data.
   * Returns pairs of (sourceFile, targetFile, referenceCount).
   */
  private queryCrossFileReferences(): Array<{
    sourceFile: string
    targetFile: string
    referenceCount: number
  }> {
    try {
      // Use gitnexus CLI to query cross-file relationships
      const output = execSync(
        `npx gitnexus query --format json "MATCH (a)-[:CALLS|IMPORTS]->(b) WHERE a.file <> b.file RETURN a.file AS source, b.file AS target, count(*) AS refs ORDER BY refs DESC LIMIT 500"`,
        { cwd: this.repoRoot, encoding: 'utf8', timeout: 30_000, stdio: ['ignore', 'pipe', 'pipe'] },
      )

      const rows = JSON.parse(output) as Array<{ source: string; target: string; refs: number }>
      return rows.map(r => ({
        sourceFile: r.source,
        targetFile: r.target,
        referenceCount: r.refs,
      }))
    } catch (err) {
      // Fallback: parse the graph data files directly
      this.logger.debug('GitNexus CLI query failed, attempting file-based fallback', { error: String(err) })
      return this.parseCrossFileRefsFromGraph()
    }
  }

  /**
   * Fallback: parse cross-file references directly from .gitnexus/graph/ data.
   */
  private parseCrossFileRefsFromGraph(): Array<{
    sourceFile: string
    targetFile: string
    referenceCount: number
  }> {
    const edgesPath = join(this.repoRoot, '.gitnexus', 'graph', 'edges.json')
    const nodesPath = join(this.repoRoot, '.gitnexus', 'graph', 'nodes.json')

    if (!existsSync(edgesPath) || !existsSync(nodesPath)) return []

    try {
      const nodes = JSON.parse(readFileSync(nodesPath, 'utf8')) as Array<{ uid: string; file?: string }>
      const edges = JSON.parse(readFileSync(edgesPath, 'utf8')) as Array<{ source: string; target: string; type: string }>

      const nodeFileMap = new Map<string, string>()
      for (const node of nodes) {
        if (node.file) nodeFileMap.set(node.uid, node.file)
      }

      const refCounts = new Map<string, number>()
      for (const edge of edges) {
        if (edge.type !== 'CALLS' && edge.type !== 'IMPORTS') continue
        const srcFile = nodeFileMap.get(edge.source)
        const tgtFile = nodeFileMap.get(edge.target)
        if (!srcFile || !tgtFile || srcFile === tgtFile) continue

        const key = `${srcFile}|${tgtFile}`
        refCounts.set(key, (refCounts.get(key) ?? 0) + 1)
      }

      return Array.from(refCounts.entries()).map(([key, count]) => {
        const [sourceFile, targetFile] = key.split('|')
        return { sourceFile, targetFile, referenceCount: count }
      })
    } catch (err) {
      this.logger.warn('Failed to parse GitNexus graph files', { error: String(err) })
      return []
    }
  }
}
