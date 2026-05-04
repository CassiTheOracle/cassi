#!/usr/bin/env node

const { spawn } = require('node:child_process')
const { closeSync, mkdirSync, openSync, unlinkSync } = require('node:fs')
const path = require('node:path')

const payloadRaw = process.argv[2]
if (!payloadRaw) {
  console.error('Missing launch payload') // contributing:ignore - CLI error output
  process.exit(1)
}

let payload
try {
  payload = JSON.parse(payloadRaw)
} catch (error) {
  console.error(`Invalid launch payload: ${String(error)}`) // contributing:ignore - CLI error output
  process.exit(1)
}

mkdirSync(path.dirname(payload.logFile), { recursive: true })

try {
  unlinkSync(payload.sockFile)
} catch {
  // ignore stale socket cleanup failures
}

const stdoutFd = openSync(payload.logFile, 'a')
const stderrFd = openSync(payload.logFile, 'a')

const child = spawn(payload.command, payload.commandArgs, {
  cwd: payload.cwd,
  detached: true,
  stdio: ['ignore', stdoutFd, stderrFd],
  env: { ...process.env },
})

closeSync(stdoutFd)
closeSync(stderrFd)

if (!child.pid) {
  console.error('Failed to spawn daemon process') // contributing:ignore - CLI error output
  process.exit(1)
}

child.unref()
process.stdout.write(String(child.pid))
