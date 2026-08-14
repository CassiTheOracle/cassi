/**
 * React context providing the DaemonClient to all components.
 */

import { createContext, useContext } from 'react'
import type { DaemonClient } from '../client/index.js'

export const DaemonContext = createContext<DaemonClient | null>(null)

/**
 * @dep callers: useCognitiveEvents (cassi-tui/src/hooks/use-cognitive-events.ts), useCommand (cassi-tui/src/hooks/use-command.ts), useModels (cassi-tui/src/hooks/use-models.ts), useSessionHistory (cassi-tui/src/hooks/use-session-history.ts), useTurnStream (cassi-tui/src/hooks/use-turn-stream.ts)
 * @dep flows: AppInner → UseDaemon (3/3)
 * @dep module: Providers
 * @dep risk: MEDIUM | 5 callers, 1 flow, 1 module
 */

export function useDaemon(): DaemonClient {
  const client = useContext(DaemonContext)
  if (!client) {
    throw new Error('useDaemon must be used within a <DaemonContext.Provider>')
  }
  return client
}
