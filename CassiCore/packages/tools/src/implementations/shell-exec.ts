import { executeToolWithProxy } from '../../tool-proxy-middleware.js';

import type { ToolDefinition, ToolHandler, ToolExecutionContext } from '../types.js';

export const shellExecDefinition: ToolDefinition = {
  name: 'shell_exec',
  description: 'Execute a shell command and return output.',
  parameters: {
    type: 'object',
    properties: {
      command: { type: 'string', description: 'Command to execute' },
      workdir: { type: 'string', description: 'Working directory' },
      timeout_ms: { type: 'number', description: 'Timeout ms' },
    },
    required: ['command'],
  },
  timeoutMs: 120_000,
};

async function nativeShellExec(command: string, workdir: string, timeoutMs: number): Promise<string> {
  const { spawn } = await import('node:child_process');
  const { spawnSync } = await import('node:child_process');

  // Check if bash is available before spawning
  const bashCheck = spawnSync('which', ['bash'], { encoding: 'utf-8', timeout: 5000 });
  const shellCommand = bashCheck.status === 0 ? 'bash' : (spawnSync('which', ['sh'], { encoding: 'utf-8', timeout: 5000 }).status === 0 ? 'sh' : null);

  if (!shellCommand) {
    throw new Error('No shell available (bash/sh not found in PATH)');
  }

  return new Promise((resolve) => {
    let output = '';
    const proc = spawn(shellCommand, ['-c', command], { cwd: workdir });
    const timer = setTimeout(() => proc.kill(), timeoutMs);
    proc.stdout.on('data', (d: Buffer) => { output += d.toString(); });
    proc.stderr.on('data', (d: Buffer) => { output += d.toString(); });
    proc.on('close', () => { clearTimeout(timer); resolve(output || '(no output)'); });
  });
}

export const shellExecHandler: ToolHandler = async (input, ctx) => {
  const command = input['command'] as string;
  const workdir = (input['workdir'] as string) ?? ctx.workingDir;
  const timeoutMs = (input['timeout_ms'] as number) ?? 30_000;
  return executeToolWithProxy('shell_exec', { command, cwd: workdir, timeout_ms: timeoutMs }, () => nativeShellExec(command, workdir, timeoutMs));
};
