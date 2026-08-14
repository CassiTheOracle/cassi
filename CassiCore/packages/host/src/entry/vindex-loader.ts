/**
 * vindex-loader.ts — Standalone LARQL vindex sidecar process.
 *
 * Loads the vindex once via N-API and exposes gateKnn / tokenize / featureMeta
 * via HTTP on localhost:7434. Survives daemon restarts — the daemon connects as
 * a client rather than loading the vindex itself.
 *
 * Managed by the supervisor (or systemd):
 *   systemd:  cassi-vindex-loader.service
 *   manual:   tsx core/entry/vindex-loader.ts
 *
 * Process title: cassi:vindex-loader
 */

process.title = 'cassi:vindex-loader'

import http from 'node:http'
import { homedir } from 'node:os'
import { join } from 'node:path'
import { existsSync, readdirSync, statSync } from 'node:fs'

const PORT = 7434
const HOST = '127.0.0.1'

function log(msg: string): void {
  process.stderr.write(`[vindex-loader] ${msg}\n`) // contributing:ignore — standalone process, no repo logger
}

interface VindexHandle { id: number; path: string; config: Record<string, unknown> }
interface FeatureHit { featureIndex: number; score: number; label: string | null }

let larql: any = null
let handle: VindexHandle | null = null

async function loadNativeBindings(): Promise<void> {
  try {
    const module = await import('cassi-larql')
    larql = module
  } catch {
    try {
      const { createRequire } = await import('node:module')
      const require = createRequire(import.meta.url)
      larql = require('cassi-larql')
    } catch {
      throw new Error('cassi-larql native module not found')
    }
  }
}

async function loadVindex(vindexPath?: string): Promise<void> {
  if (!larql) await loadNativeBindings()

  const modelsDir = join(homedir(), '.cassicore', 'models')
  if (!existsSync(modelsDir)) throw new Error(`Models directory not found: ${modelsDir}`)

  if (vindexPath && existsSync(vindexPath)) {
    const h = larql.loadVindexOnly(vindexPath)
    if (h) {
      handle = h
      log(`Loaded: ${vindexPath}`)
      return
    }
  }

  const candidates = readdirSync(modelsDir)
    .filter(n => n.endsWith('.vindex'))
    .map(n => {
      const p = join(modelsDir, n)
      const hasWeights = existsSync(join(p, 'down_weights.bin')) ||
        existsSync(join(p, 'attn_weights_q4k.bin'))
      return { name: n, path: p, mtime: statSync(p).mtimeMs, hasWeights }
    })
    .sort((a, b) => {
      if (a.hasWeights !== b.hasWeights) return a.hasWeights ? 1 : -1
      return b.mtime - a.mtime
    })

  for (const c of candidates) {
    try {
      const h = larql.loadVindexOnly(c.path)
      if (h) {
        handle = h
        log(`Loaded: ${c.name}`)
        return
      }
    } catch {
      // try next
    }
  }

  throw new Error('No vindex could be loaded')
}

function jsonResponse(res: http.ServerResponse, data: unknown, status = 200): void {
  res.writeHead(status, { 'Content-Type': 'application/json' })
  res.end(JSON.stringify(data))
}

function readBody(req: http.IncomingMessage): Promise<string> {
  return new Promise((resolve) => {
    let body = ''
    req.on('data', (chunk: Buffer) => { body += chunk.toString() })
    req.on('end', () => resolve(body))
  })
}

async function handleRequest(req: http.IncomingMessage, res: http.ServerResponse): Promise<void> {
  const url = new URL(req.url ?? '/', `http://${HOST}:${PORT}`)

  try {
    if (req.method === 'GET' && url.pathname === '/health') {
      return jsonResponse(res, {
        status: 'ok',
        loaded: !!handle,
        vindex: handle?.path ?? null,
      })
    }

    if (!handle) {
      return jsonResponse(res, { error: 'Vindex not yet loaded' }, 503)
    }

    if (req.method === 'POST' && url.pathname === '/gate-knn') {
      const body = await readBody(req)
      const { layer, tokenId, topK } = JSON.parse(body)
      const hits: FeatureHit[] = larql.vindexGateKnn(handle, layer, tokenId, topK)
      return jsonResponse(res, { hits })
    }

    if (req.method === 'POST' && url.pathname === '/tokenize') {
      const body = await readBody(req)
      const { text } = JSON.parse(body)
      const tokens: number[] = larql.vindexTokenize(handle, text)
      return jsonResponse(res, { tokens })
    }

    if (req.method === 'GET' && url.pathname === '/config') {
      return jsonResponse(res, handle.config)
    }

    if (req.method === 'POST' && url.pathname === '/feature-meta') {
      const body = await readBody(req)
      const { layer, featureIndex } = JSON.parse(body)
      const meta = larql.vindexFeatureMeta(handle, layer, featureIndex)
      return jsonResponse(res, { meta })
    }

    jsonResponse(res, { error: 'Not found' }, 404)
  } catch (err) {
    log(`Error handling ${req.method} ${url.pathname}: ${String(err)}`)
    jsonResponse(res, { error: String(err) }, 500)
  }
}

async function main(): Promise<void> {
  const vindexPath = process.argv[2] || undefined

  log(`Starting on ${HOST}:${PORT}...`)
  log('Loading vindex...')

  try {
    await loadVindex(vindexPath)
  } catch (err) {
    log(`FATAL: ${String(err)}`)
    process.exit(1)
  }

  const server = http.createServer(handleRequest)
  server.listen(PORT, HOST, () => {
    log(`Listening on ${HOST}:${PORT}`)
  })

  const shutdown = () => {
    log('Shutting down...')
    server.close(() => process.exit(0))
  }
  process.on('SIGTERM', shutdown)
  process.on('SIGINT', shutdown)
}

main().catch((err) => {
  log(`FATAL: ${String(err)}`)
  process.exit(1)
})
