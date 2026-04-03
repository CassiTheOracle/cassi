/**
 * Hook encapsulating slash command dispatch — local commands, remote daemon
 * commands, tab-completion list, and command history for up-arrow recall.
 */

import { useState, useCallback, useEffect, useRef } from 'react'
import { useDaemon } from './use-daemon.js'
import type { DisplayMessage, CommandAction } from '../types/index.js'


const LOCAL_COMMANDS = new Map<string, string>([
  ['/exit', 'Exit the TUI'],
  ['/quit', 'Exit the TUI'],
  ['/q', 'Exit the TUI'],
  ['/clear', 'Clear conversation history'],
  ['/help', 'Show help overlay'],
  ['/new', 'Start a new session'],
  ['/model', 'Show or switch the active model'],
  ['/session', 'Show or switch session'],
  ['/sessions', 'Open session picker'],
])

export interface LocalCommandCallbacks {
  onClear: () => void
  onNewSession: () => void
  onSetModel: (model: string | null) => void
  onShowSession: () => string     // WHY: Returns current session ID for /session command
  onSwitchSession: (id: string) => void
  onOpenModelSelector: () => void
  onOpenSessionPicker: () => void
  onOpenHelp: () => void
  currentModel: string | null
}

export interface UseCommandReturn {
  /** Execute a slash command. Returns a DisplayMessage with the result. */
  executeCommand: (input: string) => Promise<DisplayMessage>
  /** All known command names for tab completion. */
  completions: string[]
  /** Filter completions by partial input (e.g. "/te" -> ["/team", "/think"]) */
  getCompletions: (partial: string) => string[]
  /** Command input history for up-arrow recall. */
  history: string[]
  /** Whether the completion list has been fetched from daemon. */
  ready: boolean
}

let msgCounter = 0
function makeId(): string {
  return `cmd_${Date.now()}_${++msgCounter}`
}

export function useCommand(
  sessionId: string,
  callbacks: LocalCommandCallbacks,
): UseCommandReturn {
  const client = useDaemon()
  const [completions, setCompletions] = useState<string[]>([...LOCAL_COMMANDS.keys()])
  const [history, setHistory] = useState<string[]>([])
  const [ready, setReady] = useState(false)
  const callbacksRef = useRef(callbacks)
  callbacksRef.current = callbacks

  // Fetch command list from daemon on mount / session change
  useEffect(() => {
    let cancelled = false
    async function fetchCommands() {
      const remote = await client.listCommands(sessionId)
      if (cancelled) return
      // Merge local + remote, deduplicate
      const all = new Set([...LOCAL_COMMANDS.keys(), ...remote])
      setCompletions([...all].sort())
      setReady(true)
    }
    fetchCommands()
    return () => { cancelled = true }
  }, [client, sessionId])

  const getCompletions = useCallback(
    (partial: string): string[] => {
      if (!partial.startsWith('/')) return []
      const lower = partial.toLowerCase()
      return completions.filter((c) => c.startsWith(lower))
    },
    [completions],
  )

  const executeCommand = useCallback(
    async (input: string): Promise<DisplayMessage> => {
      // Record in history
      setHistory((h) => {
        const next = [input, ...h.filter((x) => x !== input)]
        return next.slice(0, 100) // WHY: Keep last 100 unique commands
      })

      const parts = input.trim().split(/\s+/)
      const cmd = parts[0]!.toLowerCase()
      const args = parts.slice(1)
      const cb = callbacksRef.current

      switch (cmd) {
        case '/exit':
        case '/quit':
        case '/q':
          process.exit(0)

        case '/clear':
          cb.onClear()
          return {
            id: makeId(),
            role: 'system',
            content: 'Conversation cleared.',
            timestamp: Date.now(),
          }

        case '/help':
          cb.onOpenHelp()
          return {
            id: makeId(),
            role: 'system',
            content: '',
            timestamp: Date.now(),
          }

        case '/new':
          cb.onNewSession()
          return {
            id: makeId(),
            role: 'system',
            content: 'Started new session.',
            timestamp: Date.now(),
          }

        case '/model': {
          const subcmd = (args[0] || '').toLowerCase()

          // /model (no args) — open interactive selector
          if (args.length === 0) {
            cb.onOpenModelSelector()
            return {
              id: makeId(),
              role: 'system',
              content: 'Opening model selector...',
              timestamp: Date.now(),
            }
          }

          // /model list — text listing
          if (subcmd === 'list') {
            return {
              id: makeId(),
              role: 'system',
              content: 'Use the model selector (Ctrl+M or /model) to view available models.',
              timestamp: Date.now(),
            }
          }

          // /model info — current model details
          if (subcmd === 'info') {
            return {
              id: makeId(),
              role: 'system',
              content: cb.currentModel
                ? `Current model: ${cb.currentModel}`
                : 'No model selected (using daemon default).',
              timestamp: Date.now(),
            }
          }

          // /model <name> — set model directly
          cb.onSetModel(args[0]!)
          return {
            id: makeId(),
            role: 'system',
            content: `Model set to: ${args[0]}`,
            timestamp: Date.now(),
          }
        }

        case '/session':
          if (args.length > 0) {
            cb.onSwitchSession(args[0]!)
            return {
              id: makeId(),
              role: 'system',
              content: `Switched to session: ${args[0]}`,
              timestamp: Date.now(),
            }
          }
          return {
            id: makeId(),
            role: 'system',
            content: `Current session: ${cb.onShowSession()}`,
            timestamp: Date.now(),
          }

        case '/sessions':
          cb.onOpenSessionPicker()
          return {
            id: makeId(),
            role: 'system',
            content: 'Opening session picker...',
            timestamp: Date.now(),
          }
      }

      try {
        const resp = await client.command(sessionId, input)

        const actions: CommandAction[] | undefined =
          resp.actions && resp.actions.length > 0 ? resp.actions : undefined

        return {
          id: makeId(),
          role: 'command',
          content: resp.text,
          timestamp: Date.now(),
          commandName: cmd,
          actions,
        }
      } catch (err) {
        return {
          id: makeId(),
          role: 'command',
          content: `Error: ${String(err)}`,
          timestamp: Date.now(),
          commandName: cmd,
        }
      }
    },
    [client, sessionId],
  )

  return { executeCommand, completions, getCompletions, history, ready }
}
