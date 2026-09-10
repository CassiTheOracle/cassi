#!/usr/bin/env bun
/**
 * Source-independent reconstruction for the v2 continuous-SU(2) radial
 * Feshbach campaign.
 *
 * Usage:
 *   bun computations/verify_yang_mills_radial_feshbach_v2_independent.mjs \
 *     --input <primary.json> --output <fresh-independent.json>
 *
 * The spectrum is reconstructed from the continuous-angle Dirichlet equation
 * for u(theta) on (0, pi), using two-sided Prüfer phase shooting.  The
 * measurement is continuous-angle and does not use a character-basis
 * spectral matrix.
 */

import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";

const SELF_PATH = path.resolve(fileURLToPath(import.meta.url));
const COMPUTATIONS_DIR = path.dirname(SELF_PATH);
const ROOT = path.dirname(COMPUTATIONS_DIR);

const PRIMARY_SCHEMA = "cassi.yang-mills.radial-feshbach.v2";
const RECEIPT_SCHEMA = "cassi.yang-mills.radial-feshbach.independent.v2";
const REJECTED_PRIMARY_SCHEMA = "cassi.yang-mills.radial-feshbach.v1";
const MANIFEST_SCHEMA = "cassi.yang-mills.radial-feshbach.inputs.v2";
const REJECTED_MANIFEST_SCHEMA = "cassi.yang-mills.radial-feshbach.inputs.v1";
const PROTOCOL_BASENAME = "yang-mills-radial-feshbach-v2-prereg.md";
const PRIMARY_BASENAME = "verify_yang_mills_radial_feshbach_v2.py";
const SELF_BASENAME = "verify_yang_mills_radial_feshbach_v2_independent.mjs";
const EXPECTED_PROTOCOL_SHA256 = "23da1a8972cfc0d268a438f0d99fa8a627c760b01c494f30ca260a3588bd2eca";
const IDENTITY_KEYS = ["protocol", "primary", "independent"];
const X_VALUES = [0.25, 1, 16, 256, 4096, 65536];
const LEVELS = [0, 1, 2];
const SCHEDULES = ["fixed", "C", "iso", "grow", "half"];
const ENERGY_LEVEL_COUNT = 3;
const DELTA_ISO = 1;

// The independent route is an adaptive scalar RK45 phase integration.  The
// comparison tolerance is deliberately stated separately from the phase
// integrator tolerances: it allows for a different discretization path while
// remaining far below the frozen weak-coupling landmark tolerances.
const ODE_RTOL = 2e-12;
const ODE_ATOL = 2e-13;
const COMPARISON_TOLERANCE = 5e-7;
const PRIMARY_TERMINAL_TOLERANCE = 1e-10;
const CF_RELATIVE_TOLERANCE = 1e-11;
const CF_DERIVATIVE_TOLERANCE = 1e-6;
const RF12_INEQUALITY_SLACK = 1e-11;
const RF20_SLACK = 1e-11;
const FESHBACH_RESIDUAL_TOLERANCE = 1e-9;
const CF_PRIMARY_COMPARISON_TOLERANCE = 1e-8;
const TAIL_NORM_TOLERANCE = 1e-8;
const LANDMARK_LEADING_TOLERANCE = 0.1;
const LANDMARK_SUBLEADING_TOLERANCE = 0.25;

class VerificationError extends Error {}

function isFiniteNumber(value) {
  return typeof value === "number" && Number.isFinite(value);
}

function relativeError(actual, expected) {
  if (!isFiniteNumber(actual) || !isFiniteNumber(expected)) {
    throw new VerificationError("relative error requires two finite numbers");
  }
  return Math.abs(actual - expected) / Math.max(Math.abs(actual), Math.abs(expected), Number.MIN_VALUE);
}

function normalizedError(actual, expected) {
  if (!isFiniteNumber(actual) || !isFiniteNumber(expected)) {
    throw new VerificationError("normalized error requires two finite numbers");
  }
  return Math.abs(actual - expected) / Math.max(1, Math.abs(actual), Math.abs(expected));
}

function allFinite(value, location = "value") {
  if (value === undefined) throw new VerificationError(`${location} is undefined`);
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new VerificationError(`${location} contains a non-finite number`);
    return;
  }
  if (Array.isArray(value)) {
    for (let i = 0; i < value.length; i += 1) allFinite(value[i], `${location}[${i}]`);
    return;
  }
  if (value !== null && typeof value === "object") {
    for (const [key, child] of Object.entries(value)) allFinite(child, `${location}.${key}`);
  }
}

function parseStringToken(text, index) {
  const start = index;
  if (text[index] !== '"') throw new VerificationError(`strict JSON: expected string at byte ${index}`);
  index += 1;
  while (index < text.length) {
    const ch = text[index];
    if (ch === "\\") {
      index += 2;
      continue;
    }
    if (ch === '"') {
      const raw = text.slice(start, index + 1);
      return { value: JSON.parse(raw), next: index + 1 };
    }
    if (ch.charCodeAt(0) < 0x20) throw new VerificationError(`strict JSON: control character in string at byte ${index}`);
    index += 1;
  }
  throw new VerificationError("strict JSON: unterminated string");
}

// JSON.parse already rejects malformed JSON and non-standard constants.  This
// small scanner additionally rejects duplicate object keys, which JSON.parse
// otherwise silently accepts and which would make a source-bound receipt
// ambiguous.
function rejectDuplicateKeys(text) {
  let index = 0;
  const skip = () => {
    while (index < text.length && /\s/.test(text[index])) index += 1;
  };
  const parseValue = () => {
    skip();
    const ch = text[index];
    if (ch === '"') {
      index = parseStringToken(text, index).next;
      return;
    }
    if (ch === "{") {
      index += 1;
      skip();
      const keys = new Set();
      if (text[index] === "}") {
        index += 1;
        return;
      }
      while (index < text.length) {
        skip();
        const token = parseStringToken(text, index);
        index = token.next;
        if (keys.has(token.value)) throw new VerificationError(`strict JSON: duplicate object key ${token.value}`);
        keys.add(token.value);
        skip();
        if (text[index] !== ":") throw new VerificationError(`strict JSON: expected ':' at byte ${index}`);
        index += 1;
        parseValue();
        skip();
        if (text[index] === "}") {
          index += 1;
          return;
        }
        if (text[index] !== ",") throw new VerificationError(`strict JSON: expected ',' at byte ${index}`);
        index += 1;
      }
      throw new VerificationError("strict JSON: unterminated object");
    }
    if (ch === "[") {
      index += 1;
      skip();
      if (text[index] === "]") {
        index += 1;
        return;
      }
      while (index < text.length) {
        parseValue();
        skip();
        if (text[index] === "]") {
          index += 1;
          return;
        }
        if (text[index] !== ",") throw new VerificationError(`strict JSON: expected ',' at byte ${index}`);
        index += 1;
      }
      throw new VerificationError("strict JSON: unterminated array");
    }
    const start = index;
    while (index < text.length && !/[\s,\]}]/.test(text[index])) index += 1;
    if (start === index) throw new VerificationError(`strict JSON: expected value at byte ${index}`);
  };
  parseValue();
  skip();
  if (index !== text.length) throw new VerificationError(`strict JSON: trailing data at byte ${index}`);
}

function readJsonStrict(file) {
  let text;
  try {
    text = fs.readFileSync(file, "utf8");
  } catch (error) {
    throw new VerificationError(`cannot read JSON input ${file}: ${error.message}`);
  }
  rejectDuplicateKeys(text);
  let value;
  try {
    value = JSON.parse(text);
  } catch (error) {
    throw new VerificationError(`invalid JSON in ${file}: ${error.message}`);
  }
  allFinite(value, file);
  return value;
}

function sha256File(file) {
  return crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
}

function resolveManifestPath(spec) {
  if (typeof spec !== "string" || !spec) return null;
  const normalized = spec.replaceAll("\\", "/");
  const candidates = [];
  if (path.isAbsolute(normalized)) candidates.push(normalized);
  else candidates.push(path.resolve(ROOT, normalized), path.resolve(ROOT, "..", normalized), path.resolve(process.cwd(), normalized));
  for (const candidate of candidates) {
    try {
      if (fs.statSync(candidate).isFile()) return path.resolve(candidate);
    } catch {
      // Keep trying the manifest's permitted roots.
    }
  }
  return null;
}

function expectedIdentityBasename(name) {
  if (name === "protocol") return PROTOCOL_BASENAME;
  if (name === "primary") return PRIMARY_BASENAME;
  if (name === "independent") return SELF_BASENAME;
  throw new VerificationError(`unknown identity ${name}`);
}

function validateIdentityMap(identities) {
  if (!identities || typeof identities !== "object" || Array.isArray(identities)) {
    throw new VerificationError("identities must be an object");
  }
  const keys = Object.keys(identities).sort();
  if (keys.join("\0") !== [...IDENTITY_KEYS].sort().join("\0")) {
    throw new VerificationError(`identities keys must be exactly ${IDENTITY_KEYS.join(", ")}`);
  }
  const result = {};
  const paths = new Set();
  for (const name of IDENTITY_KEYS) {
    const entry = identities[name];
    if (!entry || typeof entry !== "object" || Array.isArray(entry)) {
      throw new VerificationError(`identities.${name} must be an object`);
    }
    if (Object.keys(entry).sort().join("\0") !== "path\0sha256") {
      throw new VerificationError(`identities.${name} keys must be exactly path and sha256`);
    }
    if (typeof entry.path !== "string" || !entry.path) throw new VerificationError(`identities.${name}.path must be non-empty`);
    if (typeof entry.sha256 !== "string" || !/^[0-9a-f]{64}$/.test(entry.sha256)) {
      throw new VerificationError(`identities.${name}.sha256 must be lowercase hexadecimal SHA-256`);
    }
    if (path.basename(entry.path.replaceAll("\\", "/")) !== expectedIdentityBasename(name)) {
      throw new VerificationError(`identities.${name}.path must name ${expectedIdentityBasename(name)}`);
    }
    if (paths.has(entry.path)) throw new VerificationError("identity paths must be distinct");
    paths.add(entry.path);
    result[name] = { path: entry.path, sha256: entry.sha256 };
  }
  return result;
}

function bindSources(identities, inputPath) {
  const stem = path.basename(inputPath, path.extname(inputPath));
  const sourceDir = path.join(path.dirname(inputPath), `${stem}.sources`);
  const binding = {};
  const failures = [];
  for (const name of IDENTITY_KEYS) {
    const declared = identities[name];
    const entry = { declared_path: declared.path, manifest_sha256: declared.sha256 };
    const target = resolveManifestPath(declared.path);
    if (!target) {
      failures.push(`identity '${name}' path does not resolve to a file: ${declared.path}`);
      binding[name] = entry;
      continue;
    }
    entry.resolved_path = target;
    if (name === "independent" && target !== SELF_PATH) failures.push(`independent identity resolves to ${target}, not this source ${SELF_PATH}`);
    const snapshot = path.join(sourceDir, path.basename(target));
    entry.snapshot_path = snapshot;
    const live = sha256File(target);
    entry.live_sha256_at_bind = live;
    entry.snapshot_sha256 = null;
    try {
      if (fs.statSync(snapshot).isFile()) entry.snapshot_sha256 = sha256File(snapshot);
      else failures.push(`identity '${name}' frozen snapshot missing: ${snapshot}`);
    } catch {
      failures.push(`identity '${name}' frozen snapshot missing: ${snapshot}`);
    }
    if (declared.sha256 !== live) failures.push(`identity '${name}' manifest hash ${declared.sha256} != live hash ${live}`);
    if (entry.snapshot_sha256 !== null && entry.snapshot_sha256 !== live) {
      failures.push(`identity '${name}' live hash ${live} != snapshot hash ${entry.snapshot_sha256}`);
    }
    if (name === "protocol") {
      if (declared.sha256 !== EXPECTED_PROTOCOL_SHA256) failures.push(`protocol manifest hash ${declared.sha256} != frozen preregistration hash ${EXPECTED_PROTOCOL_SHA256}`);
      if (live !== EXPECTED_PROTOCOL_SHA256) failures.push(`protocol live hash ${live} != frozen preregistration hash ${EXPECTED_PROTOCOL_SHA256}`);
      if (entry.snapshot_sha256 !== null && entry.snapshot_sha256 !== EXPECTED_PROTOCOL_SHA256) failures.push(`protocol snapshot hash ${entry.snapshot_sha256} != frozen preregistration hash ${EXPECTED_PROTOCOL_SHA256}`);
    }
    binding[name] = entry;
  }
  return { binding, failures, sourceDir, stem };
}

function recheckSources(binding) {
  const failures = [];
  for (const name of IDENTITY_KEYS) {
    const entry = binding[name];
    if (!entry || !entry.resolved_path || !entry.live_sha256_at_bind || !entry.snapshot_path || !entry.snapshot_sha256) {
      failures.push(`identity '${name}' cannot be rechecked after binding`);
      continue;
    }
    try {
      const liveAfter = sha256File(entry.resolved_path);
      entry.live_sha256_at_check = liveAfter;
      if (liveAfter !== entry.live_sha256_at_bind) failures.push(`identity '${name}' live source changed during verification`);
    } catch (error) {
      failures.push(`identity '${name}' live source cannot be rechecked: ${error.message}`);
    }
    try {
      const snapshotAfter = sha256File(entry.snapshot_path);
      entry.snapshot_sha256_at_check = snapshotAfter;
      if (snapshotAfter !== entry.snapshot_sha256) failures.push(`identity '${name}' frozen snapshot changed during verification`);
    } catch (error) {
      failures.push(`identity '${name}' frozen snapshot cannot be rechecked: ${error.message}`);
    }
  }
  return failures;
}

function checkPassed(check) {
  return Boolean(check && typeof check === "object" && check.passed === true);
}

function validatePrimaryEnvelope(primary) {
  const failures = [];
  if (!primary || typeof primary !== "object" || Array.isArray(primary)) return ["primary receipt top level must be an object"];
  const required = ["schema", "status", "protocol", "identities", "inputs_manifest", "source_binding", "checks", "check_count", "failures", "symbolic_rows", "determinant_rows", "continued_fraction_rows", "direct_tail_rows", "bound_rows", "operator_bracket_rows", "derivative_rows", "resolvent_rows", "weak_coupling_rows", "reference_eigenvector_rows", "spectrum_rows", "cutoff_rows", "feshbach_rows", "classifications", "scope", "measured_summary"];
  for (const key of required) if (!(key in primary)) failures.push(`primary receipt missing required key '${key}'`);
  if (primary.schema === REJECTED_PRIMARY_SCHEMA) failures.push(`v1 primary schema ${REJECTED_PRIMARY_SCHEMA} is rejected by the v2 verifier`);
  else if (primary.schema !== PRIMARY_SCHEMA) failures.push(`primary.schema must be ${PRIMARY_SCHEMA}`);
  if (primary.status !== "PASS") failures.push(`primary.status must be PASS, got ${String(primary.status)}`);
  if (!primary.protocol || typeof primary.protocol !== "object" || Array.isArray(primary.protocol)) {
    failures.push("primary.protocol must be an object");
  } else {
    if (primary.protocol.schema !== PRIMARY_SCHEMA) failures.push(`primary.protocol.schema must be ${PRIMARY_SCHEMA}`);
    if (primary.protocol.expected_protocol_sha256 !== EXPECTED_PROTOCOL_SHA256) failures.push("primary.protocol must bind the frozen v2 preregistration SHA-256");
    const amendment = primary.protocol.finite_dimension_amendment;
    if (!amendment || amendment.minimum_scheduled_cutoff !== 2 || amendment.requested_ritz_values !== 3 || amendment.accepts_v1_receipts !== false) {
      failures.push("primary.protocol must declare the v2 finite-dimension amendment");
    }
  }
  if (primary.identities && typeof primary.identities === "object" && !Array.isArray(primary.identities)) {
    for (const name of IDENTITY_KEYS) {
      const declaredPath = primary.identities?.[name]?.path;
      if (typeof declaredPath !== "string" || path.basename(declaredPath.replaceAll("\\", "/")) !== expectedIdentityBasename(name)) {
        failures.push(`primary.identities.${name}.path must name ${expectedIdentityBasename(name)}`);
      }
    }
  }
  if (!primary.inputs_manifest || typeof primary.inputs_manifest !== "object" || Array.isArray(primary.inputs_manifest)) {
    failures.push("primary.inputs_manifest must be an object");
  } else {
    if (primary.inputs_manifest.schema === REJECTED_MANIFEST_SCHEMA) failures.push(`v1 manifest schema ${REJECTED_MANIFEST_SCHEMA} is rejected by the v2 verifier`);
    else if (primary.inputs_manifest.schema !== MANIFEST_SCHEMA) failures.push("primary.inputs_manifest schema mismatch");
    if (typeof primary.inputs_manifest.path !== "string" || !primary.inputs_manifest.path) failures.push("primary.inputs_manifest.path must be non-empty");
    if (typeof primary.inputs_manifest.sha256 !== "string" || !/^[0-9a-f]{64}$/.test(primary.inputs_manifest.sha256)) failures.push("primary.inputs_manifest.sha256 must be lowercase SHA-256");
  }
  if (!primary.source_binding || typeof primary.source_binding !== "object" || Array.isArray(primary.source_binding)) failures.push("primary.source_binding must be an object");
  if (!Array.isArray(primary.failures) || primary.failures.length !== 0) failures.push("primary.failures must be an empty array for a usable receipt");
  if (!Array.isArray(primary.checks) || primary.checks.length === 0 || primary.checks.some((c) => !checkPassed(c))) failures.push("every primary check must have passed == true");
  if (!Number.isInteger(primary.check_count) || !Array.isArray(primary.checks) || primary.check_count !== primary.checks.length) failures.push("primary.check_count must equal primary.checks.length");
  for (const key of ["symbolic_rows", "determinant_rows", "continued_fraction_rows", "direct_tail_rows", "bound_rows", "operator_bracket_rows", "derivative_rows", "resolvent_rows", "weak_coupling_rows", "reference_eigenvector_rows", "spectrum_rows", "cutoff_rows", "feshbach_rows"]) {
    if (!Array.isArray(primary[key]) || primary[key].length === 0) failures.push(`primary.${key} must be a non-empty array`);
  }
  for (const key of ["classifications", "scope", "measured_summary"]) {
    if (!primary[key] || typeof primary[key] !== "object" || Array.isArray(primary[key])) failures.push(`primary.${key} must be an object`);
  }
  for (const key of ["interacting_refined_fibre", "volume_uniform_resolvent", "thermodynamic_limit", "continuum_mass_gap", "cassi_microscopic_identification"]) {
    if (primary.classifications?.[key] !== "UNRESOLVED") failures.push(`primary.classifications.${key} must remain UNRESOLVED`);
  }
  for (const key of ["neighboring_plaquettes", "interacting_lattice_block", "volume_uniform_estimate", "thermodynamic_limit", "continuum_limit", "continuum_mass_gap", "cassi_microscopic_claim"]) {
    if (primary.scope?.[key] !== "UNRESOLVED") failures.push(`primary.scope.${key} must remain UNRESOLVED`);
  }
  return failures;
}

function xKey(x) {
  return String(Number(x));
}

function expectedSchedules(x) {
  const q = Math.pow(x, 0.25);
  return { fixed: 8, C: Math.max(2, Math.ceil(2 * q)), iso: Math.max(2, Math.ceil(4 * q)), grow: Math.max(2, Math.ceil(q * Math.log(2 + x))), half: Math.max(2, Math.ceil(2 * Math.sqrt(x))) };
}

function expectedReference(x, reference) {
  const schedule = expectedSchedules(x);
  return reference === "M_ref" ? Math.max(512, 4 * schedule.half) : 2 * Math.max(512, 4 * schedule.half);
}

function validateSpectrumRows(rows) {
  const failures = [];
  const map = new Map();
  if (!Array.isArray(rows)) return { failures: ["primary.spectrum_rows must be an array"], map };
  if (rows.length !== X_VALUES.length * 2) failures.push(`primary.spectrum_rows must contain exactly ${X_VALUES.length * 2} rows`);
  rows.forEach((row, index) => {
    if (!row || typeof row !== "object" || Array.isArray(row)) {
      failures.push(`spectrum_rows[${index}] must be an object`);
      return;
    }
    if (!isFiniteNumber(row.x) || !X_VALUES.includes(row.x)) failures.push(`spectrum_rows[${index}].x is not one frozen x value`);
    if (!Number.isInteger(row.terminal) || ![expectedReference(row.x, "M_ref"), expectedReference(row.x, "2M_ref")].includes(row.terminal)) failures.push(`spectrum_rows[${index}].terminal is not the declared terminal index`);
    if (row.reference !== "M_ref" && row.reference !== "2M_ref") failures.push(`spectrum_rows[${index}].reference must be M_ref or 2M_ref`);
    if (isFiniteNumber(row.x) && (row.reference === "M_ref" || row.reference === "2M_ref") && row.terminal !== expectedReference(row.x, row.reference)) failures.push(`spectrum_rows[${index}] terminal/reference mismatch`);
    if (!Array.isArray(row.eigenvalues) || row.eigenvalues.length !== ENERGY_LEVEL_COUNT || row.eigenvalues.some((v) => !isFiniteNumber(v))) failures.push(`spectrum_rows[${index}].eigenvalues must contain three finite values`);
    if (isFiniteNumber(row.x) && (row.reference === "M_ref" || row.reference === "2M_ref")) {
      const key = `${xKey(row.x)}|${row.reference}`;
      if (map.has(key)) failures.push(`duplicate spectrum row ${key}`);
      else map.set(key, row);
    }
  });
  for (const x of X_VALUES) for (const reference of ["M_ref", "2M_ref"]) {
    const key = `${xKey(x)}|${reference}`;
    if (!map.has(key)) failures.push(`missing spectrum row ${key}`);
  }
  return { failures, map };
}


function validateCutoffRows(rows) {
  const failures = [];
  const map = new Map();
  const reconstructionRows = [];
  if (!Array.isArray(rows)) return { failures: ["primary.cutoff_rows must be an array"], map, reconstructionRows };
  if (rows.length !== X_VALUES.length * SCHEDULES.length) failures.push(`primary.cutoff_rows must contain exactly ${X_VALUES.length * SCHEDULES.length} rows`);
  rows.forEach((row, index) => {
    if (!row || typeof row !== "object" || Array.isArray(row)) {
      failures.push(`cutoff_rows[${index}] must be an object`);
      return;
    }
    const schedule = row.schedule;
    if (!isFiniteNumber(row.x) || !X_VALUES.includes(row.x)) failures.push(`cutoff_rows[${index}].x is not frozen`);
    if (!SCHEDULES.includes(schedule)) failures.push(`cutoff_rows[${index}].schedule is not frozen`);
    if (isFiniteNumber(row.x) && SCHEDULES.includes(schedule)) {
      const key = `${xKey(row.x)}|${schedule}`;
      const expected = expectedSchedules(row.x)[schedule];
      if (!Number.isInteger(row.cutoff) || row.cutoff !== expected) failures.push(`cutoff_rows[${index}] cutoff mismatch for ${key}`);
      if (!Number.isInteger(row.cutoff) || row.cutoff < ENERGY_LEVEL_COUNT - 1) failures.push(`cutoff_rows[${index}] cannot contain ${ENERGY_LEVEL_COUNT} Ritz values`);
      if (map.has(key)) failures.push(`duplicate cutoff row ${key}`);
      else map.set(key, row);
    }
    if (!Array.isArray(row.eigenvalues) || row.eigenvalues.length !== 3 || row.eigenvalues.some((v) => !isFiniteNumber(v))) failures.push(`cutoff_rows[${index}].eigenvalues must contain three finite values`);
    if (!Array.isArray(row.relative_errors) || row.relative_errors.length !== 3 || row.relative_errors.some((v) => !isFiniteNumber(v) || v < 0)) failures.push(`cutoff_rows[${index}].relative_errors must contain three nonnegative finite values`);
    if (!isFiniteNumber(row.ratio_N_x_quarter) || !isFiniteNumber(row.lower_bound)) failures.push(`cutoff_rows[${index}] missing finite ratio_N_x_quarter/lower_bound`);
    const retained = row.retained_probabilities;
    const discarded = row.discarded_probabilities;
    const boundary = row.boundary_residuals;
    const massIdentity = row.mass_identity_errors;
    if (!Array.isArray(retained) || retained.length !== 3 || retained.some((v) => !isFiniteNumber(v))) failures.push(`cutoff_rows[${index}] missing three retained-mode metrics`);
    if (!Array.isArray(discarded) || discarded.length !== 3 || discarded.some((v) => !isFiniteNumber(v))) failures.push(`cutoff_rows[${index}] missing three discarded-mode metrics`);
    if (!Array.isArray(boundary) || boundary.length !== 3 || boundary.some((v) => !isFiniteNumber(v))) failures.push(`cutoff_rows[${index}] missing three boundary-mode metrics`);
    if (!Array.isArray(massIdentity) || massIdentity.length !== 3 || massIdentity.some((v) => !isFiniteNumber(v) || v < 0)) failures.push(`cutoff_rows[${index}] missing three nonnegative mass_identity_errors`);
    if (row.pass !== true) failures.push(`cutoff_rows[${index}].pass must be true`);
    if (isFiniteNumber(row.x) && X_VALUES.includes(row.x) && SCHEDULES.includes(schedule) && Number.isInteger(row.cutoff) && row.cutoff === expectedSchedules(row.x)[schedule] && row.cutoff >= ENERGY_LEVEL_COUNT - 1 && Array.isArray(row.eigenvalues) && row.eigenvalues.length === ENERGY_LEVEL_COUNT && row.eigenvalues.every(isFiniteNumber)) {
      const expectedRatio = row.cutoff / Math.pow(row.x, 0.25);
      const expectedLower = 4 * row.x * Math.pow(Math.sin(Math.PI / (2 * (row.cutoff + 2))), 2);
      const independentEigenvalues = finiteSectionEigenvalues(row.x, row.cutoff, ENERGY_LEVEL_COUNT);
      const eigenvalueErrors = independentEigenvalues.map((value, j) => relativeError(value, row.eigenvalues[j]));
      const ratioError = relativeError(row.ratio_N_x_quarter, expectedRatio);
      const lowerFormulaError = relativeError(row.lower_bound, expectedLower);
      const lowerBoundPass = independentEigenvalues[0] + RF20_SLACK * Math.max(1, Math.abs(expectedLower)) >= expectedLower;
      const primaryLowerBoundPass = row.eigenvalues[0] + RF20_SLACK * Math.max(1, Math.abs(row.lower_bound)) >= row.lower_bound;
      const reconstructionPass = eigenvalueErrors.every((error) => error < COMPARISON_TOLERANCE) && ratioError < 1e-12 && lowerFormulaError < 1e-12 && lowerBoundPass && primaryLowerBoundPass;
      reconstructionRows.push({ x: row.x, schedule, cutoff: row.cutoff, eigenvalues: independentEigenvalues, primary_eigenvalues: row.eigenvalues, eigenvalue_relative_errors: eigenvalueErrors, ratio_N_x_quarter: expectedRatio, primary_ratio_relative_error: ratioError, lower_bound_RF20: expectedLower, primary_lower_bound_relative_error: lowerFormulaError, lower_bound_slack: independentEigenvalues[0] - expectedLower, primary_lower_bound_slack: row.eigenvalues[0] - row.lower_bound, tolerance: RF20_SLACK, pass: reconstructionPass });
      if (!reconstructionPass) failures.push(`cutoff_rows[${index}] independent finite-section/RF20 reconstruction failed`);
    }
  });
  for (const x of X_VALUES) for (const schedule of SCHEDULES) {
    const key = `${xKey(x)}|${schedule}`;
    if (!map.has(key)) failures.push(`missing cutoff row ${key}`);
  }
  if (reconstructionRows.length !== X_VALUES.length * SCHEDULES.length) failures.push(`cutoff reconstruction has ${reconstructionRows.length} rows; expected ${X_VALUES.length * SCHEDULES.length}`);
  return { failures, map, reconstructionRows };
}


function validateFeshbachRows(rows) {
  const failures = [];
  const map = new Map();
  if (!Array.isArray(rows)) return { failures: ["primary.feshbach_rows must be an array"], map };
  if (rows.length !== 6) failures.push("primary.feshbach_rows must contain exactly six rows");
  rows.forEach((row, index) => {
    if (!row || typeof row !== "object" || Array.isArray(row)) {
      failures.push(`feshbach_rows[${index}] must be an object`);
      return;
    }
    if (!isFiniteNumber(row.x) || ![4096, 65536].includes(row.x)) failures.push(`feshbach_rows[${index}].x must be 4096 or 65536`);
    if (!Number.isInteger(row.j) || !LEVELS.includes(row.j)) failures.push(`feshbach_rows[${index}].j must be 0, 1, or 2`);
    if (isFiniteNumber(row.x) && Number.isInteger(row.j) && [4096, 65536].includes(row.x) && LEVELS.includes(row.j)) {
      const key = `${xKey(row.x)}|${row.j}`;
      if (map.has(key)) failures.push(`duplicate feshbach row ${key}`);
      else map.set(key, row);
      const expected = expectedSchedules(row.x).iso;
      if (!Number.isInteger(row.cutoff) || row.cutoff !== expected) failures.push(`feshbach row ${key} cutoff is not N_iso=${expected}`);
    }
    const required = [
      ["eigenvalue", row.eigenvalue],
      ["k_tail", row.k_tail],
      ["isolation_margin", row.isolation_margin],
      ["feshbach_normalized_residual", row.feshbach_normalized_residual],
      ["full_residual", row.full_residual],
      ["tail_norm_sq_direct", row.tail_norm_sq_direct],
      ["tail_norm_sq_formula", row.tail_norm_sq_formula],
      ["tail_norm_sq_relative_error", row.tail_norm_sq_relative_error],
      ["reference_tail_norm_sq", row.reference_tail_norm_sq],
      ["reference_tail_relative_error", row.reference_tail_relative_error],
      ["tail_operator_margin", row.tail_operator_margin],
      ["m", row.m],
      ["m_prime", row.m_prime],
    ];
    for (const [label, value] of required) if (!isFiniteNumber(value)) failures.push(`feshbach_rows[${index}] missing finite ${label}`);
    if (row.pass !== true) failures.push(`feshbach_rows[${index}].pass must be true`);
    if (row.pole_free !== true) failures.push(`feshbach_rows[${index}].pole_free must be true`);
    if (isFiniteNumber(row.isolation_margin) && !(row.isolation_margin > 0)) failures.push(`feshbach_rows[${index}].isolation_margin must be positive`);
    if (!isFiniteNumber(row.tail_operator_margin) || row.tail_operator_margin < -RF12_INEQUALITY_SLACK) failures.push(`feshbach_rows[${index}].tail_operator_margin violates RF21c`);
    if (isFiniteNumber(row.x) && Number.isInteger(row.cutoff) && isFiniteNumber(row.k_tail) && row.k_tail !== kValue(row.cutoff + 1)) failures.push(`feshbach_rows[${index}].k_tail does not match cutoff`);
    if (isFiniteNumber(row.x) && (!Number.isInteger(row.terminal) || row.terminal !== expectedReference(row.x, "2M_ref"))) failures.push(`feshbach_rows[${index}].terminal is not 2M_ref`);
    if (isFiniteNumber(row.m) && !(row.m > 0)) failures.push(`feshbach_rows[${index}].m must be positive`);
    if (isFiniteNumber(row.m_prime) && !(row.m_prime > 0)) failures.push(`feshbach_rows[${index}].m_prime must be positive`);
    if (isFiniteNumber(row.feshbach_normalized_residual) && !(row.feshbach_normalized_residual < FESHBACH_RESIDUAL_TOLERANCE)) failures.push(`feshbach_rows[${index}].feshbach_normalized_residual is not below ${FESHBACH_RESIDUAL_TOLERANCE}`);
    if (isFiniteNumber(row.full_residual) && !(row.full_residual < FESHBACH_RESIDUAL_TOLERANCE)) failures.push(`feshbach_rows[${index}].full_residual is not below ${FESHBACH_RESIDUAL_TOLERANCE}`);
    if (isFiniteNumber(row.tail_norm_sq_relative_error) && !(row.tail_norm_sq_relative_error < TAIL_NORM_TOLERANCE)) failures.push(`feshbach_rows[${index}].tail_norm_sq_relative_error is not below ${TAIL_NORM_TOLERANCE}`);
    if (isFiniteNumber(row.reference_tail_relative_error) && !(row.reference_tail_relative_error < TAIL_NORM_TOLERANCE)) failures.push(`feshbach_rows[${index}].reference_tail_relative_error is not below ${TAIL_NORM_TOLERANCE}`);
  });
  for (const x of [4096, 65536]) for (const j of LEVELS) {
    const key = `${xKey(x)}|${j}`;
    if (!map.has(key)) failures.push(`missing feshbach row ${key}`);
  }
  return { failures, map };
}

function expectedContinuedFractionKeys() {
  const expectedKeys = new Set();
  for (const x of X_VALUES) {
    const schedule = expectedSchedules(x);
    const ns = [...new Set([0, 1, 3, 7, ...Object.values(schedule)])];
    for (const n of ns) for (const energy of [...new Set([-1, -Math.sqrt(x), 0])]) expectedKeys.add(`${xKey(x)}|${n}|${energy}`);
  }
  return expectedKeys;
}

function validateContinuedFractionRows(rows) {
  const failures = [];
  const map = new Map();
  const expectedKeys = expectedContinuedFractionKeys();
  if (!Array.isArray(rows)) return { failures: ["primary.continued_fraction_rows must be an array"], map };
  if (rows.length !== expectedKeys.size) failures.push(`primary.continued_fraction_rows must contain exactly ${expectedKeys.size} unique rows`);
  rows.forEach((row, index) => {
    if (!row || typeof row !== "object" || Array.isArray(row)) {
      failures.push(`continued_fraction_rows[${index}] must be an object`);
      return;
    }
    if (!isFiniteNumber(row.x) || !X_VALUES.includes(row.x)) failures.push(`continued_fraction_rows[${index}].x is not frozen`);
    if (!Number.isInteger(row.N)) failures.push(`continued_fraction_rows[${index}].N must be an integer`);
    if (!isFiniteNumber(row.E)) failures.push(`continued_fraction_rows[${index}].E must be finite`);
    if (isFiniteNumber(row.x) && Number.isInteger(row.N) && isFiniteNumber(row.E)) {
      const allowedN = [0, 1, 3, 7, ...Object.values(expectedSchedules(row.x))];
      if (!allowedN.includes(row.N)) failures.push(`continued_fraction_rows[${index}] N=${row.N} is not in the frozen N inventory`);
      const energyMatches = [-1, -Math.sqrt(row.x), 0].some((value) => Math.abs(value - row.E) <= 1e-13 * Math.max(1, Math.abs(value)));
      if (!energyMatches) failures.push(`continued_fraction_rows[${index}] E=${row.E} is not in the frozen E inventory`);
      const key = `${xKey(row.x)}|${row.N}|${row.E}`;
      if (map.has(key)) failures.push(`duplicate continued-fraction row ${key}`);
      else map.set(key, row);
    }
    for (const [label, value] of [["m", row.m], ["m_prime", row.m_prime], ["sigma", row.sigma], ["lower_bound", row.lower_bound], ["upper_bound", row.upper_bound], ["reference_relative_error", row.reference_relative_error]]) {
      if (!isFiniteNumber(value)) failures.push(`continued_fraction_rows[${index}] missing finite ${label}`);
    }
    if (!row.direct_normalized_errors || typeof row.direct_normalized_errors !== "object" || Array.isArray(row.direct_normalized_errors)) {
      failures.push(`continued_fraction_rows[${index}].direct_normalized_errors must be an object`);
    } else {
      if (Object.keys(row.direct_normalized_errors).sort().join("|") !== "32|64") failures.push(`continued_fraction_rows[${index}].direct_normalized_errors keys must be exactly 32 and 64`);
      for (const label of ["32", "64"]) if (!isFiniteNumber(row.direct_normalized_errors[label]) || row.direct_normalized_errors[label] < 0) failures.push(`continued_fraction_rows[${index}].direct_normalized_errors.${label} must be finite and nonnegative`);
    }
  });
  for (const key of expectedKeys) if (!map.has(key)) failures.push(`missing continued-fraction row ${key}`);
  return { failures, map };
}
function auxiliaryKey(name, row) {
  if (["bound_rows", "operator_bracket_rows", "derivative_rows"].includes(name)) {
    if (!isFiniteNumber(row.x) || !Number.isInteger(row.N) || !isFiniteNumber(row.E)) return null;
    return `${xKey(row.x)}|${row.N}|${row.E}`;
  }
  if (name === "weak_coupling_rows") return isFiniteNumber(row.x) && Number.isInteger(row.j) ? `${xKey(row.x)}|${row.j}` : null;
  if (name === "reference_eigenvector_rows") return isFiniteNumber(row.x) && Number.isInteger(row.j) ? `${xKey(row.x)}|${row.j}` : null;
  if (name === "direct_tail_rows") {
    if (!isFiniteNumber(row.x) || !Number.isInteger(row.N) || !isFiniteNumber(row.E) || !Number.isInteger(row.L)) return null;
    return `${xKey(row.x)}|${row.N}|${row.E}|${row.L}`;
  }
  if (name === "resolvent_rows") {
    if (!isFiniteNumber(row.x) || !Number.isInteger(row.N) || !isFiniteNumber(row.eta)) return null;
    return `${xKey(row.x)}|${row.N}|${row.eta}`;
  }
  return JSON.stringify(row, Object.keys(row).sort());
}
function validateAuxiliaryRows(name, rows, expectedCount) {
  const failures = [];
  if (!Array.isArray(rows)) return [`primary.${name} must be an array`];
  if (rows.length !== expectedCount) failures.push(`primary.${name} must contain exactly ${expectedCount} rows`);
  const seen = new Set();
  rows.forEach((row, index) => {
    if (!row || typeof row !== "object" || Array.isArray(row)) {
      failures.push(`primary.${name}[${index}] must be an object`);
      return;
    }
    const key = auxiliaryKey(name, row);
    if (key === null) failures.push(`primary.${name}[${index}] missing frozen key fields`);
    else if (seen.has(key)) failures.push(`primary.${name} contains duplicate key ${key}`);
    else seen.add(key);
    if ("pass" in row && row.pass !== true) failures.push(`primary.${name}[${index}].pass must be true`);
    if ("passed" in row && row.passed !== true) failures.push(`primary.${name}[${index}].passed must be true`);
    if (name === "resolvent_rows") {
      if (![0.25, 1, 16].includes(row.x) || ![0, 2, 5].includes(row.N)) failures.push(`primary.${name}[${index}] has an unfrozen x/N key`);
      const allowedEta = [...new Set([1, Math.sqrt(row.x)])];
      if (!allowedEta.includes(row.eta)) failures.push(`primary.${name}[${index}].eta is not in the frozen set`);
      for (const field of ["P_block_norm", "P_bound_RF13", "Q_block_norm", "Q_bound_RF14"]) {
        if (!isFiniteNumber(row[field])) failures.push(`primary.${name}[${index}] missing finite ${field}`);
      }
      if (row.RF13_pass !== true || row.RF14_pass !== true) failures.push(`primary.${name}[${index}] must pass RF13 and RF14`);
    }
    if (name === "weak_coupling_rows") {
      if (![4096, 65536].includes(row.x) || !LEVELS.includes(row.j)) failures.push(`primary.${name}[${index}] has an unfrozen x/j key`);
      if (!isFiniteNumber(row.eigenvalue) || !isFiniteNumber(row.leading_error) || row.leading_pass !== true) failures.push(`primary.${name}[${index}] must contain a passing finite leading landmark`);
      if (row.x === 65536 && (!isFiniteNumber(row.subleading_error) || row.subleading_pass !== true)) failures.push(`primary.${name}[${index}] must contain a passing finite subleading landmark`);
    }
    if (name === "direct_tail_rows") {
      if (!Number.isInteger(row.L) || ![32, 64].includes(row.L)) failures.push(`primary.${name}[${index}].L must be 32 or 64`);
      if (!Number.isInteger(row.M) || row.M !== row.N + row.L) failures.push(`primary.${name}[${index}].M must equal N+L`);
      if (!Number.isInteger(row.terminal) || row.terminal !== row.M) failures.push(`primary.${name}[${index}].terminal must equal M`);
      if (!isFiniteNumber(row.normalized_discrepancy) || row.normalized_discrepancy < 0 || row.normalized_discrepancy >= CF_RELATIVE_TOLERANCE) failures.push(`primary.${name}[${index}].normalized_discrepancy must be finite and below ${CF_RELATIVE_TOLERANCE}`);
      for (const field of ["m_continued_fraction", "m_direct_tail_solve"]) if (!isFiniteNumber(row[field])) failures.push(`primary.${name}[${index}] missing finite ${field}`);
      if (isFiniteNumber(row.x) && Number.isInteger(row.N) && isFiniteNumber(row.E) && !expectedContinuedFractionKeys().has(`${xKey(row.x)}|${row.N}|${row.E}`)) failures.push(`primary.${name}[${index}] key is not in the frozen continued-fraction inventory`);
    }
    if (name === "reference_eigenvector_rows") {
      for (const field of ["x", "j", "terminal", "eigenvalue", "norm", "normalized_residual"]) {
        if (!isFiniteNumber(row[field])) failures.push(`primary.${name}[${index}] missing finite ${field}`);
      }
      if (!Number.isInteger(row.j) || !LEVELS.includes(row.j)) failures.push(`primary.${name}[${index}].j is not frozen`);
      if (!isFiniteNumber(row.terminal) || row.terminal !== expectedReference(row.x, "2M_ref")) failures.push(`primary.${name}[${index}].terminal is not 2M_ref`);
      if (isFiniteNumber(row.norm) && Math.abs(row.norm - 1) > 1e-12) failures.push(`primary.${name}[${index}].norm is not within 1e-12 of one`);
      if (isFiniteNumber(row.normalized_residual) && row.normalized_residual >= 1e-9) failures.push(`primary.${name}[${index}].normalized_residual is not below 1e-9`);
      if (row.pass !== true) failures.push(`primary.${name}[${index}].pass must be true`);
    }
  });
  return failures;
}
function validateReferenceEigenvectorRows(rows) {
  const failures = validateAuxiliaryRows("reference_eigenvector_rows", rows, X_VALUES.length * LEVELS.length);
  const map = new Map();
  if (Array.isArray(rows)) {
    for (const row of rows) {
      if (row && isFiniteNumber(row.x) && Number.isInteger(row.j)) map.set(`${xKey(row.x)}|${row.j}`, row);
    }
  }
  for (const x of X_VALUES) for (const j of LEVELS) {
    const key = `${xKey(x)}|${j}`;
    if (!map.has(key)) failures.push(`missing primary reference eigenvector row ${key}`);
  }
  return { failures, map };
}

// Dormand-Prince 5(4) step for the scalar phase equation.
function rk45Step(fn, t, y, h) {
  const k1 = fn(t, y);
  const k2 = fn(t + h / 5, y + h * k1 / 5);
  const k3 = fn(t + 3 * h / 10, y + h * (3 * k1 / 40 + 9 * k2 / 40));
  const k4 = fn(t + 4 * h / 5, y + h * (44 * k1 / 45 - 56 * k2 / 15 + 32 * k3 / 9));
  const k5 = fn(t + 8 * h / 9, y + h * (19372 * k1 / 6561 - 25360 * k2 / 2187 + 64448 * k3 / 6561 - 212 * k4 / 729));
  const k6 = fn(t + h, y + h * (9017 * k1 / 3168 - 355 * k2 / 33 + 46732 * k3 / 5247 + 49 * k4 / 176 - 5103 * k5 / 18656));
  const k7 = fn(t + h, y + h * (35 * k1 / 384 + 500 * k3 / 1113 + 125 * k4 / 192 - 2187 * k5 / 6784 + 11 * k6 / 84));
  const fifth = y + h * (35 * k1 / 384 + 500 * k3 / 1113 + 125 * k4 / 192 - 2187 * k5 / 6784 + 11 * k6 / 84);
  const fourth = y + h * (5179 * k1 / 57600 + 7571 * k3 / 16695 + 393 * k4 / 640 - 92097 * k5 / 339200 + 187 * k6 / 2100 + k7 / 40);
  return { value: fifth, error: fifth - fourth };
}

function integratePhase(x, energy, from, to) {
  const g = Math.pow(2 / x, 0.25);
  const kappa = Math.sqrt(1 + 1 / (g * g));
  const direction = Math.sign(to - from);
  if (direction === 0) return 0;
  let theta = from;
  let phase = 0;
  const phaseStepCap = Math.min(0.05, Math.PI / (8 * Math.sqrt(Math.max(1, Math.abs(energy) + 2 * x))));
  let h = direction * Math.min(Math.abs(to - from), 0.02 / Math.max(1, kappa), phaseStepCap);
  let steps = 0;
  const phaseRhs = (angle, value) => {
    const sine = Math.sin(value);
    const cosine = Math.cos(value);
    const q = energy + 1 - 2 * x * (1 - Math.cos(angle));
    return kappa * cosine * cosine + q * sine * sine / kappa;
  };
  while (direction * (to - theta) > 0) {
    const stiffness = Math.max(1, kappa, Math.abs(energy + 1 - 2 * x * (1 - Math.cos(theta))) / kappa);
    const cap = Math.min(0.28 / stiffness, phaseStepCap);
    if (Math.abs(h) > cap) h = direction * cap;
    const remaining = to - theta;
    if (Math.abs(h) > Math.abs(remaining)) h = remaining;
    const step = rk45Step(phaseRhs, theta, phase, h);
    const scale = ODE_ATOL + ODE_RTOL * Math.max(1, Math.abs(phase), Math.abs(step.value));
    const error = Math.abs(step.error);
    if (error <= scale || Math.abs(h) <= 1e-13) {
      theta += h;
      phase = step.value;
      if (!Number.isFinite(phase)) throw new VerificationError(`non-finite Prüfer phase at x=${x}, E=${energy}`);
      const factor = error === 0 ? 4 : Math.min(4, Math.max(0.2, 0.9 * Math.pow(scale / error, 0.2)));
      h *= factor;
    } else {
      h *= Math.max(0.1, 0.9 * Math.pow(scale / error, 0.2));
    }
  }
  return phase;
}

function phaseMismatch(x, energy, level) {
  const g = Math.pow(2 / x, 0.25);
  const meeting = Math.min(Math.PI / 2, 3 * g);
  const left = integratePhase(x, energy, 0, meeting);
  const right = integratePhase(x, energy, Math.PI, meeting);
  return left - right - (level + 1) * Math.PI;
}

function independentLevel(x, level) {
  const lower = -1 + (level + 1) * (level + 1);
  let lo = lower;
  let hi = lower + 4 * x + 2;
  let flo = phaseMismatch(x, lo, level);
  let fhi = phaseMismatch(x, hi, level);
  for (let attempt = 0; attempt < 12 && flo > 0; attempt += 1) {
    lo -= Math.max(1, hi - lo);
    flo = phaseMismatch(x, lo, level);
  }
  for (let attempt = 0; attempt < 16 && fhi < 0; attempt += 1) {
    hi += Math.max(1, hi - lo);
    fhi = phaseMismatch(x, hi, level);
  }
  if (!(flo <= 0 && fhi >= 0)) throw new VerificationError(`Dirichlet phase bracket failed at x=${x}, level=${level}: ${flo}, ${fhi}`);
  for (let iteration = 0; iteration < 64; iteration += 1) {
    const mid = (lo + hi) / 2;
    const fm = phaseMismatch(x, mid, level);
    if (!Number.isFinite(fm)) throw new VerificationError(`non-finite phase mismatch at x=${x}, level=${level}`);
    if (fm <= 0) lo = mid;
    else hi = mid;
    if (Math.abs(hi - lo) <= 2e-10 * Math.max(1, Math.abs(mid))) break;
  }
  return (lo + hi) / 2;
}

function independentSpectrum(x) {
  const eigenvalues = LEVELS.map((level) => independentLevel(x, level));
  return { x, eigenvalues, gap: eigenvalues[1] - eigenvalues[0] };
}

function scheduleData(x) {
  const q = Math.pow(x, 0.25);
  const values = expectedSchedules(x);
  return {
    x,
    N_fixed: values.fixed,
    N_C: values.C,
    N_iso: values.iso,
    N_grow: values.grow,
    N_half: values.half,
    M_ref: Math.max(512, 4 * values.half),
    M_double: 2 * Math.max(512, 4 * values.half),
    x_quarter: q,
  };
}

function kValue(n) {
  return n * (n + 2);
}

function cfValue(x, N, energy, terminal) {
  let m = 0;
  let derivative = 0;
  for (let n = terminal; n >= N + 1; n -= 1) {
    const denominator = kValue(n) + 2 * x - energy - x * x * m;
    const nextDerivative = derivative;
    const nextM = m;
    m = 1 / denominator;
    derivative = m * m * (1 + x * x * nextDerivative);
    if (!Number.isFinite(m) || !Number.isFinite(derivative)) throw new VerificationError(`continued fraction overflow at x=${x}, N=${N}, E=${energy}`);
    // Keep the named temporaries above: they make the differentiated
    // recurrence visibly independent from a finite linear solve.
    void nextM;
  }
  return { value: m, derivative };
}

function solveTridiagonalBoundary(x, N, energy, length) {
  const size = length;
  if (!Number.isInteger(size) || size < 1) throw new VerificationError("tail length must be positive");
  const diagonal = new Array(size);
  const rhs = new Array(size).fill(0);
  rhs[0] = 1;
  const off = -x;
  for (let i = 0; i < size; i += 1) diagonal[i] = kValue(N + 1 + i) + 2 * x - energy;
  for (let i = 1; i < size; i += 1) {
    const pivot = diagonal[i - 1];
    if (!Number.isFinite(pivot) || Math.abs(pivot) < 1e-15) throw new VerificationError("singular finite tail pivot");
    const multiplier = off / pivot;
    diagonal[i] -= multiplier * off;
    rhs[i] -= multiplier * rhs[i - 1];
  }
  const solution = new Array(size);
  solution[size - 1] = rhs[size - 1] / diagonal[size - 1];
  for (let i = size - 2; i >= 0; i -= 1) solution[i] = (rhs[i] - off * solution[i + 1]) / diagonal[i];
  return solution;
}

function directBoundaryGreen(x, N, energy, length) {
  return solveTridiagonalBoundary(x, N, energy, length)[0];
}

function selfEnergyBounds(x, N, energy, m) {
  const delta = kValue(N + 1) - energy;
  if (!(delta > 0)) throw new VerificationError(`tail bound requires delta>0 at x=${x}, N=${N}, E=${energy}`);
  const sigma = x * x * m;
  const lower = x * x / (delta + 2 * x);
  const upper = 2 * x * x / (delta + 2 * x + Math.sqrt(delta * (delta + 4 * x)));
  const minimum = Math.min(x, x * x / delta);
  return { delta, sigma, lower, upper, minimum };
}

function rankOneEndpointMinimum(dimension, coefficient) {
  if (!Number.isInteger(dimension) || dimension < 1) throw new VerificationError("rank-one endpoint dimension must be positive");
  return dimension === 1 ? coefficient : Math.min(0, coefficient);
}

function tailSturmCount(x, start, terminal, value) {
  const pivotFloor = 1e-12;
  let count = 0;
  let pivot = kValue(start) + 2 * x - value;
  if (Math.abs(pivot) < pivotFloor) pivot = -pivotFloor;
  if (pivot < 0) count += 1;
  for (let n = start + 1; n <= terminal; n += 1) {
    pivot = kValue(n) + 2 * x - value - (x * x) / pivot;
    if (Math.abs(pivot) < pivotFloor) pivot = -pivotFloor;
    if (pivot < 0) count += 1;
  }
  return count;
}

function lowestTailEigenvalue(x, N, terminal) {
  const start = N + 1;
  if (!Number.isInteger(terminal) || terminal < start) throw new VerificationError("tail terminal must include N+1");
  let lower = kValue(start);
  let upper = kValue(start) + 2 * x + Math.max(1, Math.abs(kValue(start) + 2 * x)) * 1e-12;
  if (tailSturmCount(x, start, terminal, lower) !== 0 || tailSturmCount(x, start, terminal, upper) < 1) {
    throw new VerificationError(`tail Sturm bracket failed at x=${x}, N=${N}, terminal=${terminal}`);
  }
  for (let iteration = 0; iteration < 100; iteration += 1) {
    const midpoint = (lower + upper) / 2;
    if (tailSturmCount(x, start, terminal, midpoint) >= 1) upper = midpoint;
    else lower = midpoint;
  }
  return (lower + upper) / 2;
}

function finiteSectionEigenvalues(x, N, count) {
  const dimension = N + 1;
  if (!Number.isInteger(N) || N < 0 || !Number.isInteger(count) || count < 1 || count > dimension) throw new VerificationError("invalid finite-section eigenvalue request");
  const lowerBound = 0;
  const upperBound = kValue(N) + 4 * x + Math.max(1, Math.abs(kValue(N) + 4 * x)) * 1e-12;
  if (tailSturmCount(x, 0, N, lowerBound) !== 0 || tailSturmCount(x, 0, N, upperBound) < count) {
    throw new VerificationError(`finite-section Sturm bracket failed at x=${x}, N=${N}`);
  }
  const eigenvalues = [];
  for (let level = 0; level < count; level += 1) {
    let lower = lowerBound;
    let upper = upperBound;
    for (let iteration = 0; iteration < 100; iteration += 1) {
      const midpoint = (lower + upper) / 2;
      if (tailSturmCount(x, 0, N, midpoint) >= level + 1) upper = midpoint;
      else lower = midpoint;
    }
    eigenvalues.push((lower + upper) / 2);
  }
  return eigenvalues;
}

function jacobiEigenpairs(diagonal, offDiagonal) {
  const n = diagonal.length;
  const matrix = Array.from({ length: n }, (_, i) => {
    const row = new Array(n).fill(0);
    row[i] = diagonal[i];
    if (i + 1 < n) row[i + 1] = offDiagonal[i];
    if (i > 0) row[i - 1] = offDiagonal[i - 1];
    return row;
  });
  const vectors = Array.from({ length: n }, (_, i) => Array.from({ length: n }, (_, j) => Number(i === j)));
  const maxIterations = Math.max(100, 40 * n * n);
  for (let iteration = 0; iteration < maxIterations; iteration += 1) {
    let p = 0;
    let q = 1;
    let largest = 0;
    for (let i = 0; i < n; i += 1) for (let j = i + 1; j < n; j += 1) {
      if (Math.abs(matrix[i][j]) > largest) {
        largest = Math.abs(matrix[i][j]);
        p = i;
        q = j;
      }
    }
    if (largest <= 2e-13 * Math.max(1, ...diagonal.map((value) => Math.abs(value)))) break;
    const theta = (matrix[q][q] - matrix[p][p]) / (2 * matrix[p][q]);
    const t = Math.sign(theta || 1) / (Math.abs(theta) + Math.sqrt(1 + theta * theta));
    const c = 1 / Math.sqrt(1 + t * t);
    const s = t * c;
    const app = matrix[p][p];
    const aqq = matrix[q][q];
    const apq = matrix[p][q];
    matrix[p][p] = app - t * apq;
    matrix[q][q] = aqq + t * apq;
    matrix[p][q] = 0;
    matrix[q][p] = 0;
    for (let r = 0; r < n; r += 1) {
      if (r === p || r === q) continue;
      const arp = matrix[r][p];
      const arq = matrix[r][q];
      matrix[r][p] = c * arp - s * arq;
      matrix[p][r] = matrix[r][p];
      matrix[r][q] = c * arq + s * arp;
      matrix[q][r] = matrix[r][q];
    }
    for (let r = 0; r < n; r += 1) {
      const vrp = vectors[r][p];
      const vrq = vectors[r][q];
      vectors[r][p] = c * vrp - s * vrq;
      vectors[r][q] = c * vrq + s * vrp;
    }
  }
  const pairs = matrix.map((row, index) => ({ value: row[index], vector: vectors.map((line) => line[index]) }));

  pairs.sort((a, b) => a.value - b.value);
  return pairs;
}
function referenceTailNormSquared(x, energy, N, terminal) {
  if (!Number.isInteger(terminal) || terminal <= N) throw new VerificationError(`reference terminal must exceed cutoff at x=${x}, N=${N}`);
  const logMagnitudes = new Float64Array(terminal + 1);
  const signs = new Float64Array(terminal + 1);
  signs[terminal] = 1;
  const ratioFloor = Number.MIN_VALUE;
  let ratioNext = (kValue(terminal) + 2 * x - energy) / x;
  if (!Number.isFinite(ratioNext)) throw new VerificationError(`non-finite reference tail ratio at x=${x}`);
  for (let n = terminal; n >= 1; n -= 1) {
    if (n < terminal) ratioNext = (kValue(n) + 2 * x - energy) / x - 1 / ratioNext;
    const ratio = Math.abs(ratioNext) < ratioFloor ? Math.sign(ratioNext || 1) * ratioFloor : ratioNext;
    logMagnitudes[n - 1] = logMagnitudes[n] + Math.log(Math.abs(ratio));
    signs[n - 1] = signs[n] * Math.sign(ratio);
    ratioNext = ratio;
  }
  let maxLog = -Infinity;
  for (const value of logMagnitudes) if (value > maxLog) maxLog = value;
  let retained = 0;
  let tail = 0;
  for (let n = 0; n <= terminal; n += 1) {
    const weight = Math.exp(2 * (logMagnitudes[n] - maxLog));
    if (n <= N) retained += weight;
    else tail += weight;
  }
  if (!(retained > 0) || !Number.isFinite(tail)) throw new VerificationError(`reference tail normalization failed at x=${x}, N=${N}`);
  return tail / retained;
}
function referenceEigenvectorData(x, energy, terminal) {
  const logs = new Float64Array(terminal + 1);
  const signs = new Float64Array(terminal + 1);
  signs[terminal] = 1;
  const ratioFloor = 1e-300;
  let ratioNext = (kValue(terminal) + 2 * x - energy) / x;
  if (!Number.isFinite(ratioNext)) throw new VerificationError(`non-finite reference eigenvector ratio at x=${x}`);
  for (let n = terminal; n >= 1; n -= 1) {
    const safeNext = Math.abs(ratioNext) < ratioFloor ? Math.sign(ratioNext || 1) * ratioFloor : ratioNext;
    if (n < terminal) ratioNext = (kValue(n) + 2 * x - energy) / x - 1 / safeNext;
    const ratio = Math.abs(ratioNext) < ratioFloor ? Math.sign(ratioNext || 1) * ratioFloor : ratioNext;
    logs[n - 1] = logs[n] + Math.log(Math.abs(ratio));
    signs[n - 1] = signs[n] * Math.sign(ratio);
    ratioNext = ratio;
  }
  let maxLog = -Infinity;
  for (const value of logs) if (value > maxLog) maxLog = value;
  const values = Array.from({ length: terminal + 1 }, (_, n) => signs[n] * Math.exp(logs[n] - maxLog));
  const normBefore = Math.sqrt(values.reduce((sum, value) => sum + value * value, 0));
  if (!(normBefore > 0) || !Number.isFinite(normBefore)) throw new VerificationError(`reference eigenvector normalization failed at x=${x}`);
  for (let n = 0; n <= terminal; n += 1) values[n] /= normBefore;
  const residual = values.map((value, n) => (kValue(n) + 2 * x - energy) * value - (n > 0 ? x * values[n - 1] : 0) - (n < terminal ? x * values[n + 1] : 0));
  const hv = values.map((value, n) => (kValue(n) + 2 * x) * value - (n > 0 ? x * values[n - 1] : 0) - (n < terminal ? x * values[n + 1] : 0));
  const residualNorm = Math.sqrt(residual.reduce((sum, value) => sum + value * value, 0));
  const hvNorm = Math.sqrt(hv.reduce((sum, value) => sum + value * value, 0));
  return { values, norm: Math.sqrt(values.reduce((sum, value) => sum + value * value, 0)), normalizedResidual: residualNorm / Math.max(1, hvNorm, Math.abs(energy)) };
}

function feshbachData(x, level, energy, N, terminal, referenceEnergy, tailOperatorMinimum) {
  const cf = cfValue(x, N, energy, terminal);
  const bounds = selfEnergyBounds(x, N, energy, cf.value);
  const diagonal = new Array(N + 1);
  const off = new Array(N).fill(-x);
  for (let n = 0; n <= N; n += 1) diagonal[n] = kValue(n) + 2 * x - energy;
  diagonal[N] -= bounds.sigma;
  const pairs = jacobiEigenpairs(diagonal, off);
  let selected = pairs[0];
  for (const pair of pairs) if (Math.abs(pair.value) < Math.abs(selected.value)) selected = pair;
  const feshbachScale = Math.max(1, ...pairs.map((pair) => Math.abs(pair.value)));
  const p = selected.vector;
  const pNorm = Math.sqrt(p.reduce((sum, value) => sum + value * value, 0));
  if (!(pNorm > 0)) throw new VerificationError(`Feshbach eigenvector vanished at x=${x}, level=${level}`);
  for (let i = 0; i < p.length; i += 1) p[i] /= pNorm;
  const tailSize = terminal - N;
  const tail = solveTridiagonalBoundary(x, N, energy, tailSize);
  const tailScale = x * p[N];
  const directTailNormSquared = tailScale * tailScale * tail.reduce((sum, value) => sum + value * value, 0);
  const formulaTailNormSquared = x * x * p[N] * p[N] * cf.derivative;
  const full = p.concat(tail.map((value) => tailScale * value));
  const action = new Array(full.length).fill(0);
  const residual = new Array(full.length).fill(0);
  for (let n = 0; n < full.length; n += 1) {
    action[n] = (kValue(n) + 2 * x) * full[n];
    if (n > 0) action[n] -= x * full[n - 1];
    if (n + 1 < full.length) action[n] -= x * full[n + 1];
    residual[n] = action[n] - energy * full[n];
  }
  const vectorNorm = Math.sqrt(full.reduce((sum, value) => sum + value * value, 0));
  const actionNorm = Math.sqrt(action.reduce((sum, value) => sum + value * value, 0));
  const residualNorm = Math.sqrt(residual.reduce((sum, value) => sum + value * value, 0));
  const normalizedFeshbachResidual = Math.abs(selected.value) / feshbachScale;
  const normalizedFullResidual = residualNorm / Math.max(1, actionNorm, Math.abs(energy) * vectorNorm);
  const referenceData = referenceEigenvectorData(x, referenceEnergy, terminal);
  let referenceRetained = 0;
  let referenceTail = 0;
  for (let n = 0; n <= terminal; n += 1) {
    const weight = referenceData.values[n] * referenceData.values[n];
    if (n <= N) referenceRetained += weight;
    else referenceTail += weight;
  }
  referenceTail /= referenceRetained;
  const referenceTailRelativeError = relativeError(directTailNormSquared, referenceTail);
  const poleFreeMargin = kValue(N + 1) - energy - DELTA_ISO * Math.sqrt(x);
  if (!isFiniteNumber(tailOperatorMinimum)) throw new VerificationError(`missing finite tail-operator minimum at x=${x}, N=${N}`);
  const tailOperatorTarget = kValue(N + 1) - DELTA_ISO * Math.sqrt(x);
  const tailOperatorMargin = tailOperatorMinimum - tailOperatorTarget;
  return {
    x,
    j: level,
    cutoff: N,
    eigenvalue: energy,
    k_tail: kValue(N + 1),
    isolation_margin: poleFreeMargin,
    self_energy: bounds.sigma,
    self_energy_derivative: x * x * cf.derivative,
    self_energy_lower: bounds.lower,
    self_energy_upper: bounds.upper,
    self_energy_minimum: bounds.minimum,
    tail_operator_minimum: tailOperatorMinimum,
    tail_operator_target: tailOperatorTarget,
    tail_operator_margin: tailOperatorMargin,
    feshbach_normalized_residual: normalizedFeshbachResidual,
    full_residual: normalizedFullResidual,
    tail_norm_sq_direct: directTailNormSquared,
    tail_norm_sq_formula: formulaTailNormSquared,
    tail_norm_sq_relative_error: relativeError(directTailNormSquared, formulaTailNormSquared),
    reference_tail_norm_sq: referenceTail,
    reference_tail_relative_error: referenceTailRelativeError,
    cf_terminal: terminal,
  };
}

function makeCheck(name, passed, detail, checks, failures) {
  if (checks.some((check) => check.name === name)) throw new VerificationError(`duplicate independent check name ${name}`);
  const entry = { name, passed: Boolean(passed), detail };
  checks.push(entry);
  if (!entry.passed) failures.push(`${name}: ${typeof detail === "string" ? detail : JSON.stringify(detail)}`);
  return entry;
}

function buildReceipt(status, checks, failures, payload) {
  const receipt = {
    schema: RECEIPT_SCHEMA,
    receipt_role: "independent",
    protocol: {
      primary_schema: PRIMARY_SCHEMA,
      protocol_sha256: EXPECTED_PROTOCOL_SHA256,
      manifest_schema: MANIFEST_SCHEMA,
      rejected_primary_schema: REJECTED_PRIMARY_SCHEMA,
      rejected_manifest_schema: REJECTED_MANIFEST_SCHEMA,
      finite_dimension_amendment: {
        minimum_scheduled_cutoff: ENERGY_LEVEL_COUNT - 1,
        requested_ritz_values: ENERGY_LEVEL_COUNT,
        accepts_v1_receipts: false,
      },
      x_values: [...X_VALUES],
      levels: [...LEVELS],
      schedules: [...SCHEDULES],
      continuous_problem: "-u''(theta) + [-1 + 2x(1-cos(theta))]u(theta) = E u(theta), u(0)=u(pi)=0",
      independent_method: "continuous-angle Dirichlet spectrum by two-sided Prüfer phase shooting with adaptive Dormand-Prince 5(4)",
      measurement_route: "continuous_angle_ode",
      reference_method: "independent symmetric-tridiagonal Sturm sequence and bisection at the doubled reference terminal",
      ode_rtol: ODE_RTOL,
      ode_atol: ODE_ATOL,
      comparison_tolerance: COMPARISON_TOLERANCE,
      comparison_tolerance_justification: "The independent scalar phase ODE uses adaptive RK45; 5e-7 is a fixed, non-fitted tolerance for cross-route spectrum comparison and is much tighter than the frozen 0.1/0.25 asymptotic landmark gates.",
      primary_terminal_tolerance: PRIMARY_TERMINAL_TOLERANCE,
      cf_relative_tolerance: CF_RELATIVE_TOLERANCE,
      cf_derivative_tolerance: CF_DERIVATIVE_TOLERANCE,
      rf12_inequality_slack: RF12_INEQUALITY_SLACK,
      rf20_slack: RF20_SLACK,
      feshbach_residual_tolerance: FESHBACH_RESIDUAL_TOLERANCE,
      cf_primary_comparison_tolerance: CF_PRIMARY_COMPARISON_TOLERANCE,
      tail_norm_tolerance: TAIL_NORM_TOLERANCE,
      relative_error_definition: "abs(a-b)/max(abs(a),abs(b),Number.MIN_VALUE)",
      normalized_discrepancy_definition: "abs(a-b)/max(1,abs(a),abs(b)) for finite-tail CF versus direct solves",
      delta_iso: DELTA_ISO,
      landmark_leading_tolerance: LANDMARK_LEADING_TOLERANCE,
      landmark_subleading_tolerance: LANDMARK_SUBLEADING_TOLERANCE,
    },
    runtime: { engine: "Bun/Node standard library", solver: "scalar adaptive RK45 + tridiagonal Thomas checks" },
    status,
    checks,
    failures,
    ...payload,
    check_count: checks.length,
  };
  allFinite(receipt, "receipt");
  return receipt;
}
function writeExclusive(file, receipt) {
  const serialized = JSON.stringify(receipt, null, 2);
  if (serialized.includes("NaN") || serialized.includes("Infinity")) throw new VerificationError("refusing to write non-finite JSON");
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const handle = fs.openSync(file, "wx");
  try {
    fs.writeFileSync(handle, `${serialized}\n`, "utf8");
  } finally {
    fs.closeSync(handle);
  }
}

function basePayload(inputPath) {
  return {
    input_path: inputPath,
    input_sha256: null,
    source_binding: {},
    independent_rows: [],
    reference_eigenvector_rows: [],
    independent_row_inventory: [],
    primary_row_inventory: { spectrum: [], cutoff: [], feshbach: [], continued_fraction: [] },
    comparisons: [],
    primary_convergence: [],
    continued_fraction_comparisons: [],
    continued_fraction_rows: [],
    finite_tail_rows: [],
    cutoff_reconstruction_rows: [],
    bound_rows: [],
    operator_bracket_rows: [],
    feshbach_reconstruction_rows: [],
    landmark_rows: [],
    classifications: {
      numerical_support: {
        source_binding: "INCONCLUSIVE",
        continuous_spectrum: "INCONCLUSIVE",
        Weyl_continued_fraction: "INCONCLUSIVE",
        Feshbach_self_energy: "INCONCLUSIVE",
        weak_coupling_landmarks: "INCONCLUSIVE",
      },
      analytical_reconciliation: {
        continuous_SU2_radial_normalization: "UNRESOLVED",
        exact_Feshbach_transfer_and_bounds: "UNRESOLVED",
        cutoff_asymptotics: "UNRESOLVED",
        interacting_lattice_scope: "UNRESOLVED",
      },
    },
    scope: {
      included: ["isolated continuous-SU(2) class-function radial equation", "frozen six-x/three-level numerical reconstruction", "right-tail Weyl continued fraction, derivative, bounds, and N_iso diagnostics"],
      numerical_support_is_separate_from_analytical_reconciliation: true,
      excluded: ["complete proofs of RF4-RF14", "many-plaquette or interacting-lattice conclusions", "thermodynamic or continuum mass-gap conclusions", "Cassi microscopic identification"],
    },
    measured_summary: {},
  };
}

function checkManifestInputs(inputPath, identities, binding, primaryManifest) {
  const stem = path.basename(inputPath, path.extname(inputPath));
  const manifest = path.join(path.dirname(inputPath), `${stem}.inputs.json`);
  const result = { path: manifest, sha256: null, schema: null, expected_protocol_sha256: null, snapshot_sha256: null, identities: null };
  const failures = [];
  try {
    result.sha256 = sha256File(manifest);
    const data = readJsonStrict(manifest);
    result.schema = data?.schema ?? null;
    result.expected_protocol_sha256 = data?.expected_protocol_sha256 ?? null;
    result.snapshot_sha256 = data?.snapshot_sha256 ?? null;
    result.identities = data?.identities ?? null;
    if (data?.schema !== MANIFEST_SCHEMA) failures.push("adjacent inputs manifest schema mismatch");
    if (data?.expected_protocol_sha256 !== EXPECTED_PROTOCOL_SHA256) failures.push("adjacent inputs manifest expected_protocol_sha256 mismatch");
    if (!primaryManifest || typeof primaryManifest !== "object" || Array.isArray(primaryManifest)) {
      failures.push("primary inputs_manifest declaration is unavailable");
    } else {
      const declaredPath = resolveManifestPath(primaryManifest.path);
      if (declaredPath !== path.resolve(manifest)) failures.push("primary inputs_manifest.path does not resolve to the adjacent manifest");
      if (primaryManifest.sha256 !== result.sha256) failures.push("primary inputs_manifest.sha256 differs from the adjacent manifest");
      if (primaryManifest.schema !== data?.schema) failures.push("primary inputs_manifest.schema differs from the adjacent manifest");
    }
    const declared = validateIdentityMap(data?.identities);
    if (JSON.stringify(declared) !== JSON.stringify(identities)) failures.push("adjacent inputs manifest identities differ from primary identities");
    const snapshot = data?.snapshot_sha256;
    if (!snapshot || typeof snapshot !== "object" || Array.isArray(snapshot) || Object.keys(snapshot).sort().join("\0") !== [...IDENTITY_KEYS].sort().join("\0")) {
      failures.push("adjacent inputs manifest snapshot_sha256 keys must be exactly protocol, primary, independent");
    } else {
      for (const name of IDENTITY_KEYS) {
        if (typeof snapshot[name] !== "string" || !/^[0-9a-f]{64}$/.test(snapshot[name])) {
          failures.push(`adjacent inputs manifest snapshot_sha256.${name} must be lowercase SHA-256`);
          continue;
        }
        if (snapshot[name] !== identities[name].sha256) failures.push(`adjacent inputs manifest snapshot_sha256.${name} differs from identities.${name}.sha256`);
        if (!binding?.[name] || snapshot[name] !== binding[name].snapshot_sha256) failures.push(`adjacent inputs manifest snapshot_sha256.${name} differs from bound frozen snapshot`);
      }
    }
  } catch (error) {
    failures.push(`adjacent inputs manifest invalid: ${error.message}`);
  }
  return { result, failures };
}

function run(inputPath, outputPath) {
  const payload = basePayload(inputPath);
  const checks = [];
  const failures = [];
  let primary = null;
  let identities = null;
  let binding = {};
  let inputHashBefore = null;
  try {
    if (fs.statSync(inputPath).isFile()) {
      inputHashBefore = sha256File(inputPath);
      payload.input_sha256 = inputHashBefore;
    } else throw new VerificationError(`primary input is not a file: ${inputPath}`);
  } catch (error) {
    makeCheck("primary_input_available", false, error.message, checks, failures);
  }
  try {
    if (inputHashBefore === null) throw new VerificationError("primary input unavailable");
    primary = readJsonStrict(inputPath);
    const envelopeFailures = validatePrimaryEnvelope(primary);
    makeCheck("primary_receipt_schema_and_status", envelopeFailures.length === 0, envelopeFailures, checks, failures);
    if (envelopeFailures.length === 0) {
      identities = validateIdentityMap(primary.identities);
      const sourceResult = bindSources(identities, inputPath);
      binding = sourceResult.binding;
      payload.source_binding = binding;
      makeCheck("source_manifest_and_frozen_snapshots", sourceResult.failures.length === 0, sourceResult.failures, checks, failures);
      const manifestResult = checkManifestInputs(inputPath, identities, binding, primary.inputs_manifest);
      payload.inputs_manifest = manifestResult.result;
      makeCheck("adjacent_inputs_manifest", manifestResult.failures.length === 0, manifestResult.failures, checks, failures);
    }
  } catch (error) {
    makeCheck("primary_parse_and_identity_validation", false, error.message, checks, failures);
  }
  let spectrumInfo = { failures: ["spectrum validation skipped"], map: new Map() };
  let cutoffInfo = { failures: ["cutoff validation skipped"], map: new Map(), reconstructionRows: [] };
  let feshbachInfo = { failures: ["feshbach validation skipped"], map: new Map() };
  let continuedInfo = { failures: ["continued-fraction validation skipped"], map: new Map() };
  let referenceInfo = { failures: ["reference-eigenvector validation skipped"], map: new Map() };
  if (primary && typeof primary === "object") {
    spectrumInfo = validateSpectrumRows(primary.spectrum_rows);
    cutoffInfo = validateCutoffRows(primary.cutoff_rows);
    payload.cutoff_reconstruction_rows = cutoffInfo.reconstructionRows;
    feshbachInfo = validateFeshbachRows(primary.feshbach_rows);
    continuedInfo = validateContinuedFractionRows(primary.continued_fraction_rows);
    referenceInfo = validateReferenceEigenvectorRows(primary.reference_eigenvector_rows);
    const auxFailures = [];
    const expectedCFCount = expectedContinuedFractionKeys().size;
    const auxiliaryCounts = {
      symbolic_rows: 8,
      determinant_rows: 24,
      direct_tail_rows: 2 * expectedCFCount,
      bound_rows: expectedCFCount,
      operator_bracket_rows: expectedCFCount,
      derivative_rows: expectedCFCount,
      resolvent_rows: [0.25, 1, 16].reduce((count, x) => count + 3 * new Set([1, Math.sqrt(x)]).size, 0),
      weak_coupling_rows: X_VALUES.length,
      reference_eigenvector_rows: X_VALUES.length * LEVELS.length,
    };
    for (const [name, count] of Object.entries(auxiliaryCounts)) {
      if (name === "reference_eigenvector_rows" || name === "continued_fraction_rows") continue;
      auxFailures.push(...validateAuxiliaryRows(name, primary[name], count));
    }
    auxFailures.push(...referenceInfo.failures, ...continuedInfo.failures);
    const cutoffReconstructionFailures = [];
    if (cutoffInfo.reconstructionRows.length !== X_VALUES.length * SCHEDULES.length) cutoffReconstructionFailures.push(`independent cutoff reconstruction has ${cutoffInfo.reconstructionRows.length} rows; expected ${X_VALUES.length * SCHEDULES.length}`);
    for (const row of cutoffInfo.reconstructionRows) if (row.pass !== true) cutoffReconstructionFailures.push(`independent cutoff reconstruction failed at x=${row.x}, schedule=${row.schedule}`);
    makeCheck("primary_auxiliary_row_inventories", auxFailures.length === 0, auxFailures, checks, failures);
    makeCheck("primary_spectrum_row_inventory", spectrumInfo.failures.length === 0, spectrumInfo.failures, checks, failures);
    makeCheck("primary_cutoff_row_inventory", cutoffInfo.failures.length === 0, cutoffInfo.failures, checks, failures);
    makeCheck("finite_section_RF20_independent", cutoffReconstructionFailures.length === 0, cutoffReconstructionFailures, checks, failures);
    makeCheck("primary_feshbach_row_inventory", feshbachInfo.failures.length === 0, feshbachInfo.failures, checks, failures);
    payload.primary_row_inventory = {
      spectrum: [...spectrumInfo.map.keys()],
      cutoff: [...cutoffInfo.map.keys()],
      feshbach: [...feshbachInfo.map.keys()],
      continued_fraction: [...continuedInfo.map.keys()],
      auxiliary_counts: auxiliaryCounts,
    };
  } else {
    makeCheck("primary_auxiliary_row_inventories", false, ["primary receipt unavailable"], checks, failures);
    makeCheck("primary_spectrum_row_inventory", false, spectrumInfo.failures, checks, failures);
    makeCheck("primary_cutoff_row_inventory", false, cutoffInfo.failures, checks, failures);
    makeCheck("finite_section_RF20_independent", false, ["primary receipt unavailable"], checks, failures);
    makeCheck("primary_feshbach_row_inventory", false, feshbachInfo.failures, checks, failures);
  }
  const primaryUsable = primary && spectrumInfo.failures.length === 0 && cutoffInfo.failures.length === 0 && feshbachInfo.failures.length === 0 && continuedInfo.failures.length === 0 && identities && binding && checks.find((check) => check.name === "primary_auxiliary_row_inventories")?.passed === true && checks.find((check) => check.name === "primary_receipt_schema_and_status")?.passed === true && checks.find((check) => check.name === "source_manifest_and_frozen_snapshots")?.passed === true && checks.find((check) => check.name === "adjacent_inputs_manifest")?.passed === true;
  if (primaryUsable) {
    try {
      const independentRows = [];
      const comparisons = [];
      const primaryConvergence = [];
      for (const x of X_VALUES) {
        const row = independentSpectrum(x);
        independentRows.push(row);
        const low = spectrumInfo.map.get(`${xKey(x)}|M_ref`).eigenvalues;
        const high = spectrumInfo.map.get(`${xKey(x)}|2M_ref`).eigenvalues;
        const convergenceErrors = high.map((value, j) => relativeError(value, low[j]));
        primaryConvergence.push({ x, reference: "M_ref", doubled_reference: "2M_ref", relative_errors: convergenceErrors, worst_relative_error: Math.max(...convergenceErrors), pass: Math.max(...convergenceErrors) < PRIMARY_TERMINAL_TOLERANCE });
        row.eigenvalues.forEach((value, j) => {
          const error = relativeError(value, high[j]);
          comparisons.push({ x, j, independent: value, primary_doubled_reference: high[j], absolute_error: Math.abs(value - high[j]), relative_error: error, tolerance: COMPARISON_TOLERANCE, pass: error < COMPARISON_TOLERANCE });
        });
      }
      const independentReferenceRows = [];
      const referenceFailures = [];
      const independentReferenceKeys = new Set();
      for (const x of X_VALUES) for (const j of LEVELS) {
        const key = `${xKey(x)}|${j}`;
        if (independentReferenceKeys.has(key)) throw new VerificationError(`duplicate independent reference eigenvector row ${key}`);
        independentReferenceKeys.add(key);
        const primaryReference = referenceInfo.map.get(key);
        if (!primaryReference) throw new VerificationError(`missing primary reference eigenvector row ${key}`);
        const terminal = expectedReference(x, "2M_ref");
        const data = referenceEigenvectorData(x, primaryReference.eigenvalue, terminal);
        const pass = Math.abs(data.norm - 1) <= 1e-12 && data.normalizedResidual < 1e-9;
        independentReferenceRows.push({ x, j, terminal, eigenvalue: primaryReference.eigenvalue, norm: data.norm, normalized_residual: data.normalizedResidual, pass });
        if (!pass) referenceFailures.push(`x=${x}, j=${j}: independent reference eigenvector residual/norm gate failed`);
      }
      payload.reference_eigenvector_rows = independentReferenceRows;
      makeCheck("independent_reference_eigenvector_rows", referenceFailures.length === 0 && independentReferenceKeys.size === X_VALUES.length * LEVELS.length, referenceFailures.length === 0 ? `expected ${X_VALUES.length * LEVELS.length} unique x/j rows, got ${independentReferenceKeys.size}` : referenceFailures, checks, failures);
      const independentInventory = [];
      const independentKeys = new Set();
      for (const row of independentRows) for (const j of LEVELS) {
        const key = `${xKey(row.x)}|${j}`;
        if (independentKeys.has(key)) throw new VerificationError(`duplicate independent row ${key}`);
        independentKeys.add(key);
        independentInventory.push(key);
      }
      payload.independent_row_inventory = independentInventory;
      makeCheck("independent_spectrum_row_inventory", independentKeys.size === X_VALUES.length * LEVELS.length, `expected ${X_VALUES.length * LEVELS.length} unique x/j rows, got ${independentKeys.size}`, checks, failures);
      payload.independent_rows = independentRows;
      payload.comparisons = comparisons;
      payload.primary_convergence = primaryConvergence;
      const comparisonFailures = comparisons.filter((row) => !row.pass).map((row) => `x=${row.x}, j=${row.j}: relative error ${row.relative_error} >= ${COMPARISON_TOLERANCE}`);
      const convergenceFailures = primaryConvergence.filter((row) => !row.pass).map((row) => `x=${row.x}: terminal relative error ${row.worst_relative_error} >= ${PRIMARY_TERMINAL_TOLERANCE}`);
      makeCheck("doubled_reference_convergence", convergenceFailures.length === 0, convergenceFailures, checks, failures);
      makeCheck("continuous_angle_spectrum_vs_primary", comparisonFailures.length === 0, comparisonFailures, checks, failures);
    } catch (error) {
      makeCheck("independent_reference_eigenvector_rows", false, error.message, checks, failures);
      makeCheck("independent_spectrum_row_inventory", false, error.message, checks, failures);
      makeCheck("doubled_reference_convergence", false, error.message, checks, failures);
      makeCheck("continuous_angle_spectrum_vs_primary", false, error.message, checks, failures);
    }
  } else {
    makeCheck("doubled_reference_convergence", false, ["primary row inventory or source binding unavailable"], checks, failures);
    makeCheck("independent_spectrum_row_inventory", false, ["primary row inventory or source binding unavailable"], checks, failures);
    makeCheck("continuous_angle_spectrum_vs_primary", false, ["primary row inventory or source binding unavailable"], checks, failures);
  }

  // Continued fractions and differentiated Weyl bounds are evaluated even
  // when comparison rows fail, as long as the frozen schedule itself is
  // available.  This keeps numerical support diagnostic rather than masking a
  // malformed primary receipt.
  const cfFailures = [];
  const finiteTailFailures = [];
  const boundFailures = [];
  const bracketFailures = [];
  const cfRows = [];
  const finiteTailRows = [];
  const boundRows = [];
  const bracketRows = [];
  try {
    for (const x of X_VALUES) {
      const schedule = scheduleData(x);
      const ns = [0, 1, 3, 7, schedule.N_fixed, schedule.N_C, schedule.N_iso, schedule.N_grow, schedule.N_half];
      const uniqueNs = [...new Set(ns)];
      for (const n of uniqueNs) {
        for (const energy of [...new Set([-1, -Math.sqrt(x), 0])]) {
          const first = cfValue(x, n, energy, schedule.M_ref);
          const second = cfValue(x, n, energy, schedule.M_double);
          const discrepancy = relativeError(first.value, second.value);
          const h = 1e-5 * Math.max(1, Math.sqrt(x), Math.abs(energy));
          const centered = (cfValue(x, n, energy + h, schedule.M_double).value - cfValue(x, n, energy - h, schedule.M_double).value) / (2 * h);
          const derivativeError = relativeError(centered, second.derivative);
          const bounds = selfEnergyBounds(x, n, energy, second.value);
          const lowerSlack = bounds.sigma - bounds.lower;
          const upperSlack = bounds.upper - bounds.sigma;
          const minimumSlack = bounds.minimum - bounds.upper;
          const inequalitiesPass = lowerSlack >= -RF12_INEQUALITY_SLACK && upperSlack >= -RF12_INEQUALITY_SLACK && minimumSlack >= -RF12_INEQUALITY_SLACK;
          const leftMinimum = rankOneEndpointMinimum(n + 1, upperSlack);
          const rightMinimum = rankOneEndpointMinimum(n + 1, lowerSlack);
          const bracketsPass = leftMinimum >= -RF12_INEQUALITY_SLACK && rightMinimum >= -RF12_INEQUALITY_SLACK;
          const directNormalizedErrors = {};
          for (const L of [32, 64]) {
            const direct = directBoundaryGreen(x, n, energy, L);
            const M = n + L;
            const finiteValue = cfValue(x, n, energy, M).value;
            directNormalizedErrors[String(L)] = Math.abs(finiteValue - direct) / Math.max(1, Math.abs(finiteValue), Math.abs(direct));
            const finiteRow = { x, N: n, E: energy, L, M, terminal: M, continued_fraction: finiteValue, direct_boundary_green: direct, normalized_discrepancy: directNormalizedErrors[String(L)], pass: directNormalizedErrors[String(L)] < CF_RELATIVE_TOLERANCE };
            finiteTailRows.push(finiteRow);
            if (!finiteRow.pass) finiteTailFailures.push(`x=${x}, N=${n}, E=${energy}, L=${L}: finite-tail solve mismatch`);
          }
          const boundRow = { x, N: n, E: energy, delta: bounds.delta, self_energy: bounds.sigma, lower: bounds.lower, upper: bounds.upper, min_upper: bounds.minimum, lower_slack: lowerSlack, upper_slack: upperSlack, min_upper_slack: minimumSlack, tolerance: RF12_INEQUALITY_SLACK, pass: inequalitiesPass };
          boundRows.push(boundRow);
          if (!boundRow.pass) boundFailures.push(`x=${x}, N=${n}, E=${energy}: RF12 bound inequality failed`);
          const bracketRow = { x, N: n, E: energy, left_min_eigenvalue: leftMinimum, right_min_eigenvalue: rightMinimum, left_projector_slack: upperSlack, right_projector_slack: lowerSlack, tolerance: RF12_INEQUALITY_SLACK, pass: bracketsPass };
          bracketRows.push(bracketRow);
          if (!bracketRow.pass) bracketFailures.push(`x=${x}, N=${n}, E=${energy}: RF12a operator bracket failed`);
          const row = { x, N: n, E: energy, m: second.value, m_prime: second.derivative, sigma: bounds.sigma, lower_bound: bounds.lower, upper_bound: bounds.upper, reference_relative_error: discrepancy, direct_normalized_errors: directNormalizedErrors, M_ref: schedule.M_ref, M_double: schedule.M_double, m_M_ref: first.value, m_centered_derivative: centered, derivative_relative_error: derivativeError, pass: second.value > 0 && second.derivative > 0 && discrepancy < CF_RELATIVE_TOLERANCE && derivativeError < CF_DERIVATIVE_TOLERANCE && inequalitiesPass && directNormalizedErrors["32"] < CF_RELATIVE_TOLERANCE && directNormalizedErrors["64"] < CF_RELATIVE_TOLERANCE };
          cfRows.push(row);
          if (!row.pass) cfFailures.push(`x=${x}, N=${n}, E=${energy}: continued-fraction/derivative/bound check failed`);
        }
      }
    }
  } catch (error) {
    cfFailures.push(error.message);
    finiteTailFailures.push(error.message);
  }
  const expectedCfRows = X_VALUES.reduce((total, x) => {
    const schedule = scheduleData(x);
    const ns = new Set([0, 1, 3, 7, schedule.N_fixed, schedule.N_C, schedule.N_iso, schedule.N_grow, schedule.N_half]);
    const energies = new Set([-1, -Math.sqrt(x), 0]);
    return total + ns.size * energies.size;
  }, 0);
  const uniqueCfKeys = new Set(cfRows.map((row) => `${xKey(row.x)}|${row.N}|${row.E}`));
  if (cfRows.length !== expectedCfRows || uniqueCfKeys.size !== expectedCfRows) cfFailures.push(`continued-fraction inventory has ${cfRows.length} rows and ${uniqueCfKeys.size} unique keys; expected ${expectedCfRows}`);
  if (finiteTailRows.length !== 2 * expectedCfRows) finiteTailFailures.push(`finite-tail inventory has ${finiteTailRows.length} rows; expected ${2 * expectedCfRows}`);
  if (boundRows.length !== expectedCfRows) boundFailures.push(`RF12 bound inventory has ${boundRows.length} rows; expected ${expectedCfRows}`);
  if (bracketRows.length !== expectedCfRows) bracketFailures.push(`RF12a bracket inventory has ${bracketRows.length} rows; expected ${expectedCfRows}`);
  payload.continued_fraction_rows = cfRows;
  payload.finite_tail_rows = finiteTailRows;
  payload.bound_rows = boundRows;
  payload.operator_bracket_rows = bracketRows;
  makeCheck("continued_fraction_derivative_bounds", cfFailures.length === 0, cfFailures, checks, failures);
  makeCheck("finite_tail_linear_reconstruction", finiteTailFailures.length === 0, finiteTailFailures, checks, failures);
  makeCheck("RF12_bound_inequalities", boundFailures.length === 0, boundFailures, checks, failures);
  makeCheck("RF12a_operator_brackets", bracketFailures.length === 0, bracketFailures, checks, failures);

  const landmarkRows = [];
  const cfComparisons = [];
  const cfComparisonFailures = [];
  if (continuedInfo.failures.length === 0) {
    for (const row of cfRows) {
      const primaryRow = continuedInfo.map.get(`${xKey(row.x)}|${row.N}|${row.E}`);
      if (!primaryRow) {
        cfComparisonFailures.push(`missing primary continued-fraction row x=${row.x}, N=${row.N}, E=${row.E}`);
        continue;
      }
      const fields = ["m", "m_prime", "sigma", "lower_bound", "upper_bound", "reference_relative_error"];
      const errors = {};
      for (const field of fields) errors[field] = relativeError(row[field], primaryRow[field]);
      for (const label of ["32", "64"]) errors[`direct_normalized_errors_${label}`] = normalizedError(row.direct_normalized_errors[label], primaryRow.direct_normalized_errors[label]);
      const worst = Math.max(...Object.values(errors));
      const comparison = { x: row.x, N: row.N, E: row.E, relative_errors: errors, worst_relative_error: worst, tolerance: CF_PRIMARY_COMPARISON_TOLERANCE, pass: worst < CF_PRIMARY_COMPARISON_TOLERANCE };
      cfComparisons.push(comparison);
      if (!comparison.pass) cfComparisonFailures.push(`x=${row.x}, N=${row.N}, E=${row.E}: independent/primary CF error ${worst} >= ${CF_PRIMARY_COMPARISON_TOLERANCE}`);
    }
  } else {
    cfComparisonFailures.push("primary continued-fraction inventory unavailable");
  }
  payload.continued_fraction_comparisons = cfComparisons;
  makeCheck("continued_fraction_vs_primary_rows", cfComparisonFailures.length === 0, cfComparisonFailures, checks, failures);
  const landmarkFailures = [];
  const independentByX = new Map(payload.independent_rows.map((row) => [row.x, row]));
  for (const x of [4096, 65536]) {
    const row = independentByX.get(x);
    if (!row) {
      landmarkFailures.push(`missing independent spectrum at x=${x}`);
      continue;
    }
    for (const j of LEVELS) {
      const c = -1 - (6 * j * j + 9 * j + 15 / 4) / 12;
      const leading = row.eigenvalues[j] / Math.sqrt(x) - (4 * j + 3);
      const subleading = row.eigenvalues[j] - (4 * j + 3) * Math.sqrt(x) - c;
      const landmark = { x, j, leading_scaled_residual: leading, subleading_residual: subleading, leading_pass: Math.abs(leading) < LANDMARK_LEADING_TOLERANCE, subleading_pass: x !== 65536 || Math.abs(subleading) < LANDMARK_SUBLEADING_TOLERANCE };
      landmarkRows.push(landmark);
      if (!landmark.leading_pass) landmarkFailures.push(`leading landmark failed at x=${x}, j=${j}`);
      if (!landmark.subleading_pass) landmarkFailures.push(`subleading landmark failed at x=${x}, j=${j}`);
    }
  }
  payload.landmark_rows = landmarkRows;
  makeCheck("weak_coupling_leading_subleading_landmarks", landmarkFailures.length === 0, landmarkFailures, checks, failures);

  const feshbachRows = [];
  const feshbachFailures = [];
  try {
    for (const x of [4096, 65536]) {
      const independent = independentByX.get(x);
      const nIso = expectedSchedules(x).iso;
      const terminal = scheduleData(x).M_double;
      const tailOperatorMinimum = lowestTailEigenvalue(x, nIso, terminal);
      const independentReferenceEigenvalues = finiteSectionEigenvalues(x, terminal, ENERGY_LEVEL_COUNT);
      for (const j of LEVELS) {
        if (!independent) throw new VerificationError(`missing independent spectrum at x=${x}`);
        const primaryRow = feshbachInfo.map.get(`${xKey(x)}|${j}`);
        if (!primaryRow) throw new VerificationError(`missing primary Feshbach row at x=${x}, j=${j}`);
        const primaryReferenceRow = spectrumInfo.map.get(`${xKey(x)}|2M_ref`);
        if (!primaryReferenceRow) throw new VerificationError(`missing doubled-reference spectrum at x=${x}`);
        const continuousEigenvalue = independent.eigenvalues[j];
        const independentReferenceEigenvalue = independentReferenceEigenvalues[j];
        const primaryFeshbachEigenvalue = primaryRow.eigenvalue;
        const primarySpectrumEigenvalue = primaryReferenceRow.eigenvalues[j];
        const computed = feshbachData(x, j, independentReferenceEigenvalue, nIso, terminal, independentReferenceEigenvalue, tailOperatorMinimum);
        const primaryMargin = primaryRow.isolation_margin;
        const continuousMargin = kValue(nIso + 1) - continuousEigenvalue - DELTA_ISO * Math.sqrt(x);
        const continuousReferenceError = relativeError(continuousEigenvalue, independentReferenceEigenvalue);
        const primaryFeshbachEnergyError = relativeError(primaryFeshbachEigenvalue, independentReferenceEigenvalue);
        const primarySpectrumEnergyError = relativeError(primarySpectrumEigenvalue, independentReferenceEigenvalue);
        const primaryInternalEnergyError = relativeError(primaryFeshbachEigenvalue, primarySpectrumEigenvalue);
        const continuousMarginError = relativeError(continuousMargin, primaryMargin);
        const referenceMarginError = relativeError(computed.isolation_margin, primaryMargin);
        const tailOperatorMarginError = relativeError(computed.tail_operator_margin, primaryRow.tail_operator_margin);
        const primarySelfEnergyError = relativeError(computed.self_energy, x * x * primaryRow.m);
        const primarySelfEnergyDerivativeError = relativeError(computed.self_energy_derivative, x * x * primaryRow.m_prime);
        const primaryReferenceTailError = relativeError(
          computed.reference_tail_norm_sq,
          primaryRow.reference_tail_norm_sq,
        );
        const row = {
          ...computed,
          continuous_eigenvalue: continuousEigenvalue,
          independent_reference_eigenvalue: independentReferenceEigenvalue,
          primary_feshbach_eigenvalue: primaryFeshbachEigenvalue,
          primary_spectrum_eigenvalue: primarySpectrumEigenvalue,
          continuous_isolation_margin: continuousMargin,
          primary_isolation_margin: primaryMargin,
          continuous_reference_relative_error: continuousReferenceError,
          primary_feshbach_energy_relative_error: primaryFeshbachEnergyError,
          primary_spectrum_energy_relative_error: primarySpectrumEnergyError,
          primary_internal_energy_relative_error: primaryInternalEnergyError,
          continuous_isolation_margin_relative_error: continuousMarginError,
          reference_isolation_margin_relative_error: referenceMarginError,
          tail_operator_margin_relative_error: tailOperatorMarginError,
          primary_self_energy_relative_error: primarySelfEnergyError,
          primary_self_energy_derivative_relative_error: primarySelfEnergyDerivativeError,
          primary_reference_tail_relative_error: primaryReferenceTailError,
          pass:
            continuousReferenceError < COMPARISON_TOLERANCE
            && primaryFeshbachEnergyError < PRIMARY_TERMINAL_TOLERANCE
            && primarySpectrumEnergyError < PRIMARY_TERMINAL_TOLERANCE
            && primaryInternalEnergyError < PRIMARY_TERMINAL_TOLERANCE
            && computed.isolation_margin > 0
            && computed.tail_operator_margin >= -RF20_SLACK
            && computed.self_energy > 0
            && computed.self_energy_derivative > 0
            && computed.self_energy >= computed.self_energy_lower - RF12_INEQUALITY_SLACK
            && computed.self_energy <= computed.self_energy_upper + RF12_INEQUALITY_SLACK
            && computed.self_energy_upper <= computed.self_energy_minimum + RF12_INEQUALITY_SLACK
            && computed.tail_norm_sq_relative_error < TAIL_NORM_TOLERANCE
            && computed.reference_tail_relative_error < TAIL_NORM_TOLERANCE
            && primaryReferenceTailError < TAIL_NORM_TOLERANCE
            && computed.feshbach_normalized_residual < FESHBACH_RESIDUAL_TOLERANCE
            && computed.full_residual < FESHBACH_RESIDUAL_TOLERANCE
            && continuousMarginError < COMPARISON_TOLERANCE
            && referenceMarginError < COMPARISON_TOLERANCE
            && tailOperatorMarginError < COMPARISON_TOLERANCE
            && primarySelfEnergyError < CF_PRIMARY_COMPARISON_TOLERANCE
            && primarySelfEnergyDerivativeError < CF_PRIMARY_COMPARISON_TOLERANCE,
        };
        feshbachRows.push(row);
        if (!row.pass) feshbachFailures.push(`x=${x}, j=${j}: N_iso self-energy/Feshbach reconstruction failed`);
      }
    }
  } catch (error) {
    feshbachFailures.push(error.message);
  }
  payload.feshbach_reconstruction_rows = feshbachRows;
  makeCheck("N_iso_self_energy_and_feshbach_reconstruction", feshbachFailures.length === 0, feshbachFailures, checks, failures);

  const scheduleSummary = {};
  for (const schedule of SCHEDULES) {
    const rows = X_VALUES.map((x) => cutoffInfo.map.get(`${xKey(x)}|${schedule}`)).filter(Boolean);
    scheduleSummary[schedule] = { rows: rows.length, maximum_primary_relative_error: rows.length ? Math.max(...rows.flatMap((row) => row.relative_errors)) : null, scope: "numerical_control_only" };
  }

  const spectrumPass = checks.find((check) => check.name === "continuous_angle_spectrum_vs_primary")?.passed === true;
  const cfIndependentPass = checks.find((check) => check.name === "continued_fraction_derivative_bounds")?.passed === true
    && checks.find((check) => check.name === "finite_tail_linear_reconstruction")?.passed === true
    && checks.find((check) => check.name === "RF12_bound_inequalities")?.passed === true
    && checks.find((check) => check.name === "RF12a_operator_brackets")?.passed === true;
  const cfPrimaryPass = checks.find((check) => check.name === "continued_fraction_vs_primary_rows")?.passed === true;
  const cfPass = cfIndependentPass && cfPrimaryPass;
  const feshbachPass = checks.find((check) => check.name === "N_iso_self_energy_and_feshbach_reconstruction")?.passed === true;
  const landmarkPass = checks.find((check) => check.name === "weak_coupling_leading_subleading_landmarks")?.passed === true;
  const sourcePass = checks.find((check) => check.name === "source_manifest_and_frozen_snapshots")?.passed === true && checks.find((check) => check.name === "adjacent_inputs_manifest")?.passed === true;
  payload.classifications.numerical_support.source_binding = sourcePass ? "SUPPORTS" : "INCONCLUSIVE";
  payload.classifications.numerical_support.continuous_spectrum = spectrumPass ? "SUPPORTS" : "INCONCLUSIVE";
  payload.classifications.numerical_support.Weyl_continued_fraction = cfPass ? "SUPPORTS" : "INCONCLUSIVE";
  payload.classifications.numerical_support.Feshbach_self_energy = feshbachPass ? "SUPPORTS" : "INCONCLUSIVE";
  payload.classifications.numerical_support.weak_coupling_landmarks = landmarkPass ? "SUPPORTS" : "INCONCLUSIVE";
  payload.measured_summary = {
    schedule_summary: scheduleSummary,
    independent_x_count: payload.independent_rows.length,
    independent_level_count: payload.independent_rows.length * LEVELS.length,
    reference_eigenvector_count: payload.reference_eigenvector_rows.length,
    comparison_count: payload.comparisons.length,
    continued_fraction_count: cfRows.length,
    finite_tail_count: finiteTailRows.length,
    cutoff_reconstruction_count: payload.cutoff_reconstruction_rows.length,
    bound_count: boundRows.length,
    operator_bracket_count: bracketRows.length,
    feshbach_count: feshbachRows.length,
    Delta_square_1: independentByX.has(65536) ? independentByX.get(65536).gap / Math.sqrt(2 * 65536) : null,
  };
  payload.classifications.analytical_reconciliation.continuous_SU2_radial_normalization = "UNRESOLVED";
  payload.classifications.analytical_reconciliation.exact_Feshbach_transfer_and_bounds = "UNRESOLVED";
  payload.classifications.analytical_reconciliation.cutoff_asymptotics = "UNRESOLVED";
  payload.classifications.analytical_reconciliation.interacting_lattice_scope = "UNRESOLVED";

  const driftFailures = [];
  if (binding && Object.keys(binding).length) driftFailures.push(...recheckSources(binding));
  else driftFailures.push("source binding unavailable");
  if (inputHashBefore !== null) {
    const after = sha256File(inputPath);
    if (after !== inputHashBefore) driftFailures.push("primary input changed during verification");
  }
  if (payload.inputs_manifest?.path && payload.inputs_manifest?.sha256) {
    try {
      const manifestAfter = sha256File(payload.inputs_manifest.path);
      if (manifestAfter !== payload.inputs_manifest.sha256) driftFailures.push("adjacent inputs manifest changed during verification");
    } catch (error) {
      driftFailures.push(`adjacent inputs manifest cannot be rechecked: ${error.message}`);
    }
  } else {
    driftFailures.push("adjacent inputs manifest binding unavailable");
  }
  makeCheck("sources_stable_during_verification", driftFailures.length === 0, driftFailures, checks, failures);
  payload.classifications.numerical_support.source_binding = sourcePass && driftFailures.length === 0 ? "SUPPORTS" : "INCONCLUSIVE";
  if (driftFailures.length !== 0) {
    for (const key of Object.keys(payload.classifications.numerical_support)) payload.classifications.numerical_support[key] = "INCONCLUSIVE";
  }
  const status = failures.length === 0 ? "PASS" : "FAIL";
  const receipt = buildReceipt(status, checks, failures, payload);
  allFinite(receipt, "receipt");
  writeExclusive(outputPath, receipt);
  return status === "PASS" ? 0 : 1;
}

function emergencyReceipt(inputPath, outputPath, error) {
  const payload = basePayload(inputPath);
  payload.measured_summary = { emergency: true };
  const receipt = buildReceipt("FAIL", [{ name: "unhandled_exception", passed: false, detail: `${error.name}: ${error.message}` }], [`verification failure: ${error.name}: ${error.message}`], payload);
  try {
    allFinite(receipt, "emergency receipt");
    writeExclusive(outputPath, receipt);
  } catch (writeError) {
    process.stderr.write(`verification failure: ${error.message}; receipt write failed: ${writeError.message}\n`);
  }
}

function parseArgs(argv) {
  const result = { input: null, output: null };
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === "--input" && i + 1 < argv.length) result.input = argv[++i];
    else if (argv[i] === "--output" && i + 1 < argv.length) result.output = argv[++i];
    else throw new VerificationError(`unknown or incomplete argument ${argv[i]}`);
  }
  if (!result.input || !result.output) throw new VerificationError("usage requires --input <primary.json> --output <fresh-independent.json>");
  return { input: path.resolve(result.input), output: path.resolve(result.output) };
}

let args;
try {
  args = parseArgs(process.argv.slice(2));
  if (fs.existsSync(args.output)) throw new VerificationError(`refusing to overwrite existing receipt: ${args.output}`);
  process.exitCode = run(args.input, args.output);
} catch (error) {
  if (args && !fs.existsSync(args.output)) emergencyReceipt(args.input, args.output, error);
  else process.stderr.write(`verification aborted: ${error.message}\n`);
  process.exitCode = 1;
}
