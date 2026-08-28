/**
 * Tool Output Presentation Layer
 * 
 * Formats raw tool outputs into LLM-friendly representations.
 * Implements the "two-layer architecture" pattern:
 * - Layer 1: Raw execution (handled by tool implementations)
 * - Layer 2: Presentation formatting (this module)
 * 
 * Features:
 * - Binary content detection and graceful handling
 * - Output overflow management with temp file spill
 * - Metadata footers for shell executions
 * - Stderr visibility for failed commands
 */

import { writeFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'
import { randomBytes } from 'node:crypto'

import type { ILogger } from "@cassicore/foundation"
import { rootLogger } from '@cassicore/events'

const logger: ILogger = rootLogger.child('presentation')

/** Configuration for presentation formatting */
export interface PresentationOptions {
  /** Name of the tool that produced the output */
  toolName: string
  /** Exit code (for shell tools) */
  exitCode?: number
  /** Execution duration in milliseconds */
  durationMs?: number
  /** Standard error output (for shell tools) */
  stderr?: string
}

/** Thresholds for overflow mode */
const MAX_LINES = 2000
const MAX_SIZE_BYTES = 200 * 1024 // 200KB

// WHY: File-read tools have their own size bounds (1MB/512KB) and agents request
// them deliberately.  Truncating their output at 200 lines (the old limit) forces
// agents into chunk-reading loops that waste 80%+ of their tool calls.
const FILE_READ_TOOLS = new Set([
  'read_file', 'read_files', 'file',
  'cassi_do',  // wraps read_file calls
])

/** Temp directory for overflow files */
const TEMP_DIR = '/tmp'

/**
 * Detect if content contains binary data (null bytes or non-UTF8 sequences)
 */
function isBinaryContent(content: string): boolean {
  // Check for null bytes (most reliable binary indicator in text)
  if (content.includes('\0')) {
    return true
  }
  
  // Check for high concentration of non-printable characters
  let nonPrintableCount = 0
  const checkLength = Math.min(content.length, 1000)
  
  for (let i = 0; i < checkLength; i++) {
    const code = content.charCodeAt(i)
    // Allow common whitespace: tab (9), newline (10), carriage return (13)
    if (code < 9 || (code > 13 && code < 32)) {
      nonPrintableCount++
    }
  }
  
  // If >5% of characters are non-printable, consider it binary
  return nonPrintableCount / checkLength > 0.05
}

/**
 * Generate a unique temp filename for overflow output
 */
function generateTempFilename(): string {
  const randomId = randomBytes(8).toString('hex')
  return join(TEMP_DIR, `cassicore-tool-${randomId}.txt`)
}

/**
 * Count lines in a string
 */
function countLines(content: string): number {
  if (content.length === 0) return 0
  return content.split('\n').length
}

/**
 * Format byte size as human-readable string
 */
function formatSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes}B`
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)}KB`
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`
}

/**
 * Process raw tool output and produce LLM-friendly formatted output.
 * 
 * @param rawOutput - The raw string output from the tool handler
 * @param opts - Presentation options including tool metadata
 * @returns Formatted output string suitable for LLM consumption
 * @dep callers: tool-presentation.test.ts (tests/tool-presentation.test.ts), applyPresentation (core/tools/executor.ts)
 * @dep calls: isBinaryContent, generateTempFilename, countLines, formatSize
 * @dep module: Tools
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
export function presentForLLM(rawOutput: string, opts: PresentationOptions): string {
  const parts: string[] = []
  
  // 1. Binary guard - detect and handle binary content
  if (isBinaryContent(rawOutput)) {
    logger.debug('Binary content detected', { 
      toolName: opts.toolName, 
      size: rawOutput.length 
    })
    return `[binary content detected: ${rawOutput.length} bytes. Use appropriate tools to view.]`
  }
  
  // 2. Overflow mode - handle large outputs
  // Skip overflow for file-read tools — they already have implementation-level
  // size bounds and agents should see the full content they requested
  const totalLines = countLines(rawOutput)
  const sizeBytes = Buffer.byteLength(rawOutput, 'utf8')
  const isFileRead = FILE_READ_TOOLS.has(opts.toolName)
  
  if (!isFileRead && (totalLines > MAX_LINES || sizeBytes > MAX_SIZE_BYTES)) {
    logger.debug('Output overflow detected', {
      toolName: opts.toolName,
      totalLines,
      sizeBytes,
      maxLines: MAX_LINES,
      maxSizeBytes: MAX_SIZE_BYTES,
    })
    
    // Write full output to temp file
    const tempPath = generateTempFilename()
    try {
      writeFileSync(tempPath, rawOutput, 'utf8')
      logger.debug('Overflow written to temp file', { tempPath })
    } catch (err) {
      logger.error('Failed to write overflow file', { 
        tempPath, 
        error: String(err) 
      })
      // Continue with truncation even if temp write fails
    }
    
    // Truncate to first MAX_LINES
    const lines = rawOutput.split('\n')
    const truncatedContent = lines.slice(0, MAX_LINES).join('\n')
    
    parts.push(truncatedContent)
    parts.push('')
    parts.push(`[output truncated: ${totalLines} lines, ${formatSize(sizeBytes)}. Full output: ${tempPath}]`)
    
    // Add exploration hints for shell tools
    if (opts.toolName === 'bash' || opts.toolName === 'shell_exec' || opts.toolName === 'shell-exec') {
      parts.push('[Explore: bash "grep <pattern> /tmp/cassicore-tool-*.txt" | bash "tail -n 50 /tmp/cassicore-tool-*.txt"]')
    }
  } else {
    // No overflow - use full content
    parts.push(rawOutput)
  }
  
  // 3. Metadata footer for shell tools
  if (opts.toolName === 'bash' || opts.toolName === 'shell_exec' || opts.toolName === 'shell-exec') {
    const metaParts: string[] = []
    
    if (opts.exitCode !== undefined) {
      metaParts.push(`exit:${opts.exitCode}`)
    }
    
    if (opts.durationMs !== undefined) {
      metaParts.push(`${opts.durationMs}ms`)
    }
    
    if (metaParts.length > 0) {
      parts.push('')
      parts.push(`[${metaParts.join(' | ')}]`)
    }
    
    // 4. Stderr attachment for failed commands
    if (opts.exitCode !== undefined && opts.exitCode !== 0 && opts.stderr) {
      parts.push('')
      parts.push(`[stderr] ${opts.stderr}`)
    }
  }
  
  return parts.join('\n')
}
