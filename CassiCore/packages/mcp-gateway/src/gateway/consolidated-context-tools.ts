/**
 * Consolidated Context Tools Module
 *
 * Provides cassi_context tool for Thalamus visibility and control:
 * - audit: recent drop history with luminance breakdowns
 * - pin: protect messages matching a pattern from future drops
 * - why: introspect the 5-axis luminance score for a specific message
 * - stats: Thalamus curation statistics
 */

import { fetchWithTimeout, fetchIntelligence, formatJsonResponse, formatTextResponse } from './helpers.js'
import type { ILogger } from '../../types/interfaces.js'

const ADMIN_BASE = 'http://localhost:7433'

export const CONTEXT_CONSOLIDATED_TOOL_NAME = 'context'

export const CONTEXT_CONSOLIDATED_TOOL = {
  name: CONTEXT_CONSOLIDATED_TOOL_NAME,
  description:
    'Thalamus context visibility and control — inspect what was dropped, pin important messages, understand scoring decisions.\n\n' +
    'Use this tool to understand and steer Thalamus curation decisions. The Thalamus filters messages to keep context within budget; ' +
    'this tool makes those decisions visible and reversible.\n\n' +
    'Common actions: audit (recent drop history), pin (protect messages from drops), why (luminance breakdown for one message), stats (curation statistics).',
  inputSchema: {
    type: 'object',
    properties: {
      action: {
        type: 'string',
        enum: ['audit', 'pin', 'unpin', 'why', 'stats', 'recall', 'recall_inject'],
        description:
          'Context operation: audit (recent drops), pin (protect pattern), unpin (remove pin), why (score breakdown), stats (curation stats), recall (search dropped messages), recall_inject (queue content for re-injection)',
      },
      sessionId: {
        type: 'string',
        description: 'Session ID to inspect. Required for audit, pin, unpin, why.',
      },
      window: {
        type: 'number',
        description: 'Number of recent curation rounds for audit (default 5).',
      },
      msgIndex: {
        type: 'number',
        description: 'Message index for why action.',
      },
      pattern: {
        type: 'string',
        description: 'Substring pattern to pin/unpin (e.g. "V4 Pro quant layout").',
      },
      reason: {
        type: 'string',
        description: 'Why this pattern should be protected from drops.',
      },
      pinId: {
        type: 'string',
        description: 'Pin ID to remove (from audit response).',
      },
      query: {
        type: 'string',
        description: 'Search query for recall action — matches against dropped message content.',
      },
      limit: {
        type: 'number',
        description: 'Max results for recall (default 5) or recall_inject batch size.',
      },
      content: {
        type: 'string',
        description: 'Content to inject via recall_inject.',
      },
      role: {
        type: 'string',
        description: 'Role for recall_inject (default "user").',
      },
      label: {
        type: 'string',
        description: 'Label for recall_inject — describes what was recalled.',
      },
    },
    required: ['action'],
  },
} as const

export async function executeContextAction(
  baseUrl: string,
  args: Record<string, unknown>,
  logger: ILogger,
): Promise<{ content: Array<{ type: 'text'; text: string }> }> {
  const action = args.action as string
  const sessionId = args.sessionId as string | undefined
  const adminBase = baseUrl || ADMIN_BASE

  switch (action) {
    case 'audit': {
      if (!sessionId) return formatTextResponse('sessionId is required for audit')
      const window = (args.window as number) ?? 5
      const data = await fetchIntelligence(adminBase, '/context/audit', {
        sessionId,
        window: String(window),
      })
      return formatContextAudit(data)
    }

    case 'why': {
      if (!sessionId) return formatTextResponse('sessionId is required for why')
      if (args.msgIndex === undefined) return formatTextResponse('msgIndex is required for why')
      const data = await fetchIntelligence(adminBase, '/context/why', {
        sessionId,
        msgIndex: String(args.msgIndex),
      })
      return formatContextWhy(data)
    }

    case 'pin': {
      if (!sessionId) return formatTextResponse('sessionId is required for pin')
      const pattern = args.pattern as string | undefined
      if (!pattern) return formatTextResponse('pattern is required for pin')
      const url = `${adminBase}/context/pin`
      const res = await fetchWithTimeout(url, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          sessionId,
          pattern,
          reason: args.reason ?? 'manual pin via cassi_context',
        }),
      })
      const data = await res.json()
      return formatJsonResponse(data)
    }

    case 'unpin': {
      if (!sessionId) return formatTextResponse('sessionId is required for unpin')
      const pinId = args.pinId as string | undefined
      if (!pinId) return formatTextResponse('pinId is required for unpin')
      const url = `${adminBase}/context/pin/${encodeURIComponent(pinId)}?sessionId=${encodeURIComponent(sessionId)}`
      const res = await fetchWithTimeout(url, { method: 'DELETE' })
      const data = await res.json()
      return formatJsonResponse(data)
    }

    case 'stats': {
      const data = await fetchIntelligence(adminBase, '/context/curate/stats')
      return formatJsonResponse(data)
    }

    case 'recall': {
      if (!sessionId) return formatTextResponse('sessionId is required for recall')
      const query = args.query as string | undefined
      const limit = (args.limit as number) ?? 5
      const data = await fetchIntelligence(adminBase, '/context/recall', {
        sessionId,
        query: query ?? '',
        limit: String(limit),
      })
      return formatContextRecall(data)
    }

    case 'recall_inject': {
      if (!sessionId) return formatTextResponse('sessionId is required for recall_inject')
      const content = args.content as string | undefined
      if (!content) return formatTextResponse('content is required for recall_inject')
      const url = `${adminBase}/context/recall_inject`
      const res = await fetchWithTimeout(url, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          sessionId,
          content,
          role: args.role ?? 'user',
          label: args.label ?? 'manual recall_inject',
        }),
      })
      const data = await res.json()
      return formatJsonResponse(data)
    }

    default:
      return formatTextResponse(`Unknown cassi_context action: ${action}. Valid: audit, pin, unpin, why, stats, recall, recall_inject`)
  }
}

function formatContextAudit(data: any): { content: Array<{ type: 'text'; text: string }> } {
  if (!data.records || data.records.length === 0) {
    return formatTextResponse(`No drop history for session ${data.sessionId ?? 'unknown'}.`)
  }

  // Aggregate per-message DropRecords into per-turn summaries
  const byPass = new Map<number, any[]>()
  for (const rec of data.records) {
    const pass = rec.curationPass ?? 0
    if (!byPass.has(pass)) byPass.set(pass, [])
    byPass.get(pass)!.push(rec)
  }

  const lines = [`Drop history for ${data.sessionId} (last ${data.window} turns):\n`]
  for (const [pass, records] of [...byPass.entries()].sort((a, b) => b[0] - a[0])) {
    const dropped = records.filter(r => !r.kept)
    const total = records.length
    const roles = new Map<string, number>()
    for (const r of dropped) {
      roles.set(r.role, (roles.get(r.role) ?? 0) + 1)
    }
    const roleSummary = [...roles.entries()].map(([role, count]) => `${count} ${role}`).join(', ')

    lines.push(`Pass ${pass}: dropped ${dropped.length}/${total} messages`)
    if (roleSummary) lines.push(`  Roles: ${roleSummary}`)

    // Find closest miss (highest luminance among dropped)
    const closest = dropped
      .filter(r => r.luminance?.composite !== undefined)
      .sort((a, b) => b.luminance.composite - a.luminance.composite)[0]
    if (closest) {
      const lum = closest.luminance
      lines.push(`  Closest miss: "${(closest.preview ?? '').slice(0, 80)}" (composite ${lum.composite.toFixed(3)}: nov=${lum.novelty?.toFixed(2)} urg=${lum.urgency?.toFixed(2)} rel=${lum.relevance?.toFixed(2)} cred=${lum.sourceCredibility?.toFixed(2)} cog=${lum.cognitiveResonance?.toFixed(2)} strat=${lum.strategicImportance?.toFixed(2)})`)
    }

    // Show any pinned that were kept despite low luminance
    const pinnedKept = records.filter(r => r.kept && r.pinned)
    if (pinnedKept.length > 0) {
      lines.push(`  Pin-immune: ${pinnedKept.length} kept`)
    }
    lines.push('')
  }

  return formatTextResponse(lines.join('\n'))
}

function formatContextWhy(data: any): { content: Array<{ type: 'text'; text: string }> } {
  if (data.error) return formatTextResponse(`Error: ${data.error}`)

  const lines = [`Luminance breakdown for message ${data.msgIndex}:\n`]
  const scores = data.scores
  if (scores) {
    lines.push(`  Composite:   ${scores.composite?.toFixed(3) ?? 'n/a'}`)
    lines.push(`  Recency:     ${scores.recency?.toFixed(3) ?? 'n/a'}`)
    lines.push(`  Relevance:   ${scores.relevance?.toFixed(3) ?? 'n/a'}`)
    lines.push(`  Urgency:     ${scores.urgency?.toFixed(3) ?? 'n/a'}`)
    lines.push(`  Credibility: ${scores.credibility?.toFixed(3) ?? 'n/a'}`)
    lines.push(`  Load:        ${scores.load?.toFixed(3) ?? 'n/a'}`)
  }
  if (data.kept !== undefined) {
    lines.push(`\n  Status: ${data.kept ? 'KEPT' : 'DROPPED'}`)
  }
  if (data.preview) {
    lines.push(`\n  Preview: "${data.preview}"`)
  }

  return formatTextResponse(lines.join('\n'))
}

function formatChars(n: number | undefined): string {
  if (n === undefined) return '? chars'
  if (n < 1024) return `${n} chars`
  return `${(n / 1024).toFixed(1)}k chars`
}

function formatContextRecall(data: any): { content: Array<{ type: 'text'; text: string }> } {
  if (data.error) return formatTextResponse(`Error: ${data.error}`)
  if (!data.results || data.results.length === 0) {
    return formatTextResponse(`No matching dropped messages found for query "${data.query ?? ''}".`)
  }

  const lines = [`Recall results for "${data.query}" (${data.results.length} matches):\n`]
  for (const r of data.results) {
    const role = r.role ?? 'unknown'
    const idx = r.msgIndex ?? '?'
    const preview = (r.preview ?? '').slice(0, 120)
    lines.push(`  [${idx}] ${role}: "${preview}${preview.length >= 120 ? '...' : ''}"`)
    if (r.luminance) {
      lines.push(`    composite=${r.luminance.composite?.toFixed(2)} strat=${r.luminance.strategicImportance?.toFixed(2) ?? 'n/a'}`)
    }
  }
  lines.push(`\nTo re-inject content, use cassi_context({action: "recall_inject", sessionId, content, label})`)

  return formatTextResponse(lines.join('\n'))
}

export function getContextConsolidatedTool(): typeof CONTEXT_CONSOLIDATED_TOOL {
  return CONTEXT_CONSOLIDATED_TOOL
}
