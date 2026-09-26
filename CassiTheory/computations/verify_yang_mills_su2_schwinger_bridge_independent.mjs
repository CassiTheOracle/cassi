#!/usr/bin/env node
/* Independent reconstruction of the finite-regulator SU(2) Schwinger bridge. */

import { createHash } from "node:crypto";
import { existsSync, readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join, resolve, relative } from "node:path";
import { fileURLToPath } from "node:url";

const SOURCE = fileURLToPath(import.meta.url);
const ROOT = resolve(dirname(SOURCE), "..");
const PROTOCOL = join(ROOT, "computations", "yang-mills-su2-schwinger-prereg.md");
const PRIMARY_SOURCE = join(ROOT, "computations", "verify_yang_mills_su2_schwinger_bridge.py");
const DEFAULT_INPUT = join(ROOT, "runs", "yang_mills_su2_schwinger_bridge", "verification.json");
const DEFAULT_OUTPUT = join(ROOT, "runs", "yang_mills_su2_schwinger_bridge", "verification-independent.json");

const DOUBLED_CUTOFFS = [8, 16, 24, 32];
const G2_VALUES = [0.5, 1.0, 2.0];
const TIMES = [0.0, 0.5, 1.0, 2.0];
const DELTA_T = 0.5;
const TOLERANCE = 1.0e-9;
const EXPECTED_ROWS = DOUBLED_CUTOFFS.length * G2_VALUES.length;
const EXPECTED_PRIMARY_CHECKS = EXPECTED_ROWS * 8;

function sha256(path) {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

function matrix(n, fill = 0) {
  return Array.from({ length: n }, () => Array(n).fill(fill));
}

function identity(n) {
  const out = matrix(n);
  for (let i = 0; i < n; i += 1) out[i][i] = 1;
  return out;
}

function finiteHamiltonian(nMax, g2) {
  const size = nMax + 1;
  const h = matrix(size);
  const observable = matrix(size);
  for (let n = 0; n < size; n += 1) {
    const j = 0.5 * n;
    h[n][n] = 0.5 * g2 * j * (j + 1) + 2 / g2;
    if (n < nMax) {
      observable[n][n + 1] = 1;
      observable[n + 1][n] = 1;
      h[n][n + 1] = -1 / g2;
      h[n + 1][n] = -1 / g2;
    }
  }
  return { h, observable };
}

function jacobiEigen(input) {
  const n = input.length;
  const a = input.map((row) => row.slice());
  const vectors = identity(n);
  const maxIterations = 100 * n * n;
  for (let iteration = 0; iteration < maxIterations; iteration += 1) {
    let p = 0;
    let q = 1;
    let largest = 0;
    for (let i = 0; i < n; i += 1) {
      for (let j = i + 1; j < n; j += 1) {
        const value = Math.abs(a[i][j]);
        if (value > largest) {
          largest = value;
          p = i;
          q = j;
        }
      }
    }
    if (largest <= 1.0e-14) break;
    const app = a[p][p];
    const aqq = a[q][q];
    const apq = a[p][q];
    const angle = 0.5 * Math.atan2(2 * apq, aqq - app);
    const c = Math.cos(angle);
    const s = Math.sin(angle);
    for (let k = 0; k < n; k += 1) {
      if (k === p || k === q) continue;
      const akp = a[k][p];
      const akq = a[k][q];
      a[k][p] = c * akp - s * akq;
      a[p][k] = a[k][p];
      a[k][q] = s * akp + c * akq;
      a[q][k] = a[k][q];
    }
    a[p][p] = c * c * app - 2 * s * c * apq + s * s * aqq;
    a[q][q] = s * s * app + 2 * s * c * apq + c * c * aqq;
    a[p][q] = 0;
    a[q][p] = 0;
    for (let k = 0; k < n; k += 1) {
      const vkp = vectors[k][p];
      const vkq = vectors[k][q];
      vectors[k][p] = c * vkp - s * vkq;
      vectors[k][q] = s * vkp + c * vkq;
    }
  }
  const order = Array.from({ length: n }, (_, i) => i).sort((i, j) => a[i][i] - a[j][j]);
  const values = order.map((index) => a[index][index]);
  const sorted = matrix(n);
  for (let row = 0; row < n; row += 1) {
    for (let column = 0; column < n; column += 1) sorted[row][column] = vectors[row][order[column]];
  }
  return { values, vectors: sorted };
}

function matVec(a, v) {
  return a.map((row) => row.reduce((sum, value, i) => sum + value * v[i], 0));
}

function dot(a, b) {
  return a.reduce((sum, value, i) => sum + value * b[i], 0);
}

function maxAbs(values) {
  return Math.max(...values.map((value) => Math.abs(value)));
}

function reconstruct(nMax, g2) {
  const { h, observable } = finiteHamiltonian(nMax, g2);
  const { values, vectors } = jacobiEigen(h);
  const ground = vectors.map((row) => row[0]);
  if (ground.reduce((sum, value) => sum + value, 0) < 0) {
    for (let i = 0; i < ground.length; i += 1) ground[i] *= -1;
  }
  const transformed = matVec(observable, ground);
  const amplitudes = [];
  for (let column = 0; column < values.length; column += 1) {
    amplitudes.push(dot(vectors.map((row) => row[column]), transformed));
  }
  const gap = values[1] - values[0];
  const correlator = (time) => {
    let total = 0;
    for (let i = 1; i < values.length; i += 1) total += amplitudes[i] ** 2 * Math.exp(-(values[i] - values[0]) * time);
    return total;
  };
  const times = TIMES.map((time) => {
    const c0 = correlator(time);
    const c1 = correlator(time + DELTA_T);
    return {
      t: time,
      correlator: c0,
      next_correlator: c1,
      effective_mass: -Math.log(c1 / c0) / DELTA_T,
    };
  });
  return {
    n_max: nMax,
    g2,
    dimension: nMax + 1,
    ground_energy: values[0],
    first_excited_energy: values[1],
    spectral_gap: gap,
    min_ground_coefficient: Math.min(...ground),
    ground_coefficients: ground,
    vacuum_one_point: amplitudes[0],
    times,
  };
}

function closeEnough(a, b) {
  return Math.abs(a - b) <= TOLERANCE * Math.max(1, Math.abs(a), Math.abs(b));
}

function arrayClose(a, b) {
  return a.length === b.length && a.every((value, i) => closeEnough(value, b[i]));
}

function rowClose(expected, actual) {
  const scalarFields = [
    "n_max", "g2", "dimension", "ground_energy", "first_excited_energy",
    "spectral_gap", "min_ground_coefficient", "vacuum_one_point",
  ];
  if (!scalarFields.every((field) => closeEnough(expected[field], actual[field]))) return false;
  if (!arrayClose(expected.ground_coefficients, actual.ground_coefficients)) return false;
  if (expected.times.length !== actual.times.length) return false;
  return expected.times.every((time, i) =>
    closeEnough(time.t, actual.times[i].t)
    && closeEnough(time.correlator, actual.times[i].correlator)
    && closeEnough(time.next_correlator, actual.times[i].next_correlator)
    && closeEnough(time.effective_mass, actual.times[i].effective_mass));
}

function check(name, passed, detail = {}) {
  return { name, passed, ...detail };
}

function main() {
  const input = process.argv[process.argv.indexOf("--input") + 1] || DEFAULT_INPUT;
  const output = process.argv[process.argv.indexOf("--output") + 1] || DEFAULT_OUTPUT;
  const inputPath = resolve(input);
  const outputPath = resolve(output);
  if (!existsSync(inputPath)) throw new Error(`primary receipt not found: ${inputPath}`);
  if (existsSync(outputPath) && !process.argv.includes("--force")) throw new Error(`refusing to overwrite: ${outputPath}`);
  const primary = JSON.parse(readFileSync(inputPath, "utf8"));
  const checks = [];
  checks.push(check("primary_schema", primary.schema === "cassi.yang-mills.su2-schwinger-bridge.v1"));
  checks.push(check("primary_verdict", primary.verdict === "PASS"));
  checks.push(check("protocol_path", primary.protocol === "computations/yang-mills-su2-schwinger-prereg.md"));
  checks.push(check("protocol_hash", primary.protocol_sha256 === sha256(PROTOCOL)));
  checks.push(check("primary_source_path", primary.source === "computations/verify_yang_mills_su2_schwinger_bridge.py"));
  checks.push(check("primary_source_hash", primary.source_sha256 === sha256(PRIMARY_SOURCE)));
  checks.push(check("primary_counts", primary.summary.rows === EXPECTED_ROWS && primary.summary.checks === EXPECTED_PRIMARY_CHECKS));
  checks.push(check("primary_all_checks_pass", primary.summary.failed === 0 && primary.summary.passed === EXPECTED_PRIMARY_CHECKS));

  for (const nMax of DOUBLED_CUTOFFS) {
    for (const g2 of G2_VALUES) {
      const expected = reconstruct(nMax, g2);
      const actual = primary.rows.find((row) => row.n_max === nMax && closeEnough(row.g2, g2));
      const passed = actual !== undefined && rowClose(expected, actual);
      checks.push(check(`row_n${nMax}_g2_${String(g2).replace(".", "p")}`, passed));
    }
  }

  const passed = checks.every((item) => item.passed);
  const record = {
    schema: "cassi.yang-mills.su2-schwinger-bridge.independent.v1",
    verdict: passed ? "PASS" : "FAIL",
    classification: "FINITE_REGULATOR_SCHWINGER_BRIDGE_INDEPENDENT",
    protocol: "computations/yang-mills-su2-schwinger-prereg.md",
    protocol_sha256: sha256(PROTOCOL),
    source: relative(ROOT, SOURCE).replaceAll("\\", "/"),
    source_sha256: sha256(SOURCE),
    primary_source: "computations/verify_yang_mills_su2_schwinger_bridge.py",
    primary_source_sha256: sha256(PRIMARY_SOURCE),
    primary_receipt: relative(ROOT, inputPath).replaceAll("\\", "/"),
    primary_receipt_sha256: sha256(inputPath),
    tolerances: { comparison: TOLERANCE },
    summary: {
      checks: checks.length,
      passed: checks.filter((item) => item.passed).length,
      failed: checks.filter((item) => !item.passed).length,
      rows: EXPECTED_ROWS,
    },
    checks,
    uniformity_and_scope: [
      "Independent reconstruction covers the declared finite character-cutoff matrices and correlators.",
      "No character-cutoff, spatial-volume, thermodynamic, or continuum estimate is inferred.",
    ],
  };
  mkdirSync(dirname(outputPath), { recursive: true });
  writeFileSync(outputPath, `${JSON.stringify(record, null, 2)}\n`, "utf8");
  console.log(`${record.verdict}: ${record.summary.passed}/${record.summary.checks} independent checks`);
  process.exitCode = passed ? 0 : 1;
}

main();
