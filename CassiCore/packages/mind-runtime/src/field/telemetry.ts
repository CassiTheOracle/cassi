import { once } from 'node:events'
import { Worker } from 'node:worker_threads'
import * as net from 'node:net'

const PHI = (1 + Math.sqrt(5)) / 2
const DEFAULT_HOST = '127.0.0.1'
const DEFAULT_PORT = 7599
const DEFAULT_TIMEOUT_MS = 1_500
const DEFAULT_MAX_PAYLOAD_BYTES = 8 * 1024 * 1024
const DEFAULT_MAX_CELLS = 64 * 64 * 64

export interface FieldTelemetryConfig {
  host?: string
  port?: number
  timeoutMs?: number
  maxPayloadBytes?: number
  gridN?: number
  identityTolerance?: number
  /** Hard cap on decoded grid cells (default 64³). */
  maxCells?: number
}

export interface FieldTelemetryStatus {
  readonly host: string
  readonly port: number
  readonly connected: boolean
  readonly lastReadAt: number | null
  readonly lastError: string | null
}

export interface FieldBalanceSummary {
  readonly meanRho: number
  readonly meanEpsilon: number
  readonly meanFieldPower: number
  readonly meanCoherence: number
}

export interface ThetaTemporalResultant {
  readonly resultant: number
  readonly weightedMeanAbsoluteIncrement: number
  readonly samples: number
}

export interface JProxySummary {
  readonly rms: number
  readonly samples: number
}

export interface FixedHelicalScanSummary {
  readonly canonicalSpiral: false
  readonly bestValue: number
  readonly bestAxis: 'x' | 'y' | 'z' | null
  readonly bestMode: number
  readonly modeZero: readonly [number, number, number]
  readonly samples: number
}

export interface FieldTelemetrySnapshot {
  readonly step: number | null
  readonly time: number | null
  readonly gridN: number
  readonly cells: number
  readonly ey: Float32Array
  readonly ei: Float32Array
  /** q_b64 is the engine's field-power readout; it must equal EY² + EI². */
  readonly fieldPower: Float32Array
  /** eps2_b64 is the engine's epsilon-square readout; it must equal (EY - φ EI)². */
  readonly eps2: Float32Array
  readonly balance: FieldBalanceSummary
  readonly thetaTemporalResultant: ThetaTemporalResultant
  readonly jProxy: JProxySummary
  readonly helicalScan: FixedHelicalScanSummary
}

export type ReadoutReply = {
  ok?: unknown
  cmd?: unknown
  step?: unknown
  t?: unknown
  ey_b64?: unknown
  ei_b64?: unknown
  q_b64?: unknown
  eps2_b64?: unknown
}

type Pending = {
  resolve: (line: Buffer | null) => void
  timer: NodeJS.Timeout
}

export type ThetaSnapshot = {
  theta: Float64Array
  power: Float64Array
}

export interface FieldDecodeConfig {
  maxPayloadBytes: number
  maxCells: number
  gridN?: number
  identityTolerance: number
}

export interface FieldDecodeResult {
  snapshot: FieldTelemetrySnapshot
  nextTheta: ThetaSnapshot
}

/** Lazy, read-only 7599 client. It only ever sends the readout command. */
export class MindFieldTelemetry {
  private readonly config: Required<Pick<FieldTelemetryConfig, 'host' | 'port' | 'timeoutMs' | 'maxPayloadBytes' | 'maxCells' | 'identityTolerance'>> & Pick<FieldTelemetryConfig, 'gridN'>
  private socket: net.Socket | null = null
  private connected = false
  private closed = false
  private chunks: Buffer[] = []
  private bufferedBytes = 0
  private pending: Pending | null = null
  private lastReadAt: number | null = null
  private lastError: string | null = null
  private previousTheta: ThetaSnapshot | null = null

  constructor(config: FieldTelemetryConfig = {}) {
    this.config = {
      host: config.host ?? DEFAULT_HOST,
      port: config.port ?? DEFAULT_PORT,
      timeoutMs: config.timeoutMs ?? DEFAULT_TIMEOUT_MS,
      maxPayloadBytes: config.maxPayloadBytes ?? DEFAULT_MAX_PAYLOAD_BYTES,
      maxCells: config.maxCells ?? DEFAULT_MAX_CELLS,
      gridN: config.gridN,
      identityTolerance: config.identityTolerance ?? 1e-4,
    }
  }

  status(): FieldTelemetryStatus {
    return {
      host: this.config.host,
      port: this.config.port,
      connected: this.connected,
      lastReadAt: this.lastReadAt,
      lastError: this.lastError,
    }
  }

  async read(): Promise<FieldTelemetrySnapshot | null> {
    if (this.closed) return null

    try {
      const line = await this.requestReadout()
      if (!line) return null

      const snapshot = await this.decode(line)
      this.lastReadAt = Date.now()
      this.lastError = null
      return snapshot
    } catch (error) {
      this.lastError = error instanceof Error ? error.message : String(error)
      this.markOffline()
      return null
    }
  }

  close(): void {
    if (this.closed) return
    this.closed = true
    this.markOffline()
  }

  private async requestReadout(): Promise<Buffer | null> {
    if (!this.socket || !this.connected) {
      if (!(await this.connect())) return null
    }

    return new Promise<Buffer | null>((resolve) => {
      const timer = setTimeout(() => {
        if (this.pending?.resolve === resolve) this.pending = null
        resolve(null)
        this.markOffline()
      }, this.config.timeoutMs)

      this.pending = { resolve, timer }
      this.socket?.write('{"cmd":"readout"}\n')
    })
  }

  private connect(): Promise<boolean> {
    if (this.closed) return Promise.resolve(false)

    return new Promise((resolve) => {
      const socket = net.createConnection({ host: this.config.host, port: this.config.port })
      let settled = false
      const timer = setTimeout(() => {
        socket.destroy()
        if (!settled) {
          settled = true
          resolve(false)
        }
      }, this.config.timeoutMs)

      socket.once('connect', () => {
        clearTimeout(timer)
        if (settled) return
        settled = true
        this.socket = socket
        this.connected = true
        this.chunks = []
        this.bufferedBytes = 0
        socket.on('data', (chunk) => this.onData(Buffer.from(chunk)))
        socket.on('error', () => this.markOffline())
        socket.on('close', () => this.markOffline())
        resolve(true)
      })

      socket.once('error', () => {
        clearTimeout(timer)
        if (!settled) {
          settled = true
          resolve(false)
        }
      })
    })
  }

  private onData(chunk: Buffer): void {
    if (this.bufferedBytes + chunk.length > this.config.maxPayloadBytes) {
      this.failPending(new Error('field telemetry payload exceeds maximum'))
      this.markOffline()
      return
    }

    const newline = chunk.indexOf(0x0a)
    if (newline < 0) {
      this.chunks.push(chunk)
      this.bufferedBytes += chunk.length
      return
    }

    const prefix = chunk.subarray(0, newline)
    if (prefix.length > 0) {
      this.chunks.push(prefix)
      this.bufferedBytes += prefix.length
    }
    const line = this.chunks.length === 1
      ? this.chunks[0]
      : Buffer.concat(this.chunks, this.bufferedBytes)
    const remainder = chunk.subarray(newline + 1)
    this.chunks = remainder.length > 0 ? [remainder] : []
    this.bufferedBytes = remainder.length

    const pending = this.pending
    this.pending = null
    if (pending) {
      clearTimeout(pending.timer)
      pending.resolve(line)
    }
  }

  private failPending(error: Error): void {
    this.lastError = error.message
    const pending = this.pending
    this.pending = null
    if (pending) {
      clearTimeout(pending.timer)
      pending.resolve(null)
    }
  }

  private markOffline(): void {
    this.connected = false
    const socket = this.socket
    this.socket = null
    if (socket) {
      socket.removeAllListeners()
      socket.destroy()
    }
    this.chunks = []
    this.bufferedBytes = 0
    this.previousTheta = null
    const pending = this.pending
    this.pending = null
    if (pending) {
      clearTimeout(pending.timer)
      pending.resolve(null)
    }
  }

  private async decode(line: Buffer): Promise<FieldTelemetrySnapshot> {
    const decodeConfig: FieldDecodeConfig = {
      maxPayloadBytes: this.config.maxPayloadBytes,
      maxCells: this.config.maxCells,
      gridN: this.config.gridN,
      identityTolerance: this.config.identityTolerance,
    }
    if (import.meta.url.endsWith('.ts')) {
      const reply = JSON.parse(line.toString('utf8')) as ReadoutReply
      if (reply.ok !== true || reply.cmd !== 'readout') throw new Error('invalid-readout')
      const result = decodeFieldTelemetryReply(reply, decodeConfig, this.previousTheta)
      this.previousTheta = result.nextTheta
      return result.snapshot
    }

    const payload = Uint8Array.from(line)
    const worker = new Worker(new URL('./telemetry-decode-worker.js', import.meta.url), {
      workerData: {
        payload,
        config: decodeConfig,
        previousTheta: this.previousTheta,
      },
    })
    try {
      const signal = AbortSignal.timeout(this.config.timeoutMs)
      const [message] = await once(worker, 'message', { signal }) as [{
        ok: boolean
        result?: FieldDecodeResult
        error?: string
      }]
      if (!message.ok || !message.result) throw new Error(message.error ?? 'field-decode-failed')
      this.previousTheta = message.result.nextTheta
      return message.result.snapshot
    } finally {
      await worker.terminate()
    }
  }
}

/** Pure CPU decode used only inside the telemetry worker (exported for that entry). */
export function decodeFieldTelemetryReply(
  reply: ReadoutReply,
  config: FieldDecodeConfig,
  previousTheta: ThetaSnapshot | null,
): FieldDecodeResult {
  const ey = decodeFloat32(reply.ey_b64, 'ey_b64', config.maxPayloadBytes)
  const ei = decodeFloat32(reply.ei_b64, 'ei_b64', config.maxPayloadBytes)
  const fieldPower = decodeFloat32(reply.q_b64, 'q_b64', config.maxPayloadBytes)
  const eps2 = decodeFloat32(reply.eps2_b64, 'eps2_b64', config.maxPayloadBytes)

  if (
    ey.length === 0
    || ey.length > config.maxCells
    || ey.length !== ei.length
    || ey.length !== fieldPower.length
    || ey.length !== eps2.length
  ) {
    throw new Error('field telemetry arrays exceed the cell budget or have incompatible shapes')
  }

  const n = config.gridN ?? Math.round(Math.cbrt(ey.length))
  if (!Number.isInteger(n) || n < 1 || n * n * n !== ey.length) {
    throw new Error('field telemetry array is not a cubic grid')
  }

  const phases = new Float64Array(ey.length)
  const powers = new Float64Array(ey.length)
  let rhoSum = 0
  let epsilonSum = 0
  let powerSum = 0
  let coherenceSum = 0
  let jSquaredSum = 0

  for (let i = 0; i < ey.length; i += 1) {
    const yang = ey[i]
    const yin = ei[i]
    const rho = yang + yin
    const epsilon = yang - PHI * yin
    const power = yang * yang + yin * yin

    if (
      !nearlyEqual(fieldPower[i], power, config.identityTolerance)
      || !nearlyEqual(eps2[i], epsilon * epsilon, config.identityTolerance)
    ) {
      throw new Error('field telemetry identity check failed')
    }

    const coherenceDenominator = rho * rho + PHI ** -2 + epsilon * epsilon
    phases[i] = Math.atan2(yin, yang)
    powers[i] = power
    rhoSum += rho
    epsilonSum += epsilon
    powerSum += power
    coherenceSum += (rho * rho) / coherenceDenominator
  }

  for (let i = 0; i < ey.length; i += 1) {
    const xPlus = indexAt(i, n, 0, 1)
    const yPlus = indexAt(i, n, 1, 1)
    const zPlus = indexAt(i, n, 2, 1)
    const xMinus = indexAt(i, n, 0, -1)
    const yMinus = indexAt(i, n, 1, -1)
    const zMinus = indexAt(i, n, 2, -1)
    const dEyDx = (ey[xPlus] - ey[xMinus]) * 0.5
    const dEyDy = (ey[yPlus] - ey[yMinus]) * 0.5
    const dEyDz = (ey[zPlus] - ey[zMinus]) * 0.5
    const dEiDx = (ei[xPlus] - ei[xMinus]) * 0.5
    const dEiDy = (ei[yPlus] - ei[yMinus]) * 0.5
    const dEiDz = (ei[zPlus] - ei[zMinus]) * 0.5
    const jx = ey[i] * dEiDx - ei[i] * dEyDx
    const jy = ey[i] * dEiDy - ei[i] * dEyDy
    const jz = ey[i] * dEiDz - ei[i] * dEyDz
    jSquaredSum += jx * jx + jy * jy + jz * jz
  }

  const temporal = temporalMetric(phases, powers, previousTheta)
  const snapshot: FieldTelemetrySnapshot = {
    step: typeof reply.step === 'number' ? reply.step : null,
    time: typeof reply.t === 'number' ? reply.t : null,
    gridN: n,
    cells: ey.length,
    ey,
    ei,
    fieldPower,
    eps2,
    balance: {
      meanRho: rhoSum / ey.length,
      meanEpsilon: epsilonSum / ey.length,
      meanFieldPower: powerSum / ey.length,
      meanCoherence: coherenceSum / ey.length,
    },
    thetaTemporalResultant: temporal,
    jProxy: {
      rms: Math.sqrt(jSquaredSum / Math.max(1, ey.length * 3)),
      samples: ey.length * 3,
    },
    helicalScan: {
      ...helicalScan(phases, powers, n),
      canonicalSpiral: false,
    },
  }
  return { snapshot, nextTheta: { theta: phases, power: powers } }
}

function decodeFloat32(value: unknown, name: string, maxBytes: number): Float32Array {
  if (
    typeof value !== 'string' ||
    !/^[A-Za-z0-9+/]*={0,2}$/.test(value) ||
    value.length % 4 !== 0
  ) {
    throw new Error(`invalid ${name}`)
  }

  const bytes = Buffer.from(value, 'base64')
  if (bytes.length > maxBytes || bytes.length % 4 !== 0) {
    throw new Error(`invalid ${name} size`)
  }

  const out = new Float32Array(bytes.length / 4)
  for (let i = 0; i < out.length; i += 1) {
    out[i] = bytes.readFloatLE(i * 4)
    if (!Number.isFinite(out[i])) throw new Error(`nonfinite ${name}`)
  }
  return out
}

function nearlyEqual(a: number, b: number, tolerance: number): boolean {
  return Math.abs(a - b) <= tolerance * Math.max(1, Math.abs(a), Math.abs(b))
}

function wrapAngle(angle: number): number {
  return Math.atan2(Math.sin(angle), Math.cos(angle))
}

function indexAt(index: number, n: number, axis: number, direction: number): number {
  const stride = axis === 0 ? n * n : axis === 1 ? n : 1
  const coordinate = axis === 0
    ? Math.floor(index / (n * n))
    : axis === 1
      ? Math.floor((index % (n * n)) / n)
      : index % n
  const wrapped = (coordinate + direction + n) % n
  return index + (wrapped - coordinate) * stride
}


function temporalMetric(
  currentTheta: Float64Array,
  currentPower: Float64Array,
  previous: ThetaSnapshot | null,
): ThetaTemporalResultant {
  if (!previous || previous.theta.length !== currentTheta.length) {
    return { resultant: 0, weightedMeanAbsoluteIncrement: 0, samples: 0 }
  }

  let real = 0
  let imaginary = 0
  let totalWeight = 0
  let weightedIncrement = 0
  for (let i = 0; i < currentTheta.length; i += 1) {
    const weight = Math.sqrt(Math.max(0, currentPower[i] * previous.power[i]))
    const increment = wrapAngle(currentTheta[i] - previous.theta[i])
    real += weight * Math.cos(increment)
    imaginary += weight * Math.sin(increment)
    totalWeight += weight
    weightedIncrement += weight * Math.abs(increment)
  }

  return {
    resultant: totalWeight === 0 ? 0 : Math.hypot(real, imaginary) / totalWeight,
    weightedMeanAbsoluteIncrement: totalWeight === 0 ? 0 : weightedIncrement / totalWeight,
    samples: currentTheta.length,
  }
}

function helicalScan(
  phases: Float64Array,
  powers: Float64Array,
  n: number,
): Omit<FixedHelicalScanSummary, 'canonicalSpiral'> {
  const axisNames: Array<'x' | 'y' | 'z'> = ['x', 'y', 'z']
  const modeZero: [number, number, number] = [0, 0, 0]
  let totalPower = 0
  for (const power of powers) totalPower += power

  if (totalPower === 0) {
    return { bestValue: 0, bestAxis: null, bestMode: 0, modeZero, samples: phases.length }
  }

  let bestValue = -1
  let bestAxis: 'x' | 'y' | 'z' | null = null
  let bestMode = 0
  for (let axis = 0; axis < 3; axis += 1) {
    for (let mode = -8; mode <= 8; mode += 1) {
      let real = 0
      let imaginary = 0
      for (let i = 0; i < phases.length; i += 1) {
        const coordinate = axis === 0
          ? Math.floor(i / (n * n))
          : axis === 1
            ? Math.floor((i % (n * n)) / n)
            : i % n
        const angle = phases[i] - (2 * Math.PI * mode * coordinate) / n
        real += powers[i] * Math.cos(angle)
        imaginary += powers[i] * Math.sin(angle)
      }
      const value = Math.hypot(real, imaginary) / totalPower
      if (mode === 0) modeZero[axis] = value
      if (value > bestValue) {
        bestValue = value
        bestAxis = axisNames[axis]
        bestMode = mode
      }
    }
  }

  return { bestValue, bestAxis, bestMode, modeZero, samples: phases.length }
}
