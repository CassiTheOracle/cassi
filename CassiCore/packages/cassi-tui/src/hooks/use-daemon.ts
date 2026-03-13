/**
 * React context providing the DaemonClient to all components.
 */

import { createContext, useContext } from 'react'
import type { DaemonClient } from '../client/index.js'

export const DaemonContext = createContext<DaemonClient | null>(null)

export function useDaemon(): DaemonClient {
  const client = useContext(DaemonContext)
  if (!client) {
    throw new Error('useDaemon must be used within a <DaemonContext.Provider>')
  }
  return client
}
