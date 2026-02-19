import { spawn } from 'node:child_process'
import type { ToolDefinition, ToolHandler, ToolExecutionContext } from '../types.js'

export const shellExecDefinition: ToolDefinition = {
  name: 'shell_exec',
  description: 'Execute a shell command and return the combined stdout/stderr output. Use for running code, system queries, file operations, or anything requiring a terminal.',
  parameters: {
    type: 'object',
    properties: {
      command:    { type: 'string', description: 'Shell command to execute' },
      workdir:    { type: 'string', description: 'Working directory (optional, defaults to workspace)' },
      timeout_ms: { type: 'number', description: 'Timeout in milliseconds (default 30000, max 120000)' },
    },
    required: ['command'],
  },
  timeoutMs: 120_000,
}

const MAX_OUTPUT = 100 * 1024  // 100KB

export const shellExecHandler: ToolHandler = async (input, ctx: ToolExecutionContext) => {
  const command    = input['command'] as string
  const workdir    = (input['workdir'] as string | undefined) ?? ctx.workingDir
  const timeoutMs  = Math.min((input['timeout_ms'] as number | undefined) ?? 30_000, 120_000)

  return new Promise((resolve, reject) => {
    let output = ''
    let killed = false

    const proc = spawn('bash', ['-c', command], {
      cwd: workdir,
      env: { ...process.env, HOME: process.env['HOME'] ?? '/home/valerie' },
    })

    const killTimer = setTimeout(() => {
      killed = true
      proc.kill('SIGTERM')
      setTimeout(() => proc.kill('SIGKILL'), 5_000)
    }, timeoutMs)

    proc.stdout.on('data', (d: Buffer) => {
      output += d.toString()
      if (output.length > MAX_OUTPUT) output = output.slice(0, MAX_OUTPUT) + '\n[output truncated]'
    })
    proc.stderr.on('data', (d: Buffer) => {
      output += d.toString()
      if (output.length > MAX_OUTPUT) output = output.slice(0, MAX_OUTPUT) + '\n[output truncated]'
    })

    proc.on('close', (code) => {
      clearTimeout(killTimer)
      if (killed) {
        resolve(`[command timed out after ${timeoutMs}ms]\n${output}`)
      } else {
        const exitLine = code !== 0 ? `\n[exit code: ${code}]` : ''
        resolve((output || '(no output)') + exitLine)
      }
    })

    proc.on('error', (err) => {
      clearTimeout(killTimer)
      reject(err)
    })
  })
}
