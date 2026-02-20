import type { IConfig, ILogger } from '../../types/interfaces.js'
import type { IEventBus } from '../../types/interfaces.js'
import type { IProvider } from '../../types/runtime.js'
import { AnthropicProvider } from './anthropic.js'
import { GitHubCopilotProvider } from './github-copilot.js'
import { KimiProvider } from './kimi.js'
import { KimiCodingProvider } from './kimi-coding.js'
import { CentralizedProvider, wrapProvidersWithCentralized } from './centralized.js'

export { CentralizedProvider, wrapProvidersWithCentralized }

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

  // ── Anthropic ──────────────────────────────────────────────────────────────
  const anthropicKey = config.get<string>('providers.anthropic.apiKey', '') || process.env.ANTHROPIC_API_KEY || ''
  if (anthropicKey) {
    rawProviders.set('anthropic', new AnthropicProvider(anthropicKey))
    logger.info('Provider loaded: anthropic')
  }

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

  // ── Kimi (Moonshot AI) ─────────────────────────────────────────────────────
  const kimiKey =
    config.get<string>('providers.kimi.apiKey', '') ||
    process.env.KIMI_API_KEY ||
    ''
  if (kimiKey) {
    try {
      rawProviders.set('kimi', new KimiProvider(kimiKey))
      logger.info('Provider loaded: kimi')
    } catch (err) {
      logger.warn(`failed to load kimi provider: ${String(err)}`)
    }
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
      rawProviders.set('kimi-coding', new KimiCodingProvider(kimiCodingKey))
      logger.info('Provider loaded: kimi-coding')
    } catch (err) {
      logger.warn(`failed to load kimi-coding provider: ${String(err)}`)
    }
  }

  if (rawProviders.size === 0) {
    logger.warn('[providers] No providers loaded — set at least one API key in config or env')
    return rawProviders
  }

  // ── Wrap with centralized request management ───────────────────────────────
  if (centralized && bus) {
    const wrapped = wrapProvidersWithCentralized(rawProviders, logger, bus)
    logger.info(`[providers] Centralized request management enabled for ${wrapped.size} provider(s)`)
    return wrapped as Map<string, IProvider>
  }

  return rawProviders
}
