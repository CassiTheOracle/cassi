/**
 * SteeringHandler — Parses user replies in the Telegram cognitive feed group
 * and routes them as steering commands back into the CassiCore runtime.
 *
 * Supports:
 *  - Slash commands: /mute, /unmute, /verbose, /status, /pause, /resume, etc.
 *  - Reply-to-message: Routes feedback to the module/team/session that
 *    generated the original message.
 *  - Topic context: Infers target module from which topic the reply was sent in.
 */

import type { ILogger } from '@cassicore/foundation'
import type { TelegramMessage } from './telegram-client.js'
import type { MessageTracker, TrackedMessage } from './message-tracker.js'
import type { TopicManager } from './topic-manager.js'

// Types

export interface SteeringCommand {
  /** Command type */
  type:
    | 'feedback'       // General feedback to a module/session
    | 'mute'           // Mute a topic
    | 'unmute'         // Unmute a topic
    | 'verbose'        // Toggle verbose mode
    | 'status'         // Request status dump
    | 'pause'          // Pause a team
    | 'resume'         // Resume a team
    | 'cancel'         // Cancel a team
    | 'approve'        // Approve a checkpoint
    | 'reject'         // Reject a checkpoint
    | 'steer'          // Inject steering text into a team/session
    | 'cassi'          // MCP tool access
    | 'cassicore'      // CLI-style daemon access
    | 'skip'           // Skip optional tool param
    | 'confirm'        // Confirm pending tool execution
    | 'unknown'        // Unrecognized command

  /** Target module key (e.g., 'thinker', 'lumen') */
  targetModule?: string
  /** Target session ID */
  targetSessionId?: string
  /** Target team ID */
  targetTeamId?: string
  /** Target orchestration session (Lumen/Dyad) */
  targetOrchestrationId?: string
  /** The text content (feedback, steer instruction, etc.) */
  text: string
  /** Telegram user who sent the command */
  fromUserId: number
  /** Telegram username */
  fromUsername?: string
  /** Original tracked message being replied to */
  replyContext?: TrackedMessage
}

export interface SteeringConfig {
  /** Whether steering is enabled */
  enabled: boolean
  /** Telegram user IDs allowed to steer (empty = anyone) */
  allowedUserIds: number[]
}

// Command Parsers

interface ParsedCommand {
  type: SteeringCommand['type']
  args: string[]
}

function parseSlashCommand(text: string): ParsedCommand | null {
  const trimmed = text.trim()
  if (!trimmed.startsWith('/')) return null

  const parts = trimmed.split(/\s+/)
  const cmd = parts[0].toLowerCase()
  const args = parts.slice(1)

  switch (cmd) {
    case '/mute':    return { type: 'mute', args }
    case '/unmute':  return { type: 'unmute', args }
    case '/verbose': return { type: 'verbose', args }
    case '/status':  return { type: 'status', args }
    case '/pause':   return { type: 'pause', args }
    case '/resume':  return { type: 'resume', args }
    case '/cancel':  return { type: 'cancel', args }
    case '/approve': return { type: 'approve', args }
    case '/reject':  return { type: 'reject', args }
    case '/steer':   return { type: 'steer', args }
    case '/cassi':   return { type: 'cassi', args }
    case '/cassicore': return { type: 'cassicore', args }
    case '/skip':    return { type: 'skip', args }
    case '/confirm': return { type: 'confirm', args }
    default:         return { type: 'unknown', args: [trimmed] }
  }
}

// SteeringHandler

export class SteeringHandler {
  private readonly config: SteeringConfig
  private readonly messageTracker: MessageTracker
  private readonly topicManager: TopicManager
  private readonly logger: ILogger

  /** Callback invoked when a valid steering command is parsed */
  public onCommand?: (cmd: SteeringCommand) => void

  constructor(
    config: SteeringConfig,
    messageTracker: MessageTracker,
    topicManager: TopicManager,
    logger: ILogger,
  ) {
    this.config = config
    this.messageTracker = messageTracker
    this.topicManager = topicManager
    this.logger = logger
  }

  /**
   * Handle an incoming Telegram message from the cognitive feed group.
   * Determines if it's a steering command or feedback, parses it, and
   * invokes the onCommand callback.
   */
  handleMessage(message: TelegramMessage, chatId: number): void {
    if (!this.config.enabled) return
    if (!message.text) return
    if (!message.from) return

    // Verify the message is from the cognitive feed group
    if (message.chat.id !== chatId) return

    // Check permissions
    if (this.config.allowedUserIds.length > 0) {
      if (!this.config.allowedUserIds.includes(message.from.id)) {
        this.logger.debug('[steering] Ignoring message from unauthorized user', {
          userId: message.from.id,
          username: message.from.username,
        })
        return
      }
    }

    // Determine context from reply and topic
    const replyContext = message.reply_to_message
      ? this.messageTracker.get(message.reply_to_message.message_id)
      : undefined

    const topicKey = message.message_thread_id
      ? this.topicManager.getTopicKeyByThreadId(message.message_thread_id)
      : undefined

    // Parse the message
    const parsed = parseSlashCommand(message.text)

    const command: SteeringCommand = {
      type: parsed?.type ?? 'feedback',
      text: parsed ? parsed.args.join(' ') : message.text,
      fromUserId: message.from.id,
      fromUsername: message.from.username,
      replyContext,
      targetModule: replyContext?.moduleKey ?? topicKey,
      targetSessionId: replyContext?.sessionId,
      targetTeamId: replyContext?.teamId,
      targetOrchestrationId: replyContext?.orchestrationSessionId,
    }

    // For /mute and /unmute, the arg is the topic name
    if ((command.type === 'mute' || command.type === 'unmute') && parsed?.args[0]) {
      command.targetModule = parsed.args[0].toLowerCase()
    }

    // For /steer, the text is everything after /steer
    if (command.type === 'steer' && parsed) {
      command.text = parsed.args.join(' ')
    }

    // For /pause, /resume, /cancel, try to extract team ID from context or args
    if (['pause', 'resume', 'cancel'].includes(command.type)) {
      if (parsed?.args[0]) {
        command.targetTeamId = parsed.args[0]
      }
    }

    this.logger.debug('[steering] Parsed command', {
      type: command.type,
      targetModule: command.targetModule,
      targetTeamId: command.targetTeamId,
      textLength: command.text.length,
    })

    if (this.onCommand) {
      this.onCommand(command)
    }
  }

  /**
   * Update config at runtime.
   */
  updateConfig(updates: Partial<SteeringConfig>): void {
    if (updates.enabled !== undefined) this.config.enabled = updates.enabled
    if (updates.allowedUserIds) this.config.allowedUserIds = updates.allowedUserIds
  }
}
