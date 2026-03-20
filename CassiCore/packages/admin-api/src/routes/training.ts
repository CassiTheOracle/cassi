/**
 * Admin API routes for the Training Warehouse.
 *
 * GET    /training/stats           — warehouse statistics
 * GET    /training/search          — full-text search over chunks
 * GET    /training/objects         — filtered object search with labels/quality
 * GET    /training/resolve/:ref    — resolve a ref key or object ID to full detail
 * GET    /training/labels          — label distribution (optional ?namespace=)
 * GET    /training/quality/:metric — quality metric distribution
 * GET    /training/annotations     — annotation run summary
 * POST   /training/ingest          — trigger ingest from operational stores
 * POST   /training/tag             — trigger LLM tagging batch
 * GET    /training/export          — export training examples as JSONL
 */

import type http from 'node:http'
import type { ILogger } from '../../types/interfaces.js'

export interface TrainingRoutesDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
  url: URL
  pathname: string
}

export async function handleTrainingRoutes(
  deps: TrainingRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
): Promise<boolean> {
  const { daemon, sendJSON, parseBody, pathname, url } = deps

  if (!pathname.startsWith('/training')) return false

  const warehouse = daemon?.intelligence?.training
  if (!warehouse) {
    sendJSON(res, 503, { error: 'Training warehouse not available' })
    return true
  }

  if (method === 'GET' && pathname === '/training/stats') {
    try {
      sendJSON(res, 200, warehouse.getStats())
    } catch (err) {
      sendJSON(res, 500, { error: 'Failed to get training stats', detail: String(err) })
    }
    return true
  }

  if (method === 'GET' && pathname === '/training/search') {
    try {
      const query = url.searchParams.get('q') || ''
      const limit = Number(url.searchParams.get('limit') || '50')
      const offset = Number(url.searchParams.get('offset') || '0')
      const role = url.searchParams.get('role') || undefined
      const chunkType = url.searchParams.get('chunk_type') || undefined
      const sessionId = url.searchParams.get('session_id') || undefined

      const results = warehouse.searchChunks(query, {
        limit, offset, role, chunkType, sessionId,
      })
      sendJSON(res, 200, { query, results, count: results.length })
    } catch (err) {
      sendJSON(res, 500, { error: 'Search failed', detail: String(err) })
    }
    return true
  }

  if (method === 'GET' && pathname === '/training/objects') {
    try {
      const limit = Number(url.searchParams.get('limit') || '50')
      const offset = Number(url.searchParams.get('offset') || '0')
      const objectTypes = url.searchParams.get('types')?.split(',').filter(Boolean) || undefined
      const sessionId = url.searchParams.get('session_id') || undefined
      const startTime = url.searchParams.get('start_time') ? Number(url.searchParams.get('start_time')) : undefined
      const endTime = url.searchParams.get('end_time') ? Number(url.searchParams.get('end_time')) : undefined

      // Parse label filters: labels=topic:typescript,task:coding
      const labelStr = url.searchParams.get('labels')
      const labels = labelStr
        ? labelStr.split(',').map(l => {
            const [namespace, name] = l.split(':')
            return { namespace, name }
          }).filter(l => l.namespace && l.name)
        : undefined

      // Parse quality filter: min_quality=trainability:0.5
      const qualityStr = url.searchParams.get('min_quality')
      const minQuality = qualityStr
        ? (() => {
            const [metric, val] = qualityStr.split(':')
            return metric && val ? { metric, value: Number(val) } : undefined
          })()
        : undefined

      const results = warehouse.searchObjects({
        limit, offset, objectTypes, sessionId, startTime, endTime, labels, minQuality,
      })
      sendJSON(res, 200, { results, count: results.length })
    } catch (err) {
      sendJSON(res, 500, { error: 'Object search failed', detail: String(err) })
    }
    return true
  }

  if (method === 'GET' && pathname.startsWith('/training/resolve/')) {
    try {
      const ref = decodeURIComponent(pathname.slice('/training/resolve/'.length))
      const result = warehouse.resolve(ref)
      if (!result) {
        sendJSON(res, 404, { error: 'Object not found', ref })
      } else {
        sendJSON(res, 200, result)
      }
    } catch (err) {
      sendJSON(res, 500, { error: 'Resolve failed', detail: String(err) })
    }
    return true
  }

  if (method === 'GET' && pathname === '/training/labels') {
    try {
      const namespace = url.searchParams.get('namespace') || undefined
      const distribution = warehouse.getLabelDistribution(namespace)
      sendJSON(res, 200, { distribution, count: distribution.length })
    } catch (err) {
      sendJSON(res, 500, { error: 'Failed to get label distribution', detail: String(err) })
    }
    return true
  }

  if (method === 'GET' && pathname.startsWith('/training/quality/')) {
    try {
      const metric = pathname.slice('/training/quality/'.length)
      const distribution = warehouse.getQualityDistribution(metric)
      sendJSON(res, 200, { metric, ...distribution })
    } catch (err) {
      sendJSON(res, 500, { error: 'Failed to get quality distribution', detail: String(err) })
    }
    return true
  }

  if (method === 'GET' && pathname === '/training/annotations') {
    try {
      const summary = warehouse.getAnnotationSummary()
      sendJSON(res, 200, summary)
    } catch (err) {
      sendJSON(res, 500, { error: 'Failed to get annotation summary', detail: String(err) })
    }
    return true
  }

  if (method === 'POST' && pathname === '/training/ingest') {
    try {
      const body = await parseBody(req)
      const batchSize = body?.batchSize ?? 500
      const results = warehouse.runIngest({ batchSize })
      sendJSON(res, 200, {
        message: 'Ingest complete',
        results,
        totalIngested: results.reduce((sum: number, r: any) => sum + r.rowsIngested, 0),
        totalChunks: results.reduce((sum: number, r: any) => sum + r.chunksCreated, 0),
      })
    } catch (err) {
      sendJSON(res, 500, { error: 'Ingest failed', detail: String(err) })
    }
    return true
  }

  if (method === 'POST' && pathname === '/training/tag') {
    try {
      const body = await parseBody(req)
      const scope = body?.scope || 'message'
      const batchSize = body?.batchSize ?? 50
      const dryRun = body?.dryRun ?? false

      // The actual LLM must be provided by the daemon's provider system.
      // For now, return what would be tagged without an LLM (dry run).
      if (!body?.llm && !daemon?.intelligence?.tagger) {
        sendJSON(res, 200, {
          message: 'Dry run: no LLM configured for tagging',
          scope,
          batchSize,
          hint: 'Provide an LLM adapter or configure daemon.intelligence.tagger',
        })
        return true
      }

      const llm = daemon.intelligence.tagger
      const result = await warehouse.runTagging(llm, scope, { batchSize, dryRun })
      sendJSON(res, 200, { message: 'Tagging complete', result })
    } catch (err) {
      sendJSON(res, 500, { error: 'Tagging failed', detail: String(err) })
    }
    return true
  }

  if (method === 'GET' && pathname === '/training/export') {
    try {
      const limit = Number(url.searchParams.get('limit') || '100')
      const minTrainability = url.searchParams.get('min_trainability')
        ? Number(url.searchParams.get('min_trainability')) : undefined
      const maxPrivacyRisk = url.searchParams.get('max_privacy_risk')
        ? Number(url.searchParams.get('max_privacy_risk')) : undefined
      const sessionTypes = url.searchParams.get('session_types')?.split(',').filter(Boolean) || undefined
      const format = url.searchParams.get('format') || 'json'

      const examples = warehouse.assembleExamples({
        limit, minTrainability, maxPrivacyRisk, sessionTypes,
      })

      if (format === 'jsonl') {
        res.writeHead(200, {
          'Content-Type': 'application/x-ndjson',
          'Content-Disposition': 'attachment; filename="training-export.jsonl"',
        })
        for (const ex of examples) {
          res.write(JSON.stringify(ex) + '\n')
        }
        res.end()
      } else {
        sendJSON(res, 200, { examples, count: examples.length })
      }
    } catch (err) {
      sendJSON(res, 500, { error: 'Export failed', detail: String(err) })
    }
    return true
  }

  return false
}
