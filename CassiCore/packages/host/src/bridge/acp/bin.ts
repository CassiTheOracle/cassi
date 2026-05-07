import { appendFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'
import { Readable, Writable } from 'node:stream'

import {
  AgentSideConnection,
  ndJsonStream,
} from '@zed-industries/agent-client-protocol'

import { CassiAgent } from './server.js'

const baseUrl = process.env.CASSICORE_ADMIN_URL || 'http://127.0.0.1:7433'
const adminToken = process.env.CASSI_ADMIN_TOKEN || process.env.CASSICORE_ADMIN_TOKEN
const logPath = process.env.CASSI_ACP_LOG || join(homedir(), '.cassicore', 'cassi-acp.log')

function logToStderr(msg: string): void {
  const line = `[cassi-acp ${new Date().toISOString()}] ${msg}\n`
  process.stderr.write(line)
  try { appendFileSync(logPath, line) } catch { /* best effort */ }
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
