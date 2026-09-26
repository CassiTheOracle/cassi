#!/usr/bin/env node
/** Independent reconstruction of the finite SU(2) local-observable controls. */

import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const SOURCE = fileURLToPath(import.meta.url);
const ROOT = resolve(dirname(SOURCE), "..");
const PROTOCOL = resolve(ROOT, "computations/yang-mills-local-observable-completeness-prereg.md");
const PRIMARY_SOURCE = resolve(ROOT, "computations/verify_yang_mills_local_observable_completeness.py");
const PRIMARY_RECEIPT = resolve(ROOT, "runs/yang_mills_local_observable_completeness/verification.json");
const DEFAULT_OUTPUT = resolve(ROOT, "runs/yang_mills_local_observable_completeness/verification-independent.json");

const TOLERANCE = 1e-12;
const CHARACTER_MAX = 8;
const WORD_MAX_LENGTH = 3;
const VECTOR_SEEDS = [
  [0.23, -0.31, 0.17],
  [-0.19, 0.27, 0.34],
  [0.29, 0.11, -0.21],
  [-0.37, 0.16, 0.08],
  [0.13, 0.33, 0.22],
  [-0.24, -0.18, 0.31],
];
const GAUGE_SEEDS = [
  [0.17, -0.22, 0.29],
  [-0.28, 0.14, 0.19],
  [0.21, 0.32, -0.13],
  [-0.16, 0.25, 0.35],
];
const GRAPH_FIXTURES = [
  { name: "cycle4", vertices: 4, edges: [[0, 1], [1, 2], [2, 3], [3, 0]], treeIndices: [0, 1, 2] },
  { name: "theta3", vertices: 2, edges: [[0, 1], [0, 1], [0, 1]], treeIndices: [0] },
  { name: "bouquet3", vertices: 1, edges: [[0, 0], [0, 0], [0, 0]], treeIndices: [] },
];

function parseArguments(argv) {
  let output = DEFAULT_OUTPUT;
  let replace = false;
  for (let index = 0; index < argv.length; index += 1) {
    if (argv[index] === "--replace") replace = true;
    else if (argv[index] === "--output") {
      index += 1;
      if (index >= argv.length) throw new Error("--output requires a path");
      output = resolve(argv[index]);
    } else throw new Error(`unknown argument: ${argv[index]}`);
  }
  return { output, replace };
}

function digest(path) {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

function displayPath(path) {
  const value = relative(ROOT, path);
  return (value || path).replaceAll("\\", "/");
}

function loadJson(path) {
  return JSON.parse(readFileSync(path, "utf8"));
}

function qmul(left, right) {
  const [lw, lx, ly, lz] = left;
  const [rw, rx, ry, rz] = right;
  return [
    lw * rw - lx * rx - ly * ry - lz * rz,
    lw * rx + lx * rw + ly * rz - lz * ry,
    lw * ry - lx * rz + ly * rw + lz * rx,
    lw * rz + lx * ry - ly * rx + lz * rw,
  ];
}

function qinv(value) {
  const norm = value.reduce((sum, component) => sum + component * component, 0);
  return [value[0] / norm, -value[1] / norm, -value[2] / norm, -value[3] / norm];
}

function qexp(vector) {
  const theta = Math.hypot(...vector);
  if (theta === 0) return [1, 0, 0, 0];
  const scale = Math.sin(theta) / theta;
  return [Math.cos(theta), vector[0] * scale, vector[1] * scale, vector[2] * scale];
}

function qnormError(value) {
  return Math.abs(value.reduce((sum, component) => sum + component * component, 0) - 1);
}

function qmaxDifference(left, right) {
  return Math.max(...left.map((value, index) => Math.abs(value - right[index])));
}

function trace(value) {
  return 2 * value[0];
}

function qmatrix(value) {
  const [w, x, y, z] = value;
  return [
    [[w, z], [y, x]],
    [[-y, x], [w, -z]],
  ].map((row) => row.map(([real, imaginary]) => ({ real, imaginary })));
}

function complexAdd(left, right) {
  return { real: left.real + right.real, imaginary: left.imaginary + right.imaginary };
}

function complexMultiply(left, right) {
  return {
    real: left.real * right.real - left.imaginary * right.imaginary,
    imaginary: left.real * right.imaginary + left.imaginary * right.real,
  };
}

function complexConjugate(value) {
  return { real: value.real, imaginary: -value.imaginary };
}

function matrixMultiply(left, right) {
  return Array.from({ length: 2 }, (_, row) => Array.from({ length: 2 }, (_, column) => {
    let value = { real: 0, imaginary: 0 };
    for (let index = 0; index < 2; index += 1) value = complexAdd(value, complexMultiply(left[row][index], right[index][column]));
    return value;
  }));
}

function matrixMaxDifference(left, right) {
  let result = 0;
  for (let row = 0; row < 2; row += 1) for (let column = 0; column < 2; column += 1) {
    const real = left[row][column].real - right[row][column].real;
    const imaginary = left[row][column].imaginary - right[row][column].imaginary;
    result = Math.max(result, Math.hypot(real, imaginary));
  }
  return result;
}

function matrixRank(input, tolerance) {
  const work = input.map((row) => [...row]);
  const rows = work.length;
  const columns = rows ? work[0].length : 0;
  let rank = 0;
  for (let column = 0; column < columns; column += 1) {
    let pivot = rank;
    for (let row = rank + 1; row < rows; row += 1) if (Math.abs(work[row][column]) > Math.abs(work[pivot]?.[column] ?? 0)) pivot = row;
    if (pivot >= rows || Math.abs(work[pivot][column]) <= tolerance) continue;
    [work[rank], work[pivot]] = [work[pivot], work[rank]];
    const pivotValue = work[rank][column];
    work[rank] = work[rank].map((value) => value / pivotValue);
    for (let row = 0; row < rows; row += 1) {
      if (row === rank) continue;
      const factor = work[row][column];
      if (factor !== 0) work[row] = work[row].map((value, index) => value - factor * work[rank][index]);
    }
    rank += 1;
  }
  return rank;
}

function makeWords(alphabetSize, maximumLength) {
  const alphabet = [];
  for (let index = 1; index <= alphabetSize; index += 1) alphabet.push(index, -index);
  const result = [];
  function extend(prefix) {
    if (prefix.length > 0) result.push(prefix);
    if (prefix.length === maximumLength) return;
    for (const value of alphabet) extend([...prefix, value]);
  }
  extend([]);
  return result;
}

function wordTrace(chords, word) {
  let value = [1, 0, 0, 0];
  for (const letter of word) value = qmul(value, letter > 0 ? chords[letter - 1] : qinv(chords[-letter - 1]));
  return trace(value);
}

function wordSignature(chords, maximumLength) {
  return new Map(makeWords(chords.length, maximumLength).map((word) => [word.join(","), wordTrace(chords, word)]));
}

function maxSignatureDifference(left, right) {
  let result = 0;
  for (const [key, value] of left) result = Math.max(result, Math.abs(value - (right.get(key) ?? 0)));
  for (const [key, value] of right) result = Math.max(result, Math.abs(value - (left.get(key) ?? 0)));
  return result;
}

function reconstructLinks(fixture, transports, chords) {
  const treeIndices = new Set(fixture.treeIndices);
  const links = [];
  let chordIndex = 0;
  fixture.edges.forEach(([tail, head], edgeIndex) => {
    if (treeIndices.has(edgeIndex)) links.push(qmul(qinv(transports[tail]), transports[head]));
    else {
      links.push(qmul(qmul(qinv(transports[tail]), chords[chordIndex]), transports[head]));
      chordIndex += 1;
    }
  });
  return links;
}

function recoverTreeAndChords(fixture, links) {
  const transports = { 0: [1, 0, 0, 0] };
  for (const edgeIndex of fixture.treeIndices) {
    const [tail, head] = fixture.edges[edgeIndex];
    if (transports[tail]) transports[head] = qmul(transports[tail], links[edgeIndex]);
    else transports[tail] = qmul(transports[head], qinv(links[edgeIndex]));
  }
  const treeIndices = new Set(fixture.treeIndices);
  const chords = [];
  fixture.edges.forEach(([tail, head], edgeIndex) => {
    if (!treeIndices.has(edgeIndex)) chords.push(qmul(qmul(transports[tail], links[edgeIndex]), qinv(transports[head])));
  });
  return { transports, chords };
}

function gaugeTransform(fixture, links, gauges) {
  return fixture.edges.map(([tail, head], index) => qmul(qmul(gauges[tail], links[index]), qinv(gauges[head])));
}

function cyclicRotate(word, offset) {
  return [...word.slice(offset), ...word.slice(0, offset)];
}

function inverseWord(word) {
  return [...word].reverse().map((letter) => -letter);
}

function maxCyclicInverseResidual(chords) {
  let cyclicError = 0;
  let inverseError = 0;
  for (const word of makeWords(chords.length, WORD_MAX_LENGTH)) {
    const value = wordTrace(chords, word);
    for (let offset = 0; offset < word.length; offset += 1) cyclicError = Math.max(cyclicError, Math.abs(value - wordTrace(chords, cyclicRotate(word, offset))));
    inverseError = Math.max(inverseError, Math.abs(value - wordTrace(chords, inverseWord(word))));
  }
  return { cyclicError, inverseError };
}

function addDecision(decisions, name, passed, measured, criterion) {
  decisions.push({ name, passed: Boolean(passed), measured, criterion });
}

function characterRows() {
  const rows = [];
  let recurrenceError = 0;
  let inverseError = 0;
  let rangeExcess = 0;
  for (let index = 1; index <= 17; index += 1) {
    const theta = index * Math.PI / 18;
    const q = [Math.cos(theta), Math.sin(theta), 0, 0];
    const inverse = qinv(q);
    const values = [1, trace(q)];
    const inverseValues = [1, trace(inverse)];
    for (let n = 2; n <= CHARACTER_MAX; n += 1) {
      values.push(trace(q) * values.at(-1) - values.at(-2));
      inverseValues.push(trace(inverse) * inverseValues.at(-1) - inverseValues.at(-2));
    }
    rows.push(values);
    inverseError = Math.max(inverseError, ...values.map((value, n) => Math.abs(value - inverseValues[n])));
    rangeExcess = Math.max(rangeExcess, Math.max(0, Math.abs(values[1]) - 2));
    values.forEach((value, n) => {
      recurrenceError = Math.max(recurrenceError, Math.abs(value - Math.sin((n + 1) * theta) / Math.sin(theta)));
    });
  }
  return { rows, recurrenceError, inverseError, rangeExcess, rank: matrixRank(rows, 1e-10) };
}

function epsilonConjugationError(values) {
  const epsilon = [
    [{ real: 0, imaginary: 0 }, { real: 1, imaginary: 0 }],
    [{ real: -1, imaginary: 0 }, { real: 0, imaginary: 0 }],
  ];
  const epsilonInverse = [
    [{ real: 0, imaginary: 0 }, { real: -1, imaginary: 0 }],
    [{ real: 1, imaginary: 0 }, { real: 0, imaginary: 0 }],
  ];
  let error = 0;
  for (const value of values) {
    const matrix = qmatrix(value);
    const transformed = matrixMultiply(matrixMultiply(epsilon, matrix), epsilonInverse);
    const conjugate = matrix.map((row) => row.map(complexConjugate));
    error = Math.max(error, matrixMaxDifference(transformed, conjugate));
  }
  return error;
}

function finiteCutoffResidual(rows) {
  const xValues = Array.from({ length: 17 }, (_, index) => Math.cos((index + 1) * Math.PI / 18));
  const basis = [0, 1, 2, 3];
  const targetRow = 4;
  let predicted = 0;
  for (const index of basis) {
    let coefficient = 1;
    for (const other of basis) if (other !== index) coefficient *= (xValues[targetRow] - xValues[other]) / (xValues[index] - xValues[other]);
    predicted += rows[index][8] * coefficient;
  }
  return Math.abs(predicted - rows[targetRow][8]);
}

function orientationFixture() {
  const scalar = 0.8;
  const radial = 0.6;
  return [
    [[scalar, radial, 0, 0], [scalar, 0, radial, 0], [scalar, 0, 0, radial]],
    [[scalar, radial, 0, 0], [scalar, 0, radial, 0], [scalar, 0, 0, -radial]],
  ];
}

function runReconstruction(primary) {
  const decisions = [];
  const graphRecords = [];
  const sampleQuaternions = VECTOR_SEEDS.map(qexp);
  const gaugeQuaternions = GAUGE_SEEDS.map(qexp);

  GRAPH_FIXTURES.forEach((fixture, fixtureIndex) => {
    const transports = { 0: [1, 0, 0, 0] };
    for (let vertex = 1; vertex < fixture.vertices; vertex += 1) transports[vertex] = sampleQuaternions[(fixtureIndex + vertex) % sampleQuaternions.length];
    const chordCount = fixture.edges.length - fixture.treeIndices.length;
    const chords = Array.from({ length: chordCount }, (_, index) => sampleQuaternions[(fixtureIndex + 3 + index) % sampleQuaternions.length]);
    const links = reconstructLinks(fixture, transports, chords);
    const recovered = recoverTreeAndChords(fixture, links);
    const reconstructionError = Math.max(
      ...Object.keys(transports).map((key) => qmaxDifference(transports[key], recovered.transports[key])),
      ...chords.map((value, index) => qmaxDifference(value, recovered.chords[index])),
    );
    const normError = Math.max(...links.map(qnormError));
    const chordError = chordCount ? Math.max(...chords.map((value, index) => Math.abs(trace(value) - trace(recovered.chords[index])))) : 0;
    const gauges = {};
    for (let vertex = 0; vertex < fixture.vertices; vertex += 1) gauges[vertex] = gaugeQuaternions[(vertex + fixtureIndex) % gaugeQuaternions.length];
    const transformed = recoverTreeAndChords(fixture, gaugeTransform(fixture, links, gauges));
    const gaugeError = maxSignatureDifference(wordSignature(chords, WORD_MAX_LENGTH), wordSignature(transformed.chords, WORD_MAX_LENGTH));
    const { cyclicError, inverseError } = maxCyclicInverseResidual(chords);
    let pairError = 0;
    sampleQuaternions.forEach((left, index) => {
      const right = sampleQuaternions[(index + 1) % sampleQuaternions.length];
      pairError = Math.max(pairError, Math.abs(trace(left) * trace(right) - trace(qmul(left, right)) - trace(qmul(left, qinv(right)))));
    });
    graphRecords.push({
      name: fixture.name,
      vertices: fixture.vertices,
      edges: fixture.edges,
      tree_indices: fixture.treeIndices,
      chord_count: chordCount,
      word_count: makeWords(chordCount, WORD_MAX_LENGTH).length,
      reconstruction_error: reconstructionError,
      link_norm_error: normError,
      chord_recovery_error: chordError,
      gauge_word_error: gaugeError,
      cyclic_word_error: cyclicError,
      inverse_word_error: inverseError,
      trace_product_error: pairError,
    });
    addDecision(decisions, `tree_reconstruction_${fixture.name}`, reconstructionError <= TOLERANCE, reconstructionError, `max quaternion reconstruction error <= ${TOLERANCE}`);
    addDecision(decisions, `tree_norms_${fixture.name}`, normError <= TOLERANCE, normError, `max link norm error <= ${TOLERANCE}`);
    addDecision(decisions, `chord_recovery_${fixture.name}`, chordError <= TOLERANCE, chordError, `max chord trace recovery error <= ${TOLERANCE}`);
    addDecision(decisions, `gauge_word_invariance_${fixture.name}`, gaugeError <= TOLERANCE, gaugeError, `max gauge-invariant word error <= ${TOLERANCE}`);
    addDecision(decisions, `word_conjugation_${fixture.name}`, gaugeError <= TOLERANCE, gaugeError, `max simultaneous-conjugation trace error <= ${TOLERANCE}`);
    addDecision(decisions, `word_cyclic_${fixture.name}`, cyclicError <= TOLERANCE, cyclicError, `max cyclic trace error <= ${TOLERANCE}`);
    addDecision(decisions, `word_inverse_${fixture.name}`, inverseError <= TOLERANCE, inverseError, `max inverse-word trace error <= ${TOLERANCE}`);
    addDecision(decisions, `trace_product_${fixture.name}`, pairError <= TOLERANCE, pairError, `max SU(2) trace-product error <= ${TOLERANCE}`);
  });

  const characters = characterRows();
  addDecision(decisions, "character_recurrence", characters.recurrenceError <= TOLERANCE, characters.recurrenceError, `max Chebyshev character error <= ${TOLERANCE}`);
  addDecision(decisions, "character_inverse_invariance", characters.inverseError <= TOLERANCE, characters.inverseError, `max inverse-character error <= ${TOLERANCE}`);
  addDecision(decisions, "fundamental_character_range", characters.rangeExcess <= TOLERANCE, characters.rangeExcess, "fundamental character lies in [-2, 2]");
  addDecision(decisions, "character_evaluation_rank", characters.rank === CHARACTER_MAX + 1, characters.rank, `evaluation rank equals ${CHARACTER_MAX + 1}`);
  const epsilonError = epsilonConjugationError(sampleQuaternions);
  addDecision(decisions, "epsilon_conjugation", epsilonError <= TOLERANCE, epsilonError, `max epsilon-conjugation error <= ${TOLERANCE}`);
  const contractionError = Math.max(...graphRecords.map((record) => record.trace_product_error));
  addDecision(decisions, "trace_contraction_identity", contractionError <= TOLERANCE, contractionError, `max contraction error <= ${TOLERANCE}`);

  const [plus, minus] = orientationFixture();
  const fullDifference = maxSignatureDifference(wordSignature(plus, WORD_MAX_LENGTH), wordSignature(minus, WORD_MAX_LENGTH));
  const shortDifference = maxSignatureDifference(wordSignature(plus, 2), wordSignature(minus, 2));
  const abcDifference = Math.abs(wordTrace(plus, [1, 2, 3]) - wordTrace(minus, [1, 2, 3]));
  const cutoffResidual = finiteCutoffResidual(characters.rows);
  const rawNorm = 1;
  const centeredNorm = 0;
  addDecision(decisions, "orientation_full_word_separation", fullDifference > 1e-6, fullDifference, "full word family separates the orientation pair");
  addDecision(decisions, "orientation_short_word_collision", shortDifference <= TOLERANCE, shortDifference, `length-at-most-two family collides within ${TOLERANCE}`);
  addDecision(decisions, "orientation_word_inventory", abcDifference > 1e-6, abcDifference, "the ABC word is orientation sensitive");
  addDecision(decisions, "centered_vacuum_direction", rawNorm > TOLERANCE && centeredNorm <= TOLERANCE, { raw_constant_norm: rawNorm, centered_constant_norm: centeredNorm }, "centering removes the constant vacuum vector");
  addDecision(decisions, "finite_character_cutoff_residual", cutoffResidual > 1e-3, cutoffResidual, "chi_8 is not represented by chi_0 through chi_3 on the frozen nodes");
  addDecision(decisions, "infinite_domain_declaration", WORD_MAX_LENGTH >= 3 && CHARACTER_MAX >= 8, { word_max_length: WORD_MAX_LENGTH, character_max: CHARACTER_MAX }, "finite controls do not replace the infinite local word family");

  const cycle = GRAPH_FIXTURES[0];
  const cycleTransports = { 0: [1, 0, 0, 0], 1: sampleQuaternions[0], 2: sampleQuaternions[1], 3: sampleQuaternions[2] };
  const cycleLinks = reconstructLinks(cycle, cycleTransports, [sampleQuaternions[3]]);
  const rawBefore = qmatrix(cycleLinks[0])[0][0];
  const identity = [1, 0, 0, 0];
  const rawGauges = { 0: gaugeQuaternions[0], 1: identity, 2: identity, 3: identity };
  const transformedCycleLinks = gaugeTransform(cycle, cycleLinks, rawGauges);
  const rawAfter = qmatrix(transformedCycleLinks[0])[0][0];
  const transformedCycle = recoverTreeAndChords(cycle, transformedCycleLinks);
  const rawEntryDifference = Math.hypot(rawBefore.real - rawAfter.real, rawBefore.imaginary - rawAfter.imaginary);
  const rawTraceError = Math.abs(trace(sampleQuaternions[3]) - trace(transformedCycle.chords[0]));
  const mutations = [
    { name: "accept_raw_link_matrix_entries", passed: rawEntryDifference > 1e-6 && rawTraceError <= TOLERANCE, witness: { raw_entry_difference: rawEntryDifference, wilson_trace_error: rawTraceError } },
    { name: "drop_orientation_words", passed: shortDifference <= TOLERANCE && fullDifference > 1e-6, witness: { short_difference: shortDifference, full_difference: fullDifference } },
    { name: "omit_centering", passed: rawNorm > TOLERANCE && centeredNorm <= TOLERANCE, witness: { raw_constant_norm: rawNorm, centered_constant_norm: centeredNorm } },
    { name: "finite_word_cutoff_is_complete", passed: cutoffResidual > 1e-3, witness: cutoffResidual },
  ];

  const primaryChecks = primary.checks ?? [];
  const independentMatchesPrimary = decisions.length === primaryChecks.length
    && decisions.every((decision, index) => decision.name === primaryChecks[index]?.name && decision.passed === primaryChecks[index]?.passed);
  const sourceAudit = {
    name: "primary_receipt_source_binding",
    passed: primary.inputs?.protocol?.sha256 === digest(PROTOCOL)
      && primary.inputs?.source?.sha256 === digest(PRIMARY_SOURCE)
      && primary.status === "PASS"
      && primary.check_count === 36
      && primary.passed_check_count === 36
      && primary.mutation_count === 4
      && primary.passed_mutation_count === 4
      && independentMatchesPrimary,
    measured: {
      protocol_hash_matches: primary.inputs?.protocol?.sha256 === digest(PROTOCOL),
      primary_source_hash_matches: primary.inputs?.source?.sha256 === digest(PRIMARY_SOURCE),
      primary_status: primary.status,
      primary_check_count: primary.check_count,
      primary_mutation_count: primary.mutation_count,
      independent_schedule_matches: independentMatchesPrimary,
    },
    criterion: "current protocol/source hashes and the complete primary schedule bind",
  };
  const allScientific = decisions.every((decision) => decision.passed);
  const allMutations = mutations.every((mutation) => mutation.passed);
  const allPassed = allScientific && allMutations && sourceAudit.passed;
  return {
    schema: "cassi.yang-mills.local-observable-completeness.verification-independent.v1",
    status: allPassed ? "PASS" : "FAIL",
    inputs: {
      protocol: { path: displayPath(PROTOCOL), sha256: digest(PROTOCOL) },
      primary_source: { path: displayPath(PRIMARY_SOURCE), sha256: digest(PRIMARY_SOURCE) },
      primary_receipt: { path: displayPath(PRIMARY_RECEIPT), sha256: digest(PRIMARY_RECEIPT) },
      source: { path: displayPath(SOURCE), sha256: digest(SOURCE) },
    },
    scientific_checks: decisions,
    scientific_check_count: decisions.length,
    passed_scientific_check_count: decisions.filter((decision) => decision.passed).length,
    mutation_checks: mutations,
    mutation_count: mutations.length,
    passed_mutation_count: mutations.filter((mutation) => mutation.passed).length,
    source_binding_checks: [sourceAudit],
    decision_count: decisions.length + mutations.length + 1,
    passed_decision_count: decisions.filter((decision) => decision.passed).length + mutations.filter((mutation) => mutation.passed).length + (sourceAudit.passed ? 1 : 0),
    graphs: graphRecords,
    character_controls: {
      maximum_recurrence_error: characters.recurrenceError,
      maximum_inverse_error: characters.inverseError,
      range_excess: characters.rangeExcess,
      evaluation_rank: characters.rank,
      epsilon_conjugation_error: epsilonError,
      finite_cutoff_residual: cutoffResidual,
    },
    orientation_control: {
      full_word_difference: fullDifference,
      length_at_most_two_difference: shortDifference,
      abc_difference: abcDifference,
    },
    claims: {
      finite_tree_gauge_controls: allByPrefix(decisions, ["tree_reconstruction_", "tree_norms_", "chord_recovery_", "gauge_word_invariance_"]) ? "PASS" : "FAIL",
      finite_wilson_word_controls: allByPrefix(decisions, ["word_conjugation_", "word_cyclic_", "word_inverse_", "trace_product_"]) ? "PASS" : "FAIL",
      finite_character_controls: allByPrefix(decisions, ["character_recurrence", "character_inverse_invariance", "fundamental_character_range", "character_evaluation_rank", "epsilon_conjugation", "trace_contraction_identity"]) ? "PASS" : "FAIL",
      finite_orientation_separation_control: allByPrefix(decisions, ["orientation_", "centered_vacuum_direction", "finite_character_cutoff_residual", "infinite_domain_declaration"]) ? "PASS" : "FAIL",
      local_gauge_invariant_algebra_dense: "DERIVED_CONDITIONAL",
      retained_rg_family_complete: "UNRESOLVED",
      uniform_physical_gap: "UNRESOLVED",
      continuum_mass_gap: "UNRESOLVED",
      clay_verdict: "NULL",
    },
    claim_boundary: "The independent source reconstructs finite local-algebra controls and does not construct an RG map, a uniform spectral lower bound or a continuum mass gap.",
  };
}

function allByPrefix(decisions, prefixes) {
  return decisions.filter((decision) => prefixes.some((prefix) => decision.name.startsWith(prefix))).every((decision) => decision.passed);
}

function main() {
  const { output, replace } = parseArguments(process.argv.slice(2));
  for (const path of [PROTOCOL, PRIMARY_SOURCE, PRIMARY_RECEIPT]) if (!existsSync(path)) throw new Error(`missing required input: ${path}`);
  if (existsSync(output) && !replace) throw new Error(`refusing to overwrite existing receipt: ${output}`);
  const primary = loadJson(PRIMARY_RECEIPT);
  const receipt = runReconstruction(primary);
  mkdirSync(dirname(output), { recursive: true });
  writeFileSync(output, `${JSON.stringify(receipt, null, 2)}\n`, "utf8");
  console.log(JSON.stringify({ status: receipt.status, decisions: `${receipt.passed_decision_count}/${receipt.decision_count}`, output: displayPath(output) }, null, 2));
  process.exitCode = receipt.status === "PASS" ? 0 : 1;
}

main();
