/**
 * Blackboard Formatting Utilities
 *
 * Provides human-readable markdown formatting for Blackboard summaries.
 * Used by MCP tools and admin API endpoints.
 */

import type { BlackboardChannel } from '../../types/flux-team.js'

/**
 * Summary type matching Blackboard.getSummary() output.
 * Also handles plain snapshot objects from persisted sessions.
 */
interface BlackboardSummaryLike {
  cellId?: string
  createdAt?: number
  lastActivityAt?: number
  channelCounts?: Record<BlackboardChannel, number>
  latestEntries?: Record<BlackboardChannel, Array<{
    id: string
    author: string
    content: string
    timestamp: number
    priority: number
  }>>
  toolLog?: {
    count: number
    lastTools: Array<{ tool: string; isError?: boolean; durationMs?: number }>
  }
  scratchpad?: {
    count: number
    keys: Array<{ key: string; author: string; hasValue: boolean; sizeChars: number }>
  }
  artifacts?: {
    count: number
    list: Array<{ path: string; operation: string; notes?: string }>
  }
  plan?: {
    exists: boolean
    totalSteps?: number
    completedSteps?: number
    steps?: Array<{ id: string; title: string; status: string }>
  }
  report?: {
    exists: boolean
    totalSections?: number
    sections?: Array<{ id: string; type: string; title: string; status: string }>
  }
  childResultsCount?: number
  totalSizeEstimateKB?: number
}

/**
 * Format a Blackboard summary as readable markdown.
 * Renders channels, plan, report, tools, and artifacts in a compact view.
 */
export function formatBlackboardSummary(summary: BlackboardSummaryLike): string {
  const lines: string[] = []

  // Header with size estimate
  const sizeEst = summary.totalSizeEstimateKB ?? 0
  lines.push(`## Blackboard Summary (est. ${sizeEst} KB full)`)

  if (summary.cellId) {
    lines.push(`**Cell ID:** ${summary.cellId}`)
  }

  // Channels section
  lines.push('')
  lines.push('### Channels')

  const channelOrder: BlackboardChannel[] = ['findings', 'concerns', 'decisions', 'artifacts', 'requests']
  const channelCounts = (summary.channelCounts ?? {}) as Record<string, number>
  const latestEntries = (summary.latestEntries ?? {}) as Record<string, Array<{ content: string }>>

  for (const channel of channelOrder) {
    const count = channelCounts[channel] ?? 0
    const entries = latestEntries[channel] ?? []
    const latestStr = entries.length > 0
      ? ` — latest: "${entries[0].content.slice(0, 60)}${entries[0].content.length > 60 ? '...' : ''}"`
      : ''
    lines.push(`- **${channel}** (${count} entries)${latestStr}`)
  }

  // Plan section
  lines.push('')
  if (summary.plan?.exists) {
    const plan = summary.plan
    const completed = plan.completedSteps ?? 0
    const total = plan.totalSteps ?? 0
    lines.push(`### Plan (${completed}/${total} steps complete)`)

    if (plan.steps) {
      for (const step of plan.steps) {
        const check = step.status === 'completed' ? 'x' : ' '
        lines.push(`- [${check}] ${step.title}`)
      }
    }
  } else {
    lines.push('### Plan')
    lines.push('_No plan defined_')
  }

  // Report section
  lines.push('')
  if (summary.report?.exists) {
    lines.push('### Report')
    if (summary.report.sections) {
      for (const section of summary.report.sections) {
        const statusStr = section.status === 'active' ? '' : ` (${section.status})`
        lines.push(`- ${section.title}${statusStr}`)
      }
    }
  } else {
    lines.push('### Report')
    lines.push('_No report sections_')
  }

  // Tools section
  lines.push('')
  const toolLog = summary.toolLog
  if (toolLog) {
    lines.push(`### Tools (${toolLog.count} calls)`)
    if (toolLog.lastTools.length > 0) {
      const toolNames = toolLog.lastTools.map(t => t.tool).join(', ')
      lines.push(`Last ${toolLog.lastTools.length}: ${toolNames}`)
    }
  } else {
    lines.push('### Tools')
    lines.push('_No tool calls recorded_')
  }

  // Artifacts section
  lines.push('')
  const artifacts = summary.artifacts
  if (artifacts && artifacts.count > 0) {
    lines.push(`### Artifacts (${artifacts.count} files)`)
    for (const artifact of artifacts.list) {
      lines.push(`- ${artifact.path} (${artifact.operation})`)
    }
  } else {
    lines.push('### Artifacts')
    lines.push('_No artifacts tracked_')
  }

  // Scratchpad section
  lines.push('')
  const scratchpad = summary.scratchpad
  if (scratchpad && scratchpad.count > 0) {
    lines.push(`### Scratchpad (${scratchpad.count} entries)`)
    for (const key of scratchpad.keys.slice(0, 5)) {
      lines.push(`- ${key.key} (${key.sizeChars} chars, by ${key.author})`)
    }
    if (scratchpad.keys.length > 5) {
      lines.push(`  ... and ${scratchpad.keys.length - 5} more`)
    }
  } else {
    lines.push('### Scratchpad')
    lines.push('_No scratchpad entries_')
  }

  return lines.join('\n')
}

/**
 * Format a single channel's entries as markdown.
 * Used when ?channel=X is specified.
 */
export function formatChannelEntries(
  channel: BlackboardChannel,
  entries: Array<{ id: string; author: string; content: string; timestamp: number; priority: number; tags?: string[] }>,
): string {
  const lines: string[] = []

  lines.push(`## Channel: ${channel}`)
  lines.push(`**${entries.length} entries**`)
  lines.push('')

  for (const entry of entries) {
    const time = new Date(entry.timestamp).toISOString()
    const priorityStr = entry.priority > 0 ? ` [P${entry.priority}]` : ''
    const tagsStr = entry.tags?.length ? ` {${entry.tags.join(', ')}}` : ''

    lines.push(`### ${entry.id.slice(0, 8)}${priorityStr}`)
    lines.push(`**Author:** ${entry.author}  `)
    lines.push(`**Time:** ${time}${tagsStr}`)
    lines.push('')
    lines.push(entry.content)
    lines.push('')
  }

  return lines.join('\n')
}

/**
 * Check if an object looks like a Blackboard summary (vs a full snapshot).
 * Summaries have channelCounts, full snapshots have channels with arrays.
 */
export function isSummary(obj: unknown): obj is BlackboardSummaryLike {
  if (!obj || typeof obj !== 'object') return false
  const s = obj as Record<string, unknown>
  return 'channelCounts' in s && typeof s.channelCounts === 'object'
}

/**
 * Check if an object looks like a full Blackboard snapshot.
 */
export function isFullSnapshot(obj: unknown): boolean {
  if (!obj || typeof obj !== 'object') return false
  const s = obj as Record<string, unknown>
  return 'channels' in s && typeof s.channels === 'object'
}