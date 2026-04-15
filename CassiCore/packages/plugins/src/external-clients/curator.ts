/**
 * External Client Curation Service
 *
 * Provides thalamus-based context curation for external editor clients.
 * This is the shared layer that any editor plugin (OpenCode, Claude Code,
 * Cursor, etc.) uses to get intelligent context window management.
 *
 * The service works in "index-only" mode — it receives lightweight message
 * digests (text + role + char count) and returns which indices to keep,
 * rather than reconstructing full message objects. This preserves the
 * caller's AI SDK type fidelity while getting CassiCore's cognitive
 * scoring (GWT luminance, Cortex signals, Mnemic Field coverage).
 *
 * Architecture:
 *   External editor → ContextBridge.curate() → Admin API /context/curate/external
 *   → ExternalClientCurator.curate() → ThalamusModule.curate() → scored result
 */

import type { ILogger } from '../../../types/interfaces.js'
import type { ThalamusModule } from '../../intelligence/thalamus/index.js'
import type { CurationConfig } from '../../intelligence/thalamus/types.js'
import type {
  ExternalCurateRequest,
  ExternalCurationResult,
  ExternalMessageDigest,
  CurationGap,
} from './types.js'

interface ExternalClientCuratorDeps {
  logger: ILogger
  getThalamus: () => ThalamusModule | undefined
  getSystemContext?: (sessionId: string) => Promise<string[]>
}

export class ExternalClientCurator {
  private logger: ILogger
  private getThalamus: () => ThalamusModule | undefined
  private getSystemContext: ((sessionId: string) => Promise<string[]>) | undefined

  constructor(deps: ExternalClientCuratorDeps) {
    this.logger = deps.logger.child('external-client-curator')
    this.getThalamus = deps.getThalamus
    this.getSystemContext = deps.getSystemContext
  }

  /**
   * Curate messages for an external client using thalamus scoring.
   *
   * Converts lightweight digests into synthetic messages that the thalamus
   * can score, runs curation, then maps the result back to the original
   * indices. The caller applies the kept/gaps decisions to its own message
   * array, preserving AI SDK type fidelity.
   */
  async curate(request: ExternalCurateRequest): Promise<ExternalCurationResult> {
    const thalamus = this.getThalamus()
    if (!thalamus) {
      return this.passthroughResult(request.digests, 'thalamus_unavailable')
    }

    const { sessionId, digests, query, charBudget, config: configOverrides, clientId } = request

    if (!digests || digests.length === 0) {
      return this.passthroughResult(digests ?? [], 'empty')
    }

    // Convert digests to synthetic messages the thalamus can score
    const syntheticMessages = this.digestsToMessages(digests)

    // Build curation config, applying external client defaults
    const curateConfig: Partial<CurationConfig> = {
      ...configOverrides,
    }
    if (charBudget !== undefined) {
      curateConfig.charBudget = charBudget
    }
    // External client sessions should never be excluded
    curateConfig.excludeSessionPrefixes = []

    // Run thalamus curation
    const result = thalamus.curate(sessionId, syntheticMessages, curateConfig)

    // Map curated messages back to original indices.
    // The thalamus may drop messages and insert gap notes, but it preserves
    // the relative order of surviving messages. We walk both arrays in
    // parallel to match curated messages to their original positions.
    const keptIndices = this.mapCuratedToIndices(result.messages, digests)
    const gaps = this.buildGaps(keptIndices, digests.length)

    // Fetch system context if available
    let systemContext: string[] = []
    if (this.getSystemContext) {
      try {
        systemContext = await this.getSystemContext(sessionId)
      } catch {
        // Degrade gracefully — system context is supplementary
      }
    }

    this.logger.info('External curation completed', {
      sessionId,
      clientId: clientId ?? 'unknown',
      original: digests.length,
      kept: keptIndices.length,
      dropped: digests.length - keptIndices.length,
      gaps: gaps.length,
      charBudget: curateConfig.charBudget,
      durationMs: result.meta.durationMs,
    })

    // Calculate estimated token count for overflow detection by the caller
    const keptChars = digests
      .filter(d => keptIndices.includes(d.index))
      .reduce((sum, d) => sum + d.chars, 0)
    const systemChars = systemContext.reduce((sum, s) => sum + s.length, 0)
    const estimatedChars = keptChars + systemChars
    // Use 4 chars/token as conservative estimate (code-heavy content has lower ratio)
    const estimatedTokens = Math.ceil(estimatedChars / 4)

    return {
      kept: keptIndices,
      gaps,
      systemContext,
      estimatedTokens,
      estimatedChars,
      meta: {
        ...result.meta,
        applied: true,
      },
    }
  }

  /**
   * Convert lightweight digests into synthetic messages the thalamus can score.
   *
   * The thalamus operates on message objects with `role` and `content` fields.
   * We construct minimal synthetic messages that carry enough information for
   * the scorer (term extraction, file path detection, role-based credibility)
   * without requiring the full AI SDK message structure.
   *
   * Each synthetic message is tagged with `_originalIndex` so that
   * `mapCuratedToIndices` can recover the original digest position after
   * curation, without relying on fragile role-matching heuristics.
   */
  private digestsToMessages(digests: ExternalMessageDigest[]): any[] {
    return digests.map(digest => {
      // Reconstruct tool_use/tool_result structure when applicable
      if (digest.isToolResult && digest.toolCallId) {
        return {
          role: 'user',
          content: [{
            type: 'tool_result',
            tool_use_id: digest.toolCallId,
            content: digest.text,
          }],
          // WHY: The digest text is truncated (≤2000 chars) but the real message
          // in the editor's context has `digest.chars` chars. The scorer must use
          // real char count for budget tracking, or it will underestimate message
          // sizes by 10-50x and keep too many messages.
          _originalChars: digest.chars,
          _originalIndex: digest.index,
        }
      }

      if (digest.toolName && digest.toolCallId) {
        return {
          role: 'assistant',
          content: [{
            type: 'tool_use',
            id: digest.toolCallId,
            name: digest.toolName,
            input: {},
          }, {
            type: 'text',
            text: digest.text,
          }],
          _originalChars: digest.chars,
          _originalIndex: digest.index,
        }
      }

      return {
        role: digest.role,
        content: digest.text,
        _originalChars: digest.chars,
        _originalIndex: digest.index,
      }
    })
  }

  /**
   * Map curated messages back to original digest indices.
   *
   * Synthetic messages are tagged with `_originalIndex` in `digestsToMessages`.
   * The tag survives the thalamus compressor (which uses `{ ...msg, ... }` spread)
   * and assembly (kept messages are referenced directly or spread). We simply read
   * the tag back to recover the original position.
   *
   * Gap notes created by `assembleByThreshold` carry the index of the message they
   * annotate (via the same spread), so they are counted as kept. Synthesized system
   * messages with no `_originalIndex` are skipped.
   */
  private mapCuratedToIndices(
    curatedMessages: any[],
    originalDigests: ExternalMessageDigest[],
  ): number[] {
    const keptIndices: number[] = []

    for (const msg of curatedMessages) {
      const idx = msg?._originalIndex
      if (typeof idx !== 'number') continue
      if (idx >= 0 && idx < originalDigests.length) {
        keptIndices.push(idx)
      }
    }

    return keptIndices
  }

  /**
   * Build gap annotations from the kept indices.
   * A gap exists wherever consecutive kept indices have a span > 1.
   */
  private buildGaps(keptIndices: number[], totalCount: number): CurationGap[] {
    const gaps: CurationGap[] = []
    const keptSet = new Set(keptIndices)

    let gapStart = -1
    for (let i = 0; i < totalCount; i++) {
      if (!keptSet.has(i)) {
        if (gapStart === -1) gapStart = i
      } else {
        if (gapStart !== -1) {
          const count = i - gapStart
          if (count >= 2) {
            gaps.push({
              start: gapStart,
              end: i - 1,
              count,
              summary: `[${count} message${count !== 1 ? 's' : ''} omitted]`,
            })
          }
          gapStart = -1
        }
      }
    }

    // Trailing gap
    if (gapStart !== -1) {
      const count = totalCount - gapStart
      if (count >= 2) {
        gaps.push({
          start: gapStart,
          end: totalCount - 1,
          count,
          summary: `[${count} messages omitted]`,
        })
      }
    }

    return gaps
  }

  /**
   * Passthrough result when curation can't be applied.
   * Returns all indices as kept.
   */
  private passthroughResult(
    digests: ExternalMessageDigest[],
    reason: string,
  ): ExternalCurationResult {
    return {
      kept: digests.map(d => d.index),
      gaps: [],
      systemContext: [],
      meta: {
        originalCount: digests.length,
        curatedCount: digests.length,
        originalChars: digests.reduce((sum, d) => sum + d.chars, 0),
        curatedChars: digests.reduce((sum, d) => sum + d.chars, 0),
        compressed: 0,
        deduped: 0,
        dropped: 0,
        gapNotes: 0,
        durationMs: 0,
        skipped: true,
        reason,
        applied: false,
      },
    }
  }
}
