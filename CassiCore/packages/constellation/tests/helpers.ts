/**
 * Shared test utilities for Constellation package tests.
 * Import: import { mockLogger, tmpDir } from './helpers.js'
 *
 * Ported from CassiCore `tests/helpers.ts` during Constellation extraction.
 * The `ILogger` import points at the standalone package's vendor interface
 * surface (`src/vendor/types/interfaces.js`) instead of the daemon's
 * `../types/interfaces.js`.
 */
import { mkdtempSync, rmSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';
import type { ILogger } from '../src/vendor/types/interfaces.js';

/** Silent mock logger — records calls for assertion if needed */
export function mockLogger(): ILogger {
  const calls: { level: string; msg: string }[] = [];
  const make = (level: string) => (msg: string, _meta?: Record<string, unknown>) => calls.push({ level, msg });
  const logger: ILogger & { _calls: { level: string; msg: string }[] } = {
    debug: make('debug'),
    info: make('info'),
    warn: make('warn'),
    error: make('error'),
    child: () => logger,
    _calls: calls,
  };
  return logger;
}

/** Create a temp directory, return { path, cleanup } */
export function tmpDir(): { path: string; cleanup: () => void } {
  const p = mkdtempSync(join(tmpdir(), 'constellation-test-'));
  return { path: p, cleanup: () => rmSync(p, { recursive: true, force: true }) };
}
