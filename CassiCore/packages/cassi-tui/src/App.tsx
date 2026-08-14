/**
 * App — root layout for CassiTUI.
 *
 * Architecture:
 *   - Static area (above):  completed messages rendered once into terminal scrollback
 *   - Dynamic area (below): status bar, live streaming turn, cognitive panels, input bar
 *
 * The dynamic area fills the terminal height so the input bar stays at the bottom.
 * Terminal scrollback handles reviewing past messages (Shift+PageUp in most terminals).
 *
 * Manages session history, message flow, model selection, and cognitive event wiring.
 */

import React, { useState, useCallback, useRef, useEffect } from 'react'
import { Box, Text, useApp, useInput } from 'ink'

import { DaemonContext } from './hooks/use-daemon.js'
import { useCognitiveEvents } from './hooks/use-cognitive-events.js'
import { useTurnStream } from './hooks/use-turn-stream.js'
import { useCommand } from './hooks/use-command.js'
import { useModels } from './hooks/use-models.js'
import { useTerminalSize } from './hooks/use-terminal-size.js'
import { useSessionHistory } from './hooks/use-session-history.js'
import { DaemonClient } from './client/index.js'

import { StatusBar } from './components/StatusBar.js'
import { MessageBlock, LiveTurn } from './components/ConversationPanel.js'
import { ThinkerIndicator } from './components/ThinkerIndicator.js'
import { DialecticPanel } from './components/DialecticPanel.js'
import { AutonomyDialog } from './components/AutonomyDialog.js'
import { InputBar } from './components/InputBar.js'
import { ModelSelector } from './components/ModelSelector.js'
import { SessionPicker } from './components/SessionPicker.js'
import { HelpOverlay } from './components/HelpOverlay.js'

import type {
  DisplayMessage,
  DaemonSession,
  DialecticSignalPayload,
  AutonomyConfirmationPayload,
  ThinkerActivityPayload,
  ThinkerInsightPayload,
} from './types/index.js'

interface AppProps {
  client: DaemonClient
  initialSessionId: string
  initialModel?: string
  /** Pre-populate with demo messages to test rendering without a live daemon. */
  demo?: boolean
}

let msgCounter = 0
function makeId(): string {
  return `msg_${Date.now()}_${++msgCounter}`
}

/** Create demo messages showcasing tool call rendering. */
function makeDemoMessages(): DisplayMessage[] {
  return [
    {
      id: makeId(),
      role: 'user',
      content: 'List the files in the components directory and show me the App.tsx',
      timestamp: Date.now() - 30000,
    },
    {
      id: makeId(),
      role: 'assistant',
      content: 'Here are the files in the components directory. I\'ve also read App.tsx for you.\n\n## Key Files\n\n- **App.tsx** — Root layout component\n- **InputBar.tsx** — User input with tab completion\n- **ConversationPanel.tsx** — Message rendering\n\n### Example Code\n\n```typescript\nimport { useTerminalSize } from \'./hooks/use-terminal-size.js\'\n\nconst { rows, columns } = useTerminalSize()\nconsole.log(`Terminal: ${columns}x${rows}`)\n```\n\nThe `useTerminalSize` hook listens for **resize events** and re-renders automatically.',
      timestamp: Date.now() - 25000,
      thinking: 'The user wants to see the directory listing and a specific file. I\'ll use shell_exec to list files and read_file to show the contents.',
      toolCalls: [
        {
          id: 'tc_1',
          name: 'shell_exec',
          input: JSON.stringify({ command: 'ls -la cassi-tui/src/components/', workdir: '/home/valerie/workspaces/cassicore' }),
          finished: true,
          startedAt: Date.now() - 28000,
          finishedAt: Date.now() - 27200,
        },
        {
          id: 'tc_2',
          name: 'read_file',
          input: JSON.stringify({ path: 'cassi-tui/src/App.tsx', offset: 1, limit: 50 }),
          finished: true,
          startedAt: Date.now() - 26000,
          finishedAt: Date.now() - 25700,
        },
        {
          id: 'tc_3',
          name: 'web_fetch',
          input: JSON.stringify({ url: 'https://docs.inkjs.dev/components/box' }),
          finished: true,
          startedAt: Date.now() - 24000,
          finishedAt: Date.now() - 20500,
        },
      ],
      toolResults: [
        {
          toolCallId: 'tc_1',
          name: 'shell_exec',
          content: 'total 48\ndrwxr-xr-x 2 valerie valerie 4096 ...\n-rw-r--r-- 1 valerie valerie 2847 App.tsx\n-rw-r--r-- 1 valerie valerie 1523 InputBar.tsx\n...',
          isError: false,
        },
        {
          toolCallId: 'tc_2',
          name: 'read_file',
          content: '/**\n * App — root layout for CassiTUI.\n * ...',
          isError: false,
        },
        {
          toolCallId: 'tc_3',
          name: 'web_fetch',
          content: '# Box\n\nBox is the fundamental building block...',
          isError: false,
        },
      ],
    },
    {
      id: makeId(),
      role: 'system',
      content: 'Demo mode — tool rendering preview. Type /clear to reset.',
      timestamp: Date.now(),
    },
  ]
}


function AppInner({ client, initialSessionId, initialModel, demo }: AppProps): React.ReactElement {
  const { exit } = useApp()
  const { rows } = useTerminalSize()

  const [sessionId, setSessionId] = useState(initialSessionId)
  const [model, setModel] = useState<string | null>(initialModel ?? null)
  const [connected, setConnected] = useState(false)

  // completedMessages: messages rendered via Static (never re-rendered)
  // We track a "version" counter to handle session switches — Static items
  // are immutable, so on session switch we bump version which resets the array.
  const [completedMessages, setCompletedMessages] = useState<DisplayMessage[]>(
    demo ? makeDemoMessages() : [],
  )

  const history = useSessionHistory(sessionId)

  // Merge loaded history into completedMessages (once, on load)
  const historyMergedRef = useRef<string>('')
  useEffect(() => {
    if (history.loading || historyMergedRef.current === sessionId) return
    if (history.messages.length > 0 && !demo) {
      setCompletedMessages(history.messages)
    }
    historyMergedRef.current = sessionId
  }, [history.loading, history.messages, sessionId, demo])

  const [selectorOpen, setSelectorOpen] = useState(false)
  const models = useModels()

  const [sessionPickerOpen, setSessionPickerOpen] = useState(false)
  const [sessionList, setSessionList] = useState<DaemonSession[]>([])
  const [sessionListLoading, setSessionListLoading] = useState(false)

  const [helpOpen, setHelpOpen] = useState(false)

  // This must live at the App level (always mounted) because useInput in
  // conditionally-rendered overlays can fail to receive events due to Ink's
  // stdin listener lifecycle when the component tree changes.
  useInput((value, key) => {
    if (helpOpen && (key.escape || value === 'q')) {
      setHelpOpen(false)
    }
    if (selectorOpen && key.escape) {
      setSelectorOpen(false)
    }
    if (sessionPickerOpen && key.escape) {
      setSessionPickerOpen(false)
    }
  })

  const [thinkerActive, setThinkerActive] = useState(false)
  const [thinkerLevel, setThinkerLevel] = useState('')
  const [thinkerTrigger, setThinkerTrigger] = useState('')
  const [lastInsight, setLastInsight] = useState<string | null>(null)

  const [dialecticSignal, setDialecticSignal] = useState<DialecticSignalPayload | null>(null)

  const [pendingConfirmation, setPendingConfirmation] = useState<AutonomyConfirmationPayload | null>(null)

  const turn = useTurnStream()

  const cmd = useCommand(sessionId, {
    onClear: useCallback(() => {
      setCompletedMessages([])
    }, []),
    onNewSession: useCallback(() => {
      const newId = client.generateSessionId()
      setSessionId(newId)
      setCompletedMessages([])
      historyMergedRef.current = '' // Allow history reload
      // Add system message about the new session
      setCompletedMessages([{
        id: makeId(),
        role: 'system',
        content: `New session: ${newId}`,
        timestamp: Date.now(),
      }])
    }, [client]),
    onSetModel: useCallback((m: string | null) => {
      setModel(m)
    }, []),
    onShowSession: useCallback(() => sessionId, [sessionId]),
    onSwitchSession: useCallback((id: string) => {
      setSessionId(id)
      setCompletedMessages([])
      historyMergedRef.current = '' // Allow history reload for new session
      setCompletedMessages([{
        id: makeId(),
        role: 'system',
        content: `Switched to session: ${id}`,
        timestamp: Date.now(),
      }])
    }, []),
    onOpenModelSelector: useCallback(() => {
      setSelectorOpen(true)
    }, []),
    onOpenSessionPicker: useCallback(() => {
      setSessionPickerOpen(true)
      setSessionListLoading(true)
      void client.sessions().then((sessions) => {
        // Sort by last active (most recent first)
        sessions.sort((a, b) => b.lastActiveAt - a.lastActiveAt)
        setSessionList(sessions)
        setSessionListLoading(false)
      }).catch(() => {
        setSessionListLoading(false)
      })
    }, [client]),
    onOpenHelp: useCallback(() => {
      setHelpOpen(true)
    }, []),
    currentModel: model,
  })

  const wasStreamingRef = useRef(false)

  if (wasStreamingRef.current && !turn.isStreaming && turn.text) {
    wasStreamingRef.current = false
    const assistantMsg: DisplayMessage = {
      id: makeId(),
      role: 'assistant',
      content: turn.text,
      timestamp: Date.now(),
      thinking: turn.thinking || undefined,
      toolCalls: turn.toolCalls.length > 0 ? [...turn.toolCalls] : undefined,
      toolResults: turn.toolResults.length > 0 ? [...turn.toolResults] : undefined,
    }
    if (turn.lastUsedModel && turn.lastUsedModel !== model) {
      setModel(turn.lastUsedModel)
    }
    setCompletedMessages((prev) => [...prev, assistantMsg])
    turn.reset()
  }

  useCognitiveEvents(sessionId, {
    onConnected: useCallback(() => setConnected(true), []),
    onDisconnected: useCallback(() => setConnected(false), []),
    onThinkerActive: useCallback((p: ThinkerActivityPayload) => {
      setThinkerActive(true)
      setThinkerLevel(p.level)
      setThinkerTrigger(p.trigger ?? '')
    }, []),
    onThinkerIdle: useCallback(() => {
      setThinkerActive(false)
    }, []),
    onThinkerInsight: useCallback((p: ThinkerInsightPayload) => {
      setLastInsight(p.text)
    }, []),
    onDialecticSignal: useCallback((p: DialecticSignalPayload) => {
      setDialecticSignal(p)
    }, []),
    onAutonomyConfirmation: useCallback((p: AutonomyConfirmationPayload) => {
      setPendingConfirmation(p)
    }, []),
  })

  const handleSubmit = useCallback(
    async (text: string) => {
      // Slash command
      if (text.startsWith('/')) {
        if (text.trim() === '/exit' || text.trim() === '/quit' || text.trim() === '/q') {
          exit()
          return
        }
        const result = await cmd.executeCommand(text)
        setCompletedMessages((prev) => [...prev, result])
        return
      }

      // Add user message to completed messages
      const userMsg: DisplayMessage = {
        id: makeId(),
        role: 'user',
        content: text,
        timestamp: Date.now(),
      }
      setCompletedMessages((prev) => [...prev, userMsg])

      // Start streaming turn
      wasStreamingRef.current = true
      await turn.sendTurn(sessionId, text, model ?? undefined)
    },
    [cmd, exit, model, sessionId, turn],
  )

  const handleCancel = useCallback(() => {
    turn.cancel()
  }, [turn])

  const handleAction = useCallback(
    (command: string) => {
      void handleSubmit(command)
    },
    [handleSubmit],
  )

  const handleModelSelect = useCallback(
    (modelId: string) => {
      setModel(modelId)
      setSelectorOpen(false)
    },
    [],
  )

  const handleSelectorCancel = useCallback(() => {
    setSelectorOpen(false)
  }, [])

  const handleSessionSelect = useCallback(
    (id: string) => {
      setSessionPickerOpen(false)
      setSessionId(id)
      setCompletedMessages([])
      historyMergedRef.current = '' // Allow history reload
      setCompletedMessages([{
        id: makeId(),
        role: 'system',
        content: `Switched to session: ${id}`,
        timestamp: Date.now(),
      }])
    },
    [],
  )

  const handleSessionNew = useCallback(() => {
    setSessionPickerOpen(false)
    const newId = client.generateSessionId()
    setSessionId(newId)
    setCompletedMessages([])
    historyMergedRef.current = ''
    setCompletedMessages([{
      id: makeId(),
      role: 'system',
      content: `New session: ${newId}`,
      timestamp: Date.now(),
    }])
  }, [client])

  const handleSessionPickerCancel = useCallback(() => {
    setSessionPickerOpen(false)
  }, [])

  const handleApprove = useCallback(
    (id: string) => {
      void client.approveConfirmation(id)
      setPendingConfirmation(null)
    },
    [client],
  )

  const handleReject = useCallback(
    (id: string) => {
      void client.rejectConfirmation(id)
      setPendingConfirmation(null)
    },
    [client],
  )

  const currentTurn = turn.isStreaming
    ? {
        text: turn.text,
        thinking: turn.thinking,
        toolCalls: turn.toolCalls,
        toolResults: turn.toolResults,
        isStreaming: turn.isStreaming,
        error: turn.error,
      }
    : null

  if (selectorOpen) {
    return (
      <Box flexDirection="column" height={rows} paddingX={1}>
        <StatusBar
          connected={connected}
          connectionString={client.connectionString}
          model={model}
          modelInfo={models.getModelInfo(model ?? '')}
          sessionId={sessionId}
          isStreaming={turn.isStreaming}
          tokenCount={turn.tokenCount}
          inputTokens={turn.inputTokens}
          outputTokens={turn.outputTokens}
        />
        <Box flexGrow={1} />
        <ModelSelector
          models={models.models}
          currentModel={model}
          onSelect={handleModelSelect}
          onCancel={handleSelectorCancel}
        />
      </Box>
    )
  }

  if (sessionPickerOpen) {
    return (
      <Box flexDirection="column" height={rows} paddingX={1}>
        <StatusBar
          connected={connected}
          connectionString={client.connectionString}
          model={model}
          modelInfo={models.getModelInfo(model ?? '')}
          sessionId={sessionId}
          isStreaming={turn.isStreaming}
          tokenCount={turn.tokenCount}
          inputTokens={turn.inputTokens}
          outputTokens={turn.outputTokens}
        />
        <Box flexGrow={1} />
        <SessionPicker
          sessions={sessionList}
          currentSessionId={sessionId}
          loading={sessionListLoading}
          onSelect={handleSessionSelect}
          onNewSession={handleSessionNew}
          onCancel={handleSessionPickerCancel}
        />
      </Box>
    )
  }

  if (helpOpen) {
    return (
      <Box flexDirection="column" height={rows} paddingX={1}>
        <StatusBar
          connected={connected}
          connectionString={client.connectionString}
          model={model}
          modelInfo={models.getModelInfo(model ?? '')}
          sessionId={sessionId}
          isStreaming={turn.isStreaming}
          tokenCount={turn.tokenCount}
          inputTokens={turn.inputTokens}
          outputTokens={turn.outputTokens}
        />
        <Box flexGrow={1} />
        <HelpOverlay onClose={useCallback(() => setHelpOpen(false), [])} />
      </Box>
    )
  }

  // Full-screen layout: StatusBar at top, conversation in the middle (auto-scrolling),
  // and InputBar pinned at the bottom. Messages are pushed to the bottom of the
  // conversation area via justifyContent="flex-end", so the most recent messages
  // are always visible and older ones clip at the top.

  return (
    <Box flexDirection="column" height={rows}>
      {/* Top bar */}
      <StatusBar
        connected={connected}
        connectionString={client.connectionString}
        model={model}
        modelInfo={models.getModelInfo(model ?? '')}
        sessionId={sessionId}
        isStreaming={turn.isStreaming}
        tokenCount={turn.tokenCount}
        inputTokens={turn.inputTokens}
        outputTokens={turn.outputTokens}
      />

      {/* Main content area — flexGrow fills remaining space */}
      <Box flexDirection="row" flexGrow={1} overflow="hidden">
        {/* Conversation area (left / main) */}
        <Box
          flexDirection="column"
          flexGrow={1}
          paddingX={1}
          justifyContent="flex-end"
          overflow="hidden"
        >
          {/* Loading indicator */}
          {history.loading ? (
            <Text dimColor>{'Loading session history...'}</Text>
          ) : null}

          {/* Completed messages */}
          {completedMessages.map((msg) => (
            <MessageBlock key={msg.id} message={msg} onAction={handleAction} />
          ))}

          {/* Live streaming turn */}
          {currentTurn ? (
            <LiveTurn turn={currentTurn} />
          ) : null}

          {/* Idle state — show when no streaming and no messages */}
          {!currentTurn && completedMessages.length === 0 && !history.loading ? (
            <Text dimColor>{'Type a message or /help for commands.'}</Text>
          ) : null}
        </Box>

        {/* Side panel (right) — dialectic + thinker */}
        {(dialecticSignal || thinkerActive || lastInsight) ? (
          <Box flexDirection="column" width={40} paddingX={1}>
            <ThinkerIndicator
              active={thinkerActive}
              level={thinkerLevel}
              trigger={thinkerTrigger}
              lastInsight={lastInsight}
            />
            <DialecticPanel signal={dialecticSignal} />
          </Box>
        ) : null}
      </Box>

      {/* Autonomy dialog (overlays input when active) */}
      {pendingConfirmation ? (
        <AutonomyDialog
          id={pendingConfirmation.id}
          agentId={pendingConfirmation.agentId}
          tool={pendingConfirmation.tool}
          reason={pendingConfirmation.reason}
          onApprove={handleApprove}
          onReject={handleReject}
        />
      ) : null}

      {/* Input bar — always at the bottom */}
      <InputBar
        onSubmit={handleSubmit}
        onCancel={handleCancel}
        isStreaming={turn.isStreaming}
        completions={cmd.completions}
        commandHistory={cmd.history}
        getCompletions={cmd.getCompletions}
        onClear={useCallback(() => {
          setCompletedMessages([])
        }, [])}
      />
    </Box>
  )
}

export function App({ client, initialSessionId, initialModel, demo }: AppProps): React.ReactElement {
  return (
    <DaemonContext.Provider value={client}>
      <AppInner client={client} initialSessionId={initialSessionId} initialModel={initialModel} demo={demo} />
    </DaemonContext.Provider>
  )
}
