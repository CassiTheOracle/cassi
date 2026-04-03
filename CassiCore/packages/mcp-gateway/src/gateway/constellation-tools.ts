/**
 * Constellation MCP Gateway Tools
 *
 * Exposes Constellation orchestration through the MCP tool interface.
 * Follows the same pattern as helix-tools.ts — proxies to admin API endpoints.
 *
 * Actions: project, status, cancel, jobs, sessions, watch, progress, tree, steer, blackboard, analyze
 */

import type { ILogger } from '../../types/interfaces.js'



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

  // --- External Corpus Protocol ---

  {
    name: 'constellation_corpus_assume',
    description: 'Assume the Corpus role for a running Constellation. Pauses the internal Corpus LLM and lets the calling agent make strategic decisions (directives, spawn approvals, synthesis) via subsequent tool calls. Only one external agent can hold the Corpus at a time. Auto-releases after heartbeat timeout (default: 5min of inactivity).',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: { type: 'string', description: 'The Constellation session ID.' },
        agentId: { type: 'string', description: 'Identifier for the assuming agent (for attribution and audit).' },
        heartbeatTimeoutMs: { type: 'number', description: 'Inactivity timeout in ms before auto-release. Default: 300000.' },
      },
      required: ['sessionId', 'agentId'],
    },
  },
  {
    name: 'constellation_corpus_release',
    description: 'Release the Corpus role back to the internal Corpus LLM. Pending spawn requests are re-evaluated by the internal Corpus.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: { type: 'string', description: 'The Constellation session ID.' },
        reason: { type: 'string', description: 'Optional reason for releasing.' },
      },
      required: ['sessionId'],
    },
  },
  {
    name: 'constellation_corpus_snapshot',
    description: 'Get a full Corpus state snapshot: reasoning tree, branch assessments, cross-Helix patterns, pending spawn requests, and recent interventions. Use this to understand the current state before making decisions as an external Corpus.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: { type: 'string', description: 'The Constellation session ID.' },
      },
      required: ['sessionId'],
    },
  },
  {
    name: 'constellation_corpus_state',
    description: 'Get the external Corpus protocol state (who holds the lock, heartbeat status, pending requests count).',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: { type: 'string', description: 'The Constellation session ID.' },
      },
      required: ['sessionId'],
    },
  },
  {
    name: 'constellation_corpus_directive',
    description: 'Send a directive to a branch as the external Corpus. The directive is delivered through the Brainstem-mediated intervention model, same as internal Corpus directives.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: { type: 'string', description: 'The Constellation session ID.' },
        targetHelixId: { type: 'string', description: 'The Helix branch to direct.' },
        type: {
          type: 'string',
          enum: ['guidance', 'redirect', 'throttle', 'priority-shift', 'cancel', 'context-inject'],
          description: 'Directive type.',
        },
        content: { type: 'string', description: 'Directive content/message.' },
        urgency: {
          type: 'string',
          enum: ['low', 'medium', 'high', 'critical'],
          description: 'Urgency level. Default: medium.',
        },
      },
      required: ['sessionId', 'targetHelixId', 'type', 'content'],
    },
  },
  {
    name: 'constellation_corpus_spawn_decide',
    description: 'Approve or reject a pending spawn request as the external Corpus. When an external agent holds the Corpus role, spawn requests queue instead of being auto-evaluated.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: { type: 'string', description: 'The Constellation session ID.' },
        requestId: { type: 'string', description: 'The spawn request ID to decide on.' },
        approved: { type: 'boolean', description: 'Whether to approve the spawn.' },
        reason: { type: 'string', description: 'Reason for the decision.' },
        modifiedGoal: { type: 'string', description: 'Optional modified goal for the spawned branch (if approved).' },
      },
      required: ['sessionId', 'requestId', 'approved', 'reason'],
    },
  },
  {
    name: 'constellation_corpus_synthesis',
    description: 'Post a synthesis message visible to all branches as the external Corpus. This appears on the Constellation blackboard under the decisions channel.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: { type: 'string', description: 'The Constellation session ID.' },
        content: { type: 'string', description: 'Synthesis content to post.' },
      },
      required: ['sessionId', 'content'],
    },
  },
]

export const CONSTELLATION_TOOL_NAMES = new Set(CONSTELLATION_TOOLS.map(t => t.name))

export function getConstellationTools(): Array<{ name: string; description: string; inputSchema: any }> {
  return [...CONSTELLATION_TOOLS]
}



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

      // --- External Corpus Protocol ---

      case 'constellation_corpus_assume': {
        const res = await fetchWithTimeout(
          `${adminBaseUrl}/constellation/${args.sessionId}/corpus/assume`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              agentId: args.agentId,
              heartbeatTimeoutMs: args.heartbeatTimeoutMs,
            }),
            timeoutMs: 5000,
          },
        )
        return await res.json()
      }

      case 'constellation_corpus_release': {
        const res = await fetchWithTimeout(
          `${adminBaseUrl}/constellation/${args.sessionId}/corpus/release`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reason: args.reason }),
            timeoutMs: 5000,
          },
        )
        return await res.json()
      }

      case 'constellation_corpus_snapshot': {
        const res = await fetchWithTimeout(
          `${adminBaseUrl}/constellation/${args.sessionId}/corpus/snapshot`,
          { timeoutMs: 10_000 },
        )
        if (!res.ok) throw new Error(`Status ${res.status}`)
        return await res.json()
      }

      case 'constellation_corpus_state': {
        const res = await fetchWithTimeout(
          `${adminBaseUrl}/constellation/${args.sessionId}/corpus/state`,
          { timeoutMs: 5000 },
        )
        if (!res.ok) throw new Error(`Status ${res.status}`)
        return await res.json()
      }

      case 'constellation_corpus_directive': {
        const res = await fetchWithTimeout(
          `${adminBaseUrl}/constellation/${args.sessionId}/corpus/directive`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              targetHelixId: args.targetHelixId,
              type: args.type,
              content: args.content,
              urgency: args.urgency ?? 'medium',
            }),
            timeoutMs: 5000,
          },
        )
        return await res.json()
      }

      case 'constellation_corpus_spawn_decide': {
        const res = await fetchWithTimeout(
          `${adminBaseUrl}/constellation/${args.sessionId}/corpus/spawn-decide`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              requestId: args.requestId,
              approved: args.approved,
              reason: args.reason,
              modifiedGoal: args.modifiedGoal,
            }),
            timeoutMs: 5000,
          },
        )
        return await res.json()
      }

      case 'constellation_corpus_synthesis': {
        const res = await fetchWithTimeout(
          `${adminBaseUrl}/constellation/${args.sessionId}/corpus/synthesis`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: args.content }),
            timeoutMs: 5000,
          },
        )
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
