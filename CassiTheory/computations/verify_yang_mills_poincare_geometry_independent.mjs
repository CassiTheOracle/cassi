#!/usr/bin/env node

import { createHash } from "node:crypto";
import { readFileSync, mkdirSync, writeFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const SOURCE = fileURLToPath(import.meta.url);
const ROOT = dirname(dirname(SOURCE));
const PROTOCOL = join(ROOT, "computations", "yang-mills-poincare-geometry-prereg.md");
const PRIMARY_SOURCE = join(ROOT, "computations", "verify_yang_mills_poincare_geometry.py");
const OUT_DIR = join(ROOT, "runs", "yang_mills_poincare_geometry");
const PRIMARY_RECEIPT = join(OUT_DIR, "verification.json");
const OUT_PATH = join(OUT_DIR, "verification-independent.json");
const ALGEBRAIC_TOLERANCE = 1.0e-12;
const FINITE_DIFFERENCE_TOLERANCE = 5.0e-6;

const sha256 = (path) => createHash("sha256").update(readFileSync(path)).digest("hex");
const dot = (a, b) => a.reduce((sum, value, index) => sum + value * b[index], 0);
const norm2 = (a) => dot(a, a);
const add = (a, b) => a.map((value, index) => value + b[index]);
const sub = (a, b) => a.map((value, index) => value - b[index]);
const scale = (factor, a) => a.map((value) => factor * value);
const transpose = (matrix) => matrix[0].map((_, column) => matrix.map((row) => row[column]));
const matVec = (matrix, vector) => matrix.map((row) => dot(row, vector));

function rotation(q) {
  const [w, x, y, z] = q;
  return [
    [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
    [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
    [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
  ];
}

function largestEigenvalue(a, b, d) {
  const trace = a + d;
  const determinant = a * d - b * b;
  return 0.5 * (trace + Math.sqrt(Math.max(0, trace * trace - 4 * determinant)));
}

const primary = JSON.parse(readFileSync(PRIMARY_RECEIPT, "utf8"));
const algebraicTolerance = ALGEBRAIC_TOLERANCE;
const finiteDifferenceTolerance = FINITE_DIFFERENCE_TOLERANCE;
const checks = [];
function check(name, pass, details = {}) {
  checks.push({ name, pass: Boolean(pass), ...details });
}
function close(a, b, tolerance = algebraicTolerance) {
  return Math.abs(a - b) <= tolerance;
}

check("primary_schema", primary.schema === "cassi.yang-mills-poincare-geometry.verification.v1");
check("primary_verdict", primary.verdict === "PASS");
check("protocol_path", primary.protocol === "computations/yang-mills-poincare-geometry-prereg.md");
check("source_path", primary.source === "computations/verify_yang_mills_poincare_geometry.py");
check("protocol_hash", primary.protocol_sha256 === sha256(PROTOCOL));
check("primary_source_hash", primary.source_sha256 === sha256(PRIMARY_SOURCE));
check(
  "algebraic_tolerance",
  primary.tolerances?.algebraic === ALGEBRAIC_TOLERANCE,
  { recorded: primary.tolerances?.algebraic, expected: ALGEBRAIC_TOLERANCE },
);
check(
  "finite_difference_tolerance",
  primary.tolerances?.finite_difference === FINITE_DIFFERENCE_TOLERANCE,
  { recorded: primary.tolerances?.finite_difference, expected: FINITE_DIFFERENCE_TOLERANCE },
);
const primaryChecks = Array.isArray(primary.checks) ? primary.checks : [];
const primaryCheckNames = primaryChecks.map((item) => item.name);
check(
  "primary_check_array",
  primaryChecks.length === 118 &&
    primaryChecks.every((item) => item.pass === true && typeof item.name === "string") &&
    new Set(primaryCheckNames).size === primaryCheckNames.length,
);
check(
  "primary_summary_totals",
  primary.summary?.checks === 118 &&
    primary.summary?.passed === 118 &&
    primary.summary?.failed === 0,
);
check(
  "primary_summary_rows",
  primary.summary?.spectrum_rows === primary.spectrum_rows.length &&
    primary.summary?.link_character_rows === primary.link_character_rows.length &&
    primary.summary?.hessian_rows === primary.hessian_rows.length &&
    primary.summary?.geometry_rows === primary.geometry_rows.length &&
    primary.summary?.recurrence_rows === primary.recurrence_rows.length &&
    primary.summary?.scaling_rows === primary.scaling_rows.length &&
    primary.summary?.induction_rows === primary.induction_rows.length,
);
const primaryMaxima = {
  hessian: Math.max(...primary.hessian_rows.map((row) => Math.abs(row.abs_error))),
  energy: Math.max(
    ...primary.geometry_rows.map((row) => Math.abs(row.original_energy - row.reconstructed_energy)),
  ),
  orthogonality: Math.max(...primary.geometry_rows.map((row) => Math.abs(row.orthogonality))),
  recurrence: Math.max(...primary.recurrence_rows.map((row) => Math.abs(row.abs_error))),
};
check(
  "primary_summary_maxima",
  close(primary.summary?.max_hessian_abs_error, primaryMaxima.hessian) &&
    close(primary.summary?.max_energy_abs_error, primaryMaxima.energy) &&
    close(primary.summary?.max_orthogonality_abs_error, primaryMaxima.orthogonality) &&
    close(primary.summary?.max_recurrence_abs_error, primaryMaxima.recurrence),
  { recorded: primary.summary, reconstructed: primaryMaxima },
);
check("spectrum_row_count", primary.spectrum_rows.length === 12);
check("link_character_row_count", primary.link_character_rows.length === 5);
check("hessian_row_count", primary.hessian_rows.length === 18);
check("geometry_row_count", primary.geometry_rows.length === 8);
check("coordinate_row_count", primary.coordinate_rows.length === 8);
check("recurrence_row_count", primary.recurrence_rows.length === 8);
check("scaling_row_count", primary.scaling_rows.length === 3);
check("induction_row_count", primary.induction_rows.length === 6);

for (const [index, row] of primary.spectrum_rows.entries()) {
  const expected = ((row.k + 1) / row.radius) ** 2;
  check(`spectrum_${index}`, close(row.measured, expected) && close(row.expected, expected), {
    reconstructed: expected,
    recorded: row.measured,
  });
}
for (const [index, row] of primary.link_character_rows.entries()) {
  const expected = (row.n * (row.n + 2)) / 4;
  check(
    `link_character_${index}`,
    close(row.spin, row.n / 2) && close(row.measured, expected) && close(row.expected, expected),
    { reconstructed: expected, recorded: row.measured },
  );
}


for (const [index, row] of primary.hessian_rows.entries()) {
  const speed = Math.sqrt(norm2(row.v));
  const direction = scale(1 / speed, row.v);
  const qPlus = add(scale(Math.cos(speed * row.h), row.q), scale(Math.sin(speed * row.h), direction));
  const qMinus = add(scale(Math.cos(speed * row.h), row.q), scale(-Math.sin(speed * row.h), direction));
  const w0 = 1 - row.q[0];
  const measured = ((1 - qPlus[0]) + (1 - qMinus[0]) - 2 * w0) / (row.h * row.h);
  const casimirNorm2 = 4 * norm2(row.v);
  const expected = 0.25 * row.q[0] * casimirNorm2;
  const error = Math.abs(measured - expected);
  check(
    `hessian_${index}`,
    close(row.measured, measured, finiteDifferenceTolerance / 20) &&
      close(row.expected, expected) && close(row.casimir_norm2, casimirNorm2) &&
      error <= finiteDifferenceTolerance,
    { reconstructed: measured, expected, abs_error: error },
  );
}

for (const [index, row] of primary.geometry_rows.entries()) {
  const adjoint = rotation(row.q);
  const adjointInverse = transpose(adjoint);
  const adInvEta = matVec(adjointInverse, row.eta);
  const adInvZeta = matVec(adjointInverse, row.zeta);
  const h1 = scale(0.5, row.eta);
  const h2 = scale(0.5, adInvEta);
  const z1 = row.zeta;
  const z2 = scale(-1, adInvZeta);
  const horizontalNorm2 = norm2(h1) + norm2(h2);
  const verticalNorm2 = norm2(z1) + norm2(z2);
  const orthogonality = dot(h1, z1) + dot(h2, z2);
  const fixed1 = [0, 0, 0];
  const fixed2 = adInvEta;
  const connection1 = sub(fixed1, h1);
  const connection2 = sub(fixed2, h2);
  const expectedConnection1 = scale(-0.5, row.eta);
  const expectedConnection2 = scale(0.5, adInvEta);
  const connectionError = Math.sqrt(
    norm2(sub(connection1, expectedConnection1)) + norm2(sub(connection2, expectedConnection2)),
  );
  const adP2 = matVec(adjoint, row.p2);
  const gradH = scale(0.5, add(row.p1, adP2));
  const gradV = sub(row.p1, adP2);
  const originalEnergy = norm2(row.p1) + norm2(row.p2);
  const reconstructedEnergy = 2 * norm2(gradH) + 0.5 * norm2(gradV);
  check(
    `blocking_geometry_${index}`,
    close(horizontalNorm2, 0.5 * norm2(row.eta)) &&
      close(verticalNorm2, 2 * norm2(row.zeta)) &&
      Math.abs(orthogonality) <= algebraicTolerance &&
      connectionError <= algebraicTolerance &&
      close(originalEnergy, reconstructedEnergy),
    {
      horizontal_norm2: horizontalNorm2,
      vertical_norm2: verticalNorm2,
      orthogonality,
      connection_error: connectionError,
      original_energy: originalEnergy,
      reconstructed_energy: reconstructedEnergy,
    },
  );
}

const cMinus = 0.5 * (3 - Math.sqrt(5));
const cPlus = 0.5 * (3 + Math.sqrt(5));
check("c_minus", close(primary.constants.c_minus, cMinus));
check("c_plus", close(primary.constants.c_plus, cPlus));
for (const [index, row] of primary.coordinate_rows.entries()) {
  const euclidean = row.x * row.x + row.y * row.y;
  const quadratic = row.x * row.x - 2 * row.x * row.y + 2 * row.y * row.y;
  check(
    `coordinate_metric_${index}`,
    close(row.euclidean, euclidean) &&
      close(row.quadratic, quadratic) &&
      quadratic + algebraicTolerance >= cMinus * euclidean &&
      quadratic <= cPlus * euclidean + algebraicTolerance,
  );
}

for (const [index, row] of primary.recurrence_rows.entries()) {
  const a = 1 / (2 * row.lambda_c);
  const b = row.kappa / (row.lambda_c * Math.sqrt(row.lambda_fib));
  const d = (2 / row.lambda_fib) * (1 + (row.kappa * row.kappa) / row.lambda_c);
  const cStar = largestEigenvalue(a, b, d);
  const lowerBound = 1 / cStar;
  let zeroScorePass = true;
  if (row.kappa === 0) {
    zeroScorePass = close(lowerBound, Math.min(2 * row.lambda_c, row.lambda_fib / 2));
  }
  check(
    `recurrence_${index}`,
    close(row.A, a) && close(row.B, b) && close(row.D, d) &&
      close(row.C_star, cStar) && close(row.direct_C_star, cStar) &&
      close(row.lower_bound, lowerBound) && zeroScorePass,
    { reconstructed_C_star: cStar, reconstructed_lower_bound: lowerBound },
  );
}

for (const [index, row] of primary.scaling_rows.entries()) {
  const af = row.a_f;
  const ac = 2 * af;
  const gc = 2 * row.g_f;
  const rf = (2 * af * row.mass) / (row.g_f * row.g_f);
  const rc = (2 * ac * row.mass) / (gc * gc);
  check(
    `physical_scaling_${index}`,
    close(row.a_c, ac) && close(row.g_c, gc) && close(row.r_f, rf) &&
      close(row.r_c, rc) && close(rc, rf / 2),
  );
}

for (const [index, row] of primary.induction_rows.entries()) {
  const a = 1 / (2 * row.lambda_c);
  const b = row.kappa / (row.lambda_c * Math.sqrt(row.lambda_fib));
  const d = (2 / row.lambda_fib) * (1 + (row.kappa * row.kappa) / row.lambda_c);
  const cStar = largestEigenvalue(a, b, d);
  const threshold = 1 / row.r_f;
  const scalarPass =
    a <= threshold + algebraicTolerance &&
    d <= threshold + algebraicTolerance &&
    b * b <= (threshold - a) * (threshold - d) + algebraicTolerance;
  const eigenPass = cStar <= threshold + algebraicTolerance;
  check(
    `induction_${index}`,
    scalarPass === eigenPass && row.scalar_pass === scalarPass &&
      row.eigen_pass === eigenPass && row.expected === (scalarPass && eigenPass),
    { scalar_pass: scalarPass, eigen_pass: eigenPass, C_star: cStar, threshold },
  );
}

if (checks.length !== 90) {
  throw new Error(`independent check-count drift: expected 90, got ${checks.length}`);
}

const passed = checks.every((item) => item.pass);
const output = {
  schema: "cassi.yang-mills-poincare-geometry.verification-independent.v2",
  verdict: passed ? "PASS" : "FAIL",
  protocol: relative(ROOT, PROTOCOL).replaceAll("\\", "/"),
  protocol_sha256: sha256(PROTOCOL),
  source: relative(ROOT, SOURCE).replaceAll("\\", "/"),
  source_sha256: sha256(SOURCE),
  primary_source: relative(ROOT, PRIMARY_SOURCE).replaceAll("\\", "/"),
  primary_source_sha256: sha256(PRIMARY_SOURCE),
  primary_receipt: relative(ROOT, PRIMARY_RECEIPT).replaceAll("\\", "/"),
  primary_receipt_sha256: sha256(PRIMARY_RECEIPT),
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
