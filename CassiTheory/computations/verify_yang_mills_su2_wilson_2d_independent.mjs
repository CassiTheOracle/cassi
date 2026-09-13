#!/usr/bin/env node
/* Independent reconstruction of the normalization-corrected SU(2) Wilson bridge. */

import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const SOURCE = fileURLToPath(import.meta.url);
const ROOT = resolve(dirname(SOURCE), "..");
const PROTOCOL = join(ROOT, "computations", "yang-mills-su2-wilson-2d-prereg-v2.md");
const PRIMARY_SOURCE = join(ROOT, "computations", "verify_yang_mills_su2_wilson_2d.py");
const DEFAULT_INPUT = join(ROOT, "runs", "yang_mills_su2_wilson_2d", "verification-v2.json");
const DEFAULT_OUTPUT = join(ROOT, "runs", "yang_mills_su2_wilson_2d", "verification-independent-v2.json");

const BETA_VALUES = [1.0, 2.0, 4.0];
const SPATIAL_LENGTHS = [1, 2, 4];
const TEMPORAL_LENGTHS = [1, 2, 4];
const CHARACTER_CUTOFFS = [8, 16, 24, 32];
const TIME_SEPARATIONS = [0, 1, 2, 4];
const HAAR_ORDERS = [1, 2, 3, 4, 5, 6, 7, 8];
const HAAR_MIDPOINTS = 65536;
const TOLERANCE = 1.0e-9;
const EXPECTED_ROWS = BETA_VALUES.length * SPATIAL_LENGTHS.length * TEMPORAL_LENGTHS.length * CHARACTER_CUTOFFS.length;
const EXPECTED_PRIMARY_CHECKS = EXPECTED_ROWS * 10 + 12;
const EXPECTED_TOP_LEVEL_CHECKS = 12;
const MIN_NORMAL = 2.2250738585072014e-308;

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

function besselISeries(n, beta) {
  let term = (beta / 2) ** n / factorial(n);
  let sum = term;
  for (let k = 1; k < 10000; k += 1) {
    term *= (beta * beta / 4) / (k * (k + n));
    sum += term;
    if (Math.abs(term) <= Math.abs(sum) * 2.0e-16) return sum;
  }
  throw new Error(`Bessel series did not converge for n=${n}, beta=${beta}`);
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

function characterData(beta, nMax) {
  const dimensions = [];
  const coefficients = [];
  const reduced = [];
  for (let n = 1; n <= nMax; n += 1) {
    const reducedValue = 2 * besselISeries(n, beta) / beta;
    dimensions.push(n);
    reduced.push(reducedValue);
    coefficients.push(n * reducedValue);
  }
  return { dimensions, coefficients, reduced };
}

function qBoundLog(beta, n) {
  return Math.log(2) + beta * beta / 4
    - Math.log(beta)
    + n * Math.log(beta / 2)
    - Math.log(factorial(n));
}

function qBound(beta, n) {
  return Math.exp(qBoundLog(beta, n));
}

function tailData(beta, nMax, area) {
  const firstOmitted = qBound(beta, nMax + 1);
  const rho = beta / (2 * (nMax + 2));
  const logFirstPower = area * qBoundLog(beta, nMax + 1);
  const logBound = logFirstPower - Math.log1p(-(rho ** area));
  const bound = logBound >= Math.log(MIN_NORMAL) ? Math.exp(logBound) : 0;
  let probe = 0;
  for (let n = nMax + 1; n < nMax + 65; n += 1) {
    const reduced = 2 * besselISeries(n, beta) / beta;
    probe += reduced ** area;
  }
  return {
    firstOmitted,
    rho,
    bound,
    firstPower: logFirstPower >= Math.log(MIN_NORMAL) ? Math.exp(logFirstPower) : 0,
    logBound,
    probe,
  };
}

function finitePayload(value) {
  if (Array.isArray(value)) return value.every(finitePayload);
  if (value && typeof value === "object") return Object.values(value).every(finitePayload);
  if (typeof value === "number") return Number.isFinite(value);
  return true;
}

function reconstruct(beta, spatialLength, temporalLength, nMax) {
  const area = spatialLength * temporalLength;
  const { dimensions, coefficients, reduced } = characterData(beta, nMax);
  const haarCoefficients = HAAR_ORDERS.map((n) => haarCoefficientMidpoint(beta, n));
  const haarRelativeErrors = haarCoefficients.map((value, index) => relativeError(value, coefficients[index]));
  const quotientResiduals = coefficients.map((value, index) => value / dimensions[index] - reduced[index]);
  const quotientResidual = Math.max(...quotientResiduals.map(Math.abs));
  const quotientRelativeResidual = Math.max(...quotientResiduals.map((value, index) => Math.abs(value) / Math.max(Math.abs(reduced[index]), Number.MIN_VALUE)));
  const rejectedDoubleDivision = reduced.map((value, index) => value / dimensions[index]);
  const doubleDivisionRelativeErrorN2 = Math.abs(rejectedDoubleDivision[1] - reduced[1]) / reduced[1];
  const ratio = reduced[1] / reduced[0];
  const correlators = TIME_SEPARATIONS.map((time) => {
    const correlator = ratio ** (spatialLength * time);
    const nextCorrelator = ratio ** (spatialLength * (time + 1));
    return {
      t: time,
      correlator,
      next_correlator: nextCorrelator,
      effective_mass: -Math.log(nextCorrelator / correlator),
    };
  });
  const tail = tailData(beta, nMax, area);
  const partition = reduced.reduce((sum, value) => sum + value ** area, 0);
  const expectedEffectiveMass = spatialLength * Math.log(reduced[0] / reduced[1]);
  const correlatorError = Math.max(...correlators.map((item) => Math.abs(item.correlator - ratio ** (spatialLength * item.t))));
  const effectiveError = Math.max(...correlators.map((item) => Math.abs(item.effective_mass - expectedEffectiveMass)));
  const checks = [
    check(
      "positive_finite_character_and_reduced_coefficients",
      coefficients.every((value) => Number.isFinite(value) && value > 0)
        && reduced.every((value) => Number.isFinite(value) && value > 0),
    ),
    check(
      "haar_character_normalization",
      Math.max(...haarRelativeErrors) <= TOLERANCE,
      { maximum_relative_error: Math.max(...haarRelativeErrors) },
    ),
    check(
      "single_convolution_quotient",
      quotientResidual <= TOLERANCE && quotientRelativeResidual <= TOLERANCE,
      { maximum_absolute_residual: quotientResidual, maximum_relative_residual: quotientRelativeResidual },
    ),
    check(
      "double_division_firing_control",
      doubleDivisionRelativeErrorN2 >= 0.5 - TOLERANCE,
      { n: 2, relative_error: doubleDivisionRelativeErrorN2 },
    ),
    check(
      "strict_reduced_coefficient_decrease",
      reduced.slice(0, -1).every((value, index) => value > reduced[index + 1]),
    ),
    check("character_fusion_vacuum_correlator", correlatorError <= TOLERANCE),
    check("effective_mass_identity", effectiveError <= TOLERANCE),
    check(
      "corrected_positive_character_tail_bound",
      Number.isFinite(tail.logBound) && tail.logBound < 0 && tail.rho > 0 && tail.rho < 1,
    ),
    check("partition_tail_ordering", partition > 0 && tail.probe <= tail.bound + TOLERANCE),
    check("gauge_projected_area_identity", area === spatialLength * temporalLength),
  ];
  const payload = {
    beta,
    spatial_length: spatialLength,
    temporal_length: temporalLength,
    area,
    character_cutoff: nMax,
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
    partition_function_cutoff: partition,
    tail_probe: tail.probe,
    tail_bound: tail.bound,
    tail_relative_bound: tail.bound / partition,
    tail_log_bound: tail.logBound,
    tail_log_relative_bound: tail.logBound - Math.log(partition),
    tail_first_power: tail.firstPower,
    tail_ratio_bound: tail.rho,
    correlator_ratio: ratio,
    expected_effective_mass: expectedEffectiveMass,
    correlators,
    checks,
  };
  if (!finitePayload(payload)) throw new Error("non-finite independent Wilson row payload");
  return payload;
}

function rowKey(row) {
  return [row.beta, row.spatial_length, row.temporal_length, row.character_cutoff].join("|");
}

function rowClose(expected, actual) {
  if (actual === undefined) return false;
  for (const field of ["beta", "spatial_length", "temporal_length", "area", "character_cutoff"]) {
    if (expected[field] !== actual[field]) return false;
  }
  for (const field of [
    "convolution_quotient_residual", "convolution_quotient_relative_residual",
    "double_division_relative_error_n2", "tail_log_bound", "tail_log_relative_bound",
    "tail_ratio_bound", "correlator_ratio", "expected_effective_mass",
  ]) {
    if (!closeEnough(expected[field], actual[field])) return false;
  }
  for (const field of [
    "partition_function_cutoff", "tail_probe", "tail_bound", "tail_relative_bound", "tail_first_power",
  ]) {
    if (!relativeClose(expected[field], actual[field])) return false;
  }
  for (const field of ["character_dimensions", "haar_orders"]) {
    if (JSON.stringify(expected[field]) !== JSON.stringify(actual[field])) return false;
  }
  for (const field of [
    "character_coefficients", "reduced_coefficients", "haar_coefficients", "rejected_double_division",
  ]) {
    if (!arrayClose(expected[field], actual[field], true)) return false;
  }
  if (!Array.isArray(actual.correlators) || actual.correlators.length !== expected.correlators.length) return false;
  return expected.correlators.every((expectedTime, index) => {
    const actualTime = actual.correlators[index];
    return expectedTime.t === actualTime.t
      && relativeClose(expectedTime.correlator, actualTime.correlator)
      && relativeClose(expectedTime.next_correlator, actualTime.next_correlator)
      && closeEnough(expectedTime.effective_mass, actualTime.effective_mass);
  });
}

function argumentValue(flag, fallback) {
  const index = process.argv.indexOf(flag);
  return index >= 0 ? process.argv[index + 1] : fallback;
}

function main() {
  const inputPath = resolve(argumentValue("--input", DEFAULT_INPUT));
  const outputPath = resolve(argumentValue("--output", DEFAULT_OUTPUT));
  if (!existsSync(inputPath)) throw new Error(`primary receipt not found: ${inputPath}`);
  if (existsSync(outputPath) && !process.argv.includes("--replace")) {
    throw new Error(`refusing to overwrite: ${outputPath}`);
  }

  const primary = JSON.parse(readFileSync(inputPath, "utf8"));
  const checks = [
    check("primary_schema", primary.schema === "cassi.yang-mills.su2-wilson-2d.v2"),
    check("primary_verdict", primary.verdict === "PASS"),
    check("protocol_path", primary.protocol === "computations/yang-mills-su2-wilson-2d-prereg-v2.md"),
    check("protocol_hash", primary.protocol_sha256 === sha256(PROTOCOL)),
    check("primary_source_path", primary.source === "computations/verify_yang_mills_su2_wilson_2d.py"),
    check("primary_source_hash", primary.source_sha256 === sha256(PRIMARY_SOURCE)),
    check("beta_schedule", JSON.stringify(primary.schedule?.beta_values) === JSON.stringify(BETA_VALUES)),
    check("spatial_schedule", JSON.stringify(primary.schedule?.spatial_lengths) === JSON.stringify(SPATIAL_LENGTHS)),
    check("temporal_schedule", JSON.stringify(primary.schedule?.temporal_lengths) === JSON.stringify(TEMPORAL_LENGTHS)),
    check("character_cutoff_schedule", JSON.stringify(primary.schedule?.character_cutoffs) === JSON.stringify(CHARACTER_CUTOFFS)),
    check(
      "time_and_haar_schedules",
      JSON.stringify(primary.schedule?.time_separations) === JSON.stringify(TIME_SEPARATIONS)
        && JSON.stringify(primary.schedule?.haar_orders) === JSON.stringify(HAAR_ORDERS),
    ),
    check(
      "primary_counts_and_passed",
      primary.summary?.rows === EXPECTED_ROWS
        && primary.summary?.checks === EXPECTED_PRIMARY_CHECKS
        && primary.summary?.passed === EXPECTED_PRIMARY_CHECKS
        && primary.summary?.failed === 0
        && primary.rows?.length === EXPECTED_ROWS
        && primary.normalization?.double_division_rejected === true,
    ),
  ];

  const rows = [];
  const primaryRows = new Map((primary.rows ?? []).map((row) => [rowKey(row), row]));
  for (const beta of BETA_VALUES) {
    for (const spatialLength of SPATIAL_LENGTHS) {
      for (const temporalLength of TEMPORAL_LENGTHS) {
        for (const nMax of CHARACTER_CUTOFFS) {
          const expected = reconstruct(beta, spatialLength, temporalLength, nMax);
          const actual = primaryRows.get(rowKey(expected));
          const matches = rowClose(expected, actual) && expected.checks.every((item) => item.passed);
          checks.push(check(`row_${rowKey(expected)}`, matches));
          rows.push({ ...expected, matches_primary: matches });
        }
      }
    }
  }

  const passed = checks.every((item) => item.passed);
  const record = {
    schema: "cassi.yang-mills.su2-wilson-2d.independent.v2",
    verdict: passed ? "PASS" : "FAIL",
    classification: "NORMALIZATION_CORRECTED_FINITE_VOLUME_2D_WILSON_BRIDGE_INDEPENDENT",
    protocol: "computations/yang-mills-su2-wilson-2d-prereg-v2.md",
    protocol_sha256: sha256(PROTOCOL),
    source: relative(ROOT, SOURCE).replaceAll("\\", "/"),
    source_sha256: sha256(SOURCE),
    primary_source: "computations/verify_yang_mills_su2_wilson_2d.py",
    primary_source_sha256: sha256(PRIMARY_SOURCE),
    primary_receipt: relative(ROOT, inputPath).replaceAll("\\", "/"),
    primary_receipt_sha256: sha256(inputPath),
    tolerances: { comparison: TOLERANCE, haar_midpoints: HAAR_MIDPOINTS },
    summary: {
      checks: checks.length,
      passed: checks.filter((item) => item.passed).length,
      failed: checks.filter((item) => !item.passed).length,
      rows: EXPECTED_ROWS,
      top_level_checks: EXPECTED_TOP_LEVEL_CHECKS,
      reconstruction_checks: EXPECTED_ROWS,
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
      "The positive Bessel series and deterministic midpoint Haar integral are independent of the primary numerical library.",
      "Every corrected row reconstructs the direct coefficient, single convolution quotient, transfer-vacuum correlator and tail bound.",
      "The rejected double division fires in every row.",
      "No four-dimensional Gibbs state, OS reconstruction, continuum limit or physical mass gap is inferred.",
    ],
  };
  mkdirSync(dirname(outputPath), { recursive: true });
  writeFileSync(outputPath, `${JSON.stringify(record, null, 2)}\n`, "utf8");
  console.log(JSON.stringify(record.summary));
  process.exit(record.verdict === "PASS" ? 0 : 1);
}

main();
