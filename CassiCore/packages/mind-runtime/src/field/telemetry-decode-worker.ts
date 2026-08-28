import { parentPort, workerData } from 'node:worker_threads'

import {
  decodeFieldTelemetryReply,
  type FieldDecodeConfig,
  type ReadoutReply,
  type ThetaSnapshot,
} from './telemetry.js'

interface TelemetryWorkerData {
  payload: Uint8Array
  config: FieldDecodeConfig
  previousTheta: ThetaSnapshot | null
}

const data = workerData as TelemetryWorkerData

try {
  const reply = JSON.parse(Buffer.from(data.payload).toString('utf8')) as ReadoutReply
  if (reply.ok !== true || reply.cmd !== 'readout') throw new Error('invalid-readout')
  const result = decodeFieldTelemetryReply(reply, data.config, data.previousTheta)
  parentPort?.postMessage({ ok: true, result })
} catch {
  // The readout can contain attacker-controlled bytes; only a static code crosses
  // back to the runtime/log boundary.
  parentPort?.postMessage({ ok: false, error: 'field-decode-failed' })
}
