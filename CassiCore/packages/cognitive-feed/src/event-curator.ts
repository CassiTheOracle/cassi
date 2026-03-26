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

import type { RuntimeEvent } from '../../../types/events.js'

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
 * Event type prefix → routing rule.
 * More specific patterns are checked first (exact match), then prefix match.
 */
const EXACT_ROUTES: Record<string, RouteRule> = {
  'lumen:synthesis-complete':  { topicKey: 'lumen', highlight: true, priority: 'high' },
  'lumen:started':             { topicKey: 'lumen', highlight: true, priority: 'medium' },
  'lumen:completed':            { topicKey: 'lumen', highlight: true, priority: 'high' },
  'lumen:persisted':           { topicKey: 'lumen', highlight: false },
  'lumen:yang-complete':       { topicKey: 'lumen', highlight: false },
  'lumen:yin-complete':        { topicKey: 'lumen', highlight: false },
  'lumen:posture:start':       { topicKey: 'lumen', highlight: false },
  'lumen:posture:concluded':   { topicKey: 'lumen', highlight: false },
  'lumen:posture:error':       { topicKey: 'lumen', highlight: true, priority: 'high' },

  // Lumen dialectic flow events (real-time message flow)
  'lumen:dialectic:finding':           { topicKey: 'lumen', highlight: false },
  'lumen:dialectic:challenge':         { topicKey: 'lumen', highlight: false },
  'lumen:dialectic:concession':        { topicKey: 'lumen', highlight: false },
  'lumen:dialectic:investigation':     { topicKey: 'lumen', highlight: false },
  'lumen:dialectic:executive-injection': { topicKey: 'lumen', highlight: true, priority: 'medium' },
  'lumen:dialectic:executive-steering': { topicKey: 'lumen', highlight: true, priority: 'medium' },
  'lumen:dialectic:digest':            { topicKey: 'lumen', highlight: false },
  'lumen:posture:iteration':           { topicKey: 'lumen', highlight: false },
  'lumen:posture:progress':            { topicKey: 'lumen', highlight: false },
  'lumen:iteration:digest':            { topicKey: 'lumen', highlight: false },
  'lumen:progress:digest':             { topicKey: 'lumen', highlight: false },

  'dyad:started':              { topicKey: 'dyad', highlight: true, priority: 'medium' },
  'dyad:completed':             { topicKey: 'dyad', highlight: true, priority: 'high' },
  'dyad:failed':               { topicKey: 'dyad', highlight: true, priority: 'high' },
  'dyad:role:completed':       { topicKey: 'dyad', highlight: false },
  'dyad:role:failed':          { topicKey: 'dyad', highlight: true, priority: 'high' },

  // Dyad work stream flow events (real-time message flow)
  'dyad:work-unit':            { topicKey: 'dyad', highlight: false },
  'dyad:refinement':           { topicKey: 'dyad', highlight: false },
  'dyad:nudge':                { topicKey: 'dyad', highlight: false },
  'dyad:research':             { topicKey: 'dyad', highlight: false },
  'dyad:guidance':             { topicKey: 'dyad', highlight: false },
  'dyad:quality-assessment':   { topicKey: 'dyad', highlight: true, priority: 'medium' },
  'dyad:posture:iteration':    { topicKey: 'dyad', highlight: false },
  'dyad:work-stream:digest':   { topicKey: 'dyad', highlight: false },
  'dyad:iteration:digest':     { topicKey: 'dyad', highlight: false },

  // Flux team direct events (real-time flow)
  'team:started':              { topicKey: 'fluxTeam', highlight: true, priority: 'medium' },
  'team:completed':            { topicKey: 'fluxTeam', highlight: true, priority: 'high' },
  'team:failed':               { topicKey: 'fluxTeam', highlight: true, priority: 'high' },

  'flux:event':                { topicKey: 'fluxTeam', highlight: false },
  'flux:node:completed':       { topicKey: 'fluxTeam', highlight: false },

  'triad-team:created':        { topicKey: 'triadTeam', highlight: true, priority: 'medium' },
  'triad-team:completed':      { topicKey: 'triadTeam', highlight: true, priority: 'medium' },
  'triad-team:failed':         { topicKey: 'triadTeam', highlight: true, priority: 'high' },
  'triad-team:cancelled':      { topicKey: 'triadTeam', highlight: true, priority: 'medium' },
  'triad-team:checkpoint':     { topicKey: 'triadTeam', highlight: true, priority: 'high' },
  'triad-team:cell-completed-without-action': { topicKey: 'triadTeam', highlight: true, priority: 'high' },
  'cell:turn:start':           { topicKey: 'fluxTeam', highlight: false },
  'cell:turn:end':             { topicKey: 'fluxTeam', highlight: false },
  'cell:thinking:signal-extracted': { topicKey: 'fluxTeam', highlight: false },

  'drone:swarm:completed':     { topicKey: 'droneSwarm', highlight: true, priority: 'medium' },
  'drone:swarm:failed':        { topicKey: 'droneSwarm', highlight: true, priority: 'high' },
  'drone:swarm:cognitive-summary': { topicKey: 'droneSwarm', highlight: false },
  'drone:prediction':          { topicKey: 'droneSwarm', highlight: false },
  'drone:speculative:matched': { topicKey: 'droneSwarm', highlight: true, priority: 'medium' },
  'drone:speculative:discarded': { topicKey: 'droneSwarm', highlight: false },
  'drone:autonomous-probe:triggered': { topicKey: 'droneSwarm', highlight: true, priority: 'medium' },
  'drone:autonomous-probe:completed': { topicKey: 'droneSwarm', highlight: false },
  'drone:spawned':             { topicKey: 'droneSwarm', highlight: false, priority: 'low' },
  'drone:completed':           { topicKey: 'droneSwarm', highlight: false, priority: 'low' },
  'drone:failed':              { topicKey: 'droneSwarm', highlight: false },
  'drone:cache-hit':           { topicKey: 'droneSwarm', highlight: false, priority: 'low' },

  'agent:spawned':             { topicKey: 'multiAgent', highlight: false },
  'agent:task-assigned':       { topicKey: 'multiAgent', highlight: false },
  'agent:completed':           { topicKey: 'multiAgent', highlight: true, priority: 'medium' },
  'agent:error':               { topicKey: 'multiAgent', highlight: true, priority: 'high' },
  'agent:handoff':             { topicKey: 'multiAgent', highlight: true, priority: 'medium' },
  'multi-agent:spawn-failed':  { topicKey: 'multiAgent', highlight: true, priority: 'high' },

  'thinker:insight-applied':   { topicKey: 'thinker', highlight: true, priority: 'high' },
  'thinker:early-warning':     { topicKey: 'thinker', highlight: true, priority: 'high' },
  'thinker:strategy-snapshot': { topicKey: 'thinker', highlight: false },
  'thinker:self-modified':     { topicKey: 'thinker', highlight: true, priority: 'medium' },

  'dialectic:signal': {
    topicKey: 'dialectic',
    highlight: true,
    priority: 'medium',
    filter: (event, config) => {
      const e = event as any
      return (e.confidence ?? 1) >= config.minConfidence
    },
    /** Boost priority based on urgency field (added per Lumen analysis) */
    priorityFn: (event) => {
      const e = event as any
      return e.urgency === 'immediate' ? 'high' : 'medium'
    },
  },
  'dialectic:round-complete':  { topicKey: 'dialectic', highlight: false },
  'dialectic:convergence':     { topicKey: 'dialectic', highlight: false },

  'consciousness:anomaly': {
    topicKey: 'consciousness',
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
  'consciousness:insight':     { topicKey: 'consciousness', highlight: true, priority: 'medium' },
  'consciousness:observation': { topicKey: 'consciousness', highlight: false },
  'subconscious:learning':     { topicKey: 'consciousness', highlight: false },

  'dreamer:cycle-complete':    { topicKey: 'memoryDreams', highlight: true, priority: 'medium' },
  'dreamer:insight':           { topicKey: 'memoryDreams', highlight: true, priority: 'medium' },
  'memory:stored':             { topicKey: 'memoryDreams', highlight: false, priority: 'low' },
  'memory:recalled':           { topicKey: 'memoryDreams', highlight: false, priority: 'low' },

  'adaptive:adaptation-applied':  { topicKey: 'adaptive', highlight: true, priority: 'medium' },
  'adaptive:adaptation-reverted': { topicKey: 'adaptive', highlight: true, priority: 'medium' },
  'verification:scenario-run':    { topicKey: 'adaptive', highlight: false },
  'improvement:cycle-complete':   { topicKey: 'adaptive', highlight: false },

  'heart:beat':                { topicKey: 'heart', highlight: false, priority: 'low' },
  'heart:delivered':           { topicKey: 'heart', highlight: false, priority: 'low' },
  'heart:skipped':             { topicKey: 'heart', highlight: false, priority: 'low' },

  'provider:request_error':    { topicKey: 'system', highlight: true, priority: 'high' },
  'provider:request_timeout':  { topicKey: 'system', highlight: true, priority: 'high' },
  'provider:rate_limited':     { topicKey: 'system', highlight: true, priority: 'high' },
  'self-healer:repair':        { topicKey: 'system', highlight: true, priority: 'high' },
  'trust:update':              { topicKey: 'system', highlight: false },
  'permission:decision':       { topicKey: 'system', highlight: false },
  'daemon:health':             { topicKey: 'system', highlight: false, priority: 'low' },
  'daemon:ready':              { topicKey: 'system', highlight: true, priority: 'high' },
  'daemon:shutdown':           { topicKey: 'system', highlight: true, priority: 'high' },

  // Budget events — consolidated in dedicated topic (per Lumen analysis: single-topic rule)
  'budget:warning':            { topicKey: 'budget', highlight: true, priority: 'high' },
  'budget:exhausted':          { topicKey: 'budget', highlight: true, priority: 'high' },
  'budget:tier_changed':       { topicKey: 'budget', highlight: true, priority: 'medium' },
  'team:budget:warning':       { topicKey: 'budget', highlight: true, priority: 'high' },
  'triad-team:budget-warning': { topicKey: 'budget', highlight: true, priority: 'high', mirrorTopics: ['triadTeam'] },

  // Tool lifecycle
  'tool:registered':           { topicKey: 'tools', highlight: false, priority: 'low' },
  'tool:executed':             { topicKey: 'tools', highlight: false, priority: 'low' },

  'provider:request_start':    { topicKey: 'llmCalls', highlight: false, priority: 'low' },
  'provider:request_end':      { topicKey: 'llmCalls', highlight: false, priority: 'low' },
  'provider:request_chunk':    { topicKey: 'llmCalls', highlight: false, priority: 'low' },

  // Session lifecycle — dedicated user-facing topic
  'session:created':           { topicKey: 'sessions', highlight: true, priority: 'medium' },
  'session:ended':             { topicKey: 'sessions', highlight: true, priority: 'low' },
  'turn:start':                { topicKey: 'sessions', highlight: false, priority: 'low' },
  'turn:end':                  { topicKey: 'sessions', highlight: false, priority: 'low' },

  'blackboard:entry':          { topicKey: 'blackboard', highlight: false },

  // Timeline store events
  'timeline:retention':        { topicKey: 'timeStore', highlight: true, priority: 'medium' },
  'timeline:stats':            { topicKey: 'timeStore', highlight: false, priority: 'low' },

  'team:cancelled':            { topicKey: 'fluxTeam', highlight: true, priority: 'medium' },
  'team:paused':               { topicKey: 'fluxTeam', highlight: false },
  'team:resumed':              { topicKey: 'fluxTeam', highlight: false },
  'team:checkpoint':           { topicKey: 'fluxTeam', highlight: true, priority: 'high' },
}

/**
 * Prefix-based routing for event types not in EXACT_ROUTES.
 * Checked in order — first match wins.
 */
const PREFIX_ROUTES: Array<{ prefix: string; rule: RouteRule }> = [
  { prefix: 'lumen:',          rule: { topicKey: 'lumen', highlight: false } },
  { prefix: 'dyad:',           rule: { topicKey: 'dyad', highlight: false } },
  { prefix: 'flux:',           rule: { topicKey: 'fluxTeam', highlight: false } },
  { prefix: 'triad-team:',     rule: { topicKey: 'triadTeam', highlight: false } },
  { prefix: 'cell:',           rule: { topicKey: 'fluxTeam', highlight: false } },
  { prefix: 'drone:',          rule: { topicKey: 'droneSwarm', highlight: false } },
  { prefix: 'agent:',          rule: { topicKey: 'multiAgent', highlight: false } },
  { prefix: 'multi-agent:',    rule: { topicKey: 'multiAgent', highlight: false } },
  { prefix: 'thinker:',        rule: { topicKey: 'thinker', highlight: false } },
  { prefix: 'dialectic:',      rule: { topicKey: 'dialectic', highlight: false } },
  { prefix: 'consciousness:',  rule: { topicKey: 'consciousness', highlight: false } },
  { prefix: 'subconscious:',   rule: { topicKey: 'consciousness', highlight: false } },
  { prefix: 'axon:',           rule: { topicKey: 'consciousness', highlight: false, priority: 'low' } },
  { prefix: 'synapse:',        rule: { topicKey: 'consciousness', highlight: true, priority: 'medium' } },
  { prefix: 'brainstem:',      rule: { topicKey: 'consciousness', highlight: true, priority: 'medium' } },
  { prefix: 'dreamer:',        rule: { topicKey: 'memoryDreams', highlight: false } },
  { prefix: 'memory:',         rule: { topicKey: 'memoryDreams', highlight: false } },
  { prefix: 'archive:',        rule: { topicKey: 'memoryDreams', highlight: false } },
  { prefix: 'adaptive:',       rule: { topicKey: 'adaptive', highlight: false } },
  { prefix: 'improvement:',    rule: { topicKey: 'adaptive', highlight: false } },
  { prefix: 'verification:',   rule: { topicKey: 'adaptive', highlight: false } },
  { prefix: 'heart:',          rule: { topicKey: 'heart', highlight: false } },
  { prefix: 'budget:',         rule: { topicKey: 'budget', highlight: false } },
  { prefix: 'tool:',           rule: { topicKey: 'tools', highlight: false, priority: 'low' } },
  { prefix: 'provider:',       rule: { topicKey: 'llmCalls', highlight: false, priority: 'low' } },
  { prefix: 'daemon:',         rule: { topicKey: 'system', highlight: false } },
  { prefix: 'self-healer:',    rule: { topicKey: 'system', highlight: false } },
  { prefix: 'trust:',          rule: { topicKey: 'system', highlight: false } },
  { prefix: 'permission:',     rule: { topicKey: 'system', highlight: false } },
  { prefix: 'error-learner:',  rule: { topicKey: 'system', highlight: false } },
  { prefix: 'session:',        rule: { topicKey: 'sessions', highlight: false } },
  { prefix: 'turn:',           rule: { topicKey: 'sessions', highlight: false, priority: 'low' } },
  { prefix: 'team:',           rule: { topicKey: 'fluxTeam', highlight: false } },
  { prefix: 'blackboard:',     rule: { topicKey: 'blackboard', highlight: false } },
  { prefix: 'timeline:',       rule: { topicKey: 'timeStore', highlight: false } },
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

    // Look up routing rule
    const rule = this.resolveRule(type)
    if (!rule) return null // Unrecognized event type — drop

    // Check if the target topic is enabled
    if (rule.topicKey && !this.config.enabledTopics[rule.topicKey]) return null

    // Apply filter function if present
    if (rule.filter && !rule.filter(event, this.config)) return null

    // Determine mirror topics
    const mirrorTopics = [...(rule.mirrorTopics ?? [])]

    // Blackboard events from orchestration systems also mirror to the parent system's topic
    if (type === 'blackboard:entry') {
      const e = event as any
      // If we can identify the source system, mirror there too
      if (e.teamId || e.source === 'flux') mirrorTopics.push('fluxTeam')
      if (e.source === 'lumen' || e.lumenId) mirrorTopics.push('lumen')
      if (e.source === 'dyad' || e.dyadId) mirrorTopics.push('dyad')
    }

    return {
      event,
      topicKey: rule.topicKey,
      mirrorTopics: mirrorTopics.filter(t => this.config.enabledTopics[t]),
      isHighlight: rule.highlight,
      priority: rule.priorityFn ? rule.priorityFn(event) : (rule.priority ?? 'medium'),
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
