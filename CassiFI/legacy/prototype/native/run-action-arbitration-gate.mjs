import { writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { encodeActionCandidates, CANONICAL_KINDS } from './cassi-semantic-field-encoder.mjs'

const OUTPUT = resolve(process.cwd(), 'action-arbitration-gate.json')
const KINDS = CANONICAL_KINDS
const ORDER = new Map(KINDS.map((kind, index) => [kind, index]))

const couplings = new Map([
  ['answer|retrieve', -0.25], ['retrieve|answer', 0.30],
  ['answer|clarify', -0.35], ['clarify|answer', -0.35],
  ['answer|abstain', -0.35], ['abstain|answer', -0.35],
  ['retrieve|stop', -0.20], ['stop|retrieve', -0.20],
  ['clarify|stop', -0.20], ['stop|clarify', -0.20],
  ['think|answer', 0.15], ['answer|think', 0.15],
  ['think|stop', -0.15], ['stop|think', -0.15],
  ['tool|answer', 0.20], ['answer|tool', 0.20],
  ['tool|stop', -0.20], ['stop|tool', -0.20],
  ['abstain|stop', -0.25], ['stop|abstain', -0.25],
])

function candidate(kind, features) {
  return {
    id: kind,
    kind,
    support: 0.05,
    goalAlignment: 0.05,
    urgency: 0.05,
    contradiction: 0.05,
    missingInformation: 0.05,
    risk: 0.05,
    cost: 0.05,
    ...features,
  }
}

function item(id, expected, emphasis) {
  const candidates = KINDS.map((kind) => candidate(kind, kind === expected ? emphasis : {}))
  return { id, expected, candidates }
}

const BOARD = [
  item('answer-1', 'answer', { support: 0.95, goalAlignment: 0.95, urgency: 0.70, contradiction: 0.02, missingInformation: 0.02, risk: 0.02, cost: 0.02 }),
  item('answer-2', 'answer', { support: 0.85, goalAlignment: 0.90, urgency: 0.65, contradiction: 0.05, missingInformation: 0.05, risk: 0.05, cost: 0.05 }),
  item('answer-3', 'answer', { support: 0.80, goalAlignment: 0.85, urgency: 0.60, contradiction: 0.06, missingInformation: 0.05, risk: 0.04, cost: 0.04 }),
  item('retrieve-1', 'retrieve', { support: 0.92, goalAlignment: 0.95, urgency: 0.85, contradiction: 0.03, missingInformation: 0.08, risk: 0.05, cost: 0.08 }),
  item('retrieve-2', 'retrieve', { support: 0.86, goalAlignment: 0.90, urgency: 0.75, contradiction: 0.06, missingInformation: 0.12, risk: 0.05, cost: 0.08 }),
  item('retrieve-3', 'retrieve', { support: 0.82, goalAlignment: 0.88, urgency: 0.70, contradiction: 0.07, missingInformation: 0.15, risk: 0.06, cost: 0.10 }),
  item('clarify-1', 'clarify', { support: 0.90, goalAlignment: 0.92, urgency: 0.80, contradiction: 0.04, missingInformation: 0.10, risk: 0.07, cost: 0.10 }),
  item('clarify-2', 'clarify', { support: 0.84, goalAlignment: 0.88, urgency: 0.72, contradiction: 0.06, missingInformation: 0.15, risk: 0.08, cost: 0.10 }),
  item('clarify-3', 'clarify', { support: 0.80, goalAlignment: 0.85, urgency: 0.68, contradiction: 0.08, missingInformation: 0.18, risk: 0.10, cost: 0.10 }),
  item('think-1', 'think', { support: 0.90, goalAlignment: 0.90, urgency: 0.80, contradiction: 0.08, missingInformation: 0.05, risk: 0.05, cost: 0.12 }),
  item('think-2', 'think', { support: 0.85, goalAlignment: 0.87, urgency: 0.74, contradiction: 0.10, missingInformation: 0.07, risk: 0.06, cost: 0.13 }),
  item('think-3', 'think', { support: 0.80, goalAlignment: 0.84, urgency: 0.70, contradiction: 0.12, missingInformation: 0.08, risk: 0.07, cost: 0.14 }),
  item('tool-1', 'tool', { support: 0.92, goalAlignment: 0.94, urgency: 0.82, contradiction: 0.04, missingInformation: 0.08, risk: 0.05, cost: 0.10 }),
  item('tool-2', 'tool', { support: 0.86, goalAlignment: 0.89, urgency: 0.76, contradiction: 0.06, missingInformation: 0.10, risk: 0.06, cost: 0.12 }),
  item('tool-3', 'tool', { support: 0.80, goalAlignment: 0.85, urgency: 0.70, contradiction: 0.08, missingInformation: 0.12, risk: 0.08, cost: 0.14 }),
  item('abstain-1', 'abstain', { support: 0.82, goalAlignment: 0.85, urgency: 0.70, contradiction: 0.08, missingInformation: 0.12, risk: 0.12, cost: 0.12 }),
  item('abstain-2', 'abstain', { support: 0.78, goalAlignment: 0.82, urgency: 0.68, contradiction: 0.10, missingInformation: 0.14, risk: 0.14, cost: 0.13 }),
  item('abstain-3', 'abstain', { support: 0.74, goalAlignment: 0.80, urgency: 0.66, contradiction: 0.12, missingInformation: 0.16, risk: 0.16, cost: 0.14 }),
  item('stop-1', 'stop', { support: 0.92, goalAlignment: 0.95, urgency: 0.75, contradiction: 0.02, missingInformation: 0.02, risk: 0.02, cost: 0.02 }),
  item('stop-2', 'stop', { support: 0.86, goalAlignment: 0.90, urgency: 0.70, contradiction: 0.04, missingInformation: 0.04, risk: 0.04, cost: 0.04 }),
  item('stop-3', 'stop', { support: 0.80, goalAlignment: 0.85, urgency: 0.65, contradiction: 0.05, missingInformation: 0.05, risk: 0.05, cost: 0.05 }),
]

function choose(scores) {
  return [...scores].sort((left, right) => right.score - left.score || ORDER.get(left.kind) - ORDER.get(right.kind))[0]
}

function scalar(deposits) {
  return choose(deposits.map((deposit) => ({ kind: deposit.kind, score: deposit.cy - deposit.ci })))
}

function field(deposits) {
  let state = deposits.map((deposit) => ({ kind: deposit.kind, y: deposit.cy, i: deposit.ci }))
  for (let step = 0; step < 5; step += 1) {
    state = state.map((current) => {
      let dy = -0.08 * current.y
      let di = -0.08 * current.i
      for (const peer of state) {
        if (peer.kind === current.kind) continue
        const w = couplings.get(`${current.kind}|${peer.kind}`) ?? 0
        dy += 0.20 * w * (peer.y - peer.i)
        di += 0.20 * w * (peer.i - peer.y)
      }
      return { kind: current.kind, y: Math.min(1, Math.max(0, current.y + dy)), i: Math.min(1, Math.max(0, current.i + di)) }
    })
  }
  return { choice: choose(state.map(({ kind, y, i }) => ({ kind, score: y - i }))), state }
}

const rows = BOARD.map((entry) => {
  const encoded = encodeActionCandidates(entry.candidates, { enabled: true })
  if (!encoded.applied) throw new Error(`${entry.id}: ${encoded.reason}`)
  const scalarChoice = scalar(encoded.deposits)
  const noEvolutionChoice = scalar(encoded.deposits)
  const fieldResult = field(encoded.deposits)
  return { id: entry.id, expected: entry.expected, scalar: scalarChoice, noEvolution: noEvolutionChoice, field: fieldResult.choice, state: fieldResult.state }
})
const scalarAccuracy = rows.filter((row) => row.scalar.kind === row.expected).length
const noEvolutionAccuracy = rows.filter((row) => row.noEvolution.kind === row.expected).length
const fieldAccuracy = rows.filter((row) => row.field.kind === row.expected).length
const finite = rows.every((row) => row.state.every((cell) => Number.isFinite(cell.y) && Number.isFinite(cell.i) && cell.y >= 0 && cell.y <= 1 && cell.i >= 0 && cell.i <= 1))
const verdict = scalarAccuracy !== noEvolutionAccuracy || !finite
  ? 'INVALID'
  : fieldAccuracy > scalarAccuracy ? 'SUPPORTS' : fieldAccuracy === scalarAccuracy ? 'NULL' : 'CONTRADICTS'
const report = { protocol: 'CassiQwen L10 action arbitration gate', rows, accuracy: { scalar: scalarAccuracy, noEvolution: noEvolutionAccuracy, field: fieldAccuracy, total: BOARD.length }, finite, verdict }
await writeFile(OUTPUT, `${JSON.stringify(report, null, 2)}\n`, 'utf8')
console.log(JSON.stringify({ verdict, accuracy: report.accuracy, finite }, null, 2))
if (verdict === 'INVALID') process.exitCode = 1
