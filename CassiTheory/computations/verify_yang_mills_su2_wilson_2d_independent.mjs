#!/usr/bin/env node
/* Independent reconstruction of the finite-volume two-dimensional SU(2) Wilson bridge. */

import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const SOURCE = fileURLToPath(import.meta.url);
const ROOT = resolve(dirname(SOURCE), "..");
const PROTOCOL = join(ROOT, "computations", "yang-mills-su2-wilson-2d-prereg.md");
const PRIMARY_SOURCE = join(ROOT, "computations", "verify_yang_mills_su2_wilson_2d.py");
const DEFAULT_INPUT = join(ROOT, "runs", "yang_mills_su2_wilson_2d", "verification.json");
const DEFAULT_OUTPUT = join(ROOT, "runs", "yang_mills_su2_wilson_2d", "verification-independent.json");

const BETA_VALUES = [1.0, 2.0, 4.0];
const SPATIAL_LENGTHS = [1, 2, 4];
const TEMPORAL_LENGTHS = [1, 2, 4];
const CHARACTER_CUTOFFS = [8, 16, 24, 32];
const TIME_SEPARATIONS = [0, 1, 2, 4];
const TOLERANCE = 1.0e-9;
const EXPECTED_ROWS = BETA_VALUES.length * SPATIAL_LENGTHS.length * TEMPORAL_LENGTHS.length * CHARACTER_CUTOFFS.length;
const EXPECTED_PRIMARY_CHECKS = EXPECTED_ROWS * 8 + 12;
const EXPECTED_TOP_LEVEL_CHECKS = 12;

function sha256(path) {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

function closeEnough(left, right) {
  return Math.abs(left - right) <= TOLERANCE * Math.max(1, Math.abs(left), Math.abs(right));
}

function arrayClose(left, right) {
  return Array.isArray(left)
    && Array.isArray(right)
    && left.length === right.length
    && left.every((value, index) => closeEnough(value, right[index]));
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

function transferData(beta, nMax) {
  const coefficients = [];
  const transfer = [];
  for (let n = 1; n <= nMax; n += 1) {
    const coefficient = 2 * besselISeries(n, beta) / beta;
    coefficients.push(coefficient);
    transfer.push(coefficient / n);
  }
  return { coefficients, transfer };
}

function qBoundLog(beta, n) {
  return Math.log(2) + beta * beta / 4
    - Math.log(beta * n)
    + n * Math.log(beta / 2)
    - Math.log(factorial(n));
}

function qBound(beta, n) {
  return Math.exp(qBoundLog(beta, n));
}

function tailData(beta, nMax, area) {
  const firstOmitted = qBound(beta, nMax + 1);
  const rho = beta * (nMax + 1) / (2 * (nMax + 2) ** 2);
  const logFirstPower = area * qBoundLog(beta, nMax + 1);
  const logBound = logFirstPower - Math.log1p(-(rho ** area));
  const bound = logBound >= Math.log(Number.MIN_VALUE) ? Math.exp(logBound) : 0;
  let probe = 0;
  for (let n = nMax + 1; n < nMax + 65; n += 1) {
    const transfer = 2 * besselISeries(n, beta) / (beta * n);
    probe += transfer ** area;
  }
  return {
    firstOmitted,
    rho,
    bound,
    firstPower: logFirstPower >= Math.log(Number.MIN_VALUE) ? Math.exp(logFirstPower) : 0,
    logBound,
    probe,
  };
}

function reconstruct(beta, spatialLength, temporalLength, nMax) {
  const area = spatialLength * temporalLength;
  const { coefficients, transfer } = transferData(beta, nMax);
  const ratio = transfer[1] / transfer[0];
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
  const partition = transfer.reduce((sum, value) => sum + value ** area, 0);
  const expectedEffectiveMass = spatialLength * Math.log(transfer[0] / transfer[1]);
  return {
    beta,
    spatial_length: spatialLength,
    temporal_length: temporalLength,
    area,
    character_cutoff: nMax,
    character_coefficients: coefficients,
    transfer_eigenvalues: transfer,
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
  };
}

function rowKey(row) {
  return [row.beta, row.spatial_length, row.temporal_length, row.character_cutoff].join("|");
}

function rowClose(expected, actual) {
  if (actual === undefined) return false;
  const scalarFields = [
    "beta", "spatial_length", "temporal_length", "area", "character_cutoff",
    "partition_function_cutoff", "tail_probe", "tail_bound", "tail_relative_bound",
    "tail_log_bound", "tail_log_relative_bound", "tail_first_power", "tail_ratio_bound",
    "correlator_ratio", "expected_effective_mass",
  ];
  if (!scalarFields.every((field) => closeEnough(expected[field], actual[field]))) return false;
  if (!arrayClose(expected.character_coefficients, actual.character_coefficients)) return false;
  if (!arrayClose(expected.transfer_eigenvalues, actual.transfer_eigenvalues)) return false;
  if (!Array.isArray(actual.correlators) || actual.correlators.length !== expected.correlators.length) return false;
  return expected.correlators.every((expectedTime, index) => {
    const actualTime = actual.correlators[index];
    return expectedTime.t === actualTime.t
      && closeEnough(expectedTime.correlator, actualTime.correlator)
      && closeEnough(expectedTime.next_correlator, actualTime.next_correlator)
      && closeEnough(expectedTime.effective_mass, actualTime.effective_mass);
  });
}

function main() {
  const inputArgument = process.argv.indexOf("--input");
  const outputArgument = process.argv.indexOf("--output");
  const input = inputArgument >= 0 ? process.argv[inputArgument + 1] : DEFAULT_INPUT;
  const output = outputArgument >= 0 ? process.argv[outputArgument + 1] : DEFAULT_OUTPUT;
  const inputPath = resolve(input);
  const outputPath = resolve(output);
  if (!existsSync(inputPath)) throw new Error(`primary receipt not found: ${inputPath}`);
  if (existsSync(outputPath) && !process.argv.includes("--force")) {
    throw new Error(`refusing to overwrite: ${outputPath}`);
  }

  const primary = JSON.parse(readFileSync(inputPath, "utf8"));
  const checks = [
    check("primary_schema", primary.schema === "cassi.yang-mills.su2-wilson-2d.v1"),
    check("primary_verdict", primary.verdict === "PASS"),
    check("protocol_path", primary.protocol === "computations/yang-mills-su2-wilson-2d-prereg.md"),
    check("protocol_hash", primary.protocol_sha256 === sha256(PROTOCOL)),
    check("primary_source_path", primary.source === "computations/verify_yang_mills_su2_wilson_2d.py"),
    check("primary_source_hash", primary.source_sha256 === sha256(PRIMARY_SOURCE)),
    check("beta_schedule", JSON.stringify(primary.schedule?.beta_values) === JSON.stringify(BETA_VALUES)),
    check("spatial_schedule", JSON.stringify(primary.schedule?.spatial_lengths) === JSON.stringify(SPATIAL_LENGTHS)),
    check("temporal_schedule", JSON.stringify(primary.schedule?.temporal_lengths) === JSON.stringify(TEMPORAL_LENGTHS)),
    check("character_cutoff_schedule", JSON.stringify(primary.schedule?.character_cutoffs) === JSON.stringify(CHARACTER_CUTOFFS)),
    check("time_schedule", JSON.stringify(primary.schedule?.time_separations) === JSON.stringify(TIME_SEPARATIONS)),
    check(
      "primary_counts_and_passed",
      primary.summary?.rows === EXPECTED_ROWS
        && primary.summary?.checks === EXPECTED_PRIMARY_CHECKS
        && primary.summary?.passed === EXPECTED_PRIMARY_CHECKS
        && primary.summary?.failed === 0
        && primary.rows?.length === EXPECTED_ROWS,
    ),
  ];

  const primaryRows = new Map((primary.rows ?? []).map((row) => [rowKey(row), row]));
  for (const beta of BETA_VALUES) {
    for (const spatialLength of SPATIAL_LENGTHS) {
      for (const temporalLength of TEMPORAL_LENGTHS) {
        for (const nMax of CHARACTER_CUTOFFS) {
          const expected = reconstruct(beta, spatialLength, temporalLength, nMax);
          const actual = primaryRows.get(rowKey(expected));
          checks.push(check(`row_${rowKey(expected)}`, rowClose(expected, actual)));
        }
      }
    }
  }

  const passed = checks.every((item) => item.passed);
  const record = {
    schema: "cassi.yang-mills.su2-wilson-2d.independent.v1",
    verdict: passed ? "PASS" : "FAIL",
    classification: "FINITE_VOLUME_2D_WILSON_SCHWINGER_BRIDGE_INDEPENDENT",
    protocol: "computations/yang-mills-su2-wilson-2d-prereg.md",
    protocol_sha256: sha256(PROTOCOL),
    source: relative(ROOT, SOURCE).replaceAll("\\", "/"),
    source_sha256: sha256(SOURCE),
    primary_source: "computations/verify_yang_mills_su2_wilson_2d.py",
    primary_source_sha256: sha256(PRIMARY_SOURCE),
    primary_receipt: relative(ROOT, inputPath).replaceAll("\\", "/"),
    primary_receipt_sha256: sha256(inputPath),
    tolerances: { comparison: TOLERANCE },
    summary: {
      checks: checks.length,
      passed: checks.filter((item) => item.passed).length,
      failed: checks.filter((item) => !item.passed).length,
      rows: EXPECTED_ROWS,
      top_level_checks: EXPECTED_TOP_LEVEL_CHECKS,
      reconstruction_checks: EXPECTED_ROWS,
    },
    checks,
    uniformity_and_scope: [
      "Independent reconstruction evaluates the declared character transfer spectrum and all four correlator separations.",
      "The positive Bessel series and tail sum are implemented independently of the primary numerical library.",
      "No four-dimensional spatial-volume, thermodynamic, OS, or physical mass-gap claim is inferred.",
    ],
  };
  mkdirSync(dirname(outputPath), { recursive: true });
  writeFileSync(outputPath, `${JSON.stringify(record, null, 2)}\n`, "utf8");
  console.log(`${record.verdict}: ${record.summary.passed}/${record.summary.checks} independent checks`);
  process.exitCode = passed ? 0 : 1;
}

main();
