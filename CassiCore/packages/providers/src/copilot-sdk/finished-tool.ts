/**
 * Warm Session State + `finished()` Tool — Infinite Session Pattern
 *
 * Keeps Copilot SDK sessions alive across iterations by blocking the
 * `finished()` tool handler via a deferred Promise. When the caller
 * has new work, it resolves the deferred with the new prompt, and
 * the agent seamlessly continues within the SAME `sendAndWait()` call.
 *
 * This collapses all iterations into a single premium request for billing.
 *
 * @dep callers: complete (core/providers/copilot-sdk/provider.ts)
 */
import type { Tool as SdkTool } from '@github/copilot-sdk'
import type { ILogger } from '../../../types/interfaces.js'

// ─── Deferred Promise utility ───────────────────────────────────────

export interface Deferred<T> {
  promise: Promise<T>
  resolve: (value: T) => void
  reject: (err: Error) => void
  isSettled: boolean
}

export function createDeferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void
  let reject!: (err: Error) => void
  const d: Partial<Deferred<T>> = { isSettled: false }
  d.promise = new Promise<T>((res, rej) => {
    resolve = (v: T) => { d.isSettled = true; res(v) }
    reject = (e: Error) => { d.isSettled = true; rej(e) }
  })
  d.resolve = resolve
  d.reject = reject
  return d as Deferred<T>
}

// ─── Iteration result ───────────────────────────────────────────────

export interface IterationResult {
  /** The agent's reported result text */
  result: string
  /** Which iteration number this was (1-based) */
  iterationNumber: number
  /** When finished() was called */
  timestamp: number
}

// ─── Warm Session State ─────────────────────────────────────────────

/**
 * Mutable state for a warm (kept-alive) SDK session.
 *
 * Lifecycle:
 *   1. Created when a warm session starts its first iteration
 *   2. `isBlocked = true` when the agent calls finished() and the handler is awaiting resume
 *   3. `resume(prompt)` resolves the blocked handler, starting the next iteration
 *   4. `waitForFinished()` returns a Promise that resolves on the next finished() call
 *   5. Repeat 2–4 until the session is destroyed
 */
export class WarmSessionState {
  /** Deferred that resolves when new work arrives (blocks the finished() handler) */
  private resumeDeferred: Deferred<string> | null = null

  /** Deferred that resolves when the agent calls finished() */
  private finishedDeferred: Deferred<IterationResult> | null = null

  /** Whether the agent is currently blocked in finished() */
  isBlocked = false

  /** Total iterations completed */
  iterationCount = 0

  /** Timestamp of last finished() call */
  lastFinishedAt = 0

  /** Timestamp of last resume() call */
  lastResumeAt = 0

  /**
   * Prepare for the next iteration.
   * Creates a fresh finishedDeferred that the caller can await.
   */
  prepareForIteration(): void {
    this.finishedDeferred = createDeferred<IterationResult>()
  }

  /**
   * Wait for the agent to call finished().
   * Returns the agent's iteration result.
   */
  waitForFinished(): Promise<IterationResult> {
    if (!this.finishedDeferred) {
      this.prepareForIteration()
    }
    return this.finishedDeferred!.promise
  }

  /**
   * Called by the finished() tool handler when the agent invokes it.
   * Signals the iteration result and then blocks until resume() is called.
   *
   * @returns Promise<string> — resolves with the new prompt when resume() is called
   */
  async onFinishedCalled(result: string): Promise<string> {
    this.iterationCount++
    this.lastFinishedAt = Date.now()
    this.isBlocked = true

    const iterationResult: IterationResult = {
      result,
      iterationNumber: this.iterationCount,
      timestamp: this.lastFinishedAt,
    }

    // Signal the caller that the agent called finished()
    this.finishedDeferred?.resolve(iterationResult)

    // Block until the caller provides new work
    this.resumeDeferred = createDeferred<string>()
    try {
      return await this.resumeDeferred.promise
    } finally {
      this.isBlocked = false
      this.resumeDeferred = null
    }
  }

  /**
   * Resume the blocked finished() handler with new work.
   * The agent will receive this as the tool's return value.
   */
  resume(newPrompt: string): void {
    if (!this.isBlocked || !this.resumeDeferred) {
      throw new Error('Cannot resume: session is not blocked in finished()')
    }
    this.lastResumeAt = Date.now()
    this.resumeDeferred.resolve(newPrompt)
  }

  /**
   * Abort the blocked finished() handler (e.g., on shutdown).
   * The handler will reject and the SDK may receive an error tool result.
   */
  abort(reason = 'Session terminated'): void {
    if (this.resumeDeferred && !this.resumeDeferred.isSettled) {
      this.resumeDeferred.reject(new Error(reason))
    }
    if (this.finishedDeferred && !this.finishedDeferred.isSettled) {
      this.finishedDeferred.reject(new Error(reason))
    }
    this.isBlocked = false
  }
}

// ─── finished() SDK tool builder ────────────────────────────────────

/**
 * Build the `finished()` SDK tool for warm sessions.
 *
 * When the agent calls finished():
 *   1. The handler captures the agent's result
 *   2. Signals the iteration result to the caller via state.onFinishedCalled()
 *   3. Blocks until state.resume() is called with a new prompt
 *   4. Returns the new prompt as the tool result (feeds back into the agent)
 *
 * If the session is being torn down, state.abort() rejects the deferred
 * and the handler returns an error result.
 */
export function buildFinishedSdkTool(state: WarmSessionState, log: ILogger): SdkTool {
  return {
    name: 'finished',
    description: [
      'Call this tool when you have completed the current task.',
      'Pass your final result or summary as the "result" parameter.',
      'The tool will return with new instructions if there is more work to do.',
      'If it returns a confirmation with no new task, you may stop.',
    ].join(' '),
    parameters: {
      type: 'object',
      properties: {
        result: {
          type: 'string',
          description: 'Your result or summary for the completed task',
        },
      },
      required: ['result'],
    },
    handler: async (args: unknown) => {
      const result = (args as { result?: string })?.result ?? ''
      const iteration = state.iterationCount + 1

      log.info('Agent called finished()', {
        iteration,
        resultLength: result.length,
        resultPreview: result.slice(0, 120),
      })

      try {
        const newPrompt = await state.onFinishedCalled(result)

        log.info('Warm session resumed', {
          iteration: iteration + 1,
          promptLength: newPrompt.length,
          blockedMs: Date.now() - state.lastFinishedAt,
        })

        return {
          textResultForLlm: newPrompt,
          resultType: 'success' as const,
        }
      } catch (err) {
        log.info('Warm session terminated during finished() block', {
          iteration,
          error: String(err),
        })
        return {
          textResultForLlm: `Session ended: ${String(err)}. You may stop now.`,
          resultType: 'success' as const, // Use 'success' so the agent stops cleanly
        }
      }
    },
  }
}
