import { Buffer } from 'node:buffer'
import { createHash } from 'node:crypto'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  AMPLITUDE,
  DIMENSION,
  DT,
  DTYPE,
  GRID_N,
  HORIZONS,
  LAYOUT,
  PHI,
  PROTOCOL,
  VERSION,
  VOLUME_SIZE,
  base64ToFloat32,
  cosineSimilarity,
  decodeEmbedding,
  encodeEmbedding,
  fieldMetrics,
  fixtureBoard,
  float32ToBase64,
  l2Norm,
  maxPairwiseCosineError,
  modeBasisManifest,
  normalizeEmbedding,
  relativeL2Error,
  subspaceResidualEnergy,
  zeroField,
} from './cassi-embedding-field-codec.mjs'

const HERE = dirname(fileURLToPath(import.meta.url))
const COSMOS_DIAG = resolve(HERE, '../CassiCosmos/_diag')
const SEED_PATH = resolve(COSMOS_DIAG, 'cassi_qwen_embedding_field_seed.json')
const GPU_PATH = resolve(COSMOS_DIAG, 'cassi_qwen_embedding_field_gpu.json')
const RECEIPT_PATH = resolve(HERE, 'embedding-field-lift.json')
const CASE_IDS = Object.freeze([
  'anchor', 'near', 'orthogonal', 'opposite',
  'anchor_shuffled', 'near_shuffled', 'zero',
])
const CASE_BASIS = Object.freeze({
  anchor: 'canonical',
  near: 'canonical',
  orthogonal: 'canonical',
  opposite: 'canonical',
  anchor_shuffled: 'shuffled',
  near_shuffled: 'shuffled',
  zero: 'zero',
})
const CANONICAL_IDS = Object.freeze(['anchor', 'near', 'orthogonal', 'opposite'])
const NONZERO_IDS = Object.freeze([...CANONICAL_IDS, 'anchor_shuffled', 'near_shuffled'])
const C1_COSINE_MIN = 0.999999
const C1_RELATIVE_L2_MAX = 2e-6
const C1_PAIRWISE_MAX = 2e-6
const MAX_FIELD_ABS = 10
const DECODED_NORM_FLOOR = 1e-6

class ReceiptError extends Error {
  constructor(message) {
    super(message)
    this.name = 'ReceiptError'
  }
}

function requireCondition(condition, message) {
  if (!condition) throw new ReceiptError(message)
}

function sha256(bytes) {
  return createHash('sha256').update(bytes).digest('hex')
}

function finiteArray(values) {
  for (const value of values) if (!Number.isFinite(value)) return false
  return true
}

function byteZero(base64) {
  const bytes = Buffer.from(base64, 'base64')
  for (const value of bytes) if (value !== 0) return false
  return true
}

function exactArray(actual, expected, label) {
  requireCondition(Array.isArray(actual), `${label} must be an array`)
  requireCondition(actual.length === expected.length, `${label} length mismatch`)
  for (let index = 0; index < expected.length; index += 1) {
    requireCondition(actual[index] === expected[index], `${label}[${index}] mismatch`)
  }
}

function numericClose(actual, expected, tolerance = 1e-13) {
  return Number.isFinite(actual) && Math.abs(actual - expected) <= tolerance
}

function validateCommon(document, label) {
  requireCondition(document && typeof document === 'object' && !Array.isArray(document), `${label} must be an object`)
  requireCondition(document.protocol === PROTOCOL, `${label} protocol mismatch`)
  requireCondition(document.version === VERSION, `${label} version mismatch`)
  requireCondition(document.grid_n === GRID_N, `${label} grid_n mismatch`)
  requireCondition(document.dimension === DIMENSION, `${label} dimension mismatch`)
  requireCondition(numericClose(document.phi, PHI), `${label} phi mismatch`)
  requireCondition(numericClose(document.dt, DT), `${label} dt mismatch`)
  requireCondition(document.layout === LAYOUT, `${label} layout mismatch`)
  requireCondition(document.dtype === DTYPE, `${label} dtype mismatch`)
  exactArray(document.horizons, HORIZONS, `${label} horizons`)
  requireCondition(Array.isArray(document.cases), `${label} cases must be an array`)
  requireCondition(document.cases.length === CASE_IDS.length, `${label} must contain ${CASE_IDS.length} cases`)
}

function normalizeForComparison(embedding) {
  return normalizeEmbedding(embedding)
}

function prepareCase(entry) {
  if (entry.id === 'zero') {
    const zero = zeroField()
    return {
      id: entry.id,
      basis: entry.basis,
      embedding_b64: null,
      signal_b64: float32ToBase64(zero.signal),
      ey_b64: float32ToBase64(zero.ey),
      ei_b64: float32ToBase64(zero.ei),
    }
  }
  const encoded = encodeEmbedding(entry.embedding, { basis: entry.basis })
  return {
    id: entry.id,
    basis: entry.basis,
    embedding_b64: float32ToBase64(entry.embedding),
    signal_b64: float32ToBase64(encoded.signal),
    ey_b64: float32ToBase64(encoded.ey),
    ei_b64: float32ToBase64(encoded.ei),
  }
}

async function prepare() {
  const basis = {
    kind: 'real-periodic-fourier',
    flat_layout: LAYOUT,
    coefficient_pair: 'X[k]=sqrt(V/2)*(a-i*b), X[-k]=conjugate(X[k])',
    mode_order: 'k2 then signed (kz,ky,kx)',
    ...modeBasisManifest(),
  }
  const seed = {
    protocol: PROTOCOL,
    version: VERSION,
    grid_n: GRID_N,
    dimension: DIMENSION,
    phi: PHI,
    amplitude: AMPLITUDE,
    dt: DT,
    layout: LAYOUT,
    dtype: DTYPE,
    horizons: [...HORIZONS],
    basis,
    cases: fixtureBoard().map(prepareCase),
  }
  await mkdir(COSMOS_DIAG, { recursive: true })
  const text = `${JSON.stringify(seed, null, 2)}\n`
  await writeFile(SEED_PATH, text, 'utf8')
  console.log(JSON.stringify({ prepared: true, path: SEED_PATH, sha256: sha256(Buffer.from(text)), cases: seed.cases.length, horizons: HORIZONS }, null, 2))
}

function parseCases(document, label) {
  const byId = new Map()
  for (const entry of document.cases) {
    requireCondition(entry && typeof entry === 'object' && !Array.isArray(entry), `${label} case must be an object`)
    requireCondition(CASE_IDS.includes(entry.id), `${label} unsupported case id ${String(entry.id)}`)
    requireCondition(!byId.has(entry.id), `${label} duplicate case ${entry.id}`)
    requireCondition(entry.basis === CASE_BASIS[entry.id], `${label} basis mismatch for ${entry.id}`)
    byId.set(entry.id, entry)
  }
  for (const id of CASE_IDS) requireCondition(byId.has(id), `${label} missing case ${id}`)
  return byId
}

function parseSeedCase(entry) {
  const signal = base64ToFloat32(entry.signal_b64, VOLUME_SIZE)
  const ey = base64ToFloat32(entry.ey_b64, VOLUME_SIZE)
  const ei = base64ToFloat32(entry.ei_b64, VOLUME_SIZE)
  requireCondition(finiteArray(signal) && finiteArray(ey) && finiteArray(ei), `seed ${entry.id} contains non-finite fields`)
  if (entry.id === 'zero') {
    requireCondition(entry.embedding_b64 === null, 'zero seed must not contain an embedding')
    requireCondition(byteZero(entry.signal_b64) && byteZero(entry.ey_b64) && byteZero(entry.ei_b64), 'zero seed is not byte-zero')
    return { ...entry, signal, ey, ei, embedding: null }
  }
  const embedding = base64ToFloat32(entry.embedding_b64, DIMENSION)
  requireCondition(finiteArray(embedding), `seed ${entry.id} contains a non-finite embedding`)
  const rebuilt = encodeEmbedding(embedding, { basis: entry.basis })
  requireCondition(entry.signal_b64 === float32ToBase64(rebuilt.signal), `seed ${entry.id} signal does not match the deterministic codec`)
  requireCondition(entry.ey_b64 === float32ToBase64(rebuilt.ey), `seed ${entry.id} EY does not match the deterministic codec`)
  requireCondition(entry.ei_b64 === float32ToBase64(rebuilt.ei), `seed ${entry.id} EI does not match the deterministic codec`)
  return { ...entry, signal, ey, ei, embedding }
}

function analyzeCpu(seedCases) {
  const cases = {}
  const expected = {}
  const decoded = {}
  let pass = true
  for (const id of CANONICAL_IDS) {
    const entry = seedCases.get(id)
    const normalized = normalizeForComparison(entry.embedding)
    const reconstructed = decodeEmbedding({ ey: entry.ey, ei: entry.ei }, { basis: entry.basis })
    const cosine = cosineSimilarity(reconstructed, normalized)
    const relativeL2 = relativeL2Error(reconstructed, normalized)
    const metrics = fieldMetrics(entry.ey, entry.ei, { basis: entry.basis })
    expected[id] = normalized
    decoded[id] = reconstructed
    const casePass = cosine >= C1_COSINE_MIN && relativeL2 <= C1_RELATIVE_L2_MAX
    pass = pass && casePass
    cases[id] = {
      cosine,
      relative_l2_error: relativeL2,
      signal_l2: l2Norm(entry.signal),
      subspace_residual_energy: metrics.subspace_residual_energy,
      pass: casePass,
    }
  }
  for (const id of ['anchor_shuffled', 'near_shuffled']) {
    const entry = seedCases.get(id)
    const normalized = normalizeForComparison(entry.embedding)
    const reconstructed = decodeEmbedding({ ey: entry.ey, ei: entry.ei }, { basis: entry.basis })
    const cosine = cosineSimilarity(reconstructed, normalized)
    const relativeL2 = relativeL2Error(reconstructed, normalized)
    const casePass = cosine >= C1_COSINE_MIN && relativeL2 <= C1_RELATIVE_L2_MAX
    pass = pass && casePass
    cases[id] = { cosine, relative_l2_error: relativeL2, pass: casePass }
    expected[id] = normalized
    decoded[id] = reconstructed
  }
  const maxPairwise = maxPairwiseCosineError(expected, decoded)
  pass = pass && maxPairwise <= C1_PAIRWISE_MAX
  return {
    pass,
    thresholds: {
      cosine_min: C1_COSINE_MIN,
      relative_l2_max: C1_RELATIVE_L2_MAX,
      pairwise_cosine_error_max: C1_PAIRWISE_MAX,
    },
    max_pairwise_cosine_error: maxPairwise,
    cases,
  }
}

function compareReportedMetric(actual, reported) {
  if (!Number.isFinite(reported)) return false
  const scale = Math.max(1, Math.abs(actual), Math.abs(reported))
  return Math.abs(actual - reported) <= 2e-6 * scale
}

function analyzeGpu(seedCases, gpuCases, gpuDocument) {
  const perCase = {}
  const decodedByHorizon = new Map(HORIZONS.map((horizon) => [horizon, {}]))
  let c2Pass = true
  let c3Pass = gpuDocument.finite === true && gpuDocument.verdict === 'PASS'
  let globalMaxAbs = 0
  let zeroByteZero = true

  for (const id of CASE_IDS) {
    const seed = seedCases.get(id)
    const gpu = gpuCases.get(id)
    requireCondition(Array.isArray(gpu.checkpoints), `GPU case ${id} checkpoints must be an array`)
    requireCondition(gpu.checkpoints.length === HORIZONS.length, `GPU case ${id} checkpoint count mismatch`)
    const checkpointRows = []
    for (let checkpointIndex = 0; checkpointIndex < HORIZONS.length; checkpointIndex += 1) {
      const expectedStep = HORIZONS[checkpointIndex]
      const checkpoint = gpu.checkpoints[checkpointIndex]
      requireCondition(checkpoint && typeof checkpoint === 'object', `GPU ${id}/${expectedStep} checkpoint malformed`)
      const ey = base64ToFloat32(checkpoint.ey_b64, VOLUME_SIZE)
      const ei = base64ToFloat32(checkpoint.ei_b64, VOLUME_SIZE)
      const rawFinite = finiteArray(ey) && finiteArray(ei)
      const metrics = rawFinite ? fieldMetrics(ey, ei, { basis: id === 'zero' ? 'canonical' : gpu.basis }) : null
      const timeOk = Number.isFinite(checkpoint.t) && Math.abs(checkpoint.t - expectedStep * DT) <= 1e-6
      const summaryOk = metrics !== null
        && compareReportedMetric(metrics.maxAbs, checkpoint.max_abs)
        && compareReportedMetric(metrics.ey_l2, checkpoint.ey_l2)
        && compareReportedMetric(metrics.ei_l2, checkpoint.ei_l2)
        && compareReportedMetric(metrics.epsilon_l2, checkpoint.epsilon_l2)
      const horizonPass = checkpoint.step === expectedStep
        && checkpoint.finite === true
        && rawFinite
        && timeOk
        && metrics.maxAbs <= MAX_FIELD_ABS
        && summaryOk
      c3Pass = c3Pass && horizonPass
      globalMaxAbs = Math.max(globalMaxAbs, metrics?.maxAbs ?? Infinity)

      let decodedNorm = null
      let subspaceResidual = null
      if (id === 'zero') {
        const isZero = byteZero(checkpoint.ey_b64) && byteZero(checkpoint.ei_b64)
        zeroByteZero = zeroByteZero && isZero
        c3Pass = c3Pass && isZero
      } else {
        const decoded = decodeEmbedding({ ey, ei }, { basis: gpu.basis })
        decodedByHorizon.get(expectedStep)[id] = decoded
        decodedNorm = l2Norm(decoded)
        subspaceResidual = subspaceResidualEnergy({ ey, ei }, gpu.basis)
      }

      let t0 = null
      if (expectedStep === 0 && id !== 'zero') {
        const normalized = normalizeForComparison(seed.embedding)
        const decoded = decodedByHorizon.get(0)[id]
        const cosine = cosineSimilarity(decoded, normalized)
        const relativeL2 = relativeL2Error(decoded, normalized)
        const seedByteIdentity = checkpoint.ey_b64 === seed.ey_b64 && checkpoint.ei_b64 === seed.ei_b64
        const casePass = seedByteIdentity && cosine >= C1_COSINE_MIN && relativeL2 <= C1_RELATIVE_L2_MAX
        c2Pass = c2Pass && casePass
        t0 = { cosine, relative_l2_error: relativeL2, seed_byte_identical: seedByteIdentity, pass: casePass }
      }
      checkpointRows.push({
        step: expectedStep,
        t: checkpoint.t,
        finite: rawFinite,
        max_abs: metrics?.maxAbs ?? null,
        epsilon_l2: metrics?.epsilon_l2 ?? null,
        ey_l2: metrics?.ey_l2 ?? null,
        ei_l2: metrics?.ei_l2 ?? null,
        decoded_norm: decodedNorm,
        subspace_residual_energy: subspaceResidual,
        contract_pass: horizonPass,
        ...(t0 ? { t0 } : {}),
      })
    }
    perCase[id] = { basis: gpu.basis, checkpoints: checkpointRows }
  }

  const seedExpected = {}
  const seedDecoded = {}
  for (const id of NONZERO_IDS) {
    seedExpected[id] = normalizeForComparison(seedCases.get(id).embedding)
    seedDecoded[id] = decodedByHorizon.get(0)[id]
  }
  const t0Pairwise = maxPairwiseCosineError(seedExpected, seedDecoded)
  c2Pass = c2Pass && t0Pairwise <= C1_PAIRWISE_MAX

  const geometryRows = []
  let geometryVerdict = 'SUPPORTS'
  for (const horizon of HORIZONS) {
    const vectors = decodedByHorizon.get(horizon)
    const norms = Object.fromEntries(CANONICAL_IDS.map((id) => [id, l2Norm(vectors[id])]))
    const near = cosineSimilarity(vectors.anchor, vectors.near)
    const orthogonal = cosineSimilarity(vectors.anchor, vectors.orthogonal)
    const opposite = cosineSimilarity(vectors.anchor, vectors.opposite)
    const ordered = near > orthogonal && orthogonal > opposite
    const aboveFloor = Object.values(norms).every((norm) => norm > DECODED_NORM_FLOOR)
    if (!aboveFloor) geometryVerdict = 'INCONCLUSIVE'
    else if (!ordered && geometryVerdict !== 'INCONCLUSIVE') geometryVerdict = 'CONTRADICTS'
    geometryRows.push({ horizon, near, orthogonal, opposite, ordered, norms })
  }

  const shuffledRows = HORIZONS.map((horizon) => {
    const vectors = decodedByHorizon.get(horizon)
    const canonical = cosineSimilarity(vectors.anchor, vectors.near)
    const shuffled = cosineSimilarity(vectors.anchor_shuffled, vectors.near_shuffled)
    return { horizon, canonical, shuffled, shuffled_minus_canonical: shuffled - canonical }
  })

  return {
    gpu_seed_contract: {
      pass: c2Pass,
      max_pairwise_cosine_error: t0Pairwise,
    },
    extended_horizon_contract: {
      pass: c3Pass,
      max_abs: globalMaxAbs,
      bound: MAX_FIELD_ABS,
      zero_byte_zero: zeroByteZero,
    },
    geometry: {
      verdict: geometryVerdict,
      decoded_norm_floor: DECODED_NORM_FLOOR,
      rows: geometryRows,
    },
    shuffled_control: shuffledRows,
    cases: perCase,
  }
}

async function analyze() {
  let seedBytes
  let gpuBytes
  let seed
  let gpu
  try {
    ;[seedBytes, gpuBytes] = await Promise.all([readFile(SEED_PATH), readFile(GPU_PATH)])
    seed = JSON.parse(seedBytes.toString('utf8'))
    gpu = JSON.parse(gpuBytes.toString('utf8'))
    validateCommon(seed, 'seed')
    requireCondition(seed.amplitude === AMPLITUDE, 'seed amplitude mismatch')
    requireCondition(seed.basis && typeof seed.basis === 'object', 'seed basis manifest missing')
    requireCondition(JSON.stringify(seed.basis.canonical) === JSON.stringify(modeBasisManifest().canonical), 'seed canonical basis manifest mismatch')
    requireCondition(JSON.stringify(seed.basis.shuffled) === JSON.stringify(modeBasisManifest().shuffled), 'seed shuffled basis manifest mismatch')
    validateCommon(gpu, 'GPU receipt')

    const seedCaseEntries = parseCases(seed, 'seed')
    const gpuCases = parseCases(gpu, 'GPU receipt')
    const seedCases = new Map([...seedCaseEntries].map(([id, entry]) => [id, parseSeedCase(entry)]))
    const cpuContract = analyzeCpu(seedCases)
    const gpuAnalysis = analyzeGpu(seedCases, gpuCases, gpu)
    const verdict = !gpuAnalysis.extended_horizon_contract.pass
      ? 'INVALID'
      : !cpuContract.pass || !gpuAnalysis.gpu_seed_contract.pass
        ? 'FAIL'
        : 'PASS'
    const receipt = {
      protocol: PROTOCOL,
      version: VERSION,
      artifacts: {
        seed: { path: 'CassiCosmos/_diag/cassi_qwen_embedding_field_seed.json', sha256: sha256(seedBytes) },
        gpu: { path: 'CassiCosmos/_diag/cassi_qwen_embedding_field_gpu.json', sha256: sha256(gpuBytes) },
      },
      config: {
        grid_n: GRID_N,
        dimension: DIMENSION,
        phi: PHI,
        amplitude: AMPLITUDE,
        dt: DT,
        horizons: [...HORIZONS],
        layout: LAYOUT,
        dtype: DTYPE,
      },
      cpu_codec_contract: cpuContract,
      ...gpuAnalysis,
      gates: {
        C1: cpuContract.pass,
        C2: gpuAnalysis.gpu_seed_contract.pass,
        C3: gpuAnalysis.extended_horizon_contract.pass,
      },
      verdict,
    }
    await writeFile(RECEIPT_PATH, `${JSON.stringify(receipt, null, 2)}\n`, 'utf8')
    console.log(JSON.stringify({ verdict, geometry: receipt.geometry.verdict, cpu: cpuContract.pass, gpuSeed: receipt.gpu_seed_contract.pass, extended: receipt.extended_horizon_contract.pass, path: RECEIPT_PATH }, null, 2))
    if (verdict !== 'PASS') process.exitCode = 1
  } catch (error) {
    const receipt = {
      protocol: PROTOCOL,
      version: VERSION,
      artifacts: {
        ...(seedBytes ? { seed: { path: 'CassiCosmos/_diag/cassi_qwen_embedding_field_seed.json', sha256: sha256(seedBytes) } } : {}),
        ...(gpuBytes ? { gpu: { path: 'CassiCosmos/_diag/cassi_qwen_embedding_field_gpu.json', sha256: sha256(gpuBytes) } } : {}),
      },
      cpu_codec_contract: { pass: false },
      gpu_seed_contract: { pass: false },
      extended_horizon_contract: { pass: false },
      geometry: { verdict: 'INCONCLUSIVE', rows: [] },
      gates: { C1: false, C2: false, C3: false },
      verdict: 'INVALID',
      reason: error instanceof Error ? error.message : String(error),
    }
    await writeFile(RECEIPT_PATH, `${JSON.stringify(receipt, null, 2)}\n`, 'utf8')
    console.error(JSON.stringify(receipt, null, 2))
    process.exitCode = 1
  }
}

const command = process.argv[2]
if (command === '--prepare') await prepare()
else if (command === '--analyze') await analyze()
else {
  console.error('Usage: node run-embedding-field-lift.mjs --prepare | --analyze')
  process.exitCode = 2
}
