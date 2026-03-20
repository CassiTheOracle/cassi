/**
 * cassicore-commands.ts
 *
 * Registers /cassicore — CLI-style access to daemon operations.
 *
 *   /cassicore boot   status|start|stop|restart|logs
 *   /cassicore model  list|routing|tiers
 *   /cassicore provider list|health|metrics|reset
 */

import { processor } from './universal-processor.js'
import type { CommandResult } from './universal-processor.js'

const ADMIN_BASE = 'http://localhost:7433'

processor.register({
  name: '/cassicore',
  description: 'CassiCore CLI — daemon boot, model routing, provider operations',
  category: 'intelligence',
  handler: async (args): Promise<CommandResult> => {
    const sub = (args[0] || 'help').toLowerCase()
    const rest = args.slice(1)

    switch (sub) {
      case 'boot':     return handleBoot(rest)
      case 'model':    return handleModel(rest)
      case 'provider': return handleProvider(rest)
      default:
        return {
          text: [
            'Usage: /cassicore <command>',
            '',
            '  boot status|start|stop|restart|logs',
            '  model list|routing|tiers',
            '  provider list|health|metrics|reset <id>',
          ].join('\n'),
        }
    }
  },
})

// ─── boot ────────────────────────────────────────────────────────────────────

async function handleBoot(args: string[]): Promise<CommandResult> {
  const op = (args[0] || 'status').toLowerCase()

  if (op === 'status') {
    try {
      const res = await fetch(`${ADMIN_BASE}/health`)
      if (!res.ok) return { text: '🔴 Daemon unreachable' }
      const data = await res.json() as any
      const uptime = data.uptime ? formatUptime(data.uptime) : 'unknown'
      return {
        text: [
          '🟢 **CassiCore Daemon**',
          `Uptime: ${uptime}`,
          `PID: ${data.pid ?? 'unknown'}`,
          `Sessions: ${data.sessions ?? 'unknown'}`,
          `Admin API: ${ADMIN_BASE}`,
        ].join('\n'),
      }
    } catch {
      return { text: '🔴 Daemon unreachable — is CassiCore running?' }
    }
  }

  if (op === 'logs') {
    // Return last 50 lines from runtime log via bash tool
    try {
      const res = await fetch(`${ADMIN_BASE}/tools/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tool: 'bash', input: { command: 'journalctl -u cassicore -n 50 --no-pager 2>/dev/null || tail -50 /tmp/cassicore.log 2>/dev/null || echo "No log found"' } }),
      })
      const data = await res.json() as any
      const text = extractText(data)
      return { text: text.slice(0, 3800) }
    } catch (err) {
      return { text: `Failed to fetch logs: ${String(err)}` }
    }
  }

  return { text: `Use 'status' or 'logs'. Start/stop/restart require direct shell access.` }
}

// ─── model ───────────────────────────────────────────────────────────────────

async function handleModel(args: string[]): Promise<CommandResult> {
  const op = (args[0] || 'routing').toLowerCase()

  try {
    if (op === 'routing') {
      return executeTool('model_directive', { action: 'get' })
    }

    if (op === 'list') {
      return executeTool('models_list', {})
    }

    if (op === 'tiers') {
      return {
        text: [
          'Named model tiers:',
          '  fast       — Quick tasks, low-latency',
          '  swift      — Fast with decent reasoning',
          '  standard   — Solid mid-range',
          '  balanced   — Primary coding, good reasoning/cost',
          '  premium    — Complex reasoning, high-stakes',
          '  background — Unlimited background tasks',
        ].join('\n'),
      }
    }

    return { text: 'Usage: /cassicore model list|routing|tiers' }
  } catch (err) {
    return { text: `Error: ${String(err)}` }
  }
}

// ─── provider ────────────────────────────────────────────────────────────────

async function handleProvider(args: string[]): Promise<CommandResult> {
  const op = (args[0] || 'list').toLowerCase()
  const providerId = args[1]

  try {
    if (op === 'list' || op === 'health') {
      return executeTool('providers', { includeHealth: true })
    }

    if (op === 'metrics') {
      return executeTool('provider_metrics', providerId ? { providerId } : {})
    }

    if (op === 'reset') {
      if (!providerId) return { text: 'Usage: /cassicore provider reset <provider_id>' }
      return executeTool('provider_config', { action: 'reset', providerId })
    }

    return { text: 'Usage: /cassicore provider list|health|metrics [id]|reset <id>' }
  } catch (err) {
    return { text: `Error: ${String(err)}` }
  }
}

// ─── helpers ─────────────────────────────────────────────────────────────────

function extractText(data: unknown): string {
  if (typeof data === 'string') return data
  if (Array.isArray((data as any)?.content)) {
    return (data as any).content
      .filter((c: any) => c?.type === 'text')
      .map((c: any) => c.text as string)
      .join('\n')
  }
  return JSON.stringify(data, null, 2)
}

async function executeTool(tool: string, input: Record<string, unknown>): Promise<CommandResult> {
  try {
    const res = await fetch(`${ADMIN_BASE}/tools/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tool, input }),
    })
    const data = await res.json() as any
    if (!res.ok) return { text: data?.error ? `Error: ${data.error}` : `Tool ${tool} failed` }
    return { text: extractText(data).slice(0, 3800) }
  } catch (err) {
    return { text: `Error: ${String(err)}` }
  }
}

function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400)
  const h = Math.floor((seconds % 86400) / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const parts: string[] = []
  if (d) parts.push(`${d}d`)
  if (h) parts.push(`${h}h`)
  parts.push(`${m}m`)
  return parts.join(' ')
}
