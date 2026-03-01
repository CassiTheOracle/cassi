/**
 * Qwen Provider for CassiCore
 * 
 * Alibaba Qwen models via OpenAI-compatible API.
 * Supports multi-account load balancing.
 */

import type { Api, Model, KnownProvider } from "../../types.js";

export type QwenModel = "qwen3-coder-plus" | "qwen3-coder-flash" | "qwen3-vl-plus" | "qwen-max";

const QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1";

export const qwenModels: Array<Model<"openai-completions">> = [
  {
    id: "qwen3-coder-plus",
    name: "Qwen3 Coder Plus",
    api: "openai-completions",
    provider: "qwen" as KnownProvider,
    baseUrl: QWEN_BASE_URL,
    reasoning: true,
    input: ["text"],
    cost: { input: 0.3, output: 0.6, cacheRead: 0, cacheWrite: 0 },
    contextWindow: 1000000,
    maxTokens: 65536,
    compat: {
      supportsDeveloperRole: false,
      supportsReasoningEffort: false,
      thinkingFormat: "qwen"
    }
  },
  {
    id: "qwen3-coder-flash",
    name: "Qwen3 Coder Flash",
    api: "openai-completions",
    provider: "qwen" as KnownProvider,
    baseUrl: QWEN_BASE_URL,
    reasoning: false,
    input: ["text"],
    cost: { input: 0.1, output: 0.2, cacheRead: 0, cacheWrite: 0 },
    contextWindow: 1000000,
    maxTokens: 65536,
    compat: {
      supportsDeveloperRole: false,
      supportsReasoningEffort: false
    }
  },
  {
    id: "qwen3-vl-plus",
    name: "Qwen3 VL Plus",
    api: "openai-completions",
    provider: "qwen" as KnownProvider,
    baseUrl: QWEN_BASE_URL,
    reasoning: true,
    input: ["text", "image"],
    cost: { input: 0.5, output: 1.0, cacheRead: 0, cacheWrite: 0 },
    contextWindow: 262144,
    maxTokens: 32768,
    compat: {
      supportsDeveloperRole: false,
      supportsReasoningEffort: false,
      thinkingFormat: "qwen"
    }
  },
  {
    id: "qwen-max",
    name: "Qwen Max",
    api: "openai-completions",
    provider: "qwen" as KnownProvider,
    baseUrl: QWEN_BASE_URL,
    reasoning: true,
    input: ["text"],
    cost: { input: 0.8, output: 2.0, cacheRead: 0, cacheWrite: 0 },
    contextWindow: 128000,
    maxTokens: 8192,
    compat: {
      supportsDeveloperRole: false,
      supportsReasoningEffort: false,
      thinkingFormat: "qwen"
    }
  }
];

export interface QwenAccount {
  profileId: string;
  credentials: {
    apiKey: string;
  };
  baseUrl?: string;
}

/**
 * Qwen Load Balancer
 * Distributes requests across multiple Qwen accounts
 */
export class QwenLoadBalancer {
  private accounts: QwenAccount[];
  private currentIndex = 0;
  private cooldowns = new Map<string, number>();
  private cooldownMs: number;
  maxRetries: number;

  constructor(options: {
    accounts: QwenAccount[];
    strategy?: "round-robin" | "random";
    cooldownMs?: number;
    maxRetries?: number;
  }) {
    this.accounts = options.accounts;
    this.cooldownMs = options.cooldownMs || 60000;
    this.maxRetries = options.maxRetries || 2;
  }

  /**
   * Get next available account
   */
  getNextAccount(): QwenAccount | undefined {
    const now = Date.now();
    
    // Filter out accounts in cooldown
    const available = this.accounts.filter(acc => {
      const cooldownEnd = this.cooldowns.get(acc.profileId);
      return !cooldownEnd || now > cooldownEnd;
    });

    if (available.length === 0) {
      // All accounts in cooldown, reset and try again
      this.cooldowns.clear();
      return this.accounts[0];
    }

    const account = available[this.currentIndex % available.length];
    this.currentIndex++;
    return account;
  }

  /**
   * Mark account as failed (put in cooldown)
   */
  markFailed(profileId: string): void {
    this.cooldowns.set(profileId, Date.now() + this.cooldownMs);
  }
}

/**
 * Get Qwen model by ID
 */
export function getQwenModel(modelId: QwenModel): Model<"openai-completions"> | undefined {
  return qwenModels.find(m => m.id === modelId);
}
