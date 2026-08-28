import { mkdir, writeFile } from 'node:fs/promises'
import { performance } from 'node:perf_hooks'
import { resolve } from 'node:path'

const BASE_URL = (process.env.CASSI_QWEN_BASE_URL ?? 'http://127.0.0.1:8080').replace(/\/+$/, '')
const EXPECTED_MODEL = process.env.CASSI_QWEN_MODEL
  ?? 'C:/Users/Carina/workspaces/Cassi/CassiQwen/Qwen3.8-27B-Q4_K_M.gguf'
const OUTPUT_PATH = resolve(process.cwd(), 'baseline-receipt.json')

const BOARD = [
  {
    id: 'echo_ready',
    prompt: 'Reply with exactly: CASSI_LOCAL_READY',
    maxTokens: 16,
    evaluate: (content) => content.trim() === 'CASSI_LOCAL_READY',
  },
  {
    id: 'arithmetic',
    prompt: 'What is 17 multiplied by 6? Reply with only the integer.',
    maxTokens: 16,
    evaluate: (content) => content.trim() === '102',
  },
  {
    id: 'reverse_word',
    prompt: 'Reverse the letters in cassi. Reply with only the reversed word.',
    maxTokens: 16,
    evaluate: (content) => content.trim() === 'issac',
  },
  {
    id: 'json_shape',
    prompt: 'Return exactly this JSON object and nothing else: {"cassi":true,"rungs":3}',
    maxTokens: 32,
    evaluate: (content) => {
      try {
        return JSON.stringify(JSON.parse(content)) === JSON.stringify({ cassi: true, rungs: 3 })
      } catch {
        return false
      }
    },
  },
  {
    id: 'short_explanation',
    prompt: 'In one sentence, define a loopback network address.',
    maxTokens: 64,
    evaluate: (content) => content.trim().length > 0,
  },
]

function median(values) {
  if (values.length === 0) return null
  const ordered = [...values].sort((left, right) => left - right)
  const midpoint = Math.floor(ordered.length / 2)
  return ordered.length % 2 === 0
    ? (ordered[midpoint - 1] + ordered[midpoint]) / 2
    : ordered[midpoint]
}

async function requestJson(path, init = undefined) {
  const response = await fetch(`${BASE_URL}${path}`, init)
  const body = await response.text()
  if (!response.ok) {
    throw new Error(`${path} returned HTTP ${response.status}: ${body}`)
  }
  try {
    return JSON.parse(body)
  } catch (error) {
    throw new Error(`${path} returned malformed JSON: ${error instanceof Error ? error.message : String(error)}`)
  }
}

function modelId(models) {
  if (!Array.isArray(models?.data) || typeof models.data[0]?.id !== 'string') {
    throw new Error('/v1/models response did not contain a first string model id')
  }
  return models.data[0].id
}

async function main() {
  const run = {
    protocol: 'CassiQwen L2 baseline performance receipt',
    startedAt: new Date().toISOString(),
    baseUrl: BASE_URL,
    expectedModel: EXPECTED_MODEL,
    decision: null,
    health: null,
    model: null,
    results: [],
    aggregates: null,
  }

  try {
    run.health = await requestJson('/health')
  } catch (error) {
    run.decision = 'INVALID'
    run.error = `health check failed: ${error instanceof Error ? error.message : String(error)}`
    await persist(run)
    process.exitCode = 1
    return
  }

  try {
    const models = await requestJson('/v1/models')
    run.model = modelId(models)
    if (run.model !== EXPECTED_MODEL) {
      throw new Error(`expected model ${EXPECTED_MODEL}, received ${run.model}`)
    }
  } catch (error) {
    run.decision = 'INVALID'
    run.error = `model identity check failed: ${error instanceof Error ? error.message : String(error)}`
    await persist(run)
    process.exitCode = 1
    return
  }

  for (const [index, item] of BOARD.entries()) {
    const started = performance.now()
    const result = {
      id: item.id,
      requestClass: index === 0 ? 'first-request' : 'resident-request',
      prompt: item.prompt,
      maxTokens: item.maxTokens,
      outcome: null,
      elapsedMs: null,
      content: null,
      reasoningContent: null,
      usage: null,
      timings: null,
      error: null,
    }

    try {
      const payload = await requestJson('/v1/chat/completions', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          model: run.model,
          messages: [{ role: 'user', content: item.prompt }],
          temperature: 0,
          max_tokens: item.maxTokens,
          stream: false,
          chat_template_kwargs: { enable_thinking: false },
        }),
      })
      const message = payload?.choices?.[0]?.message
      result.elapsedMs = performance.now() - started
      result.content = typeof message?.content === 'string' ? message.content : null
      result.reasoningContent = typeof message?.reasoning_content === 'string'
        ? message.reasoning_content
        : null
      result.usage = payload?.usage ?? null
      result.timings = payload?.timings ?? null

      if (result.content === null) {
        result.outcome = 'ERROR'
        result.error = 'response did not contain string final content'
      } else if (result.reasoningContent !== null && result.reasoningContent.length > 0) {
        result.outcome = 'ERROR'
        result.error = 'response returned reasoning content while thinking was disabled'
      } else {
        result.outcome = item.evaluate(result.content) ? 'PASS' : 'FAIL'
      }
    } catch (error) {
      result.elapsedMs = performance.now() - started
      result.outcome = 'ERROR'
      result.error = error instanceof Error ? error.message : String(error)
    }

    run.results.push(result)
  }

  const exactItems = run.results.slice(0, 4)
  const completed = run.results.filter((result) => result.outcome !== 'ERROR')
  const timed = run.results.filter((result) => result.outcome !== 'ERROR' && result.timings)
  run.aggregates = {
    exactBoard: `${exactItems.filter((result) => result.outcome === 'PASS').length}/4`,
    serviceBoard: `${completed.length}/5`,
    medianClientWallMs: median(completed.map((result) => result.elapsedMs)),
    medianPromptTokensPerSecond: median(
      timed.map((result) => result.timings.prompt_per_second).filter(Number.isFinite),
    ),
    medianGeneratedTokensPerSecond: median(
      timed.map((result) => result.timings.predicted_per_second).filter(Number.isFinite),
    ),
  }
  run.decision = run.results.some((result) => result.outcome === 'ERROR')
    ? 'FAIL'
    : exactItems.some((result) => result.outcome !== 'PASS')
      ? 'FAIL'
      : 'PASS'
  run.finishedAt = new Date().toISOString()
  await persist(run)
  console.log(JSON.stringify({ decision: run.decision, aggregates: run.aggregates }, null, 2))
  if (run.decision !== 'PASS') process.exitCode = 1
}

async function persist(run) {
  await mkdir(resolve(process.cwd()), { recursive: true })
  await writeFile(OUTPUT_PATH, `${JSON.stringify(run, null, 2)}\n`, 'utf8')
  console.log(`Wrote ${OUTPUT_PATH}`)
}

await main()
