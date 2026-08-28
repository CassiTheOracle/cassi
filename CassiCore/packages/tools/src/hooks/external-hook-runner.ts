/**
 * External Hook Runner
 *
 * Executes user-defined shell hooks before and after tool execution.
 * Inspired by Claude Code's hook protocol:
 *
 * - Exit 0 = allow (stdout becomes feedback message)
 * - Exit 2 = deny  (stdout becomes deny reason)
 * - Any other exit code = warn but allow
 *
 * Hooks receive context via environment variables:
 *   HOOK_EVENT       — "PreToolUse" or "PostToolUse"
 *   HOOK_TOOL_NAME   — Name of the tool being called
 *   HOOK_TOOL_INPUT  — JSON string of the tool input
 *   HOOK_TOOL_OUTPUT — Tool output (PostToolUse only)
 *   HOOK_TOOL_IS_ERROR — "1" if tool errored, "0" otherwise (PostToolUse only)
 *
 * The full payload is also piped via stdin as JSON.
 */

import { execFile } from 'node:child_process'
import type { ILogger } from "@cassicore/foundation"

export type HookEvent = 'PreToolUse' | 'PostToolUse'

export interface HookRunResult {
  /** Whether the hook denied the tool execution */
  denied: boolean
  /** Messages from hook stdout (feedback/deny reasons) */
  messages: string[]
}

export interface ExternalHookConfig {
  preToolUse: string[]
  postToolUse: string[]
  /** Maximum time per hook command in ms. Default 5000. */
  timeoutMs?: number
}

export const EMPTY_HOOK_CONFIG: ExternalHookConfig = {
  preToolUse: [],
  postToolUse: [],
}

export class ExternalHookRunner {
  private config: ExternalHookConfig
  private timeoutMs: number
  private logger: ILogger

  constructor(config: ExternalHookConfig, logger: ILogger) {
    this.config = config
    this.timeoutMs = config.timeoutMs ?? 5_000
    this.logger = logger.child('external-hooks')
  }

  /** Update hook configuration at runtime (hot-reload safe). */
  updateConfig(config: ExternalHookConfig): void {
    this.config = config
    this.timeoutMs = config.timeoutMs ?? 5_000
  }

  /** Run PreToolUse hooks. Returns allow/deny + messages. */
  async runPreToolUse(
    toolName: string,
    toolInput: Record<string, unknown>,
  ): Promise<HookRunResult> {
    return this.runCommands('PreToolUse', this.config.preToolUse, {
      toolName,
      toolInput,
    })
  }

  /** Run PostToolUse hooks. Returns allow/deny + messages. */
  async runPostToolUse(
    toolName: string,
    toolInput: Record<string, unknown>,
    toolOutput: string,
    isError: boolean,
  ): Promise<HookRunResult> {
    return this.runCommands('PostToolUse', this.config.postToolUse, {
      toolName,
      toolInput,
      toolOutput,
      isError,
    })
  }

  /** Returns true if any hooks are configured. */
  hasHooks(): boolean {
    return this.config.preToolUse.length > 0 || this.config.postToolUse.length > 0
  }

  private async runCommands(
    event: HookEvent,
    commands: string[],
    context: {
      toolName: string
      toolInput: Record<string, unknown>
      toolOutput?: string
      isError?: boolean
    },
  ): Promise<HookRunResult> {
    if (commands.length === 0) {
      return { denied: false, messages: [] }
    }

    const payload = JSON.stringify({
      hook_event_name: event,
      tool_name: context.toolName,
      tool_input: context.toolInput,
      tool_input_json: JSON.stringify(context.toolInput),
      tool_output: context.toolOutput ?? null,
      tool_result_is_error: context.isError ?? false,
    })

    const messages: string[] = []

    for (const command of commands) {
      const outcome = await this.runSingleCommand(command, event, context, payload)

      switch (outcome.type) {
        case 'allow':
          if (outcome.message) messages.push(outcome.message)
          break
        case 'deny': {
          const msg = outcome.message ?? `${event} hook denied tool \`${context.toolName}\``
          messages.push(msg)
          return { denied: true, messages }
        }
        case 'warn':
          messages.push(outcome.message)
          break
      }
    }

    return { denied: false, messages }
  }

  private async runSingleCommand(
    command: string,
    event: HookEvent,
    context: {
      toolName: string
      toolInput: Record<string, unknown>
      toolOutput?: string
      isError?: boolean
    },
    payload: string,
  ): Promise<HookCommandOutcome> {
    const env: Record<string, string> = {
      ...process.env,
      HOOK_EVENT: event,
      HOOK_TOOL_NAME: context.toolName,
      HOOK_TOOL_INPUT: JSON.stringify(context.toolInput),
      HOOK_TOOL_IS_ERROR: context.isError ? '1' : '0',
    }
    if (context.toolOutput !== undefined) {
      env.HOOK_TOOL_OUTPUT = context.toolOutput
    }

    return new Promise<HookCommandOutcome>(resolve => {
      try {
        const child = execFile('sh', ['-lc', command], {
          env,
          timeout: this.timeoutMs,
          maxBuffer: 1024 * 64, // 64KB
        }, (err, stdout, stderr) => {
          const stdoutTrimmed = (stdout ?? '').trim()
          const stderrTrimmed = (stderr ?? '').trim()

          if (err && 'killed' in err && err.killed) {
            // Timed out
            resolve({
              type: 'warn',
              message: `${event} hook \`${command}\` timed out after ${this.timeoutMs}ms for \`${context.toolName}\``,
            })
            return
          }

          const code = err && 'code' in err ? (err as any).code : 0

          if (code === 0) {
            resolve({ type: 'allow', message: stdoutTrimmed || undefined })
          } else if (code === 2) {
            resolve({ type: 'deny', message: stdoutTrimmed || undefined })
          } else {
            resolve({
              type: 'warn',
              message: formatHookWarning(command, code, stdoutTrimmed, stderrTrimmed),
            })
          }
        })

        // Pipe payload via stdin
        if (child.stdin) {
          child.stdin.write(payload)
          child.stdin.end()
        }
      } catch (err) {
        this.logger.error('hook spawn error', { command, event, error: String(err) })
        resolve({
          type: 'warn',
          message: `${event} hook \`${command}\` failed to start for \`${context.toolName}\`: ${String(err)}`,
        })
      }
    })
  }
}

type HookCommandOutcome =
  | { type: 'allow'; message?: string }
  | { type: 'deny'; message?: string }
  | { type: 'warn'; message: string }

function formatHookWarning(
  command: string,
  code: number,
  stdout: string,
  stderr: string,
): string {
  let msg = `Hook \`${command}\` exited with status ${code}; allowing tool execution to continue`
  if (stdout) {
    msg += ': ' + stdout
  } else if (stderr) {
    msg += ': ' + stderr
  }
  return msg
}

// HOW: Merges hook feedback messages into tool output by appending them
// after the tool's original output with a labeled section header
export function mergeHookFeedback(
  hookMessages: string[],
  toolOutput: string,
  denied: boolean,
): string {
  if (hookMessages.length === 0) return toolOutput

  const sections: string[] = []
  if (toolOutput.trim()) sections.push(toolOutput)

  const label = denied ? 'Hook feedback (denied)' : 'Hook feedback'
  sections.push(`${label}:\n${hookMessages.join('\n')}`)
  return sections.join('\n\n')
}
