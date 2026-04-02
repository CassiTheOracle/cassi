/**
 * Constellation MCP Gateway Tools
 *
 * Exposes Constellation orchestration through the MCP tool interface.
 * Follows the same pattern as helix-tools.ts — proxies to admin API endpoints.
 *
 * Actions: project, status, cancel, jobs, sessions, watch, progress, tree, steer, blackboard, analyze
 */

import type { ILogger } from '../../types/interfaces.js'


// ── Tool Definitions ──────────────────────────────────────────────

export const CONSTELLATION_TOOLS = [
  {
    name: 'constellation_project',
    description: 'Start a new Constellation — a tree of Helix sessions coordinated by a Corpus. The Corpus maintains a shared reasoning tree and detects cross-Helix patterns. Returns a session ID for tracking.',
    inputSchema: {
      type: 'object',
      properties: {
        goal: { type: 'string', description: 'What the Constellation should accomplish.' },
        context: { type: 'string', description: 'Additional context or constraints.' },
        template: {
          type: 'string',
          enum: ['standard', 'research', 'implementation', 'review', 'minimal'],
          description: 'Helix template for child nodes. Default: standard.',
        },
        maxHelixes: { type: 'number', description: 'Maximum number of Helix nodes. Default: 16.' },
        maxDepth: { type: 'number', description: 'Maximum tree depth. Default: 4.' },
      },
      required: ['goal'],
    },
  },
  {
    name: 'constellation_status',
    description: 'Get the status/result of a Constellation job.',
    inputSchema: {
      type: 'object',
      properties: {
        jobId: { type: 'string', description: 'The Constellation job ID.' },
      },
      required: ['jobId'],
    },
  },
  {
    name: 'constellation_cancel',
    description: 'Cancel a running Constellation session.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: { type: 'string', description: 'The Constellation session ID to cancel.' },
      },
      required: ['sessionId'],
    },
  },
  {
    name: 'constellation_sessions',
    description: 'List active Constellation sessions.',
    inputSchema: {
      type: 'object',
      properties: {},
    },
  },
  {
    name: 'constellation_jobs',
    description: 'List recent Constellation jobs.',
    inputSchema: {
      type: 'object',
      properties: {},
    },
  },
  {
    name: 'constellation_progress',
    description: 'Get live progress report for a running Constellation. Shows node count, branch statuses, Corpus sweep count, and cross-Helix pattern detections.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: { type: 'string', description: 'The Constellation session ID.' },
      },
      required: ['sessionId'],
    },
  },
  {
    name: 'constellation_tree',
    description: 'Get the Corpus reasoning tree snapshot. Shows all branches (one per Helix), their annotation steps, scores, patterns, and the Corpus\'s cross-branch analysis. This is how Cassi sees what every Helix is doing.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: { type: 'string', description: 'The Constellation session ID.' },
      },
      required: ['sessionId'],
    },
  },
  {
    name: 'constellation_steer',
    description: 'Send a steering directive through the Corpus to child Helix Brainstems. The Corpus converts it to a CorpusDirective and delivers it through the Brainstem-mediated intervention model.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: { type: 'string', description: 'The Constellation session ID.' },
        message: { type: 'string', description: 'The steering directive text.' },
        targetHelixId: { type: 'string', description: 'Target a specific Helix (optional — omit to steer all).' },
        urgency: {
          type: 'string',
          enum: ['low', 'medium', 'high', 'critical'],
          description: 'Urgency of the directive. Default: medium.',
        },
      },
      required: ['sessionId', 'message'],
    },
  },
  {
    name: 'constellation_watch',
    description: 'Block until a Constellation completes or times out. Returns the final result.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: { type: 'string', description: 'The Constellation session ID to watch.' },
        timeoutSecs: { type: 'number', description: 'Max seconds to wait. Default: 300.' },
      },
      required: ['sessionId'],
    },
  },
  {
    name: 'constellation_blackboard',
    description: 'Get the Constellation-level Blackboard snapshot.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: { type: 'string', description: 'The Constellation session ID.' },
        channel: {
          type: 'string',
          enum: ['findings', 'concerns', 'decisions', 'artifacts', 'requests'],
          description: 'Return only entries from this channel.',
        },
      },
      required: ['sessionId'],
    },
  },
  {
    name: 'constellation_analyze',
    description: 'Deep post-mortem analysis of a completed (or failed) Constellation session. ' +
      'Queries helix.db and constellation.db to produce a structured report covering Corpus health, ' +
      'branch timing, phase detection, idle gaps, reviewer nudges, and known failure pattern detection. ' +
      'Use this after a run to understand why it was slow, what Corpus did, or to diagnose provider issues.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: { type: 'string', description: 'The Constellation session ID to analyze.' },
        depth: {
          type: 'string',
          enum: ['summary', 'timeline', 'full'],
          description: 'summary = diagnosis + stats (default). timeline = adds iteration-by-iteration timeline. full = adds raw store data.',
        },
      },
      required: ['sessionId'],
    },
  },
]

export const CONSTELLATION_TOOL_NAMES = new Set(CONSTELLATION_TOOLS.map(t => t.name))

export function getConstellationTools(): Array<{ name: string; description: string; inputSchema: any }> {
  return [...CONSTELLATION_TOOLS]
}


// ── Executor ──────────────────────────────────────────────────────

async function fetchWithTimeout(
  url: string,
  opts: RequestInit & { timeoutMs?: number } = {},
): Promise<Response> {
  const { timeoutMs = 10_000, ...fetchOpts } = opts
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    return await fetch(url, { ...fetchOpts, signal: controller.signal })
  } finally {
    clearTimeout(timer)
  }
}


export async function executeConstellationTool(
  adminBaseUrl: string,
  name: string,
  args: any,
  logger: ILogger,
  heartbeat?: () => void,
): Promise<any> {
  logger.debug('constellation-mcp:invoke', { name, args })

  try {
    switch (name) {
      case 'constellation_project': {
        const res = await fetchWithTimeout(`${adminBaseUrl}/constellation`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(args ?? {}),
          timeoutMs: 5000,
        })
        return await res.json()
      }

      case 'constellation_status': {
        const res = await fetchWithTimeout(
          `${adminBaseUrl}/constellation/${args.jobId}`,
          { timeoutMs: 10_000 },
        )
        if (!res.ok) throw new Error(`Status ${res.status}`)
        return await res.json()
      }

      case 'constellation_cancel': {
        const res = await fetchWithTimeout(
          `${adminBaseUrl}/constellation/${args.sessionId}/cancel`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({}),
            timeoutMs: 5000,
          },
        )
        return await res.json()
      }

      case 'constellation_sessions': {
        const res = await fetchWithTimeout(`${adminBaseUrl}/constellation/sessions`, { timeoutMs: 5000 })
        return await res.json()
      }

      case 'constellation_jobs': {
        const res = await fetchWithTimeout(`${adminBaseUrl}/constellation/jobs`, { timeoutMs: 5000 })
        return await res.json()
      }

      case 'constellation_progress': {
        const res = await fetchWithTimeout(
          `${adminBaseUrl}/constellation/${args.sessionId}/progress`,
          { timeoutMs: 10_000 },
        )
        if (!res.ok) throw new Error(`Status ${res.status}`)
        return await res.json()
      }

      case 'constellation_tree': {
        const res = await fetchWithTimeout(
          `${adminBaseUrl}/constellation/${args.sessionId}/tree`,
          { timeoutMs: 10_000 },
        )
        if (!res.ok) throw new Error(`Status ${res.status}`)
        return await res.json()
      }

      case 'constellation_steer': {
        const res = await fetchWithTimeout(
          `${adminBaseUrl}/constellation/${args.sessionId}/steer`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              message: args.message,
              targetHelixId: args.targetHelixId,
              urgency: args.urgency ?? 'medium',
            }),
            timeoutMs: 5000,
          },
        )
        return await res.json()
      }

      case 'constellation_watch': {
        const sessionId = args?.sessionId
        if (!sessionId) throw new Error('sessionId is required')
        const timeoutSecs = Math.min(Math.max(args?.timeoutSecs ?? 300, 10), 600)
        const timeoutMs = timeoutSecs * 1000
        const deadline = Date.now() + timeoutMs

        // Poll-based watch (simpler than SSE for initial version)
        while (Date.now() < deadline) {
          heartbeat?.()

          try {
            const res = await fetchWithTimeout(
              `${adminBaseUrl}/constellation/${sessionId}`,
              { timeoutMs: 10_000 },
            )
            if (res.ok) {
              const data = await res.json() as any
              if (data.status !== 'running') {
                return data
              }
            }
          } catch {
            // Ignore poll errors
          }

          await new Promise(r => setTimeout(r, 5000))
        }

        // Final check
        try {
          const res = await fetchWithTimeout(
            `${adminBaseUrl}/constellation/${sessionId}`,
            { timeoutMs: 10_000 },
          )
          if (res.ok) return await res.json()
        } catch { /* ignore */ }

        return { sessionId, status: 'timeout', message: `Watch timed out after ${timeoutSecs}s` }
      }

      case 'constellation_blackboard': {
        const channelParam = args.channel ? `?channel=${args.channel}` : ''
        // WHY: Constellation-level blackboard endpoint deferred — see contributing-todos blackboard (for now, proxy to progress which includes it)
        const res = await fetchWithTimeout(
          `${adminBaseUrl}/constellation/${args.sessionId}/progress${channelParam}`,
          { timeoutMs: 10_000 },
        )
        if (!res.ok) throw new Error(`Status ${res.status}`)
        return await res.json()
      }

      case 'constellation_analyze': {
        const depth = (args.depth as string | undefined) ?? 'summary'
        const res = await fetchWithTimeout(
          `${adminBaseUrl}/constellation/${args.sessionId}/analyze?depth=${depth}`,
          { timeoutMs: 30_000 },
        )
        if (!res.ok) throw new Error(`Status ${res.status}`)
        return await res.json()
      }

      default:
        throw new Error(`Unknown Constellation tool: ${name}`)
    }
  } catch (err) {
    logger.error('constellation-mcp:error', { name, error: String(err) })
    throw err
  }
}
