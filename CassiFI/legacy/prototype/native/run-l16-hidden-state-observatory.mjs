import { Buffer } from 'node:buffer'
import { createHash } from 'node:crypto'
import { mkdir, readFile, rename, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  AMPLITUDE,
  DT,
  DTYPE,
  GRID_N,
  HORIZONS,
  L16_DIMENSION,
  L16_MODE_CAPACITY,
  LAYOUT,
  PHI,
  base64ToFloat32,
  cosineSimilarity,
  decodeEmbedding,
  encodeEmbedding,
  fieldMetrics,
  float32ToBase64,
  l2Norm,
  modeBasisManifest,
  normalizeEmbeddingWithNorm,
  relativeL2Error,
  restoreEmbeddingNorm,
  zeroField,
} from './cassi-embedding-field-codec.mjs'

const HERE = dirname(fileURLToPath(import.meta.url))
const ARTIFACTS = resolve(HERE, '../../artifacts/native')
const DIAG = resolve(HERE, '../../../CassiCosmos/_diag')
const CAPTURE_PATH = resolve(ARTIFACTS, 'hidden-state-capture.json')
const SEED_PATH = resolve(DIAG, 'cassi_qwen_hidden_state_field_seed.json')
const GPU_PATH = resolve(DIAG, 'cassi_qwen_hidden_state_field_gpu.json')
const RECEIPT_PATH = resolve(ARTIFACTS, 'hidden-state-field-observatory.json')

const PROTOCOL = 'CassiQwen L16 hidden-state field observatory'
const VERSION = 1
const VOLUME = GRID_N ** 3
const CASE_IDS = Object.freeze(['hidden_canonical', 'hidden_shuffled', 'zero'])
const CASE_BASIS = Object.freeze({
  hidden_canonical: 'canonical',
  hidden_shuffled: 'shuffled',
  zero: 'zero',
})
const CODEC = Object.freeze({
  dimension: L16_DIMENSION,
  capacity: L16_DIMENSION,
  gridN: GRID_N,
})
const COSINE_MIN = 0.999999
const RELATIVE_L2_MAX = 2e-6
const MAX_FIELD_ABS = 10
const LOGIT_DELTA_MAX = 1e-6
const TOP_K = 16

class ContractError extends Error {
  constructor(message, verdict = 'INVALID') {
    super(message)
    this.name = 'ContractError'
    this.verdict = verdict
  }
}

function requireCondition(condition, message, verdict = 'INVALID') {
  if (!condition) throw new ContractError(message, verdict)
}

function sha256(bytes) {
  return createHash('sha256').update(bytes).digest('hex')
}

function finite(values) {
  for (const value of values) if (!Number.isFinite(value)) return false
  return true
}

function bytesZero(base64) {
  const bytes = Buffer.from(base64, 'base64')
  for (const value of bytes) if (value !== 0) return false
  return true
}

function numericClose(actual, expected, tolerance = 2e-6) {
  return Number.isFinite(actual) && Math.abs(actual - expected) <= tolerance * Math.max(1, Math.abs(actual), Math.abs(expected))
}

function topK(values, count = TOP_K) {
  const indexed = Array.from(values, (value, tokenId) => ({ tokenId, value }))
  indexed.sort((left, right) => right.value - left.value || left.tokenId - right.tokenId)
  return indexed.slice(0, count)
}

function validateBase64Hash(text, expected, label) {
  requireCondition(typeof text === 'string', `${label} base64 is absent`)
  const bytes = Buffer.from(text, 'base64')
  requireCondition(bytes.toString('base64') === text, `${label} base64 is not canonical`)
  requireCondition(typeof expected === 'string' && /^[0-9a-f]{64}$/.test(expected), `${label} SHA-256 is malformed`)
  requireCondition(sha256(bytes) === expected, `${label} SHA-256 mismatch`)
  return bytes
}

function validateTop16(logits, rows, label) {
  requireCondition(Array.isArray(rows) && rows.length === TOP_K, `${label} top16 has wrong shape`)
  const expected = topK(logits)
  for (let index = 0; index < TOP_K; index += 1) {
    const row = rows[index]
    requireCondition(row && Number.isInteger(row.token_id), `${label} top16 row ${index} has no token id`)
    requireCondition(row.token_id === expected[index].tokenId, `${label} top16 token rank ${index} mismatch`)
    requireCondition(numericClose(row.logit, expected[index].value, 1e-7), `${label} top16 logit rank ${index} mismatch`)
  }
  return expected
}

function validateCapture(document, rawBytes) {
  requireCondition(document && typeof document === 'object' && !Array.isArray(document), 'capture receipt must be an object')
  requireCondition(document.protocol === PROTOCOL, 'capture protocol mismatch')
  requireCondition(document.version === VERSION, 'capture version mismatch')
  requireCondition(document.verdict === 'PASS', `capture verdict is ${String(document.verdict)}`, 'FAIL')

  const model = document.model
  const runtime = document.runtime
  const hook = document.hook
  const prompt = document.prompt
  requireCondition(model && runtime && hook && prompt, 'capture metadata is incomplete')
  requireCondition(model.hidden_dimension === L16_DIMENSION, 'capture hidden dimension mismatch')
  requireCondition(Number.isInteger(model.vocabulary_size) && model.vocabulary_size > TOP_K, 'capture vocabulary size is invalid')
  requireCondition(model.sha256 === '7e78da5d7e3ae28d178121f58646953305f3e5bd3cb46f4a75584e8b6c6fe169', 'capture model hash mismatch')
  requireCondition(runtime.llama_version === '0.1.1-dev', 'capture llama version mismatch')
  requireCondition(runtime.requested_gpu_layers === 99, 'capture GPU request mismatch')
  requireCondition(runtime.context_size === 512 && runtime.batch_size === 512, 'capture context/batch mismatch')
  requireCondition(hook.kind === 'layer_input_residual' && hook.layer_rule === 'floor(n_layer / 2)', 'capture hook semantics mismatch')
  requireCondition(Number.isInteger(hook.layer_index) && hook.layer_index >= 0 && hook.layer_index < model.layer_count, 'capture layer index mismatch')
  requireCondition(hook.token_row === prompt.final_token_index, 'capture hook row mismatch')
  requireCondition(typeof hook.setter_export === 'string' && hook.setter_export.includes('llama_set_embeddings_layer_inp'), 'capture setter export mismatch')
  requireCondition(typeof hook.getter_export === 'string' && hook.getter_export.includes('llama_get_embeddings_layer_inp'), 'capture getter export mismatch')
  requireCondition(prompt.tokenization?.add_special === true && prompt.tokenization?.parse_special === true, 'capture tokenization mismatch')
  requireCondition(Array.isArray(prompt.token_ids) && prompt.token_ids.length === prompt.token_count && prompt.token_count > 0, 'capture token board mismatch')
  requireCondition(prompt.final_token_index === prompt.token_count - 1 && prompt.final_token_id === prompt.token_ids.at(-1), 'capture final token mismatch')

  const hiddenRaw = validateBase64Hash(document.hidden_state_b64, document.hidden_state_sha256, 'hidden state')
  requireCondition(hiddenRaw.byteLength === L16_DIMENSION * 4, 'hidden state byte size mismatch')
  const hidden = base64ToFloat32(document.hidden_state_b64, L16_DIMENSION)
  requireCondition(finite(hidden), 'hidden state contains non-finite values')
  const norm = l2Norm(hidden)
  requireCondition(Number.isFinite(document.hidden_l2_norm) && document.hidden_l2_norm > 0, 'hidden norm is invalid')
  requireCondition(numericClose(norm, document.hidden_l2_norm, 1e-12), 'hidden norm does not match raw state')

  const off = document.capture_off
  const on = document.capture_on
  requireCondition(off && on, 'capture parity arms are absent')
  const expectedLogitBytes = model.vocabulary_size * 4
  const offRaw = validateBase64Hash(off.logits_b64, off.logits_sha256, 'capture-off logits')
  const onRaw = validateBase64Hash(on.logits_b64, on.logits_sha256, 'capture-on logits')
  requireCondition(offRaw.byteLength === expectedLogitBytes && onRaw.byteLength === expectedLogitBytes, 'capture logit byte size mismatch')
  const offLogits = base64ToFloat32(off.logits_b64, model.vocabulary_size)
  const onLogits = base64ToFloat32(on.logits_b64, model.vocabulary_size)
  requireCondition(finite(offLogits) && finite(onLogits), 'capture logits contain non-finite values')
  const expectedOffTop = validateTop16(offLogits, off.top16, 'capture-off')
  const expectedOnTop = validateTop16(onLogits, on.top16, 'capture-on')
  const offArgmax = expectedOffTop[0].tokenId
  const onArgmax = expectedOnTop[0].tokenId
  requireCondition(off.argmax_token_id === offArgmax && on.argmax_token_id === onArgmax, 'capture argmax metadata mismatch')
  let maxDelta = 0
  for (let index = 0; index < offLogits.length; index += 1) maxDelta = Math.max(maxDelta, Math.abs(offLogits[index] - onLogits[index]))
  const topIdsMatch = expectedOffTop.every((row, index) => row.tokenId === expectedOnTop[index].tokenId)
  const parity = document.parity
  requireCondition(parity && parity.argmax_match === (offArgmax === onArgmax), 'capture argmax parity metadata mismatch')
  requireCondition(parity.top16_token_ids_match === topIdsMatch, 'capture top16 parity metadata mismatch')
  requireCondition(numericClose(parity.max_abs_logit_difference, maxDelta, 1e-12), 'capture logit delta metadata mismatch')
  const h1Pass = offArgmax === onArgmax && topIdsMatch && maxDelta <= LOGIT_DELTA_MAX
  requireCondition(parity.pass === h1Pass, 'capture parity pass metadata mismatch')
  requireCondition(h1Pass, `capture parity gate failed at ${maxDelta}`, 'FAIL')

  return {
    document,
    rawBytes,
    hash: sha256(rawBytes),
    hidden,
    hiddenNorm: norm,
    h1: {
      pass: h1Pass,
      argmax_token_id: offArgmax,
      max_abs_logit_difference: maxDelta,
      top16_token_ids_match: topIdsMatch,
    },
  }
}

function assertCommon(document, label, { requireAmplitude = false } = {}) {
  requireCondition(document && typeof document === 'object' && !Array.isArray(document), `${label} must be an object`)
  requireCondition(document.protocol === PROTOCOL, `${label} protocol mismatch`)
  requireCondition(document.version === VERSION, `${label} version mismatch`)
  requireCondition(document.grid_n === GRID_N, `${label} grid_n mismatch`)
  requireCondition(document.dimension === L16_DIMENSION, `${label} dimension mismatch`)
  requireCondition(numericClose(document.phi, PHI, 1e-13), `${label} phi mismatch`)
  requireCondition(numericClose(document.dt, DT, 1e-13), `${label} dt mismatch`)
  requireCondition(document.layout === LAYOUT && document.dtype === DTYPE, `${label} layout/dtype mismatch`)
  if (requireAmplitude) requireCondition(numericClose(document.amplitude, AMPLITUDE, 1e-13), `${label} amplitude mismatch`)
  requireCondition(Array.isArray(document.horizons) && document.horizons.length === HORIZONS.length, `${label} horizons mismatch`)
  for (let index = 0; index < HORIZONS.length; index += 1) {
    requireCondition(document.horizons[index] === HORIZONS[index], `${label} horizon ${index} mismatch`)
  }
}

function indexCases(document, label) {
  requireCondition(Array.isArray(document.cases) && document.cases.length === CASE_IDS.length, `${label} cases mismatch`)
  const byId = new Map()
  for (const entry of document.cases) {
    requireCondition(entry && typeof entry === 'object', `${label} case is malformed`)
    requireCondition(CASE_IDS.includes(entry.id), `${label} unsupported case ${String(entry.id)}`)
    requireCondition(!byId.has(entry.id), `${label} duplicate case ${entry.id}`)
    requireCondition(entry.basis === CASE_BASIS[entry.id], `${label} basis mismatch for ${entry.id}`)
    byId.set(entry.id, entry)
  }
  for (const id of CASE_IDS) requireCondition(byId.has(id), `${label} missing case ${id}`)
  return byId
}

function encodeCase(id, basis, hidden) {
  if (id === 'zero') {
    const zero = zeroField()
    return {
      id,
      basis,
      signal_b64: float32ToBase64(zero.signal),
      ey_b64: float32ToBase64(zero.ey),
      ei_b64: float32ToBase64(zero.ei),
    }
  }
  const encoded = encodeEmbedding(hidden, { ...CODEC, basis })
  return {
    id,
    basis,
    signal_b64: float32ToBase64(encoded.signal),
    ey_b64: float32ToBase64(encoded.ey),
    ei_b64: float32ToBase64(encoded.ei),
  }
}

async function writeAtomic(path, document) {
  await mkdir(dirname(path), { recursive: true })
  const temp = `${path}.tmp`
  await writeFile(temp, `${JSON.stringify(document, null, 2)}\n`, 'utf8')
  await rename(temp, path)
}

async function prepareField() {
  const captureBytes = await readFile(CAPTURE_PATH)
  const capture = validateCapture(JSON.parse(captureBytes.toString('utf8')), captureBytes)
  const manifest = modeBasisManifest({ count: L16_MODE_CAPACITY, gridN: GRID_N })
  const seed = {
    protocol: PROTOCOL,
    version: VERSION,
    grid_n: GRID_N,
    dimension: L16_DIMENSION,
    phi: PHI,
    amplitude: AMPLITUDE,
    dt: DT,
    layout: LAYOUT,
    dtype: DTYPE,
    horizons: [...HORIZONS],
    capture_sha256: capture.hash,
    hidden_state_sha256: capture.document.hidden_state_sha256,
    hidden_l2_norm: capture.hiddenNorm,
    basis: {
      kind: 'real-periodic-fourier',
      flat_layout: LAYOUT,
      coefficient_pair: 'X[k]=sqrt(V/2)*(a-i*b), X[-k]=conjugate(X[k])',
      mode_order: 'k2 then signed (kz,ky,kx)',
      ...manifest,
    },
    cases: [
      encodeCase('hidden_canonical', 'canonical', capture.hidden),
      encodeCase('hidden_shuffled', 'shuffled', capture.hidden),
      encodeCase('zero', 'zero', capture.hidden),
    ],
  }
  await writeAtomic(SEED_PATH, seed)
  console.log(JSON.stringify({
    verdict: 'PASS',
    h1: capture.h1,
    hidden_l2_norm: capture.hiddenNorm,
    path: SEED_PATH,
  }, null, 2))
}

function decodeSeedCase(entry) {
  const signal = base64ToFloat32(entry.signal_b64, VOLUME)
  const ey = base64ToFloat32(entry.ey_b64, VOLUME)
  const ei = base64ToFloat32(entry.ei_b64, VOLUME)
  requireCondition(finite(signal) && finite(ey) && finite(ei), `seed ${entry.id} has non-finite values`)
  return { ...entry, signal, ey, ei }
}

function verifyPreparedSeed(seed, capture) {
  assertCommon(seed, 'seed', { requireAmplitude: true })
  requireCondition(seed.capture_sha256 === capture.hash, 'seed capture hash mismatch')
  requireCondition(seed.hidden_state_sha256 === capture.document.hidden_state_sha256, 'seed hidden state hash mismatch')
  requireCondition(numericClose(seed.hidden_l2_norm, capture.hiddenNorm, 1e-12), 'seed hidden norm mismatch')
  const expectedManifest = modeBasisManifest({ count: L16_MODE_CAPACITY, gridN: GRID_N })
  requireCondition(JSON.stringify(seed.basis?.canonical) === JSON.stringify(expectedManifest.canonical), 'seed canonical basis mismatch')
  requireCondition(JSON.stringify(seed.basis?.shuffled) === JSON.stringify(expectedManifest.shuffled), 'seed shuffled basis mismatch')
  const cases = indexCases(seed, 'seed')
  const parsed = new Map([...cases].map(([id, entry]) => [id, decodeSeedCase(entry)]))
  const normalization = normalizeEmbeddingWithNorm(capture.hidden, CODEC)
  const cpuRows = {}
  let pass = true
  for (const id of ['hidden_canonical', 'hidden_shuffled']) {
    const entry = parsed.get(id)
    const expected = encodeEmbedding(capture.hidden, { ...CODEC, basis: entry.basis })
    requireCondition(entry.signal_b64 === float32ToBase64(expected.signal), `seed ${id} signal differs from deterministic codec`)
    requireCondition(entry.ey_b64 === float32ToBase64(expected.ey), `seed ${id} EY differs from deterministic codec`)
    requireCondition(entry.ei_b64 === float32ToBase64(expected.ei), `seed ${id} EI differs from deterministic codec`)
    const decodedDirection = decodeEmbedding({ ey: entry.ey, ei: entry.ei }, { ...CODEC, basis: entry.basis })
    const restored = restoreEmbeddingNorm(decodedDirection, capture.hiddenNorm, CODEC)
    const cosine = cosineSimilarity(restored, capture.hidden)
    const relativeL2 = relativeL2Error(restored, capture.hidden)
    const directionCosine = cosineSimilarity(decodedDirection, normalization.vector)
    const casePass = cosine >= COSINE_MIN && relativeL2 <= RELATIVE_L2_MAX && directionCosine >= COSINE_MIN
    pass = pass && casePass
    cpuRows[id] = {
      restored_cosine: cosine,
      restored_relative_l2_error: relativeL2,
      direction_cosine: directionCosine,
      decoded_direction_norm: l2Norm(decodedDirection),
      subspace_residual_energy: fieldMetrics(entry.ey, entry.ei, { ...CODEC, basis: entry.basis }).subspace_residual_energy,
      pass: casePass,
    }
  }
  const zero = parsed.get('zero')
  requireCondition(bytesZero(zero.signal_b64) && bytesZero(zero.ey_b64) && bytesZero(zero.ei_b64), 'seed zero case is not byte-zero')
  return { cases: parsed, cpu: { pass, rows: cpuRows } }
}

function analyzeGpu(seedCases, gpu, capture) {
  assertCommon(gpu, 'GPU receipt')
  requireCondition(gpu.finite === true && gpu.verdict === 'PASS', 'GPU receipt is not PASS')
  const gpuCases = indexCases(gpu, 'GPU receipt')
  const resultCases = {}
  let h2 = true
  let h3 = true
  let maximum = 0
  let zeroByteZero = true
  for (const id of CASE_IDS) {
    const seed = seedCases.get(id)
    const arm = gpuCases.get(id)
    requireCondition(Array.isArray(arm.checkpoints) && arm.checkpoints.length === HORIZONS.length, `GPU ${id} checkpoint count mismatch`)
    const rows = []
    for (let index = 0; index < HORIZONS.length; index += 1) {
      const expectedStep = HORIZONS[index]
      const checkpoint = arm.checkpoints[index]
      requireCondition(checkpoint && typeof checkpoint === 'object', `GPU ${id}/${expectedStep} checkpoint malformed`)
      const ey = base64ToFloat32(checkpoint.ey_b64, VOLUME)
      const ei = base64ToFloat32(checkpoint.ei_b64, VOLUME)
      const rawFinite = finite(ey) && finite(ei)
      const metrics = rawFinite ? fieldMetrics(ey, ei, { ...CODEC, basis: arm.basis === 'zero' ? 'canonical' : arm.basis }) : null
      const checkpointPass = checkpoint.step === expectedStep
        && checkpoint.finite === true
        && rawFinite
        && Math.abs(checkpoint.t - expectedStep * DT) <= 1e-6
        && metrics.maxAbs <= MAX_FIELD_ABS
        && numericClose(checkpoint.max_abs, metrics.maxAbs)
        && numericClose(checkpoint.ey_l2, metrics.ey_l2)
        && numericClose(checkpoint.ei_l2, metrics.ei_l2)
        && numericClose(checkpoint.epsilon_l2, metrics.epsilon_l2)
      h3 = h3 && checkpointPass
      maximum = Math.max(maximum, metrics?.maxAbs ?? Infinity)
      const zero = id === 'zero'
      let t0 = null
      let trajectory = null
      if (zero) {
        const byteZero = bytesZero(checkpoint.ey_b64) && bytesZero(checkpoint.ei_b64)
        zeroByteZero = zeroByteZero && byteZero
        h3 = h3 && byteZero
      } else {
        const decodedDirection = decodeEmbedding({ ey, ei }, { ...CODEC, basis: arm.basis })
        const restored = restoreEmbeddingNorm(decodedDirection, capture.hiddenNorm, CODEC)
        trajectory = {
          direction_cosine: cosineSimilarity(decodedDirection, normalizeEmbeddingWithNorm(capture.hidden, CODEC).vector),
          restored_cosine: cosineSimilarity(restored, capture.hidden),
          restored_relative_l2_error: relativeL2Error(restored, capture.hidden),
          decoded_direction_norm: l2Norm(decodedDirection),
          subspace_residual_energy: metrics.subspace_residual_energy,
        }
        if (expectedStep === 0) {
          const byteIdentical = checkpoint.ey_b64 === seed.ey_b64 && checkpoint.ei_b64 === seed.ei_b64
          const pass = byteIdentical && trajectory.restored_cosine >= COSINE_MIN && trajectory.restored_relative_l2_error <= RELATIVE_L2_MAX
          h2 = h2 && pass
          t0 = { seed_byte_identical: byteIdentical, pass }
        }
      }
      rows.push({
        step: expectedStep,
        t: checkpoint.t,
        finite: rawFinite,
        max_abs: metrics?.maxAbs ?? null,
        ey_l2: metrics?.ey_l2 ?? null,
        ei_l2: metrics?.ei_l2 ?? null,
        epsilon_l2: metrics?.epsilon_l2 ?? null,
        contract_pass: checkpointPass,
        ...(t0 ? { t0 } : {}),
        ...(trajectory ? { trajectory } : {}),
      })
    }
    resultCases[id] = { basis: arm.basis, checkpoints: rows }
  }
  return {
    gpu_seed_contract: { pass: h2, cosine_min: COSINE_MIN, relative_l2_max: RELATIVE_L2_MAX },
    extended_horizon_contract: { pass: h3, max_abs: maximum, bound: MAX_FIELD_ABS, zero_byte_zero: zeroByteZero },
    cases: resultCases,
  }
}

async function analyze() {
  let captureBytes
  let seedBytes
  let gpuBytes
  try {
    ;[captureBytes, seedBytes, gpuBytes] = await Promise.all([readFile(CAPTURE_PATH), readFile(SEED_PATH), readFile(GPU_PATH)])
    const capture = validateCapture(JSON.parse(captureBytes.toString('utf8')), captureBytes)
    const seed = JSON.parse(seedBytes.toString('utf8'))
    const gpu = JSON.parse(gpuBytes.toString('utf8'))
    const seedAnalysis = verifyPreparedSeed(seed, capture)
    const gpuAnalysis = analyzeGpu(seedAnalysis.cases, gpu, capture)
    const verdict = !gpuAnalysis.extended_horizon_contract.pass
      ? 'INVALID'
      : !capture.h1.pass || !seedAnalysis.cpu.pass || !gpuAnalysis.gpu_seed_contract.pass
        ? 'FAIL'
        : 'PASS'
    const receipt = {
      protocol: PROTOCOL,
      version: VERSION,
      artifacts: {
        capture: { path: 'CassiFI/artifacts/native/hidden-state-capture.json', sha256: sha256(captureBytes) },
        seed: { path: 'CassiCosmos/_diag/cassi_qwen_hidden_state_field_seed.json', sha256: sha256(seedBytes) },
        gpu: { path: 'CassiCosmos/_diag/cassi_qwen_hidden_state_field_gpu.json', sha256: sha256(gpuBytes) },
      },
      config: {
        grid_n: GRID_N,
        dimension: L16_DIMENSION,
        mode_count: L16_MODE_CAPACITY,
        phi: PHI,
        amplitude: AMPLITUDE,
        dt: DT,
        horizons: [...HORIZONS],
        layout: LAYOUT,
        dtype: DTYPE,
      },
      hidden_l2_norm: capture.hiddenNorm,
      capture_parity: capture.h1,
      cpu_codec_contract: seedAnalysis.cpu,
      ...gpuAnalysis,
      gates: {
        H1: capture.h1.pass,
        H2: seedAnalysis.cpu.pass && gpuAnalysis.gpu_seed_contract.pass,
        H3: gpuAnalysis.extended_horizon_contract.pass,
      },
      verdict,
    }
    await writeAtomic(RECEIPT_PATH, receipt)
    console.log(JSON.stringify({
      verdict,
      gates: receipt.gates,
      max_abs: receipt.extended_horizon_contract.max_abs,
      path: RECEIPT_PATH,
    }, null, 2))
    if (verdict !== 'PASS') process.exitCode = 1
  } catch (error) {
    const receipt = {
      protocol: PROTOCOL,
      version: VERSION,
      artifacts: {
        ...(captureBytes ? { capture: { path: 'CassiFI/artifacts/native/hidden-state-capture.json', sha256: sha256(captureBytes) } } : {}),
        ...(seedBytes ? { seed: { path: 'CassiCosmos/_diag/cassi_qwen_hidden_state_field_seed.json', sha256: sha256(seedBytes) } } : {}),
        ...(gpuBytes ? { gpu: { path: 'CassiCosmos/_diag/cassi_qwen_hidden_state_field_gpu.json', sha256: sha256(gpuBytes) } } : {}),
      },
      gates: { H1: false, H2: false, H3: false },
      verdict: error instanceof ContractError ? error.verdict : 'INVALID',
      reason: error instanceof Error ? error.message : String(error),
    }
    await writeAtomic(RECEIPT_PATH, receipt)
    console.error(JSON.stringify(receipt, null, 2))
    process.exitCode = 1
  }
}

const command = process.argv[2]
if (command === '--prepare-field') await prepareField()
else if (command === '--analyze') await analyze()
else {
  console.error('Usage: node run-l16-hidden-state-observatory.mjs --prepare-field | --analyze')
  process.exitCode = 2
}
