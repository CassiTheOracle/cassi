import { Buffer } from 'node:buffer'
import { createHash } from 'node:crypto'
import { mkdir, readFile, rename, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  AMPLITUDE,
  DTYPE,
  GRID_N,
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
} from './cassi-embedding-field-codec.mjs'

const HERE = dirname(fileURLToPath(import.meta.url))
const DIAG = resolve(HERE, '../CassiCosmos/_diag')
const CAPTURE_PATH = resolve(HERE, 'all-layer-hidden-state-capture.json')
const SEED_PATH = resolve(DIAG, 'cassi_qwen_all_layer_iir_seed.json')
const GPU_PATH = resolve(DIAG, 'cassi_qwen_all_layer_iir_gpu.json')
const RECEIPT_PATH = resolve(HERE, 'all-layer-iir-observatory.json')

const PROTOCOL = 'CassiQwen L17 all-layer IIR field observatory'
const VERSION = 1
const DIMENSION = L16_DIMENSION
const MODE_CAPACITY = L16_MODE_CAPACITY
const VOLUME = GRID_N ** 3
const LAYER_COUNT = 64
const RETAINED_WEIGHT = 0.9
const STEPS_PER_LAYER = 4
const LAYER_CHECKPOINTS = Object.freeze([0, 1, 2, 3, 7, 15, 31, 47, 63])
const CONTINUATION_HORIZONS = Object.freeze([0, 1, 4, 16, 64])
const FORWARD_ORDER = Object.freeze(Array.from({ length: LAYER_COUNT }, (_, index) => index))
const REVERSE_ORDER = Object.freeze([...FORWARD_ORDER].reverse())
const ARM_IDS = Object.freeze(['forward_canonical', 'reverse_canonical', 'forward_shuffled', 'zero'])
const ARM_BASIS = Object.freeze({
  forward_canonical: 'canonical',
  reverse_canonical: 'canonical',
  forward_shuffled: 'shuffled',
  zero: 'zero',
})
const COSINE_MIN = 0.999999
const RELATIVE_L2_MAX = 2e-6
const LOGIT_DELTA_MAX = 1e-6
const MAX_FIELD_ABS = 10
const FIRST_BLEND_ERROR_MAX = 2e-6
const TOP_K = 16
const FLOAT32_BYTES = 4
const MODEL_SHA256 = '7e78da5d7e3ae28d178121f58646953305f3e5bd3cb46f4a75584e8b6c6fe169'
const MODEL_PATH = 'Qwen3.8-27B-Q4_K_M.gguf'
const MODEL_ARCHITECTURE = 'qwen35'
const MODEL_VOCABULARY_SIZE = 248320
const RUNTIME_FILE_HASHES = Object.freeze({
  llama_dll_sha256: 'd5bb3c11dd5767f4f0041e04a82e1c2fd54c687f1996706bba6e3bfdb7d3c5a6',
  ggml_dll_sha256: '362831c05b00cc6b7dabf0f4868894564f52740d0c3ae6a1d7f3d13e38046942',
  ggml_base_dll_sha256: '841889f26faacff284c2c5607f96358d2bbd0605c36fb33709e7e9490d2fec5b',
  openmp_dll_sha256: '4a20c1e5c115c29771a12324513eb109badac72180f79481527ad79d996ffb33',
})
const RUNTIME_EXPECTED = Object.freeze({
  llama_version: '0.1.1-dev',
  package_build: 10472,
  package_commit: '60eeeb608',
  requested_gpu_layers: 99,
  context_size: 512,
  batch_size: 512,
})
const PROMPT_UTF8 = 'Cassi hidden-state observatory: reply with exactly one physical field name.'
const PROMPT_SHA256 = 'd4d47a5b46c1c6ba6706643da2a73b752572bf2d862c55f7171bab255c6628ad'
const PROMPT_TOKEN_IDS = Object.freeze([34, 78732, 7920, 20105, 9006, 5101, 25, 9559, 440, 6681, 799, 6745, 2002, 803, 13])
const PROMPT_TOKENIZATION = Object.freeze({ add_special: true, parse_special: true })
const EXPECTED_BASIS = Object.freeze({
  kind: 'real-periodic-fourier',
  flat_layout: LAYOUT,
  coefficient_pair: 'X[k]=sqrt(V/2)*(a-i*b), X[-k]=conjugate(X[k])',
  mode_order: 'k2 then signed (kz,ky,kx)',
  ...modeBasisManifest({ count: MODE_CAPACITY, gridN: GRID_N }),
})

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

function numericClose(actual, expected, tolerance = 2e-6) {
  return Number.isFinite(actual)
    && Number.isFinite(expected)
    && Math.abs(actual - expected) <= tolerance * Math.max(1, Math.abs(actual), Math.abs(expected))
}

function exactArray(actual, expected, label) {
  requireCondition(Array.isArray(actual), `${label} must be an array`)
  requireCondition(actual.length === expected.length, `${label} length mismatch`)
  for (let index = 0; index < expected.length; index += 1) {
    requireCondition(actual[index] === expected[index], `${label}[${index}] mismatch`)
  }
}

function exactObject(actual, expected, label) {
  requireCondition(actual && typeof actual === 'object' && !Array.isArray(actual), `${label} must be an object`)
  for (const [key, value] of Object.entries(expected)) {
    requireCondition(actual[key] === value, `${label}.${key} mismatch`)
  }
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
    requireCondition(Number.isFinite(row.logit), `${label} top16 row ${index} has no finite logit`)
    requireCondition(row.token_id === expected[index].tokenId, `${label} top16 token rank ${index} mismatch`)
    requireCondition(numericClose(row.logit, expected[index].value, 1e-7), `${label} top16 logit rank ${index} mismatch`)
  }
  return expected
}

function validateRuntime(runtime) {
  requireCondition(runtime && typeof runtime === 'object' && !Array.isArray(runtime), 'capture runtime is incomplete')
  for (const [key, expected] of Object.entries(RUNTIME_EXPECTED)) {
    requireCondition(runtime[key] === expected, `capture runtime.${key} mismatch`)
  }
  requireCondition(runtime.backend_loader === 'ggml_backend_load_all_from_path', 'capture backend loader mismatch')
  requireCondition(runtime.backend_path === 'CassiQwen', 'capture backend path mismatch')
  const expectedRuntimeFiles = {
    llama_dll: 'llama.dll',
    ggml_dll: 'ggml.dll',
    ggml_base_dll: 'ggml-base.dll',
    openmp_dll: 'libomp140.x86_64.dll',
  }
  for (const [key, expected] of Object.entries(expectedRuntimeFiles)) {
    requireCondition(runtime[key] === expected, `capture runtime.${key} mismatch`)
  }
  for (const [key, expected] of Object.entries(RUNTIME_FILE_HASHES)) {
    requireCondition(runtime[key] === expected, `capture runtime.${key} mismatch`)
  }
}

function validatePrompt(prompt) {
  requireCondition(prompt && typeof prompt === 'object' && !Array.isArray(prompt), 'capture prompt is incomplete')
  requireCondition(prompt.utf8 === PROMPT_UTF8, 'capture prompt bytes mismatch')
  requireCondition(prompt.sha256 === PROMPT_SHA256, 'capture prompt SHA-256 mismatch')
  requireCondition(JSON.stringify(prompt.tokenization) === JSON.stringify(PROMPT_TOKENIZATION), 'capture prompt tokenization mismatch')
  exactArray(prompt.token_ids, PROMPT_TOKEN_IDS, 'capture prompt token IDs')
  requireCondition(prompt.token_count === PROMPT_TOKEN_IDS.length, 'capture prompt token count mismatch')
  requireCondition(prompt.final_token_index === PROMPT_TOKEN_IDS.length - 1, 'capture final token index mismatch')
  requireCondition(prompt.final_token_id === PROMPT_TOKEN_IDS.at(-1), 'capture final token ID mismatch')
}

function validateCapture(document, rawBytes) {
  requireCondition(document && typeof document === 'object' && !Array.isArray(document), 'capture receipt must be an object')
  requireCondition(document.protocol === PROTOCOL, 'capture protocol mismatch')
  requireCondition(document.version === VERSION, 'capture version mismatch')
  requireCondition(document.verdict === 'PASS' || document.verdict === 'FAIL', 'capture verdict is malformed')

  const model = document.model
  requireCondition(model && typeof model === 'object' && !Array.isArray(model), 'capture model is incomplete')
  requireCondition(model.path === MODEL_PATH, 'capture model path mismatch')
  requireCondition(model.sha256 === MODEL_SHA256, 'capture model hash mismatch')
  requireCondition(model.architecture === MODEL_ARCHITECTURE, 'capture model architecture mismatch')
  requireCondition(model.hidden_dimension === DIMENSION, 'capture hidden dimension mismatch')
  requireCondition(model.layer_count === LAYER_COUNT, 'capture model layer count mismatch')
  requireCondition(model.vocabulary_size === MODEL_VOCABULARY_SIZE, 'capture vocabulary size mismatch')
  validateRuntime(document.runtime)
  validatePrompt(document.prompt)

  const hook = document.hook
  requireCondition(hook && typeof hook === 'object' && !Array.isArray(hook), 'capture hook is incomplete')
  requireCondition(hook.kind === 'all_layer_input_residuals', 'capture hook kind mismatch')
  requireCondition(hook.layer_rule === '0..n_layer-1', 'capture hook layer rule mismatch')
  exactArray(hook.layer_indices, FORWARD_ORDER, 'capture hook layer indices')
  requireCondition(hook.token_row === document.prompt.final_token_index, 'capture hook token row mismatch')
  requireCondition(typeof hook.setter_export === 'string' && hook.setter_export.includes('llama_set_embeddings_layer_inp'), 'capture setter export mismatch')
  requireCondition(typeof hook.getter_export === 'string' && hook.getter_export.includes('llama_get_embeddings_layer_inp'), 'capture getter export mismatch')

  const layers = document.layers
  requireCondition(Array.isArray(layers) && layers.length === LAYER_COUNT, 'capture layer rows must contain exactly 64 entries')
  const parsedLayers = []
  for (let index = 0; index < LAYER_COUNT; index += 1) {
    const row = layers[index]
    requireCondition(row && typeof row === 'object' && !Array.isArray(row), `capture layer ${index} is malformed`)
    requireCondition(row.layer_index === index, `capture layer ${index} true index mismatch`)
    const raw = validateBase64Hash(row.hidden_state_b64, row.hidden_state_sha256, `capture layer ${index} hidden state`)
    requireCondition(raw.byteLength === DIMENSION * FLOAT32_BYTES, `capture layer ${index} hidden state byte size mismatch`)
    const hidden = base64ToFloat32(row.hidden_state_b64, DIMENSION)
    requireCondition(finite(hidden), `capture layer ${index} hidden state contains non-finite values`)
    const norm = l2Norm(hidden)
    requireCondition(norm > 0 && Number.isFinite(norm), `capture layer ${index} hidden norm is invalid`)
    requireCondition(numericClose(row.hidden_l2_norm, norm, 1e-12), `capture layer ${index} hidden norm mismatch`)
    parsedLayers.push({
      layer_index: index,
      hidden_state_b64: row.hidden_state_b64,
      hidden_state_sha256: row.hidden_state_sha256,
      hidden_l2_norm: norm,
      hidden,
    })
  }

  const off = document.capture_off
  const on = document.capture_on
  requireCondition(off && on, 'capture parity arms are absent')
  const expectedLogitBytes = model.vocabulary_size * FLOAT32_BYTES
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
  requireCondition(parity && typeof parity === 'object' && !Array.isArray(parity), 'capture parity metadata is absent')
  requireCondition(parity.argmax_match === (offArgmax === onArgmax), 'capture argmax parity metadata mismatch')
  requireCondition(parity.top16_token_ids_match === topIdsMatch, 'capture top16 parity metadata mismatch')
  requireCondition(numericClose(parity.max_abs_logit_difference, maxDelta, 1e-12), 'capture logit delta metadata mismatch')
  requireCondition(numericClose(parity.max_abs_logit_difference_bound, LOGIT_DELTA_MAX, 1e-12), 'capture logit delta bound mismatch')
  const h1Pass = offArgmax === onArgmax && topIdsMatch && maxDelta <= LOGIT_DELTA_MAX
  requireCondition(parity.pass === h1Pass, 'capture parity pass metadata mismatch')
  requireCondition(document.verdict === (h1Pass ? 'PASS' : 'FAIL'), 'capture verdict/parity mismatch')

  return {
    document,
    rawBytes,
    hash: sha256(rawBytes),
    layers: parsedLayers,
    h1: {
      pass: h1Pass,
      argmax_token_id: offArgmax,
      max_abs_logit_difference: maxDelta,
      top16_token_ids_match: topIdsMatch,
    },
  }
}

function assertFieldCommon(document, label, { requireAmplitude = false } = {}) {
  requireCondition(document && typeof document === 'object' && !Array.isArray(document), `${label} must be an object`)
  requireCondition(document.protocol === PROTOCOL, `${label} protocol mismatch`)
  requireCondition(document.version === VERSION, `${label} version mismatch`)
  requireCondition(document.grid_n === GRID_N, `${label} grid_n mismatch`)
  requireCondition(document.dimension === DIMENSION, `${label} dimension mismatch`)
  requireCondition(numericClose(document.phi, PHI, 1e-13), `${label} phi mismatch`)
  requireCondition(numericClose(document.dt, 0.005, 1e-13), `${label} dt mismatch`)
  requireCondition(document.layout === LAYOUT && document.dtype === DTYPE, `${label} layout/dtype mismatch`)
  if (requireAmplitude) requireCondition(numericClose(document.amplitude, AMPLITUDE, 1e-13), `${label} amplitude mismatch`)
}

function validateSeedLayerRows(rows, captureLayers, basis, label) {
  requireCondition(Array.isArray(rows) && rows.length === LAYER_COUNT, `${label} must contain exactly 64 rows`)
  const parsed = []
  for (let index = 0; index < LAYER_COUNT; index += 1) {
    const row = rows[index]
    const capture = captureLayers[index]
    requireCondition(row && typeof row === 'object' && !Array.isArray(row), `${label}[${index}] is malformed`)
    requireCondition(row.layer_index === index, `${label}[${index}] layer index mismatch`)
    requireCondition(!Object.prototype.hasOwnProperty.call(row, 'signal_b64'), `${label}[${index}] must not duplicate signal`) 
    requireCondition(row.hidden_state_sha256 === capture.hidden_state_sha256, `${label}[${index}] hidden state hash mismatch`)
    requireCondition(numericClose(row.hidden_l2_norm, capture.hidden_l2_norm, 1e-12), `${label}[${index}] hidden norm mismatch`)
    const ey = base64ToFloat32(row.ey_b64, VOLUME)
    const ei = base64ToFloat32(row.ei_b64, VOLUME)
    requireCondition(finite(ey) && finite(ei), `${label}[${index}] contains non-finite field values`)
    const expected = encodeEmbedding(capture.hidden, { dimension: DIMENSION, capacity: DIMENSION, gridN: GRID_N, basis })
    requireCondition(row.ey_b64 === float32ToBase64(expected.ey), `${label}[${index}] EY differs from deterministic codec`)
    requireCondition(row.ei_b64 === float32ToBase64(expected.ei), `${label}[${index}] EI differs from deterministic codec`)
    parsed.push({ ...row, ey, ei })
  }
  return parsed
}

function validateSeed(seed, capture) {
  assertFieldCommon(seed, 'seed', { requireAmplitude: true })
  exactObject(seed, {
    retained_weight: RETAINED_WEIGHT,
    steps_per_layer: STEPS_PER_LAYER,
    layer_count: LAYER_COUNT,
  }, 'seed')
  exactArray(seed.layer_checkpoints, LAYER_CHECKPOINTS, 'seed layer checkpoints')
  exactArray(seed.continuation_horizons, CONTINUATION_HORIZONS, 'seed continuation horizons')
  requireCondition(seed.capture_sha256 === capture.hash, 'seed capture hash mismatch')
  requireCondition(JSON.stringify(seed.basis) === JSON.stringify(EXPECTED_BASIS), 'seed Fourier basis manifest mismatch')
  return {
    canonical: validateSeedLayerRows(seed.canonical_layers, capture.layers, 'canonical', 'seed canonical_layers'),
    shuffled: validateSeedLayerRows(seed.shuffled_layers, capture.layers, 'shuffled', 'seed shuffled_layers'),
  }
}

function compareReportedMetric(actual, reported, label) {
  requireCondition(Number.isFinite(reported), `${label} is not finite`)
  requireCondition(numericClose(actual, reported), `${label} disagrees with raw field`)
}

function validateMetricRow(row, label) {
  requireCondition(row && typeof row === 'object' && !Array.isArray(row), `${label} is malformed`)
  requireCondition(row.finite === true, `${label} finite flag failed`)
  for (const key of ['max_abs', 'ey_l2', 'ei_l2', 'epsilon_l2']) {
    requireCondition(Number.isFinite(row[key]) && row[key] >= 0, `${label}.${key} is invalid`)
  }
  requireCondition(row.max_abs <= MAX_FIELD_ABS, `${label}.max_abs exceeds field bound`)
}

function validateRawFieldRow(row, label, basis, expectedMetrics = undefined) {
  validateMetricRow(row, label)
  const ey = base64ToFloat32(row.ey_b64, VOLUME)
  const ei = base64ToFloat32(row.ei_b64, VOLUME)
  requireCondition(finite(ey) && finite(ei), `${label} raw field is non-finite`)
  const metrics = fieldMetrics(ey, ei, { dimension: DIMENSION, capacity: DIMENSION, gridN: GRID_N, basis: basis === 'zero' ? 'canonical' : basis, phi: PHI })
  compareReportedMetric(metrics.maxAbs, row.max_abs, `${label}.max_abs`)
  compareReportedMetric(metrics.ey_l2, row.ey_l2, `${label}.ey_l2`)
  compareReportedMetric(metrics.ei_l2, row.ei_l2, `${label}.ei_l2`)
  compareReportedMetric(metrics.epsilon_l2, row.epsilon_l2, `${label}.epsilon_l2`)
  if (expectedMetrics) {
    for (const key of ['max_abs', 'ey_l2', 'ei_l2', 'epsilon_l2']) compareReportedMetric(expectedMetrics[key], row[key], `${label}.${key} summary agreement`)
  }
  return { ...row, ey, ei, metrics }
}

function expectedStepForLayer(updateIndex) {
  return STEPS_PER_LAYER * (updateIndex + 1)
}

function expectedTime(step) {
  return step * 0.005
}

function validateGpu(gpu, captureHash, captureLayers) {
  assertFieldCommon(gpu, 'GPU receipt')
  exactObject(gpu, {
    retained_weight: RETAINED_WEIGHT,
    steps_per_layer: STEPS_PER_LAYER,
    layer_count: LAYER_COUNT,
  }, 'GPU receipt')
  exactArray(gpu.layer_checkpoints, LAYER_CHECKPOINTS, 'GPU layer checkpoints')
  exactArray(gpu.continuation_horizons, CONTINUATION_HORIZONS, 'GPU continuation horizons')
  requireCondition(gpu.capture_sha256 === captureHash, 'GPU capture hash mismatch')
  requireCondition(gpu.finite === true, 'GPU receipt finite flag failed')
  requireCondition(gpu.verdict === 'PASS', `GPU receipt verdict is ${String(gpu.verdict)}`)
  requireCondition(Array.isArray(gpu.arms) && gpu.arms.length === ARM_IDS.length, 'GPU arm array shape mismatch')

  const armResults = {}
  let h2 = true
  let h3 = true
  let maximumFieldAbs = 0
  let zeroByteZero = true
  let firstBlendPass = true

  for (let armIndex = 0; armIndex < ARM_IDS.length; armIndex += 1) {
    const id = ARM_IDS[armIndex]
    const arm = gpu.arms[armIndex]
    const basis = ARM_BASIS[id]
    const expectedOrder = id === 'reverse_canonical' ? REVERSE_ORDER : FORWARD_ORDER
    requireCondition(arm && typeof arm === 'object' && !Array.isArray(arm), `GPU arm ${id} is malformed`)
    requireCondition(arm.id === id, `GPU arm ${id} id/order mismatch`)
    requireCondition(arm.basis === basis, `GPU arm ${id} basis mismatch`)
    exactArray(arm.layer_order, expectedOrder, `GPU arm ${id} layer order`)
    const firstBlend = arm.first_blend_contract
    requireCondition(firstBlend && typeof firstBlend === 'object' && !Array.isArray(firstBlend), `GPU arm ${id} first blend contract is absent`)
    requireCondition(firstBlend.pass === true, `GPU arm ${id} first blend contract failed`, 'FAIL')
    requireCondition(Number.isFinite(firstBlend.max_abs_error) && firstBlend.max_abs_error >= 0, `GPU arm ${id} first blend error is invalid`)
    const firstBlendArmPass = firstBlend.max_abs_error <= FIRST_BLEND_ERROR_MAX
    firstBlendPass = firstBlendPass && firstBlendArmPass
    h2 = h2 && firstBlendArmPass

    const summaries = arm.layer_summaries
    requireCondition(Array.isArray(summaries) && summaries.length === LAYER_COUNT, `GPU arm ${id} layer summary count mismatch`)
    const summaryByLayer = new Map()
    const summaryRows = []
    for (let updateIndex = 0; updateIndex < LAYER_COUNT; updateIndex += 1) {
      const row = summaries[updateIndex]
      const expectedLayer = expectedOrder[updateIndex]
      requireCondition(row && typeof row === 'object' && !Array.isArray(row), `GPU arm ${id} summary ${updateIndex} is malformed`)
      requireCondition(row.layer_index === expectedLayer, `GPU arm ${id} summary ${updateIndex} layer mismatch`)
      requireCondition(row.update_index === updateIndex, `GPU arm ${id} summary ${updateIndex} update index mismatch`)
      const step = expectedStepForLayer(updateIndex)
      requireCondition(row.step === step, `GPU arm ${id} summary ${updateIndex} step mismatch`)
      requireCondition(numericClose(row.t, expectedTime(step), 1e-6), `GPU arm ${id} summary ${updateIndex} time mismatch`)
      validateMetricRow(row, `GPU arm ${id} summary ${updateIndex}`)
      maximumFieldAbs = Math.max(maximumFieldAbs, row.max_abs)
      if (id === 'zero') {
        const summaryZero = row.max_abs === 0 && row.ey_l2 === 0 && row.ei_l2 === 0 && row.epsilon_l2 === 0
        zeroByteZero = zeroByteZero && summaryZero
        h3 = h3 && summaryZero
      }
      summaryByLayer.set(row.layer_index, row)
      summaryRows.push({
        layer_index: row.layer_index,
        update_index: row.update_index,
        step: row.step,
        t: row.t,
        finite: row.finite,
        max_abs: row.max_abs,
        ey_l2: row.ey_l2,
        ei_l2: row.ei_l2,
        epsilon_l2: row.epsilon_l2,
      })
    }

    const layerCheckpoints = arm.layer_checkpoints
    requireCondition(Array.isArray(layerCheckpoints) && layerCheckpoints.length === LAYER_CHECKPOINTS.length, `GPU arm ${id} layer checkpoint count mismatch`)
    const checkpointRows = []
    for (let checkpointIndex = 0; checkpointIndex < LAYER_CHECKPOINTS.length; checkpointIndex += 1) {
      const layerIndex = LAYER_CHECKPOINTS[checkpointIndex]
      const row = layerCheckpoints[checkpointIndex]
      requireCondition(row && typeof row === 'object' && !Array.isArray(row), `GPU arm ${id} layer checkpoint ${layerIndex} is malformed`)
      requireCondition(row.layer_index === layerIndex, `GPU arm ${id} layer checkpoint ${layerIndex} layer mismatch`)
      const updateIndex = expectedOrder.indexOf(layerIndex)
      requireCondition(row.update_index === updateIndex, `GPU arm ${id} layer checkpoint ${layerIndex} update index mismatch`)
      const step = expectedStepForLayer(updateIndex)
      requireCondition(row.step === step, `GPU arm ${id} layer checkpoint ${layerIndex} step mismatch`)
      requireCondition(numericClose(row.t, expectedTime(step), 1e-6), `GPU arm ${id} layer checkpoint ${layerIndex} time mismatch`)
      const summary = summaryByLayer.get(layerIndex)
      const parsed = validateRawFieldRow(row, `GPU arm ${id} layer checkpoint ${layerIndex}`, basis, summary)
      maximumFieldAbs = Math.max(maximumFieldAbs, parsed.metrics.maxAbs)
      const checkpointAgrees = numericClose(parsed.t, summary.t, 1e-6)
        && parsed.step === summary.step
        && parsed.finite === summary.finite
      h3 = h3 && checkpointAgrees
      if (id === 'zero') {
        const byteZero = Buffer.from(row.ey_b64, 'base64').every((value) => value === 0)
          && Buffer.from(row.ei_b64, 'base64').every((value) => value === 0)
        zeroByteZero = zeroByteZero && byteZero
        h3 = h3 && byteZero
      }
      checkpointRows.push({
        layer_index: row.layer_index,
        update_index: row.update_index,
        step: row.step,
        t: row.t,
        finite: parsed.metrics.finite,
        max_abs: parsed.metrics.maxAbs,
        ey_l2: parsed.metrics.ey_l2,
        ei_l2: parsed.metrics.ei_l2,
        epsilon_l2: parsed.metrics.epsilon_l2,
        decoded: id === 'zero' ? null : decodeCheckpoint(parsed, basis, captureLayers, row.layer_index),
        contract_pass: checkpointAgrees,
      })
    }

    const continuations = arm.continuation_checkpoints
    requireCondition(Array.isArray(continuations) && continuations.length === CONTINUATION_HORIZONS.length, `GPU arm ${id} continuation checkpoint count mismatch`)
    const continuationRows = []
    for (let horizonIndex = 0; horizonIndex < CONTINUATION_HORIZONS.length; horizonIndex += 1) {
      const horizon = CONTINUATION_HORIZONS[horizonIndex]
      const row = continuations[horizonIndex]
      requireCondition(row && typeof row === 'object' && !Array.isArray(row), `GPU arm ${id} continuation ${horizon} is malformed`)
      requireCondition(row.horizon === horizon, `GPU arm ${id} continuation ${horizon} horizon mismatch`)
      const step = LAYER_COUNT * STEPS_PER_LAYER + horizon
      requireCondition(row.step === step, `GPU arm ${id} continuation ${horizon} step mismatch`)
      requireCondition(numericClose(row.t, expectedTime(step), 1e-6), `GPU arm ${id} continuation ${horizon} time mismatch`)
      const parsed = validateRawFieldRow(row, `GPU arm ${id} continuation ${horizon}`, basis)
      maximumFieldAbs = Math.max(maximumFieldAbs, parsed.metrics.maxAbs)
      if (id === 'zero') {
        const byteZero = Buffer.from(row.ey_b64, 'base64').every((value) => value === 0)
          && Buffer.from(row.ei_b64, 'base64').every((value) => value === 0)
        zeroByteZero = zeroByteZero && byteZero
        h3 = h3 && byteZero
      }
      continuationRows.push({
        horizon: row.horizon,
        step: row.step,
        t: row.t,
        finite: parsed.metrics.finite,
        max_abs: parsed.metrics.maxAbs,
        ey_l2: parsed.metrics.ey_l2,
        ei_l2: parsed.metrics.ei_l2,
        epsilon_l2: parsed.metrics.epsilon_l2,
        decoded: id === 'zero' ? null : decodeCheckpoint(parsed, basis, captureLayers, null),
        contract_pass: true,
      })
    }

    armResults[id] = {
      id,
      basis,
      layer_order: [...arm.layer_order],
      first_blend_contract: {
        pass: firstBlend.pass,
        max_abs_error: firstBlend.max_abs_error,
        contract_pass: firstBlendArmPass,
      },
      layer_summaries: summaryRows,
      layer_checkpoints: checkpointRows,
      continuation_checkpoints: continuationRows,
    }
  }

  if (maximumFieldAbs > MAX_FIELD_ABS || !zeroByteZero) h3 = false
  return {
    pass_h2_first_blend: firstBlendPass,
    pass_h3_transport: h3,
    max_abs: maximumFieldAbs,
    bound: MAX_FIELD_ABS,
    zero_byte_zero: zeroByteZero,
    arms: armResults,
  }
}

function decodeCheckpoint(parsed, basis, captureLayers, layerIndex) {
  const direction = decodeEmbedding({ ey: parsed.ey, ei: parsed.ei }, {
    dimension: DIMENSION,
    capacity: DIMENSION,
    gridN: GRID_N,
    basis: basis === 'zero' ? 'canonical' : basis,
    phi: PHI,
    amplitude: AMPLITUDE,
  })
  requireCondition(finite(direction), 'GPU decoded direction contains non-finite values')
  const result = {
    direction_norm: l2Norm(direction),
    subspace_residual_energy: parsed.metrics.subspace_residual_energy,
  }
  if (layerIndex !== null && layerIndex !== undefined && captureLayers) {
    const source = captureLayers[layerIndex]
    const expected = normalizeEmbeddingWithNorm(source.hidden, { dimension: DIMENSION, capacity: DIMENSION })
    const restored = restoreEmbeddingNorm(direction, source.hidden_l2_norm, { dimension: DIMENSION })
    result.direction_cosine = cosineSimilarity(direction, expected.vector)
    result.restored_cosine = cosineSimilarity(restored, source.hidden)
    result.restored_relative_l2_error = relativeL2Error(restored, source.hidden)
  }
  return result
}

function analyzeCpuCodec(captureLayers, seedLayers) {
  const rows = { canonical: [], shuffled: [] }
  let pass = true
  for (const basis of ['canonical', 'shuffled']) {
    const seedRows = seedLayers[basis]
    for (let layerIndex = 0; layerIndex < LAYER_COUNT; layerIndex += 1) {
      const source = captureLayers[layerIndex]
      const row = seedRows[layerIndex]
      const direction = decodeEmbedding({ ey: row.ey, ei: row.ei }, {
        dimension: DIMENSION,
        capacity: DIMENSION,
        gridN: GRID_N,
        basis,
        phi: PHI,
        amplitude: AMPLITUDE,
      })
      const normalized = normalizeEmbeddingWithNorm(source.hidden, { dimension: DIMENSION, capacity: DIMENSION })
      const restored = restoreEmbeddingNorm(direction, source.hidden_l2_norm, { dimension: DIMENSION })
      const metrics = fieldMetrics(row.ey, row.ei, { dimension: DIMENSION, capacity: DIMENSION, gridN: GRID_N, basis, phi: PHI })
      const directionCosine = cosineSimilarity(direction, normalized.vector)
      const restoredCosine = cosineSimilarity(restored, source.hidden)
      const restoredRelativeL2 = relativeL2Error(restored, source.hidden)
      const rowPass = directionCosine >= COSINE_MIN && restoredCosine >= COSINE_MIN && restoredRelativeL2 <= RELATIVE_L2_MAX
      pass = pass && rowPass
      rows[basis].push({
        layer_index: layerIndex,
        hidden_l2_norm: source.hidden_l2_norm,
        direction_cosine: directionCosine,
        restored_cosine: restoredCosine,
        restored_relative_l2_error: restoredRelativeL2,
        decoded_direction_norm: l2Norm(direction),
        subspace_residual_energy: metrics.subspace_residual_energy,
        pass: rowPass,
      })
    }
  }
  return {
    pass,
    thresholds: { cosine_min: COSINE_MIN, relative_l2_max: RELATIVE_L2_MAX },
    rows,
  }
}

function iirDirectionBaseline(captureLayers, order) {
  const state = new Float64Array(DIMENSION)
  const rows = []
  for (let updateIndex = 0; updateIndex < order.length; updateIndex += 1) {
    const layerIndex = order[updateIndex]
    const normalized = normalizeEmbeddingWithNorm(captureLayers[layerIndex].hidden, { dimension: DIMENSION, capacity: DIMENSION }).vector
    for (let coordinate = 0; coordinate < DIMENSION; coordinate += 1) {
      state[coordinate] = RETAINED_WEIGHT * state[coordinate] + (1 - RETAINED_WEIGHT) * normalized[coordinate]
    }
    const stateNorm = l2Norm(state)
    rows.push({
      layer_index: layerIndex,
      update_index: updateIndex,
      norm: stateNorm,
      direction_cosine_to_input: cosineSimilarity(state, normalized),
    })
  }
  return { rows, terminal_norm: l2Norm(state), terminal_direction: state }
}

function summarizeBaseline(baseline, decodedTerminal) {
  return {
    layer_rows: baseline.rows,
    terminal_norm: baseline.terminal_norm,
    terminal_decoded_cosine: decodedTerminal === null ? null : cosineSimilarity(baseline.terminal_direction, decodedTerminal),
  }
}

function buildReceipt(capture, captureBytes, seed, seedBytes, gpu, gpuBytes, cpu, gpuAnalysis, baselines, h4) {
  const h1 = capture.h1.pass
  const h2 = cpu.pass && gpuAnalysis.pass_h2_first_blend && gpuAnalysis.zero_byte_zero
  const h3 = gpuAnalysis.pass_h3_transport
  const verdict = !h3 ? 'INVALID' : !h1 || !h2 ? 'FAIL' : 'PASS'
  const h4Verdict = !h1 || !h2 || !h3 ? 'INVALID' : h4.cosine_gap >= 1e-4 ? 'SUPPORTS' : 'NULL'
  return {
    protocol: PROTOCOL,
    version: VERSION,
    artifacts: {
      capture: { path: 'CassiQwen/all-layer-hidden-state-capture.json', sha256: sha256(captureBytes) },
      seed: { path: 'CassiCosmos/_diag/cassi_qwen_all_layer_iir_seed.json', sha256: sha256(seedBytes) },
      gpu: { path: 'CassiCosmos/_diag/cassi_qwen_all_layer_iir_gpu.json', sha256: sha256(gpuBytes) },
    },
    config: {
      grid_n: GRID_N,
      dimension: DIMENSION,
      mode_count: MODE_CAPACITY,
      phi: PHI,
      amplitude: AMPLITUDE,
      dt: 0.005,
      retained_weight: RETAINED_WEIGHT,
      steps_per_layer: STEPS_PER_LAYER,
      layer_count: LAYER_COUNT,
      layer_checkpoints: [...LAYER_CHECKPOINTS],
      continuation_horizons: [...CONTINUATION_HORIZONS],
      layout: LAYOUT,
      dtype: DTYPE,
    },
    capture_parity: capture.h1,
    cpu_codec_contract: cpu,
    ordinary_cpu_iir_direction_baseline: baselines,
    gpu_contract: {
      first_blend_pass: gpuAnalysis.pass_h2_first_blend,
      h3_transport_pass: gpuAnalysis.pass_h3_transport,
      max_abs: gpuAnalysis.max_abs,
      bound: gpuAnalysis.bound,
      zero_byte_zero: gpuAnalysis.zero_byte_zero,
      arms: gpuAnalysis.arms,
    },
    h4_temporal_order: {
      cosine: h4.cosine,
      forward_reverse_cosine: h4.cosine,
      one_minus_cosine: h4.cosine_gap,
      threshold: 1e-4,
      verdict: h4Verdict,
    },
    gates: { H1: h1, H2: h2, H3: h3, H4: h4Verdict },
    verdict,
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
  requireCondition(capture.h1.pass, 'capture parity gate failed', 'FAIL')
  const canonicalLayers = []
  const shuffledLayers = []
  for (const source of capture.layers) {
    const canonical = encodeEmbedding(source.hidden, { dimension: DIMENSION, capacity: DIMENSION, gridN: GRID_N, basis: 'canonical', phi: PHI, amplitude: AMPLITUDE })
    const shuffled = encodeEmbedding(source.hidden, { dimension: DIMENSION, capacity: DIMENSION, gridN: GRID_N, basis: 'shuffled', phi: PHI, amplitude: AMPLITUDE })
    canonicalLayers.push({
      layer_index: source.layer_index,
      ey_b64: float32ToBase64(canonical.ey),
      ei_b64: float32ToBase64(canonical.ei),
      hidden_l2_norm: source.hidden_l2_norm,
      hidden_state_sha256: source.hidden_state_sha256,
    })
    shuffledLayers.push({
      layer_index: source.layer_index,
      ey_b64: float32ToBase64(shuffled.ey),
      ei_b64: float32ToBase64(shuffled.ei),
      hidden_l2_norm: source.hidden_l2_norm,
      hidden_state_sha256: source.hidden_state_sha256,
    })
  }
  const seed = {
    protocol: PROTOCOL,
    version: VERSION,
    grid_n: GRID_N,
    dimension: DIMENSION,
    phi: PHI,
    amplitude: AMPLITUDE,
    dt: 0.005,
    layout: LAYOUT,
    dtype: DTYPE,
    retained_weight: RETAINED_WEIGHT,
    steps_per_layer: STEPS_PER_LAYER,
    layer_count: LAYER_COUNT,
    layer_checkpoints: [...LAYER_CHECKPOINTS],
    continuation_horizons: [...CONTINUATION_HORIZONS],
    capture_sha256: capture.hash,
    basis: EXPECTED_BASIS,
    canonical_layers: canonicalLayers,
    shuffled_layers: shuffledLayers,
  }
  await writeAtomic(SEED_PATH, seed)
  console.log(JSON.stringify({
    verdict: capture.h1.pass ? 'PASS' : 'FAIL',
    h1: capture.h1,
    layer_count: LAYER_COUNT,
    path: SEED_PATH,
  }, null, 2))
  if (!capture.h1.pass) process.exitCode = 1
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
    const seedLayers = validateSeed(seed, capture)
    const cpu = analyzeCpuCodec(capture.layers, seedLayers)
    const gpuAnalysis = validateGpu(gpu, capture.hash, capture.layers)

    const forwardBaseline = iirDirectionBaseline(capture.layers, FORWARD_ORDER)
    const reverseBaseline = iirDirectionBaseline(capture.layers, REVERSE_ORDER)
    const forwardDirection = decodeEmbedding({
      ey: base64ToFloat32(gpu.arms[0].continuation_checkpoints[0].ey_b64, VOLUME),
      ei: base64ToFloat32(gpu.arms[0].continuation_checkpoints[0].ei_b64, VOLUME),
    }, { dimension: DIMENSION, capacity: DIMENSION, gridN: GRID_N, basis: 'canonical', phi: PHI, amplitude: AMPLITUDE })
    const reverseDirection = decodeEmbedding({
      ey: base64ToFloat32(gpu.arms[1].continuation_checkpoints[0].ey_b64, VOLUME),
      ei: base64ToFloat32(gpu.arms[1].continuation_checkpoints[0].ei_b64, VOLUME),
    }, { dimension: DIMENSION, capacity: DIMENSION, gridN: GRID_N, basis: 'canonical', phi: PHI, amplitude: AMPLITUDE })
    const baselines = {
      retained_weight: RETAINED_WEIGHT,
      forward: summarizeBaseline(forwardBaseline, forwardDirection),
      reverse: summarizeBaseline(reverseBaseline, reverseDirection),
    }
    const h4Cosine = cosineSimilarity(forwardDirection, reverseDirection)
    const h4 = { cosine: h4Cosine, cosine_gap: 1 - h4Cosine }
    const receipt = buildReceipt(capture, captureBytes, seed, seedBytes, gpu, gpuBytes, cpu, gpuAnalysis, baselines, h4)
    await writeAtomic(RECEIPT_PATH, receipt)
    console.log(JSON.stringify({
      verdict: receipt.verdict,
      gates: receipt.gates,
      h4: receipt.h4_temporal_order,
      path: RECEIPT_PATH,
    }, null, 2))
    if (receipt.verdict !== 'PASS') process.exitCode = 1
  } catch (error) {
    const receipt = {
      protocol: PROTOCOL,
      version: VERSION,
      artifacts: {
        ...(captureBytes ? { capture: { path: 'CassiQwen/all-layer-hidden-state-capture.json', sha256: sha256(captureBytes) } } : {}),
        ...(seedBytes ? { seed: { path: 'CassiCosmos/_diag/cassi_qwen_all_layer_iir_seed.json', sha256: sha256(seedBytes) } } : {}),
        ...(gpuBytes ? { gpu: { path: 'CassiCosmos/_diag/cassi_qwen_all_layer_iir_gpu.json', sha256: sha256(gpuBytes) } } : {}),
      },
      gates: { H1: false, H2: false, H3: false, H4: 'INVALID' },
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
  console.error('Usage: node run-l17-all-layer-iir-observatory.mjs --prepare-field | --analyze')
  process.exitCode = 2
}
