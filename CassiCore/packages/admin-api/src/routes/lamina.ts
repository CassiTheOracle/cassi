import type http from 'node:http'
import type { ILogger } from '../../types/interfaces.js'
import type { LaminaField } from '../intelligence/lamina/index.js'
import type { LaminaScope } from '../intelligence/lamina/types.js'
import { LaminaCasConflict, LaminaOverflow, LaminaAuthorityError } from '../intelligence/lamina/types.js'
import type { AuditStore, RunKind } from '../runtime/audit/index.js'
import { withStep } from '../runtime/audit/index.js'

interface LaminaDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, status: number, data: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
}

function getField(daemon: any): LaminaField | undefined {
  return daemon?.intelligence?.lamina
}

function getAudit(daemon: any): AuditStore | undefined {
  return daemon?.intelligence?.audit
}

function parseScope(s: any): LaminaScope {
  if (!s || typeof s !== 'object') return { kind: 'global' }
  switch (s.kind) {
    case 'session': return { kind: 'session', sessionId: String(s.sessionId ?? '') }
    case 'channel': return { kind: 'channel', channel: String(s.channel ?? '') }
    case 'agent': return { kind: 'agent', agentId: String(s.agentId ?? '') }
    default: return { kind: 'global' }
  }
}

function laminaErrorStatus(err: unknown): number {
  if (err instanceof LaminaCasConflict) return 409
  if (err instanceof LaminaOverflow) return 413
  if (err instanceof LaminaAuthorityError) return 403
  return 400
}

function serializeError(err: unknown): Record<string, unknown> {
  if (err instanceof LaminaCasConflict) {
    return { error: 'cas_conflict', label: err.label, currentHash: err.currentHash, currentContent: err.currentContent }
  }
  if (err instanceof LaminaOverflow) {
    return { error: 'overflow', label: err.label, attempted: err.attemptedSize, limit: err.limit }
  }
  if (err instanceof LaminaAuthorityError) {
    return { error: 'authority', label: err.label, action: err.action, owner: err.ownerAgentId, caller: err.callerAgentId }
  }
  return { error: String(err) }
}

/**
 * Wrap a mutation in an audit run/step so every write carries provenance.
 * Used for MCP-originated edits where there's no enclosing AsyncLocalStorage frame.
 */
function withAuditedStep<T>(
  audit: AuditStore | undefined,
  agentId: string,
  reason: string | undefined,
  fn: () => T,
): T {
  if (!audit) return fn()
  const run = audit.startRun({ kind: 'turn' as RunKind, agentId, goal: 'mcp-lamina-mutation' })
  const step = audit.startStep({ runId: run.id, slot: 'mcp', reason: reason ?? null })
  try {
    return withStep({ runId: run.id, stepId: step.id, agentId, reason }, fn)
  } finally {
    audit.finishStep(step.id, { status: 'completed' })
    audit.finishRun(run.id, 'completed')
  }
}

export async function handleLaminaRoutes(
  deps: LaminaDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
): Promise<boolean> {
  const url = new URL(req.url ?? '/', `http://${req.headers.host ?? 'localhost'}`)
  const pathname = url.pathname
  if (!pathname.startsWith('/lamina')) return false

  const field = getField(deps.daemon)
  const audit = getAudit(deps.daemon)
  if (!field) {
    deps.sendJSON(res, 503, { error: 'LaminaField not available' })
    return true
  }

  // GET /lamina/list
  if (method === 'GET' && pathname === '/lamina/list') {
    const owner = url.searchParams.get('owner') ?? undefined
    const sessionId = url.searchParams.get('sessionId') ?? undefined
    const limit = url.searchParams.has('limit') ? Number(url.searchParams.get('limit')) : undefined
    const list = field.list({
      owner,
      matchScope: sessionId ? { kind: 'session', sessionId } : undefined,
      limit,
    })
    deps.sendJSON(res, 200, { count: list.length, laminae: list })
    return true
  }

  // GET /lamina/read?label=...&scope=...
  if (method === 'GET' && pathname === '/lamina/read') {
    const label = url.searchParams.get('label')
    if (!label) { deps.sendJSON(res, 400, { error: 'label required' }); return true }
    const sessionId = url.searchParams.get('sessionId')
    const scope: LaminaScope = sessionId ? { kind: 'session', sessionId } : { kind: 'global' }
    const lamina = field.read(label, scope)
    if (!lamina) { deps.sendJSON(res, 404, { error: 'not_found', label }); return true }
    deps.sendJSON(res, 200, lamina)
    return true
  }

  // POST /lamina/create
  if (method === 'POST' && pathname === '/lamina/create') {
    const body = await deps.parseBody(req)
    if (!body?.label || !body?.owner) {
      deps.sendJSON(res, 400, { error: 'label and owner required' }); return true
    }
    try {
      const lamina = withAuditedStep(audit, body.owner, body.reason, () =>
        field.create({
          label: body.label,
          content: body.content ?? '',
          description: body.description ?? null,
          owner: body.owner,
          ownerExclusive: !!body.ownerExclusive,
          readOnly: !!body.readOnly,
          scope: parseScope(body.scope),
          tags: body.tags,
          pinned: !!body.pinned,
          charLimit: body.charLimit,
        }, body.owner),
      )
      deps.sendJSON(res, 201, lamina); return true
    } catch (err) {
      deps.sendJSON(res, laminaErrorStatus(err), serializeError(err)); return true
    }
  }

  // POST /lamina/replace
  if (method === 'POST' && pathname === '/lamina/replace') {
    const body = await deps.parseBody(req)
    if (!body?.label || !body?.agentId) { deps.sendJSON(res, 400, { error: 'label and agentId required' }); return true }
    if (body?.content === undefined) { deps.sendJSON(res, 400, { error: 'content required' }); return true }
    try {
      const lamina = withAuditedStep(audit, body.agentId, body.reason, () =>
        field.replace(body.label, {
          expectedHash: body.expectedHash ?? null,
          content: body.content,
          reason: body.reason,
        }, body.agentId, parseScope(body.scope)),
      )
      deps.sendJSON(res, 200, lamina); return true
    } catch (err) {
      deps.sendJSON(res, laminaErrorStatus(err), serializeError(err)); return true
    }
  }

  // POST /lamina/append
  if (method === 'POST' && pathname === '/lamina/append') {
    const body = await deps.parseBody(req)
    if (!body?.label || !body?.agentId || body?.content === undefined) {
      deps.sendJSON(res, 400, { error: 'label, agentId, content required' }); return true
    }
    try {
      const lamina = withAuditedStep(audit, body.agentId, body.reason, () =>
        field.append(body.label, {
          content: body.content,
          separator: body.separator,
          reason: body.reason,
        }, body.agentId, parseScope(body.scope)),
      )
      deps.sendJSON(res, 200, lamina); return true
    } catch (err) {
      deps.sendJSON(res, laminaErrorStatus(err), serializeError(err)); return true
    }
  }

  // POST /lamina/rethink
  if (method === 'POST' && pathname === '/lamina/rethink') {
    const body = await deps.parseBody(req)
    if (!body?.label || !body?.agentId || body?.content === undefined || !body?.reason) {
      deps.sendJSON(res, 400, { error: 'label, agentId, content, reason required' }); return true
    }
    try {
      const lamina = withAuditedStep(audit, body.agentId, body.reason, () =>
        field.rethink(body.label, {
          content: body.content,
          reason: body.reason,
        }, body.agentId, parseScope(body.scope)),
      )
      deps.sendJSON(res, 200, lamina); return true
    } catch (err) {
      deps.sendJSON(res, laminaErrorStatus(err), serializeError(err)); return true
    }
  }

  // GET /lamina/metrics
  if (method === 'GET' && pathname === '/lamina/metrics') {
    deps.sendJSON(res, 200, {
      lamina: field.metrics(),
      audit: audit?.metrics() ?? null,
    })
    return true
  }

  return false
}
