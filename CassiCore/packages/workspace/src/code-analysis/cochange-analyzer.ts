/**
 * Git Cochange Analyzer
 *
 * Analyzes git history to find files that frequently change together,
 * revealing hidden coupling not visible in static analysis.
 *
 * Algorithm:
 *  1. Parse `git log --name-only` to get file sets per commit
 *  2. Build co-occurrence matrix (files changed in same commit)
 *  3. Score: cochanges(A,B) / max(changes(A), changes(B))
 *  4. Cache results keyed by HEAD (invalidate on new commits)
 */

import { execSync } from 'node:child_process'
import type { ILogger } from '@cassicore/foundation'
import type { CochangeResult, CochangeOptions } from './types.js'

/** In-memory cache keyed by HEAD commit hash. */
let cachedHead: string | null = null
let cachedMatrix: Map<string, Map<string, number>> | null = null
let cachedChangeCounts: Map<string, number> | null = null

/**
 * Parse git log into per-commit file sets.
 */
function parseGitLog(
  root: string,
  since: string,
  maxCommits: number,
): Array<Set<string>> {
  try {
    const output = execSync(
      `git log --format="%H" --name-only --diff-filter=ACMR --since="${since}" -${maxCommits}`,
      { encoding: 'utf-8', cwd: root, timeout: 60_000 },
    )

    const commits: Array<Set<string>> = []
    let currentSet: Set<string> | null = null

    for (const line of output.split('\n')) {
      const trimmed = line.trim()
      if (!trimmed) {
        if (currentSet && currentSet.size > 0) {
          commits.push(currentSet)
        }
        currentSet = null
        continue
      }

      // SHA line (40 hex chars)
      if (/^[0-9a-f]{40}$/.test(trimmed)) {
        if (currentSet && currentSet.size > 0) {
          commits.push(currentSet)
        }
        currentSet = new Set()
        continue
      }

      // File path line
      if (currentSet) {
        // Only include code files
        if (trimmed.match(/\.(ts|js|tsx|jsx|py|go|rs|java|rb|c|cpp|h|hpp)$/)) {
          currentSet.add(trimmed)
        }
      }
    }

    // Last commit
    if (currentSet && currentSet.size > 0) {
      commits.push(currentSet)
    }

    return commits
  } catch {
    return []
  }
}

/**
 * Build co-occurrence matrix from commit file sets.
 */
function buildCooccurrenceMatrix(
  commits: Array<Set<string>>,
): { matrix: Map<string, Map<string, number>>; changeCounts: Map<string, number> } {
  const matrix = new Map<string, Map<string, number>>()
  const changeCounts = new Map<string, number>()

  for (const files of commits) {
    const fileList = [...files]

    // Count individual file changes
    for (const f of fileList) {
      changeCounts.set(f, (changeCounts.get(f) || 0) + 1)
    }

    // Count co-occurrences (only for commits with 2-30 files — larger commits are noise)
    if (fileList.length >= 2 && fileList.length <= 30) {
      for (let i = 0; i < fileList.length; i++) {
        for (let j = i + 1; j < fileList.length; j++) {
          const a = fileList[i]
          const b = fileList[j]

          if (!matrix.has(a)) matrix.set(a, new Map())
          if (!matrix.has(b)) matrix.set(b, new Map())

          const aMap = matrix.get(a)!
          const bMap = matrix.get(b)!

          aMap.set(b, (aMap.get(b) || 0) + 1)
          bMap.set(a, (bMap.get(a) || 0) + 1)
        }
      }
    }
  }

  return { matrix, changeCounts }
}

/**
 * Get current HEAD for cache key.
 */
function currentHead(root: string): string {
  try {
    return execSync('git rev-parse HEAD', { encoding: 'utf-8', cwd: root }).trim()
  } catch {
    return ''
  }
}

/**
 * Analyze git cochange patterns for a target file.
 */
export async function analyzeCochange(
  options: CochangeOptions,
  logger: ILogger,
): Promise<CochangeResult[]> {
  const {
    target,
    limit = 10,
    minCommits = 3,
    since = '6 months ago',
  } = options

  const root = process.cwd()
  const head = currentHead(root)

  // Check cache
  if (!head || head !== cachedHead || !cachedMatrix || !cachedChangeCounts) {
    logger.debug('Building cochange matrix…', { since })
    const commits = parseGitLog(root, since, 500)
    logger.debug(`Parsed ${commits.length} commits for cochange analysis`)

    const { matrix, changeCounts } = buildCooccurrenceMatrix(commits)
    cachedMatrix = matrix
    cachedChangeCounts = changeCounts
    cachedHead = head
  }

  // Look up the target file's co-movers
  const comovers = cachedMatrix!.get(target)
  if (!comovers) {
    logger.debug('No cochange data for target file', { target })
    return []
  }

  const results: CochangeResult[] = []
  const targetChanges = cachedChangeCounts!.get(target) || 1

  for (const [filePath, cochangeCount] of comovers) {
    if (cochangeCount < minCommits) continue

    const fileChanges = cachedChangeCounts!.get(filePath) || 1
    const score = cochangeCount / Math.max(targetChanges, fileChanges)

    results.push({
      filePath,
      score: Math.round(score * 1000) / 1000,
      cochangeCount,
      fileChangeCount: fileChanges,
    })
  }

  // Sort by score descending
  results.sort((a, b) => b.score - a.score || b.cochangeCount - a.cochangeCount)

  return results.slice(0, limit)
}

/**
 * Invalidate the cochange cache (call when needed, e.g. after a commit).
 */
export function invalidateCochangeCache(): void {
  cachedHead = null
  cachedMatrix = null
  cachedChangeCounts = null
}
