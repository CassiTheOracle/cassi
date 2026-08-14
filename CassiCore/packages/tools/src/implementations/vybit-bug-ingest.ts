/**
 * VyBit Bug Report Ingestion Pipeline
 *
 * Parses VyBit's rich bug report data (timeline events, DOM snapshots,
 * console errors, network failures, screenshots) and transforms them
 * into structured investigation briefs for CassiCore.
 *
 * Pipeline stages:
 *   1. Parse — extract structured signals from the raw bug report
 *   2. Analyze — classify bug type, severity, and affected components
 *   3. Contextualize — assemble relevant code context for investigation
 *   4. Brief — produce a formatted investigation brief for the agent
 *   5. Store — save the bug pattern in memory for future reference
 *
 * The output can be used directly by the agent or delegated to
 * a Constellation session for deep root-cause analysis.
 */

import { getEventBus } from '../vendor/core/events/index.js'

import type { ILogger } from "@cassicore/foundation"

// Input types (mirror VyBit's bug report structure)

interface VyBitBugPatch {
  id: string
  kind: 'bug-report'
  commitId?: string
  component?: { name: string; instanceCount?: number }
  bugDescription?: string
  bugScreenshots?: string[]
  bugTimeline?: BugTimelineEntry[]
  bugTimeRange?: { start: string; end: string }
  bugElement?: BugElement | null
}

interface BugTimelineEntry {
  timestamp: string
  trigger: string
  url: string
  consoleLogs?: ConsoleLogEntry[]
  networkErrors?: NetworkErrorEntry[]
  domChanges?: DomChangeEntry[]
  domSnapshot?: string
  domDiff?: string
  hasScreenshot?: boolean
  elementInfo?: { tag: string; classes: string }
}

interface ConsoleLogEntry {
  level: string
  args: string[]
  stack?: string
}

interface NetworkErrorEntry {
  url: string
  method: string
  status?: number
  errorMessage?: string
}

interface DomChangeEntry {
  type: string
  selector: string
  componentName?: string
}

interface BugElement {
  tag: string
  selectorPath: string
  componentName?: string
  outerHTML: string
  boundingBox: { x: number; y: number; width: number; height: number }
}

// Output types

export interface BugInvestigationBrief {
  /** Unique ID for this bug report */
  bugId: string
  /** One-line summary of the bug */
  summary: string
  /** User's original description */
  userDescription: string
  /** Classified bug type */
  bugType: BugType
  /** Severity assessment */
  severity: BugSeverity
  /** Affected component(s) */
  affectedComponents: string[]
  /** Extracted console errors with stack traces */
  consoleErrors: ExtractedError[]
  /** Extracted network failures */
  networkFailures: ExtractedNetworkError[]
  /** DOM mutations that may be relevant */
  domMutations: ExtractedDomMutation[]
  /** Timeline summary (key events in chronological order) */
  timelineSummary: TimelineEvent[]
  /** The bug-reporting element's location */
  element: {
    selector: string
    component: string | null
    tag: string
    htmlSnippet: string
  } | null
  /** Number of screenshots available */
  screenshotCount: number
  /** Time range of the bug (if captured) */
  timeRange: { start: string; end: string } | null
  /** Investigation hints — suggested first steps */
  investigationHints: string[]
  /** Formatted brief for direct agent consumption */
  formattedBrief: string
  /** Constellation task description if delegating */
  constellationGoal: string
}

type BugType =
  | 'runtime-error'      // Console errors / unhandled exceptions
  | 'network-error'      // API / fetch failures
  | 'visual-regression'  // DOM changes causing visual issues
  | 'interaction-bug'    // Click/input not working as expected
  | 'performance'        // Slow rendering, jank
  | 'unknown'            // Cannot classify

type BugSeverity = 'critical' | 'high' | 'medium' | 'low'

interface ExtractedError {
  message: string
  stack: string | null
  /** Which timeline entry this came from */
  timelineIndex: number
  /** Trigger that caused the error */
  trigger: string
  /** URL where the error occurred */
  url: string
}

interface ExtractedNetworkError {
  url: string
  method: string
  status: number | null
  errorMessage: string | null
  timelineIndex: number
  trigger: string
}

interface ExtractedDomMutation {
  type: string
  selector: string
  component: string | null
  timelineIndex: number
}

interface TimelineEvent {
  index: number
  timestamp: string
  trigger: string
  url: string
  errorCount: number
  networkErrorCount: number
  domChangeCount: number
  hasDomDiff: boolean
  hasDomSnapshot: boolean
}

// Stage 1: Parse — extract structured signals

function extractConsoleErrors(timeline: BugTimelineEntry[]): ExtractedError[] {
  const errors: ExtractedError[] = []

  for (let i = 0; i < timeline.length; i++) {
    const entry = timeline[i]
    if (!entry.consoleLogs) continue

    for (const log of entry.consoleLogs) {
      if (log.level === 'error' || log.level === 'warn') {
        errors.push({
          message: log.args.join(' ').slice(0, 1000),
          stack: log.stack?.slice(0, 2000) ?? null,
          timelineIndex: i,
          trigger: entry.trigger,
          url: entry.url,
        })
      }
    }
  }

  return errors
}

function extractNetworkErrors(timeline: BugTimelineEntry[]): ExtractedNetworkError[] {
  const errors: ExtractedNetworkError[] = []

  for (let i = 0; i < timeline.length; i++) {
    const entry = timeline[i]
    if (!entry.networkErrors) continue

    for (const netErr of entry.networkErrors) {
      errors.push({
        url: netErr.url,
        method: netErr.method,
        status: netErr.status ?? null,
        errorMessage: netErr.errorMessage ?? null,
        timelineIndex: i,
        trigger: entry.trigger,
      })
    }
  }

  return errors
}

function extractDomMutations(timeline: BugTimelineEntry[]): ExtractedDomMutation[] {
  const mutations: ExtractedDomMutation[] = []

  for (let i = 0; i < timeline.length; i++) {
    const entry = timeline[i]
    if (!entry.domChanges) continue

    for (const change of entry.domChanges) {
      mutations.push({
        type: change.type,
        selector: change.selector,
        component: change.componentName ?? null,
        timelineIndex: i,
      })
    }
  }

  return mutations
}

function buildTimelineSummary(timeline: BugTimelineEntry[]): TimelineEvent[] {
  return timeline.map((entry, i) => ({
    index: i,
    timestamp: entry.timestamp,
    trigger: entry.trigger,
    url: entry.url,
    errorCount: entry.consoleLogs?.filter(l => l.level === 'error').length ?? 0,
    networkErrorCount: entry.networkErrors?.length ?? 0,
    domChangeCount: entry.domChanges?.length ?? 0,
    hasDomDiff: !!entry.domDiff,
    hasDomSnapshot: !!entry.domSnapshot,
  }))
}

// Stage 2: Analyze — classify bug type and severity

function classifyBugType(
  consoleErrors: ExtractedError[],
  networkErrors: ExtractedNetworkError[],
  domMutations: ExtractedDomMutation[],
  description: string,
): BugType {
  const descLower = description.toLowerCase()

  // Check for runtime errors (highest signal)
  if (consoleErrors.some(e => e.message.includes('Uncaught') || e.message.includes('TypeError') ||
    e.message.includes('ReferenceError') || e.message.includes('Cannot read'))) {
    return 'runtime-error'
  }

  // Check for network errors
  if (networkErrors.length > 0) {
    return 'network-error'
  }

  // Check for console errors (general)
  if (consoleErrors.length > 0) {
    return 'runtime-error'
  }

  // Check for visual regression indicators
  if (domMutations.length > 0 || descLower.includes('look') || descLower.includes('display') ||
    descLower.includes('style') || descLower.includes('layout') || descLower.includes('visual')) {
    return 'visual-regression'
  }

  // Check for interaction keywords
  if (descLower.includes('click') || descLower.includes('input') || descLower.includes('button') ||
    descLower.includes('submit') || descLower.includes('navigate') || descLower.includes('scroll')) {
    return 'interaction-bug'
  }

  // Check for performance keywords
  if (descLower.includes('slow') || descLower.includes('lag') || descLower.includes('freeze') ||
    descLower.includes('performance') || descLower.includes('jank')) {
    return 'performance'
  }

  return 'unknown'
}

function assessSeverity(
  bugType: BugType,
  consoleErrors: ExtractedError[],
  networkErrors: ExtractedNetworkError[],
): BugSeverity {
  // Critical: unhandled exceptions or 5xx server errors
  if (consoleErrors.some(e => e.message.includes('Uncaught') || e.stack?.includes('Uncaught'))) {
    return 'critical'
  }
  if (networkErrors.some(e => e.status && e.status >= 500)) {
    return 'critical'
  }

  // High: multiple errors or TypeError/ReferenceError
  if (consoleErrors.length >= 3 || networkErrors.length >= 3) {
    return 'high'
  }
  if (consoleErrors.some(e => e.message.includes('TypeError') || e.message.includes('ReferenceError'))) {
    return 'high'
  }

  // Medium: some errors
  if (consoleErrors.length > 0 || networkErrors.length > 0) {
    return 'medium'
  }

  // Low: visual/interaction bugs with no errors
  return 'low'
}

// Stage 3: Build investigation hints

function buildInvestigationHints(
  bugType: BugType,
  consoleErrors: ExtractedError[],
  networkErrors: ExtractedNetworkError[],
  domMutations: ExtractedDomMutation[],
  element: BugElement | null | undefined,
): string[] {
  const hints: string[] = []

  switch (bugType) {
    case 'runtime-error':
      if (consoleErrors.length > 0) {
        const firstError = consoleErrors[0]
        hints.push(`Start from the first console error: "${firstError.message.slice(0, 100)}"`)
        if (firstError.stack) {
          // Extract file references from stack trace
          const fileRefs = firstError.stack.match(/(?:at\s+)?[\w.]+\s+\(?([\w/.-]+\.(?:ts|tsx|js|jsx)):\d+/g)
          if (fileRefs && fileRefs.length > 0) {
            hints.push(`Stack trace references: ${fileRefs.slice(0, 3).join(', ')}`)
          }
        }
        hints.push(`Error occurred during "${firstError.trigger}" action at ${firstError.url}`)
      }
      break

    case 'network-error':
      if (networkErrors.length > 0) {
        const first = networkErrors[0]
        hints.push(`First failing request: ${first.method} ${first.url} → ${first.status ?? 'no response'}`)
        if (first.errorMessage) {
          hints.push(`Network error: ${first.errorMessage}`)
        }
        hints.push('Check API route handler, request payload, CORS config, and backend server status')
      }
      break

    case 'visual-regression':
      if (domMutations.length > 0) {
        const components = [...new Set(domMutations.map(m => m.component).filter(Boolean))]
        if (components.length > 0) {
          hints.push(`DOM mutations in components: ${components.join(', ')}`)
        }
        hints.push('Compare current DOM snapshot with expected layout')
      }
      hints.push('Check Tailwind classes, conditional rendering, and CSS specificity')
      break

    case 'interaction-bug':
      hints.push('Check event handlers, state updates, and conditional rendering')
      if (element?.componentName) {
        hints.push(`Bug reported on element in ${element.componentName} — check event handler bindings`)
      }
      break

    case 'performance':
      hints.push('Profile the component with React DevTools or browser Performance tab')
      hints.push('Check for excessive re-renders, missing memoization, or large list rendering')
      break

    case 'unknown':
      hints.push('Review the timeline events chronologically for the triggering action')
      break
  }

  // Add element-specific hints
  if (element) {
    hints.push(`Bug element: <${element.tag}> at ${element.selectorPath}`)
    if (element.componentName) {
      hints.push(`Component: ${element.componentName} — search for this component file`)
    }
  }

  return hints
}

// Stage 4: Format the investigation brief

function formatBrief(brief: Omit<BugInvestigationBrief, 'formattedBrief' | 'constellationGoal'>): {
  formattedBrief: string
  constellationGoal: string
} {
  const lines: string[] = []

  lines.push(`# Bug Report: ${brief.summary}`)
  lines.push('')
  lines.push(`**Type:** ${brief.bugType} | **Severity:** ${brief.severity} | **Screenshots:** ${brief.screenshotCount}`)
  lines.push('')
  lines.push(`## User Description`)
  lines.push(brief.userDescription || '(no description)')
  lines.push('')

  if (brief.affectedComponents.length > 0) {
    lines.push(`## Affected Components`)
    lines.push(brief.affectedComponents.map(c => `- ${c}`).join('\n'))
    lines.push('')
  }

  if (brief.consoleErrors.length > 0) {
    lines.push(`## Console Errors (${brief.consoleErrors.length})`)
    for (const err of brief.consoleErrors.slice(0, 5)) {
      lines.push(`### Error during "${err.trigger}"`)
      lines.push('```')
      lines.push(err.message)
      if (err.stack) {
        lines.push('')
        lines.push(err.stack.split('\n').slice(0, 5).join('\n'))
      }
      lines.push('```')
      lines.push('')
    }
  }

  if (brief.networkFailures.length > 0) {
    lines.push(`## Network Failures (${brief.networkFailures.length})`)
    for (const err of brief.networkFailures.slice(0, 5)) {
      lines.push(`- **${err.method} ${err.url}** → ${err.status ?? 'no response'}${err.errorMessage ? ` (${err.errorMessage})` : ''}`)
    }
    lines.push('')
  }

  if (brief.domMutations.length > 0) {
    lines.push(`## DOM Mutations (${brief.domMutations.length})`)
    for (const mut of brief.domMutations.slice(0, 10)) {
      lines.push(`- [${mut.type}] ${mut.selector}${mut.component ? ` (${mut.component})` : ''}`)
    }
    lines.push('')
  }

  if (brief.element) {
    lines.push(`## Bug Element`)
    lines.push(`- **Tag:** <${brief.element.tag}>`)
    lines.push(`- **Selector:** ${brief.element.selector}`)
    if (brief.element.component) {
      lines.push(`- **Component:** ${brief.element.component}`)
    }
    lines.push(`- **HTML:** \`${brief.element.htmlSnippet}\``)
    lines.push('')
  }

  if (brief.timelineSummary.length > 0) {
    lines.push(`## Timeline (${brief.timelineSummary.length} events)`)
    for (const evt of brief.timelineSummary) {
      const flags: string[] = []
      if (evt.errorCount > 0) flags.push(`${evt.errorCount} error(s)`)
      if (evt.networkErrorCount > 0) flags.push(`${evt.networkErrorCount} net error(s)`)
      if (evt.domChangeCount > 0) flags.push(`${evt.domChangeCount} DOM change(s)`)
      if (evt.hasDomDiff) flags.push('has DOM diff')
      const flagStr = flags.length > 0 ? ` [${flags.join(', ')}]` : ''
      lines.push(`${evt.index + 1}. **${evt.trigger}** at ${evt.url}${flagStr}`)
    }
    lines.push('')
  }

  lines.push(`## Investigation Hints`)
  for (const hint of brief.investigationHints) {
    lines.push(`- ${hint}`)
  }

  const formattedBrief = lines.join('\n')

  // Build a concise Constellation goal
  const goalParts: string[] = [
    `Investigate and fix bug: "${brief.summary}"`,
  ]
  if (brief.affectedComponents.length > 0) {
    goalParts.push(`Affected components: ${brief.affectedComponents.join(', ')}`)
  }
  if (brief.consoleErrors.length > 0) {
    goalParts.push(`${brief.consoleErrors.length} console error(s), first: "${brief.consoleErrors[0].message.slice(0, 100)}"`)
  }
  if (brief.networkFailures.length > 0) {
    goalParts.push(`${brief.networkFailures.length} network failure(s)`)
  }
  goalParts.push(`Severity: ${brief.severity}`)

  return {
    formattedBrief,
    constellationGoal: goalParts.join('. '),
  }
}

// Main Pipeline

/**
 * Ingest a VyBit bug report patch and produce a structured investigation brief.
 *
 * This is the main entry point for the bug ingestion pipeline.
 * Call it with a bug-report patch from VyBit's change queue.
 */
export function ingestBugReport(
  patch: VyBitBugPatch,
  logger?: ILogger,
): BugInvestigationBrief {
  const description = patch.bugDescription || '(no description)'
  const timeline = patch.bugTimeline || []

  // Stage 1: Parse
  const consoleErrors = extractConsoleErrors(timeline)
  const networkErrors = extractNetworkErrors(timeline)
  const domMutations = extractDomMutations(timeline)
  const timelineSummary = buildTimelineSummary(timeline)

  // Stage 2: Analyze
  const bugType = classifyBugType(consoleErrors, networkErrors, domMutations, description)
  const severity = assessSeverity(bugType, consoleErrors, networkErrors)

  // Collect affected components
  const components = new Set<string>()
  if (patch.component?.name) components.add(patch.component.name)
  if (patch.bugElement?.componentName) components.add(patch.bugElement.componentName)
  for (const mut of domMutations) {
    if (mut.component) components.add(mut.component)
  }

  // Build element info
  const element = patch.bugElement ? {
    selector: patch.bugElement.selectorPath,
    component: patch.bugElement.componentName ?? null,
    tag: patch.bugElement.tag,
    htmlSnippet: patch.bugElement.outerHTML.slice(0, 300),
  } : null

  // Stage 3: Investigation hints
  const investigationHints = buildInvestigationHints(
    bugType, consoleErrors, networkErrors, domMutations, patch.bugElement,
  )

  // Build summary
  const summary = buildSummary(bugType, description, consoleErrors, networkErrors, patch.bugElement)

  // Stage 4: Format
  const baseBrief = {
    bugId: patch.id,
    summary,
    userDescription: description,
    bugType,
    severity,
    affectedComponents: [...components],
    consoleErrors,
    networkFailures: networkErrors,
    domMutations,
    timelineSummary,
    element,
    screenshotCount: patch.bugScreenshots?.length ?? 0,
    timeRange: patch.bugTimeRange ?? null,
    investigationHints,
  }

  const { formattedBrief, constellationGoal } = formatBrief(baseBrief)

  // Emit event
  const bus = getEventBus()
  if (bus) {
    bus.emit({
      type: 'vybit:bug_report',
      commitId: patch.commitId ?? patch.id,
      description: summary,
      hasTimeline: timeline.length > 0,
      hasScreenshots: (patch.bugScreenshots?.length ?? 0) > 0,
      timestamp: new Date(),
    })
  }

  if (logger) {
    logger.info(`[vybit] Bug report ingested: ${summary}`, {
      bugId: patch.id,
      bugType,
      severity,
      consoleErrors: consoleErrors.length,
      networkErrors: networkErrors.length,
      domMutations: domMutations.length,
    })
  }

  return {
    ...baseBrief,
    formattedBrief,
    constellationGoal,
  }
}

/**
 * Build a concise one-line summary from the bug data.
 */
function buildSummary(
  bugType: BugType,
  description: string,
  consoleErrors: ExtractedError[],
  networkErrors: ExtractedNetworkError[],
  element: BugElement | null | undefined,
): string {
  // If user gave a good description, use it
  if (description && description.length > 10 && description !== '(no description)') {
    return description.length > 100 ? description.slice(0, 97) + '...' : description
  }

  // Auto-generate from signals
  const component = element?.componentName ? ` in ${element.componentName}` : ''

  switch (bugType) {
    case 'runtime-error':
      if (consoleErrors.length > 0) {
        const msg = consoleErrors[0].message.slice(0, 80)
        return `Runtime error${component}: ${msg}`
      }
      return `Runtime error${component}`

    case 'network-error':
      if (networkErrors.length > 0) {
        const first = networkErrors[0]
        let urlPath: string
        try {
          urlPath = new URL(first.url).pathname
        } catch {
          urlPath = first.url
        }
        return `${first.method} ${urlPath} failed (${first.status ?? 'no response'})${component}`
      }
      return `Network error${component}`

    case 'visual-regression':
      return `Visual regression${component}`

    case 'interaction-bug':
      return `Interaction bug${component}`

    case 'performance':
      return `Performance issue${component}`

    default:
      return `Bug report${component}`
  }
}

// Batch processing helper

/**
 * Process all bug-report patches from a VyBit commit.
 * Returns an array of investigation briefs.
 */
export function ingestBugReports(
  patches: VyBitBugPatch[],
  logger?: ILogger,
): BugInvestigationBrief[] {
  return patches
    .filter(p => p.kind === 'bug-report')
    .map(p => ingestBugReport(p, logger))
}
