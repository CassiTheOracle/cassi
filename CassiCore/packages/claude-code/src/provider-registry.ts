/**
 * Provider Registry for the CassiCore Claude Code Proxy.
 *
 * Manages a set of API providers (z.ai, Anthropic direct, etc.) with their
 * credentials, base URLs, health status, and circuit-breaker state.
 *
 * Provider credentials are loaded from environment variables (or a .env file
 * loaded by the proxy entry point). The registry does NOT read
 * ~/.claude/settings.json — that file is managed by settings-sync.ts.
 *
 * Environment variables:
 *   Z_AI_API_KEY          — API key for z.ai (GLM models)
 *   Z_AI_BASE_URL         — z.ai base URL (default: https://api.z.ai/api/anthropic)
 *   ANTHROPIC_API_KEY     — API key for Anthropic direct (Claude models)
 *   ANTHROPIC_BASE_URL_DIRECT — Anthropic base URL (default: https://api.anthropic.com)
 *   ANTHROPIC_AUTH_TOKEN  — Legacy fallback for z.ai API key
 */

import { integrationLogger } from "./logger.js";

const logger = integrationLogger.child("provider-registry");


export interface ProviderConfig {
  /** Unique provider identifier (e.g., "z.ai", "anthropic") */
  id: string;
  /** Upstream base URL */
  baseUrl: string;
  /** API key */
  apiKey: string;
  /** Header name for the API key (default: "x-api-key") */
  apiKeyHeader: string;
  /** Anthropic API version header value (if applicable) */
  anthropicVersion: string;
  /** Human-readable label */
  label: string;
  /** Whether this provider is enabled */
  enabled: boolean;
}

export interface ProviderHealth {
  /** Timestamp of last health check attempt */
  lastCheck: number;
  /** Consecutive failure count */
  consecutiveFailures: number;
  /** Whether the circuit breaker is open (provider is skipped) */
  circuitOpen: boolean;
  /** Timestamp when circuit was opened */
  circuitOpenedAt: number;
  /** Total requests routed to this provider */
  totalRequests: number;
  /** Total successful requests */
  totalSuccesses: number;
  /** Total failed requests */
  totalFailures: number;
}

export interface Provider extends ProviderConfig {
  health: ProviderHealth;
}


const CIRCUIT_BREAKER_THRESHOLD = 3;       // failures before opening
const CIRCUIT_BREAKER_RESET_MS = 60_000;   // 1 minute before trying again
const HEALTH_CHECK_INTERVAL_MS = 30_000;   // 30 seconds between passive health updates


const providers = new Map<string, Provider>();

/**
 * Initialize the provider registry from environment variables.
 * Called once at proxy startup.
 */
export function initFromEnv(): void {
  const zaiKey = process.env.Z_AI_API_KEY ?? process.env.ANTHROPIC_AUTH_TOKEN ?? "";
  const zaiUrl = process.env.Z_AI_BASE_URL ?? "https://api.z.ai/api/anthropic";

  if (zaiKey) {
    registerProvider({
      id: "z.ai",
      baseUrl: zaiUrl,
      apiKey: zaiKey,
      apiKeyHeader: "x-api-key",
      anthropicVersion: "2023-06-01",
      label: "z.ai (GLM models)",
      enabled: true,
    });
    logger.info(`Provider z.ai registered (${maskKey(zaiKey)}) → ${zaiUrl}`);
  } else {
    logger.warn("No Z_AI_API_KEY or ANTHROPIC_AUTH_TOKEN set — z.ai provider unavailable");
  }

  const anthropicKey = process.env.ANTHROPIC_API_KEY ?? "";
  const anthropicUrl = process.env.ANTHROPIC_BASE_URL_DIRECT ?? "https://api.anthropic.com";

  // Always register anthropic — when ANTHROPIC_API_KEY is not set,
  // the proxy passes through the client's x-api-key header instead.
  registerProvider({
    id: "anthropic",
    baseUrl: anthropicUrl,
    apiKey: anthropicKey,
    apiKeyHeader: "x-api-key",
    anthropicVersion: "2023-06-01",
    label: "Anthropic Direct (Claude models)",
    enabled: true,
  });
  if (anthropicKey) {
    logger.info(`Provider anthropic registered (${maskKey(anthropicKey)}) → ${anthropicUrl}`);
  } else {
    logger.info(`Provider anthropic registered (pass-through mode, no static key) → ${anthropicUrl}`);
  }

  // If neither provider is configured but CASSICORE_PROXY_UPSTREAM is set,
  // register it as an "upstream" provider for backward compatibility.
  if (providers.size === 0) {
    const fallbackUrl = process.env.CASSICORE_PROXY_UPSTREAM ?? "https://api.anthropic.com";
    const fallbackKey = process.env.ANTHROPIC_AUTH_TOKEN ?? process.env.ANTHROPIC_API_KEY ?? "";
    registerProvider({
      id: "upstream",
      baseUrl: fallbackUrl,
      apiKey: fallbackKey,
      apiKeyHeader: "x-api-key",
      anthropicVersion: "2023-06-01",
      label: "Legacy upstream fallback",
      enabled: true,
    });
    logger.warn(`No providers configured — using legacy upstream: ${fallbackUrl}`);
  }
}

function registerProvider(config: ProviderConfig): void {
  providers.set(config.id, {
    ...config,
    health: {
      lastCheck: 0,
      consecutiveFailures: 0,
      circuitOpen: false,
      circuitOpenedAt: 0,
      totalRequests: 0,
      totalSuccesses: 0,
      totalFailures: 0,
    },
  });
}


export function getProvider(id: string): Provider | undefined {
  return providers.get(id);
}

export function getAllProviders(): Provider[] {
  return [...providers.values()];
}

export function getEnabledProviders(): Provider[] {
  return [...providers.values()].filter(p => p.enabled);
}

/**
 * Get the default provider (first enabled, non-circuit-open provider).
 * Falls back to any enabled provider if all circuits are open.
 */
export function getDefaultProvider(): Provider | undefined {
  const enabled = getEnabledProviders();
  const healthy = enabled.find(p => !p.health.circuitOpen);
  return healthy ?? enabled[0];
}


/**
 * Record a successful request to a provider.
 * Resets the circuit breaker.
 */
export function recordSuccess(providerId: string): void {
  const provider = providers.get(providerId);
  if (!provider) return;
  provider.health.consecutiveFailures = 0;
  provider.health.circuitOpen = false;
  provider.health.circuitOpenedAt = 0;
  provider.health.totalRequests++;
  provider.health.totalSuccesses++;
  provider.health.lastCheck = Date.now();
}

/**
 * Record a failed request to a provider.
 * Opens the circuit breaker after CIRCUIT_BREAKER_THRESHOLD consecutive failures.
 */
export function recordFailure(providerId: string): void {
  const provider = providers.get(providerId);
  if (!provider) return;
  provider.health.consecutiveFailures++;
  provider.health.totalRequests++;
  provider.health.totalFailures++;
  provider.health.lastCheck = Date.now();

  if (provider.health.consecutiveFailures >= CIRCUIT_BREAKER_THRESHOLD) {
    provider.health.circuitOpen = true;
    provider.health.circuitOpenedAt = Date.now();
    logger.warn(
      `Circuit breaker OPEN for ${providerId} after ${provider.health.consecutiveFailures} consecutive failures`,
    );
  }
}

/**
 * Check if a provider is available (enabled and circuit not open, or
 * circuit-reset interval has elapsed).
 */
export function isAvailable(providerId: string): boolean {
  const provider = providers.get(providerId);
  if (!provider || !provider.enabled) return false;
  if (!provider.health.circuitOpen) return true;

  // Half-open: allow a probe after the reset interval
  const elapsed = Date.now() - provider.health.circuitOpenedAt;
  if (elapsed >= CIRCUIT_BREAKER_RESET_MS) {
    logger.info(`Circuit half-open for ${providerId} — allowing probe request`);
    return true;
  }

  return false;
}

/**
 * Get health status summary for all providers.
 */
export function getHealthSummary(): Record<string, {
  label: string;
  baseUrl: string;
  enabled: boolean;
  circuitOpen: boolean;
  consecutiveFailures: number;
  totalRequests: number;
  totalFailures: number;
  available: boolean;
  hasApiKey: boolean;
  apiKeyHeader: string;
  apiKeyPreview: string | null;
}> {
  const result: Record<string, any> = {};
  for (const [id, provider] of providers) {
    result[id] = {
      label: provider.label,
      baseUrl: provider.baseUrl,
      enabled: provider.enabled,
      circuitOpen: provider.health.circuitOpen,
      consecutiveFailures: provider.health.consecutiveFailures,
      totalRequests: provider.health.totalRequests,
      totalFailures: provider.health.totalFailures,
      available: isAvailable(id),
      hasApiKey: !!provider.apiKey,
      apiKeyHeader: provider.apiKeyHeader,
      apiKeyPreview: provider.apiKey ? maskKey(provider.apiKey) : null,
    };
  }
  return result;
}


function maskKey(key: string): string {
  if (key.length <= 8) return "****";
  return key.slice(0, 4) + "..." + key.slice(-4);
}
