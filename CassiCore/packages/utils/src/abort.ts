/**
 * @dep callers: complete (core/providers/centralized.ts), fetchWithTimeout (core/providers/github-copilot.ts), ping (core/providers/google-antigravity.ts), streamOnce (core/turn-engine.ts), streamOnce (core/turn-pipeline.ts)
 * @dep module: Providers
 * @dep risk: MEDIUM | 5 callers, 0 flows, 1 module
 */

export function signalPromise(signal?: AbortSignal): Promise<void> {
  if (!signal) return new Promise<void>(() => {})
  return new Promise<void>((resolve) => {
    if (signal.aborted) return resolve()
    const onAbort = () => {
      try { signal.removeEventListener('abort', onAbort) } catch {}
      resolve()
    }
    try { signal.addEventListener('abort', onAbort, { once: true }) } catch {}
  })
}

export function throwIfAborted(signal?: AbortSignal, message = 'cancelled'): void {
  if (signal?.aborted) throw new Error(message)
}
