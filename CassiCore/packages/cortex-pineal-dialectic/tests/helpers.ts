/**
 * Shared test utilities for Cortex-Pineal-Dialectic package tests.
 * Ported from D: tests/helpers.ts (mockLogger + tmpDir).
 */
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import type { ILogger } from '@cassicore/foundation'

/** Silent mock logger — records calls for assertion if needed */
export function mockLogger(): ILogger {
  const calls: { level: string; msg: string }[] = []
  const make = (level: string) => (msg: string) => calls.push({ level, msg })
  const logger: ILogger = {
    debug: make('debug'),
    info: make('info'),
    warn: make('warn'),
    error: make('error'),
    child: () => logger,
  }
  ;(logger as any)._calls = calls
  return logger
}

/** Create a temp directory, return { path, cleanup } */
export function tmpDir(): { path: string; cleanup: () => void } {
  const p = mkdtempSync(join(tmpdir(), 'cassicore-test-'))
  return { path: p, cleanup: () => rmSync(p, { recursive: true, force: true }) }
}
