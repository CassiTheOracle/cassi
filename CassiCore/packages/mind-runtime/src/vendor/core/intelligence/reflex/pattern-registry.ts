/**
 * PatternRegistry — Storage and matching for reflex automation patterns.
 *
 * Maintains a collection of regex patterns that map user messages to tool executions.
 * Each pattern tracks usage statistics for decay-based cleanup of unused patterns.
 *
 * @example
 * ```typescript
 * const registry = new PatternRegistry(logger)
 * registry.register({
 *   pattern: '^status$',
 *   toolName: 'shell_exec',
 *   paramTemplate: { command: 'echo "System operational"' },
 *   confidence: 0.95,
 *   source: 'builtin',
 * })
 * const match = registry.match('status')
 * if (match) {
 *   registry.recordHit(match.pattern.id)
 * }
 * ```
 */

import type { ILogger } from '@cassicore/foundation'

export interface ReflexPattern {
  id: string
  /** Regex pattern string to match against user messages */
  pattern: string
  /** Compiled regex (cached) */
  compiledPattern?: RegExp
  /** Tool to execute */
  toolName: string
  /** Template for tool parameters (can reference capture groups as $1, $2, etc.) */
  paramTemplate: Record<string, unknown>
  /** Match confidence (0-1). Higher = more trusted */
  confidence: number
  /** How many times this pattern has been matched */
  hitCount: number
  /** Whether this is a built-in pattern or learned */
  source: 'builtin' | 'learned'
  /** Last time this pattern was used (ms timestamp) */
  lastUsed: number
  /** Creation time */
  createdAt: number
}

export class PatternRegistry {
  private patterns: Map<string, ReflexPattern> = new Map()
  private logger: ILogger

  constructor(logger: ILogger) {
    this.logger = logger.child('pattern-registry')
  }

  /**
   * Register a new pattern in the registry.
   *
   * @param pattern - Pattern configuration (excluding auto-generated fields)
   * @returns The generated pattern ID
   */
  register(
    pattern: Omit<ReflexPattern, 'id' | 'hitCount' | 'lastUsed' | 'createdAt' | 'compiledPattern'>,
  ): string {
    const id = `reflex:${pattern.source}:${pattern.toolName}:${this.patterns.size}`
    const compiledPattern = new RegExp(pattern.pattern)

    const fullPattern: ReflexPattern = {
      ...pattern,
      id,
      compiledPattern,
      hitCount: 0,
      lastUsed: Date.now(),
      createdAt: Date.now(),
    }

    this.patterns.set(id, fullPattern)
    this.logger.debug('Registered reflex pattern', {
      id,
      pattern: pattern.pattern,
      toolName: pattern.toolName,
      confidence: pattern.confidence,
    })

    return id
  }

  /**
   * Match a message against all registered patterns.
   * Returns the best match (highest confidence) or null if no match.
   *
   * @param message - The user message to match
   * @returns Match result with pattern and capture groups, or null
   */
  match(message: string): { pattern: ReflexPattern; captures: string[] } | null {
    let bestMatch: { pattern: ReflexPattern; captures: string[] } | null = null
    let bestConfidence = 0

    for (const pattern of this.patterns.values()) {
      if (!pattern.compiledPattern) continue

      const matches = message.match(pattern.compiledPattern)
      if (matches) {
        // Prioritize by confidence, then by hit count (more used = more trusted)
        const effectiveConfidence =
          pattern.confidence * 0.8 + Math.min(pattern.hitCount / 100, 0.2)

        if (effectiveConfidence > bestConfidence) {
          bestConfidence = effectiveConfidence
          bestMatch = {
            pattern,
            captures: matches.slice(1), // Exclude full match, keep capture groups
          }
        }
      }
    }

    if (bestMatch) {
      this.logger.debug('Matched reflex pattern', {
        patternId: bestMatch.pattern.id,
        message,
        confidence: bestMatch.pattern.confidence,
        hitCount: bestMatch.pattern.hitCount,
      })
    }

    return bestMatch
  }

  /**
   * Increment hit count and update lastUsed timestamp for a pattern.
   *
   * @param patternId - The pattern ID to record a hit for
   */
  recordHit(patternId: string): void {
    const pattern = this.patterns.get(patternId)
    if (pattern) {
      pattern.hitCount++
      pattern.lastUsed = Date.now()
      this.logger.debug('Recorded pattern hit', {
        patternId,
        hitCount: pattern.hitCount,
      })
    } else {
      this.logger.warn('Attempted to record hit for unknown pattern', { patternId })
    }
  }

  /**
   * Remove patterns that haven't been used within the specified time window.
   * Only affects learned patterns (built-in patterns are preserved).
   *
   * @param maxAgeHours - Maximum age in hours for unused patterns
   * @returns Number of patterns removed
   */
  decayUnused(maxAgeHours: number): number {
    const maxAgeMs = maxAgeHours * 60 * 60 * 1000
    const now = Date.now()
    let removed = 0

    for (const [id, pattern] of this.patterns.entries()) {
      // Never remove built-in patterns
      if (pattern.source === 'builtin') continue

      const age = now - pattern.lastUsed
      if (age > maxAgeMs) {
        this.patterns.delete(id)
        removed++
        this.logger.info('Decayed unused learned pattern', {
          id,
          ageHours: age / (60 * 60 * 1000),
          hitCount: pattern.hitCount,
        })
      }
    }

    if (removed > 0) {
      this.logger.info('Pattern decay complete', { removed, remaining: this.patterns.size })
    }

    return removed
  }

  /**
   * List all registered patterns.
   *
   * @returns Array of all patterns
   */
  list(): ReflexPattern[] {
    return Array.from(this.patterns.values())
  }

  /**
   * Remove a specific pattern by ID.
   *
   * @param patternId - The pattern ID to remove
   * @returns True if pattern was removed, false if not found
   */
  remove(patternId: string): boolean {
    const existed = this.patterns.delete(patternId)
    if (existed) {
      this.logger.debug('Removed pattern', { patternId })
    }
    return existed
  }

  /**
   * Get the total number of registered patterns.
   *
   * @returns Pattern count
   */
  count(): number {
    return this.patterns.size
  }
}
