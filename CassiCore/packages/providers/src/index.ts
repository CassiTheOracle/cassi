import fs from 'node:fs'

import {
  KimiCodingProvider,
  OpenRouterProvider,
  QwenProvider,
} from '@cassicore/ai'

import { CentralizedProvider, wrapProvidersWithCentralized } from './centralized.js'
import { GitHubCopilotProvider } from './github-copilot.js'
import { GoogleAntigravityProvider } from './google-antigravity.js'
import { QwenLoadBalancer, createQwenLoadBalancer, type QwenAccount } from './qwen-loadbalancer.js'

import type { IConfig, ILogger , IEventBus } from '../../types/interfaces.js'
import type { IProvider } from '../../types/runtime.js'


// Import canonical provider implementations from @cassicore/ai

export { CentralizedProvider, wrapProvidersWithCentralized }
export { QwenLoadBalancer, createQwenLoadBalancer }
export type { QwenAccount }

// Re-export canonical providers from @cassicore/ai
export { KimiCodingProvider, OpenRouterProvider, QwenProvider } from '@cassicore/ai'

// ── Request optimization exports ─────────────────────────────────────────────
export { CostClassifier, getCostClassifier, DEFAULT_COST_RULES } from './cost-classifier.js'
export type { RequestCost, CostRule } from './cost-classifier.js'

export { BudgetTracker, getBudgetTracker, createBudgetTracker, DEFAULT_PROVIDER_BUDGETS } from './budget-tracker.js'
export type { BudgetSnapshot, BudgetTier, ProviderBudgetConfig } from './budget-tracker.js'

export { ModelRouter, getModelRouter, createModelRouter } from './model-router.js'
export type { RequestPurpose, RoutingDecision } from './model-router.js'

export interface CreateProvidersOptions {
  /** Enable centralized request tracking and rate limiting (default: true) */
  centralized?: boolean
  /** Event bus for centralized provider events */
  bus?: IEventBus
}

/**
 * Create provider instances with optional centralized request management.
 *
 * When centralized=true (default), all providers are wrapped with:
 *   - Request deduplication per session
 *   - Rate limiting per provider
 *   - Request metrics and event emission
 *   - Error cooldown with exponential backoff
 */
export function createProviders(
  config: IConfig,
  logger: ILogger,
  options: CreateProvidersOptions = {},
): Map<string, IProvider> {
  const { centralized = true, bus } = options
  const rawProviders = new Map<string, IProvider>()

  // ── GitHub Copilot ─────────────────────────────────────────────────────────
  const copilotToken =
    config.get<string>('providers.githubCopilot.token', '') ||
    process.env.GITHUB_TOKEN ||
    process.env.COPILOT_TOKEN ||
    ''
  if (copilotToken) {
    rawProviders.set('github-copilot', new GitHubCopilotProvider(copilotToken))
    logger.info('Provider loaded: github-copilot')
  }

  // ── Kimi Coding (kimi-code / k2.5) ─────────────────────────────────────────
  const kimiCodingKey =
    config.get<string>('providers.kimiCoding.apiKey', '') ||
    config.get<string>('providers.kimi-coding.apiKey', '') ||
    process.env.KIMI_API_KEY ||
    process.env.KIMICODE_API_KEY ||
    ''
  if (kimiCodingKey) {
    try {
      const kimiProv = new KimiCodingProvider(kimiCodingKey)
      rawProviders.set('kimi-coding', kimiProv)
      logger.info('Provider loaded: kimi-coding')
    } catch (err) {
      logger.warn(`failed to load kimi-coding provider: ${String(err)}`)
    }
  }

  // ── Google Antigravity ─────────────────────────────────────────────────────
  const antigravityKey =
    config.get<string>('providers.googleAntigravity.authKey', '') ||
    process.env.GOOGLE_ANTIGRAVITY_KEY ||
    ''
  if (antigravityKey) {
    try {
      rawProviders.set('google-antigravity', new GoogleAntigravityProvider(antigravityKey))
      logger.info('Provider loaded: google-antigravity')
    } catch (err) {
      logger.warn(`failed to load google-antigravity provider: ${String(err)}`)
    }
  }

  // ── OpenRouter ─────────────────────────────────────────────────────────────
  const openrouterKey =
    config.get<string>('providers.openrouter.apiKey', '') ||
    config.get<string>('providers.openRouter.apiKey', '') ||
    process.env.OPENROUTER_API_KEY ||
    ''
  if (openrouterKey) {
    const openrouterBaseUrl =
      config.get<string>('providers.openrouter.baseUrl', '') ||
      'https://openrouter.ai/api/v1'
    try {
      rawProviders.set('openrouter', new OpenRouterProvider(openrouterKey, openrouterBaseUrl))
      logger.info('Provider loaded: openrouter')
    } catch (err) {
      logger.warn(`failed to load openrouter provider: ${String(err)}`)
    }
  }

  // ── Qwen (Alibaba Qwen models) ─────────────────────────────────────────────
  // Support multi-account load balancing
  // First try to load from external qwen-accounts.json, then from config
  let qwenAccounts: Array<{ profileId: string; credentials: any; baseUrl?: string }> = []
  try {
    const qwenAccountsPath = process.env.QWEN_ACCOUNTS_PATH || `${process.env.HOME || '/home/valerie'}/.cassicore/qwen-accounts.json`
    if (fs.existsSync(qwenAccountsPath)) {
      const qwenAccountsConfig = JSON.parse(fs.readFileSync(qwenAccountsPath, 'utf8'))
      qwenAccounts = qwenAccountsConfig?.providers?.qwen?.accounts || []
      if (qwenAccounts.length > 0) {
        logger.info(`[qwen] Loaded ${qwenAccounts.length} account(s) from ${qwenAccountsPath}`)
      }
    }
  } catch (err) {
    logger.warn(`[qwen] Failed to load qwen-accounts.json: ${String(err)}`)
  }

  // Fallback to config if no accounts file
  if (qwenAccounts.length === 0) {
    qwenAccounts = config.get<Array<{ profileId: string; credentials: any; baseUrl?: string }>>('providers.qwen.accounts', [])
  }

  const qwenKey =
    config.get<string>('providers.qwen.apiKey', '') ||
    process.env.QWEN_API_KEY ||
    process.env.DASHSCOPE_API_KEY ||
    ''

  if (qwenAccounts.length > 1) {
    // Multi-account load balancing mode
    try {
      const accounts: QwenAccount[] = qwenAccounts.map(acc => ({
        profileId: acc.profileId,
        credentials: acc.credentials,
        baseUrl: acc.baseUrl,
      }))
      const loadBalancer = new QwenLoadBalancer({
        accounts,
        strategy: 'round-robin',
        cooldownMs: config.get('providers.qwen.cooldownMs', 60000),
        maxRetries: config.get('providers.qwen.maxRetries', 2),
      })
      rawProviders.set('qwen', loadBalancer)
      // Alias for compatibility
      rawProviders.set('qwen-cli', loadBalancer)
      logger.info(`Provider loaded: qwen (load-balanced across ${accounts.length} accounts)`)
    } catch (err) {
      logger.warn(`failed to load qwen load balancer: ${String(err)}`)
    }
  } else if (qwenKey) {
    // Single account mode (legacy)
    const qwenBaseUrl =
      config.get<string>('providers.qwen.baseUrl', '') ||
      process.env.QWEN_BASE_URL ||
      'https://dashscope.aliyuncs.com/compatible-mode/v1'
    try {
      rawProviders.set('qwen', new QwenProvider(qwenKey, qwenBaseUrl))
      // Alias for qwen-cli compatibility
      rawProviders.set('qwen-cli', new QwenProvider(qwenKey, qwenBaseUrl))
      logger.info('Provider loaded: qwen (aliases: qwen, qwen-cli)')
    } catch (err) {
      logger.warn(`failed to load qwen provider: ${String(err)}`)
    }
  }

  // ── LM Studio (Local API) ──────────────────────────────────────────────────
  const lmstudioEnabled = config.get<boolean>('providers.lmstudio.enabled', true)
  if (lmstudioEnabled) {
    const lmstudioBaseUrl = config.get<string>('providers.lmstudio.baseUrl', 'http://localhost:1234/v1')
    try {
      const lmstudioProvider = {
        id: 'lmstudio',
        // Default LM Studio model list favors the current local fallback first
        models: config.get<string[]>('providers.lmstudio.models', ['prunedhub-gpt-oss-20b-28x']),
        countTokens: async (messages: any[]) => messages.reduce((acc, m) => acc + Math.ceil(String(m.content).length / 4), 0),
        ping: async () => true,
        async *complete(messages: any[], opts: any) {
          const response = await fetch(`${lmstudioBaseUrl}/chat/completions`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': 'Bearer lmstudio'
            },
            body: JSON.stringify({
              model: opts.model || 'prunedhub-gpt-oss-20b-28x',
              messages: messages.map(m => ({
                role: m.role,
                content: typeof m.content === 'string' ? m.content : JSON.stringify(m.content)
              })),
              stream: true
            })
          })

          if (!response.ok) {
            throw new Error(`LM Studio error: ${response.status} ${response.statusText}`)
          }

          const reader = response.body?.getReader()
          if (!reader) throw new Error('No response body')

          const decoder = new TextDecoder()
          let buffer = ''

          while (true) {
            const { done, value } = await reader.read()
            if (done) break

            buffer += decoder.decode(value, { stream: true })
            const lines = buffer.split('\n')
            buffer = lines.pop() || ''

            for (const line of lines) {
              if (line.startsWith('data: ')) {
                const data = line.slice(6)
                if (data === '[DONE]') continue
                try {
                  const chunk = JSON.parse(data)
                  const content = chunk.choices?.[0]?.delta?.content || ''
                  if (content) {
                    yield { type: 'token' as const, text: content }
                  }
                } catch (e) {
                  // Ignore parse errors
                }
              }
            }
          }
          yield { type: 'done' as const }
        }
      }
      rawProviders.set('lmstudio', lmstudioProvider as IProvider)
      logger.info(`Provider loaded: lmstudio (${lmstudioBaseUrl})`)
    } catch (err) {
      logger.warn(`failed to load lmstudio provider: ${String(err)}`)
    }
  }

  if (rawProviders.size === 0) {
    logger.warn('No providers loaded — set at least one API key in config or env')
    return rawProviders
  }

  // ── Centralized request management ──────────────────────────────────────────
  // Disabled: CentralizedProvider wrapping adds complexity (dedup, rate limiting,
  // error cooldown) that interferes with provider-specific behaviors like Kimi's
  // reasoning_content requirements. The raw providers handle their own retries
  // and error handling well enough. Revisit when provider-neutral wrapping is
  // more mature.
  //
  // if (centralized && bus) {
  //   const wrapped = wrapProvidersWithCentralized(rawProviders, logger, bus, config)
  //   logger.info(`Centralized request management enabled for ${wrapped.size} provider(s)`)
  //   return wrapped as Map<string, IProvider>
  // }

  // ── Lightweight observability tap ────────────────────────────────────────────
  // Without full CentralizedProvider wrapping, we still want provider:request_start
  // and provider:request_end events on the bus so `cassicore llm events` and the
  // admin API /events/stream can surface LLM activity. We wrap each provider's
  // complete() with a thin async generator shim — no dedup, no rate-limiting,
  // just timing and token counting.
  if (bus) {
    for (const [providerId, provider] of rawProviders) {
      const originalComplete = provider.complete.bind(provider)
      provider.complete = async function* tapComplete(
        messages: import('../../types/runtime.js').Message[],
        opts: import('../../types/runtime.js').CompletionOpts,
      ) {
        const requestId = `req_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
        const sessionId = (opts as any)?.sessionId ?? 'unknown'
        const source = opts?.source ?? 'unknown'
        const trigger = opts?.trigger ?? undefined
        const model = opts?.model ?? (provider as any).model ?? '?'
        const startMs = Date.now()
        let tokensIn = 0
        let tokensOut = 0
        let thinkingTokens = 0
        let errored = false

        bus.emit({ type: 'provider:request_start', providerId, requestId, sessionId, source, model, messageCount: messages.length, timestamp: new Date() })
        bus.emit({
          type: 'provider:request_prompt',
          providerId,
          requestId,
          sessionId,
          source,
          messages: messages.map(m => ({
            role: m.role,
            content: typeof m.content === 'string' ? m.content : JSON.stringify(m.content),
          })),
          systemPrompt: opts?.systemPrompt,
          timestamp: new Date(),
        })

        try {
          try {
            tokensIn = await provider.countTokens(messages)
          } catch {
            // Best-effort estimate only; providers that report structured usage
            // will override this fallback later.
          }

          for await (const chunk of originalComplete(messages, opts)) {
            if (chunk.type === 'token') {
              tokensOut += (chunk.text?.length ?? 0)
              if (chunk.text) bus.emit({ type: 'provider:request_chunk', providerId, requestId, sessionId, source, trigger, model, chunkType: 'token', text: chunk.text, timestamp: new Date() })
            } else if (chunk.type === 'thinking') {
              thinkingTokens += (chunk.text?.length ?? 0)
              if (chunk.text) bus.emit({ type: 'provider:request_chunk', providerId, requestId, sessionId, source, trigger, model, chunkType: 'thinking', text: chunk.text, timestamp: new Date() })
            } else if (chunk.type === 'tool_use' && chunk.toolCall) {
              bus.emit({ type: 'provider:request_chunk', providerId, requestId, sessionId, source, trigger, model, chunkType: 'tool_use', toolCall: chunk.toolCall, timestamp: new Date() })
            } else if (chunk.type === 'done' && (chunk as any).tokensUsed != null) {
              const t = (chunk as any).tokensUsed
              if (typeof t === 'number') {
                // Provider reported a single total (e.g. output_tokens only)
                tokensOut = t || tokensOut
              } else if (typeof t === 'object') {
                tokensIn = t.input ?? tokensIn
                tokensOut = t.output ?? tokensOut
                if (t.thinking != null) thinkingTokens = t.thinking
              }
            }
            yield chunk
          }
        } catch (err) {
          errored = true
          bus.emit({ type: 'provider:request_error', providerId, requestId, sessionId, source, trigger, model, error: String(err), durationMs: Date.now() - startMs, timestamp: new Date() })
          throw err
        } finally {
          if (!errored) {
              bus.emit({
                type: 'provider:request_end',
                providerId,
                requestId,
                sessionId,
                source,
                trigger,
                model,
                tokensUsed: { input: tokensIn, output: tokensOut, thinking: thinkingTokens },
                durationMs: Date.now() - startMs,
                timestamp: new Date(),
              })
          }
        }
      } as any
    }
    logger.info(`Observability tap installed on ${rawProviders.size} provider(s)`)
  }

  logger.info(`${rawProviders.size} provider(s) loaded (direct mode)`)
  return rawProviders
}
