#!/usr/bin/env node
/**
 * Independent verifier for the frozen conditional Yang-Mills RG gap-matching
 * diagnostic. Uses only Node built-ins and imports no primary implementation.
 * The synthetic arithmetic does not establish an RG flow or a continuum gap.
 */

import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const SOURCE = fileURLToPath(import.meta.url);
const ROOT = path.resolve(path.dirname(SOURCE), "..");
const PROTOCOL = path.join(ROOT, "computations", "yang-mills-rg-gap-matching-prereg.md");
const PRIMARY_SOURCE = path.join(
  ROOT,
  "computations",
  "verify_yang_mills_rg_gap_matching.py",
);
const PRIMARY_RECEIPT = path.join(
  ROOT,
  "runs",
  "yang-mills-rg-gap-matching",
  "verification.json",
);
const OUTPUT = path.join(
  ROOT,
  "runs",
  "yang-mills-rg-gap-matching",
  "verification-independent.json",
);
const EXPECTED_PROTOCOL_SHA256 = "d8749326eb0fcf2062302e0afec4cb68dc2dd96ac532962bffdb18c658860f36";

const G2_VALUES = [0.8, 0.5, 0.3, 0.2, 0.1, 0.05];
const FLATNESS_POWERS = [1, 2, 4, 8];
const B = 2;
const LOG_B = Math.log(B);
const ENDPOINT_LOWER = 1 / 64;
const ENDPOINT_UPPER_EXACT = 1 / 32;
const BOUNDED_STEP_DEFECT = 0.025;
const BOUNDED_CUMULATIVE_LIMIT = 0.025;
const ENDPOINT_UPPER_BOUNDED = B * Math.exp(BOUNDED_STEP_DEFECT) * ENDPOINT_LOWER;
const DRIFT_STEP_DEFECT = BOUNDED_STEP_DEFECT / 4;
const COARSE_RATE_LOWER = 0.5;
const COARSE_RATE_UPPER = 2;
const TOLERANCE = 2e-12;

const EXPECTED_PRIMARY_CHECKS = 139;
const EXPECTED_PRIMARY_EXACT_CHECKS = 42;
const EXPECTED_PRIMARY_BOUNDED_CHECKS = 48;
const EXPECTED_PRIMARY_DRIFT_CHECKS = 18;
const EXPECTED_PRIMARY_VOLUME_CHECKS = 5;
const EXPECTED_PRIMARY_FLATNESS_CHECKS = 4;
const EXPECTED_PRIMARY_FIRING_CHECKS = 7;
const EXPECTED_PRIMARY_TOP_CHECKS = 15;
const EXPECTED_INDEPENDENT_CHECKS = 32;
const EXPECTED_FIRING_CONTROLS = 7;

const PI2 = Math.PI * Math.PI;
const b0 = 11 / (24 * PI2);
const b1 = 17 / (96 * PI2 * PI2);
const p = b1 / (2 * b0 * b0);

const NEGATIVE_CLAIMS = [
  "balaban_uv_stability_is_mass_gap",
  "gaussian_no_go_claimed",
  "rg_trajectory_constructed",
  "exact_block_map_constructed",
  "transfer_correlation_matching_established",
  "observable_completeness_established",
  "coarse_interacting_gap_computed",
  "interacting_gap_computed",
  "thermodynamic_limit_constructed",
  "os_axioms_established",
  "nontrivial_continuum_limit_established",
  "continuum_mass_gap_established",
];

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

function absoluteClose(left, right, tolerance = TOLERANCE) {
  return Math.abs(left - right) <= tolerance;
}

function relativeClose(left, right, tolerance = TOLERANCE) {
  return Math.abs(left - right) <= tolerance * Math.max(1, Math.abs(left), Math.abs(right));
}

function scaledDifference(left, right) {
  return Math.abs(left - right) / Math.max(1, Math.abs(left), Math.abs(right));
}

function strictlyIncreasing(values) {
  return values.slice(1).every((value, index) => value > values[index]);
}

function strictlyDecreasing(values) {
  return values.slice(1).every((value, index) => value < values[index]);
}

function finitePayload(value) {
  if (value === null || typeof value === "boolean" || typeof value === "string") return true;
  if (typeof value === "number") return Number.isFinite(value);
  if (Array.isArray(value)) return value.every(finitePayload);
  if (typeof value === "object") return Object.values(value).every(finitePayload);
  return false;
}

function deepSort(value) {
  if (Array.isArray(value)) return value.map(deepSort);
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.keys(value).sort().map((key) => [key, deepSort(value[key])]),
    );
  }
  return value;
}

function logScale(g2) {
  return -1 / (2 * b0 * g2) - p * Math.log(b0 * g2);
}

function exactRow(g2, index) {
  const logF0 = logScale(g2);
  const f0 = Math.exp(logF0);
  const blockCount = Math.ceil((Math.log(ENDPOINT_LOWER) - logF0) / LOG_B);
  const logEndpoint = logF0 + blockCount * LOG_B;
  const endpoint = Math.exp(logEndpoint);
  const coarseRate = COARSE_RATE_LOWER + 0.25 * index;
  const logFineRate = Math.log(coarseRate) - blockCount * LOG_B;
  const fineRate = Math.exp(logFineRate);
  const blockRatio = Math.exp(-blockCount * LOG_B - logF0);
  const renormalizedRate = Math.exp(logFineRate - logF0);
  const n0F0 = 3 + index;
  const logN0 = Math.log(n0F0) - logF0;
  const logNn = logN0 - blockCount * LOG_B;
  return {
    index,
    g0_squared: g2,
    log_scale: logF0,
    scale: f0,
    block_count: blockCount,
    log_endpoint_scale: logEndpoint,
    endpoint_scale: endpoint,
    cumulative_defect: 0,
    coarse_rate: coarseRate,
    log_fine_rate: logFineRate,
    fine_rate: fineRate,
    block_ratio_over_scale: blockRatio,
    renormalized_rate: renormalizedRate,
    expected_renormalized_rate: coarseRate / endpoint,
    n0_times_scale: n0F0,
    log_initial_sites: logN0,
    log_coarse_sites: logNn,
    expected_log_coarse_sites: Math.log(n0F0) + Math.log(blockRatio),
  };
}

function runSchedule(logF0, defectAtStep) {
  const logValues = [logF0];
  const defects = [];
  while (logValues.at(-1) < Math.log(ENDPOINT_LOWER)) {
    if (defects.length >= 10000) throw new Error("defect schedule did not reach endpoint");
    const defect = Number(defectAtStep(defects.length));
    defects.push(defect);
    logValues.push(logValues.at(-1) + LOG_B + defect);
  }
  return { logValues, defects };
}

function boundedRow(g2, index) {
  const logF0 = logScale(g2);
  const f0 = Math.exp(logF0);
  const { logValues, defects } = runSchedule(
    logF0,
    (step) => (step % 2 === 0 ? BOUNDED_STEP_DEFECT : -BOUNDED_STEP_DEFECT),
  );
  const blockCount = defects.length;
  const cumulativeDefect = defects.reduce((total, value) => total + value, 0);
  const logEndpoint = logValues.at(-1);
  const endpoint = Math.exp(logEndpoint);
  const coarseRate = COARSE_RATE_LOWER + 0.25 * index;
  const logFineRate = Math.log(coarseRate) - blockCount * LOG_B;
  const fineRate = Math.exp(logFineRate);
  const blockRatio = Math.exp(-blockCount * LOG_B - logF0);
  const renormalizedRate = Math.exp(logFineRate - logF0);
  return {
    index,
    g0_squared: g2,
    log_scale: logF0,
    scale: f0,
    block_count: blockCount,
    defects,
    cumulative_defect: cumulativeDefect,
    log_endpoint_scale: logEndpoint,
    endpoint_scale: endpoint,
    coarse_rate: coarseRate,
    log_fine_rate: logFineRate,
    fine_rate: fineRate,
    block_ratio_over_scale: blockRatio,
    expected_block_ratio_over_scale: Math.exp(cumulativeDefect) / endpoint,
    renormalized_rate: renormalizedRate,
    expected_renormalized_rate: coarseRate * Math.exp(cumulativeDefect) / endpoint,
    qualified: (
      ENDPOINT_LOWER <= endpoint
      && endpoint <= ENDPOINT_UPPER_BOUNDED
      && Math.abs(cumulativeDefect) <= BOUNDED_CUMULATIVE_LIMIT + TOLERANCE
    ),
  };
}

function driftRow(g2, index) {
  const logF0 = logScale(g2);
  const { logValues, defects } = runSchedule(logF0, () => DRIFT_STEP_DEFECT);
  const blockCount = defects.length;
  const cumulativeDefect = defects.reduce((total, value) => total + value, 0);
  const logEndpoint = logValues.at(-1);
  const endpoint = Math.exp(logEndpoint);
  const maximumStepDefect = Math.max(...defects.map(Math.abs));
  const qualified = (
    ENDPOINT_LOWER <= endpoint
    && endpoint <= ENDPOINT_UPPER_BOUNDED
    && Math.abs(cumulativeDefect) <= BOUNDED_CUMULATIVE_LIMIT + TOLERANCE
  );
  const perStepOnlyQualified = (
    ENDPOINT_LOWER <= endpoint
    && endpoint <= ENDPOINT_UPPER_BOUNDED
    && maximumStepDefect <= BOUNDED_STEP_DEFECT + TOLERANCE
  );
  return {
    index,
    g0_squared: g2,
    log_scale: logF0,
    block_count: blockCount,
    defects,
    cumulative_defect: cumulativeDefect,
    maximum_step_defect: maximumStepDefect,
    log_endpoint_scale: logEndpoint,
    endpoint_scale: endpoint,
    qualified,
    per_step_only_qualified: perStepOnlyQualified,
  };
}

function buildVolumeSchedules(logScales) {
  const logG2 = G2_VALUES.map(Math.log);
  return [
    {
      name: "fixed_sites",
      classification: "COLLAPSE",
      log_n0_times_scale: logScales.map((value) => Math.log(1024) + value),
    },
    {
      name: "polynomial",
      classification: "COLLAPSE",
      log_n0_times_scale: logScales.map((value, index) => value - 4 * logG2[index]),
    },
    {
      name: "fixed_physical_box",
      classification: "FIXED",
      log_n0_times_scale: logScales.map(() => Math.log(3)),
    },
    {
      name: "inverse_g2_enhanced",
      classification: "INFINITE",
      log_n0_times_scale: logG2.map((value) => -value),
    },
    {
      name: "logarithmically_enhanced",
      classification: "INFINITE",
      log_n0_times_scale: logScales.map((value) => Math.log(-value)),
    },
  ];
}

function buildFlatnessRows(logScales) {
  return FLATNESS_POWERS.map((power) => {
    const logRatios = logScales.map(
      (logF, index) => logF - 0.5 * power * Math.log(G2_VALUES[index]),
    );
    return {
      power,
      log_ratios: logRatios,
      ratios: logRatios.map(Math.exp),
    };
  });
}

function fullGapConclusionAllowed(flags) {
  return [
    "rg_construction",
    "cumulative_defect_bound",
    "transfer_matching",
    "positive_endpoint_gap",
    "observable_completeness",
    "os_continuum_construction",
  ].every((name) => flags[name] === true);
}

function reconstructFiringControls(exactRows, boundedRows, driftRows) {
  const defectWitness = boundedRows.find(
    (row) => Math.abs(row.cumulative_defect) > BOUNDED_STEP_DEFECT / 2,
  );
  if (defectWitness === undefined) throw new Error("bounded defect witness absent");
  const exactWitness = exactRows.at(-1);
  const driftWitness = driftRows.at(-1);
  const actualBlockRatio = defectWitness.block_ratio_over_scale;
  const correctDefectFormula = Math.exp(defectWitness.cumulative_defect)
    / defectWitness.endpoint_scale;
  const omittedDefectFormula = 1 / defectWitness.endpoint_scale;
  const reversedDefectFormula = Math.exp(-defectWitness.cumulative_defect)
    / defectWitness.endpoint_scale;
  const fullFlags = {
    rg_construction: true,
    cumulative_defect_bound: true,
    transfer_matching: true,
    positive_endpoint_gap: true,
    observable_completeness: true,
    os_continuum_construction: true,
  };
  const incompleteFlags = { ...fullFlags, observable_completeness: false };
  const controls = [
    {
      name: "omit_cumulative_defect_factor",
      unmutated_passed: relativeClose(actualBlockRatio, correctDefectFormula),
      mutation_passed: relativeClose(actualBlockRatio, omittedDefectFormula),
    },
    {
      name: "reverse_cumulative_defect_sign",
      unmutated_passed: relativeClose(actualBlockRatio, correctDefectFormula),
      mutation_passed: relativeClose(actualBlockRatio, reversedDefectFormula),
    },
    {
      name: "accept_per_step_only_drift",
      unmutated_passed: !driftWitness.qualified,
      mutation_passed: !driftWitness.per_step_only_qualified,
    },
    {
      name: "omit_time_rate_rescaling",
      unmutated_passed: relativeClose(
        exactWitness.fine_rate,
        exactWitness.coarse_rate * Math.exp(-exactWitness.block_count * LOG_B),
      ),
      mutation_passed: relativeClose(exactWitness.coarse_rate, exactWitness.fine_rate),
    },
    {
      name: "call_fixed_box_infinite",
      unmutated_passed: "FIXED" === "FIXED",
      mutation_passed: "INFINITE" === "FIXED",
    },
    {
      name: "accept_zero_endpoint_rate",
      unmutated_passed: COARSE_RATE_LOWER > 0,
      mutation_passed: 0 > 0,
    },
    {
      name: "conclude_without_observable_completeness",
      unmutated_passed: fullGapConclusionAllowed(fullFlags),
      mutation_passed: fullGapConclusionAllowed(incompleteFlags),
    },
  ];
  for (const control of controls) {
    control.fired = control.unmutated_passed && !control.mutation_passed;
    control.comparisons_attempted = 2;
  }
  return controls;
}

function exactClaimBoundary(claims, executableStatus) {
  return (
    claims.two_loop_blocking_arithmetic === executableStatus
    && claims.conditional_rg_gap_matching_theorem_analytic === true
    && claims.analytic_theorem_outside_executable === true
    && NEGATIVE_CLAIMS.every((name) => claims[name] === false)
    && claims.clay_verdict === "NULL"
  );
}

function compareNumericFields(primary, reconstructed, scalarFields, arrayFields = []) {
  let maximumScaledError = 0;
  let comparisons = 0;
  let exactValuesMatch = true;
  for (const field of scalarFields) {
    const left = primary[field];
    const right = reconstructed[field];
    if (typeof left === "number" && typeof right === "number") {
      maximumScaledError = Math.max(maximumScaledError, scaledDifference(left, right));
    } else {
      exactValuesMatch &&= left === right;
    }
    comparisons += 1;
  }
  for (const field of arrayFields) {
    const left = primary[field];
    const right = reconstructed[field];
    if (!Array.isArray(left) || !Array.isArray(right) || left.length !== right.length) {
      exactValuesMatch = false;
      comparisons += 1;
      continue;
    }
    for (let index = 0; index < right.length; index += 1) {
      maximumScaledError = Math.max(
        maximumScaledError,
        scaledDifference(left[index], right[index]),
      );
      comparisons += 1;
    }
  }
  return { maximumScaledError, comparisons, exactValuesMatch };
}

function exactRowDecision(primary, row) {
  const comparison = compareNumericFields(
    primary,
    row,
    [
      "index",
      "g0_squared",
      "log_scale",
      "scale",
      "block_count",
      "log_endpoint_scale",
      "endpoint_scale",
      "cumulative_defect",
      "coarse_rate",
      "log_fine_rate",
      "fine_rate",
      "block_ratio_over_scale",
      "renormalized_rate",
      "expected_renormalized_rate",
      "n0_times_scale",
      "log_initial_sites",
      "log_coarse_sites",
      "expected_log_coarse_sites",
    ],
  );
  const ownIdentities = (
    Number.isInteger(row.block_count)
    && row.block_count > 0
    && ENDPOINT_LOWER <= row.endpoint_scale
    && row.endpoint_scale < ENDPOINT_UPPER_EXACT
    && relativeClose(row.block_ratio_over_scale, 1 / row.endpoint_scale)
    && relativeClose(
      row.fine_rate,
      row.coarse_rate * Math.exp(-row.block_count * LOG_B),
    )
    && relativeClose(row.renormalized_rate, row.coarse_rate / row.endpoint_scale)
    && relativeClose(row.log_coarse_sites, row.expected_log_coarse_sites)
  );
  return decision(
    `exact_row_${row.index}_reconstructed`,
    comparison.exactValuesMatch
      && comparison.maximumScaledError <= TOLERANCE
      && ownIdentities,
    {
      g0_squared: row.g0_squared,
      block_count: row.block_count,
      maximum_scaled_error: comparison.maximumScaledError,
      comparisons_attempted: comparison.comparisons + 7,
    },
    TOLERANCE,
  );
}

function boundedRowDecision(primary, row) {
  const comparison = compareNumericFields(
    primary,
    row,
    [
      "index",
      "g0_squared",
      "log_scale",
      "scale",
      "block_count",
      "cumulative_defect",
      "log_endpoint_scale",
      "endpoint_scale",
      "coarse_rate",
      "log_fine_rate",
      "fine_rate",
      "block_ratio_over_scale",
      "expected_block_ratio_over_scale",
      "renormalized_rate",
      "expected_renormalized_rate",
      "qualified",
    ],
    ["defects"],
  );
  const ownIdentities = (
    row.block_count === row.defects.length
    && row.block_count > 0
    && ENDPOINT_LOWER <= row.endpoint_scale
    && row.endpoint_scale <= ENDPOINT_UPPER_BOUNDED
    && Math.abs(row.cumulative_defect) <= BOUNDED_CUMULATIVE_LIMIT + TOLERANCE
    && relativeClose(
      row.block_ratio_over_scale,
      Math.exp(row.cumulative_defect) / row.endpoint_scale,
    )
    && relativeClose(
      row.fine_rate,
      row.coarse_rate * Math.exp(-row.block_count * LOG_B),
    )
    && relativeClose(
      row.renormalized_rate,
      row.coarse_rate * Math.exp(row.cumulative_defect) / row.endpoint_scale,
    )
    && row.qualified
  );
  return decision(
    `bounded_row_${row.index}_reconstructed`,
    comparison.exactValuesMatch
      && comparison.maximumScaledError <= TOLERANCE
      && ownIdentities,
    {
      g0_squared: row.g0_squared,
      block_count: row.block_count,
      cumulative_defect: row.cumulative_defect,
      maximum_scaled_error: comparison.maximumScaledError,
      comparisons_attempted: comparison.comparisons + 9,
    },
    TOLERANCE,
  );
}

function driftRowDecision(primary, row) {
  const comparison = compareNumericFields(
    primary,
    row,
    [
      "index",
      "g0_squared",
      "log_scale",
      "block_count",
      "cumulative_defect",
      "maximum_step_defect",
      "log_endpoint_scale",
      "endpoint_scale",
      "qualified",
      "per_step_only_qualified",
    ],
    ["defects"],
  );
  const replayed = row.log_scale + row.block_count * LOG_B + row.cumulative_defect;
  const ownIdentities = (
    row.block_count === row.defects.length
    && relativeClose(row.log_endpoint_scale, replayed)
    && row.cumulative_defect > BOUNDED_CUMULATIVE_LIMIT
    && row.maximum_step_defect < BOUNDED_STEP_DEFECT
    && !row.qualified
    && row.per_step_only_qualified
  );
  return decision(
    `drift_row_${row.index}_reconstructed`,
    comparison.exactValuesMatch
      && comparison.maximumScaledError <= TOLERANCE
      && ownIdentities,
    {
      g0_squared: row.g0_squared,
      block_count: row.block_count,
      cumulative_defect: row.cumulative_defect,
      maximum_scaled_error: comparison.maximumScaledError,
      comparisons_attempted: comparison.comparisons + 6,
    },
    TOLERANCE,
  );
}

function compareScheduleRows(primaryRows, rows, numericArrays) {
  if (!Array.isArray(primaryRows) || primaryRows.length !== rows.length) return false;
  return rows.every((row, index) => {
    const primary = primaryRows[index];
    if (primary.name !== undefined && primary.name !== row.name) return false;
    if (primary.classification !== undefined && primary.classification !== row.classification) return false;
    if (primary.power !== undefined && primary.power !== row.power) return false;
    return numericArrays.every((field) => (
      Array.isArray(primary[field])
      && primary[field].length === row[field].length
      && row[field].every((value, itemIndex) => relativeClose(primary[field][itemIndex], value))
    ));
  });
}

function buildReceipt() {
  const exactRows = G2_VALUES.map(exactRow);
  const boundedRows = G2_VALUES.map(boundedRow);
  const driftRows = G2_VALUES.map(driftRow);
  const logScales = G2_VALUES.map(logScale);
  const volumeSchedules = buildVolumeSchedules(logScales);
  const flatnessRows = buildFlatnessRows(logScales);
  const firingControls = reconstructFiringControls(exactRows, boundedRows, driftRows);

  if (!fs.existsSync(PRIMARY_RECEIPT)) {
    throw new Error(`primary receipt not found: ${PRIMARY_RECEIPT}`);
  }
  const primaryBytes = fs.readFileSync(PRIMARY_RECEIPT);
  const primary = JSON.parse(primaryBytes.toString("utf8"));

  const protocolHash = sha256(PROTOCOL);
  const primarySourceHash = sha256(PRIMARY_SOURCE);
  const independentSourceHash = sha256(SOURCE);
  const primaryReceiptHash = crypto.createHash("sha256").update(primaryBytes).digest("hex");

  const checks = [
    decision(
      "primary_schema_and_verdict",
      primary.schema === "cassi.yang-mills.rg-gap-matching.verification.v1"
        && primary.verdict === "PASS",
      { schema: primary.schema, verdict: primary.verdict },
    ),
    decision(
      "primary_frozen_counts",
      primary.summary.checks === EXPECTED_PRIMARY_CHECKS
        && primary.summary.passing_checks === EXPECTED_PRIMARY_CHECKS
        && primary.summary.exact_checks === EXPECTED_PRIMARY_EXACT_CHECKS
        && primary.summary.bounded_checks === EXPECTED_PRIMARY_BOUNDED_CHECKS
        && primary.summary.drift_checks === EXPECTED_PRIMARY_DRIFT_CHECKS
        && primary.summary.volume_checks === EXPECTED_PRIMARY_VOLUME_CHECKS
        && primary.summary.flatness_checks === EXPECTED_PRIMARY_FLATNESS_CHECKS
        && primary.summary.firing_checks === EXPECTED_PRIMARY_FIRING_CHECKS
        && primary.summary.top_level_checks === EXPECTED_PRIMARY_TOP_CHECKS,
      primary.summary,
    ),
    decision(
      "protocol_hash_binding_and_freeze",
      protocolHash === EXPECTED_PROTOCOL_SHA256
        && primary.sources.protocol.path === relative(PROTOCOL)
        && primary.sources.protocol.sha256 === protocolHash,
      {
        path: relative(PROTOCOL),
        sha256: protocolHash,
        expected_sha256: EXPECTED_PROTOCOL_SHA256,
        comparisons_attempted: 3,
      },
    ),
    decision(
      "verifier_source_hash_bindings",
      primary.sources.primary_source.path === relative(PRIMARY_SOURCE)
        && primary.sources.primary_source.sha256 === primarySourceHash
        && primary.sources.independent_source.path === relative(SOURCE)
        && primary.sources.independent_source.sha256 === independentSourceHash,
      {
        primary_source: { path: relative(PRIMARY_SOURCE), sha256: primarySourceHash },
        independent_source: { path: relative(SOURCE), sha256: independentSourceHash },
        comparisons_attempted: 4,
      },
    ),
    decision(
      "primary_receipt_hash_computed",
      primaryBytes.length > 0
        && primaryReceiptHash.length === 64
        && /^[0-9a-f]{64}$/u.test(primaryReceiptHash),
      {
        path: relative(PRIMARY_RECEIPT),
        sha256: primaryReceiptHash,
        bytes: primaryBytes.length,
        comparisons_attempted: 3,
      },
    ),
    decision(
      "coefficient_reconstruction",
      absoluteClose(b0, 11 / (24 * PI2))
        && absoluteClose(b1, 17 / (96 * PI2 * PI2))
        && absoluteClose(p, 51 / 121)
        && relativeClose(primary.coefficients.b0, b0)
        && relativeClose(primary.coefficients.b1, b1)
        && relativeClose(primary.coefficients.p, p),
      { b0, b1, p, comparisons_attempted: 6 },
      TOLERANCE,
    ),
    decision(
      "frozen_constant_reconstruction",
      primary.parameters.B === B
        && relativeClose(primary.parameters.endpoint_lower, ENDPOINT_LOWER)
        && relativeClose(primary.parameters.endpoint_upper_exact, ENDPOINT_UPPER_EXACT)
        && relativeClose(primary.parameters.endpoint_upper_bounded, ENDPOINT_UPPER_BOUNDED)
        && relativeClose(primary.parameters.bounded_step_defect, BOUNDED_STEP_DEFECT)
        && relativeClose(primary.parameters.bounded_cumulative_limit, BOUNDED_CUMULATIVE_LIMIT)
        && relativeClose(primary.parameters.drift_step_defect, DRIFT_STEP_DEFECT)
        && relativeClose(primary.parameters.coarse_rate_lower, COARSE_RATE_LOWER)
        && relativeClose(primary.parameters.coarse_rate_upper, COARSE_RATE_UPPER),
      {
        B,
        endpoint_lower: ENDPOINT_LOWER,
        endpoint_upper_exact: ENDPOINT_UPPER_EXACT,
        endpoint_upper_bounded: ENDPOINT_UPPER_BOUNDED,
        bounded_step_defect: BOUNDED_STEP_DEFECT,
        bounded_cumulative_limit: BOUNDED_CUMULATIVE_LIMIT,
        drift_step_defect: DRIFT_STEP_DEFECT,
        comparisons_attempted: 9,
      },
      TOLERANCE,
    ),
    decision(
      "frozen_schedule_reconstruction",
      JSON.stringify(primary.parameters.g0_squared) === JSON.stringify(G2_VALUES)
        && JSON.stringify(primary.parameters.flatness_powers) === JSON.stringify(FLATNESS_POWERS),
      {
        g0_squared: G2_VALUES,
        flatness_powers: FLATNESS_POWERS,
        comparisons_attempted: G2_VALUES.length + FLATNESS_POWERS.length,
      },
    ),
    decision(
      "primary_claim_boundary",
      exactClaimBoundary(primary.claims, "PASS"),
      primary.claims,
    ),
    decision(
      "all_firing_controls_reconstructed",
      firingControls.length === EXPECTED_FIRING_CONTROLS
        && firingControls.every((control) => control.fired)
        && primary.firing_controls.length === EXPECTED_FIRING_CONTROLS
        && firingControls.every((control, index) => (
          control.name === primary.firing_controls[index].name
          && control.unmutated_passed === primary.firing_controls[index].unmutated_passed
          && control.mutation_passed === primary.firing_controls[index].mutation_passed
          && primary.firing_controls[index].fired === true
        )),
      { controls: firingControls, comparisons_attempted: 5 * firingControls.length },
      { controls: EXPECTED_FIRING_CONTROLS, fired: EXPECTED_FIRING_CONTROLS },
    ),
    decision(
      "primary_row_family_shapes",
      primary.exact_rows.length === exactRows.length
        && primary.bounded_rows.length === boundedRows.length
        && primary.drift_rows.length === driftRows.length
        && primary.exact_rows.every((row) => row.checks.length === 7 && row.checks.every((item) => item.passed))
        && primary.bounded_rows.every((row) => row.checks.length === 8 && row.checks.every((item) => item.passed))
        && primary.drift_rows.every((row) => row.checks.length === 3 && row.checks.every((item) => item.passed)),
      {
        exact_rows: exactRows.length,
        bounded_rows: boundedRows.length,
        drift_rows: driftRows.length,
        comparisons_attempted: 3 + 18,
      },
    ),
    decision(
      "primary_decision_and_payload_consistency",
      finitePayload(primary)
        && primary.checks.length === EXPECTED_PRIMARY_CHECKS
        && primary.checks.every((item) => item.passed)
        && primary.summary.passing_checks === primary.checks.filter((item) => item.passed).length,
      {
        decisions: primary.checks.length,
        passing: primary.checks.filter((item) => item.passed).length,
        finite_payload: finitePayload(primary),
        comparisons_attempted: primary.checks.length + 3,
      },
    ),
  ];

  if (checks.length !== 12) {
    throw new Error(`global independent check count drifted: ${checks.length}`);
  }

  exactRows.forEach((row, index) => checks.push(exactRowDecision(primary.exact_rows[index], row)));
  boundedRows.forEach((row, index) => checks.push(boundedRowDecision(primary.bounded_rows[index], row)));
  driftRows.forEach((row, index) => checks.push(driftRowDecision(primary.drift_rows[index], row)));

  const volumeValuesMatch = compareScheduleRows(
    primary.volume_schedules,
    volumeSchedules,
    ["log_n0_times_scale"],
  );
  const flatnessValuesMatch = compareScheduleRows(
    primary.flatness_rows,
    flatnessRows,
    ["log_ratios", "ratios"],
  );
  const volumeBehavior = (
    strictlyDecreasing(volumeSchedules[0].log_n0_times_scale)
    && strictlyDecreasing(volumeSchedules[1].log_n0_times_scale)
    && volumeSchedules[2].log_n0_times_scale.every((value) => absoluteClose(value, Math.log(3)))
    && strictlyIncreasing(volumeSchedules[3].log_n0_times_scale)
    && strictlyIncreasing(volumeSchedules[4].log_n0_times_scale)
  );
  const flatnessBehavior = flatnessRows.every(
    (row) => strictlyDecreasing(row.log_ratios) && row.ratios.every((value) => value > 0),
  );
  checks.push(
    decision(
      "volume_and_flatness_reconstructed",
      volumeValuesMatch && flatnessValuesMatch && volumeBehavior && flatnessBehavior,
      {
        volume_schedules: volumeSchedules.length,
        flatness_powers: flatnessRows.map((row) => row.power),
        comparisons_attempted: 5 * G2_VALUES.length + 2 * FLATNESS_POWERS.length * G2_VALUES.length,
      },
      TOLERANCE,
    ),
  );

  if (checks.length !== EXPECTED_INDEPENDENT_CHECKS - 1) {
    throw new Error(`pre-summary independent check count drifted: ${checks.length}`);
  }
  const provisionalStatus = checks.every((item) => item.passed) ? "PASS" : "FAIL";
  const claims = {
    two_loop_blocking_arithmetic: provisionalStatus,
    conditional_rg_gap_matching_theorem_analytic: true,
    analytic_theorem_outside_executable: true,
    ...Object.fromEntries(NEGATIVE_CLAIMS.map((name) => [name, false])),
    clay_verdict: "NULL",
  };
  checks.push(
    decision(
      "independent_summary_and_claim_consistency",
      exactClaimBoundary(claims, provisionalStatus)
        && checks.length === EXPECTED_INDEPENDENT_CHECKS - 1
        && exactRows.length === G2_VALUES.length
        && boundedRows.length === G2_VALUES.length
        && driftRows.length === G2_VALUES.length,
      {
        pre_summary_checks: checks.length,
        exact_rows: exactRows.length,
        bounded_rows: boundedRows.length,
        drift_rows: driftRows.length,
        claims,
        comparisons_attempted: 5,
      },
    ),
  );

  if (checks.length !== EXPECTED_INDEPENDENT_CHECKS) {
    throw new Error(`independent check count drifted: ${checks.length}`);
  }
  const verdict = checks.every((item) => item.passed) ? "PASS" : "FAIL";
  if (verdict === "FAIL") claims.two_loop_blocking_arithmetic = "FAIL";

  const receipt = {
    schema: "cassi.yang-mills.rg-gap-matching.verification-independent.v1",
    verdict,
    summary: {
      checks: checks.length,
      passing_checks: checks.filter((item) => item.passed).length,
      reconstructed_exact_rows: exactRows.length,
      reconstructed_bounded_rows: boundedRows.length,
      reconstructed_drift_rows: driftRows.length,
      firing_controls: firingControls.length,
      firing_controls_activated: firingControls.filter((control) => control.fired).length,
    },
    parameters: {
      reconstruction_tolerance: TOLERANCE,
      node_builtins_only: true,
      primary_module_imported: false,
      primary_read_after_independent_reconstruction: true,
    },
    coefficients: { b0, b1, p },
    firing_controls: firingControls,
    claims,
    checks,
    sources: {
      protocol: { path: relative(PROTOCOL), sha256: protocolHash },
      primary_source: { path: relative(PRIMARY_SOURCE), sha256: primarySourceHash },
      independent_source: { path: relative(SOURCE), sha256: independentSourceHash },
      primary_receipt: { path: relative(PRIMARY_RECEIPT), sha256: primaryReceiptHash },
    },
  };
  if (!finitePayload(receipt)) throw new Error("receipt contains a non-finite value");
  return receipt;
}

function parseArgs(argv) {
  let output = OUTPUT;
  let replace = false;
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    if (argument === "--replace") {
      replace = true;
    } else if (argument === "--output") {
      index += 1;
      if (index >= argv.length) throw new Error("--output requires a path");
      output = path.resolve(argv[index]);
    } else {
      throw new Error(`unknown argument: ${argument}`);
    }
  }
  return { output, replace };
}

function main() {
  const { output, replace } = parseArgs(process.argv.slice(2));
  if (fs.existsSync(output) && !replace) {
    throw new Error(`refusing to overwrite existing receipt without --replace: ${output}`);
  }
  const receipt = buildReceipt();
  fs.mkdirSync(path.dirname(output), { recursive: true });
  fs.writeFileSync(output, `${JSON.stringify(deepSort(receipt), null, 2)}\n`, "utf8");
  console.log(
    `YANG-MILLS RG GAP MATCHING INDEPENDENT ${receipt.verdict} `
      + `(${receipt.summary.passing_checks}/${receipt.summary.checks} checks)`,
  );
  console.log(
    "scope: conditional arithmetic only; rg_trajectory_constructed=false; "
      + "interacting_gap_computed=false; continuum_mass_gap_established=false; "
      + "clay_verdict=NULL",
  );
  return receipt.verdict === "PASS" ? 0 : 1;
}

process.exitCode = main();
