/**
 * VENDOR RUNTIME STUB — `core/intelligence/permission-oracle/types.ts`.
 *
 * RUNTIME pure function surface consumed by executor.ts (tools):
 * `resolveToolDomain` + `TOOL_DOMAIN_MAP`. Self-contained (no external
 * imports). Owned by `@cassicore/training-trust-ledger` (P5); re-pointed there
 * when its Permission Oracle surface publishes.
 */

/**
 * Maps tool names to trust domains.
 * This determines which domain's trust score is consulted
 * when making permission decisions for a given tool.
 */
export const TOOL_DOMAIN_MAP: Record<string, string> = {
  // File operations
  'read': 'file-read',
  'read_file': 'file-read',
  'cassi_read': 'file-read',
  'serena__read_file': 'file-read',
  'grep': 'file-read',
  'glob': 'file-read',
  'write': 'file-write',
  'write_file': 'file-write',
  'cassi_write': 'file-write',
  'edit': 'file-write',
  'cassi_edit': 'file-write',
  'serena__replace_content': 'file-write',
  'serena__replace_symbol_body': 'file-write',
  'serena__insert_after_symbol': 'file-write',
  'serena__insert_before_symbol': 'file-write',
  'delete': 'file-delete',
  'cassi_delete': 'file-delete',
  // Shell
  'bash': 'shell-execution',
  'cassi_bash': 'shell-execution',
  'shell_exec': 'shell-execution',
  // Network
  'web_fetch': 'network-fetch',
  'cassi_web_fetch': 'network-fetch',
  'cassi_web_search': 'network-fetch',
  // Memory
  'memory_store': 'memory-operations',
  'memory_delete': 'memory-operations',
}

/**
 * Resolve a tool name to its trust domain.
 * Falls back to 'shell-execution' (highest risk) for unknown tools.
 */
export function resolveToolDomain(toolName: string): string {
  if (typeof toolName !== 'string' || toolName.length === 0) {
    return 'shell-execution'
  }

  // Direct match
  if (TOOL_DOMAIN_MAP[toolName]) return TOOL_DOMAIN_MAP[toolName]

  // Strip MCP server prefix (e.g., 'serena__find_file' → 'find_file')
  if (toolName.includes('__')) {
    const baseName = toolName.split('__').pop()!
    if (TOOL_DOMAIN_MAP[baseName]) return TOOL_DOMAIN_MAP[baseName]
  }

  // Heuristic: classify by name patterns
  if (toolName.includes('read') || toolName.includes('search') || toolName.includes('find') || toolName.includes('list') || toolName.includes('get')) {
    return 'file-read'
  }
  if (toolName.includes('write') || toolName.includes('edit') || toolName.includes('replace') || toolName.includes('insert') || toolName.includes('create')) {
    return 'file-write'
  }
  if (toolName.includes('delete') || toolName.includes('remove')) {
    return 'file-delete'
  }
  if (toolName.includes('fetch') || toolName.includes('web') || toolName.includes('http') || toolName.includes('url')) {
    return 'network-fetch'
  }
  if (toolName.includes('git') || toolName.includes('commit') || toolName.includes('push') || toolName.includes('branch')) {
    return 'git-operations'
  }
  if (toolName.includes('bash') || toolName.includes('shell') || toolName.includes('exec')) {
    return 'shell-execution'
  }

  // Unknown tool → treat as shell execution (high baseline risk)
  return 'shell-execution'
}
