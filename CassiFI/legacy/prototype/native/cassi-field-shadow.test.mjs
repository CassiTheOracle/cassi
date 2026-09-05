import assert from 'node:assert/strict'
import net from 'node:net'
import test from 'node:test'
import { observeCassiField } from './cassi-field-shadow.mjs'

function validState() {
  return { ok: true, cmd: 'state', step: 7, t: 0.035, mean_ey: 0.1, mean_ei: 0.2, max_eps2: 0.3 }
}

function validProject() {
  return {
    ok: true,
    cmd: 'project',
    step: 7,
    t: 0.035,
    cells: [
      { x: 0.1, y: 0.2, z: 0.3, ey: 1.0, ei: 0.5, q: 1.25 },
      { x: -0.1, y: -0.2, z: -0.3, ey: 0.4, ei: 0.2, q: 0.2 },
    ],
  }
}

async function startBridge(handler) {
  const commands = []
  const server = net.createServer((socket) => {
    let buffer = ''
    socket.setEncoding('utf8')
    socket.on('data', (chunk) => {
      buffer += chunk
      let newline
      while ((newline = buffer.indexOf('\n')) >= 0) {
        const line = buffer.slice(0, newline)
        buffer = buffer.slice(newline + 1)
        const command = JSON.parse(line)
        commands.push(command)
        const response = handler(command, commands)
        if (response !== undefined) socket.write(`${typeof response === 'string' ? response : JSON.stringify(response)}\n`)
      }
    })
  })
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve))
  const address = server.address()
  return {
    commands,
    port: address.port,
    async close() {
      await new Promise((resolve) => server.close(resolve))
    },
  }
}

test('disabled observation opens no connection', async () => {
  const result = await observeCassiField({ enabled: false })
  assert.deepEqual(result, { available: false, reason: 'field observation is disabled' })
})

test('valid bridge response yields an ordered bounded observation', async () => {
  const bridge = await startBridge((command) => {
    if (command.cmd === 'ping') return { ok: true, cmd: 'ping', step: 7, t: 0.035 }
    if (command.cmd === 'state') return validState()
    if (command.cmd === 'project') return validProject()
    throw new Error(`unexpected command ${command.cmd}`)
  })
  try {
    const result = await observeCassiField({ enabled: true, port: bridge.port })
    assert.equal(result.available, true)
    assert.equal(result.state.step, 7)
    assert.deepEqual(result.projection.cells.map((cell) => cell.q), [1.25, 0.2])
    assert.deepEqual(bridge.commands, [{ cmd: 'ping' }, { cmd: 'state' }, { cmd: 'project', k: 8 }])
  } finally {
    await bridge.close()
  }
})

test('connection refusal becomes an unavailable observation', async () => {
  const result = await observeCassiField({ enabled: true, port: 1, timeoutMs: 100 })
  assert.equal(result.available, false)
  assert.match(result.reason, /ECONNREFUSED|connection/i)
})

test('malformed JSON becomes an unavailable observation', async () => {
  const bridge = await startBridge(() => '{not json')
  try {
    const result = await observeCassiField({ enabled: true, port: bridge.port })
    assert.equal(result.available, false)
    assert.match(result.reason, /malformed JSON/)
  } finally {
    await bridge.close()
  }
})

test('non-finite projection data becomes unavailable', async () => {
  const bridge = await startBridge((command) => {
    if (command.cmd === 'ping') return { ok: true, cmd: 'ping' }
    if (command.cmd === 'state') return validState()
    return { ...validProject(), cells: [{ x: 0, y: 0, z: 0, ey: 1, ei: 1, q: null }] }
  })
  try {
    const result = await observeCassiField({ enabled: true, port: bridge.port })
    assert.equal(result.available, false)
    assert.match(result.reason, /project cell 0 q must be finite/)
  } finally {
    await bridge.close()
  }
})

test('timeout becomes unavailable', async () => {
  const bridge = await startBridge(() => undefined)
  try {
    const result = await observeCassiField({ enabled: true, port: bridge.port, timeoutMs: 25 })
    assert.equal(result.available, false)
    assert.match(result.reason, /timed out after 25ms/)
  } finally {
    await bridge.close()
  }
})
