/**
 * Provider Factory — simplified to single HermesBridgeProvider.
 *
 * All LLM calls route through Hermes's provider stack. Individual provider
 * classes (DeepSeekProvider, OpenRouterProvider, etc.) have been removed
 * — Hermes manages all upstream providers via config.yaml + .env.
 */

import { HermesBridgeProvider, getHermesBridgeProvider, shutdownHermesBridgeProvider } from './hermes-bridge.js'
import { CentralizedProvider, wrapProvidersWithCentralized } from './centralized.js'
import { CostClassifier, getCostClassifier, DEFAULT_COST_RULES } from './cost-classifier.js'
import { BudgetTracker, getBudgetTracker, createBudgetTracker, DEFAULT_PROVIDER_BUDGETS } from './budget-tracker.js'
import { ModelRouter, getModelRouter, createModelRouter } from './model-router.js'

import type { IConfig, ILogger, IEventBus } from '../../types/interfaces.js'
import type { IProvider } from '../../types/runtime.js'
import type { RequestCost, CostRule } from './cost-classifier.js'
import type { BudgetSnapshot, BudgetTier, ProviderBudgetConfig } from './budget-tracker.js'
import type { RequestPurpose, RoutingDecision } from './model-router.js'


export { CentralizedProvider, wrapProvidersWithCentralized }
export { CostClassifier, getCostClassifier, DEFAULT_COST_RULES }
export type { RequestCost, CostRule }
export { BudgetTracker, getBudgetTracker, createBudgetTracker, DEFAULT_PROVIDER_BUDGETS }
export type { BudgetSnapshot, BudgetTier, ProviderBudgetConfig }
export { ModelRouter, getModelRouter, createModelRouter }
export type { RequestPurpose, RoutingDecision }
export { HermesBridgeProvider, getHermesBridgeProvider, shutdownHermesBridgeProvider }


export interface CreateProvidersOptions {
  /** Enable centralized request tracking and rate limiting (default: true) */
  centralized?: boolean
  /** Event bus for centralized provider events */
  bus?: IEventBus
}

/**
 * Create provider instances — just the HermesBridgeProvider.
 *
 * The bridge spawns a Python subprocess that wraps Hermes's provider stack,
 * giving CassiCore access to all 20+ Hermes providers.
 */
export async function createProviders(
  config: IConfig,
  logger: ILogger,
  options: CreateProvidersOptions = {},
): Promise<Map<string, IProvider>> {
  const { centralized = true, bus } = options
  const rawProviders = new Map<string, IProvider>()

  try {
    const bridge = getHermesBridgeProvider()
    await bridge.start()
    rawProviders.set('hermes', bridge)
    logger.info(`Provider loaded: hermes (${bridge.models.length} models)`)
  } catch (err) {
    logger.error(`failed to start Hermes bridge provider: ${String(err)}`)
    throw err
  }

  if (centralized && bus) {
    return wrapProvidersWithCentralized(rawProviders, logger, bus, config)
  }

  return rawProviders
}
