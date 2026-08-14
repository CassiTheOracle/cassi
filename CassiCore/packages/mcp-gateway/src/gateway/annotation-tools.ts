/**
 * Annotation Tools Module
 * MCP gateway tool for iterative Self-Model Field annotation.
 *
 * Tool: _annotate_mnemic_fields
 *
 * Workflow:
 *   1. First call (no params) → returns first unannotated engram
 *   2. Call with { engramId, summary } → stores summary, returns next
 *   3. Call with { engramId, skip: true } → marks as reviewed, returns next
 *   4. When complete → returns status: 'complete'
 */

import { fetchWithTimeout } from './helpers.js'
import type { ILogger } from '../../types/interfaces.js'

export const ANNOTATION_TOOL_NAME = '_annotate_mnemic_fields'

export const ANNOTATION_TOOLS = [{
  name: ANNOTATION_TOOL_NAME,
  description:
    'Iteratively annotate Self-Model engrams (modules, capabilities, patterns, weaknesses) ' +
    'with LLM-generated semantic summaries. Each call finds the next unannotated engram ' +
    'from the Self-Model Field and enriches it with relational and metric context.\n\n' +
    'Workflow:\n' +
    '- First call (no params) returns the first unannotated engram needing a summary\n' +
    '- Call with { engramId, summary } to store your annotation and receive the next\n' +
    '- Call with { engramId, skip: true } to skip this engram without annotating\n' +
    '- Call with { target: "ModuleName" } to find an unannotated engram by name substring\n' +
    '- Call with { engramId, summary, force: true } to overwrite an existing annotation\n' +
    '- When complete, returns status: "complete"\n\n' +
    'Each response includes:\n' +
    '- engram.id, name, nodeType, currentDescription, rawContent\n' +
    '- executionFlows[] — execution flows passing through this module\n' +
    '- metrics { symbolCount, cohesion, complexityScore, maturity }\n' +
    '- domain, provenance, createdAt, lastSyncedAt, potentiation\n' +
    '- connectivityHint (isolated / leaf / hub / critical / bridge / foundation)\n' +
    '- dependencies[], dependedBy[], enables[], allRelationships[]\n' +
    '- domainSiblings[] — other modules in the same domain\n' +
    '- relatedCapabilities[] — capabilities using this module\n' +
    '- annotatedNeighbors[] — annotation examples from nearby engrams\n\n' +
    'Your summaries are stored in metadata.llm_summary for improved semantic retrieval.',
  inputSchema: {
    type: 'object',
    properties: {
      engramId: {
        type: 'string',
        description: 'ID of the engram you are annotating (from previous response)',
      },
      summary: {
        type: 'string',
        description: 'Your semantic summary for this engram (2-4 sentences). Omit to start session or skip.',
      },
      skip: {
        type: 'boolean',
        description: 'Set true to skip this engram without annotating (marks as reviewed)',
      },
      target: {
        type: 'string',
        description: 'Optional: find an unannotated engram matching this name pattern (e.g., "Thalamus", "Cortex"). Uses case-insensitive substring match. Ignored if engramId is provided.',
      },
      force: {
        type: 'boolean',
        description: 'Set true to overwrite existing annotation on an already-annotated engram. Use with engramId + summary.',
      },
    },
  },
}]

export const ANNOTATION_TOOL_NAMES = new Set([ANNOTATION_TOOL_NAME])

/**
 * Execute the annotation tool via the admin API.
 */
export async function executeAnnotationTool(
  baseUrl: string,
  args: Record<string, unknown>,
  logger: ILogger,
): Promise<unknown> {
  logger.info('Executing annotation tool', { hasEngramId: !!args?.engramId, hasSummary: !!args?.summary, skip: !!args?.skip })

  const res = await fetchWithTimeout(`${baseUrl}/memory/self-model/annotate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(args ?? {}),
  })

  if (!res.ok) {
    throw new Error(`Annotation request failed: ${res.status}`)
  }

  return res.json()
}

export function getAnnotationTools(): typeof ANNOTATION_TOOLS {
  return [...ANNOTATION_TOOLS]
}