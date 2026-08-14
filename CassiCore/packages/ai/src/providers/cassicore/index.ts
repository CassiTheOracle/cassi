/**
 * CassiCore-specific provider extensions
 *
 * Direct API providers (not Hermes-bridged).
 * These are loaded from process.env API keys at daemon boot.
 */
export { OpenCodeGoProvider } from "./opencode-go.js";
export { AlibabaCodingProvider } from "./alibaba-coding.js";
export { DeepSeekProvider } from "./deepseek.js";
export { KimiCodingProvider } from "./kimi-coding.js";
export { OpenRouterProvider } from "./openrouter.js";
export { QwenProvider, QwenLoadBalancer, qwenModels, getQwenModel } from "./qwen.js";
export type { QwenAccount, QwenOAuthCredentials, QwenModel } from "./qwen.js";
export { ZaiProvider } from "./zai.js";
