#!/usr/bin/env node
/**
 * CassiTUI — Ink/React terminal frontend for the CassiCore daemon.
 *
 * Usage:
 *   cassi                          # Connect to daemon, create new session
 *   cassi --session <id>           # Resume an existing session
 *   cassi --model <model-id>       # Use a specific model
 *   cassi --socket <path>          # Custom Unix socket path
 *   cassi --url <url>              # Custom daemon HTTP URL
 */

import React from 'react'
import { render } from 'ink'

import { DaemonClient } from './client/index.js'
import { App } from './App.js'

// ── Argument parsing (minimal, no dep) ──────────────────────────────────────

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

  const client = new DaemonClient({
    socketPath: args['socket'],
    baseURL: args['url'],
  })

  // Check daemon connectivity
  try {
    const info = await client.ping()
    const version = info.version ?? 'unknown'
    process.stderr.write(`Connected to CassiCore daemon v${version} at ${client.connectionString}\n`)
  } catch (err) {
    process.stderr.write(
      `Failed to connect to CassiCore daemon: ${String(err)}\n` +
        `Make sure the daemon is running (npm run dev or cassicore start).\n`,
    )
    process.exit(1)
  }

  // Resolve or create session
  let sessionId = args['session'] ?? ''
  const model = args['model']

  if (!sessionId) {
    // Check if there's a recent session to resume, otherwise generate a new ID.
    // Sessions are created implicitly by the daemon on first turn — no explicit
    // creation endpoint exists.
    try {
      const sessions = await client.sessions()
      if (sessions.length > 0) {
        sessions.sort((a, b) => b.lastActiveAt - a.lastActiveAt)
        sessionId = sessions[0]!.id
        process.stderr.write(`Resumed session: ${sessionId}\n`)
      }
    } catch {
      // Session listing may fail on fresh daemon — that's fine
    }

    if (!sessionId) {
      sessionId = client.generateSessionId()
      process.stderr.write(`New session: ${sessionId}\n`)
    }
  }

  // Render the Ink application
  const { waitUntilExit } = render(
    React.createElement(App, {
      client,
      initialSessionId: sessionId,
      initialModel: model,
      demo: args['demo'] === 'true',
    }),
    { exitOnCtrlC: false }, // We handle Ctrl+C ourselves
  )

  await waitUntilExit()
}

main().catch((err) => {
  process.stderr.write(`Fatal: ${String(err)}\n`)
  process.exit(1)
})
