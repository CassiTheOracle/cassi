#!/usr/bin/env node
/**
 * Independent verifier for the fixed-graph anisotropic SU(2)
 * transfer-to-Hamiltonian receipt.
 *
 * This implementation uses only Node built-ins. It does not import or execute
 * the primary Python implementation. Modified-Bessel ratios are reconstructed
 * by midpoint integration, half-potential matrices by direct normalized-Haar
 * midpoint integration, and symmetric matrix functions by a Jacobi eigensolver.
 */

import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const SOURCE = fileURLToPath(import.meta.url);
const ROOT = path.resolve(path.dirname(SOURCE), "..");
const PROTOCOL = path.join(ROOT, "computations", "yang-mills-anisotropic-hamiltonian-limit-prereg.md");
const PRIMARY_SOURCE = path.join(ROOT, "computations", "verify_yang_mills_anisotropic_hamiltonian_limit.py");
const PRIMARY_RECEIPT = path.join(ROOT, "runs", "yang-mills-anisotropic-hamiltonian-limit", "verification.json");
const OUTPUT = path.join(ROOT, "runs", "yang-mills-anisotropic-hamiltonian-limit", "verification-independent.json");

const A = 1.0;
const G2_VALUES = [0.5, 1.0, 2.0];
const CUTOFFS = [2, 4, 6];
const DELTAS = [1 / 256, 1 / 512, 1 / 1024, 1 / 2048];
const LAMBDAS = [0.25, 1.0, 4.0];
const SEMIGROUP_N = [64, 128, 256, 512];
const BESSEL_POINTS = 65_536;
const HAAR_POINTS = 16_384;
const TOLERANCE = 5e-8;
const MONOTONE_FLOOR = 1e-13;
const EXPECTED_CHECKS = 24;

function sha256(filename) {
  return crypto.createHash("sha256").update(fs.readFileSync(filename)).digest("hex");
}

function relative(filename) {
  return path.relative(ROOT, filename).replaceAll(path.sep, "/");
}

function decision(name, passed, value = undefined, threshold = undefined) {
  const result = { name, passed: Boolean(passed) };
  if (value !== undefined) result.value = value;
  if (threshold !== undefined) result.threshold = threshold;
  return result;
}

function zeros(size) {
  return Array.from({ length: size }, () => new Float64Array(size));
}

function identity(size) {
  const result = zeros(size);
  for (let i = 0; i < size; i += 1) result[i][i] = 1;
  return result;
}

function cloneMatrix(matrix) {
  return matrix.map((row) => Float64Array.from(row));
}

function transpose(matrix) {
  const size = matrix.length;
  const result = zeros(size);
  for (let i = 0; i < size; i += 1) {
    for (let j = 0; j < size; j += 1) result[j][i] = matrix[i][j];
  }
  return result;
}

function multiply(left, right) {
  const size = left.length;
  const result = zeros(size);
  for (let i = 0; i < size; i += 1) {
    for (let k = 0; k < size; k += 1) {
      const coefficient = left[i][k];
      for (let j = 0; j < size; j += 1) result[i][j] += coefficient * right[k][j];
    }
  }
  return result;
}

function subtract(left, right) {
  const size = left.length;
  const result = zeros(size);
  for (let i = 0; i < size; i += 1) {
    for (let j = 0; j < size; j += 1) result[i][j] = left[i][j] - right[i][j];
  }
  return result;
}

function affineIdentity(matrix, identityCoefficient, matrixCoefficient) {
  const size = matrix.length;
  const result = zeros(size);
  for (let i = 0; i < size; i += 1) {
    for (let j = 0; j < size; j += 1) {
      result[i][j] = matrixCoefficient * matrix[i][j] + (i === j ? identityCoefficient : 0);
    }
  }
  return result;
}

function maxAbs(matrix) {
  let maximum = 0;
  for (const row of matrix) {
    for (const value of row) maximum = Math.max(maximum, Math.abs(value));
  }
  return maximum;
}

function symmetryResidual(matrix) {
  let maximum = 0;
  for (let i = 0; i < matrix.length; i += 1) {
    for (let j = i + 1; j < matrix.length; j += 1) {
      maximum = Math.max(maximum, Math.abs(matrix[i][j] - matrix[j][i]));
    }
  }
  return maximum;
}

function jacobiEigen(matrix) {
  const size = matrix.length;
  const work = cloneMatrix(matrix);
  const vectors = identity(size);
  const maximumIterations = 200 * size * size;

  for (let iteration = 0; iteration < maximumIterations; iteration += 1) {
    let p = 0;
    let q = 1;
    let largest = 0;
    for (let i = 0; i < size; i += 1) {
      for (let j = i + 1; j < size; j += 1) {
        const magnitude = Math.abs(work[i][j]);
        if (magnitude > largest) {
          largest = magnitude;
          p = i;
          q = j;
        }
      }
    }
    if (largest <= 2e-15 * Math.max(1, maxAbs(work))) break;

    const app = work[p][p];
    const aqq = work[q][q];
    const apq = work[p][q];
    const tau = (aqq - app) / (2 * apq);
    const tangent = (tau >= 0 ? 1 : -1) / (Math.abs(tau) + Math.sqrt(1 + tau * tau));
    const cosine = 1 / Math.sqrt(1 + tangent * tangent);
    const sine = tangent * cosine;

    for (let k = 0; k < size; k += 1) {
      if (k === p || k === q) continue;
      const akp = work[k][p];
      const akq = work[k][q];
      const newKp = cosine * akp - sine * akq;
      const newKq = sine * akp + cosine * akq;
      work[k][p] = newKp;
      work[p][k] = newKp;
      work[k][q] = newKq;
      work[q][k] = newKq;
    }
    work[p][p] = app - tangent * apq;
    work[q][q] = aqq + tangent * apq;
    work[p][q] = 0;
    work[q][p] = 0;

    for (let k = 0; k < size; k += 1) {
      const vkp = vectors[k][p];
      const vkq = vectors[k][q];
      vectors[k][p] = cosine * vkp - sine * vkq;
      vectors[k][q] = sine * vkp + cosine * vkq;
    }
  }

  const order = Array.from({ length: size }, (_, index) => index).sort(
    (left, right) => work[left][left] - work[right][right],
  );
  const values = order.map((index) => work[index][index]);
  const sortedVectors = zeros(size);
  for (let column = 0; column < size; column += 1) {
    for (let row = 0; row < size; row += 1) {
      sortedVectors[row][column] = vectors[row][order[column]];
    }
  }
  return { values, vectors: sortedVectors };
}

function symmetricFunction(matrix, transform) {
  const { values, vectors } = jacobiEigen(matrix);
  const size = matrix.length;
  const result = zeros(size);
  for (let i = 0; i < size; i += 1) {
    for (let j = 0; j < size; j += 1) {
      let total = 0;
      for (let k = 0; k < size; k += 1) {
        total += vectors[i][k] * transform(values[k]) * vectors[j][k];
      }
      result[i][j] = total;
    }
  }
  return result;
}

function spectralNorm(matrix) {
  const gram = multiply(transpose(matrix), matrix);
  const values = jacobiEigen(gram).values;
  return Math.sqrt(Math.max(0, values.at(-1)));
}

function matrixMetrics(matrix) {
  const values = jacobiEigen(matrix).values;
  return {
    symmetry_max_abs: symmetryResidual(matrix),
    min_eigenvalue: values[0],
    max_eigenvalue: values.at(-1),
    spectral_norm: spectralNorm(matrix),
  };
}

const besselCache = new Map();

function scaledBesselIntegrals(beta, maximumOrder) {
  const key = `${beta.toPrecision(17)}:${maximumOrder}`;
  if (besselCache.has(key)) return besselCache.get(key);

  const sums = new Float64Array(maximumOrder + 1);
  const corrections = new Float64Array(maximumOrder + 1);
  for (let point = 0; point < BESSEL_POINTS; point += 1) {
    const theta = (point + 0.5) * Math.PI / BESSEL_POINTS;
    const weight = Math.exp(beta * (Math.cos(theta) - 1));
    for (let order = 0; order <= maximumOrder; order += 1) {
      const addend = weight * Math.cos(order * theta) - corrections[order];
      const updated = sums[order] + addend;
      corrections[order] = updated - sums[order] - addend;
      sums[order] = updated;
    }
  }
  for (let order = 0; order <= maximumOrder; order += 1) sums[order] /= BESSEL_POINTS;
  besselCache.set(key, sums);
  return sums;
}

function etaValues(beta, cutoff) {
  const integrals = scaledBesselIntegrals(beta, cutoff + 1);
  const denominator = integrals[1];
  return Array.from({ length: cutoff + 1 }, (_, n) => integrals[n + 1] / denominator);
}

const halfPotentialCache = new Map();

function halfPotentialHaar(zeta, cutoff) {
  const key = `${zeta.toPrecision(17)}:${cutoff}`;
  if (halfPotentialCache.has(key)) return halfPotentialCache.get(key);

  const size = cutoff + 1;
  const matrix = zeros(size);
  const sine = new Float64Array(size);
  const factor = 2 / HAAR_POINTS;
  for (let point = 0; point < HAAR_POINTS; point += 1) {
    const theta = (point + 0.5) * Math.PI / HAAR_POINTS;
    const weight = Math.exp(-zeta * (1 - Math.cos(theta)));
    for (let n = 0; n < size; n += 1) sine[n] = Math.sin((n + 1) * theta);
    for (let n = 0; n < size; n += 1) {
      for (let m = 0; m <= n; m += 1) {
        matrix[n][m] += factor * weight * sine[n] * sine[m];
      }
    }
  }
  for (let n = 0; n < size; n += 1) {
    for (let m = 0; m < n; m += 1) matrix[m][n] = matrix[n][m];
  }
  halfPotentialCache.set(key, matrix);
  return matrix;
}

function diagonal(values) {
  const matrix = zeros(values.length);
  for (let i = 0; i < values.length; i += 1) matrix[i][i] = values[i];
  return matrix;
}

function targetHamiltonian(g2, cutoff) {
  const size = cutoff + 1;
  const matrix = zeros(size);
  const magnetic = 1 / (g2 * A);
  for (let n = 0; n < size; n += 1) {
    matrix[n][n] = (g2 * n * (n + 2)) / (2 * A) + 2 * magnetic;
    if (n + 1 < size) {
      matrix[n][n + 1] = -magnetic;
      matrix[n + 1][n] = -magnetic;
    }
  }
  return matrix;
}

function reconstructRow(g2, cutoff, delta) {
  const epsilon = delta * A;
  const betaTau = (4 * A) / (g2 * epsilon);
  const betaSigma = (2 * epsilon) / (g2 * A);
  const zeta = epsilon / (g2 * A);
  const eta = etaValues(betaTau, cutoff);
  const electric = diagonal(eta.map((value) => value ** 4));
  const half = halfPotentialHaar(zeta, cutoff);
  const transfer = multiply(multiply(half, electric), half);
  const hamiltonian = targetHamiltonian(g2, cutoff);
  const differenceGenerator = affineIdentity(transfer, 1 / epsilon, -1 / epsilon);
  const transferEigen = jacobiEigen(transfer).values;
  if (transferEigen[0] <= 0) throw new Error("independent transfer reconstruction lost positivity");
  const logarithmicGenerator = symmetricFunction(transfer, (value) => -Math.log(value) / epsilon);
  const normalization = Math.max(1, spectralNorm(hamiltonian));
  const differenceError = spectralNorm(subtract(differenceGenerator, hamiltonian)) / normalization;
  const logarithmicError = spectralNorm(subtract(logarithmicGenerator, hamiltonian)) / normalization;

  const mMetrics = matrixMetrics(half);
  const tMetrics = matrixMetrics(transfer);
  const hMetrics = matrixMetrics(hamiltonian);
  const aMetrics = matrixMetrics(differenceGenerator);
  const gMetrics = matrixMetrics(logarithmicGenerator);
  let resolventLowerViolation = 0;
  let resolventUpperViolation = 0;
  for (const eigenvalue of transferEigen) {
    const aEigenvalue = (1 - eigenvalue) / epsilon;
    const gEigenvalue = -Math.log(eigenvalue) / epsilon;
    for (const lambda of LAMBDAS) {
      const difference = 1 / (aEigenvalue + lambda) - 1 / (gEigenvalue + lambda);
      resolventLowerViolation = Math.max(resolventLowerViolation, -difference);
      resolventUpperViolation = Math.max(resolventUpperViolation, difference - epsilon);
    }
  }

  const rowChecks = [
    eta.every((value) => Number.isFinite(value) && value > 0 && value <= 1 + TOLERANCE),
    Math.abs(eta[0] - 1) <= TOLERANCE && eta.slice(0, -1).every((value, index) => value > eta[index + 1]),
    Math.abs(2 / (betaTau * epsilon) - g2 / (2 * A)) <= TOLERANCE,
    Math.abs(betaSigma / (2 * epsilon) - 1 / (g2 * A)) <= TOLERANCE,
    mMetrics.symmetry_max_abs <= TOLERANCE && mMetrics.min_eigenvalue > 0 && mMetrics.max_eigenvalue <= 1 + TOLERANCE,
    tMetrics.symmetry_max_abs <= TOLERANCE && tMetrics.min_eigenvalue > 0 && tMetrics.max_eigenvalue <= 1 + TOLERANCE,
    hMetrics.symmetry_max_abs <= TOLERANCE && hMetrics.min_eigenvalue >= -TOLERANCE * Math.max(1, hMetrics.spectral_norm),
    aMetrics.symmetry_max_abs <= TOLERANCE && aMetrics.min_eigenvalue >= -TOLERANCE * Math.max(1, aMetrics.spectral_norm),
    gMetrics.symmetry_max_abs <= TOLERANCE && gMetrics.min_eigenvalue >= -TOLERANCE * Math.max(1, gMetrics.spectral_norm),
    resolventLowerViolation <= TOLERANCE && resolventUpperViolation <= TOLERANCE,
  ];

  return {
    g_squared: g2,
    cutoff,
    delta,
    epsilon,
    beta_tau: betaTau,
    beta_sigma: betaSigma,
    eta,
    difference_generator_relative_error: differenceError,
    logarithmic_generator_relative_error: logarithmicError,
    row_checks: rowChecks,
    passed: rowChecks.every(Boolean),
    matrices: { half, electric, transfer, hamiltonian },
  };
}

function strictDecrease(values) {
  const drops = values.slice(0, -1).map((value, index) => value - values[index + 1]);
  return { passed: drops.every((drop) => drop > MONOTONE_FLOOR), minimum_drop: Math.min(...drops) };
}

function finitePayload(value) {
  if (value === null || typeof value === "string" || typeof value === "boolean") return true;
  if (typeof value === "number") return Number.isFinite(value);
  if (ArrayBuffer.isView(value)) return Array.from(value).every(Number.isFinite);
  if (Array.isArray(value)) return value.every(finitePayload);
  if (typeof value === "object") return Object.values(value).every(finitePayload);
  return false;
}

function keyOf(row) {
  return `${Number(row.g_squared).toPrecision(17)}:${row.cutoff}:${Number(row.delta).toPrecision(17)}`;
}

function sameSchedule(left, right) {
  return (
    Number(left.g_squared) === Number(right.g_squared)
    && Number(left.cutoff) === Number(right.cutoff)
    && Number(left.delta) === Number(right.delta)
  );
}

function parseArguments() {
  const unknown = process.argv.slice(2).filter((argument) => argument !== "--replace");
  if (unknown.length > 0) throw new Error(`unknown arguments: ${unknown.join(", ")}`);
  return { replace: process.argv.includes("--replace") };
}

function main() {
  const { replace } = parseArguments();
  if (fs.existsSync(OUTPUT) && !replace) {
    throw new Error(`refusing to overwrite existing receipt: ${OUTPUT}; pass --replace explicitly`);
  }
  for (const filename of [PROTOCOL, PRIMARY_SOURCE, PRIMARY_RECEIPT]) {
    if (!fs.existsSync(filename)) throw new Error(`missing required input: ${filename}`);
  }

  const primary = JSON.parse(fs.readFileSync(PRIMARY_RECEIPT, "utf8"));
  const reconstructedRows = [];
  for (const g2 of G2_VALUES) {
    for (const cutoff of CUTOFFS) {
      for (const delta of DELTAS) reconstructedRows.push(reconstructRow(g2, cutoff, delta));
    }
  }
  const primaryByKey = new Map(primary.matrix_rows.map((row) => [keyOf(row), row]));

  let maximumEtaDifference = 0;
  let maximumGeneratorErrorDifference = 0;
  let rowScheduleMatches = primary.matrix_rows.length === reconstructedRows.length;
  let rowDecisionsMatch = true;
  for (let index = 0; index < reconstructedRows.length; index += 1) {
    const independent = reconstructedRows[index];
    const primaryRow = primaryByKey.get(keyOf(independent));
    if (!primaryRow || !sameSchedule(independent, primaryRow)) {
      rowScheduleMatches = false;
      continue;
    }
    for (let etaIndex = 0; etaIndex < independent.eta.length; etaIndex += 1) {
      maximumEtaDifference = Math.max(
        maximumEtaDifference,
        Math.abs(independent.eta[etaIndex] - primaryRow.eta[etaIndex]),
      );
    }
    maximumGeneratorErrorDifference = Math.max(
      maximumGeneratorErrorDifference,
      Math.abs(independent.difference_generator_relative_error - primaryRow.difference_generator_relative_error),
      Math.abs(independent.logarithmic_generator_relative_error - primaryRow.logarithmic_generator_relative_error),
    );
    rowDecisionsMatch = rowDecisionsMatch
      && independent.passed
      && primaryRow.passed
      && independent.row_checks.length === 10
      && primaryRow.checks.length === 10
      && primaryRow.checks.every((item) => item.passed);
  }

  const reconstructedConvergence = [];
  for (const g2 of G2_VALUES) {
    for (const cutoff of CUTOFFS) {
      const familyRows = reconstructedRows.filter((row) => row.g_squared === g2 && row.cutoff === cutoff);
      const differenceErrors = familyRows.map((row) => row.difference_generator_relative_error);
      const logarithmicErrors = familyRows.map((row) => row.logarithmic_generator_relative_error);
      const differenceDecrease = strictDecrease(differenceErrors);
      const logarithmicDecrease = strictDecrease(logarithmicErrors);
      const checks = [
        differenceDecrease.passed,
        logarithmicDecrease.passed,
        differenceErrors.at(-1) / differenceErrors[0] <= 0.20
          && logarithmicErrors.at(-1) / logarithmicErrors[0] <= 0.20,
        differenceErrors.at(-1) / differenceErrors.at(-2) <= 0.70
          && logarithmicErrors.at(-1) / logarithmicErrors.at(-2) <= 0.70,
      ];
      reconstructedConvergence.push({
        g_squared: g2,
        cutoff,
        difference_errors: differenceErrors,
        logarithmic_errors: logarithmicErrors,
        checks,
        passed: checks.every(Boolean),
      });
    }
  }

  let convergenceScheduleMatches = primary.convergence_families.length === reconstructedConvergence.length;
  let maximumConvergenceDifference = 0;
  let convergenceDecisionsMatch = true;
  for (const family of reconstructedConvergence) {
    const primaryFamily = primary.convergence_families.find(
      (candidate) => candidate.g_squared === family.g_squared && candidate.cutoff === family.cutoff,
    );
    if (!primaryFamily) {
      convergenceScheduleMatches = false;
      continue;
    }
    for (let index = 0; index < DELTAS.length; index += 1) {
      maximumConvergenceDifference = Math.max(
        maximumConvergenceDifference,
        Math.abs(family.difference_errors[index] - primaryFamily.difference_errors[index]),
        Math.abs(family.logarithmic_errors[index] - primaryFamily.logarithmic_errors[index]),
      );
    }
    convergenceDecisionsMatch = convergenceDecisionsMatch
      && family.passed
      && primaryFamily.passed
      && family.checks.length === 4
      && primaryFamily.checks.length === 4
      && primaryFamily.checks.every((item) => item.passed);
  }

  let besselMaximumDifference = 0;
  for (const beta of [0.5, 2.0, 8.0]) {
    const primaryRows = primary.fixtures.bessel_character_coefficients.filter((row) => row.beta === beta);
    const primaryC1 = primaryRows.find((row) => row.dimension === 1).analytic;
    const independentIntegrals = scaledBesselIntegrals(beta, 7);
    for (const row of primaryRows) {
      const primaryEta = row.analytic / (row.dimension * primaryC1);
      const independentEta = independentIntegrals[row.dimension] / independentIntegrals[1];
      besselMaximumDifference = Math.max(besselMaximumDifference, Math.abs(primaryEta - independentEta));
    }
  }

  const halfPotentialProperties = [];
  for (const zeta of [1 / 64, 1 / 16, 1 / 4]) {
    const matrix = halfPotentialHaar(zeta, 6);
    const metrics = matrixMetrics(matrix);
    halfPotentialProperties.push({
      zeta,
      ...metrics,
      passed:
        metrics.symmetry_max_abs <= TOLERANCE
        && metrics.min_eigenvalue > 0
        && metrics.max_eigenvalue <= 1 + TOLERANCE,
    });
  }

  let coefficientMaximumError = 0;
  let wilsonMaximumRelativeError = 0;
  for (const g2 of G2_VALUES) {
    for (const delta of DELTAS) {
      const epsilon = delta;
      const betaTau = 4 / (g2 * epsilon);
      const betaSigma = (2 * epsilon) / g2;
      coefficientMaximumError = Math.max(
        coefficientMaximumError,
        Math.abs(2 / (betaTau * epsilon) - g2 / 2),
        Math.abs(betaSigma / (2 * epsilon) - 1 / g2),
        Math.abs(betaTau - 2 * (2 / (g2 * epsilon))),
        Math.abs(betaSigma - 2 * (epsilon / g2)),
      );
      const gWSquared = Math.sqrt(2) * g2;
      const aTau = epsilon / Math.sqrt(2);
      const xi = 1 / aTau;
      wilsonMaximumRelativeError = Math.max(
        wilsonMaximumRelativeError,
        Math.abs(4 * xi / gWSquared - betaTau) / betaTau,
        Math.abs(4 / (gWSquared * xi) - betaSigma) / betaSigma,
      );
    }
  }

  const mutationEpsilon = 1 / 16;
  const mutationBetaTau = 4 / mutationEpsilon;
  const mutationBetaSigma = 2 * mutationEpsilon;
  const temporalMutationRatio = (2 / ((mutationBetaTau / 2) * mutationEpsilon)) / 0.5;
  const spatialMutationRatio = ((2 * mutationBetaSigma) / (2 * mutationEpsilon)) / 1;
  const betaFourIntegral = scaledBesselIntegrals(4, 1)[1];
  const rawVacuumEigenvalue = (2 * Math.exp(4) * betaFourIntegral) / 4;

  const mutationHalf = halfPotentialHaar(mutationEpsilon, 6);
  const mutationR = diagonal(etaValues(mutationBetaTau, 6).map((value) => value ** 4));
  const asymmetric = multiply(multiply(mutationHalf, mutationHalf), mutationR);
  const asymmetricResidual = symmetryResidual(asymmetric);

  const gapRows = [8, 16, 32, 64, 128, 256].map((length) => {
    const gap = 2 - 2 * Math.cos((2 * Math.PI) / length);
    return { length, gap, excited_transfer_eigenvalue: Math.exp(-gap) };
  });
  const gapValues = gapRows.map((row) => row.gap);
  const gapDecrease = strictDecrease(gapValues);
  const gapControlsPass = gapRows.every(
    (row) => row.excited_transfer_eigenvalue > 0 && row.excited_transfer_eigenvalue < 1,
  ) && gapDecrease.passed && gapValues.at(-1) / gapValues[0] <= 0.002;

  let scalarLowerViolation = 0;
  let scalarUpperViolation = 0;
  for (const s of [0, 2 ** -16, 2 ** -12, 2 ** -8, 2 ** -4, 0.5, 0.75, 1 - 2 ** -8]) {
    for (const lambda of LAMBDAS) {
      const difference = 1 / (s + lambda) - 1 / (-Math.log(1 - s) + lambda);
      scalarLowerViolation = Math.max(scalarLowerViolation, -difference);
      scalarUpperViolation = Math.max(scalarUpperViolation, difference - 1);
    }
  }

  let fourLinkMaximumRelativeError = 0;
  for (const g2 of G2_VALUES) {
    const epsilon = DELTAS[0];
    const betaTau = 4 / (g2 * epsilon);
    const oneLinkCoefficient = 2 / (betaTau * epsilon);
    for (let n = 1; n <= 6; n += 1) {
      const j = n / 2;
      const induced = 4 * oneLinkCoefficient * j * (j + 1);
      const target = 2 * g2 * j * (j + 1);
      fourLinkMaximumRelativeError = Math.max(
        fourLinkMaximumRelativeError,
        Math.abs(induced - target) / target,
      );
    }
  }

  const semigroupHamiltonian = targetHamiltonian(1, 6);
  const semigroupExact = symmetricFunction(semigroupHamiltonian, (value) => Math.exp(-0.5 * value));
  const semigroupRows = [];
  for (const steps of SEMIGROUP_N) {
    const row = reconstructRow(1, 6, 0.5 / steps);
    const product = symmetricFunction(row.matrices.transfer, (value) => value ** steps);
    semigroupRows.push({
      steps,
      delta: 0.5 / steps,
      spectral_error: spectralNorm(subtract(product, semigroupExact)),
    });
  }
  const semigroupErrors = semigroupRows.map((row) => row.spectral_error);
  const semigroupDecrease = strictDecrease(semigroupErrors);
  let semigroupMaximumDifference = 0;
  for (let index = 0; index < SEMIGROUP_N.length; index += 1) {
    semigroupMaximumDifference = Math.max(
      semigroupMaximumDifference,
      Math.abs(semigroupErrors[index] - primary.fixtures.semigroup.rows[index].spectral_error),
    );
  }
  const semigroupPass = semigroupDecrease.passed
    && semigroupErrors.at(-1) / semigroupErrors[0] <= 0.20
    && semigroupMaximumDifference <= TOLERANCE;

  const expectedBoundary = {
    fixed_graph_anisotropic_hamiltonian_limit: "PASS",
    analytic_fixed_graph_core_limit: true,
    analytic_fixed_graph_strong_resolvent_limit: true,
    analytic_fixed_graph_log_generator_limit: true,
    analytic_fixed_graph_chernoff_limit: true,
    analytic_theorem_outside_executable: true,
    fixed_beta_gibbs_identified_with_anisotropic_limit: false,
    spatial_volume_uniformity_established: false,
    thermodynamic_limit_established: false,
    lattice_spacing_limit_established: false,
    continuum_limit_established: false,
    wightman_reconstruction_established: false,
    uniform_mass_gap_established: false,
    clay_verdict: "NULL",
    finite_isolated_square_fixture: "PASS",
  };
  const boundaryMatches = Object.entries(expectedBoundary).every(
    ([key, value]) => primary.claims[key] === value,
  );

  const checks = [
    decision(
      "primary_schema_and_verdict",
      primary.schema === "cassi.yang-mills.anisotropic-hamiltonian-limit.verification.v1"
        && primary.verdict === "PASS",
      { schema: primary.schema, verdict: primary.verdict },
    ),
    decision(
      "primary_frozen_counts",
      primary.summary.matrix_rows === 36
        && primary.summary.matrix_row_checks === 360
        && primary.summary.convergence_families === 9
        && primary.summary.convergence_checks === 36
        && primary.summary.top_level_checks === 18
        && primary.summary.total_checks === 414
        && primary.summary.passing_checks === 414
        && primary.summary.counts_match_frozen_contract === true,
      primary.summary,
    ),
    decision(
      "protocol_hash_binding",
      primary.source_bindings.protocol.sha256 === sha256(PROTOCOL)
        && primary.source_bindings.protocol.path === relative(PROTOCOL),
      primary.source_bindings.protocol,
    ),
    decision(
      "primary_source_hash_binding",
      primary.source_bindings.primary.sha256 === sha256(PRIMARY_SOURCE)
        && primary.source_bindings.primary.path === relative(PRIMARY_SOURCE),
      primary.source_bindings.primary,
    ),
    decision("primary_claim_boundary", boundaryMatches, primary.claims),
    decision(
      "matrix_row_schedule_reconstructed",
      rowScheduleMatches && reconstructedRows.length === 36,
      { rows: reconstructedRows.length, primary_rows: primary.matrix_rows.length },
      { rows: 36 },
    ),
    decision(
      "matrix_row_bessel_ratios_reconstructed",
      maximumEtaDifference <= TOLERANCE,
      maximumEtaDifference,
      TOLERANCE,
    ),
    decision(
      "matrix_row_generator_errors_reconstructed",
      maximumGeneratorErrorDifference <= TOLERANCE,
      maximumGeneratorErrorDifference,
      TOLERANCE,
    ),
    decision("matrix_row_decisions_reconstructed", rowDecisionsMatch),
    decision(
      "convergence_schedule_reconstructed",
      convergenceScheduleMatches && reconstructedConvergence.length === 9,
      { families: reconstructedConvergence.length, primary_families: primary.convergence_families.length },
      { families: 9 },
    ),
    decision(
      "convergence_values_reconstructed",
      maximumConvergenceDifference <= TOLERANCE,
      maximumConvergenceDifference,
      TOLERANCE,
    ),
    decision("convergence_decisions_reconstructed", convergenceDecisionsMatch),
    decision(
      "bessel_ratios_from_65536_point_midpoint_integral",
      besselMaximumDifference <= TOLERANCE,
      { maximum_abs_difference: besselMaximumDifference, points: BESSEL_POINTS },
      TOLERANCE,
    ),
    decision(
      "half_potentials_from_16384_point_normalized_haar_rule",
      halfPotentialProperties.every((row) => row.passed),
      { points: HAAR_POINTS, rows: halfPotentialProperties },
    ),
    decision(
      "anisotropic_coefficient_identities",
      coefficientMaximumError <= TOLERANCE,
      coefficientMaximumError,
      TOLERANCE,
    ),
    decision(
      "standard_wilson_bare_convention_map",
      wilsonMaximumRelativeError <= TOLERANCE,
      wilsonMaximumRelativeError,
      TOLERANCE,
    ),
    decision(
      "halved_temporal_weight_mutation_fires",
      Math.abs(temporalMutationRatio - 2) <= TOLERANCE,
      temporalMutationRatio,
      { target: 2, abs_tolerance: TOLERANCE },
    ),
    decision(
      "doubled_spatial_weight_mutation_fires",
      Math.abs(spatialMutationRatio - 2) <= TOLERANCE,
      spatialMutationRatio,
      { target: 2, abs_tolerance: TOLERANCE },
    ),
    decision(
      "omitted_kernel_normalization_mutation_fires",
      Math.abs(rawVacuumEigenvalue - 1) >= 0.10
        && Math.abs(rawVacuumEigenvalue - primary.fixtures.unnormalized_vacuum_eigenvalue_at_beta_4) <= TOLERANCE,
      {
        independent: rawVacuumEigenvalue,
        primary: primary.fixtures.unnormalized_vacuum_eigenvalue_at_beta_4,
      },
      { minimum_distance_from_one: 0.10, reconstruction_tolerance: TOLERANCE },
    ),
    decision(
      "asymmetric_product_mutation_fires",
      asymmetricResidual >= 1e-8
        && Math.abs(asymmetricResidual - primary.fixtures.asymmetric_product_max_abs_residual) <= TOLERANCE,
      { independent: asymmetricResidual, primary: primary.fixtures.asymmetric_product_max_abs_residual },
      { minimum: 1e-8, reconstruction_tolerance: TOLERANCE },
    ),
    decision("positive_transfer_collapsing_gap_control", gapControlsPass, gapRows),
    decision(
      "scalar_resolvent_inequality",
      scalarLowerViolation <= TOLERANCE && scalarUpperViolation <= TOLERANCE,
      { lower_violation: scalarLowerViolation, upper_violation: scalarUpperViolation },
      TOLERANCE,
    ),
    decision(
      "four_link_electric_identity",
      fourLinkMaximumRelativeError <= TOLERANCE,
      fourLinkMaximumRelativeError,
      TOLERANCE,
    ),
    decision(
      "semigroup_fixture_reconstructed",
      semigroupPass,
      {
        rows: semigroupRows,
        maximum_primary_difference: semigroupMaximumDifference,
        final_to_first_ratio: semigroupErrors.at(-1) / semigroupErrors[0],
      },
      { reconstruction_tolerance: TOLERANCE, final_to_first_ratio: 0.20 },
    ),
  ];

  if (checks.length !== EXPECTED_CHECKS) {
    throw new Error(`independent check count ${checks.length} != frozen ${EXPECTED_CHECKS}`);
  }
  const payloadForFiniteCheck = {
    reconstructedRows: reconstructedRows.map(({ matrices, ...row }) => row),
    reconstructedConvergence,
    besselMaximumDifference,
    halfPotentialProperties,
    coefficientMaximumError,
    wilsonMaximumRelativeError,
    temporalMutationRatio,
    spatialMutationRatio,
    rawVacuumEigenvalue,
    asymmetricResidual,
    gapRows,
    scalarLowerViolation,
    scalarUpperViolation,
    fourLinkMaximumRelativeError,
    semigroupRows,
    semigroupMaximumDifference,
    checks,
  };
  if (!finitePayload(payloadForFiniteCheck)) throw new Error("independent payload contains non-finite data");

  const passed = checks.every((item) => item.passed);
  const receipt = {
    schema: "cassi.yang-mills.anisotropic-hamiltonian-limit.verification-independent.v1",
    verdict: passed ? "PASS" : "FAIL",
    summary: {
      checks: checks.length,
      passing_checks: checks.filter((item) => item.passed).length,
      reconstructed_rows: reconstructedRows.length,
      reconstructed_convergence_families: reconstructedConvergence.length,
    },
    parameters: {
      reconstruction_tolerance: TOLERANCE,
      bessel_midpoint_points: BESSEL_POINTS,
      normalized_haar_midpoint_points: HAAR_POINTS,
      jacobi_eigensolver: true,
      primary_module_imported: false,
      scipy_used: false,
    },
    checks,
    reconstruction: payloadForFiniteCheck,
    claims: {
      independent_fixed_graph_fixture: passed ? "PASS" : "FAIL",
      analytic_theorem_outside_executable: true,
      spatial_volume_uniformity_established: false,
      thermodynamic_limit_established: false,
      lattice_spacing_limit_established: false,
      continuum_limit_established: false,
      wightman_reconstruction_established: false,
      uniform_mass_gap_established: false,
      clay_verdict: "NULL",
    },
    source_bindings: {
      protocol: { path: relative(PROTOCOL), sha256: sha256(PROTOCOL) },
      primary: { path: relative(PRIMARY_SOURCE), sha256: sha256(PRIMARY_SOURCE) },
      independent: { path: relative(SOURCE), sha256: sha256(SOURCE) },
      primary_receipt: { path: relative(PRIMARY_RECEIPT), sha256: sha256(PRIMARY_RECEIPT) },
    },
    runtime: {
      node: process.version,
      platform: `${process.platform}-${process.arch}`,
      cpus: os.cpus().length,
    },
  };

  fs.mkdirSync(path.dirname(OUTPUT), { recursive: true });
  fs.writeFileSync(OUTPUT, `${JSON.stringify(receipt, null, 2)}\n`, "utf8");

  console.log("Independent Yang-Mills anisotropic transfer verification");
  console.log(`  reconstructed rows: ${reconstructedRows.length}`);
  console.log(`  checks:             ${checks.filter((item) => item.passed).length}/${checks.length}`);
  console.log(`  Bessel points:      ${BESSEL_POINTS}`);
  console.log(`  Haar points:        ${HAAR_POINTS}`);
  console.log(`  receipt:            ${relative(OUTPUT)}`);
  console.log(`  VERDICT:            ${passed ? "PASS" : "FAIL"}`);
  console.log("  CLAY VERDICT:       NULL");
  if (!passed) {
    console.log(`  failed checks:      ${checks.filter((item) => !item.passed).map((item) => item.name).join(", ")}`);
    return 1;
  }
  return 0;
}

try {
  process.exitCode = main();
} catch (error) {
  console.error(error instanceof Error ? error.stack : String(error));
  process.exitCode = 1;
}
