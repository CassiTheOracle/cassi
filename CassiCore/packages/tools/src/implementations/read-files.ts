import { readFileSync, existsSync } from 'node:fs'
import { resolve } from 'node:path'

import type { ToolDefinition, ToolHandler, ToolExecutionContext } from '../types.js'

export const readFilesDefinition: ToolDefinition = {
  name: 'read_files',
  description: 'Read multiple files in a single call. More efficient than calling read_file repeatedly.',
  parameters: {
    type: 'object',
    properties: {
      paths: {
        type: 'string',
        description: 'JSON array of file paths to read (e.g. ["file1.md", "file2.ts"])',
      },
      limit_each: {
        type: 'number',
        description: 'Max lines to read per file (optional)',
      },
    },
    required: ['paths'],
  },
  timeoutMs: 15_000,
  readOnly: true,
}

const MAX_BYTES_EACH = 512 * 1024  // 512KB per file

export const readFilesHandler: ToolHandler = async (input, ctx: ToolExecutionContext) => {
  let paths: string[]
  try {
    paths = JSON.parse(input['paths'] as string) as string[]
    if (!Array.isArray(paths)) throw new Error('not an array')
  } catch {
    return 'Error: paths must be a JSON array of strings'
  }

  const limitEach = input['limit_each'] as number | undefined
  const results: string[] = []

  for (const rawPath of paths) {
    const absPath = rawPath.startsWith('/') ? rawPath : resolve(ctx.workingDir, rawPath)
    const allowed = ctx.allowedPaths.some(p => absPath.startsWith(p))
    if (!allowed) {
      results.push(`## ${rawPath}\nERROR: access denied`)
      continue
    }
    if (!existsSync(absPath)) {
      results.push(`## ${rawPath}\nERROR: not found`)
      continue
    }
    try {
      const raw = readFileSync(absPath)
      let content = raw.slice(0, MAX_BYTES_EACH).toString('utf8')
      if (raw.length > MAX_BYTES_EACH) content += `\n\n[file truncated at ${MAX_BYTES_EACH.toLocaleString()} bytes — total is ${raw.length.toLocaleString()} bytes. Use read_file with offset to paginate.]`
      if (limitEach) {
        content = content.split('\n').slice(0, limitEach).join('\n')
      }
      results.push(`## ${rawPath}\n${content}`)
    } catch (err) {
      results.push(`## ${rawPath}\nERROR: ${String(err)}`)
    }
  }

  return results.join('\n\n---\n\n')
}
