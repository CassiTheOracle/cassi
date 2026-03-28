#!/usr/bin/env node
/**
 * Consolidated Code Tools Module
 *
 * Merges GitNexus + Serena code intelligence behind a single cassi_code tool.
 */

import { SerenaAutoOnboarding, type ToolRouter } from './serena-onboarding.js'
import type { ILogger } from '../../types/interfaces.js'

// Module-level singleton for Serena onboarding
let serenaOnboarding: SerenaAutoOnboarding | null = null

function getSerenaOnboarding(logger: ILogger): SerenaAutoOnboarding {
  if (!serenaOnboarding) {
    serenaOnboarding = new SerenaAutoOnboarding(logger)
  }
  return serenaOnboarding
}

/**
 * Consolidated code tool definition
 */
export const CODE_CONSOLIDATED_TOOL = {
  name: 'code',
  description: 'Code intelligence operations — query code knowledge graph, analyze symbol context, assess impact, run Cypher queries, and perform code modifications. Use action parameter to select operation.',
  inputSchema: {
    type: 'object',
    properties: {
      action: {
        type: 'string',
        enum: [
          'query', 'context', 'impact', 'cypher', 'detect_changes', 'list_repos', 'rename_graph',
          'symbol', 'refs', 'overview', 'search_pattern', 'rename_symbol', 'replace_symbol', 'insert_after', 'insert_before',
        ],
        description: 'Code operation to perform',
      },
      // query params
      query: {
        type: 'string',
        description: 'Search query (for query, cypher, search_pattern actions)',
      },
      goal: {
        type: 'string',
        description: 'What you want to find (for query action)',
      },
      task_context: {
        type: 'string',
        description: 'What you are working on (for query action)',
      },
      // context params
      name: {
        type: 'string',
        description: 'Symbol name (for context action)',
      },
      uid: {
        type: 'string',
        description: 'Direct symbol UID (for context action)',
      },
      file_path: {
        type: 'string',
        description: 'File path to disambiguate common names (for context, rename_graph actions)',
      },
      // impact params
      target: {
        type: 'string',
        description: 'Name of function, class, or file to analyze (for impact action)',
      },
      direction: {
        type: 'string',
        enum: ['upstream', 'downstream'],
        description: 'upstream (what depends on this) or downstream (what this depends on) (for impact action)',
      },
      maxDepth: {
        type: 'number',
        description: 'Maximum relationship depth (for impact action, default 3)',
      },
      minConfidence: {
        type: 'number',
        description: 'Minimum confidence 0-1 (for impact action, default 0.7)',
      },
      relationTypes: {
        type: 'array',
        items: { type: 'string' },
        description: 'Relationship types to include: CALLS, IMPORTS, EXTENDS, IMPLEMENTS, HAS_METHOD, HAS_PROPERTY, OVERRIDES, ACCESSES (for impact action)',
      },
      includeTests: {
        type: 'boolean',
        description: 'Include test files (for impact action)',
      },
      // detect_changes params
      scope: {
        type: 'string',
        enum: ['unstaged', 'staged', 'all', 'compare'],
        description: 'What to analyze (for detect_changes action)',
      },
      base_ref: {
        type: 'string',
        description: 'Branch/commit for compare scope (for detect_changes action)',
      },
      // rename_graph params
      symbol_name: {
        type: 'string',
        description: 'Current symbol name to rename (for rename_graph action)',
      },
      symbol_uid: {
        type: 'string',
        description: 'Direct symbol UID (for rename_graph action)',
      },
      new_name: {
        type: 'string',
        description: 'New name for the symbol (for rename_graph, rename_symbol actions)',
      },
      dry_run: {
        type: 'boolean',
        description: 'Preview edits without modifying files (for rename_graph action, default true)',
      },
      // symbol, refs, rename_symbol, replace_symbol, insert_after, insert_before params
      name_path: {
        type: 'string',
        description: 'Name path pattern for symbol lookup (for symbol, refs, rename_symbol, replace_symbol, insert_after, insert_before actions)',
      },
      name_path_pattern: {
        type: 'string',
        description: 'Name path pattern to match (for symbol action)',
      },
      relative_path: {
        type: 'string',
        description: 'File or directory path (for symbol, refs, overview, search_pattern, rename_symbol, replace_symbol, insert_after, insert_before actions)',
      },
      // symbol params
      include_body: {
        type: 'boolean',
        description: 'Include full symbol source code (for symbol action)',
      },
      include_info: {
        type: 'boolean',
        description: 'Include additional info like docstring and signature (for symbol action)',
      },
      depth: {
        type: 'number',
        description: 'Depth up to which descendants shall be retrieved (for symbol, overview actions)',
      },
      substring_matching: {
        type: 'boolean',
        description: 'Use substring matching for the last element of the pattern (for symbol action)',
      },
      // search_pattern params
      substring_pattern: {
        type: 'string',
        description: 'Regular expression for a substring pattern to search for (for search_pattern action)',
      },
      restrict_search_to_code_files: {
        type: 'boolean',
        description: 'Restrict search to only code files (for search_pattern action)',
      },
      context_lines_before: {
        type: 'number',
        description: 'Number of lines of context to include before each match (for search_pattern action)',
      },
      context_lines_after: {
        type: 'number',
        description: 'Number of lines of context to include after each match (for search_pattern action)',
      },
      paths_include_glob: {
        type: 'string',
        description: 'Glob pattern specifying files to include (for search_pattern action)',
      },
      paths_exclude_glob: {
        type: 'string',
        description: 'Glob pattern specifying files to exclude (for search_pattern action)',
      },
      // replace_symbol, insert_after, insert_before params
      body: {
        type: 'string',
        description: 'The new symbol body or content to insert (for replace_symbol, insert_after, insert_before actions)',
      },
      // Common params
      repo: {
        type: 'string',
        description: 'Repository name or path (for GitNexus actions)',
      },
      limit: {
        type: 'number',
        description: 'Maximum results to return (for query action, default 5)',
      },
      max_symbols: {
        type: 'number',
        description: 'Max symbols per process (for query action, default 10)',
      },
      include_content: {
        type: 'boolean',
        description: 'Include full symbol source code (for query, context actions)',
      },
      // params catch-all for less common params
      params: {
        type: 'object',
        description: 'Additional parameters for the underlying tool',
      },
    },
    required: ['action'],
  },
}

/**
 * Tool name for routing
 */
export const CODE_CONSOLIDATED_TOOL_NAME = 'code'

/**
 * Read-only actions (for Yang/Yin postures)
 */
const READ_ONLY_ACTIONS = new Set([
  'query', 'context', 'impact', 'cypher', 'detect_changes', 'list_repos',
  'symbol', 'refs', 'overview', 'search_pattern',
])

/**
 * Actions that require Serena onboarding
 */
const SERENA_ACTIONS = new Set([
  'symbol', 'refs', 'overview', 'search_pattern', 'rename_symbol', 'replace_symbol', 'insert_after', 'insert_before',
])

/**
 * Execute the consolidated code tool
 *
 * @param args - Tool arguments including action
 * @param logger - Logger instance
 * @param router - Tool router function
 */
export async function executeCodeConsolidatedTool(
  args: any,
  logger: ILogger,
  router: ToolRouter
): Promise<any> {
  const { action, params: extraParams = {}, ...restArgs } = args

  if (!action) {
    throw new Error('Missing required parameter: action')
  }

  logger.debug('Executing consolidated code tool', { action })

  // Ensure Serena onboarding for Serena-backed actions
  if (SERENA_ACTIONS.has(action)) {
    const onboarding = getSerenaOnboarding(logger)
    await onboarding.ensureOnboarded(router)
  }

  // Merge extra params
  const mergedArgs = { ...restArgs, ...extraParams }

  switch (action) {
    case 'query': {
      const { query, goal, task_context, limit, max_symbols, include_content, repo } = mergedArgs
      return await router('gitnexus_query', {
        query,
        goal,
        task_context,
        limit,
        max_symbols,
        include_content,
        repo,
      })
    }
    case 'context': {
      const { name, uid, file_path, include_content, repo } = mergedArgs
      return await router('gitnexus_context', {
        name,
        uid,
        file_path,
        include_content,
        repo,
      })
    }
    case 'impact': {
      const { target, direction, maxDepth, minConfidence, relationTypes, includeTests, repo } = mergedArgs
      return await router('gitnexus_impact', {
        target,
        direction,
        maxDepth,
        minConfidence,
        relationTypes,
        includeTests,
        repo,
      })
    }
    case 'cypher': {
      const { query, repo } = mergedArgs
      return await router('gitnexus_cypher', { query, repo })
    }
    case 'detect_changes': {
      const { scope, base_ref, repo } = mergedArgs
      return await router('gitnexus_detect_changes', { scope, base_ref, repo })
    }
    case 'list_repos': {
      return await router('gitnexus_list_repos', {})
    }
    case 'rename_graph': {
      const { symbol_name, symbol_uid, new_name, file_path, dry_run, repo } = mergedArgs
      return await router('gitnexus_rename', {
        symbol_name,
        symbol_uid,
        new_name,
        file_path,
        dry_run,
        repo,
      })
    }
    case 'symbol': {
      const { name_path_pattern, relative_path, include_body, include_info, depth, substring_matching } = mergedArgs
      return await router('serena_find_symbol', {
        name_path_pattern,
        relative_path,
        include_body,
        include_info,
        depth,
        substring_matching,
      })
    }
    case 'refs': {
      const { name_path, relative_path } = mergedArgs
      return await router('serena_find_referencing_symbols', { name_path, relative_path })
    }
    case 'overview': {
      const { relative_path, depth } = mergedArgs
      return await router('serena_get_symbols_overview', { relative_path, depth })
    }
    case 'search_pattern': {
      const {
        substring_pattern,
        relative_path,
        restrict_search_to_code_files,
        context_lines_before,
        context_lines_after,
        paths_include_glob,
        paths_exclude_glob,
      } = mergedArgs
      return await router('serena_search_for_pattern', {
        substring_pattern,
        relative_path,
        restrict_search_to_code_files,
        context_lines_before,
        context_lines_after,
        paths_include_glob,
        paths_exclude_glob,
      })
    }
    case 'rename_symbol': {
      const { name_path, relative_path, new_name } = mergedArgs
      return await router('serena_rename_symbol', { name_path, relative_path, new_name })
    }
    case 'replace_symbol': {
      const { name_path, relative_path, body } = mergedArgs
      return await router('serena_replace_symbol_body', { name_path, relative_path, body })
    }
    case 'insert_after': {
      const { name_path, relative_path, body } = mergedArgs
      return await router('serena_insert_after_symbol', { name_path, relative_path, body })
    }
    case 'insert_before': {
      const { name_path, relative_path, body } = mergedArgs
      return await router('serena_insert_before_symbol', { name_path, relative_path, body })
    }
    default:
      throw new Error(`Unknown code action: ${action}`)
  }
}

/**
 * Get the consolidated code tool definition
 */
export function getCodeConsolidatedTool(): typeof CODE_CONSOLIDATED_TOOL {
  return CODE_CONSOLIDATED_TOOL
}

/**
 * Get the code tool schema with filtered actions for read-only access
 */
export function getCodeConsolidatedToolSchema(readOnly: boolean = false): typeof CODE_CONSOLIDATED_TOOL {
  if (!readOnly) {
    return CODE_CONSOLIDATED_TOOL
  }

  // Filter to read-only actions
  const readOnlyEnum = CODE_CONSOLIDATED_TOOL.inputSchema.properties.action.enum.filter(
    (a: string) => READ_ONLY_ACTIONS.has(a)
  )

  return {
    ...CODE_CONSOLIDATED_TOOL,
    inputSchema: {
      ...CODE_CONSOLIDATED_TOOL.inputSchema,
      properties: {
        ...CODE_CONSOLIDATED_TOOL.inputSchema.properties,
        action: {
          ...CODE_CONSOLIDATED_TOOL.inputSchema.properties.action,
          enum: readOnlyEnum,
        },
      },
    },
  }
}
