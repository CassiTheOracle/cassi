/**
 * MessageFormatter — Converts runtime events into human-readable Telegram messages.
 *
 * Produces two formats:
 *  - Highlight: concise one-liner for the main chat with module identity prefix
 *  - Verbose: detailed multi-line format for per-module topic threads
 *
 * Uses Telegram HTML formatting: <b>, <i>, <code>, <pre>
 */

import type { RuntimeEvent } from '../../../types/events.js'
import type { CuratedEvent } from './event-curator.js'

// Constants

/** Module labels used in highlight messages */
const MODULE_LABELS: Record<string, string> = {
  // Orchestration
  dyad:          'Dyad',
  lumen:         'Lumen',
  fluxTeam:      'FluxTeam',
  triadTeam:     'Triad',
  droneSwarm:    'Swarm',
  multiAgent:    'Agent',

  // Intelligence
  thinker:       'Thinker',
  dialectic:     'Dialectic',
  consciousness: 'Observer',
  memoryDreams:  'Memory',
  adaptive:      'Adaptive',
  heart:         'Heart',
  system:        'System',
  llmCalls:      'LLM',
  blackboard:    'Board',
}

// Helpers

/** Escape HTML special characters for Telegram */
function esc(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

/** Truncate text to max length */
function truncate(text: string, max: number): string {
  if (text.length <= max) return text
  return text.slice(0, max - 20) + '... [truncated]'
}

/** Format duration in ms to human-readable */
function fmtDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`
  return `${(ms / 60_000).toFixed(1)}m`
}

/** Format token count */
function fmtTokens(tokens: number): string {
  if (tokens < 1000) return `${tokens}`
  return `${(tokens / 1000).toFixed(1)}k`
}

/** Format a timestamp as HH:MM:SS */
function fmtTime(ts?: number): string {
  const d = ts ? new Date(ts) : new Date()
  return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

// MessageFormatter

export class MessageFormatter {
  /**
   * Format a curated event for the main chat highlight.
   * Returns a concise one-line(ish) message with module prefix.
   */
  formatHighlight(curated: CuratedEvent): string {
    const e = curated.event as any
    const label = MODULE_LABELS[curated.topicKey ?? 'system'] ?? 'System'
    const type = e.type as string
    const time = fmtTime(e.timestamp)

    // Dispatch to specific formatters
    const body = this.formatHighlightBody(type, e)

    return `<b>[${esc(label)}]</b> ${body}\n<i>${time}</i>`
  }

  /**
   * Format a curated event for a topic thread (verbose).
   * Returns a detailed multi-line message with full context.
   */
  formatVerbose(curated: CuratedEvent): string {
    const e = curated.event as any
    const type = e.type as string
    const time = fmtTime(e.timestamp)

    const body = this.formatVerboseBody(type, e)

    return `<b>${esc(type)}</b>\n${body}\n<i>${time}</i>`
  }


  private formatHighlightBody(type: string, e: any): string {
    if (type === 'lumen:synthesis-complete') {
      return `Recommendation: <b>${esc(e.recommendation ?? 'N/A')}</b> (${e.confidence ?? '?'}% confidence)`
    }
    if (type === 'lumen:started') {
      return `Analysis started: <i>${esc(truncate(e.goal ?? '', 100))}</i>`
    }
    if (type === 'lumen:posture:error') {
      return `Posture error (${esc(e.posture ?? '?')}): ${esc(truncate(String(e.error ?? ''), 100))}`
    }

    if (type === 'dyad:started') {
      return `Pipeline started: <i>${esc(truncate(e.goal ?? '', 100))}</i>`
    }
    if (type === 'dyad:complete') {
      const dur = e.durationMs ? ` in ${fmtDuration(e.durationMs)}` : ''
      return `Pipeline complete${dur}`
    }
    if (type === 'dyad:role:failed') {
      return `Role <b>${esc(e.role ?? '?')}</b> failed: ${esc(truncate(String(e.error ?? ''), 100))}`
    }

    if (type === 'team:started' || type === 'team:completed' || type === 'team:failed') {
      const status = type.split(':')[1]
      const name = e.teamName ?? e.teamId ?? '?'
      return `Team <b>${esc(name)}</b> ${status}`
    }
    if (type === 'team:checkpoint') {
      return `Checkpoint awaiting approval: <i>${esc(truncate(e.description ?? '', 100))}</i>`
    }
    if (type === 'team:budget:warning') {
      return `Budget warning: ${esc(e.message ?? 'approaching limit')}`
    }

    if (type === 'triad-team:created') {
      return `Team created: <i>${esc(truncate(e.goal ?? '', 100))}</i>`
    }
    if (type === 'triad-team:completed') {
      return `Team completed (${e.cellCount ?? '?'} cells)`
    }
    if (type === 'triad-team:failed') {
      return `Team failed: ${esc(truncate(String(e.error ?? ''), 100))}`
    }
    if (type === 'triad-team:checkpoint') {
      return `Checkpoint: <i>${esc(truncate(e.description ?? '', 100))}</i>`
    }

    if (type === 'drone:swarm:completed') {
      const total = e.total ?? '?'
      const succeeded = e.succeeded ?? '?'
      return `Swarm complete: ${succeeded}/${total} succeeded`
    }
    if (type === 'drone:speculative:matched') {
      return `Speculative cache hit: <i>${esc(truncate(e.description ?? '', 80))}</i>`
    }
    if (type === 'drone:autonomous-probe:triggered') {
      return `Autonomous probe: <i>${esc(truncate(e.reason ?? '', 80))}</i>`
    }

    if (type === 'agent:completed') {
      return `Agent completed: <i>${esc(truncate(e.role ?? e.task ?? '', 80))}</i>`
    }
    if (type === 'agent:error') {
      return `Agent error: ${esc(truncate(String(e.error ?? ''), 100))}`
    }
    if (type === 'agent:handoff') {
      return `Handoff: ${esc(e.from ?? '?')} \u2192 ${esc(e.to ?? '?')}`
    }

    if (type === 'thinker:insight-applied') {
      return `Insight: <i>${esc(truncate(e.insight ?? '', 150))}</i>`
    }
    if (type === 'thinker:early-warning') {
      return `Early warning: <i>${esc(truncate(e.warning ?? e.message ?? '', 100))}</i>`
    }
    if (type === 'thinker:self-modified') {
      return `Self-modified: ${esc(e.parameter ?? '?')} = ${esc(String(e.newValue ?? '?'))}`
    }

    if (type === 'dialectic:signal') {
      const conf = e.confidence ? ` (${Math.round(e.confidence * 100)}%)` : ''
      return `${esc(e.signalType ?? 'signal')}${conf}: <i>${esc(truncate(e.content ?? '', 120))}</i>`
    }

    if (type === 'consciousness:anomaly') {
      return `ANOMALY (${esc(e.severity ?? 'medium')}): <i>${esc(truncate(e.description ?? '', 100))}</i>`
    }
    if (type === 'consciousness:insight') {
      return `Insight: <i>${esc(truncate(e.insight ?? '', 120))}</i>`
    }

    if (type === 'adaptive:adaptation-applied') {
      return `Applied: ${esc(e.adaptationType ?? '?')} to ${esc(e.target ?? '?')}`
    }
    if (type === 'adaptive:adaptation-reverted') {
      return `Reverted: ${esc(e.adaptationType ?? '?')} on ${esc(e.target ?? '?')}`
    }

    if (type === 'dreamer:cycle-complete') {
      return `Dream cycle complete (${e.insightsGenerated ?? 0} insights)`
    }
    if (type === 'dreamer:insight') {
      return `Dream insight: <i>${esc(truncate(e.insight ?? '', 120))}</i>`
    }

    if (type === 'provider:request_error') {
      return `Provider error (${esc(e.provider ?? '?')}): ${esc(truncate(String(e.error ?? ''), 100))}`
    }
    if (type === 'provider:rate_limited') {
      return `Rate limited: ${esc(e.provider ?? '?')} (retry after ${e.retryAfterMs ?? '?'}ms)`
    }
    if (type === 'self-healer:repair') {
      return `Self-healed: <i>${esc(truncate(e.description ?? '', 100))}</i>`
    }
    if (type === 'budget:warning' || type === 'budget:exhausted') {
      return `${type === 'budget:exhausted' ? 'BUDGET EXHAUSTED' : 'Budget warning'}: ${esc(e.message ?? '')}`
    }

    if (type === 'session:created') {
      const channel = e.channel ? ` (${esc(e.channel)})` : ''
      return `Session started${channel}: <code>${esc(String(e.sessionId ?? '?').slice(0, 12))}</code>`
    }
    if (type === 'session:ended') {
      return `Session ended: <code>${esc(String(e.sessionId ?? '?').slice(0, 12))}</code>`
    }

    if (type.startsWith('blackboard:')) {
      const channel = e.channel ?? '?'
      return `[${esc(channel)}] ${esc(truncate(e.content ?? '', 100))}`
    }

    return `${esc(type)}`
  }


  private formatVerboseBody(type: string, e: any): string {
    const parts: string[] = []

    if (type === 'lumen:synthesis-complete') {
      if (e.recommendation) parts.push(`<b>Recommendation:</b> ${esc(e.recommendation)}`)
      if (e.confidence) parts.push(`<b>Confidence:</b> ${e.confidence}%`)
      if (e.reasoning) parts.push(`<b>Reasoning:</b>\n${esc(truncate(e.reasoning, 2000))}`)
      if (e.dissent) parts.push(`<b>Dissent:</b>\n${esc(truncate(e.dissent, 500))}`)
      if (e.totalTokens) parts.push(`<b>Tokens:</b> ${fmtTokens(e.totalTokens)}`)
      return parts.join('\n\n') || esc(JSON.stringify(e, null, 2))
    }

    if (type.startsWith('lumen:posture:')) {
      if (e.posture) parts.push(`<b>Posture:</b> ${esc(e.posture)}`)
      if (e.conclusion) parts.push(`<b>Conclusion:</b>\n${esc(truncate(e.conclusion, 2000))}`)
      if (e.tokens) parts.push(`<b>Tokens:</b> ${fmtTokens(e.tokens)}`)
      if (e.error) parts.push(`<b>Error:</b> ${esc(String(e.error))}`)
      return parts.join('\n\n') || this.formatGenericVerbose(e)
    }

    if (type === 'dyad:role:completed' || type === 'dyad:role:failed') {
      if (e.role) parts.push(`<b>Role:</b> ${esc(e.role)}`)
      if (e.summary) parts.push(`<b>Summary:</b>\n${esc(truncate(e.summary, 2000))}`)
      if (e.filesModified?.length) parts.push(`<b>Files modified:</b> ${e.filesModified.length}`)
      if (e.tokens) parts.push(`<b>Tokens:</b> ${fmtTokens(e.tokens)}`)
      if (e.durationMs) parts.push(`<b>Duration:</b> ${fmtDuration(e.durationMs)}`)
      if (e.error) parts.push(`<b>Error:</b> ${esc(truncate(String(e.error), 500))}`)
      return parts.join('\n\n') || this.formatGenericVerbose(e)
    }

    if (type === 'drone:swarm:cognitive-summary') {
      if (e.summary) parts.push(esc(truncate(e.summary, 2000)))
      if (e.resonance) parts.push(`<b>Resonance:</b> ${esc(truncate(JSON.stringify(e.resonance), 500))}`)
      return parts.join('\n\n') || this.formatGenericVerbose(e)
    }

    if (type === 'provider:request_start') {
      if (e.provider) parts.push(`<b>Provider:</b> ${esc(e.provider)}`)
      if (e.model) parts.push(`<b>Model:</b> ${esc(e.model)}`)
      if (e.source) parts.push(`<b>Source:</b> ${esc(e.source)}`)
      if (e.sessionId) parts.push(`<b>Session:</b> <code>${esc(String(e.sessionId).slice(0, 12))}</code>`)
      return parts.join('\n') || this.formatGenericVerbose(e)
    }

    if (type === 'provider:request_end') {
      if (e.provider) parts.push(`<b>Provider:</b> ${esc(e.provider)}`)
      if (e.model) parts.push(`<b>Model:</b> ${esc(e.model)}`)
      if (e.source) parts.push(`<b>Source:</b> ${esc(e.source)}`)
      if (e.inputTokens) parts.push(`<b>Input:</b> ${fmtTokens(e.inputTokens)}`)
      if (e.outputTokens) parts.push(`<b>Output:</b> ${fmtTokens(e.outputTokens)}`)
      if (e.durationMs) parts.push(`<b>Duration:</b> ${fmtDuration(e.durationMs)}`)
      return parts.join('\n') || this.formatGenericVerbose(e)
    }

    if (type === 'thinker:insight-applied') {
      if (e.insight) parts.push(`<b>Insight:</b>\n${esc(truncate(e.insight, 2000))}`)
      if (e.sessionId) parts.push(`<b>Session:</b> <code>${esc(String(e.sessionId).slice(0, 12))}</code>`)
      if (e.confidence) parts.push(`<b>Confidence:</b> ${Math.round(e.confidence * 100)}%`)
      return parts.join('\n\n') || this.formatGenericVerbose(e)
    }

    if (type === 'thinker:strategy-snapshot') {
      if (e.strategy) parts.push(`<pre>${esc(truncate(JSON.stringify(e.strategy, null, 2), 2000))}</pre>`)
      return parts.join('\n\n') || this.formatGenericVerbose(e)
    }

    if (type === 'dialectic:signal') {
      if (e.signalType) parts.push(`<b>Type:</b> ${esc(e.signalType)}`)
      if (e.content) parts.push(`<b>Content:</b>\n${esc(truncate(e.content, 2000))}`)
      if (e.confidence) parts.push(`<b>Confidence:</b> ${Math.round(e.confidence * 100)}%`)
      if (e.source) parts.push(`<b>Source:</b> ${esc(e.source)}`)
      return parts.join('\n\n') || this.formatGenericVerbose(e)
    }

    if (type === 'consciousness:anomaly') {
      if (e.severity) parts.push(`<b>Severity:</b> ${esc(e.severity)}`)
      if (e.description) parts.push(`<b>Description:</b>\n${esc(truncate(e.description, 2000))}`)
      if (e.evidence) parts.push(`<b>Evidence:</b>\n${esc(truncate(JSON.stringify(e.evidence, null, 2), 500))}`)
      return parts.join('\n\n') || this.formatGenericVerbose(e)
    }

    if (type === 'consciousness:observation') {
      if (e.observationType) parts.push(`<b>Type:</b> ${esc(e.observationType)}`)
      if (e.content) parts.push(esc(truncate(e.content, 2000)))
      if (e.signals) parts.push(`<b>Signals:</b> ${esc(truncate(JSON.stringify(e.signals), 500))}`)
      return parts.join('\n\n') || this.formatGenericVerbose(e)
    }

    if (type.startsWith('blackboard:')) {
      if (e.boardName) parts.push(`<b>Board:</b> ${esc(e.boardName)}`)
      if (e.channel) parts.push(`<b>Channel:</b> ${esc(e.channel)}`)
      if (e.author) parts.push(`<b>Author:</b> ${esc(e.author)}`)
      if (e.priority) parts.push(`<b>Priority:</b> ${esc(e.priority)}`)
      if (e.content) parts.push(`\n${esc(truncate(e.content, 2000))}`)
      if (e.tags?.length) parts.push(`<b>Tags:</b> ${e.tags.map((t: string) => esc(t)).join(', ')}`)
      return parts.join('\n') || this.formatGenericVerbose(e)
    }

    if (type.startsWith('cell:')) {
      if (e.cellId) parts.push(`<b>Cell:</b> ${esc(e.cellId)}`)
      if (e.role) parts.push(`<b>Role:</b> ${esc(e.role)}`)
      if (e.phase) parts.push(`<b>Phase:</b> ${esc(e.phase)}`)
      if (e.turn) parts.push(`<b>Turn:</b> ${e.turn}`)
      if (e.tokens) parts.push(`<b>Tokens:</b> ${fmtTokens(e.tokens)}`)
      if (e.signals?.length) parts.push(`<b>Signals:</b> ${e.signals.length} extracted`)
      return parts.join('\n') || this.formatGenericVerbose(e)
    }

    return this.formatGenericVerbose(e)
  }

  private formatGenericVerbose(e: any): string {
    // Remove common noise fields
    const { type, timestamp, ...rest } = e
    const json = JSON.stringify(rest, null, 2)
    if (json.length > 2500) {
      return `<pre>${esc(truncate(json, 2500))}</pre>`
    }
    return `<pre>${esc(json)}</pre>`
  }
}
