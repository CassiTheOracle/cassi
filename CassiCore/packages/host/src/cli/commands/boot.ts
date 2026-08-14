import { readFile } from 'node:fs/promises'

import { ParsedArgs, assertNoExtraPositionals, takeCommand } from '../runtime/args.js'
import { fetchHealth, getLocalDaemonStatus, waitForDaemonReady, ensureLaunchPrerequisites } from '../runtime/boot.js'
import { getBuildIdentifier, type BuildIdentifier } from '../../vendor/core/build-id.js'
import { getAdminUrl } from '../runtime/http.js'
import { fail, printData, printKeyValue, printLine } from '../runtime/output.js'
import { getPaths, runForeground, startDaemonProcess, stopDaemon } from '../runtime/process.js'

/** Cached source build identifier read once at module load. */
const SOURCE_BUILD: BuildIdentifier = getBuildIdentifier()

/** Timeout for health checks in stale detection (5 seconds) */
const STALE_CHECK_TIMEOUT_MS = 5000

export async function handleBootCommand(args: ParsedArgs): Promise<void> {
  const subcommand = takeCommand(args, 'boot command')

  switch (subcommand) {
    case 'start':
      assertNoExtraPositionals(args)
      await startCommand()
      return
    case 'stop':
      assertNoExtraPositionals(args)
      await stopCommand()
      return
    case 'restart':
      assertNoExtraPositionals(args)
      await restartCommand()
      return
    case 'status':
      assertNoExtraPositionals(args)
      await statusCommand()
      return
    case 'logs':
      assertNoExtraPositionals(args)
      await logsCommand()
      return
    case 'run':
      assertNoExtraPositionals(args)
      await runCommand()
      return
    default:
      fail(`Unknown boot command: ${subcommand}`)
  }
}

async function startCommand(): Promise<void> {
  const local = getLocalDaemonStatus()
  if (local.running) {
    // Check if running daemon is on the current version
    const stale = await isDaemonStale()
    if (stale) {
      printLine(`Daemon running (PID ${local.daemonPid ?? 'unknown'}) but version is stale — restarting...`)
      await stopDaemon()
    } else {
      printLine(`Daemon already running (PID ${local.daemonPid ?? 'unknown'})`)
      return
    }
  }

  await ensureLaunchPrerequisites()
  const result = startDaemonProcess([])
  printLine(`Starting daemon process (PID ${result.pid})`)
  await waitForDaemonReady()
  printLine(`Ready at ${getAdminUrl()}`)
}

async function stopCommand(): Promise<void> {
  const stopped = await stopDaemon()
  printLine(stopped ? 'Daemon stopped' : 'Daemon was not running')
}

async function restartCommand(): Promise<void> {
  await stopDaemon()
  await ensureLaunchPrerequisites()
  const result = startDaemonProcess([])
  printLine(`Restarting daemon process (PID ${result.pid})`)
  await waitForDaemonReady()
  printLine(`Ready at ${getAdminUrl()}`)
}

async function statusCommand(): Promise<void> {
  const local = getLocalDaemonStatus()
  const daemonPid = local.daemonPid

  if (!local.running) {
    printLine('Daemon not running')
    return
  }

  printKeyValue('Daemon PID', daemonPid)
  printKeyValue('Admin URL', getAdminUrl())

  try {
    const health = await fetchHealth({ timeout: STALE_CHECK_TIMEOUT_MS })
    printKeyValue('HTTP status', health.statusCode)
    printData(health.data)
  } catch (error) {
    printKeyValue('Health', `unavailable (${String(error)})`)
  }
}

async function logsCommand(): Promise<void> {
  const { logFile } = getPaths()
  try {
    const content = await readFile(logFile, 'utf8')
    printLine(content)
  } catch (error) {
    fail(`Unable to read log file ${logFile}: ${String(error)}`)
  }
}

async function runCommand(): Promise<void> {
  await ensureLaunchPrerequisites()
  const exitCode = runForeground([])
  process.exit(exitCode)
}

/** Compare the running daemon build identifier against the cached source build. */
async function isDaemonStale(): Promise<boolean> {
  if (SOURCE_BUILD.version === 'unknown') return false // can't determine, assume OK

  try {
    const health = await fetchHealth({ timeout: STALE_CHECK_TIMEOUT_MS })
    const data = health.data as Record<string, unknown>
    const runningVersion = data.version as string | undefined
    const runningBuildDetails = data.buildDetails as Record<string, unknown> | undefined
    const runningGitRef = runningBuildDetails?.gitRef as string | undefined

    // Version mismatch always means stale
    if (!runningVersion || runningVersion === 'unknown') return true
    if (runningVersion !== SOURCE_BUILD.version) return true

    // If source has git ref, running daemon must match it
    if (SOURCE_BUILD.gitRef) {
      if (!runningGitRef || runningGitRef !== SOURCE_BUILD.gitRef) return true
    }

    return false
  } catch {
    // Can't reach health endpoint — daemon might be unhealthy, restart it
    return true
  }
}