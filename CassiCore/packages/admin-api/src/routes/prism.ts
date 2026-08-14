import type { ILogger } from '@cassicore/foundation'
import { MnemicField } from '@cassicore/mnemic-field'
import { getDataDir } from '@cassicore/foundation'
import path from 'node:path'
import type http from 'node:http'

export interface PrismRoutesDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
  url: URL
  parts: string[]
}

let mnemicField: MnemicField | undefined

function getField(logger: ILogger, daemon?: any): MnemicField {
  if (mnemicField) return mnemicField
  const dbPath = path.join(getDataDir(), 'mnemic-field.db')
  mnemicField = new MnemicField(logger, dbPath)
  if (daemon) (daemon as any).__mnemicField = mnemicField
  return mnemicField
}

export async function handlePrismRoutes(
  deps: PrismRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
): Promise<boolean> {
  const { daemon, logger, sendJSON, parseBody, url, parts } = deps

  if (parts[0] !== 'prism') return false

  const field = getField(logger, daemon)

  if (parts[1] === 'positions' && !parts[2] && method === 'GET') {
    try {
      const limit = url.searchParams.get('limit') ? Number(url.searchParams.get('limit')) : undefined
      const positions = field.getPositions(limit)
      sendJSON(res, 200, { ok: true, count: positions.length, positions })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  if (parts[1] === 'spatial' && !parts[2] && method === 'POST') {
    try {
      const body = await parseBody(req)
      const engrams = field.querySpatial(body)
      sendJSON(res, 200, { ok: true, count: engrams.length, engrams })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  if (parts[1] === 'neighbors' && parts[2] && !parts[3] && method === 'GET') {
    try {
      const engramId = decodeURIComponent(parts[2])
      const center = field.get(engramId)
      if (!center) {
        sendJSON(res, 404, { error: 'engram not found' })
        return true
      }
      const { engrams, synapses } = field.neighbors(engramId)
      sendJSON(res, 200, { ok: true, center, neighbors: engrams, synapses })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  if (parts[1] === 'kindle' && !parts[2] && method === 'POST') {
    try {
      const body = await parseBody(req)
      const query = body?.query as string
      if (!query) {
        sendJSON(res, 400, { error: 'query is required' })
        return true
      }
      const luminalSet = field.kindle(null, query, {
        complexity: body?.complexity ?? 'normal',
        maxLuminalSize: body?.maxLuminalSize ?? 50,
        recordTrace: true,
      })
      sendJSON(res, 200, { ok: true, luminalSet })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  if (parts[1] === 'stats' && !parts[2] && method === 'GET') {
    try {
      const stats = field.stats()
      sendJSON(res, 200, { ok: true, stats })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  return false
}
