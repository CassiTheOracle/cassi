/**
 * Admin API verification routes — /verify/*
 *
 * Enables agent self-testing against the live daemon:
 *
 *   POST /verify/run           Run a named scenario
 *   GET  /verify/scenarios     List available scenarios
 *   POST /verify/snapshot      Capture a labeled state snapshot
 *   POST /verify/diff          Compare two labeled snapshots
 *   GET  /verify/events        Query event history with filters
 */

import type { ILogger } from '../../types/interfaces.js'
import type http from 'node:http'

import { ScenarioRunner } from '../../src/testing/verification/scenario-runner.js'
import { LiveWorkflowHarness } from '../../src/testing/live/live-harness.js'
import { StateSnapshot } from '../../src/testing/verification/state-snapshot.js'
import { getScenario, listScenarios } from '../../src/testing/scenarios/index.js'
import { sessionExportToScenario } from '../../src/testing/replay/session-replay-adapter.js'
import { ReplayRunner } from '../../src/testing/replay/replay-runner.js'

export interface VerificationRoutesDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
  url: URL
  pathname: string
}

/** In-memory snapshot store — labeled snapshots for diff comparisons */
const snapshotStore = new Map<string, StateSnapshot>()

export async function handleVerificationRoutes(
  deps: VerificationRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
): Promise<boolean> {
  const { logger, sendJSON, parseBody, url, pathname } = deps

  // ── POST /verify/run ──────────────────────────────────────────────────────
  if (method === 'POST' && pathname === '/verify/run') {
    try {
      const body = await parseBody(req)
      const scenarioName = body?.scenario
      if (!scenarioName || typeof scenarioName !== 'string') {
        sendJSON(res, 400, { error: 'Missing required field: scenario (string)' })
        return true
      }

      const scenario = getScenario(scenarioName)
      if (!scenario) {
        const available = listScenarios().map(s => s.name)
        sendJSON(res, 404, {
          error: `Scenario "${scenarioName}" not found`,
          available,
        })
        return true
      }

      const timeoutMs = body?.options?.timeout ?? scenario.timeoutMs ?? 60_000
      const baseUrl = body?.options?.baseUrl // Allow override for testing

      logger.info('Running scenario', { scenario: scenarioName })

      const harness = new LiveWorkflowHarness({
        baseUrl,
        turnTimeoutMs: timeoutMs,
      })

      // Verify daemon is reachable
      const reachable = await harness.ping()
      if (!reachable) {
        sendJSON(res, 503, { error: 'Daemon not reachable — is it running?' })
        return true
      }

      const runner = new ScenarioRunner(harness)
      const result = await runner.run(scenario)

      logger.info('Scenario complete', {
        scenario: scenarioName,
        passed: result.passed,
        durationMs: result.durationMs,
      })

      sendJSON(res, result.passed ? 200 : 422, result)
      return true
    } catch (err) {
      logger.error('Scenario execution error', { error: String(err) })
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // ── GET /verify/scenarios ─────────────────────────────────────────────────
  if (method === 'GET' && pathname === '/verify/scenarios') {
    sendJSON(res, 200, { scenarios: listScenarios() })
    return true
  }

  // ── POST /verify/snapshot ─────────────────────────────────────────────────
  if (method === 'POST' && pathname === '/verify/snapshot') {
    try {
      const body = await parseBody(req)
      const label = body?.label
      if (!label || typeof label !== 'string') {
        sendJSON(res, 400, { error: 'Missing required field: label (string)' })
        return true
      }

      const sessionId = body?.sessionId
      const harness = new LiveWorkflowHarness({ autoPrune: false })
      const snapshot = await harness.snapshot(sessionId)
      snapshotStore.set(label, snapshot)

      await harness.teardown()

      sendJSON(res, 200, {
        label,
        timestamp: snapshot.data.timestamp,
        snapshot: snapshot.data,
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // ── POST /verify/diff ─────────────────────────────────────────────────────
  if (method === 'POST' && pathname === '/verify/diff') {
    try {
      const body = await parseBody(req)
      const beforeLabel = body?.before
      const afterLabel = body?.after

      if (!beforeLabel || !afterLabel) {
        sendJSON(res, 400, { error: 'Missing required fields: before, after (string labels)' })
        return true
      }

      const beforeSnap = snapshotStore.get(beforeLabel)
      if (!beforeSnap) {
        sendJSON(res, 404, {
          error: `Snapshot "${beforeLabel}" not found`,
          available: Array.from(snapshotStore.keys()),
        })
        return true
      }

      let afterSnap: StateSnapshot
      if (afterLabel === 'current') {
        // "current" is a special label — take a fresh snapshot
        const harness = new LiveWorkflowHarness({ autoPrune: false })
        afterSnap = await harness.snapshot(body?.sessionId)
        await harness.teardown()
      } else {
        const stored = snapshotStore.get(afterLabel)
        if (!stored) {
          sendJSON(res, 404, {
            error: `Snapshot "${afterLabel}" not found`,
            available: Array.from(snapshotStore.keys()),
          })
          return true
        }
        afterSnap = stored
      }

      const diff = beforeSnap.diff(afterSnap)
      sendJSON(res, 200, diff)
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // ── GET /verify/events ────────────────────────────────────────────────────
  if (method === 'GET' && pathname === '/verify/events') {
    try {
      const sessionId = url.searchParams.get('sessionId')
      if (!sessionId) {
        sendJSON(res, 400, { error: 'sessionId query parameter required' })
        return true
      }

      const sinceParam = url.searchParams.get('since') ?? '0'
      const typesParam = url.searchParams.get('types')
      const limitParam = parseInt(url.searchParams.get('limit') ?? '200', 10)

      // Parse "since" — supports ISO string, Unix ms, or relative like "5m"
      let since = 0
      if (sinceParam.endsWith('m')) {
        since = Date.now() - parseInt(sinceParam) * 60_000
      } else if (sinceParam.endsWith('h')) {
        since = Date.now() - parseInt(sinceParam) * 3600_000
      } else if (sinceParam.includes('T') || sinceParam.includes('-')) {
        since = new Date(sinceParam).getTime()
      } else {
        since = parseInt(sinceParam, 10)
      }

      const eventTypes = typesParam ? typesParam.split(',') : []

      // Fetch from event bus via internal import
      const { getEventBus } = await import('../events/index.js')
      const eventBus = getEventBus()

      let events = eventBus.getEventsSince(sessionId, since)
      if (eventTypes.length > 0) {
        events = events.filter((e: any) => eventTypes.includes(e.type))
      }
      events = events.slice(0, limitParam)

      sendJSON(res, 200, {
        events,
        count: events.length,
        sessionId,
        since,
        filters: eventTypes.length > 0 ? { types: eventTypes } : undefined,
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // ── POST /verify/replay ───────────────────────────────────────────────────
  if (method === 'POST' && pathname === '/verify/replay') {
    try {
      const body = await parseBody(req)
      const sessionId = body?.sessionId
      if (!sessionId || typeof sessionId !== 'string') {
        sendJSON(res, 400, { error: 'Missing required field: sessionId (string)' })
        return true
      }

      const exported = deps.daemon.intelligence?.memory?.exportSession?.(sessionId)
      if (!exported) {
        sendJSON(res, 404, { error: `Session ${sessionId} not found or not exportable` })
        return true
      }

      const scenario = sessionExportToScenario(sessionId, exported)
      const runner = new ReplayRunner()
      const report = await runner.run(sessionId, scenario, body?.baseline, body?.treatment)
      sendJSON(res, report.comparison.treatmentPassed ? 200 : 422, report)
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  return false
}
