import { writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { encodeActionCandidates, CANONICAL_KINDS } from './cassi-semantic-field-encoder.mjs'

const OUTPUT = resolve(process.cwd(), 'relational-arbitration-gate.json')
const ORDER = new Map(CANONICAL_KINDS.map((kind, index) => [kind, index]))

function candidate(kind, extra = {}) {
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
    ...extra,
  }
}

function buildCase(id, family, shift) {
  const candidates = CANONICAL_KINDS.map((kind) => candidate(kind))
  const byKind = new Map(candidates.map((entry) => [entry.kind, entry]))
  const answer = byKind.get('answer')
  answer.support = 0.88 - shift
  answer.goalAlignment = 0.90 - shift
  answer.urgency = 0.76 - shift / 2
  answer.contradiction = 0.12 + shift
  answer.missingInformation = 0.08 + shift / 2
  answer.risk = 0.08
  answer.cost = 0.05

  if (family === 'retrieve') {
    Object.assign(byKind.get('retrieve'), { support: 0.62 + shift, goalAlignment: 0.80, urgency: 0.70, contradiction: 0.05, missingInformation: 0.10, risk: 0.05, cost: 0.12 })
    return { id, expected: 'retrieve', candidates, relations: [{ type: 'resolves', source: 'retrieve', target: 'answer' }, { type: 'blocks', source: 'retrieve', target: 'answer' }] }
  }
  if (family === 'clarify') {
    Object.assign(byKind.get('clarify'), { support: 0.60 + shift, goalAlignment: 0.82, urgency: 0.72, contradiction: 0.04, missingInformation: 0.10, risk: 0.06, cost: 0.12 })
    return { id, expected: 'clarify', candidates, relations: [{ type: 'resolves', source: 'clarify', target: 'answer' }, { type: 'blocks', source: 'clarify', target: 'answer' }] }
  }
  if (family === 'think') {
    Object.assign(byKind.get('think'), { support: 0.61 + shift, goalAlignment: 0.83, urgency: 0.73, contradiction: 0.05, missingInformation: 0.06, risk: 0.05, cost: 0.18 })
    return { id, expected: 'think', candidates, relations: [{ type: 'resolves', source: 'think', target: 'answer' }, { type: 'blocks', source: 'think', target: 'answer' }] }
  }
  Object.assign(byKind.get('stop'), { support: 0.88 - shift, goalAlignment: 0.90 - shift, urgency: 0.76, contradiction: 0.07, missingInformation: 0.04, risk: 0.04, cost: 0.03 })
  Object.assign(byKind.get('abstain'), { support: 0.64 + shift, goalAlignment: 0.82, urgency: 0.74, contradiction: 0.05, missingInformation: 0.08, risk: 0.06, cost: 0.12 })
  return { id, expected: 'abstain', candidates, relations: [{ type: 'blocks', source: 'abstain', target: 'stop' }, { type: 'supports', source: 'abstain', target: 'abstain' }] }
}

const families = ['retrieve', 'clarify', 'think', 'abstain']
const BOARD = families.flatMap((family) => [0, 0.02, 0.04, 0.06, 0.08, 0.10].map((shift, index) => buildCase(`${family}-${index + 1}`, family, shift)))

function choose(scores) {
  return [...scores].sort((a, b) => b.score - a.score || ORDER.get(a.kind) - ORDER.get(b.kind))[0]
}

function scalar(deposits) {
  return choose(deposits.map((entry) => ({ kind: entry.kind, score: entry.cy - entry.ci })))
}

function evolve(deposits, relations, useRelations) {
  let state = deposits.map((entry) => ({ kind: entry.kind, y: entry.cy, i: entry.ci }))
  for (let step = 0; step < 5; step += 1) {
    state = state.map((current) => {
      let y = 0.92 * current.y
      let i = 0.92 * current.i
      if (useRelations) {
        for (const relation of relations) {
          if (relation.target !== current.kind) continue
          const source = state.find((entry) => entry.kind === relation.source)
          if (relation.type === 'supports') {
            y += 0.35 * source.y
            i -= 0.35 * source.i
          } else if (relation.type === 'resolves') {
            y += 0.45 * source.y
            i -= 0.45 * source.i
          } else if (relation.type === 'blocks') {
            y -= 0.45 * source.y
            i += 0.45 * source.i
          }
        }
      }
      return { kind: current.kind, y: Math.min(1, Math.max(0, y)), i: Math.min(1, Math.max(0, i)) }
    })
  }
  return { choice: choose(state.map((entry) => ({ kind: entry.kind, score: entry.y - entry.i }))), state }
}

const rows = BOARD.map((entry) => {
  const encoded = encodeActionCandidates(entry.candidates, { enabled: true })
  if (!encoded.applied) throw new Error(`${entry.id}: ${encoded.reason}`)
  const scalarChoice = scalar(encoded.deposits)
  const blind = evolve(encoded.deposits, entry.relations, false)
  const coupled = evolve(encoded.deposits, entry.relations, true)
  return { id: entry.id, expected: entry.expected, scalar: scalarChoice, relationBlind: blind.choice, coupled: coupled.choice, state: coupled.state, relations: entry.relations }
})

const accuracy = Object.fromEntries(['scalar', 'relationBlind', 'coupled'].map((key) => [key, rows.filter((row) => row[key].kind === row.expected).length]))
const finite = rows.every((row) => row.state.every((entry) => Number.isFinite(entry.y) && Number.isFinite(entry.i) && entry.y >= 0 && entry.y <= 1 && entry.i >= 0 && entry.i <= 1))
const verdict = !finite || accuracy.scalar !== accuracy.relationBlind
  ? 'INVALID'
  : accuracy.coupled > accuracy.scalar ? 'SURROGATE-SUPPORTS' : accuracy.coupled === accuracy.scalar ? 'NULL' : 'CONTRADICTS'
const report = { protocol: 'CassiQwen L10b relational action arbitration', rows, accuracy: { ...accuracy, total: BOARD.length }, finite, verdict }
await writeFile(OUTPUT, `${JSON.stringify(report, null, 2)}\n`, 'utf8')
console.log(JSON.stringify({ verdict, accuracy: report.accuracy, finite }, null, 2))
if (verdict === 'INVALID') process.exitCode = 1
