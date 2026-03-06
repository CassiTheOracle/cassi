import type { ILogger } from '../../types/interfaces.js'
import type http from 'node:http'

/**
 * Maps CassiCore model IDs to their Catwalk equivalents so that the Crush fork
 * can enrich CassiCore models with Catwalk metadata (display name, context
 * window, capability flags, cost per token) without duplicating that data here.
 *
 * The key is the CassiCore model id (as returned in the models array).
 * The value is the canonical Catwalk model id.
 */
const CATWALK_ID_MAP: Record<string, string> = {
  // GitHub Copilot models routed through CassiCore
  'github-copilot/gpt-4o': 'openai:gpt-4o',
  'github-copilot/gpt-4o-mini': 'openai:gpt-4o-mini',
  'github-copilot/gpt-4.5': 'openai:gpt-4.5',
  'github-copilot/o1': 'openai:o1',
  'github-copilot/o3-mini': 'openai:o3-mini',
  'github-copilot/o3': 'openai:o3',
  'github-copilot/claude-3-5-sonnet': 'anthropic:claude-3-5-sonnet-20241022',
  'github-copilot/claude-3-7-sonnet': 'anthropic:claude-3-7-sonnet-20250219',
  'github-copilot/claude-sonnet-4': 'anthropic:claude-sonnet-4-5',
  'github-copilot/claude-opus-4': 'anthropic:claude-opus-4-5',
  'github-copilot/gemini-2.0-flash': 'google:gemini-2.0-flash',
  'github-copilot/gemini-2.5-pro': 'google:gemini-2.5-pro-preview',
}

export interface ModelsRoutesDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
}

export async function handleModelsRoutes(
  deps: ModelsRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
  pathname: string
): Promise<boolean> {
  const { daemon, sendJSON } = deps

  // GET /models
  if (method === 'GET' && pathname === '/models') {
    try {
      const providerMap = (daemon.pipeline as any)?.providers ?? new Map()
      const models: any[] = []

      for (const [provId, prov] of providerMap.entries()) {
        try {
          const provModels = (prov as any)?.models ?? (prov as any)?.modelList ?? undefined
          if (!provModels || !Array.isArray(provModels)) continue

          for (const m of provModels) {
            const modelName = typeof m === 'string' ? m : String((m as any).id ?? m)
            const id = modelName.includes('/') ? modelName : `${provId}/${modelName}`

            let api = 'openai-completions'
            let reasoning = false
            let input: string[] = ['text']
            let contextWindow = 131072
            let maxTokens = 8192

            if (String(provId).toLowerCase().includes('kimi')) {
              api = 'anthropic-messages'
              reasoning = true
              input = ['text', 'image']
              contextWindow = 262144
              maxTokens = 32768
            } else if (String(provId).toLowerCase().includes('copilot') || String(provId).toLowerCase().includes('github')) {
              api = 'openai-completions'
              reasoning = false
            }

            const meta: any = {
              id,
              name: typeof m === 'string' ? id : ((m as any).name ?? id),
              api,
              reasoning,
              input,
              cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
              contextWindow,
              maxTokens,
              // catwalk_id lets the Crush fork merge CassiCore routing with Catwalk
              // display metadata (context window, capability flags, pricing).
              catwalk_id: CATWALK_ID_MAP[id] ?? null,
            }

            try {
              if (typeof (prov as any).describeModel === 'function') {
                const info = await (prov as any).describeModel(modelName)
                if (info && typeof info === 'object') {
                  meta.name = info.name ?? meta.name
                  meta.api = info.api ?? meta.api
                  meta.reasoning = info.reasoning ?? meta.reasoning
                  meta.input = info.input ?? meta.input
                  meta.cost = info.cost ?? meta.cost
                  meta.contextWindow = info.contextWindow ?? meta.contextWindow
                  meta.maxTokens = info.maxTokens ?? meta.maxTokens
                }
              } else if (typeof (prov as any).getModelInfo === 'function') {
                const info = (prov as any).getModelInfo(modelName)
                if (info && typeof info === 'object') {
                  meta.name = info.name ?? meta.name
                  meta.api = info.api ?? meta.api
                  meta.reasoning = info.reasoning ?? meta.reasoning
                  meta.input = info.input ?? meta.input
                  meta.cost = info.cost ?? meta.cost
                  meta.contextWindow = info.contextWindow ?? meta.contextWindow
                  meta.maxTokens = info.maxTokens ?? meta.maxTokens
                }
              }
            } catch (err) { deps.logger.debug('Failed to describe model', { providerId: provId, model: modelName, error: String(err) }); }

            models.push(meta)
          }
        } catch (err) { deps.logger.debug('Failed to get models from provider', { providerId: provId, error: String(err) }); }
      }

      if (models.length === 0) {
        models.push(
          { id: 'kimi-coding/k2p5', name: 'Kimi K2.5 (CassiCore)', api: 'anthropic-messages', reasoning: true, input: ['text','image'], cost: { input:0,output:0,cacheRead:0,cacheWrite:0 }, contextWindow: 262144, maxTokens: 32768, catwalk_id: null },
          { id: 'github-copilot/gpt-5-mini', name: 'GitHub Copilot gpt-5-mini (via CassiCore)', api: 'openai-completions', reasoning: false, input: ['text'], cost: { input:0,output:0,cacheRead:0,cacheWrite:0 }, contextWindow: 131072, maxTokens: 8192, catwalk_id: null },
          { id: 'openrouter/auto', name: 'OpenRouter (via CassiCore)', api: 'openai-completions', reasoning: false, input: ['text'], cost: { input:0,output:0,cacheRead:0,cacheWrite:0 }, contextWindow: 131072, maxTokens: 8192, catwalk_id: null },
        )
      }

      sendJSON(res, 200, { models })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  return false
}
