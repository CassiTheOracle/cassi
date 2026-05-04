import { ParsedArgs, assertNoExtraPositionals, optionalBoolean, optionalString, parseJsonOption, requiredString, takeCommand } from '../runtime/args.js'
import { deleteJson, getJson, postJson } from '../runtime/http.js'
import { fail, printData } from '../runtime/output.js'

export async function handleProviderCommand(args: ParsedArgs): Promise<void> {
  const subcommand = takeCommand(args, 'provider command')

  switch (subcommand) {
    case 'list':
      assertNoExtraPositionals(args)
      printData((await getJson('/providers')).data)
      return
    case 'metrics':
      assertNoExtraPositionals(args)
      printData((await getJson('/providers/metrics', { query: { providerId: optionalString(args.options, 'id'), model: optionalString(args.options, 'model') } })).data)
      return
    case 'health':
      assertNoExtraPositionals(args)
      printData((await getJson('/health/providers')).data)
      return
    case 'qwen-stats':
      assertNoExtraPositionals(args)
      printData((await getJson('/providers/qwen/stats')).data)
      return
    case 'qwen-accounts':
      assertNoExtraPositionals(args)
      printData((await getJson('/providers/qwen/accounts')).data)
      return
    case 'qwen-renew':
      assertNoExtraPositionals(args)
      printData((await postJson('/providers/qwen/renew')).data)
      return
    case 'config':
      assertNoExtraPositionals(args)
      printData((await getJson('/providers/config')).data)
      return
    case 'config-keys':
      assertNoExtraPositionals(args)
      printData((await getJson('/providers/config/keys')).data)
      return
    case 'set-config':
      await setConfig(args)
      return
    case 'clear-config':
      await clearConfig(args)
      return
    case 'apply-config':
      assertNoExtraPositionals(args)
      printData((await postJson('/providers/config/apply', { body: {} })).data)
      return
    case 'reset':
      await resetProviders(args)
      return
    default:
      fail(`Unknown provider command: ${subcommand}`)
  }
}

async function setConfig(args: ParsedArgs): Promise<void> {
  const body = parseJsonOption<Record<string, unknown>>(args.options, 'body')
  if (body) {
    assertNoExtraPositionals(args)
    printData((await postJson('/providers/config', { body })).data)
    return
  }

  const key = requiredString(args.options, 'key')
  const valueRaw = requiredString(args.options, 'value')
  assertNoExtraPositionals(args)
  printData((await postJson('/providers/config', { body: { key, value: parseLooseJson(valueRaw) } })).data)
}

async function clearConfig(args: ParsedArgs): Promise<void> {
  const key = optionalString(args.options, 'key')
  const keys = parseJsonOption<string[]>(args.options, 'keys')
  assertNoExtraPositionals(args)
  printData((await deleteJson('/providers/config', { body: { key, keys } })).data)
}

async function resetProviders(args: ParsedArgs): Promise<void> {
  const body = {
    providerId: optionalString(args.options, 'id'),
    resetErrors: optionalBoolean(args.options, 'reset-errors'),
    resetRateLimits: optionalBoolean(args.options, 'reset-rate-limits'),
  }
  assertNoExtraPositionals(args)
  printData((await postJson('/providers/reset', { body })).data)
}

function parseLooseJson(value: string): unknown {
  try {
    return JSON.parse(value)
  } catch {
    return value
  }
}
