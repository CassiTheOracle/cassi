/**
 * Kimi Coding Provider for CassiCore
 * 
 * Moonshot AI's Kimi models (k2.5 series) via OpenAI-compatible API.
 * Extended with CassiCore-specific features.
 */

import type { Api, Model, KnownProvider } from "../../types.js";

export type KimiModel = "k2.5" | "k2.5-long" | "k2.5-vision";

const KIMI_BASE_URL = "https://api.moonshot.cn/v1";

export const kimiModels: Array<Model<"openai-completions">> = [
  {
    id: "k2.5",
    name: "Kimi K2.5",
    api: "openai-completions",
    provider: "kimi-coding" as KnownProvider,
    baseUrl: KIMI_BASE_URL,
    reasoning: true,
    input: ["text", "image"],
    cost: { input: 0.5, output: 2.0, cacheRead: 0, cacheWrite: 0 },
    contextWindow: 256000,
    maxTokens: 8192,
    compat: {
      supportsDeveloperRole: false,
      supportsReasoningEffort: false,
      thinkingFormat: "openai"
    }
  },
  {
    id: "k2.5-long",
    name: "Kimi K2.5 (Long Context)",
    api: "openai-completions", 
    provider: "kimi-coding" as KnownProvider,
    baseUrl: KIMI_BASE_URL,
    reasoning: true,
    input: ["text"],
    cost: { input: 0.5, output: 2.0, cacheRead: 0, cacheWrite: 0 },
    contextWindow: 2000000, // 2M context
    maxTokens: 8192,
    compat: {
      supportsDeveloperRole: false,
      supportsReasoningEffort: false,
      thinkingFormat: "openai"
    }
  },
  {
    id: "k2.5-vision",
    name: "Kimi K2.5 Vision",
    api: "openai-completions",
    provider: "kimi-coding" as KnownProvider,
    baseUrl: KIMI_BASE_URL,
    reasoning: true,
    input: ["text", "image"],
    cost: { input: 0.5, output: 2.0, cacheRead: 0, cacheWrite: 0 },
    contextWindow: 256000,
    maxTokens: 8192,
    compat: {
      supportsDeveloperRole: false,
      supportsReasoningEffort: false,
      thinkingFormat: "openai"
    }
  }
];

/**
 * Get Kimi model by ID
 */
export function getKimiModel(modelId: KimiModel): Model<"openai-completions"> | undefined {
  return kimiModels.find(m => m.id === modelId);
}
