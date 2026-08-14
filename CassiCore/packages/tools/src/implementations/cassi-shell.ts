/**
 * cassi — Unified shell interface for Cassi.
 *
 * Provides a single entry point for:
 * - Help/discovery: `cassi` or `cassi help [topic]`
 * - Bash commands: `cassi ls`, `cassi cat foo.ts`, `cassi grep -r "pattern" src/`
 * - Cassi tools: `cassi memory.store key=x value=y`
 *
 * Minimal context footprint — only this tool schema is needed.
 * Full tool docs are loaded on-demand via `cassi help <tool>`.
 */

import type { ToolDefinition, ToolHandler, ToolExecutionContext } from '../types.js'
import type { ToolRegistry } from '../registry.js'
import { spawn } from 'node:child_process'

export const cassiShellDefinition: ToolDefinition = {
  name: 'cassi',
  description: `Unified shell for Cassi. Usage:
  cassi              → Show help (tool categories)
  cassi help [topic] → Help for a category or tool
  cassi ls [-la] [path]   → List files (bash ls)
  cassi cat <file>        → Show file contents
  cassi grep <pattern> [path] → Search files
  cassi <any bash cmd>    → Execute bash command
  cassi <tool.name> [args] → Execute Cassi tool (e.g. memory.store key=x)`,
  parameters: {
    type: 'object',
    properties: {
      cmd: {
        type: 'string',
        description: 'Command to execute. Empty or "help" shows help.',
      },
    },
    required: [],
  },
  category: 'core',
  timeoutMs: 120_000,
  requiredPermission: 'full-access',
}

// Bash commands that pass through directly
const BASH_COMMANDS = new Set([
  'ls', 'cat', 'head', 'tail', 'grep', 'find', 'wc', 'pwd', 'cd',
  'echo', 'mkdir', 'rm', 'cp', 'mv', 'touch', 'chmod', 'which',
  'git', 'npm', 'npx', 'node', 'python', 'python3', 'pip',
  'curl', 'wget', 'tar', 'zip', 'unzip', 'diff', 'sort', 'uniq',
  'awk', 'sed', 'cut', 'tr', 'xargs', 'tree', 'df', 'du', 'ps',
  'kill', 'pkill', 'top', 'htop', 'env', 'export', 'source',
])

interface CassiShellDeps {
  toolRegistry: ToolRegistry
  executeToolByName: (name: string, input: Record<string, unknown>, ctx: ToolExecutionContext) => Promise<string>
  workdir: string
  logger: { debug: (msg: string, meta?: Record<string, unknown>) => void }
}

let _deps: CassiShellDeps | undefined

/**
 * @dep callers: registerCoreTools (core/tools/implementations/index.ts)
 * @dep flows: BootPipelineTools → SetCassiShellDeps (4/4)
 * @dep module: Unknown
 * @dep risk: LOW | 1 caller, 1 flow, 1 module
 */

export function setCassiShellDeps(deps: CassiShellDeps): void {
  _deps = deps
}

/**
 * Execute a bash command and return output.
 */
async function execBash(command: string, workdir: string, timeoutMs = 30_000): Promise<string> {
  return new Promise((resolve) => {
    let stdout = ''
    let stderr = ''

    const proc = spawn('bash', ['-c', command], { cwd: workdir })
    const timer = setTimeout(() => {
      proc.kill()
      resolve(`[timeout after ${timeoutMs}ms]\n${stdout}${stderr}`)
    }, timeoutMs)

    proc.stdout.on('data', (d: Buffer) => { stdout += d.toString() })
    proc.stderr.on('data', (d: Buffer) => { stderr += d.toString() })

    proc.on('close', (code) => {
      clearTimeout(timer)
      const output = stdout + (stderr ? `\n[stderr] ${stderr}` : '')
      if (code !== 0 && code !== null) {
        resolve(`[exit ${code}]\n${output}`)
      } else {
        resolve(output || '(no output)')
      }
    })

    proc.on('error', (err) => {
      clearTimeout(timer)
      resolve(`[error] ${err.message}`)
    })
  })
}

/**
 * Generate help text for the cassi shell.
 */
function generateHelp(topic: string | undefined, registry: ToolRegistry): string {
  if (!topic || topic === 'help') {
    // Root help — show categories and basic usage
    const tools = registry.list()
    const categories = new Map<string, string[]>()

    for (const t of tools) {
      const cat = t.category ?? 'core'
      if (!categories.has(cat)) categories.set(cat, [])
      categories.get(cat)!.push(t.name)
    }

    const lines = [
      '# cassi — Unified Shell',
      '',
      '## Usage',
      '  cassi                    Show this help',
      '  cassi help <topic>       Help for category or tool',
      '  cassi <bash-cmd> [args]  Run bash command (ls, cat, grep, git, etc.)',
      '  cassi <tool> [k=v ...]   Run Cassi tool',
      '',
      '## Tool Categories',
    ]

    for (const [cat, names] of categories) {
      lines.push(`  ${cat.padEnd(12)} ${names.length} tools — cassi help ${cat}`)
    }

    lines.push('')
    lines.push('## Examples')
    lines.push('  cassi ls -la src/')
    lines.push('  cassi grep -r "TODO" .')
    lines.push('  cassi git status')
    lines.push('  cassi memory.store key=project value="CassiCore"')
    lines.push('  cassi help memory')

    return lines.join('\n')
  }

  // Check if topic is a category
  const tools = registry.list()
  const inCategory = tools.filter(t => (t.category ?? 'core') === topic)
  if (inCategory.length > 0) {
    const lines = [`# Category: ${topic}`, '']
    for (const t of inCategory) {
      const desc = t.description.split('\n')[0].slice(0, 60)
      lines.push(`  ${t.name.padEnd(28)} ${desc}`)
    }
    lines.push('')
    lines.push(`Use: cassi help <tool-name> for full documentation`)
    return lines.join('\n')
  }

  // Check if topic is a specific tool
  const tool = registry.getDefinition(topic)
  if (tool) {
    const lines = [
      `# ${tool.name}`,
      '',
      tool.description,
      '',
      '## Parameters',
    ]
    const params = (tool.parameters as { properties?: Record<string, { type?: string; description?: string }> })?.properties ?? {}
    for (const [name, schema] of Object.entries(params)) {
      lines.push(`  ${name}: ${schema.type ?? 'any'} — ${schema.description ?? ''}`)
    }
    const required = (tool.parameters as { required?: string[] })?.required ?? []
    if (required.length > 0) {
      lines.push('')
      lines.push(`Required: ${required.join(', ')}`)
    }
    return lines.join('\n')
  }

  return `Unknown topic: ${topic}\n\nUse 'cassi help' to see available categories.`
}

/**
 * Parse key=value arguments into an object.
 */
function parseArgs(args: string[]): Record<string, unknown> {
  const result: Record<string, unknown> = {}
  for (const arg of args) {
    const eq = arg.indexOf('=')
    if (eq > 0) {
      const key = arg.slice(0, eq)
      let value: unknown = arg.slice(eq + 1)
      // Try to parse as JSON for complex values
      if (typeof value === 'string') {
        if (value === 'true') value = true
        else if (value === 'false') value = false
        else if (/^-?\d+$/.test(value)) value = parseInt(value, 10)
        else if (/^-?\d*\.\d+$/.test(value)) value = parseFloat(value)
        else if ((value.startsWith('{') && value.endsWith('}')) ||
                 (value.startsWith('[') && value.endsWith(']'))) {
          try { value = JSON.parse(value) } catch { /* keep as string */ }
        }
      }
      result[key] = value
    }
  }
  return result
}

export const cassiShellHandler: ToolHandler = async (input, ctx) => {
  const cmd = ((input.cmd as string) ?? '').trim()

  if (!_deps) {
    return 'cassi shell not initialized — deps not set'
  }

  const { toolRegistry, executeToolByName, workdir, logger } = _deps

  // Empty command or "help" → show help
  if (!cmd || cmd === 'help') {
    return generateHelp(undefined, toolRegistry)
  }

  // Parse command
  const parts = cmd.split(/\s+/)
  const firstWord = parts[0]
  const rest = parts.slice(1)

  // "help <topic>" → show topic help
  if (firstWord === 'help' && rest.length > 0) {
    return generateHelp(rest.join(' '), toolRegistry)
  }

  // Check if it's a bash command
  if (BASH_COMMANDS.has(firstWord)) {
    logger.debug('cassi: executing bash command', { cmd })
    return execBash(cmd, workdir)
  }

  // Check if it looks like a Cassi tool (contains a dot or matches a registered tool)
  const toolDef = toolRegistry.getDefinition(firstWord)
  if (toolDef || firstWord.includes('.')) {
    const toolName = firstWord
    const args = parseArgs(rest)
    logger.debug('cassi: executing tool', { tool: toolName, args })

    try {
      const result = await executeToolByName(toolName, args, ctx)
      return result
    } catch (err) {
      return `[error] Tool '${toolName}' failed: ${err instanceof Error ? err.message : String(err)}`
    }
  }

  // Default: try as bash command (for commands not in BASH_COMMANDS set)
  logger.debug('cassi: falling back to bash', { cmd })
  return execBash(cmd, workdir)
}

/**
 * History tracking (optional enhancement — stores last N commands).
 */
const commandHistory: string[] = []
const MAX_HISTORY = 50

export function recordCommand(cmd: string): void {
  commandHistory.push(cmd)
  if (commandHistory.length > MAX_HISTORY) {
    commandHistory.shift()
  }
}

export function getHistory(n = 10): string[] {
  return commandHistory.slice(-n)
}
