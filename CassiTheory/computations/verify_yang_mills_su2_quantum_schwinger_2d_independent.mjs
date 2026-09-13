#!/usr/bin/env node
/* Independent normalization-corrected finite SU(2) Schwinger reconstruction. */

import { createHash } from "node:crypto";
import { existsSync, readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, resolve, join } from "node:path";
import { fileURLToPath } from "node:url";

const SOURCE = fileURLToPath(import.meta.url);
const ROOT = resolve(dirname(SOURCE), "..");
const PROTOCOL = join(ROOT, "computations", "yang-mills-su2-quantum-schwinger-2d-prereg-v2.md");
const WILSON_PROTOCOL = join(ROOT, "computations", "yang-mills-su2-wilson-2d-prereg-v2.md");
const PRIMARY_SOURCE = join(ROOT, "computations", "verify_yang_mills_su2_quantum_schwinger_2d.py");
const WILSON_SOURCE = join(ROOT, "computations", "verify_yang_mills_su2_wilson_2d.py");
const PRIMARY_RECEIPT = join(ROOT, "runs", "yang_mills_su2_quantum_schwinger_2d", "verification-v2.json");
const WILSON_RECEIPT = join(ROOT, "runs", "yang_mills_su2_wilson_2d", "verification-v2.json");
const DEFAULT_OUTPUT = join(ROOT, "runs", "yang_mills_su2_quantum_schwinger_2d", "verification-independent-v2.json");

const BETA_VALUES = [1.0, 2.0, 4.0];
const SPATIAL_LENGTHS = [1, 2, 4];
const CHARACTER_CUTOFFS = [8, 16, 24, 32];
const CHANNELS = [1, 2, 3];
const TIMES = [0.0, 0.5, 1.0, 2.0, 4.0];
const DELTA_T = 0.5;
const HAAR_ORDERS = [1, 2, 3, 4, 5, 6, 7, 8];
const HAAR_MIDPOINTS = 65536;
const TOLERANCE = 1.0e-9;
const EXPECTED_ROWS = BETA_VALUES.length * SPATIAL_LENGTHS.length * CHARACTER_CUTOFFS.length;
const CHECKS_PER_ROW = 13;
const EXPECTED_PRIMARY_CHECKS = EXPECTED_ROWS * CHECKS_PER_ROW + 8;
const EXPECTED_TOP_LEVEL_CHECKS = 10;

function sha256(path) {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

function closeEnough(left, right) {
  return Math.abs(left - right) <= TOLERANCE * Math.max(1, Math.abs(left), Math.abs(right));
}

function relativeClose(left, right) {
  return Math.abs(left - right) <= TOLERANCE * Math.max(Math.abs(left), Math.abs(right), Number.MIN_VALUE);
}

function relativeError(left, right) {
  return Math.abs(left - right) / Math.max(Math.abs(left), Math.abs(right), Number.MIN_VALUE);
}

function arrayClose(left, right, relative = false) {
  return Array.isArray(left)
    && Array.isArray(right)
    && left.length === right.length
    && left.every((value, index) => (relative ? relativeClose(value, right[index]) : closeEnough(value, right[index])));
}

function check(name, passed, detail = {}) {
  return { name, passed: Boolean(passed), ...detail };
}

function factorial(n) {
  let value = 1;
  for (let i = 2; i <= n; i += 1) value *= i;
  return value;
}

function besselISeries(order, beta) {
  let term = Math.pow(beta / 2, order) / factorial(order);
  let sum = term;
  for (let q = 0; q < 10000; q += 1) {
    const ratio = (beta * beta / 4) / ((q + 1) * (q + order + 1));
    term *= ratio;
    sum += term;
    const nextRatio = (beta * beta / 4) / ((q + 2) * (q + order + 2));
    const nextTerm = Math.abs(term * nextRatio);
    const tailBound = nextTerm / (1 - nextRatio);
    const relativeTailBound = tailBound / Math.abs(sum);
    if (relativeTailBound <= 1.0e-16) {
      return { value: sum, omitted: nextTerm, tailBound, relativeTailBound };
    }
  }
  throw new Error(`Bessel series did not converge for order=${order}, beta=${beta}`);
}

const haarCache = new Map();
function haarCoefficientMidpoint(beta, n) {
  const key = `${beta}|${n}`;
  if (haarCache.has(key)) return haarCache.get(key);
  let sum = 0;
  for (let index = 0; index < HAAR_MIDPOINTS; index += 1) {
    const theta = (index + 0.5) * Math.PI / HAAR_MIDPOINTS;
    sum += Math.exp(beta * Math.cos(theta)) * Math.sin(theta) * Math.sin(n * theta);
  }
  const value = 2 * sum / HAAR_MIDPOINTS;
  haarCache.set(key, value);
  return value;
}

function characterData(beta, cutoff) {
  const dimensions = [];
  const coefficients = [];
  const reduced = [];
  const omitted = [];
  const tailBounds = [];
  const relativeTailBounds = [];
  for (let n = 1; n <= cutoff; n += 1) {
    const series = besselISeries(n, beta);
    const reducedValue = 2 * series.value / beta;
    dimensions.push(n);
    coefficients.push(n * reducedValue);
    reduced.push(reducedValue);
    omitted.push(series.omitted);
    tailBounds.push(series.tailBound);
    relativeTailBounds.push(series.relativeTailBound);
  }
  return { dimensions, coefficients, reduced, omitted, tailBounds, relativeTailBounds };
}

function zeros(rows, columns) {
  return Array.from({ length: rows }, () => Array(columns).fill(0));
}

function fusionMatrix(channel, cutoff) {
  const matrix = zeros(cutoff, cutoff);
  for (let n = 1; n <= cutoff; n += 1) {
    const first = Math.abs(channel - (n - 1));
    const last = channel + n - 1;
    for (let doubledSpin = first; doubledSpin <= last; doubledSpin += 2) {
      const m = doubledSpin + 1;
      if (m >= 1 && m <= cutoff) matrix[m - 1][n - 1] = 1;
    }
  }
  return matrix;
}

function maxAbs(values) {
  let maximum = 0;
  for (const value of values) maximum = Math.max(maximum, Math.abs(value));
  return maximum;
}

function matrixSymmetryResidual(matrix) {
  let maximum = 0;
  for (let row = 0; row < matrix.length; row += 1) {
    for (let column = 0; column < matrix.length; column += 1) {
      maximum = Math.max(maximum, Math.abs(matrix[row][column] - matrix[column][row]));
    }
  }
  return maximum;
}

function jacobiEigen(input) {
  const matrix = input.map((row) => row.slice());
  const n = matrix.length;
  const limit = Math.max(32, 64 * n * n);
  for (let iteration = 0; iteration < limit; iteration += 1) {
    let p = 0;
    let q = 1;
    let largest = n > 1 ? Math.abs(matrix[p][q]) : 0;
    for (let row = 0; row < n; row += 1) {
      for (let column = row + 1; column < n; column += 1) {
        const candidate = Math.abs(matrix[row][column]);
        if (candidate > largest) {
          largest = candidate;
          p = row;
          q = column;
        }
      }
    }
    if (largest <= 1.0e-14) break;
    const theta = 0.5 * Math.atan2(2 * matrix[p][q], matrix[q][q] - matrix[p][p]);
    const cosine = Math.cos(theta);
    const sine = Math.sin(theta);
    const app = matrix[p][p];
    const aqq = matrix[q][q];
    const apq = matrix[p][q];
    matrix[p][p] = cosine * cosine * app - 2 * sine * cosine * apq + sine * sine * aqq;
    matrix[q][q] = sine * sine * app + 2 * sine * cosine * apq + cosine * cosine * aqq;
    matrix[p][q] = 0;
    matrix[q][p] = 0;
    for (let index = 0; index < n; index += 1) {
      if (index === p || index === q) continue;
      const aip = matrix[index][p];
      const aiq = matrix[index][q];
      matrix[index][p] = cosine * aip - sine * aiq;
      matrix[p][index] = matrix[index][p];
      matrix[index][q] = sine * aip + cosine * aiq;
      matrix[q][index] = matrix[index][q];
    }
  }
  return matrix.map((row, index) => row[index]).sort((left, right) => left - right);
}

function finitePayload(value) {
  if (Array.isArray(value)) return value.every(finitePayload);
  if (value && typeof value === "object") return Object.values(value).every(finitePayload);
  if (typeof value === "number") return Number.isFinite(value);
  return true;
}

function reconstruct(beta, spatialLength, cutoff) {
  const {
    dimensions,
    coefficients,
    reduced,
    omitted,
    tailBounds,
    relativeTailBounds,
  } = characterData(beta, cutoff);
  const haarCoefficients = HAAR_ORDERS.map((n) => haarCoefficientMidpoint(beta, n));
  const haarRelativeErrors = haarCoefficients.map((value, index) => relativeError(value, coefficients[index]));
  const quotientResiduals = coefficients.map((value, index) => value / dimensions[index] - reduced[index]);
  const quotientResidual = Math.max(...quotientResiduals.map(Math.abs));
  const quotientRelativeResidual = Math.max(...quotientResiduals.map((value, index) => Math.abs(value) / Math.max(Math.abs(reduced[index]), Number.MIN_VALUE)));
  const rejectedDoubleDivision = reduced.map((value, index) => value / dimensions[index]);
  const doubleDivisionRelativeErrorN2 = Math.abs(rejectedDoubleDivision[1] - reduced[1]) / reduced[1];
  const transfer = reduced.map((value) => Math.pow(value, spatialLength));
  const transferMatrix = zeros(cutoff, cutoff);
  transfer.forEach((value, index) => {
    transferMatrix[index][index] = value;
  });
  const transferSymmetryResidual = matrixSymmetryResidual(transferMatrix);
  const energies = reduced.map((value) => spatialLength * Math.log(reduced[0] / value));
  const energyErrorBounds = reduced.map((_, index) =>
    spatialLength
      * (-Math.log1p(-relativeTailBounds[0]) - Math.log1p(-relativeTailBounds[index])),
  );
  const rowChecks = [];
  const channels = {};
  rowChecks.push(check(
    "positive_finite_coefficients_and_transfer",
    coefficients.every((value) => Number.isFinite(value) && value > 0)
      && reduced.every((value) => Number.isFinite(value) && value > 0)
      && transfer.every((value) => Number.isFinite(value) && value > 0),
    {
      maximum_omitted_bessel_term: Math.max(...omitted),
      maximum_bessel_tail_bound: Math.max(...tailBounds),
      maximum_bessel_relative_tail_bound: Math.max(...relativeTailBounds),
      maximum_energy_error_bound: Math.max(...energyErrorBounds),
    },
  ));
  rowChecks.push(check(
    "haar_character_normalization",
    Math.max(...haarRelativeErrors) <= TOLERANCE,
    { maximum_relative_error: Math.max(...haarRelativeErrors) },
  ));
  rowChecks.push(check(
    "single_convolution_quotient",
    quotientResidual <= TOLERANCE && quotientRelativeResidual <= TOLERANCE,
    { maximum_absolute_residual: quotientResidual, maximum_relative_residual: quotientRelativeResidual },
  ));
  rowChecks.push(check(
    "double_division_firing_control",
    doubleDivisionRelativeErrorN2 >= 0.5 - TOLERANCE,
    { n: 2, relative_error: doubleDivisionRelativeErrorN2 },
  ));
  rowChecks.push(check(
    "symmetric_transfer_matrix",
    transferSymmetryResidual <= TOLERANCE,
    { symmetry_residual: transferSymmetryResidual },
  ));
  const reducedDrops = reduced.slice(0, -1).map((value, index) => value - reduced[index + 1]);
  rowChecks.push(check(
    "strict_transfer_order",
    reducedDrops.every((value) => value > 0),
    { minimum_reduced_drop: Math.min(...reducedDrops) },
  ));
  rowChecks.push(check(
    "normalized_ground_and_positive_gaps",
    closeEnough(energies[0], 0) && energies.slice(1).every((value) => Number.isFinite(value) && value > 0),
    { ground_energy: energies[0], minimum_gap: Math.min(...energies.slice(1)) },
  ));

  let allObservablesSymmetric = true;
  let allVacuumOrbits = true;
  let allCorrelatorsNonnegative = true;
  let allEffectiveAndSemigroup = true;
  let allOperatorBounds = true;
  for (const channel of CHANNELS) {
    const observable = fusionMatrix(channel, cutoff);
    const symmetryResidual = matrixSymmetryResidual(observable);
    const eigenvalues = jacobiEigen(observable);
    const operatorNorm = Math.max(...eigenvalues.map((value) => Math.abs(value)));
    const vacuum = observable.map((row) => row[0]);
    const target = Array(cutoff).fill(0);
    target[channel] = 1;
    const vacuumError = maxAbs(vacuum.map((value, index) => value - target[index]));
    const spectralEnergy = energies[channel];
    const correlators = TIMES.map((time) => Math.exp(-time * spectralEnergy));
    const shiftedCorrelators = TIMES.map((time) => Math.exp(-(time + DELTA_T) * spectralEnergy));
    const effectiveMasses = correlators.map((value, index) => -(1 / DELTA_T) * Math.log(shiftedCorrelators[index] / value));
    const effectiveMassError = Math.max(...effectiveMasses.map((value) => Math.abs(value - spectralEnergy)));
    const semigroupError = Math.max(...shiftedCorrelators.map((shifted, index) => Math.abs(shifted - correlators[index] * Math.exp(-DELTA_T * spectralEnergy))));
    channels[String(channel)] = {
      allowed_entries: observable.flat().filter((value) => value !== 0).length,
      matrix_symmetry_residual: symmetryResidual,
      operator_norm: operatorNorm,
      declared_operator_bound: channel + 1,
      vacuum_target: channel + 1,
      vacuum_orbit_error: vacuumError,
      spectral_energy: spectralEnergy,
      correlators,
      shifted_correlators: shiftedCorrelators,
      effective_masses: effectiveMasses,
      effective_mass_error: effectiveMassError,
      semigroup_error: semigroupError,
    };
    allObservablesSymmetric = allObservablesSymmetric && symmetryResidual <= TOLERANCE;
    allVacuumOrbits = allVacuumOrbits && vacuumError <= TOLERANCE;
    allCorrelatorsNonnegative = allCorrelatorsNonnegative && correlators.every((value) => Number.isFinite(value) && value >= 0);
    allEffectiveAndSemigroup = allEffectiveAndSemigroup && effectiveMassError <= TOLERANCE && semigroupError <= TOLERANCE;
    allOperatorBounds = allOperatorBounds && operatorNorm <= channel + 1 + TOLERANCE;
  }
  rowChecks.push(check("symmetric_finite_fusion_observables", allObservablesSymmetric));
  rowChecks.push(check("vacuum_fusion_orbits", allVacuumOrbits));
  rowChecks.push(check("nonnegative_connected_correlators", allCorrelatorsNonnegative));
  rowChecks.push(check("effective_mass_and_semigroup_identities", allEffectiveAndSemigroup));
  rowChecks.push(check("fusion_operator_norm_bounds", allOperatorBounds));

  const row = {
    beta,
    spatial_length: spatialLength,
    character_cutoff: cutoff,
    character_dimensions: dimensions,
    character_coefficients: coefficients,
    reduced_coefficients: reduced,
    haar_orders: HAAR_ORDERS,
    haar_coefficients: haarCoefficients,
    haar_relative_errors: haarRelativeErrors,
    convolution_quotient_residual: quotientResidual,
    convolution_quotient_relative_residual: quotientRelativeResidual,
    rejected_double_division: rejectedDoubleDivision,
    double_division_relative_error_n2: doubleDivisionRelativeErrorN2,
    transfer_values: transfer,
    bessel_tail_bounds: tailBounds,
    bessel_relative_tail_bounds: relativeTailBounds,
    energy_error_bounds: energyErrorBounds,
    transfer_symmetry_residual: transferSymmetryResidual,
    energies,
    transfer_symmetric: transferSymmetryResidual <= TOLERANCE,
    channels,
    checks: rowChecks,
  };
  rowChecks.push(check("finite_complete_row_payload", finitePayload(row)));
  row.checks_passed = rowChecks.every((item) => item.passed);
  return row;
}

function rowClose(expected, actual) {
  if (actual === undefined) return false;
  if (expected.beta !== actual.beta || expected.spatial_length !== actual.spatial_length || expected.character_cutoff !== actual.character_cutoff) return false;
  for (const field of ["character_dimensions", "haar_orders"]) {
    if (JSON.stringify(expected[field]) !== JSON.stringify(actual[field])) return false;
  }
  for (const field of ["character_coefficients", "reduced_coefficients", "haar_coefficients", "rejected_double_division", "transfer_values"]) {
    if (!arrayClose(expected[field], actual[field], true)) return false;
  }
  if (!arrayClose(expected.energies, actual.energies)) return false;
  for (const field of ["convolution_quotient_residual", "convolution_quotient_relative_residual", "double_division_relative_error_n2", "transfer_symmetry_residual"]) {
    if (!closeEnough(expected[field], actual[field])) return false;
  }
  for (const channel of CHANNELS.map(String)) {
    const left = expected.channels[channel];
    const right = actual.channels[channel];
    for (const field of ["allowed_entries", "vacuum_target"]) if (left[field] !== right[field]) return false;
    for (const field of ["matrix_symmetry_residual", "operator_norm", "declared_operator_bound", "vacuum_orbit_error", "spectral_energy", "effective_mass_error", "semigroup_error"]) {
      if (!closeEnough(left[field], right[field])) return false;
    }
    for (const field of ["correlators", "shifted_correlators"]) {
      if (!arrayClose(left[field], right[field], true)) return false;
    }
    if (!arrayClose(left.effective_masses, right.effective_masses)) return false;
  }
  return true;
}

function argumentValue(flag, fallback) {
  const index = process.argv.indexOf(flag);
  return index >= 0 ? process.argv[index + 1] : fallback;
}

function main() {
  const primaryPath = resolve(argumentValue("--input", PRIMARY_RECEIPT));
  const outputPath = resolve(argumentValue("--output", DEFAULT_OUTPUT));
  if (!existsSync(PROTOCOL) || !existsSync(WILSON_PROTOCOL) || !existsSync(PRIMARY_SOURCE) || !existsSync(WILSON_SOURCE) || !existsSync(primaryPath) || !existsSync(WILSON_RECEIPT)) {
    throw new Error("required protocol, source, or primary receipt is missing");
  }
  if (existsSync(outputPath) && !process.argv.includes("--replace")) {
    throw new Error(`refusing to overwrite existing receipt: ${outputPath}`);
  }
  const primary = JSON.parse(readFileSync(primaryPath, "utf8"));
  const wilson = JSON.parse(readFileSync(WILSON_RECEIPT, "utf8"));
  const rows = [];
  let allRowsMatch = true;
  for (const beta of BETA_VALUES) {
    for (const spatialLength of SPATIAL_LENGTHS) {
      for (const cutoff of CHARACTER_CUTOFFS) {
        const reconstructed = reconstruct(beta, spatialLength, cutoff);
        const expected = primary.rows.find(
          (row) => row.beta === beta && row.spatial_length === spatialLength && row.character_cutoff === cutoff,
        );
        const matches = expected !== undefined && rowClose(expected, reconstructed) && reconstructed.checks_passed;
        allRowsMatch = allRowsMatch && matches;
        rows.push({ ...reconstructed, matches_primary: matches });
      }
    }
  }
  const checks = [
    check(
      "protocol_and_primary_source_identity",
      sha256(PROTOCOL) === primary.protocol_sha256 && sha256(PRIMARY_SOURCE) === primary.source_sha256,
    ),
    check(
      "wilson_protocol_and_source_identity",
      primary.prerequisites?.wilson_protocol_sha256 === sha256(WILSON_PROTOCOL)
        && primary.prerequisites?.wilson_source_sha256 === sha256(WILSON_SOURCE),
    ),
    check("quantum_primary_receipt_present", existsSync(primaryPath)),
    check(
      "wilson_primary_receipt_current",
      wilson.schema === "cassi.yang-mills.su2-wilson-2d.v2"
        && wilson.verdict === "PASS"
        && wilson.protocol_sha256 === sha256(WILSON_PROTOCOL)
        && wilson.source_sha256 === sha256(WILSON_SOURCE)
        && primary.prerequisites?.wilson_receipt_sha256 === sha256(WILSON_RECEIPT),
    ),
    check(
      "schedule_identity",
      JSON.stringify(primary.schedule) === JSON.stringify({
        beta_values: BETA_VALUES,
        spatial_lengths: SPATIAL_LENGTHS,
        character_cutoffs: CHARACTER_CUTOFFS,
        channels: CHANNELS,
        times: TIMES,
        delta_t: DELTA_T,
        haar_orders: HAAR_ORDERS,
      }),
    ),
    check("primary_verdict", primary.verdict === "PASS"),
    check(
      "primary_count_integrity",
      primary.summary.rows === EXPECTED_ROWS
        && primary.summary.row_checks === EXPECTED_ROWS * CHECKS_PER_ROW
        && primary.summary.top_level_checks === 8
        && primary.summary.checks === EXPECTED_PRIMARY_CHECKS
        && primary.summary.passed === EXPECTED_PRIMARY_CHECKS
        && primary.summary.failed === 0,
    ),
    check("independent_row_count", rows.length === EXPECTED_ROWS),
    check("independent_row_reconstruction", allRowsMatch && rows.every((row) => row.checks_passed)),
    check(
      "independent_payload_and_firing",
      finitePayload(rows) && rows.every((row) => row.double_division_relative_error_n2 >= 0.5 - TOLERANCE),
    ),
  ];
  const record = {
    schema: "cassi.yang-mills.su2.quantum-schwinger-2d.independent.v2",
    verdict: checks.every((item) => item.passed) ? "PASS" : "FAIL",
    classification: "NORMALIZATION_CORRECTED_FINITE_VOLUME_2D_QUANTUM_SCHWINGER_GENERATOR_INDEPENDENT",
    protocol: "computations/yang-mills-su2-quantum-schwinger-2d-prereg-v2.md",
    protocol_sha256: sha256(PROTOCOL),
    source: "computations/verify_yang_mills_su2_quantum_schwinger_2d_independent.mjs",
    source_sha256: sha256(SOURCE),
    primary_source: "computations/verify_yang_mills_su2_quantum_schwinger_2d.py",
    primary_source_sha256: sha256(PRIMARY_SOURCE),
    primary_receipt: "runs/yang_mills_su2_quantum_schwinger_2d/verification-v2.json",
    primary_receipt_sha256: sha256(primaryPath),
    wilson_protocol: "computations/yang-mills-su2-wilson-2d-prereg-v2.md",
    wilson_protocol_sha256: sha256(WILSON_PROTOCOL),
    wilson_source: "computations/verify_yang_mills_su2_wilson_2d.py",
    wilson_source_sha256: sha256(WILSON_SOURCE),
    wilson_receipt: "runs/yang_mills_su2_wilson_2d/verification-v2.json",
    wilson_receipt_sha256: sha256(WILSON_RECEIPT),
    tolerances: { independent: TOLERANCE, bessel_series_relative: 1.0e-16, haar_midpoints: HAAR_MIDPOINTS },
    summary: {
      rows: rows.length,
      checks: checks.length,
      passed: checks.filter((item) => item.passed).length,
      failed: checks.filter((item) => !item.passed).length,
      expected_top_level_checks: EXPECTED_TOP_LEVEL_CHECKS,
    },
    checks,
    rows,
    normalization: {
      character_coefficient: "C_n=2*n*I_n(beta)/beta",
      gluing_eigenvalue: "r_n=C_n/n=2*I_n(beta)/beta",
      independent_haar_method: `midpoint:${HAAR_MIDPOINTS}`,
      double_division_rejected: true,
    },
    uniformity_and_scope: [
      "The independent source reconstructs the corrected finite transfer model from a positive Bessel series and midpoint Haar integral.",
      "The current Wilson v2 primary receipt is bound as a prerequisite.",
      "The rejected double division fires in every row.",
      "No four-dimensional thermodynamic, OS, continuum or physical mass-gap estimate is inferred.",
    ],
  };
  mkdirSync(dirname(outputPath), { recursive: true });
  writeFileSync(outputPath, `${JSON.stringify(record, null, 2)}\n`, "utf8");
  console.log(JSON.stringify(record.summary));
  process.exit(record.verdict === "PASS" ? 0 : 1);
}

main();
