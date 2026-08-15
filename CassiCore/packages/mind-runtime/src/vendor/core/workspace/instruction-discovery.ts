/**
 * Ancestor Directory Chain Instruction Discovery
 *
 * Walks from the working directory up to the filesystem root,
 * loading instruction files at each level. This allows nested
 * projects (monorepos, sub-workspaces) to inherit and override
 * instructions from parent directories.
 *
 * Inspired by Claude Code's CLAW.md ancestor discovery pattern.
 *
 * Files checked at each directory level:
 * - AGENTS.md
 * - AGENTS.local.md
 * - .cassicore/AGENTS.md
 * - .cassicore/instructions.md
 *
 * Features:
 * - Content deduplication by hash
 * - Per-file token budget (4K chars)
 * - Total instruction budget (12K chars)
 * - Ancestor-first ordering
 */

import { join, dirname, resolve } from 'node:path'
import { readFileSync, existsSync } from 'node:fs'
import { createHash } from 'node:crypto'

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const MAX_INSTRUCTION_FILE_CHARS = 4_000
const MAX_TOTAL_INSTRUCTION_CHARS = 12_000

const INSTRUCTION_FILENAMES = [
  'AGENTS.md',
  'AGENTS.local.md',
  '.cassicore/AGENTS.md',
  '.cassicore/instructions.md',
] as const

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface InstructionFile {
  /** Absolute path to the file. */
  path: string
  /** Raw file content. */
  content: string
  /** Directory scope (the directory containing the file). */
  scope: string
}

export interface DiscoveredInstructions {
  /** Discovered instruction files, ancestor-first. */
  files: InstructionFile[]
  /** Rendered instruction content with budgeting applied. */
  rendered: string
  /** Total characters before budgeting. */
  totalCharsRaw: number
  /** Total characters after budgeting. */
  totalCharsBudgeted: number
}

/* ------------------------------------------------------------------ */
/*  Discovery                                                          */
/* ------------------------------------------------------------------ */

/**
 * Discover instruction files by walking from `cwd` up to the filesystem root.
 * Returns files in ancestor-first order (root → leaf).
 */
export function discoverInstructionFiles(cwd: string): InstructionFile[] {
  const directories: string[] = []
  let current: string | null = resolve(cwd)

  // Collect ancestor chain (leaf → root)
  while (current) {
    directories.push(current)
    const parent = dirname(current)
    if (parent === current) break // filesystem root
    current = parent
  }

  // Reverse to ancestor-first order (root → leaf)
  directories.reverse()

  const files: InstructionFile[] = []
  for (const dir of directories) {
    for (const filename of INSTRUCTION_FILENAMES) {
      const filePath = join(dir, filename)
      try {
        if (!existsSync(filePath)) continue
        const content = readFileSync(filePath, 'utf-8')
        if (!content.trim()) continue
        files.push({ path: filePath, content, scope: dir })
      } catch {
        // Permission denied or other error — skip
      }
    }
  }

  return deduplicateByContent(files)
}

/**
 * Discover and render instruction files with token budgeting.
 */
export function discoverAndRenderInstructions(cwd: string): DiscoveredInstructions {
  const files = discoverInstructionFiles(cwd)
  const totalCharsRaw = files.reduce((sum, f) => sum + f.content.length, 0)

  if (files.length === 0) {
    return { files, rendered: '', totalCharsRaw: 0, totalCharsBudgeted: 0 }
  }

  const sections: string[] = ['# Workspace Instructions']
  let remainingChars = MAX_TOTAL_INSTRUCTION_CHARS

  for (const file of files) {
    if (remainingChars <= 0) {
      sections.push('\n_Additional instruction content omitted after reaching the prompt budget._')
      break
    }

    const truncated = truncateContent(file.content, Math.min(MAX_INSTRUCTION_FILE_CHARS, remainingChars))
    const consumed = Math.min(truncated.length, remainingChars)
    remainingChars -= consumed

    const label = describeFile(file)
    sections.push(`\n## ${label}\n${truncated}`)
  }

  const rendered = sections.join('\n')
  const totalCharsBudgeted = MAX_TOTAL_INSTRUCTION_CHARS - remainingChars

  return { files, rendered, totalCharsRaw, totalCharsBudgeted }
}

/* ------------------------------------------------------------------ */
/*  Deduplication                                                      */
/* ------------------------------------------------------------------ */

function deduplicateByContent(files: InstructionFile[]): InstructionFile[] {
  const seen = new Set<string>()
  const result: InstructionFile[] = []

  for (const file of files) {
    const normalized = normalizeContent(file.content)
    const hash = contentHash(normalized)
    if (seen.has(hash)) continue
    seen.add(hash)
    result.push(file)
  }

  return result
}

function normalizeContent(content: string): string {
  return collapseBlankLines(content).trim()
}

function contentHash(content: string): string {
  return createHash('sha256').update(content).digest('hex').slice(0, 16)
}

/* ------------------------------------------------------------------ */
/*  Budgeting                                                          */
/* ------------------------------------------------------------------ */

function truncateContent(content: string, maxChars: number): string {
  const trimmed = content.trim()
  if (trimmed.length <= maxChars) return trimmed
  return trimmed.slice(0, maxChars) + '\n\n[truncated]'
}

/* ------------------------------------------------------------------ */
/*  Formatting                                                         */
/* ------------------------------------------------------------------ */

function describeFile(file: InstructionFile): string {
  const filename = file.path.split('/').pop() ?? file.path
  return `${filename} (scope: ${file.scope})`
}

function collapseBlankLines(content: string): string {
  const lines: string[] = []
  let prevBlank = false
  for (const line of content.split('\n')) {
    const isBlank = !line.trim()
    if (isBlank && prevBlank) continue
    lines.push(line.trimEnd())
    prevBlank = isBlank
  }
  return lines.join('\n')
}
