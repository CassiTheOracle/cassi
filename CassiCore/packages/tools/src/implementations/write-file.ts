import { writeFileSync, mkdirSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import type { ToolDefinition, ToolHandler, ToolExecutionContext } from '../types.js'

export const writeFileDefinition: ToolDefinition = {
  name: 'write_file',
  description: 'Write content to a file. Creates parent directories automatically. Overwrites existing files.',
  parameters: {
    type: 'object',
    properties: {
      path:    { type: 'string', description: 'Destination path (absolute or relative to workspace)' },
      content: { type: 'string', description: 'Content to write' },
    },
    required: ['path', 'content'],
  },
  timeoutMs: 10_000,
}

export const writeFileHandler: ToolHandler = async (input, ctx: ToolExecutionContext) => {
  const rawPath = input['path'] as string
  const content = input['content'] as string

  const absPath = rawPath.startsWith('/') ? rawPath : resolve(ctx.workingDir, rawPath)

  // Security: must be under an allowed path
  const allowed = ctx.allowedPaths.some(p => absPath.startsWith(p))
  if (!allowed) {
    return `Error: access denied — ${absPath} is outside allowed paths`
  }

  try {
    mkdirSync(dirname(absPath), { recursive: true })
    writeFileSync(absPath, content, 'utf8')
    return `Wrote ${Buffer.byteLength(content, 'utf8')} bytes to ${absPath}`
  } catch (err) {
    return `Error writing file: ${String(err)}`
  }
}
