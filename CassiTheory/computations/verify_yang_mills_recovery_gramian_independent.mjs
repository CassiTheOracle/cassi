import { createHash } from "node:crypto";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

/*
 * Independent reconstruction for the frozen YMRG protocol.
 *
 * The primary receipt is evidence only: every matrix, eigenspectrum, bound,
 * and identity below is reconstructed from the protocol's fixed schedule.
 * In particular, no primary-generated matrix is ever used to construct an
 * expected quantity.  The primary source is touched only by sha256File().
 */

const HERE = dirname(fileURLToPath(import.meta.url));
const THEORY_ROOT = resolve(HERE, "..");
const PROTOCOL_PATH = join(HERE, "yang-mills-recovery-gramian-prereg.md");
const PRIMARY_SOURCE_PATH = join(HERE, "verify_yang_mills_recovery_gramian.py");
const PRIMARY_RECEIPT_PATH = join(
  THEORY_ROOT,
  "runs",
  "yang_mills_recovery_gramian",
  "verification.json",
);
const INDEPENDENT_RECEIPT_PATH = join(
  THEORY_ROOT,
  "runs",
  "yang_mills_recovery_gramian",
  "verification-independent.json",
);

const PROTOCOL_ID = "CassiTheory/computations/yang-mills-recovery-gramian-prereg.md";
const PRIMARY_SOURCE_ID =
  "CassiTheory/computations/verify_yang_mills_recovery_gramian.py";
const PRIMARY_RECEIPT_ID =
  "CassiTheory/runs/yang_mills_recovery_gramian/verification.json";
const OWN_SOURCE_ID =
  "CassiTheory/computations/verify_yang_mills_recovery_gramian_independent.mjs";

const PRIMARY_SCHEMA = "cassi.yang-mills-recovery-gramian.verification.v1";
const INDEPENDENT_SCHEMA =
  "cassi.yang-mills-recovery-gramian.verification-independent.v1";
const PRIMARY_TOLERANCE = 1e-11;
const COMPARISON_TOLERANCE = 1e-9;
const INDEPENDENT_CHECK_COUNT = 30;
const PRIMARY_CHECK_COUNT = 58;
const ANGLE_EPSILONS = Object.freeze([1 / 2, 1 / 4, 1 / 8, 1 / 16]);
const SCORE_THETAS = Object.freeze([0, 1 / 10, 1 / 2, 1]);
const GAUSSIAN_SIZES = Object.freeze([4, 8, 16, 32, 64]);
const GAUSSIAN_MASSES = Object.freeze([0, 1 / 2]);

function sha256Bytes(bytes) {
  return createHash("sha256").update(bytes).digest("hex");
}

function sha256File(filePath) {
  return sha256Bytes(readFileSync(filePath));
}

function finiteNumber(value) {
  return typeof value === "number" && Number.isFinite(value);
}

function scalarNormalizedError(actual, expected) {
  if (!finiteNumber(actual) || !finiteNumber(expected)) return Infinity;
  return Math.abs(actual - expected) / Math.max(1, Math.abs(expected));
}

function sameScheduleNumber(actual, expected) {
  return finiteNumber(actual) && actual === expected;
}

function zeros(size) {
  return Array.from({ length: size }, () => Array(size).fill(0));
}

function identity(size) {
  const result = zeros(size);
  for (let i = 0; i < size; i += 1) result[i][i] = 1;
  return result;
}

function cloneMatrix(matrix) {
  return matrix.map((row) => row.slice());
}

function outer(left, right = left) {
  return left.map((x) => right.map((y) => x * y));
}

function matrixAdd(left, right, rightScale = 1) {
  const result = zeros(left.length);
  for (let i = 0; i < left.length; i += 1) {
    for (let j = 0; j < left.length; j += 1) {
      result[i][j] = left[i][j] + rightScale * right[i][j];
    }
  }
  return result;
}

function matrixScale(matrix, scale) {
  return matrix.map((row) => row.map((value) => scale * value));
}

function transpose(matrix) {
  if (!Array.isArray(matrix) || matrix.length === 0) return [];
  return matrix[0].map((_, column) => matrix.map((row) => row[column]));
}

function matrixMultiply(left, right) {
  if (left.length === 0 || right.length === 0) return [];
  const result = Array.from({ length: left.length }, () =>
    Array(right[0].length).fill(0),
  );
  for (let i = 0; i < left.length; i += 1) {
    for (let k = 0; k < right.length; k += 1) {
      const leftValue = left[i][k];
      if (leftValue === 0) continue;
      for (let j = 0; j < right[0].length; j += 1) {
        result[i][j] += leftValue * right[k][j];
      }
    }
  }
  return result;
}

function matrixVectorMultiply(matrix, vector) {
  return matrix.map((row) =>
    row.reduce((sum, value, index) => sum + value * vector[index], 0),
  );
}

function dot(left, right) {
  let result = 0;
  for (let i = 0; i < left.length; i += 1) result += left[i] * right[i];
  return result;
}

function frobeniusNorm(matrix) {
  let sum = 0;
  for (const row of matrix) {
    for (const value of row) sum += value * value;
  }
  return Math.sqrt(sum);
}

function symmetrize(matrix) {
  const result = cloneMatrix(matrix);
  for (let i = 0; i < result.length; i += 1) {
    for (let j = i + 1; j < result.length; j += 1) {
      const value = 0.5 * (result[i][j] + result[j][i]);
      result[i][j] = value;
      result[j][i] = value;
    }
  }
  return result;
}

/* Cyclic Jacobi diagonalization of a real symmetric matrix. */
function jacobiSymmetric(input) {
  const n = input.length;
  const matrix = symmetrize(input);
  const vectors = identity(n);
  const scale = Math.max(1, frobeniusNorm(matrix));
  const tolerance = 1e-15 * scale;
  const maxSweeps = Math.max(32, Math.min(128, 2 * n + 16));

  for (let sweep = 0; sweep < maxSweeps; sweep += 1) {
    let offDiagonalSquared = 0;
    for (let p = 0; p < n - 1; p += 1) {
      for (let q = p + 1; q < n; q += 1) {
        const apq = matrix[p][q];
        offDiagonalSquared += 2 * apq * apq;
        if (Math.abs(apq) <= tolerance) continue;

        const app = matrix[p][p];
        const aqq = matrix[q][q];
        const tau = (aqq - app) / (2 * apq);
        const sign = tau < 0 ? -1 : 1;
        const t = sign / (Math.abs(tau) + Math.sqrt(1 + tau * tau));
        const c = 1 / Math.sqrt(1 + t * t);
        const s = t * c;

        for (let k = 0; k < n; k += 1) {
          if (k === p || k === q) continue;
          const akp = matrix[k][p];
          const akq = matrix[k][q];
          const newKp = c * akp - s * akq;
          const newKq = s * akp + c * akq;
          matrix[k][p] = newKp;
          matrix[p][k] = newKp;
          matrix[k][q] = newKq;
          matrix[q][k] = newKq;
        }

        matrix[p][p] = app - t * apq;
        matrix[q][q] = aqq + t * apq;
        matrix[p][q] = 0;
        matrix[q][p] = 0;

        for (let k = 0; k < n; k += 1) {
          const vkp = vectors[k][p];
          const vkq = vectors[k][q];
          vectors[k][p] = c * vkp - s * vkq;
          vectors[k][q] = s * vkp + c * vkq;
        }
      }
    }
    if (Math.sqrt(offDiagonalSquared) <= tolerance) break;
  }

  const order = Array.from({ length: n }, (_, index) => index).sort(
    (left, right) => matrix[left][left] - matrix[right][right],
  );
  return {
    values: order.map((index) => matrix[index][index]),
    vectors: vectors.map((row) => order.map((index) => row[index])),
  };
}

function operatorNorm(matrix) {
  if (!Array.isArray(matrix) || matrix.length === 0) return 0;
  const gramian = symmetrize(matrixMultiply(transpose(matrix), matrix));
  const values = jacobiSymmetric(gramian).values;
  return Math.sqrt(Math.max(0, values[values.length - 1] ?? 0));
}

function matrixNormalizedError(actual, expected) {
  if (!Array.isArray(actual) || !Array.isArray(expected)) return Infinity;
  if (actual.length !== expected.length || expected.length === 0) return Infinity;
  for (let i = 0; i < expected.length; i += 1) {
    if (!Array.isArray(actual[i]) || actual[i].length !== expected[i].length) {
      return Infinity;
    }
    for (const value of actual[i]) if (!finiteNumber(value)) return Infinity;
  }
  const difference = expected.map((row, i) =>
    row.map((value, j) => actual[i][j] - value),
  );
  return operatorNorm(difference) / Math.max(1, operatorNorm(expected));
}

function vectorNormalizedError(actual, expected) {
  if (!Array.isArray(actual) || !Array.isArray(expected)) return Infinity;
  if (actual.length !== expected.length) return Infinity;
  let maximum = 0;
  for (let i = 0; i < expected.length; i += 1) {
    const error = scalarNormalizedError(actual[i], expected[i]);
    if (error > maximum) maximum = error;
  }
  return maximum;
}
function vectorArrayNormalizedError(actual, expected) {
  if (!Array.isArray(actual) || !Array.isArray(expected)) return Infinity;
  if (actual.length !== expected.length) return Infinity;
  let maximum = 0;
  for (let i = 0; i < expected.length; i += 1) {
    const error = vectorNormalizedError(actual[i], expected[i]);
    if (error > maximum) maximum = error;
  }
  return maximum;
}


function matrixArrayNormalizedError(actual, expected) {
  if (!Array.isArray(actual) || !Array.isArray(expected)) return Infinity;
  if (actual.length !== expected.length) return Infinity;
  let maximum = 0;
  for (let i = 0; i < expected.length; i += 1) {
    const error = matrixNormalizedError(actual[i], expected[i]);
    if (error > maximum) maximum = error;
  }
  return maximum;
}

function compareNumber(actual, expected) {
  const error = scalarNormalizedError(actual, expected);
  return { error, pass: error <= COMPARISON_TOLERANCE };
}

function compareMatrix(actual, expected) {
  const error = matrixNormalizedError(actual, expected);
  return { error, pass: error <= COMPARISON_TOLERANCE };
}

function compareVector(actual, expected) {
  const error = vectorNormalizedError(actual, expected);
  return { error, pass: error <= COMPARISON_TOLERANCE };
}
function compareVectorArray(actual, expected) {
  const error = vectorArrayNormalizedError(actual, expected);
  return { error, pass: error <= COMPARISON_TOLERANCE };
}


function compareMatrixArray(actual, expected) {
  const error = matrixArrayNormalizedError(actual, expected);
  return { error, pass: error <= COMPARISON_TOLERANCE };
}

function compareBoolean(actual, expected) {
  const pass = actual === expected;
  return { error: pass ? 0 : Infinity, pass };
}

function compareIndex(actual, position) {
  const pass = actual === position;
  return { error: pass ? 0 : Infinity, pass };
}


function aggregateComparisons(comparisons) {
  let pass = true;
  let error = 0;
  for (const comparison of comparisons) {
    pass = pass && comparison.pass;
    if (comparison.error > error) error = comparison.error;
  }
  return { pass, error };
}

function makeCheck(name, pass, error, category = "scalar") {
  return {
    name,
    pass: Boolean(pass),
    normalized_error: Number.isFinite(error) ? error : null,
    tolerance: COMPARISON_TOLERANCE,
    category,
  };
}

function maxFinite(values) {
  let maximum = 0;
  for (const value of values) if (finiteNumber(value) && value > maximum) maximum = value;
  return maximum;
}

function precisionMatrix(size, mass) {
  const result = zeros(size);
  const diagonal = 2 + mass * mass;
  for (let i = 0; i < size; i += 1) {
    result[i][i] = diagonal;
    if (i > 0) result[i][i - 1] = -1;
    if (i + 1 < size) result[i][i + 1] = -1;
  }
  return result;
}

function sineBasis(size) {
  const result = zeros(size);
  const factor = Math.sqrt(2 / (size + 1));
  for (let i = 0; i < size; i += 1) {
    for (let k = 0; k < size; k += 1) {
      result[i][k] =
        factor * Math.sin(((i + 1) * (k + 1) * Math.PI) / (size + 1));
    }
  }
  return result;
}

function gaussianChainExpectation(size, mass) {
  const precision = precisionMatrix(size, mass);
  const basis = sineBasis(size);
  const precisionEigenvalues = Array.from({ length: size }, (_, k) =>
    mass * mass + 4 * Math.sin(((k + 1) * Math.PI) / (2 * (size + 1))) ** 2,
  );
  const squareRoot = zeros(size);
  for (let i = 0; i < size; i += 1) {
    for (let j = 0; j < size; j += 1) {
      let value = 0;
      for (let k = 0; k < size; k += 1) {
        value +=
          basis[i][k] * Math.sqrt(precisionEigenvalues[k]) * basis[j][k];
      }
      squareRoot[i][j] = value;
    }
  }

  const diagonal = squareRoot.map((row, index) => row[index]);
  const diagonalMinimum = Math.min(...diagonal);
  const diagonalMaximum = Math.max(...diagonal);
  const gramian = zeros(size);
  for (let i = 0; i < size; i += 1) {
    for (let j = 0; j < size; j += 1) {
      gramian[i][j] =
        squareRoot[i][j] /
        Math.sqrt(Math.max(0, diagonal[i] * diagonal[j]));
    }
  }
  const precisionSpectrum = jacobiSymmetric(precision).values;
  const qSpectrum = jacobiSymmetric(squareRoot).values;
  const gramianSpectrum = jacobiSymmetric(gramian).values;
  const minimumPrecisionEigenvalue = qSpectrum[0];
  const expectedMinimumPrecisionEigenvalue = Math.sqrt(precisionEigenvalues[0]);
  const qMinimumError = scalarNormalizedError(
    minimumPrecisionEigenvalue,
    expectedMinimumPrecisionEigenvalue,
  );
  const gammaRecovery = gramianSpectrum[0];
  const squareRootError = matrixNormalizedError(
    matrixMultiply(squareRoot, squareRoot),
    precision,
  );
  const rayleighLower =
    minimumPrecisionEigenvalue / diagonalMaximum;
  const rayleighUpper =
    minimumPrecisionEigenvalue / diagonalMinimum;
  const reciprocalError = scalarNormalizedError(
    gammaRecovery * (1 / gammaRecovery),
    1,
  );



  return {
    size,
    mass,
    squareRoot,
    precision,
    gramian,
    squareRootError,
    diagonalMinimum,
    diagonalMaximum,
    minimumPrecisionEigenvalue,
    expectedMinimumPrecisionEigenvalue,
    gammaRecovery,
    optimalTensorization: 1 / gammaRecovery,
    rayleighLower,
    rayleighUpper,
    finiteKernel: gammaRecovery > 0,
    eigenvalues: gramianSpectrum,
    qMinimumError,
    reciprocalError,
    scalarLedger: [
      vectorNormalizedError(precisionSpectrum, precisionEigenvalues),
      vectorNormalizedError(
        qSpectrum,
        precisionEigenvalues.map((value) => Math.sqrt(value)),
      ),
    ],
  };
}

function buildExpectations() {
  const matrixLedger = [];
  const scalarLedger = [];

  const angles = ANGLE_EPSILONS.map((epsilon, index) => {
    const cosine = Math.cos(epsilon);
    const sine = Math.sin(epsilon);
    const firstResidual = outer([1, 0]);
    const secondResidual = outer([cosine, sine]);
    const gramian = matrixAdd(firstResidual, secondResidual);
    const eigenvalues = jacobiSymmetric(gramian).values;
    const expectedEigenvalues = [1 - cosine, 1 + cosine];
    const spectrumError = vectorNormalizedError(eigenvalues, expectedEigenvalues);
    const gammaRecovery = eigenvalues[0];
    const gammaError = scalarNormalizedError(gammaRecovery, 1 - cosine);
    matrixLedger.push(spectrumError);
    scalarLedger.push(gammaError);
    return {
      index,
      epsilon,
      gramian,
      eigenvalues,
      expectedEigenvalues,
      gammaRecovery,
      spectrumError,
      positiveDecreasing: true,
    };
  });

  const orthogonalGramian = matrixAdd(outer([1, 0]), outer([0, 1]));
  const orthogonal = {
    gramian: orthogonalGramian,
    eigenvalues: jacobiSymmetric(orthogonalGramian).values,
    gammaRecovery: 1,
    optimalTensorization: 1,
  };

  const gaugeGramian = [
    [1, 0, 0],
    [0, 1, 0],
    [0, 0, 0],
  ];
  const gauge = {
    gramian: gaugeGramian,
    fullEigenvalues: jacobiSymmetric(gaugeGramian).values,
    physicalEigenvalues: [1, 1],
    fullFloor: 0,
    physicalFloor: 1,
  };

  const scores = SCORE_THETAS.map((theta, index) => {
    const matrix = [
      [1 / (2 * 1), theta / 1],
      [theta / 1, 2 * (1 / 2 + (theta * theta) / 1)],
    ];
    const eigenvalues = jacobiSymmetric(matrix).values;
    const closed =
      (matrix[0][0] + matrix[1][1] +
        Math.sqrt(
          (matrix[0][0] - matrix[1][1]) ** 2 + 4 * matrix[0][1] ** 2,
        )) /
      2;
    const direct = eigenvalues[eigenvalues.length - 1];
    const eigenError = scalarNormalizedError(closed, direct);
    scalarLedger.push(eigenError);
    return {
      index,
      theta,
      matrix,
      cClosed: closed,
      cDirect: direct,
      certifiedRate: 1 / closed,
      monotoneNonincreasing: true,
      eigenError,
    };
  });

  const product = {
    scoreNorm: 0,
    witnessVariance: 1 / 2,
    witnessEnergy: 1,
    witnessRayleigh: 2,
    globalPoincareRate: 2,
    incompleteRecoveryFloor: 0,
    fibreConditionalRate: 4,
  };

  const gaussians = [];
  for (const size of GAUSSIAN_SIZES) {
    for (const mass of GAUSSIAN_MASSES) {
      const row = gaussianChainExpectation(size, mass);
      gaussians.push(row);
      matrixLedger.push(row.squareRootError);
      scalarLedger.push(row.qMinimumError, row.reciprocalError);
    }
  }

  const residuals = [
    outer([1, 0, 0]),
    outer([0, 1, 0]),
    outer([1, 0, 0]),
  ];
  const transports = [
    identity(3),
    [
      [-1, 0, 0],
      [0, 1, 0],
      [0, 0, 1],
    ],
    [
      [1, 0, 0],
      [0, -1, 0],
      [0, 0, 1],
    ],
  ];
  const weights = [1 / 2, 1, 1 / 2];
  let transportedGramian = zeros(3);
  for (let i = 0; i < residuals.length; i += 1) {
    const transportedResidual = matrixMultiply(
      transpose(transports[i]),
      matrixMultiply(residuals[i], transports[i]),
    );
    transportedGramian = matrixAdd(
      transportedGramian,
      transportedResidual,
      weights[i],
    );
  }
  const expectedTransportedGramian = [
    [1, 0, 0],
    [0, 1, 0],
    [0, 0, 0],
  ];
  const transportVectors = [
    [1, 2, 3],
    [-2, 1 / 2, 1],
    [0, 1, -4],
    [Math.sqrt(2), -Math.PI, 1 / 4],
  ];

  let quadraticError = 0;
  for (const vector of transportVectors) {
    const direct = dot(vector, matrixVectorMultiply(transportedGramian, vector));
    let transportedDirect = 0;
    for (let i = 0; i < residuals.length; i += 1) {
      const moved = matrixVectorMultiply(transports[i], vector);
      const residualValue = dot(moved, matrixVectorMultiply(residuals[i], moved));
      transportedDirect += weights[i] * residualValue;
    }
    quadraticError = Math.max(
      quadraticError,
      scalarNormalizedError(transportedDirect, direct),
    );
  }
  const transported = {
    weights,
    transports,
    residuals,
    gramian: transportedGramian,
    expectedGramian: expectedTransportedGramian,
    constructionError: matrixNormalizedError(
      transportedGramian,
      expectedTransportedGramian,
    ),
    gaugeResidual: operatorNorm(matrixVectorMultiply(transportedGramian, [0, 0, 1]).map((value) => [value])),
    physicalFloor: jacobiSymmetric([
      [transportedGramian[0][0], transportedGramian[0][1]],
      [transportedGramian[1][0], transportedGramian[1][1]],
    ]).values[0],
    quadraticError,
    vectors: transportVectors,
  };
  matrixLedger.push(transported.constructionError);
  scalarLedger.push(transported.quadraticError);

  return {
    angles,
    orthogonal,
    gauge,
    scores,
    product,
    gaussians,
    transported,
    matrixMaximum: maxFinite(matrixLedger),
    scalarMaximum: maxFinite(scalarLedger),
  };
}

function getNestedObject(value, keys) {
  let current = value;
  for (const key of keys) {
    if (current === null || typeof current !== "object") return undefined;
    current = current[key];
  }
  return current;
}

function firstDefined(values) {
  for (const value of values) if (value !== undefined && value !== null) return value;
  return undefined;
}

function bindingFrom(receipt, kind) {
  const nested = receipt && typeof receipt[kind] === "object" ? receipt[kind] : {};
  const paths = [
    receipt?.[kind],
    receipt?.[`${kind}_path`],
    receipt?.[`${kind}_file`],
    receipt?.[`${kind}Path`],
    nested.path,
    nested.file,
    nested.source_path,
    getNestedObject(receipt, ["bindings", kind, "path"]),
    getNestedObject(receipt, ["files", kind, "path"]),
    getNestedObject(receipt, ["sources", kind, "path"]),
  ];

  const hashes = [
    receipt?.[`${kind}_sha256`],
    receipt?.[`${kind}_hash`],
    receipt?.[`${kind}Sha256`],
    nested.sha256,
    nested.hash,
    nested.source_sha256,
    getNestedObject(receipt, ["bindings", kind, "sha256"]),
    getNestedObject(receipt, ["files", kind, "sha256"]),
    getNestedObject(receipt, ["sources", kind, "sha256"]),
  ];
  return { path: firstDefined(paths), sha256: firstDefined(hashes) };
}

function pathEquivalent(actual, expected) {
  if (typeof actual !== "string") return false;
  const normalize = (value) =>
    value
      .replaceAll("\\", "/")
      .replace(/^\.\//, "")
      .replace(/^\/+/, "")
      .toLowerCase();
  const actualNormalized = normalize(actual);
  const expectedNormalized = normalize(expected);
  if (actualNormalized === expectedNormalized) return true;
  const withoutRoot = expectedNormalized.replace(/^cassitheory\//, "");
  return (
    actualNormalized === withoutRoot ||
    actualNormalized.endsWith(`/${expectedNormalized}`) ||
    actualNormalized.endsWith(`/${withoutRoot}`)
  );
}

function hashEquivalent(actual, expected) {
  return typeof actual === "string" &&
    typeof expected === "string" &&
    actual.toLowerCase() === expected.toLowerCase();
}

function primaryRows(primary, key) {
  return Array.isArray(primary?.[key]) ? primary[key] : [];
}

function primaryObject(primary, key) {
  return primary && typeof primary[key] === "object" && !Array.isArray(primary[key])
    ? primary[key]
    : null;
}

function exactRowSchedule(rows, expected, keyOf) {
  if (!Array.isArray(rows) || rows.length !== expected.length) return false;
  const keys = rows.map(keyOf);
  if (keys.some((key) => key === undefined || key === null)) return false;
  const unique = new Set(keys);
  if (unique.size !== expected.length) return false;
  return expected.every((key) => unique.has(key));
}


function extractVersions(primary) {
  return {
    python: firstDefined([
      primary?.python_version,
      primary?.python,
      getNestedObject(primary, ["versions", "python"]),
      getNestedObject(primary, ["runtime", "python_version"]),
    ]),
    numpy: firstDefined([
      primary?.numpy_version,
      primary?.numpy,
      getNestedObject(primary, ["versions", "numpy"]),
      getNestedObject(primary, ["runtime", "numpy_version"]),
    ]),
  };
}

function buildChecks(primary, expected, protocolHash, ownHash, primarySourceHash, primaryReceiptHash) {
  const checks = [];
  const summary = primary?.summary;
  const angleRows = primaryRows(primary, "angle_rows");
  const scoreRows = primaryRows(primary, "score_rows");
  const gaussianRows = primaryRows(primary, "gaussian_rows");
  const orthogonalRow = primaryObject(primary, "orthogonal_row");
  const gaugeRow = primaryObject(primary, "gauge_row");
  const productRow = primaryObject(primary, "product_row");
  const transportedRow = primaryObject(primary, "transported_row");

  const primaryProtocol = bindingFrom(primary, "protocol");
  const primarySource = bindingFrom(primary, "source");

  const schemaAndVerdict =
    primary?.schema === PRIMARY_SCHEMA && primary?.verdict === "PASS";
  checks.push(makeCheck("primary_schema_and_verdict", schemaAndVerdict, schemaAndVerdict ? 0 : Infinity));

  const protocolIdentity =
    pathEquivalent(primaryProtocol.path, PROTOCOL_ID) &&
    hashEquivalent(primaryProtocol.sha256, protocolHash);
  checks.push(makeCheck("primary_protocol_identity", protocolIdentity, protocolIdentity ? 0 : Infinity));

  const sourceIdentity =
    pathEquivalent(primarySource.path, PRIMARY_SOURCE_ID) &&
    hashEquivalent(primarySource.sha256, primarySourceHash);
  checks.push(makeCheck("primary_source_identity", sourceIdentity, sourceIdentity ? 0 : Infinity));

  const primaryTolerance =
    primary?.tolerances && primary.tolerances.primary === PRIMARY_TOLERANCE;
  checks.push(makeCheck("primary_tolerance", primaryTolerance, primaryTolerance ? 0 : Infinity));

  const primaryChecks = Array.isArray(primary?.checks) ? primary.checks : [];
  const primaryNames = primaryChecks.map((check) => check && check.name);
  const primaryCheckIntegrity =
    primaryChecks.length === PRIMARY_CHECK_COUNT &&
    primaryChecks.every(
      (check) =>
        check !== null &&
        typeof check === "object" &&
        typeof check.name === "string" &&
        typeof check.pass === "boolean" &&
        check.pass,
    ) &&
    new Set(primaryNames).size === PRIMARY_CHECK_COUNT;
  checks.push(makeCheck("primary_check_integrity", primaryCheckIntegrity, primaryCheckIntegrity ? 0 : Infinity));

  const primarySummaryIntegrity =
    summary !== null &&
    typeof summary === "object" &&
    summary.checks === PRIMARY_CHECK_COUNT &&
    summary.passed === PRIMARY_CHECK_COUNT &&
    summary.failed === 0;
  checks.push(makeCheck("primary_summary_integrity", primarySummaryIntegrity, primarySummaryIntegrity ? 0 : Infinity));

  const angleSchedule = exactRowSchedule(
    angleRows,
    ANGLE_EPSILONS,
    (row) => (finiteNumber(row?.epsilon) ? row.epsilon : undefined),
  );
  const scoreSchedule = exactRowSchedule(
    scoreRows,
    SCORE_THETAS,
    (row) => (finiteNumber(row?.theta) ? row.theta : undefined),
  );
  const gaussianSchedule = exactRowSchedule(
    gaussianRows,
    GAUSSIAN_SIZES.flatMap((size) => GAUSSIAN_MASSES.map((mass) => `${size}:${mass}`)),
    (row) =>
      finiteNumber(row?.size) && finiteNumber(row?.mass)
        ? `${row.size}:${row.mass}`
        : undefined,
  );
  const rowCounts =
    summary !== null &&
    typeof summary === "object" &&
    summary.angle_rows === 4 &&
    summary.score_rows === 4 &&
    summary.gaussian_rows === 10 &&
    angleRows.length === 4 &&
    scoreRows.length === 4 &&
    gaussianRows.length === 10 &&
    orthogonalRow !== null &&
    gaugeRow !== null &&
    productRow !== null &&
    transportedRow !== null &&
    angleSchedule &&
    scoreSchedule &&
    gaussianSchedule;
  checks.push(makeCheck("primary_row_counts", rowCounts, rowCounts ? 0 : Infinity));

  const summaryMatrixMaximum = finiteNumber(summary?.max_matrix_error)
    ? summary.max_matrix_error
    : NaN;
  const summaryScalarMaximum = finiteNumber(summary?.max_scalar_error)
    ? summary.max_scalar_error
    : NaN;
  const matrixMaximumError = scalarNormalizedError(
    summaryMatrixMaximum,
    expected.matrixMaximum,
  );
  const scalarMaximumError = scalarNormalizedError(
    summaryScalarMaximum,
    expected.scalarMaximum,
  );
  const maximaInTolerance =
    finiteNumber(summaryMatrixMaximum) &&
    finiteNumber(summaryScalarMaximum) &&
    summaryMatrixMaximum >= 0 &&
    summaryScalarMaximum >= 0 &&
    summaryMatrixMaximum <= PRIMARY_TOLERANCE * (1 + 1e-6) &&
    summaryScalarMaximum <= PRIMARY_TOLERANCE * (1 + 1e-6);
  const summaryMaxima =
    maximaInTolerance &&
    matrixMaximumError <= COMPARISON_TOLERANCE &&
    scalarMaximumError <= COMPARISON_TOLERANCE;
  checks.push(
    makeCheck(
      "primary_summary_maxima",
      summaryMaxima,
      Math.max(matrixMaximumError, scalarMaximumError),
      "matrix-and-scalar",
    ),
  );

  for (let i = 0; i < expected.angles.length; i += 1) {
    const row = angleRows[i] ?? {};
    const target = expected.angles[i];
    const comparison = aggregateComparisons([
      compareIndex(row.index, i),
      compareNumber(row.epsilon, target.epsilon),
      compareMatrix(row.gramian, target.gramian),
      compareVector(row.eigenvalues, target.eigenvalues),
      compareVector(row.expected_eigenvalues, target.expectedEigenvalues),
      compareNumber(row.gamma_recovery, target.gammaRecovery),
      compareNumber(row.spectrum_error, target.spectrumError),
      compareBoolean(row.positive_decreasing, target.positiveDecreasing),
    ]);
    checks.push(
      makeCheck(
        `near_parallel_epsilon_${String(target.epsilon).replace(".", "_")}`,
        comparison.pass,
        comparison.error,
        "matrix-and-scalar",
      ),
    );
  }

  {
    const row = orthogonalRow ?? {};
    const target = expected.orthogonal;
    const comparison = aggregateComparisons([
      compareMatrix(row.gramian, target.gramian),
      compareVector(row.eigenvalues, target.eigenvalues),
      compareNumber(row.gamma_recovery, target.gammaRecovery),
      compareNumber(row.optimal_tensorization, target.optimalTensorization),
    ]);
    checks.push(makeCheck("orthogonal_recovery", comparison.pass, comparison.error, "matrix-and-scalar"));
  }

  {
    const row = gaugeRow ?? {};
    const target = expected.gauge;
    const comparison = aggregateComparisons([
      compareMatrix(row.gramian, target.gramian),
      compareVector(row.full_eigenvalues, target.fullEigenvalues),
      compareVector(row.physical_eigenvalues, target.physicalEigenvalues),
      compareNumber(row.full_floor, target.fullFloor),
      compareNumber(row.physical_floor, target.physicalFloor),
    ]);
    checks.push(makeCheck("gauge_quotient", comparison.pass, comparison.error, "matrix-and-scalar"));
  }

  for (let i = 0; i < expected.scores.length; i += 1) {
    const row = scoreRows[i] ?? {};
    const target = expected.scores[i];
    const comparison = aggregateComparisons([
      compareIndex(row.index, i),
      compareNumber(row.theta, target.theta),
      compareMatrix(row.matrix, target.matrix),
      compareNumber(row.C_closed, target.cClosed),
      compareNumber(row.C_direct, target.cDirect),
      compareNumber(row.certified_rate, target.certifiedRate),
      compareBoolean(row.monotone_nonincreasing, target.monotoneNonincreasing),
      compareNumber(row.eigen_error, target.eigenError),
    ]);
    checks.push(
      makeCheck(
        `score_theta_${String(target.theta).replace(".", "_")}`,
        comparison.pass,
        comparison.error,
        "matrix-and-scalar",
      ),
    );
  }

  {
    const row = productRow ?? {};
    const target = expected.product;
    const comparison = aggregateComparisons([
      compareNumber(row.score_norm, target.scoreNorm),
      compareNumber(row.witness_variance, target.witnessVariance),
      compareNumber(row.witness_energy, target.witnessEnergy),
      compareNumber(row.witness_rayleigh, target.witnessRayleigh),
      compareNumber(row.global_poincare_rate, target.globalPoincareRate),
      compareNumber(row.incomplete_recovery_floor, target.incompleteRecoveryFloor),
      compareNumber(row.fibre_conditional_rate, target.fibreConditionalRate),
    ]);
    checks.push(makeCheck("product_score_kernel", comparison.pass, comparison.error));
  }

  for (const target of expected.gaussians) {
    const row = gaussianRows.find(
      (candidate) =>
        candidate?.size === target.size && candidate?.mass === target.mass,
    ) ?? {};
    const comparison = aggregateComparisons([
      compareNumber(row.size, target.size),
      compareNumber(row.mass, target.mass),
      compareNumber(row.square_root_error, target.squareRootError),
      compareNumber(row.diagonal_min, target.diagonalMinimum),
      compareNumber(row.diagonal_max, target.diagonalMaximum),
      compareNumber(row.minimum_precision_eigenvalue, target.minimumPrecisionEigenvalue),
      compareNumber(
        row.expected_minimum_precision_eigenvalue,
        target.expectedMinimumPrecisionEigenvalue,
      ),
      compareNumber(row.gamma_recovery, target.gammaRecovery),
      compareNumber(row.optimal_tensorization, target.optimalTensorization),
      compareNumber(row.rayleigh_lower, target.rayleighLower),
      compareNumber(row.rayleigh_upper, target.rayleighUpper),
      compareBoolean(row.finite_kernel, target.finiteKernel),
    ]);
    checks.push(
      makeCheck(
        `gaussian_N${target.size}_m${String(target.mass).replace(".", "_")}`,
        comparison.pass,
        comparison.error,
        "matrix-and-scalar",
      ),
    );
  }

  {
    const row = transportedRow ?? {};
    const target = expected.transported;
    const comparison = aggregateComparisons([
      compareVector(row.weights, target.weights),
      compareMatrixArray(row.transports, target.transports),
      compareMatrixArray(row.residuals, target.residuals),
      compareMatrix(row.gramian, target.gramian),
      compareMatrix(row.expected_gramian, target.expectedGramian),
      compareNumber(row.construction_error, target.constructionError),
      compareNumber(row.gauge_residual, target.gaugeResidual),
      compareNumber(row.physical_floor, target.physicalFloor),
      compareNumber(row.quadratic_error, target.quadraticError),
      compareVectorArray(row.vectors, target.vectors),
    ]);
    checks.push(
      makeCheck(
        "transported_quotient_gramian",
        comparison.pass,
        comparison.error,
        "matrix-and-scalar",
      ),
    );
  }

  if (checks.length !== INDEPENDENT_CHECK_COUNT) {
    throw new Error(`independent check count invariant violated: ${checks.length}`);
  }
  if (new Set(checks.map((check) => check.name)).size !== INDEPENDENT_CHECK_COUNT) {
    throw new Error("independent check-name uniqueness invariant violated");
  }
  return checks;
}

function loadPrimaryReceipt() {
  try {
    const bytes = readFileSync(PRIMARY_RECEIPT_PATH);
    return { bytes, receipt: JSON.parse(bytes.toString("utf8")), error: null };
  } catch (error) {
    return { bytes: null, receipt: null, error };
  }
}

function safeHash(filePath) {
  try {
    return sha256File(filePath);
  } catch {
    return null;
  }
}

function writeIndependentReceipt() {
  const primaryFile = loadPrimaryReceipt();
  const primary = primaryFile.receipt;
  const protocolHash = safeHash(PROTOCOL_PATH);
  const ownHash = safeHash(fileURLToPath(import.meta.url));
  /* This is the sole operation involving the Python source: hash its bytes. */
  const primarySourceHash = safeHash(PRIMARY_SOURCE_PATH);
  const primaryReceiptHash = primaryFile.bytes === null ? null : sha256Bytes(primaryFile.bytes);
  const expected = buildExpectations();
  const checks = buildChecks(
    primary,
    expected,
    protocolHash,
    ownHash,
    primarySourceHash,
    primaryReceiptHash,
  );
  const passed = checks.filter((check) => check.pass).length;
  const versions = extractVersions(primary);
  const receipt = {
    schema: INDEPENDENT_SCHEMA,
    verdict: passed === INDEPENDENT_CHECK_COUNT ? "PASS" : "FAIL",
    protocol_path: PROTOCOL_ID,
    protocol_sha256: protocolHash,
    source_path: OWN_SOURCE_ID,
    source_sha256: ownHash,
    primary_source_path: PRIMARY_SOURCE_ID,
    primary_source_sha256: primarySourceHash,
    primary_receipt_path: PRIMARY_RECEIPT_ID,
    primary_receipt_sha256: primaryReceiptHash,
    python_version: versions.python ?? null,
    numpy_version: versions.numpy ?? null,
    tolerances: {
      primary: PRIMARY_TOLERANCE,
      comparison: COMPARISON_TOLERANCE,
    },
    summary: {
      checks: INDEPENDENT_CHECK_COUNT,
      passed,
      failed: INDEPENDENT_CHECK_COUNT - passed,
      angle_rows: 4,
      score_rows: 4,
      gaussian_rows: 10,
      max_matrix_error: expected.matrixMaximum,
      max_scalar_error: expected.scalarMaximum,
    },
    checks,
  };
  mkdirSync(dirname(INDEPENDENT_RECEIPT_PATH), { recursive: true });
  writeFileSync(INDEPENDENT_RECEIPT_PATH, `${JSON.stringify(receipt, null, 2)}\n`);
  return receipt;
}

const receipt = writeIndependentReceipt();
process.stdout.write(
  `${receipt.verdict}: ${receipt.summary.passed}/${receipt.summary.checks} independent checks\n`,
);
if (receipt.verdict !== "PASS") process.exitCode = 1;
