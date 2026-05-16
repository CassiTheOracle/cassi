import { fetchJson } from '../helpers.js'
import type { ToolDefinition, ToolHandler } from '../types.js'

export const ORCHESTRATION_TOOLS: ToolDefinition[] = [
  {
    name: 'constellation_start',
    description: 'For large complex tasks: spawn a tree of parallel Helix workers coordinated by a Corpus. The Corpus maintains a shared reasoning tree, detects cross-Helix patterns, and synthesizes results. Non-blocking: returns immediately with a sessionId. Use constellation_watch to block until done.',
    inputSchema: {
      type: 'object',
      properties: {
        goal: { type: 'string', description: 'What the Constellation should accomplish.' },
        context: { type: 'string', description: 'Additional context or constraints for every branch.' },
        template: { type: 'string', enum: ['standard', 'research', 'implementation', 'review', 'minimal'], description: 'Helix template for child nodes. Default: standard.' },
        maxHelixes: { type: 'number', description: 'Maximum parallel Helix nodes. Default: 16.' },
        maxDepth: { type: 'number', description: 'Maximum tree depth. Default: 4.' },
        costEffective: { type: 'boolean', description: 'Use cheaper model tiers. Default: false.' },
      },
      required: ['goal'],
    },
  },
  {
    name: 'constellation_watch',
    description: 'Wait for a running Constellation to finish. Polls the SSE event stream with heartbeats and returns the final result including per-branch summaries, Corpus synthesis, and resource usage. Blocks up to the specified timeout.',
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
    name: 'constellation_steer',
    description: 'Guide a running Constellation while it works. Sends a steering directive through the Corpus to child Helix Brainstems -- useful when you see a branch going the wrong direction or want to inject a new constraint mid-flight.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: { type: 'string', description: 'The Constellation session ID.' },
        message: { type: 'string', description: 'What to tell the Constellation.' },
        targetHelixId: { type: 'string', description: 'Target a specific Helix branch (omit to steer all).' },
        urgency: { type: 'string', enum: ['low', 'medium', 'high', 'critical'], description: 'How urgently the directive should be applied. Default: medium.' },
      },
      required: ['sessionId', 'message'],
    },
  },
  {
    name: 'helix_start',
    description: 'For focused single tasks: spawn a Helix session with three equally capable agents (Unity, Yang, Yin) that collaborate. All three postures implement, review, and deliberate. Non-blocking: returns immediately. Use helix_watch to block until completion.',
    inputSchema: {
      type: 'object',
      properties: {
        goal: { type: 'string', description: 'What the Helix should accomplish.' },
        context: { type: 'string', description: 'Additional context or constraints.' },
        sessionId: { type: 'string', description: 'Optional explicit session ID for correlation.' },
        parentSessionId: { type: 'string', description: 'Parent session ID for context distillation.' },
      },
      required: ['goal'],
    },
  },
  {
    name: 'helix_watch',
    description: 'Wait for a running Helix session to complete. Streams SSE events with progress updates and returns the final result including posture summaries, cross-posture findings, dialectic convergence points, and token usage.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: { type: 'string', description: 'The Helix session ID to watch.' },
        timeoutSecs: { type: 'number', description: 'Max seconds to wait. Default: 300.' },
      },
      required: ['sessionId'],
    },
  },
]

async function readAllSSE(sseUrl: string, signal: AbortSignal): Promise<Array<{ type: string; message: string }>> {
  const response = await fetch(sseUrl, { signal })
  if (!response.ok || !response.body) return []
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  const events: Array<{ type: string; message: string }> = []

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const parsed = JSON.parse(line.slice(6))
          const type = parsed.type ?? parsed.event ?? '?'
          events.push({ type, message: (parsed.message ?? type).slice(0, 200) })
        } catch { /* skip malformed */ }
      }
    }
  } finally {
    reader.releaseLock()
  }
  return events
}

const SIGNIFICANT_CONSTELLATION = new Set([
  'corpus:sweep', 'corpus:pattern', 'corpus:intervention',
  'corpus:spawn-evaluated', 'corpus:synthesis',
  'topology:cluster_formed', 'topology:cluster_dissolved',
  'constellation:completed', 'constellation:failed',
])

const SIGNIFICANT_HELIX = new Set([
  'helix:completed', 'helix:failed', 'helix:posture:concluded', 'helix:persisted',
])

export async function executeOrchestrationTool(
  adminUrl: string,
  name: string,
  args: any,
  _hermesDbPath: string,
  _logger: any,
): Promise<{ content: Array<{ type: 'text'; text: string }>; isError?: boolean }> {
  try {
    switch (name) {
      case 'constellation_start': {
        const result = await fetchJson(`${adminUrl}/constellation`, { method: 'POST', body: args ?? {}, timeoutMs: 15_000 })
        if (result?.error) {
          return { content: [{ type: 'text', text: `Constellation failed: ${result.error}` }], isError: true }
        }
        return { content: [{ type: 'text', text: `Constellation started.\nSession: ${result.sessionId ?? '?'}\nGoal: ${(result.goal ?? '').slice(0, 200)}\nStatus: ${result.status ?? 'running'}\n\nUse constellation_watch({ sessionId: "${result.sessionId ?? '?'}" }) to wait for completion.` }] }
      }

      case 'constellation_watch': {
        const sessionId = args.sessionId
        if (!sessionId) return { content: [{ type: 'text', text: 'sessionId is required' }], isError: true }
        const timeoutMs = Math.min(Math.max(args.timeoutSecs ?? 300, 10), 600) * 1000
        const controller = new AbortController()
        const timer = setTimeout(() => controller.abort(), timeoutMs)

        const events = await readAllSSE(`${adminUrl}/constellation/${sessionId}/stream`, controller.signal)
        clearTimeout(timer)

        const significant = events.filter(e => SIGNIFICANT_CONSTELLATION.has(e.type))
        const status = await fetchJson(`${adminUrl}/constellation/${sessionId}`, { timeoutMs: 10_000 }).catch(() => null)
        let out = `## Constellation ${sessionId}\n`
        out += `**Status:** ${status?.status ?? 'completed'}\n`
        if (status?.goal) out += `**Goal:** ${String(status.goal).slice(0, 200)}\n`
        if (status?.durationMs) out += `**Duration:** ${(status.durationMs / 1000).toFixed(1)}s\n`
        if (status?.nodeCount != null) out += `**Nodes:** ${status.nodeCount}\n`
        if (status?.result) {
          const r = String(status.result)
          out += `\n**Result:** ${r.slice(0, 2000)}${r.length > 2000 ? '...' : ''}\n`
        }
        if (significant.length > 0) {
          out += `\n### Events (${significant.length})\n`
          for (const evt of significant.slice(-20)) {
            out += `- ${evt.type}: ${evt.message}\n`
          }
        }
        return { content: [{ type: 'text', text: out }] }
      }

      case 'constellation_steer': {
        await fetchJson(`${adminUrl}/constellation/${args.sessionId}/steer`, {
          method: 'POST',
          body: { message: args.message, targetHelixId: args.targetHelixId, urgency: args.urgency ?? 'medium' },
          timeoutMs: 10_000,
        })
        return { content: [{ type: 'text', text: `Steering directive sent to Constellation ${args.sessionId}.` }] }
      }

      case 'helix_start': {
        const result = await fetchJson(`${adminUrl}/helix`, { method: 'POST', body: args ?? {}, timeoutMs: 15_000 })
        if (result?.error) {
          return { content: [{ type: 'text', text: `Helix failed: ${result.error}` }], isError: true }
        }
        return { content: [{ type: 'text', text: `Helix started.\nSession: ${result.sessionId ?? '?'}\nGoal: ${(result.goal ?? '').slice(0, 200)}\nStatus: ${result.status ?? 'running'}\n\nUse helix_watch({ sessionId: "${result.sessionId ?? '?'}" }) to wait for completion.` }] }
      }

      case 'helix_watch': {
        const sessionId = args.sessionId
        if (!sessionId) return { content: [{ type: 'text', text: 'sessionId is required' }], isError: true }
        const timeoutMs = Math.min(Math.max(args.timeoutSecs ?? 300, 10), 600) * 1000
        const controller = new AbortController()
        const timer = setTimeout(() => controller.abort(), timeoutMs)

        const events = await readAllSSE(`${adminUrl}/helix/${sessionId}/stream`, controller.signal)
        clearTimeout(timer)

        const significant = events.filter(e => SIGNIFICANT_HELIX.has(e.type))
        const status = await fetchJson(`${adminUrl}/helix/${sessionId}`, { timeoutMs: 10_000 }).catch(() => null)
        let out = `## Helix ${sessionId}\n`
        out += `**Status:** ${status?.status ?? 'completed'}\n`
        if (status?.goal) out += `**Goal:** ${String(status.goal).slice(0, 200)}\n`
        if (status?.result) {
          const r = status.result
          if (r.unitySummary) out += `**Summary:** ${r.unitySummary.slice(0, 500)}\n`
          if (r.durationMs) out += `**Duration:** ${(r.durationMs / 1000).toFixed(1)}s\n`
          if (r.dialecticStats) {
            const ds = r.dialecticStats
            out += `**Dialectic:** ${ds.findings} findings, ${ds.challenges} challenges, ${ds.concessions} concessions\n`
          }
        }
        if (significant.length > 0) {
          out += `\n### Events (${significant.length})\n`
          for (const evt of significant.slice(-20)) {
            out += `- ${evt.type}: ${evt.message}\n`
          }
        }
        return { content: [{ type: 'text', text: out }] }
      }

      default:
        return { content: [{ type: 'text', text: `Unknown orchestration tool: ${name}` }], isError: true }
    }
  } catch (err: any) {
    return { content: [{ type: 'text', text: `Orchestration error: ${err.message ?? String(err)}` }], isError: true }
  }
}
