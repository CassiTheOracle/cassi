#!/usr/bin/env node
/**
 * cassi-watch — Real-time LLM call streaming viewer for CassiCore
 *
 * Usage:
 *   cassicore watch                          # Start watching LLM calls
 *   cassicore watch --socket <path>          # Use custom Unix socket
 *   cassicore watch --url <url>              # Use custom HTTP URL
 *   cassicore watch --provider <name>        # Filter by provider
 *   cassicore watch --session <id>           # Filter by session
 */

import React from 'react'
import { render } from 'ink'

import { WatchClient } from './client/watch-client.js'
import { App } from './App.js'

// ── Argument parsing ──────────────────────────────────────────────────────

function parseArgs(argv: string[]): Record<string, string> {
  const args: Record<string, string> = {}
  for (let i = 0; i < argv.length; i++) {
    if (argv[i]?.startsWith('--') && argv[i + 1] && !argv[i + 1]?.startsWith('--')) {
      args[argv[i]!.slice(2)] = argv[i + 1]!
      i++
    } else if (argv[i]?.startsWith('--')) {
      args[argv[i]!.slice(2)] = 'true'
    }
  }
  return args
}

// ── Main ────────────────────────────────────────────────────────────────────

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2))

  const client = new WatchClient({
    socketPath: args['socket'],
    baseURL: args['url'],
  })

  // Check daemon connectivity
  try {
    const info = await client.ping()
    const version = info.version ?? 'unknown'
    process.stderr.write(
      `Connected to CassiCore daemon v${version} at ${client.connectionString}\n` +
        `Streaming LLM calls... Press '?' for help, 'q' to quit.\n\n`,
    )
  } catch (err) {
    process.stderr.write(
      `Failed to connect to CassiCore daemon: ${String(err)}\n` +
        `Make sure the daemon is running (cassicore start or npm run dev).\n`,
    )
    process.exit(1)
  }

  // Render the Ink application
  const { waitUntilExit } = render(
    React.createElement(App, {
      client,
      daemonUrl: args['url'],
    }),
    { exitOnCtrlC: false }, // We handle Ctrl+C ourselves
  )

  await waitUntilExit()
}

main().catch((err) => {
  process.stderr.write(`Fatal: ${String(err)}\n`)
  process.exit(1)
})
