/**
 * VENDOR STUB — core/utils/abort.ts
 * Faithful pure copy of the D: original (signalPromise/throwIfAborted).
 * Re-pointed to `@cassicore/utils` at P6; delete this stub then.
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
