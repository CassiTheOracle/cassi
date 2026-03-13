import fs from 'node:fs'

import {
  AlibabaCodingProvider,
  KimiCodingProvider,
  OpenRouterProvider,
  QwenProvider,
} from '@cassicore/ai'

import { CentralizedProvider, wrapProvidersWithCentralized } from './centralized.js'
import { GitHubCopilotProvider } from './github-copilot.js'
import { GitHubCopilotLoadBalancer, type GitHubCopilotAccount } from './github-copilot-loadbalancer.js'
import { GoogleAntigravityProvider } from './google-antigravity.js'
import { QwenLoadBalancer, createQwenLoadBalancer, type QwenAccount } from './qwen-loadbalancer.js'

import type { IConfig, ILogger , IEventBus } from '../../types/interfaces.js'
import type { IProvider } from '../../types/runtime.js'


// Import canonical provider implementations from @cassicore/ai

export { CentralizedProvider, wrapProvidersWithCentralized }
export { QwenLoadBalancer, createQwenLoadBalancer }
export type { QwenAccount }

// Re-export canonical providers from @cassicore/ai
export { AlibabaCodingProvider, KimiCodingProvider, OpenRouterProvider, QwenProvider } from '@cassicore/ai'

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

  // Attempt to load multi-account file
  let copilotAccounts: GitHubCopilotAccount[] = []
  try {
    const path = process.env.GITHUB_COPILOT_ACCOUNTS_PATH || `${process.env.HOME || '/home/valerie'}/.cassicore/github-copilot-accounts.json`
    if (fs.existsSync(path)) {
      const cfg = JSON.parse(fs.readFileSync(path, 'utf8'))
      copilotAccounts = cfg?.providers?.['github-copilot']?.accounts || []
      if (copilotAccounts.length > 0) logger.info(`[github-copilot] Loaded ${copilotAccounts.length} account(s) from ${path}`)
    }
  } catch (err) {
    logger.warn(`[github-copilot] Failed to load accounts file: ${String(err)}`)
  }

  if (copilotAccounts.length > 1) {
    try {
      const lb = new GitHubCopilotLoadBalancer({ accounts: copilotAccounts, strategy: 'round-robin', cooldownMs: config.get('providers.githubCopilot.cooldownMs', 60000), maxRetries: config.get('providers.githubCopilot.maxRetries', 2) })
      rawProviders.set('github-copilot', lb)
      logger.info(`Provider loaded: github-copilot (load-balanced across ${copilotAccounts.length} accounts)`)
    } catch (err) {
      logger.warn(`failed to load github-copilot load balancer: ${String(err)}`)
    }
  } else if (copilotToken) {
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

  // ── Alibaba Coding Plan ─────────────────────────────────────────────────────
  const alibabaCodingKey =
    config.get<string>('providers.alibabaCoding.apiKey', '') ||
    process.env.ALIBABA_CODING_API_KEY ||
    ''
  if (alibabaCodingKey) {
    try {
      const alibabaProv = new AlibabaCodingProvider(alibabaCodingKey)
      rawProviders.set('alibaba-coding', alibabaProv)
      logger.info('Provider loaded: alibaba-coding')
    } catch (err) {
      logger.warn(`failed to load alibaba-coding provider: ${String(err)}`)
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

  // ── Qwen ───────────────────────────────────────────────────────────────────
  const qwenAccounts: QwenAccount[] = []
  try {
    const qwenPath = process.env.QWEN_ACCOUNTS_PATH || `${process.env.HOME || '/home/valerie'}/.cassicore/qwen-accounts.json`
    if (fs.existsSync(qwenPath)) {
      const cfg = JSON.parse(fs.readFileSync(qwenPath, 'utf8'))
      qwenAccounts.push(...(cfg?.accounts || []))
      if (qwenAccounts.length > 0) logger.info(`[qwen] Loaded ${qwenAccounts.length} account(s)`)
    }
  } catch (err) {
    logger.warn(`[qwen] Failed to load accounts file: ${String(err)}`)
  }

  if (qwenAccounts.length > 1) {
    try {
      const lb = createQwenLoadBalancer(qwenAccounts)
      rawProviders.set('qwen', lb)
      logger.info(`Provider loaded: qwen (load-balanced across ${qwenAccounts.length} accounts)`)
    } catch (err) {
      logger.warn(`failed to load qwen load balancer: ${String(err)}`)
    }
  } else if (qwenAccounts.length === 1) {
    try {
      const acc = qwenAccounts[0]
      const provider = new QwenProvider(
        acc.credentials?.access || '',
        acc.baseUrl,
        acc.credentials,
      )
      rawProviders.set('qwen', provider)
      logger.info('Provider loaded: qwen')
    } catch (err) {
      logger.warn(`failed to load qwen provider: ${String(err)}`)
    }
  }

  // ── OpenRouter ─────────────────────────────────────────────────────────────
  const openRouterKey =
    config.get<string>('providers.openrouter.apiKey', '') ||
    process.env.OPENROUTER_API_KEY ||
    ''
  if (openRouterKey) {
    try {
      const orProvider = new OpenRouterProvider(openRouterKey)
      rawProviders.set('openrouter', orProvider)
      logger.info('Provider loaded: openrouter')
    } catch (err) {
      logger.warn(`failed to load openrouter provider: ${String(err)}`)
    }
  }

  // ── Return with optional centralization ────────────────────────────────────
  if (centralized && bus) {
    return wrapProvidersWithCentralized(rawProviders, logger, bus)
  }

  return rawProviders
}
