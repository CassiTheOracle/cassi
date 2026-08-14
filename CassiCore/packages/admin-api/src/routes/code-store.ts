/**
 * Code Store Admin API Routes
 *
 * REST endpoints for the codebase-in-database system.
 *
 * Routes:
 *   GET    /code/stats                      — Code store statistics
 *   GET    /code/files                      — List source file paths
 *   GET    /code/file?path=                 — Read a source file from the code store
 *   GET    /code/changesets                 — List changesets
 *   GET    /code/changeset/:id              — Get changeset details
 *   POST   /code/changeset/:id/commit       — Commit a changeset
 *   POST   /code/changeset/:id/verify       — Mark changeset as verified (build passed)
 *   POST   /code/changeset/:id/rollback     — Rollback a changeset
 *   POST   /code/extract                    — Trigger extraction + build
 *   POST   /code/ingest                     — Trigger codebase ingestion
 */

import type http from 'node:http'
import type { ILogger } from '@cassicore/foundation'

interface CodeStoreDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, status: number, data: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
}

function getCodeStore(daemon: any): import('../intelligence/mnemic-field/code-store.js').CodeStore | null {
  // The code store is injected into the ToolExecutor's defaultContext
  // Access via the daemon's toolExecutor reference (set during daemon startup)
  return daemon?.toolExecutor?.defaultContext?._codeStore
    ?? daemon?.__codeStore
    ?? null
}

export async function handleCodeStoreRoutes(
  deps: CodeStoreDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
): Promise<boolean> {
  const { daemon, logger, sendJSON, parseBody } = deps
  const url = new URL(req.url || '/', `http://${req.headers.host || 'localhost'}`)
  const parts = url.pathname.replace(/^\//, '').split('/')

  if (parts[0] !== 'code') return false

  const codeStore = getCodeStore(daemon)
  if (!codeStore) {
    return sendJSON(res, 503, { error: 'CodeStore not available' }), true
  }

  try {
    // GET /code/stats
    if (parts[1] === 'stats' && method === 'GET') {
      const count = codeStore.sourceFileCount()
      const changesets = codeStore.listChangesets(5)
      const latestCommit = codeStore.latestCommittedAt()
      const lastVerified = codeStore.lastVerifiedChangeset()

      return sendJSON(res, 200, {
        sourceFileCount: count,
        latestCommittedAt: latestCommit,
        lastVerifiedChangeset: lastVerified ? {
          id: lastVerified.id,
          description: lastVerified.description,
          committedAt: lastVerified.committedAt,
        } : null,
        recentChangesets: changesets.map(cs => ({
          id: cs.id,
          description: cs.description,
          status: cs.status,
          fileCount: cs.fileCount,
          createdAt: cs.createdAt,
          committedAt: cs.committedAt,
        })),
      }), true
    }

    // GET /code/files
    if (parts[1] === 'files' && method === 'GET') {
      const paths = codeStore.listSourceFilePaths()
      return sendJSON(res, 200, { count: paths.length, files: paths }), true
    }

    // GET /code/file?path=...
    if (parts[1] === 'file' && method === 'GET') {
      const filePath = url.searchParams.get('path')
      if (!filePath) {
        return sendJSON(res, 400, { error: 'Missing path parameter' }), true
      }
      const engram = codeStore.getFileByPath(filePath)
      if (!engram) {
        return sendJSON(res, 404, { error: `Source file not found: ${filePath}` }), true
      }
      return sendJSON(res, 200, {
        id: engram.id,
        filePath,
        content: engram.content,
        metadata: engram.metadata,
        potentiation: engram.potentiation,
        createdAt: engram.createdAt,
        accessedAt: engram.accessedAt,
      }), true
    }

    // GET /code/changesets
    if (parts[1] === 'changesets' && method === 'GET') {
      const limit = parseInt(url.searchParams.get('limit') ?? '20', 10)
      const changesets = codeStore.listChangesets(limit)
      return sendJSON(res, 200, { changesets }), true
    }

    // GET /code/changeset/:id
    if (parts[1] === 'changeset' && parts[2] && !parts[3] && method === 'GET') {
      const cs = codeStore.getChangeset(parts[2])
      if (!cs) {
        return sendJSON(res, 404, { error: `Changeset not found: ${parts[2]}` }), true
      }
      const files = codeStore.getChangesetFiles(parts[2])
      return sendJSON(res, 200, { changeset: cs, files }), true
    }

    // POST /code/changeset/:id/commit
    if (parts[1] === 'changeset' && parts[3] === 'commit' && method === 'POST') {
      const cs = codeStore.commitChangeset(parts[2])
      if (!cs) {
        return sendJSON(res, 404, { error: `Changeset not found: ${parts[2]}` }), true
      }
      return sendJSON(res, 200, { changeset: cs }), true
    }

    // POST /code/changeset/:id/verify
    if (parts[1] === 'changeset' && parts[3] === 'verify' && method === 'POST') {
      const cs = codeStore.verifyChangeset(parts[2])
      if (!cs) {
        return sendJSON(res, 404, { error: `Changeset not found: ${parts[2]}` }), true
      }
      return sendJSON(res, 200, { changeset: cs }), true
    }

    // POST /code/changeset/:id/rollback
    if (parts[1] === 'changeset' && parts[3] === 'rollback' && method === 'POST') {
      const restored = codeStore.rollbackChangeset(parts[2])
      return sendJSON(res, 200, { restored, changesetId: parts[2] }), true
    }

    // POST /code/extract — trigger extraction + build
    if (parts[1] === 'extract' && method === 'POST') {
      const { extractAndBuild } = await import('../entry/code-extractor.js')
      const { getRepoRoot } = await import('@cassicore/foundation')
      const result = extractAndBuild(getRepoRoot())
      return sendJSON(res, result.success ? 200 : 500, result), true
    }

    // POST /code/ingest — trigger codebase ingestion
    if (parts[1] === 'ingest' && method === 'POST') {
      const { CodeIngestor } = await import('../intelligence/mnemic-field/code-ingestor.js')
      const { getRepoRoot } = await import('@cassicore/foundation')
      const ingestor = new CodeIngestor(codeStore, logger)
      const result = await ingestor.ingest({ rootDir: getRepoRoot() })
      return sendJSON(res, 200, result), true
    }

    // POST /code/gitnexus-sync — sync GitNexus symbol graph into mnemic field synapses
    if (parts[1] === 'gitnexus-sync' && method === 'POST') {
      const { GitNexusBridge } = await import('../intelligence/mnemic-field/gitnexus-bridge.js')
      const { getRepoRoot } = await import('@cassicore/foundation')
      const field = (daemon as any).__mnemicFieldForCode ?? null
      if (!field) {
        return sendJSON(res, 503, { error: 'MnemicField not available for GitNexus sync' }), true
      }
      const bridge = new GitNexusBridge(field, codeStore, logger, getRepoRoot())
      const result = bridge.sync()
      return sendJSON(res, 200, result), true
    }

  } catch (err) {
    logger.error('Code store route error', { error: String(err) })
    return sendJSON(res, 500, { error: String(err) }), true
  }

  return false
}
