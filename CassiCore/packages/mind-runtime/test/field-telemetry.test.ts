import { afterEach, describe, expect, it } from 'vitest'
import { createServer, type Server, type Socket } from 'node:net'
import { MindFieldTelemetry } from '../src/field/telemetry.js'

const servers: Server[] = []
const PHI = (1 + Math.sqrt(5)) / 2

function b64(values: number[]): string {
  const bytes = Buffer.alloc(values.length * 4)
  values.forEach((value, index) => bytes.writeFloatLE(value, index * 4))
  return bytes.toString('base64')
}

function helixReply(phaseOffset = 0) {
  const n = 8
  const ey: number[] = []
  const ei: number[] = []
  const power: number[] = []
  const eps2: number[] = []

  for (let x = 0; x < n; x += 1) {
    for (let y = 0; y < n; y += 1) {
      for (let z = 0; z < n; z += 1) {
        const theta = (2 * Math.PI * x) / n + phaseOffset
        const yang = Math.cos(theta)
        const yin = Math.sin(theta)
        ey.push(yang)
        ei.push(yin)
        power.push(yang * yang + yin * yin)
        const epsilon = yang - PHI * yin
        eps2.push(epsilon * epsilon)
      }
    }
  }

  return {
    ok: true,
    cmd: 'readout',
    step: 4,
    t: 0.2,
    ey_b64: b64(ey),
    ei_b64: b64(ei),
    q_b64: b64(power),
    eps2_b64: b64(eps2),
  }
}

function listen(server: Server): Promise<number> {
  return new Promise((resolve) => {
    server.listen(0, '127.0.0.1', () => {
      const address = server.address() as { port: number }
      resolve(address.port)
    })
  })
}

afterEach(() => {
  for (const server of servers) server.close()
  servers.length = 0
})

describe('MindFieldTelemetry', () => {
  it('reads the canonical field formulas and weighted helix modal order', async () => {
    const commands: string[] = []
    const server = createServer((socket: Socket) => {
      socket.on('data', (data) => {
        commands.push(data.toString())
        socket.write(`${JSON.stringify(helixReply())}\n`)
      })
    })
    servers.push(server)
    const port = await listen(server)

    const snapshot = await new MindFieldTelemetry({ port }).read()
    expect(snapshot).not.toBeNull()
    expect(snapshot?.gridN).toBe(8)
    expect(snapshot?.fieldPower[0]).toBeCloseTo(1)
    expect(snapshot?.balance.meanRho).toBeCloseTo(0, 5)
    expect(snapshot?.balance.meanFieldPower).toBeCloseTo(1)
    expect(snapshot?.balance.meanCoherence).toBeGreaterThanOrEqual(0)
    expect(snapshot?.balance.meanCoherence).toBeLessThanOrEqual(1)
    expect(snapshot?.helicalScan.bestAxis).toBe('x')
    expect(((snapshot?.helicalScan.bestMode ?? 0) % 8 + 8) % 8).toBe(1)
    expect(snapshot?.helicalScan.bestValue).toBeCloseTo(1, 5)
    expect(snapshot?.helicalScan.modeZero[0]).toBeCloseTo(0, 5)
    expect(snapshot?.helicalScan.canonicalSpiral).toBe(false)
    expect(snapshot?.thetaTemporalResultant.samples).toBe(0)
    expect(commands).toEqual(['{"cmd":"readout"}\n'])
  })

  it('computes cellwise weighted temporal continuity against the prior readout', async () => {
    let reads = 0
    const server = createServer((socket: Socket) => {
      socket.on('data', () => {
        socket.write(`${JSON.stringify(helixReply(reads === 0 ? 0 : Math.PI / 4))}\n`)
        reads += 1
      })
    })
    servers.push(server)
    const port = await listen(server)
    const telemetry = new MindFieldTelemetry({ port })

    expect((await telemetry.read())?.thetaTemporalResultant.samples).toBe(0)
    const second = await telemetry.read()
    expect(second?.thetaTemporalResultant.resultant).toBeCloseTo(1, 5)
    expect(second?.thetaTemporalResultant.weightedMeanAbsoluteIncrement).toBeCloseTo(Math.PI / 4, 5)
    expect(second?.thetaTemporalResultant.samples).toBe(512)
  })

  it.each([
    ['malformed base64', { ...helixReply(), ey_b64: '!' }],
    ['shape mismatch', { ...helixReply(), ei_b64: b64([0]) }],
    ['nonfinite', { ...helixReply(), ey_b64: b64([Infinity]) }],
    ['identity mismatch', { ...helixReply(), q_b64: b64(new Array(512).fill(2)) }],
    ['wrong command', { ...helixReply(), cmd: 'step' }],
  ])('rejects %s replies', async (_name, response) => {
    const server = createServer((socket: Socket) => socket.on('data', () => socket.write(`${JSON.stringify(response)}\n`)))
    servers.push(server)
    const port = await listen(server)
    expect(await new MindFieldTelemetry({ port, timeoutMs: 100 }).read()).toBeNull()
  })

  it('degrades cleanly when the field server is unavailable', async () => {
    const telemetry = new MindFieldTelemetry({ port: 1, timeoutMs: 20 })
    expect(telemetry.status().connected).toBe(false)
    expect(await telemetry.read()).toBeNull()
    expect(telemetry.status().connected).toBe(false)
    telemetry.close()
    telemetry.close()
  })
})
