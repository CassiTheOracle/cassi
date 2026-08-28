/**
 * PatternLearner — Automatic pattern extraction from successful interactions.
 *
 * Observes tool executions and learns recurring message→tool mappings.
 * When the same mapping is observed multiple times, it creates a regex pattern
 * and registers it in the PatternRegistry for future reflex automation.
 *
 * Pattern generalization strategy:
 * - Escape special regex characters
 * - Replace numeric values with \\d+
 * - Replace quoted strings with "[^"]*"
 *
 * @example
 * ```typescript
 * const learner = new PatternLearner(logger, registry)
 * learner.record({
 *   userMessage: 'run the tests',
 *   toolName: 'shell_exec',
 *   toolParams: { command: 'npm test' },
 *   success: true,
 * })
 * learner.checkPromotions() // Promotes after 3 occurrences
 * ```
 */

import type { ILogger } from '@cassicore/foundation'
import { PatternRegistry } from './pattern-registry.js'

export interface LearnableInteraction {
  userMessage: string
  toolName: string
  toolParams: Record<string, unknown>
  success: boolean
}

interface PendingPattern {
  message: string
  toolName: string
  toolParams: Record<string, unknown>
  occurrences: number
  lastSeen: number
}

export class PatternLearner {
  private pendingPatterns: Map<string, PendingPattern> = new Map()
  private logger: ILogger
  private registry: PatternRegistry
  private minOccurrences: number

  constructor(
    logger: ILogger,
    registry: PatternRegistry,
    minOccurrences: number = 3,
  ) {
    this.logger = logger.child('pattern-learner')
    this.registry = registry
    this.minOccurrences = minOccurrences
  }

  /**
   * Record a successful interaction for potential learning.
   * Only successful interactions are considered for pattern learning.
   *
   * @param interaction - The interaction to record
   */
  record(interaction: LearnableInteraction): void {
    if (!interaction.success) {
      this.logger.debug('Skipping failed interaction for learning', {
        toolName: interaction.toolName,
        message: interaction.userMessage,
      })
      return
    }

    const key = this.createInteractionKey(interaction)
    const existing = this.pendingPatterns.get(key)

    if (existing) {
      existing.occurrences++
      existing.lastSeen = Date.now()
      this.logger.debug('Updated pending pattern', {
        key,
        occurrences: existing.occurrences,
      })
    } else {
      this.pendingPatterns.set(key, {
        message: interaction.userMessage,
        toolName: interaction.toolName,
        toolParams: interaction.toolParams,
        occurrences: 1,
        lastSeen: Date.now(),
      })
      this.logger.debug('Created new pending pattern', {
        key,
        message: interaction.userMessage,
        toolName: interaction.toolName,
      })
    }
  }

  /**
   * Check if any recorded patterns should be promoted to the registry.
   * A pattern is promoted after being seen minOccurrences times.
   *
   * @param minOccurrences - Override the default minimum occurrences (optional)
   */
  checkPromotions(minOccurrences?: number): void {
    const threshold = minOccurrences ?? this.minOccurrences
    const toPromote: Array<{ key: string; pattern: PendingPattern }> = []

    for (const [key, pattern] of this.pendingPatterns.entries()) {
      if (pattern.occurrences >= threshold) {
        toPromote.push({ key, pattern })
      }
    }

    for (const { key, pattern } of toPromote) {
      this.promotePattern(pattern)
      this.pendingPatterns.delete(key)
    }

    if (toPromote.length > 0) {
      this.logger.info('Promoted learned patterns', {
        count: toPromote.length,
        threshold,
      })
    }
  }

  /**
   * Create a unique key for an interaction.
   * Uses message + toolName as the learning key.
   *
   * @param interaction - The interaction to create a key for
   * @returns Unique interaction key
   */
  private createInteractionKey(interaction: LearnableInteraction): string {
    return `${interaction.userMessage.toLowerCase().trim()}::${interaction.toolName}`
  }

  /**
   * Promote a pending pattern to the registry.
   * Converts the message to a generalized regex pattern.
   *
   * @param pattern - The pending pattern to promote
   */
  private promotePattern(pattern: PendingPattern): void {
    try {
      const regexPattern = this.generalizeMessageToRegex(pattern.message)

      // Create parameter template (simple passthrough for now)
      // Future enhancement: extract variable parts and create templates
      const paramTemplate = { ...pattern.toolParams }

      // Calculate confidence based on occurrence count
      // More occurrences = higher confidence (capped at 0.95)
      const confidence = Math.min(0.75 + (pattern.occurrences - this.minOccurrences) * 0.05, 0.95)

      this.registry.register({
        pattern: regexPattern,
        toolName: pattern.toolName,
        paramTemplate,
        confidence,
        source: 'learned',
      })

      this.logger.info('Promoted learned pattern to registry', {
        message: pattern.message,
        toolName: pattern.toolName,
        regexPattern,
        confidence,
        occurrences: pattern.occurrences,
      })
    } catch (err) {
      this.logger.error('Failed to promote pattern', {
        message: pattern.message,
        toolName: pattern.toolName,
        error: String(err),
      })
    }
  }

  /**
   * Generalize a message string to a regex pattern.
   *
   * Strategy:
   * 1. Escape special regex characters
   * 2. Replace numeric values with \\d+
   * 3. Replace quoted strings with "[^"]*"
   * 4. Replace multiple whitespace with \\s+
   *
   * @param message - The original message
   * @returns Generalized regex pattern
   */
  private generalizeMessageToRegex(message: string): string {
    let pattern = message

    // Escape special regex characters (except spaces which we handle separately)
    const specialChars = /[.*+?^${}()|[\]\\]/g
    pattern = pattern.replace(specialChars, '\\$&')

    // Replace numeric values with \d+
    // Match standalone numbers or numbers within words
    pattern = pattern.replace(/\b\d+\b/g, '\\d+')

    // Replace quoted strings with "[^"]*"
    pattern = pattern.replace(/"[^"]*"/g, '"[^"]*"')
    pattern = pattern.replace(/'[^']*'/g, "'[^']*'")

    // Replace multiple whitespace with \s+
    pattern = pattern.replace(/\s+/g, '\\s+')

    // Trim and anchor the pattern
    pattern = pattern.trim()

    // Add anchors if not present
    if (!pattern.startsWith('^')) {
      pattern = '^' + pattern
    }
    if (!pattern.endsWith('$')) {
      pattern = pattern + '$'
    }

    return pattern
  }

  /**
   * Get the number of pending patterns waiting to be promoted.
   *
   * @returns Count of pending patterns
   */
  getPendingCount(): number {
    return this.pendingPatterns.size
  }

  /**
   * Clear all pending patterns (e.g., on shutdown or reset).
   */
  clear(): void {
    this.pendingPatterns.clear()
    this.logger.debug('Cleared all pending patterns')
  }
}
