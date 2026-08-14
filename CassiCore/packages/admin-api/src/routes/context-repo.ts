import type http from 'node:http'
import path from 'node:path'
import fs from 'node:fs'

import type { ILogger } from '../../types/interfaces.js'
import type { ContextRepo } from '../intelligence/context-repo/index.js'

interface Deps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, status: number, data: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
}

function getRepo(daemon: any): ContextRepo | undefined {
  return daemon?.intelligence?.contextRepo
}

export async function handleContextRepoRoutes(
  deps: Deps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
): Promise<boolean> {
  const url = new URL(req.url ?? '/', `http://${req.headers.host ?? 'localhost'}`)
  const pathname = url.pathname
  if (!pathname.startsWith('/context-repo')) return false

  const repo = getRepo(deps.daemon)
  if (!repo) {
    deps.sendJSON(res, 503, { error: 'ContextRepo not available' })
    return true
  }

  if (method === 'GET' && pathname === '/context-repo/show') {
    const section = url.searchParams.get('section')
    if (section) {
      const files = repo.fs.listEntities(section)
      deps.sendJSON(res, 200, { section, count: files.length, files })
      return true
    }
    deps.sendJSON(res, 200, {
      system: repo.fs.listEntities('system'),
      laminae: repo.fs.listEntities('laminae'),
      entities: repo.fs.listEntities('entities'),
      skills: repo.fs.listEntities('skills'),
    })
    return true
  }

  if (method === 'GET' && pathname === '/context-repo/log') {
    const limit = url.searchParams.has('limit') ? Number(url.searchParams.get('limit')) : 20
    deps.sendJSON(res, 200, { commits: repo.fs.log(limit) })
    return true
  }

  if (method === 'POST' && pathname === '/context-repo/diff') {
    const body = await deps.parseBody(req)
    const args = Array.isArray(body?.args) ? body.args.map(String) : []
    deps.sendJSON(res, 200, { diff: repo.fs.diff(args) })
    return true
  }

  if (method === 'GET' && pathname === '/context-repo/inspect') {
    const file = url.searchParams.get('file')
    if (!file) { deps.sendJSON(res, 400, { error: 'file required' }); return true }
    // Defensive — disallow escapes
    const safe = path.normalize(file).replace(/^[/\\]+/, '')
    if (safe.startsWith('..')) { deps.sendJSON(res, 400, { error: 'invalid path' }); return true }
    const full = path.join(repo.fs.identity.repoDir, safe)
    if (!fs.existsSync(full)) { deps.sendJSON(res, 404, { error: 'not_found', file: safe }); return true }
    const content = fs.readFileSync(full, 'utf8')
    deps.sendJSON(res, 200, { file: safe, content })
    return true
  }

  if (method === 'POST' && pathname === '/context-repo/rebuild') {
    repo.rebuild()
    deps.sendJSON(res, 200, { ok: true })
    return true
  }

  if (method === 'POST' && pathname === '/context-repo/gc') {
    repo.fs.gc()
    deps.sendJSON(res, 200, { ok: true })
    return true
  }

  if (method === 'GET' && pathname === '/context-repo/stats') {
    deps.sendJSON(res, 200, repo.fs.stats())
    return true
  }

  return false
}
