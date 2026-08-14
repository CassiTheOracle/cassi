/**
 * Shared test utility — mockLogger (ported from D: tests/helpers.ts).
 */
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
  return logger
}
