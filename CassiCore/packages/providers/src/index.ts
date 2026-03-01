import type { IConfig, ILogger } from '../../types/interfaces.js'
import type { IEventBus } from '../../types/interfaces.js'
import type { IProvider } from '../../types/runtime.js'
import { GitHubCopilotProvider } from './github-copilot.js'
import { KimiCodingProvider } from './kimi-coding.js'
import { OpenRouterProvider } from './openrouter.js'
import { GoogleAntigravityProvider } from './google-antigravity.js'
import { QwenProvider } from './qwen.js'
import { QwenLoadBalancer, createQwenLoadBalancer, type QwenAccount } from './qwen-loadbalancer.js'
import { CentralizedProvider, wrapProvidersWithCentralized } from './centralized.js'
import fs from 'node:fs'

export { CentralizedProvider, wrapProvidersWithCentralized }
export { QwenLoadBalancer, createQwenLoadBalancer }
export type { QwenAccount }

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
      // Legacy alias: some configs refer to 'kimi'
      rawProviders.set('kimi', kimiProv)
      logger.info('Provider loaded: kimi-coding (aliases: kimi-coding, kimi)')
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
        // Default to fast lfm2.5-1.2b model, prunedhub-gpt-oss-20b-28x as fallback
        models: config.get<string[]>('providers.lmstudio.models', ['lfm2.5-1.2b', 'prunedhub-gpt-oss-20b-28x']),
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
              model: opts.model || 'lfm2.5-1.2b',
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
    logger.warn('[providers] No providers loaded — set at least one API key in config or env')
    return rawProviders
  }

  // ── Wrap with centralized request management ───────────────────────────────
  if (centralized && bus) {
    const wrapped = wrapProvidersWithCentralized(rawProviders, logger, bus, config)
    logger.info(`[providers] Centralized request management enabled for ${wrapped.size} provider(s)`)
    return wrapped as Map<string, IProvider>
  }

  return rawProviders
}
