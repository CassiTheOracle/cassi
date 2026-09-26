/**
 * Hermes Tool Definitions & Registration
 *
 * Registers Hermes-compatible tool schemas in CassiCore's tool registry.
 * Tool handlers delegate to the Hermes ACP server via MCP over stdio
 * (replaces the old Python bridge subprocess).
 */
import type { ToolDefinition } from './types.js'
import { getHermesMcpClient } from './hermes-mcp-client.js'

/**
 * Create a tool handler that delegates to the Hermes MCP client.
 * The MCP client auto-connects on first call if not already connected.
 */
function createHermesToolHandler(toolName: string) {
  return async (input: Record<string, unknown>): Promise<string> => {
    const client = getHermesMcpClient()
    return client.callTool(toolName, input)
  }
}


const terminalDefinition: ToolDefinition = {
  name: 'terminal',
  description: 'Execute shell commands with timeout, working directory, and background support.',
  parameters: {
    type: 'object',
    properties: {
      command: { type: 'string', description: 'The shell command to execute' },
      timeout: { type: 'number', description: 'Max seconds to wait (default: 180)' },
      workdir: { type: 'string', description: 'Working directory for the command' },
      background: { type: 'boolean', description: 'Run in background and return session ID' },
      pty: { type: 'boolean', description: 'Use pseudo-terminal for interactive commands' },
      notify_on_complete: { type: 'boolean', description: 'Auto-notify when background task finishes' },
    },
    required: ['command'],
  },
  timeoutMs: 300_000,
  readOnly: false,
  category: 'core',
  requiredPermission: 'full-access',
}


const readFileDefinition: ToolDefinition = {
  name: 'read_file',
  description: 'Read a text file with line numbers and pagination. Use offset and limit for large files.',
  parameters: {
    type: 'object',
    properties: {
      path: { type: 'string', description: 'Path to the file (absolute or relative)' },
      offset: { type: 'number', description: 'Line number to start reading from (1-indexed, default: 1)' },
      limit: { type: 'number', description: 'Maximum number of lines to read (default: 500)' },
    },
    required: ['path'],
  },
  timeoutMs: 15_000,
  readOnly: true,
  category: 'core',
  requiredPermission: 'read-only',
}

const writeFileDefinition: ToolDefinition = {
  name: 'write_file',
  description: 'Write content to a file. Creates parent directories automatically. Overwrites existing files.',
  parameters: {
    type: 'object',
    properties: {
      path: { type: 'string', description: 'Path to the file to write' },
      content: { type: 'string', description: 'Complete content to write to the file' },
    },
    required: ['path', 'content'],
  },
  timeoutMs: 15_000,
  readOnly: false,
  category: 'core',
  requiredPermission: 'workspace-write',
}

const patchDefinition: ToolDefinition = {
  name: 'patch',
  description: 'Targeted find-and-replace edits in files. Uses fuzzy matching so minor whitespace/indentation differences won\'t break it. Returns a unified diff on success.',
  parameters: {
    type: 'object',
    properties: {
      mode: { type: 'string', enum: ['replace', 'patch'], description: 'Edit mode: replace (default) or patch (V4A multi-file patches)', default: 'replace' },
      path: { type: 'string', description: 'File path to edit (required for mode=replace)' },
      old_string: { type: 'string', description: 'Exact text to find and replace (required for mode=replace)' },
      new_string: { type: 'string', description: 'Replacement text (required for mode=replace). Empty string deletes the matched text.' },
      replace_all: { type: 'boolean', description: 'Replace all occurrences instead of requiring unique match (default: false)' },
      patch: { type: 'string', description: 'V4A format patch content (required for mode=patch)' },
    },
    required: ['mode'],
  },
  timeoutMs: 30_000,
  readOnly: false,
  category: 'core',
  requiredPermission: 'workspace-write',
}

const searchFilesDefinition: ToolDefinition = {
  name: 'search_files',
  description: 'Search file contents (ripgrep) or find files by name. Content search supports regex. File search supports glob patterns.',
  parameters: {
    type: 'object',
    properties: {
      pattern: { type: 'string', description: 'Regex pattern (content search) or glob pattern (file search)' },
      target: { type: 'string', enum: ['content', 'files'], description: '"content" searches inside files, "files" finds files by name', default: 'content' },
      path: { type: 'string', description: 'Directory to search in (default: current directory)' },
      file_glob: { type: 'string', description: 'Filter by file pattern in grep mode (e.g., "*.py")' },
      limit: { type: 'number', description: 'Maximum results (default: 50)' },
      offset: { type: 'number', description: 'Skip first N results (default: 0)' },
      output_mode: { type: 'string', enum: ['content', 'files_only', 'count'], description: 'Output format: content (lines), files_only (paths), count (per-file match counts)' },
      context: { type: 'number', description: 'Context lines before and after each match' },
    },
    required: ['pattern'],
  },
  timeoutMs: 30_000,
  readOnly: true,
  category: 'core',
  requiredPermission: 'read-only',
}


const webSearchDefinition: ToolDefinition = {
  name: 'web_search',
  description: 'Search the web for information. Returns up to 5 results with titles, URLs, and descriptions.',
  parameters: {
    type: 'object',
    properties: {
      query: { type: 'string', description: 'The search query' },
      limit: { type: 'number', description: 'Maximum number of results (default: 5)' },
    },
    required: ['query'],
  },
  timeoutMs: 30_000,
  readOnly: true,
  category: 'core',
  requiredPermission: 'read-only',
}

const webExtractDefinition: ToolDefinition = {
  name: 'web_extract',
  description: 'Extract content from web page URLs. Returns page content as markdown. Supports PDF URLs.',
  parameters: {
    type: 'object',
    properties: {
      urls: { type: 'array', items: { type: 'string' }, description: 'List of URLs to extract (max 5)' },
    },
    required: ['urls'],
  },
  timeoutMs: 30_000,
  readOnly: true,
  category: 'core',
  requiredPermission: 'read-only',
}


const todoDefinition: ToolDefinition = {
  name: 'todo',
  description: 'Manage your task list for the current session. Use for complex tasks with 3+ steps or when tracking multiple items.',
  parameters: {
    type: 'object',
    properties: {
      todos: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            id: { type: 'string', description: 'Unique item identifier' },
            content: { type: 'string', description: 'Task description' },
            status: { type: 'string', enum: ['pending', 'in_progress', 'completed', 'cancelled'], description: 'Current status' },
          },
          required: ['id', 'content', 'status'],
        },
        description: 'Task items to write or update',
      },
      merge: { type: 'boolean', description: 'True: update existing items by id. False: replace the entire list.', default: false },
    },
  },
  timeoutMs: 10_000,
  readOnly: false,
  category: 'core',
  requiredPermission: 'workspace-write',
}


function createBrowserDefinition(action: string, desc: string, params: Record<string, any>, required: string[] = []): ToolDefinition {
  const isWrite = ['navigate', 'click', 'type', 'press', 'back'].includes(action)
  return {
    name: `browser_${action}`,
    description: desc,
    parameters: { type: 'object', properties: params, required },
    timeoutMs: 60_000,
    readOnly: !isWrite,
    category: 'core',
    requiredPermission: isWrite ? 'workspace-write' as const : 'read-only' as const,
  }
}

const browserNavigateDef = createBrowserDefinition(
  'navigate',
  'Navigate to a URL in the browser. Initializes the session and loads the page.',
  { url: { type: 'string', description: 'The URL to navigate to' } },
  ['url'],
)

const browserClickDef = createBrowserDefinition(
  'click',
  'Click on an element identified by its ref ID from the snapshot.',
  { ref: { type: 'string', description: 'The element reference from the snapshot (e.g., "@e5")' } },
  ['ref'],
)

const browserSnapshotDef = createBrowserDefinition(
  'snapshot',
  'Get a text-based snapshot of the current page. Returns interactive elements with ref IDs.',
  { full: { type: 'boolean', description: 'Return complete page content if true, compact interactive view if false' } },
)

const browserScrollDef = createBrowserDefinition(
  'scroll',
  'Scroll the page up or down.',
  { direction: { type: 'string', enum: ['up', 'down'], description: 'Direction to scroll' } },
  ['direction'],
)

const browserTypeDef = createBrowserDefinition(
  'type',
  'Type text into an input field identified by its ref ID.',
  { ref: { type: 'string', description: 'The element reference from the snapshot' }, text: { type: 'string', description: 'The text to type' } },
  ['ref', 'text'],
)

const browserPressDef = createBrowserDefinition(
  'press',
  'Press a keyboard key (Enter, Tab, Escape, ArrowDown, etc.).',
  { key: { type: 'string', description: 'Key to press' } },
  ['key'],
)

const browserConsoleDef = createBrowserDefinition(
  'console',
  'Get browser console output (console.log/warn/error/info messages and uncaught JS exceptions).',
  { clear: { type: 'boolean', description: 'Clear message buffers after reading' } },
)

const browserVisionDef = createBrowserDefinition(
  'vision',
  'Take a screenshot of the current page and analyze it with vision. Returns both analysis and screenshot path.',
  { question: { type: 'string', description: 'What to look for visually' }, annotate: { type: 'boolean', description: 'Overlay numbered labels on interactive elements' } },
  ['question'],
)

const browserGetImagesDef = createBrowserDefinition(
  'get_images',
  'Get a list of all images on the current page with their URLs and alt text.',
  {},
)

const browserBackDef = createBrowserDefinition(
  'back',
  'Navigate back to the previous page in browser history.',
  {},
)


const memoryDefinition: ToolDefinition = {
  name: 'memory',
  description: 'Save durable information to persistent memory that survives across sessions.',
  parameters: {
    type: 'object',
    properties: {
      action: { type: 'string', enum: ['add', 'replace', 'remove'], description: 'The action to perform.' },
      target: { type: 'string', enum: ['memory', 'user'], description: "Which memory store: 'memory' for personal notes, 'user' for user profile." },
      content: { type: 'string', description: "The entry content. Required for 'add' and 'replace'." },
      old_text: { type: 'string', description: 'Short unique substring identifying the entry to replace or remove.' },
    },
    required: ['action', 'target'],
  },
  timeoutMs: 10_000,
  readOnly: false,
  category: 'core',
  requiredPermission: 'workspace-write',
}


const sessionSearchDefinition: ToolDefinition = {
  name: 'session_search',
  description: 'Search your long-term memory of past conversations across all sessions.',
  parameters: {
    type: 'object',
    properties: {
      query: { type: 'string', description: 'Search query — keywords, phrases, or boolean expressions.' },
      role_filter: { type: 'string', description: 'Optional: only search messages from specific roles.' },
      limit: { type: 'number', description: 'Max sessions to summarize (default: 3, max: 5).' },
    },
  },
  timeoutMs: 15_000,
  readOnly: true,
  category: 'core',
  requiredPermission: 'read-only',
}


const delegateTaskDefinition: ToolDefinition = {
  name: 'delegate_task',
  description: 'Spawn one or more subagents to work on tasks in isolated contexts. Each subagent gets its own conversation, terminal session, and toolset. Use for reasoning-heavy subtasks that would flood your context.',
  parameters: {
    type: 'object',
    properties: {
      goal: { type: 'string', description: 'What the subagent should accomplish. Be specific and self-contained.' },
      context: { type: 'string', description: 'Background information the subagent needs: file paths, error messages, project structure, constraints.' },
      toolsets: { type: 'array', items: { type: 'string' }, description: 'Toolsets to enable. Common: [\'terminal\',\'file\'] for code work, [\'web\'] for research.' },
      tasks: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            goal: { type: 'string', description: 'Task goal' },
            context: { type: 'string', description: 'Task-specific context' },
            toolsets: { type: 'array', items: { type: 'string' }, description: 'Toolsets for this specific task' },
          },
          required: ['goal'],
        },
        description: 'Batch mode: tasks to run in parallel (up to 3)',
      },
      role: { type: 'string', enum: ['leaf', 'orchestrator'], description: 'Role: leaf (default) or orchestrator.' },
    },
  },
  timeoutMs: 600_000,
  readOnly: false,
  category: 'core',
  requiredPermission: 'full-access',
}


export const HERMES_TOOL_DEFINITIONS: ToolDefinition[] = [
  terminalDefinition,
  readFileDefinition,
  writeFileDefinition,
  patchDefinition,
  searchFilesDefinition,
  webSearchDefinition,
  webExtractDefinition,
  todoDefinition,
  browserNavigateDef,
  browserClickDef,
  browserSnapshotDef,
  browserScrollDef,
  browserTypeDef,
  browserPressDef,
  browserConsoleDef,
  browserVisionDef,
  browserGetImagesDef,
  browserBackDef,
  memoryDefinition,
  sessionSearchDefinition,
  delegateTaskDefinition,
]

export type HermesToolName = (typeof HERMES_TOOL_DEFINITIONS)[number]['name']

/**
 * Register all Hermes tools into a CassiCore ToolRegistry.
 * Starts the Hermes MCP client (async, fire-and-forget) so
 * tool calls work when the client is ready.
 */
export function registerHermesTools(registry: { register: (def: ToolDefinition, handler: any) => void }): void {
  for (const def of HERMES_TOOL_DEFINITIONS) {
    const handler = createHermesToolHandler(def.name)
    registry.register(def, handler)
  }

  // Start the MCP client — fire-and-forget, tools will work once connected
  getHermesMcpClient().start().catch((err: Error) => {
    // Logged by the client internally
  })
}
