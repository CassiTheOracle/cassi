import { readFileSync, existsSync } from 'node:fs'
import { resolve } from 'node:path'
import type { ToolDefinition, ToolHandler, ToolExecutionContext } from '../types.js'

export const readFileDefinition: ToolDefinition = {
  name: 'read_file',
  description: 'Read the contents of a file. Supports optional line offset and limit.',
  parameters: {
    type: 'object',
    properties: {
      path:   { type: 'string', description: 'Path to the file (absolute or relative to workspace)' },
      offset: { type: 'number', description: 'Line number to start reading from (1-indexed, optional)' },
      limit:  { type: 'number', description: 'Maximum number of lines to read (optional)' },
    },
    required: ['path'],
  },
  timeoutMs: 10_000,
}

const MAX_BYTES = 1024 * 1024  // 1MB

export const readFileHandler: ToolHandler = async (input, ctx: ToolExecutionContext) => {
  const rawPath = input['path'] as string
  const offset  = (input['offset'] as number | undefined) ?? 1
  const limit   = input['limit'] as number | undefined

  // Resolve path
  const absPath = rawPath.startsWith('/') ? rawPath : resolve(ctx.workingDir, rawPath)
  const realPath = absPath  // TODO: symlink resolve if needed

  // Security: must be under an allowed path
  const allowed = ctx.allowedPaths.some(p => realPath.startsWith(p))
  if (!allowed) {
    return `Error: access denied — ${realPath} is outside allowed paths`
  }

  if (!existsSync(realPath)) {
    return `Error: file not found — ${realPath}`
  }

  let content: string
  try {
    const raw = readFileSync(realPath)
    if (raw.length > MAX_BYTES) {
      content = raw.slice(0, MAX_BYTES).toString('utf8') + '\n[file truncated at 1MB]'
    } else {
      content = raw.toString('utf8')
    }
  } catch (err) {
    return `Error reading file: ${String(err)}`
  }

  // Apply offset / limit
  if (offset > 1 || limit !== undefined) {
    const lines = content.split('\n')
    const start  = Math.max(0, offset - 1)
    const end    = limit !== undefined ? start + limit : lines.length
    content = lines.slice(start, end).join('\n')
  }

  return content
}
