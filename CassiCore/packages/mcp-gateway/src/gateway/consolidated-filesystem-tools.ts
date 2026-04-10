#!/usr/bin/env node
/**
 * Consolidated Filesystem Tools Module
 *
 * Wraps Serena file operations behind a single cassi_file tool.
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
 * Consolidated filesystem tool definition
 */
export const FILESYSTEM_CONSOLIDATED_TOOL = {
  name: 'file',
  description: 'Filesystem operations — read, write, edit, list, find, and search files. Use action parameter to select operation.\n\nUse this tool for direct file I/O: reading file contents (read), writing/creating files (write), replacing text in files (edit), browsing directories (list), finding files by name pattern (find), or searching file contents by regex (search). For code-level operations like symbol lookup, impact analysis, or knowledge graph queries, use cassi_code instead.\n\nCommon actions: read (get file contents with optional offset pagination), edit (find-and-replace text, supports literal or regex mode), search (regex search across files with glob filters), list (directory listing with optional recursion).',
  inputSchema: {
    type: 'object',
    properties: {
      action: {
        type: 'string',
        enum: ['read', 'write', 'edit', 'list', 'find', 'search', 'symbols'],
        description: 'Filesystem operation to perform',
      },
      // read, write, edit, list, find, search, symbols params
      path: {
        type: 'string',
        description: 'File or directory path (for read, write, edit, list actions)',
      },
      // read params
      offset: {
        type: 'number',
        description: 'Character offset to start reading from (for read action). Use to paginate through large files. Default: 0.',
      },
      limit: {
        type: 'number',
        description: 'Maximum characters to return (for read action, maps to max_answer_chars)',
      },
      // write, edit params
      content: {
        type: 'string',
        description: 'Content to write (for write action)',
      },
      // edit params
      oldText: {
        type: 'string',
        description: 'Text to find and replace (for edit action, maps to needle)',
      },
      newText: {
        type: 'string',
        description: 'Replacement text (for edit action, maps to repl)',
      },
      mode: {
        type: 'string',
        enum: ['literal', 'regex'],
        description: 'Replacement mode: literal or regex (for edit action)',
      },
      allow_multiple_occurrences: {
        type: 'boolean',
        description: 'Allow replacing multiple occurrences (for edit action)',
      },
      // list params
      recursive: {
        type: 'boolean',
        description: 'Scan subdirectories recursively (for list action)',
      },
      skip_ignored_files: {
        type: 'boolean',
        description: 'Skip files and directories that are ignored (for list action)',
      },
      // find params
      file_mask: {
        type: 'string',
        description: 'Filename or file mask using wildcards * or ? (for find action)',
      },
      // search params
      pattern: {
        type: 'string',
        description: 'Regular expression pattern to search for (for search action, maps to substring_pattern)',
      },
      context_lines: {
        type: 'number',
        description: 'Number of lines of context around matches (for search action, applies to both before and after)',
      },
      restrict_search_to_code_files: {
        type: 'boolean',
        description: 'Restrict search to only code files (for search action)',
      },
      paths_include_glob: {
        type: 'string',
        description: 'Glob pattern specifying files to include (for search action)',
      },
      paths_exclude_glob: {
        type: 'string',
        description: 'Glob pattern specifying files to exclude (for search action)',
      },
      // symbols params
      depth: {
        type: 'number',
        description: 'Depth up to which descendants shall be retrieved (for symbols action)',
      },
      // Common params
      relative_path: {
        type: 'string',
        description: 'Alternative to path - file or directory path',
      },
    },
    required: ['action'],
  },
}

/**
 * Tool name for routing
 */
export const FILESYSTEM_CONSOLIDATED_TOOL_NAME = 'file'

/**
 * Read-only actions (for Yang/Yin postures)
 */
const READ_ONLY_ACTIONS = new Set(['read', 'list', 'find', 'search', 'symbols'])

/**
 * Execute the consolidated filesystem tool
 *
 * @param args - Tool arguments including action
 * @param logger - Logger instance
 * @param router - Tool router function
 */
export async function executeFilesystemConsolidatedTool(
  args: any,
  logger: ILogger,
  router: ToolRouter
): Promise<any> {
  const { action, path, relative_path, ...restArgs } = args

  if (!action) {
    // Infer action from provided parameters when the LLM omits it
    if (args.pattern || args.substring_pattern) return executeFilesystemConsolidatedTool({ ...args, action: 'search' }, logger, router)
    if (args.file_mask) return executeFilesystemConsolidatedTool({ ...args, action: 'find' }, logger, router)
    if (args.oldText && args.newText) return executeFilesystemConsolidatedTool({ ...args, action: 'edit' }, logger, router)
    if (args.content && (args.path || args.relative_path)) return executeFilesystemConsolidatedTool({ ...args, action: 'write' }, logger, router)
    if (args.path || args.relative_path) return executeFilesystemConsolidatedTool({ ...args, action: 'read' }, logger, router)
    throw new Error('Missing required parameter: action. Use one of: read, write, edit, list, find, search, symbols')
  }

  // Ensure Serena onboarding for all filesystem actions
  const onboarding = getSerenaOnboarding(logger)
  await onboarding.ensureOnboarded(router)

  const targetPath = path ?? relative_path
  if (!targetPath && action !== 'find') {
    throw new Error(`Missing required parameter: path or relative_path for action ${action}`)
  }

  logger.debug('Executing consolidated filesystem tool', { action, path: targetPath })

  switch (action) {
    case 'read': {
      const { limit, offset } = restArgs
      // WHY: When offset is provided, Serena must return at least offset+limit chars
      // so we can slice from the offset position. Without this, Serena's default
      // max_answer_chars may be smaller than the offset, causing "beyond file length"
      // errors that make agents unable to paginate through large files.
      const effectiveMaxChars = (offset && typeof offset === 'number' && offset > 0)
        ? offset + (limit ?? 30_000)
        : limit
      const result = await router('serena_read_file', {
        relative_path: targetPath,
        max_answer_chars: effectiveMaxChars,
      })

      // Apply client-side offset if requested
      if (offset && typeof offset === 'number' && offset > 0) {
        const text = result?.content?.[0]?.text ?? (typeof result === 'string' ? result : '')
        const fullText = typeof text === 'string' ? text : String(text)
        if (offset < fullText.length) {
          const sliced = fullText.slice(offset, limit ? offset + limit : undefined)
          const remaining = fullText.length - offset - sliced.length
          let notice = sliced
          if (remaining > 0) {
            notice += `\n\n[showing chars ${offset.toLocaleString()}-${(offset + sliced.length).toLocaleString()} of ${fullText.length.toLocaleString()} total — ${remaining.toLocaleString()} chars remaining. Use offset: ${offset + sliced.length} to continue.]`
          }
          return { content: [{ type: 'text', text: notice }] }
        } else {
          return { content: [{ type: 'text', text: `[offset ${offset} is beyond file length of ${fullText.length} chars]` }] }
        }
      }

      return result
    }
    case 'write': {
      const { content } = restArgs
      if (content === undefined) {
        throw new Error('Missing required parameter: content for write action')
      }
      // For write, we use replace_content with literal mode
      // If the file doesn't exist, needle won't match anything - we need to handle this
      // Try to read first to see if file exists
      try {
        await router('serena_read_file', { relative_path: targetPath })
        // File exists — use regex to replace all content
        return await router('serena_replace_content', {
          relative_path: targetPath,
          needle: '[\\s\\S]*',
          repl: content,
          mode: 'regex',
        })
      } catch {
        // File doesn't exist or is empty, create it by using empty needle
        return await router('serena_replace_content', {
          relative_path: targetPath,
          needle: '',
          repl: content,
          mode: 'literal',
        })
      }
    }
    case 'edit': {
      const { oldText, newText, mode = 'literal', allow_multiple_occurrences = false } = restArgs
      if (oldText === undefined || newText === undefined) {
        throw new Error('Missing required parameters: oldText and newText for edit action')
      }
      return await router('serena_replace_content', {
        relative_path: targetPath,
        needle: oldText,
        repl: newText,
        mode,
        allow_multiple_occurrences,
      })
    }
    case 'list': {
      const { recursive = false, skip_ignored_files = false } = restArgs
      return await router('serena_list_dir', {
        relative_path: targetPath,
        recursive,
        skip_ignored_files,
      })
    }
    case 'find': {
      const { file_mask = '*' } = restArgs
      return await router('serena_find_file', {
        relative_path: targetPath ?? '.',
        file_mask,
      })
    }
    case 'search': {
      const {
        pattern,
        context_lines = 0,
        restrict_search_to_code_files = false,
        paths_include_glob,
        paths_exclude_glob,
      } = restArgs
      if (!pattern) {
        throw new Error('Missing required parameter: pattern for search action')
      }
      return await router('serena_search_for_pattern', {
        relative_path: targetPath,
        substring_pattern: pattern,
        context_lines_before: context_lines,
        context_lines_after: context_lines,
        restrict_search_to_code_files,
        paths_include_glob,
        paths_exclude_glob,
      })
    }
    case 'symbols': {
      const { depth = 0 } = restArgs
      return await router('serena_get_symbols_overview', {
        relative_path: targetPath,
        depth,
      })
    }
    default:
      throw new Error(`Unknown filesystem action: ${action}`)
  }
}

/**
 * Get the consolidated filesystem tool definition
 */
export function getFilesystemConsolidatedTool(): typeof FILESYSTEM_CONSOLIDATED_TOOL {
  return FILESYSTEM_CONSOLIDATED_TOOL
}

/**
 * Get the filesystem tool schema with filtered actions for read-only access
 */
export function getFilesystemConsolidatedToolSchema(readOnly: boolean = false): typeof FILESYSTEM_CONSOLIDATED_TOOL {
  if (!readOnly) {
    return FILESYSTEM_CONSOLIDATED_TOOL
  }

  // Filter to read-only actions
  const readOnlyEnum = FILESYSTEM_CONSOLIDATED_TOOL.inputSchema.properties.action.enum.filter(
    (a: string) => READ_ONLY_ACTIONS.has(a)
  )

  return {
    ...FILESYSTEM_CONSOLIDATED_TOOL,
    inputSchema: {
      ...FILESYSTEM_CONSOLIDATED_TOOL.inputSchema,
      properties: {
        ...FILESYSTEM_CONSOLIDATED_TOOL.inputSchema.properties,
        action: {
          ...FILESYSTEM_CONSOLIDATED_TOOL.inputSchema.properties.action,
          enum: readOnlyEnum,
        },
      },
    },
  }
}
