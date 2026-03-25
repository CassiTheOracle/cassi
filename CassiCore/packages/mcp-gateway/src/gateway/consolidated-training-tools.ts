#!/usr/bin/env node
/**
 * Consolidated Training Tools Module
 *
 * Merges 10 training tools into a single cassi_training tool with action parameter:
 * - stats, search, objects, resolve, labels, quality, annotations, ingest, tag, export
 */

import { executeTrainingTool } from './training-tools.js';
import type { ILogger } from '../../types/interfaces.js';

/**
 * Consolidated training tool definition
 */
export const TRAINING_CONSOLIDATED_TOOL = {
  name: 'training',
  description: 'Training warehouse operations — stats, search, objects, labels, quality, annotations, ingest, tag, export. Use action parameter to select operation.',
  inputSchema: {
    type: 'object',
    properties: {
      action: {
        type: 'string',
        enum: [
          'stats', 'search', 'objects', 'resolve', 'labels',
          'quality', 'annotations', 'ingest', 'tag', 'export',
        ],
        description: 'Training operation to perform',
      },
      // search params
      q: {
        type: 'string',
        description: 'Search query (FTS5 syntax supported)',
      },
      role: {
        type: 'string',
        description: 'Filter by message role (e.g., "user", "assistant", "system")',
      },
      chunk_type: {
        type: 'string',
        description: 'Filter by chunk type (e.g., "tool_call", "tool_result", "message")',
      },
      // objects params
      label: {
        type: 'string',
        description: 'Filter by label',
      },
      minQuality: {
        type: 'number',
        description: 'Minimum quality score filter',
      },
      // resolve params
      ref: {
        type: 'string',
        description: 'Ref key or object ID to resolve',
      },
      // labels params
      namespace: {
        type: 'string',
        description: 'Filter labels by namespace',
      },
      // quality params
      metric: {
        type: 'string',
        description: 'Quality metric name (e.g., "coherence", "helpfulness")',
      },
      // annotations params
      runId: {
        type: 'string',
        description: 'Annotation run ID',
      },
      // ingest/params params
      sources: {
        type: 'array',
        items: { type: 'string' },
        description: 'Sources to ingest from',
      },
      // tag params
      batchSize: {
        type: 'number',
        description: 'Batch size for tagging',
      },
      // export params
      format: {
        type: 'string',
        enum: ['json', 'jsonl'],
        description: 'Export format (default: json)',
      },
      // Common params
      limit: {
        type: 'number',
        description: 'Maximum results to return',
      },
      offset: {
        type: 'number',
        description: 'Offset for pagination',
      },
    },
    required: ['action'],
  },
};

/**
 * Tool name for routing
 */
export const TRAINING_CONSOLIDATED_TOOL_NAME = 'training';

/**
 * Action to legacy tool name mapping
 */
const ACTION_TO_TOOL_NAME: Record<string, string> = {
  stats: 'training_stats',
  search: 'training_search',
  objects: 'training_objects',
  resolve: 'training_resolve',
  labels: 'training_labels',
  quality: 'training_quality',
  annotations: 'training_annotations',
  ingest: 'training_ingest',
  tag: 'training_tag',
  export: 'training_export',
};

/**
 * Execute the consolidated training tool
 *
 * @param baseUrl - CassiCore base URL
 * @param args - Tool arguments including action
 * @param logger - Logger instance
 */
export async function executeTrainingConsolidatedTool(
  baseUrl: string,
  args: any,
  logger: ILogger
): Promise<any> {
  const { action, ...restArgs } = args;

  if (!action) {
    throw new Error('Missing required parameter: action');
  }

  logger.info('Executing consolidated training tool', { action, args: restArgs });

  const toolName = ACTION_TO_TOOL_NAME[action];
  if (!toolName) {
    throw new Error(`Unknown training action: ${action}`);
  }

  return await executeTrainingTool(baseUrl, toolName, restArgs, logger);
}

/**
 * Get the consolidated training tool definition
 */
export function getTrainingConsolidatedTool(): typeof TRAINING_CONSOLIDATED_TOOL {
  return TRAINING_CONSOLIDATED_TOOL;
}
