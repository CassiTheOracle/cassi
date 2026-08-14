import { spawnSync } from 'node:child_process'
import { existsSync, mkdirSync, readFileSync, unlinkSync } from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { fail } from './output.js'

const CURRENT_DIR = path.dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = resolveRepoRoot()
const CASSICORE_HOME = process.env.CASSICORE_HOME || path.join(os.homedir(), '.cassicore')
const PID_FILE = path.join(CASSICORE_HOME, 'daemon.pid')
const LOG_FILE = path.join(CASSICORE_HOME, 'daemon.log')
const SOCK_FILE = path.join(CASSICORE_HOME, 'admin.sock')
const BACKGROUND_LAUNCHER = path.join(CURRENT_DIR, 'background-launcher.cjs')
const SOURCE_DAEMON_ENTRY = path.join(REPO_ROOT, 'core', 'entry', 'daemon-main.ts')
const COMPILED_DAEMON_ENTRY = path.join(REPO_ROOT, 'dist', 'core', 'entry', 'daemon-main.js')
const AI_DIST = path.join(REPO_ROOT, 'ai', 'dist', 'index.js')
const TSX_CLI = path.join(REPO_ROOT, 'node_modules', 'tsx', 'dist', 'cli.mjs')

export interface SpawnResult {
  pid: number
}

export function getPaths() {
  return {
    repoRoot: REPO_ROOT,
    cassicoreHome: CASSICORE_HOME,
    pidFile: PID_FILE,
    logFile: LOG_FILE,
    sockFile: SOCK_FILE,
    backgroundLauncher: BACKGROUND_LAUNCHER,
    sourceDaemonEntry: SOURCE_DAEMON_ENTRY,
    compiledDaemonEntry: COMPILED_DAEMON_ENTRY,
    aiDist: AI_DIST,
    tsxCli: TSX_CLI,
  }
}

export function ensureLaunchTarget(): void {
  if (!existsSync(TSX_CLI)) {
    fail(`Missing tsx launcher at ${TSX_CLI}. Run npm install.`)
  }
  if (!existsSync(SOURCE_DAEMON_ENTRY)) {
    fail(`Missing source daemon entrypoint ${SOURCE_DAEMON_ENTRY}`)
  }
}

export function readPid(): number | undefined {
  try {
    const value = readFileSync(PID_FILE, 'utf8').trim()
    if (!value) return undefined
    const pid = Number(value)
    return Number.isInteger(pid) ? pid : undefined
  } catch {
    return undefined
  }
}

export function isPidRunning(pid: number | undefined): boolean {
  if (!pid) return false
  try {
    process.kill(pid, 0)
    return true
  } catch {
    return false
  }
}

export function findProcessIdsByTitle(title: string): number[] {
  const result = spawnSync('pgrep', ['-x', title], {
    cwd: REPO_ROOT,
    encoding: 'utf8',
  })

  if (result.status !== 0 || !result.stdout.trim()) {
    return []
  }

  return result.stdout
    .trim()
    .split(/\s+/)
    .map(value => Number(value))
    .filter(value => Number.isInteger(value) && value > 0)
}

export function findDaemonPid(): number | undefined {
  return findProcessIdsByTitle('cassi:daemon')[0]
}

export function cleanupOrphanedProcesses(trackedPid?: number): void {
  const targets = new Set<number>()

  for (const title of ['cassi:daemon']) {
    for (const pid of findProcessIdsByTitle(title)) {
      if (trackedPid && pid === trackedPid) continue
      targets.add(pid)
    }
  }

  if (targets.size === 0) {
    return
  }

  for (const pid of targets) {
    try {
      process.kill(pid, 'SIGTERM')
    } catch {
      // ignore
    }
  }

  const deadline = Date.now() + 5_000
  while (Date.now() < deadline) {
    const alive = [...targets].some(pid => isPidRunning(pid))
    if (!alive) {
      return
    }
    Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 100)
  }

  for (const pid of targets) {
    try {
      process.kill(pid, 'SIGKILL')
    } catch {
      // ignore
    }
  }
}

export async function stopDaemon(): Promise<boolean> {
  const pid = findDaemonPid() ?? readPid()

  if (!pid || !isPidRunning(pid)) {
    cleanupOrphanedProcesses(undefined)
    cleanupPidFile()
    return false
  }

  try {
    process.kill(pid, 'SIGTERM')
  } catch {
    cleanupPidFile()
    return false
  }

  const deadline = Date.now() + 30_000
  while (Date.now() < deadline) {
    const daemonAlive = isPidRunning(findDaemonPid() ?? readPid())
    if (!daemonAlive) {
      cleanupOrphanedProcesses(undefined)
      cleanupPidFile()
      return true
    }
    await sleep(250)
  }

  try {
    process.kill(pid, 'SIGKILL')
  } catch {
    // ignore
  }

  cleanupOrphanedProcesses(undefined)
  cleanupPidFile()
  return true
}

export function startDaemonProcess(args: string[] = []): SpawnResult {
  ensureLaunchTarget()
  mkdirSync(CASSICORE_HOME, { recursive: true })
  cleanupOrphanedProcesses(undefined)

  const command = process.execPath
  const commandArgs = [TSX_CLI, SOURCE_DAEMON_ENTRY, ...args]

  const launcherPayload = JSON.stringify({
    command,
    commandArgs,
    cwd: REPO_ROOT,
    logFile: LOG_FILE,
    pidFile: PID_FILE,
    sockFile: SOCK_FILE,
  })

  const result = spawnSync(process.execPath, [BACKGROUND_LAUNCHER, launcherPayload], {
    cwd: REPO_ROOT,
    encoding: 'utf8',
    env: { ...process.env },
  })

  if (result.status !== 0) {
    fail(result.stderr.trim() || result.stdout.trim() || 'Failed to start daemon process')
  }

  const pid = Number(result.stdout.trim())
  if (!Number.isInteger(pid) || pid <= 0) {
    fail(`Invalid daemon pid from launcher: ${result.stdout.trim()}`)
  }

  return { pid }
}

export function runForeground(args: string[] = []): number {
  ensureLaunchTarget()
  const command = process.execPath
  const commandArgs = [TSX_CLI, SOURCE_DAEMON_ENTRY, ...args]

  const result = spawnSync(command, commandArgs, {
    cwd: REPO_ROOT,
    stdio: 'inherit',
    env: { ...process.env },
  })

  return result.status ?? 1
}

function cleanupPidFile(): void {
  try {
    unlinkSync(PID_FILE)
  } catch {
    // ignore
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}

function resolveRepoRoot(): string {
  const candidates = [
    path.resolve(CURRENT_DIR, '../../..'),
    path.resolve(CURRENT_DIR, '../../../..'),
  ]

  for (const candidate of candidates) {
    if (existsSync(path.join(candidate, 'package.json'))) {
      return candidate
    }
  }

  return candidates[0]
}
