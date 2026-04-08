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
  // New consolidated topics (2026-04 redesign)
  constellation: 'Constellation',
  intelligence:  'Intelligence',
  memory:        'Memory',
  meditation:    'Meditation',
  system:        'System',
  sessions:      'Sessions',
}

// Helpers

/** Escape HTML special characters for Telegram */
/**
 * @dep callers: formatHighlight (core/intelligence/cognitive-feed/message-formatter.ts), formatVerbose (core/intelligence/cognitive-feed/message-formatter.ts), formatHighlightBody (core/intelligence/cognitive-feed/message-formatter.ts), formatVerboseBody (core/intelligence/cognitive-feed/message-formatter.ts), formatGenericVerbose (core/intelligence/cognitive-feed/message-formatter.ts) [+2]
 * @dep flows: Init → Esc (5/5)
 * @dep module: Cognitive-feed
 * @dep risk: HIGH | 7 callers, 1 flow, 1 module
 */

function esc(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

/** Truncate text to max length */
/**
 * @dep callers: formatHighlightBody (core/intelligence/cognitive-feed/message-formatter.ts), formatVerboseBody (core/intelligence/cognitive-feed/message-formatter.ts), formatGenericVerbose (core/intelligence/cognitive-feed/message-formatter.ts), formatBatchDigest (core/intelligence/cognitive-feed/message-formatter.ts), formatHighlightDigest (core/intelligence/cognitive-feed/message-formatter.ts)
 * @dep flows: Init → Truncate (5/5)
 * @dep module: Cognitive-feed
 * @dep risk: MEDIUM | 5 callers, 1 flow, 1 module
 */

function truncate(text: unknown, max: number): string {
  const str = String(text ?? '')
  if (str.length <= max) return str
  return str.slice(0, max - 20) + '... [truncated]'
}

/** Format duration in ms to human-readable */
/**
 * @dep callers: formatHighlightBody (core/intelligence/cognitive-feed/message-formatter.ts), formatVerboseBody (core/intelligence/cognitive-feed/message-formatter.ts)
 * @dep module: Cognitive-feed
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

function fmtDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`
  return `${(ms / 60_000).toFixed(1)}m`
}

/** Format token count */
/**
 * @dep callers: formatHighlightBody (core/intelligence/cognitive-feed/message-formatter.ts), formatVerboseBody (core/intelligence/cognitive-feed/message-formatter.ts)
 * @dep flows: Init → FmtTokens (5/5)
 * @dep module: Cognitive-feed
 * @dep risk: LOW | 2 callers, 1 flow, 1 module
 */

function fmtTokens(tokens: number): string {
  if (tokens < 1000) return `${tokens}`
  return `${(tokens / 1000).toFixed(1)}k`
}

/** Format a timestamp as HH:MM:SS */
/**
 * @dep callers: formatHighlight (core/intelligence/cognitive-feed/message-formatter.ts), formatVerbose (core/intelligence/cognitive-feed/message-formatter.ts), formatBatchDigest (core/intelligence/cognitive-feed/message-formatter.ts), formatHighlightDigest (core/intelligence/cognitive-feed/message-formatter.ts)
 * @dep flows: Init → FmtTime (4/4)
 * @dep module: Cognitive-feed
 * @dep risk: MEDIUM | 4 callers, 1 flow, 1 module
 */

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
    if (type === 'lumen:completed') {
      const conf = e.confidence ? ` (${Math.round(e.confidence * 100)}%)` : ''
      const dur = e.durationMs ? ` in ${fmtDuration(e.durationMs)}` : ''
      return `Analysis complete${dur}: <b>${esc(e.recommendation ?? 'N/A')}</b>${conf}`
    }
    if (type === 'lumen:posture:error') {
      return `Posture error (${esc(e.posture ?? '?')}): ${esc(truncate(String(e.error ?? ''), 100))}`
    }

    // Lumen dialectic flow highlights
    if (type === 'lumen:dialectic:executive-injection') {
      return `Executive context injection → ${esc(e.target ?? 'both')}: <i>${esc(truncate(e.content ?? '', 100))}</i>`
    }
    if (type === 'lumen:dialectic:executive-steering') {
      return `Executive steering → ${esc(e.target ?? 'both')}: <i>${esc(truncate(e.instruction ?? '', 100))}</i>`
    }

    if (type === 'dyad:started') {
      return `Pipeline started: <i>${esc(truncate(e.goal ?? '', 100))}</i>`
    }
    if (type === 'dyad:completed') {
      const dur = e.durationMs ? ` in ${fmtDuration(e.durationMs)}` : ''
      const score = e.qualityScore ? ` (quality: ${Math.round(e.qualityScore * 100)}%)` : ''
      return `Pipeline complete${dur}${score}`
    }
    if (type === 'dyad:failed') {
      const dur = e.durationMs ? ` after ${fmtDuration(e.durationMs)}` : ''
      return `Pipeline failed${dur}: ${esc(truncate(String(e.error ?? ''), 100))}`
    }
    if (type === 'dyad:role:failed') {
      return `Role <b>${esc(e.role ?? '?')}</b> failed: ${esc(truncate(String(e.error ?? ''), 100))}`
    }

    // Dyad work stream highlights
    if (type === 'dyad:quality-assessment') {
      const score = e.overallScore != null ? ` (${Math.round(e.overallScore * 10)}/10)` : ''
      return `Quality assessment${score}: <i>${esc(truncate(e.assessment ?? '', 100))}</i>`
    }

    if (type === 'team:started') {
      const goal = e.goal ? `: <i>${esc(truncate(e.goal, 100))}</i>` : ''
      return `Team started${goal}`
    }
    if (type === 'team:completed') {
      const dur = e.durationMs ? ` in ${fmtDuration(e.durationMs)}` : ''
      const tokens = e.totalTokens ? ` (${fmtTokens(e.totalTokens)} tokens)` : ''
      return `Team completed${dur}${tokens}`
    }
    if (type === 'team:failed') {
      const dur = e.durationMs ? ` after ${fmtDuration(e.durationMs)}` : ''
      return `Team failed${dur}: ${esc(truncate(String(e.error ?? ''), 100))}`
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
      const urgTag = e.urgency === 'immediate' ? ' 🔴' : ''
      return `${esc(e.signalType ?? 'signal')}${conf}${urgTag}: <i>${esc(truncate(e.content ?? '', 120))}</i>`
    }

    if (type === 'consciousness:anomaly') {
      return `ANOMALY (${esc(e.severity ?? 'medium')}): <i>${esc(truncate(e.description ?? '', 100))}</i>`
    }
    if (type === 'consciousness:insight') {
      return `Insight: <i>${esc(truncate(e.insight ?? '', 120))}</i>`
    }

    if (type === 'synapse:fired') {
      const energy = e.energy ? ` [${esc(e.energy)}]` : ''
      const guidance = e.hasGuidance ? 'guided' : 'no guidance'
      return `Synapse step ${e.step ?? '?'}${energy}: ${guidance} (${e.latencyMs ?? '?'}ms, ${e.remaining ?? '?'} left)`
    }

    if (type === 'brainstem:annotation') {
      const scoreColor = (e.score ?? 0) >= 0.7 ? '🟢' : (e.score ?? 0) >= 0.5 ? '🟡' : '🔴'
      return `Brainstem: ${scoreColor} ${e.score ?? '?'} — ${esc(e.annotation ?? '?')} (step ${e.axonStep ?? '?'})`
    }
    if (type === 'brainstem:pattern') {
      return `Brainstem detected: ${esc(e.pattern ?? '?')} (step ${e.axonStep ?? '?'})`
    }
    if (type === 'brainstem:guidance') {
      return `Brainstem [${esc(e.urgency ?? '?')}]: ${esc(e.text?.slice(0, 120) ?? '')}`
    }

    if (type === 'corpus:sweep') {
      return `Corpus sweep #${e.sweepCount ?? '?'}: ${e.branches ?? '?'} branches, ${e.patterns ?? 0} patterns`
    }
    if (type === 'corpus:pattern') {
      const severity = (e.severity ?? 'unknown').toUpperCase()
      return `Corpus [${severity}]: ${esc(e.pattern ?? '?')} across ${(e.helixIds ?? []).join(', ')} — ${esc(e.description ?? '')}`
    }
    if (type === 'corpus:intervention') {
      return `Corpus → ${esc(e.targetHelixId ?? '?')} [${esc(e.urgency ?? '?')}]: ${esc(e.directiveType ?? '?')} — ${esc(e.reason?.slice(0, 120) ?? '')}`
    }
    if (type === 'corpus:spawn-evaluated') {
      const icon = e.approved ? '✅' : '❌'
      return `Corpus spawn ${icon}: ${esc(e.requestId ?? '?')} — ${esc(e.reason?.slice(0, 120) ?? '')}`
    }
    if (type === 'corpus:synthesis') {
      return `Corpus synthesis: ${esc(e.synthesis?.slice(0, 200) ?? '')}`
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

    // Meditation events
    if (type === 'meditation:started') {
      const prompts = (e.prompts ?? []).map((p: any) => p.promptId).join(', ')
      return `🔮 Meditation started (${esc(e.style ?? '?')}) — prompts: ${esc(prompts)}`
    }
    if (type === 'meditation:stopped') {
      const dur = e.durationMs ? fmtDuration(e.durationMs) : '?'
      return `🔮 Meditation ended (${esc(e.reason ?? '?')}) — ${dur}, ${e.engrams?.spiked ?? 0} engrams spiked`
    }
    if (type === 'meditation:evaluation-complete') {
      const scores = (e.scores ?? []).map((s: any) => `${s.promptId}: ${s.overallScore.toFixed(2)}`).join(', ')
      return `🔮 Evaluation: ${esc(scores)}`
    }
    if (type === 'meditation:prompt-created') {
      return `🔮 New prompt: "<i>${esc(truncate(e.content ?? '', 80))}</i>" (from ${esc(e.parentId ?? '?')})`
    }
    if (type === 'meditation:evolution-adjusted') {
      return `🔮 Evolution rate: ${e.oldTemperature?.toFixed(2) ?? '?'} → ${e.newTemperature?.toFixed(2) ?? '?'} (${esc(e.direction ?? '?')})`
    }
    if (type === 'meditation:focused-seeding') {
      const topics = (e.focusTopics ?? []).join(', ')
      return `🔮 Focused seeding: ${esc(topics)} (${e.engramsKindled ?? 0} kindled)`
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

    if (type === 'lumen:started') {
      if (e.goal) parts.push(`<b>Goal:</b>\n${esc(truncate(e.goal, 1000))}`)
      if (e.sessionId) parts.push(`<b>Session:</b> <code>${esc(String(e.sessionId).slice(0, 16))}</code>`)
      return parts.join('\n\n') || this.formatGenericVerbose(e)
    }

    if (type === 'dyad:started') {
      if (e.goal) parts.push(`<b>Goal:</b>\n${esc(truncate(e.goal, 1000))}`)
      if (e.sessionId) parts.push(`<b>Session:</b> <code>${esc(String(e.sessionId).slice(0, 16))}</code>`)
      return parts.join('\n\n') || this.formatGenericVerbose(e)
    }

    // Lumen dialectic flow verbose formatters
    if (type === 'lumen:dialectic:finding') {
      parts.push(`<b>Finding</b> (${esc(e.from ?? '?')})`)
      if (e.text) parts.push(esc(truncate(e.text, 500)))
      if (e.evidence) parts.push(`<i>Evidence:</i> ${esc(truncate(e.evidence, 200))}`)
      if (e.tags?.length) parts.push(`<i>Tags:</i> ${(e.tags as string[]).map(t => `#${esc(t)}`).join(' ')}`)
      return parts.join('\n') || this.formatGenericVerbose(e)
    }

    if (type === 'lumen:dialectic:challenge') {
      parts.push(`<b>Challenge</b> (${esc(e.from ?? '?')} → ${esc(e.targetFindingId ?? '?')})`)
      if (e.counterargument) parts.push(esc(truncate(e.counterargument, 500)))
      if (e.evidence) parts.push(`<i>Evidence:</i> ${esc(truncate(e.evidence, 200))}`)
      return parts.join('\n') || this.formatGenericVerbose(e)
    }

    if (type === 'lumen:dialectic:concession') {
      parts.push(`<b>Concession</b> (${esc(e.from ?? '?')} → ${esc(e.challengeId ?? '?')})`)
      if (e.reason) parts.push(esc(truncate(e.reason, 300)))
      return parts.join('\n') || this.formatGenericVerbose(e)
    }

    if (type === 'lumen:dialectic:investigation') {
      parts.push(`<b>Investigation Request</b> (${esc(e.from ?? '?')})`)
      if (e.area) parts.push(`<b>Area:</b> ${esc(truncate(e.area, 200))}`)
      if (e.reason) parts.push(`<b>Reason:</b> ${esc(truncate(e.reason, 200))}`)
      return parts.join('\n') || this.formatGenericVerbose(e)
    }

    if (type === 'lumen:dialectic:executive-injection') {
      parts.push(`<b>Executive Context Injection</b> → ${esc(e.target ?? 'both')}`)
      if (e.content) parts.push(esc(truncate(e.content, 500)))
      if (e.source) parts.push(`<i>Source:</i> ${esc(e.source)}`)
      return parts.join('\n') || this.formatGenericVerbose(e)
    }

    if (type === 'lumen:dialectic:executive-steering') {
      parts.push(`<b>Executive Steering</b> → ${esc(e.target ?? 'both')}`)
      if (e.instruction) parts.push(esc(truncate(e.instruction, 500)))
      if (e.reason) parts.push(`<i>Reason:</i> ${esc(truncate(e.reason, 200))}`)
      return parts.join('\n') || this.formatGenericVerbose(e)
    }

    if (type === 'lumen:dialectic:digest') {
      if (e.summary) parts.push(`<b>Dialectic Digest:</b> ${esc(e.summary)}`)
      if (e.events?.length) {
        const items = (e.events as any[]).slice(-5).map(ev => {
          const subType = (ev.type as string).split(':').pop() ?? ev.type
          const who = ev.from ?? ev.posture ?? ''
          const content = ev.text ?? ev.counterargument ?? ev.reason ?? ev.content ?? ''
          return `  • <b>${esc(subType)}</b>${who ? ` (${esc(who)})` : ''}: ${esc(truncate(content, 150))}`
        }).join('\n')
        parts.push(items)
      }
      return parts.join('\n\n') || this.formatGenericVerbose(e)
    }

    // Lumen posture iteration and progress (must come before generic lumen:posture: handler)
    if (type === 'lumen:posture:iteration') {
      parts.push(`<b>${esc(e.posture ?? '?')}</b> iteration ${e.iteration ?? '?'}`)
      const metaParts: string[] = []
      if (e.tokensUsedThisIteration) metaParts.push(`${fmtTokens(e.tokensUsedThisIteration)} tokens`)
      if (e.totalTokens) metaParts.push(`${fmtTokens(e.totalTokens)} total`)
      if (e.totalToolCalls) metaParts.push(`${e.totalToolCalls} tool calls`)
      if (e.hasToolUse != null) metaParts.push(e.hasToolUse ? 'used tools' : 'text only')
      if (metaParts.length) parts.push(`<i>${metaParts.join(' | ')}</i>`)
      return parts.join('\n') || this.formatGenericVerbose(e)
    }

    if (type === 'lumen:iteration:digest') {
      if (e.summary) parts.push(`<b>Iteration Digest:</b> ${esc(e.summary)}`)
      return parts.join('\n') || this.formatGenericVerbose(e)
    }

    if (type === 'lumen:posture:progress') {
      if (e.elapsedMs) parts.push(`<b>Progress</b> — ${fmtDuration(e.elapsedMs)} elapsed`)
      for (const posture of ['yang', 'yin', 'executive'] as const) {
        const p = e[posture]
        if (!p) continue
        const state = p.state ?? 'unknown'
        const stateParts: string[] = [`<b>${posture}:</b> [${esc(state)}]`]
        if (p.iterationCount) stateParts.push(`${p.iterationCount} iterations`)
        if (p.toolCallCount) stateParts.push(`${p.toolCallCount} tools`)
        if (p.tokensUsed) stateParts.push(fmtTokens(p.tokensUsed))
        parts.push(stateParts.join(' | '))
      }
      if (e.dialecticStats) {
        const ds = e.dialecticStats
        const dsParts: string[] = []
        if (ds.findings) dsParts.push(`${ds.findings} findings`)
        if (ds.challenges) dsParts.push(`${ds.challenges} challenges`)
        if (ds.concessions) dsParts.push(`${ds.concessions} concessions`)
        if (ds.unresolvedChallenges) dsParts.push(`${ds.unresolvedChallenges} unresolved`)
        if (dsParts.length) parts.push(`<i>Dialectic: ${dsParts.join(', ')}</i>`)
      }
      return parts.join('\n') || this.formatGenericVerbose(e)
    }

    if (type === 'lumen:progress:digest') {
      if (e.summary) parts.push(`<b>Progress Digest:</b> ${esc(e.summary)}`)
      return parts.join('\n') || this.formatGenericVerbose(e)
    }

    if (type.startsWith('lumen:posture:')) {
      if (e.posture) parts.push(`<b>Posture:</b> ${esc(e.posture)}`)
      if (e.conclusion) parts.push(`<b>Conclusion:</b>\n${esc(truncate(e.conclusion, 2000))}`)
      if (e.keyPoints?.length) {
        const kps = (e.keyPoints as string[]).map(kp => `  • ${esc(truncate(kp, 200))}`).join('\n')
        parts.push(`<b>Key Points:</b>\n${kps}`)
      }
      if (e.confidence) parts.push(`<b>Confidence:</b> ${Math.round(e.confidence * 100)}%`)
      if (e.iterationCount) parts.push(`<b>Iterations:</b> ${e.iterationCount}`)
      if (e.toolCallCount) parts.push(`<b>Tool calls:</b> ${e.toolCallCount}`)
      if (e.tokensUsed) parts.push(`<b>Tokens:</b> ${fmtTokens(e.tokensUsed)}`)
      if (e.error) parts.push(`<b>Error:</b> ${esc(String(e.error))}`)
      return parts.join('\n\n') || this.formatGenericVerbose(e)
    }

    if (type === 'lumen:completed') {
      if (e.goal) parts.push(`<b>Goal:</b>\n${esc(truncate(e.goal, 500))}`)
      if (e.recommendation) parts.push(`<b>Recommendation:</b> ${esc(e.recommendation)}`)
      if (e.confidence != null) parts.push(`<b>Confidence:</b> ${Math.round(e.confidence * 100)}%`)

      if (e.synthesis) parts.push(`<b>Executive Synthesis:</b>\n${esc(truncate(e.synthesis, 2000))}`)

      if (e.yangConclusion) {
        parts.push(`<b>Yang (Assertive):</b>\n${esc(truncate(e.yangConclusion, 1000))}`)
        if (e.yangKeyPoints?.length) {
          const kps = (e.yangKeyPoints as string[]).slice(0, 5).map(kp => `  • ${esc(truncate(kp, 200))}`).join('\n')
          parts.push(kps)
        }
        if (e.yangConfidence != null) parts.push(`  <i>Confidence: ${Math.round(e.yangConfidence * 100)}%</i>`)
      }

      if (e.yinConclusion) {
        parts.push(`<b>Yin (Cautious):</b>\n${esc(truncate(e.yinConclusion, 1000))}`)
        if (e.yinKeyPoints?.length) {
          const kps = (e.yinKeyPoints as string[]).slice(0, 5).map(kp => `  • ${esc(truncate(kp, 200))}`).join('\n')
          parts.push(kps)
        }
        if (e.yinConfidence != null) parts.push(`  <i>Confidence: ${Math.round(e.yinConfidence * 100)}%</i>`)
      }

      if (e.convergencePoints?.length) {
        const cps = (e.convergencePoints as any[]).slice(0, 5).map(cp => {
          if (typeof cp === 'string') return `  • ${esc(truncate(cp, 200))}`
          return `  • <b>${esc(cp.topic ?? '')}</b>: ${esc(truncate(cp.resolution ?? '', 200))} (concession from ${esc(cp.concessionFrom ?? '?')})`
        }).join('\n')
        parts.push(`<b>Convergence Points:</b>\n${cps}`)
      }

      if (e.unresolvedTensions?.length) {
        const uts = (e.unresolvedTensions as any[]).slice(0, 5).map(t => {
          if (typeof t === 'string') return `  • ${esc(truncate(t, 200))}`
          return `  • Yang: ${esc(truncate(t.yangPosition ?? '', 100))} vs Yin: ${esc(truncate(t.yinPosition ?? '', 100))}`
        }).join('\n')
        parts.push(`<b>Unresolved Tensions:</b>\n${uts}`)
      }

      if (e.dialecticStats) {
        const ds = e.dialecticStats
        const statParts: string[] = []
        if (ds.totalFindings) statParts.push(`${ds.totalFindings} findings`)
        if (ds.totalChallenges) statParts.push(`${ds.totalChallenges} challenges`)
        if (ds.totalConcessions) statParts.push(`${ds.totalConcessions} concessions`)
        if (statParts.length) parts.push(`<b>Dialectic:</b> ${statParts.join(', ')}`)
      }

      if (e.report) parts.push(`<b>Report:</b>\n${esc(truncate(e.report, 2000))}`)

      const metaParts: string[] = []
      if (e.durationMs) metaParts.push(`Duration: ${fmtDuration(e.durationMs)}`)
      if (e.tokensUsed) metaParts.push(`Tokens: ${fmtTokens(e.tokensUsed)}`)
      if (e.completionStatus) metaParts.push(`Status: ${e.completionStatus}`)
      if (metaParts.length) parts.push(`<i>${metaParts.join(' | ')}</i>`)

      return parts.join('\n\n') || this.formatGenericVerbose(e)
    }

    // Dyad work stream flow verbose formatters
    if (type === 'dyad:work-unit') {
      parts.push(`<b>Work Unit</b> #${esc(String(e.id ?? '?'))} (iteration ${e.iteration ?? '?'})`)
      if (e.description) parts.push(esc(truncate(e.description, 500)))
      if (e.filesModified?.length) {
        const files = (e.filesModified as string[]).slice(0, 5).map(f => `  • <code>${esc(f)}</code>`).join('\n')
        parts.push(`<b>Files:</b>\n${files}`)
      }
      return parts.join('\n') || this.formatGenericVerbose(e)
    }

    if (type === 'dyad:refinement') {
      parts.push(`<b>Refinement</b> #${esc(String(e.id ?? '?'))} → WU ${esc(String(e.workUnitId ?? '?'))}`)
      if (e.description) parts.push(esc(truncate(e.description, 500)))
      if (e.fileCount) parts.push(`<i>${e.fileCount} files modified</i>`)
      return parts.join('\n') || this.formatGenericVerbose(e)
    }

    if (type === 'dyad:nudge') {
      const sev = e.severity ? ` [${esc(e.severity)}]` : ''
      parts.push(`<b>Nudge</b>${sev}${e.blocking ? ' ⚠️ blocking' : ''}`)
      if (e.content) parts.push(esc(truncate(e.content, 300)))
      return parts.join('\n') || this.formatGenericVerbose(e)
    }

    if (type === 'dyad:research') {
      parts.push(`<b>Research</b>${e.target ? ` → ${esc(e.target)}` : ''}`)
      if (e.topic) parts.push(`<b>Topic:</b> ${esc(truncate(e.topic, 200))}`)
      if (e.findings) parts.push(esc(truncate(e.findings, 500)))
      return parts.join('\n') || this.formatGenericVerbose(e)
    }

    if (type === 'dyad:guidance') {
      parts.push(`<b>Guidance</b>${e.target ? ` → ${esc(e.target)}` : ''}`)
      if (e.direction) parts.push(esc(truncate(e.direction, 300)))
      if (e.rationale) parts.push(`<i>Rationale:</i> ${esc(truncate(e.rationale, 200))}`)
      return parts.join('\n') || this.formatGenericVerbose(e)
    }

    if (type === 'dyad:quality-assessment') {
      if (e.overallScore != null) parts.push(`<b>Quality Score:</b> ${Math.round(e.overallScore * 10)}/10`)
      if (e.assessment) parts.push(`<b>Assessment:</b>\n${esc(truncate(e.assessment, 500))}`)
      if (e.strengths?.length) {
        parts.push(`<b>Strengths:</b>\n${(e.strengths as string[]).slice(0, 3).map(s => `  ✓ ${esc(truncate(s, 150))}`).join('\n')}`)
      }
      if (e.weaknesses?.length) {
        parts.push(`<b>Weaknesses:</b>\n${(e.weaknesses as string[]).slice(0, 3).map(w => `  ✗ ${esc(truncate(w, 150))}`).join('\n')}`)
      }
      if (e.remainingIssues?.length) {
        parts.push(`<b>Issues:</b>\n${(e.remainingIssues as string[]).slice(0, 3).map(i => `  • ${esc(truncate(i, 150))}`).join('\n')}`)
      }
      return parts.join('\n\n') || this.formatGenericVerbose(e)
    }

    if (type === 'dyad:posture:iteration') {
      parts.push(`<b>${esc(e.role ?? '?')}</b> iteration ${e.iteration ?? '?'}`)
      const metaParts: string[] = []
      if (e.tokensUsedThisIteration) metaParts.push(`${fmtTokens(e.tokensUsedThisIteration)} tokens`)
      if (e.totalTokens) metaParts.push(`${fmtTokens(e.totalTokens)} total`)
      if (e.totalToolCalls) metaParts.push(`${e.totalToolCalls} tool calls`)
      if (metaParts.length) parts.push(`<i>${metaParts.join(' | ')}</i>`)
      return parts.join('\n') || this.formatGenericVerbose(e)
    }

    if (type === 'dyad:work-stream:digest') {
      if (e.summary) parts.push(`<b>Work Stream Digest:</b> ${esc(e.summary)}`)
      if (e.events?.length) {
        const items = (e.events as any[]).slice(-5).map(ev => {
          const subType = (ev.type as string).split(':').pop() ?? ev.type
          const desc = ev.description ?? ev.content ?? ev.direction ?? ev.topic ?? ''
          return `  • <b>${esc(subType)}</b>: ${esc(truncate(desc, 150))}`
        }).join('\n')
        parts.push(items)
      }
      return parts.join('\n\n') || this.formatGenericVerbose(e)
    }

    if (type === 'dyad:iteration:digest') {
      if (e.summary) parts.push(`<b>Iteration Digest:</b> ${esc(e.summary)}`)
      return parts.join('\n') || this.formatGenericVerbose(e)
    }

    if (type === 'dyad:role:completed' || type === 'dyad:role:failed') {
      if (e.role) parts.push(`<b>Role:</b> ${esc(e.role)}`)
      if (e.goal) parts.push(`<b>Goal:</b> ${esc(truncate(e.goal, 300))}`)
      if (e.summary) parts.push(`<b>Summary:</b>\n${esc(truncate(e.summary, 2000))}`)
      if (e.filesModified?.length) parts.push(`<b>Files modified:</b> ${e.filesModified.length}`)
      if (e.tokens) parts.push(`<b>Tokens:</b> ${fmtTokens(e.tokens)}`)
      if (e.durationMs) parts.push(`<b>Duration:</b> ${fmtDuration(e.durationMs)}`)
      if (e.error) parts.push(`<b>Error:</b> ${esc(truncate(String(e.error), 500))}`)
      return parts.join('\n\n') || this.formatGenericVerbose(e)
    }

    if (type === 'dyad:completed') {
      if (e.goal) parts.push(`<b>Goal:</b>\n${esc(truncate(e.goal, 500))}`)

      if (e.yangConclusion) {
        parts.push(`<b>Yang (Worker):</b>\n${esc(truncate(e.yangConclusion, 1000))}`)
        if (e.yangKeyPoints?.length) {
          const kps = (e.yangKeyPoints as string[]).slice(0, 5).map(kp => `  • ${esc(truncate(kp, 200))}`).join('\n')
          parts.push(kps)
        }
      }

      if (e.yinConclusion) {
        parts.push(`<b>Yin (Refiner):</b>\n${esc(truncate(e.yinConclusion, 1000))}`)
        if (e.yinKeyPoints?.length) {
          const kps = (e.yinKeyPoints as string[]).slice(0, 5).map(kp => `  • ${esc(truncate(kp, 200))}`).join('\n')
          parts.push(kps)
        }
      }

      if (e.apexSummary) parts.push(`<b>Apex (Overseer):</b>\n${esc(truncate(e.apexSummary, 1000))}`)

      if (e.qualityAssessment) {
        parts.push(`<b>Quality Assessment:</b>\n${esc(truncate(e.qualityAssessment, 1000))}`)
      }
      if (e.qualityScore != null) parts.push(`<b>Quality Score:</b> ${Math.round(e.qualityScore * 100)}%`)

      if (e.remainingIssues?.length) {
        const issues = (e.remainingIssues as string[]).slice(0, 5).map(i => `  • ${esc(truncate(i, 200))}`).join('\n')
        parts.push(`<b>Remaining Issues:</b>\n${issues}`)
      }

      if (e.report) parts.push(`<b>Report:</b>\n${esc(truncate(e.report, 2000))}`)

      const metaParts: string[] = []
      if (e.durationMs) metaParts.push(`Duration: ${fmtDuration(e.durationMs)}`)
      if (e.tokensUsed) metaParts.push(`Tokens: ${fmtTokens(e.tokensUsed)}`)
      if (e.workUnitsProduced) metaParts.push(`Work units: ${e.workUnitsProduced}`)
      if (e.refinementsMade) metaParts.push(`Refinements: ${e.refinementsMade}`)
      if (e.convergenceScore != null) metaParts.push(`Convergence: ${Math.round(e.convergenceScore * 100)}%`)
      if (e.completionStatus) metaParts.push(`Status: ${e.completionStatus}`)
      if (metaParts.length) parts.push(`<i>${metaParts.join(' | ')}</i>`)

      return parts.join('\n\n') || this.formatGenericVerbose(e)
    }

    if (type === 'dyad:failed') {
      if (e.goal) parts.push(`<b>Goal:</b>\n${esc(truncate(e.goal, 500))}`)
      if (e.error) parts.push(`<b>Error:</b>\n${esc(truncate(String(e.error), 1000))}`)
      if (e.durationMs) parts.push(`<b>Duration:</b> ${fmtDuration(e.durationMs)}`)
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
      if (e.urgency) parts.push(`<b>Urgency:</b> ${esc(e.urgency)}${e.urgency === 'immediate' ? ' 🔴' : ''}`)
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

    if (type === 'synapse:fired') {
      parts.push(`<b>Synapse fired</b> at step ${e.step ?? '?'}`)
      if (e.reason) parts.push(`<b>Trigger:</b> ${esc(e.reason)}`)
      if (e.energy) parts.push(`<b>Posture energy:</b> ${esc(e.energy)}`)
      if (e.latencyMs != null) parts.push(`<b>Latency:</b> ${e.latencyMs}ms`)
      parts.push(`<b>Generated guidance:</b> ${e.hasGuidance ? 'yes' : 'no'}`)
      if (e.remaining != null) parts.push(`<b>Budget remaining:</b> ${e.remaining} calls`)
      if (e.axonSessionId) parts.push(`<b>Axon:</b> <code>${esc(String(e.axonSessionId).slice(0, 16))}</code>`)
      return parts.join('\n') || this.formatGenericVerbose(e)
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

    if (type === 'team:started') {
      if (e.goal) parts.push(`<b>Goal:</b>\n${esc(truncate(e.goal, 500))}`)
      if (e.teamId) parts.push(`<b>Team ID:</b> <code>${esc(e.teamId)}</code>`)
      if (e.taskSignature) {
        const ts = e.taskSignature
        if (ts.domains?.length) parts.push(`<b>Domains:</b> ${(ts.domains as string[]).map(d => esc(d)).join(', ')}`)
        if (ts.complexity) parts.push(`<b>Complexity:</b> ${esc(ts.complexity)}`)
        if (ts.suggestedTopology) parts.push(`<b>Topology:</b> ${esc(ts.suggestedTopology)}`)
      }
      return parts.join('\n\n') || this.formatGenericVerbose(e)
    }

    if (type === 'team:completed') {
      if (e.goal) parts.push(`<b>Goal:</b>\n${esc(truncate(e.goal, 500))}`)

      if (e.finalResult) parts.push(`<b>Result:</b>\n${esc(truncate(e.finalResult, 2000))}`)

      if (e.cells?.length) {
        const cellSummaries = (e.cells as any[]).map(c => {
          const status = c.status ?? '?'
          const tok = c.tokensUsed ? ` (${fmtTokens(c.tokensUsed)} tokens)` : ''
          const err = c.error ? ` — ${esc(truncate(c.error, 100))}` : ''
          return `  • <code>${esc(c.cellId ?? '?')}</code> [${esc(status)}]${tok}${err}`
        }).join('\n')
        parts.push(`<b>Cells:</b>\n${cellSummaries}`)
      }

      if (e.taskSignature) {
        const ts = e.taskSignature
        const sigParts: string[] = []
        if (ts.domains?.length) sigParts.push(`Domains: ${(ts.domains as string[]).join(', ')}`)
        if (ts.complexity) sigParts.push(`Complexity: ${ts.complexity}`)
        if (sigParts.length) parts.push(`<b>Task:</b> ${sigParts.join(' | ')}`)
      }

      const metaParts: string[] = []
      if (e.durationMs) metaParts.push(`Duration: ${fmtDuration(e.durationMs)}`)
      if (e.totalTokens) metaParts.push(`Tokens: ${fmtTokens(e.totalTokens)}`)
      if (metaParts.length) parts.push(`<i>${metaParts.join(' | ')}</i>`)

      return parts.join('\n\n') || this.formatGenericVerbose(e)
    }

    if (type === 'team:failed') {
      if (e.goal) parts.push(`<b>Goal:</b>\n${esc(truncate(e.goal, 500))}`)
      if (e.error) parts.push(`<b>Error:</b>\n${esc(truncate(String(e.error), 1000))}`)

      if (e.cells?.length) {
        const cellSummaries = (e.cells as any[]).map(c => {
          const status = c.status ?? '?'
          const err = c.error ? ` — ${esc(truncate(c.error, 100))}` : ''
          return `  • <code>${esc(c.cellId ?? '?')}</code> [${esc(status)}]${err}`
        }).join('\n')
        parts.push(`<b>Cells:</b>\n${cellSummaries}`)
      }

      const metaParts: string[] = []
      if (e.durationMs) metaParts.push(`Duration: ${fmtDuration(e.durationMs)}`)
      if (e.totalTokens) metaParts.push(`Tokens: ${fmtTokens(e.totalTokens)}`)
      if (metaParts.length) parts.push(`<i>${metaParts.join(' | ')}</i>`)

      return parts.join('\n\n') || this.formatGenericVerbose(e)
    }

    if (type === 'flux:event') {
      // Unwrap the inner FluxTeamEvent for display
      const inner = e.event
      if (inner) {
        if (inner.type) parts.push(`<b>Event:</b> ${esc(inner.type)}`)
        if (inner.teamId) parts.push(`<b>Team:</b> <code>${esc(inner.teamId)}</code>`)
        if (inner.message) parts.push(`<b>Message:</b> ${esc(truncate(inner.message, 500))}`)
        if (inner.entityId && inner.entityId !== inner.teamId) parts.push(`<b>Entity:</b> <code>${esc(inner.entityId)}</code>`)
        if (inner.data) {
          const dataStr = JSON.stringify(inner.data, null, 2)
          if (dataStr.length > 2) parts.push(`<pre>${esc(truncate(dataStr, 1000))}</pre>`)
        }
        return parts.join('\n') || this.formatGenericVerbose(e)
      }
      return this.formatGenericVerbose(e)
    }

    // Synapse events
    if (type === 'synapse:fired') {
      parts.push(`<b>Synapse fired</b> at step ${e.step ?? '?'}`)
      if (e.reason) parts.push(`<b>Reason:</b> ${esc(e.reason)}`)
      if (e.energy) parts.push(`<b>Energy:</b> ${esc(e.energy)}`)
      if (e.latencyMs != null) parts.push(`<b>Latency:</b> ${e.latencyMs}ms`)
      parts.push(`<b>Guidance:</b> ${e.hasGuidance ? 'yes' : 'no'}`)
      if (e.remaining != null) parts.push(`<b>Budget remaining:</b> ${e.remaining}`)
      return parts.join('\n') || this.formatGenericVerbose(e)
    }

    // Axon events (collect_thoughts thinking steps)
    if (type === 'axon:step') {
      parts.push(`<b>Step ${e.step ?? '?'}/${e.totalSteps ?? '?'}</b>`)
      if (e.thought) parts.push(esc(truncate(e.thought, 500)))
      if (e.isRevision) parts.push(`<i>(revision)</i>`)
      if (e.signals?.length) parts.push(`<i>Signals:</i> ${e.signals.length}`)
      return parts.join('\n') || this.formatGenericVerbose(e)
    }

    if (type === 'axon:branch') {
      parts.push(`<b>Branch</b> from step ${e.fromStep ?? '?'}`)
      if (e.branchId) parts.push(`<b>Branch ID:</b> <code>${esc(e.branchId)}</code>`)
      return parts.join('\n') || this.formatGenericVerbose(e)
    }

    if (type === 'axon:complete') {
      parts.push(`<b>Thinking complete</b> (${e.totalSteps ?? '?'} steps)`)
      if (e.summary) parts.push(esc(truncate(e.summary, 500)))
      return parts.join('\n') || this.formatGenericVerbose(e)
    }

    // Meditation events
    if (type === 'meditation:started') {
      parts.push(`🔮 <b>Meditation Started</b> (${esc(e.style ?? 'passive')})`)
      if (e.prompts?.length) {
        const promptLines = (e.prompts as any[]).map((p: any) =>
          `  • <b>${esc(p.explorer)}</b>: [${esc(p.promptId)}] <i>${esc(truncate(p.prompt, 60))}</i>`,
        )
        parts.push(promptLines.join('\n'))
      }
      return parts.join('\n\n') || this.formatGenericVerbose(e)
    }
    if (type === 'meditation:stopped') {
      parts.push(`🔮 <b>Meditation Complete</b> (${esc(e.reason ?? '?')})`)
      if (e.durationMs) parts.push(`<b>Duration:</b> ${fmtDuration(e.durationMs)}`)
      if (e.engrams) parts.push(`<b>Engrams:</b> ${e.engrams.spiked} spiked, ${e.engrams.created} created`)
      if (e.consolidations) parts.push(`<b>Consolidations:</b> ${e.consolidations}`)
      return parts.join('\n') || this.formatGenericVerbose(e)
    }
    if (type === 'meditation:evaluation-complete') {
      parts.push(`🔮 <b>Evaluation Complete</b> (${esc(e.style ?? 'passive')})`)
      if (e.scores?.length) {
        const scoreLines = (e.scores as any[]).map((s: any) =>
          `  • <b>${esc(s.promptId)}</b> → ${s.overallScore.toFixed(2)}`,
        )
        parts.push(scoreLines.join('\n'))
      }
      if (e.summary) parts.push(`\n<i>${esc(truncate(e.summary, 500))}</i>`)
      if (e.evalDurationMs) parts.push(`<b>Eval:</b> ${fmtDuration(e.evalDurationMs)}, ${fmtTokens(e.evalTokensUsed ?? 0)} tokens`)
      return parts.join('\n') || this.formatGenericVerbose(e)
    }
    if (type === 'meditation:prompt-created') {
      parts.push(`🔮 <b>New Prompt Created</b>`)
      parts.push(`<b>ID:</b> <code>${esc(e.promptId ?? '?')}</code>`)
      parts.push(`<b>Parent:</b> <code>${esc(e.parentId ?? '?')}</code>`)
      parts.push(`<b>Category:</b> ${esc(e.category ?? '?')}`)
      parts.push(`<b>Content:</b> <i>"${esc(truncate(e.content ?? '', 200))}"</i>`)
      if (e.rationale) parts.push(`<b>Rationale:</b> ${esc(truncate(e.rationale, 200))}`)
      return parts.join('\n') || this.formatGenericVerbose(e)
    }
    if (type === 'meditation:evolution-adjusted') {
      parts.push(`🔮 <b>Evolution Rate Adjusted</b> (${esc(e.direction ?? '?')})`)
      parts.push(`<b>Temperature:</b> ${e.oldTemperature?.toFixed(2) ?? '?'} → ${e.newTemperature?.toFixed(2) ?? '?'}`)
      return parts.join('\n') || this.formatGenericVerbose(e)
    }
    if (type === 'meditation:focused-seeding') {
      parts.push(`🔮 <b>Focused Seeding</b>`)
      if (e.focusTopics?.length) parts.push(`<b>Topics:</b> ${(e.focusTopics as string[]).map(t => esc(t)).join(', ')}`)
      parts.push(`<b>Engrams kindled:</b> ${e.engramsKindled ?? 0}`)
      if (e.seedingDurationMs) parts.push(`<b>Duration:</b> ${fmtDuration(e.seedingDurationMs)}`)
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


  /**
   * Format multiple curated events as a batch digest for a topic thread.
   * Groups events by type and shows a summary with the latest event details.
   */
  formatBatchDigest(events: CuratedEvent[]): string {
    if (events.length === 0) return ''
    if (events.length === 1) return this.formatVerbose(events[0])

    const parts: string[] = ['<b>Batch Summary</b>', '']

    // Group by event type and count
    const typeCounts = new Map<string, number>()
    for (const curated of events) {
      const type = (curated.event as any).type as string
      typeCounts.set(type, (typeCounts.get(type) ?? 0) + 1)
    }

    for (const [type, count] of typeCounts) {
      parts.push(`  \u2022 <code>${esc(type)}</code> \u00d7 ${count}`)
    }

    // Show the last event's details for context
    const lastEvent = events[events.length - 1]
    const lastBody = this.formatVerboseBody((lastEvent.event as any).type, lastEvent.event)
    if (lastBody) {
      parts.push('')
      parts.push('<i>Latest:</i>')
      parts.push(truncate(lastBody, 500))
    }

    parts.push('')
    parts.push(`<i>${fmtTime()} | ${events.length} events batched</i>`)

    return parts.join('\n')
  }

  /**
   * Format multiple curated highlight events as a digest for the main chat.
   * Shows the most recent highlights with module labels.
   */
  formatHighlightDigest(events: CuratedEvent[]): string {
    if (events.length === 0) return ''
    if (events.length === 1) return this.formatHighlight(events[0])

    const MAX_SHOWN = 5
    const parts: string[] = [`<b>[Digest]</b> ${events.length} highlights:`, '']

    // Show the most recent N events
    const shown = events.slice(-MAX_SHOWN)
    for (const curated of shown) {
      const e = curated.event as any
      const label = MODULE_LABELS[curated.topicKey ?? 'system'] ?? 'System'
      const body = this.formatHighlightBody(e.type as string, e)
      parts.push(`  <b>${esc(label)}</b>: ${truncate(body, 100)}`)
    }

    if (events.length > MAX_SHOWN) {
      parts.push(`  <i>... and ${events.length - MAX_SHOWN} more</i>`)
    }

    parts.push('')
    parts.push(`<i>${fmtTime()}</i>`)

    return parts.join('\n')
  }
}
