#!/usr/bin/env node
/**
 * Config/Admin Tools Module
 * Configuration management, provider management, and health checks
 */

import { fetchWithTimeout, isConfigKeySafe } from './helpers.js';
import type { ILogger } from '@cassicore/foundation';

/**
 * Tool definitions for config/admin tools
 */
export const CONFIG_ADMIN_TOOLS = [
  {
    name: 'config_get',
    description: 'Read CassiCore runtime configuration. Optionally specify a key to read a single value, or omit for the full config.',
    inputSchema: {
      type: 'object',
      properties: {
        key: {
          type: 'string',
          description: 'Specific config key path (e.g., "intelligence.thinker.enabled"). Omit for full config.',
        },
      },
    },
  },
  {
    name: 'config_set',
    description: 'Modify CassiCore runtime configuration (hot-reloaded). Restricted to safe keys: intelligence.*, providers.*.model, providers.*.enabled, channels.*.enabled, logging.level.',
    inputSchema: {
      type: 'object',
      properties: {
        key: {
          type: 'string',
          description: 'Config key path to set',
        },
        value: {
          description: 'Value to set (string, number, boolean, or object)',
        },
      },
      required: ['key', 'value'],
    },
  },
  {
    name: 'providers',
    description: 'List all configured LLM providers with their health status, available models, and quota information.',
    inputSchema: {
      type: 'object',
      properties: {
        includeHealth: {
          type: 'boolean',
          description: 'Include detailed health and quota data (default true)',
        },
      },
    },
  },
  {
    name: 'provider_metrics',
    description: 'Get aggregated provider performance metrics — request counts, latency, error rates, token usage per provider/model.',
    inputSchema: {
      type: 'object',
      properties: {
        providerId: {
          type: 'string',
          description: 'Filter by provider ID (e.g., "anthropic", "github-copilot")',
        },
        model: {
          type: 'string',
          description: 'Filter by model name',
        },
      },
    },
  },
  {
    name: 'provider_config',
    description: 'View or modify provider configuration. Use action "get" to read current config, "set" to update, "reset" to clear error state.',
    inputSchema: {
      type: 'object',
      properties: {
        action: {
          type: 'string',
          enum: ['get', 'set', 'reset'],
          description: 'Action to perform (default "get")',
        },
        providerId: {
          type: 'string',
          description: 'Provider ID (required for "set" and "reset")',
        },
        config: {
          type: 'object',
          description: 'Configuration object to set (for action "set")',
        },
      },
    },
  },
];

/**
 * Config/admin tool names set for quick lookup
 */
export const CONFIG_ADMIN_TOOL_NAMES = new Set(CONFIG_ADMIN_TOOLS.map(t => t.name));

/**
 * Execute a config/admin tool
 */
export async function executeConfigAdminTool(
  baseUrl: string,
  toolName: string,
  args: any,
  logger: ILogger
): Promise<any> {
  logger.info('Executing config/admin tool', { tool: toolName, args });

  switch (toolName) {
    case 'config_get': {
      const path = args?.key ? `/config/${encodeURIComponent(args.key)}` : '/config';
      const res = await fetchWithTimeout(`${baseUrl}${path}`);
      if (!res.ok) throw new Error(`Config get failed: ${await res.text()}`);
      return await res.json();
    }

    case 'config_set': {
      if (!isConfigKeySafe(args.key)) {
        throw new Error(
          `Config key "${args.key}" is not in the safe-list. Allowed patterns: intelligence.*, providers.*.model, providers.*.enabled, channels.*.enabled, logging.level`
        );
      }
      const res = await fetchWithTimeout(`${baseUrl}/config/set`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: args.key, value: args.value }),
      });
      if (!res.ok) throw new Error(`Config set failed: ${await res.text()}`);
      return await res.json();
    }

    case 'providers': {
      const providersRes = await fetchWithTimeout(`${baseUrl}/providers`);
      if (!providersRes.ok) throw new Error(`Providers list failed: ${await providersRes.text().catch(() => 'unknown')}`);
      const providers = await providersRes.json();
      // Health endpoint is best-effort — don't fail the whole call if it 404s
      let health = null;
      if (args?.includeHealth !== false) {
        try {
          const healthRes = await fetchWithTimeout(`${baseUrl}/health/providers`);
          if (healthRes.ok) health = await healthRes.json();
        } catch { /* best-effort */ }
      }
      return health ? { providers, health } : providers;
    }

    case 'provider_metrics': {
      const params = new URLSearchParams();
      if (args?.providerId) params.set('providerId', args.providerId);
      if (args?.model) params.set('model', args.model);
      const qs = params.toString();
      const res = await fetchWithTimeout(`${baseUrl}/providers/metrics${qs ? '?' + qs : ''}`);
      if (!res.ok) throw new Error(`Provider metrics failed: ${await res.text()}`);
      return await res.json();
    }

    case 'provider_config': {
      const action = args?.action || 'get';
      if (action === 'get') {
        const res = await fetchWithTimeout(`${baseUrl}/providers/config`);
        if (!res.ok) throw new Error(`Provider config get failed: ${await res.text()}`);
        return await res.json();
      } else if (action === 'set') {
        const res = await fetchWithTimeout(`${baseUrl}/providers/config`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ providerId: args.providerId, config: args.config }),
        });
        if (!res.ok) throw new Error(`Provider config set failed: ${await res.text()}`);
        return await res.json();
      } else if (action === 'reset') {
        const res = await fetchWithTimeout(`${baseUrl}/providers/reset`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ providerId: args.providerId }),
        });
        if (!res.ok) throw new Error(`Provider reset failed: ${await res.text()}`);
        return await res.json();
      }
      throw new Error(`Unknown provider config action: ${action}`);
    }

    default:
      throw new Error(`Unknown config/admin tool: ${toolName}`);
  }
}

/**
 * Get all config/admin tool definitions
 */
export function getConfigAdminTools(): Array<{
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
}> {
  return CONFIG_ADMIN_TOOLS;
}
