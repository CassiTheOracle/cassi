/**
 * @cassicore/spine — STUBBED ExtensionAPI for contract tests (no live ohmypi).
 *
 * Implements the minimal `ExtensionAPI` surface the spine factory touches so the
 * extension runs headless against a stubbed bridge: registerTool, on (multiple
 * handlers per event, faithful to the real event bus), appendEntry, registerCommand,
 * sendMessage, zod (minimal builder — tests don't parse through it), the full
 * ReadonlySessionManager accessor set, cwd, models.resolve, getContextUsage,
 * ui.notify, logger, exec. Registered tools, lifecycle handlers, commands,
 * notifications, and sent messages are recorded.
 *
 * NOTE: it does NOT import `@oh-my-pi/pi-coding-agent` (its native allocator fails to
 * load headlessly) — it uses the [SPINE-TYPES] shim (src/oh-my-pi-types.ts).
 */

import type { ExtensionAPI, ToolDefinition, ZodLike } from '../src/oh-my-pi-types.js'

export interface RecordedTool {
  def: Omit<ToolDefinition, 'execute'>
  execute: ToolDefinition['execute'] | undefined
}

export interface StubPi {
  pi: ExtensionAPI
  registered: Array<{ name: string; label: string; description: string; hidden?: boolean; defaultInactive?: boolean }>
  handlers: Map<string, Array<(e: unknown, ctx: unknown) => unknown | Promise<unknown>>>
  entries: Array<{ type: string; data: unknown }>
  commands: Array<{ name: string; description?: string }>
  notifications: Array<{ message: string; type?: string }>
  sentMessages: Array<{ message: unknown; options?: unknown }>
  resolvedModels: string[]
  executed: Array<{ name: string; params: unknown; sessionId: string }>
  setSessionId: (id: string) => void
  setResolveResult: (value: unknown) => void
  setContextUsage: (value: { tokens: number; contextWindow: number; percent: number } | undefined) => void
  makeCtx: () => Record<string, unknown>
  getTool(name: string): RecordedTool | undefined
  fire(event: string, payload?: unknown, ctx?: Record<string, unknown>): Promise<unknown[]>
  runCommand(name: string, args: string, ctx?: Record<string, unknown>): Promise<unknown>
}

/** Minimal zod-like builder producing schemas with `.optional()`/`.passthrough()`. */
function makeZod(): ZodLike {
  const leaf = (type: string) => ({
    _type: type,
    optional() { return { ...this } },
    passthrough() { return { ...this } },
    safeParse(v: unknown) { return { success: true, data: v } },
  })
  return {
    object: (shape: Record<string, unknown>) => ({ _type: 'object', shape, optional() { return this }, passthrough() { return this }, safeParse(v: unknown) { return { success: true, data: v } } }),
    string: () => leaf('string'),
    number: () => leaf('number'),
    boolean: () => leaf('boolean'),
    array: () => leaf('array'),
    enum: () => leaf('enum'),
    any: () => leaf('any'),
  }
}

export function createStubPi(overrides: { sessionId?: string } = {}): StubPi {
  let sessionId = overrides.sessionId ?? 'sess-test-1'
  const registered: StubPi['registered'] = []
  const handlers = new Map<string, Array<(e: unknown, ctx: unknown) => unknown | Promise<unknown>>>()
  const entries: StubPi['entries'] = []
  const commands: StubPi['commands'] = []
  const notifications: StubPi['notifications'] = []
  const sentMessages: StubPi['sentMessages'] = []
  const resolvedModels: string[] = []
  const executed: StubPi['executed'] = []
  const toolExecutes = new Map<string, ToolDefinition['execute']>()
  const commandHandlers = new Map<string, (args: string, ctx: unknown) => unknown | Promise<unknown>>()
  const defaultResolve = (spec: string) => ({ id: spec, family: 'test' })
  let resolveResult: ((spec: string) => unknown) | unknown = defaultResolve
  let contextUsage: { tokens: number; contextWindow: number; percent: number } | undefined = { tokens: 12_000, contextWindow: 200_000, percent: 6 }

  const ctx = () => ({
    sessionManager: {
      getSessionId: () => sessionId,
      getCwd: () => '/workspaces/test',
      getSessionDir: () => '/workspaces/test/.omp/sessions',
      getSessionFile: () => undefined,
      getSessionName: () => undefined,
      getArtifactsDir: () => null,
      getArtifactManager: () => null,
      allocateArtifactPath: async () => ({ id: 'art-1' }),
      saveArtifact: async () => 'art-1',
      getArtifactPath: async () => null,
      getLeafId: () => null,
      getLeafEntry: () => undefined,
      getEntry: () => undefined,
      getLabel: () => undefined,
      getBranch: () => [],
      getHeader: () => null,
      getEntries: () => [],
      getTree: () => [],
      getUsageStatistics: () => ({}),
      putBlob: async () => ({}),
      putBlobSync: () => ({}),
    },
    ui: {
      notify: (message: string, type?: 'info' | 'warning' | 'error') => { notifications.push({ message, type }) },
      setStatus: () => {},
    },
    cwd: '/workspaces/test',
    models: {
      list: () => [],
      current: () => ({ id: 'resolved' }),
      resolve: (spec: string) => {
        resolvedModels.push(spec)
        return typeof resolveResult === 'function' ? (resolveResult as (s: string) => unknown)(spec) : resolveResult
      },
      family: () => 'test',
    },
    mode: 'tui',
    model: { id: 'resolved' },
    getContextUsage: () => contextUsage,
    hasUI: true,
    isIdle: () => true,
    logger: { debug() {}, info() {}, warn() {}, error() {} },
  })

  const pi = {
    zod: makeZod(),
    arktype: makeZod(),
    typebox: undefined,
    logger: { debug() {}, info() {}, warn() {}, error() {} },
    registerTool: (def: ToolDefinition) => {
      toolExecutes.set(def.name, def.execute)
      registered.push({
        name: def.name,
        label: def.label,
        description: def.description,
        hidden: def.hidden,
        defaultInactive: def.defaultInactive,
      })
    },
    on: (event: string, handler: (e: unknown, ctx: unknown) => unknown | Promise<unknown>) => {
      const list = handlers.get(event) ?? []
      list.push(handler)
      handlers.set(event, list)
    },
    registerCommand: (name: string, options: { description?: string; handler: (args: string, ctx: unknown) => unknown | Promise<unknown> }) => {
      commandHandlers.set(name, options.handler)
      commands.push({ name, description: options.description })
    },
    sendMessage: (message: unknown, options?: unknown) => { sentMessages.push({ message, options }) },
    appendEntry: (type: string, data: unknown) => { entries.push({ type, data }) },
    exec: async () => ({ stdout: '', stderr: '', exitCode: 0 }),
  } as unknown as ExtensionAPI

  return {
    pi,
    registered,
    handlers,
    entries,
    commands,
    notifications,
    sentMessages,
    resolvedModels,
    executed,
    setSessionId: (id: string) => { sessionId = id },
    setResolveResult: (value: unknown) => { resolveResult = value },
    setContextUsage: (value) => { contextUsage = value },
    makeCtx: () => ctx(),
    getTool: (name) => {
      const execute = toolExecutes.get(name)
      const def = registered.find(r => r.name === name)
      if (!def) return undefined
      return { def, execute }
    },
    fire: async (event, payload = {}, c = {}) => {
      const list = handlers.get(event)
      if (!list || list.length === 0) throw new Error(`no handler for ${event}`)
      const fullCtx = { ...ctx(), ...(c as object) }
      const results: unknown[] = []
      for (const h of list) results.push(await h(payload, fullCtx))
      return results
    },
    runCommand: async (name, args, c = {}) => {
      const h = commandHandlers.get(name)
      if (!h) throw new Error(`no command ${name}`)
      return h(args, { ...ctx(), ...(c as object) })
    },
  }
}
