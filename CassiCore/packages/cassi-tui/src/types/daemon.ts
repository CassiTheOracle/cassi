/**
 * Shared types for the CassiCore daemon admin API.
 *
 * These mirror the JSON shapes returned by the daemon's HTTP endpoints
 * and SSE event streams. Single source of truth — no Go struct duplication.
 */

// ── Models ──────────────────────────────────────────────────────────────────

export interface DaemonModel {
  id: string
  name: string
  api: string
  reasoning: boolean
  input: string[]
  contextWindow: number
  maxTokens: number
  catwalk_id: string | null
}

export interface ProviderAccountHealth {
  profileId: string
  status: 'ok' | 'degraded' | 'down'
  quotaStatus?: 'healthy' | 'low' | 'exhausted'
  error?: string
}

export interface ProviderHealth {
  id: string
  status: 'ok' | 'degraded' | 'down'
  models: string[]
  accounts?: ProviderAccountHealth[]
}

export interface ModelInfo {
  id: string
  name: string
  shortName: string        // "claude-sonnet-4" extracted from "github-copilot/claude-sonnet-4"
  providerId: string       // "github-copilot"
  api: string
  reasoning: boolean
  contextWindow: number
  maxTokens: number
  providerStatus: 'ok' | 'degraded' | 'down'
}

// ── Sessions ────────────────────────────────────────────────────────────────

export interface DaemonSession {
  id: string
  channelId: string
  senderId: string
  createdAt: number
  lastActiveAt: number
  historyLength: number
  tokenCount: number
  projectPath: string | null
  title: string | null
  firstMessage: string
  lastMessage: string
}

export interface SessionMessage {
  role: 'user' | 'assistant' | 'system'
  content: string | ContentBlock[]
}

export type ContentBlock =
  | string
  | { type: 'text'; text: string }
  | { content: string | ContentBlock[] }

// ── Turn stream SSE events ──────────────────────────────────────────────────

export type TurnEventType =
  | 'token'
  | 'thinking'
  | 'tool_call'
  | 'tool_result'
  | 'done'
  | 'error'
  | 'dialectic'
  | 'memory'

export interface TurnTokenEvent {
  token?: string
  content?: string
}

export interface TurnThinkingEvent {
  token?: string
  content?: string
}

export interface TurnToolCallEvent {
  id?: string
  toolCallId?: string
  name?: string
  tool?: string
  input?: unknown
}

export interface TurnToolResultEvent {
  toolCallId?: string
  id?: string
  name?: string
  content: string
  isError: boolean
}

export interface TurnDoneEvent {
  model?: string
  tokensUsed?: number
  durationMs?: number
  response?: string
  finishReason?: string
  inputTokens?: number
  outputTokens?: number
}

export interface TurnErrorEvent {
  error: string
  type?: string
}

export interface TurnEvent {
  type: TurnEventType | string
  data: unknown
}

// ── Cognitive SSE events (/events/stream) ───────────────────────────────────

export interface CognitiveEvent {
  type: string
  sessionId?: string
  timestamp: number
  eventId: string
  [key: string]: unknown
}

export interface ThinkerActivityPayload {
  level: string
  trigger?: string
}

export interface ThinkerInsightPayload {
  sessionId: string
  text: string
  level: string
}

export interface DialecticVoice {
  analysis: string
  position: string
  confidence: number
}

export interface DialecticSignalPayload {
  sessionId?: string
  yang: DialecticVoice
  yin: DialecticVoice
  serenity: DialecticVoice
}

export interface AutonomyConfirmationPayload {
  id: string
  agentId: string
  tool: string
  reason: string
}

export interface MemoryInjectedPayload {
  sessionId: string
  memories: Array<{
    content: string
    relevance: number
    source: string
  }>
}

export interface ScoutStartedPayload {
  sessionId: string
  message: string
}

export interface ScoutToolCallPayload {
  sessionId: string
  tool: string
}

export interface ScoutCompletedPayload {
  sessionId: string
  contextLength: number
  toolCalls: number
  durationMs: number
  roundsUsed: number
  status: 'completed' | 'timeout' | 'error' | 'skipped'
}

export interface ScoutSkippedPayload {
  sessionId: string
  reason: string
}

export interface TeamActivityPayload {
  teamId: string
  checkpointId?: string
  progress?: string
  reason?: string
  error?: string
}

export interface DaemonRestartingPayload {
  reason: string
  expectedDowntimeMs: number
}

export interface DaemonResumedPayload {
  previousShutdownReason: string
  downtimeMs: number
  restoredTeams: number
  restoredLoops: number
}

// ── Teams ───────────────────────────────────────────────────────────────────

export interface DaemonTeam {
  id: string
  status: string
  goal: string
  startedAt: string
  completedAt: string
  agentCount: number
  coordinatorAgentId: string
}

export interface DaemonTeamCheckpoint {
  id: string
  trigger: string
  progressSummary: string
}

export interface DaemonTeamStatus {
  team: Record<string, unknown>
  goalTree: unknown
  progress: Record<string, unknown>
  activeAgents: Array<Record<string, unknown>>
  pendingCheckpoints: DaemonTeamCheckpoint[]
}

// ── Image attachments ───────────────────────────────────────────────────────

export interface DaemonImageAttachment {
  data: string // base64
  mediaType: string
  label?: string
}

// ── Commands ────────────────────────────────────────────────────────────────

export interface CommandAction {
  label: string
  command: string
}

export interface CommandResponse {
  ok: boolean
  text: string
  actions?: CommandAction[] | null
}

// ── Display messages (TUI conversation history) ─────────────────────────────

export interface DisplayMessage {
  id: string
  role: 'user' | 'assistant' | 'command' | 'system'
  content: string
  timestamp: number
  // Assistant-specific fields (populated after turn completes)
  thinking?: string
  toolCalls?: Array<{
    id: string
    name: string
    input: string
    finished: boolean
    startedAt?: number
    finishedAt?: number
  }>
  toolResults?: Array<{
    toolCallId: string
    name: string
    content: string
    isError: boolean
  }>
  // Command-specific fields
  commandName?: string
  actions?: CommandAction[]
}

// ── Daemon info ─────────────────────────────────────────────────────────────

export interface DaemonInfo {
  version: string
  uptime: number
  [key: string]: unknown
}
