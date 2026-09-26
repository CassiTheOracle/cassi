#!/usr/bin/env node

import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const SOURCE = fileURLToPath(import.meta.url);
const COMPUTATIONS_DIR = dirname(SOURCE);
const ROOT = dirname(COMPUTATIONS_DIR);
const PROTOCOL = join(COMPUTATIONS_DIR, "yang-mills-transport-score-prereg.md");
const PRIMARY_SOURCE = join(COMPUTATIONS_DIR, "verify_yang_mills_transport_score.py");
const OUT_DIR = join(ROOT, "runs", "yang_mills_transport_score");
const PRIMARY_RECEIPT = join(OUT_DIR, "verification.json");
const OUT_PATH = join(OUT_DIR, "verification-independent.json");

const PRIMARY_SCHEMA = "cassi.yang-mills-transport-score.verification.v2";
const INDEPENDENT_SCHEMA = "cassi.yang-mills-transport-score.verification-independent.v2";
const MATRIX_TOLERANCE = 1.0e-10;
const ALGEBRAIC_TOLERANCE = 1.0e-11;
const COMPARISON_TOLERANCE = 1.0e-9;
const CHAIN_SIZES = [4, 8, 16, 32, 64];
const CHAIN_MASSES = [0, 0.5];
const MOMENTA = Array.from({ length: 17 }, (_, index) => -Math.PI + index * Math.PI / 8);

const relativePath = (file) => relative(ROOT, file).replaceAll("\\", "/");
const sha256 = (file) => createHash("sha256").update(readFileSync(file)).digest("hex");

function isFiniteNumber(value) {
  return typeof value === "number" && Number.isFinite(value);
}

function dot(a, b) {
  let result = 0;
  for (let index = 0; index < a.length; index += 1) result += a[index] * b[index];
  return result;
}

function zeros(rows, columns) {
  return Array.from({ length: rows }, () => Array(columns).fill(0));
}

function identity(size) {
  const result = zeros(size, size);
  for (let index = 0; index < size; index += 1) result[index][index] = 1;
  return result;
}

function cloneMatrix(matrix) {
  return matrix.map((row) => row.slice());
}

function transpose(matrix) {
  if (matrix.length === 0) return [];
  return matrix[0].map((_, column) => matrix.map((row) => row[column]));
}

function matmul(left, right) {
  const rows = left.length;
  const shared = rows === 0 ? 0 : left[0].length;
  const columns = right.length === 0 ? 0 : right[0].length;
  if (shared !== right.length) throw new Error(`matrix product dimension mismatch ${rows}x${shared} times ${right.length}x${columns}`);
  const result = zeros(rows, columns);
  for (let row = 0; row < rows; row += 1) {
    for (let pivot = 0; pivot < shared; pivot += 1) {
      const factor = left[row][pivot];
      if (factor === 0) continue;
      for (let column = 0; column < columns; column += 1) {
        result[row][column] += factor * right[pivot][column];
      }
    }
  }
  return result;
}

function addMatrices(left, right) {
  return left.map((row, i) => row.map((value, j) => value + right[i][j]));
}

function subtractMatrices(left, right) {
  return left.map((row, i) => row.map((value, j) => value - right[i][j]));
}

function scaleMatrix(factor, matrix) {
  return matrix.map((row) => row.map((value) => factor * value));
}

function selectMatrix(matrix, rows, columns) {
  return rows.map((row) => columns.map((column) => matrix[row][column]));
}

function matrixIsRectangular(matrix) {
  return Array.isArray(matrix) && matrix.every((row) => Array.isArray(row)) &&
    (matrix.length === 0 || matrix.every((row) => row.length === matrix[0].length));
}

function matrixOperatorNorm(matrix) {
  if (!matrixIsRectangular(matrix)) return Number.POSITIVE_INFINITY;
  if (matrix.length === 0 || matrix[0].length === 0) return 0;
  const gram = matmul(transpose(matrix), matrix);
  const values = symmetricJacobi(gram).values;
  return Math.sqrt(Math.max(0, values[values.length - 1] ?? 0));
}

function scalarError(actual, expected) {
  if (!isFiniteNumber(actual) || !isFiniteNumber(expected)) return Number.POSITIVE_INFINITY;
  return Math.abs(actual - expected) / Math.max(1, Math.abs(expected));
}

function matrixError(actual, expected) {
  if (!matrixIsRectangular(actual) || !matrixIsRectangular(expected)) return Number.POSITIVE_INFINITY;
  if (actual.length !== expected.length || (actual.length > 0 && actual[0].length !== expected[0].length)) {
    return Number.POSITIVE_INFINITY;
  }
  return matrixOperatorNorm(subtractMatrices(actual, expected)) / Math.max(1, matrixOperatorNorm(expected));
}

// Independent symmetric Jacobi eigensolver.  It is used for all eigenvalue and
// operator-norm calculations after the chain square root has been built from
// its explicit discrete-sine basis.
function symmetricJacobi(input) {
  if (!matrixIsRectangular(input) || input.length === 0 || input.length !== input[0].length) {
    throw new Error("Jacobi eigensolver requires a non-empty square matrix");
  }
  const size = input.length;
  const matrix = cloneMatrix(input);
  const vectors = identity(size);
  const maxIterations = Math.max(100, 100 * size * size);
  const stopping = 1.0e-14;
  for (let iteration = 0; iteration < maxIterations; iteration += 1) {
    let p = 0;
    let q = 1;
    let largest = 0;
    for (let row = 0; row < size; row += 1) {
      for (let column = row + 1; column < size; column += 1) {
        const magnitude = Math.abs(matrix[row][column]);
        if (magnitude > largest) {
          largest = magnitude;
          p = row;
          q = column;
        }
      }
    }
    if (largest <= stopping || size === 1) break;
    const app = matrix[p][p];
    const aqq = matrix[q][q];
    const apq = matrix[p][q];
    const angle = 0.5 * Math.atan2(2 * apq, aqq - app);
    const cosine = Math.cos(angle);
    const sine = Math.sin(angle);
    for (let index = 0; index < size; index += 1) {
      if (index === p || index === q) continue;
      const aip = matrix[index][p];
      const aiq = matrix[index][q];
      const newIp = cosine * aip - sine * aiq;
      const newIq = sine * aip + cosine * aiq;
      matrix[index][p] = newIp;
      matrix[p][index] = newIp;
      matrix[index][q] = newIq;
      matrix[q][index] = newIq;
    }
    matrix[p][p] = cosine * cosine * app - 2 * sine * cosine * apq + sine * sine * aqq;
    matrix[q][q] = sine * sine * app + 2 * sine * cosine * apq + cosine * cosine * aqq;
    matrix[p][q] = 0;
    matrix[q][p] = 0;
    for (let index = 0; index < size; index += 1) {
      const vip = vectors[index][p];
      const viq = vectors[index][q];
      vectors[index][p] = cosine * vip - sine * viq;
      vectors[index][q] = sine * vip + cosine * viq;
    }
  }
  const order = Array.from({ length: size }, (_, index) => index).sort((a, b) => matrix[a][a] - matrix[b][b]);
  return {
    values: order.map((index) => matrix[index][index]),
    vectors: order.map((index) => vectors.map((row) => row[index])),
  };
}

function minimumEigenvalue(matrix) {
  return symmetricJacobi(matrix).values[0];
}

// Partial-pivot Gaussian elimination is deliberately separate from the
// symmetric eigensolver and is the only route used for block inverses.
function solvePivoted(matrix, right) {
  if (!matrixIsRectangular(matrix) || matrix.length === 0 || matrix.length !== matrix[0].length) {
    throw new Error("Gaussian solve requires a non-empty square matrix");
  }
  const size = matrix.length;
  if (!Array.isArray(right) || right.length !== size) throw new Error("Gaussian right-hand side dimension mismatch");
  const augmented = matrix.map((row, index) => [...row, right[index]]);
  for (let pivot = 0; pivot < size; pivot += 1) {
    let pivotRow = pivot;
    let pivotMagnitude = Math.abs(augmented[pivot][pivot]);
    for (let row = pivot + 1; row < size; row += 1) {
      const magnitude = Math.abs(augmented[row][pivot]);
      if (magnitude > pivotMagnitude) {
        pivotMagnitude = magnitude;
        pivotRow = row;
      }
    }
    if (!(pivotMagnitude > Number.EPSILON)) throw new Error("singular matrix in pivoted Gaussian solve");
    if (pivotRow !== pivot) [augmented[pivot], augmented[pivotRow]] = [augmented[pivotRow], augmented[pivot]];
    const pivotValue = augmented[pivot][pivot];
    for (let row = pivot + 1; row < size; row += 1) {
      const factor = augmented[row][pivot] / pivotValue;
      augmented[row][pivot] = 0;
      for (let column = pivot + 1; column <= size; column += 1) {
        augmented[row][column] -= factor * augmented[pivot][column];
      }
    }
  }
  const solution = Array(size).fill(0);
  for (let row = size - 1; row >= 0; row -= 1) {
    let value = augmented[row][size];
    for (let column = row + 1; column < size; column += 1) value -= augmented[row][column] * solution[column];
    solution[row] = value / augmented[row][row];
  }
  return solution;
}

function inversePivoted(matrix) {
  const size = matrix.length;
  const result = zeros(size, size);
  for (let column = 0; column < size; column += 1) {
    const right = Array(size).fill(0);
    right[column] = 1;
    const solution = solvePivoted(matrix, right);
    for (let row = 0; row < size; row += 1) result[row][column] = solution[row];
  }
  return result;
}

function buildChainSquareRoot(size, mass) {
  const denominator = size + 1;
  const sineScale = Math.sqrt(2 / denominator);
  const eigenvalues = Array.from(
    { length: size },
    (_, mode) => mass * mass + 2 - 2 * Math.cos((mode + 1) * Math.PI / denominator),
  );
  const sine = Array.from({ length: size }, (_, coordinate) =>
    Array.from({ length: size }, (_, mode) => sineScale * Math.sin((coordinate + 1) * (mode + 1) * Math.PI / denominator)),
  );
  const root = zeros(size, size);
  for (let row = 0; row < size; row += 1) {
    for (let mode = 0; mode < size; mode += 1) {
      const weighted = sine[row][mode] * Math.sqrt(eigenvalues[mode]);
      for (let column = 0; column < size; column += 1) root[row][column] += weighted * sine[column][mode];
    }
  }
  for (let row = 0; row < size; row += 1) {
    for (let column = row + 1; column < size; column += 1) {
      const symmetric = 0.5 * (root[row][column] + root[column][row]);
      root[row][column] = symmetric;
      root[column][row] = symmetric;
    }
  }
  const operator = zeros(size, size);
  for (let row = 0; row < size; row += 1) {
    operator[row][row] = 2 + mass * mass;
    if (row > 0) operator[row][row - 1] = -1;
    if (row + 1 < size) operator[row][row + 1] = -1;
  }
  return { root, operator };
}

function recurrence(lambdaCoarse, lambdaFibre, thetaSquared) {
  const theta = Math.sqrt(Math.max(0, thetaSquared));
  const A = 1 / (2 * lambdaCoarse);
  const B = theta / lambdaCoarse;
  const D = 2 * (1 / lambdaFibre + thetaSquared / lambdaCoarse);
  const discriminant = Math.sqrt((A - D) * (A - D) + 4 * B * B);
  const CClosed = 0.5 * (A + D + discriminant);
  const CDirect = largestEigenvalue2(A, B, D);
  return { A, B, D, C_closed: CClosed, C_direct: CDirect, bound: 1 / CClosed };
}

function largestEigenvalue2(a, b, d) {
  return 0.5 * (a + d + Math.sqrt((a - d) * (a - d) + 4 * b * b));
}

function blockMetrics(precision, retained, eliminated) {
  const qVV = selectMatrix(precision, retained, retained);
  const qVR = selectMatrix(precision, retained, eliminated);
  const qRV = selectMatrix(precision, eliminated, retained);
  const qRR = selectMatrix(precision, eliminated, eliminated);
  const qRRInverse = inversePivoted(qRR);
  const transport = scaleMatrix(-1, matmul(qRRInverse, qRV));
  const qEff = subtractMatrices(qVV, matmul(qVR, matmul(qRRInverse, qRV)));
  const qEffInverse = inversePivoted(qEff);
  const fullInverse = inversePivoted(precision);
  const blockInverse = selectMatrix(fullInverse, retained, retained);
  const cross = matmul(qVR, matmul(qRRInverse, qRV));
  const thetaSquared = matrixOperatorNorm(transport) ** 2;
  const kappaSquared = 2 * matrixOperatorNorm(cross);
  const lambdaCoarse = 2 * minimumEigenvalue(qEff);
  const lambdaFibre = 2 * minimumEigenvalue(qRR);
  const schurError = matrixError(qEffInverse, blockInverse);
  const transportResidual = addMatrices(matmul(qRR, transport), qRV);
  const transportError = matrixError(transportResidual, zeros(transportResidual.length, transportResidual[0].length));
  const relaxedThetaSquared = kappaSquared / lambdaFibre;
  const comparisonFactor = thetaSquared > 0 ? relaxedThetaSquared / thetaSquared : 1;
  const hminus1 = recurrence(lambdaCoarse, lambdaFibre, thetaSquared);
  const l2 = recurrence(lambdaCoarse, lambdaFibre, relaxedThetaSquared);
  const weights = precision.map((_, index) => retained.includes(index) ? Math.sqrt(2) : Math.sqrt(0.5));
  const weighted = precision.map((row, i) => row.map((value, j) => weights[i] * value * weights[j]));
  const exactGap = 2 * minimumEigenvalue(weighted);
  return {
    retained: retained.slice(),
    eliminated: eliminated.slice(),
    lambda_c: lambdaCoarse,
    lambda_fib: lambdaFibre,
    theta: Math.sqrt(Math.max(0, thetaSquared)),
    theta_sq: thetaSquared,
    kappa_sq: kappaSquared,
    kappa_sq_over_lambda_fib: relaxedThetaSquared,
    comparison_factor: comparisonFactor,
    hminus1_recurrence: hminus1,
    l2_recurrence: l2,
    exact_anisotropic_gap: exactGap,
    schur_inverse_error: schurError,
    transport_identity_error: transportError,
    minimum_q_eff_eigenvalue: minimumEigenvalue(qEff),
    minimum_q_rr_eigenvalue: minimumEigenvalue(qRR),
  };
}

function reconstructChain(size, mass) {
  const { root, operator } = buildChainSquareRoot(size, mass);
  const retained = Array.from({ length: size / 2 }, (_, index) => 2 * index);
  const eliminated = Array.from({ length: size / 2 }, (_, index) => 2 * index + 1);
  return {
    size,
    mass,
    square_root_error: matrixError(matmul(root, root), operator),
    ...blockMetrics(root, retained, eliminated),
  };
}

const FIXTURES = [
  {
    name: "equality",
    precision: [[2, -1, 0], [-1, 2, 0], [0, 0, 2]],
    expected_theta_sq: 0.25,
    expected_relaxed_theta_sq: 0.25,
    expected_factor: 1,
  },
  {
    name: "strict",
    precision: [[4, 0, -3], [0, 1, 0], [-3, 0, 9]],
    expected_theta_sq: 1 / 9,
    expected_relaxed_theta_sq: 1,
    expected_factor: 9,
  },
];

function reconstructFixture(specification) {
  const metrics = blockMetrics(specification.precision, [0], [1, 2]);
  return { ...specification, ...metrics };
}

const MARGINS = [
  [0, 0, 0, 0],
  [0, 1, 0, 0],
  [0, 1, 0, 1.0e-6],
  [1, 3, 0, 3 / 16],
  [1, 3, 0, 0.19],
  [2, 4, 0.5, 0.175],
  [2, 4, 0.5, 0.18],
  [0.5, 3, 1, 0],
  [3, 0.5, 1, 0],
  [3, 10, 1, 0.1],
];
const MARGIN_EXPECTED = [true, true, false, true, false, true, false, false, false, true];

function reconstructMargin(index) {
  const [deltaCoarse, deltaVertical, deltaFine, thetaSquared] = MARGINS[index];
  const h = 1 / (1 + deltaCoarse);
  const v = 1 / (1 + deltaVertical);
  const target = 1 / (1 + deltaFine);
  const budget = ((target - h) * (target - v)) / (4 * h * target);
  const theta = Math.sqrt(thetaSquared);
  const CNormalizedDirect = largestEigenvalue2(h, 2 * h * theta, v + 4 * h * thetaSquared);
  const diagonalDifference = h - (v + 4 * h * thetaSquared);
  const CNormalizedClosed = 0.5 * (
    h + v + 4 * h * thetaSquared + Math.sqrt(diagonalDifference * diagonalDifference + 16 * h * h * thetaSquared)
  );
  const matrixPass = CNormalizedDirect <= target + ALGEBRAIC_TOLERANCE;
  const closedPass = h <= target + ALGEBRAIC_TOLERANCE &&
    v <= target + ALGEBRAIC_TOLERANCE && thetaSquared <= budget + ALGEBRAIC_TOLERANCE;
  return {
    index,
    delta_c: deltaCoarse,
    delta_v: deltaVertical,
    delta_f: deltaFine,
    theta_sq: thetaSquared,
    h,
    v,
    target,
    budget,
    C_normalized_direct: CNormalizedDirect,
    C_normalized_closed: CNormalizedClosed,
    matrix_pass: matrixPass,
    closed_pass: closedPass,
    expected: MARGIN_EXPECTED[index],
  };
}

function symbolValues(mass) {
  const q = (momentum) => Math.sqrt(mass * mass + 4 * Math.sin(momentum / 2) ** 2);
  const aValues = [];
  const bValues = [];
  const qEffValues = [];
  let determinantError = 0;
  for (const momentum of MOMENTA) {
    const first = q(momentum / 2);
    const second = q(momentum / 2 + Math.PI);
    const a = 0.5 * (first + second);
    const b = 0.5 * Math.abs(first - second);
    const qEff = a - b * b / a;
    aValues.push(a);
    bValues.push(b);
    qEffValues.push(qEff);
    determinantError = Math.max(determinantError, Math.abs(a * a - b * b - first * second));
  }
  const s = Math.sqrt(mass * mass + 4);
  const expectedLambda = mass === 0 ? 2 : mass + s;
  const expectedTheta = mass === 0 ? 1 : (s - mass) / (s + mass);
  const expectedQEffZero = mass === 0 ? 0 : 2 * mass * s / (mass + s);
  const zeroIndex = MOMENTA.findIndex((momentum) => momentum === 0);
  return {
    mass,
    momenta: MOMENTA.slice(),
    a_values: aValues,
    b_values: bValues,
    q_eff_values: qEffValues,
    lambda_fib_infinite: 2 * Math.min(...aValues),
    theta_infinite: Math.max(...bValues.map((value, index) => value / aValues[index])),
    q_eff_zero: qEffValues[zeroIndex],
    expected_lambda_fib_infinite: expectedLambda,
    expected_theta_infinite: expectedTheta,
    expected_q_eff_zero: expectedQEffZero,
    determinant_error: determinantError,
  };
}

function comparison(actual, expected) {
  if (isFiniteNumber(expected) || isFiniteNumber(actual)) {
    const error = scalarError(actual, expected);
    return { pass: error <= COMPARISON_TOLERANCE, error, failures: error <= COMPARISON_TOLERANCE ? [] : ["number"] };
  }
  if (Array.isArray(expected) || Array.isArray(actual)) {
    if (!Array.isArray(expected) || !Array.isArray(actual) || expected.length !== actual.length) {
      return { pass: false, error: Number.POSITIVE_INFINITY, failures: ["array shape"] };
    }
    const expectedMatrix = expected.length > 0 && expected.every((row) => Array.isArray(row));
    const actualMatrix = actual.length > 0 && actual.every((row) => Array.isArray(row));
    if (expectedMatrix || actualMatrix) {
      const error = matrixError(actual, expected);
      return { pass: error <= COMPARISON_TOLERANCE, error, failures: error <= COMPARISON_TOLERANCE ? [] : ["matrix"] };
    }
    let pass = true;
    let maxError = 0;
    const failures = [];
    for (let index = 0; index < expected.length; index += 1) {
      const result = comparison(actual[index], expected[index]);
      pass = pass && result.pass;
      maxError = Math.max(maxError, result.error);
      if (!result.pass && failures.length < 8) failures.push(`[${index}]${result.failures[0] ? ` ${result.failures[0]}` : ""}`);
    }
    return { pass, error: maxError, failures };
  }
  if (expected !== null && typeof expected === "object" || actual !== null && typeof actual === "object") {
    if (expected === null || actual === null || typeof expected !== "object" || typeof actual !== "object" || Array.isArray(expected) || Array.isArray(actual)) {
      return { pass: false, error: Number.POSITIVE_INFINITY, failures: ["object shape"] };
    }
    let pass = true;
    let maxError = 0;
    const failures = [];
    for (const key of Object.keys(expected)) {
      const result = comparison(actual[key], expected[key]);
      pass = pass && result.pass;
      maxError = Math.max(maxError, result.error);
      if (!result.pass && failures.length < 8) failures.push(`${key}${result.failures.length ? `.${result.failures[0]}` : ""}`);
    }
    return { pass, error: maxError, failures };
  }
  const pass = Object.is(actual, expected);
  return { pass, error: pass ? 0 : Number.POSITIVE_INFINITY, failures: pass ? [] : ["value"] };
}

function compareRow(primaryRow, reconstructedRow, exactFields = []) {
  const result = comparison(primaryRow, reconstructedRow);
  let pass = result.pass;
  const failures = result.failures.slice();
  for (const field of exactFields) {
    if (!Array.isArray(primaryRow?.[field]) || JSON.stringify(primaryRow[field]) !== JSON.stringify(reconstructedRow[field])) {
      pass = false;
      if (failures.length < 8) failures.push(`${field} exact`);
    }
  }
  return { pass, error: result.error, failures };
}

const primaryText = readFileSync(PRIMARY_RECEIPT, "utf8");
const primary = JSON.parse(primaryText);
const protocolHash = sha256(PROTOCOL);
const primarySourceHash = sha256(PRIMARY_SOURCE);
const primaryReceiptHash = sha256(PRIMARY_RECEIPT);
const checks = [];

function addCheck(name, pass, details = {}) {
  if (checks.some((item) => item.name === name)) throw new Error(`duplicate independent check name: ${name}`);
  checks.push({ name, pass: Boolean(pass), ...details });
}

const chainRows = Array.isArray(primary?.chain_rows) ? primary.chain_rows : [];
const fixtureRows = Array.isArray(primary?.fixture_rows) ? primary.fixture_rows : [];
const marginRows = Array.isArray(primary?.margin_rows) ? primary.margin_rows : [];
const symbolRows = Array.isArray(primary?.symbol_rows) ? primary.symbol_rows : [];
const summary = primary?.summary && typeof primary.summary === "object" ? primary.summary : {};
const primaryChecks = Array.isArray(primary?.checks) ? primary.checks : [];
const primaryCheckNames = primaryChecks.map((item) => item?.name);

addCheck(
  "primary_schema_and_verdict",
  primary?.schema === PRIMARY_SCHEMA && primary?.verdict === "PASS",
  { schema: primary?.schema ?? null, verdict: primary?.verdict ?? null },
);
addCheck(
  "primary_protocol_identity",
  primary?.protocol === relativePath(PROTOCOL) && primary?.protocol_sha256 === protocolHash,
  { recorded: { path: primary?.protocol ?? null, sha256: primary?.protocol_sha256 ?? null }, expected: { path: relativePath(PROTOCOL), sha256: protocolHash } },
);
addCheck(
  "primary_source_identity",
  primary?.source === relativePath(PRIMARY_SOURCE) && primary?.source_sha256 === primarySourceHash,
  { recorded: { path: primary?.source ?? null, sha256: primary?.source_sha256 ?? null }, expected: { path: relativePath(PRIMARY_SOURCE), sha256: primarySourceHash } },
);
addCheck(
  "primary_tolerances",
  primary?.tolerances?.matrix === MATRIX_TOLERANCE && primary?.tolerances?.algebraic === ALGEBRAIC_TOLERANCE,
  { recorded: primary?.tolerances ?? null, expected: { matrix: MATRIX_TOLERANCE, algebraic: ALGEBRAIC_TOLERANCE } },
);
addCheck(
  "primary_check_integrity",
  primaryChecks.length === 86 &&
    primaryChecks.every((item) => item && typeof item.name === "string" && item.pass === true) &&
    new Set(primaryCheckNames).size === primaryCheckNames.length,
  { count: primaryChecks.length, unique_names: new Set(primaryCheckNames).size, expected: 86 },
);
addCheck(
  "primary_summary_integrity",
  summary.checks === 86 && summary.passed === 86 && summary.failed === 0,
  { recorded: summary, expected: { checks: 86, passed: 86, failed: 0 } },
);

let chainSchedulePass = chainRows.length === 10;
for (let index = 0; index < chainRows.length && index < 10; index += 1) {
  const size = CHAIN_SIZES[Math.floor(index / CHAIN_MASSES.length)];
  const mass = CHAIN_MASSES[index % CHAIN_MASSES.length];
  chainSchedulePass = chainSchedulePass && chainRows[index]?.size === size && chainRows[index]?.mass === mass;
}
const fixtureSchedulePass = fixtureRows.length === 2 && fixtureRows.every((row, index) => row?.name === FIXTURES[index].name);
const marginSchedulePass = marginRows.length === 10 && marginRows.every((row, index) => row?.index === index);
const symbolSchedulePass = symbolRows.length === 2 && symbolRows.every((row, index) => row?.mass === [0, 0.5][index]);
addCheck(
  "primary_row_counts",
  chainSchedulePass && fixtureSchedulePass && marginSchedulePass && symbolSchedulePass &&
    summary.chain_rows === 10 && summary.fixture_rows === 2 && summary.margin_rows === 10 && summary.symbol_rows === 2,
  { counts: { chain: chainRows.length, fixture: fixtureRows.length, margin: marginRows.length, symbol: symbolRows.length }, summary_counts: { chain: summary.chain_rows ?? null, fixture: summary.fixture_rows ?? null, margin: summary.margin_rows ?? null, symbol: summary.symbol_rows ?? null }, expected: { chain: 10, fixture: 2, margin: 10, symbol: 2 } },
);

function maximum(values) {
  const finite = values.filter((value) => isFiniteNumber(value));
  return finite.length ? Math.max(...finite) : 0;
}
const independentChainRows = [];
for (let index = 0; index < CHAIN_SIZES.length * CHAIN_MASSES.length; index += 1) {
  const size = CHAIN_SIZES[Math.floor(index / CHAIN_MASSES.length)];
  const mass = CHAIN_MASSES[index % CHAIN_MASSES.length];
  independentChainRows.push(reconstructChain(size, mass));
}
const independentFixtureRows = FIXTURES.map((specification) => reconstructFixture(specification));
const independentMarginRows = MARGINS.map((_, index) => reconstructMargin(index));
const independentSymbolRows = [0, 0.5].map((mass) => symbolValues(mass));

const reconstructedMatrixMaximum = maximum([
  ...independentChainRows.map((row) => row.square_root_error),
  ...independentChainRows.map((row) => row.schur_inverse_error),
  ...independentChainRows.map((row) => row.transport_identity_error),
  ...independentSymbolRows.map((row) => row.determinant_error),
]);
const reconstructedScalarMaximum = maximum([
  ...independentChainRows.flatMap((row) => [
    scalarError(row.hminus1_recurrence.C_closed, row.hminus1_recurrence.C_direct),
    scalarError(row.l2_recurrence.C_closed, row.l2_recurrence.C_direct),
  ]),
  ...independentFixtureRows.flatMap((row) => [
    scalarError(row.theta_sq, row.expected_theta_sq),
    scalarError(row.kappa_sq_over_lambda_fib, row.expected_relaxed_theta_sq),
    scalarError(row.comparison_factor, row.expected_factor),
    scalarError(row.hminus1_recurrence.C_closed, row.hminus1_recurrence.C_direct),
    scalarError(row.l2_recurrence.C_closed, row.l2_recurrence.C_direct),
  ]),
  ...independentMarginRows.map((row) => scalarError(row.C_normalized_direct, row.C_normalized_closed)),
  ...independentSymbolRows.flatMap((row) => [
    scalarError(row.lambda_fib_infinite, row.expected_lambda_fib_infinite),
    scalarError(row.theta_infinite, row.expected_theta_infinite),
    scalarError(row.q_eff_zero, row.expected_q_eff_zero),
  ]),
]);
const matrixMaximumComparison = scalarError(summary.max_matrix_error, reconstructedMatrixMaximum);
const scalarMaximumComparison = scalarError(summary.max_scalar_error, reconstructedScalarMaximum);
addCheck(
  "primary_summary_maxima",
  matrixMaximumComparison <= COMPARISON_TOLERANCE && scalarMaximumComparison <= COMPARISON_TOLERANCE,
  { recorded: { max_matrix_error: summary.max_matrix_error ?? null, max_scalar_error: summary.max_scalar_error ?? null }, reconstructed: { max_matrix_error: reconstructedMatrixMaximum, max_scalar_error: reconstructedScalarMaximum } },
);

for (let index = 0; index < CHAIN_SIZES.length * CHAIN_MASSES.length; index += 1) {
  const size = CHAIN_SIZES[Math.floor(index / CHAIN_MASSES.length)];
  const mass = CHAIN_MASSES[index % CHAIN_MASSES.length];
  const reconstructed = independentChainRows[index];
  const row = chainRows[index];
  const result = compareRow(row, reconstructed, ["retained", "eliminated"]);
  addCheck(`chain_${size}_${mass === 0 ? "zero" : "half"}`, result.pass, { row: { size, mass }, max_normalized_error: result.error, mismatches: result.failures });
}

for (let index = 0; index < FIXTURES.length; index += 1) {
  const reconstructed = independentFixtureRows[index];
  const row = fixtureRows[index];
  const result = compareRow(row, reconstructed);
  addCheck(`fixture_${FIXTURES[index].name}`, result.pass, { row: FIXTURES[index].name, max_normalized_error: result.error, mismatches: result.failures });
}

for (let index = 0; index < MARGINS.length; index += 1) {
  const reconstructed = independentMarginRows[index];
  const row = marginRows[index];
  const result = compareRow(row, reconstructed);
  addCheck(`margin_${index}`, result.pass, { row: index, max_normalized_error: result.error, mismatches: result.failures });
}

for (let index = 0; index < [0, 0.5].length; index += 1) {
  const mass = [0, 0.5][index];
  const reconstructed = independentSymbolRows[index];
  const row = symbolRows[index];
  const result = compareRow(row, reconstructed);
  addCheck(`symbol_${mass === 0 ? "zero" : "half"}`, result.pass, { row: { mass }, max_normalized_error: result.error, mismatches: result.failures });
}


if (checks.length !== 32) throw new Error(`independent check-count drift: expected 32, got ${checks.length}`);
const passed = checks.every((item) => item.pass === true);
const output = {
  schema: INDEPENDENT_SCHEMA,
  verdict: passed ? "PASS" : "FAIL",
  protocol: relativePath(PROTOCOL),
  protocol_sha256: protocolHash,
  source: relativePath(SOURCE),
  source_sha256: sha256(SOURCE),
  primary_source: relativePath(PRIMARY_SOURCE),
  primary_source_sha256: primarySourceHash,
  primary_receipt: relativePath(PRIMARY_RECEIPT),
  primary_receipt_sha256: primaryReceiptHash,
  tolerances: { matrix: MATRIX_TOLERANCE, algebraic: ALGEBRAIC_TOLERANCE, comparison: COMPARISON_TOLERANCE },
  summary: {
    checks: checks.length,
    passed: checks.filter((item) => item.pass).length,
    failed: checks.filter((item) => !item.pass).length,
  },
  checks,
};
mkdirSync(OUT_DIR, { recursive: true });
writeFileSync(OUT_PATH, `${JSON.stringify(output, null, 2)}\n`, "utf8");
console.log(JSON.stringify({ verdict: output.verdict, ...output.summary }, null, 2));
process.exitCode = passed ? 0 : 1;
