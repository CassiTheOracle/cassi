import { fetchJson } from '../helpers.js'
import type { ToolDefinition, ToolHandler } from '../types.js'

export const ROUTING_TOOLS: ToolDefinition[] = [
  {
    name: 'model_tier',
    description: 'For cheap background work or quick lookups: route the next LLM call through a more cost-effective model tier. Does not affect behavior -- only model selection. The override is consumed on use and routing returns to the session default.',
    inputSchema: {
      type: 'object',
      properties: {
        tier: { type: 'string', description: 'Which tier to route through. Common options: background (cheapest), sonnet (balanced), opus (most capable).' },
      },
      required: ['tier'],
    },
  },
  {
    name: 'model_tiers',
    description: 'See what model tiers are available and what provider/model each maps to. Helps you pick the right tier for model_tier.',
    inputSchema: {
      type: 'object',
      properties: {},
    },
  },
]

export async function executeRoutingTool(
  adminUrl: string,
  name: string,
  args: any,
  _hermesDbPath: string,
  _logger: any,
): Promise<{ content: Array<{ type: 'text'; text: string }>; isError?: boolean }> {
  try {
    switch (name) {
      case 'model_tier': {
        const result = await fetchJson(`${adminUrl}/model-directive/set`, {
          method: 'POST',
          body: { scope: 'next', tier: args.tier },
          timeoutMs: 5000,
        })
        return { content: [{ type: 'text', text: `Next request routed to tier "${args.tier}" (${result.provider ?? '?'} / ${result.model ?? '?'}). Override consumed on use.` }] }
      }

      case 'model_tiers': {
        const result = await fetchJson(`${adminUrl}/model-directive/tiers`, { timeoutMs: 5000 })
        const tiers = result?.tiers ?? result ?? {}
        let out = '## Available Model Tiers\n\n|Tier|Provider|Model|\n|---|---|---|\n'
        for (const [tier, mapping] of Object.entries(tiers)) {
          const m = mapping as any
          out += `|${tier}|${m.provider ?? '?'}|${m.model ?? '?'}|\n`
        }
        return { content: [{ type: 'text', text: out }] }
      }

      default:
        return { content: [{ type: 'text', text: `Unknown routing tool: ${name}` }], isError: true }
    }
  } catch (err: any) {
    return { content: [{ type: 'text', text: `Routing error: ${err.message ?? String(err)}` }], isError: true }
  }
}
