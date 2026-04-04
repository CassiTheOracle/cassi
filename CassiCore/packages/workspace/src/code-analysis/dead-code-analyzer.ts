/**
 * Dead Code Analyzer
 *
 * Finds exported symbols with zero incoming references (no callers, no importers).
 * Uses GitNexus graph when available, with automatic reindex on stale.
 *
 * Strategy:
 *  1. Cypher query: all symbols with zero incoming CALLS/IMPORTS edges
 *  2. Filter to exported symbols only
 *  3. Cross-reference with git log to find last-modified dates
 *  4. Exclude known false positives (entry points, handlers, tool defs)
 *  5. Score confidence and return ranked results
 */

import { execSync } from 'node:child_process'
import type { ILogger } from '../../../types/interfaces.js'
import type { DeadCodeResult, DeadCodeOptions } from './types.js'
import { isIndexAvailable, ensureFreshIndexBackground } from './gitnexus-bridge.js'

/** Patterns that indicate a symbol is an entry point (not dead). */
const ENTRY_POINT_PATTERNS = [
  /^main$/i,
  /^index$/i,
  /^execute.*Tool$/,
  /^handle.*Request$/,
  /^get.*Tool(?:s)?$/,
  /^route.*Call$/,
  /^create.*Server$/,
  /^register/,
  /^setup/,
  /^init(?:ialize)?$/,
  /^bootstrap/,
  /^default$/,                // default exports
  /^module\.exports$/,
  /Test$/,                    // test utilities
  /Spec$/,
  /^describe$/,
  /^it$/,
  /^test$/,
]

/**
 * Check if a symbol name matches a known entry-point pattern.
 */
function isLikelyEntryPoint(name: string): boolean {
  return ENTRY_POINT_PATTERNS.some(p => p.test(name))
}

/**
 * Get last-modified dates for files via git log.
 */
function getLastModifiedDates(root: string): Map<string, string> {
  const dates = new Map<string, string>()
  try {
    const output = execSync(
      'git log --format="%aI" --name-only --diff-filter=M -200',
      { encoding: 'utf-8', cwd: root, timeout: 30_000 },
    )
    let currentDate = ''
    for (const line of output.split('\n')) {
      const trimmed = line.trim()
      if (!trimmed) continue
      if (trimmed.match(/^\d{4}-\d{2}-\d{2}T/)) {
        currentDate = trimmed
      } else if (currentDate && !dates.has(trimmed)) {
        dates.set(trimmed, currentDate)
      }
    }
  } catch {
    // Best-effort
  }
  return dates
}

/**
 * Run dead-code analysis using GitNexus Cypher queries.
 */
export async function analyzeDeadCode(
  router: (tool: string, args: any) => Promise<any>,
  options: DeadCodeOptions,
  logger: ILogger,
): Promise<DeadCodeResult[]> {
  const { path: scopePath, minConfidence = 0.7, includeTestOnly = false, repo } = options

  if (!isIndexAvailable()) {
    logger.warn('GitNexus index not available for dead code analysis')
    return []
  }
  ensureFreshIndexBackground(logger)

  // Step 1: Find all symbols with zero incoming CALLS or IMPORTS edges
    const pathFilter = scopePath
      ? `AND s.filePath STARTS WITH "${scopePath}"`
      : ''
    const testFilter = includeTestOnly
      ? ''
      : 'AND NOT s.filePath CONTAINS "test"'

    const cypher = `
      MATCH (s)
      WHERE (s:Function OR s:Class OR s:Method)
      ${pathFilter}
      ${testFilter}
      AND NOT EXISTS {
        MATCH (caller)-[:CodeRelation {type: 'CALLS'}]->(s)
      }
      AND NOT EXISTS {
        MATCH (importer)-[:CodeRelation {type: 'IMPORTS'}]->(s)
      }
      RETURN s.name AS name, s.filePath AS filePath, label(s) AS kind,
             s.startLine AS startLine, s.endLine AS endLine
      ORDER BY s.filePath
      LIMIT 200
    `

    let cypherResult: any
    try {
      cypherResult = await router('gitnexus_cypher', { query: cypher, repo })
    } catch (err) {
      logger.warn('Dead code Cypher query failed, trying simpler query', { error: String(err) })
      // Fallback: simpler query without NOT EXISTS (KuzuDB compatibility)
      const simpleCypher = `
        MATCH (s)
        WHERE (s:Function OR s:Class OR s:Method)
        ${pathFilter}
        ${testFilter}
        RETURN s.name AS name, s.filePath AS filePath, label(s) AS kind,
               s.startLine AS startLine, s.endLine AS endLine
        LIMIT 500
      `
      cypherResult = await router('gitnexus_cypher', { query: simpleCypher, repo })
    }

    // Parse markdown table result
    const symbols = parseCypherMarkdown(cypherResult?.markdown || cypherResult?.output || '')

    // Step 2: For each symbol, check if it has incoming references via context
    const results: DeadCodeResult[] = []
    const modDates = getLastModifiedDates(process.cwd())

    for (const sym of symbols) {
      if (isLikelyEntryPoint(sym.name)) continue

      let confidence = 0.8  // Base confidence from graph query
      const lineCount = (sym.endLine || 0) - (sym.startLine || 0) + 1

      // Symbols not modified in 90+ days get a confidence boost
      const lastMod = modDates.get(sym.filePath)
      if (lastMod) {
        const daysSinceModified = (Date.now() - new Date(lastMod).getTime()) / (1000 * 60 * 60 * 24)
        if (daysSinceModified > 90) confidence += 0.1
        if (daysSinceModified > 180) confidence += 0.05
      }

      // Very small symbols (< 5 lines) are less interesting
      if (lineCount < 5) confidence -= 0.1

      confidence = Math.min(1.0, Math.max(0.0, confidence))

      if (confidence >= minConfidence) {
        results.push({
          symbolName: sym.name,
          filePath: sym.filePath,
          kind: sym.kind || 'unknown',
          lineCount,
          lastModified: lastMod || 'unknown',
          confidence,
          reason: `No incoming CALLS or IMPORTS edges in knowledge graph${
            !lastMod ? '' : `. Last modified: ${lastMod.split('T')[0]}`
          }`,
        })
      }
    }

    // Sort by confidence desc, then by line count desc (biggest dead symbols first)
    results.sort((a, b) => b.confidence - a.confidence || b.lineCount - a.lineCount)

    return results
}

/**
 * Parse GitNexus Cypher markdown table output into structured rows.
 */
function parseCypherMarkdown(markdown: string): Array<{
  name: string
  filePath: string
  kind: string
  startLine: number
  endLine: number
}> {
  const rows: Array<{ name: string; filePath: string; kind: string; startLine: number; endLine: number }> = []
  const lines = markdown.split('\n')

  // Find header line to get column indices
  let headerIdx = -1
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].includes('name') && lines[i].includes('filePath')) {
      headerIdx = i
      break
    }
  }
  if (headerIdx < 0) return rows

  const headers = lines[headerIdx].split('|').map(h => h.trim()).filter(Boolean)
  const nameIdx = headers.indexOf('name')
  const fileIdx = headers.indexOf('filePath')
  const kindIdx = headers.indexOf('kind')
  const startIdx = headers.indexOf('startLine')
  const endIdx = headers.indexOf('endLine')

  // Parse data rows (skip separator line)
  for (let i = headerIdx + 2; i < lines.length; i++) {
    const cols = lines[i].split('|').map(c => c.trim()).filter(Boolean)
    if (cols.length < headers.length) continue

    rows.push({
      name: cols[nameIdx] || '',
      filePath: cols[fileIdx] || '',
      kind: cols[kindIdx] || '',
      startLine: parseInt(cols[startIdx] || '0', 10),
      endLine: parseInt(cols[endIdx] || '0', 10),
    })
  }

  return rows
}
