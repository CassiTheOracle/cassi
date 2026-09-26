#!/usr/bin/env node
/**
 * Independent verifier for the renormalized SU(2) gap and volume scaling
 * diagnostic. Uses only Node built-ins and imports no primary implementation.
 * This checks frozen scale arithmetic; it does not compute a Yang-Mills gap.
 */

import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const SOURCE = fileURLToPath(import.meta.url);
const ROOT = path.resolve(path.dirname(SOURCE), "..");
const PROTOCOL = path.join(ROOT, "computations", "yang-mills-renormalized-gap-scaling-prereg.md");
const PRIMARY_SOURCE = path.join(
  ROOT,
  "computations",
  "verify_yang_mills_renormalized_gap_scaling.py",
);
const PRIMARY_RECEIPT = path.join(
  ROOT,
  "runs",
  "yang-mills-renormalized-gap-scaling",
  "verification.json",
);
const OUTPUT = path.join(
  ROOT,
  "runs",
  "yang-mills-renormalized-gap-scaling",
  "verification-independent.json",
);

const G2_VALUES = [0.8, 0.5, 0.3, 0.2, 0.1, 0.05];
const TOLERANCE = 5e-13;
const EXPECTED_PRIMARY_CHECKS = 80;
const EXPECTED_PRIMARY_ROW_CHECKS = 60;
const EXPECTED_PRIMARY_TOP_CHECKS = 20;
const EXPECTED_INDEPENDENT_CHECKS = 20;
const EXPECTED_FIRING_CONTROLS = 6;

const COLOR_COUNT = 2;
const PI2 = Math.PI * Math.PI;
const LOOP_DENOMINATOR = 16 * PI2;
const b0 = (11 * COLOR_COUNT) / (3 * LOOP_DENOMINATOR);
const b1 = (34 * COLOR_COUNT * COLOR_COUNT) / (3 * LOOP_DENOMINATOR * LOOP_DENOMINATOR);
const p = b1 / (2 * b0 * b0);
const couplingFactor = 2 ** 0.25;
const matchedGapRatio = 7 / 4;
const syntheticGap = 13 / 10;

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

function logScale(g2) {
  return -1 / (2 * b0 * g2) - p * Math.log(b0 * g2);
}

function logScaleViaWilsonBeta(g2) {
  const betaWilson = 4 / g2;
  return (
    (-3 * PI2 * betaWilson) / 11
    + (51 / 121) * Math.log((6 * PI2 * betaWilson) / 11)
  );
}

function logHamiltonianScale(gH2) {
  return (
    (-6 * Math.SQRT2 * PI2) / (11 * gH2)
    + (51 / 121) * Math.log((12 * Math.SQRT2 * PI2) / (11 * gH2))
  );
}

function reconstructRow(g2) {
  const g = Math.sqrt(g2);
  const logF = logScale(g2);
  const scale = Math.exp(logF);
  const gH2 = g2 / Math.SQRT2;
  const derivative = 1 / (b0 * g ** 3) - (2 * p) / g;
  const betaFromDerivative = -1 / derivative;
  const betaRational = -(b0 * g ** 3) / (1 - (b1 / b0) * g2);
  const betaTwoLoop = -(b0 * g ** 3) - b1 * g ** 5;
  const betaRemainder = betaFromDerivative - betaTwoLoop;
  const deltaW = (g2 * syntheticGap) / 2;
  const deltaH = deltaW / Math.SQRT2;

  return {
    g0_squared: g2,
    g0: g,
    beta_lattice: 4 / g2,
    log_scale_from_coupling: logF,
    log_scale_from_beta: logScaleViaWilsonBeta(g2),
    scale,
    g_h_squared: gH2,
    log_scale_hamiltonian: logHamiltonianScale(gH2),
    beta_from_log_derivative: betaFromDerivative,
    beta_rational: betaRational,
    beta_two_loop_truncation: betaTwoLoop,
    beta_remainder: betaRemainder,
    beta_remainder_over_g7: betaRemainder / g ** 7,
    beta_remainder_over_g7_expected: -(b1 * b1 / b0) / (1 - (b1 / b0) * g2),
    volume_log_products: {
      fixed_count: Math.log(64) + logF,
      polynomial_count: -4 * Math.log(g2) + logF,
      fixed_box: Math.log(8),
      thermodynamic_inverse_g2: -Math.log(g2),
      thermodynamic_log_scale: Math.log(-logF),
    },
    gap_log_ratios: {
      constant: Math.log(0.25) - logF,
      polynomial: 3 * Math.log(g2) - logF,
      subscale: Math.log(g2),
      matched: Math.log(matchedGapRatio),
      isolated_square: Math.log(2 * Math.SQRT2) - logHamiltonianScale(gH2),
    },
    synthetic_gap_map: {
      widehat_delta: syntheticGap,
      delta_w: deltaW,
      delta_h_from_energy_map: deltaH,
      delta_h_from_prefactor: (gH2 * syntheticGap) / 2,
      recovered_h_widehat_delta: (2 * deltaH) / gH2,
    },
  };
}

function scaledDifference(left, right) {
  return Math.abs(left - right) / Math.max(1, Math.abs(left), Math.abs(right));
}

function compareFlatRows(primaryRows, independentRows) {
  const scalarKeys = [
    "g0_squared",
    "g0",
    "beta_lattice",
    "log_scale_from_coupling",
    "log_scale_from_beta",
    "scale",
    "g_h_squared",
    "log_scale_hamiltonian",
    "beta_from_log_derivative",
    "beta_rational",
    "beta_two_loop_truncation",
    "beta_remainder",
    "beta_remainder_over_g7",
    "beta_remainder_over_g7_expected",
  ];
  const nestedGroups = ["volume_log_products", "gap_log_ratios", "synthetic_gap_map"];
  let maximum = 0;
  let comparisons = 0;
  for (let index = 0; index < independentRows.length; index += 1) {
    const primary = primaryRows[index];
    const independent = independentRows[index];
    for (const key of scalarKeys) {
      maximum = Math.max(maximum, scaledDifference(primary[key], independent[key]));
      comparisons += 1;
    }
    for (const group of nestedGroups) {
      for (const [key, value] of Object.entries(independent[group])) {
        maximum = Math.max(maximum, scaledDifference(primary[group][key], value));
        comparisons += 1;
      }
    }
  }
  return { maximum, comparisons };
}

function volumeClassification(cancelExponent, residualKind) {
  const remainingF = 1 - cancelExponent;
  if (remainingF > 0) return "COLLAPSES_TO_ZERO";
  if (remainingF < 0) return "DIVERGES_TO_INFINITY";
  if (residualKind === "constant") return "FIXED_PHYSICAL_SIZE";
  if (["inverse_g2", "log_scale"].includes(residualKind)) return "DIVERGES_TO_INFINITY";
  throw new Error(`unsupported volume residual ${residualKind}`);
}

function gapClassification(fExponent, g2Exponent) {
  const remainingF = fExponent - 1;
  if (remainingF < 0) return "DIVERGES_TO_INFINITY";
  if (remainingF > 0) return "VANISHES_TO_ZERO";
  if (g2Exponent > 0) return "VANISHES_TO_ZERO";
  if (g2Exponent < 0) return "DIVERGES_TO_INFINITY";
  return "FINITE_POSITIVE";
}

function coefficientTripletValid(candidateB0, candidateB1, candidateP) {
  return (
    absoluteClose(candidateB0, 11 / (24 * PI2))
    && absoluteClose(candidateB1, 17 / (96 * PI2 * PI2))
    && absoluteClose(candidateP, 51 / 121)
  );
}

function betaPowerValid(candidatePower) {
  return (
    absoluteClose(1 / (8 * b0), (3 * PI2) / 11)
    && absoluteClose(1 / (4 * b0), (6 * PI2) / 11)
    && absoluteClose(candidatePower, 51 / 121)
  );
}

function volumeDiverges(values) {
  return strictlyIncreasing(values) && values.at(-1) > values[0];
}

function finitePositiveRatios(values) {
  const lower = Math.log(0.5);
  const upper = Math.log(4);
  return values.every((value) => lower <= value && value <= upper);
}

function couplingMapValid(factor) {
  return G2_VALUES.every((gW2) => {
    const gH2 = gW2 / factor ** 2;
    return absoluteClose(logScale(gW2), logHamiltonianScale(gH2));
  });
}

function gapMapValid(deltaFactor) {
  return G2_VALUES.every((gW2) => {
    const gH2 = gW2 / Math.SQRT2;
    const deltaW = (gW2 * syntheticGap) / 2;
    return absoluteClose((2 * deltaFactor * deltaW) / gH2, syntheticGap);
  });
}

function reconstructFiringControls(rows) {
  const inverseVolume = rows.map(
    (row) => row.volume_log_products.thermodynamic_inverse_g2,
  );
  const fixedBox = rows.map((row) => row.volume_log_products.fixed_box);
  const matched = rows.map((row) => row.gap_log_ratios.matched);
  const constantGap = rows.map((row) => row.gap_log_ratios.constant);
  const controls = [
    {
      name: "omit_two_loop_power",
      unmutated_passed: betaPowerValid(p),
      mutation_passed: betaPowerValid(0),
    },
    {
      name: "replace_su2_b0_with_su3_b0",
      unmutated_passed: coefficientTripletValid(b0, b1, p),
      mutation_passed: coefficientTripletValid(11 / (16 * PI2), b1, p),
    },
    {
      name: "mislabel_fixed_box_as_thermodynamic",
      unmutated_passed: volumeDiverges(inverseVolume),
      mutation_passed: volumeDiverges(fixedBox),
    },
    {
      name: "mislabel_constant_gap_as_finite_mass",
      unmutated_passed: finitePositiveRatios(matched),
      mutation_passed: finitePositiveRatios(constantGap),
    },
    {
      name: "reverse_wilson_hamiltonian_coupling_map",
      unmutated_passed: couplingMapValid(couplingFactor),
      mutation_passed: couplingMapValid(1 / couplingFactor),
    },
    {
      name: "omit_gap_time_rescaling",
      unmutated_passed: gapMapValid(1 / Math.SQRT2),
      mutation_passed: gapMapValid(1),
    },
  ];
  for (const control of controls) {
    control.fired = control.unmutated_passed && !control.mutation_passed;
    control.comparisons_attempted = 2;
  }
  return controls;
}

function exactClaimBoundary(claims, executableStatus) {
  const negatives = [
    "interacting_gap_computed",
    "continuum_trajectory_constructed",
    "thermodynamic_limit_constructed",
    "os_axioms_established",
    "euclidean_covariance_restored",
    "nontrivial_continuum_limit_established",
    "volume_uniform_mass_gap_established",
    "continuum_mass_gap_established",
  ];
  return (
    claims.two_loop_scaling_arithmetic === executableStatus
    && claims.double_scaling_necessity_diagnostic === executableStatus
    && claims.conditional_continuum_bridge_analytic === true
    && claims.analytic_theorem_outside_executable === true
    && negatives.every((name) => claims[name] === false)
    && claims.clay_verdict === "NULL"
  );
}

function buildReceipt() {
  if (!fs.existsSync(PRIMARY_RECEIPT)) {
    throw new Error(`primary receipt not found: ${PRIMARY_RECEIPT}`);
  }
  const primaryBytes = fs.readFileSync(PRIMARY_RECEIPT);
  const primary = JSON.parse(primaryBytes.toString("utf8"));
  const rows = G2_VALUES.map(reconstructRow);
  const rowComparison = compareFlatRows(primary.rows, rows);
  const firingControls = reconstructFiringControls(rows);

  const volume = {
    fixed_count: volumeClassification(0, "constant"),
    polynomial_count: volumeClassification(0, "constant"),
    fixed_box: volumeClassification(1, "constant"),
    thermodynamic_inverse_g2: volumeClassification(1, "inverse_g2"),
    thermodynamic_log_scale: volumeClassification(1, "log_scale"),
  };
  const gap = {
    constant: gapClassification(0, 0),
    polynomial: gapClassification(0, 3),
    subscale: gapClassification(1, 1),
    matched: gapClassification(1, 0),
    isolated_square: gapClassification(0, 0),
  };

  const primarySourceHash = sha256(PRIMARY_SOURCE);
  const independentSourceHash = sha256(SOURCE);
  const protocolHash = sha256(PROTOCOL);
  const primaryReceiptHash = crypto.createHash("sha256").update(primaryBytes).digest("hex");

  const logValues = rows.map((row) => row.log_scale_from_coupling);
  const derivativeScaledErrors = rows.map((row) =>
    scaledDifference(row.beta_from_log_derivative, row.beta_rational));
  const derivativeCoefficientErrors = rows.map((row) =>
    scaledDifference(row.beta_remainder_over_g7, row.beta_remainder_over_g7_expected));
  const volumeSeries = Object.fromEntries(
    Object.keys(rows[0].volume_log_products).map((name) => [
      name,
      rows.map((row) => row.volume_log_products[name]),
    ]),
  );
  const gapSeries = Object.fromEntries(
    Object.keys(rows[0].gap_log_ratios).map((name) => [
      name,
      rows.map((row) => row.gap_log_ratios[name]),
    ]),
  );

  const checks = [
    decision(
      "primary_schema_and_verdict",
      primary.schema === "cassi.yang-mills.renormalized-gap-scaling.verification.v1"
        && primary.verdict === "PASS",
      { schema: primary.schema, verdict: primary.verdict },
    ),
    decision(
      "primary_frozen_counts",
      primary.summary.checks === EXPECTED_PRIMARY_CHECKS
        && primary.summary.passing_checks === EXPECTED_PRIMARY_CHECKS
        && primary.summary.rows === G2_VALUES.length
        && primary.summary.row_checks === EXPECTED_PRIMARY_ROW_CHECKS
        && primary.summary.top_level_checks === EXPECTED_PRIMARY_TOP_CHECKS,
      primary.summary,
    ),
    decision(
      "protocol_hash_binding",
      primary.sources.protocol.path === relative(PROTOCOL)
        && primary.sources.protocol.sha256 === protocolHash,
      { path: relative(PROTOCOL), sha256: protocolHash },
    ),
    decision(
      "source_hash_bindings",
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
      "coefficient_reconstruction",
      coefficientTripletValid(b0, b1, p)
        && relativeClose(primary.coefficients.b0, b0)
        && relativeClose(primary.coefficients.b1, b1)
        && relativeClose(primary.coefficients.p, p),
      { b0, b1, p, comparisons_attempted: 6 },
      TOLERANCE,
    ),
    decision(
      "row_schedule_reconstructed",
      primary.rows.length === rows.length
        && primary.rows.every((row, index) => row.g0_squared === G2_VALUES[index])
        && primary.rows.every((row) => row.checks.length === 10 && row.checks.every((item) => item.passed)),
      { rows: rows.length, primary_rows: primary.rows.length, checks_per_row: 10 },
    ),
    decision(
      "row_numeric_values_reconstructed",
      rowComparison.maximum <= TOLERANCE,
      { maximum_scaled_error: rowComparison.maximum, comparisons_attempted: rowComparison.comparisons },
      TOLERANCE,
    ),
    decision(
      "wilson_scale_forms_reconstructed",
      rows.every((row) => absoluteClose(row.log_scale_from_coupling, row.log_scale_from_beta))
        && strictlyDecreasing(logValues)
        && rows.every((row) => row.scale > 0 && row.scale < 1),
      { log_scales: logValues, comparisons_attempted: 3 * rows.length - 1 },
      TOLERANCE,
    ),
    decision(
      "derivative_beta_identity_reconstructed",
      Math.max(...derivativeScaledErrors) <= TOLERANCE,
      { maximum_scaled_error: Math.max(...derivativeScaledErrors), comparisons_attempted: rows.length },
      TOLERANCE,
    ),
    decision(
      "derivative_order_g7_reconstructed",
      Math.max(...derivativeCoefficientErrors) <= TOLERANCE
        && strictlyDecreasing(rows.map((row) => Math.abs(row.beta_remainder / row.g0 ** 5))),
      {
        maximum_scaled_error: Math.max(...derivativeCoefficientErrors),
        remainder_over_g7: rows.map((row) => row.beta_remainder_over_g7),
        comparisons_attempted: 2 * rows.length - 1,
      },
      TOLERANCE,
    ),
    decision(
      "volume_schedule_values_reconstructed",
      Object.entries(volumeSeries).every(([name, values]) =>
        values.every((value, index) => relativeClose(value, primary.rows[index].volume_log_products[name]))),
      { schedules: Object.keys(volumeSeries), rows: rows.length, comparisons_attempted: 5 * rows.length },
      TOLERANCE,
    ),
    decision(
      "gap_schedule_values_reconstructed",
      Object.entries(gapSeries).every(([name, values]) =>
        values.every((value, index) => relativeClose(value, primary.rows[index].gap_log_ratios[name]))),
      { schedules: Object.keys(gapSeries), rows: rows.length, comparisons_attempted: 5 * rows.length },
      TOLERANCE,
    ),
    decision(
      "volume_classifications_reconstructed",
      Object.keys(volume).length === Object.keys(primary.classifications.volume).length
        && Object.entries(volume).every(
          ([name, value]) => primary.classifications.volume[name] === value,
        )
        && strictlyDecreasing(volumeSeries.fixed_count)
        && strictlyDecreasing(volumeSeries.polynomial_count)
        && volumeSeries.fixed_box.every((value) => absoluteClose(value, Math.log(8)))
        && strictlyIncreasing(volumeSeries.thermodynamic_inverse_g2)
        && strictlyIncreasing(volumeSeries.thermodynamic_log_scale),
      { classifications: volume, comparisons_attempted: 5 + 4 * (rows.length - 1) + rows.length },
    ),
    decision(
      "gap_classifications_reconstructed",
      Object.keys(gap).length === Object.keys(primary.classifications.gap).length
        && Object.entries(gap).every(
          ([name, value]) => primary.classifications.gap[name] === value,
        )
        && strictlyIncreasing(gapSeries.constant)
        && strictlyIncreasing(gapSeries.polynomial)
        && strictlyDecreasing(gapSeries.subscale)
        && finitePositiveRatios(gapSeries.matched)
        && strictlyIncreasing(gapSeries.isolated_square),
      { classifications: gap, comparisons_attempted: 5 + 4 * (rows.length - 1) + rows.length },
    ),
    decision(
      "hamiltonian_scale_map_reconstructed",
      couplingMapValid(couplingFactor)
        && rows.every((row) => absoluteClose(row.log_scale_from_coupling, row.log_scale_hamiltonian)),
      {
        maximum_absolute_error: Math.max(
          ...rows.map((row) => Math.abs(row.log_scale_from_coupling - row.log_scale_hamiltonian)),
        ),
        comparisons_attempted: 2 * rows.length,
      },
      TOLERANCE,
    ),
    decision(
      "hamiltonian_gap_normalization_reconstructed",
      gapMapValid(1 / Math.SQRT2)
        && rows.every((row) =>
          absoluteClose(
            row.synthetic_gap_map.delta_h_from_energy_map,
            row.synthetic_gap_map.delta_h_from_prefactor,
          )
          && absoluteClose(row.synthetic_gap_map.recovered_h_widehat_delta, syntheticGap)),
      { rows: rows.length, comparisons_attempted: 3 * rows.length },
      TOLERANCE,
    ),
    decision(
      "all_firing_controls_reconstructed",
      firingControls.length === EXPECTED_FIRING_CONTROLS
        && firingControls.every((control) => control.fired)
        && primary.firing_controls.length === EXPECTED_FIRING_CONTROLS
        && firingControls.every((control, index) =>
          control.name === primary.firing_controls[index].name
          && primary.firing_controls[index].fired === true),
      { controls: firingControls, comparisons_attempted: 4 * firingControls.length },
      { controls: EXPECTED_FIRING_CONTROLS, fired: EXPECTED_FIRING_CONTROLS },
    ),
    decision(
      "finite_payload_and_attempted_comparisons",
      finitePayload(primary)
        && finitePayload(rows)
        && finitePayload(firingControls)
        && Object.values(primary.attempted_comparisons).every((count) => Number.isInteger(count) && count > 0),
      {
        primary_comparison_families: Object.keys(primary.attempted_comparisons).length,
        rows_checked: rows.length,
        firing_controls_checked: firingControls.length,
      },
    ),
    decision(
      "primary_claim_boundary",
      exactClaimBoundary(primary.claims, "PASS"),
      primary.claims,
    ),
  ];

  if (checks.length !== EXPECTED_INDEPENDENT_CHECKS - 1) {
    throw new Error(`pre-claim independent check count drifted: ${checks.length}`);
  }

  const preliminaryPass = checks.every((item) => item.passed);
  const executableStatus = preliminaryPass ? "PASS" : "FAIL";
  const claims = {
    two_loop_scaling_arithmetic: executableStatus,
    double_scaling_necessity_diagnostic: executableStatus,
    conditional_continuum_bridge_analytic: true,
    analytic_theorem_outside_executable: true,
    interacting_gap_computed: false,
    continuum_trajectory_constructed: false,
    thermodynamic_limit_constructed: false,
    os_axioms_established: false,
    euclidean_covariance_restored: false,
    nontrivial_continuum_limit_established: false,
    volume_uniform_mass_gap_established: false,
    continuum_mass_gap_established: false,
    clay_verdict: "NULL",
  };
  checks.push(decision("independent_claim_boundary", exactClaimBoundary(claims, executableStatus), claims));

  if (checks.length !== EXPECTED_INDEPENDENT_CHECKS) {
    throw new Error(`independent check count drifted: ${checks.length}`);
  }
  const verdict = checks.every((item) => item.passed) ? "PASS" : "FAIL";
  if (verdict === "FAIL") {
    claims.two_loop_scaling_arithmetic = "FAIL";
    claims.double_scaling_necessity_diagnostic = "FAIL";
  }

  return {
    schema: "cassi.yang-mills.renormalized-gap-scaling.verification-independent.v1",
    verdict,
    summary: {
      checks: checks.length,
      passing_checks: checks.filter((item) => item.passed).length,
      reconstructed_rows: rows.length,
      firing_controls: firingControls.length,
      firing_controls_activated: firingControls.filter((control) => control.fired).length,
    },
    parameters: {
      reconstruction_tolerance: TOLERANCE,
      node_builtins_only: true,
      primary_module_imported: false,
    },
    coefficients: { b0, b1, p },
    classifications: { volume, gap },
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
  fs.writeFileSync(output, `${JSON.stringify(receipt, null, 2)}\n`, "utf8");
  console.log(
    `RENORMALIZED GAP SCALING INDEPENDENT ${receipt.verdict} `
      + `(${receipt.summary.passing_checks}/${receipt.summary.checks} checks)`,
  );
  console.log(
    "scope: arithmetic diagnostic only; interacting_gap_computed=false; "
      + "continuum_mass_gap_established=false; clay_verdict=NULL",
  );
  return receipt.verdict === "PASS" ? 0 : 1;
}

process.exitCode = main();
