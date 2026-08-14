/**
 * Helix Tools Module
 * Three-posture collaborative analysis — Unity, Yang, and Yin as equally capable agents
 */

import { fetchWithTimeout, watchViaSSE } from './helpers.js'
import { formatBlackboardSummary, formatChannelEntries, isSummary } from './blackboard-format.js'
import type { ILogger } from '@cassicore/foundation'


const SIGNIFICANT_HELIX_EVENTS = new Set([
  'helix:completed',
  'helix:failed',
  'helix:posture:concluded',
  'helix:persisted',
])

export const HELIX_TOOLS = [
  {
    name: 'helix_project',
    description: 'Start a Helix session with three equally capable agents (Unity, Yang, Yin) that collaborate. All postures implement, review, and deliberate. Non-blocking: returns immediately with jobId and sessionId. Use helix_watch(sessionId) to block until completion.',
    inputSchema: {
      type: 'object',
      properties: {
        goal: { type: 'string', description: 'The goal or task to implement.' },
        context: { type: 'string', description: 'Additional context or constraints.' },
        sessionId: { type: 'string', description: 'Optional session ID.' },
        parentSessionId: {
          type: 'string',
          description: 'Parent session ID for Phase Zero context distillation. When provided, the session will be briefed with context from the parent conversation.',
        },
      },
      required: ['goal'],
    },
  },
  {
    name: 'helix_status',
    description: 'Check the status of a running Helix job.',
    inputSchema: {
      type: 'object',
      properties: {
        jobId: { type: 'string', description: 'The Helix job ID.' },
      },
      required: ['jobId'],
    },
  },
  {
    name: 'helix_health',
    description: 'Check Helix system health.',
    inputSchema: {
      type: 'object',
      properties: {},
    },
  },
  {
    name: 'helix_jobs',
    description: 'List recent Helix jobs.',
    inputSchema: {
      type: 'object',
      properties: {},
    },
  },
  {
    name: 'helix_watch',
    description: 'Block until a Helix session has new activity, then return a status snapshot. Uses SSE streaming with 15s heartbeats. Returns on significant events (session completed/failed) or timeout.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: { type: 'string', description: 'The Helix session ID to watch.' },
        timeoutSecs: { type: 'number', description: 'Maximum seconds to wait (default: 300, max: 600).' },
      },
      required: ['sessionId'],
    },
  },
  {
    name: 'helix_cancel',
    description: 'Cancel a running Helix session.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: { type: 'string', description: 'The Helix session ID to cancel.' },
      },
      required: ['sessionId'],
    },
  },
  {
    name: 'helix_sessions',
    description: 'List active Helix sessions.',
    inputSchema: {
      type: 'object',
      properties: {},
    },
  },
  {
    name: 'helix_progress',
    description: 'Get live progress report for a running Helix session. Shows per-posture status (Unity/Yang/Yin), work unit count, nudge activity, dialectic stats (Yang↔Yin findings/challenges/concessions), and convergence points.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: { type: 'string', description: 'The Helix session ID to inspect.' },
      },
      required: ['sessionId'],
    },
  },
  {
    name: 'helix_blackboard',
    description: 'Get the Blackboard snapshot for a Helix session. Returns all channels, scratchpad entries, plan, report, and artifact tracking. Defaults to summary mode for compact output. Use summary=false for the full raw snapshot.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: { type: 'string', description: 'The Helix session ID to read the blackboard from.' },
        summary: { type: 'boolean', description: 'Return compact summary instead of full snapshot (default: true).' },
        channel: {
          type: 'string',
          enum: ['findings', 'concerns', 'decisions', 'artifacts', 'requests', 'bugs'],
          description: 'Return only entries from this channel. Overrides summary mode.',
        },
        limit: { type: 'number', description: 'Max entries per channel (when using channel filter).' },
      },
      required: ['sessionId'],
    },
  },
]

export const HELIX_TOOL_NAMES = new Set(HELIX_TOOLS.map(t => t.name))

export function getHelixTools(): Array<{ name: string; description: string; inputSchema: any }> {
  return [...HELIX_TOOLS]
}

export async function executeHelixTool(
  adminBaseUrl: string,
  name: string,
  args: any,
  logger: ILogger,
  heartbeat?: () => void,
): Promise<any> {
  logger.debug('helix-mcp:invoke', { name, args })

  try {
    switch (name) {
      case 'helix_project': {
        const { timeoutMs: _ignored, ...projectArgs } = args ?? {}
        const res = await fetchWithTimeout(`${adminBaseUrl}/helix`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(projectArgs),
          timeoutMs: 5000,
        })
        return await res.json()
      }

      case 'helix_status': {
        const res = await fetchWithTimeout(`${adminBaseUrl}/helix/${args.jobId}`, { timeoutMs: 10000 })
        if (!res.ok) throw new Error(`Status ${res.status}`)
        return await res.json()
      }

      case 'helix_health': {
        const res = await fetchWithTimeout(`${adminBaseUrl}/helix/health`, { timeoutMs: 5000 })
        return await res.json()
      }

      case 'helix_jobs': {
        const res = await fetchWithTimeout(`${adminBaseUrl}/helix/jobs`, { timeoutMs: 5000 })
        return await res.json()
      }

      case 'helix_watch': {
        const sessionId = args?.sessionId
        if (!sessionId) throw new Error('sessionId is required')
        const timeoutSecs = Math.min(Math.max(args?.timeoutSecs ?? 300, 10), 600)

        return await watchViaSSE({
          sseUrl: `${adminBaseUrl}/helix/${sessionId}/stream`,
          pollUrl: `${adminBaseUrl}/helix/${sessionId}/progress`,
          timeoutSecs,
          interestingOnly: true,
          heartbeat,
          logger,
          isSignificant: (type) => SIGNIFICANT_HELIX_EVENTS.has(type),
          getEventMessage: (type, parsed) => parsed?.message ?? type,
          buildSnapshot: async (reason, events) => {
            const lines: string[] = []

            // Fetch job status
            let status: any = null
            try {
              const res = await fetchWithTimeout(`${adminBaseUrl}/helix/${sessionId}`, { timeoutMs: 10_000 })
              if (res.ok) status = await res.json()
            } catch { /* ignore */ }

            // Fetch live progress
            let liveProgress: any = null
            if (!status || status.status === 'running') {
              try {
                const progressRes = await fetchWithTimeout(
                  `${adminBaseUrl}/helix/${sessionId}/progress`,
                  { timeoutMs: 10_000 },
                )
                if (progressRes.ok) liveProgress = await progressRes.json()
              } catch { /* ignore */ }
            }

            const sessionStatus = status?.status ?? 'unknown'
            lines.push(`## Helix Session ${sessionId} — ${sessionStatus}`)
            lines.push(`**Reason returned:** ${reason}`)

            if (liveProgress?.markdown && sessionStatus === 'running') {
              lines.push('')
              lines.push(liveProgress.markdown)
            }

            if (status) {
              if (status.goal) {
                lines.push(`**Goal:** ${String(status.goal).slice(0, 100)}`)
              }
              const result = status.result
              if (result) {
                const totalTokens = (result.tokensUsed?.unity ?? 0) + (result.tokensUsed?.yang ?? 0) + (result.tokensUsed?.yin ?? 0)
                if (totalTokens > 0) {
                  lines.push(
                    `**Tokens:** ${totalTokens.toLocaleString()}` +
                    ` (unity: ${(result.tokensUsed?.unity ?? 0).toLocaleString()}` +
                    `, yang: ${(result.tokensUsed?.yang ?? 0).toLocaleString()}` +
                    `, yin: ${(result.tokensUsed?.yin ?? 0).toLocaleString()})`,
                  )
                }
                if (result.durationMs) {
                  lines.push(`**Duration:** ${(result.durationMs / 1000).toFixed(1)}s`)
                }
                if (result.dialecticStats) {
                  const ds = result.dialecticStats
                  lines.push(`**Dialectic:** ${ds.findings} findings, ${ds.challenges} challenges, ${ds.concessions} concessions, ${ds.convergencePoints} convergence points`)
                }
                if (result.pipelineStats) {
                  const ps = result.pipelineStats
                  lines.push(`**Work:** ${ps.workUnitsProduced} work units, ${ps.nudgesSent} nudges, ${ps.nudgesAcknowledged} acknowledged`)
                }
                if (result.unitySummary) {
                  lines.push(`\n**Unity Summary:** ${result.unitySummary.slice(0, 300)}`)
                }
              }
              if (status.error) {
                lines.push(`\n**Error:** ${String(status.error).slice(0, 200)}`)
              }
            }

            if (events.length > 0) {
              lines.push(`\n### Events Since Last Check (${events.length})`)
              for (const evt of events.slice(-20)) {
                lines.push(`- **${evt.type}**: ${evt.message}`)
              }
            }

            return { content: [{ type: 'text', text: lines.join('\n') }] }
          },
        })
      }

      case 'helix_cancel': {
        const res = await fetchWithTimeout(`${adminBaseUrl}/helix/${args.sessionId}/cancel`, {
          method: 'POST',
          timeoutMs: 5000,
        })
        return await res.json()
      }

      case 'helix_sessions': {
        const res = await fetchWithTimeout(`${adminBaseUrl}/helix/sessions`, { timeoutMs: 5000 })
        return await res.json()
      }

      case 'helix_progress': {
        const res = await fetchWithTimeout(`${adminBaseUrl}/helix/${args.sessionId}/progress`, { timeoutMs: 10000 })
        return await res.json()
      }

      case 'helix_blackboard': {
        const params = new URLSearchParams()
        const wantSummary = args.summary !== false
        if (args.channel) {
          params.set('channel', String(args.channel))
          if (args.limit !== undefined) params.set('limit', String(args.limit))
        } else if (wantSummary) {
          params.set('summary', 'true')
        }
        const qs = params.toString()
        const bbUrl = `${adminBaseUrl}/helix/${args.sessionId}/blackboard${qs ? `?${qs}` : ''}`
        const res = await fetchWithTimeout(bbUrl, { timeoutMs: 10000 })
        const data = await res.json()

        // Format as markdown when using summary or channel mode
        if (res.ok && (qs.includes('summary=true') || qs.includes('channel='))) {
          if (isSummary(data)) {
            return { content: [{ type: 'text', text: formatBlackboardSummary(data) }] }
          }
          if (data.channel && Array.isArray(data.entries)) {
            return { content: [{ type: 'text', text: formatChannelEntries(data.channel, data.entries) }] }
          }
        }
        return data
      }

      default:
        throw new Error(`Unknown Helix tool: ${name}`)
    }
  } catch (error) {
    logger.error('helix-mcp:error', { name, error: String(error) })
    throw error
  }
}
