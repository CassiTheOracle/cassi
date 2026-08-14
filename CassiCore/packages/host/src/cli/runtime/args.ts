import { fail } from './output.js'

export interface ParsedArgs {
  positionals: string[]
  options: Record<string, unknown>
}

export function parseArgv(argv: string[]): ParsedArgs {
  const positionals: string[] = []
  const options: Record<string, unknown> = {}

  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index]

    if (token === '--') {
      positionals.push(...argv.slice(index + 1))
      break
    }

    if (!token.startsWith('--') || token === '--') {
      positionals.push(token)
      continue
    }

    const withoutPrefix = token.slice(2)
    const eqIndex = withoutPrefix.indexOf('=')
    if (eqIndex >= 0) {
      const key = withoutPrefix.slice(0, eqIndex)
      const rawValue = withoutPrefix.slice(eqIndex + 1)
      options[key] = coerceValue(rawValue)
      continue
    }

    const next = argv[index + 1]
    if (next && !next.startsWith('--')) {
      options[withoutPrefix] = coerceValue(next)
      index += 1
      continue
    }

    options[withoutPrefix] = true
  }

  return { positionals, options }
}

export function takeCommand(args: ParsedArgs, label: string): string {
  const next = args.positionals.shift()
  if (!next) {
    fail(`Missing ${label}`)
  }
  return next
}

export function optionalString(options: Record<string, unknown>, key: string): string | undefined {
  const value = options[key]
  if (value === undefined || value === null || value === false) {
    return undefined
  }
  return String(value)
}

export function requiredString(options: Record<string, unknown>, key: string, message?: string): string {
  const value = optionalString(options, key)
  if (!value) {
    fail(message ?? `Missing --${key}`)
  }
  return value
}

export function optionalNumber(options: Record<string, unknown>, key: string): number | undefined {
  const value = options[key]
  if (value === undefined || value === null || value === false) {
    return undefined
  }

  const parsed = Number(value)
  if (!Number.isFinite(parsed)) {
    fail(`Invalid numeric value for --${key}: ${String(value)}`)
  }

  return parsed
}

export function optionalBoolean(options: Record<string, unknown>, key: string): boolean | undefined {
  const value = options[key]
  if (value === undefined) {
    return undefined
  }
  if (typeof value === 'boolean') {
    return value
  }
  if (typeof value === 'string') {
    if (value === 'true') return true
    if (value === 'false') return false
  }
  fail(`Invalid boolean value for --${key}: ${String(value)}`)
}

export function stringList(value: string | undefined): string[] | undefined {
  if (!value) {
    return undefined
  }

  const parts = value
    .split(',')
    .map(part => part.trim())
    .filter(Boolean)

  return parts.length > 0 ? parts : undefined
}

export function parseJsonOption<T>(options: Record<string, unknown>, key: string): T | undefined {
  const raw = optionalString(options, key)
  if (!raw) {
    return undefined
  }

  try {
    return JSON.parse(raw) as T
  } catch (error) {
    fail(`Invalid JSON for --${key}: ${String(error)}`)
  }
}

export function assertNoExtraPositionals(args: ParsedArgs): void {
  if (args.positionals.length > 0) {
    fail(`Unexpected arguments: ${args.positionals.join(' ')}`)
  }
}

function coerceValue(value: string): unknown {
  if (value === 'true') return true
  if (value === 'false') return false
  return value
}
