import { ParsedArgs, assertNoExtraPositionals, optionalString, requiredString, takeCommand } from '../runtime/args.js'
import { getJson, postJson } from '../runtime/http.js'
import { fail, printData } from '../runtime/output.js'

export async function handleModelCommand(args: ParsedArgs): Promise<void> {
  const subcommand = takeCommand(args, 'model command')

  switch (subcommand) {
    case 'list':
      assertNoExtraPositionals(args)
      printData((await getJson('/models')).data)
      return
    case 'routing':
      assertNoExtraPositionals(args)
      printData((await getJson('/model-directive', { query: { jobId: optionalString(args.options, 'job-id') } })).data)
      return
    case 'tiers':
      assertNoExtraPositionals(args)
      printData((await getJson('/model-directive/tiers')).data)
      return
    case 'set':
      await setDirective(args)
      return
    case 'clear':
      await clearDirective(args)
      return
    default:
      fail(`Unknown model command: ${subcommand}`)
  }
}

async function setDirective(args: ParsedArgs): Promise<void> {
  const scope = args.positionals.shift() ?? requiredString(args.options, 'scope')
  assertNoExtraPositionals(args)
  const body = {
    scope,
    tier: optionalString(args.options, 'tier'),
    provider: optionalString(args.options, 'provider'),
    model: optionalString(args.options, 'model'),
    jobId: optionalString(args.options, 'job-id'),
    slot: optionalString(args.options, 'slot'),
  }
  printData((await postJson('/model-directive/set', { body })).data)
}

async function clearDirective(args: ParsedArgs): Promise<void> {
  const scope = args.positionals.shift() ?? requiredString(args.options, 'scope')
  assertNoExtraPositionals(args)
  const body = {
    scope,
    jobId: optionalString(args.options, 'job-id'),
    slot: optionalString(args.options, 'slot'),
  }
  printData((await postJson('/model-directive/clear', { body })).data)
}
