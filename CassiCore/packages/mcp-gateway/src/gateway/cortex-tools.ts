import { fetchIntelligence, fetchWithTimeout } from './helpers.js'
import type { ILogger } from '../../types/interfaces.js'

export const CORTEX_CONSOLIDATED_TOOL = {
  name: 'cortex',
  description: 'Cortex operations — post signals, read working memory, search, attend, and inspect affect state. The cortex is CassiCore\'s self-organizing working memory with 6 regions (sensory, association, executive, motor, limbic, monitor) and activation dynamics.\n\nUse this tool for ephemeral cognitive signals during task execution. For persistent board entries that survive across sessions, use cassi_memory with board_* actions instead.\n\nCommon actions: signal (post a new signal), read (get active signals), search (find signals by content/type/tags), attend (boost a signal\'s activation).',
  inputSchema: {
    type: 'object',
    properties: {
      action: {
        type: 'string',
        enum: ['signal', 'read', 'search', 'attend', 'stats', 'sessions', 'affect'],
        description: 'Cortex operation to perform',
      },
      region: {
        type: 'string',
        description: 'Cortex region: sensory, association, executive, motor, limbic, monitor',
      },
      type: {
        type: 'string',
        enum: ['perception', 'association', 'concern', 'decision', 'action', 'request', 'anomaly', 'insight'],
        description: 'Signal type (required for signal action)',
      },
      content: {
        type: 'string',
        description: 'Signal content text (required for signal action, optional filter for search)',
      },
      author: {
        type: 'string',
        description: 'Signal author (required for signal action, optional filter for search)',
      },
      salience: {
        type: 'number',
        description: 'Signal salience 0-1 (for signal action, default 0.5)',
      },
      valence: {
        type: 'number',
        description: 'Emotional valence -1 to 1 (for signal action)',
      },
      confidence: {
        type: 'number',
        description: 'Confidence 0-1 (for signal action)',
      },
      tags: {
        type: 'string',
        description: 'Comma-separated tags (for signal action as array, for search as filter)',
      },
      sessionId: {
        type: 'string',
        description: 'Session ID scope (for signal, read, search actions)',
      },
      signalId: {
        type: 'string',
        description: 'Signal ID (required for attend action)',
      },
      signalState: {
        type: 'string',
        description: 'Signal state filter for search: active, fading, consolidated, decayed',
      },
      limit: {
        type: 'number',
        description: 'Maximum results to return (default varies by action)',
      },
    },
    required: ['action'],
  },
}

export const CORTEX_CONSOLIDATED_TOOL_NAME = 'cortex'

async function postJSON(baseUrl: string, path: string, body: unknown): Promise<unknown> {
  const response = await fetchWithTimeout(new URL(path, baseUrl), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    const text = await response.text().catch(() => '(unreadable body)')
    throw new Error(`Admin API error (${response.status}): ${text}`)
  }
  return response.json()
}

export async function executeCortexConsolidatedTool(
  baseUrl: string,
  args: Record<string, unknown>,
  logger: ILogger,
): Promise<unknown> {
  const { action, ...rest } = args

  if (!action) throw new Error('Missing required parameter: action')

  logger.info('Executing cortex tool', { action })

  if (action === 'signal') {
    if (!rest.region || !rest.type || !rest.content || !rest.author) {
      throw new Error('signal action requires: region, type, content, author')
    }
    const body: Record<string, unknown> = {
      region: rest.region,
      type: rest.type,
      content: rest.content,
      author: rest.author,
    }
    if (rest.salience !== undefined) body.salience = rest.salience
    if (rest.valence !== undefined) body.valence = rest.valence
    if (rest.confidence !== undefined) body.confidence = rest.confidence
    if (rest.sessionId !== undefined) body.sessionId = rest.sessionId
    if (rest.tags) {
      body.tags = typeof rest.tags === 'string'
        ? (rest.tags as string).split(',').map(t => t.trim())
        : rest.tags
    }

    return await postJSON(baseUrl, '/cortex/signal', body)
  }

  if (action === 'read') {
    const params = new URLSearchParams()
    if (rest.region) params.set('regions', String(rest.region))
    if (rest.type) params.set('types', String(rest.type))
    if (rest.sessionId) params.set('sessionId', String(rest.sessionId))
    if (rest.limit) params.set('limit', String(rest.limit))
    const qs = params.toString()
    return await fetchIntelligence(baseUrl, `/cortex/active${qs ? '?' + qs : ''}`)
  }

  if (action === 'search') {
    const params = new URLSearchParams()
    if (rest.region) params.set('region', String(rest.region))
    if (rest.type) params.set('type', String(rest.type))
    if (rest.signalState) params.set('state', String(rest.signalState))
    if (rest.author) params.set('author', String(rest.author))
    if (rest.tags) params.set('tags', String(rest.tags))
    if (rest.sessionId) params.set('sessionId', String(rest.sessionId))
    if (rest.content) params.set('content', String(rest.content))
    if (rest.limit) params.set('limit', String(rest.limit))
    const qs = params.toString()
    return await fetchIntelligence(baseUrl, `/cortex/signals/search${qs ? '?' + qs : ''}`)
  }

  if (action === 'attend') {
    if (!rest.signalId) throw new Error('attend action requires: signalId')
    return await postJSON(baseUrl, '/cortex/attend', { signalId: rest.signalId })
  }

  if (action === 'stats') {
    return await fetchIntelligence(baseUrl, '/cortex/stats')
  }

  if (action === 'sessions') {
    return await fetchIntelligence(baseUrl, '/cortex/sessions')
  }

  if (action === 'affect') {
    return await fetchIntelligence(baseUrl, '/cortex/affect')
  }

  throw new Error(`Unknown cortex action: ${action}. Valid: signal, read, search, attend, stats, sessions, affect`)
}

export function getCortexConsolidatedTool(): typeof CORTEX_CONSOLIDATED_TOOL {
  return CORTEX_CONSOLIDATED_TOOL
}
