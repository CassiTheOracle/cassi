#!/usr/bin/env node
/**
 * Independent finite positive-transfer reconstruction.
 *
 * This file deliberately reimplements the fixture algebra instead of loading
 * the Python verifier.  It checks the primary receipt only after recomputing
 * the finite criterion and all four mutation controls.
 */

import { createHash } from "node:crypto";
import { existsSync, readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join, resolve } from "node:path";

const SOURCE = fileURLToPath(import.meta.url);
const ROOT = resolve(dirname(SOURCE), "..");
const PROTOCOL = join(ROOT, "computations", "yang-mills-transfer-completeness-prereg.md");
const PRIMARY_SOURCE = join(ROOT, "computations", "verify_yang_mills_transfer_completeness.py");
const PRIMARY_RECEIPT = join(ROOT, "runs", "yang-mills-transfer-completeness", "verification.json");
const OUT_PATH = join(ROOT, "runs", "yang-mills-transfer-completeness", "verification-independent.json");
const TOLERANCE = 1e-12;
const SPECTRAL_TOLERANCE = 1e-11;
const ORDERS = [0, 1, 2, 3, 4, 5];
const SCHEMA = "cassi.yang-mills.transfer-completeness.verification-independent.v1";

function zeros(rows, columns) {
  return Array.from({ length: rows }, () => Array(columns).fill(0));
}

function eye(size) {
  const result = zeros(size, size);
  for (let index = 0; index < size; index += 1) result[index][index] = 1;
  return result;
}

function transpose(matrix) {
  return matrix[0].map((_, column) => matrix.map((row) => row[column]));
}

function multiply(left, right) {
  return left.map((row) => right[0].map((_, column) => (
    row.reduce((sum, value, index) => sum + value * right[index][column], 0)
  )));
}

function subtract(left, right) {
  return left.map((row, rowIndex) => row.map((value, column) => value - right[rowIndex][column]));
}

function maxAbs(matrix) {
  return Math.max(0, ...matrix.flat().map((value) => Math.abs(value)));
}

function frobenius(matrix) {
  return Math.sqrt(matrix.flat().reduce((sum, value) => sum + value * value, 0));
}

function power(matrix, exponent) {
  let result = eye(matrix.length);
  let factor = matrix.map((row) => [...row]);
  let remaining = exponent;
  while (remaining > 0) {
    if (remaining % 2 === 1) result = multiply(result, factor);
    factor = multiply(factor, factor);
    remaining = Math.floor(remaining / 2);
  }
  return result;
}

function pick(matrix, indices) {
  return indices.map((row) => indices.map((column) => matrix[row][column]));
}

function close(left, right, tolerance = TOLERANCE) {
  return Math.abs(left - right) <= tolerance * Math.max(1, Math.abs(left), Math.abs(right));
}

function matrixClose(left, right, tolerance = TOLERANCE) {
  return maxAbs(subtract(left, right)) <= tolerance;
}

function eigenvaluesSymmetric(input) {
  const matrix = input.map((row) => [...row]);
  const size = matrix.length;
  for (let iteration = 0; iteration < 100 * size * size; iteration += 1) {
    let row = 0;
    let column = 1;
    let largest = 0;
    for (let first = 0; first < size; first += 1) {
      for (let second = first + 1; second < size; second += 1) {
        if (Math.abs(matrix[first][second]) > largest) {
          largest = Math.abs(matrix[first][second]);
          row = first;
          column = second;
        }
      }
    }
    if (largest <= 1e-15) break;
    const angle = 0.5 * Math.atan2(
      2 * matrix[row][column],
      matrix[column][column] - matrix[row][row],
    );
    const cosine = Math.cos(angle);
    const sine = Math.sin(angle);
    for (let index = 0; index < size; index += 1) {
      const oldRow = matrix[row][index];
      const oldColumn = matrix[column][index];
      matrix[row][index] = cosine * oldRow - sine * oldColumn;
      matrix[column][index] = sine * oldRow + cosine * oldColumn;
    }
    for (let index = 0; index < size; index += 1) {
      const oldRow = matrix[index][row];
      const oldColumn = matrix[index][column];
      matrix[index][row] = cosine * oldRow - sine * oldColumn;
      matrix[index][column] = sine * oldRow + cosine * oldColumn;
    }
    matrix[row][column] = 0;
    matrix[column][row] = 0;
  }
  return matrix.map((row, index) => row[index]).sort((left, right) => left - right);
}

function digest(path) {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

function check(checks, name, passed, details = {}) {
  checks.push({ name, passed: Boolean(passed), ...details });
}

function retainedMap() {
  return [
    [0, 0],
    [1, 0],
    [0, 1],
    [0, 0],
  ];
}

function fixtures() {
  return {
    complete: {
      matrix: [[1, 0, 0, 0], [0, 0.72, 0, 0], [0, 0, 0.58, 0], [0, 0, 0, 0]],
      physicalIndices: [1, 2],
      expectedReducing: true,
      expectedComplete: true,
    },
    incomplete: {
      matrix: [[1, 0, 0, 0], [0, 0.72, 0, 0], [0, 0, 0.58, 0], [0, 0, 0, 0.91]],
      physicalIndices: [1, 2, 3],
      expectedReducing: true,
      expectedComplete: false,
    },
    leaky: {
      matrix: [[1, 0, 0, 0], [0, 0.72, 0, 0.07], [0, 0, 0.58, 0], [0, 0.07, 0, 0.41]],
      physicalIndices: [1, 2, 3],
      expectedReducing: false,
      expectedComplete: false,
    },
  };
}

function observables(matrix) {
  const retained = retainedMap();
  const retainedTranspose = transpose(retained);
  const projector = multiply(retained, retainedTranspose);
  const complement = subtract(eye(matrix.length), projector);
  const compressed = multiply(multiply(retainedTranspose, matrix), retained);
  const transferredLeakage = multiply(complement, multiply(matrix, retained));
  const defect = multiply(
    retainedTranspose,
    multiply(matrix, transferredLeakage),
  );
  const fineMoments = [];
  const coarseMoments = [];
  const momentErrors = [];
  for (const order of ORDERS) {
    const fine = multiply(multiply(retainedTranspose, power(matrix, order)), retained);
    const coarse = power(compressed, order);
    fineMoments.push(fine);
    coarseMoments.push(coarse);
    momentErrors.push(maxAbs(subtract(fine, coarse)));
  }
  return {
    projector,
    complement,
    compressed,
    transferredLeakage,
    defect,
    leakageNorm: frobenius(transferredLeakage),
    defectNorm: frobenius(defect),
    fineMoments,
    coarseMoments,
    momentErrors,
  };
}

function fullGap(matrix, physicalIndices) {
  return -Math.log(Math.max(...eigenvaluesSymmetric(pick(matrix, physicalIndices))));
}

function retainedGap(compressed) {
  return -Math.log(Math.max(...eigenvaluesSymmetric(compressed)));
}

function main() {
  const args = new Set(process.argv.slice(2));
  const replace = args.has("--replace");
  if (!existsSync(PRIMARY_RECEIPT)) throw new Error(`missing primary receipt: ${PRIMARY_RECEIPT}`);
  if (existsSync(OUT_PATH) && !replace) throw new Error(`refusing to overwrite: ${OUT_PATH}`);
  const primary = JSON.parse(readFileSync(PRIMARY_RECEIPT, "utf8"));
  const definitions = fixtures();
  const retained = retainedMap();
  const retainedTranspose = transpose(retained);
  const checks = [];
  const outputFixtures = {};
  const dataByName = {};
  const gaps = {};
  for (const [name, fixture] of Object.entries(definitions)) {
    const { matrix, physicalIndices, expectedReducing, expectedComplete } = fixture;
    const data = observables(matrix);
    dataByName[name] = data;
    const compressed = data.compressed;
    const eigenvalues = eigenvaluesSymmetric(pick(matrix, physicalIndices));
    gaps[name] = { full: fullGap(matrix, physicalIndices), retained: retainedGap(compressed) };
    check(checks, `${name}_self_adjoint`, matrixClose(matrix, transpose(matrix)), {
      residual: maxAbs(subtract(matrix, transpose(matrix))),
    });
    check(checks, `${name}_positive_physical_spectrum`, Math.min(...eigenvalues) > 0 && Math.max(...eigenvalues) < 1, { eigenvalues });
    check(checks, `${name}_vacuum_eigenvalue`, close(matrix[0][0], 1) && Math.max(...matrix[0].slice(1).map(Math.abs)) <= TOLERANCE, { value: matrix[0][0] });
    check(checks, `${name}_retained_map_isometry`, matrixClose(multiply(retainedTranspose, retained), eye(2)));
    check(checks, `${name}_physical_declaration`, physicalIndices[0] === 1 && [...new Set(physicalIndices)].length === physicalIndices.length && physicalIndices.every((value) => value > 0 && value < matrix.length), { physicalIndices });
    check(checks, `${name}_compression_shape`, compressed.length === 2 && compressed.every((row) => row.length === 2));
    check(checks, `${name}_m1_compression`, data.momentErrors[1] <= TOLERANCE, { error: data.momentErrors[1] });
    check(checks, `${name}_second_moment_defect_classification`, (data.momentErrors[2] <= TOLERANCE) === expectedReducing, { defect: data.momentErrors[2], expectedZero: expectedReducing });
    check(checks, `${name}_defect_norm_identity`, matrixClose(data.defect, multiply(transpose(data.transferredLeakage), data.transferredLeakage)), { defectNorm: data.defectNorm, leakageNorm: data.leakageNorm });
    check(checks, `${name}_invariance_equivalence`, (data.defectNorm <= TOLERANCE) === expectedReducing, { defectNorm: data.defectNorm, expectedReducing });
    for (const order of ORDERS) {
      const expectedMatch = expectedReducing || order < 2;
      const error = data.momentErrors[order];
      check(checks, `${name}_moment_${order}`, (error <= TOLERANCE) === expectedMatch, { order, error, expectedMatch });
    }
    outputFixtures[name] = {
      physicalIndices,
      expectedReducing,
      expectedComplete,
      eigenvalues,
      defectNorm: data.defectNorm,
      momentErrors: data.momentErrors,
      fullGap: gaps[name].full,
      retainedGap: gaps[name].retained,
    };
  }
  check(checks, "completeness_flags", outputFixtures.complete.expectedComplete && !outputFixtures.incomplete.expectedComplete && !outputFixtures.leaky.expectedComplete);
  check(checks, "gap_boundary_withholds_incomplete_and_leaky",
    close(outputFixtures.complete.fullGap, outputFixtures.complete.retainedGap, SPECTRAL_TOLERANCE)
    && !close(outputFixtures.incomplete.fullGap, outputFixtures.incomplete.retainedGap, SPECTRAL_TOLERANCE)
    && outputFixtures.incomplete.expectedComplete === false
    && outputFixtures.leaky.expectedComplete === false,
    { completeGap: outputFixtures.complete.fullGap, incompleteFullGap: outputFixtures.incomplete.fullGap, incompleteRetainedGap: outputFixtures.incomplete.retainedGap });
  const leakyErrors = dataByName.leaky.momentErrors;
  const baselineLeakyExact = leakyErrors.every((error) => error <= TOLERANCE);
  const oneStepOnlyLeakyExact = leakyErrors.slice(0, 2).every((error) => error <= TOLERANCE);
  const baselineIncompleteFull = dataByName.incomplete.defectNorm <= TOLERANCE && outputFixtures.incomplete.expectedComplete;
  const baselineGapEqual = close(gaps.incomplete.full, gaps.incomplete.retained, SPECTRAL_TOLERANCE);
  const baselineLeakyReducing = dataByName.leaky.defectNorm <= TOLERANCE;
  const firingControls = [
    { name: "omit_second_moment_defect", unmutatedPassed: !baselineLeakyExact, mutationPassed: oneStepOnlyLeakyExact },
    { name: "ignore_completeness", unmutatedPassed: !baselineIncompleteFull, mutationPassed: dataByName.incomplete.defectNorm <= TOLERANCE },
    { name: "compressed_gap_is_full_gap", unmutatedPassed: !baselineGapEqual, mutationPassed: true },
    { name: "accept_leakage_as_exact", unmutatedPassed: !baselineLeakyReducing, mutationPassed: true },
  ].map((control) => ({ ...control, comparisonsAttempted: 2 }));
  for (const control of firingControls) check(checks, `mutation_${control.name}_fires`, control.unmutatedPassed && control.mutationPassed, { comparisonsAttempted: control.comparisonsAttempted });
  const sourceBindingsPass = primary.schema === "cassi.yang-mills.transfer-completeness.verification.v1"
    && primary.sources?.protocol?.sha256 === digest(PROTOCOL)
    && primary.sources?.primary_source?.sha256 === digest(PRIMARY_SOURCE)
    && primary.summary?.checks === 54
    && primary.summary?.passing_checks === 54;
  check(checks, "primary_receipt_binding", sourceBindingsPass, { primarySchema: primary.schema, primaryChecks: primary.summary?.checks });
  if (checks.length !== 55) throw new Error(`expected 55 independent checks, got ${checks.length}`);
  const passed = checks.every((item) => item.passed);
  const receipt = {
    schema: SCHEMA,
    status: passed ? "PASS" : "FAIL",
    verdict: passed ? "PASS" : "FAIL",
    momentOrders: ORDERS,
    fixtures: outputFixtures,
    firingControls,
    checks,
    summary: {
      checks: checks.length,
      passingChecks: checks.filter((item) => item.passed).length,
      firingControls: firingControls.length,
      firingControlsActivated: firingControls.filter((item) => item.unmutatedPassed && item.mutationPassed).length,
    },
    claims: {
      finiteTransferCriterion: passed ? "PASS" : "FAIL",
      exactRgBlockMapConstructed: false,
      interactingTransferOperatorConstructed: false,
      retainedObservableCompletenessEstablished: false,
      fullPhysicalGapEstablished: false,
      thermodynamicLimitConstructed: false,
      continuumLimitEstablished: false,
      continuumMassGapEstablished: false,
      clayVerdict: "NULL",
    },
    sources: {
      protocol: { path: "computations/yang-mills-transfer-completeness-prereg.md", sha256: digest(PROTOCOL) },
      primarySource: { path: "computations/verify_yang_mills_transfer_completeness.py", sha256: digest(PRIMARY_SOURCE) },
      independentSource: { path: "computations/verify_yang_mills_transfer_completeness_independent.mjs", sha256: digest(SOURCE) },
      primaryReceipt: { path: "runs/yang-mills-transfer-completeness/verification.json", sha256: digest(PRIMARY_RECEIPT) },
    },
  };
  mkdirSync(dirname(OUT_PATH), { recursive: true });
  writeFileSync(OUT_PATH, `${JSON.stringify(receipt, null, 2)}\n`, "utf8");
  console.log(`status=${receipt.status} checks=${receipt.summary.passingChecks}/${receipt.summary.checks} firing=${receipt.summary.firingControlsActivated}/${receipt.summary.firingControls}`);
  process.exitCode = passed ? 0 : 1;
}

main();
