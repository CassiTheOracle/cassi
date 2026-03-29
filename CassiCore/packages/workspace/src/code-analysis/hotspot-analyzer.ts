/**
 * Hotspot Analyzer
 *
 * Ranks files by composite risk score: size × complexity × coupling.
 * Uses GitNexus graph for coupling data and file system for size/complexity.
 *
 * Dimensions:
 *  - Size: file line count, normalized across codebase
 *  - Complexity: exported symbol count × nesting factor (proxy for McCabe)
 *  - Coupling: incoming + outgoing edges in knowledge graph
 */

import { execSync } from 'node:child_process'
import type { ILogger } from '../../../types/interfaces.js'
import type { HotspotResult, HotspotOptions } from './types.js'
import { withAutoReindex } from './gitnexus-bridge.js'

/** Weight distribution for composite score. */
const WEIGHT_SIZE = 0.3
const WEIGHT_COMPLEXITY = 0.3
const WEIGHT_COUPLING = 0.4

/**
 * Get line counts for all tracked files.
 */
function getFileSizes(root: string, scopePath?: string): Map<string, number> {
  const sizes = new Map<string, number>()
  try {
    const pathArg = scopePath ? `-- "${scopePath}"` : ''
    // Use git ls-files to get tracked files, then wc -l for line counts
    const files = execSync(
      `git ls-files --cached "*.ts" "*.js" "*.tsx" "*.jsx" ${pathArg}`,
      { encoding: 'utf-8', cwd: root, timeout: 30_000 },
    ).trim().split('\n').filter(Boolean)

    for (const file of files) {
      try {
        const count = execSync(
          `wc -l < "${file}"`,
          { encoding: 'utf-8', cwd: root, timeout: 5_000 },
        ).trim()
        sizes.set(file, parseInt(count, 10) || 0)
      } catch {
        // Skip unreadable files
      }
    }
  } catch {
    // Fallback: empty map
  }
  return sizes
}

/**
 * Normalize a map of values to 0-1 range.
 */
function normalize(values: Map<string, number>): Map<string, number> {
  const vals = [...values.values()]
  if (vals.length === 0) return new Map()
  const max = Math.max(...vals)
  const min = Math.min(...vals)
  const range = max - min || 1
  const result = new Map<string, number>()
  for (const [k, v] of values) {
    result.set(k, (v - min) / range)
  }
  return result
}

/**
 * Run hotspot analysis.
 */
export async function analyzeHotspots(
  router: (tool: string, args: any) => Promise<any>,
  options: HotspotOptions,
  logger: ILogger,
): Promise<HotspotResult[]> {
  const { path: scopePath, limit = 20, repo } = options

  return withAutoReindex(async () => {
    const root = process.cwd()

    // Step 1: Get file sizes
    const fileSizes = getFileSizes(root, scopePath)
    if (fileSizes.size === 0) {
      logger.warn('No files found for hotspot analysis')
      return []
    }

    // Step 2: Get symbol counts per file from GitNexus
    const symbolCounts = new Map<string, number>()
    const pathFilter = scopePath
      ? `WHERE f.filePath STARTS WITH "${scopePath}"`
      : ''

    try {
      const cypher = `
        MATCH (f:File)-[:CodeRelation {type: 'DEFINES'}]->(s)
        ${pathFilter}
        RETURN f.filePath AS filePath, count(s) AS symbolCount
        ORDER BY symbolCount DESC
        LIMIT 500
      `
      const result = await router('gitnexus_cypher', { query: cypher, repo })
      const rows = parseSimpleMarkdown(result?.markdown || result?.output || '', 'filePath', 'symbolCount')
      for (const row of rows) {
        symbolCounts.set(row.filePath, parseInt(String(row.symbolCount), 10) || 0)
      }
    } catch (err) {
      logger.warn('Failed to get symbol counts from GitNexus', { error: String(err) })
      // Fallback: use file size as complexity proxy
    }

    // Step 3: Get coupling data (incoming + outgoing edges per file)
    const couplingCounts = new Map<string, number>()
    try {
      const cypher = `
        MATCH (s)-[:CodeRelation]->(t)
        WHERE s.filePath <> t.filePath
        RETURN s.filePath AS filePath, count(*) AS edgeCount
        ORDER BY edgeCount DESC
        LIMIT 500
      `
      const result = await router('gitnexus_cypher', { query: cypher, repo })
      const rows = parseSimpleMarkdown(result?.markdown || result?.output || '', 'filePath', 'edgeCount')
      for (const row of rows) {
        const current = couplingCounts.get(row.filePath) || 0
        couplingCounts.set(row.filePath, current + (parseInt(String(row.edgeCount), 10) || 0))
      }

      // Also count incoming
      const cypher2 = `
        MATCH (s)-[:CodeRelation]->(t)
        WHERE s.filePath <> t.filePath
        RETURN t.filePath AS filePath, count(*) AS edgeCount
        ORDER BY edgeCount DESC
        LIMIT 500
      `
      const result2 = await router('gitnexus_cypher', { query: cypher2, repo })
      const rows2 = parseSimpleMarkdown(result2?.markdown || result2?.output || '', 'filePath', 'edgeCount')
      for (const row of rows2) {
        const current = couplingCounts.get(row.filePath) || 0
        couplingCounts.set(row.filePath, current + (parseInt(String(row.edgeCount), 10) || 0))
      }
    } catch (err) {
      logger.warn('Failed to get coupling data from GitNexus', { error: String(err) })
    }

    // Step 4: Normalize all dimensions to 0-1
    const sizeNorm = normalize(fileSizes)
    const complexityNorm = normalize(symbolCounts.size > 0 ? symbolCounts : fileSizes)
    const couplingNorm = normalize(couplingCounts)

    // Step 5: Compute composite scores
    const allFiles = new Set([...fileSizes.keys()])
    const results: HotspotResult[] = []

    for (const filePath of allFiles) {
      const sizeScore = sizeNorm.get(filePath) || 0
      const complexityScore = complexityNorm.get(filePath) || 0
      const couplingScore = couplingNorm.get(filePath) || 0

      const composite = (
        WEIGHT_SIZE * sizeScore +
        WEIGHT_COMPLEXITY * complexityScore +
        WEIGHT_COUPLING * couplingScore
      )

      results.push({
        filePath,
        score: Math.round(composite * 1000) / 1000,
        dimensions: {
          size: Math.round(sizeScore * 1000) / 1000,
          complexity: Math.round(complexityScore * 1000) / 1000,
          coupling: Math.round(couplingScore * 1000) / 1000,
        },
        raw: {
          lineCount: fileSizes.get(filePath) || 0,
          symbolCount: symbolCounts.get(filePath) || 0,
          incomingEdges: 0, // Approximated in coupling
          outgoingEdges: couplingCounts.get(filePath) || 0,
        },
      })
    }

    // Sort by composite score descending
    results.sort((a, b) => b.score - a.score)

    return results.slice(0, limit)
  }, logger)
}

/**
 * Parse a simple 2-column Cypher markdown table.
 */
function parseSimpleMarkdown(
  markdown: string,
  col1Name: string,
  col2Name: string,
): Array<{ filePath: string; [key: string]: any }> {
  const rows: Array<{ filePath: string; [key: string]: any }> = []
  const lines = markdown.split('\n')

  let headerIdx = -1
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].includes(col1Name)) {
      headerIdx = i
      break
    }
  }
  if (headerIdx < 0) return rows

  const headers = lines[headerIdx].split('|').map(h => h.trim()).filter(Boolean)
  const idx1 = headers.indexOf(col1Name)
  const idx2 = headers.indexOf(col2Name)

  for (let i = headerIdx + 2; i < lines.length; i++) {
    const cols = lines[i].split('|').map(c => c.trim()).filter(Boolean)
    if (cols.length < headers.length) continue
    rows.push({
      filePath: cols[idx1] || '',
      [col2Name]: cols[idx2] || '',
    })
  }

  return rows
}
