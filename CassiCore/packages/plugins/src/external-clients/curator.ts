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

    return {
      kept: keptIndices,
      gaps,
      systemContext,
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
        }
      }

      return {
        role: digest.role,
        content: digest.text,
      }
    })
  }

  /**
   * Map curated messages back to original digest indices.
   *
   * The thalamus preserves relative order of surviving messages — it drops
   * and compresses but never reorders. We walk both arrays with two pointers:
   * for each curated message, advance the original pointer until we find a
   * role match, then record that index as kept. Gap notes (role 'system'
   * with bracketed text) are skipped as they have no original index.
   */
  private mapCuratedToIndices(
    curatedMessages: any[],
    originalDigests: ExternalMessageDigest[],
  ): number[] {
    const keptIndices: number[] = []
    let origPtr = 0

    for (const msg of curatedMessages) {
      const role = msg?.role ?? ''
      const text = typeof msg.content === 'string'
        ? msg.content
        : Array.isArray(msg.content)
          ? msg.content.map((c: any) => c?.text ?? c?.content ?? '').join('')
          : ''

      // Skip gap notes inserted by the thalamus
      if (role === 'system' && text.startsWith('[')) continue

      // Advance original pointer to find the matching message
      while (origPtr < originalDigests.length) {
        const orig = originalDigests[origPtr]
        if (orig.role === role) {
          keptIndices.push(orig.index)
          origPtr++
          break
        }
        origPtr++
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
