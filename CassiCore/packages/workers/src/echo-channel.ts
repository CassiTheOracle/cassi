import { workerPort } from './vendor/core/worker-ipc.js'
import { rootLogger } from '@cassicore/events'
import type { HostToWorkerMessage } from '@cassicore/foundation'

const logger = rootLogger.child('echo-channel')

workerPort.on('message', (msg: HostToWorkerMessage) => {
  if (msg.type === 'init') {
    // announce ready
    workerPort.postMessage({ type: 'ready' })
    logger.info('echo-channel ready')
    return
  }

  if (msg.type === 'message') {
    const payload = msg.payload
    if (typeof payload === 'string') {
      if (payload === 'crash') {
        throw new Error('deliberate crash — testing recovery')
      }
      workerPort.postMessage({ type: 'message', payload: `echo: ${payload}` })
    } else {
      workerPort.postMessage({ type: 'message', payload: `echo: ${String(payload)}` })
    }
    return
  }

  if (msg.type === 'shutdown') {
    process.exit(0)
  }

  if (msg.type === 'config:update') {
    // for this simple worker, accept config but do nothing
    workerPort.postMessage({ type: 'message', payload: { info: 'config updated' } })
    return
  }
})
