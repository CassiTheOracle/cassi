import { writeFile } from 'node:fs/promises'
import { performance } from 'node:perf_hooks'
import { resolve } from 'node:path'

const BASE_URL = (process.env.CASSI_QWEN_BASE_URL ?? 'http://127.0.0.1:8080').replace(/\/+$/, '')
const MODEL = process.env.CASSI_QWEN_MODEL
  ?? 'C:/Users/Carina/workspaces/Cassi/CassiQwen/Qwen3.8-27B-Q4_K_M.gguf'
const OUTPUT = resolve(process.cwd(), 'thinking-policy-board.json')

const BOARD = [
  ['logic_chain', 'Nora is older than Ivo. Ivo is older than Pia. Who is youngest? Reply with only the name.', 'Pia'],
  ['modular_arithmetic', 'What is the remainder when 7 to the power of 4 is divided by 10? Reply with only the integer.', '1'],
  ['syllogism', 'All maps are tools. Some tools are blue. Does it follow that some maps are blue? Reply with only Yes or No.', 'No'],
  ['sequence', 'Complete the sequence: 2, 6, 12, 20, 30, ?. Reply with only the integer.', '42'],
  ['constraint_count', 'A box contains 3 red balls, 4 blue balls, and 5 green balls. How many balls are not blue? Reply with only the integer.', '8'],
  ['conditional_logic', 'If the alarm is armed, the light is on. The light is off. What follows about the alarm? Reply with only: armed, not armed, or unknown.', 'not armed'],
].map(([id, prompt, expected]) => ({ id, prompt, expected }))

const ARMS = [
  { name: 'fast', enableThinking: false, maxTokens: 64 },
  { name: 'deliberate', enableThinking: true, maxTokens: 256 },
]

function median(values) {
  if (values.length === 0) return null
  const sorted = [...values].sort((a, b) => a - b)
  const middle = Math.floor(sorted.length / 2)
  return sorted.length % 2 === 0 ? (sorted[middle - 1] + sorted[middle]) / 2 : sorted[middle]
}

async function complete(item, arm) {
  const started = performance.now()
  const response = await fetch(`${BASE_URL}/v1/chat/completions`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      model: MODEL,
      messages: [{ role: 'user', content: item.prompt }],
      temperature: 0,
      max_tokens: arm.maxTokens,
      stream: false,
      chat_template_kwargs: { enable_thinking: arm.enableThinking },
    }),
  })
  const raw = await response.text()
  if (!response.ok) throw new Error(`HTTP ${response.status}: ${raw}`)
  const payload = JSON.parse(raw)
  const message = payload?.choices?.[0]?.message
  if (typeof message?.content !== 'string') throw new Error('response did not contain string final content')
  return {
    item: item.id,
    arm: arm.name,
    expected: item.expected,
    response: message.content,
    reasoningContent: typeof message.reasoning_content === 'string' ? message.reasoning_content : null,
    pass: message.content.trim() === item.expected,
    elapsedMs: performance.now() - started,
    usage: payload.usage ?? null,
    timings: payload.timings ?? null,
  }
}

const run = { protocol: 'CassiQwen L8 thinking policy capability board', startedAt: new Date().toISOString(), results: [], verdict: null }
for (const item of BOARD) {
  for (const arm of ARMS) {
    try {
      run.results.push(await complete(item, arm))
    } catch (error) {
      run.results.push({ item: item.id, arm: arm.name, expected: item.expected, error: error instanceof Error ? error.message : String(error), pass: false })
    }
  }
}
if (run.results.some((result) => result.error)) run.verdict = 'INVALID'
else {
  const aggregate = {}
  for (const arm of ARMS) {
    const rows = run.results.filter((result) => result.arm === arm.name)
    aggregate[arm.name] = {
      exactScore: rows.filter((result) => result.pass).length,
      totalCompletionTokens: rows.reduce((sum, result) => sum + (result.usage?.completion_tokens ?? 0), 0),
      medianGeneratedTokensPerSecond: median(rows.map((result) => result.timings?.predicted_per_second).filter(Number.isFinite)),
      medianClientWallMs: median(rows.map((result) => result.elapsedMs).filter(Number.isFinite)),
    }
  }
  run.aggregate = aggregate
  const fast = aggregate.fast
  const deliberate = aggregate.deliberate
  run.verdict = deliberate.exactScore > fast.exactScore
    ? 'DELIBERATE-QUALITY-GAIN'
    : deliberate.exactScore < fast.exactScore
      ? 'DELIBERATE-REGRESSION'
      : deliberate.totalCompletionTokens > fast.totalCompletionTokens
        ? 'FAST-PARETO'
        : 'TIE'
}
run.finishedAt = new Date().toISOString()
await writeFile(OUTPUT, `${JSON.stringify(run, null, 2)}\n`, 'utf8')
console.log(JSON.stringify({ verdict: run.verdict, aggregate: run.aggregate }, null, 2))
if (run.verdict === 'INVALID') process.exitCode = 1
