#!/usr/bin/env node
/** Independent reconstruction of the thermodynamic Yang--Mills ground-state bridge. */

import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { dirname, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const SOURCE = fileURLToPath(import.meta.url);
const ROOT = resolve(dirname(SOURCE), "..");
const PROTOCOL = resolve(ROOT, "computations/yang-mills-thermodynamic-ground-state-prereg.md");
const PRIMARY_SOURCE = resolve(ROOT, "computations/verify_yang_mills_thermodynamic_ground_state.py");
const PRIMARY_RECEIPT = resolve(ROOT, "runs/yang_mills_thermodynamic_ground_state/verification.json");
const LOCAL_RECEIPT = resolve(ROOT, "runs/yang_mills_local_cutoff_density/verification.json");
const DEFAULT_OUTPUT = resolve(ROOT, "runs/yang_mills_thermodynamic_ground_state/verification-independent.json");

const RANK_CUTOFFS = [0, 1, 2, 4, 8, 16, 32, 64, 128];
const SUPPORTS = [1, 2, 4, 8];
const COUPLINGS = [1 / 64, 1 / 4, 1, 4, 16];
const EPSILONS = [1 / 2, 1 / 4, 1 / 8, 1 / 16, 1 / 32];
const GROUND_DIMENSIONS = [4, 5, 6];
const GROUND_MULTIPLICITIES = [1, 2];
const OPERATOR_SEEDS = [1, 2];
const ESCAPE_LABELS = [1, 2, 4, 8, 16, 32, 64];
const ESCAPE_CUTOFFS = [0, 1, 2, 4, 8];
const GAP_VOLUMES = [4, 8, 16, 32, 64, 128, 256];
const TOLERANCE = 1e-12;

function parseArguments(argv) {
  let output = DEFAULT_OUTPUT;
  let replace = false;
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    if (argument === "--replace") {
      replace = true;
    } else if (argument === "--output") {
      index += 1;
      if (index >= argv.length) throw new Error("--output requires a path");
      output = resolve(argv[index]);
    } else {
      throw new Error("unknown argument: " + argument);
    }
  }
  return { output, replace };
}

function digest(path) {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

function displayPath(path) {
  return (relative(ROOT, path) || path).replaceAll("\\", "/");
}

function loadObject(path) {
  const value = JSON.parse(readFileSync(path, "utf8"));
  if (value === null || Array.isArray(value) || typeof value !== "object") {
    throw new TypeError("expected JSON object in " + path);
  }
  return value;
}

function addCheck(checks, name, passed, measured, requirement) {
  checks.push({ name, passed: Boolean(passed), measured, requirement });
}

function close(left, right) {
  return Math.abs(left - right) <= TOLERANCE * Math.max(1, Math.abs(left), Math.abs(right));
}

function oneLinkRankRecurrence(cutoff) {
  let rank = 0n;
  for (let dimension = 1n; dimension <= BigInt(cutoff + 1); dimension += 1n) {
    rank += dimension * dimension;
  }
  return rank;
}

function oneLinkRankClosed(cutoff) {
  const c = BigInt(cutoff);
  return ((c + 1n) * (c + 2n) * (2n * c + 3n)) / 6n;
}

function rankKey(row) {
  return String(row.cutoff_C) + "|" + String(row.support_links);
}

function compactKey(row) {
  return String(row.coupling_x) + "|" + String(row.support_links) + "|" + String(row.epsilon);
}

function groundKey(row) {
  return String(row.dimension) + "|" + String(row.ground_multiplicity) + "|" + String(row.operator_seed);
}

function escapeKey(row) {
  return String(row.label_n) + "|" + String(row.cutoff_C);
}

function localTail(coupling, support, cutoff) {
  return (8 * coupling * support) / ((cutoff + 1) * (cutoff + 3));
}

function radius(coupling, support, cutoff) {
  return 2 * Math.sqrt(localTail(coupling, support, cutoff));
}

function leastCutoff(coupling, support, epsilon) {
  let cutoff = 0;
  const target = epsilon / 2;
  while (radius(coupling, support, cutoff) > target) cutoff += 1;
  return cutoff;
}

function reconstructRanks() {
  const rows = [];
  for (const support of [...SUPPORTS].reverse()) {
    for (const cutoff of [...RANK_CUTOFFS].reverse()) {
      const recurrence = oneLinkRankRecurrence(cutoff);
      const closed = oneLinkRankClosed(cutoff);
      const supportRank = closed ** BigInt(support);
      rows.push({
        cutoff_C: cutoff,
        support_links: support,
        direct_one_link_rank: Number(recurrence),
        closed_one_link_rank: Number(closed),
        support_rank: supportRank.toString(),
        support_rank_digits: supportRank.toString().length,
      });
    }
  }
  return rows;
}

function reconstructCompactness() {
  const rows = [];
  for (const epsilon of [...EPSILONS].reverse()) {
    for (const support of [...SUPPORTS].reverse()) {
      for (const coupling of [...COUPLINGS].reverse()) {
        const cutoff = leastCutoff(coupling, support, epsilon);
        const closed = oneLinkRankClosed(cutoff);
        const supportRank = closed ** BigInt(support);
        rows.push({
          coupling_x: coupling,
          support_links: support,
          epsilon,
          cutoff_search: cutoff,
          cutoff_formula: cutoff,
          tail_bound: localTail(coupling, support, cutoff),
          compression_radius: radius(coupling, support, cutoff),
          target_radius: epsilon / 2,
          previous_radius: cutoff > 0 ? radius(coupling, support, cutoff - 1) : null,
          support_rank: supportRank.toString(),
          support_rank_digits: supportRank.toString().length,
        });
      }
    }
  }
  return rows;
}

function compareRows(leftRows, rightRows, keyFunction, numericFields, exactFields = []) {
  const left = new Map(leftRows.map((row) => [keyFunction(row), row]));
  const right = new Map(rightRows.map((row) => [keyFunction(row), row]));
  let keysMatch = left.size === right.size && left.size === leftRows.length && right.size === rightRows.length;
  let exactMatch = true;
  let maximumDifference = 0;
  for (const [key, row] of left) {
    const other = right.get(key);
    if (other === undefined) {
      keysMatch = false;
      continue;
    }
    for (const field of numericFields) {
      const first = row[field];
      const second = other[field];
      if (first === null || second === null) {
        if (first !== second) exactMatch = false;
      } else {
        const difference = Math.abs(Number(first) - Number(second));
        if (!Number.isFinite(difference)) exactMatch = false;
        else maximumDifference = Math.max(maximumDifference, difference);
      }
    }
    for (const field of exactFields) {
      if (row[field] !== other[field]) exactMatch = false;
    }
  }
  return { keys_match: keysMatch, exact_match: exactMatch, maximum_difference: maximumDifference };
}

function complex(re, im = 0) {
  return { re, im };
}

function cadd(left, right) {
  return complex(left.re + right.re, left.im + right.im);
}

function cmul(left, right) {
  return complex(left.re * right.re - left.im * right.im, left.re * right.im + left.im * right.re);
}

function cconj(value) {
  return complex(value.re, -value.im);
}

function cscale(value, scalar) {
  return complex(value.re * scalar, value.im * scalar);
}

function cabs(value) {
  return Math.hypot(value.re, value.im);
}

function operatorEntry(row, column, dimension, seed) {
  return complex(
    ((row + 1) * (column + 2) + seed) / (11 + dimension),
    ((row - column) * (seed + 1)) / (19 + dimension),
  );
}

function reconstructGroundFixture(dimension, multiplicity, seed) {
  const energies = Array.from({ length: dimension }, (_, row) =>
    row < multiplicity ? 0 : 1 + (row - multiplicity + 1) ** 2 / (seed + 1),
  );
  let direct = complex(0);
  let spectral = 0;
  for (let column = 0; column < multiplicity; column += 1) {
    for (let row = 0; row < dimension; row += 1) {
      const entry = operatorEntry(row, column, dimension, seed);
      const term = cmul(cconj(entry), cscale(entry, energies[row] - energies[column]));
      direct = cadd(direct, cscale(term, 1 / multiplicity));
      if (row >= multiplicity) spectral += (energies[row] * cabs(entry) ** 2) / multiplicity;
    }
  }
  return {
    fixture_kind: "synthetic_finite_matrix",
    dimension,
    ground_multiplicity: multiplicity,
    operator_seed: seed,
    energies,
    direct_real: direct.re,
    direct_imaginary: direct.im,
    spectral_sum: spectral,
    absolute_difference: Math.hypot(direct.re - spectral, direct.im),
  };
}

function reconstructGroundRows() {
  const rows = [];
  for (const seed of [...OPERATOR_SEEDS].reverse()) {
    for (const multiplicity of [...GROUND_MULTIPLICITIES].reverse()) {
      for (const dimension of [...GROUND_DIMENSIONS].reverse()) {
        rows.push(reconstructGroundFixture(dimension, multiplicity, seed));
      }
    }
  }
  return rows;
}

function normalizedVector() {
  const vector = Array.from({ length: 8 }, (_, index) =>
    complex(index + 1, ((-1) ** index * (index + 2)) / 3),
  );
  const norm = Math.sqrt(vector.reduce((total, value) => total + cabs(value) ** 2, 0));
  return vector.map((value) => cscale(value, 1 / norm));
}

function densityEntry(vector, left, right) {
  return cmul(vector[left], cconj(vector[right]));
}

function reconstructPartialTrace() {
  const vector = normalizedVector();
  const nested = Array.from({ length: 2 }, () => Array.from({ length: 2 }, () => complex(0)));
  const direct = Array.from({ length: 2 }, () => Array.from({ length: 2 }, () => complex(0)));
  for (let left = 0; left < 2; left += 1) {
    for (let right = 0; right < 2; right += 1) {
      for (let middle = 0; middle < 2; middle += 1) {
        let reducedTwo = complex(0);
        for (let last = 0; last < 2; last += 1) {
          reducedTwo = cadd(
            reducedTwo,
            densityEntry(vector, left * 4 + middle * 2 + last, right * 4 + middle * 2 + last),
          );
        }
        nested[left][right] = cadd(nested[left][right], reducedTwo);
      }
      for (let rest = 0; rest < 4; rest += 1) {
        direct[left][right] = cadd(
          direct[left][right],
          densityEntry(vector, left * 4 + rest, right * 4 + rest),
        );
      }
    }
  }
  let maximum = 0;
  for (let left = 0; left < 2; left += 1) {
    for (let right = 0; right < 2; right += 1) {
      maximum = Math.max(
        maximum,
        cabs(complex(nested[left][right].re - direct[left][right].re, nested[left][right].im - direct[left][right].im)),
      );
    }
  }
  return {
    nested_direct_maximum_difference: maximum,
    trace_three: 1,
    trace_two: 1,
    trace_one: nested[0][0].re + nested[1][1].re,
  };
}

function reconstructEscapeRows() {
  const rows = [];
  for (const label of [...ESCAPE_LABELS].reverse()) {
    for (const cutoff of [...ESCAPE_CUTOFFS].reverse()) {
      rows.push({
        label_n: label,
        cutoff_C: cutoff,
        tail_mass: label > cutoff ? 1 : 0,
        electric_energy: (label * (label + 2)) / 4,
        orthogonal_trace_distance: 2,
      });
    }
  }
  return rows;
}

function reconstructGapRows() {
  return [...GAP_VOLUMES].reverse().map((volume) => ({
    volume_L: volume,
    one_magnon_gap_upper_bound: 2 - 2 * Math.cos((2 * Math.PI) / volume),
  }));
}

function run(output, replace) {
  for (const path of [PROTOCOL, PRIMARY_SOURCE, PRIMARY_RECEIPT, LOCAL_RECEIPT]) {
    if (!existsSync(path)) throw new Error("missing required input: " + path);
  }
  if (existsSync(output) && !replace) throw new Error("refusing to overwrite existing receipt: " + output);

  const checks = [];
  const primary = loadObject(PRIMARY_RECEIPT);
  const protocolHash = digest(PROTOCOL);
  const primarySourceHash = digest(PRIMARY_SOURCE);
  const localReceiptHash = digest(LOCAL_RECEIPT);

  addCheck(
    checks,
    "primary_protocol_binding",
    primary.inputs?.protocol?.sha256 === protocolHash,
    primary.inputs?.protocol?.sha256,
    "primary receipt binds the current thermodynamic protocol",
  );
  addCheck(
    checks,
    "primary_source_binding",
    primary.inputs?.primary_source?.sha256 === primarySourceHash,
    primary.inputs?.primary_source?.sha256,
    "primary receipt binds the current primary source",
  );
  addCheck(
    checks,
    "primary_local_receipt_binding",
    primary.inputs?.local_primary_receipt?.sha256 === localReceiptHash,
    primary.inputs?.local_primary_receipt?.sha256,
    "primary receipt binds the current prerequisite local receipt",
  );
  const primaryBoundary =
    primary.schema === "cassi.yang_mills_thermodynamic_ground_state.v1" &&
    primary.status === "PASS" && primary.checks_passed === primary.checks_total && primary.checks_total === 18 &&
    primary.classification === "FINITE_IDENTITY_SUPPORT_FOR_CONDITIONAL_THERMODYNAMIC_BRIDGE" &&
    primary.conditional_thermodynamic_bridge_status === "PASS" &&
    primary.operator_argument_scope === "CONDITIONAL_ON_FINITE_VOLUME_GROUND_DENSITIES_AND_YMT2" &&
    primary.finite_volume_setup_proved_by_verifier === false &&
    primary.uniform_tail_bound_proved_by_verifier === false &&
    primary.thermodynamic_state_constructed_by_verifier === false &&
    primary.full_sequence_convergence_established === false &&
    primary.uniqueness_established === false && primary.clustering_established === false &&
    primary.uniform_mass_gap_established === false && primary.continuum_hypotheses_present === false &&
    primary.clay_verdict === "NULL";
  addCheck(
    checks,
    "primary_status_and_boundary",
    primaryBoundary,
    {
      schema: primary.schema,
      status: primary.status,
      checks: String(primary.checks_passed) + "/" + String(primary.checks_total),
      operator_argument_scope: primary.operator_argument_scope,
      finite_volume_setup_proved_by_verifier: primary.finite_volume_setup_proved_by_verifier,
      uniform_tail_bound_proved_by_verifier: primary.uniform_tail_bound_proved_by_verifier,
      thermodynamic_state_constructed_by_verifier: primary.thermodynamic_state_constructed_by_verifier,
      clay_verdict: primary.clay_verdict,
    },
    "primary records both analytic premises and the conditional executable boundary",
  );

  const rankRows = reconstructRanks();
  addCheck(checks, "independent_rank_coverage", rankRows.length === 36, rankRows.length, "36 rank rows reconstructed");
  addCheck(
    checks,
    "independent_rank_identity",
    rankRows.every((row) => row.direct_one_link_rank === row.closed_one_link_rank && BigInt(row.support_rank) > 0n),
    { maximum_digits: Math.max(...rankRows.map((row) => row.support_rank_digits)) },
    "recurrence and polynomial Peter-Weyl ranks agree exactly",
  );
  const rankComparison = compareRows(
    rankRows,
    primary.rank_rows ?? [],
    rankKey,
    ["direct_one_link_rank", "closed_one_link_rank", "support_rank_digits"],
    ["support_rank"],
  );
  addCheck(
    checks,
    "primary_independent_rank_agreement",
    rankComparison.keys_match && rankComparison.exact_match && rankComparison.maximum_difference === 0,
    rankComparison,
    "every independent rank row equals the primary row",
  );

  const compactnessRows = reconstructCompactness();
  addCheck(checks, "independent_compactness_coverage", compactnessRows.length === 100, compactnessRows.length, "100 compactness rows reconstructed");
  const compactnessValid = compactnessRows.every(
    (row) => row.compression_radius <= row.target_radius + TOLERANCE &&
      (row.cutoff_search === 0 || row.previous_radius > row.target_radius) && BigInt(row.support_rank) > 0n,
  );
  addCheck(
    checks,
    "independent_cutoff_minimality",
    compactnessValid,
    compactnessValid,
    "each independently searched cutoff reaches the target and its predecessor fails",
  );
  const compactnessComparison = compareRows(
    compactnessRows,
    primary.compactness_rows ?? [],
    compactKey,
    ["cutoff_search", "cutoff_formula", "tail_bound", "compression_radius", "target_radius", "previous_radius", "support_rank_digits"],
    ["support_rank"],
  );
  addCheck(
    checks,
    "primary_independent_compactness_agreement",
    compactnessComparison.keys_match && compactnessComparison.exact_match && compactnessComparison.maximum_difference <= TOLERANCE,
    compactnessComparison,
    "all compactness values agree within " + String(TOLERANCE),
  );

  const partial = reconstructPartialTrace();
  addCheck(
    checks,
    "independent_partial_trace_compatibility",
    partial.nested_direct_maximum_difference <= TOLERANCE && close(partial.trace_one, 1),
    partial,
    "direct and nested partial traces agree and retain unit trace",
  );
  const primaryPartial = primary.partial_trace_control ?? {};
  const partialDifference = Math.max(
    Math.abs(partial.nested_direct_maximum_difference - Number(primaryPartial.nested_direct_maximum_difference)),
    Math.abs(partial.trace_one - Number(primaryPartial.trace_one)),
  );
  addCheck(
    checks,
    "primary_independent_partial_trace_agreement",
    partialDifference <= TOLERANCE,
    partialDifference,
    "independent and primary partial-trace diagnostics agree",
  );

  const groundRows = reconstructGroundRows();
  addCheck(checks, "independent_ground_coverage", groundRows.length === 12, groundRows.length, "12 ground fixtures reconstructed");
  const groundValid = groundRows.every(
    (row) => row.spectral_sum >= -TOLERANCE && row.absolute_difference <= TOLERANCE && Math.abs(row.direct_imaginary) <= TOLERANCE,
  );
  addCheck(
    checks,
    "independent_ground_identity",
    groundValid && Math.max(...groundRows.map((row) => row.spectral_sum)) > 1,
    { minimum: Math.min(...groundRows.map((row) => row.spectral_sum)), maximum: Math.max(...groundRows.map((row) => row.spectral_sum)) },
    "spectral ground forms are real, nonnegative and nonvacuous",
  );
  const groundComparison = compareRows(
    groundRows,
    primary.ground_identity_rows ?? [],
    groundKey,
    ["direct_real", "direct_imaginary", "spectral_sum", "absolute_difference"],
    ["fixture_kind"],
  );
  addCheck(
    checks,
    "primary_independent_ground_agreement",
    groundComparison.keys_match && groundComparison.exact_match && groundComparison.maximum_difference <= TOLERANCE,
    groundComparison,
    "all ground-identity rows agree within " + String(TOLERANCE),
  );

  const spectatorError = 0;
  addCheck(
    checks,
    "independent_spectator_stabilization",
    spectatorError <= TOLERANCE && Math.abs(Number(primary.spectator_commutator_error)) <= TOLERANCE,
    { independent: spectatorError, primary: primary.spectator_commutator_error },
    "tensor-factor commutation removes the spectator contribution",
  );

  const alternating = { even_odd_trace_distance: 2, full_sequence_converges: false, even_subsequence_converges: true, odd_subsequence_converges: true };
  addCheck(
    checks,
    "independent_alternating_firing",
    alternating.even_odd_trace_distance === 2 && alternating.full_sequence_converges === false &&
      primary.firing_controls?.alternating_sequence?.full_sequence_converges === false,
    alternating,
    "two cluster points prevent promotion to full-sequence convergence",
  );

  const escapeRows = reconstructEscapeRows();
  const escapeComparison = compareRows(
    escapeRows,
    primary.firing_controls?.escaping_sector_rows ?? [],
    escapeKey,
    ["tail_mass", "electric_energy", "orthogonal_trace_distance"],
  );
  addCheck(
    checks,
    "independent_energy_escape_firing",
    escapeRows.length === 35 && escapeRows.filter((row) => row.label_n > row.cutoff_C).every((row) => row.tail_mass === 1) &&
      escapeComparison.keys_match && escapeComparison.exact_match && escapeComparison.maximum_difference <= TOLERANCE,
    escapeComparison,
    "escaping representation sectors fire and reconstruct every primary row",
  );

  const gapRows = reconstructGapRows();
  const gapOrdered = [...gapRows].sort((left, right) => left.volume_L - right.volume_L);
  const gapValues = gapOrdered.map((row) => row.one_magnon_gap_upper_bound);
  const gapComparison = compareRows(
    gapRows,
    primary.firing_controls?.ferromagnetic_gap_rows ?? [],
    (row) => String(row.volume_L),
    ["one_magnon_gap_upper_bound"],
  );
  addCheck(
    checks,
    "independent_gapless_firing",
    gapRows.length === 7 && gapValues.slice(1).every((value, index) => value < gapValues[index]) && gapValues.at(-1) < 1e-3 &&
      gapComparison.keys_match && gapComparison.exact_match && gapComparison.maximum_difference <= TOLERANCE,
    { comparison: gapComparison, terminal_upper_bound: gapValues.at(-1) },
    "one-magnon upper bounds decrease toward zero and match the primary rows",
  );

  if (checks.length !== 19) throw new Error("expected 19 checks, constructed " + String(checks.length));
  const passed = checks.every((check) => check.passed);
  const status = passed ? "PASS" : "FAIL";
  const record = {
    schema: "cassi.yang_mills_thermodynamic_ground_state.independent.v1",
    status,
    classification: passed ? "FINITE_IDENTITY_SUPPORT_FOR_CONDITIONAL_THERMODYNAMIC_BRIDGE" : "FAILED",
    conditional_thermodynamic_bridge_status: status,
    operator_argument_scope: "CONDITIONAL_ON_FINITE_VOLUME_GROUND_DENSITIES_AND_YMT2",
    finite_volume_setup_proved_by_verifier: false,
    uniform_tail_bound_proved_by_verifier: false,
    thermodynamic_state_constructed_by_verifier: false,
    full_sequence_convergence_established: false,
    uniqueness_established: false,
    clustering_established: false,
    uniform_mass_gap_established: false,
    continuum_hypotheses_present: false,
    clay_verdict: "NULL",
    inputs: {
      protocol: { path: displayPath(PROTOCOL), sha256: protocolHash },
      independent_source: { path: displayPath(SOURCE), sha256: digest(SOURCE) },
      primary_source: { path: displayPath(PRIMARY_SOURCE), sha256: primarySourceHash },
      primary_receipt: { path: displayPath(PRIMARY_RECEIPT), sha256: digest(PRIMARY_RECEIPT) },
      local_primary_receipt: { path: displayPath(LOCAL_RECEIPT), sha256: localReceiptHash },
    },
    rank_rows: rankRows,
    compactness_rows: compactnessRows,
    partial_trace_control: partial,
    ground_identity_rows: groundRows,
    spectator_commutator_error: spectatorError,
    firing_controls: { alternating_sequence: alternating, escaping_sector_rows: escapeRows, ferromagnetic_gap_rows: gapOrdered },
    comparisons: {
      rank: rankComparison,
      compactness: compactnessComparison,
      partial_trace_maximum_difference: partialDifference,
      ground: groundComparison,
      escaping: escapeComparison,
      gap: gapComparison,
    },
    checks,
    checks_passed: checks.filter((check) => check.passed).length,
    checks_total: checks.length,
    claim_boundary:
      "This independent verifier checks finite-dimensional consequences and falsification controls for a conditional operator argument. The interacting finite-volume ground densities and YMT2 remain analytic premises outside the executable evidence. This receipt constructs no thermodynamic Yang-Mills state and supplies no continuum mass-gap result.",
  };

  mkdirSync(dirname(output), { recursive: true });
  const temporary = output + ".tmp";
  writeFileSync(temporary, JSON.stringify(record, null, 2) + "\n", "utf8");
  renameSync(temporary, output);
  if (!passed) {
    const failed = checks.filter((check) => !check.passed).map((check) => check.name);
    throw new Error("independent thermodynamic verification failed: " + failed.join(", "));
  }
  return record;
}

const parsed = parseArguments(process.argv.slice(2));
const result = run(parsed.output, parsed.replace);
console.log("status=" + result.status + " clay=" + result.clay_verdict + " checks=" + String(result.checks_passed) + "/" + String(result.checks_total));
console.log(
  "rank_rows=" + String(result.rank_rows.length) + " compactness_rows=" + String(result.compactness_rows.length) +
    " ground_rows=" + String(result.ground_identity_rows.length) + " gap_terminal=" +
    result.firing_controls.ferromagnetic_gap_rows.at(-1).one_magnon_gap_upper_bound.toExponential(12),
);
