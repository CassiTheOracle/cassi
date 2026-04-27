import { fetchIntelligence, fetchWithTimeout } from './helpers.js'
import type { ILogger } from '../../types/interfaces.js'

export const LAMINA_CONSOLIDATED_TOOL = {
  name: 'lamina',
  description: 'Lamina operations — labeled, CAS-edited memory blocks for persistent working context. Use for state that should survive across turns: active task description, user model, open hypotheses, session decisions. Each lamina has a stable label and a content_hash used as an optimistic-concurrency token (CAS).\n\nActions:\n- list: enumerate laminae (optionally by owner or session scope)\n- read: fetch the full content of one lamina by label\n- create: declare a new lamina with a fresh label\n- replace: overwrite content. Requires expectedHash from a prior read (CAS); pass null to force.\n- append: race-safe concatenation\n- rethink: full-content replacement with an explicit reason. Owner-exclusive on owner-exclusive laminae.\n\nUse cassi_memory for topological long-term memory and cortex for ephemeral signals.',
  inputSchema: {
    type: 'object',
    properties: {
      action: {
        type: 'string',
        enum: ['list', 'read', 'create', 'replace', 'append', 'rethink', 'metrics'],
        description: 'Lamina operation to perform',
      },
      label: { type: 'string', description: 'Stable lamina label (e.g. "active-task")' },
      content: { type: 'string', description: 'Content body (for create/replace/append/rethink)' },
      owner: { type: 'string', description: 'Owner agent (required for create)' },
      agentId: { type: 'string', description: 'Caller agent identity (required for replace/append/rethink)' },
      expectedHash: { type: 'string', description: 'Current contentHash from a prior read (CAS for replace). Pass null to force.' },
      reason: { type: 'string', description: 'Why this edit happened (required for rethink, recommended otherwise)' },
      ownerExclusive: { type: 'boolean', description: 'For create — only owner can rethink' },
      readOnly: { type: 'boolean', description: 'For create — only owner can mutate at all' },
      pinned: { type: 'boolean', description: 'For create — show first in injection ordering' },
      charLimit: { type: 'number', description: 'For create — maximum byte length' },
      description: { type: 'string', description: 'For create — human description of purpose' },
      tags: { type: 'array', items: { type: 'string' }, description: 'For create — descriptive tags' },
      separator: { type: 'string', description: 'For append — separator inserted between existing and new content (default: newline)' },
      sessionId: { type: 'string', description: 'Scope to a session (optional)' },
      limit: { type: 'number', description: 'For list — max items' },
    },
    required: ['action'],
  },
}

export const LAMINA_CONSOLIDATED_TOOL_NAME = 'lamina'

async function postJSON(baseUrl: string, path: string, body: unknown): Promise<unknown> {
  const response = await fetchWithTimeout(new URL(path, baseUrl), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    const text = await response.text().catch(() => '(unreadable body)')
    // Pass the structured error through — agents need it for CAS retry
    try { return JSON.parse(text) } catch { /* fall through */ }
    throw new Error(`Lamina API error (${response.status}): ${text}`)
  }
  return response.json()
}

function scopeFromArgs(args: Record<string, unknown>) {
  if (args.sessionId) return { kind: 'session', sessionId: String(args.sessionId) }
  return undefined
}

export async function executeLaminaConsolidatedTool(
  baseUrl: string,
  args: Record<string, unknown>,
  logger: ILogger,
): Promise<unknown> {
  const { action } = args
  if (!action) throw new Error('Missing required parameter: action')
  logger.info('Executing lamina tool', { action })

  switch (action) {
    case 'list': {
      const params = new URLSearchParams()
      if (args.owner) params.set('owner', String(args.owner))
      if (args.sessionId) params.set('sessionId', String(args.sessionId))
      if (args.limit) params.set('limit', String(args.limit))
      const qs = params.toString()
      return await fetchIntelligence(baseUrl, `/lamina/list${qs ? '?' + qs : ''}`)
    }

    case 'read': {
      if (!args.label) throw new Error('read requires: label')
      const params = new URLSearchParams({ label: String(args.label) })
      if (args.sessionId) params.set('sessionId', String(args.sessionId))
      return await fetchIntelligence(baseUrl, `/lamina/read?${params.toString()}`)
    }

    case 'create': {
      if (!args.label || !args.owner) throw new Error('create requires: label, owner')
      return await postJSON(baseUrl, '/lamina/create', {
        label: args.label,
        owner: args.owner,
        content: args.content ?? '',
        description: args.description,
        ownerExclusive: args.ownerExclusive,
        readOnly: args.readOnly,
        pinned: args.pinned,
        charLimit: args.charLimit,
        tags: args.tags,
        scope: scopeFromArgs(args),
        reason: args.reason,
      })
    }

    case 'replace': {
      if (!args.label || !args.agentId || args.content === undefined) {
        throw new Error('replace requires: label, agentId, content (and expectedHash for safety)')
      }
      return await postJSON(baseUrl, '/lamina/replace', {
        label: args.label,
        agentId: args.agentId,
        content: args.content,
        expectedHash: args.expectedHash ?? null,
        reason: args.reason,
        scope: scopeFromArgs(args),
      })
    }

    case 'append': {
      if (!args.label || !args.agentId || args.content === undefined) {
        throw new Error('append requires: label, agentId, content')
      }
      return await postJSON(baseUrl, '/lamina/append', {
        label: args.label,
        agentId: args.agentId,
        content: args.content,
        separator: args.separator,
        reason: args.reason,
        scope: scopeFromArgs(args),
      })
    }

    case 'rethink': {
      if (!args.label || !args.agentId || args.content === undefined || !args.reason) {
        throw new Error('rethink requires: label, agentId, content, reason')
      }
      return await postJSON(baseUrl, '/lamina/rethink', {
        label: args.label,
        agentId: args.agentId,
        content: args.content,
        reason: args.reason,
        scope: scopeFromArgs(args),
      })
    }

    case 'metrics':
      return await fetchIntelligence(baseUrl, '/lamina/metrics')

    default:
      throw new Error(`Unknown lamina action: ${action}`)
  }
}

export function getLaminaConsolidatedTool(): typeof LAMINA_CONSOLIDATED_TOOL {
  return LAMINA_CONSOLIDATED_TOOL
}
