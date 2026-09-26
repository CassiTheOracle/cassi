/**
 * ThinkerSession scoped tools — Phase 2 of the parallel Thinker architecture.
 *
 * Provides a curated set of read-heavy tools for the Thinker's SDK sessions.
 * The Thinker can read files, search code, access memory, and post to blackboards,
 * but cannot write to the filesystem. This gives the Thinker independent research
 * capability while preventing side effects.
 *
 * Tool set:
 *   - read_file       — Read file contents (workspace-bounded, max 50KB)
 *   - search_code     — Regex search across codebase files (max 50 results)
 *   - list_directory  — List files/dirs at a path
 *   - memory_store    — Store insights/findings to persistent memory
 *   - blackboard_read — Read shared blackboard entries
 *   - blackboard_post — Post findings/concerns to blackboards
 *
 * Safety constraints:
 *   - No filesystem writes (read-only FS access)
 *   - Path validation (workspace-bounded)
 *   - Size caps on reads (50KB per file, 50 search results)
 *   - Per-turn tool call limit (15 calls before forced stop)
 */

import type { ILogger } from '@cassicore/foundation'

/** Safety limits for Thinker tool operations */
export const TOOL_LIMITS = {
  maxFileBytes: 50_000,
  maxSearchResults: 50,
  maxMemoryResults: 10,
  maxToolCallsPerTurn: 15,
} as const

/**
 * Mutable counter shared between tool handlers and the ThinkerSession.
 * ThinkerSession resets the count at the start of each processItem() call;
 * tool handlers increment it on each invocation.
 */
export interface ToolCallTracker {
  count: number
  reset(): void
}

export function createToolCallTracker(): ToolCallTracker {
  return {
    count: 0,
    reset() { this.count = 0 },
  }
}

/**
 * Interface for the concrete tool implementations injected into ThinkerSession.
 * Implementations wire to CassiCore internals (filesystem, memory, blackboard)
 * and enforce workspace-bounding and size limits.
 */
export interface ThinkerToolProvider {
  readFile(path: string, maxBytes: number): Promise<string>

  searchCode(
    pattern: string,
    options?: { path?: string; maxResults?: number },
  ): Promise<Array<{ file: string; line: number; text: string }>>

  listDirectory(path: string): Promise<string[]>

  memorySearch(
    query: string,
    limit: number,
  ): Promise<Array<{ content: string; tags?: string[]; key?: string }>>

  memoryStore(content: string, tags?: string[]): Promise<string>

  blackboardRead(name: string, channel?: string): Promise<string>

  blackboardPost(
    name: string,
    content: string,
    channel: string,
    tags?: string[],
  ): Promise<void>

  /** Phase 4: Read context health posted by the OpenCode plugin */
  kvGet?(key: string): Promise<unknown>

  /** Phase 4: Write context directives for the OpenCode plugin */
  kvSet?(key: string, value: unknown): Promise<void>

}

/**
 * SDK-compatible tool definition.
 * Matches the customTools parameter shape of CopilotSdkProvider.executeStandaloneTurn().
 */
export interface ThinkerSdkTool {
  name: string
  description: string
  parameters: Record<string, unknown>
  handler: (args: unknown) => Promise<{ textResultForLlm: string; resultType: 'success' | 'error' }>
}

/**
 * Build the set of scoped SDK tools for a ThinkerSession.
 *
 * Each tool wraps the provider's implementation with:
 *   - Per-turn call limit enforcement (via shared tracker)
 *   - Error containment (handler errors become error text, never throw)
 *   - Debug logging for observability
 *
 * The returned tools are passed to CopilotSdkProvider.executeScopedTurn()
 * which registers them with the SDK session. The tool handlers close over
 * the tracker reference — resetting tracker.count between turns resets
 * the per-turn limit without rebuilding the tools.
 */
export function buildThinkerSdkTools(
  provider: ThinkerToolProvider,
  logger: ILogger,
  tracker: ToolCallTracker,
): ThinkerSdkTool[] {
  const log = logger.child?.('thinker-tools') ?? logger

  const guard = (): { textResultForLlm: string; resultType: 'error' } | null => {
    tracker.count++
    if (tracker.count > TOOL_LIMITS.maxToolCallsPerTurn) {
      log.info('Thinker tool call limit reached', { count: tracker.count })
      return {
        textResultForLlm: `Tool call limit reached (${TOOL_LIMITS.maxToolCallsPerTurn} per turn). Summarize your findings and respond without further tool calls.`,
        resultType: 'error',
      }
    }
    return null
  }

  return [
    // read_file — read workspace file contents (bounded)
    {
      name: 'read_file',
      description: 'Read the contents of a file in the workspace. Returns up to 50KB of text.',
      parameters: {
        type: 'object',
        properties: {
          path: { type: 'string', description: 'Relative path to the file from workspace root' },
        },
        required: ['path'],
      },
      handler: async (args: unknown) => {
        const limited = guard()
        if (limited) return limited
        try {
          const { path } = args as { path: string }
          const content = await provider.readFile(path, TOOL_LIMITS.maxFileBytes)
          log.debug('read_file', { path, bytes: content.length })
          return { textResultForLlm: content, resultType: 'success' as const }
        } catch (err) {
          return { textResultForLlm: `Error reading file: ${String(err)}`, resultType: 'error' as const }
        }
      },
    },

    // search_code — regex search across codebase
    {
      name: 'search_code',
      description: 'Search for a regex pattern across codebase files. Returns matching lines with file paths and line numbers. Max 50 results.',
      parameters: {
        type: 'object',
        properties: {
          pattern: { type: 'string', description: 'Regex pattern to search for' },
          path: { type: 'string', description: 'Optional subdirectory to restrict search' },
        },
        required: ['pattern'],
      },
      handler: async (args: unknown) => {
        const limited = guard()
        if (limited) return limited
        try {
          const { pattern, path } = args as { pattern: string; path?: string }
          const results = await provider.searchCode(pattern, {
            path,
            maxResults: TOOL_LIMITS.maxSearchResults,
          })
          log.debug('search_code', { pattern, resultCount: results.length })
          if (results.length === 0) {
            return { textResultForLlm: 'No matches found.', resultType: 'success' as const }
          }
          const formatted = results.map(r => `${r.file}:${r.line}: ${r.text}`).join('\n')
          return { textResultForLlm: formatted, resultType: 'success' as const }
        } catch (err) {
          return { textResultForLlm: `Error searching: ${String(err)}`, resultType: 'error' as const }
        }
      },
    },

    // list_directory — list files and dirs at a path
    {
      name: 'list_directory',
      description: 'List files and directories at the given path. Use "." for workspace root.',
      parameters: {
        type: 'object',
        properties: {
          path: { type: 'string', description: 'Relative path to list' },
        },
        required: ['path'],
      },
      handler: async (args: unknown) => {
        const limited = guard()
        if (limited) return limited
        try {
          const { path } = args as { path: string }
          const entries = await provider.listDirectory(path)
          log.debug('list_directory', { path, entries: entries.length })
          return { textResultForLlm: entries.join('\n'), resultType: 'success' as const }
        } catch (err) {
          return { textResultForLlm: `Error listing directory: ${String(err)}`, resultType: 'error' as const }
        }
      },
    },

    // memory_store — persist insights/findings
    {
      name: 'memory_store',
      description: 'Store an insight, finding, or observation in persistent memory for future reference.',
      parameters: {
        type: 'object',
        properties: {
          content: { type: 'string', description: 'Content to store' },
          tags: {
            type: 'array',
            items: { type: 'string' },
            description: 'Optional categorization tags',
          },
        },
        required: ['content'],
      },
      handler: async (args: unknown) => {
        const limited = guard()
        if (limited) return limited
        try {
          const { content, tags } = args as { content: string; tags?: string[] }
          const id = await provider.memoryStore(content, tags)
          log.debug('memory_store', { id, tags })
          return { textResultForLlm: `Stored to memory (id: ${id})`, resultType: 'success' as const }
        } catch (err) {
          return { textResultForLlm: `Error storing memory: ${String(err)}`, resultType: 'error' as const }
        }
      },
    },

    // blackboard_read — read shared board entries
    {
      name: 'blackboard_read',
      description: 'Read entries from a shared blackboard. Boards persist across sessions.',
      parameters: {
        type: 'object',
        properties: {
          name: { type: 'string', description: 'Board name (e.g. "contributing-todos", "bugs")' },
          channel: {
            type: 'string',
            description: 'Optional channel filter: findings, concerns, decisions, artifacts, bugs',
          },
        },
        required: ['name'],
      },
      handler: async (args: unknown) => {
        const limited = guard()
        if (limited) return limited
        try {
          const { name, channel } = args as { name: string; channel?: string }
          const content = await provider.blackboardRead(name, channel)
          log.debug('blackboard_read', { name, channel })
          return { textResultForLlm: content || 'Board is empty.', resultType: 'success' as const }
        } catch (err) {
          return { textResultForLlm: `Error reading blackboard: ${String(err)}`, resultType: 'error' as const }
        }
      },
    },

    // blackboard_post — post findings/concerns/decisions
    {
      name: 'blackboard_post',
      description: 'Post a finding, concern, decision, or bug to a shared blackboard.',
      parameters: {
        type: 'object',
        properties: {
          name: { type: 'string', description: 'Board name' },
          content: { type: 'string', description: 'Content to post' },
          channel: {
            type: 'string',
            enum: ['findings', 'concerns', 'decisions', 'bugs'],
            description: 'Channel to post in',
          },
          tags: {
            type: 'array',
            items: { type: 'string' },
            description: 'Optional tags',
          },
        },
        required: ['name', 'content', 'channel'],
      },
      handler: async (args: unknown) => {
        const limited = guard()
        if (limited) return limited
        try {
          const { name, content, channel, tags } = args as {
            name: string; content: string; channel: string; tags?: string[]
          }
          await provider.blackboardPost(name, content, channel, tags)
          log.debug('blackboard_post', { name, channel, tags })
          return { textResultForLlm: `Posted to ${name}/${channel}`, resultType: 'success' as const }
        } catch (err) {
          return { textResultForLlm: `Error posting to blackboard: ${String(err)}`, resultType: 'error' as const }
        }
      },
    },

    // read_context_health — Phase 4: read the main agent's context health from KV
    ...(provider.kvGet ? [{
      name: 'read_context_health',
      description: 'Read the main agent\'s context health state including pressure level, top token consumers, and collapse candidates. Use this to decide what context management actions to take.',
      parameters: {
        type: 'object' as const,
        properties: {
          sessionId: { type: 'string', description: 'The OpenCode session ID (from the event payload)' },
        },
        required: ['sessionId'],
      },
      handler: async (args: unknown) => {
        const limited = guard()
        if (limited) return limited
        try {
          const { sessionId } = args as { sessionId: string }
          const health = await provider.kvGet!(`working-state:${sessionId}`)
          if (!health) {
            return { textResultForLlm: 'No context health data available for this session.', resultType: 'success' as const }
          }
          return { textResultForLlm: JSON.stringify(health, null, 2), resultType: 'success' as const }
        } catch (err) {
          return { textResultForLlm: `Error reading context health: ${String(err)}`, resultType: 'error' as const }
        }
      },
    }] : []) as ThinkerSdkTool[],

    // suggest_context_action — Phase 4: write directives for the plugin to apply
    ...(provider.kvSet ? [{
      name: 'suggest_context_action',
      description: 'Write context management directives for the main agent\'s context window. The OpenCode plugin reads these and applies them on the next turn. Use chunk IDs from the context health data.',
      parameters: {
        type: 'object' as const,
        properties: {
          sessionId: { type: 'string', description: 'The OpenCode session ID' },
          collapse: {
            type: 'array',
            items: { type: 'string' },
            description: 'Chunk IDs to collapse (replace with summary placeholder)',
          },
          remove: {
            type: 'array',
            items: { type: 'string' },
            description: 'Chunk IDs to remove entirely (minimal placeholder)',
          },
          pin: {
            type: 'array',
            items: { type: 'string' },
            description: 'Chunk IDs to protect from automatic pruning',
          },
          reason: { type: 'string', description: 'Brief explanation of why these actions are recommended' },
        },
        required: ['sessionId', 'reason'],
      },
      handler: async (args: unknown) => {
        const limited = guard()
        if (limited) return limited
        try {
          const { sessionId, collapse, remove, pin, reason } = args as {
            sessionId: string; collapse?: string[]; remove?: string[]; pin?: string[]; reason: string
          }
          const directive = {
            timestamp: Date.now(),
            collapse: collapse ?? [],
            remove: remove ?? [],
            pin: pin ?? [],
            reason,
          }
          await provider.kvSet!(`context-directives:${sessionId}`, directive)
          const actionCount = (collapse?.length ?? 0) + (remove?.length ?? 0) + (pin?.length ?? 0)
          log.info('suggest_context_action', { sessionId, actionCount, reason })
          return {
            textResultForLlm: `Context directive written: ${actionCount} actions (${collapse?.length ?? 0} collapse, ${remove?.length ?? 0} remove, ${pin?.length ?? 0} pin). Will be applied on the agent's next turn.`,
            resultType: 'success' as const,
          }
        } catch (err) {
          return { textResultForLlm: `Error writing context directive: ${String(err)}`, resultType: 'error' as const }
        }
      },
    }] : []) as ThinkerSdkTool[],
  ]
}
