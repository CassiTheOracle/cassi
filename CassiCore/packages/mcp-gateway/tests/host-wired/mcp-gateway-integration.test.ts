import { describe, it, expect, beforeAll, afterAll, vi } from 'vitest';
import { spawn, ChildProcess } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';
import { createAdminRuntimeFacade } from '../core/admin-api/runtime.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');

describe('MCP Gateway', () => {
  describe('stdio transport mode (updated)', () => {
    let gatewayProcess: ChildProcess;
    const messages: string[] = [];

    beforeAll(async () => {
      gatewayProcess = spawn('npx', [
        'tsx', path.join(ROOT, 'mcp', 'cassicore-gateway.ts')
      ], {
        env: {
          ...process.env,
          CASSICORE_URL: 'http://localhost:7433',
        },
      });

      gatewayProcess.stdout?.on('data', (data) => {
        const lines = data.toString().trim().split('\n');
        lines.forEach((line: string) => {
          if (line) messages.push(line);
        });
      });

      gatewayProcess.stderr?.on('data', (data) => {
        const log = data.toString().trim();
        if (log.includes('"level":"error"')) {
          console.log('Gateway error:', log);
        }
      });

      await new Promise(resolve => setTimeout(resolve, 2000));
    }, 15000);

    afterAll(async () => {
      if (gatewayProcess) {
        gatewayProcess.kill();
        await new Promise(resolve => setTimeout(resolve, 500));
      }
    });

    describe('SSE Transport and Streaming Resources', () => {
      it('rejects HTTP/SSE-only methods over stdio transport', async () => {
        const testRequest = {
          jsonrpc: '2.0',
          id: 10,
          method: 'sse/stream',
          params: {
            streamId: 'test-stream',
          },
        };

        gatewayProcess.stdin?.write(JSON.stringify(testRequest) + '\n');

        await new Promise(resolve => setTimeout(resolve, 500));

        const responseMessages = messages.filter(m => {
          try {
            const parsed = JSON.parse(m);
            return parsed.id === 10;
          } catch {
            return false;
          }
        });

        expect(responseMessages).toHaveLength(1);
        const response = JSON.parse(responseMessages[0]);
        expect(response.error).toBeDefined();
        expect(response.error.code).toBe(-32601);
        expect(response.error.message).toBe('Method not found');
      });
    });
  });

  describe('HTTP mode auth posture', () => {
    it('requires an auth token when starting HTTP mode', async () => {
      const gatewayPath = path.join(ROOT, 'mcp', 'cassicore-gateway.ts');
      const proc = spawn('npx', ['tsx', gatewayPath, '--http', '--port=3999'], {
        env: {
          ...process.env,
          CASSICORE_URL: 'http://localhost:7433',
          CASSICORE_MCP_TOKEN: '',
        },
      });

      let stderr = '';
      proc.stderr?.on('data', (data) => {
        stderr += data.toString();
      });

      const exitCode = await new Promise<number | null>((resolve) => {
        proc.on('exit', resolve);
      });

      expect(exitCode).not.toBe(0);
      expect(stderr).toContain('CASSICORE_MCP_TOKEN is required in HTTP mode');
    }, 15000);
  });

  describe('admin runtime facade', () => {
    it('surfaces provider metrics through the facade', () => {
      const runtime = createAdminRuntimeFacade({
        logger: { info: vi.fn(), warn: vi.fn(), error: vi.fn(), debug: vi.fn(), child: vi.fn() },
        bus: { emit: vi.fn(), on: vi.fn(), off: vi.fn() },
        pipeline: {
          providers: new Map([
            ['test', { getMetrics: () => ({ currentRates: {}, learnedLimits: {}, globalConfig: { maxConcurrent: 8 } }) }],
          ]),
        },
      } as any);

      const metrics = runtime.getProviderMetrics();
      expect(metrics.global).toMatchObject({ maxConcurrent: 8 });
      expect(metrics.providers).toHaveLength(1);
      expect(metrics.providers[0]).toMatchObject({ id: 'test' });
    });
  });
});
