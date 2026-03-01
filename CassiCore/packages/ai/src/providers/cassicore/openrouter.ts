/**
 * OpenRouter Provider for CassiCore
 *
 * Unified API for 100+ models via OpenRouter.
 * Extended with CassiCore-specific routing preferences.
 */

import type {
  Api,
  Model,
  KnownProvider,
  OpenRouterRouting,
} from "../../types.js";

export type OpenRouterModel =
  | "anthropic/claude-sonnet-4"
  | "anthropic/claude-opus-4"
  | "openai/gpt-5"
  | "openai/gpt-5-mini"
  | "google/gemini-2.5-pro"
  | "meta/llama-4-maverick"
  | "deepseek/deepseek-chat-v3"
  | "xai/grok-3";

const OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1";

export const openrouterModels: Array<Model<"openai-completions">> = [
  {
    id: "anthropic/claude-sonnet-4",
    name: "Claude Sonnet 4 (via OpenRouter)",
    api: "openai-completions",
    provider: "openrouter" as KnownProvider,
    baseUrl: OPENROUTER_BASE_URL,
    reasoning: true,
    input: ["text", "image"],
    cost: { input: 3, output: 15, cacheRead: 0.3, cacheWrite: 3.75 },
    contextWindow: 200000,
    maxTokens: 64000,
    compat: {
      supportsDeveloperRole: false,
      supportsReasoningEffort: false,
      openRouterRouting: {
        order: ["anthropic"],
      },
    },
  },
  {
    id: "anthropic/claude-opus-4",
    name: "Claude Opus 4 (via OpenRouter)",
    api: "openai-completions",
    provider: "openrouter" as KnownProvider,
    baseUrl: OPENROUTER_BASE_URL,
    reasoning: true,
    input: ["text", "image"],
    cost: { input: 15, output: 75, cacheRead: 1.5, cacheWrite: 18.75 },
    contextWindow: 200000,
    maxTokens: 64000,
    compat: {
      supportsDeveloperRole: false,
      supportsReasoningEffort: false,
      openRouterRouting: {
        order: ["anthropic"],
      },
    },
  },
  {
    id: "openai/gpt-5",
    name: "GPT-5 (via OpenRouter)",
    api: "openai-completions",
    provider: "openrouter" as KnownProvider,
    baseUrl: OPENROUTER_BASE_URL,
    reasoning: true,
    input: ["text", "image"],
    cost: { input: 5, output: 15, cacheRead: 0, cacheWrite: 0 },
    contextWindow: 128000,
    maxTokens: 16384,
    compat: {
      supportsDeveloperRole: true,
      supportsReasoningEffort: true,
    },
  },
  {
    id: "openai/gpt-5-mini",
    name: "GPT-5 Mini (via OpenRouter)",
    api: "openai-completions",
    provider: "openrouter" as KnownProvider,
    baseUrl: OPENROUTER_BASE_URL,
    reasoning: true,
    input: ["text", "image"],
    cost: { input: 0.5, output: 1.5, cacheRead: 0, cacheWrite: 0 },
    contextWindow: 128000,
    maxTokens: 16384,
    compat: {
      supportsDeveloperRole: true,
      supportsReasoningEffort: true,
    },
  },
  {
    id: "google/gemini-2.5-pro",
    name: "Gemini 2.5 Pro (via OpenRouter)",
    api: "openai-completions",
    provider: "openrouter" as KnownProvider,
    baseUrl: OPENROUTER_BASE_URL,
    reasoning: true,
    input: ["text", "image"],
    cost: { input: 1.25, output: 10, cacheRead: 0, cacheWrite: 0 },
    contextWindow: 1000000,
    maxTokens: 65536,
    compat: {
      supportsDeveloperRole: false,
      supportsReasoningEffort: false,
    },
  },
  {
    id: "meta/llama-4-maverick",
    name: "Llama 4 Maverick (via OpenRouter)",
    api: "openai-completions",
    provider: "openrouter" as KnownProvider,
    baseUrl: OPENROUTER_BASE_URL,
    reasoning: false,
    input: ["text", "image"],
    cost: { input: 0.2, output: 0.6, cacheRead: 0, cacheWrite: 0 },
    contextWindow: 256000,
    maxTokens: 8192,
    compat: {
      supportsDeveloperRole: false,
      supportsReasoningEffort: false,
    },
  },
  {
    id: "deepseek/deepseek-chat-v3",
    name: "DeepSeek V3 (via OpenRouter)",
    api: "openai-completions",
    provider: "openrouter" as KnownProvider,
    baseUrl: OPENROUTER_BASE_URL,
    reasoning: true,
    input: ["text"],
    cost: { input: 0.07, output: 0.28, cacheRead: 0, cacheWrite: 0 },
    contextWindow: 64000,
    maxTokens: 8192,
    compat: {
      supportsDeveloperRole: false,
      supportsReasoningEffort: false,
    },
  },
  {
    id: "xai/grok-3",
    name: "Grok 3 (via OpenRouter)",
    api: "openai-completions",
    provider: "openrouter" as KnownProvider,
    baseUrl: OPENROUTER_BASE_URL,
    reasoning: true,
    input: ["text", "image"],
    cost: { input: 3, output: 15, cacheRead: 0, cacheWrite: 0 },
    contextWindow: 128000,
    maxTokens: 32768,
    compat: {
      supportsDeveloperRole: false,
      supportsReasoningEffort: false,
    },
  },
];

/**
 * Get OpenRouter model by ID
 */
export function getOpenRouterModel(
  modelId: OpenRouterModel
): Model<"openai-completions"> | undefined {
  return openrouterModels.find((m) => m.id === modelId);
}
