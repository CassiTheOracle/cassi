/**
 * Backfill worker — embeds engram batches using vindex gate vectors.
 *
 * Each worker loads its own vindex handle (mmap shared via OS page cache).
 * Receives batches via parentPort messages, transfers Float32Array embeddings
 * back via zero-copy ArrayBuffer transfer.
 *
 * Spawned by BackfillWorkerPool in index.ts.
 */
import { parentPort, workerData } from 'node:worker_threads'
import { LarqlKnowledgeProvider } from '../aurora/larql-provider.js'
import type { ILogger } from '../../../types/interfaces.js'

const noopLogger: ILogger = {
  info() {}, warn() {}, error() {}, debug() {}, child() { return this },
}

interface BatchMessage {
  type: 'batch'
  batchId: number
  batch: Array<{ id: string; content: string }>
}

async function main() {
  const { vindexPath } = workerData as { vindexPath: string }

  const provider = new LarqlKnowledgeProvider(noopLogger)
  await provider.load(vindexPath)

  parentPort?.postMessage({ type: 'ready' })

  parentPort?.on('message', async (msg: BatchMessage) => {
    if (msg.type !== 'batch') return

    const { batchId, batch } = msg
    const ids: string[] = []
    const buffers: ArrayBuffer[] = []

    for (const { id, content } of batch) {
      const emb = provider.gateEmbed(content)
      if (emb) {
        ids.push(id)
        // Detach the ArrayBuffer for zero-copy transfer.
        // After transfer, emb is neutered — don't use it again.
        buffers.push(emb.buffer as ArrayBuffer)
      }
    }

    parentPort?.postMessage(
      { type: 'result', batchId, ids, buffers },
      buffers, // transfer list — these ArrayBuffers are moved, not copied
    )
  })
}

main().catch((err) => {
  parentPort?.postMessage({ type: 'error', message: String(err) })
})
