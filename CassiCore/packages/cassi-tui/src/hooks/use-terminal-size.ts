/**
 * Hook that tracks terminal dimensions and re-renders on resize.
 *
 * Uses Ink's useStdout() to access the underlying WriteStream,
 * then listens for 'resize' events to keep rows/columns current.
 */

import { useState, useEffect } from 'react'
import { useStdout } from 'ink'

export interface TerminalSize {
  rows: number
  columns: number
}

const FALLBACK_ROWS = 24
const FALLBACK_COLS = 80

export function useTerminalSize(): TerminalSize {
  const { stdout } = useStdout()

  const [size, setSize] = useState<TerminalSize>({
    rows: stdout.rows ?? FALLBACK_ROWS,
    columns: stdout.columns ?? FALLBACK_COLS,
  })

  useEffect(() => {
    function onResize(): void {
      setSize({
        rows: stdout.rows ?? FALLBACK_ROWS,
        columns: stdout.columns ?? FALLBACK_COLS,
      })
    }

    stdout.on('resize', onResize)
    return () => {
      stdout.off('resize', onResize)
    }
  }, [stdout])

  return size
}
