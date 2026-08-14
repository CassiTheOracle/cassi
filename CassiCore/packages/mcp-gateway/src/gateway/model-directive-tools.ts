/**
 * MCP tools for the ModelDirective subsystem.
 *
 * Provides a single `model_directive` tool that controls which provider+model
 * is used for LLM operations (Lumen, Teams, etc.) with layered scopes:
 *   - next: one-shot, consumed after the next operation
 *   - next-job: accumulated per-slot, consumed when the next Lumen/Dyad/Team job starts
 *   - session: applies to ALL jobs launched from this session (not consumed)
 *   - job: scoped to a team/lumen session ID
 *   - default: persisted across restarts
 *
 * Named tiers (minimax, qwenPlus, glm, kimi, qwenMax, sonnet, opus, background) are convenient aliases
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
- scope="next-job": accumulated per-slot, automatically consumed when the next Lumen/Dyad/Team starts. Set models BEFORE launching the job — no race condition, correct from iteration 1.
- scope="session": applies to ALL jobs launched during this session. Not consumed — set once, applies to every Lumen/Dyad/Team until cleared.
- scope="job": scoped to a specific team or Lumen session ID
- scope="default": persisted as the new default across restarts

Named tiers are available as shortcuts:
- minimax: Fastest, lightweight (MiniMax-M2.5)
- qwenPlus: Fast with decent reasoning (qwen3.6-plus)
- glm: Solid mid-range (glm-5)
- kimi: Best mid-tier reasoning (kimi-k2.5)
- qwenMax: High-capability 2nd tier (qwen3-max-2026-01-23)
- sonnet: Strong reasoning, balanced (claude-sonnet-4.6)
- opus: Complex reasoning, high-stakes (claude-opus-4.6)
- background: Unlimited background tasks (gpt-5-mini)

Use action="get" to see current routing state.
Use action="set" with either a tier name, explicit provider+model, or just model (provider auto-inferred).
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
          enum: ['next', 'next-job', 'session', 'job', 'default'],
          description: 'Override scope: "next" (one-shot), "next-job" (pre-seed models for next Lumen/Dyad/Team — consumed at job start), "session" (applies to ALL jobs in this session — not consumed), "job" (team/lumen session), "default" (persistent)',
        },
        tier: {
          type: 'string',
          enum: ['minimax', 'qwenPlus', 'glm', 'kimi', 'qwenMax', 'sonnet', 'opus', 'background'],
          description: 'Named tier (alternative to raw provider+model). Use this for convenience.',
        },
        provider: {
          type: 'string',
          description: 'Raw provider ID (e.g. "alibaba-coding"). Optional when model is set — provider is auto-inferred by matching model name across available providers.',
        },
        model: {
          type: 'string',
          description: 'Raw model name (e.g. "kimi-k2.5", "glm-5", "claude-opus-4.6"). When set without provider, the provider is resolved automatically.',
        },
        jobId: {
          type: 'string',
          description: 'Team or Lumen session ID. Required when scope="job".',
        },
        slot: {
          type: 'string',
          description: 'Dotted-hierarchy slot for per-component granularity. Examples: "lumen.yang", "lumen.yin", "lumen.executive", "dyad.yang", "dyad.yin", "dyad.apex", "dialectic.yang", "thinker", "subconscious". When set, the override only applies to that specific slot.',
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
