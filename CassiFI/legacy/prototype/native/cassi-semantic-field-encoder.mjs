const ROLE_COORDINATES = Object.freeze({
  answer: Object.freeze({ x: 0.72, y: 0, z: 0 }),
  clarify: Object.freeze({ x: -0.72, y: 0, z: 0 }),
  retrieve: Object.freeze({ x: 0, y: 0.72, z: 0 }),
  think: Object.freeze({ x: 0, y: -0.72, z: 0 }),
  tool: Object.freeze({ x: 0, y: 0, z: 0.72 }),
  stop: Object.freeze({ x: 0, y: 0, z: -0.72 }),
  abstain: Object.freeze({ x: 0, y: 0, z: 0 }),
})

const CANONICAL_KINDS = Object.freeze(Object.keys(ROLE_COORDINATES).sort())
const FEATURE_KEYS = Object.freeze([
  'support',
  'goalAlignment',
  'urgency',
  'contradiction',
  'missingInformation',
  'risk',
  'cost',
])

function unavailable(reason) {
  return { applied: false, reason, deposits: [] }
}

function unitInterval(value) {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 1
}

function validateCandidates(candidates) {
  if (!Array.isArray(candidates) || candidates.length === 0) return 'candidates must be a non-empty array'
  const ids = new Set()
  const kinds = new Set()
  for (const candidate of candidates) {
    if (typeof candidate?.id !== 'string' || candidate.id.length === 0) return 'every candidate requires a non-empty string id'
    if (ids.has(candidate.id)) return `duplicate candidate id: ${candidate.id}`
    ids.add(candidate.id)
    if (!(candidate.kind in ROLE_COORDINATES)) return `unsupported candidate kind: ${String(candidate.kind)}`
    if (kinds.has(candidate.kind)) return `duplicate candidate kind: ${candidate.kind}`
    kinds.add(candidate.kind)
    for (const key of FEATURE_KEYS) {
      if (!unitInterval(candidate[key])) return `candidate ${candidate.id} ${key} must be finite and within [0,1]`
    }
  }
  return null
}

/**
 * Convert explicit operational action features into fixed role deposits.
 * The output is a semantic encoding contract, not an action decision and not
 * a claim that a field value represents truth, relevance, or safety.
 */
export function encodeActionCandidates(candidates, { enabled = false } = {}) {
  if (!enabled) return unavailable('semantic field encoding is disabled')
  const error = validateCandidates(candidates)
  if (error) return unavailable(error)

  const byKind = new Map(candidates.map((candidate) => [candidate.kind, candidate]))
  const deposits = CANONICAL_KINDS
    .filter((kind) => byKind.has(kind))
    .map((kind) => {
      const candidate = byKind.get(kind)
      const coordinate = ROLE_COORDINATES[kind]
      const cy = (candidate.support + candidate.goalAlignment + candidate.urgency) / 3
      const ci = (candidate.contradiction + candidate.missingInformation + candidate.risk + candidate.cost) / 4
      return {
        id: candidate.id,
        kind,
        x: coordinate.x,
        y: coordinate.y,
        z: coordinate.z,
        cy,
        ci,
        sigma: 1,
        features: Object.fromEntries(FEATURE_KEYS.map((key) => [key, candidate[key]])),
      }
    })
  return { applied: true, reason: null, deposits }
}

export { CANONICAL_KINDS, ROLE_COORDINATES }
