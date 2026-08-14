#!/usr/bin/env node

import { handleBootCommand } from './commands/boot.js'
import { handleLogCommand } from './commands/log.js'
import { handleModelCommand } from './commands/model.js'
import { handleProviderCommand } from './commands/provider.js'
import { ParsedArgs, parseArgv, takeCommand } from './runtime/args.js'
import { fail, printLine, runMain } from './runtime/output.js'

export async function main(argv = process.argv.slice(2)): Promise<void> {
  const args = parseArgv(argv)

  if (args.positionals.length === 0) {
    printHelp()
    return
  }

  const command = takeCommand(args, 'command')

  switch (command) {
    case 'boot':
      await handleBootCommand(args)
      return
    case 'log':
      await handleLogCommand(args)
      return
    case 'model':
      await handleModelCommand(args)
      return
    case 'provider':
      await handleProviderCommand(args)
      return
    case 'help':
    case '--help':
    case '-h':
      printHelp()
      return
    default:
      fail(`Unknown command: ${command}`)
  }
}

function printHelp(): void {
  const lines = [
    'CassiCore CLI',
    '',
    'Commands:',
    '  cassicore boot start|stop|restart|status|logs|run',
    '  cassicore log [--tail N] [--level LEVEL] [--grep PATTERN] [--follow] [--no-color]',
    '  cassicore model       list|routing|tiers|set|clear',
    '  cassicore provider    list|metrics|health|config|reset ...',
    '',
    'log — view daemon log with colorization:',
    '  cassicore log                    Show all log entries with colors',
    '  cassicore log --tail 100         Show last 100 lines',
    '  cassicore log --level warn       Show warn and error only',
    '  cassicore log --grep "session"   Filter lines matching pattern',
    '  cassicore log --follow           Tail -f style live view',
    '  cassicore log --no-color         Plain output without ANSI codes',
    '',
    'constellation — multi-Helix orchestration (use HTTP API):',
    '  POST /api/constellation/start     Start a new constellation',
    '  GET  /api/constellation/status    Check constellation status',
    '  GET  /api/constellation/tree      View Corpus reasoning tree',
    '',
    'helix — single-session orchestration (use HTTP API):',
    '  POST /api/helix/start             Start a new Helix session',
    '  GET  /api/helix/status            Check Helix session status',
  ]

  for (const line of lines) {
    printLine(line)
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  void runMain(() => main())
}
