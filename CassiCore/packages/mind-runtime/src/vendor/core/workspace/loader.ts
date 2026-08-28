/**
 * WorkspaceLoader — reads persona + user files from the workspace
 * and composes a system prompt for new sessions.
 *
 * Reads (in order, all optional):
 *   IDENTITY.md  — name, creature, emoji
 *   SOUL.md      — who I am, principles, vibe
 *   USER.md      — who Valerie is
 *   MEMORY.md    — index (truncated)
 *
 * Falls back gracefully if files are missing.
 */

import { readFileSync, existsSync, writeFileSync, mkdirSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'

import type { ILogger } from '@cassicore/foundation'

const WORKSPACE = join(homedir(), '.cassi')
const MAX_MEMORY_LINES = 200  // keep MEMORY.md index reasonably sized

/** Files to include in system prompt, in order */
const PERSONA_FILES: Array<{ path: string; label: string }> = [
  { path: join(WORKSPACE, 'IDENTITY.md'), label: 'IDENTITY' },
  { path: join(WORKSPACE, 'SOUL.md'),     label: 'SOUL' },
  { path: join(WORKSPACE, 'USER.md'),     label: 'USER' },
  { path: join(WORKSPACE, 'MEMORY.md'),  label: 'MEMORY_INDEX' },
]

/**
 * @dep callers: buildSystemPromptSections (core/workspace/loader.ts), buildSystemPrompt (core/workspace/loader.ts)
 * @dep module: Workspace
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

function readTruncated(filePath: string, maxLines?: number): string {
  if (!existsSync(filePath)) return ''
  try {
    const text = readFileSync(filePath, 'utf8')
    if (!maxLines) return text
    const lines = text.split('\n')
    if (lines.length <= maxLines) return text
    return `${lines.slice(0, maxLines).join('\n')  }\n\n[... ${lines.length - maxLines} more lines truncated]`
  } catch { return '' }
}

/**
 * @dep callers: loadSystemPrompt (core/pipeline/adapter/SessionPipeline.ts), start (core/daemon.ts), handleSystemPromptRoutes (core/admin-api/system-prompt.ts), reloadSystemPrompt (core/workspace/loader.ts)
 * @dep calls: trim, readTruncated
 * @dep module: Workspace
 * @dep risk: MEDIUM | 4 callers, 0 flows, 1 module
 */

export function buildSystemPrompt(logger?: ILogger): string {
  const sections: string[] = []

  // Preamble
  sections.push(`You are Cassandra — a personal AI assistant running on CassiCore, your own custom runtime.
Current date/time: ${new Date().toLocaleString('en-US', { timeZone: 'America/Los_Angeles', weekday: 'long', year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZoneName: 'short' })}
Workspace: ${WORKSPACE}
`)

  // Load each persona file
  for (const { path: filePath, label } of PERSONA_FILES) {
    const maxLines = label === 'MEMORY_INDEX' ? MAX_MEMORY_LINES : undefined
    const content = readTruncated(filePath, maxLines)
    if (content.trim()) {
      sections.push(`## ${label}\n${content}`)
      logger?.info(`[workspace-loader] loaded ${label} (${content.length} chars)`)
    } else {
      logger?.info(`[workspace-loader] skipped ${label} (not found or empty)`)
    }
  }

  // Tool guidance
  sections.push(`## TOOLS
You have access to tools. Use them freely — they are your hands.
- shell_exec: run bash commands (captures stdout+stderr, timeout enforced)
- read_file: read a single file (offset/limit supported)
- read_files: read multiple files in ONE tool call — prefer this when reading 2+ files
- write_file: create or overwrite files
- web_fetch: fetch URLs as plain text
- memory_search: search your memory database
- list_sessions: list active CassiCore sessions

## CODE INTELLIGENCE (SERENA & SCIP)
You have advanced code intelligence tools. ALWAYS prefer these for code exploration and editing:
- serena__find_symbol: Find functions, classes, and variables by name (semantic)
- serena__read_symbol: Read the full body of a symbol without needing line numbers
- serena__list_files: Browse the codebase structure efficiently
- serena__replace_symbol_body: Modify code by symbol name — safer than manual editing
- scip__find_references: Find all usages of a symbol across the project

## TOOL USE STRATEGY — CRITICAL FOR EFFICIENCY
Each tool-call round is an API request. Minimize rounds by batching:

✅ DO: Call all tools you need in ONE response. If you need to read 3 files and run a command — return all 4 tool calls together in one response.
✅ DO: Use Serena/SCIP tools first to map the codebase before reading individual files.
✅ DO: Use shell_exec for complex multi-step operations (pipe, grep, awk) rather than chaining single commands.
❌ DON'T: Call one tool, wait for the result, then call another if you could have predicted you'd need both.
❌ DON'T: Guess file paths — use serena__list_files or ls to find them first.

Example (BAD — 3 rounds):
  Round 1: read_file("MEMORY.md")
  Round 2: read_file("memory/projects/cassicore.md")
  Round 3: shell_exec("ls ~/workspaces/Cassi/CassiCore")

Example (GOOD — 1 round):
  Round 1: read_file("MEMORY.md") + read_file("memory/projects/cassiecore.md") + shell_exec("ls ~/Workspaces/CassieCore")

## RESPONSE STYLE — NATURAL TOOL INTEGRATION
When using tools, integrate them seamlessly into your response:

✅ DO: Jump directly into tool calls when action is needed
✅ DO: Provide brief context only when it adds clarity
✅ DO: Let tool results speak for themselves
❌ DON'T: Use filler phrases like "Let me check...", "I'll verify...", "I'll run this now..."
❌ DON't: Announce what you're about to do before doing it
❌ DON'T: Say "I'm going to use [tool]" — just use the tool

Example (BAD — verbose preamble):
  "I'll check this now. Let me verify the files exist and see what's in the directory. I'll use the ls tool to list the contents."
  [tool_use: ls]

Example (GOOD — direct action):
  [tool_use: ls]

Example (GOOD — minimal context when helpful):
  Checking the workspace structure:
  [tool_use: ls]

## STYLE
Be the assistant described in SOUL.md. Direct, competent, genuine. Skip filler phrases.
When working: show your actions, explain briefly, deliver results.`)

  return sections.join('\n\n---\n\n')
}

/** Return individual persona sections for the admin API */
export interface PersonaSection {
  label: string
  content: string
  source: string
  charCount: number
}

export function buildSystemPromptSections(logger?: ILogger): PersonaSection[] {
  const results: PersonaSection[] = []

  for (const { path: filePath, label } of PERSONA_FILES) {
    const maxLines = label === 'MEMORY_INDEX' ? MAX_MEMORY_LINES : undefined
    const content = readTruncated(filePath, maxLines)
    results.push({
      label,
      content: content.trim(),
      source: filePath,
      charCount: content.trim().length,
    })
    if (content.trim()) {
      logger?.info(`[workspace-loader] section ${label} (${content.trim().length} chars)`)
    }
  }

  return results
}

/** Write a persona section back to disk */
export function writePersonaSection(label: string, content: string, logger?: ILogger): boolean {
  const entry = PERSONA_FILES.find(f => f.label === label)
  if (!entry) {
    logger?.error(`[workspace-loader] unknown persona section: ${label}`)
    return false
  }
  try {
    mkdirSync(WORKSPACE, { recursive: true })
    writeFileSync(entry.path, content, 'utf8')
    logger?.info(`[workspace-loader] wrote ${label} (${content.length} chars) to ${entry.path}`)
    return true
  } catch (err) {
    logger?.error(`[workspace-loader] failed to write ${label}`, { error: String(err) })
    return false
  }
}

/** Reload the system prompt (call on SIGHUP or file-change) */
export function reloadSystemPrompt(logger?: ILogger): string {
  logger?.info('[workspace-loader] reloading system prompt')
  return buildSystemPrompt(logger)
}
