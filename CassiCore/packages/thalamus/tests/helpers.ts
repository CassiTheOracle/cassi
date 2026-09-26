/**
 * Shared test utility for Thalamus package tests.
 * Ported from D: tests/helpers.ts (mockLogger only).
 */
import type { ILogger } from '@cassicore/foundation'

/** Silent mock logger — records calls for assertion if needed */
export function mockLogger(): ILogger {
  const calls: { level: string; msg: string }[] = [];
  const make = (level: string) => (msg: string) => calls.push({ level, msg });
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
