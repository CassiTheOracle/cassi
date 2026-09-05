import net from 'node:net'

const DEFAULT_HOST = '127.0.0.1'
const DEFAULT_PORT = 7599
const DEFAULT_TIMEOUT_MS = 2_000
const DEFAULT_PROJECTION_K = 8

function finiteNumber(value) {
  return typeof value === 'number' && Number.isFinite(value)
}

function unavailable(reason) {
  return { available: false, reason }
}

function validateState(response) {
  if (response?.ok !== true || response?.cmd !== 'state') {
    throw new Error('invalid state response envelope')
  }
  for (const key of ['step', 't', 'mean_ey', 'mean_ei', 'max_eps2']) {
    if (!finiteNumber(response[key])) throw new Error(`state ${key} must be finite`)
  }
  if (response.step < 0 || response.t < 0 || response.max_eps2 < 0) {
    throw new Error('state contains an invalid non-negative field')
  }
  return {
    step: response.step,
    t: response.t,
    meanEy: response.mean_ey,
    meanEi: response.mean_ei,
    maxEps2: response.max_eps2,
  }
}

function validateProjection(response, k) {
  if (response?.ok !== true || response?.cmd !== 'project' || !Array.isArray(response.cells)) {
    throw new Error('invalid project response envelope')
  }
  if (response.cells.length < 1 || response.cells.length > k) {
    throw new Error(`project cell count must be within 1..${k}`)
  }
  const cells = response.cells.map((cell, index) => {
    if (typeof cell !== 'object' || cell === null) throw new Error(`project cell ${index} is invalid`)
    for (const key of ['x', 'y', 'z', 'ey', 'ei', 'q']) {
      if (!finiteNumber(cell[key])) throw new Error(`project cell ${index} ${key} must be finite`)
    }
    if (cell.q < 0) throw new Error(`project cell ${index} q must be non-negative`)
    return {
      x: cell.x,
      y: cell.y,
      z: cell.z,
      ey: cell.ey,
      ei: cell.ei,
      q: cell.q,
    }
  })
  return {
    step: finiteNumber(response.step) ? response.step : null,
    t: finiteNumber(response.t) ? response.t : null,
    cells,
  }
}

async function withTimeout(promise, timeoutMs, label) {
  let timer
  try {
    return await Promise.race([
      promise,
      new Promise((_, reject) => {
        timer = setTimeout(() => reject(new Error(`${label} timed out after ${timeoutMs}ms`)), timeoutMs)
      }),
    ])
  } finally {
    clearTimeout(timer)
  }
}

class JsonLineClient {
  constructor(socket, timeoutMs) {
    this.socket = socket
    this.timeoutMs = timeoutMs
    this.buffer = ''
    this.pending = []
    socket.setEncoding('utf8')
    socket.on('data', (chunk) => this.#onData(chunk))
    socket.on('error', (error) => this.#rejectPending(error))
    socket.on('close', () => this.#rejectPending(new Error('field bridge closed the connection')))
  }

  #onData(chunk) {
    this.buffer += chunk
    let newline
    while ((newline = this.buffer.indexOf('\n')) >= 0) {
      const line = this.buffer.slice(0, newline)
      this.buffer = this.buffer.slice(newline + 1)
      const next = this.pending.shift()
      if (!next) continue
      try {
        next.resolve(JSON.parse(line))
      } catch (error) {
        next.reject(new Error(`field bridge returned malformed JSON: ${error instanceof Error ? error.message : String(error)}`))
      }
    }
  }

  #rejectPending(error) {
    while (this.pending.length > 0) this.pending.shift().reject(error)
  }

  request(command) {
    return withTimeout(new Promise((resolve, reject) => {
      this.pending.push({ resolve, reject })
      this.socket.write(`${JSON.stringify(command)}\n`, (error) => {
        if (!error) return
        const pending = this.pending.pop()
        pending?.reject(error)
      })
    }), this.timeoutMs, command.cmd)
  }

  close() {
    this.socket.destroy()
  }
}

async function connect(host, port, timeoutMs) {
  const socket = new net.Socket()
  await withTimeout(new Promise((resolve, reject) => {
    socket.once('error', reject)
    socket.connect(port, host, () => {
      socket.off('error', reject)
      resolve()
    })
  }), timeoutMs, 'field bridge connection')
  return new JsonLineClient(socket, timeoutMs)
}

/**
 * Reads an optional, bounded observation from the Cassi mind engine.
 * The adapter is read-only: it never clears, deposits into, steps, reads out,
 * or snapshots the field, and callers must keep any future use default-off.
 */
export async function observeCassiField({
  enabled = false,
  host = DEFAULT_HOST,
  port = DEFAULT_PORT,
  timeoutMs = DEFAULT_TIMEOUT_MS,
  projectionK = DEFAULT_PROJECTION_K,
} = {}) {
  if (!enabled) return unavailable('field observation is disabled')
  if (!Number.isInteger(port) || port < 1 || port > 65_535) return unavailable('field bridge port is invalid')
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) return unavailable('field bridge timeout is invalid')
  if (!Number.isInteger(projectionK) || projectionK < 1 || projectionK > DEFAULT_PROJECTION_K) {
    return unavailable(`projectionK must be an integer within 1..${DEFAULT_PROJECTION_K}`)
  }

  let client
  try {
    client = await connect(host, port, timeoutMs)
    const ping = await client.request({ cmd: 'ping' })
    if (ping?.ok !== true || ping?.cmd !== 'ping') throw new Error('invalid ping response envelope')
    const state = validateState(await client.request({ cmd: 'state' }))
    const projection = validateProjection(await client.request({ cmd: 'project', k: projectionK }), projectionK)
    return {
      available: true,
      bridge: { host, port },
      state,
      projection,
    }
  } catch (error) {
    return unavailable(error instanceof Error ? error.message : String(error))
  } finally {
    client?.close()
  }
}
