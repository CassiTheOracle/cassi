#!/usr/bin/env node

import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const SOURCE = fileURLToPath(import.meta.url);
const COMPUTATIONS = dirname(SOURCE);
const ROOT = dirname(COMPUTATIONS);
const PROTOCOL = join(COMPUTATIONS, "yang-mills-su2-transport-expansion-prereg.md");
const PRIMARY_SOURCE = join(COMPUTATIONS, "verify_yang_mills_su2_transport_expansion.py");
const PRIMARY_RECEIPT = join(ROOT, "runs", "yang_mills_su2_transport_expansion", "verification.json");
const OUTPUT = join(ROOT, "runs", "yang_mills_su2_transport_expansion", "verification-independent.json");
const TOLERANCE = 1.0e-10;
const KAPPAS = [0.5, 1, 2, 4];
const BOUNDARIES = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 2]];
const TANGENTS = [[1, 0, 0], [0, 1, 0], [0, 0, 1]];
const ZERO_EXPONENT = "0,0,0";

function sha256(path) {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

function relativePath(path) {
  return relative(ROOT, path).replaceAll("\\", "/");
}

function finite(value) {
  return typeof value === "number" && Number.isFinite(value);
}

function scalarError(actual, expected) {
  return Math.abs(actual - expected);
}

function exponentKey(exponent) {
  return exponent.join(",");
}

function parseExponent(key) {
  return key.split(",").map(Number);
}

function constant(value) {
  return Math.abs(value) < 1.0e-13 ? new Map() : new Map([[ZERO_EXPONENT, value]]);
}

function variable(index) {
  const exponent = [0, 0, 0];
  exponent[index] = 1;
  return new Map([[exponentKey(exponent), 1]]);
}

function add(...polynomials) {
  const result = new Map();
  for (const polynomial of polynomials) {
    for (const [key, value] of polynomial) {
      const next = (result.get(key) ?? 0) + value;
      if (Math.abs(next) < 1.0e-13) result.delete(key);
      else result.set(key, next);
    }
  }
  return result;
}

function scale(factor, polynomial) {
  const result = new Map();
  for (const [key, value] of polynomial) {
    const next = factor * value;
    if (Math.abs(next) >= 1.0e-13) result.set(key, next);
  }
  return result;
}

function multiply(left, right) {
  const result = new Map();
  for (const [leftKey, leftValue] of left) {
    for (const [rightKey, rightValue] of right) {
      const leftExponent = parseExponent(leftKey);
      const rightExponent = parseExponent(rightKey);
      const exponent = leftExponent.map((value, index) => value + rightExponent[index]);
      const key = exponentKey(exponent);
      const next = (result.get(key) ?? 0) + leftValue * rightValue;
      if (Math.abs(next) < 1.0e-13) result.delete(key);
      else result.set(key, next);
    }
  }
  return result;
}

function derivative(polynomial, index) {
  const result = new Map();
  for (const [key, value] of polynomial) {
    const exponent = parseExponent(key);
    if (exponent[index] === 0) continue;
    const coefficient = value * exponent[index];
    exponent[index] -= 1;
    const reducedKey = exponentKey(exponent);
    result.set(reducedKey, (result.get(reducedKey) ?? 0) + coefficient);
  }
  return result;
}

function gradient(polynomial) {
  return [0, 1, 2].map((index) => derivative(polynomial, index));
}

function laplacian(polynomial) {
  return add(...[0, 1, 2].map((index) => derivative(derivative(polynomial, index), index)));
}

function gaussianMoment(power, variance) {
  if (power % 2 === 1) return 0;
  let result = 1;
  for (let order = 1; order <= power / 2; order += 1) result *= (2 * order - 1) * variance;
  return result;
}

function expectation(polynomial, variance) {
  let result = 0;
  for (const [key, value] of polynomial) {
    const exponent = parseExponent(key);
    result += value
      * gaussianMoment(exponent[0], variance)
      * gaussianMoment(exponent[1], variance)
      * gaussianMoment(exponent[2], variance);
  }
  return result;
}

function dot(left, right) {
  return add(...left.map((value, index) => multiply(value, right[index])));
}

function normSquared(vector) {
  return dot(vector, vector);
}
function numericDot(left, right) {
  return left.reduce((sum, value, index) => sum + value * right[index], 0);
}

function numericNormSquared(vector) {
  return numericDot(vector, vector);
}

function aTerm(q, r) {
  const qSquared = q.reduce((sum, value) => sum + value * value, 0);
  const rSquared = normSquared(r);
  const qDotR = add(...r.map((coordinate, index) => scale(q[index], coordinate)));
  return add(
    constant((qSquared * qSquared) / 384),
    scale(1 / 384, multiply(rSquared, rSquared)),
    scale(qSquared / 64, rSquared),
    scale(1 / 96, multiply(qDotR, add(constant(qSquared), rSquared))),
  );
}

function l0(polynomial, kappa) {
  let result = scale(-1, laplacian(polynomial));
  for (let index = 0; index < 3; index += 1) {
    result = add(result, scale(kappa / 2, multiply(variable(index), derivative(polynomial, index))));
  }
  return result;
}

function buildBasis() {
  const result = [];
  for (let first = 0; first <= 3; first += 1) {
    for (let second = 0; second <= 3 - first; second += 1) {
      for (let third = 0; third <= 3 - first - second; third += 1) {
        const exponent = [first, second, third];
        if (exponent.some((value) => value !== 0)) result.push(exponent);
      }
    }
  }
  return result;
}

const BASIS = buildBasis();
const BASIS_INDEX = new Map(BASIS.map((exponent, index) => [exponentKey(exponent), index]));

function monomial(exponent) {
  return new Map([[exponentKey(exponent), 1]]);
}

function solveLinear(input, right) {
  const matrix = input.map((row, index) => [...row, right[index]]);
  const size = input.length;
  for (let column = 0; column < size; column += 1) {
    let pivot = column;
    for (let row = column + 1; row < size; row += 1) {
      if (Math.abs(matrix[row][column]) > Math.abs(matrix[pivot][column])) pivot = row;
    }
    if (Math.abs(matrix[pivot][column]) < 1.0e-12) throw new Error(`singular Poisson matrix at column ${column}`);
    [matrix[pivot], matrix[column]] = [matrix[column], matrix[pivot]];
    const divisor = matrix[column][column];
    for (let index = column; index <= size; index += 1) matrix[column][index] /= divisor;
    for (let row = 0; row < size; row += 1) {
      if (row === column) continue;
      const factor = matrix[row][column];
      if (Math.abs(factor) < 1.0e-14) continue;
      for (let index = column; index <= size; index += 1) matrix[row][index] -= factor * matrix[column][index];
    }
  }
  return matrix.map((row) => row[size]);
}

function invertL0(rhs, kappa) {
  const variance = 2 / kappa;
  const rhsMean = expectation(rhs, variance);
  if (Math.abs(rhsMean) > 1.0e-9) throw new Error(`non-centered Poisson RHS: ${rhsMean}`);
  const matrix = BASIS.map(() => BASIS.map(() => 0));
  BASIS.forEach((exponent, column) => {
    const image = l0(monomial(exponent), kappa);
    for (const [key, value] of image) {
      const row = BASIS_INDEX.get(key);
      if (row !== undefined) matrix[row][column] = value;
    }
  });
  const vector = BASIS.map((exponent) => rhs.get(exponentKey(exponent)) ?? 0);
  const coefficients = solveLinear(matrix, vector);
  const solution = new Map();
  BASIS.forEach((exponent, index) => {
    if (Math.abs(coefficients[index]) >= 1.0e-12) solution.set(exponentKey(exponent), coefficients[index]);
  });
  solution.set(ZERO_EXPONENT, -expectation(solution, variance));
  if (Math.abs(expectation(solution, variance)) > 1.0e-10) throw new Error("Poisson solution was not centered");
  const residual = add(l0(solution, kappa), scale(-1, rhs));
  const residualError = Math.max(0, ...Array.from(residual.values()).map((value) => Math.abs(value)));
  if (residualError > 1.0e-9) throw new Error(`Poisson residual ${residualError}`);
  return solution;
}

function scalarPart(polynomial) {
  return polynomial.get(ZERO_EXPONENT) ?? 0;
}

function computeRow(kappa, z, xi) {
  const variance = 2 / kappa;
  const r = [0, 1, 2].map((index) => add(variable(index), constant(-z[index] / 2)));
  const rSquared = normSquared(r);
  const phi = add(scale(kappa, add(aTerm([0, 0, 0], r), aTerm(z, r))), scale(-1 / 12, rSquared));
  const scoreFirst = [];
  for (let index = 0; index < 3; index += 1) {
    const derivativeAction = scale(-kappa / 96, multiply(r[index], rSquared));
    const leadingAction = scale(kappa / 4, r[index]);
    const covariance = expectation(multiply(leadingAction, phi), variance)
      - expectation(leadingAction, variance) * expectation(phi, variance);
    scoreFirst.push(add(scale(-1, derivativeAction), constant(expectation(derivativeAction, variance) + covariance)));
  }
  const w0 = add(...xi.map((value, index) => scale(-value / 2, variable(index))));
  const gradW0 = gradient(w0);
  const gradPhi = gradient(phi);
  const metric = [0, 1, 2].map((i) => [0, 1, 2].map((j) => scale(
    1 / 12,
    add(i === j ? rSquared : new Map(), scale(-1, multiply(r[i], r[j]))),
  )));
  const l1W = [];
  for (let j = 0; j < 3; j += 1) {
    let divergence = new Map();
    for (let i = 0; i < 3; i += 1) {
      divergence = add(divergence, derivative(metric[i][j], i), scale(-kappa / 2, multiply(variable(i), metric[i][j])));
    }
    l1W.push(add(scale(-scalarPart(gradW0[j]), gradPhi[j]), scale(-scalarPart(gradW0[j]), divergence)));
  }
  const scoreProjection = add(...xi.map((value, index) => scale(value, scoreFirst[index])));
  const l1Projection = add(...xi.map((value, index) => scale(value, l1W[index])));
  const rhs = add(scoreProjection, scale(-1, l1Projection));
  const w1 = invertL0(rhs, kappa);
  const cross = 2 * expectation(dot(gradW0, gradient(w1)), variance);
  let metricCost = 0;
  for (let i = 0; i < 3; i += 1) {
    for (let j = 0; j < 3; j += 1) metricCost += scalarPart(gradW0[i]) * scalarPart(gradW0[j]) * expectation(metric[i][j], variance);
  }
  const c1 = cross + metricCost;
  const expected = -1 / (4 * kappa) + (numericNormSquared(z) - numericDot(z, xi) ** 2) / 64;
  const values = [cross, metricCost, c1, expected, 0.25];
  if (!values.every(finite)) throw new Error(`nonfinite reconstructed row ${JSON.stringify({ kappa, z, xi })}`);
  return { theta0Squared: 0.25, poisson: cross, metric: metricCost, c1, expected, error: Math.abs(c1 - expected) };
}

const primary = JSON.parse(readFileSync(PRIMARY_RECEIPT, "utf8"));
const checks = [];
function addCheck(name, pass, details = {}) {
  checks.push({ name, pass: Boolean(pass), ...details });
}

addCheck("primary_schema", primary?.schema === "cassi.yang-mills.su2-transport-expansion.v1" && primary?.verdict === "PASS", { schema: primary?.schema ?? null, verdict: primary?.verdict ?? null });
addCheck("protocol_identity", primary?.protocol === relativePath(PROTOCOL) && primary?.protocol_sha256 === sha256(PROTOCOL), { recorded: primary?.protocol_sha256 ?? null, expected: sha256(PROTOCOL) });
addCheck("primary_source_identity", primary?.source === relativePath(PRIMARY_SOURCE) && primary?.source_sha256 === sha256(PRIMARY_SOURCE), { recorded: primary?.source_sha256 ?? null, expected: sha256(PRIMARY_SOURCE) });
addCheck("primary_receipt_exists", existsSync(PRIMARY_RECEIPT), { path: relativePath(PRIMARY_RECEIPT) });
addCheck("primary_summary", primary?.summary?.rows === 48 && primary?.summary?.checks === 150 && primary?.summary?.passed === 150 && primary?.summary?.failed === 0 && primary?.summary?.max_error <= 1.0e-11, { summary: primary?.summary ?? null });
addCheck("primary_checks_all_pass", Array.isArray(primary?.checks) && primary.checks.length === 150 && primary.checks.every((item) => item?.pass === true), { count: Array.isArray(primary?.checks) ? primary.checks.length : null });
addCheck("primary_schedule", JSON.stringify(primary?.schedule?.kappas) === JSON.stringify(KAPPAS) && JSON.stringify(primary?.schedule?.boundaries) === JSON.stringify(BOUNDARIES) && JSON.stringify(primary?.schedule?.tangents) === JSON.stringify(TANGENTS), { schedule: primary?.schedule ?? null });

const rows = Array.isArray(primary?.rows) ? primary.rows : [];
let rowIndex = 0;
for (const kappa of KAPPAS) {
  for (const z of BOUNDARIES) {
    for (const xi of TANGENTS) {
      const reconstructed = computeRow(kappa, z, xi);
      const recorded = rows[rowIndex];
      const pass = recorded
        && recorded.kappa === kappa
        && JSON.stringify(recorded.z) === JSON.stringify(z)
        && JSON.stringify(recorded.xi) === JSON.stringify(xi)
        && scalarError(recorded.theta0_squared, reconstructed.theta0Squared) <= TOLERANCE
        && scalarError(recorded.poisson_contribution, reconstructed.poisson) <= TOLERANCE
        && scalarError(recorded.metric_contribution, reconstructed.metric) <= TOLERANCE
        && scalarError(recorded.c1, reconstructed.c1) <= TOLERANCE
        && scalarError(reconstructed.c1, reconstructed.expected) <= TOLERANCE
        && finite(recorded.absolute_error);
      addCheck(`row_${rowIndex}`, pass, { index: rowIndex, reconstructed, recorded: recorded ?? null });
      rowIndex += 1;
    }
  }
}
addCheck("row_count", rowIndex === 48 && rows.length === 48, { expected: 48, reconstructed: rowIndex, recorded: rows.length });

const alpha = [0, 1, 0];
const xi = [1, 0, 0];
const transverse = numericNormSquared(alpha) - numericDot(alpha, xi) ** 2;
addCheck("boundary_target_nonzero", Math.abs(transverse) > 1.0e-12, { transverse });
for (const [index, u] of [1e-2, 1e-3, 1e-4].entries()) {
  const z = alpha.map((value) => value / Math.sqrt(u));
  const expected = transverse / 64;
  let measured = Number.NaN;
  let failure = null;
  try {
    const boundary = computeRow(1, z, xi);
    measured = u * (boundary.c1 + 0.25);
  } catch (error) {
    failure = String(error);
  }
  addCheck(`boundary_scaling_${index}`, failure === null && finite(measured) && Math.abs(measured - expected) <= TOLERANCE, { kappa: 1, u, z, measured, expected, failure, chartAnnotation: "z grows as u^{-1/2}; the boundary contribution is routed through the verified c1 row" });
}

const passed = checks.every((item) => item.pass === true);
const boundaryChecks = checks.filter((item) => item.name.startsWith("boundary_scaling_") || item.name === "boundary_target_nonzero");
const boundaryOk = boundaryChecks.length === 4 && boundaryChecks.every((item) => item.pass === true);
const receipt = {
  schema: "cassi.yang-mills.su2-transport-expansion-independent.v1",
  verdict: passed ? "PASS" : "FAIL",
  protocol: relativePath(PROTOCOL),
  protocol_sha256: sha256(PROTOCOL),
  source: relativePath(SOURCE),
  source_sha256: sha256(SOURCE),
  primary_source: relativePath(PRIMARY_SOURCE),
  primary_source_sha256: sha256(PRIMARY_SOURCE),
  primary_receipt: relativePath(PRIMARY_RECEIPT),
  primary_receipt_sha256: sha256(PRIMARY_RECEIPT),
  tolerance: TOLERANCE,
  summary: { checks: checks.length, passed: checks.filter((item) => item.pass).length, failed: checks.filter((item) => !item.pass).length, reconstructed_rows: rowIndex },
  classifications: { local_chart_expansion: passed ? "SUPPORTS" : "INCONCLUSIVE", full_holonomy_boundary_uniformity: passed && boundaryOk ? "REJECT_CHART_UNIFORMITY" : "INCONCLUSIVE", exact_interacting_vacuum: "UNRESOLVED" },
  checks,
};
mkdirSync(dirname(OUTPUT), { recursive: true });
if (existsSync(OUTPUT)) throw new Error(`Refusing to overwrite ${OUTPUT}`);
writeFileSync(OUTPUT, `${JSON.stringify(receipt, null, 2)}\n`, "utf8");
console.log(JSON.stringify({ verdict: receipt.verdict, ...receipt.summary, classifications: receipt.classifications }, null, 2));
process.exitCode = passed ? 0 : 1;
