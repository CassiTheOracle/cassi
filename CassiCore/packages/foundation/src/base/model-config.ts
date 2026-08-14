/**
 * Model Config Manager — resolves and watches intelligence module model configurations.
 *
 * Reads configuration from config.json with precedence:
 *   config.json → constructor overrides → DEFAULT_MODULE_MODEL_CONFIG
 *
 * Extracted from BaseCognitiveModule for independent testability and reuse.
 */

import { MODEL_DEFAULTS } from '../config/system-settings.js'

import type { IConfig, ILogger } from '../../types/interfaces.js'

// Model Configuration Types

export interface ModuleModelConfig {
  /** Provider ID (e.g., 'lmstudio', 'kimi-coding', 'github-copilot') */
  providerId: string
  /** Model name (e.g., 'gpt-5-mini', 'k2p5') */
  model: string
  /** Temperature for inference (0-2) */
  temperature: number
  /** Max tokens for response */
  maxTokens: number
  /** Timeout for inference calls (ms) */
  timeoutMs: number
}

export const DEFAULT_MODULE_MODEL_CONFIG: ModuleModelConfig = {
  providerId: MODEL_DEFAULTS.fast.provider,
  model: MODEL_DEFAULTS.fast.model,
  temperature: 0.3,
  maxTokens: 1024,
  timeoutMs: 10_000,
}

// Model Config Resolution (pure function — no side effects)

/**
 * Resolve model configuration from config.json for a named module.
 *
 * Reads `intelligence.<moduleName>.model`, `.provider`, `.temperature`,
 * `.maxTokens`, and `.timeoutMs` from config.json and merges into the
 * given base config.
 *
 * @param config - The IConfig instance to read from
 * @param moduleName - The intelligence module name (e.g., 'thinker')
 * @param baseConfig - Existing config to merge into (mutated in place)
 * @returns Whether any config.json values were applied
 * @dep callers: reloadModelConfig (core/intelligence/base/cognitive-module.ts), init (core/intelligence/base/cognitive-module.ts)
 * @dep calls: get
 * @dep module: Base
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
export function resolveModelConfigFromJson(
  config: IConfig,
  moduleName: string,
  baseConfig: ModuleModelConfig,
): boolean {
  const prefix = `intelligence.${moduleName}`
  let applied = false

  try {
    const configModel = config.get<string | undefined>(`${prefix}.model`, undefined)
    const configProvider = config.get<string | undefined>(`${prefix}.provider`, undefined)
    const configTemperature = config.get<number | undefined>(`${prefix}.temperature`, undefined)
    const configMaxTokens = config.get<number | undefined>(`${prefix}.maxTokens`, undefined)
    const configTimeoutMs = config.get<number | undefined>(`${prefix}.timeoutMs`, undefined)

    if (configModel !== undefined) {
      if (configModel.includes('/')) {
        const [provider, model] = configModel.split('/', 2)
        baseConfig.providerId = provider
        baseConfig.model = model
      } else {
        baseConfig.model = configModel
      }
      applied = true
    }

    if (configProvider !== undefined) {
      baseConfig.providerId = configProvider
      applied = true
    }

    if (configTemperature !== undefined && typeof configTemperature === 'number') {
      baseConfig.temperature = configTemperature
      applied = true
    }

    if (configMaxTokens !== undefined && typeof configMaxTokens === 'number') {
      baseConfig.maxTokens = configMaxTokens
      applied = true
    }

    if (configTimeoutMs !== undefined && typeof configTimeoutMs === 'number') {
      baseConfig.timeoutMs = configTimeoutMs
      applied = true
    }
  } catch {
    // No config.json or error reading — return false
  }

  return applied
}

/**
 * Wire config.json watcher for live model config changes.
 *
 * @returns Array of unsubscribe functions for cleanup
 */
export function wireModelConfigWatcher(
  config: IConfig,
  moduleName: string,
  onChanged: () => void,
): Array<() => void> {
  const prefix = `intelligence.${moduleName}`
  const keys = [
    `${prefix}.model`,
    `${prefix}.provider`,
    `${prefix}.temperature`,
    `${prefix}.maxTokens`,
    `${prefix}.timeoutMs`,
  ]

  return keys.map(key => config.onChanged(key, onChanged))
}

/**
 * Apply partial model config overrides.
 * Supports combined 'provider/model' format in the model field.
 * @dep callers: setModelConfig (core/intelligence/base/cognitive-module.ts)
 * @dep flows: HandleIntelligenceRoutes → ApplyModelConfigOverrides (3/3)
 * @dep module: Subconscious
 * @dep risk: LOW | 1 caller, 1 flow, 1 module
 */
export function applyModelConfigOverrides(
  baseConfig: ModuleModelConfig,
  overrides: Partial<ModuleModelConfig>,
): void {
  // Handle combined 'provider/model' format
  if (overrides.model && overrides.model.includes('/') && !overrides.providerId) {
    const [provider, model] = overrides.model.split('/', 2)
    overrides = { ...overrides, providerId: provider, model }
  }
  Object.assign(baseConfig, overrides)
}
