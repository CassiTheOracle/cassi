import { writeFile } from 'node:fs/promises'
import { performance } from 'node:perf_hooks'
import { resolve } from 'node:path'
import { rankCandidatesByField } from './cassi-field-candidate-mapper.mjs'

const BASE_URL = (process.env.CASSI_QWEN_BASE_URL ?? 'http://127.0.0.1:8080').replace(/\/+$/, '')
const MODEL = process.env.CASSI_QWEN_MODEL
  ?? 'C:/Users/Carina/workspaces/Cassi/CassiQwen/Qwen3.8-27B-Q4_K_M.gguf'
const OUTPUT = resolve(process.cwd(), 'field-retrieval-gate.json')

const PROJECTION = [
  { x: 0.290322580645161, y: -0.354838709677419, z: 0.67741935483871, q: 0.19971212884439 },
  { x: 0.290322580645161, y: -0.419354838709677, z: 0.67741935483871, q: 0.0941064028914262 },
  { x: 0.290322580645161, y: -0.354838709677419, z: 0.612903225806452, q: 0.0941060578995814 },
  { x: 0.290322580645161, y: -0.419354838709677, z: 0.612903225806452, q: 0.0443439469163787 },
  { x: 0.225806451612903, y: -0.354838709677419, z: 0.67741935483871, q: 0.00554844662012527 },
  { x: 0.354838709677419, y: -0.354838709677419, z: 0.67741935483871, q: 0.00554844662012527 },
  { x: 0.225806451612903, y: -0.419354838709677, z: 0.67741935483871, q: 0.00261457884843892 },
  { x: 0.354838709677419, y: -0.419354838709677, z: 0.67741935483871, q: 0.00261457884843892 },
]

const BOARD = [
  {
    id: 'alpha', correctId: 'E-ALPHA-2',
    query: 'Which evidence ID states that the CassiQwen field bridge is read-only?',
    candidates: [
      { id: 'E-ALPHA-1', text: 'The bridge can deposit and step the field for every model request.' },
      { id: 'E-ALPHA-2', text: 'The field bridge issues only ping, state, and project read commands.' },
      { id: 'E-ALPHA-3', text: 'The bridge modifies Qwen logits from the top-q field cells.' },
    ],
  },
  {
    id: 'beta', correctId: 'E-BETA-3',
    query: 'Which evidence ID states that Qwen thinking must be explicitly disabled for short deterministic completions?',
    candidates: [
      { id: 'E-BETA-1', text: 'A larger context window always disables Qwen reasoning automatically.' },
      { id: 'E-BETA-2', text: 'The field projection removes the need for a Qwen chat template setting.' },
      { id: 'E-BETA-3', text: 'Set chat_template_kwargs.enable_thinking to false for short deterministic final answers.' },
    ],
  },
  {
    id: 'gamma', correctId: 'E-GAMMA-1',
    query: 'Which evidence ID states the calibrated projection coordinate map uses N - 1?',
    candidates: [
      { id: 'E-GAMMA-1', text: 'Projection vertices use 2 times g divided by N minus 1, then subtract 1.' },
      { id: 'E-GAMMA-2', text: 'Projection coordinates use the cell-center denominator N.' },
      { id: 'E-GAMMA-3', text: 'Projection ranks are independent of grid coordinates.' },
    ],
  },
  {
    id: 'delta', correctId: 'E-DELTA-2',
    query: 'Which evidence ID reports the fixed Qwen generation baseline in tokens per second?',
    candidates: [
      { id: 'E-DELTA-1', text: 'The fixed baseline generated 136.950 tokens per second.' },
      { id: 'E-DELTA-2', text: 'The fixed baseline generated 36.161 tokens per second.' },
      { id: 'E-DELTA-3', text: 'The fixed baseline generated 0.1997 tokens per second.' },
    ],
  },
  {
    id: 'epsilon', correctId: 'E-EPSILON-3',
    query: 'Which evidence ID says the L6 mapper does not interpret q as factual truth?',
    candidates: [
      { id: 'E-EPSILON-1', text: 'A high q cell certifies that a candidate is factually true.' },
      { id: 'E-EPSILON-2', text: 'The mapper converts q directly into the final Qwen answer.' },
      { id: 'E-EPSILON-3', text: 'The mapper uses q only for a candidate-order permutation, not truth.' },
    ],
  },
  {
    id: 'zeta', correctId: 'E-ZETA-1',
    query: 'Which evidence ID says the model server is loopback-only?',
    candidates: [
      { id: 'E-ZETA-1', text: 'The server binds to 127.0.0.1 and is not exposed on the LAN.' },
      { id: 'E-ZETA-2', text: 'The server binds to every network interface for remote access.' },
      { id: 'E-ZETA-3', text: 'The server requires a public endpoint for field observations.' },
    ],
  },
]

function promptFor(item, candidates) {
  return `Use only the evidence below. Answer with exactly one evidence ID and no other text.\n\nQuestion: ${item.query}\n\nEvidence:\n${candidates.map(({ id, text }) => `[${id}] ${text}`).join('\n')}`
}

async function complete(prompt) {
  const started = performance.now()
  const response = await fetch(`${BASE_URL}/v1/chat/completions`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      model: MODEL,
      messages: [{ role: 'user', content: prompt }],
      temperature: 0,
      max_tokens: 32,
      stream: false,
      chat_template_kwargs: { enable_thinking: false },
    }),
  })
  const text = await response.text()
  if (!response.ok) throw new Error(`HTTP ${response.status}: ${text}`)
  const payload = JSON.parse(text)
  const message = payload?.choices?.[0]?.message
  if (typeof message?.content !== 'string' || (typeof message?.reasoning_content === 'string' && message.reasoning_content.length > 0)) {
    throw new Error('response did not contain a usable non-thinking final content')
  }
  return { content: message.content, elapsedMs: performance.now() - started, usage: payload.usage ?? null, timings: payload.timings ?? null }
}

async function runArm(item, arm, candidates) {
  try {
    const response = await complete(promptFor(item, candidates))
    return { item: item.id, arm, candidateOrder: candidates.map(({ id }) => id), correctId: item.correctId, response: response.content, pass: response.content.trim() === item.correctId, ...response }
  } catch (error) {
    return { item: item.id, arm, candidateOrder: candidates.map(({ id }) => id), correctId: item.correctId, error: error instanceof Error ? error.message : String(error), pass: false }
  }
}

const run = { protocol: 'CassiQwen L7 field candidate-order retrieval gate', startedAt: new Date().toISOString(), arms: [], verdict: null }
for (const item of BOARD) {
  const baseline = item.candidates
  const mapped = rankCandidatesByField(item.candidates, PROJECTION, { enabled: true })
  if (!mapped.applied) throw new Error(`field mapping failed for ${item.id}: ${mapped.reason}`)
  run.arms.push(await runArm(item, 'baseline', baseline))
  run.arms.push(await runArm(item, 'field', mapped.candidates))
}
const baseline = run.arms.filter((arm) => arm.arm === 'baseline')
const field = run.arms.filter((arm) => arm.arm === 'field')
if (run.arms.some((arm) => arm.error)) run.verdict = 'INVALID'
else {
  const baselineScore = baseline.filter((arm) => arm.pass).length
  const fieldScore = field.filter((arm) => arm.pass).length
  run.scores = { baseline: baselineScore, field: fieldScore, total: BOARD.length }
  run.verdict = fieldScore > baselineScore ? 'SUPPORTS' : fieldScore === baselineScore ? 'NULL' : 'CONTRADICTS'
}
run.finishedAt = new Date().toISOString()
await writeFile(OUTPUT, `${JSON.stringify(run, null, 2)}\n`, 'utf8')
console.log(JSON.stringify({ verdict: run.verdict, scores: run.scores }, null, 2))
if (run.verdict === 'INVALID') process.exitCode = 1
