/**
 * EventCurator — Routes runtime events to the correct topic and decides
 * which events deserve a highlight in the main chat.
 *
 * Responsibilities:
 *  - Classify events as highlight vs verbose
 *  - Route events to the correct forum topic
 *  - Filter out noise (e.g., low-confidence signals, routine heartbeats)
 *  - Apply per-module enable/disable toggles
 */

import type { RuntimeEvent } from '@cassicore/foundation'

const TEAM_EVENT_TYPE = 'team:event'

// Types

export interface CuratedEvent {
  /** The original event */
  event: RuntimeEvent
  /** Primary topic to send to (null = main chat only) */
  topicKey: string | null
  /** Additional topics to mirror to (e.g., blackboard events go to parent + blackboard) */
  mirrorTopics: string[]
  /** Whether this event also appears as a curated highlight in the main chat */
  isHighlight: boolean
  /** Display priority for rate limiter */
  priority: 'high' | 'medium' | 'low'
  /** Constellation session ID for per-session routing */
  constellationSessionId?: string
}

export interface CuratorConfig {
  /** Min confidence for dialectic signals to become highlights (default: 0.5) */
  minConfidence: number
  /** Min severity for anomalies to become highlights (default: 'medium') */
  minSeverity: 'low' | 'medium' | 'high'
  /** Per-topic enable toggles */
  enabledTopics: Record<string, boolean>
}

// Routing table

interface RouteRule {
  /** Topic key to route to */
  topicKey: string | null
  /** Whether this event type is a highlight candidate */
  highlight: boolean
  /** Additional topics to mirror the event to */
  mirrorTopics?: string[]
  /** Static priority */
  priority?: 'high' | 'medium' | 'low'
  /** Dynamic priority — overrides static priority when present */
  priorityFn?: (event: RuntimeEvent) => 'high' | 'medium' | 'low'
  /** Filter function — return false to drop the event */
  filter?: (event: RuntimeEvent, config: CuratorConfig) => boolean
}

/**
 * Event type → routing rule.
 * More specific patterns are checked first (exact match), then prefix match.
 *
 * Consolidated topic mapping (2026-04 redesign):
 *   constellation → all orchestration events (Lumen, Dyad, FluxTeam, Triad, Drone, Multi-Agent, Constellation)
 *   intelligence  → Thinker, Dialectic, Consciousness, Adaptive
 *   memory        → Dreams, Archive, Search, Heart
 *   system        → Errors, budget, tools, LLM calls, blackboard, timeline, trust, self-healing
 *   sessions      → User session lifecycle
 */
const EXACT_ROUTES: Record<string, RouteRule> = {
  // Constellation War Room — all orchestration events
  'lumen:synthesis-complete':  { topicKey: 'constellation', highlight: true, priority: 'high' },
  'lumen:started':             { topicKey: 'constellation', highlight: true, priority: 'medium' },
  'lumen:completed':           { topicKey: 'constellation', highlight: true, priority: 'high' },
  'lumen:persisted':           { topicKey: 'constellation', highlight: false },
  'lumen:yang-complete':       { topicKey: 'constellation', highlight: false },
  'lumen:yin-complete':        { topicKey: 'constellation', highlight: false },
  'lumen:posture:start':       { topicKey: 'constellation', highlight: false },
  'lumen:posture:concluded':   { topicKey: 'constellation', highlight: false },
  'lumen:posture:error':       { topicKey: 'constellation', highlight: true, priority: 'high' },
  'lumen:dialectic:finding':           { topicKey: 'constellation', highlight: false },
  'lumen:dialectic:challenge':         { topicKey: 'constellation', highlight: false },
  'lumen:dialectic:concession':        { topicKey: 'constellation', highlight: false },
  'lumen:dialectic:investigation':     { topicKey: 'constellation', highlight: false },
  'lumen:dialectic:executive-injection': { topicKey: 'constellation', highlight: true, priority: 'medium' },
  'lumen:dialectic:executive-steering': { topicKey: 'constellation', highlight: true, priority: 'medium' },
  'lumen:dialectic:digest':            { topicKey: 'constellation', highlight: false },
  'lumen:posture:iteration':           { topicKey: 'constellation', highlight: false },
  'lumen:posture:progress':            { topicKey: 'constellation', highlight: false },
  'lumen:iteration:digest':            { topicKey: 'constellation', highlight: false },
  'lumen:progress:digest':             { topicKey: 'constellation', highlight: false },

  'dyad:started':              { topicKey: 'constellation', highlight: true, priority: 'medium' },
  'dyad:completed':            { topicKey: 'constellation', highlight: true, priority: 'high' },
  'dyad:failed':               { topicKey: 'constellation', highlight: true, priority: 'high' },
  'dyad:role:completed':       { topicKey: 'constellation', highlight: false },
  'dyad:role:failed':          { topicKey: 'constellation', highlight: true, priority: 'high' },
  'dyad:work-unit':            { topicKey: 'constellation', highlight: false },
  'dyad:refinement':           { topicKey: 'constellation', highlight: false },
  'dyad:nudge':                { topicKey: 'constellation', highlight: false },
  'dyad:research':             { topicKey: 'constellation', highlight: false },
  'dyad:guidance':             { topicKey: 'constellation', highlight: false },
  'dyad:quality-assessment':   { topicKey: 'constellation', highlight: true, priority: 'medium' },
  'dyad:posture:iteration':    { topicKey: 'constellation', highlight: false },
  'dyad:work-stream:digest':   { topicKey: 'constellation', highlight: false },
  'dyad:iteration:digest':     { topicKey: 'constellation', highlight: false },

  'team:started':              { topicKey: 'constellation', highlight: true, priority: 'medium' },
  'team:completed':            { topicKey: 'constellation', highlight: true, priority: 'high' },
  'team:failed':               { topicKey: 'constellation', highlight: true, priority: 'high' },
  'team:cancelled':            { topicKey: 'constellation', highlight: true, priority: 'medium' },
  'team:paused':               { topicKey: 'constellation', highlight: false },
  'team:resumed':              { topicKey: 'constellation', highlight: false },
  'team:checkpoint':           { topicKey: 'constellation', highlight: true, priority: 'high' },
  'flux:event':                { topicKey: 'constellation', highlight: false },
  'flux:node:completed':       { topicKey: 'constellation', highlight: false },

  'triad-team:created':        { topicKey: 'constellation', highlight: true, priority: 'medium' },
  'triad-team:completed':      { topicKey: 'constellation', highlight: true, priority: 'medium' },
  'triad-team:failed':         { topicKey: 'constellation', highlight: true, priority: 'high' },
  'triad-team:cancelled':      { topicKey: 'constellation', highlight: true, priority: 'medium' },
  'triad-team:checkpoint':     { topicKey: 'constellation', highlight: true, priority: 'high' },
  'triad-team:cell-completed-without-action': { topicKey: 'constellation', highlight: true, priority: 'high' },
  'cell:turn:start':           { topicKey: 'constellation', highlight: false },
  'cell:turn:end':             { topicKey: 'constellation', highlight: false },
  'cell:thinking:signal-extracted': { topicKey: 'constellation', highlight: false },

  'agent:spawned':             { topicKey: 'constellation', highlight: false },
  'agent:task-assigned':       { topicKey: 'constellation', highlight: false },
  'agent:completed':           { topicKey: 'constellation', highlight: true, priority: 'medium' },
  'agent:error':               { topicKey: 'constellation', highlight: true, priority: 'high' },
  'agent:handoff':             { topicKey: 'constellation', highlight: true, priority: 'medium' },
  'multi-agent:spawn-failed':  { topicKey: 'constellation', highlight: true, priority: 'high' },

  'constellation:started':     { topicKey: 'constellation', highlight: true, priority: 'high' },
  'constellation:decomposing': { topicKey: 'constellation', highlight: false },
  'constellation:decomposed':  { topicKey: 'constellation', highlight: true, priority: 'medium' },
  'constellation:executing':   { topicKey: 'constellation', highlight: false },
  'constellation:checkpoint':  { topicKey: 'constellation', highlight: true, priority: 'medium' },
  'constellation:stagnation':  { topicKey: 'constellation', highlight: true, priority: 'high' },
  'constellation:completed':   { topicKey: 'constellation', highlight: true, priority: 'high' },
  'constellation:failed':      { topicKey: 'constellation', highlight: true, priority: 'high' },
  'constellation:cancelled':   { topicKey: 'constellation', highlight: true, priority: 'medium' },
  'constellation:branch:created':   { topicKey: 'constellation', highlight: false },
  'constellation:branch:launched':  { topicKey: 'constellation', highlight: false },
  'constellation:branch:completed': { topicKey: 'constellation', highlight: true, priority: 'medium' },
  'constellation:branch:degraded':  { topicKey: 'constellation', highlight: true, priority: 'medium' },
  'constellation:branch:failed':    { topicKey: 'constellation', highlight: true, priority: 'high' },

  'helix:started':   { topicKey: 'constellation', highlight: false },
  'helix:completed': { topicKey: 'constellation', highlight: true, priority: 'medium' },
  'helix:failed':    { topicKey: 'constellation', highlight: true, priority: 'high' },
  'helix:iteration:complete': { topicKey: 'constellation', highlight: false },

  'helix:synapse:started':   { topicKey: 'constellation', highlight: false },
  'helix:synapse:stopped':   { topicKey: 'constellation', highlight: false },
  'helix:synapse:fired':     { topicKey: 'constellation', highlight: false },
  'helix:synapse:broadcast': { topicKey: 'constellation', highlight: true, priority: 'medium' },
  'helix:synapse:feedback':  { topicKey: 'constellation', highlight: false },

  'corpus:intervention':     { topicKey: 'constellation', highlight: true, priority: 'high' },
  'corpus:spawn-decision':   { topicKey: 'constellation', highlight: true, priority: 'medium' },
  'corpus:escalation':       { topicKey: 'constellation', highlight: true, priority: 'high' },
  'corpus:discovery':        { topicKey: 'constellation', highlight: true, priority: 'medium' },
  'corpus:synthesis':        { topicKey: 'constellation', highlight: true, priority: 'medium' },
  'corpus:checkpoint':       { topicKey: 'constellation', highlight: false },
  'corpus:external-assumed':        { topicKey: 'constellation', highlight: true, priority: 'medium' },
  'corpus:external-released':       { topicKey: 'constellation', highlight: true, priority: 'medium' },
  'corpus:external-directive':      { topicKey: 'constellation', highlight: true, priority: 'high' },
  'corpus:external-spawn-decision': { topicKey: 'constellation', highlight: true, priority: 'high' },

  'topology:updated':      { topicKey: 'constellation', highlight: false },
  'constellation:corpus-observer:broadcast':  { topicKey: 'constellation', highlight: false },
  'constellation:cluster-observer:broadcast': { topicKey: 'constellation', highlight: false },

  // Intelligence — reasoning and awareness
  'thinker:insight-applied':   { topicKey: 'intelligence', highlight: true, priority: 'high' },
  'thinker:early-warning':     { topicKey: 'intelligence', highlight: true, priority: 'high' },
  'thinker:strategy-snapshot': { topicKey: 'intelligence', highlight: false },
  'thinker:self-modified':     { topicKey: 'intelligence', highlight: true, priority: 'medium' },

  'dialectic:signal': {
    topicKey: 'intelligence',
    highlight: true,
    priority: 'medium',
    filter: (event, config) => {
      const e = event as any
      return (e.confidence ?? 1) >= config.minConfidence
    },
    priorityFn: (event) => {
      const e = event as any
      return e.urgency === 'immediate' ? 'high' : 'medium'
    },
  },
  'dialectic:round-complete':  { topicKey: 'intelligence', highlight: false },
  'dialectic:convergence':     { topicKey: 'intelligence', highlight: false },

  'consciousness:anomaly': {
    topicKey: 'intelligence',
    highlight: true,
    priority: 'high',
    filter: (event, config) => {
      const e = event as any
      const severity = e.severity ?? 'medium'
      const severityOrder = { low: 0, medium: 1, high: 2 }
      return (severityOrder[severity as keyof typeof severityOrder] ?? 1) >=
             (severityOrder[config.minSeverity] ?? 1)
    },
  },
  'consciousness:insight':              { topicKey: 'intelligence', highlight: true, priority: 'medium' },
  'consciousness:observation':          { topicKey: 'intelligence', highlight: true, priority: 'low' },
  'consciousness:cross-session-correlation': { topicKey: 'intelligence', highlight: true, priority: 'medium' },
  'subconscious:learning':              { topicKey: 'intelligence', highlight: true, priority: 'low' },

  'adaptive:adaptation-applied':  { topicKey: 'intelligence', highlight: true, priority: 'medium' },
  'adaptive:adaptation-reverted': { topicKey: 'intelligence', highlight: true, priority: 'medium' },
  'verification:scenario-run':    { topicKey: 'intelligence', highlight: false },
  'improvement:cycle-complete':   { topicKey: 'intelligence', highlight: false },

  // Memory — dreams, archive, heart
  'dreamer:cycle-complete':    { topicKey: 'memory', highlight: true, priority: 'medium' },
  'dreamer:insight':           { topicKey: 'memory', highlight: true, priority: 'medium' },
  'memory:stored':             { topicKey: 'memory', highlight: false, priority: 'low' },
  'memory:recalled':           { topicKey: 'memory', highlight: false, priority: 'low' },
  'heart:beat':                { topicKey: 'memory', highlight: false, priority: 'low' },
  'heart:delivered':           { topicKey: 'memory', highlight: false, priority: 'low' },
  'heart:skipped':             { topicKey: 'memory', highlight: false, priority: 'low' },

  // Meditation — idle-time exploration and prompt evolution
  'meditation:started':              { topicKey: 'meditation', highlight: true, priority: 'medium' },
  'meditation:stopped':              { topicKey: 'meditation', highlight: true, priority: 'medium' },
  'meditation:evaluation-complete':  { topicKey: 'meditation', highlight: true, priority: 'high' },
  'meditation:prompt-created':       { topicKey: 'meditation', highlight: true, priority: 'high' },
  'meditation:prompt-retired':       { topicKey: 'meditation', highlight: true, priority: 'medium' },
  'meditation:style-selected':       { topicKey: 'meditation', highlight: false, priority: 'low' },
  'meditation:evolution-adjusted':   { topicKey: 'meditation', highlight: true, priority: 'medium' },
  'meditation:focused-seeding':      { topicKey: 'meditation', highlight: true, priority: 'medium' },
  'meditation:self-modeling-complete': { topicKey: 'meditation', highlight: true, priority: 'high' },

  // System — errors, budget, tools, LLM, blackboard, timeline
  'provider:request_error':    { topicKey: 'system', highlight: true, priority: 'high' },
  'provider:request_timeout':  { topicKey: 'system', highlight: true, priority: 'high' },
  'provider:rate_limited':     { topicKey: 'system', highlight: true, priority: 'high' },
  'self-healer:repair':        { topicKey: 'system', highlight: true, priority: 'high' },
  'trust:update':              { topicKey: 'system', highlight: false },
  'permission:decision':       { topicKey: 'system', highlight: false },
  'daemon:health':             { topicKey: 'system', highlight: false, priority: 'low' },
  'daemon:ready':              { topicKey: 'system', highlight: true, priority: 'high' },
  'daemon:shutdown':           { topicKey: 'system', highlight: true, priority: 'high' },
  'budget:warning':            { topicKey: 'system', highlight: true, priority: 'high' },
  'budget:exhausted':          { topicKey: 'system', highlight: true, priority: 'high' },
  'budget:tier_changed':       { topicKey: 'system', highlight: true, priority: 'medium' },
  'team:budget:warning':       { topicKey: 'system', highlight: true, priority: 'high' },
  'triad-team:budget-warning': { topicKey: 'system', highlight: true, priority: 'high' },
  'tool:registered':           { topicKey: 'system', highlight: false, priority: 'low' },
  'tool:executed':             { topicKey: 'system', highlight: false, priority: 'low' },
  'provider:request_start':    { topicKey: 'system', highlight: false, priority: 'low' },
  'provider:request_end':      { topicKey: 'system', highlight: false, priority: 'low' },
  'provider:request_chunk':    { topicKey: 'system', highlight: false, priority: 'low' },
  'blackboard:entry':          { topicKey: 'system', highlight: false },
  'timeline:retention':        { topicKey: 'system', highlight: true, priority: 'medium' },
  'timeline:stats':            { topicKey: 'system', highlight: false, priority: 'low' },

  // Sessions — user-facing lifecycle
  'session:created':           { topicKey: 'sessions', highlight: true, priority: 'medium' },
  'session:ended':             { topicKey: 'sessions', highlight: true, priority: 'low' },
  'turn:start':                { topicKey: 'sessions', highlight: false, priority: 'low' },
  'turn:end':                  { topicKey: 'sessions', highlight: false, priority: 'low' },
}

/**
 * Prefix-based routing for event types not in EXACT_ROUTES.
 * Checked in order — first match wins.
 */
const PREFIX_ROUTES: Array<{ prefix: string; rule: RouteRule }> = [
  // Constellation War Room — all orchestration prefixes
  { prefix: 'lumen:',          rule: { topicKey: 'constellation', highlight: false } },
  { prefix: 'dyad:',           rule: { topicKey: 'constellation', highlight: false } },
  { prefix: 'flux:',           rule: { topicKey: 'constellation', highlight: false } },
  { prefix: 'triad-team:',     rule: { topicKey: 'constellation', highlight: false } },
  { prefix: 'cell:',           rule: { topicKey: 'constellation', highlight: false } },
  { prefix: 'agent:',          rule: { topicKey: 'constellation', highlight: false } },
  { prefix: 'multi-agent:',    rule: { topicKey: 'constellation', highlight: false } },
  { prefix: 'constellation:',  rule: { topicKey: 'constellation', highlight: true, priority: 'high' } },
  { prefix: 'corpus:',         rule: { topicKey: 'constellation', highlight: true, priority: 'medium' } },
  { prefix: 'brainstem:',      rule: { topicKey: 'constellation', highlight: false } },
  { prefix: 'team:',           rule: { topicKey: 'constellation', highlight: false } },
  { prefix: 'drone:',          rule: { topicKey: 'constellation', highlight: true } },

  // Intelligence — reasoning, awareness, adaptation
  { prefix: 'thinker:',        rule: { topicKey: 'intelligence', highlight: false } },
  { prefix: 'dialectic:',      rule: { topicKey: 'intelligence', highlight: false } },
  { prefix: 'consciousness:',  rule: { topicKey: 'intelligence', highlight: true } },
  { prefix: 'subconscious:',   rule: { topicKey: 'intelligence', highlight: true } },
  { prefix: 'axon:',           rule: { topicKey: 'intelligence', highlight: true, priority: 'low' } },
  { prefix: 'synapse:',        rule: { topicKey: 'intelligence', highlight: true, priority: 'medium' } },
  { prefix: 'adaptive:',       rule: { topicKey: 'intelligence', highlight: false } },
  { prefix: 'improvement:',    rule: { topicKey: 'intelligence', highlight: false } },
  { prefix: 'verification:',   rule: { topicKey: 'intelligence', highlight: false } },

  // Memory — dreams, archive, heart
  { prefix: 'dreamer:',        rule: { topicKey: 'memory', highlight: false } },
  { prefix: 'memory:',         rule: { topicKey: 'memory', highlight: false } },
  { prefix: 'archive:',        rule: { topicKey: 'memory', highlight: false } },
  { prefix: 'heart:',          rule: { topicKey: 'memory', highlight: false } },

  // Meditation — idle-time exploration
  { prefix: 'meditation:',     rule: { topicKey: 'meditation', highlight: true, priority: 'medium' } },

  // System — operational catch-all
  { prefix: 'budget:',         rule: { topicKey: 'system', highlight: false } },
  { prefix: 'tool:',           rule: { topicKey: 'system', highlight: false, priority: 'low' } },
  { prefix: 'provider:',       rule: { topicKey: 'system', highlight: false, priority: 'low' } },
  { prefix: 'daemon:',         rule: { topicKey: 'system', highlight: false } },
  { prefix: 'self-healer:',    rule: { topicKey: 'system', highlight: false } },
  { prefix: 'trust:',          rule: { topicKey: 'system', highlight: false } },
  { prefix: 'permission:',     rule: { topicKey: 'system', highlight: false } },
  { prefix: 'error-learner:',  rule: { topicKey: 'system', highlight: false } },
  { prefix: 'blackboard:',     rule: { topicKey: 'system', highlight: false } },
  { prefix: 'timeline:',       rule: { topicKey: 'system', highlight: false } },

  // Sessions
  { prefix: 'session:',        rule: { topicKey: 'sessions', highlight: false } },
  { prefix: 'turn:',           rule: { topicKey: 'sessions', highlight: false, priority: 'low' } },
]

// EventCurator

export class EventCurator {
  private readonly config: CuratorConfig

  constructor(config: Partial<CuratorConfig>) {
    this.config = {
      minConfidence: config.minConfidence ?? 0.5,
      minSeverity: config.minSeverity ?? 'medium',
      enabledTopics: config.enabledTopics ?? {},
    }
  }

  /**
   * Curate an event: determine topic routing, highlight status, and priority.
   * Returns null if the event should be dropped (disabled topic, filtered out).
   */
  curate(event: RuntimeEvent): CuratedEvent | null {
    const type = event.type as string

    if (type === TEAM_EVENT_TYPE) {
      const e = event as any
      const innerEvent = e.data?.event ?? ''
      if (innerEvent) {
        const innerRule = this.resolveRule(innerEvent)
        if (innerRule) {
          if (innerRule.topicKey && !this.config.enabledTopics[innerRule.topicKey]) return null
          return {
            event,
            topicKey: innerRule.topicKey,
            mirrorTopics: [],
            isHighlight: innerRule.highlight,
            priority: innerRule.priority ?? 'medium',
            constellationSessionId: e.teamId ?? e.sessionId ?? undefined,
          }
        }
      }
    }

    // Look up routing rule
    const rule = this.resolveRule(type)
    if (!rule) return null

    // Check if the target topic is enabled
    if (rule.topicKey && !this.config.enabledTopics[rule.topicKey]) return null

    // Apply filter function if present
    if (rule.filter && !rule.filter(event, this.config)) return null

    // Determine mirror topics
    const mirrorTopics = [...(rule.mirrorTopics ?? [])]

    // Blackboard events from orchestration systems mirror to the constellation topic
    if (type === 'blackboard:entry' && rule.topicKey !== 'constellation') {
      const e = event as any
      if (e.teamId || e.constellationId || e.source === 'flux' || e.source === 'lumen' || e.lumenId || e.source === 'dyad' || e.dyadId) {
        mirrorTopics.push('constellation')
      }
    }

    // Extract constellation session ID
    const constellationSessionId = (event as any).constellationId ?? (event as any).teamId ?? (event as any).sessionId ?? undefined

    return {
      event,
      topicKey: rule.topicKey,
      mirrorTopics: mirrorTopics.filter(t => this.config.enabledTopics[t]),
      isHighlight: rule.highlight,
      priority: rule.priorityFn ? rule.priorityFn(event) : (rule.priority ?? 'medium'),
      constellationSessionId,
    }
  }

  /**
   * Update config at runtime (e.g., topic enable/disable, confidence thresholds).
   */
  updateConfig(updates: Partial<CuratorConfig>): void {
    if (updates.minConfidence !== undefined) this.config.minConfidence = updates.minConfidence
    if (updates.minSeverity !== undefined) this.config.minSeverity = updates.minSeverity
    if (updates.enabledTopics) {
      Object.assign(this.config.enabledTopics, updates.enabledTopics)
    }
  }


  private resolveRule(type: string): RouteRule | null {
    // Route resolution order (per Lumen analysis):
    // 1. EXACT_ROUTES: highest priority — direct event type → topic mapping
    //    Examples: 'budget:warning', 'team:budget:warning', 'triad-team:budget-warning'
    //    These prevent accidental double-routing and document special cases.
    //
    // 2. PREFIX_ROUTES: fallback — event prefix → topic mapping
    //    Examples: 'budget:*' → budget, 'tool:*' → tools, 'provider:*' → llmCalls
    //    Digest events (provider:stream:digest, tool:execution:digest, etc.) route via prefix.
    //
    // Special case (documented exception to single-topic rule):
    //   'triad-team:budget-warning' routes to both 'budget' (exact) AND 'triadTeam' (mirror)
    //   Reason: TriadTeam coordinators need budget visibility alongside other team events
    //   This is intentional and maintained for backwards compatibility.
    
    if (EXACT_ROUTES[type]) return EXACT_ROUTES[type]

    for (const { prefix, rule } of PREFIX_ROUTES) {
      if (type.startsWith(prefix)) return rule
    }

    return null
  }
}
