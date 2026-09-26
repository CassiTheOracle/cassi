import { writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'

const OUTPUT = resolve(process.cwd(), 'correction-persistence-board.json')
const CLIP = (value) => Math.min(1, Math.max(0, value))

function cleanScenario(id, family, variant) {
  const events = [
    { type: 'assert', claim: 'old', strength: 0.80, quality: 0.90 },
    { type: 'distractor', topic: `noise-${variant}`, strength: 0.4 },
    { type: 'correct', old: 'old', claim: 'new', strength: 0.90, quality: family === 'mixed' ? 1.0 : 0.85 },
    { type: 'distractor', topic: `noise-${variant + 1}`, strength: 0.5 },
    { type: 'distractor', topic: `noise-${variant + 2}`, strength: 0.5 },
    { type: 'distractor', topic: `noise-${variant + 3}`, strength: 0.5 },
  ]
  if (family === 'repeated-stale') {
    events[3] = { type: 'assert', claim: 'old', strength: 0.18, quality: 0.35 }
    events[4] = { type: 'assert', claim: 'old', strength: 0.18, quality: 0.35 }
  }
  if (family === 'mixed') {
    events[3] = { type: 'assert', claim: 'old', strength: 0.25, quality: 0.20 }
    events[4] = { type: 'assert', claim: 'old', strength: 0.25, quality: 0.20 }
  }
  return { id, family, expected: 'new', events }
}

const BOARD = ['clean', 'repeated-stale', 'mixed'].flatMap((family) => Array.from({ length: 6 }, (_, index) => cleanScenario(`${family}-${index + 1}`, family, index)))

function latestEvent(scenario) {
  return scenario.events.filter((event) => event.type === 'correct').at(-1)?.claim ?? null
}

function recencyScore(scenario) {
  const scores = new Map([['old', 0], ['new', 0]])
  const last = new Map([['old', -1], ['new', -1]])
  scenario.events.forEach((event, index) => {
    if (event.type === 'assert') {
      scores.set(event.claim, scores.get(event.claim) + event.strength * event.quality * (0.85 ** (scenario.events.length - index - 1)))
      last.set(event.claim, index)
    } else if (event.type === 'correct') {
      scores.set(event.claim, scores.get(event.claim) + event.strength * event.quality * (0.85 ** (scenario.events.length - index - 1)))
      last.set(event.claim, index)
    }
  })
  const oldScore = scores.get('old')
  const newScore = scores.get('new')
  return { choice: newScore > oldScore || (newScore === oldScore && last.get('new') > last.get('old')) ? 'new' : 'old', scores: Object.fromEntries(scores) }
}

function persistentState(scenario) {
  const state = { old: { y: 0, i: 0 }, new: { y: 0, i: 0 } }
  const history = []
  for (const event of scenario.events) {
    for (const claim of ['old', 'new']) {
      state[claim].y *= 0.97
      state[claim].i *= 0.97
    }
    if (event.type === 'assert') state[event.claim].y = CLIP(state[event.claim].y + 0.30 * event.strength * event.quality)
    if (event.type === 'correct') {
      state[event.claim].y = CLIP(state[event.claim].y + 0.45 * event.strength * event.quality)
      state[event.old].i = CLIP(state[event.old].i + 0.55 * event.strength * event.quality)
    }
    history.push(JSON.parse(JSON.stringify(state)))
  }
  const scores = { old: state.old.y - state.old.i, new: state.new.y - state.new.i }
  return { choice: scores.new >= scores.old ? 'new' : 'old', scores, history }
}

const rows = BOARD.map((scenario) => {
  const latest = latestEvent(scenario)
  const recency = recencyScore(scenario)
  const persistent = persistentState(scenario)
  const finite = persistent.history.every((state) => ['old', 'new'].every((claim) => Number.isFinite(state[claim].y) && Number.isFinite(state[claim].i) && state[claim].y >= 0 && state[claim].y <= 1 && state[claim].i >= 0 && state[claim].i <= 1))
  return { id: scenario.id, family: scenario.family, expected: scenario.expected, latest, recency, persistent, finite }
})
const latestScore = rows.filter((row) => row.latest === row.expected).length
const recencyScoreTotal = rows.filter((row) => row.recency.choice === row.expected).length
const persistentScore = rows.filter((row) => row.persistent.choice === row.expected).length
const finite = rows.every((row) => row.finite)
const verdict = !finite || latestScore !== BOARD.length
  ? 'INVALID'
  : persistentScore > recencyScoreTotal ? 'PERSISTENCE-SUPPORTS' : persistentScore === recencyScoreTotal ? 'NULL' : 'PERSISTENCE-REGRESSION'
const report = { protocol: 'CassiQwen L12 correction persistence board', scores: { latest: latestScore, recency: recencyScoreTotal, persistent: persistentScore, total: BOARD.length }, finite, rows, verdict }
await writeFile(OUTPUT, `${JSON.stringify(report, null, 2)}\n`, 'utf8')
console.log(JSON.stringify({ verdict, scores: report.scores, finite }, null, 2))
if (verdict === 'INVALID') process.exitCode = 1
