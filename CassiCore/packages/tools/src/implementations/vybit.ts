/**
 * VyBit Integration Tool for CassiCore
 *
 * Connects to VyBit's MCP server to receive visual browser changes
 * (Tailwind class edits, component drops, design sketches, text edits, bug reports)
 * and translates them into CassiCore actions.
 *
 * Architecture:
 *   - Uses CassiCore's MCPClient to spawn and manage VyBit's STDIO MCP server
 *   - Exposes a unified `vybit` tool with action-based dispatch
 *   - Emits typed events to the CassiCore event bus for intelligence layer awareness
 *   - Translates VyBit patches into structured context for Constellation delegation
 *
 * VyBit MCP tools consumed:
 *   - implement_next_change: blocks waiting for next committed change, returns instructions + images
 *   - get_next_change: blocks, returns raw commit data
 *   - mark_change_implemented: marks a commit's patches as done
 *   - list_changes: lists changes by status
 *   - discard_all_changes: clears the queue
 */

import { MCPClient } from '../../vendor/core/mcp/client.js'
import { getEventBus } from '../../vendor/core/events/index.js'
import {
  handleDevStart, handleDevStop, handleInjectOverlay,
  handleBrowserOpen, handleSession, handleSessionStop,
  getDevServerState,
} from './vybit-loop.js'
import { ingestBugReport, ingestBugReports } from './vybit-bug-ingest.js'

import type { ToolDefinition, ToolHandler, ToolExecutionContext } from '../types.js'
import type { MCPServerConfig } from '../../vendor/core/mcp/types.js'

// VyBit patch types (subset of VyBit's shared/types.ts — enough for CassiCore)

type PatchKind = 'class-change' | 'message' | 'design' | 'component-drop' | 'text-change' | 'bug-report'
type PatchStatus = 'staged' | 'committed' | 'implementing' | 'implemented' | 'error'

interface VyBitPatch {
  id: string
  kind: PatchKind
  elementKey: string
  status: PatchStatus
  originalClass: string
  newClass: string
  property: string
  timestamp: string
  component?: { name: string; instanceCount?: number }
  target?: { tag: string; classes: string; innerText: string }
  context?: string
  message?: string
  image?: string
  insertMode?: string
  canvasWidth?: number
  canvasHeight?: number
  canvasComponents?: Array<{
    componentName: string
    componentPath?: string
    x: number
    y: number
    width: number
    height: number
    args?: Record<string, unknown>
  }>
  ghostHtml?: string
  componentPath?: string
  originalHtml?: string
  newHtml?: string
  componentArgs?: Record<string, unknown>
  parentComponent?: { name: string }
  targetPatchId?: string
  targetComponentName?: string
  bugDescription?: string
  bugScreenshots?: string[]
  bugTimeline?: Array<{
    timestamp: string
    trigger: string
    url: string
    consoleLogs?: Array<{ level: string; args: string[]; stack?: string }>
    networkErrors?: Array<{ url: string; method: string; status?: number; errorMessage?: string }>
    domChanges?: Array<{ type: string; selector: string; componentName?: string }>
    domSnapshot?: string
    domDiff?: string
    hasScreenshot?: boolean
    elementInfo?: { tag: string; classes: string }
  }>
  bugTimeRange?: { start: string; end: string }
  bugElement?: {
    tag: string
    selectorPath: string
    componentName?: string
    outerHTML: string
    boundingBox: { x: number; y: number; width: number; height: number }
  } | null
  commitId?: string
}

interface VyBitCommit {
  id: string
  patches: VyBitPatch[]
  status: string
  timestamp: string
}

interface VyBitQueueCounts {
  staged: number
  committed: number
  implementing: number
  implemented: number
}

// Singleton VyBit connection manager

let vybitClient: MCPClient | null = null
let vybitProjectPath: string | null = null
let vybitPort: number = 3333

function getVyBitConfig(projectPath: string, port: number): MCPServerConfig {
  return {
    id: 'vybit',
    command: 'npx',
    args: ['@bitovi/vybit', '--cwd', projectPath],
    description: 'VyBit visual browser editing server',
    env: { PORT: String(port) },
    startupTimeoutMs: 30_000,
    restartOnCrash: true,
    maxRestarts: 3,
  }
}

// Tool Definition

export const vybitDefinition: ToolDefinition = {
  name: 'vybit',
  description:
    'Visual browser editing integration via VyBit. ' +
    'Connects to a running VyBit server or starts one to receive visual changes ' +
    '(Tailwind class edits, component drops, design sketches, text changes, bug reports) ' +
    'from the browser and translate them into code implementation tasks.\n\n' +
    'Actions:\n' +
    '- session: Start a complete VyBit session (VyBit server + dev server + overlay + browser)\n' +
    '- session_stop: Stop the full session (VyBit + dev server)\n' +
    '- start: Start VyBit MCP server for a project directory\n' +
    '- stop: Disconnect and stop the VyBit server\n' +
    '- status: Get connection state, queue counts, and dev server state\n' +
    '- poll: Wait for the next committed change (blocks until available)\n' +
    '- list: List all changes, optionally filtered by status\n' +
    '- implement_next: Get the next change with full implementation instructions\n' +
    '- mark_done: Mark a commit as implemented\n' +
    '- discard: Discard all queued changes\n' +
    '- dev_start: Start the project dev server as a background process\n' +
    '- dev_stop: Stop the dev server\n' +
    '- inject_overlay: Inject VyBit overlay script into the project HTML\n' +
    '- browser_open: Open a browser to the dev server URL\n' +
    '- ingest_bugs: Parse all bug reports from the queue into structured investigation briefs',
  parameters: {
    type: 'object',
    properties: {
      action: {
        type: 'string',
        enum: [
          'session', 'session_stop',
          'start', 'stop', 'status', 'poll', 'list', 'implement_next', 'mark_done', 'discard',
          'dev_start', 'dev_stop', 'inject_overlay', 'browser_open',
          'ingest_bugs',
        ],
        description: 'Action to perform',
      },
      projectPath: {
        type: 'string',
        description: 'Absolute path to the target project (required for "start")',
      },
      port: {
        type: 'string',
        description: 'VyBit server port (default: 3333, used with "start")',
      },
      commitId: {
        type: 'string',
        description: 'Commit ID to mark as done (required for "mark_done")',
      },
      results: {
        type: 'string',
        description: 'JSON array of { patchId, success, error? } results (for "mark_done")',
      },
      filter: {
        type: 'string',
        description: 'Filter by status: staged, committed, implementing, implemented, error (for "list")',
      },
      devCommand: {
        type: 'string',
        description: 'Custom dev server command (e.g., "npm run dev"). Auto-detected from package.json if omitted.',
      },
      devPort: {
        type: 'string',
        description: 'Dev server port (auto-detected or default 3000)',
      },
      entryFile: {
        type: 'string',
        description: 'HTML/layout entry file for overlay injection (auto-detected if omitted)',
      },
      url: {
        type: 'string',
        description: 'URL to open in browser (defaults to dev server URL)',
      },
      skipBrowser: {
        type: 'string',
        description: 'Skip browser launch in session setup (default: false)',
      },
      skipOverlay: {
        type: 'string',
        description: 'Skip overlay injection in session setup (default: false)',
      },
    },
    required: ['action'],
  },
  timeoutMs: 120_000, // poll/implement_next can block for a long time
  category: 'extended',
  readOnly: false,
  backend: 'cassi',
  capability: 'vybit.visual_editing',
  requiredPermission: 'workspace-write',
}

// Action Handlers

async function handleStart(
  input: Record<string, unknown>,
  ctx: ToolExecutionContext,
): Promise<string> {
  if (vybitClient?.connected) {
    return JSON.stringify({
      status: 'already_connected',
      projectPath: vybitProjectPath,
      port: vybitPort,
      message: `VyBit is already running for ${vybitProjectPath} on port ${vybitPort}`,
    })
  }

  const projectPath = input.projectPath as string
  if (!projectPath) {
    return JSON.stringify({ error: 'projectPath is required for the "start" action' })
  }

  const port = input.port ? Number(input.port) : 3333
  vybitPort = port
  vybitProjectPath = projectPath

  const config = getVyBitConfig(projectPath, port)
  vybitClient = new MCPClient(config, ctx.logger)

  try {
    await vybitClient.connect()
    const tools = await vybitClient.listTools()

    // Emit connection event
    const bus = getEventBus()
    if (bus) {
      bus.emit({
        type: 'vybit:connected',
        projectPath,
        port,
        timestamp: new Date(),
      })
    }

    return JSON.stringify({
      status: 'connected',
      projectPath,
      port,
      tools: tools.map(t => t.name),
      message: `VyBit server started for ${projectPath}. Open http://localhost:${port} to access the visual editor. Available tools: ${tools.map(t => t.name).join(', ')}`,
    })
  } catch (err) {
    vybitClient = null
    vybitProjectPath = null
    return JSON.stringify({
      error: `Failed to start VyBit: ${String(err)}`,
      hint: 'Ensure @bitovi/vybit is installed (npm install -g @bitovi/vybit) and the project has tailwindcss configured.',
    })
  }
}

async function handleStop(ctx: ToolExecutionContext): Promise<string> {
  if (!vybitClient?.connected) {
    return JSON.stringify({ status: 'not_connected', message: 'VyBit is not running' })
  }

  try {
    await vybitClient.disconnect()
  } catch (err) {
    ctx.logger.warn(`VyBit disconnect error: ${String(err)}`)
  }

  const oldPath = vybitProjectPath
  vybitClient = null
  vybitProjectPath = null

  // Emit disconnection event
  const bus = getEventBus()
  if (bus) {
    bus.emit({
      type: 'vybit:disconnected',
      reason: 'manual_stop',
      timestamp: new Date(),
    })
  }

  return JSON.stringify({
    status: 'disconnected',
    message: `VyBit server stopped (was serving ${oldPath})`,
  })
}

async function handleStatus(): Promise<string> {
  const devState = getDevServerState()

  if (!vybitClient?.connected) {
    return JSON.stringify({
      connected: false,
      devServer: devState,
      message: 'VyBit is not running. Use action "session" to start a full visual editing session, or "start" for VyBit only.',
    })
  }

  try {
    const raw = await vybitClient.callTool('list_changes', {})
    const data = JSON.parse(raw)

    return JSON.stringify({
      connected: true,
      projectPath: vybitProjectPath,
      port: vybitPort,
      devServer: devState,
      queue: {
        draftCount: data.draftCount ?? 0,
        committedCount: data.committedCount ?? 0,
        implementingCount: data.implementingCount ?? 0,
        implementedCount: data.implementedCount ?? 0,
      },
    })
  } catch (err) {
    return JSON.stringify({
      connected: true,
      projectPath: vybitProjectPath,
      port: vybitPort,
      devServer: devState,
      queueError: String(err),
    })
  }
}

async function handlePoll(ctx: ToolExecutionContext): Promise<string> {
  assertConnected()

  try {
    ctx.logger.info('[vybit] Polling for next committed change (blocking)...')
    const raw = await vybitClient!.callTool('get_next_change', {})
    const commit: VyBitCommit = JSON.parse(raw)

    // Emit event
    const bus = getEventBus()
    if (bus) {
      bus.emit({
        type: 'vybit:change_committed',
        commitId: commit.id,
        patchCount: commit.patches.length,
        kinds: [...new Set(commit.patches.map(p => p.kind))],
        timestamp: new Date(),
      })
    }

    // Build a CassiCore-friendly summary
    return JSON.stringify({
      commit: {
        id: commit.id,
        status: commit.status,
        timestamp: commit.timestamp,
        patchCount: commit.patches.length,
        patches: commit.patches.map(summarizePatch),
      },
      analysis: analyzeCommit(commit),
    }, null, 2)
  } catch (err) {
    return JSON.stringify({ error: `Poll failed: ${String(err)}` })
  }
}

async function handleImplementNext(ctx: ToolExecutionContext): Promise<string> {
  assertConnected()

  try {
    ctx.logger.info('[vybit] Requesting next change with implementation instructions (blocking)...')
    const raw = await vybitClient!.callTool('implement_next_change', {})

    // The response contains JSON data + markdown instructions (and possibly images)
    // The MCPClient joins all text blocks with newlines
    // Try parsing the entire response as JSON first, then fall back to regex extraction
    let commit: VyBitCommit | null = null
    let instructions = raw

    // Attempt 1: try parsing the whole response as JSON
    try {
      const parsed = JSON.parse(raw)
      if (parsed.commit) {
        commit = parsed.commit
        instructions = ''
      }
    } catch {
      // Attempt 2: extract JSON object from the beginning of mixed content
      const jsonMatch = raw.match(/^\{[\s\S]*?"commit"[\s\S]*?\n\}/)
      if (jsonMatch) {
        try {
          const parsed = JSON.parse(jsonMatch[0])
          commit = parsed.commit
          instructions = raw.slice(jsonMatch[0].length).trim()
        } catch {
          // Fall through with raw text
        }
      }
    }

    // Emit events
    const bus = getEventBus()
    if (bus && commit) {
      bus.emit({
        type: 'vybit:change_implementing',
        commitId: commit.id,
        patchIds: commit.patches.map(p => p.id),
        sessionId: ctx.sessionId,
        timestamp: new Date(),
      })
    }

    // Build structured response for CassiCore agents
    const response: Record<string, unknown> = {
      raw_instructions: instructions,
    }

    if (commit) {
      response.commit = {
        id: commit.id,
        patchCount: commit.patches.length,
        patches: commit.patches.map(summarizePatch),
      }
      response.analysis = analyzeCommit(commit)
      response.delegation_hints = buildDelegationHints(commit)
    }

    return JSON.stringify(response, null, 2)
  } catch (err) {
    return JSON.stringify({ error: `implement_next failed: ${String(err)}` })
  }
}

async function handleMarkDone(
  input: Record<string, unknown>,
  ctx: ToolExecutionContext,
): Promise<string> {
  assertConnected()

  const commitId = input.commitId as string
  if (!commitId) {
    return JSON.stringify({ error: 'commitId is required for "mark_done"' })
  }

  let results: Array<{ patchId: string; success: boolean; error?: string }> = []
  if (input.results) {
    try {
      results = typeof input.results === 'string' ? JSON.parse(input.results) : input.results as any
    } catch {
      return JSON.stringify({ error: 'Invalid results JSON' })
    }
  }

  try {
    const raw = await vybitClient!.callTool('mark_change_implemented', {
      commitId,
      results,
    })

    // Emit event
    const bus = getEventBus()
    if (bus) {
      bus.emit({
        type: 'vybit:change_implemented',
        commitId,
        patchIds: results.filter(r => r.success).map(r => r.patchId),
        durationMs: 0,
        timestamp: new Date(),
      })
    }

    return raw
  } catch (err) {
    // Emit error event
    const bus = getEventBus()
    if (bus) {
      bus.emit({
        type: 'vybit:change_error',
        commitId,
        patchId: '',
        error: String(err),
        timestamp: new Date(),
      })
    }
    return JSON.stringify({ error: `mark_done failed: ${String(err)}` })
  }
}

async function handleList(input: Record<string, unknown>): Promise<string> {
  assertConnected()

  const filter = input.filter as string | undefined
  try {
    const raw = await vybitClient!.callTool('list_changes', filter ? { status: filter } : {})
    return raw
  } catch (err) {
    return JSON.stringify({ error: `list failed: ${String(err)}` })
  }
}

async function handleDiscard(): Promise<string> {
  assertConnected()

  try {
    const raw = await vybitClient!.callTool('discard_all_changes', {})
    return raw
  } catch (err) {
    return JSON.stringify({ error: `discard failed: ${String(err)}` })
  }
}

// Analysis helpers — translate VyBit patches into CassiCore-friendly context

function summarizePatch(patch: VyBitPatch): Record<string, unknown> {
  const summary: Record<string, unknown> = {
    id: patch.id,
    kind: patch.kind,
    component: patch.component?.name ?? 'unknown',
  }

  switch (patch.kind) {
    case 'class-change':
      summary.change = `${patch.originalClass} → ${patch.newClass}`
      summary.property = patch.property
      summary.element = patch.target?.tag ?? 'unknown'
      break
    case 'text-change':
      summary.originalHtml = patch.originalHtml?.slice(0, 200)
      summary.newHtml = patch.newHtml?.slice(0, 200)
      break
    case 'message':
      summary.message = patch.message
      break
    case 'design':
      summary.insertMode = patch.insertMode
      summary.canvasSize = `${patch.canvasWidth}x${patch.canvasHeight}`
      summary.componentCount = patch.canvasComponents?.length ?? 0
      summary.hasImage = !!patch.image
      break
    case 'component-drop':
      summary.componentPath = patch.componentPath
      summary.insertMode = patch.insertMode
      summary.parentComponent = patch.parentComponent?.name
      summary.args = patch.componentArgs
      break
    case 'bug-report':
      summary.description = patch.bugDescription
      summary.timelineEvents = patch.bugTimeline?.length ?? 0
      summary.screenshots = patch.bugScreenshots?.length ?? 0
      summary.element = patch.bugElement?.selectorPath
      summary.consoleErrors = countConsoleErrors(patch)
      summary.networkErrors = countNetworkErrors(patch)
      break
  }

  return summary
}

function analyzeCommit(commit: VyBitCommit): Record<string, unknown> {
  const kinds = commit.patches.map(p => p.kind)
  const components = [...new Set(commit.patches.map(p => p.component?.name).filter(Boolean))]

  const analysis: Record<string, unknown> = {
    totalPatches: commit.patches.length,
    kinds: [...new Set(kinds)],
    affectedComponents: components,
  }

  // Classify complexity for delegation decisions
  const hasBugReport = kinds.includes('bug-report')
  const hasDesign = kinds.includes('design')
  const hasComponentDrop = kinds.includes('component-drop')
  const classChangeCount = kinds.filter(k => k === 'class-change').length
  const textChangeCount = kinds.filter(k => k === 'text-change').length

  if (hasBugReport) {
    analysis.complexity = 'investigation'
    analysis.suggestedApproach = 'Delegate to Constellation with research template for root-cause analysis'
  } else if (hasDesign && hasComponentDrop) {
    analysis.complexity = 'high'
    analysis.suggestedApproach = 'Delegate to Constellation with implementation template'
  } else if (hasDesign || hasComponentDrop) {
    analysis.complexity = 'medium'
    analysis.suggestedApproach = 'Can be handled directly or delegated to a single Helix session'
  } else if (classChangeCount + textChangeCount <= 3) {
    analysis.complexity = 'low'
    analysis.suggestedApproach = 'Apply directly — simple class/text changes'
  } else {
    analysis.complexity = 'medium'
    analysis.suggestedApproach = 'Batch class changes — can be applied directly'
  }

  return analysis
}

/**
 * Build hints for how to delegate this commit to Constellation or apply directly.
 * Returns structured context that maps VyBit patch kinds to CassiCore actions.
 */
function buildDelegationHints(commit: VyBitCommit): Record<string, unknown> {
  const hints: Record<string, unknown> = { commitId: commit.id }
  const directEdits: string[] = []
  const constellationTasks: string[] = []

  for (const patch of commit.patches) {
    switch (patch.kind) {
      case 'class-change':
        directEdits.push(
          `In component ${patch.component?.name ?? '?'}, change Tailwind class ` +
          `"${patch.originalClass}" to "${patch.newClass}" on <${patch.target?.tag ?? '?'}>`,
        )
        break
      case 'text-change':
        directEdits.push(
          `In component ${patch.component?.name ?? '?'}, replace HTML content on <${patch.target?.tag ?? '?'}>`,
        )
        break
      case 'message':
        // Messages are context, not actions
        break
      case 'design':
        constellationTasks.push(
          `Implement design sketch in component ${patch.component?.name ?? '?'}: ` +
          `${patch.canvasComponents?.length ?? 0} component(s) to place, ` +
          `canvas ${patch.canvasWidth}x${patch.canvasHeight}px, ` +
          `insert ${patch.insertMode ?? 'after'} target element`,
        )
        break
      case 'component-drop':
        directEdits.push(
          `In component ${patch.parentComponent?.name ?? patch.component?.name ?? '?'}, ` +
          `add <${patch.component?.name ?? '?'}> ${patch.insertMode ?? 'after'} target element` +
          (patch.componentPath ? ` (import from ${patch.componentPath})` : ''),
        )
        break
      case 'bug-report':
        constellationTasks.push(
          `Investigate and fix bug: "${patch.bugDescription ?? 'no description'}" ` +
          `(${patch.bugTimeline?.length ?? 0} timeline events, ` +
          `${patch.bugScreenshots?.length ?? 0} screenshots, ` +
          `${countConsoleErrors(patch)} console errors, ` +
          `${countNetworkErrors(patch)} network errors)`,
        )
        break
    }
  }

  // Gather user messages as context
  const userMessages = commit.patches
    .filter(p => p.kind === 'message' && p.message)
    .map(p => p.message!)

  if (directEdits.length > 0) hints.directEdits = directEdits
  if (constellationTasks.length > 0) hints.constellationTasks = constellationTasks
  if (userMessages.length > 0) hints.userContext = userMessages

  return hints
}

function countConsoleErrors(patch: VyBitPatch): number {
  if (!patch.bugTimeline) return 0
  return patch.bugTimeline.reduce((sum, entry) => {
    return sum + (entry.consoleLogs?.filter(l => l.level === 'error').length ?? 0)
  }, 0)
}

function countNetworkErrors(patch: VyBitPatch): number {
  if (!patch.bugTimeline) return 0
  return patch.bugTimeline.reduce((sum, entry) => {
    return sum + (entry.networkErrors?.length ?? 0)
  }, 0)
}

// Bug Report Ingestion

/**
 * Ingest all bug reports from the VyBit queue.
 * Lists committed changes, filters for bug-report patches, and runs them
 * through the ingestion pipeline to produce structured investigation briefs.
 */
async function handleIngestBugs(ctx: ToolExecutionContext): Promise<string> {
  assertConnected()

  try {
    // Get all committed and implementing changes
    const raw = await vybitClient!.callTool('list_changes', {})
    const data = JSON.parse(raw)

    // Extract bug report patches from all commits
    const allPatches: Array<{
      id: string
      kind: 'bug-report'
      commitId?: string
      component?: { name: string; instanceCount?: number }
      bugDescription?: string
      bugScreenshots?: string[]
      bugTimeline?: any[]
      bugTimeRange?: { start: string; end: string }
      bugElement?: any
    }> = []

    // Iterate through all changes to find bug reports
    const changes = data.changes || data.commits || []
    for (const change of changes) {
      const patches = change.patches || []
      for (const patch of patches) {
        if (patch.kind === 'bug-report') {
          allPatches.push({
            ...patch,
            commitId: change.id || patch.commitId,
          })
        }
      }
    }

    if (allPatches.length === 0) {
      return JSON.stringify({
        status: 'no_bugs',
        message: 'No bug reports found in the VyBit queue.',
      })
    }

    // Run through the ingestion pipeline
    const briefs = ingestBugReports(allPatches, ctx.logger)

    return JSON.stringify({
      status: 'ingested',
      bugCount: briefs.length,
      briefs: briefs.map(b => ({
        bugId: b.bugId,
        summary: b.summary,
        bugType: b.bugType,
        severity: b.severity,
        affectedComponents: b.affectedComponents,
        consoleErrors: b.consoleErrors.length,
        networkFailures: b.networkFailures.length,
        screenshotCount: b.screenshotCount,
        investigationHints: b.investigationHints,
        constellationGoal: b.constellationGoal,
        formattedBrief: b.formattedBrief,
      })),
    }, null, 2)
  } catch (err) {
    return JSON.stringify({ error: `Bug ingestion failed: ${String(err)}` })
  }
}

// Guards

function assertConnected(): void {
  if (!vybitClient?.connected) {
    throw new Error(
      'VyBit is not connected. Use action "start" with a projectPath first.',
    )
  }
}

// Tool Handler (main dispatch)

export const vybitHandler: ToolHandler = async (
  input: Record<string, unknown>,
  ctx: ToolExecutionContext,
): Promise<string> => {
  const action = input.action as string

  switch (action) {
    // Session management (full setup/teardown)
    case 'session':
      return handleSession(input, ctx, handleStart)
    case 'session_stop': {
      // Stop both VyBit and dev server
      const stopResult = JSON.parse(await handleSessionStop(ctx))
      const vybitStopResult = JSON.parse(await handleStop(ctx))
      return JSON.stringify({
        ...stopResult,
        vybit: vybitStopResult,
      })
    }

    // VyBit MCP server lifecycle
    case 'start':
      return handleStart(input, ctx)
    case 'stop':
      return handleStop(ctx)
    case 'status':
      return handleStatus()

    // Change queue operations
    case 'poll':
      return handlePoll(ctx)
    case 'implement_next':
      return handleImplementNext(ctx)
    case 'mark_done':
      return handleMarkDone(input, ctx)
    case 'list':
      return handleList(input)
    case 'discard':
      return handleDiscard()

    // Dev server management
    case 'dev_start':
      return handleDevStart(input, ctx)
    case 'dev_stop':
      return handleDevStop(ctx)

    // Overlay injection
    case 'inject_overlay':
      return handleInjectOverlay(input, ctx)

    // Browser launch
    case 'browser_open':
      return handleBrowserOpen(input, ctx)

    // Bug report ingestion
    case 'ingest_bugs':
      return handleIngestBugs(ctx)

    default:
      return JSON.stringify({
        error: `Unknown action: ${action}`,
        validActions: [
          'session', 'session_stop',
          'start', 'stop', 'status', 'poll', 'list', 'implement_next', 'mark_done', 'discard',
          'dev_start', 'dev_stop', 'inject_overlay', 'browser_open',
          'ingest_bugs',
        ],
      })
  }
}
