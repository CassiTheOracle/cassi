/**
 * @cassicore/spine — [SPINE-TYPES] faithful minimal type shim of the ohmypi surface.
 *
 * WHY: `@oh-my-pi/pi-coding-agent` is pinned in devDependencies (17.3.4, per brief
 * Open Item 5) and its TYPES load for typechecking, but its ROOT module pulls a native
 * allocator (`@oh-my-pi/pi-natives`) that fails to load headlessly in plain CI/vitest
 * (no ohmypi runtime env). The constraint in the P3 brief allows a FAITHFUL minimal
 * local type shim so the spine compiles + its contract tests pass WITHOUT live ohmypi.
 * This shim re-declares ONLY the surface the spine uses, transcribed from the inspected
 * `dist/types/…` signatures at 17.3.4:
 *
 *   - `ExtensionAPI` (extensibility/extensions/types.d.ts): zod, arktype, on(event, h),
 *     registerTool(tool: ToolDefinition), registerCommand(name, opts), sendMessage(payload),
 *     appendEntry(customType, data), …
 *   - `ToolDefinition<TParams,TDetails>`: name, label, description, parameters,
 *     hidden?, defaultInactive?, execute(toolCallId, params, signal, onUpdate, ctx).
 *   - `ExtensionContext`: ui.notify, sessionManager (full ReadonlySessionManager accessor
 *     set), cwd, models.resolve(spec), getContextUsage(), memory? (read-only MemoryRuntimeContext).
 *   - `AgentToolResult`: { content: TextContent[]; isError? }.
 *   - session event payloads (session_start/switch/branch/compact/shutdown), message
 *     start/update/end, turn_start/turn_end, context (+ContextEventResult), session.compacting
 *     (+SessionCompactingResult), McpNotificationEvent. User-message observation is delivered
 *     through the real `message_end` event (role 'user') — 17.3.4 has no `user_message` event.
 *   - memory-backend surface: MemoryRuntimeContext, MemoryBackendStatus, MemoryBackendSearchResult,
 *     MemoryBackendSearchOptions, MemoryBackendSaveInput.
 *
 * Drift guard: if the pinned version's API changes, the real-devDep types break the
 * typecheck when an environment CAN load them; the shim mirrors those signatures 1:1.
 *
 * ALL spine source imports from THIS module (never `@oh-my-pi/pi-coding-agent` directly)
 * so the shipped extension + its tests are self-contained.
 */

// ── Text/Image content (pi-agent-core types) ────────────────────────────────
export interface TextContent {
  type: 'text'
  text: string
}
export interface ImageContent {
  type: 'image'
  [k: string]: unknown
}
export type ContentPart = TextContent | ImageContent

/** Who initiated a message for billing/attribution semantics (pi-ai). */
export type MessageAttribution = 'user' | 'agent'

// ── Messages (pi-ai `Message` + session custom messages, transcribed at 17.3.4) ─
export interface ToolCallBlock {
  type: 'toolCall'
  id: string
  name: string
  arguments: Record<string, unknown>
  [k: string]: unknown
}
export interface UserMessage {
  role: 'user'
  content: string | ContentPart[]
  /** True if the message was injected by the system (e.g., auto-continue). */
  synthetic?: boolean
  /** True when injected mid-turn as a steer; never rendered. */
  steering?: boolean
  attribution?: MessageAttribution
  timestamp: number
  [k: string]: unknown
}
export interface AssistantMessage {
  role: 'assistant'
  content: (TextContent | ToolCallBlock)[]
  stopReason?: string
  errorMessage?: string
  timestamp: number
  [k: string]: unknown
}
export interface ToolResultMessage<TDetails = unknown> {
  role: 'toolResult'
  toolCallId: string
  toolName: string
  content: ContentPart[]
  details?: TDetails
  isError: boolean
  attribution?: MessageAttribution
  timestamp: number
  [k: string]: unknown
}
/** Extension-injected message via `pi.sendMessage` (session/messages.js). */
export interface CustomMessage<T = unknown> {
  role: 'custom'
  customType: string
  content: string | ContentPart[]
  display: boolean
  details?: T
  attribution?: MessageAttribution
  timestamp: number
}
export type CustomMessageContent = string | ContentPart[]
export type CustomMessagePayload<T = unknown> = string | Partial<Pick<CustomMessage<T>, 'customType' | 'content' | 'display' | 'details' | 'attribution'>>
/** Union of LLM messages + custom messages (pi-agent-core AgentMessage). */
export type AgentMessage = UserMessage | AssistantMessage | ToolResultMessage | CustomMessage

export interface AgentToolResult<T = unknown> {
  content: ContentPart[]
  details?: T
  isError?: boolean
  useless?: boolean
}
export type AgentToolUpdateCallback<T = unknown> = (partialResult: AgentToolResult<T>) => void

// ── zod / arktype / typebox builders ─────────────────────────────────────────
/** A permissive schema value produced by the omptype builders (real shape at runtime). */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export interface ZodSchemaLike {
  optional(): ZodSchemaLike
  passthrough(): ZodSchemaLike
  _type?: string
  shape?: Record<string, unknown>
  [k: string]: unknown
}
export type ZodLike = {
  object: (shape: Record<string, unknown>) => ZodSchemaLike
  string: () => ZodSchemaLike
  number: () => ZodSchemaLike
  boolean: () => ZodSchemaLike
  array: (item: unknown) => ZodSchemaLike
  enum: (values: [string, ...string[]]) => ZodSchemaLike
  any: () => ZodSchemaLike
}
export interface PiBuilders {
  zod: ZodLike
  arktype: ZodLike
  typebox: unknown
}

// ── ToolDefinition / registerTool ────────────────────────────────────────────
export interface ToolDefinition<P = unknown> {
  name: string
  label: string
  description: string
  parameters: P
  hidden?: boolean
  defaultInactive?: boolean
  loadMode?: string
  approval?: 'read' | 'write' | 'exec'
  strict?: boolean
  execute: (
    toolCallId: string,
    params: unknown,
    signal: AbortSignal | undefined,
    onUpdate: AgentToolUpdateCallback | undefined,
    ctx: ExtensionContext,
  ) => Promise<AgentToolResult>
}

// ── ExtensionContext ─────────────────────────────────────────────────────────
/**
 * Read-only session manager facade (session/session-manager.ts `ReadonlySessionManager`
 * at 17.3.4 — the `Pick` over SessionManager's read accessors, transcribed as a minimal
 * structural shim: entry/tree/blob shapes are opaque `unknown` because the spine only
 * reads ids/names/paths through these).
 */
export interface ReadonlySessionManager {
  getCwd(): string
  getSessionDir(): string
  getSessionId(): string
  getSessionFile(): string | undefined
  getSessionName(): string | undefined
  getArtifactsDir(): string | null
  getArtifactManager(): unknown | null
  allocateArtifactPath(toolType: string): Promise<{ id?: string; path?: string }>
  saveArtifact(content: string, toolType: string): Promise<string | undefined>
  getArtifactPath(id: string): Promise<string | null>
  getLeafId(): string | null
  getLeafEntry(): unknown | undefined
  getEntry(id: string): unknown | undefined
  getLabel(id: string): string | undefined
  getBranch(fromId?: string): unknown[]
  getHeader(): unknown | null
  getEntries(): unknown[]
  getTree(): unknown[]
  getUsageStatistics(): unknown
  putBlob(data: unknown, options?: unknown): Promise<unknown>
  putBlobSync(data: unknown, options?: unknown): unknown
}

export interface ExtensionModelQuery {
  list(): unknown[]
  current(): { id: string } | undefined
  resolve(spec: string): { id: string; family?: string } | undefined
  family(model: unknown): string
}

/** Runtime host mode exposed to Pi-compatible extensions. */
export type ExtensionMode = 'tui' | 'rpc' | 'json' | 'print'

/** Estimated context usage for the active model (extensions/types.ts ContextUsage). */
export interface ContextUsage {
  tokens: number
  contextWindow: number
  /** Context usage as percentage of context window. */
  percent: number
}

/** UI primitives for extensions (extensions/types.ts ExtensionUIContext subset). */
export interface ExtensionUIContext {
  /** Show a notification to the user. */
  notify(message: string, type?: 'info' | 'warning' | 'error'): void
  /** Set status text in the footer/status bar. Pass undefined to clear. */
  setStatus?(key: string, text: string | undefined): void
  [k: string]: unknown
}

export interface ExtensionContext {
  /** UI methods for user interaction. */
  ui: ExtensionUIContext
  sessionManager: ReadonlySessionManager
  cwd: string
  models: ExtensionModelQuery
  memory?: MemoryRuntimeContext
  mode: ExtensionMode
  model?: { id: string } | undefined
  logger: { debug(m: string): void; info(m: string): void; warn(m: string): void; error(m: string): void }
  /** Get current context usage for the active model. */
  getContextUsage?(): ContextUsage | undefined
  /** Whether UI is available (false in print/RPC mode). */
  hasUI?: boolean
  /** Whether the agent is idle (not streaming). */
  isIdle?(): boolean
  /** Abort the current agent operation. */
  abort?(): void
  /** Gracefully shutdown and exit. */
  shutdown?(): void
  /** Get the current effective system prompt. */
  getSystemPrompt?(): string[]
}

// ── Session lifecycle events ─────────────────────────────────────────────────
export interface SessionStartEvent { type: 'session_start' }
export interface SessionSwitchEvent {
  type: 'session_switch'
  /** Reason for the switch. */
  reason: 'new' | 'resume' | 'fork' | 'handoff'
  /** Session file we came from. */
  previousSessionFile: string | undefined
}
export interface SessionBeforeBranchEvent { type: 'session_before_branch'; entryId: string }
export interface SessionBranchEvent { type: 'session_branch'; previousSessionFile: string | undefined }
export interface SessionCompactEvent {
  type: 'session_compact'
  compactionEntry: { summary: string }
  fromExtension: boolean
}
export interface SessionShutdownEvent { type: 'session_shutdown' }
export interface McpNotificationEvent { type: 'mcp_notification'; payload?: unknown }

// ── Message / turn / context / compaction events (17.3.4 shared-events) ─────
/** Fired once at the beginning of each agent run, before provider-context transforms. */
export interface AgentStartEvent { type: 'agent_start' }
/** Fired when a message starts (user, assistant, or toolResult). */
export interface MessageStartEvent { type: 'message_start'; message: AgentMessage }
/** Fired during assistant message streaming (token-by-token updates). */
export interface MessageUpdateEvent { type: 'message_update'; message: AgentMessage; assistantMessageEvent: unknown }
/** Fired when a message ends. Notification-only: the message is a detached snapshot. */
export interface MessageEndEvent { type: 'message_end'; message: AgentMessage }
/** Fired at the start of each turn. */
export interface TurnStartEvent { type: 'turn_start'; turnIndex: number; timestamp: number }
/** Fired at the end of each turn. */
export interface TurnEndEvent { type: 'turn_end'; turnIndex: number; message: AgentMessage; toolResults: unknown[] }
/**
 * Fired before each LLM call. Original session messages are NOT modified — only
 * the messages sent to the LLM are affected when a handler returns a replacement.
 */
export interface ContextEvent {
  type: 'context'
  /** Messages about to be sent to the LLM (deep copy, safe to modify). */
  messages: AgentMessage[]
}
export interface ContextEventResult { messages?: AgentMessage[] }
/** Fired before compaction summarization to customize prompts/context. */
export interface SessionCompactingEvent {
  type: 'session.compacting'
  sessionId: string
  messages: AgentMessage[]
}
export interface SessionCompactingResult {
  /** Additional context lines to include in summary. */
  context?: string[]
  /** Override the default compaction prompt. */
  prompt?: string
  /** Custom data to store in the compaction entry. */
  preserveData?: Record<string, unknown>
}

export type ExtensionHandler<E, R = undefined> = (event: E, ctx: ExtensionContext) => Promise<R | void> | R | void

// ── ExtensionAPI (the subset the spine touches) ──────────────────────────────
/** Extended context for command handlers (extensions/types.ts ExtensionCommandContext). */
export interface ExtensionCommandContext extends ExtensionContext {
  /** Wait for the agent to finish streaming. */
  waitForIdle?(): Promise<void>
  /** Compact the session context (interactive mode shows UI). */
  compact?(instructionsOrOptions?: string | { onComplete?: (result: unknown) => void }): Promise<void>
  [k: string]: unknown
}

/** Registered command handler signature (extensions/types.ts RegisteredCommand). */
export type CommandHandler = (args: string, ctx: ExtensionCommandContext) => Promise<void> | void

export interface ExtensionAPI extends PiBuilders {
  logger: { debug(m: string): void; info(m: string): void; warn(m: string): void; error(m: string): void }
  on(event: 'session_start', handler: ExtensionHandler<SessionStartEvent>): void
  on(event: 'session_switch', handler: ExtensionHandler<SessionSwitchEvent>): void
  on(event: 'session_before_branch', handler: ExtensionHandler<SessionBeforeBranchEvent>): void
  on(event: 'session_branch', handler: ExtensionHandler<SessionBranchEvent>): void
  on(event: 'session_compact', handler: ExtensionHandler<SessionCompactEvent>): void
  on(event: 'session_shutdown', handler: ExtensionHandler<SessionShutdownEvent>): void
  on(event: 'mcp_notification', handler: ExtensionHandler<McpNotificationEvent>): void
  on(event: 'agent_start', handler: ExtensionHandler<AgentStartEvent>): void
  on(event: 'message_start', handler: ExtensionHandler<MessageStartEvent>): void
  on(event: 'message_update', handler: ExtensionHandler<MessageUpdateEvent>): void
  on(event: 'message_end', handler: ExtensionHandler<MessageEndEvent>): void
  on(event: 'turn_start', handler: ExtensionHandler<TurnStartEvent>): void
  on(event: 'turn_end', handler: ExtensionHandler<TurnEndEvent>): void
  on(event: 'context', handler: ExtensionHandler<ContextEvent, ContextEventResult>): void
  on(event: 'session.compacting', handler: ExtensionHandler<SessionCompactingEvent, SessionCompactingResult>): void
  registerTool(tool: ToolDefinition): void
  /** Register a custom command (extensions/types.ts registerCommand). */
  registerCommand(name: string, options: {
    description?: string
    getArgumentCompletions?: (argumentPrefix: string) => unknown[] | null
    handler: CommandHandler
  }): void
  /**
   * Send a custom message to the session (extensions/types.ts sendMessage).
   * `deliverAs: "nextTurn"` keeps the message hidden from the editable pending-message UI.
   */
  sendMessage<T = unknown>(message: CustomMessagePayload<T>, options?: {
    triggerTurn?: boolean
    deliverAs?: 'steer' | 'followUp' | 'nextTurn'
  }): void
  appendEntry<T = unknown>(customType: string, data?: T): void
  exec(command: string, args: string[]): Promise<{ stdout: string; stderr: string; exitCode: number }>
}

// ── Memory backend surface ───────────────────────────────────────────────────
export type MemoryBackendId = 'off' | 'local' | 'hindsight' | 'mnemopi'
export interface MemoryBackendStatus {
  backend: MemoryBackendId
  active: boolean
  writable: boolean
  searchable: boolean
  scope?: string
  database?: string
  message?: string
  error?: string
}
export interface MemoryBackendSearchOptions {
  limit?: number
  signal?: AbortSignal
}
export interface MemoryBackendSearchItem {
  id?: string
  content: string
  source?: string
  timestamp?: string
  score?: number
}
export interface MemoryBackendSearchResult {
  backend: MemoryBackendId
  query: string
  count: number
  items: MemoryBackendSearchItem[]
  message?: string
}
export interface MemoryBackendSaveInput {
  content: string
  context?: string
  source?: string
  importance?: number
}
export interface MemoryBackendSaveResult {
  backend: MemoryBackendId
  stored: number
  ids?: string[]
  queued?: boolean
  message?: string
}
export interface MemoryRuntimeContext {
  status(): Promise<MemoryBackendStatus>
  search(query: string, options?: MemoryBackendSearchOptions): Promise<MemoryBackendSearchResult>
  save(input: string | MemoryBackendSaveInput): Promise<MemoryBackendSaveResult>
}
