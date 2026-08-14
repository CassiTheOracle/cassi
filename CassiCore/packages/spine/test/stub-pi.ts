/**
 * @cassicore/spine — STUBBED ExtensionAPI for contract tests (no live ohmypi).
 *
 * Implements the minimal `ExtensionAPI` surface the spine factory touches so the
 * extension runs headless against a stubbed bridge: registerTool, on, appendEntry,
 * zod (minimal builder — tests don't parse through it), sessionManager.getSessionId(),
 * cwd, models.resolve, logger, exec. Registered tools + lifecycle handlers are recorded.
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
  handlers: Map<string, (e: unknown, ctx: unknown) => void | Promise<void>>
  entries: Array<{ type: string; data: unknown }>
  resolvedModels: string[]
  executed: Array<{ name: string; params: unknown; sessionId: string }>
  setSessionId: (id: string) => void
  setResolveResult: (value: unknown) => void
  makeCtx: () => Record<string, unknown>
  getTool(name: string): RecordedTool | undefined
  fire(event: string, payload?: unknown, ctx?: unknown): Promise<void>
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
  const handlers = new Map<string, (e: unknown, ctx: unknown) => void | Promise<void>>()
  const entries: StubPi['entries'] = []
  const resolvedModels: string[] = []
  const executed: StubPi['executed'] = []
  const toolExecutes = new Map<string, ToolDefinition['execute']>()
  const defaultResolve = (spec: string) => ({ id: spec, family: 'test' })
  let resolveResult: ((spec: string) => unknown) | unknown = defaultResolve

  const ctx = () => ({
    sessionManager: { getSessionId: () => sessionId, getCwd: () => '/workspaces/test' },
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
    on: (event: string, handler: (e: unknown, ctx: unknown) => void | Promise<void>) => {
      handlers.set(event, handler)
    },
    appendEntry: (type: string, data: unknown) => { entries.push({ type, data }) },
    exec: async () => ({ stdout: '', stderr: '', exitCode: 0 }),
  } as unknown as ExtensionAPI

  return {
    pi,
    registered,
    handlers,
    entries,
    resolvedModels,
    executed,
    setSessionId: (id: string) => { sessionId = id },
    setResolveResult: (value: unknown) => { resolveResult = value },
    makeCtx: () => ctx(),
    getTool: (name) => {
      const execute = toolExecutes.get(name)
      const def = registered.find(r => r.name === name)
      if (!def) return undefined
      return { def, execute }
    },
    fire: async (event, payload = {}, c = {}) => {
      const h = handlers.get(event)
      if (!h) throw new Error(`no handler for ${event}`)
      await h(payload, { ...ctx(), ...(c as object) })
    },
  }
}
