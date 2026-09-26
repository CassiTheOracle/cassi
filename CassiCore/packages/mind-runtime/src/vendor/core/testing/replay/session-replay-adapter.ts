import type { WorkflowScenario } from '../verification/scenario-types.js'

interface ArchivedConversationEntry {
  type?: string
  content?: string
  metadata?: {
    role?: string
  }
}

interface ArchivedSessionExport {
  sessionId?: string
  entries?: ArchivedConversationEntry[]
}

export function sessionExportToScenario(sessionId: string, exported: string): WorkflowScenario {
  const parsed = JSON.parse(exported) as ArchivedSessionExport
  const entries = parsed.entries ?? []

  const steps = entries
    .filter((entry) => entry.type === 'conversation' && entry.metadata?.role === 'user' && typeof entry.content === 'string')
    .map((entry, index) => ({
      label: `Replay turn ${index + 1}`,
      action: {
        type: 'turn' as const,
        message: entry.content ?? '',
      },
    }))

  return {
    name: `replay-${sessionId}`,
    description: `Replay archived session ${sessionId}`,
    steps,
  }
}
