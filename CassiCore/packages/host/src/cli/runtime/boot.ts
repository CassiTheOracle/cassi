import { readFile } from 'node:fs/promises'
import { existsSync } from 'node:fs'

import { getJson } from './http.js'
import { fail } from './output.js'
import { findDaemonPid, getPaths, isPidRunning, readPid } from './process.js'

export async function ensureLaunchPrerequisites(): Promise<void> {
  const { sourceDaemonEntry, tsxCli } = getPaths()

  if (!existsSync(tsxCli)) {
    fail(`Missing tsx launcher at ${tsxCli}. Run npm install.`)
  }

  if (!existsSync(sourceDaemonEntry)) {
    fail(`Missing source daemon entrypoint at ${sourceDaemonEntry}.`)
  }
}

export async function waitForDaemonReady(timeoutMs = 30_000): Promise<void> {
  const deadline = Date.now() + timeoutMs

  while (Date.now() < deadline) {
    try {
      const response = await getJson<Record<string, unknown>>('/health', { allowNotOk: true })
      if (response.status >= 200 && response.status < 600) {
        return
      }
    } catch {
      // keep waiting
    }

    await sleep(500)
  }

  fail(`Daemon did not become ready within ${Math.ceil(timeoutMs / 1000)}s`)
}

export interface FetchHealthOptions {
  allowNotOk?: boolean
  /** Request timeout in milliseconds. Default: 30000 */
  timeout?: number
}

export async function fetchHealth(options: FetchHealthOptions = {}): Promise<{ statusCode: number; data: Record<string, unknown> }> {
  const response = await getJson<Record<string, unknown>>('/health', { 
    allowNotOk: options.allowNotOk ?? true,
    timeout: options.timeout,
  })
  return { statusCode: response.status, data: response.data }
}

export function getLocalDaemonStatus(): { running: boolean; daemonPid?: number } {
  const daemonPid = findDaemonPid() ?? readPid()
  return {
    running: isPidRunning(daemonPid),
    daemonPid,
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}