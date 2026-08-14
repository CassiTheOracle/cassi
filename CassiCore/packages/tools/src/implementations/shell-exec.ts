import { executeToolWithProxy } from '../vendor/core/tool-proxy-middleware.js';

import type { ToolDefinition, ToolHandler, ToolExecutionContext } from '../types.js';

export const shellExecDefinition: ToolDefinition = {
  name: 'bash',
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
  requiredPermission: 'full-access',
};

interface ShellExecResult {
  stdout: string
  stderr: string
  exitCode: number
  durationMs: number
}

async function nativeShellExec(command: string, workdir: string, timeoutMs: number): Promise<string> {
  const { spawn } = await import('node:child_process');
  const { spawnSync } = await import('node:child_process');

  // Check if bash is available before spawning
  const bashCheck = spawnSync('which', ['bash'], { encoding: 'utf-8', timeout: 5000 });
  const shellCommand = bashCheck.status === 0 ? 'bash' : (spawnSync('which', ['sh'], { encoding: 'utf-8', timeout: 5000 }).status === 0 ? 'sh' : null);

  if (!shellCommand) {
    throw new Error('No shell available (bash/sh not found in PATH)');
  }

  const startTime = Date.now();
  
  return new Promise((resolve, reject) => {
    let stdout = '';
    let stderr = '';
    let exitCode = 0;
    
    const proc = spawn(shellCommand, ['-c', command], { cwd: workdir });
    const timer = setTimeout(() => {
      proc.kill();
      exitCode = 124; // timeout exit code
      stderr += '\n[Process killed: timeout exceeded]';
    }, timeoutMs);
    
    proc.stdout.on('data', (d: Buffer) => { stdout += d.toString(); });
    proc.stderr.on('data', (d: Buffer) => { stderr += d.toString(); });
    
    proc.on('close', (code) => {
      clearTimeout(timer);
      exitCode = code ?? 1;
      const durationMs = Date.now() - startTime;
      
      const result: ShellExecResult = {
        stdout: stdout || '(no output)',
        stderr,
        exitCode,
        durationMs,
      };
      
      // Return structured JSON that executor can parse
      resolve(JSON.stringify(result));
    });
    
    proc.on('error', (err) => {
      clearTimeout(timer);
      reject(new Error(`Spawn failed: ${err.message}`));
    });
  });
}

export const shellExecHandler: ToolHandler = async (input, ctx) => {
  const command = input['command'] as string;
  const workdir = (input['workdir'] as string) ?? ctx.workingDir;
  const timeoutMs = (input['timeout_ms'] as number) ?? 30_000;
  return executeToolWithProxy('bash', { command, cwd: workdir, timeout_ms: timeoutMs }, () => nativeShellExec(command, workdir, timeoutMs));
};
