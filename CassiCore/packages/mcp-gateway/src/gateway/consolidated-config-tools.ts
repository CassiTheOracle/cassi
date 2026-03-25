#!/usr/bin/env node
/**
 * Consolidated Config Tools Module
 *
 * Merges 5 config tools into a single cassi_config tool with action parameter:
 * - get, set, providers, provider_metrics, provider_config
 */

import { executeConfigAdminTool } from './config-admin-tools.js';
import type { ILogger } from '../../types/interfaces.js';

/**
 * Consolidated config tool definition
 */
export const CONFIG_CONSOLIDATED_TOOL = {
  name: 'config',
  description: 'Configuration management — get/set config, list providers, view metrics. Use action parameter to select operation.',
  inputSchema: {
    type: 'object',
    properties: {
      action: {
        type: 'string',
        enum: ['get', 'set', 'providers', 'provider_metrics', 'provider_config'],
        description: 'Config operation to perform',
      },
      // get/set params
      key: {
        type: 'string',
        description: 'Config key path (e.g., "intelligence.thinker.enabled")',
      },
      // set params
      value: {
        description: 'Value to set (string, number, boolean, or object)',
      },
      // providers params
      includeHealth: {
        type: 'boolean',
        description: 'Include detailed health and quota data (default true)',
      },
      // provider_metrics params
      providerId: {
        type: 'string',
        description: 'Filter by provider ID (e.g., "anthropic", "github-copilot")',
      },
      model: {
        type: 'string',
        description: 'Filter by model name',
      },
      // provider_config params
      providerAction: {
        type: 'string',
        enum: ['get', 'set', 'reset'],
        description: 'Action for provider_config (default "get")',
      },
      config: {
        type: 'object',
        description: 'Configuration object to set (for provider_config set action)',
      },
    },
    required: ['action'],
  },
};

/**
 * Tool name for routing
 */
export const CONFIG_CONSOLIDATED_TOOL_NAME = 'config';

/**
 * Action to legacy tool name mapping
 */
const ACTION_TO_TOOL_NAME: Record<string, string> = {
  get: 'config_get',
  set: 'config_set',
  providers: 'providers',
  provider_metrics: 'provider_metrics',
  provider_config: 'provider_config',
};

/**
 * Execute the consolidated config tool
 *
 * @param baseUrl - CassiCore base URL
 * @param args - Tool arguments including action
 * @param logger - Logger instance
 */
export async function executeConfigConsolidatedTool(
  baseUrl: string,
  args: any,
  logger: ILogger
): Promise<any> {
  const { action, providerAction, ...restArgs } = args;

  if (!action) {
    throw new Error('Missing required parameter: action');
  }

  logger.info('Executing consolidated config tool', { action, args: restArgs });

  const toolName = ACTION_TO_TOOL_NAME[action];
  if (!toolName) {
    throw new Error(`Unknown config action: ${action}`);
  }

  // Merge providerAction into args for provider_config
  const finalArgs = {
    ...restArgs,
    ...(providerAction && action === 'provider_config' ? { action: providerAction } : {}),
  };

  return await executeConfigAdminTool(baseUrl, toolName, finalArgs, logger);
}

/**
 * Get the consolidated config tool definition
 */
export function getConfigConsolidatedTool(): typeof CONFIG_CONSOLIDATED_TOOL {
  return CONFIG_CONSOLIDATED_TOOL;
}
