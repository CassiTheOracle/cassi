/**
 * PrimarySessionRouter — routes all channel messages to a single persistent
 * "Cassi conductor" session (`cassi:primary`).
 *
 * Generalizes the former TelegramDirectMode: any channel (Telegram, CLI,
 * future channels) can be routed to one unified session. Response fanout
 * delivers content back to the original channel/session for display.
 */
import type { ILogger } from '../../types/interfaces.js'

export class PrimarySessionRouter {
  readonly primarySessionId: string
  /** Per-turn: map from primarySessionId → { original sessionId, channelId } */
  private activeTurns = new Map<string, { sessionId: string; channelId: string }>()

  constructor(primarySessionId: string, private logger: ILogger) {
    this.primarySessionId = primarySessionId
  }

  /** True if the given session ID is the primary session itself. */
  isPrimary(sessionId: string): boolean {
    return sessionId === this.primarySessionId
  }

  /**
   * Track that a turn on the primary session was triggered by a message
   * on `originalSessionId` from `channelId`.
   */
  trackTurn(originalSessionId: string, channelId: string): void {
    this.activeTurns.set(this.primarySessionId, { sessionId: originalSessionId, channelId })
    this.logger.debug('PrimarySessionRouter: tracking turn', {
      primary: this.primarySessionId,
      original: originalSessionId,
      channel: channelId,
    })
  }

  /** Get the original session + channel for the current primary turn, if any. */
  getSource(): { sessionId: string; channelId: string } | undefined {
    return this.activeTurns.get(this.primarySessionId)
  }

  /** Clear turn tracking after turn ends. */
  clearTurn(): void {
    this.activeTurns.delete(this.primarySessionId)
  }
}

/**
 * Create a PrimarySessionRouter from daemon config.
 * Returns `undefined` if `channels.primarySessionId` is not set — graceful degradation.
 */
export function createPrimarySessionRouter(
  config: { get: <T>(key: string, def?: T) => T },
  logger: ILogger,
): PrimarySessionRouter | undefined {
  const primarySessionId = config.get<string>('channels.primarySessionId', '')
  if (!primarySessionId) return undefined
  return new PrimarySessionRouter(primarySessionId, logger)
}
