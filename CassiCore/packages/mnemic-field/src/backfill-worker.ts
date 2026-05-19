/**
 * Backfill worker — embeds engram batches using vindex gate vectors.
 *
 * Uses an absolute require path for the native N-API addon to avoid
 * module resolution issues: under tsx, import.meta.url points to a
 * temp directory that lacks node_modules/cassi-larql.
 *
 * Spawned by BackfillWorkerPool in index.ts.
 */
import { parentPort, workerData } from 'node:worker_threads'
import { createRequire } from 'node:module'
import path from 'node:path'

// Resolve cassi-larql relative to the CASSICORE_ROOT env var (set by
// the daemon and backfill-runner) or fall back to process.cwd().
const root = process.env.CASSICORE_ROOT || process.cwd()
const nativePath = path.resolve(root, 'node_modules/cassi-larql')
const require = createRequire(import.meta.url)
const native = require(nativePath)

interface BatchMessage {
  type: 'batch'
  batchId: number
  batch: Array<{ id: string; content: string }>
}

async function main() {
  const { vindexPath } = workerData as { vindexPath: string }

  // Load the vindex via native N-API (same as LarqlKnowledgeProvider.load)
  const handle = native.loadVindexOnly(vindexPath)
  const config = native.getVindexConfig(handle)

  parentPort?.postMessage({ type: 'ready' })

  parentPort?.on('message', (msg: BatchMessage) => {
    if (msg.type !== 'batch') return

    const { batchId, batch } = msg
    const ids: string[] = []
    const buffers: ArrayBuffer[] = []

    for (const { id, content } of batch) {
      try {
        // Use native gate_embed for speed. Falls back to JS path if
        // native function is unavailable (older binary).
        let emb: Float32Array | null = null

        if (typeof native.gateEmbed === 'function') {
          const buf: Buffer = native.gateEmbed(
            handle, content,
            null, // layers (default L14-L27)
            null, // top_k (default 10)
            null, // min_score (default 0.05)
            null, // patches (none)
          )
          if (buf && buf.byteLength > 0) {
            emb = new Float32Array(buf.buffer, buf.byteOffset, buf.byteLength / 4)
          }
        } else {
          // Fallback JS path
          const tokens = native.vindexTokenize(handle, content)
          if (tokens.length === 0) continue
          const lastToken = tokens[tokens.length - 1]
          const hiddenDim = config.hiddenDim
          const embedding = new Float32Array(hiddenDim)
          const weights: number[] = []
          let totalWeight = 0

          for (let layer = 14; layer <= 27; layer++) {
            const hits = native.vindexGateKnn(handle, layer, lastToken, 10)
            for (const hit of hits) {
              if (hit.score < 0.05) continue
              const vecBuf = native.gateVector(handle, layer, hit.featureIndex)
              if (!vecBuf) continue
              const vec = new Float32Array(vecBuf.buffer, vecBuf.byteOffset, vecBuf.byteLength / 4)
              for (let j = 0; j < hiddenDim; j++) {
                embedding[j] += vec[j] * hit.score
              }
              totalWeight += hit.score
            }
          }

          if (totalWeight > 0) {
            let norm = 0
            for (let j = 0; j < hiddenDim; j++) {
              embedding[j] /= totalWeight
              norm += embedding[j] * embedding[j]
            }
            norm = Math.sqrt(norm)
            if (norm > 0) {
              for (let j = 0; j < hiddenDim; j++) embedding[j] /= norm
            }
          }
          emb = embedding
        }

        if (emb) {
          ids.push(id)
          buffers.push(emb.buffer as ArrayBuffer)
        }
      } catch {
        // Skip engrams that fail embedding (e.g., empty tokenization)
      }
    }

    if (ids.length > 0) {
      parentPort?.postMessage(
        { type: 'result', batchId, ids, buffers },
        buffers,
      )
    } else {
      parentPort?.postMessage(
        { type: 'result', batchId, ids: [], buffers: [] },
      )
    }
  })
}

main().catch((err) => {
  parentPort?.postMessage({ type: 'error', message: String(err) })
})
