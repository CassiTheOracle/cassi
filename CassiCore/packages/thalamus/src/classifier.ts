import type { MessageSlotType } from './types.js'
import { hasQuestionResult } from '../../pipeline/turn/overflow.js'

/**
 * Tool class map — classifies tool names into high-level categories.
 * Originally lived in mcp/gateway/do-augmentation.ts as TOOL_CLASS_MAP.
 * Moved here so the Thalamus owns tool classification rather than the gateway.
 *
 * Used by ToolCallSlot and ToolResultSlot for type-specific compression
 * strategies, scoring adjustments, and prefix rendering.
 */
const TOOL_CLASS_MAP: Record<string, string> = {
  // Shell
  bash: 'shell',

  // Filesystem
  read: 'fs',
  write: 'fs',
  edit: 'fs',
  exists: 'fs',
  mkdir: 'fs',
  delete: 'fs',
  glob: 'fs',
  grep: 'fs',

  // Serena code intelligence
  serena_list_dir: 'fs',
  serena_find_file: 'fs',
  serena_search_for_pattern: 'code',
  serena_get_symbols_overview: 'code',
  serena_find_symbol: 'code',
  serena_find_referencing_symbols: 'code',
  serena_replace_symbol_body: 'code',
  serena_insert_after_symbol: 'code',
  serena_insert_before_symbol: 'code',
  serena_replace_content: 'code',
  serena_rename_symbol: 'code',
  serena_initial_instructions: 'code',
  serena_check_onboarding_performed: 'code',
  serena_onboarding: 'code',
  serena_open_dashboard: 'code',

  // Memory
  memory_search: 'memory',
  memory_store: 'memory',
  memory_recent: 'memory',
  memory_kv_get: 'memory',
  memory_kv_set: 'memory',
  memory_kv_del: 'memory',
  memory_delete: 'memory',
  memory_stats: 'memory',

  // Archive
  archive_search: 'archive',
  archive_recent: 'archive',
  archive_get: 'archive',
  archive_related: 'archive',
  browse: 'archive',
  universal_search: 'archive',

  // Sessions
  sessions: 'sessions',
  session_detail: 'sessions',
  session_export: 'sessions',
  session_conversation: 'sessions',
  session_prune: 'sessions',
  resolve_ref: 'sessions',
  index_search: 'sessions',
  index_session: 'sessions',
  index_stats: 'sessions',

  // Orchestration
  flux_team: 'orchestration',
  flux_run: 'orchestration',
  flux_inspect: 'orchestration',
  flux_watch: 'orchestration',
  lumen_project: 'orchestration',
  lumen_watch: 'orchestration',
  lumen_status: 'orchestration',
  lumen_cancel: 'orchestration',
  lumen_jobs: 'orchestration',
  lumen_sessions: 'orchestration',
  lumen_messages: 'orchestration',
  lumen_tool_calls: 'orchestration',
  lumen_events: 'orchestration',
  lumen_postures: 'orchestration',
  lumen_blackboard: 'orchestration',
  lumen_health: 'orchestration',
  dyad_project: 'orchestration',
  dyad_watch: 'orchestration',
  dyad_status: 'orchestration',
  dyad_cancel: 'orchestration',
  dyad_jobs: 'orchestration',
  dyad_sessions: 'orchestration',
  dyad_messages: 'orchestration',
  dyad_tool_calls: 'orchestration',
  dyad_events: 'orchestration',
  dyad_progress: 'orchestration',
  dyad_blackboard: 'orchestration',
  dyad_health: 'orchestration',

  // Jobs / subagents
  jobs_list: 'jobs',
  jobs_status: 'jobs',
  jobs_create: 'jobs',
  jobs_cancel: 'jobs',
  subagents_list: 'subagents',
  subagents_status: 'subagents',
  subagents_result: 'subagents',

  // Intelligence
  activity: 'intelligence',
  subconscious: 'intelligence',
  thinker: 'intelligence',
  consciousness: 'intelligence',
  effectiveness: 'intelligence',
  budget: 'intelligence',
  evolution: 'intelligence',
  blindspots: 'intelligence',
  snapshot: 'intelligence',
  trust: 'intelligence',
  consequences: 'intelligence',
  trace: 'intelligence',

  // Providers / config
  providers: 'providers',
  provider_metrics: 'providers',
  provider_config: 'providers',
  config_get: 'config',
  config_set: 'config',
  model_directive: 'config',

  // Blackboard
  bb_global_list: 'blackboard',
  bb_global_create: 'blackboard',
  bb_global_read: 'blackboard',
  bb_global_post: 'blackboard',
  bb_global_delete: 'blackboard',

  // Training
  training_stats: 'training',
  training_search: 'training',
  training_objects: 'training',
  training_resolve: 'training',
  training_labels: 'training',
  training_quality: 'training',
  training_annotations: 'training',
  training_ingest: 'training',
  training_tag: 'training',
  training_export: 'training',

  // Web
  webfetch: 'web',
  google_search: 'web',
  duckduckgo_search: 'web',
  duckduckgo_fetch_content: 'web',

  // Meta (self-referential)
  enrich: 'meta',
  dialectic: 'meta',

  // Consolidated cassi_* tools (action-based)
  cassi_bash: 'shell',
  cassi_read: 'fs',
  cassi_write: 'fs',
  cassi_edit: 'fs',
  cassi_file: 'fs',
  cassi_code: 'code',
  cassi_memory: 'memory',
  cassi_session: 'sessions',
  cassi_agent: 'orchestration',
  cassi_intelligence: 'intelligence',
  cassi_config: 'config',
  cassi_model: 'config',
  cassi_artifact: 'fs',
  cassi_training: 'training',
  cassi_browser: 'web',
  cassi_web: 'web',
  cassi_cortex: 'intelligence',
  cassi_self_model: 'intelligence',
  cassi_enrich: 'meta',
  cassi_vybit: 'web',
  cassi_todo_write: 'meta',
  cassi_skill_intelligence: 'meta',
  cassi_workflow: 'orchestration',

  // Question / interaction
  question: 'interaction',
  cassi_do: 'meta',
  task: 'orchestration',
  skill: 'meta',
}

/**
 * Classify a tool name into a high-level category.
 * Strips one leading `cassi_` or `mcp__*__` prefix before lookup.
 */
export function classifyTool(toolName: string): string {
  // Direct lookup first
  const direct = TOOL_CLASS_MAP[toolName]
  if (direct) return direct

  // Strip cassi_ prefix
  if (toolName.startsWith('cassi_')) {
    const stripped = toolName.slice(6)
    const found = TOOL_CLASS_MAP[stripped]
    if (found) return found
  }

  // Strip mcp__*__ prefix (e.g. mcp__cassicore__bash → bash)
  const mcpMatch = toolName.match(/^mcp__\w+__(.+)$/)
  if (mcpMatch) {
    const found = TOOL_CLASS_MAP[mcpMatch[1]]
    if (found) return found
  }

  return 'tool'
}

/**
 * Determine which slot type a message should be routed to.
 */
export function classifyMessage(
  msg: any,
  toolUseMap?: Map<string, string>,
): MessageSlotType {
  if (!msg) return 'system'

  const role = msg.role as string
  const content = msg.content

  if (role === 'system') return 'system'

  if (role === 'assistant') {
    if (Array.isArray(content) && content.some((c: any) => c?.type === 'tool_use')) {
      return 'tool_call'
    }
    return 'assistant'
  }

  if (role === 'user') {
    // AskUserQuestion answers arrive as tool_result blocks but are
    // semantically user input, so they classify as 'user'.
    // Pass toolUseMap so we can resolve tool_use_id → tool_name when
    // the block itself doesn't carry a tool_name field.
    if (hasQuestionResult(msg, { toolUseMap })) return 'user'
    if (Array.isArray(content) && content.some((c: any) => c?.type === 'tool_result')) {
      return 'tool_result'
    }
    return 'user'
  }

  return 'system'
}

/**
 * Extract tool names from tool_use blocks in a message.
 * Returns an array of { id, name } pairs.
 */
export function extractToolUses(msg: any): Array<{ id: string; name: string }> {
  if (!Array.isArray(msg?.content)) return []
  const uses: Array<{ id: string; name: string }> = []
  for (const block of msg.content) {
    if (block?.type === 'tool_use' && block.id && block.name) {
      uses.push({ id: block.id, name: block.name })
    }
  }
  return uses
}

/**
 * Extract tool_result blocks from a message.
 * Returns an array of { toolUseId, content, isError } objects.
 */
export function extractToolResults(msg: any): Array<{ toolUseId: string; content: string; isError: boolean }> {
  if (!Array.isArray(msg?.content)) return []
  const results: Array<{ toolUseId: string; content: string; isError: boolean }> = []
  for (const block of msg.content) {
    if (block?.type === 'tool_result') {
      const inner = typeof block.content === 'string'
        ? block.content
        : Array.isArray(block.content)
          ? block.content.map((b: any) => b?.text ?? '').join('\n')
          : ''
      results.push({
        toolUseId: block.tool_use_id ?? '',
        content: inner,
        isError: block.is_error === true,
      })
    }
  }
  return results
}


/**
 * Build a compact tool result status prefix from raw execution data.
 * Used by the SDK tool bridge and MCP gateway to annotate tool results
 * before they enter the conversation.
 *
 * Format: [bash · 342ms · 3.2KB · ✓]
 */
export function buildToolResultPrefix(
  toolName: string,
  durationMs: number,
  outputBytes: number,
  isError: boolean,
): string {
  const displayName = toolName || 'tool'

  let size: string
  if (outputBytes < 1_024) size = `${outputBytes}B`
  else if (outputBytes < 1_048_576) size = `${(outputBytes / 1_024).toFixed(1)}KB`
  else size = `${(outputBytes / 1_048_576).toFixed(1)}MB`

  const status = isError ? '✗' : '✓'
  return `[${displayName} · ${durationMs}ms · ${size} · ${status}]`
}
