export class CliError extends Error {
  readonly exitCode: number

  constructor(message: string, exitCode = 1) {
    super(message)
    this.name = 'CliError'
    this.exitCode = exitCode
  }
}

export function fail(message: string, exitCode = 1): never {
  throw new CliError(message, exitCode)
}

export function describeError(error: unknown): string {
  if (error instanceof CliError || error instanceof Error) {
    return error.message
  }

  if (typeof error === 'string') {
    return error
  }

  return String(error)
}

export function getExitCode(error: unknown): number {
  return error instanceof CliError ? error.exitCode : 1
}

/**
 * @dep callers: printHelp (src/cli/cassicore.ts), followFile (src/cli/commands/log.ts), handleLogCommand (src/cli/commands/log.ts), startCommand (src/cli/commands/boot.ts), stopCommand (src/cli/commands/boot.ts) [+6]
 * @dep flows: Main → PrintLine (4/4)
 * @dep module: Runtime
 * @dep risk: CRITICAL | 11 callers, 1 flow, 1 module
 */

export function printLine(message: string): void {
  console.log(message) // contributing:ignore
}

/**
 * @dep callers: handleProviderCommand (src/cli/commands/provider.ts), setConfig (src/cli/commands/provider.ts), clearConfig (src/cli/commands/provider.ts), resetProviders (src/cli/commands/provider.ts), handleModelCommand (src/cli/commands/model.ts) [+12]
 * @dep module: Runtime
 * @dep risk: CRITICAL | 17 callers, 0 flows, 1 module
 */

export function printData(value: unknown): void {
  if (typeof value === 'string') {
    console.log(value) // contributing:ignore
    return
  }

  console.log(JSON.stringify(value, null, 2)) // contributing:ignore
}

export function printKeyValue(label: string, value: unknown): void {
  console.log(`${label}: ${formatInline(value)}`) // contributing:ignore
}

export function formatInline(value: unknown): string {
  if (value === null || value === undefined) {
    return '-'
  }

  if (typeof value === 'string') {
    return value
  }

  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value)
  }

  return JSON.stringify(value)
}

/**
 * @dep callers: cli.ts (src/cli.ts), cassicore.ts (src/cli/cassicore.ts)
 * @dep calls: getExitCode, describeError, main
 * @dep module: Unknown
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

export async function runMain(main: () => Promise<void>): Promise<void> {
  try {
    await main()
  } catch (error) {
    console.error(describeError(error)) // contributing:ignore
    process.exit(getExitCode(error))
  }
}
