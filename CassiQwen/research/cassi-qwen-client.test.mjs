import assert from 'node:assert/strict'
import test from 'node:test'
import { createCassiQwenClient } from './cassi-qwen-client.mjs'

const MODEL = 'C:/models/Qwen.gguf'

function response(body, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
}

function healthyFetch(handler = undefined) {
  return async (url, init = {}) => {
    const path = new URL(url).pathname
    if (path === '/health') return response({ status: 'ok' })
    if (path === '/v1/models') return response({ data: [{ id: MODEL }] })
    if (path === '/v1/chat/completions') return handler?.(url, init) ?? response({ choices: [{ message: { content: 'ok' }, finish_reason: 'stop' }], usage: { total_tokens: 1 }, timings: { predicted_per_second: 2 } })
    throw new Error(`unexpected path ${path}`)
  }
}

test('readiness validates health and exact model identity', async () => {
  const client = createCassiQwenClient({ expectedModel: MODEL, fetch: healthyFetch() })
  assert.deepEqual(await client.readiness(), { ready: true, model: MODEL })

  const mismatch = createCassiQwenClient({ expectedModel: MODEL, fetch: async (url) => {
    const path = new URL(url).pathname
    return path === '/health' ? response({ status: 'ok' }) : response({ data: [{ id: 'wrong' }] })
  } })
  assert.equal((await mismatch.readiness()).ready, false)
})

test('fast completion sends a bounded non-thinking request and returns a receipt', async () => {
  let request
  const client = createCassiQwenClient({ expectedModel: MODEL, fetch: healthyFetch((_url, init) => {
    request = JSON.parse(init.body)
    return response({ choices: [{ message: { content: 'CASSI_LOCAL_READY' }, finish_reason: 'stop' }], usage: { completion_tokens: 3 }, timings: { predicted_per_second: 4 } })
  }) })
  const result = await client.complete({ prompt: 'ready', mode: 'fast', maxTokens: 16 })
  assert.equal(result.content, 'CASSI_LOCAL_READY')
  assert.equal(result.receipt.fieldMode, 'off')
  assert.equal(request.chat_template_kwargs.enable_thinking, false)
  assert.equal(request.model, MODEL)
})

test('deliberate completion explicitly enables thinking', async () => {
  let request
  const client = createCassiQwenClient({ expectedModel: MODEL, fetch: healthyFetch((_url, init) => {
    request = JSON.parse(init.body)
    return response({ choices: [{ message: { content: '1', reasoning_content: 'work' }, finish_reason: 'stop' }] })
  }) })
  const result = await client.complete({ prompt: 'solve', mode: 'deliberate', maxTokens: 128 })
  assert.equal(result.reasoningContent, 'work')
  assert.equal(request.chat_template_kwargs.enable_thinking, true)
})

test('completion fails before request when readiness fails', async () => {
  let completions = 0
  const client = createCassiQwenClient({ expectedModel: MODEL, fetch: async (url) => {
    const path = new URL(url).pathname
    if (path === '/health') return response({ status: 'down' })
    if (path === '/v1/chat/completions') completions += 1
    return response({ data: [{ id: MODEL }] })
  } })
  await assert.rejects(client.complete({ prompt: 'x', maxTokens: 1 }), /not ready/)
  assert.equal(completions, 0)
})

test('completion rejects missing final content and invalid inputs', async () => {
  const client = createCassiQwenClient({ expectedModel: MODEL, fetch: healthyFetch(() => response({ choices: [{ message: {} }] })) })
  await assert.rejects(client.complete({ prompt: 'x', maxTokens: 1 }), /final string content/)
  await assert.rejects(client.complete({ prompt: '', maxTokens: 1 }), /non-empty prompt/)
  await assert.rejects(client.complete({ prompt: 'x', mode: 'bad', maxTokens: 1 }), /fast or deliberate/)
})
