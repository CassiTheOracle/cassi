/**
 * BlackboardBridge — Parent↔Child Blackboard forwarding for Constellation.
 *
 * Connects a parent Helix's Blackboard to a child Helix's Blackboard,
 * allowing relevant findings/concerns/decisions to flow between them
 * and up to the Constellation-wide board.
 */

import type { ILogger } from '../../../types/interfaces.js'
import type {
  BlackboardChannel,
  BlackboardEntry,
} from '../../../types/flux-team.js'
import type { BlackboardBridgeConfig } from './types.js'

// Types

/**
 * Minimal Blackboard interface for dependency injection.
 * Avoids importing the full Blackboard class.
 */
export interface MinimalBlackboard {
  post(
    channel: BlackboardChannel,
    entry: Omit<BlackboardEntry, 'id' | 'timestamp' | 'channel'>,
  ): BlackboardEntry
  subscribe(
    channel: BlackboardChannel,
    tags: string[] | undefined,
    callback: (entry: BlackboardEntry) => void,
  ): () => void
  read(channel: BlackboardChannel, limit?: number): BlackboardEntry[]
}

/**
 * Options for creating a BlackboardBridge.
 */
export interface BlackboardBridgeOpts {
  /** Parent Helix Blackboard */
  parent: MinimalBlackboard
  /** Child Helix Blackboard */
  child: MinimalBlackboard
  /** Child Helix ID for attribution */
  childHelixId: string
  /** Logger instance */
  logger: ILogger
  /** Optional configuration overrides */
  config?: Partial<BlackboardBridgeConfig>
}

/**
 * Statistics for the BlackboardBridge.
 */
export interface BlackboardBridgeStats {
  /** Number of entries forwarded from parent to child */
  parentToChildCount: number
  /** Number of entries forwarded from child to parent */
  childToParentCount: number
  /** Number of entries dropped due to rate limiting */
  droppedCount: number
  /** Timestamp when the bridge was started */
  startedAt: number
}

// Constants

/** Maximum forwards per second per direction */
const MAX_FORWARDS_PER_SECOND = 10

/** Priority cap for escalation */
const MAX_PRIORITY = 3

/** Priority threshold for escalation */
const ESCALATION_PRIORITY_THRESHOLD = 2

// BlackboardBridge Class

/**
 * Bridges parent and child Blackboards, forwarding relevant entries
 * between them with de-duplication, priority escalation, and rate limiting.
 */
export class BlackboardBridge {
  private readonly parent: MinimalBlackboard
  private readonly child: MinimalBlackboard
  private readonly childHelixId: string
  private readonly logger: ILogger
  private readonly config: Partial<BlackboardBridgeConfig>

  // Subscription unsubscribe functions
  private unsubscribeChildFindings: (() => void) | null = null
  private unsubscribeChildConcerns: (() => void) | null = null
  private unsubscribeParentDecisions: (() => void) | null = null

  // De-duplication tracking (set of forwarded entry IDs)
  private readonly forwardedIds: Set<string> = new Set()

  // Rate limiting state (capped at 100 entries per direction to prevent unbounded growth)
  private readonly childToParentTimestamps: number[] = []
  private readonly parentToChildTimestamps: number[] = []
  private readonly maxRateLimitEntries = 100

  // Statistics
  private stats: BlackboardBridgeStats = {
    parentToChildCount: 0,
    childToParentCount: 0,
    droppedCount: 0,
    startedAt: 0,
  }

  // Running state
  private isRunning = false

  constructor(opts: BlackboardBridgeOpts) {
    this.parent = opts.parent
    this.child = opts.child
    this.childHelixId = opts.childHelixId
    this.logger = opts.logger.child('blackboard-bridge')
    this.config = opts.config ?? {}
  }

  /**
   * Start forwarding between parent and child Blackboards.
   */
  start(): void {
    if (this.isRunning) {
      this.logger.warn('Bridge already started', { childHelixId: this.childHelixId })
      return
    }

    this.logger.info('Starting BlackboardBridge', { childHelixId: this.childHelixId })

    // Subscribe to child's findings channel
    try {
      this.unsubscribeChildFindings = this.child.subscribe(
        'findings',
        undefined,
        (entry) => this.handleChildFinding(entry),
      )
      this.logger.debug('Subscribed to child findings', { childHelixId: this.childHelixId })
    } catch (err) {
      this.logger.warn('Failed to subscribe to child findings', {
        childHelixId: this.childHelixId,
        error: err instanceof Error ? err.message : String(err),
      })
    }

    // Subscribe to child's concerns channel
    try {
      this.unsubscribeChildConcerns = this.child.subscribe(
        'concerns',
        undefined,
        (entry) => this.handleChildConcern(entry),
      )
      this.logger.debug('Subscribed to child concerns', { childHelixId: this.childHelixId })
    } catch (err) {
      this.logger.warn('Failed to subscribe to child concerns', {
        childHelixId: this.childHelixId,
        error: err instanceof Error ? err.message : String(err),
      })
    }

    // Subscribe to parent's decisions channel
    try {
      this.unsubscribeParentDecisions = this.parent.subscribe(
        'decisions',
        undefined,
        (entry) => this.handleParentDecision(entry),
      )
      this.logger.debug('Subscribed to parent decisions', { childHelixId: this.childHelixId })
    } catch (err) {
      this.logger.warn('Failed to subscribe to parent decisions', {
        childHelixId: this.childHelixId,
        error: err instanceof Error ? err.message : String(err),
      })
    }

    this.isRunning = true
    this.stats.startedAt = Date.now()

    this.logger.info('BlackboardBridge started', { childHelixId: this.childHelixId })
  }

  /**
   * Stop forwarding and clean up subscriptions.
   */
  stop(): void {
    if (!this.isRunning) {
      this.logger.warn('Bridge not running', { childHelixId: this.childHelixId })
      return
    }

    this.logger.info('Stopping BlackboardBridge', { childHelixId: this.childHelixId })

    // Unsubscribe from all channels
    if (this.unsubscribeChildFindings) {
      this.unsubscribeChildFindings()
      this.unsubscribeChildFindings = null
    }

    if (this.unsubscribeChildConcerns) {
      this.unsubscribeChildConcerns()
      this.unsubscribeChildConcerns = null
    }

    if (this.unsubscribeParentDecisions) {
      this.unsubscribeParentDecisions()
      this.unsubscribeParentDecisions = null
    }

    this.isRunning = false

    this.logger.info('BlackboardBridge stopped', {
      childHelixId: this.childHelixId,
      stats: this.getStats(),
    })
  }

  /**
   * Get current bridge statistics.
   */
  getStats(): BlackboardBridgeStats {
    return { ...this.stats }
  }

  // Private Handlers

  /**
   * Handle a finding posted by the child.
   * Forwards to parent with prefix and tags.
   */
  private handleChildFinding(entry: BlackboardEntry): void {
    // De-duplication check
    if (this.forwardedIds.has(entry.id)) {
      return
    }

    // Check if we should forward all findings or only high-priority
    const forwardAll = this.config.forwardAllFindings ?? true
    if (!forwardAll && entry.priority < ESCALATION_PRIORITY_THRESHOLD) {
      return
    }

    // Rate limiting check
    if (!this.checkRateLimit('childToParent')) {
      this.stats.droppedCount++
      this.logger.warn('Rate limit exceeded for child→parent forwarding', {
        childHelixId: this.childHelixId,
        entryId: entry.id,
      })
      return
    }

    // Mark as forwarded (with size limit to prevent unbounded growth)
    if (this.forwardedIds.size >= 1000) {
      // Clear oldest 20% of entries when limit reached
      const entriesToDelete = Math.floor(1000 * 0.2)
      const entries = Array.from(this.forwardedIds).slice(0, entriesToDelete)
      for (const id of entries) {
        this.forwardedIds.delete(id)
      }
    }
    this.forwardedIds.add(entry.id)

    // Build forwarded content with prefix
    const prefixedContent = `[child:${this.childHelixId}] ${entry.content}`

    // Build tags: preserve original, add 'bridged' and 'from:{helixId}'
    const forwardedTags = [...entry.tags, 'bridged', `from:${this.childHelixId}`]

    // Calculate priority (escalate if >= threshold)
    const forwardedPriority = entry.priority >= ESCALATION_PRIORITY_THRESHOLD
      ? Math.min(entry.priority + 1, MAX_PRIORITY)
      : entry.priority

    try {
      this.parent.post('findings', {
        author: entry.author,
        content: prefixedContent,
        structured: entry.structured,
        priority: forwardedPriority,
        tags: forwardedTags,
      })

      this.stats.childToParentCount++

      this.logger.debug('Forwarded child finding to parent', {
        childHelixId: this.childHelixId,
        entryId: entry.id,
        priority: forwardedPriority,
      })
    } catch (err) {
      this.logger.warn('Failed to forward child finding to parent', {
        childHelixId: this.childHelixId,
        entryId: entry.id,
        error: err instanceof Error ? err.message : String(err),
      })
    }
  }

  /**
   * Handle a concern posted by the child.
   * Forwards to parent with prefix, tags, and priority escalation.
   */
  private handleChildConcern(entry: BlackboardEntry): void {
    // De-duplication check
    if (this.forwardedIds.has(entry.id)) {
      return
    }

    // Check minimum priority for escalation
    const minPriority = this.config.escalationPriority ?? 'high'
    const minPriorityValue = this.priorityToNumber(minPriority)
    if (entry.priority < minPriorityValue) {
      return
    }

    // Rate limiting check
    if (!this.checkRateLimit('childToParent')) {
      this.stats.droppedCount++
      this.logger.warn('Rate limit exceeded for child→parent forwarding', {
        childHelixId: this.childHelixId,
        entryId: entry.id,
      })
      return
    }

    // Mark as forwarded (with size limit to prevent unbounded growth)
    if (this.forwardedIds.size >= 1000) {
      // Clear oldest 20% of entries when limit reached
      const entriesToDelete = Math.floor(1000 * 0.2)
      const entries = Array.from(this.forwardedIds).slice(0, entriesToDelete)
      for (const id of entries) {
        this.forwardedIds.delete(id)
      }
    }
    this.forwardedIds.add(entry.id)

    // Build forwarded content with prefix
    const prefixedContent = `[child:${this.childHelixId}] ${entry.content}`

    // Build tags: preserve original, add 'bridged' and 'from:{helixId}'
    const forwardedTags = [...entry.tags, 'bridged', `from:${this.childHelixId}`]

    // Calculate priority (escalate if >= threshold)
    const forwardedPriority = entry.priority >= ESCALATION_PRIORITY_THRESHOLD
      ? Math.min(entry.priority + 1, MAX_PRIORITY)
      : entry.priority

    try {
      this.parent.post('concerns', {
        author: entry.author,
        content: prefixedContent,
        structured: entry.structured,
        priority: forwardedPriority,
        tags: forwardedTags,
      })

      this.stats.childToParentCount++

      this.logger.debug('Forwarded child concern to parent', {
        childHelixId: this.childHelixId,
        entryId: entry.id,
        priority: forwardedPriority,
      })
    } catch (err) {
      this.logger.warn('Failed to forward child concern to parent', {
        childHelixId: this.childHelixId,
        entryId: entry.id,
        error: err instanceof Error ? err.message : String(err),
      })
    }
  }

  /**
   * Handle a decision posted by the parent.
   * Forwards to child with prefix and tags.
   */
  private handleParentDecision(entry: BlackboardEntry): void {
    // De-duplication check
    if (this.forwardedIds.has(entry.id)) {
      return
    }

    // Rate limiting check
    if (!this.checkRateLimit('parentToChild')) {
      this.stats.droppedCount++
      this.logger.warn('Rate limit exceeded for parent→child forwarding', {
        childHelixId: this.childHelixId,
        entryId: entry.id,
      })
      return
    }

    // Mark as forwarded (with size limit to prevent unbounded growth)
    if (this.forwardedIds.size >= 1000) {
      // Clear oldest 20% of entries when limit reached
      const entriesToDelete = Math.floor(1000 * 0.2)
      const entries = Array.from(this.forwardedIds).slice(0, entriesToDelete)
      for (const id of entries) {
        this.forwardedIds.delete(id)
      }
    }
    this.forwardedIds.add(entry.id)

    // Build forwarded content with prefix
    const prefixedContent = `[parent] ${entry.content}`

    // Build tags: preserve original, add 'bridged' and 'from:parent'
    const forwardedTags = [...entry.tags, 'bridged', 'from:parent']

    try {
      // Forward to child's requests channel (decisions become requests for child)
      this.child.post('requests', {
        author: entry.author,
        content: prefixedContent,
        structured: entry.structured,
        priority: entry.priority,
        tags: forwardedTags,
      })

      this.stats.parentToChildCount++

      this.logger.debug('Forwarded parent decision to child', {
        childHelixId: this.childHelixId,
        entryId: entry.id,
      })
    } catch (err) {
      this.logger.warn('Failed to forward parent decision to child', {
        childHelixId: this.childHelixId,
        entryId: entry.id,
        error: err instanceof Error ? err.message : String(err),
      })
    }
  }

  // Private Helpers

  /**
   * Check if rate limit allows forwarding in the given direction.
   * Cleans up old timestamps and adds new one if allowed.
   */
  private checkRateLimit(direction: 'childToParent' | 'parentToChild'): boolean {
    const now = Date.now()
    const windowMs = 1000 // 1 second window
    const timestamps = direction === 'childToParent'
      ? this.childToParentTimestamps
      : this.parentToChildTimestamps

    // Remove timestamps outside the window
    const cutoff = now - windowMs
    while (timestamps.length > 0 && timestamps[0] < cutoff) {
      timestamps.shift()
    }

    // Prevent unbounded growth - cap the array size
    if (timestamps.length > this.maxRateLimitEntries) {
      timestamps.splice(0, timestamps.length - this.maxRateLimitEntries)
    }

    // Check if under limit
    if (timestamps.length >= MAX_FORWARDS_PER_SECOND) {
      return false
    }

    // Record this forward
    timestamps.push(now)
    return true
  }

  /**
   * Convert priority string to numeric value.
   */
  private priorityToNumber(priority: 'low' | 'medium' | 'high'): number {
    switch (priority) {
      case 'low':
        return 0
      case 'medium':
        return 1
      case 'high':
        return 2
      default:
        return 0
    }
  }
}

// Helper Function

/**
 * Create a BlackboardBridge between a parent and child Blackboard.
 *
 * @param parent - Parent Helix Blackboard
 * @param child - Child Helix Blackboard
 * @param childHelixId - Child Helix ID for attribution
 * @param logger - Logger instance
 * @returns Configured BlackboardBridge instance (not yet started)
 */
export function createBridge(
  parent: MinimalBlackboard,
  child: MinimalBlackboard,
  childHelixId: string,
  logger: ILogger,
): BlackboardBridge {
  return new BlackboardBridge({
    parent,
    child,
    childHelixId,
    logger,
  })
}
