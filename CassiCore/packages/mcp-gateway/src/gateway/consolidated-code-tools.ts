#!/usr/bin/env node
/**
 * Consolidated Code Tools Module
 *
 * Merges GitNexus + Serena code intelligence behind a single cassi_code tool.
 */

import { SerenaAutoOnboarding, type ToolRouter } from './serena-onboarding.js'
import type { ILogger } from '@cassicore/foundation'
import {
  analyzeDeadCode,
  analyzeHotspots,
  analyzeCochange,
  prepareContext,
  scoreSpecificity,
  introspectSchemas,
  ensureFreshIndex,
  ensureFreshIndexBackground,
} from '@cassicore/workspace'

/**
 * Wraps a GitNexus router call so failures return a structured error object
 * instead of propagating as a raw exception. This lets the agent see the error
 * and optionally retry with `action: 'reindex'`.
 */
async function safeGitNexusRoute(
  router: ToolRouter,
  tool: string,
  args: Record<string, unknown>,
  logger: ILogger,
): Promise<any> {
  try {
    return await router(tool, args)
  } catch (err) {
    const msg = String(err)
    logger.warn('GitNexus tool call failed, returning structured error', { tool, error: msg })
    return {
      content: [{ type: 'text', text: `GitNexus ${tool} failed: ${msg}. The index may be stale — try cassi_code({ action: 'reindex' }).` }],
      isError: true,
    }
  }
}

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
  description: 'Code intelligence operations — query the knowledge graph, analyze symbols, assess blast radius, detect dead code, find hotspots, and perform code modifications. Use action parameter to select operation.\n\nUse this tool for code understanding (query/context), safety analysis before edits (impact), codebase health (dead_code/hotspots/cochange), context assembly for delegation (prepare_context/specificity), and symbol-level code edits (symbol/refs/replace_symbol/insert_after). For simple text search or file reads, prefer cassi_file instead. For full-text pattern search in code, use search_pattern action here or cassi_file with action=search.\n\nCommon actions: query (find code by concept), context (360-degree view of a symbol), impact (blast radius before editing), prepare_context (assemble context for delegation), search_pattern (regex search across codebase).',
  inputSchema: {
    type: 'object',
    properties: {
      action: {
        type: 'string',
        enum: [
          'query', 'context', 'impact', 'cypher', 'detect_changes', 'list_repos', 'rename_graph',
          'symbol', 'refs', 'overview', 'search_pattern', 'rename_symbol', 'replace_symbol', 'insert_after', 'insert_before',
          'dead_code', 'hotspots', 'cochange', 'prepare_context', 'specificity', 'schema', 'reindex',
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
      // dead_code params
      path: {
        type: 'string',
        description: 'Directory scope for dead_code, hotspots actions',
      },
      include_test_only: {
        type: 'boolean',
        description: 'Include test-only symbols (for dead_code action)',
      },
      // cochange params (target reuses existing 'target' field)
      min_commits: {
        type: 'number',
        description: 'Minimum co-occurrences to include (for cochange action, default 3)',
      },
      since: {
        type: 'string',
        description: 'Git date filter (for cochange action, default "6 months ago")',
      },
      // prepare_context params
      task: {
        type: 'string',
        description: 'Task description (for prepare_context action)',
      },
      token_budget: {
        type: 'number',
        description: 'Token budget for assembled context (for prepare_context action, default 8000)',
      },
      // schema params
      database: {
        type: 'string',
        description: 'Filter to specific database (for schema action)',
      },
      table: {
        type: 'string',
        description: 'Filter to specific table (for schema action)',
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
  'dead_code', 'hotspots', 'cochange', 'prepare_context', 'specificity', 'schema', 'reindex',
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
 * @dep callers: routeToolCall (mcp/cassicore-gateway.ts), executeConsolidatedGatewayTools (core/intelligence/helix/helix-posture-runner.ts)
 * @dep calls: analyzeCochange, prepareContext, analyzeDeadCode, ensureFreshIndex, analyzeHotspots [+5]
 * @dep module: Code-analysis
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
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
      ensureFreshIndexBackground(logger)
      return await safeGitNexusRoute(router, 'gitnexus_query', {
        query,
        goal,
        task_context,
        limit,
        max_symbols,
        include_content,
        repo,
      }, logger)
    }
    case 'context': {
      const { name, uid, file_path, include_content, repo } = mergedArgs
      ensureFreshIndexBackground(logger)
      return await safeGitNexusRoute(router, 'gitnexus_context', {
        name,
        uid,
        file_path,
        include_content,
        repo,
      }, logger)
    }
    case 'impact': {
      const { target, direction, maxDepth, minConfidence, relationTypes, includeTests, repo } = mergedArgs
      ensureFreshIndexBackground(logger)
      return await safeGitNexusRoute(router, 'gitnexus_impact', {
        target,
        direction,
        maxDepth,
        minConfidence,
        relationTypes,
        includeTests,
        repo,
      }, logger)
    }
    case 'cypher': {
      const { query, repo } = mergedArgs
      ensureFreshIndexBackground(logger)
      return await safeGitNexusRoute(router, 'gitnexus_cypher', { query, repo }, logger)
    }
    case 'detect_changes': {
      const { scope, base_ref, repo } = mergedArgs
      ensureFreshIndexBackground(logger)
      return await safeGitNexusRoute(router, 'gitnexus_detect_changes', { scope, base_ref, repo }, logger)
    }
    case 'list_repos': {
      ensureFreshIndexBackground(logger)
      return await safeGitNexusRoute(router, 'gitnexus_list_repos', {}, logger)
    }
    case 'rename_graph': {
      const { symbol_name, symbol_uid, new_name, file_path, dry_run, repo } = mergedArgs
      ensureFreshIndexBackground(logger)
      return await safeGitNexusRoute(router, 'gitnexus_rename', {
        symbol_name,
        symbol_uid,
        new_name,
        file_path,
        dry_run,
        repo,
      }, logger)
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


    case 'dead_code': {
      const { path: scopePath, minConfidence, include_test_only, repo } = mergedArgs
      const results = await analyzeDeadCode(router, {
        path: scopePath,
        minConfidence,
        includeTestOnly: include_test_only,
        repo,
      }, logger)

      return {
        output: `Found ${results.length} potentially dead symbols:\n\n` +
          results.map((r, i) =>
            `${i + 1}. **${r.symbolName}** (${r.kind}) in \`${r.filePath}\`\n` +
            `   ${r.lineCount} lines | Confidence: ${(r.confidence * 100).toFixed(0)}% | ${r.reason}`
          ).join('\n\n') +
          (results.length === 0 ? 'No dead code detected with current confidence threshold.' : ''),
        results,
        count: results.length,
      }
    }

    case 'hotspots': {
      const { path: scopePath, limit, repo } = mergedArgs
      const results = await analyzeHotspots(router, {
        path: scopePath,
        limit,
        repo,
      }, logger)

      return {
        output: `Top ${results.length} hotspots (ranked by size × complexity × coupling):\n\n` +
          results.map((r, i) =>
            `${i + 1}. \`${r.filePath}\` — **score: ${r.score}**\n` +
            `   Size: ${r.dimensions.size.toFixed(2)} (${r.raw.lineCount} lines) | ` +
            `Complexity: ${r.dimensions.complexity.toFixed(2)} (${r.raw.symbolCount} symbols) | ` +
            `Coupling: ${r.dimensions.coupling.toFixed(2)} (${r.raw.outgoingEdges} edges)`
          ).join('\n\n') +
          (results.length === 0 ? 'No hotspots found.' : ''),
        results,
        count: results.length,
      }
    }

    case 'cochange': {
      const { path: pathArg, target: targetArg, limit, min_commits, since } = mergedArgs
      const target = targetArg || pathArg
      if (!target) throw new Error('Missing required parameter: target (file path)')

      const results = await analyzeCochange({
        target,
        limit,
        minCommits: min_commits,
        since,
      }, logger)

      return {
        output: `Files that frequently change with \`${target}\`:\n\n` +
          results.map((r, i) =>
            `${i + 1}. \`${r.filePath}\` — score: ${r.score} (${r.cochangeCount} co-changes out of ${r.fileChangeCount} total changes)`
          ).join('\n') +
          (results.length === 0 ? 'No cochange patterns found for this file.' : ''),
        results,
        count: results.length,
      }
    }

    case 'prepare_context': {
      const { task, token_budget, include_content, scope, repo, timeout_ms } = mergedArgs
      if (!task) throw new Error('Missing required parameter: task (description)')

      const result = await prepareContext(router, {
        task,
        tokenBudget: token_budget,
        includeContent: include_content,
        scope,
        repo,
        timeoutMs: timeout_ms,
      }, logger)

      return {
        output: `**Context prepared** (~${result.estimatedTokens} tokens)\n\n` +
          `Keywords: ${result.extractedKeywords.join(', ')}\n\n` +
          `${result.summary}\n\n` +
          `**Key files (${result.files.length}):**\n` +
          result.files.map((f, i) =>
            `${i + 1}. \`${f.filePath}\` (relevance: ${f.relevance.toFixed(2)})\n` +
            `   ${f.reason}\n` +
            `   Symbols: ${f.keySymbols.join(', ') || 'none'}` +
            (f.excerpt ? `\n   \`\`\`\n${f.excerpt.slice(0, 300)}\n   \`\`\`` : '')
          ).join('\n\n'),
        ...result,
      }
    }

    case 'specificity': {
      const { task, query: queryText } = mergedArgs
      const text = task || queryText
      if (!text) throw new Error('Missing required parameter: task or query')

      const result = scoreSpecificity(text)

      const adaptiveNote = result.adaptiveOverride
        ? `\n\n**Adaptive override:** Bayesian model recommends **${result.mode}** (was ${result.adaptiveOverride.originalMode}, confidence: ${result.adaptiveOverride.confidence})\n${result.adaptiveOverride.reason}`
        : ''

      return {
        output: `**Specificity score: ${result.score}** → recommended mode: **${result.mode}**\n\n` +
          `Signals:\n` +
          result.signals.map(s =>
            `  ${s.weight > 0 ? '+' : ''}${s.weight.toFixed(2)} ${s.type}: "${s.match}"`
          ).join('\n') +
          `\n\nInterpretation: ${
            result.mode === 'full' ? 'Query is specific enough for full code context injection.'
            : result.mode === 'file_only' ? 'Query is moderately specific — inject file-level context only.'
            : 'Query is too vague for code context injection — would likely cause context pollution.'
          }` + adaptiveNote,
        ...result,
      }
    }

    case 'schema': {
      const { database, table } = mergedArgs
      const result = introspectSchemas(logger, { database, table })

      return {
        output: `**CassiCore Internal Databases** (${result.databases.length} databases, ${result.totalTables} tables, ${result.totalRows.toLocaleString()} total rows)\n\n` +
          result.databases.map(db =>
            `### ${db.name} (${(db.sizeBytes / 1024).toFixed(1)} KB)\n` +
            `Path: \`${db.path}\`\n\n` +
            db.tables.map(t =>
              `- **${t.name}** (${t.rowCount >= 0 ? t.rowCount.toLocaleString() + ' rows' : 'count unavailable'})\n` +
              `  Columns: ${t.columns.map(c => `\`${c.name}\` ${c.type}${c.pk ? ' PK' : ''}${c.notnull ? ' NOT NULL' : ''}`).join(', ')}`
            ).join('\n')
          ).join('\n\n'),
        ...result,
      }
    }

    case 'reindex': {
      await ensureFreshIndex(logger)
      return {
        output: 'GitNexus index rebuild triggered. The index will be refreshed with the current HEAD commit.',
      }
    }

    default:
      // Handle common LLM confusion: 'read' is a file operation, not a code operation.
      // Provide a helpful error message with valid actions.
      if (action === 'read' || action === 'write' || action === 'edit' || action === 'list' || action === 'find') {
        throw new Error(
          `"${action}" is a file operation, not a code operation. ` +
          `Use the "file" tool with action: "${action}" instead. ` +
          `The "code" tool supports: query, context, impact, symbol, refs, overview, search_pattern, dead_code, hotspots, cochange, schema, reindex`
        )
      }
      throw new Error(
        `Unknown code action: ${action}. ` +
        `Valid actions: query, context, impact, symbol, refs, overview, search_pattern, dead_code, hotspots, cochange, schema, reindex`
      )
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
