/**
 * Constellation MCP Gateway Tools
 *
 * Exposes Constellation orchestration through the MCP tool interface.
 * Follows the same pattern as helix-tools.ts — proxies to admin API endpoints.
 *
 * Actions: project, status, cancel, jobs, sessions, watch, progress, tree, steer, blackboard, analyze
 */

import type { ILogger } from '../../types/interfaces.js'
import { fetchWithTimeout as fetchWithTimeoutShared, watchViaSSE } from './helpers.js'



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
        costEffective: { type: 'boolean', description: 'When true, posture model tiers are downgraded to cheaper alternatives. Does not affect behavior, only model selection. Default: false.' },
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
    name: 'constellation_topology',
    description: 'Get the live Topology Graph snapshot. Shows spatial Helix positions, gravity-based links between similar Helixes, detected clusters, and pairwise distances. Available while a Constellation is running or from completed results.',
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
          enum: ['findings', 'concerns', 'decisions', 'artifacts', 'requests', 'bugs'],
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
  {
    name: 'constellation_resume',
    description: 'Resume a Constellation from a checkpoint. Reads the tree snapshot, progress, and branch data from the database, recreates the pipeline with the same configuration, injects the checkpoint state into the Corpus, and respawns only the active branches. Non-serializable handles (ModelHandle, Brainstem instances) are recreated fresh for resumed branches.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: { type: 'string', description: 'The Constellation session ID to resume.' },
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
    name: 'constellation_locus_snapshot',
    description: 'Get the Locus (Global Workspace) snapshot — attention state, focus slots, kindling/radiance history, and memory stats. Shows what the constellation is paying attention to and how experiential memory is accumulating.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: { type: 'string', description: 'The Constellation session ID.' },
      },
      required: ['sessionId'],
    },
  },
  {
    name: 'constellation_locus_memories',
    description: 'Get active Locus memories — experiential knowledge accumulated across constellation sweeps. Each memory has content, confidence, phase (provisional/confirmed/consolidated), and confirmation/contradiction counts.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: { type: 'string', description: 'The Constellation session ID (live) or any session ID (archived from DB).' },
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
  {
    name: 'constellation_audit_trail',
    description: 'Get the full event audit trail for a Constellation session. Returns all corpus sweeps, pattern detections, interventions, spawn decisions, topology changes, and Helix lifecycle events in chronological order. Useful for understanding what happened during a run.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: { type: 'string', description: 'The Constellation session ID.' },
        since: { type: 'string', description: 'ISO timestamp — only return events after this time.' },
        limit: { type: 'number', description: 'Max events to return. Default: 100.' },
      },
      required: ['sessionId'],
    },
  },
]

export const CONSTELLATION_TOOL_NAMES = new Set(CONSTELLATION_TOOLS.map(t => t.name))

export function getConstellationTools(): Array<{ name: string; description: string; inputSchema: any }> {
  return [...CONSTELLATION_TOOLS]
}


const fetchWithTimeout = fetchWithTimeoutShared


// WHY: SSE event types that indicate meaningful constellation activity (not just heartbeats)
const SIGNIFICANT_CONSTELLATION_EVENTS = new Set([
  'corpus:sweep', 'corpus:pattern', 'corpus:intervention',
  'corpus:spawn-evaluated', 'corpus:synthesis',
  'topology:cluster_formed', 'topology:cluster_dissolved',
  'constellation:completed',
])



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

      case 'constellation_topology': {
        const res = await fetchWithTimeout(
          `${adminBaseUrl}/constellation/${args.sessionId}/topology`,
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

        return await watchViaSSE({
          sseUrl: `${adminBaseUrl}/constellation/${sessionId}/stream`,
          pollUrl: `${adminBaseUrl}/constellation/${sessionId}`,
          timeoutSecs,
          interestingOnly: true,
          heartbeat,
          logger,
          isSignificant: (type) => SIGNIFICANT_CONSTELLATION_EVENTS.has(type),
          getEventMessage: (type, parsed) => {
            if (type === 'corpus:pattern') return `Pattern: ${parsed?.pattern ?? 'detected'} (${parsed?.severity ?? '?'})`
            if (type === 'corpus:intervention') return `Intervention → ${parsed?.targetHelixId ?? '?'}: ${parsed?.reason ?? ''}`
            if (type === 'corpus:sweep') return `Corpus sweep #${parsed?.sweepCount ?? '?'} (${parsed?.branches ?? '?'} branches, ${parsed?.patterns ?? '?'} patterns)`
            if (type === 'corpus:spawn-evaluated') return `Spawn ${parsed?.approved ? 'approved' : 'rejected'}: ${parsed?.reason ?? ''}`
            if (type === 'corpus:synthesis') return `Synthesis posted`
            if (type.startsWith('topology:')) return `${type}: ${parsed?.clusterId ?? parsed?.helixIdA ?? ''}`
            return parsed?.message ?? type
          },
          buildSnapshot: async (reason, events) => {
            const lines: string[] = []

            let status: any = null
            try {
              const res = await fetchWithTimeout(`${adminBaseUrl}/constellation/${sessionId}`, { timeoutMs: 10_000 })
              if (res.ok) status = await res.json()
            } catch { /* status is optional */ }

            let progress: any = null
            if (!status || status.status === 'running') {
              try {
                const res = await fetchWithTimeout(`${adminBaseUrl}/constellation/${sessionId}/progress`, { timeoutMs: 10_000 })
                if (res.ok) progress = await res.json()
              } catch { /* progress is best-effort */ }
            }

            const sessionStatus = status?.status ?? progress?.status ?? 'unknown'
            lines.push(`## Constellation ${sessionId} — ${sessionStatus}`)
            lines.push(`**Reason returned:** ${reason}`)

            if (progress?.markdown && sessionStatus === 'running') {
              lines.push('')
              lines.push(progress.markdown)
            }

            if (status) {
              if (status.goal) lines.push(`**Goal:** ${String(status.goal).slice(0, 200)}`)
              if (status.durationMs) lines.push(`**Duration:** ${(status.durationMs / 1000).toFixed(1)}s`)
              if (status.nodeCount != null) lines.push(`**Nodes:** ${status.nodeCount}`)
              if (status.result) {
                const r = String(status.result)
                lines.push(`\n**Result:** ${r.slice(0, 1000)}${r.length > 1000 ? '...' : ''}`)
              }
              if (status.error) lines.push(`\n**Error:** ${String(status.error).slice(0, 300)}`)
            }

            if (events.length > 0) {
              lines.push(`\n### Events Since Last Check (${events.length})`)
              for (const evt of events.slice(-30)) {
                lines.push(`- **${evt.type}**: ${evt.message}`)
              }
            }

            return { content: [{ type: 'text', text: lines.join('\n') }] }
          },
        })
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

      case 'constellation_resume': {
        const res = await fetchWithTimeout(
          `${adminBaseUrl}/constellation/${args.sessionId}/resume`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({}),
            timeoutMs: 5000,
          },
        )
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

      case 'constellation_locus_snapshot': {
        const res = await fetchWithTimeout(
          `${adminBaseUrl}/constellation/${args.sessionId}/locus`,
          { timeoutMs: 10_000 },
        )
        if (!res.ok) throw new Error(`Status ${res.status}`)
        return await res.json()
      }

      case 'constellation_locus_memories': {
        const res = await fetchWithTimeout(
          `${adminBaseUrl}/constellation/${args.sessionId}/locus/memories`,
          { timeoutMs: 10_000 },
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

      case 'constellation_audit_trail': {
        const params = new URLSearchParams()
        if (args.since) params.set('since', args.since)
        if (args.limit) params.set('limit', String(args.limit))
        const qs = params.toString() ? `?${params.toString()}` : ''
        const res = await fetchWithTimeout(
          `${adminBaseUrl}/constellation/${args.sessionId}/audit-trail${qs}`,
          { timeoutMs: 15_000 },
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
