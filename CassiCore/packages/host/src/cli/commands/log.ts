import { createReadStream, statSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'
import { createInterface } from 'node:readline'

import { ParsedArgs, optionalNumber, optionalString, assertNoExtraPositionals } from '../runtime/args.js'
import { fail, printLine } from '../runtime/output.js'

const LOG_FILE_PATH = join(homedir(), '.cassicore', 'daemon.log')

// ANSI color codes (matching logger.ts)
const RESET = '\u001b[0m'
const BOLD = '\u001b[1m'
const DIM = '\u001b[2m'
const GRAY = '\u001b[90m'
const WHITE = '\u001b[37m'
const CYAN = '\u001b[36m'
const YELLOW = '\u001b[33m'
const RED_BOLD = '\u001b[1;31m'

// Log level symbols and labels (matching logger.ts)
const LEVEL_SYMBOL: Record<string, string> = {
  debug: '·',
  info: '▸',
  warn: '▵',
  error: '●',
}

const LEVEL_LABEL: Record<string, string> = {
  debug: 'DEBUG',
  info: 'INFO ',
  warn: 'WARN ',
  error: 'ERROR',
}

const LEVEL_PRIORITY: Record<string, number> = {
  debug: 10,
  info: 20,
  warn: 30,
  error: 40,
}

interface LogEntry {
  timestamp: string
  level: string
  component: string
  message: string
  meta?: string
}

/** ANSI escape code pattern for stripping */
const ANSI_PATTERN = /\x1b\[[0-9;]*[a-zA-Z]/g

/**
 * Strip ANSI escape codes from a string.
 * Handles both color codes and other escape sequences.
 */
function stripAnsi(str: string): string {
  return str.replace(ANSI_PATTERN, '')
}

/**
 * Parse a log line into structured components.
 * Expected format: HH:MM:SS.mmm ▸ INFO   component  Message text  key=value
 * Handles both plain text and ANSI-colorized input (strips ANSI first).
 */
function parseLogLine(line: string): LogEntry | null {
  // Strip any ANSI codes from the input (handles old log files)
  const cleanLine = stripAnsi(line)
  // Match: timestamp symbol LEVEL component message [meta]
  const match = cleanLine.match(
    /^(\d{2}:\d{2}:\d{2}\.\d{3})\s+([▸▵●·])\s+(DEBUG|INFO |WARN |ERROR)\s+(\S+)\s+(.+)$/
  )
  if (!match) return null

  const [, timestamp, symbol, label, component, rest] = match

  // Map symbol/label back to level
  let level = 'info'
  for (const [key, val] of Object.entries(LEVEL_SYMBOL)) {
    if (val === symbol) {
      level = key
      break
    }
  }

  // Check if there's metadata at the end (key=value pairs)
  const metaMatch = rest.match(/^(.*?)\s+((?:\w+=[^\s]+\s*)+)$/)
  const message = metaMatch ? metaMatch[1] : rest
  const meta = metaMatch ? metaMatch[2] : undefined

  return { timestamp, level, component, message, meta }
}

/**
 * Colorize a log entry for terminal output.
 */
function colorizeEntry(entry: LogEntry, useColor: boolean): string {
  if (!useColor) {
    let line = `${entry.timestamp} ${LEVEL_SYMBOL[entry.level]} ${LEVEL_LABEL[entry.level]}  ${entry.component}  ${entry.message}`
    if (entry.meta) line += `  ${entry.meta}`
    return line
  }

  const symbol = LEVEL_SYMBOL[entry.level]
  const label = LEVEL_LABEL[entry.level]

  // Color per level
  let color: string
  switch (entry.level) {
    case 'debug':
      color = GRAY
      break
    case 'info':
      color = CYAN
      break
    case 'warn':
      color = YELLOW
      break
    case 'error':
      color = RED_BOLD
      break
    default:
      color = WHITE
  }

  let line = `${DIM}${entry.timestamp}${RESET} ${color}${symbol} ${label}${RESET}  ${BOLD}${WHITE}${entry.component}${RESET}  ${entry.message}`
  if (entry.meta) {
    line += `  ${DIM}${entry.meta}${RESET}`
  }
  return line
}

/**
 * Filter log entry based on level and grep pattern.
 */
function shouldShowEntry(entry: LogEntry, minLevel?: string, grepPattern?: string): boolean {
  // Level filter
  if (minLevel) {
    const entryPriority = LEVEL_PRIORITY[entry.level] ?? 0
    const minPriority = LEVEL_PRIORITY[minLevel] ?? 0
    if (entryPriority < minPriority) return false
  }

  // Grep filter
  if (grepPattern) {
    const fullLine = `${entry.timestamp} ${LEVEL_SYMBOL[entry.level]} ${LEVEL_LABEL[entry.level]} ${entry.component} ${entry.message} ${entry.meta ?? ''}`
    if (!fullLine.toLowerCase().includes(grepPattern.toLowerCase())) return false
  }

  return true
}

/**
 * Get the last N lines from a file efficiently.
 */
async function getLastLines(filePath: string, n: number): Promise<string[]> {
  const lines: string[] = []
  const stream = createReadStream(filePath, { encoding: 'utf8' })
  const rl = createInterface({ input: stream, crlfDelay: Infinity })

  for await (const line of rl) {
    lines.push(line)
    if (lines.length > n) {
      lines.shift()
    }
  }

  return lines
}

/**
 * Follow a file and print new lines as they arrive.
 */
async function followFile(
  filePath: string,
  useColor: boolean,
  minLevel?: string,
  grepPattern?: string
): Promise<void> {
  // Get initial file size
  let lastSize = statSync(filePath).size

  // First print any existing content
  const lines = await getLastLines(filePath, 50)
  for (const line of lines) {
    const entry = parseLogLine(line)
    if (entry && shouldShowEntry(entry, minLevel, grepPattern)) {
      printLine(colorizeEntry(entry, useColor))
    }
  }

  // Watch for new content
  const checkInterval = setInterval(async () => {
    try {
      const stats = statSync(filePath)
      if (stats.size > lastSize) {
        const stream = createReadStream(filePath, {
          encoding: 'utf8',
          start: lastSize,
        })
        const rl = createInterface({ input: stream, crlfDelay: Infinity })

        for await (const line of rl) {
          if (line.trim()) {
            const entry = parseLogLine(line)
            if (entry && shouldShowEntry(entry, minLevel, grepPattern)) {
              printLine(colorizeEntry(entry, useColor))
            }
          }
        }

        lastSize = stats.size
      }
    } catch {
      // File may have been rotated, reset
      try {
        lastSize = statSync(filePath).size
      } catch {
        // File doesn't exist
      }
    }
  }, 100)

  // Handle Ctrl+C gracefully
  process.on('SIGINT', () => {
    clearInterval(checkInterval)
    process.exit(0)
  })

  // Keep process alive
  await new Promise(() => {})
}

/**
 * Handle the `cassicore log` command.
 */
export async function handleLogCommand(args: ParsedArgs): Promise<void> {
  assertNoExtraPositionals(args)

  const tailCount = optionalNumber(args.options, 'tail')
  const minLevel = optionalString(args.options, 'level')
  const grepPattern = optionalString(args.options, 'grep')
  const noColor = args.options['no-color'] === true
  const follow = args.options['follow'] === true

  // Validate level
  if (minLevel && !LEVEL_PRIORITY[minLevel]) {
    fail(`Invalid level: ${minLevel}. Valid levels: debug, info, warn, error`)
  }

  // Determine color usage
  const useColor = !noColor && process.stdout.isTTY === true

  try {
    // Check if log file exists
    statSync(LOG_FILE_PATH)
  } catch {
    fail(`Log file not found: ${LOG_FILE_PATH}`)
  }

  if (follow) {
    await followFile(LOG_FILE_PATH, useColor, minLevel, grepPattern)
    return
  }

  // Read and display log content
  // When tail is specified with filters, we need to find the last N matching lines
  // not just filter the last N raw lines
  if (tailCount !== undefined && (minLevel || grepPattern)) {
    // Read all lines, filter, then take last N
    const stream = createReadStream(LOG_FILE_PATH, { encoding: 'utf8' })
    const rl = createInterface({ input: stream, crlfDelay: Infinity })
    const matchingLines: string[] = []
    
    for await (const line of rl) {
      const entry = parseLogLine(line)
      if (entry && shouldShowEntry(entry, minLevel, grepPattern)) {
        matchingLines.push(line)
      }
    }
    
    // Take last N matching lines
    const displayLines = matchingLines.slice(-tailCount)
    for (const line of displayLines) {
      const entry = parseLogLine(line)
      if (entry) {
        printLine(colorizeEntry(entry, useColor))
      }
    }
  } else if (tailCount !== undefined) {
    // No filters, just get last N lines
    const lines = await getLastLines(LOG_FILE_PATH, tailCount)
    for (const line of lines) {
      const entry = parseLogLine(line)
      if (entry) {
        printLine(colorizeEntry(entry, useColor))
      }
    }
  } else {
    // No tail limit, read all and filter
    const stream = createReadStream(LOG_FILE_PATH, { encoding: 'utf8' })
    const rl = createInterface({ input: stream, crlfDelay: Infinity })
    
    for await (const line of rl) {
      const entry = parseLogLine(line)
      if (entry && shouldShowEntry(entry, minLevel, grepPattern)) {
        printLine(colorizeEntry(entry, useColor))
      }
    }
  }
}
