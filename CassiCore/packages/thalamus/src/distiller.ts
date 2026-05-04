/**
 * Tool-Result Distiller — LLM-driven semantic compression of file-read tool results.
 *
 * Turns large tool results (80KB file reads) into concise findings (~500 chars)
 * keyed to the session's active goal. Distillation is non-blocking: it runs
 * in the background after curate() and the summary is available next turn.
 *
 * Two-tier memory model:
 *   Hot (full content) → Warm (LLM-distilled summary) → Recoverable (original in SQLite)
 *
 * Only distills read-class tools. Write/edit/error results are never distilled.
 */

import type { ILogger } from '../../../types/interfaces.js'
import { isReadTool } from './classifier.js'

export interface DistillationResult {
  /** Tool use ID (links to the tool_use block) */
  toolUseId: string
  /** File path extracted from tool input */
  filePath: string
  /** Goal-context the distillation was keyed to */
  goalHash: string
  /** The distilled summary (~500 chars) */
  summary: string
  /** Original content length (chars) */
  originalChars: number
  /** Compression ratio */
  ratio: number
  /** When this was distilled */
  distilledAt: number
}

export interface PendingDistillation {
  toolUseId: string
  filePath: string
  content: string
  goalContext: string
}

const DISTILLATION_PROMPT = `You are a code analysis distiller. Given a file's contents and a task context, produce a concise finding summary.

Rules:
- Maximum 500 characters
- Focus on what's relevant to the task context
- Include key function/class names, line numbers, and relationships
- Note any patterns, anti-patterns, or architectural decisions visible
- If the file is configuration, summarize the key settings
- Do NOT include pleasantries or meta-commentary — just the findings

Task context: {goal}

File: {path}
Content:
{content}

Finding:`

const MAX_DISTILLATION_INPUT = 30000
const MAX_SUMMARY_CHARS = 500

export class ToolResultDistiller {
  constructor(private readonly logger: ILogger) {}

  /**
   * Build a cache key from file path + goal hash.
   * Same file for same goal = same distillation.
   */
  buildCacheKey(filePath: string, goalContext: string): string {
    const goalHash = this.hashString(goalContext)
    return `${filePath}::${goalHash}`
  }

  /**
   * Extract pending distillations from a set of messages.
   * Returns read-class tool results that haven't been distilled yet.
   */
  extractPending(
    messages: any[],
    goalContext: string,
    existingSummaries: Map<string, string>,
  ): PendingDistillation[] {
    const toolUseMap = new Map<string, { name: string; input: any }>()
    const pending: PendingDistillation[] = []

    // First pass: build tool_use map
    for (const msg of messages) {
      if (msg?.role === 'assistant' && Array.isArray(msg.content)) {
        for (const block of msg.content) {
          if (block?.type === 'tool_use' && block.id && block.name) {
            toolUseMap.set(block.id, { name: block.name, input: block.input })
          }
        }
      }
    }

    // Second pass: find read tool_results that could be distilled
    for (const msg of messages) {
      if (msg?.role !== 'user' || !Array.isArray(msg.content)) continue

      for (const block of msg.content) {
        if (block?.type !== 'tool_result' || !block.tool_use_id) continue

        const toolUse = toolUseMap.get(block.tool_use_id)
        if (!toolUse || !isReadTool(toolUse.name)) continue

        const content = typeof block.content === 'string'
          ? block.content
          : Array.isArray(block.content)
            ? block.content.map((c: any) => c.text ?? c.content ?? String(c)).join('\n')
            : String(block.content)

        // Skip small results — not worth the LLM call
        if (content.length < 2000) continue

        const filePath = toolUse.input?.file_path ?? toolUse.input?.path ?? toolUse.input?.relative_path ?? ''
        if (!filePath) continue

        // Skip if already distilled for this goal
        const cacheKey = this.buildCacheKey(filePath, goalContext)
        if (existingSummaries.has(cacheKey)) continue

        pending.push({
          toolUseId: block.tool_use_id,
          filePath,
          content: content.slice(0, MAX_DISTILLATION_INPUT),
          goalContext,
        })
      }
    }

    return pending
  }

  /**
   * Distill a single tool result using the LLM handle.
   * Returns null if distillation fails (non-fatal).
   */
  async distill(
    pending: PendingDistillation,
    complete: (messages: Array<{ role: string; content: string }>) => Promise<{ response: string }>,
  ): Promise<DistillationResult | null> {
    const prompt = DISTILLATION_PROMPT
      .replace('{goal}', pending.goalContext.slice(0, 500))
      .replace('{path}', pending.filePath)
      .replace('{content}', pending.content)

    try {
      const result = await complete([
        { role: 'user', content: prompt },
      ])

      const summary = result.response.slice(0, MAX_SUMMARY_CHARS).trim()
      if (!summary) return null

      return {
        toolUseId: pending.toolUseId,
        filePath: pending.filePath,
        goalHash: this.hashString(pending.goalContext),
        summary,
        originalChars: pending.content.length,
        ratio: summary.length / pending.content.length,
        distilledAt: Date.now(),
      }
    } catch (err) {
      this.logger.warn('Distillation failed', { filePath: pending.filePath, error: String(err) })
      return null
    }
  }

  private hashString(s: string): string {
    let hash = 0
    for (let i = 0; i < s.length; i++) {
      const chr = s.charCodeAt(i)
      hash = ((hash << 5) - hash) + chr
      hash |= 0
    }
    return Math.abs(hash).toString(36)
  }
}
