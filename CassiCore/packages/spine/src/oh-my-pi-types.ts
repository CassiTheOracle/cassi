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
 *     registerTool(tool: ToolDefinition), appendEntry(customType, data), …
 *   - `ToolDefinition<TParams,TDetails>`: name, label, description, parameters,
 *     hidden?, defaultInactive?, execute(toolCallId, params, signal, onUpdate, ctx).
 *   - `ExtensionContext`: sessionManager.getSessionId(), cwd, models.resolve(spec),
 *     memory? (read-only MemoryRuntimeContext).
 *   - `AgentToolResult`: { content: TextContent[]; isError? }.
 *   - session event payloads (session_start/switch/branch/compact/shutdown), McpNotificationEvent.
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
export type ContentPart = TextContent

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
export interface ReadonlySessionManager {
  getSessionId(): string
  getCwd(): string
  getBranch?(fromId?: string): unknown[]
}

export interface ExtensionModelQuery {
  list(): unknown[]
  current(): { id: string } | undefined
  resolve(spec: string): { id: string; family?: string } | undefined
  family(model: unknown): string
}

export interface ExtensionContext {
  sessionManager: ReadonlySessionManager
  cwd: string
  models: ExtensionModelQuery
  memory?: MemoryRuntimeContext
  mode: string
  model?: { id: string } | undefined
  logger: { debug(m: string): void; info(m: string): void; warn(m: string): void; error(m: string): void }
}

// ── Session lifecycle events ─────────────────────────────────────────────────
export interface SessionStartEvent { type: 'session_start' }
export interface SessionSwitchEvent { type: 'session_switch'; reason: string; previousSessionFile?: string }
export interface SessionBranchEvent { type: 'session_branch'; previousSessionFile?: string; entryId?: string }
export interface SessionCompactEvent { type: 'session_compact'; summary?: string }
export interface SessionShutdownEvent { type: 'session_shutdown' }
export interface McpNotificationEvent { type: 'mcp_notification'; payload?: unknown }

export type ExtensionHandler<E, R = undefined> = (event: E, ctx: ExtensionContext) => Promise<R | void> | R | void

// ── ExtensionAPI (the subset the spine touches) ──────────────────────────────
export interface ExtensionAPI extends PiBuilders {
  logger: { debug(m: string): void; info(m: string): void; warn(m: string): void; error(m: string): void }
  on(event: 'session_start', handler: ExtensionHandler<SessionStartEvent>): void
  on(event: 'session_switch', handler: ExtensionHandler<SessionSwitchEvent>): void
  on(event: 'session_branch', handler: ExtensionHandler<SessionBranchEvent>): void
  on(event: 'session_compact', handler: ExtensionHandler<SessionCompactEvent>): void
  on(event: 'session_shutdown', handler: ExtensionHandler<SessionShutdownEvent>): void
  on(event: 'mcp_notification', handler: ExtensionHandler<McpNotificationEvent>): void
  registerTool(tool: ToolDefinition): void
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
