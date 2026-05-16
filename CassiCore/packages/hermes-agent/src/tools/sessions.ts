import { openHermesDb, openHermesDbForWrite, listSessions, getSessionDetail, searchSessions, countSessions, pruneSessions, getSessionCounts, getSessionTokenUsage } from '../state-db.js'
import { fetchJson } from '../helpers.js'
import type { ToolDefinition, ToolHandler } from '../types.js'

const HERMES_STATE_DB = process.env.HERMES_STATE_DB || ''

export const SESSION_TOOLS: ToolDefinition[] = [
  {
    name: 'sessions_list',
    description: 'See what sessions exist across your Hermes environment. Browse recent conversations by model, source, and turn count so you can pick the right one to continue, analyze, or clean up.',
    inputSchema: {
      type: 'object',
      properties: {
        limit: { type: 'number', description: 'Max sessions to return. Default: 20.' },
        offset: { type: 'number', description: 'Pagination offset. Default: 0.' },
        source: { type: 'string', description: 'Filter by source platform (cli, telegram, discord, slack, etc.).' },
        includeStats: { type: 'boolean', description: 'Return aggregate stats (totals by source) alongside the list.' },
      },
    },
  },
  {
    name: 'session_get',
    description: 'Continue a prior conversation or investigate past work. Loads the full session including all messages, tool calls, token usage, and child sessions so you know exactly what happened and where you left off.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: { type: 'string', description: 'The session ID to retrieve.' },
        messageLimit: { type: 'number', description: 'Max messages to return. Default: 200.' },
      },
      required: ['sessionId'],
    },
  },
  {
    name: 'session_search',
    description: 'Find where something was discussed when you cannot remember the session. Full-text search across every message in every session using FTS5 so you can jump directly to the relevant conversation.',
    inputSchema: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'Search terms.' },
        limit: { type: 'number', description: 'Max results. Default: 20.' },
      },
      required: ['query'],
    },
  },
  {
    name: 'session_prune',
    description: 'Free disk space or clean up old experiments. Delete sessions older than N days. Always dry-runs first to show what would be removed so you do not lose data accidentally.',
    inputSchema: {
      type: 'object',
      properties: {
        olderThanDays: { type: 'number', description: 'Delete sessions older than this many days. Default: 90.' },
        dryRun: { type: 'boolean', description: 'Preview without deleting. Default: true. Set to false to actually delete.' },
      },
    },
  },
  {
    name: 'session_resume',
    description: "Prepare CassiCore to continue a past session. Loads the session context into CassiCore's lamina system so cross-session recall and cognitive enrichment can work with the full history, not just the current conversation.",
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: { type: 'string', description: 'The session to bring into CassiCore focus.' },
        injectAsContext: { type: 'boolean', description: 'When true, inject session context into CassiCore lamina for enrichment.' },
      },
      required: ['sessionId'],
    },
  },
  {
    name: 'session_active',
    description: 'Check what is currently running before starting something new. Returns the most recent active session\'s metadata, token usage, and status so you know whether you are continuing work or starting fresh.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: { type: 'string', description: 'Optional explicit session ID. When omitted, returns the most recent session.' },
      },
    },
  },
]

export async function executeSessionTool(
  adminUrl: string,
  name: string,
  args: any,
  _hermesDbPath: string,
  _logger: any,
): Promise<{ content: Array<{ type: 'text'; text: string }>; isError?: boolean }> {
  const dbPath = _hermesDbPath || HERMES_STATE_DB

  if (name === 'session_prune') {
    return executePrune(dbPath, args)
  }

  let db: ReturnType<typeof openHermesDb> | null = null
  try {
    db = openHermesDb(dbPath)
  } catch {
    return { content: [{ type: 'text', text: 'Hermes state.db not found or inaccessible. Have you started a session yet?' }], isError: true }
  }

  try {
    switch (name) {
      case 'sessions_list': {
        const limit = args.limit ?? 20
        const offset = args.offset ?? 0
        const source = args.source ?? undefined
        const sessions = listSessions(db, limit, offset, source)
        const total = countSessions(db, source)
        let out = `## Hermes Sessions (${total} total)\n\n`
        if (sessions.length === 0) {
          out += 'No sessions found.\n'
        } else {
          for (const s of sessions) {
            const started = new Date(s.started_at * 1000).toISOString().slice(0, 19).replace('T', ' ')
            const ended = s.ended_at ? new Date(s.ended_at * 1000).toISOString().slice(0, 19).replace('T', ' ') : 'active'
            out += `- **${s.id.slice(0, 12)}** | ${started} | ${s.title ?? '(untitled)'} | ${s.message_count}msgs | ${s.model ?? '?'} | ${s.source}\n`
          }
        }
        if (args.includeStats) {
          const counts = getSessionCounts(db)
          out += '\n### By Source\n'
          for (const c of counts) {
            out += `- ${c.source}: ${c.count} sessions, ${c.total_messages} messages, ${(c.total_tokens / 1000).toFixed(0)}k tokens\n`
          }
        }
        return { content: [{ type: 'text', text: out }] }
      }

      case 'session_get': {
        const detail = getSessionDetail(db, args.sessionId)
        if (!detail) {
          return { content: [{ type: 'text', text: `Session ${args.sessionId} not found.` }], isError: true }
        }
        const started = new Date(detail.started_at * 1000).toISOString().slice(0, 19).replace('T', ' ')
        const ended = detail.ended_at ? new Date(detail.ended_at * 1000).toISOString().slice(0, 19).replace('T', ' ') : 'active'
        const tokens = getSessionTokenUsage(db, detail.id)

        let out = `## Session: ${detail.id}\n`
        out += `- **Title:** ${detail.title ?? '(untitled)'}\n`
        out += `- **Source:** ${detail.source}\n`
        out += `- **Model:** ${detail.model ?? '?'}\n`
        out += `- **Started:** ${started}\n`
        out += `- **Ended:** ${ended}\n`
        out += `- **Status:** ${detail.ended_at ? 'ended (' + (detail.end_reason ?? 'unknown') + ')' : 'active'}\n`
        out += `- **Messages:** ${detail.message_count}\n`
        out += `- **Tool calls:** ${detail.tool_call_count}\n`
        out += `- **Tokens:** ${(tokens.total_tokens / 1000).toFixed(1)}k (${(tokens.input_tokens / 1000).toFixed(1)}k in / ${(tokens.output_tokens / 1000).toFixed(1)}k out)\n`
        if (tokens.estimated_cost_usd) {
          out += `- **Estimated cost:** $${tokens.estimated_cost_usd.toFixed(4)}\n`
        }
        if (detail.parent_session_id) {
          out += `- **Parent session:** ${detail.parent_session_id}\n`
        }
        if (detail.child_sessions.length > 0) {
          out += `- **Child sessions:** ${detail.child_sessions.map(c => c.id.slice(0, 12)).join(', ')}\n`
        }

        const limit = Math.min(args.messageLimit ?? 200, 1000)
        const msgs = detail.messages.slice(0, limit)
        if (msgs.length > 0) {
          out += `\n### Messages (${msgs.length} shown)\n`
          for (const m of msgs) {
            const ts = new Date(m.timestamp * 1000).toISOString().slice(11, 19)
            const preview = (m.content ?? '').slice(0, 300).replace(/\n/g, ' ').trim()
            out += `\`${ts}\` **${m.role}**${m.tool_name ? ` [tool: ${m.tool_name}]` : ''}: ${preview}\n`
          }
          if (detail.messages.length > limit) {
            out += `\n... and ${detail.messages.length - limit} more messages (use messageLimit to increase)\n`
          }
        }
        return { content: [{ type: 'text', text: out }] }
      }

      case 'session_search': {
        const results = searchSessions(db, args.query, args.limit ?? 20)
        if (results.length === 0) {
          return { content: [{ type: 'text', text: `No results for "${args.query}". Try different terms or simpler keywords.` }] }
        }
        let out = `## Search Results: "${args.query}"\n\n`
        for (const r of results) {
          const ts = new Date(r.timestamp * 1000).toISOString().slice(0, 19).replace('T', ' ')
          out += `- **${r.session_id.slice(0, 12)}** | ${ts} | ${r.role}\n  ${r.content_preview}\n\n`
        }
        return { content: [{ type: 'text', text: out }] }
      }

      case 'session_resume': {
        const { sessionId, injectAsContext } = args
        const detail = getSessionDetail(db, sessionId)
        if (!detail) {
          return { content: [{ type: 'text', text: `Session ${sessionId} not found.` }], isError: true }
        }
        if (injectAsContext) {
          const summary = `Resumed session ${sessionId}: ${detail.title ?? 'untitled'}, ${detail.message_count} messages, ${detail.tool_call_count} tool calls, model ${detail.model ?? '?'}`
          await fetchJson(`${adminUrl}/lamina/rethink`, {
            method: 'POST',
            body: { label: 'hermes-resumed-session', content: summary, reason: `hermes-session-resume: ${sessionId}`, agentId: 'hermes-gateway', scope: { kind: 'global' } },
            timeoutMs: 5000,
          }).catch(() => {})
          const lastMessages = detail.messages.slice(-10).map(m => `[${m.role}] ${(m.content ?? '').slice(0, 500)}`).join('\\n')
          await fetchJson(`${adminUrl}/cortex/signal`, {
            method: 'POST',
            body: { sessionId, type: 'perception', region: 'sensory', content: `Resumed Hermes session ${sessionId}. Recent context:\\n${lastMessages}`, tags: ['hermes', 'session-resume'], author: 'hermes-gateway', salience: 0.6 },
            timeoutMs: 5000,
          }).catch(() => {})
        }
        return { content: [{ type: 'text', text: `Session ${sessionId} resumed${injectAsContext ? ' with context injected into CassiCore' : ''}.` }] }
      }

      case 'session_active': {
        if (args.sessionId) {
          const detail = getSessionDetail(db, args.sessionId)
          if (!detail) return { content: [{ type: 'text', text: `Session ${args.sessionId} not found.` }], isError: true }
          const tokens = getSessionTokenUsage(db, detail.id)
          return { content: [{ type: 'text', text: `Session ${detail.id}: ${detail.ended_at ? 'ended' : 'active'}, ${detail.message_count} messages, ${(tokens.total_tokens / 1000).toFixed(1)}k tokens, model ${detail.model ?? '?'}` }] }
        }
        const latest = listSessions(db, 1, 0)
        if (latest.length === 0) {
          return { content: [{ type: 'text', text: 'No sessions found. Start a conversation first.' }] }
        }
        const tokens = getSessionTokenUsage(db, latest[0].id)
        return { content: [{ type: 'text', text: `Active session: ${latest[0].id} (${latest[0].title ?? 'untitled'}), ${latest[0].message_count} messages, ${(tokens.total_tokens / 1000).toFixed(1)}k tokens, model ${latest[0].model ?? '?'}` }] }
      }

      default:
        return { content: [{ type: 'text', text: `Unknown session tool: ${name}` }], isError: true }
    }
  } finally {
    try { db?.close() } catch { /* ignore */ }
  }
}

async function executePrune(dbPath: string, args: any): Promise<{ content: Array<{ type: 'text'; text: string }>; isError?: boolean }> {
  let db: ReturnType<typeof openHermesDbForWrite> | null = null
  try {
    db = openHermesDbForWrite(dbPath)
    const olderThan = args.olderThanDays ?? 90
    const dryRun = args.dryRun !== false
    const result = pruneSessions(db, olderThan, dryRun)
    const mode = dryRun ? 'DRY RUN (set dryRun=false to execute)' : 'EXECUTED'
    return { content: [{ type: 'text', text: `## Session Prune (${mode})\n\nRemoved: ${result.removed}\nKept: ${result.kept}\nThreshold: ${olderThan} days` }] }
  } finally {
    try { db?.close() } catch { /* ignore */ }
  }
}
