import type { IConfig, ILogger } from '../../types/interfaces.js'
import type { IEventBus } from '../../types/interfaces.js'
import type { IProvider } from '../../types/runtime.js'
import { GitHubCopilotProvider } from './github-copilot.js'
import { KimiCodingProvider } from './kimi-coding.js'
import { OpenRouterProvider } from './openrouter.js'
import { GoogleAntigravityProvider } from './google-antigravity.js'
import { PiBridgeProvider } from './pi-bridge.js'
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
      rawProviders.set('kimi-coding', new KimiCodingProvider(kimiCodingKey))
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

  // ── Pi Bridge ──────────────────────────────────────────────────────────────
  rawProviders.set('pi-bridge', new PiBridgeProvider(logger, bus || (config as any).bus))
  logger.info('Provider loaded: pi-bridge')

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
