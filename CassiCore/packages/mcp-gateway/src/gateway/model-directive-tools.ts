/**
 * MCP tools for the ModelDirective subsystem.
 *
 * Provides a single `model_directive` tool that controls which provider+model
 * is used for LLM operations (Lumen, Teams, etc.) with layered scopes:
 *   - next: one-shot, consumed after the next operation
 *   - job: scoped to a team/lumen session ID
 *   - default: persisted across restarts
 *
 * Named tiers (fast, balanced, premium, background) are convenient aliases
 * for pre-configured provider+model combos.
 */

import type { ILogger } from '../../types/interfaces.js'
import { fetchWithTimeout } from './helpers.js'

export const MODEL_DIRECTIVE_TOOLS = [
  {
    name: 'model_directive',
    description: `Central model/provider routing for LLM operations (Lumen, Teams).

Instead of specifying provider/model on each tool call, use this tool to set the model routing at a scope level:
- scope="next": one-shot override, consumed after the next LLM operation
- scope="job": scoped to a specific team or Lumen session ID
- scope="default": persisted as the new default across restarts

Named tiers are available as shortcuts:
- fast: Quick tasks, low-latency (MiniMax-M2.5)
- swift: Fast with decent reasoning (qwen3.5-plus)
- standard: Solid mid-range (glm-5)
- balanced: Primary coding, good reasoning/cost (kimi-k2.5)
- premium: Complex reasoning, high-stakes (claude-opus-4.6)
- background: Unlimited background tasks (gpt-4o)

Use action="get" to see current routing state.
Use action="set" with either a tier name OR explicit provider+model.
Use action="clear" to remove an override at a scope.`,
    inputSchema: {
      type: 'object' as const,
      required: ['action', 'scope'],
      properties: {
        action: {
          type: 'string',
          enum: ['set', 'get', 'clear'],
          description: 'Operation to perform',
        },
        scope: {
          type: 'string',
          enum: ['next', 'job', 'default'],
          description: 'Override scope: "next" (one-shot), "job" (team/lumen session), "default" (persistent)',
        },
        tier: {
          type: 'string',
          enum: ['fast', 'swift', 'standard', 'balanced', 'premium', 'background'],
          description: 'Named tier (alternative to raw provider+model). Use this for convenience.',
        },
        provider: {
          type: 'string',
          description: 'Raw provider ID (e.g. "alibaba-coding", "copilot-sdk", "github-copilot")',
        },
        model: {
          type: 'string',
          description: 'Raw model name (e.g. "kimi-k2.5", "claude-opus-4.6", "gpt-4o")',
        },
        jobId: {
          type: 'string',
          description: 'Team or Lumen session ID. Required when scope="job".',
        },
        slot: {
          type: 'string',
          description: 'Dotted-hierarchy slot for per-component granularity. Examples: "lumen.yang", "lumen.yin", "lumen.executive", "dialectic.yang", "thinker", "subconscious". When set, the override only applies to that specific slot.',
        },
      },
    },
  },
]

export const MODEL_DIRECTIVE_TOOL_NAMES = new Set(MODEL_DIRECTIVE_TOOLS.map(t => t.name))

export function getModelDirectiveTools() {
  return MODEL_DIRECTIVE_TOOLS
}

export async function executeModelDirectiveTool(
  baseUrl: string,
  toolName: string,
  args: any,
  logger: ILogger,
): Promise<any> {
  logger.info('Executing model directive tool', { tool: toolName, args })

  if (toolName !== 'model_directive') {
    throw new Error(`Unknown model directive tool: ${toolName}`)
  }

  const { action, scope, tier, provider, model, jobId, slot } = args || {}

  switch (action) {
    case 'get': {
      // Return current state, optionally scoped to a jobId
      const url = new URL(`${baseUrl}/model-directive`)
      if (jobId) url.searchParams.set('jobId', jobId)
      if (slot) url.searchParams.set('slot', slot)
      const res = await fetchWithTimeout(url.toString())
      if (!res.ok) throw new Error(`Model directive get failed: ${await res.text()}`)
      const state = await res.json()

      // Also fetch tiers for context
      const tiersRes = await fetchWithTimeout(`${baseUrl}/model-directive/tiers`)
      const tiersData = tiersRes.ok ? await tiersRes.json() : null

      return {
        ...state,
        availableTiers: tiersData?.tiers ?? null,
      }
    }

    case 'set': {
      const body: Record<string, unknown> = { scope }
      if (tier) body.tier = tier
      if (provider) body.provider = provider
      if (model) body.model = model
      if (jobId) body.jobId = jobId
      if (slot) body.slot = slot

      const res = await fetchWithTimeout(`${baseUrl}/model-directive/set`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) {
        const errorText = await res.text()
        throw new Error(`Model directive set failed: ${errorText}`)
      }
      return await res.json()
    }

    case 'clear': {
      const body: Record<string, unknown> = { scope }
      if (jobId) body.jobId = jobId
      if (slot) body.slot = slot

      const res = await fetchWithTimeout(`${baseUrl}/model-directive/clear`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) {
        const errorText = await res.text()
        throw new Error(`Model directive clear failed: ${errorText}`)
      }
      return await res.json()
    }

    default:
      throw new Error(`Invalid action: "${action}". Must be "set", "get", or "clear".`)
  }
}
