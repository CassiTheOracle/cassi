import { fetchJson } from '../helpers.js'
import type { ToolDefinition, ToolHandler } from '../types.js'

export const CURATION_TOOLS: ToolDefinition[] = [
  {
    name: 'context_curate',
    description: 'Before a long LLM call: send the current message history to CassiCore\'s Thalamus for scoring, compression, and distillation. Thalamus decides what stays, what gets summarized, and what gets dropped based on 6-axis luminance scoring. Returns the curated message set with cognitive signals woven in so you fit more useful work into every turn.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: { type: 'string', description: 'CassiCore session ID to curate under.' },
        messages: { type: 'array', items: { type: 'object' }, description: 'Array of message objects (OpenAI format: role + content). Pass the full history to let Thalamus decide what to keep.' },
        charBudget: { type: 'number', description: 'Target character budget. Default: 80000 (roughly 20k tokens).' },
        recentWindowSize: { type: 'number', description: 'Last N messages always kept verbatim. Default: 8.' },
      },
      required: ['sessionId', 'messages'],
    },
  },
  {
    name: 'context_health',
    description: 'When the conversation feels sluggish or you suspect context pressure: check how full the context window is. Returns token usage, compression ratio, dropped message count, and gap notes so you can decide whether to curate, summarize, or delegate.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: { type: 'string', description: 'CassiCore session ID.' },
      },
      required: ['sessionId'],
    },
  },
  {
    name: 'context_map',
    description: 'See exactly what survived Thalamus curation and what was dropped, and why. Shows each visible message\'s protection status (pinned, recent-window, live-read), luminance score, and char count so you can audit context budget decisions.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: { type: 'string', description: 'CassiCore session ID.' },
        since: { type: 'number', description: 'Only show messages with index >= this value.' },
        limit: { type: 'number', description: 'Max rows to return.' },
      },
      required: ['sessionId'],
    },
  },
  {
    name: 'context_why',
    description: 'When a critical message was dropped and you need to understand why: get the full luminance breakdown (novelty, urgency, relevance, credibility, resonance, strategic importance). Helps you decide what to pin or whether to adjust your prompting.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: { type: 'string', description: 'CassiCore session ID.' },
        msgIndex: { type: 'number', description: 'The message index from the inline marker (e.g., #42).' },
      },
      required: ['sessionId', 'msgIndex'],
    },
  },
  {
    name: 'context_pin',
    description: 'Protect important context from being dropped in future curation passes. Messages matching the pattern become immune to scoring -- useful for task instructions, API credentials, file paths, or decisions that must survive compression.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: { type: 'string', description: 'CassiCore session ID.' },
        target: { type: 'string', description: 'Content substring or message index to pin.' },
        reason: { type: 'string', description: 'Why this should survive curation.' },
        pinClass: { type: 'string', enum: ['episode', 'decision', 'goal', 'anomaly', 'concern'], description: 'Category of the pinned content. Default: decision.' },
      },
      required: ['sessionId', 'target', 'reason'],
    },
  },
  {
    name: 'context_recall',
    description: 'Recover information that was dropped during curation. Search the drop history by query and optionally re-inject the best match into the conversation on the next curate pass.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: { type: 'string', description: 'CassiCore session ID.' },
        query: { type: 'string', description: 'What to search for in dropped messages.' },
        limit: { type: 'number', description: 'Max results. Default: 5.' },
        reInject: { type: 'boolean', description: 'When true, queue the top result for re-injection on next curate.' },
      },
      required: ['sessionId', 'query'],
    },
  },
]

export async function executeCurationTool(
  adminUrl: string,
  name: string,
  args: any,
  _hermesDbPath: string,
  _logger: any,
): Promise<{ content: Array<{ type: 'text'; text: string }>; isError?: boolean }> {
  try {
    switch (name) {
      case 'context_curate': {
        const { sessionId, messages, charBudget, recentWindowSize } = args
        if (!Array.isArray(messages) || messages.length === 0) {
          return { content: [{ type: 'text', text: 'No messages to curate.' }], isError: true }
        }
        const result = await fetchJson(`${adminUrl}/context/curate`, {
          method: 'POST',
          body: { sessionId, messages, config: { charBudget: charBudget ?? 80000, recentWindowSize: recentWindowSize ?? 8 } },
          timeoutMs: 60_000,
        })
        const curated = result?.messages ?? []
        const meta = result?.meta ?? {}
        if (!result || !Array.isArray(curated)) {
          return { content: [{ type: 'text', text: 'Thalamus curation returned no result. Is the daemon running?' }], isError: true }
        }
        const keptPct = messages.length > 0 ? Math.round((curated.length / messages.length) * 100) : 0
        let out = `## Context Curation Complete\n\n`
        out += `- **Messages:** ${messages.length} -> ${curated.length} (${keptPct}% kept)\n`
        out += `- **Chars:** ${(meta.originalChars ?? 0).toLocaleString()} -> ${(meta.curatedChars ?? 0).toLocaleString()}\n`
        if (meta.compressed) out += `- **Compressed:** ${meta.compressed} messages\n`
        if (meta.deduped) out += `- **Deduped:** ${meta.deduped} messages\n`
        if (meta.dropped) out += `- **Dropped:** ${meta.dropped} messages\n`
        if (meta.durationMs) out += `- **Duration:** ${(meta.durationMs / 1000).toFixed(1)}s\n`
        if (meta.repetitionWarning) out += `\n**WARNING:** ${meta.repetitionWarning}\n`

        const curatedJson = JSON.stringify(curated, (_k, v) => v === undefined ? null : v)
        return { content: [{ type: 'text', text: out }, { type: 'text', text: curatedJson }] }
      }

      case 'context_health': {
        const [stats, active, map] = await Promise.all([
          fetchJson(`${adminUrl}/context/curate/stats`, { timeoutMs: 5000 }).catch(() => null),
          fetchJson(`${adminUrl}/context/active?windowMs=300000`, { timeoutMs: 5000 }).catch(() => null),
          fetchJson(`${adminUrl}/context/map?sessionId=${encodeURIComponent(args.sessionId)}`, { timeoutMs: 5000 }).catch(() => null),
        ])
        let out = `## Context Health (${args.sessionId})\n\n`
        if (active?.sessionId) out += `- **Active session:** ${active.sessionId}\n`
        if (stats) {
          out += `- **Total curations:** ${stats.totalCurations ?? '?'}\n`
          out += `- **Active sessions tracked:** ${stats.activeSessions ?? '?'}\n`
          out += `- **Avg compaction ratio:** ${stats.averageCompressionRatio ?? '?'}\n`
        }
        if (map) {
          const visible = map.visibleCount ?? map.rows?.length ?? 0
          const charsUsed = map.charsUsed ?? 0
          const budget = map.charBudget ?? 80000
          const pct = budget > 0 ? Math.round((charsUsed / budget) * 100) : 0
          out += `- **Context window:** ${pct}% (${(charsUsed / 1000).toFixed(0)}k/${(budget / 1000).toFixed(0)}k chars)\n`
          out += `- **Visible messages:** ${visible}\n`
        }
        if (!active && !stats && !map) {
          out += 'Thalamus has not curated this session yet. Send messages first.\n'
        }
        return { content: [{ type: 'text', text: out }] }
      }

      case 'context_map': {
        const params = new URLSearchParams({ sessionId: args.sessionId })
        if (args.since !== undefined) params.set('since', String(args.since))
        if (args.limit !== undefined) params.set('limit', String(args.limit))
        const result = await fetchJson(`${adminUrl}/context/map?${params.toString()}`, { timeoutMs: 5000 })
        if (!result || !Array.isArray(result.rows)) {
          return { content: [{ type: 'text', text: 'No curated state for this session yet.' }] }
        }
        const { pass, charBudget, charsUsed, rows } = result
        const pct = charBudget > 0 ? Math.round((charsUsed / charBudget) * 100) : 0
        let out = `## Context Map (Pass ${pass}, ${pct}% full)\n\n|Idx|Role|Protected|Score|Chars|Preview\n|---|---|---|---|---|---\n`
        for (const row of rows) {
          const score = row.composite !== undefined ? row.composite.toFixed(2) : '-'
          const pv = (row.preview ?? '').slice(0, 60).replace(/\n/g, ' ')
          out += `|${row.msgIndex}|${row.role}|${row.protectedBy ?? '-'}|${score}|${row.chars}|${pv}\n`
        }
        return { content: [{ type: 'text', text: out }] }
      }

      case 'context_why': {
        const result = await fetchJson(
          `${adminUrl}/context/why?sessionId=${encodeURIComponent(args.sessionId)}&msgIndex=${args.msgIndex}`,
          { timeoutMs: 5000 },
        )
        if (!result) {
          return { content: [{ type: 'text', text: `No score record for message ${args.msgIndex} in session ${args.sessionId}.` }], isError: true }
        }
        const l = result.luminance ?? result
        let out = `## Why Message #${args.msgIndex} Was ${result.kept ? 'Kept' : 'Dropped'}\n\n|Axis|Score|\n|---|---|\n`
        out += `|Novelty|${(l.novelty ?? 0).toFixed(3)}\n`
        out += `|Urgency|${(l.urgency ?? 0).toFixed(3)}\n`
        out += `|Relevance|${(l.relevance ?? 0).toFixed(3)}\n`
        out += `|Source Credibility|${(l.sourceCredibility ?? 0).toFixed(3)}\n`
        out += `|Cognitive Resonance|${(l.cognitiveResonance ?? 0).toFixed(3)}\n`
        out += `|Strategic Importance|${(l.strategicImportance ?? 0).toFixed(3)}\n`
        out += `|**Composite**|**${(l.composite ?? 0).toFixed(3)}**\n`
        if (result.pinned) out += `\nPinned: ${result.pinReason ?? 'yes'}\n`
        if (result.preview) out += `\n**Preview:** ${result.preview.slice(0, 200)}\n`
        return { content: [{ type: 'text', text: out }] }
      }

      case 'context_pin': {
        const result = await fetchJson(`${adminUrl}/context/pin`, {
          method: 'POST',
          body: { sessionId: args.sessionId, target: args.target, reason: args.reason, pinClass: args.pinClass ?? 'decision' },
          timeoutMs: 5000,
        })
        return { content: [{ type: 'text', text: `Pinned "${args.target}" in session ${args.sessionId}. Pin ID: ${result?.pinId ?? 'ok'}` }] }
      }

      case 'context_recall': {
        const result = await fetchJson(
          `${adminUrl}/context/recall?sessionId=${encodeURIComponent(args.sessionId)}&query=${encodeURIComponent(args.query)}&limit=${args.limit ?? 5}`,
          { timeoutMs: 5000 },
        )
        const results = result?.results ?? []
        if (results.length === 0) {
          return { content: [{ type: 'text', text: `No dropped messages matched "${args.query}".` }] }
        }
        let out = `## Recall Results: "${args.query}"\n\n`
        for (const r of results) {
          out += `- **#${r.msgIndex}** | ${r.role} | ${(r.luminance?.composite ?? 0).toFixed(2)} luminance | ${(r.preview ?? '').slice(0, 200).replace(/\n/g, ' ')}\n`
        }
        if (args.reInject && results.length > 0) {
          const best = results[0]
          await fetchJson(`${adminUrl}/context/recall_inject`, {
            method: 'POST',
            body: { sessionId: args.sessionId, content: `[Recall: ${args.query}]\n${best.preview ?? ''}`, role: 'user', label: `hermes-recall:${args.query.slice(0, 40)}` },
            timeoutMs: 5000,
          }).catch(() => {})
          out += `\nTop result queued for re-injection.\n`
        }
        return { content: [{ type: 'text', text: out }] }
      }

      default:
        return { content: [{ type: 'text', text: `Unknown curation tool: ${name}` }], isError: true }
    }
  } catch (err: any) {
    return { content: [{ type: 'text', text: `Curation error: ${err.message ?? String(err)}` }], isError: true }
  }
}
