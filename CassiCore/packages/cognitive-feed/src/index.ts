/**
 * CognitiveFeedModule — Projects CassiCore's internal cognitive activity
 * into a Telegram supergroup with Forum Topics.
 *
 * Architecture:
 *  - Subscribes to the event bus via onAll() to capture all runtime events
 *  - Routes events through EventCurator to classify and filter them
 *  - Formats events via MessageFormatter into human-readable Telegram HTML
 *  - Sends to the appropriate forum topic via TopicManager
 *  - Curated highlights also go to the main chat
 *  - Tracks sent messages via MessageTracker for reply-based steering
 *  - Polls for replies via SteeringHandler and routes steering commands back
 *
 * The module uses a separate Telegram bot (not the main conversation channel bot)
 * to keep cognitive observation distinct from user conversations.
 *
 * @module cognitive-feed
 */

import { BaseCognitiveModule } from '../base/cognitive-module.js'
import { TelegramClient } from './telegram-client.js'
import { TopicManager, TOPIC_DEFINITIONS } from './topic-manager.js'
import { EventCurator } from './event-curator.js'
import { MessageFormatter } from './message-formatter.js'
import { MessageTracker } from './message-tracker.js'
import { SteeringHandler, type SteeringCommand } from './steering-handler.js'
import { GeneralChatHandler } from './general-chat-handler.js'
import { RateLimiter, type QueuedMessage } from './rate-limiter.js'
import { InteractiveToolSession, splitForTelegram } from '../../tools/interactive-tool-session.js'
import type { ToolDefinition } from '../../tools/interactive-tool-session.js'
import type { ILogger } from '../../../types/interfaces.js'
import type { RuntimeEvent } from '../../../types/events.js'

// Config Types

export interface CognitiveFeedConfig {
  enabled: boolean
  telegram: {
    token: string
    chatId: number
    pollIntervalMs: number
  }
  highlights: {
    enabled: boolean
    minConfidence: number
    minSeverity: 'low' | 'medium' | 'high'
  }
  topics: {
    autoCreate: boolean
    dyad: boolean
    lumen: boolean
    fluxTeam: boolean
    triadTeam: boolean
    droneSwarm: boolean
    multiAgent: boolean
    thinker: boolean
    dialectic: boolean
    consciousness: boolean
    memoryDreams: boolean
    adaptive: boolean
    heart: boolean
    system: boolean
    llmCalls: boolean
    blackboard: boolean
  }
  rateLimit: {
    messagesPerSecond: number
    batchWindowMs: number
    maxMessageLength: number
  }
  steering: {
    enabled: boolean
    allowedUserIds: number[]
  }
}

const DEFAULT_CONFIG: CognitiveFeedConfig = {
  enabled: false,
  telegram: {
    token: '',
    chatId: 0,
    pollIntervalMs: 3000,
  },
  highlights: {
    enabled: true,
    minConfidence: 0.5,
    minSeverity: 'medium',
  },
  topics: {
    autoCreate: true,
    dyad: true,
    lumen: true,
    fluxTeam: true,
    triadTeam: true,
    droneSwarm: true,
    multiAgent: true,
    thinker: true,
    dialectic: true,
    consciousness: true,
    memoryDreams: true,
    adaptive: true,
    heart: true,
    system: true,
    llmCalls: false, // Off by default — very noisy
    blackboard: true,
  },
  rateLimit: {
    messagesPerSecond: 20,
    batchWindowMs: 500,
    maxMessageLength: 3500,
  },
  steering: {
    enabled: true,
    allowedUserIds: [],
  },
}

// Module

export class CognitiveFeedModule extends BaseCognitiveModule {
  readonly name = 'cognitive-feed'
  readonly priority = 5 // Low priority — observation only, runs after everything else

  private feedConfig: CognitiveFeedConfig = { ...DEFAULT_CONFIG }
  private client!: TelegramClient
  private topicManager!: TopicManager
  private curator!: EventCurator
  private formatter!: MessageFormatter
  private tracker!: MessageTracker
  private steering!: SteeringHandler
  private generalChat!: GeneralChatHandler
  private rateLimiter!: RateLimiter
  private activeToolSessions = new Map<number, InteractiveToolSession>()

  private pollTimer: ReturnType<typeof setInterval> | null = null
  private pollOffset = 0
  private eventUnsubscriber: (() => void) | null = null
  private msgCounter = 0
  private isShuttingDown = false
  private adminApiUrl = 'http://127.0.0.1:7433'

  constructor(logger: ILogger) {
    super(logger)
  }


  override async init(): Promise<void> {
    await super.init()

    // Load config
    this.loadFeedConfig()

    if (!this.feedConfig.enabled) {
      this.logger.info('[cognitive-feed] Disabled in config — skipping initialization')
      return
    }

    // Resolve token: prefer env var, fall back to config
    if (!this.feedConfig.telegram.token) {
      const envToken = process.env.COGNITIVE_FEED_TELEGRAM_TOKEN
      if (envToken) {
        this.feedConfig.telegram.token = envToken
        this.logger.debug('[cognitive-feed] Using token from COGNITIVE_FEED_TELEGRAM_TOKEN env var')
      }
    }

    if (!this.feedConfig.telegram.token || !this.feedConfig.telegram.chatId) {
      this.logger.warn('[cognitive-feed] Enabled but missing telegram token or chatId — disabling')
      this.feedConfig.enabled = false
      return
    }

    // Initialize components
    this.client = new TelegramClient(
      { token: this.feedConfig.telegram.token },
      this.logger,
    )

    this.topicManager = new TopicManager(
      this.client,
      this.feedConfig.telegram.chatId,
      this.logger,
    )

    this.curator = new EventCurator({
      minConfidence: this.feedConfig.highlights.minConfidence,
      minSeverity: this.feedConfig.highlights.minSeverity,
      enabledTopics: this.feedConfig.topics as unknown as Record<string, boolean>,
    })

    this.formatter = new MessageFormatter()

    this.tracker = new MessageTracker()

    this.steering = new SteeringHandler(
      {
        enabled: this.feedConfig.steering.enabled,
        allowedUserIds: this.feedConfig.steering.allowedUserIds,
      },
      this.tracker,
      this.topicManager,
      this.logger,
    )

    this.rateLimiter = new RateLimiter(
      this.feedConfig.rateLimit,
      (msg) => this.sendMessage(msg),
      this.logger,
    )

    // General chat session bridge
    const adminPort = this.config?.get<number>('daemon.port', 7433) ?? 7433
    this.adminApiUrl = `http://127.0.0.1:${adminPort}`
    this.generalChat = new GeneralChatHandler(
      this.client,
      this.feedConfig.telegram.chatId,
      this.logger,
      { adminApiUrl: this.adminApiUrl },
    )

    // Wire steering command handler
    this.steering.onCommand = (cmd) => this.handleSteeringCommand(cmd)

    this.logger.info('[cognitive-feed] Initialized')
  }

  override async start(): Promise<void> {
    await super.start()

    if (!this.feedConfig.enabled) return

    // Validate bot token
    const me = await this.client.validateToken()
    if (!me) {
      this.logger.error('[cognitive-feed] Failed to validate bot token — disabling')
      this.feedConfig.enabled = false
      return
    }
    this.logger.info(`[cognitive-feed] Bot authenticated as @${me.username ?? me.first_name}`)

    // Create/verify forum topics
    if (this.feedConfig.topics.autoCreate) {
      await this.topicManager.ensureTopics(
        this.feedConfig.topics as unknown as Record<string, boolean>,
      )
    }

    await this.client.setMyCommands([
      { command: 'cassi', description: 'MCP tools: list, invoke, or run agents' },
      { command: 'cassicore', description: 'Daemon CLI (boot/model/provider)' },
      { command: 'help', description: 'Show available commands' },
      { command: 'start', description: 'Initialize the bot' },
      { command: 'cancel', description: 'Cancel current operation' },
      { command: 'skip', description: 'Skip optional parameter' },
      { command: 'confirm', description: 'Confirm tool execution' },
      { command: 'status', description: 'Show cognitive feed status' },
    ]).catch(() => {})

    // Start rate limiter
    this.rateLimiter.start()

    // Subscribe to ALL events on the bus
    this.subscribeToEvents()

    // Start polling for steering replies
    if (this.feedConfig.steering.enabled) {
      this.startPollLoop()
    }

    // Send startup notification
    await this.sendStartupMessage(me)

    this.logger.info('[cognitive-feed] Started — listening for events')
  }

  override async stop(): Promise<void> {
    this.isShuttingDown = true

    // Unsubscribe from events
    if (this.eventUnsubscriber) {
      this.eventUnsubscriber()
      this.eventUnsubscriber = null
    }

    // Stop polling
    this.stopPollLoop()

    // Stop general chat handler (abort active streams)
    if (this.generalChat) {
      this.generalChat.stop()
    }

    // Stop rate limiter (drains queue)
    if (this.rateLimiter) {
      this.rateLimiter.stop()
    }

    // Send shutdown notification
    if (this.feedConfig.enabled && this.client) {
      const chatId = this.feedConfig.telegram.chatId
      await this.client.sendMessage(
        chatId,
        '<b>[System]</b> CassiCore shutting down \u{1F534}',
        { disableNotification: true },
      ).catch(() => {}) // Best effort
    }

    await super.stop()
    this.logger.info('[cognitive-feed] Stopped')
  }


  private subscribeToEvents(): void {
    if (!this.eventBus) {
      this.logger.warn('[cognitive-feed] No event bus — cannot subscribe to events')
      return
    }

    // Subscribe to all events using the bus's onAll method if available,
    // otherwise subscribe to individual event types
    const bus = this.eventBus as any

    if (typeof bus.onAll === 'function') {
      this.eventUnsubscriber = bus.onAll((event: RuntimeEvent) => {
        this.handleBusEvent(event)
      })
    } else if (typeof bus.on === 'function') {
      // Fallback: subscribe to key event prefixes
      const unsubs: Array<() => void> = []
      const keyTypes = [
        'lumen:*', 'dyad:*', 'flux:*', 'team:*', 'triad-team:*', 'cell:*',
        'drone:*', 'agent:*', 'multi-agent:*',
        'thinker:*', 'dialectic:*', 'consciousness:*', 'subconscious:*',
        'dreamer:*', 'memory:*', 'heart:*', 'adaptive:*', 'improvement:*',
        'provider:*', 'budget:*', 'self-healer:*', 'trust:*', 'permission:*',
        'session:created', 'session:ended',
        'blackboard:*', 'verification:*',
      ]
      for (const type of keyTypes) {
        try {
          const unsub = bus.on(type, (event: RuntimeEvent) => this.handleBusEvent(event))
          if (typeof unsub === 'function') unsubs.push(unsub)
        } catch {
          // Some event types might not be supported — skip
        }
      }
      this.eventUnsubscriber = () => {
        for (const u of unsubs) {
          try { u() } catch { /* best effort */ }
        }
      }
    }
  }

  /**
   * Handle a single runtime event: curate, format, and enqueue for sending.
   */
  private handleBusEvent(event: RuntimeEvent): void {
    if (this.isShuttingDown) return
    if (!this.feedConfig.enabled) return

    // Don't feed our own events back
    const type = event.type as string
    if (type.startsWith('cognitive-feed:')) return

    // Curate: determine routing, highlight status, priority
    const curated = this.curator.curate(event)
    if (!curated) return

    // Format messages
    const verboseText = this.formatter.formatVerbose(curated)
    const highlightText = curated.isHighlight && this.feedConfig.highlights.enabled
      ? this.formatter.formatHighlight(curated)
      : null

    // Record event in General chat's cognitive context buffer
    // (uses highlight text if available, otherwise verbose — stripped of HTML)
    const contextText = highlightText ?? verboseText
    const topicDef = curated.topicKey ? this.topicManager.getDefinition(curated.topicKey) : null
    this.generalChat.recordEvent(
      contextText,
      curated.topicKey,
      topicDef?.displayName ?? 'Highlights',
    )

    const chatId = this.feedConfig.telegram.chatId
    const e = event as any
    const baseContext = {
      eventType: type,
      moduleKey: curated.topicKey ?? 'system',
      sessionId: e.sessionId as string | undefined,
      teamId: e.teamId as string | undefined,
      orchestrationSessionId: (e.lumenSessionId ?? e.dyadSessionId ?? e.orchestrationId) as string | undefined,
    }

    // Send to primary topic
    if (curated.topicKey) {
      const threadId = this.topicManager.getThreadId(curated.topicKey)
      if (threadId) {
        const id = `topic:${curated.topicKey}:${++this.msgCounter}`
        this.rateLimiter.enqueue({
          id,
          text: verboseText,
          chatId,
          threadId,
          priority: curated.priority,
          timestamp: Date.now(),
        })
      }
    }

    // Send to mirror topics (e.g., blackboard → parent system)
    for (const mirrorKey of curated.mirrorTopics) {
      const threadId = this.topicManager.getThreadId(mirrorKey)
      if (threadId) {
        const id = `mirror:${mirrorKey}:${++this.msgCounter}`
        this.rateLimiter.enqueue({
          id,
          text: verboseText,
          chatId,
          threadId,
          priority: 'low',
          timestamp: Date.now(),
        })
      }
    }

    // Send highlight to main chat
    if (highlightText) {
      const id = `highlight:${++this.msgCounter}`
      this.rateLimiter.enqueue({
        id,
        text: highlightText,
        chatId,
        priority: curated.priority,
        timestamp: Date.now(),
      })
    }
  }


  /**
   * Send a single message via the Telegram client.
   * Used as the callback for the RateLimiter.
   */
  private async sendMessage(msg: QueuedMessage): Promise<number | null> {
    try {
      if (msg.editMessageId) {
        await this.client.editMessage(msg.chatId, msg.editMessageId, msg.text)
        return msg.editMessageId
      }

      const messageId = await this.client.sendMessage(msg.chatId, msg.text, {
        threadId: msg.threadId,
        disableNotification: msg.priority === 'low',
      })

      // Track the message for steering
      if (messageId) {
        this.tracker.track({
          messageId,
          eventType: msg.id.split(':')[1] ?? 'unknown',
          topicKey: msg.threadId
            ? this.topicManager.getTopicKeyByThreadId(msg.threadId) ?? null
            : null,
          moduleKey: msg.id.split(':')[1] ?? 'system',
          timestamp: msg.timestamp,
        })
      }

      return messageId
    } catch (err) {
      this.logger.warn('[cognitive-feed] Failed to send message', {
        id: msg.id,
        error: String(err),
      })
      return null
    }
  }


  private startPollLoop(): void {
    if (this.pollTimer) return

    // Use sequential long polling — each poll waits for the previous to complete
    // before starting the next one. This avoids the Telegram "Conflict" error
    // caused by overlapping getUpdates requests.
    const pollLoop = async () => {
      while (!this.isShuttingDown) {
        try {
          const updates = await this.client.getUpdates(this.pollOffset, 25)
          if (!updates || updates.length === 0) continue

          for (const update of updates) {
            this.pollOffset = Math.max(this.pollOffset, update.update_id + 1)

            if (update.message) {
              const msg = update.message
              const isGeneralChat = !msg.message_thread_id
              const isFromOurGroup = msg.chat.id === this.feedConfig.telegram.chatId
              const isSlashCommand = msg.text?.trim().startsWith('/')

              const hasActiveToolSession = !!msg.from && this.activeToolSessions.get(msg.from.id)?.isActive

              if (isFromOurGroup && isGeneralChat && !isSlashCommand && msg.text && !hasActiveToolSession) {
                // General chat plain text → full session bridge
                this.generalChat.handleMessage(msg).catch(err => {
                  this.logger.warn('[cognitive-feed] General chat handler error', { error: String(err) })
                })
              } else {
                // Topic messages, slash commands → steering handler
                this.steering.handleMessage(msg, this.feedConfig.telegram.chatId)
              }
            }
          }
        } catch (err) {
          if (!this.isShuttingDown) {
            this.logger.debug('[cognitive-feed] Poll error', { error: String(err) })
            // Brief pause before retrying on error
            await new Promise(r => setTimeout(r, 2000))
          }
        }
      }
    }

    // Start the loop (non-blocking — runs in background)
    pollLoop().catch(() => {})
    this.logger.debug('[cognitive-feed] Poll loop started (sequential long polling)')
  }

  private stopPollLoop(): void {
    if (this.pollTimer) {
      clearInterval(this.pollTimer)
      this.pollTimer = null
    }
  }


  private handleSteeringCommand(cmd: SteeringCommand): void {
    const chatId = this.feedConfig.telegram.chatId

    if (cmd.type === 'cassi' || cmd.type === 'cassicore' || cmd.type === 'skip' || cmd.type === 'confirm') {
      this.handleCassiCommand(cmd).catch(err => {
        this.client.sendMessage(chatId, `<b>[CognitiveFeed]</b> Command failed: ${String(err)}`)
      })
      return
    }

    if (cmd.type === 'cancel' && cmd.fromUserId) {
      const toolSession = this.activeToolSessions.get(cmd.fromUserId)
      if (toolSession?.isActive) {
        const message = toolSession.cancel()
        this.activeToolSessions.delete(cmd.fromUserId)
        this.client.sendMessage(chatId, message)
        return
      }
    }

    if (cmd.type === 'feedback' && cmd.fromUserId) {
      const session = this.activeToolSessions.get(cmd.fromUserId)
      if (session?.isActive && cmd.text) {
        this.handleCassiFreeformInput(cmd.fromUserId, chatId, cmd.text).catch(err => {
          this.client.sendMessage(chatId, `<b>[CognitiveFeed]</b> Input failed: ${String(err)}`)
        })
        return
      }
    }

    switch (cmd.type) {
      case 'status': {
        const status = this.getStatusReport()
        this.client.sendMessage(chatId, status, {
          threadId: cmd.replyContext
            ? this.topicManager.getThreadId(cmd.replyContext.topicKey ?? '') ?? undefined
            : undefined,
        })
        break
      }

      case 'mute': {
        const topic = cmd.targetModule ?? cmd.text
        if (topic && this.feedConfig.topics[topic as keyof typeof this.feedConfig.topics] !== undefined) {
          (this.feedConfig.topics as Record<string, boolean>)[topic] = false
          this.curator.updateConfig({ enabledTopics: this.feedConfig.topics as unknown as Record<string, boolean> })
          this.client.sendMessage(chatId, `<b>[CognitiveFeed]</b> Muted: ${topic}`)
        }
        break
      }

      case 'unmute': {
        const topic = cmd.targetModule ?? cmd.text
        if (topic) {
          (this.feedConfig.topics as Record<string, boolean>)[topic] = true
          this.curator.updateConfig({ enabledTopics: this.feedConfig.topics as unknown as Record<string, boolean> })
          this.client.sendMessage(chatId, `<b>[CognitiveFeed]</b> Unmuted: ${topic}`)
        }
        break
      }

      case 'pause':
      case 'resume':
      case 'cancel': {
        // Emit a team control event on the bus
        if (cmd.targetTeamId && this.eventBus) {
          this.emit({
            type: `cognitive-feed:steering:${cmd.type}`,
            teamId: cmd.targetTeamId,
            fromUserId: cmd.fromUserId,
            fromUsername: cmd.fromUsername,
            timestamp: Date.now(),
          } as any)
          this.client.sendMessage(chatId,
            `<b>[CognitiveFeed]</b> ${cmd.type} sent to team ${cmd.targetTeamId}`,
          )
        } else {
          this.client.sendMessage(chatId,
            `<b>[CognitiveFeed]</b> No team ID found. Use: /${cmd.type} &lt;teamId&gt;`,
          )
        }
        break
      }

      case 'approve':
      case 'reject': {
        if (this.eventBus) {
          this.emit({
            type: `cognitive-feed:steering:${cmd.type}`,
            teamId: cmd.targetTeamId,
            feedback: cmd.text,
            fromUserId: cmd.fromUserId,
            timestamp: Date.now(),
          } as any)
          this.client.sendMessage(chatId,
            `<b>[CognitiveFeed]</b> ${cmd.type} sent${cmd.text ? ': ' + cmd.text.slice(0, 100) : ''}`,
          )
        }
        break
      }

      case 'steer':
      case 'feedback': {
        // Emit steering/feedback event that other modules can pick up
        if (this.eventBus) {
          this.emit({
            type: 'cognitive-feed:steering:feedback',
            targetModule: cmd.targetModule,
            targetSessionId: cmd.targetSessionId,
            targetTeamId: cmd.targetTeamId,
            targetOrchestrationId: cmd.targetOrchestrationId,
            text: cmd.text,
            fromUserId: cmd.fromUserId,
            fromUsername: cmd.fromUsername,
            timestamp: Date.now(),
          } as any)

          if (cmd.text.length > 0) {
            this.client.sendMessage(chatId,
              `<b>[CognitiveFeed]</b> Feedback routed to ${cmd.targetModule ?? 'system'}`,
              { threadId: cmd.replyContext
                ? this.topicManager.getThreadId(cmd.replyContext.topicKey ?? '') ?? undefined
                : undefined,
              },
            )
          }
        }
        break
      }
    }
  }


  private loadFeedConfig(): void {
    if (!this.config) return

    try {
      const raw = this.config.get<Partial<CognitiveFeedConfig>>('intelligence.cognitiveFeed', {})
      this.feedConfig = this.mergeConfig(DEFAULT_CONFIG, raw)
    } catch {
      // Config key doesn't exist yet — use defaults
    }

    // Watch for config changes
    if (this.config) {
      this.config.onChanged('intelligence.cognitiveFeed', (newVal) => {
        this.logger.info('[cognitive-feed] Config changed, reloading')
        this.feedConfig = this.mergeConfig(DEFAULT_CONFIG, newVal as Partial<CognitiveFeedConfig>)

        // Update curator config
        this.curator?.updateConfig({
          minConfidence: this.feedConfig.highlights.minConfidence,
          minSeverity: this.feedConfig.highlights.minSeverity,
          enabledTopics: this.feedConfig.topics as unknown as Record<string, boolean>,
        })

        // Update steering config
        this.steering?.updateConfig({
          enabled: this.feedConfig.steering.enabled,
          allowedUserIds: this.feedConfig.steering.allowedUserIds,
        })
      })
    }
  }

  private mergeConfig(
    defaults: CognitiveFeedConfig,
    overrides: Partial<CognitiveFeedConfig>,
  ): CognitiveFeedConfig {
    return {
      enabled: overrides.enabled ?? defaults.enabled,
      telegram: {
        ...defaults.telegram,
        ...(overrides.telegram ?? {}),
      },
      highlights: {
        ...defaults.highlights,
        ...(overrides.highlights ?? {}),
      },
      topics: {
        ...defaults.topics,
        ...(overrides.topics ?? {}),
      },
      rateLimit: {
        ...defaults.rateLimit,
        ...(overrides.rateLimit ?? {}),
      },
      steering: {
        ...defaults.steering,
        ...(overrides.steering ?? {}),
      },
    }
  }


  private async sendStartupMessage(
    me: { id: number; first_name: string; username?: string },
  ): Promise<void> {
    const chatId = this.feedConfig.telegram.chatId
    const topicCount = this.topicManager.getAllTopicIds().size
    const enabledModules = TOPIC_DEFINITIONS
      .filter(t => (this.feedConfig.topics as Record<string, boolean>)[t.key])
      .map(t => t.displayName)

    const msg = [
      '<b>[System]</b> CassiCore Cognitive Feed online \u{1F7E2}',
      '',
      `<b>Bot:</b> @${me.username ?? me.first_name}`,
      `<b>Topics:</b> ${topicCount} active`,
      `<b>Modules:</b> ${enabledModules.join(', ')}`,
      `<b>Highlights:</b> ${this.feedConfig.highlights.enabled ? 'on' : 'off'}`,
      `<b>Steering:</b> ${this.feedConfig.steering.enabled ? 'on' : 'off'}`,
      '',
      '<i>Use /status for detailed report, /mute &lt;topic&gt; to silence a topic</i>',
    ].join('\n')

    await this.client.sendMessage(chatId, msg)
  }

  private getStatusReport(): string {
    const topics = this.topicManager.getAllTopicIds()
    const parts = [
      '<b>\u{1F4CA} Cognitive Feed Status</b>',
      '',
      `<b>Queue depth:</b> ${this.rateLimiter.queueDepth}`,
      `<b>Messages tracked:</b> ${this.tracker.size}`,
      `<b>Active topics:</b> ${topics.size}`,
      '',
      '<b>Topics:</b>',
    ]

    for (const [key, threadId] of topics) {
      const def = this.topicManager.getDefinition(key)
      const enabled = (this.feedConfig.topics as Record<string, boolean>)[key] ? '\u2705' : '\u274C'
      parts.push(`  ${enabled} ${def?.displayName ?? key} (${threadId})`)
    }

    return parts.join('\n')
  }

  private async handleCassiCommand(cmd: SteeringCommand): Promise<void> {
    const chatId = this.feedConfig.telegram.chatId
    const userId = cmd.fromUserId
    const tokens = cmd.text.trim().length > 0 ? cmd.text.trim().split(/\s+/) : []
    const session = this.activeToolSessions.get(userId)

    if (cmd.type === 'skip') {
      if (!session?.isActive) {
        await this.client.sendMessage(chatId, '<b>[CognitiveFeed]</b> No active tool session.')
        return
      }
      const result = await session.skip()
      return this.respondWithSessionResult(chatId, userId, result)
    }

    if (cmd.type === 'confirm') {
      if (!session?.isActive) {
        await this.client.sendMessage(chatId, '<b>[CognitiveFeed]</b> Nothing to confirm.')
        return
      }
      const result = await session.confirm()
      this.activeToolSessions.delete(userId)
      return this.respondText(chatId, result.isError ? `❌ ${result.result}` : result.result)
    }

    if (cmd.type === 'cassicore') {
      await this.handleCassicoreCli(chatId, tokens)
      return
    }

    // /cassi
    if (tokens.length === 0) {
      await this.respondText(chatId, await this.fetchCatalogList())
      return
    }

    if (tokens[0].toLowerCase() === 'agent') {
      const toolPayload = this.mapAgentCommand(tokens.slice(1))
      if (!toolPayload) {
        await this.client.sendMessage(chatId, '<b>[CognitiveFeed]</b> Usage: /cassi agent lumen|dyad|team ...')
        return
      }
      return this.executeToolAndRespond(chatId, toolPayload.tool, toolPayload.input)
    }

    const catalog = await this.fetchCatalog()
    if (!catalog) {
      await this.client.sendMessage(chatId, '<b>[CognitiveFeed]</b> Failed to fetch tool catalog.')
      return
    }

    const category = tokens[0].toLowerCase()
    if (tokens.length === 1 && catalog.categories[category]) {
      const toolNames = catalog.categories[category]
      const lines = [
        `<b>${category.toUpperCase()} tools</b>`,
        '',
        ...catalog.tools
          .filter((t: any) => toolNames.includes(t.name))
          .map((t: any) => `• <code>${t.name}</code> — ${escapeHtml(t.description)}`),
      ]
      await this.respondText(chatId, lines.join('\n'))
      return
    }

    const toolName = tokens[0]
    const toolDef = catalog.tools.find((t: any) => t.name === toolName)
    if (!toolDef) {
      await this.client.sendMessage(chatId, `<b>[CognitiveFeed]</b> Unknown tool: <code>${escapeHtml(toolName)}</code>`) 
      return
    }

    const inlineParams: Record<string, string> = {}
    for (const token of tokens.slice(1)) {
      const eq = token.indexOf('=')
      if (eq > 0) inlineParams[token.slice(0, eq)] = token.slice(eq + 1)
    }

    const newSession = new InteractiveToolSession(toolName, toolDef as ToolDefinition)
    const result = await newSession.start(Object.keys(inlineParams).length > 0 ? inlineParams : undefined)
    if ('prompt' in result) {
      this.activeToolSessions.set(userId, newSession)
      await this.client.sendMessage(chatId, result.prompt)
      return
    }
    await this.respondText(chatId, result.isError ? `❌ ${result.result}` : result.result)
  }

  private async handleCassiFreeformInput(userId: number, chatId: number, text: string): Promise<void> {
    const session = this.activeToolSessions.get(userId)
    if (!session?.isActive) return
    const result = await session.receiveInput(text)
    await this.respondWithSessionResult(chatId, userId, result)
  }

  private async respondWithSessionResult(
    chatId: number,
    userId: number,
    result: { prompt: string } | { result: string; isError: boolean },
  ): Promise<void> {
    if ('prompt' in result) {
      await this.client.sendMessage(chatId, result.prompt)
      return
    }
    this.activeToolSessions.delete(userId)
    await this.respondText(chatId, result.isError ? `❌ ${result.result}` : result.result)
  }

  private async respondText(chatId: number, text: string): Promise<void> {
    for (const chunk of splitForTelegram(text)) {
      await this.client.sendMessage(chatId, chunk)
    }
  }

  private async fetchCatalog(): Promise<any | null> {
    try {
      const res = await fetch(`${this.adminApiUrl}/tools/catalog`)
      if (!res.ok) return null
      return await res.json()
    } catch {
      return null
    }
  }

  private async fetchCatalogList(): Promise<string> {
    const catalog = await this.fetchCatalog()
    if (!catalog) return '<b>[CognitiveFeed]</b> Failed to fetch tool catalog.'
    const lines: string[] = [`<b>CassiCore MCP Tools</b> (${catalog.count})`, '']
    for (const [cat, tools] of Object.entries(catalog.categories as Record<string, string[]>)) {
      if (tools.length === 0) continue
      lines.push(`<b>${cat.toUpperCase()}</b> (${tools.length})`)
      lines.push(escapeHtml(tools.join(', ')))
      lines.push('')
    }
    lines.push('Agents: /cassi agent lumen|dyad|team')
    return lines.join('\n')
  }

  private async executeToolAndRespond(chatId: number, tool: string, input: Record<string, unknown>): Promise<void> {
    try {
      const res = await fetch(`${this.adminApiUrl}/tools/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tool, input }),
      })
      const data = await res.json() as any
      const text = this.extractToolText(data)
      await this.respondText(chatId, data?.isError ? `❌ ${text}` : text)
    } catch (err) {
      await this.client.sendMessage(chatId, `<b>[CognitiveFeed]</b> Tool failed: ${String(err)}`)
    }
  }

  private async handleCassicoreCli(chatId: number, args: string[]): Promise<void> {
    const sub = (args[0] || 'help').toLowerCase()
    const rest = args.slice(1)

    if (sub === 'boot' && (rest[0] || 'status') === 'status') {
      try {
        const res = await fetch(`${this.adminApiUrl}/health`)
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data = await res.json() as any
        const lines = [
          '<b>CassiCore Daemon</b>',
          `PID: ${data.pid ?? 'unknown'}`,
          `Sessions: ${data.sessions ?? 'unknown'}`,
          `Admin API: ${escapeHtml(this.adminApiUrl)}`,
        ]
        await this.client.sendMessage(chatId, lines.join('\n'))
      } catch (err) {
        await this.client.sendMessage(chatId, `<b>[CognitiveFeed]</b> Status failed: ${String(err)}`)
      }
      return
    }

    if (sub === 'model' && (rest[0] || 'routing') === 'routing') {
      return this.executeToolAndRespond(chatId, 'model_directive', { action: 'get' })
    }

    if (sub === 'model' && rest[0] === 'list') {
      return this.executeToolAndRespond(chatId, 'models_list', {})
    }

    if (sub === 'provider' && ((rest[0] || 'list') === 'list' || rest[0] === 'health')) {
      return this.executeToolAndRespond(chatId, 'providers', { includeHealth: true })
    }

    if (sub === 'provider' && rest[0] === 'metrics') {
      return this.executeToolAndRespond(chatId, 'provider_metrics', rest[1] ? { providerId: rest[1] } : {})
    }

    if (sub === 'provider' && rest[0] === 'reset' && rest[1]) {
      return this.executeToolAndRespond(chatId, 'provider_config', { action: 'reset', providerId: rest[1] })
    }

    await this.client.sendMessage(chatId, [
      '<b>CassiCore CLI</b>',
      '',
      '/cassicore boot status',
      '/cassicore model list|routing',
      '/cassicore provider list|health|metrics [id]|reset <id>',
    ].join('\n'))
  }

  private mapAgentCommand(args: string[]): { tool: string; input: Record<string, unknown> } | null {
    const agentType = (args[0] || '').toLowerCase()
    const sub = (args[1] || 'help').toLowerCase()
    const rest = args.slice(2)

    if (agentType === 'lumen') {
      switch (sub) {
        case 'start': return rest.length ? { tool: 'lumen_project', input: { goal: rest.join(' ') } } : null
        case 'status': return rest[0] ? { tool: 'lumen_status', input: { jobId: rest[0] } } : null
        case 'watch': return rest[0] ? { tool: 'lumen_watch', input: { sessionId: rest[0] } } : null
        case 'cancel': return rest[0] ? { tool: 'lumen_cancel', input: { sessionId: rest[0] } } : null
        case 'jobs': return { tool: 'lumen_jobs', input: {} }
        case 'sessions': return { tool: 'lumen_sessions', input: {} }
        case 'health': return { tool: 'lumen_health', input: {} }
        case 'messages': return rest[0] ? { tool: 'lumen_messages', input: { sessionId: rest[0] } } : null
        case 'postures': return rest[0] ? { tool: 'lumen_postures', input: { sessionId: rest[0] } } : null
        case 'tool-calls': return rest[0] ? { tool: 'lumen_tool_calls', input: { sessionId: rest[0] } } : null
        case 'events': return rest[0] ? { tool: 'lumen_events', input: { sessionId: rest[0] } } : null
        case 'blackboard': return rest[0] ? { tool: 'lumen_blackboard', input: { sessionId: rest[0] } } : null
        case 'progress': return rest[0] ? { tool: 'lumen_progress', input: { sessionId: rest[0] } } : null
        default: return null
      }
    }

    if (agentType === 'dyad') {
      switch (sub) {
        case 'start': return rest.length ? { tool: 'dyad_project', input: { goal: rest.join(' ') } } : null
        case 'status': return rest[0] ? { tool: 'dyad_status', input: { jobId: rest[0] } } : null
        case 'watch': return rest[0] ? { tool: 'dyad_watch', input: { sessionId: rest[0] } } : null
        case 'cancel': return rest[0] ? { tool: 'dyad_cancel', input: { sessionId: rest[0] } } : null
        case 'jobs': return { tool: 'dyad_jobs', input: {} }
        case 'sessions': return { tool: 'dyad_sessions', input: {} }
        case 'health': return { tool: 'dyad_health', input: {} }
        case 'progress': return rest[0] ? { tool: 'dyad_progress', input: { sessionId: rest[0] } } : null
        case 'messages': return rest[0] ? { tool: 'dyad_messages', input: { sessionId: rest[0] } } : null
        case 'tool-calls': return rest[0] ? { tool: 'dyad_tool_calls', input: { sessionId: rest[0] } } : null
        case 'events': return rest[0] ? { tool: 'dyad_events', input: { sessionId: rest[0] } } : null
        case 'blackboard': return rest[0] ? { tool: 'dyad_blackboard', input: { sessionId: rest[0] } } : null
        default: return null
      }
    }

    if (agentType === 'team') {
      switch (sub) {
        case 'list': return { tool: 'flux_team', input: { action: 'list' } }
        case 'status': return { tool: 'flux_team', input: { action: 'status', teamId: rest[0] } }
        case 'tree': return { tool: 'flux_team', input: { action: 'tree', teamId: rest[0] } }
        case 'pause': return rest[0] ? { tool: 'flux_team', input: { action: 'pause', teamId: rest[0] } } : null
        case 'resume': return rest[0] ? { tool: 'flux_team', input: { action: 'resume', teamId: rest[0] } } : null
        case 'cancel': return rest[0] ? { tool: 'flux_team', input: { action: 'cancel', teamId: rest[0] } } : null
        case 'checkpoints': return { tool: 'flux_team', input: { action: 'checkpoints', teamId: rest[0] } }
        case 'inspect': return { tool: 'flux_inspect', input: rest[0] ? { teamId: rest[0] } : {} }
        case 'watch': return rest[0] ? { tool: 'flux_watch', input: { teamId: rest[0] } } : null
        default: return null
      }
    }

    return null
  }

  private extractToolText(data: unknown): string {
    if (typeof data === 'string') return data
    if (Array.isArray((data as any)?.content)) {
      return (data as any).content
        .filter((c: any) => c?.type === 'text')
        .map((c: any) => c.text as string)
        .join('\n')
    }
    return JSON.stringify(data, null, 2)
  }
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}
