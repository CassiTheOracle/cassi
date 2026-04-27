import { Readable, Writable } from 'node:stream'

import {
  AgentSideConnection,
  ndJsonStream,
} from '@zed-industries/agent-client-protocol'

import { CassiAgent } from './server.js'

const baseUrl = process.env.CASSICORE_ADMIN_URL || 'http://127.0.0.1:7433'
const adminToken = process.env.CASSI_ADMIN_TOKEN || process.env.CASSICORE_ADMIN_TOKEN

function logToStderr(msg: string): void {
  process.stderr.write(`[cassi-acp] ${msg}\n`)
}

async function main(): Promise<void> {
  const input = Readable.toWeb(process.stdin) as unknown as ReadableStream<Uint8Array>
  const output = Writable.toWeb(process.stdout) as unknown as WritableStream<Uint8Array>
  const stream = ndJsonStream(output, input)

  const conn = new AgentSideConnection(
    (c) => new CassiAgent(c, { baseUrl, adminToken, log: logToStderr }),
    stream,
  )

  void conn

  await new Promise<void>((resolve) => {
    process.stdin.on('end', () => resolve())
    process.stdin.on('close', () => resolve())
  })

  logToStderr('stdin closed; exiting')
}

main().catch((err) => {
  logToStderr(`fatal: ${String(err)}`)
  process.exit(1)
})
