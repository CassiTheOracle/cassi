import type http from 'node:http'
import type { ILogger } from '@cassicore/foundation'
import type { PinealModule } from '@cassicore/cortex-pineal-dialectic'
import type { Domain } from '@cassicore/cortex-pineal-dialectic'
import { DOMAINS } from '@cassicore/cortex-pineal-dialectic'

interface PinealDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, status: number, data: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
}

function getPineal(daemon: any): PinealModule | undefined {
  return daemon?.intelligence?.pineal
}

function extractPathParam(pathname: string, prefix: string): string | undefined {
  if (!pathname.startsWith(prefix)) return undefined
  const param = pathname.slice(prefix.length)
  return param && !param.includes('/') ? decodeURIComponent(param) : undefined
}

export async function handlePinealRoutes(
  deps: PinealDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
): Promise<boolean> {
  const url = new URL(req.url ?? '/', `http://${req.headers.host ?? 'localhost'}`)
  const pathname = url.pathname

  if (!pathname.startsWith('/pineal')) return false

  const pineal = getPineal(deps.daemon)
  if (!pineal) {
    deps.sendJSON(res, 503, { error: 'Pineal module not available' })
    return true
  }

  // GET /pineal/facets — list facets with optional filters
  if (method === 'GET' && pathname === '/pineal/facets') {
    const domain = url.searchParams.get('domain') as Domain | null
    const category = url.searchParams.get('category') ?? undefined
    const active = url.searchParams.get('active')
    const pinned = url.searchParams.get('pinned')
    const scope = url.searchParams.get('scope')
    const minConviction = url.searchParams.get('minConviction')
    const limit = url.searchParams.get('limit')

    const facets = pineal.listFacets({
      domain: domain && DOMAINS.includes(domain as Domain) ? domain as Domain : undefined,
      category,
      active: active !== null ? active !== 'false' : undefined,
      pinned: pinned !== null ? pinned !== 'false' : undefined,
      scope: scope !== null ? (scope === '' ? null : scope) : undefined,
      minConviction: minConviction ? parseFloat(minConviction) : undefined,
      limit: limit ? parseInt(limit, 10) : undefined,
    })

    deps.sendJSON(res, 200, { facets, count: facets.length })
    return true
  }

  // GET /pineal/facets/:id — get single facet
  const facetId = extractPathParam(pathname, '/pineal/facets/')
  if (method === 'GET' && facetId && !pathname.includes('/history') && !pathname.includes('/reinforce') && !pathname.includes('/evolve') && !pathname.includes('/pin') && !pathname.includes('/unpin')) {
    const facet = pineal.getFacet(facetId)
    if (!facet) {
      deps.sendJSON(res, 404, { error: 'Facet not found' })
      return true
    }
    deps.sendJSON(res, 200, facet)
    return true
  }

  // POST /pineal/facets — create new facet
  if (method === 'POST' && pathname === '/pineal/facets') {
    const body = await deps.parseBody(req)
    const { domain, category, content, conviction, salience, provenance, tags, pinned, scope } = body
    if (!domain || !category || !content) {
      deps.sendJSON(res, 400, { error: 'domain, category, and content are required' })
      return true
    }
    if (!DOMAINS.includes(domain)) {
      deps.sendJSON(res, 400, { error: `Invalid domain. Valid: ${DOMAINS.join(', ')}` })
      return true
    }
    const facet = pineal.createFacet({ domain, category, content, conviction, salience, provenance, tags, pinned, scope })
    deps.sendJSON(res, 201, facet)
    return true
  }

  // PATCH /pineal/facets/:id — update facet
  if (method === 'PATCH' && facetId) {
    const body = await deps.parseBody(req)
    const updated = pineal.updateFacet(facetId, body)
    if (!updated) {
      deps.sendJSON(res, 404, { error: 'Facet not found' })
      return true
    }
    deps.sendJSON(res, 200, updated)
    return true
  }

  // POST /pineal/facets/:id/reinforce — reinforce a facet
  if (method === 'POST' && pathname.endsWith('/reinforce')) {
    const id = pathname.replace('/pineal/facets/', '').replace('/reinforce', '')
    const reinforced = pineal.reinforceFacet(id)
    if (!reinforced) {
      deps.sendJSON(res, 404, { error: 'Facet not found or inactive' })
      return true
    }
    deps.sendJSON(res, 200, reinforced)
    return true
  }

  // POST /pineal/facets/:id/pin — pin a facet (guaranteed inclusion in assembly)
  if (method === 'POST' && pathname.endsWith('/pin') && !pathname.endsWith('/unpin')) {
    const id = pathname.replace('/pineal/facets/', '').replace('/pin', '')
    const pinned = pineal.pinFacet(id)
    if (!pinned) {
      deps.sendJSON(res, 404, { error: 'Facet not found' })
      return true
    }
    deps.sendJSON(res, 200, { pinned: true, id })
    return true
  }

  // POST /pineal/facets/:id/unpin — unpin a facet
  if (method === 'POST' && pathname.endsWith('/unpin')) {
    const id = pathname.replace('/pineal/facets/', '').replace('/unpin', '')
    const unpinned = pineal.unpinFacet(id)
    if (!unpinned) {
      deps.sendJSON(res, 404, { error: 'Facet not found' })
      return true
    }
    deps.sendJSON(res, 200, { pinned: false, id })
    return true
  }

  // GET /pineal/pinned — list all pinned facets
  if (method === 'GET' && pathname === '/pineal/pinned') {
    const facets = pineal.listFacets({ pinned: true })
    deps.sendJSON(res, 200, { facets, count: facets.length })
    return true
  }

  // POST /pineal/facets/:id/evolve — evolve a facet
  if (method === 'POST' && pathname.endsWith('/evolve')) {
    const id = pathname.replace('/pineal/facets/', '').replace('/evolve', '')
    const body = await deps.parseBody(req)
    if (!body.content) {
      deps.sendJSON(res, 400, { error: 'content is required' })
      return true
    }
    const evolved = pineal.evolveFacet(id, body.content, body)
    if (!evolved) {
      deps.sendJSON(res, 404, { error: 'Facet not found' })
      return true
    }
    deps.sendJSON(res, 200, evolved)
    return true
  }

  // DELETE /pineal/facets/:id — retire facet
  if (method === 'DELETE' && facetId) {
    const retired = pineal.retireFacet(facetId)
    deps.sendJSON(res, retired ? 200 : 404, { retired })
    return true
  }

  // GET /pineal/facets/:id/history — version chain
  if (method === 'GET' && pathname.endsWith('/history')) {
    const id = pathname.replace('/pineal/facets/', '').replace('/history', '')
    const history = pineal.getFacetHistory(id)
    deps.sendJSON(res, 200, { history })
    return true
  }

  // GET /pineal/domains — domain stats
  if (method === 'GET' && pathname === '/pineal/domains') {
    deps.sendJSON(res, 200, { domains: pineal.getDomainStats() })
    return true
  }

  // GET /pineal/snapshot — full state
  if (method === 'GET' && pathname === '/pineal/snapshot') {
    deps.sendJSON(res, 200, pineal.getSnapshot())
    return true
  }

  // POST /pineal/seed — seed initial facets
  if (method === 'POST' && pathname === '/pineal/seed') {
    const created = pineal.seed()
    deps.sendJSON(res, 200, { seeded: created })
    return true
  }

  // POST /pineal/parse-skills — parse skill files
  if (method === 'POST' && pathname === '/pineal/parse-skills') {
    const body = await deps.parseBody(req)
    const dirs = body.dirs || ['.opencode/skill', '.claude/skills']
    const created = pineal.parseSkills(dirs)
    deps.sendJSON(res, 200, { parsed: created })
    return true
  }

  // GET /pineal/skills — list available skills
  if (method === 'GET' && pathname === '/pineal/skills') {
    deps.sendJSON(res, 200, { skills: pineal.listSkills() })
    return true
  }

  // GET /pineal/skills/:name — load composed skill
  const skillName = extractPathParam(pathname, '/pineal/skills/')
  if (method === 'GET' && skillName) {
    const prompt = pineal.loadSkill(skillName)
    if (!prompt) {
      deps.sendJSON(res, 404, { error: 'Skill not found' })
      return true
    }
    deps.sendJSON(res, 200, { skill: skillName, prompt })
    return true
  }

  return false
}
