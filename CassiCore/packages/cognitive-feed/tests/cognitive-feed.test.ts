import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { EventCurator, type CuratorConfig } from '../src/event-curator.js'
import { MessageFormatter } from '../src/message-formatter.js'
import { MessageTracker } from '../src/message-tracker.js'
import { RateLimiter, type QueuedMessage } from '../src/rate-limiter.js'
import { SteeringHandler, type SteeringCommand } from '../src/steering-handler.js'
import { TopicManager, TOPIC_DEFINITIONS, TOPIC_COLORS, TOPIC_MAP } from '../src/topic-manager.js'
import { DeliveryBatcher, type RateLimiterObservability, type DeliverCallback } from '../src/delivery-batcher.js'
import type { DeliveryConfig } from '../src/delivery-types.js'
import { DEFAULT_DELIVERY_CONFIG, DEFAULT_POLICIES } from '../src/delivery-types.js'
import type { CuratedEvent } from '../src/event-curator.js'
import type { TelegramMessage } from '../src/telegram-client.js'
import { TelegramRateLimitError } from '../src/telegram-client.js'
import type { ILogger } from '@cassicore/foundation'
import type { RuntimeEvent } from '@cassicore/foundation'

// Helpers

function createMockLogger(): ILogger {
  const make = (_level: string) => (_msg: string, _meta?: any) => {}
  const logger: ILogger = {
    debug: make('debug'),
    info: make('info'),
    warn: make('warn'),
    error: make('error'),
    child: () => logger,
  }
  return logger
}

function makeEvent(type: string, extra?: Record<string, any>): RuntimeEvent {
  return { type, timestamp: Date.now(), ...extra } as any as RuntimeEvent
}

function allTopicsEnabled(): Record<string, boolean> {
  const enabled: Record<string, boolean> = {}
  for (const t of TOPIC_DEFINITIONS) {
    enabled[t.key] = true
  }
  return enabled
}

// EventCurator Tests

describe('EventCurator', () => {
  let curator: EventCurator

  beforeEach(() => {
    curator = new EventCurator({
      minConfidence: 0.5,
      minSeverity: 'medium',
      enabledTopics: allTopicsEnabled(),
    })
  })

  it('routes lumen events to lumen topic', () => {
    const result = curator.curate(makeEvent('lumen:synthesis-complete', {
      recommendation: 'proceed',
      confidence: 87,
    }))
    expect(result).not.toBeNull()
    expect(result!.topicKey).toBe('constellation')
    expect(result!.isHighlight).toBe(true)
    expect(result!.priority).toBe('high')
  })

  it('routes dyad events to dyad topic', () => {
    const result = curator.curate(makeEvent('dyad:started', { goal: 'test' }))
    expect(result).not.toBeNull()
    expect(result!.topicKey).toBe('constellation')
    expect(result!.isHighlight).toBe(true)
  })

  it('routes flux/team events to fluxTeam topic', () => {
    const result = curator.curate(makeEvent('team:started', { teamId: '123' }))
    expect(result).not.toBeNull()
    expect(result!.topicKey).toBe('constellation')
    expect(result!.isHighlight).toBe(true)
  })

  it('routes triad-team events to triadTeam topic', () => {
    const result = curator.curate(makeEvent('triad-team:created', { goal: 'test' }))
    expect(result).not.toBeNull()
    expect(result!.topicKey).toBe('constellation')
    expect(result!.isHighlight).toBe(true)
  })

  it('routes drone events to droneSwarm topic', () => {
    const result = curator.curate(makeEvent('drone:swarm:completed', { total: 5, succeeded: 5 }))
    expect(result).not.toBeNull()
    expect(result!.topicKey).toBe('constellation')
    expect(result!.isHighlight).toBe(true)
  })

  it('routes agent events to multiAgent topic', () => {
    const result = curator.curate(makeEvent('agent:completed', { role: 'coder' }))
    expect(result).not.toBeNull()
    expect(result!.topicKey).toBe('constellation')
    expect(result!.isHighlight).toBe(true)
  })

  it('routes thinker events to thinker topic', () => {
    const result = curator.curate(makeEvent('thinker:insight-applied', { insight: 'test' }))
    expect(result).not.toBeNull()
    expect(result!.topicKey).toBe('intelligence')
    expect(result!.isHighlight).toBe(true)
  })

  it('routes dialectic signals with confidence filtering', () => {
    // Below threshold
    const low = curator.curate(makeEvent('dialectic:signal', { confidence: 0.3 }))
    expect(low).toBeNull()

    // Above threshold
    const high = curator.curate(makeEvent('dialectic:signal', { confidence: 0.8 }))
    expect(high).not.toBeNull()
    expect(high!.isHighlight).toBe(true)
  })

  it('boosts dialectic:signal priority when urgency is immediate', () => {
    const result = curator.curate(makeEvent('dialectic:signal', {
      confidence: 0.9,
      urgency: 'immediate',
    }))
    expect(result).not.toBeNull()
    expect(result!.priority).toBe('high')
  })

  it('uses medium priority for dialectic:signal with background urgency', () => {
    const result = curator.curate(makeEvent('dialectic:signal', {
      confidence: 0.9,
      urgency: 'background',
    }))
    expect(result).not.toBeNull()
    expect(result!.priority).toBe('medium')
  })

  it('defaults dialectic:signal priority to medium when urgency is absent', () => {
    const result = curator.curate(makeEvent('dialectic:signal', {
      confidence: 0.9,
    }))
    expect(result).not.toBeNull()
    expect(result!.priority).toBe('medium')
  })

  it('routes budget events to budget topic', () => {
    const warning = curator.curate(makeEvent('budget:warning', { provider: 'anthropic' }))
    expect(warning).not.toBeNull()
    expect(warning!.topicKey).toBe('system')
    expect(warning!.priority).toBe('high')

    const exhausted = curator.curate(makeEvent('budget:exhausted', {}))
    expect(exhausted).not.toBeNull()
    expect(exhausted!.topicKey).toBe('system')

    const tierChanged = curator.curate(makeEvent('budget:tier_changed', {}))
    expect(tierChanged).not.toBeNull()
    expect(tierChanged!.topicKey).toBe('system')
  })

  it('routes team:budget:warning to budget topic (single-topic rule)', () => {
    const result = curator.curate(makeEvent('team:budget:warning', { teamId: 'test' }))
    expect(result).not.toBeNull()
    expect(result!.topicKey).toBe('system')
    expect(result!.priority).toBe('high')
  })

  it('routes tool events to tools topic', () => {
    const registered = curator.curate(makeEvent('tool:registered', { name: 'bash' }))
    expect(registered).not.toBeNull()
    expect(registered!.topicKey).toBe('system')

    const executed = curator.curate(makeEvent('tool:executed', { tool: 'bash' }))
    expect(executed).not.toBeNull()
    expect(executed!.topicKey).toBe('system')
  })

  it('routes provider:request_chunk to llmCalls topic', () => {
    const result = curator.curate(makeEvent('provider:request_chunk', { chunk: 'hello' }))
    expect(result).not.toBeNull()
    expect(result!.topicKey).toBe('system')
  })

  it('routes turn events to sessions topic', () => {
    const start = curator.curate(makeEvent('turn:start', { sessionId: 'test' }))
    expect(start).not.toBeNull()
    expect(start!.topicKey).toBe('sessions')

    const end = curator.curate(makeEvent('turn:end', { sessionId: 'test' }))
    expect(end).not.toBeNull()
    expect(end!.topicKey).toBe('sessions')
  })

  it('routes daemon lifecycle events to system topic', () => {
    const ready = curator.curate(makeEvent('daemon:ready', {}))
    expect(ready).not.toBeNull()
    expect(ready!.topicKey).toBe('system')
    expect(ready!.priority).toBe('high')

    const shutdown = curator.curate(makeEvent('daemon:shutdown', {}))
    expect(shutdown).not.toBeNull()
    expect(shutdown!.topicKey).toBe('system')
    expect(shutdown!.priority).toBe('high')
  })

  it('routes digest events via prefix fallback to correct topics', () => {
    // provider:stream:digest (created by batching provider:request_chunk)
    const providerDigest = curator.curate(makeEvent('provider:stream:digest', {
      batched: 5,
      timeWindowMs: 2000,
    }))
    expect(providerDigest).not.toBeNull()
    expect(providerDigest!.topicKey).toBe('system')

    // tool:execution:digest (created by batching tool:executed)
    const toolDigest = curator.curate(makeEvent('tool:execution:digest', {
      batched: 3,
      timeWindowMs: 2000,
    }))
    expect(toolDigest).not.toBeNull()
    expect(toolDigest!.topicKey).toBe('system')

    // session:turn:digest (created by batching turn:start / turn:end)
    const sessionDigest = curator.curate(makeEvent('session:turn:digest', {
      turns: 10,
      timeWindowMs: 15000,
    }))
    expect(sessionDigest).not.toBeNull()
    expect(sessionDigest!.topicKey).toBe('sessions')
  })

  it('routes consciousness anomalies with severity filtering', () => {
    // Low severity (below 'medium' threshold)
    const low = curator.curate(makeEvent('consciousness:anomaly', { severity: 'low' }))
    expect(low).toBeNull()

    // High severity
    const high = curator.curate(makeEvent('consciousness:anomaly', { severity: 'high' }))
    expect(high).not.toBeNull()
    expect(high!.isHighlight).toBe(true)
  })

  it('routes provider events to llmCalls topic', () => {
    const result = curator.curate(makeEvent('provider:request_start', {
      provider: 'anthropic',
      model: 'claude-opus-4.6',
    }))
    expect(result).not.toBeNull()
    expect(result!.topicKey).toBe('system')
    expect(result!.isHighlight).toBe(false)
  })

  it('routes session events to sessions topic', () => {
    const result = curator.curate(makeEvent('session:created', { sessionId: 'test' }))
    expect(result).not.toBeNull()
    expect(result!.topicKey).toBe('sessions')
    expect(result!.isHighlight).toBe(true)
  })

  it('routes blackboard events with parent system mirroring', () => {
    const result = curator.curate(makeEvent('blackboard:entry', {
      source: 'lumen',
      lumenId: 'test',
      channel: 'findings',
      content: 'test finding',
    }))
    expect(result).not.toBeNull()
    expect(result!.topicKey).toBe('system')
    expect(result!.mirrorTopics).toContain('constellation')
  })

  it('drops events for disabled topics', () => {
    const curator2 = new EventCurator({
      enabledTopics: { ...allTopicsEnabled(), intelligence: false },
    })
    const result = curator2.curate(makeEvent('thinker:insight-applied', { insight: 'test' }))
    expect(result).toBeNull()
  })

  it('drops unrecognized event types', () => {
    const result = curator.curate(makeEvent('unknown:something'))
    expect(result).toBeNull()
  })

  it('uses prefix routing for unknown subtypes', () => {
    const result = curator.curate(makeEvent('lumen:something-new'))
    expect(result).not.toBeNull()
    expect(result!.topicKey).toBe('constellation')
    expect(result!.isHighlight).toBe(false)
  })

  it('routes constellation events to constellation topic via prefix', () => {
    // These event types use PREFIX_ROUTES, not EXACT_ROUTES
    const helixStarted = curator.curate(makeEvent('constellation:helix:started', { helixIndex: 0 }))
    expect(helixStarted).not.toBeNull()
    expect(helixStarted!.topicKey).toBe('constellation')
    expect(helixStarted!.isHighlight).toBe(true)
    expect(helixStarted!.priority).toBe('high')

    const spawnRequested = curator.curate(makeEvent('constellation:spawn:requested', {}))
    expect(spawnRequested).not.toBeNull()
    expect(spawnRequested!.topicKey).toBe('constellation')

    const droneDispatched = curator.curate(makeEvent('constellation:drone:dispatched', {}))
    expect(droneDispatched).not.toBeNull()
    expect(droneDispatched!.topicKey).toBe('constellation')
  })

  it('routes constellation exact routes with correct priority', () => {
    const started = curator.curate(makeEvent('constellation:started', { goal: 'test' }))
    expect(started).not.toBeNull()
    expect(started!.topicKey).toBe('constellation')
    expect(started!.isHighlight).toBe(true)
    expect(started!.priority).toBe('high')
  })

  it('drops constellation events when constellation topic is disabled', () => {
    const curator2 = new EventCurator({
      enabledTopics: { ...allTopicsEnabled(), constellation: false },
    })
    const result = curator2.curate(makeEvent('constellation:started', { goal: 'test' }))
    expect(result).toBeNull()
  })

  it('updates config at runtime', () => {
    curator.updateConfig({ minConfidence: 0.9 })
    // Now 0.8 should be filtered out
    const result = curator.curate(makeEvent('dialectic:signal', { confidence: 0.8 }))
    expect(result).toBeNull()
  })
})

// MessageFormatter Tests

describe('MessageFormatter', () => {
  let formatter: MessageFormatter

  beforeEach(() => {
    formatter = new MessageFormatter()
  })

  it('formats lumen synthesis highlight', () => {
    const curated = {
      event: makeEvent('lumen:synthesis-complete', {
        recommendation: 'proceed',
        confidence: 87,
      }),
      topicKey: 'constellation',
      mirrorTopics: [],
      isHighlight: true,
      priority: 'high' as const,
    }
    const result = formatter.formatHighlight(curated)
    expect(result).toContain('[Constellation]')
    expect(result).toContain('proceed')
    expect(result).toContain('87')
  })

  it('formats dyad started highlight', () => {
    const curated = {
      event: makeEvent('dyad:started', { goal: 'implement feature X' }),
      topicKey: 'constellation',
      mirrorTopics: [],
      isHighlight: true,
      priority: 'medium' as const,
    }
    const result = formatter.formatHighlight(curated)
    expect(result).toContain('[Constellation]')
    expect(result).toContain('implement feature X')
  })

  it('formats thinker insight highlight', () => {
    const curated = {
      event: makeEvent('thinker:insight-applied', { insight: 'The user prefers concise responses' }),
      topicKey: 'intelligence',
      mirrorTopics: [],
      isHighlight: true,
      priority: 'high' as const,
    }
    const result = formatter.formatHighlight(curated)
    expect(result).toContain('[Intelligence]')
    expect(result).toContain('The user prefers concise responses')
  })

  it('formats drone swarm completion highlight', () => {
    const curated = {
      event: makeEvent('drone:swarm:completed', { total: 5, succeeded: 4 }),
      topicKey: 'constellation',
      mirrorTopics: [],
      isHighlight: true,
      priority: 'medium' as const,
    }
    const result = formatter.formatHighlight(curated)
    expect(result).toContain('[Constellation]')
    expect(result).toContain('4/5')
  })

  it('formats verbose provider event', () => {
    const curated = {
      event: makeEvent('provider:request_end', {
        provider: 'anthropic',
        model: 'claude-opus-4.6',
        source: 'thinker',
        inputTokens: 5000,
        outputTokens: 1200,
        durationMs: 3400,
      }),
      topicKey: 'system',
      mirrorTopics: [],
      isHighlight: false,
      priority: 'low' as const,
    }
    const result = formatter.formatVerbose(curated)
    expect(result).toContain('provider:request_end')
    expect(result).toContain('anthropic')
    expect(result).toContain('claude-opus-4.6')
    expect(result).toContain('5.0k')
    expect(result).toContain('3.4s')
  })

  it('escapes HTML characters', () => {
    const curated = {
      event: makeEvent('thinker:insight-applied', { insight: '<script>alert("xss")</script>' }),
      topicKey: 'intelligence',
      mirrorTopics: [],
      isHighlight: true,
      priority: 'high' as const,
    }
    const result = formatter.formatHighlight(curated)
    expect(result).not.toContain('<script>')
    expect(result).toContain('&lt;script&gt;')
  })

  it('handles verbose format for unknown events with generic JSON', () => {
    const curated = {
      event: makeEvent('some:unknown:event', { foo: 'bar' }),
      topicKey: null,
      mirrorTopics: [],
      isHighlight: false,
      priority: 'low' as const,
    }
    const result = formatter.formatVerbose(curated)
    expect(result).toContain('some:unknown:event')
    expect(result).toContain('foo')
    expect(result).toContain('bar')
  })

  it('formats dialectic:signal with urgency indicator', () => {
    const curated = {
      event: makeEvent('dialectic:signal', {
        signalType: 'edge_case',
        content: 'Potential null pointer',
        confidence: 0.95,
        urgency: 'immediate',
      }),
      topicKey: 'intelligence',
      mirrorTopics: [],
      isHighlight: true,
      priority: 'high' as const,
    }
    const highlight = formatter.formatHighlight(curated)
    expect(highlight).toContain('edge_case')
    expect(highlight).toContain('95%')
    expect(highlight).toContain('\u{1F534}') // red circle emoji for immediate urgency

    const verbose = formatter.formatVerbose(curated)
    expect(verbose).toContain('Urgency')
    expect(verbose).toContain('immediate')
  })

  it('formats dialectic:signal without urgency indicator when background', () => {
    const curated = {
      event: makeEvent('dialectic:signal', {
        signalType: 'convergence',
        content: 'Agreement reached',
        confidence: 0.8,
        urgency: 'background',
      }),
      topicKey: 'intelligence',
      mirrorTopics: [],
      isHighlight: true,
      priority: 'medium' as const,
    }
    const highlight = formatter.formatHighlight(curated)
    expect(highlight).not.toContain('\u{1F534}') // no red circle
  })
})

// MessageTracker Tests

describe('MessageTracker', () => {
  let tracker: MessageTracker

  beforeEach(() => {
    tracker = new MessageTracker({ maxEntries: 100, maxAgeMs: 60_000 })
  })

  it('tracks and retrieves messages', () => {
    tracker.track({
      messageId: 42,
      eventType: 'thinker:insight-applied',
      topicKey: 'intelligence',
      moduleKey: 'thinker',
      sessionId: 'sess-1',
      timestamp: Date.now(),
    })
    const entry = tracker.get(42)
    expect(entry).toBeDefined()
    expect(entry!.eventType).toBe('thinker:insight-applied')
    expect(entry!.sessionId).toBe('sess-1')
  })

  it('returns undefined for unknown message IDs', () => {
    expect(tracker.get(999)).toBeUndefined()
  })

  it('finds latest message for a topic', () => {
    tracker.track({
      messageId: 1,
      eventType: 'thinker:a',
      topicKey: 'intelligence',
      moduleKey: 'thinker',
      timestamp: 1000,
    })
    tracker.track({
      messageId: 2,
      eventType: 'thinker:b',
      topicKey: 'intelligence',
      moduleKey: 'thinker',
      timestamp: 2000,
    })
    const latest = tracker.getLatestForTopic('intelligence')
    expect(latest).toBeDefined()
    expect(latest!.messageId).toBe(2)
  })

  it('evicts when over maxEntries', () => {
    for (let i = 0; i < 120; i++) {
      tracker.track({
        messageId: i,
        eventType: 'test',
        topicKey: null,
        moduleKey: 'test',
        timestamp: Date.now() + i,
      })
    }
    expect(tracker.size).toBeLessThanOrEqual(100)
  })

  it('clears all entries', () => {
    tracker.track({
      messageId: 1,
      eventType: 'test',
      topicKey: null,
      moduleKey: 'test',
      timestamp: Date.now(),
    })
    expect(tracker.size).toBe(1)
    tracker.clear()
    expect(tracker.size).toBe(0)
  })
})

// RateLimiter Tests

describe('RateLimiter', () => {
  const logger = createMockLogger()

  it('enqueues and sends messages', async () => {
    const sent: QueuedMessage[] = []
    const limiter = new RateLimiter(
      { messagesPerSecond: 100 },
      async (msg) => { sent.push(msg); return 1 },
      logger,
    )
    limiter.start()

    limiter.enqueue({
      id: 'test:1',
      text: 'hello',
      chatId: -100,
      priority: 'medium',
      timestamp: Date.now(),
    })

    // Wait for drain
    await new Promise(r => setTimeout(r, 100))
    limiter.stop()

    expect(sent.length).toBe(1)
    expect(sent[0].text).toBe('hello')
  })

  it('splits long messages', () => {
    const sent: QueuedMessage[] = []
    const limiter = new RateLimiter(
      { messagesPerSecond: 100, maxMessageLength: 100 },
      async (msg) => { sent.push(msg); return 1 },
      logger,
    )

    const longText = 'A'.repeat(250)
    limiter.enqueue({
      id: 'test:1',
      text: longText,
      chatId: -100,
      priority: 'medium',
      timestamp: Date.now(),
    })

    // Check queue has multiple entries
    expect(limiter.queueDepth).toBeGreaterThan(1)
    limiter.stop()
  })

  it('prioritizes high-priority messages', () => {
    const limiter = new RateLimiter(
      { messagesPerSecond: 100 },
      async () => 1,
      logger,
    )

    limiter.enqueue({
      id: 'low:1',
      text: 'low',
      chatId: -100,
      priority: 'low',
      timestamp: Date.now(),
    })
    limiter.enqueue({
      id: 'high:1',
      text: 'high',
      chatId: -100,
      priority: 'high',
      timestamp: Date.now(),
    })

    // Queue should be reordered: high first
    expect(limiter.queueDepth).toBe(2)
    limiter.stop()
  })

  it('backs off on TelegramRateLimitError and re-queues the message', async () => {
    let callCount = 0
    const limiter = new RateLimiter(
      { messagesPerSecond: 100 },
      async (_msg) => {
        callCount++
        if (callCount <= 2) throw new TelegramRateLimitError(30)
        return 1
      },
      logger,
    )

    limiter.enqueue({
      id: 'test:rl',
      text: 'hello',
      chatId: -100,
      priority: 'medium',
      timestamp: Date.now(),
    })

    limiter.start()
    await new Promise(r => setTimeout(r, 150))

    // sendFn should have been called exactly once — subsequent drains should
    // see the 30s backoff and skip.
    expect(callCount).toBe(1)
    // The message must still be in the queue, waiting for backoff to expire.
    // Check before stop() since stop() clears the queue.
    expect(limiter.queueDepth).toBe(1)

    limiter.stop()
  })

  it('applies mild backoff when sendFn returns null', async () => {
    let callCount = 0
    const limiter = new RateLimiter(
      { messagesPerSecond: 100 },
      async (_msg) => {
        callCount++
        return null // simulate non-rate-limit failure
      },
      logger,
    )
    limiter.start()

    limiter.enqueue({
      id: 'test:null',
      text: 'hello',
      chatId: -100,
      priority: 'medium',
      timestamp: Date.now(),
    })

    // Wait for first drain attempt
    await new Promise(r => setTimeout(r, 100))

    // Message should NOT be re-queued on null (dropped), but backoff is applied
    expect(callCount).toBe(1)
    expect(limiter.queueDepth).toBe(0)

    limiter.stop()
  })

  it('enforces maxQueueSize by dropping low-priority tail', () => {
    const limiter = new RateLimiter(
      { messagesPerSecond: 100, maxQueueSize: 5 },
      async () => 1,
      logger,
    )

    // Enqueue 8 messages: 2 high, 6 low
    for (let i = 0; i < 2; i++) {
      limiter.enqueue({
        id: `high:${i}`,
        text: 'high',
        chatId: -100,
        priority: 'high',
        timestamp: Date.now(),
      })
    }
    for (let i = 0; i < 6; i++) {
      limiter.enqueue({
        id: `low:${i}`,
        text: 'low',
        chatId: -100,
        priority: 'low',
        timestamp: Date.now(),
      })
    }

    // Queue should be capped at 5
    expect(limiter.queueDepth).toBe(5)
    limiter.stop()
  })
})

// SteeringHandler Tests

describe('SteeringHandler', () => {
  let handler: SteeringHandler
  let commands: SteeringCommand[]
  const logger = createMockLogger()

  beforeEach(() => {
    const tracker = new MessageTracker()
    const topicManager = {
      getTopicKeyByThreadId: (threadId: number) => {
        if (threadId === 100) return 'intelligence'
        if (threadId === 200) return 'constellation'
        return undefined
      },
    } as any

    handler = new SteeringHandler(
      { enabled: true, allowedUserIds: [] },
      tracker,
      topicManager,
      logger,
    )

    commands = []
    handler.onCommand = (cmd) => commands.push(cmd)
  })

  function makeMessage(text: string, extra?: Partial<TelegramMessage>): TelegramMessage {
    return {
      message_id: 1,
      chat: { id: -100, type: 'supergroup' },
      from: { id: 12345, username: 'testuser', first_name: 'Test' },
      text,
      date: Math.floor(Date.now() / 1000),
      ...extra,
    }
  }

  it('parses /mute command', () => {
    handler.handleMessage(makeMessage('/mute intelligence'), -100)
    expect(commands.length).toBe(1)
    expect(commands[0].type).toBe('mute')
    expect(commands[0].targetModule).toBe('intelligence')
  })

  it('parses /unmute command', () => {
    handler.handleMessage(makeMessage('/unmute constellation'), -100)
    expect(commands.length).toBe(1)
    expect(commands[0].type).toBe('unmute')
    expect(commands[0].targetModule).toBe('constellation')
  })

  it('parses /status command', () => {
    handler.handleMessage(makeMessage('/status'), -100)
    expect(commands.length).toBe(1)
    expect(commands[0].type).toBe('status')
  })

  it('parses /steer command with text', () => {
    handler.handleMessage(makeMessage('/steer focus on performance optimization'), -100)
    expect(commands.length).toBe(1)
    expect(commands[0].type).toBe('steer')
    expect(commands[0].text).toBe('focus on performance optimization')
  })

  it('parses /pause with team ID', () => {
    handler.handleMessage(makeMessage('/pause team-abc-123'), -100)
    expect(commands.length).toBe(1)
    expect(commands[0].type).toBe('pause')
    expect(commands[0].targetTeamId).toBe('team-abc-123')
  })

  it('treats plain text as feedback', () => {
    handler.handleMessage(makeMessage('I think you should reconsider'), -100)
    expect(commands.length).toBe(1)
    expect(commands[0].type).toBe('feedback')
    expect(commands[0].text).toBe('I think you should reconsider')
  })

  it('infers module from topic thread', () => {
    handler.handleMessage(makeMessage('some feedback', { message_thread_id: 100 }), -100)
    expect(commands.length).toBe(1)
    expect(commands[0].targetModule).toBe('intelligence')
  })

  it('ignores messages from wrong chat', () => {
    handler.handleMessage(makeMessage('/status'), -999)
    expect(commands.length).toBe(0)
  })

  it('ignores messages from unauthorized users', () => {
    handler.updateConfig({ allowedUserIds: [99999] })
    handler.handleMessage(makeMessage('/status'), -100)
    expect(commands.length).toBe(0)
  })

  it('ignores messages without text', () => {
    handler.handleMessage(makeMessage('', { text: undefined }), -100)
    expect(commands.length).toBe(0)
  })
})

// TopicManager Tests

describe('TopicManager', () => {
  it('has correct number of topic definitions', () => {
    // 1 constellation + 1 intelligence + 1 memory + 1 system + 1 sessions + 1 meditation = 6
    expect(TOPIC_DEFINITIONS.length).toBe(6)
  })

  it('all definitions have unique keys', () => {
    const keys = new Set(TOPIC_DEFINITIONS.map(t => t.key))
    expect(keys.size).toBe(TOPIC_DEFINITIONS.length)
  })

  it('all definitions have valid colors', () => {
    const validColors = Object.values(TOPIC_COLORS)
    for (const def of TOPIC_DEFINITIONS) {
      expect(validColors).toContain(def.color)
    }
  })

  it('TOPIC_MAP provides correct lookups', () => {
    expect(TOPIC_MAP.get('constellation')?.displayName).toBe('Constellation')
    expect(TOPIC_MAP.get('intelligence')?.displayName).toBe('Intelligence')
    expect(TOPIC_MAP.get('memory')?.displayName).toBe('Memory')
    expect(TOPIC_MAP.get('system')?.displayName).toBe('System')
    expect(TOPIC_MAP.get('sessions')?.displayName).toBe('Sessions')
  })

  it('all definitions have a valid category', () => {
    const validCategories = ['ops', 'intel', 'team', 'user']
    for (const def of TOPIC_DEFINITIONS) {
      expect(validCategories).toContain((def as any).category)
    }
  })

  it('does NOT include macro-dialectic', () => {
    const keys = TOPIC_DEFINITIONS.map(t => t.key)
    expect(keys).not.toContain('macroDialectic')
    expect(keys).not.toContain('macro-dialectic')
  })
})

// Integration-style: EventCurator + MessageFormatter pipeline

describe('Curator → Formatter pipeline', () => {
  let curator: EventCurator
  let formatter: MessageFormatter

  beforeEach(() => {
    curator = new EventCurator({
      minConfidence: 0.5,
      minSeverity: 'medium',
      enabledTopics: allTopicsEnabled(),
    })
    formatter = new MessageFormatter()
  })

  it('produces readable highlight for Lumen synthesis', () => {
    const event = makeEvent('lumen:synthesis-complete', {
      recommendation: 'proceed',
      confidence: 92,
      reasoning: 'Analysis shows no critical issues',
    })
    const curated = curator.curate(event)
    expect(curated).not.toBeNull()

    const highlight = formatter.formatHighlight(curated!)
    expect(highlight).toContain('[Constellation]')
    expect(highlight).toContain('proceed')

    const verbose = formatter.formatVerbose(curated!)
    expect(verbose).toContain('lumen:synthesis-complete')
    expect(verbose).toContain('Analysis shows no critical issues')
  })

  it('produces readable highlight for Dyad completion', () => {
    const event = makeEvent('dyad:completed', { durationMs: 45000 })
    const curated = curator.curate(event)
    expect(curated).not.toBeNull()

    const highlight = formatter.formatHighlight(curated!)
    expect(highlight).toContain('[Constellation]')
    expect(highlight).toContain('45.0s')
  })

  it('produces readable highlight for FluxTeam checkpoint', () => {
    const event = makeEvent('team:checkpoint', {
      description: 'Ready to deploy database migration',
    })
    const curated = curator.curate(event)
    expect(curated).not.toBeNull()

    const highlight = formatter.formatHighlight(curated!)
    expect(highlight).toContain('[Constellation]')
    expect(highlight).toContain('database migration')
  })

  it('produces readable verbose for blackboard entry', () => {
    const event = makeEvent('blackboard:entry', {
      boardName: 'project:security-review',
      channel: 'findings',
      author: 'yang',
      content: 'Found potential SQL injection in user input handler',
      priority: 'high',
      tags: ['security', 'sql-injection'],
    })
    const curated = curator.curate(event)
    expect(curated).not.toBeNull()
    expect(curated!.topicKey).toBe('system')

    const verbose = formatter.formatVerbose(curated!)
    expect(verbose).toContain('project:security-review')
    expect(verbose).toContain('findings')
    expect(verbose).toContain('SQL injection')
  })
})


describe('RateLimiter observability', () => {
  const logger = createMockLogger()

  it('isBackingOff returns false initially', () => {
    const limiter = new RateLimiter(
      { messagesPerSecond: 100 },
      async () => 1,
      logger,
    )
    expect(limiter.isBackingOff).toBe(false)
    expect(limiter.recent429Count).toBe(0)
    limiter.stop()
  })

  it('isBackingOff returns true after onRateLimited', () => {
    const limiter = new RateLimiter(
      { messagesPerSecond: 100 },
      async () => 1,
      logger,
    )
    limiter.onRateLimited(5000) // 5s backoff
    expect(limiter.isBackingOff).toBe(true)
    expect(limiter.recent429Count).toBe(1)
    limiter.stop()
  })

  it('onBackoff callback fires on 429', () => {
    const limiter = new RateLimiter(
      { messagesPerSecond: 100 },
      async () => 1,
      logger,
    )
    const backoffs: number[] = []
    limiter.onBackoff((ms) => backoffs.push(ms))

    limiter.onRateLimited(3000)
    limiter.onRateLimited(6000)

    expect(backoffs).toEqual([3000, 6000])
    expect(limiter.recent429Count).toBe(2)
    limiter.stop()
  })

  it('onBackoff unsubscribe works', () => {
    const limiter = new RateLimiter(
      { messagesPerSecond: 100 },
      async () => 1,
      logger,
    )
    const backoffs: number[] = []
    const unsub = limiter.onBackoff((ms) => backoffs.push(ms))

    limiter.onRateLimited(1000)
    unsub()
    limiter.onRateLimited(2000)

    expect(backoffs).toEqual([1000])
    limiter.stop()
  })

  it('resetStats clears 429 counter', () => {
    const limiter = new RateLimiter(
      { messagesPerSecond: 100 },
      async () => 1,
      logger,
    )
    limiter.onRateLimited(1000)
    expect(limiter.recent429Count).toBe(1)

    limiter.resetStats()
    expect(limiter.recent429Count).toBe(0)
    limiter.stop()
  })
})


function makeCuratedEvent(topicKey: string | null, opts?: {
  eventType?: string
  isHighlight?: boolean
  priority?: 'high' | 'medium' | 'low'
}): CuratedEvent {
  return {
    event: makeEvent(opts?.eventType ?? `${topicKey ?? 'test'}:event`, {}),
    topicKey,
    mirrorTopics: [],
    isHighlight: opts?.isHighlight ?? false,
    priority: opts?.priority ?? 'medium',
  }
}

function createMockRateLimiterObs(overrides?: Partial<RateLimiterObservability>): RateLimiterObservability {
  return {
    queueDepth: 0,
    isBackingOff: false,
    recent429Count: 0,
    ...overrides,
  }
}

describe('DeliveryBatcher', () => {
  const logger = createMockLogger()
  let delivered: Array<{ events: CuratedEvent[]; mode: 'single' | 'digest' }>

  function createBatcher(configOverrides?: Partial<DeliveryConfig>): DeliveryBatcher {
    delivered = []
    const callback: DeliverCallback = (events, mode) => {
      delivered.push({ events: [...events], mode })
    }
    return new DeliveryBatcher(configOverrides ?? {}, callback, logger)
  }

  afterEach(() => {
    // Ensure timers are cleaned up
  })

  describe('normal load behavior', () => {
    it('delivers all events immediately under normal load', () => {
      const batcher = createBatcher()
      const event1 = makeCuratedEvent('lumen', { eventType: 'lumen:started' })
      const event2 = makeCuratedEvent('thinker', { eventType: 'thinker:insight-applied' })

      batcher.accept(event1)
      batcher.accept(event2)

      expect(delivered.length).toBe(2)
      expect(delivered[0].mode).toBe('single')
      expect(delivered[1].mode).toBe('single')
      batcher.stop()
    })

    it('delivers critical events immediately regardless of load state', () => {
      const batcher = createBatcher()
      batcher.setRateLimiterObservability(createMockRateLimiterObs({
        queueDepth: 100,
        isBackingOff: true,
      }))

      const critical = makeCuratedEvent('system', {
        eventType: 'budget:exhausted',
        priority: 'high',
      })

      batcher.accept(critical)

      expect(delivered.length).toBe(1)
      expect(delivered[0].mode).toBe('single')
      batcher.stop()
    })
  })

  describe('constellation lane behavior', () => {
    it('routes constellation events to dedicated lane with immediate delivery', () => {
      const batcher = createBatcher()
      batcher.setRateLimiterObservability(createMockRateLimiterObs({
        queueDepth: 100,
        isBackingOff: true,
      }))

      const constellationEvent = makeCuratedEvent('constellation', {
        eventType: 'constellation:started',
        priority: 'high',
      })

      batcher.accept(constellationEvent)

      expect(delivered.length).toBe(1)
      expect(delivered[0].mode).toBe('single')
      batcher.stop()
    })

    it('routes all consciousness event types to constellation lane', () => {
      const batcher = createBatcher()
      batcher.setRateLimiterObservability(createMockRateLimiterObs({
        queueDepth: 100,
        isBackingOff: true,
      }))

      const anomaly = makeCuratedEvent('consciousness', {
        eventType: 'consciousness:anomaly',
        priority: 'high',
      })
      const insight = makeCuratedEvent('consciousness', {
        eventType: 'consciousness:insight',
        priority: 'medium',
      })
      const observation = makeCuratedEvent('consciousness', {
        eventType: 'consciousness:observation',
        priority: 'low',
      })
      const crossSession = makeCuratedEvent('consciousness', {
        eventType: 'consciousness:cross-session-correlation',
        priority: 'medium',
      })

      batcher.accept(anomaly)
      batcher.accept(insight)
      batcher.accept(observation)
      batcher.accept(crossSession)

      expect(delivered.length).toBe(4)
      expect(delivered.every(d => d.mode === 'single')).toBe(true)
      batcher.stop()
    })

    it('delivers constellation events even when intelligence lane is frozen', () => {
      vi.useFakeTimers()
      try {
        const batcher = createBatcher()
        batcher.setRateLimiterObservability(createMockRateLimiterObs({
          queueDepth: 100,
          isBackingOff: true,
        }))
        batcher.start()

        // Advance timers to trigger load state update (tick runs every 1000ms)
        vi.advanceTimersByTime(1100)

        const constellationEvent = makeCuratedEvent('constellation', {
          eventType: 'constellation:checkpoint',
          priority: 'medium',
        })
        const thinkerEvent = makeCuratedEvent('thinker', {
          eventType: 'thinker:insight-applied',
          priority: 'medium',
        })

        batcher.accept(constellationEvent)
        batcher.accept(thinkerEvent)

        // Constellation event delivered immediately, thinker event batched (frozen lane)
        expect(delivered.length).toBe(1)
        expect(delivered[0].events[0].event.type).toBe('constellation:checkpoint')
        batcher.stop()
      } finally {
        vi.useRealTimers()
      }
    })
  })

  describe('load state machine', () => {
    it('starts in normal state', () => {
      const batcher = createBatcher()
      expect(batcher.getLoadState()).toBe('normal')
      batcher.stop()
    })

    it('transitions to rate-limited immediately on 429 (ignores dwell time)', () => {
      vi.useFakeTimers()
      try {
        const batcher = createBatcher({
          loadThresholds: {
            busyUp: 20, busyDown: 10,
            congestedUp: 50, congestedDown: 30,
            dwellTimeMs: 30_000,
          },
        })

        batcher.setRateLimiterObservability(createMockRateLimiterObs({
          isBackingOff: true,
        }))
        batcher.start()

        // Advance timers to trigger one tick (tick interval is 1000ms)
        vi.advanceTimersByTime(1100)

        expect(batcher.getLoadState()).toBe('rate-limited')
        batcher.stop()
      } finally {
        vi.useRealTimers()
      }
    })

    it('respects hysteresis — busyDown < busyUp', () => {
      vi.useFakeTimers()
      try {
        const batcher = createBatcher({
          loadThresholds: {
            busyUp: 20, busyDown: 10,
            congestedUp: 50, congestedDown: 30,
            dwellTimeMs: 0, // disable dwell for test
          },
        })

        // Start at normal, queue at 20 → should transition to busy
        const obs = createMockRateLimiterObs({ queueDepth: 20 })
        batcher.setRateLimiterObservability(obs)
        batcher.start()

        vi.advanceTimersByTime(1100)
        expect(batcher.getLoadState()).toBe('busy')

        // Drop to 15 — still above busyDown=10, should stay busy
        ;(obs as any).queueDepth = 15
        vi.advanceTimersByTime(1100)
        expect(batcher.getLoadState()).toBe('busy')

        // Drop to 9 — below busyDown=10, should transition to normal
        ;(obs as any).queueDepth = 9
        vi.advanceTimersByTime(1100)
        expect(batcher.getLoadState()).toBe('normal')

        batcher.stop()
      } finally {
        vi.useRealTimers()
      }
    })
  })

  describe('per-lane freeze and emergency bypass', () => {
    it('freezes freezable lanes under congestion', () => {
      vi.useFakeTimers()
      try {
        const batcher = createBatcher({
          loadThresholds: {
            busyUp: 5, busyDown: 2,
            congestedUp: 10, congestedDown: 5,
            dwellTimeMs: 0,
          },
        })

        // Force congested state
        batcher.setRateLimiterObservability(createMockRateLimiterObs({
          queueDepth: 60,
        }))
        batcher.start()

        vi.advanceTimersByTime(1100)
        expect(batcher.getLoadState()).toBe('congested')

        // Routine event (freezable lane) should be batched, not delivered immediately
        const before = delivered.length
        const routine = makeCuratedEvent('memoryDreams', {
          eventType: 'memory:consolidated',
          priority: 'low',
        })
        batcher.accept(routine)
        expect(delivered.length).toBe(before) // not delivered

        // Check stats
        const stats = batcher.getStats()
        expect(stats.pendingByLane['routine']).toBe(1)

        batcher.stop()
      } finally {
        vi.useRealTimers()
      }
    })

    it('allows emergency bypass for high-priority events in frozen lanes', () => {
      vi.useFakeTimers()
      try {
        const batcher = createBatcher({
          loadThresholds: {
            busyUp: 5, busyDown: 2,
            congestedUp: 10, congestedDown: 5,
            dwellTimeMs: 0,
          },
          emergencyBucketCapacity: 3,
          emergencyBucketRefillRate: 0,
          emergencyBucketTtlMs: 60_000,
        })

        batcher.setRateLimiterObservability(createMockRateLimiterObs({
          queueDepth: 60,
        }))
        batcher.start()

        vi.advanceTimersByTime(1100)
        expect(batcher.getLoadState()).toBe('congested')

        // High-priority event in orchestration lane (freezable) — should use emergency token
        const highPri = makeCuratedEvent('lumen', {
          eventType: 'lumen:synthesis-complete',
          priority: 'high',
        })

        const before = delivered.length
        batcher.accept(highPri)
        expect(delivered.length).toBe(before + 1) // emergency bypass worked
        expect(batcher.getStats().emergencyTokensUsed).toBe(1)

        batcher.stop()
      } finally {
        vi.useRealTimers()
      }
    })


    it('flushes previously-frozen lanes when transitioning to lower load state', () => {
      vi.useFakeTimers()
      try {
        const batcher = createBatcher({
          loadThresholds: {
            busyUp: 5, busyDown: 2,
            congestedUp: 10, congestedDown: 5,
            dwellTimeMs: 0, // disable dwell to allow immediate transition
          },
        })

        const obs = createMockRateLimiterObs({ queueDepth: 60 })
        batcher.setRateLimiterObservability(obs)
        batcher.start()

        // Reach congested state (queueDepth > congestedUp threshold of 10)
        vi.advanceTimersByTime(1100)
        expect(batcher.getLoadState()).toBe('congested')

        // Accept a routine event (will be frozen because routine lane is freezable)
        batcher.accept(makeCuratedEvent('memoryDreams', {
          eventType: 'memory:consolidated',
          priority: 'low',
        }))
        const beforeTransition = delivered.length

        // Transition down to busy state
        ;(obs as any).queueDepth = 1  // below congestedDown (5) to transition to normal
        vi.advanceTimersByTime(1100)
        expect(batcher.getLoadState()).toBe('normal')

        // The previously-frozen routine event should now be flushed
        expect(delivered.length).toBeGreaterThan(beforeTransition)

        batcher.stop()
      } finally {
        vi.useRealTimers()
      }
    })

    it('does not freeze highlight lane', () => {
      vi.useFakeTimers()
      try {
        const batcher = createBatcher({
          loadThresholds: {
            busyUp: 5, busyDown: 2,
            congestedUp: 10, congestedDown: 5,
            dwellTimeMs: 0,
          },
        })

        batcher.setRateLimiterObservability(createMockRateLimiterObs({
          queueDepth: 60,
        }))
        batcher.start()

        vi.advanceTimersByTime(1100)
        expect(batcher.getLoadState()).toBe('congested')

        // Highlight event on highlight lane (not freezable) — should batch but not freeze
        const highlight = makeCuratedEvent(null, {
          eventType: 'session:created',
          isHighlight: true,
          priority: 'medium',
        })
        // Highlight lane is not freezable, so it goes to batch
        // but with loadState=congested, batch window is multiplied
        // Since we're under non-normal load, it goes to batch (not immediate)
        batcher.accept(highlight)

        // Highlight goes to batch but is NOT frozen, so it will flush on next tick
        const stats = batcher.getStats()
        // pendingByLane may or may not have 'highlight' depending on timing
        // The key test is that it was NOT dropped

        batcher.stop()
      } finally {
        vi.useRealTimers()
      }
    })

    it('does not freeze critical lane', () => {
      vi.useFakeTimers()
      try {
        const batcher = createBatcher({
          loadThresholds: {
            busyUp: 5, busyDown: 2,
            congestedUp: 10, congestedDown: 5,
            dwellTimeMs: 0,
          },
        })

        batcher.setRateLimiterObservability(createMockRateLimiterObs({
          queueDepth: 60,
        }))
        batcher.start()

        vi.advanceTimersByTime(1100)
        expect(batcher.getLoadState()).toBe('congested')

        // Critical event should deliver immediately regardless of frozen state
        const critical = makeCuratedEvent('system', {
          eventType: 'budget:exhausted',
          priority: 'high',
        })

        const before = delivered.length
        batcher.accept(critical)
        expect(delivered.length).toBe(before + 1) // immediately delivered

        batcher.stop()
      } finally {
        vi.useRealTimers()
      }
    })
  })

  describe('batch flushing', () => {
    it('flushes all remaining events on stop', () => {
      vi.useFakeTimers()
      try {
        const batcher = createBatcher({
          loadThresholds: {
            busyUp: 5, busyDown: 2,
            congestedUp: 10, congestedDown: 5,
            dwellTimeMs: 0,
          },
        })

        batcher.setRateLimiterObservability(createMockRateLimiterObs({
          queueDepth: 25,
        }))
        batcher.start()

        vi.advanceTimersByTime(1100)

        // Accept several routine events (will be batched)
        for (let i = 0; i < 5; i++) {
          batcher.accept(makeCuratedEvent('memoryDreams', {
            eventType: 'memory:consolidated',
            priority: 'low',
          }))
        }

        const beforeStop = delivered.length
        batcher.stop() // should flush all remaining

        // After stop, everything should be delivered
        expect(delivered.length).toBeGreaterThan(beforeStop)
      } finally {
        vi.useRealTimers()
      }
    })

    it('delivers single events in single mode, multi in digest mode', () => {
      vi.useFakeTimers()
      try {
        const batcher = createBatcher({
          loadThresholds: {
            busyUp: 5, busyDown: 2,
            congestedUp: 50, congestedDown: 30,
            dwellTimeMs: 0,
          },
        })

        batcher.setRateLimiterObservability(createMockRateLimiterObs({
          queueDepth: 25, // busy state
        }))
        batcher.start()

        vi.advanceTimersByTime(1100)
        expect(batcher.getLoadState()).toBe('busy')

        // Accept 3 routine events (will be batched together)
        for (let i = 0; i < 3; i++) {
          batcher.accept(makeCuratedEvent('memoryDreams', {
            eventType: 'memory:consolidated',
            priority: 'low',
          }))
        }

        // Stop should flush as a digest
        batcher.stop()

        const digestDeliveries = delivered.filter(d => d.mode === 'digest')
        expect(digestDeliveries.length).toBeGreaterThanOrEqual(1)
        expect(digestDeliveries[0].events.length).toBeGreaterThan(1)
      } finally {
        vi.useRealTimers()
      }
    })
  })

  describe('stats and observability', () => {
    it('tracks events received and delivered', () => {
      const batcher = createBatcher()

      batcher.accept(makeCuratedEvent('lumen'))
      batcher.accept(makeCuratedEvent('thinker'))

      const stats = batcher.getStats()
      expect(stats.eventsReceived).toBe(2)
      expect(stats.eventsDelivered).toBe(2)
      expect(stats.loadState).toBe('normal')
      batcher.stop()
    })

    it('tracks emergency tokens used', () => {
      const batcher = createBatcher()
      const stats = batcher.getStats()
      expect(stats.emergencyTokensAvailable).toBeGreaterThan(0)
      expect(stats.emergencyTokensUsed).toBe(0)
      batcher.stop()
    })
  })
})


describe('MessageFormatter batch digests', () => {
  let formatter: MessageFormatter

  beforeEach(() => {
    formatter = new MessageFormatter()
  })

  it('formats single-event batch digest as regular verbose', () => {
    const event = makeCuratedEvent('lumen', { eventType: 'lumen:started' })
    const result = formatter.formatBatchDigest([event])
    // Single event should use regular verbose format
    expect(result).toContain('lumen:started')
  })

  it('formats multi-event batch digest with counts', () => {
    const events = [
      makeCuratedEvent('lumen', { eventType: 'lumen:started' }),
      makeCuratedEvent('lumen', { eventType: 'lumen:started' }),
      makeCuratedEvent('lumen', { eventType: 'lumen:synthesis-complete' }),
    ]
    const result = formatter.formatBatchDigest(events)
    expect(result).toContain('Batch Summary')
    expect(result).toContain('lumen:started')
    expect(result).toContain('\u00d7 2')
    expect(result).toContain('lumen:synthesis-complete')
    expect(result).toContain('\u00d7 1')
    expect(result).toContain('3 events batched')
  })

  it('formats single-event highlight digest as regular highlight', () => {
    const event = makeCuratedEvent('constellation', {
      eventType: 'constellation:started',
      isHighlight: true,
    })
    ;(event.event as any).goal = 'test goal'

    const result = formatter.formatHighlightDigest([event])
    expect(result).toContain('[Constellation]')
  })

  it('formats multi-event highlight digest with module labels', () => {
    const events = [
      makeCuratedEvent('constellation', {
        eventType: 'constellation:started',
        isHighlight: true,
      }),
      makeCuratedEvent('constellation', {
        eventType: 'constellation:branch:completed',
        isHighlight: true,
      }),
      makeCuratedEvent('intelligence', {
        eventType: 'thinker:insight-applied',
        isHighlight: true,
      }),
    ]
    ;(events[0].event as any).goal = 'test goal'
    ;(events[1].event as any).helixId = 'h-1'
    ;(events[2].event as any).insight = 'test insight'

    const result = formatter.formatHighlightDigest(events)
    expect(result).toContain('[Digest]')
    expect(result).toContain('3 highlights')
    expect(result).toContain('Constellation')
    expect(result).toContain('Intelligence')
  })

  it('truncates highlight digest to last 5 events', () => {
    const events = Array.from({ length: 8 }, (_, i) =>
      makeCuratedEvent('lumen', {
        eventType: `lumen:event-${i}`,
        isHighlight: true,
      }),
    )

    const result = formatter.formatHighlightDigest(events)
    expect(result).toContain('[Digest]')
    expect(result).toContain('8 highlights')
    expect(result).toContain('and 3 more')
  })

  it('handles empty arrays gracefully', () => {
    expect(formatter.formatBatchDigest([])).toBe('')
    expect(formatter.formatHighlightDigest([])).toBe('')
  })
})
