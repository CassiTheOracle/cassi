/**
 * format-tool.ts — Tool-specific display formatting for the conversation panel.
 *
 * Extracts the most relevant information from a tool call's input
 * and produces a concise one-line summary suitable for the TUI.
 */

/** Safely parse a JSON string, returning null on failure. */
function tryParse(input: string): Record<string, unknown> | null {
  try {
    const parsed = JSON.parse(input)
    return typeof parsed === 'object' && parsed !== null ? parsed as Record<string, unknown> : null
  } catch {
    return null
  }
}

/** Truncate a string with ellipsis. */
/**
 * @dep callers: format-tool.ts (cassi-tui/src/utils/format-tool.ts), ExpandedResult (cassi-tui/src/components/ToolCallBlock.tsx), ToolCallBlock (cassi-tui/src/components/ToolCallBlock.tsx), formatToolSummary (cassi-tui/src/utils/format-tool.ts), LiveTurn (cassi-tui/src/components/ConversationPanel.tsx) [+1]
 * @dep module: Components
 * @dep risk: MEDIUM | 6 callers, 0 flows, 1 module
 */

function trunc(s: string, max: number): string {
  if (s.length <= max) return s
  return s.slice(0, max - 1) + '\u2026'
}

/** Strip leading/trailing quotes from a string value. */
function unquote(s: string): string {
  if ((s.startsWith('"') && s.endsWith('"')) || (s.startsWith("'") && s.endsWith("'"))) {
    return s.slice(1, -1)
  }
  return s
}


type Extractor = (input: Record<string, unknown>) => string

const extractors: Record<string, Extractor> = {
  // Shell
  bash: (i) => {
    const cmd = String(i.command ?? '')
    return trunc(cmd, 55)
  },
  shell_exec: (i) => {
    const cmd = String(i.command ?? '')
    return trunc(cmd, 55)
  },

  // File read
  read_file: (i) => {
    const path = String(i.path ?? '')
    const parts: string[] = [shortenPath(path)]
    if (i.offset) parts.push(`L${i.offset}`)
    if (i.limit) parts.push(`+${i.limit}`)
    return parts.join(' ')
  },

  // Batch read
  read_files: (i) => {
    try {
      const paths = typeof i.paths === 'string' ? JSON.parse(i.paths) as string[] : i.paths
      if (Array.isArray(paths)) {
        if (paths.length === 1) return shortenPath(String(paths[0]))
        return `${paths.length} files`
      }
    } catch { /* fall through */ }
    return ''
  },

  // File write
  write_file: (i) => {
    const path = String(i.path ?? '')
    const content = String(i.content ?? '')
    const size = byteSize(content)
    return `${shortenPath(path)} (${size})`
  },

  // Web fetch
  web_fetch: (i) => {
    const url = String(i.url ?? '')
    return trunc(url, 80)
  },

  // Web search
  web_search: (i) => {
    const query = String(i.query ?? i.queries ?? '')
    return `"${trunc(query, 60)}"`
  },

  // Memory
  memory_search: (i) => {
    const query = String(i.query ?? '')
    return `"${trunc(query, 60)}"`
  },

  remember: (i) => {
    const note = String(i.note ?? '')
    return trunc(note, 60)
  },

  // Think
  think: (i) => {
    const query = String(i.query ?? '')
    return trunc(query, 60)
  },

  // Background jobs
  run_background: (i) => {
    const cmd = String(i.command ?? '')
    const label = i.label ? ` [${i.label}]` : ''
    return trunc(cmd, 60) + label
  },

  check_job: (i) => String(i.jobId ?? ''),
  wait_job: (i) => String(i.jobId ?? ''),

  // Tests
  run_tests: (i) => {
    const path = String(i.testPath ?? '')
    return shortenPath(path)
  },

  // Desktop vision
  desktop_vision: (i) => {
    const action = String(i.action ?? 'capture')
    return action
  },

  // Subagents
  list_subagents: () => '',
  get_subagent_status: (i) => String(i.runId ?? ''),
  get_subagent_result: (i) => String(i.runId ?? ''),

  // Cognitive internals — show a brief hint
  _reflect: (i) => String(i.focus ?? ''),
  _remember: () => 'storing observations',
  _probe: (i) => String(i.signal_kind ?? ''),
  _autofix: (i) => {
    const file = String(i.target_file ?? '')
    return shortenPath(file)
  },
}


/**
 * Produce a concise summary string for a tool call.
 *
 * @param toolName - The registered tool name (e.g. "shell_exec", "read_file")
 * @param rawInput - The JSON-stringified input, or an object
 * @returns A short human-readable description, or empty string
 */
export function formatToolSummary(toolName: string, rawInput: string | Record<string, unknown>): string {
  const input = typeof rawInput === 'string' ? tryParse(rawInput) : rawInput
  if (!input) return ''

  const extractor = extractors[toolName]
  if (extractor) {
    try {
      return extractor(input)
    } catch {
      return ''
    }
  }

  // Fallback: try common field names
  for (const key of ['path', 'command', 'query', 'url', 'name', 'file']) {
    if (input[key] && typeof input[key] === 'string') {
      return trunc(String(input[key]), 60)
    }
  }

  return ''
}

/**
 * Get a short display name for a tool.
 * Maps internal names to friendlier labels.
 */
export function formatToolName(toolName: string): string {
  const nameMap: Record<string, string> = {
    shell_exec: 'bash',
    read_file: 'read',
    read_files: 'read',
    write_file: 'write',
    web_fetch: 'fetch',
    web_search: 'search',
    memory_search: 'memory',
    run_background: 'bg',
    check_job: 'job',
    wait_job: 'job:wait',
    run_tests: 'test',
    desktop_vision: 'vision',
    get_subagent_status: 'agent:status',
    get_subagent_result: 'agent:result',
    list_subagents: 'agents',
    list_sessions: 'sessions',
    query_events: 'events',
  }
  return nameMap[toolName] ?? toolName
}

/**
 * Format a tool result's content for display.
 * Returns the first N lines and a summary of remaining content.
 */
export function formatToolOutput(content: string, maxLines = 10): { preview: string; overflow: string | null } {
  if (!content) return { preview: '', overflow: null }

  const lines = content.split('\n')
  if (lines.length <= maxLines) {
    return { preview: content, overflow: null }
  }

  const preview = lines.slice(0, maxLines).join('\n')
  const remaining = lines.length - maxLines
  return {
    preview,
    overflow: `\u2026${remaining} more line${remaining === 1 ? '' : 's'}`,
  }
}


/** Shorten a file path by showing only last 2-3 segments. */
function shortenPath(fullPath: string): string {
  if (!fullPath) return ''
  const parts = fullPath.replace(/\\/g, '/').split('/')
  // Keep last 3 segments max, or fewer if path is short
  const keep = Math.min(3, parts.length)
  const shortened = parts.slice(-keep).join('/')
  if (keep < parts.length) return '\u2026/' + shortened
  return shortened
}

/** Human-readable byte size. */
/**
 * @dep callers: format-tool.ts (cassi-tui/src/utils/format-tool.ts), MetaBadges (cassi-tui/src/components/ToolCallBlock.tsx)
 * @dep module: Components
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

function byteSize(s: string): string {
  const bytes = Buffer.byteLength(s, 'utf-8')
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`
}

export { shortenPath, byteSize, trunc }
