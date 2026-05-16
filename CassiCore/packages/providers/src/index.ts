import fs from 'node:fs'

import {
  AlibabaCodingProvider,
  DeepSeekProvider,
  KimiCodingProvider,
  OpenRouterProvider,
  QwenProvider,
  ZaiProvider,
} from '@cassicore/ai'

import { getCassiCoreHome } from '../utils/paths.js'
import { CentralizedProvider, wrapProvidersWithCentralized } from './centralized.js'
import { ClaudeCodeProvider } from './claude-code.js'
import { GitHubCopilotProvider } from './github-copilot.js'
import { GitHubCopilotLoadBalancer, type GitHubCopilotAccount } from './github-copilot-loadbalancer.js'
import { GoogleAntigravityProvider } from './google-antigravity.js'
import { QwenLoadBalancer, createQwenLoadBalancer, type QwenAccount } from './qwen-loadbalancer.js'

import type { IConfig, ILogger , IEventBus } from '../../types/interfaces.js'
import type { IProvider } from '../../types/runtime.js'
import type { ToolRegistry } from '../tools/registry.js'
import type { ToolExecutor } from '../tools/executor.js'


export { CentralizedProvider, wrapProvidersWithCentralized }
export { QwenLoadBalancer, createQwenLoadBalancer }
export type { QwenAccount }

export { AlibabaCodingProvider, DeepSeekProvider, KimiCodingProvider, OpenRouterProvider, QwenProvider, ZaiProvider } from '@cassicore/ai'

export { CostClassifier, getCostClassifier, DEFAULT_COST_RULES } from './cost-classifier.js'
export type { RequestCost, CostRule } from './cost-classifier.js'

export { BudgetTracker, getBudgetTracker, createBudgetTracker, DEFAULT_PROVIDER_BUDGETS } from './budget-tracker.js'
export type { BudgetSnapshot, BudgetTier, ProviderBudgetConfig } from './budget-tracker.js'

export { ModelRouter, getModelRouter, createModelRouter } from './model-router.js'
export type { RequestPurpose, RoutingDecision } from './model-router.js'
export { ClaudeCodeProvider } from './claude-code.js'

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

  const copilotToken =
    config.get<string>('providers.githubCopilot.token', '') ||
    process.env.GITHUB_TOKEN ||
    process.env.COPILOT_TOKEN ||
    ''

  // Load multi-account configuration for load balancing
  let copilotAccounts: GitHubCopilotAccount[] = []
  try {
    const path = process.env.GITHUB_COPILOT_ACCOUNTS_PATH || `${getCassiCoreHome()}/github-copilot-accounts.json`
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

  // Load Qwen multi-account configuration for load balancing
  const qwenAccounts: QwenAccount[] = []
  try {
    const qwenPath = process.env.QWEN_ACCOUNTS_PATH || `${getCassiCoreHome()}/qwen-accounts.json`
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

  const zaiKey =
    config.get<string>('providers.zAi.apiKey', '') ||
    process.env.ZAI_API_KEY ||
    process.env.Z_AI_API_KEY ||
    ''
  if (zaiKey) {
    try {
      const zaiProv = new ZaiProvider(zaiKey)
      rawProviders.set('z-ai', zaiProv)
      logger.info('Provider loaded: z-ai')
    } catch (err) {
      logger.warn(`failed to load z-ai provider: ${String(err)}`)
    }
  }

  const deepseekKey =
    config.get<string>('providers.deepseek.apiKey', '') ||
    process.env.DEEPSEEK_API_KEY ||
    ''
  if (deepseekKey) {
    try {
      const deepseekProv = new DeepSeekProvider(deepseekKey)
      rawProviders.set('deepseek', deepseekProv)
      logger.info('Provider loaded: deepseek')
    } catch (err) {
      logger.warn(`failed to load deepseek provider: ${String(err)}`)
    }
  }

  const claudeCodeEnabled = config.get<boolean>('providers.claudeCode.enabled', false)
  if (claudeCodeEnabled) {
    try {
      const claudeCodeProvider = new ClaudeCodeProvider({
        cliPath: config.get<string>('providers.claudeCode.cliPath', '') || undefined,
        defaultModel: config.get<string>('providers.claudeCode.model', 'claude-sonnet-4-7'),
        workingDirectory: config.get<string>('providers.claudeCode.workingDirectory', '') || undefined,
        logger,
      })
      rawProviders.set('claude-code', claudeCodeProvider)
      logger.info(`Provider loaded: claude-code (${claudeCodeProvider.models.length} models)`)
    } catch (err) {
      logger.warn(`failed to load claude-code provider: ${String(err)}`)
    }
  }

  if (centralized && bus) {
    return wrapProvidersWithCentralized(rawProviders, logger, bus, config)
  }

  return rawProviders
}


export type { CopilotSdkManagerOptions } from './copilot-sdk/client-manager.js'

/**
 * Initialize the Copilot SDK provider (async — requires starting the CLI process).
 *
 * Call this AFTER createProviders(). If the SDK initializes successfully:
 * 1. The `copilot-sdk` provider is added to the providers map
 * 2. The `github-copilot` HTTP provider is set to background-only mode
 *
 * If initialization fails (CLI not installed, auth issues, etc.), a warning is
 * logged and the existing providers continue unchanged.
 */
export async function initCopilotSdkProvider(
  providers: Map<string, IProvider>,
  config: IConfig,
  logger: ILogger,
  bus: IEventBus,
  toolRegistry?: ToolRegistry,
  toolExecutor?: ToolExecutor,
): Promise<unknown | null> {
  const sdkEnabled = config.get<boolean>('providers.copilotSdk.enabled', true)
  if (!sdkEnabled) {
    logger.info('[copilot-sdk] Disabled by config (providers.copilotSdk.enabled = false)')
    return null
  }

  const sdkLogger = logger.child('copilot-sdk-init')

  try {
    // Dynamic import prevents module crash if @github/copilot-sdk has ESM resolution issues
    const { CopilotSdkManager } = await import('./copilot-sdk/client-manager.js')
    const { CopilotSdkProvider } = await import('./copilot-sdk/provider.js')
    const { bridgeToolsToSdk } = await import('./copilot-sdk/tool-bridge.js')

    const cliPathOverride = config.get<string>('providers.copilotSdk.cliPath', '')

    const githubToken =
      config.get<string>('providers.copilotSdk.githubToken', '') ||
      config.get<string>('providers.githubCopilot.token', '') ||
      process.env.GITHUB_TOKEN ||
      process.env.COPILOT_TOKEN ||
      ''

    // Create and start the SDK manager
    const manager = new CopilotSdkManager(logger, {
      githubToken: githubToken || undefined,
      cliPath: cliPathOverride || undefined,
      cwd: process.cwd(),
      logLevel: config.get<'none' | 'error' | 'warning' | 'info'>('providers.copilotSdk.logLevel', 'warning'),
      autoRestart: true,
    })

    await manager.start()

    const sdkTools = toolRegistry && toolExecutor
      ? bridgeToolsToSdk(toolRegistry, toolExecutor, bus, logger)
      : []

    const sdkProvider = new CopilotSdkProvider({
      manager,
      tools: sdkTools,
      bus,
      logger,
      defaultModel: config.get<string>('providers.copilotSdk.model', 'gpt-4o'),
      workingDirectory: process.cwd(),
    })

    await sdkProvider.initModels()

    providers.set('copilot-sdk', sdkProvider)
    sdkLogger.info(`copilot-sdk provider ready (${sdkProvider.models.length} models, ${sdkTools.length} tools)`)

    // Set github-copilot provider to background-only when copilot-sdk is active
    const httpProvider = providers.get('github-copilot')
    if (httpProvider) {
      const raw = (httpProvider as unknown as { inner?: IProvider }).inner ?? httpProvider
      if (raw instanceof GitHubCopilotProvider) {
        raw.setBackgroundOnly(true)
        sdkLogger.info('github-copilot HTTP provider set to background-only mode')
      } else if (raw && typeof (raw as GitHubCopilotLoadBalancer).setBackgroundOnly === 'function') {
        ;(raw as GitHubCopilotLoadBalancer).setBackgroundOnly(true)
        sdkLogger.info('github-copilot load balancer set to background-only mode')
      }
    }

    return manager
  } catch (err) {
    sdkLogger.error(`Failed to initialize Copilot SDK provider: ${String(err)}`)
    sdkLogger.info('Falling back to github-copilot HTTP provider for all requests')
    return null
  }
}
