const GRID_SIZE = 32

function unavailable(candidates, reason) {
  return {
    applied: false,
    reason,
    candidates: [...candidates],
    scores: [],
  }
}

function finiteNumber(value) {
  return typeof value === 'number' && Number.isFinite(value)
}

function gridIndex(coordinate) {
  return Math.round(((coordinate + 1) * (GRID_SIZE - 1)) / 2)
}

function fnv1a32(value) {
  let hash = 0x811c9dc5
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index)
    hash = Math.imul(hash, 0x01000193) >>> 0
  }
  return hash
}

function validateCandidates(candidates) {
  if (!Array.isArray(candidates) || candidates.length === 0) return 'candidates must be a non-empty array'
  const ids = new Set()
  for (const candidate of candidates) {
    if (typeof candidate?.id !== 'string' || candidate.id.length === 0) {
      return 'every candidate requires a non-empty string id'
    }
    if (ids.has(candidate.id)) return `duplicate candidate id: ${candidate.id}`
    ids.add(candidate.id)
  }
  return null
}

function validateProjection(projection) {
  if (!Array.isArray(projection) || projection.length < 1 || projection.length > 8) {
    return 'projection must contain between 1 and 8 cells'
  }
  for (const [rank, cell] of projection.entries()) {
    if (typeof cell !== 'object' || cell === null) return `projection cell ${rank} is invalid`
    for (const key of ['x', 'y', 'z', 'q']) {
      if (!finiteNumber(cell[key])) return `projection cell ${rank} ${key} must be finite`
    }
    if (cell.q < 0) return `projection cell ${rank} q must be non-negative`
  }
  return null
}

/**
 * Pure, default-off field-rank candidate permutation.
 *
 * This function has no field-engine, network, or model dependency. It uses
 * projection geometry only to select a stable ordering permutation; neither
 * q nor rank is interpreted as candidate truth or answer quality.
 */
export function rankCandidatesByField(candidates, projection, { enabled = false } = {}) {
  if (!enabled) return unavailable(candidates, 'field candidate mapping is disabled')

  const candidateError = validateCandidates(candidates)
  if (candidateError) return unavailable(Array.isArray(candidates) ? candidates : [], candidateError)
  const projectionError = validateProjection(projection)
  if (projectionError) return unavailable(candidates, projectionError)

  const canonical = candidates
    .map((candidate) => candidate.id)
    .sort((left, right) => left < right ? -1 : left > right ? 1 : 0)
  const scoresById = new Map(canonical.map((id) => [id, 0]))
  const contributionById = new Map(canonical.map((id) => [id, []]))

  projection.forEach((cell, rank) => {
    const gx = gridIndex(cell.x)
    const gy = gridIndex(cell.y)
    const gz = gridIndex(cell.z)
    const fingerprint = `${gx}|${gy}|${gz}|${rank}`
    const recipient = canonical[fnv1a32(fingerprint) % canonical.length]
    scoresById.set(recipient, scoresById.get(recipient) + cell.q)
    contributionById.get(recipient).push({ rank, gx, gy, gz, q: cell.q })
  })

  const indexed = candidates.map((candidate, originalIndex) => ({
    candidate,
    originalIndex,
    score: scoresById.get(candidate.id),
  }))
  indexed.sort((left, right) => right.score - left.score || left.originalIndex - right.originalIndex)

  return {
    applied: true,
    reason: null,
    candidates: indexed.map(({ candidate }) => candidate),
    scores: indexed.map(({ candidate, score }) => ({
      id: candidate.id,
      score,
      contributions: contributionById.get(candidate.id),
    })),
  }
}
