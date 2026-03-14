import type { ToolDefinition, ToolHandler } from '../types.js'
import type { ISessionManager } from '../../../types/runtime.js'
import type { IMemory } from '../../../types/intelligence.js'
import type { IEventBus } from '../../../types/interfaces.js'

export interface DebugSessionDeps {
  sessionManager?: ISessionManager
  memory?: IMemory
  getEventBus: () => IEventBus | undefined
  getContextWindowDebugger: () => any
}

export const debugSessionDefinition: ToolDefinition = {
  name: 'debug_session',
  description: 'Deep debugging view of a session including context window state, turn history, and cognitive state (thinking, insights, anomalies). Aggregates data from session manager, event history, context window debugger, and cognitive signals.',
  parameters: {
    type: 'object',
    properties: {
      sessionId: {
        type: 'string',
        description: 'Session ID to debug. If omitted, returns the most recently active session.'
      },
      includeContext: {
        type: 'boolean',
        default: true,
        description: 'Include context window state (token count, messages, truncation info).'
      },
      includeTurns: {
        type: 'boolean',
        default: true,
        description: 'Include recent turn history with tool calls and responses.'
      },
      includeCognitive: {
        type: 'boolean',
        default: true,
        description: 'Include cognitive state (thinking patterns, insights, anomalies).'
      },
      turnLimit: {
        type: 'number',
        default: 20,
        description: 'Maximum number of recent turns to return (max: 100).'
      },
      includeEvents: {
        type: 'boolean',
        default: false,
        description: 'Include raw cognitive events from the event bus.'
      },
      eventLimit: {
        type: 'number',
        default: 50,
        description: 'Maximum number of events to return (max: 200).'
      }
    },
    required: []
  },
  timeoutMs: 20000
}

interface DebugSessionInput {
  sessionId?: string
  includeContext?: boolean
  includeTurns?: boolean
  includeCognitive?: boolean
  turnLimit?: number
  includeEvents?: boolean
  eventLimit?: number
}

interface ContextWindowStats {
  totalTokens: number
  messageCount: number
  systemPromptTokens: number
  historyTokens: number
  availableTokens: number
  utilizationPct: number
  truncationApplied: boolean
  oldestMessage?: string
  newestMessage?: string
}

interface TurnSummary {
  turnId: string
  timestamp: string
  role: 'user' | 'assistant' | 'system'
  content: string
  tokenCount?: number
  toolCalls?: Array<{
    id: string
    name: string
    input: Record<string, unknown>
  }>
  toolOutputs?: Array<{
    toolCallId: string
    content: string
    isError: boolean
  }>
  thinking?: string
  durationMs?: number
}

interface CognitiveState {
  mentalModel: {
    focusArea?: string
    currentTask?: string
    relatedMemories?: string[]
    assumptions?: string[]
  }
  focusState: {
    level: 'high' | 'medium' | 'low' | 'scattered'
    distractions?: string[]
    flowIndicators?: string[]
  }
  anomalies: Array<{
    kind: 'edge_case' | 'assumption' | 'tension' | 'gap' | 'insight'
    text: string
    confidence: number
    timestamp: string
    resolved?: boolean
  }>
  recentThinking: Array<{
    timestamp: string
    content: string
    signalsExtracted: number
  }>
  insights: Array<{
    id: string
    type: string
    content: string
    createdAt: string
    tags?: string[]
  }>
}

interface SessionDebugResponse {
  sessionId: string
  channelId: string
  senderId: string
  createdAt: string
  lastActiveAt: string
  status: 'active' | 'idle' | 'completed'
  config: Record<string, unknown>
  context?: ContextWindowStats
  turns?: TurnSummary[]
  cognitive?: CognitiveState
  events?: Array<{
    type: string
    timestamp: string
    payload: Record<string, unknown>
  }>
  error?: string
}

function toISOString(date: any): string {
  if (!date) return new Date().toISOString()
  return typeof date === 'number' ? new Date(date).toISOString() : date.toISOString()
}

export function makeDebugSessionHandler(deps: DebugSessionDeps): ToolHandler {
  return async (input, context) => {
    const params = input as unknown as DebugSessionInput
    const { sessionManager } = deps

    if (!sessionManager) {
      return JSON.stringify({
        error: 'Session manager not available',
        sessionId: params.sessionId,
      } as SessionDebugResponse, null, 2)
    }

    // Resolve session ID
    let sessionId = params.sessionId
    if (!sessionId) {
      const sessions = sessionManager.list()
      const sorted = sessions.sort((a, b) => b.lastActiveAt.getTime() - a.lastActiveAt.getTime())
      sessionId = sorted[0]?.id
      if (!sessionId) {
        return JSON.stringify({
          error: 'No active sessions found',
        } as SessionDebugResponse, null, 2)
      }
    }

    const session = sessionManager.get(sessionId)
    if (!session) {
      return JSON.stringify({
        error: `Session ${sessionId} not found`,
        sessionId,
      } as SessionDebugResponse, null, 2)
    }

    const response: SessionDebugResponse = {
      sessionId: session.id,
      channelId: session.channelId,
      senderId: session.senderId,
      createdAt: toISOString(session.createdAt),
      lastActiveAt: toISOString(session.lastActiveAt),
      status: Date.now() - session.lastActiveAt.getTime() < 5 * 60 * 1000 ? 'active' : 'idle',
      config: session.config as unknown as Record<string, unknown>,
    }

    // Include context window stats if requested
    if (params.includeContext !== false) {
      try {
        const contextDebugger = deps.getContextWindowDebugger()
        if (contextDebugger) {
          const snapshot = await contextDebugger.getSnapshot?.(sessionId)
          if (snapshot) {
            const messages = snapshot.messages || []
            const totalTokens = messages.reduce((sum: number, m: any) => sum + (m.tokenCount || 0), 0)
            const maxTokens = snapshot.maxTokens || 128000
            
            response.context = {
              totalTokens,
              messageCount: messages.length,
              systemPromptTokens: messages.find((m: any) => m.role === 'system')?.tokenCount || 0,
              historyTokens: totalTokens - (messages.find((m: any) => m.role === 'system')?.tokenCount || 0),
              availableTokens: maxTokens - totalTokens,
              utilizationPct: Math.round((totalTokens / maxTokens) * 100),
              truncationApplied: snapshot.truncationApplied || false,
              oldestMessage: messages[0]?.timestamp ? toISOString(messages[0].timestamp) : undefined,
              newestMessage: messages[messages.length - 1]?.timestamp ? toISOString(messages[messages.length - 1].timestamp) : undefined,
            }
          }
        }
      } catch (err) {
        response.context = {
          totalTokens: 0,
          messageCount: 0,
          systemPromptTokens: 0,
          historyTokens: 0,
          availableTokens: 0,
          utilizationPct: 0,
          truncationApplied: false,
        } as unknown as ContextWindowStats
        ;(response.context as any).error = String(err)
      }
    }

    // Include turn history if requested
    if (params.includeTurns !== false) {
      const turnLimit = Math.min(params.turnLimit ?? 20, 100)
      const history = session.history || []
      
      // Get recent turns (user + assistant pairs)
      const recentTurns: TurnSummary[] = []
      const turnHistory = history.slice(-turnLimit * 2) // Get pairs
      
      for (const msg of turnHistory) {
        const msgAny = msg as any
        const turn: TurnSummary = {
          turnId: msgAny.id || `turn-${recentTurns.length}`,
          timestamp: msgAny.timestamp ? toISOString(msgAny.timestamp) : new Date().toISOString(),
          role: msgAny.role as 'user' | 'assistant' | 'system',
          content: typeof msgAny.content === 'string' ? msgAny.content.slice(0, 500) : JSON.stringify(msgAny.content).slice(0, 500),
          tokenCount: msgAny.tokenCount,
        }

        // Include tool calls if present
        if (msgAny.toolCalls) {
          turn.toolCalls = msgAny.toolCalls.map((tc: any) => ({
            id: tc.id,
            name: tc.name,
            input: tc.input,
          }))
        }

        // Include tool outputs if present
        if (msgAny.toolOutputs) {
          turn.toolOutputs = msgAny.toolOutputs.map((to: any) => ({
            toolCallId: to.toolCallId,
            content: typeof to.content === 'string' ? to.content.slice(0, 200) : JSON.stringify(to.content).slice(0, 200),
            isError: to.isError,
          }))
        }

        // Include thinking if present
        if (msgAny.thinking) {
          turn.thinking = msgAny.thinking.slice(0, 500)
        }

        // Include duration if present
        if (msgAny.durationMs) {
          turn.durationMs = msgAny.durationMs
        }

        recentTurns.push(turn)
      }

      response.turns = recentTurns
    }

    // Include cognitive state if requested
    if (params.includeCognitive !== false) {
      response.cognitive = await buildCognitiveState(sessionId, deps, context)
    }

    // Include raw events if requested
    if (params.includeEvents !== false) {
      try {
        const eventBus = deps.getEventBus()
        if (eventBus) {
          // Note: This is a simplified approach - in production you'd query event history
          const eventLimit = Math.min(params.eventLimit ?? 50, 200)
          response.events = [] // Events would come from event history store
        }
      } catch (err) {
        // Events not available
      }
    }

    return JSON.stringify(response, null, 2)
  }
}

async function buildCognitiveState(
  sessionId: string,
  deps: DebugSessionDeps,
  context: any
): Promise<CognitiveState> {
  const cognitive: CognitiveState = {
    mentalModel: {},
    focusState: { level: 'medium' },
    anomalies: [],
    recentThinking: [],
    insights: [],
  }

  // Search memory for insights related to this session
  if (deps.memory) {
    try {
      const insights = await deps.memory.search(sessionId, {
        limit: 10,
        type: 'insight',
      })
      
      cognitive.insights = insights.map((r: any) => ({
        id: r.entry.id,
        type: r.entry.type,
        content: r.entry.content.slice(0, 500),
        createdAt: r.entry.createdAt.toISOString(),
        tags: r.entry.metadata?.tags,
      }))

      // Search for reflections (anomalies)
      const reflections = await deps.memory.search(sessionId, {
        limit: 20,
        type: 'reflection',
      })

      cognitive.anomalies = reflections.map((r: any) => {
        const kind = r.entry.metadata?.kind || 'insight'
        return {
          kind: kind as 'edge_case' | 'assumption' | 'tension' | 'gap' | 'insight',
          text: r.entry.content.slice(0, 300),
          confidence: r.entry.metadata?.confidence || r.score || 0.5,
          timestamp: r.entry.createdAt.toISOString(),
          resolved: r.entry.metadata?.resolved || false,
        }
      })
    } catch (err) {
      // Memory search failed, use defaults
    }
  }

  // Try to get cognitive signals from event history
  try {
    const eventBus = deps.getEventBus()
    if (eventBus) {
      // In production, query event history for cognitive signals
      // For now, derive from session history
      const session = context.sessionManager?.get(sessionId)
      if (session) {
        const recentHistory = session.history?.slice(-50) || []
        
        // Extract thinking patterns from assistant messages
        const thinkingBlocks = recentHistory
          .filter((m: any) => m.role === 'assistant' && m.thinking)
          .slice(-5)
        
        cognitive.recentThinking = thinkingBlocks.map((m: any) => ({
          timestamp: m.timestamp ? toISOString(m.timestamp) : new Date().toISOString(),
          content: m.thinking.slice(0, 300),
          signalsExtracted: 0, // Would need ThoughtObserver to extract
        }))

        // Derive focus state from recent activity
        const recentTurns = recentHistory.filter((m: any) => m.role === 'user').length
        const toolCalls = recentHistory.reduce((sum: number, m: any) => 
          sum + (m.toolCalls?.length || 0), 0)
        
        if (recentTurns > 10 && toolCalls > 20) {
          cognitive.focusState.level = 'high'
          cognitive.focusState.flowIndicators = ['high tool usage', 'rapid turns']
        } else if (recentTurns < 3) {
          cognitive.focusState.level = 'low'
        }
      }
    }
  } catch (err) {
    // Event bus not available
  }

  // Derive mental model from recent conversation
  try {
    const session = context.sessionManager?.get(sessionId)
    if (session) {
      const recentHistory = session.history?.slice(-20) || []
      const userMessages = recentHistory.filter((m: any) => m.role === 'user')
      
      if (userMessages.length > 0) {
        const lastUserMsg = userMessages[userMessages.length - 1]?.content
        if (typeof lastUserMsg === 'string') {
          cognitive.mentalModel.currentTask = lastUserMsg.slice(0, 200)
          
          // Extract keywords as focus area
          const words = lastUserMsg.split(/\s+/).filter(w => w.length > 4)
          cognitive.mentalModel.focusArea = words.slice(0, 3).join(' ')
        }
      }

      // Extract assumptions from tool usage patterns
      const toolCalls = recentHistory.flatMap((m: any) => m.toolCalls || [])
      const uniqueTools = new Set(toolCalls.map((tc: any) => tc.name))
      if (uniqueTools.size > 0) {
        cognitive.mentalModel.assumptions = [
          `Using tools: ${Array.from(uniqueTools).join(', ')}`,
        ]
      }
    }
  } catch (err) {
    // Derivation failed
  }

  return cognitive
}
