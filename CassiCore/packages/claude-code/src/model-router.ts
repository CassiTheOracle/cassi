/**
 * Model Router for the CassiCore Claude Code Proxy.
 *
 * Routes incoming API requests to the correct provider based on the model name.
 * Uses a hybrid resolution strategy:
 *
 *  1. Try CassiCore's ModelDirective via bridge (daemon knows all providers + tiers)
 *  2. Fall back to routes.json config file (if present)
 *  3. Fall back to hardcoded defaults
 *
 * Default routing (two rules, that's it):
 *   claude-*   → anthropic   (all Claude models → Anthropic direct)
 *   glm-*      → z.ai        (all GLM models → z.ai gateway)
 *   *          → z.ai        (catch-all)
 *
 * The router consults the provider registry for availability and circuit-breaker
 * state, falling back to the next matching provider if the first choice is down.
 */

import fs from "node:fs";
import { URL } from "node:url";
import {
  getProvider,
  getDefaultProvider,
  isAvailable,
  type Provider,
} from "./provider-registry.js";
import * as bridge from "./bridge.js";
import { integrationLogger } from "./logger.js";

const logger = integrationLogger.child("model-router");


export interface RouteRule {
  /** Glob-style pattern to match against model names (e.g., "claude-*", "glm-*") */
  pattern: string;
  /** Provider ID to route to */
  providerId: string;
  /** Optional model name alias — rename the model when sending upstream */
  modelAlias?: string;
  /** Priority (lower = higher priority). Same-priority rules are checked in order. */
  priority: number;
}

export interface ResolvedRoute {
  /** The provider to route to */
  provider: Provider;
  /** The model name to send upstream (may be aliased) */
  model: string;
  /** Which rule matched */
  matchedRule: RouteRule;
  /** Whether this is a fallback (primary provider was unavailable) */
  isFallback: boolean;
  /** The originally requested model */
  originalModel: string;
  /** Where this route came from */
  source: "daemon" | "config" | "default";
}


const DEFAULT_ROUTES: RouteRule[] = [
  { pattern: "claude-*", providerId: "anthropic", priority: 10 },
  { pattern: "glm-*",    providerId: "z.ai",      priority: 10 },
  { pattern: "*",        providerId: "z.ai",       priority: 100 },
];

let routes: RouteRule[] = [...DEFAULT_ROUTES];
let routeSource: "daemon" | "config" | "default" = "default";


/**
 * Initialize the routing table. Tries daemon → config file → defaults.
 */
export async function initRoutes(): Promise<void> {
  // 1. Try CassiCore daemon's ModelDirective
  try {
    const daemonRoutes = await fetchDaemonRoutes();
    if (daemonRoutes && daemonRoutes.length > 0) {
      routes = daemonRoutes;
      routeSource = "daemon";
      logger.info(`Loaded ${routes.length} routes from CassiCore daemon`);
      return;
    }
  } catch {
    // Daemon unavailable — expected
  }

  // 2. Try routes.json config file
  try {
    const configRoutes = loadConfigRoutes();
    if (configRoutes && configRoutes.length > 0) {
      routes = configRoutes;
      routeSource = "config";
      logger.info(`Loaded ${routes.length} routes from routes.json`);
      return;
    }
  } catch {
    // No config file — expected
  }

  // 3. Use defaults
  routes = [...DEFAULT_ROUTES];
  routeSource = "default";
  logger.info(`Using ${routes.length} default routes`);
}

/**
 * Fetch routing from CassiCore's ModelDirective via the admin API bridge.
 *
 * The daemon already knows every tier → provider mapping, so we just ask it
 * "given model X, which provider should I use?" for each known model family.
 */
async function fetchDaemonRoutes(): Promise<RouteRule[] | null> {
  const available = await bridge.available();
  if (!available) return null;

  try {
    // Ask the daemon for its current tier mappings
    const res = await bridge.send("GET", "/model-directive/tiers");
    if (!res || res.error) return null;

    // The daemon returns something like:
    // { tiers: { sonnet: { provider: "copilot-sdk", model: "claude-sonnet-4.6" }, ... } }
    const tiers = res.tiers ?? res;
    if (typeof tiers !== "object") return null;

    const rules: RouteRule[] = [];
    let priority = 10;

    for (const [tierName, config] of Object.entries(tiers as Record<string, any>)) {
      if (!config?.provider || !config?.model) continue;

      // Derive a glob pattern from the model name
      // e.g., "claude-sonnet-4.6" → "claude-sonnet-*"
      const pattern = modelToPattern(config.model);

      rules.push({
        pattern,
        providerId: mapProviderId(config.provider),
        priority,
      });
      priority += 10;
    }

    // Always add catch-all
    rules.push({ pattern: "*", providerId: "z.ai", priority: 1000 });

    return rules.length > 1 ? rules : null;
  } catch {
    return null;
  }
}

/**
 * Derive a glob pattern from a concrete model name.
 *   claude-sonnet-4.6     → claude-*
 *   glm-5-turbo           → glm-*
 *   qwen3.6-plus          → qwen*
 *   claude-opus-4.6       → claude-*
 */
function modelToPattern(model: string): string {
  // Extract the model family prefix (everything before the first number or dash-number)
  const family = model.replace(/[-.]?\d+.*$/, "");
  if (family.length >= 3) return `${family}*`;
  return `${model.split("-")[0]}*`;
}

/**
 * Map daemon provider IDs to proxy provider IDs.
 * The daemon uses names like "copilot-sdk" and "alibaba-coding";
 * the proxy uses "anthropic" and "z.ai".
 */
function mapProviderId(daemonProvider: string): string {
  const mapping: Record<string, string> = {
    "copilot-sdk": "anthropic",
    "anthropic": "anthropic",
    "claude-code": "anthropic",
    "alibaba-coding": "z.ai",
    "openrouter": "z.ai",
  };
  return mapping[daemonProvider] ?? daemonProvider;
}

/**
 * Load routes from a routes.json config file next to the proxy.
 */
function loadConfigRoutes(): RouteRule[] | null {
  try {
    const configPath = new URL("../routes.json", import.meta.url).pathname;
    if (!fs.existsSync(configPath)) return null;

    const raw = fs.readFileSync(configPath, "utf-8");
    const config = JSON.parse(raw);

    if (!Array.isArray(config.routes)) return null;

    return config.routes.map((r: any, i: number) => ({
      pattern: r.pattern,
      providerId: r.provider,
      modelAlias: r.alias,
      priority: r.priority ?? (i + 1) * 10,
    }));
  } catch {
    return null;
  }
}


/**
 * Match a model name against a glob pattern.
 * Only uses * (matches any sequence of characters).
 */
function globMatch(pattern: string, text: string): boolean {
  if (pattern === "*") return true;
  if (pattern === text) return true;

  const regexStr = pattern
    .replace(/[.+^${}()|[\]\\]/g, "\\$&")
    .replace(/\*/g, ".*")
    .replace(/\?/g, ".");

  try {
    return new RegExp(`^${regexStr}$`, "i").test(text);
  } catch {
    return pattern === text;
  }
}


/**
 * Resolve the provider for a given model name.
 *
 * Strategy:
 *  1. Sort routes by priority (lower = higher priority)
 *  2. Find the first route whose pattern matches the model
 *  3. Check if the provider is available (circuit breaker)
 *  4. If unavailable, continue to the next matching route
 *  5. If no routes match, fall back to the default provider
 */
export function resolveRoute(model: string): ResolvedRoute | null {
  const sorted = [...routes].sort((a, b) => a.priority - b.priority);
  let fallback: ResolvedRoute | null = null;

  for (const rule of sorted) {
    if (!globMatch(rule.pattern, model)) continue;

    const provider = getProvider(rule.providerId);
    if (!provider) {
      logger.debug(`Route "${rule.pattern}" → ${rule.providerId}: provider not registered`);
      continue;
    }

    if (isAvailable(rule.providerId)) {
      return {
        provider,
        model: rule.modelAlias ?? model,
        matchedRule: rule,
        isFallback: false,
        originalModel: model,
        source: routeSource,
      };
    }

    // Remember first unavailable match as fallback
    if (!fallback) {
      fallback = {
        provider,
        model: rule.modelAlias ?? model,
        matchedRule: rule,
        isFallback: true,
        originalModel: model,
        source: routeSource,
      };
    }
  }

  if (fallback) {
    logger.warn(`All preferred providers for "${model}" circuit-broken → ${fallback.provider.id}`);
    return fallback;
  }

  const defaultProvider = getDefaultProvider();
  if (defaultProvider) {
    return {
      provider: defaultProvider,
      model,
      matchedRule: { pattern: "*", providerId: defaultProvider.id, priority: 999 },
      isFallback: true,
      originalModel: model,
      source: "default",
    };
  }

  logger.error(`No provider available for model "${model}"`);
  return null;
}

/**
 * Resolve the target URL for a request, given the provider and original request path.
 */
export function resolveUpstreamUrl(provider: Provider, originalPath: string): string {
  const base = provider.baseUrl.replace(/\/+$/, "");
  const path = originalPath.startsWith("/") ? originalPath : `/${originalPath}`;
  return `${base}${path}`;
}


export function getRoutes(): RouteRule[] {
  return [...routes];
}

export function getRouteSource(): string {
  return routeSource;
}

export function setRoutes(newRoutes: RouteRule[]): void {
  routes = [...newRoutes];
  logger.info(`Routing table updated: ${routes.length} rules`);
}

export function resetRoutes(): void {
  routes = [...DEFAULT_ROUTES];
  routeSource = "default";
  logger.info("Routing table reset to defaults");
}

export function getRoutingTableSummary(): Array<{
  pattern: string;
  providerId: string;
  priority: number;
  modelAlias: string | null;
  providerAvailable: boolean;
}> {
  return routes
    .sort((a, b) => a.priority - b.priority)
    .map(rule => ({
      pattern: rule.pattern,
      providerId: rule.providerId,
      priority: rule.priority,
      modelAlias: rule.modelAlias ?? null,
      providerAvailable: isAvailable(rule.providerId),
    }));
}
