/**
 * Bridge Spark Extractor — Generate sparks from session events
 *
 * Bridge-adapted version of Constellation's SparkExtractor. Instead of
 * diffing BranchDigests between sweeps, this extracts sparks from
 * individual session events: user prompts, tool results, memory recalls,
 * and constellation radiance broadcasts.
 *
 * Each spark competes for Focus slots in the LocusBridge's attentional
 * workspace. The extractor doesn't score sparks — it creates them with
 * zeroed luminance. The LocusBridge scores them during evaluation.
 */

import type { ILogger } from '@cassicore/foundation'
import type { BridgeSpark, BridgeSparkType, BridgeLuminanceScore } from './types.js'

let sparkCounter = 0
function nextSparkId(): string {
  return `bridge-spark-${++sparkCounter}-${Date.now().toString(36)}`
}

/**
 * Base urgency scores by bridge spark type.
 * These are starting points — the LocusBridge adjusts during scoring.
 */
export const BASE_URGENCY: Record<BridgeSparkType, number> = {
  'user-intent': 0.80,
  'constellation-radiance': 0.70,
  'tool-discovery': 0.60,
  'code-reference': 0.50,
  'memory-recall': 0.40,
  'compaction-recovery': 0.85,
  'reasoning_block': 0.55,
}

export const BASE_NOVELTY: Record<BridgeSparkType, number> = {
  'user-intent': 0.75,
  'tool-discovery': 0.70,
  'constellation-radiance': 0.65,
  'code-reference': 0.55,
  'compaction-recovery': 0.50,
  'memory-recall': 0.45,
  'reasoning_block': 0.80,
}


export interface BridgeSparkExtractorDeps {
  logger: ILogger
}

export class BridgeSparkExtractor {
  private logger: ILogger

  constructor(deps: BridgeSparkExtractorDeps) {
    this.logger = deps.logger.child?.('bridge-spark-extractor') ?? deps.logger
  }

  /**
   * Extract a spark from a user prompt.
   * Parses intent, extracts file references and key concepts.
   */
  fromUserPrompt(
    sessionId: string,
    content: string,
    goal?: string,
  ): BridgeSpark {
    const files = this.extractFileReferences(content)
    const summary = this.summarizeContent(content, 200)

    return this.createSpark(
      sessionId,
      summary,
      'user-intent',
      goal ?? summary,
      files,
    )
  }

  /**
   * Extract a spark from a significant tool result.
   * File reads, grep results, code changes — anything that reveals information.
   */
  fromToolResult(
    sessionId: string,
    toolName: string,
    content: string,
    goal?: string,
  ): BridgeSpark | null {
    if (!content || content.length < 20) return null

    const files = this.extractFileReferences(content)
    const summary = `[${toolName}] ${this.summarizeContent(content, 150)}`

    return this.createSpark(
      sessionId,
      summary,
      'tool-discovery',
      goal ?? `Tool: ${toolName}`,
      files,
    )
  }

  /**
   * Extract a spark from a code file reference or modification.
   */
  fromCodeReference(
    sessionId: string,
    filePath: string,
    action: string,
    content?: string,
    goal?: string,
  ): BridgeSpark {
    const summary = content
      ? `${action}: ${filePath} — ${this.summarizeContent(content, 100)}`
      : `${action}: ${filePath}`

    return this.createSpark(
      sessionId,
      summary,
      'code-reference',
      goal ?? `Code: ${filePath}`,
      [filePath],
    )
  }

  /**
   * Extract a spark from a memory recall event.
   */
  fromMemoryRecall(
    sessionId: string,
    content: string,
    source: string,
    goal?: string,
  ): BridgeSpark {
    const summary = `Memory (${source}): ${this.summarizeContent(content, 150)}`

    return this.createSpark(
      sessionId,
      summary,
      'memory-recall',
      goal ?? `Memory recall from ${source}`,
      [],
    )
  }

  /**
   * Forward a Constellation radiance broadcast as a bridge spark.
   * Active Constellation insights become bridge-level attention.
   */
  fromConstellationRadiance(
    sessionId: string,
    content: string,
    sourceHelixId: string,
    goal?: string,
  ): BridgeSpark {
    const summary = `Constellation [${sourceHelixId}]: ${this.summarizeContent(content, 150)}`

    return this.createSpark(
      sessionId,
      summary,
      'constellation-radiance',
      goal ?? `Constellation radiance from ${sourceHelixId}`,
      this.extractFileReferences(content),
    )
  }

  /**
   * Create a compaction-recovery spark from current focus state.
   * Preserves attentional state across compaction events.
   */
   fromCompactionRecovery(
     sessionId: string,
     focusSummary: string,
     relevantFiles: string[],
   ): BridgeSpark {
     return this.createSpark(
       sessionId,
       `Recovery: ${focusSummary}`,
       'compaction-recovery',
       focusSummary,
       relevantFiles,
     )
   }

   /**
    * Extract a spark from assistant reasoning content.
    * Captures the assistant's active thinking as attentional focus.
    */
   fromReasoning(
     sessionId: string,
     content: string,
     goal?: string,
   ): BridgeSpark {
     const files = this.extractFileReferences(content)
     const summary = this.summarizeContent(content, 300)

     return this.createSpark(
       sessionId,
       summary,
       'reasoning_block',
       goal ?? summary,
       files,
     )
   }

   /**
    * Reset counter (for testing).
    */
  reset(): void {
    sparkCounter = 0
  }

  // --- Private ---

  private createSpark(
    sessionId: string,
    content: string,
    type: BridgeSparkType,
    goal: string,
    files: string[],
  ): BridgeSpark {
    const spark: BridgeSpark = {
      sparkId: nextSparkId(),
      sourceSessionId: sessionId,
      content,
      type,
      luminance: this.zeroLuminance(),
      sparkedAt: Date.now(),
      sourceGoal: goal,
      relevantFiles: files.slice(0, 10),
    }

    this.logger.debug('Spark created', {
      sparkId: spark.sparkId,
      type,
      contentLength: content.length,
      files: files.length,
    })

    return spark
  }

  private zeroLuminance(): BridgeLuminanceScore {
    return { novelty: 0, urgency: 0, relevance: 0, sourceCredibility: 0, composite: 0 }
  }

  /**
   * Extract file paths from content. Matches common path patterns.
   */
  private extractFileReferences(content: string): string[] {
    const paths = new Set<string>()

    // Match file paths with extensions (e.g., core/intelligence/index.ts)
    const pathRegex = /(?:^|[\s"'`(])([a-zA-Z0-9._/-]+\.[a-zA-Z]{1,5})(?:[\s"'`):,]|$)/gm
    let match: RegExpExecArray | null
    while ((match = pathRegex.exec(content)) !== null) {
      const p = match[1]
      if (p && p.includes('/') && !p.startsWith('http') && !p.startsWith('//')) {
        paths.add(p)
      }
    }

    return Array.from(paths)
  }

  /**
   * Truncate content to maxLen while preserving word boundaries.
   */
  private summarizeContent(content: string, maxLen: number): string {
    if (content.length <= maxLen) return content.trim()

    const truncated = content.slice(0, maxLen)
    const lastSpace = truncated.lastIndexOf(' ')
    if (lastSpace > maxLen * 0.7) {
      return truncated.slice(0, lastSpace) + '...'
    }
    return truncated + '...'
  }
}
