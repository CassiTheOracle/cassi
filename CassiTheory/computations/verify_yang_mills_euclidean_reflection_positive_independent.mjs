#!/usr/bin/env node
/* Independent reconstruction of fixed-regulator Euclidean reflection support. */

import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const SOURCE = fileURLToPath(import.meta.url);
const ROOT = resolve(dirname(SOURCE), "..");
const PROTOCOL = join(ROOT, "computations", "yang-mills-euclidean-reflection-positive-prereg.md");
const PRIMARY_SOURCE = join(ROOT, "computations", "verify_yang_mills_euclidean_reflection_positive.py");
const DEFAULT_INPUT = join(ROOT, "runs", "yang_mills_euclidean_reflection_positive", "verification.json");
const DEFAULT_OUTPUT = join(ROOT, "runs", "yang_mills_euclidean_reflection_positive", "verification-independent.json");

const BETA_VALUES = [0.25, 1.0, 4.0, 16.0];
const CHARACTER_CUTOFFS = [4, 8, 16];
const SAMPLE_COUNTS = [8, 12, 16];
const HAAR_ORDERS = [1, 2, 3, 4, 5, 6];
const CLOSURE_INDICES = [1, 2, 4, 8, 16, 32];
const SIMPLEX_TIMES = [2, 4, 8, 16, 32];
const GAP_SIZES = [8, 16, 32, 64, 128, 256];

const PSD_RELATIVE_TOLERANCE = 5.0e-10;
const PRIMARY_TOLERANCE = 1.0e-11;
const HAAR_RELATIVE_TOLERANCE = 1.0e-9;
const EIGEN_SUPPORT_RELATIVE = 1.0e-12;
const RECONSTRUCTION_TOLERANCE = 2.0e-8;
const HAAR_MIDPOINTS = 65536;
const EXPECTED_ROWS = BETA_VALUES.length * CHARACTER_CUTOFFS.length * SAMPLE_COUNTS.length;
const EXPECTED_PRIMARY_CHECKS = EXPECTED_ROWS * 8 + 20;
const EXPECTED_CHECKS = 22;

function sha256(path) {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

function check(name, passed, detail = {}) {
  return { name, passed: Boolean(passed), ...detail };
}

function finitePayload(value) {
  if (Array.isArray(value)) return value.every(finitePayload);
  if (value && typeof value === "object") return Object.values(value).every(finitePayload);
  if (typeof value === "number") return Number.isFinite(value);
  return true;
}

function relativeError(left, right) {
  return Math.abs(left - right) / Math.max(Math.abs(left), Math.abs(right), Number.MIN_VALUE);
}

function closeEnough(left, right, tolerance = RECONSTRUCTION_TOLERANCE) {
  return Math.abs(left - right) <= tolerance * Math.max(1, Math.abs(left), Math.abs(right));
}

function relativeClose(left, right, tolerance = RECONSTRUCTION_TOLERANCE) {
  return Math.abs(left - right) <= tolerance * Math.max(Math.abs(left), Math.abs(right), Number.MIN_VALUE);
}

function arrayClose(left, right, relative = false, tolerance = RECONSTRUCTION_TOLERANCE) {
  return Array.isArray(left)
    && Array.isArray(right)
    && left.length === right.length
    && left.every((value, index) => (
      relative ? relativeClose(value, right[index], tolerance) : closeEnough(value, right[index], tolerance)
    ));
}

function factorial(n) {
  let value = 1;
  for (let index = 2; index <= n; index += 1) value *= index;
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
  let compensation = 0;
  for (let index = 0; index < HAAR_MIDPOINTS; index += 1) {
    const theta = (index + 0.5) * Math.PI / HAAR_MIDPOINTS;
    const term = Math.exp(beta * Math.cos(theta)) * Math.sin(theta) * Math.sin(n * theta);
    const next = sum + term;
    compensation += Math.abs(sum) >= Math.abs(term)
      ? (sum - next) + term
      : (term - next) + sum;
    sum = next;
  }
  const value = 2 * (sum + compensation) / HAAR_MIDPOINTS;
  haarCache.set(key, value);
  return value;
}

function characterCoefficients(beta, nMax) {
  const values = [];
  for (let n = 1; n <= nMax; n += 1) {
    values.push(2 * n * besselISeries(n, beta) / beta);
  }
  return values;
}

function characterVector(xValue, nMax) {
  const x = Math.max(-1, Math.min(1, xValue));
  const values = [1];
  if (nMax >= 2) values.push(2 * x);
  for (let index = 2; index < nMax; index += 1) {
    values.push(2 * x * values[index - 1] - values[index - 2]);
  }
  return values;
}

function dot(left, right) {
  return left.reduce((sum, value, index) => sum + value * right[index], 0);
}

function norm(vector) {
  return Math.sqrt(dot(vector, vector));
}

function deterministicQuaternions(count) {
  const rows = [];
  for (let index = 0; index < count; index += 1) {
    const step = index + 1;
    const raw = [
      1 + 0.03125 * step,
      Math.sin(Math.sqrt(2) * step) + 0.125 * Math.cos(step / 3),
      Math.cos(Math.sqrt(3) * step) - 0.1 * Math.sin(step / 5),
      Math.sin(Math.sqrt(5) * step + 0.375),
    ];
    const scale = norm(raw);
    rows.push(raw.map((value) => value / scale));
  }
  return rows;
}

function zeroMatrix(size) {
  return Array.from({ length: size }, () => Array(size).fill(0));
}

function identityMatrix(size) {
  const matrix = zeroMatrix(size);
  for (let index = 0; index < size; index += 1) matrix[index][index] = 1;
  return matrix;
}

function gramMatrix(quaternions, coefficients) {
  const count = quaternions.length;
  const gram = zeroMatrix(count);
  let maximumCharacterRatio = 0;
  for (let left = 0; left < count; left += 1) {
    for (let right = 0; right < count; right += 1) {
      const characters = characterVector(dot(quaternions[left], quaternions[right]), coefficients.length);
      for (let index = 0; index < characters.length; index += 1) {
        maximumCharacterRatio = Math.max(maximumCharacterRatio, Math.abs(characters[index]) / (index + 1));
      }
      gram[left][right] = dot(coefficients, characters);
    }
  }
  return { gram, maximumCharacterRatio };
}

function maximumAbsolute(matrix) {
  let maximum = 0;
  for (const row of matrix) {
    for (const value of row) maximum = Math.max(maximum, Math.abs(value));
  }
  return maximum;
}

function symmetryResidual(matrix) {
  let maximum = 0;
  for (let row = 0; row < matrix.length; row += 1) {
    for (let column = row + 1; column < matrix.length; column += 1) {
      maximum = Math.max(maximum, Math.abs(matrix[row][column] - matrix[column][row]));
    }
  }
  return maximum;
}

function symmetricPart(matrix) {
  return matrix.map((row, i) => row.map((value, j) => 0.5 * (value + matrix[j][i])));
}

function jacobiEigenvalues(input) {
  const matrix = symmetricPart(input).map((row) => [...row]);
  const size = matrix.length;
  const maxIterations = 100 * size * size;
  for (let iteration = 0; iteration < maxIterations; iteration += 1) {
    let p = 0;
    let q = 1;
    let largest = 0;
    for (let row = 0; row < size; row += 1) {
      for (let column = row + 1; column < size; column += 1) {
        const candidate = Math.abs(matrix[row][column]);
        if (candidate > largest) {
          largest = candidate;
          p = row;
          q = column;
        }
      }
    }
    const diagonalScale = Math.max(1, ...matrix.map((row, index) => Math.abs(row[index])));
    if (largest <= 2.0e-15 * diagonalScale) {
      return matrix.map((row, index) => row[index]).sort((left, right) => left - right);
    }
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
      const rotatedP = cosine * aip - sine * aiq;
      const rotatedQ = sine * aip + cosine * aiq;
      matrix[index][p] = rotatedP;
      matrix[p][index] = rotatedP;
      matrix[index][q] = rotatedQ;
      matrix[q][index] = rotatedQ;
    }
    matrix[p][p] = cosine * cosine * app - 2 * sine * cosine * apq + sine * sine * aqq;
    matrix[q][q] = sine * sine * app + 2 * sine * cosine * apq + cosine * cosine * aqq;
    matrix[p][q] = 0;
    matrix[q][p] = 0;
  }
  throw new Error("Jacobi eigensolver did not converge");
}

function matrixMetrics(matrix) {
  const residual = symmetryResidual(matrix);
  const eigenvalues = jacobiEigenvalues(matrix);
  const spectralScale = Math.max(1, ...eigenvalues.map(Math.abs));
  const threshold = PSD_RELATIVE_TOLERANCE * spectralScale;
  return {
    symmetry_residual: residual,
    minimum_eigenvalue: eigenvalues[0],
    maximum_eigenvalue: eigenvalues[eigenvalues.length - 1],
    spectral_scale: spectralScale,
    psd_threshold: threshold,
    positive_semidefinite: eigenvalues[0] >= -threshold,
    eigenvalues,
  };
}

function spatialWeights(beta, quaternions) {
  return quaternions.map((quaternion) => Math.exp(0.125 * beta * (quaternion[0] - 1)));
}

function buildTransfer(beta, gram, quaternions) {
  const weights = spatialWeights(beta, quaternions);
  return gram.map((row, i) => row.map((value, j) => weights[i] * value * weights[j]));
}

function reflectionVectors(count) {
  return [1, 2, 3].map((seed) => {
    const vector = Array.from({ length: count }, (_, index) => {
      const coordinate = index + 1;
      return Math.sin(coordinate * Math.sqrt(seed + 1)) + 0.5 * Math.cos(coordinate * Math.sqrt(seed + 2));
    });
    const scale = norm(vector);
    return vector.map((value) => value / scale);
  });
}

function quadraticForm(vector, matrix) {
  let value = 0;
  for (let row = 0; row < matrix.length; row += 1) {
    for (let column = 0; column < matrix.length; column += 1) {
      value += vector[row] * matrix[row][column] * vector[column];
    }
  }
  return value;
}

function reconstructRow(beta, nMax, sampleCount) {
  const quaternions = deterministicQuaternions(sampleCount);
  const coefficients = characterCoefficients(beta, nMax);
  const { gram, maximumCharacterRatio } = gramMatrix(quaternions, coefficients);
  const gramMetrics = matrixMetrics(gram);
  const quadraticForms = reflectionVectors(sampleCount).map((vector) => quadraticForm(vector, gram));
  const quadraticTolerance = PSD_RELATIVE_TOLERANCE * gramMetrics.spectral_scale;

  const permutation = Array.from({ length: sampleCount }, (_, index) => (index - 1 + sampleCount) % sampleCount);
  const permuted = permutation.map((row) => permutation.map((column) => gram[row][column]));
  const schur = gram.map((row, i) => row.map((value, j) => value * permuted[i][j]));
  const schurMetrics = matrixMetrics(schur);

  const transfer = buildTransfer(beta, gram, quaternions);
  const transferMetrics = matrixMetrics(transfer);
  const spectralRadius = transferMetrics.maximum_eigenvalue;
  const supported = transferMetrics.eigenvalues.filter((value) => value > EIGEN_SUPPORT_RELATIVE * spectralRadius);
  const normalizedSupported = supported.map((value) => value / spectralRadius);
  const effectiveEnergies = normalizedSupported.map((value) => -Math.log(value));

  const checks = [
    check(
      "finite_positive_character_coefficients",
      coefficients.every((value) => Number.isFinite(value) && value > 0),
    ),
    check("su2_character_bound", maximumCharacterRatio <= 1 + PRIMARY_TOLERANCE),
    check(
      "reflection_gram_symmetry",
      gramMetrics.symmetry_residual <= PRIMARY_TOLERANCE * gramMetrics.spectral_scale,
    ),
    check("reflection_gram_positive_semidefinite", gramMetrics.positive_semidefinite),
    check("reflection_quadratic_forms", Math.min(...quadraticForms) >= -quadraticTolerance),
    check("crossing_plaquette_schur_product", schurMetrics.positive_semidefinite),
    check(
      "weighted_transfer_positive_semidefinite",
      transferMetrics.positive_semidefinite && spectralRadius > 0,
    ),
    check(
      "normalized_transfer_spectrum",
      supported.length > 0
        && Math.min(...normalizedSupported) > 0
        && Math.max(...normalizedSupported) <= 1 + PRIMARY_TOLERANCE
        && Math.min(...effectiveEnergies) >= -PRIMARY_TOLERANCE,
    ),
  ];

  return {
    beta,
    character_cutoff: nMax,
    sample_count: sampleCount,
    character_coefficients: coefficients,
    maximum_character_ratio: maximumCharacterRatio,
    gram: gramMetrics,
    reflection_quadratic_forms: quadraticForms,
    schur: schurMetrics,
    transfer: transferMetrics,
    transfer_supported_eigenvalues: supported.length,
    minimum_normalized_transfer_eigenvalue: Math.min(...normalizedSupported),
    maximum_normalized_transfer_eigenvalue: Math.max(...normalizedSupported),
    minimum_effective_energy: Math.min(...effectiveEnergies),
    maximum_effective_energy: Math.max(...effectiveEnergies),
    checks,
    matrices: { gram, transfer },
  };
}

function matrixAddDiagonal(matrix, amount) {
  return matrix.map((row, i) => row.map((value, j) => value + (i === j ? amount : 0)));
}

function matrixScale(matrix, scale) {
  return matrix.map((row) => row.map((value) => value * scale));
}

function matrixMultiply(left, right) {
  const size = left.length;
  const result = zeroMatrix(size);
  for (let row = 0; row < size; row += 1) {
    for (let inner = 0; inner < size; inner += 1) {
      const factor = left[row][inner];
      for (let column = 0; column < size; column += 1) {
        result[row][column] += factor * right[inner][column];
      }
    }
  }
  return result;
}

function matrixPower(matrix, exponent) {
  let result = identityMatrix(matrix.length);
  let factor = matrix.map((row) => [...row]);
  let power = exponent;
  while (power > 0) {
    if (power % 2 === 1) result = matrixMultiply(result, factor);
    power = Math.floor(power / 2);
    if (power > 0) factor = matrixMultiply(factor, factor);
  }
  return result;
}

function weakLimitClosureFixture(gram) {
  const rows = CLOSURE_INDICES.map((index) => {
    const current = matrixAddDiagonal(gram, 1 / index);
    const metrics = matrixMetrics(current);
    let distance = 0;
    for (let row = 0; row < gram.length; row += 1) {
      for (let column = 0; column < gram.length; column += 1) {
        distance = Math.max(distance, Math.abs(current[row][column] - gram[row][column]));
      }
    }
    return {
      index,
      minimum_eigenvalue: metrics.minimum_eigenvalue,
      psd_threshold: metrics.psd_threshold,
      positive_semidefinite: metrics.positive_semidefinite,
      maximum_entry_distance_to_limit: distance,
    };
  });
  const distances = rows.map((row) => row.maximum_entry_distance_to_limit);
  const passed = rows.every((row) => row.positive_semidefinite)
    && distances.slice(0, -1).every((value, index) => value > distances[index + 1]);
  return { passed, rows };
}

function finiteSimplexFixture(transfer) {
  const spectralRadius = matrixMetrics(transfer).maximum_eigenvalue;
  const normalized = matrixScale(transfer, 1 / spectralRadius);
  const rows = SIMPLEX_TIMES.map((time) => {
    const powered = matrixPower(normalized, time);
    const diagonal = powered.map((row, index) => row[index]);
    const total = diagonal.reduce((sum, value) => sum + value, 0);
    const probabilities = diagonal.map((value) => value / total);
    return {
      time,
      minimum_probability: Math.min(...probabilities),
      maximum_probability: Math.max(...probabilities),
      probability_sum: probabilities.reduce((sum, value) => sum + value, 0),
    };
  });
  const passed = rows.every((row) => (
    row.minimum_probability >= -PRIMARY_TOLERANCE
      && Math.abs(row.probability_sum - 1) <= PRIMARY_TOLERANCE
  ));
  return { passed, rows };
}

function negativeCoefficientFixture() {
  const quaternions = deterministicQuaternions(16);
  const coefficients = characterCoefficients(1, 8);
  const bad = [...coefficients];
  let weighted = 0;
  for (let index = 0; index < bad.length - 1; index += 1) weighted += (index + 1) * bad[index];
  bad[bad.length - 1] = -(1 + weighted) / bad.length;
  const { gram } = gramMatrix(quaternions, bad);
  const metrics = matrixMetrics(gram);
  const diagonalError = Math.max(...gram.map((row, index) => Math.abs(row[index] + 1)));
  return {
    passed: bad[bad.length - 1] < 0
      && diagonalError <= PRIMARY_TOLERANCE
      && metrics.minimum_eigenvalue < -PRIMARY_TOLERANCE
      && !metrics.positive_semidefinite,
    bad_coefficient: bad[bad.length - 1],
    maximum_diagonal_error_from_minus_one: diagonalError,
    minimum_eigenvalue: metrics.minimum_eigenvalue,
    psd_threshold: metrics.psd_threshold,
  };
}

function asymmetricKernelFixture(gram) {
  const bad = gram.map((row) => [...row]);
  const scale = Math.max(1, maximumAbsolute(gram));
  bad[0][1] += 0.125 * scale;
  const residual = symmetryResidual(bad);
  return {
    passed: residual > PRIMARY_TOLERANCE * scale,
    symmetry_residual: residual,
    scale,
  };
}

function alternatingSequenceFixture() {
  const zero = [1, 0];
  const one = [0, 1];
  const sequence = Array.from({ length: 8 }, (_, index) => (index % 2 === 0 ? zero : one));
  const l1 = (left, right) => left.reduce((sum, value, index) => sum + Math.abs(value - right[index]), 0);
  const consecutive = sequence.slice(0, -1).map((value, index) => l1(value, sequence[index + 1]));
  const even = [0, 2, 4].map((index) => l1(sequence[index], sequence[index + 2]));
  const odd = [1, 3, 5].map((index) => l1(sequence[index], sequence[index + 2]));
  return {
    passed: consecutive.every((value) => Math.abs(value - 2) <= PRIMARY_TOLERANCE)
      && [...even, ...odd].every((value) => value <= PRIMARY_TOLERANCE),
    consecutive_l1: consecutive,
    even_subsequence_l1: even,
    odd_subsequence_l1: odd,
  };
}

function collapsingGapFixture() {
  const rows = GAP_SIZES.map((size) => {
    const gap = 2 - 2 * Math.cos(2 * Math.PI / size);
    const transferEigenvalues = [Math.exp(-gap), 1];
    return {
      size,
      gap,
      transfer_eigenvalues: transferEigenvalues,
      strictly_positive: Math.min(...transferEigenvalues) > 0,
    };
  });
  const gaps = rows.map((row) => row.gap);
  return {
    passed: rows.every((row) => row.strictly_positive)
      && gaps.slice(0, -1).every((value, index) => value > gaps[index + 1] && gaps[index + 1] > 0)
      && gaps[gaps.length - 1] < 1.0e-3,
    rows,
  };
}

function haarFixture() {
  const rows = [];
  for (const beta of BETA_VALUES) {
    const coefficients = characterCoefficients(beta, Math.max(...HAAR_ORDERS));
    for (const n of HAAR_ORDERS) {
      const value = haarCoefficientMidpoint(beta, n);
      const target = coefficients[n - 1];
      rows.push({
        beta,
        n,
        haar_value: value,
        closed_value: target,
        relative_error: relativeError(value, target),
      });
    }
  }
  return {
    rows,
    maximum_relative_error: Math.max(...rows.map((row) => row.relative_error)),
  };
}

function metricsMatch(primary, independent) {
  return closeEnough(primary.symmetry_residual, independent.symmetry_residual)
    && closeEnough(primary.minimum_eigenvalue, independent.minimum_eigenvalue)
    && closeEnough(primary.maximum_eigenvalue, independent.maximum_eigenvalue)
    && closeEnough(primary.spectral_scale, independent.spectral_scale)
    && closeEnough(primary.psd_threshold, independent.psd_threshold);
}

function rowMatches(primary, independent) {
  return primary.beta === independent.beta
    && primary.character_cutoff === independent.character_cutoff
    && primary.sample_count === independent.sample_count
    && arrayClose(primary.character_coefficients, independent.character_coefficients, true)
    && closeEnough(primary.maximum_character_ratio, independent.maximum_character_ratio)
    && metricsMatch(primary.gram, independent.gram)
    && arrayClose(primary.reflection_quadratic_forms, independent.reflection_quadratic_forms)
    && metricsMatch(primary.schur, independent.schur)
    && metricsMatch(primary.transfer, independent.transfer)
    && primary.transfer_supported_eigenvalues === independent.transfer_supported_eigenvalues
    && relativeClose(primary.minimum_normalized_transfer_eigenvalue, independent.minimum_normalized_transfer_eigenvalue)
    && closeEnough(primary.maximum_normalized_transfer_eigenvalue, independent.maximum_normalized_transfer_eigenvalue)
    && closeEnough(primary.minimum_effective_energy, independent.minimum_effective_energy)
    && closeEnough(primary.maximum_effective_energy, independent.maximum_effective_energy);
}

function fixtureRowsClose(primary, independent, fields) {
  return primary.rows.length === independent.rows.length
    && primary.rows.every((row, index) => fields.every((field) => (
      typeof row[field] === "boolean"
        ? row[field] === independent.rows[index][field]
        : closeEnough(row[field], independent.rows[index][field])
    )));
}

function parseArguments(argv) {
  let input = DEFAULT_INPUT;
  let output = DEFAULT_OUTPUT;
  let replace = false;
  for (let index = 2; index < argv.length; index += 1) {
    const argument = argv[index];
    if (argument === "--input") {
      index += 1;
      input = resolve(argv[index]);
    } else if (argument === "--output") {
      index += 1;
      output = resolve(argv[index]);
    } else if (argument === "--replace") {
      replace = true;
    } else {
      throw new Error(`unknown argument: ${argument}`);
    }
  }
  return { input, output, replace };
}

function main() {
  const { input, output, replace } = parseArguments(process.argv);
  if (!existsSync(input)) throw new Error(`primary receipt does not exist: ${input}`);
  if (existsSync(output) && !replace) throw new Error(`refusing to overwrite existing receipt: ${output}`);
  const primary = JSON.parse(readFileSync(input, "utf8"));

  const rows = [];
  for (const beta of BETA_VALUES) {
    for (const nMax of CHARACTER_CUTOFFS) {
      for (const sampleCount of SAMPLE_COUNTS) rows.push(reconstructRow(beta, nMax, sampleCount));
    }
  }
  const haar = haarFixture();
  const base = reconstructRow(1, 8, 8);
  const closure = weakLimitClosureFixture(base.matrices.gram);
  const simplex = finiteSimplexFixture(base.matrices.transfer);
  const negative = negativeCoefficientFixture();
  const asymmetric = asymmetricKernelFixture(base.matrices.gram);
  const alternating = alternatingSequenceFixture();
  const collapsingGap = collapsingGapFixture();

  const allRowsMatch = primary.rows.length === rows.length
    && primary.rows.every((row, index) => rowMatches(row, rows[index]));
  const allRowChecksPass = rows.every((row) => (
    row.checks.length === 8 && row.checks.every((item) => item.passed)
  ));
  const primaryHaarMap = new Map(primary.haar_fixture.rows.map((row) => [`${row.beta}|${row.n}`, row]));
  const haarMatches = haar.maximum_relative_error <= HAAR_RELATIVE_TOLERANCE
    && haar.rows.every((row) => {
      const expected = primaryHaarMap.get(`${row.beta}|${row.n}`);
      return expected
        && relativeClose(row.closed_value, expected.closed_value)
        && relativeClose(row.haar_value, expected.haar_value, 1.0e-8);
    });
  const closureMatches = closure.passed
    && primary.weak_limit_closure_fixture.passed
    && fixtureRowsClose(primary.weak_limit_closure_fixture, closure, [
      "index",
      "minimum_eigenvalue",
      "psd_threshold",
      "positive_semidefinite",
      "maximum_entry_distance_to_limit",
    ]);
  const simplexMatches = simplex.passed
    && primary.finite_simplex_fixture.passed
    && fixtureRowsClose(primary.finite_simplex_fixture, simplex, [
      "time",
      "minimum_probability",
      "maximum_probability",
      "probability_sum",
    ]);
  const negativeMatches = negative.passed
    && primary.negative_coefficient_fixture.passed
    && relativeClose(negative.bad_coefficient, primary.negative_coefficient_fixture.bad_coefficient)
    && closeEnough(negative.minimum_eigenvalue, primary.negative_coefficient_fixture.minimum_eigenvalue);
  const asymmetricMatches = asymmetric.passed
    && primary.asymmetric_kernel_fixture.passed
    && closeEnough(asymmetric.symmetry_residual, primary.asymmetric_kernel_fixture.symmetry_residual);
  const alternatingMatches = alternating.passed && primary.alternating_sequence_fixture.passed;
  const gapMatches = collapsingGap.passed
    && primary.collapsing_gap_fixture.passed
    && fixtureRowsClose(primary.collapsing_gap_fixture, collapsingGap, ["size", "gap", "strictly_positive"]);

  const expectedBoundaries = {
    full_sequence_convergence_established: false,
    uniqueness_established: false,
    clustering_established: false,
    anisotropic_hamiltonian_equivalence_established: false,
    continuum_limit_established: false,
    wightman_reconstruction_established: false,
    uniform_mass_gap_established: false,
    clay_verdict: "NULL",
  };

  const checks = [
    check("primary_schema", primary.schema === "cassi.yang-mills.euclidean-reflection-positive.v1"),
    check("primary_verdict", primary.verdict === "PASS" && primary.fixed_regulator_euclidean_support === "PASS"),
    check("primary_classification", primary.classification === "FIXED_REGULATOR_EUCLIDEAN_REFLECTION_SUPPORT"),
    check(
      "primary_check_counts",
      primary.summary.rows === EXPECTED_ROWS
        && primary.summary.checks === EXPECTED_PRIMARY_CHECKS
        && primary.summary.passed === EXPECTED_PRIMARY_CHECKS
        && primary.summary.failed === 0,
    ),
    check(
      "protocol_binding",
      primary.protocol === "computations/yang-mills-euclidean-reflection-positive-prereg.md"
        && primary.protocol_sha256 === sha256(PROTOCOL),
    ),
    check(
      "primary_source_binding",
      primary.source === "computations/verify_yang_mills_euclidean_reflection_positive.py"
        && primary.source_sha256 === sha256(PRIMARY_SOURCE),
    ),
    check(
      "independent_source_binding",
      relative(ROOT, SOURCE).replaceAll("\\", "/")
        === "computations/verify_yang_mills_euclidean_reflection_positive_independent.mjs"
        && Boolean(sha256(SOURCE)),
    ),
    check(
      "schedule_contract",
      JSON.stringify(primary.schedule.beta_values) === JSON.stringify(BETA_VALUES)
        && JSON.stringify(primary.schedule.character_cutoffs) === JSON.stringify(CHARACTER_CUTOFFS)
        && JSON.stringify(primary.schedule.sample_counts) === JSON.stringify(SAMPLE_COUNTS)
        && JSON.stringify(primary.schedule.haar_orders) === JSON.stringify(HAAR_ORDERS)
        && JSON.stringify(primary.schedule.closure_indices) === JSON.stringify(CLOSURE_INDICES)
        && JSON.stringify(primary.schedule.simplex_times) === JSON.stringify(SIMPLEX_TIMES)
        && JSON.stringify(primary.schedule.gap_sizes) === JSON.stringify(GAP_SIZES),
    ),
    check(
      "tolerance_contract",
      primary.tolerances.primary === PRIMARY_TOLERANCE
        && primary.tolerances.haar_relative === HAAR_RELATIVE_TOLERANCE
        && primary.tolerances.psd_relative === PSD_RELATIVE_TOLERANCE
        && primary.tolerances.eigen_support_relative === EIGEN_SUPPORT_RELATIVE,
    ),
    check(
      "normalization_contract",
      primary.normalization.character_coefficient === "C_n=I_(n-1)-I_(n+1)=2*n*I_n(beta)/beta"
        && primary.normalization.convolution_eigenvalue === "r_n=C_n/n=2*I_n(beta)/beta",
    ),
    check(
      "analytic_input_contract",
      primary.analytic_inputs.finite_torus_wilson_reflection_positivity === true
        && primary.analytic_inputs.finite_spatial_volume_positive_transfer === true
        && primary.analytic_inputs.compact_group_finite_range_gibbs_compactness === true
        && primary.analytic_inputs.executable_proof_of_geometric_reflection_factorization === false
        && primary.analytic_inputs.infinite_volume_measure_constructed_by_verifier === false,
    ),
    check("boundary_contract", JSON.stringify(primary.boundaries) === JSON.stringify(expectedBoundaries)),
    check("haar_reconstruction", haarMatches, { maximum_relative_error: haar.maximum_relative_error }),
    check("all_rows_reconstructed", allRowsMatch, { rows: rows.length }),
    check("row_checks_independently_pass", allRowChecksPass),
    check("weak_limit_closure_reconstruction", closureMatches),
    check("finite_simplex_reconstruction", simplexMatches),
    check("negative_coefficient_firing", negativeMatches, { minimum_eigenvalue: negative.minimum_eigenvalue }),
    check("asymmetric_kernel_firing", asymmetricMatches),
    check("alternating_sequence_firing", alternatingMatches),
    check("collapsing_gap_firing", gapMatches),
    check("finite_payload_and_primary_receipt_binding", finitePayload(primary) && Boolean(sha256(input))),
  ];
  if (checks.length !== EXPECTED_CHECKS) throw new Error("independent check count drifted from frozen protocol");
  const passed = checks.every((item) => item.passed);

  const receipt = {
    schema: "cassi.yang-mills.euclidean-reflection-positive.independent.v1",
    verdict: passed ? "PASS" : "FAIL",
    classification: "INDEPENDENT_FIXED_REGULATOR_EUCLIDEAN_REFLECTION_RECONSTRUCTION",
    scope: "Independent positive-series, midpoint-Haar and Jacobi-spectrum reconstruction of all finite support fixtures. Infinite-volume compactness and Wilson reflection positivity remain analytic arguments.",
    protocol: relative(ROOT, PROTOCOL).replaceAll("\\", "/"),
    protocol_sha256: sha256(PROTOCOL),
    primary_source: relative(ROOT, PRIMARY_SOURCE).replaceAll("\\", "/"),
    primary_source_sha256: sha256(PRIMARY_SOURCE),
    independent_source: relative(ROOT, SOURCE).replaceAll("\\", "/"),
    independent_source_sha256: sha256(SOURCE),
    primary_receipt: relative(ROOT, input).replaceAll("\\", "/"),
    primary_receipt_sha256: sha256(input),
    runtime: { node: process.version },
    schedule: {
      beta_values: BETA_VALUES,
      character_cutoffs: CHARACTER_CUTOFFS,
      sample_counts: SAMPLE_COUNTS,
      haar_orders: HAAR_ORDERS,
      haar_midpoints: HAAR_MIDPOINTS,
      closure_indices: CLOSURE_INDICES,
      simplex_times: SIMPLEX_TIMES,
      gap_sizes: GAP_SIZES,
    },
    tolerances: {
      reconstruction: RECONSTRUCTION_TOLERANCE,
      haar_relative: HAAR_RELATIVE_TOLERANCE,
      psd_relative: PSD_RELATIVE_TOLERANCE,
    },
    boundaries: expectedBoundaries,
    summary: {
      rows_reconstructed: rows.length,
      checks: checks.length,
      passed: checks.filter((item) => item.passed).length,
      failed: checks.filter((item) => !item.passed).length,
    },
    checks,
    haar_fixture: haar,
    weak_limit_closure_fixture: closure,
    finite_simplex_fixture: simplex,
    negative_coefficient_fixture: negative,
    asymmetric_kernel_fixture: asymmetric,
    alternating_sequence_fixture: alternating,
    collapsing_gap_fixture: collapsingGap,
    rows: rows.map((row) => ({
      beta: row.beta,
      character_cutoff: row.character_cutoff,
      sample_count: row.sample_count,
      minimum_gram_eigenvalue: row.gram.minimum_eigenvalue,
      minimum_schur_eigenvalue: row.schur.minimum_eigenvalue,
      minimum_transfer_eigenvalue: row.transfer.minimum_eigenvalue,
      checks_passed: row.checks.filter((item) => item.passed).length,
    })),
  };
  if (!finitePayload(receipt)) throw new Error("non-finite independent Euclidean reflection receipt payload");
  mkdirSync(dirname(output), { recursive: true });
  writeFileSync(output, `${JSON.stringify(receipt, null, 2)}\n`, "utf8");
  console.log(JSON.stringify(receipt.summary));
  return passed ? 0 : 1;
}

process.exitCode = main();
