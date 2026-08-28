import { writeFile } from 'node:fs/promises'
import { performance } from 'node:perf_hooks'
import { resolve } from 'node:path'

const BASE_URL = (process.env.CASSI_QWEN_BASE_URL ?? 'http://127.0.0.1:8080').replace(/\/+$/, '')
const MODEL = process.env.CASSI_QWEN_MODEL ?? 'C:/Users/Carina/workspaces/Cassi/CassiQwen/Qwen3.8-27B-Q4_K_M.gguf'
const OUTPUT = resolve(process.cwd(), 'thinking-policy-receipt.json')
const TIMEOUT_MS = 120_000
const BOARD = [
  ['logic_chain', 'Nora is older than Ivo. Ivo is older than Pia. Who is youngest? Reply with only the name.', 'Pia'],
  ['modular_arithmetic', 'What is the remainder when 7 to the power of 4 is divided by 10? Reply with only the integer.', '1'],
].map(([id, prompt, expected]) => ({ id, prompt, expected }))
const ARMS = [
  { name: 'fast', enableThinking: false, maxTokens: 64 },
  { name: 'deliberate', enableThinking: true, maxTokens: 128 },
]

async function json(path, init) {
  const response = await fetch(`${BASE_URL}${path}`, init)
  const raw = await response.text()
  if (!response.ok) throw new Error(`${path} returned HTTP ${response.status}: ${raw}`)
  return JSON.parse(raw)
}

async function complete(item, arm) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS)
  const started = performance.now()
  try {
    const payload = await json('/v1/chat/completions', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      signal: controller.signal,
      body: JSON.stringify({ model: MODEL, messages: [{ role: 'user', content: item.prompt }], temperature: 0, max_tokens: arm.maxTokens, stream: false, chat_template_kwargs: { enable_thinking: arm.enableThinking } }),
    })
    const message = payload?.choices?.[0]?.message
    if (typeof message?.content !== 'string') throw new Error('response did not contain final string content')
    return { item: item.id, arm: arm.name, expected: item.expected, response: message.content, reasoningContent: typeof message.reasoning_content === 'string' ? message.reasoning_content : null, pass: message.content.trim() === item.expected, elapsedMs: performance.now() - started, usage: payload.usage ?? null, timings: payload.timings ?? null }
  } catch (error) {
    return { item: item.id, arm: arm.name, expected: item.expected, error: controller.signal.aborted ? `timed out after ${TIMEOUT_MS}ms` : error instanceof Error ? error.message : String(error), pass: false }
  } finally {
    clearTimeout(timer)
  }
}

const run = { protocol: 'CassiQwen L8b resilient thinking policy receipt', startedAt: new Date().toISOString(), results: [], verdict: null }
try {
  const health = await json('/health')
  const models = await json('/v1/models')
  const id = models?.data?.[0]?.id
  if (health?.status !== 'ok' || id !== MODEL) throw new Error(`identity mismatch: ${id}`)
  run.health = health
  run.model = id
  for (const item of BOARD) for (const arm of ARMS) run.results.push(await complete(item, arm))
  if (run.results.some((result) => result.error)) run.verdict = 'INVALID'
  else if (run.results.some((result) => !result.pass)) run.verdict = 'FAIL'
  else {
    const fastTokens = run.results.filter((result) => result.arm === 'fast').reduce((sum, result) => sum + (result.usage?.completion_tokens ?? 0), 0)
    const deliberateTokens = run.results.filter((result) => result.arm === 'deliberate').reduce((sum, result) => sum + (result.usage?.completion_tokens ?? 0), 0)
    run.cost = { fastCompletionTokens: fastTokens, deliberateCompletionTokens: deliberateTokens }
    run.verdict = deliberateTokens > fastTokens ? 'DELIBERATE-COST-CONFIRMED' : 'TIE'
  }
} catch (error) {
  run.verdict = 'INVALID'
  run.error = error instanceof Error ? error.message : String(error)
}
run.finishedAt = new Date().toISOString()
await writeFile(OUTPUT, `${JSON.stringify(run, null, 2)}\n`, 'utf8')
console.log(JSON.stringify({ verdict: run.verdict, cost: run.cost }, null, 2))
if (run.verdict === 'INVALID' || run.verdict === 'FAIL') process.exitCode = 1
