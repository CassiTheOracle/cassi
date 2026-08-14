import type { MessageSlotType } from './types.js'
import { hasQuestionResult } from '@cassicore/pipeline'

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

  // -- Hermes-native tool names (context engine integration) ----------
  // Shell
  terminal: 'shell',
  execute_code: 'shell',
  process: 'shell',

  // Filesystem
  read_file: 'fs',
  write_file: 'fs',
  patch: 'fs',
  search_files: 'fs',

  // Web / browser
  web_search: 'web',
  web_extract: 'web',
  browser_navigate: 'web',
  browser_click: 'web',
  browser_snapshot: 'web',
  browser_type: 'web',
  browser_scroll: 'web',
  browser_vision: 'web',
  browser_back: 'web',
  browser_press: 'web',
  browser_console: 'web',
  browser_get_images: 'web',
  vision_analyze: 'web',
  video_analyze: 'web',
  send_message: 'web',

  // Memory / archive
  memory: 'memory',
  session_search: 'sessions',
  skill_view: 'meta',
  skill_manage: 'meta',
  skills_list: 'meta',

  // Orchestration
  delegate_task: 'orchestration',
  cronjob: 'orchestration',

  // Interaction
  clarify: 'interaction',
  text_to_speech: 'meta',
  todo: 'meta',

  // Hermes MCP bridge tools (mcp__cassicore__hermes_*)
  hermes_sessions_list: 'sessions',
  hermes_session_get: 'sessions',
  hermes_session_search: 'sessions',
  hermes_session_prune: 'sessions',
  hermes_session_resume: 'sessions',
  hermes_session_active: 'sessions',
  hermes_context_curate: 'meta',
  hermes_context_health: 'meta',
  hermes_context_map: 'meta',
  hermes_context_why: 'meta',
  hermes_context_pin: 'meta',
  hermes_context_recall: 'meta',
  hermes_cognitive_enrich: 'meta',
  hermes_memory_retrieve: 'memory',
  hermes_memory_store: 'memory',
  hermes_memory_graph: 'memory',
  hermes_self_model: 'intelligence',
  hermes_constellation_start: 'orchestration',
  hermes_constellation_watch: 'orchestration',
  hermes_constellation_steer: 'orchestration',
  hermes_helix_start: 'orchestration',
  hermes_helix_watch: 'orchestration',
  hermes_model_tier: 'config',
  hermes_model_tiers: 'config',
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

/* ------------------------------------------------------------------ */
/*  Shared tool-metadata helpers                                       */
/* ------------------------------------------------------------------ */

/** Whether a tool name represents a write/edit operation. */
export function isWriteTool(toolName: string): boolean {
  return /^(write|edit|write_file|patch|cassi_write|cassi_edit|serena_replace_content|serena_replace_symbol_body|serena_insert_after_symbol|serena_insert_before_symbol|mcp__\w+__(write|edit))$/i.test(toolName)
}

/** Whether a tool name represents a read/search operation. */
export function isReadTool(toolName: string): boolean {
  return /^(read|glob|grep|read_file|search_files|cassi_read|cassi_file|cassi_glob|serena_find_file|serena_search_for_pattern|serena_get_symbols_overview|serena_find_symbol|serena_find_referencing_symbols|mcp__\w+__(read|glob|grep))$/i.test(toolName)
}

/** Whether a tool name is a shell/command execution tool. */
export function isShellTool(toolName: string): boolean {
  return /^(bash|terminal|execute_code|process|cassi_bash|shell)$/i.test(toolName)
}

/** Whether a tool name is a search/grep/find operation. */
export function isSearchTool(toolName: string): boolean {
  return /^(grep|search_files|web_search|web_extract|search|find|glob|duckduckgo_search|duckduckgo_fetch_content|google_search|cassi_search|serena_search_for_pattern|serena_find_symbol|serena_find_file|serena_find_referencing_symbols)$/i.test(toolName)
}

/** Extract the command string from a shell tool's input for classification. */
export function extractCommand(input: Record<string, unknown>): string {
  const cmd = input.command ?? input.cmd ?? input.args ?? input.script ?? ''
  if (typeof cmd === 'string') return cmd
  if (Array.isArray(cmd)) return (cmd as unknown[]).map(String).join(' ')
  return String(cmd)
}

/** Whether a shell command invokes a test runner (cargo test, pytest, jest, etc.). */
export function isTestCommand(command: string): boolean {
  return TEST_COMMAND_RE.test(command) || TEST_COMMAND_PATTERNS.some(r => r.test(command))
}

const TEST_COMMAND_RE = /\b(?:test|pytest|tox|nox|unittest|jest|vitest|mocha|ava|uvu|jasmine|karma|busted|rspec|minitest|ctest|phpunit)\b/i

const TEST_COMMAND_PATTERNS: RegExp[] = [
  // Python
  /\bnose2?\b/i, /\bcoverage\s+run\b/i, /\bpython\s+(?:-m\s+)?(?:pytest|unittest|nose)\b/i,
  /\bpoetry\s+run\s+pytest\b/i, /\bpipenv\s+run\s+pytest\b/i, /\bhatch\s+test\b/i,
  // JS/TS
  /\bweb-test-runner\b/i, /\bnpx\s+(?:jest|vitest|mocha|ava|playwright|cypress|tap|uvu|jasmine|karma|web-test-runner)\b/i,
  /\bnpm\s+test\b/i, /\byarn\s+test\b/i, /\bpnpm\s+test\b/i, /\bbun\s+test\b/i, /\bdeno\s+test\b/i,
  // Go / Rust / Elixir / Haskell / .NET / Scala / Java / Dart / Swift / Zig / PHP / Ruby / C
  /\bgo\s+test\b/i, /\bcargo\s+(?:test|nextest)\b/i, /\bmix\s+test\b/i,
  /\bstack\s+test\b/i, /\bcabal\s+test\b/i, /\bdotnet\s+test\b/i, /\bsbt\s+test\b/i,
  /\bmvn\s+test\b/i, /\bgradle\w*\s+test\b/i, /\bant\s+test\b/i,
  /\bflutter\s+test\b/i, /\bdart\s+test\b/i,
  /\bswift\s+test\b/i, /\bxcodebuild\s+test\b/i, /\bzig\s+build\s+test\b/i,
  /\bcomposer\s+test\b/i, /\bvendor\/bin\/phpunit\b/i,
  /\brake\s+test\b/i, /\brails\s+test\b/i,
  /\bmeson\s+test\b/i, /\bbazel\s+test\b/i,
  // Make / shell scripts
  /\bmake\s+test\b/i, /\bmake\s+check\b/i,
  /\.\/test\.sh\b/i, /\.\/run_tests?\.sh\b/i,
  // The bare word (cheap enough to always run, catches most)
  /\btest\b/i,
]

/** Whether a shell command invokes a build/compile tool. */
export function isBuildCommand(command: string): boolean {
  return BUILD_COMMAND_RE.test(command) || BUILD_COMMAND_PATTERNS.some(r => r.test(command))
}

const BUILD_COMMAND_RE = /\b(?:build|compile|gcc|g\+\+|clang|clang\+\+|rustc|make|cmake|tsc|webpack|esbuild|ncc|rollup|swc|ninja|javac|protoc)\b/i

const BUILD_COMMAND_PATTERNS: RegExp[] = [
  // C/C++
  /\bxcodebuild\b/i, /\bmsbuild\b/i, /\bmeson\b/i, /\bbazel\s+build\b/i, /\b\.\/configure\b/i,
  // Go
  /\bgo\s+build\b/i, /\bgo\s+install\b/i,
  // Rust
  /\bcargo\s+build\b/i, /\bwasm-pack\s+build\b/i,
  // JS/TS
  /\bnpm\s+run\s+build\b/i, /\byarn\s+build\b/i, /\bpnpm\s+build\b/i, /\bbun\s+build\b/i,
  /\bnpx\s+(?:tsc|webpack|esbuild|rollup|swc|ncc|parcel|rspack)\b/i,
  /\bvite\s+build\b/i, /\bdeno\s+compile\b/i, /\bturbo\s+run\s+build\b/i,
  /\bnx\s+build\b/i, /\blerna\s+run\s+build\b/i, /\bparcel\s+build\b/i, /\brspack\b/i,
  // Java / Scala
  /\bmvn\s+(?:compile|package|install|build)\b/i, /\bgradle\w*\s+build\b/i, /\bant\s+(?:compile|build)\b/i,
  /\bsbt\s+(?:compile|assembly|package)\b/i,
  // Python
  /\bpoetry\s+build\b/i, /\bpip\s+install\b/i, /\bpip3\s+install\b/i,
  /\bmaturin\s+build\b/i, /\bhatch\s+build\b/i, /\bpdm\s+build\b/i,
  /\bpython\s+(?:setup\.py|-\s*m\s+build)\b/i,
  // Ruby
  /\bgem\s+build\b/i, /\brake\s+build\b/i, /\bbundle\s+exec\s+rake\b/i,
  // Elixir / Haskell / Zig / .NET / Swift / Dart
  /\bmix\s+compile\b/i, /\bstack\s+build\b/i, /\bcabal\s+build\b/i, /\bzig\s+build\b/i,
  /\bdotnet\s+(?:build|publish)\b/i, /\bswift\s+build\b/i, /\bdart\s+compile\b/i,
  // Docker / containers
  /\bdocker\s+build\b/i, /\bpodman\s+build\b/i, /\bdocker-compose\s+build\b/i,
  // Protobuf / gRPC
  /\bbuf\s+generate\b/i,
  // Generic
  /\bnpm\s+install\b/i, /\byarn\s+install\b/i, /\bpnpm\s+install\b/i, /\bbun\s+install\b/i,
  /\bcargo\s+install\b/i, /\bgo\s+get\b/i,
  /\bmeson\s+setup\b/i, /\bcmake\b/i,
  // The bare word
  /\bbuild\b/i, /\bcompile\b/i, /\bmake\b/i,
]

/**
 * Extract the primary file path from a tool input object.
 * Tries common parameter names across tool schemas.
 */
export function extractFilePath(input: Record<string, unknown>): string {
  const fp = input.filePath ?? input.path ?? input.file_path ?? input.relative_path ?? ''
  return typeof fp === 'string' ? fp : ''
}

/**
 * Extract the primary search target from a tool input object.
 * Returns the search pattern, query, or command depending on tool class.
 */
export function extractSearchTarget(input: Record<string, unknown>): string {
  const pattern = input.pattern ?? input.substring_pattern ?? input.query ?? input.search ?? ''
  return typeof pattern === 'string' ? pattern : ''
}

/** Shorten a file path to its last 2 components for compact display. */
export function shortenPath(fp: string): string {
  const parts = fp.split('/')
  if (parts.length > 2) return parts.slice(-2).join('/')
  return fp
}

/**
 * Detect the programming/markup language for a file path based on its extension.
 */
export function detectLanguage(filePath: string): string {
  if (filePath.endsWith('.ts') || filePath.endsWith('.tsx')) return 'typescript'
  if (filePath.endsWith('.js') || filePath.endsWith('.jsx')) return 'javascript'
  if (filePath.endsWith('.json')) return 'json'
  if (filePath.endsWith('.md') || filePath.endsWith('.mdx')) return 'markdown'
  if (filePath.endsWith('.py')) return 'python'
  if (filePath.endsWith('.rs')) return 'rust'
  if (filePath.endsWith('.go')) return 'go'
  if (filePath.endsWith('.css')) return 'css'
  if (filePath.endsWith('.html')) return 'html'
  if (filePath.endsWith('.yaml') || filePath.endsWith('.yml')) return 'yaml'
  if (filePath.endsWith('.sh') || filePath.endsWith('.bash')) return 'shell'
  if (filePath.endsWith('.sql')) return 'sql'
  return 'unknown'
}

