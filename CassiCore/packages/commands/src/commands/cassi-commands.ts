/**
 * cassi-commands.ts
 *
 * Registers /cassi — the umbrella command for all CassiCore MCP tools.
 *
 *   /cassi                              — list all tools by category
 *   /cassi <category>                   — list tools in category
 *   /cassi <tool_name> [key=val ...]    — invoke any MCP tool
 *   /cassi agent lumen <subcmd> [args]  — Lumen operations
 *   /cassi agent dyad  <subcmd> [args]  — Dyad operations
 *   /cassi agent team  <subcmd> [args]  — Flux team operations
 *
 * Interactive sessions are stored in activeSessions, keyed by sessionId.
 * core/commands.ts reads this map to route non-command messages and
 * /skip, /confirm, /cancel into the active session.
 */

import type { CommandContext, CommandResult } from './universal-processor.js'
import { processor } from './universal-processor.js'
import { InteractiveToolSession, splitForTelegram } from '@cassicore/tools'
import type { ToolDefinition } from '@cassicore/tools'

const ADMIN_BASE = 'http://localhost:7433'

const RESERVED_SUBS = new Set(['agent', 'help'])

const CATEGORY_EMOJIS: Record<string, string> = {
  core:         '🔧',
  session:      '📊',
  memory:       '💾',
  intelligence: '🧠',
  lumen:        '⚡',
  dyad:         '🔬',
  flux:         '🤖',
  config:       '⚙️',
  admin:        '🏗️',
  blackboard:   '📋',
  training:     '📖',
  meta:         '🔍',
}

/** Active interactive tool sessions keyed by sessionId */
export const activeSessions = new Map<string, InteractiveToolSession>()


processor.register({
  name: '/cassi',
  description: 'CassiCore MCP tools — list, invoke any tool, or run agents',
  category: 'intelligence',
  handler: async (args, ctx): Promise<CommandResult> => {
    if (args.length === 0) return handleList()

    const sub = args[0].toLowerCase()
    const rest = args.slice(1)

    if (sub === 'agent') {
      const agentType = rest[0]?.toLowerCase()
      const agentArgs = rest.slice(1)
      switch (agentType) {
        case 'lumen': return handleLumenCommand(agentArgs, ctx)
        case 'dyad':  return handleDyadCommand(agentArgs, ctx)
        case 'team':  return handleTeamCommand(agentArgs, ctx)
        default:
          return { text: 'Usage: /cassi agent lumen|dyad|team <subcommand>' }
      }
    }

    // If sub matches a known category and there are no more args, list that category
    if (!RESERVED_SUBS.has(sub) && rest.length === 0) {
      const catalog = await fetchCatalog()
      if (catalog && sub in catalog.categories) return handleListCategory(sub, catalog)
    }

    // Otherwise treat as tool invocation
    return handleToolInvoke(args, ctx)
  },
})

// These are handled by core/commands.ts when a session is active.
// Registering them here ensures they appear in /help output.

processor.register({
  name: '/skip',
  description: 'Skip optional parameter in active /cassi tool session',
  category: 'intelligence',
  handler: async (_args, ctx): Promise<CommandResult> => {
    const session = activeSessions.get(ctx.sessionId)
    if (!session?.isActive) {
      return { text: 'No active tool session. Use /cassi <tool_name> to start one.' }
    }
    const result = await session.skip()
    if ('prompt' in result) return { text: result.prompt }
    activeSessions.delete(ctx.sessionId)
    return { text: formatOutput(result.result, result.isError) }
  },
})

processor.register({
  name: '/confirm',
  description: 'Confirm pending dangerous tool execution',
  category: 'intelligence',
  handler: async (_args, ctx): Promise<CommandResult> => {
    const session = activeSessions.get(ctx.sessionId)
    if (!session?.isActive) {
      return { text: 'No pending operation to confirm.' }
    }
    const result = await session.confirm()
    activeSessions.delete(ctx.sessionId)
    return { text: formatOutput(result.result, result.isError) }
  },
})

processor.register({
  name: '/cancel',
  description: 'Cancel active /cassi tool session',
  category: 'intelligence',
  handler: async (_args, ctx): Promise<CommandResult> => {
    const session = activeSessions.get(ctx.sessionId)
    if (!session?.isActive) {
      return { text: 'No active tool session to cancel.' }
    }
    activeSessions.delete(ctx.sessionId)
    return { text: session.cancel() }
  },
})


async function handleList(): Promise<CommandResult> {
  const catalog = await fetchCatalog()
  if (!catalog) return { text: 'Failed to fetch tool catalog. Is the daemon running?' }

  const lines: string[] = [
    `📋 **CassiCore MCP Tools** (${catalog.count})`,
    '',
  ]

  for (const [cat, names] of Object.entries(catalog.categories)) {
    if (names.length === 0) continue
    const emoji = CATEGORY_EMOJIS[cat] || '📦'
    lines.push(`${emoji} **${cat.toUpperCase()}** (${names.length})`)
    lines.push(`  ${names.join(', ')}`)
    lines.push('')
  }

  lines.push('Agents: /cassi agent lumen|dyad|team')
  lines.push('Invoke: /cassi <tool_name> [key=val ...]')

  return { text: lines.join('\n') }
}

async function handleListCategory(cat: string, catalog: CatalogResponse): Promise<CommandResult> {
  const toolNames = catalog.categories[cat] ?? []
  const tools = catalog.tools.filter(t => toolNames.includes(t.name))
  if (tools.length === 0) return { text: `No tools in category: ${cat}` }

  const emoji = CATEGORY_EMOJIS[cat] || '📦'
  const lines = [
    `${emoji} **${cat.toUpperCase()} tools** (${tools.length})`,
    '',
    ...tools.map(t => `  **${t.name}** — ${t.description}`),
    '',
    'Invoke: /cassi <tool_name>',
  ]
  return { text: lines.join('\n') }
}


async function handleToolInvoke(args: string[], ctx: CommandContext): Promise<CommandResult> {
  const toolName = args[0]

  // Parse key=value inline params
  const inlineParams: Record<string, string> = {}
  for (const arg of args.slice(1)) {
    const eq = arg.indexOf('=')
    if (eq > 0) {
      inlineParams[arg.slice(0, eq)] = arg.slice(eq + 1)
    }
  }

  const catalog = await fetchCatalog()
  if (!catalog) return { text: 'Failed to fetch tool catalog.' }

  const toolDef = catalog.tools.find(t => t.name === toolName)
  if (!toolDef) {
    return {
      text: [
        `Unknown tool: **${toolName}**`,
        'Use /cassi to list available tools.',
      ].join('\n'),
    }
  }

  const session = new InteractiveToolSession(toolName, toolDef as ToolDefinition)
  const result = await session.start(Object.keys(inlineParams).length > 0 ? inlineParams : undefined)

  if ('prompt' in result) {
    activeSessions.set(ctx.sessionId, session)
    return { text: result.prompt }
  }

  // Executed immediately — no need to store session
  return { text: formatOutput(result.result, result.isError) }
}


async function handleLumenCommand(args: string[], ctx: CommandContext): Promise<CommandResult> {
  const sub = (args[0] || 'help').toLowerCase()
  const rest = args.slice(1)

  switch (sub) {
    case 'start': {
      const goal = rest.join(' ')
      if (!goal) return { text: 'Usage: /cassi agent lumen start <goal>' }
      return callTool('lumen_project', { goal }, ctx)
    }
    case 'status':  return callTool('lumen_status', { jobId: rest[0] }, ctx)
    case 'watch':   return callTool('lumen_watch', { sessionId: rest[0] }, ctx)
    case 'cancel':  return callTool('lumen_cancel', { sessionId: rest[0] }, ctx)
    case 'jobs':    return callTool('lumen_jobs', {}, ctx)
    case 'sessions': return callTool('lumen_sessions', {}, ctx)
    case 'health':  return callTool('lumen_health', {}, ctx)
    case 'messages': return callTool('lumen_messages', { sessionId: rest[0] }, ctx)
    case 'postures': return callTool('lumen_postures', { sessionId: rest[0] }, ctx)
    case 'tool-calls': return callTool('lumen_tool_calls', { sessionId: rest[0] }, ctx)
    case 'events':  return callTool('lumen_events', { sessionId: rest[0] }, ctx)
    case 'blackboard': return callTool('lumen_blackboard', { sessionId: rest[0] }, ctx)
    case 'progress': return callTool('lumen_progress', { sessionId: rest[0] }, ctx)
    default:
      return {
        text: [
          'Lumen agent commands:',
          '  /cassi agent lumen start <goal>       — start dialectic analysis',
          '  /cassi agent lumen watch <session_id> — stream until completion',
          '  /cassi agent lumen status <job_id>    — check job status',
          '  /cassi agent lumen cancel <session_id>',
          '  /cassi agent lumen jobs               — list recent jobs',
          '  /cassi agent lumen sessions           — list persisted sessions',
          '  /cassi agent lumen health',
          '  /cassi agent lumen messages <id>',
          '  /cassi agent lumen postures <id>',
          '  /cassi agent lumen tool-calls <id>',
          '  /cassi agent lumen events <id>',
          '  /cassi agent lumen blackboard <id>',
          '  /cassi agent lumen progress <id>',
        ].join('\n'),
      }
  }
}


async function handleDyadCommand(args: string[], ctx: CommandContext): Promise<CommandResult> {
  const sub = (args[0] || 'help').toLowerCase()
  const rest = args.slice(1)

  switch (sub) {
    case 'start': {
      const goal = rest.join(' ')
      if (!goal) return { text: 'Usage: /cassi agent dyad start <goal>' }
      return callTool('dyad_project', { goal }, ctx)
    }
    case 'status':   return callTool('dyad_status', { jobId: rest[0] }, ctx)
    case 'watch':    return callTool('dyad_watch', { sessionId: rest[0] }, ctx)
    case 'cancel':   return callTool('dyad_cancel', { sessionId: rest[0] }, ctx)
    case 'jobs':     return callTool('dyad_jobs', {}, ctx)
    case 'sessions': return callTool('dyad_sessions', {}, ctx)
    case 'health':   return callTool('dyad_health', {}, ctx)
    case 'progress': return callTool('dyad_progress', { sessionId: rest[0] }, ctx)
    case 'messages': return callTool('dyad_messages', { sessionId: rest[0] }, ctx)
    case 'tool-calls': return callTool('dyad_tool_calls', { sessionId: rest[0] }, ctx)
    case 'events':   return callTool('dyad_events', { sessionId: rest[0] }, ctx)
    case 'blackboard': return callTool('dyad_blackboard', { sessionId: rest[0] }, ctx)
    default:
      return {
        text: [
          'Dyad agent commands:',
          '  /cassi agent dyad start <goal>        — start implementation pipeline',
          '  /cassi agent dyad watch <session_id>  — stream until completion',
          '  /cassi agent dyad status <job_id>     — check job status',
          '  /cassi agent dyad cancel <session_id>',
          '  /cassi agent dyad progress <id>       — live progress report',
          '  /cassi agent dyad jobs                — list recent jobs',
          '  /cassi agent dyad sessions',
          '  /cassi agent dyad health',
          '  /cassi agent dyad messages <id>',
          '  /cassi agent dyad tool-calls <id>',
          '  /cassi agent dyad events <id>',
          '  /cassi agent dyad blackboard <id>',
        ].join('\n'),
      }
  }
}


async function handleTeamCommand(args: string[], ctx: CommandContext): Promise<CommandResult> {
  const sub = (args[0] || 'help').toLowerCase()
  const rest = args.slice(1)

  switch (sub) {
    case 'start':
    case 'create': {
      const flags: Record<string, string> = {}
      const goalParts: string[] = []
      for (let i = 0; i < rest.length; i++) {
        if (rest[i].startsWith('--') && i + 1 < rest.length) {
          flags[rest[i].slice(2)] = rest[++i]
        } else {
          goalParts.push(rest[i])
        }
      }
      const goal = goalParts.join(' ')
      if (!goal) return { text: 'Usage: /cassi agent team start <goal> [--budget <tokens>] [--cells <n>]' }
      const body: Record<string, unknown> = { goal, sessionId: ctx.sessionId }
      if (flags.budget)  body.maxTokens = parseInt(flags.budget, 10)
      if (flags.cells)   body.maxCells  = parseInt(flags.cells, 10)
      if (flags.timeout) body.maxDurationMs = parseInt(flags.timeout, 10) * 60_000
      if (flags.model)   body.model     = flags.model
      if (flags.provider) body.provider = flags.provider
      return adminPost('/teams', body)
    }
    case 'status':
    case 's': {
      const q = rest[0] ? `?teamId=${encodeURIComponent(rest[0])}` : ''
      return adminGet(`/teams/status${q}`)
    }
    case 'list':
    case 'ls':   return adminGet('/teams')
    case 'tree': {
      const q = rest[0] ? `?teamId=${encodeURIComponent(rest[0])}` : ''
      return adminGet(`/teams/tree${q}`)
    }
    case 'pause':
    case 'resume':
    case 'cancel':
    case 'stop':
      return adminPost(`/teams/${sub === 'stop' ? 'cancel' : sub}`, { teamId: rest[0] || '' })
    case 'checkpoints':
    case 'cp': {
      const q = rest[0] ? `?teamId=${encodeURIComponent(rest[0])}` : ''
      return adminGet(`/teams/checkpoints${q}`)
    }
    case 'approve':
    case 'reject':
    case 'steer': {
      const cpId = rest[0]
      if (!cpId) return { text: `Usage: /cassi agent team ${sub} <checkpoint_id> [message]` }
      const message = rest.slice(1).join(' ') || undefined
      return adminPost(`/teams/checkpoints/${encodeURIComponent(cpId)}`, { action: sub, message })
    }
    case 'inspect': {
      const q = rest[0] ? `?teamId=${encodeURIComponent(rest[0])}` : ''
      return adminGet(`/teams/inspect${q}`)
    }
    default:
      return {
        text: [
          'Team agent commands:',
          '  /cassi agent team start <goal>          — start a flux team',
          '  /cassi agent team status [team_id]      — show status',
          '  /cassi agent team list                  — list all teams',
          '  /cassi agent team tree [team_id]        — cell hierarchy',
          '  /cassi agent team pause|resume|cancel [id]',
          '  /cassi agent team checkpoints [team_id] — pending checkpoints',
          '  /cassi agent team approve <cp_id> [msg]',
          '  /cassi agent team reject  <cp_id> [msg]',
          '  /cassi agent team steer   <cp_id> <instructions>',
          '  /cassi agent team inspect [team_id]',
        ].join('\n'),
      }
  }
}


interface CatalogTool {
  name: string
  description: string
  inputSchema: unknown
  category: string
}

interface CatalogResponse {
  tools: CatalogTool[]
  categories: Record<string, string[]>
  count: number
}

/**
 * @dep callers: handleList (commands/cassi-commands.ts), handleToolInvoke (commands/cassi-commands.ts), cassi-commands.ts (commands/cassi-commands.ts)
 * @dep module: Commands
 * @dep risk: LOW | 3 callers, 0 flows, 1 module
 */

async function fetchCatalog(): Promise<CatalogResponse | null> {
  try {
    const res = await fetch(`${ADMIN_BASE}/tools/catalog`)
    if (!res.ok) return null
    return await res.json() as CatalogResponse
  } catch {
    return null
  }
}

/**
 * @dep callers: handleLumenCommand (commands/cassi-commands.ts), handleDyadCommand (commands/cassi-commands.ts), main (scripts/serena-e2e-test.js), main (scripts/serena-apply.js), serenaReadFile (core/tools/serena-mcp-client.ts) [+8]
 * @dep calls: formatOutput, extractText
 * @dep module: Commands
 * @dep risk: CRITICAL | 13 callers, 0 flows, 1 module
 */

async function callTool(
  name: string,
  input: Record<string, unknown>,
  _ctx: CommandContext,
): Promise<CommandResult> {
  // Remove undefined values
  const cleanInput: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(input)) {
    if (v !== undefined && v !== null && v !== '') cleanInput[k] = v
  }
  try {
    const res = await fetch(`${ADMIN_BASE}/tools/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tool: name, input: cleanInput }),
    })
    if (!res.ok) {
      const txt = await res.text()
      return { text: `Tool ${name} failed (${res.status}): ${txt}` }
    }
    const data = await res.json() as any
    const text = extractText(data)
    return { text: formatOutput(text, data?.isError === true) }
  } catch (err) {
    return { text: `Error calling ${name}: ${String(err)}` }
  }
}

async function adminGet(path: string): Promise<CommandResult> {
  try {
    const res = await fetch(`${ADMIN_BASE}${path}`)
    const data = await res.json() as any
    if (data?.error) return { text: `Error: ${data.error}` }
    return { text: formatOutput(JSON.stringify(data, null, 2), false) }
  } catch (err) {
    return { text: `Request failed: ${String(err)}` }
  }
}

async function adminPost(path: string, body: unknown): Promise<CommandResult> {
  try {
    const res = await fetch(`${ADMIN_BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    const data = await res.json() as any
    if (data?.error) return { text: `Error: ${data.error}` }
    return { text: formatOutput(JSON.stringify(data, null, 2), false) }
  } catch (err) {
    return { text: `Request failed: ${String(err)}` }
  }
}

function extractText(data: unknown): string {
  if (typeof data === 'string') return data
  if (Array.isArray((data as any)?.content)) {
    return (data as any).content
      .filter((c: any) => c?.type === 'text')
      .map((c: any) => c.text as string)
      .join('\n')
  }
  if (typeof (data as any)?.text === 'string') return (data as any).text
  return JSON.stringify(data, null, 2)
}

/**
 * @dep callers: handleToolInvoke (commands/cassi-commands.ts), callTool (commands/cassi-commands.ts), adminGet (commands/cassi-commands.ts), adminPost (commands/cassi-commands.ts), cassi-commands.ts (commands/cassi-commands.ts)
 * @dep calls: splitForTelegram
 * @dep module: Commands
 * @dep risk: MEDIUM | 5 callers, 0 flows, 1 module
 */

function formatOutput(text: string, isError: boolean): string {
  const prefix = isError ? '❌ ' : ''
  const chunks = splitForTelegram(`${prefix}${text}`)
  // For command results, return first chunk only — multi-part handled by dispatcher
  return chunks[0]
}
