#!/usr/bin/env node
/** Independent reconstruction of the local Yang--Mills cutoff theorem. */

import { createHash } from "node:crypto";
import {
  existsSync,
  mkdirSync,
  readFileSync,
  renameSync,
  writeFileSync,
} from "node:fs";
import { dirname, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const SOURCE = fileURLToPath(import.meta.url);
const ROOT = resolve(dirname(SOURCE), "..");
const PROTOCOL = resolve(ROOT, "computations/yang-mills-local-cutoff-density-prereg.md");
const PRIMARY_SOURCE = resolve(ROOT, "computations/verify_yang_mills_local_cutoff_density.py");
const PRIMARY_RECEIPT = resolve(ROOT, "runs/yang_mills_local_cutoff_density/verification.json");
const DEFAULT_OUTPUT = resolve(
  ROOT,
  "runs/yang_mills_local_cutoff_density/verification-independent.json",
);

const VOLUMES = [3, 4, 6, 8, 12, 16, 24, 32];
const COUPLINGS = [0.015625, 0.0625, 0.25, 1, 4, 16];
const SUPPORTS = [1, 4, 6, 12];
const CUTOFFS = [1, 2, 4, 8, 16, 32, 64, 128];
const JOINT_SCALES = [2, 4, 8, 16, 32, 64, 128];
const PRODUCT_Q = [0.25, 0.5, 0.75];
const PRODUCT_CUTOFFS = [0, 1, 2, 4, 8];
const PRODUCT_VOLUMES = [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 4096];
const EPSILON = 0.1;
const SERIES_TERMINAL = 4096;
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
      throw new Error(`unknown argument: ${argument}`);
    }
  }
  return { output, replace };
}

function digest(path) {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

function displayPath(path) {
  const value = relative(ROOT, path);
  return (value || path).replaceAll("\\", "/");
}

function loadJson(path) {
  const value = JSON.parse(readFileSync(path, "utf8"));
  if (value === null || Array.isArray(value) || typeof value !== "object") {
    throw new TypeError(`expected JSON object in ${path}`);
  }
  return value;
}

function close(left, right) {
  return Math.abs(left - right) <= TOLERANCE * Math.max(1, Math.abs(left), Math.abs(right));
}

function addCheck(checks, name, passed, measured, requirement) {
  checks.push({ name, passed: Boolean(passed), measured, requirement });
}

function excludedCasimir(cutoff) {
  return ((cutoff + 2) ** 2 - 1) / 4;
}

function envelope(bound) {
  return bound >= 0 && bound < 1 ? 2 * Math.sqrt(bound) + bound : null;
}

function directOneLoopTail(q, cutoff) {
  const ratio = q * q;
  let coefficient = (1 - ratio) * ratio ** (cutoff + 1);
  let total = 0;
  for (let label = cutoff + 1; label <= SERIES_TERMINAL; label += 1) {
    total += coefficient;
    coefficient *= ratio;
  }
  return total;
}

function closedOneLoopTail(q, cutoff) {
  return q ** (2 * (cutoff + 1));
}

function directElectricEnergy(q) {
  const ratio = q * q;
  let coefficient = 1 - ratio;
  let total = 0;
  for (let label = 0; label <= SERIES_TERMINAL; label += 1) {
    total += label * (label + 2) * coefficient;
    coefficient *= ratio;
  }
  return total;
}

function closedElectricEnergy(q) {
  const ratio = q * q;
  return (ratio * (3 - ratio)) / (1 - ratio) ** 2;
}

function retainedStable(q, cutoff, loops) {
  return Math.exp(loops * Math.log1p(-closedOneLoopTail(q, cutoff)));
}

function retainedRecurrence(q, cutoff, loops) {
  const factor = 1 - closedOneLoopTail(q, cutoff);
  let retained = 1;
  for (let index = 0; index < loops; index += 1) retained *= factor;
  return retained;
}

function minimumCutoffSearch(loops, q, epsilon) {
  const target = 1 - epsilon;
  let cutoff = 0;
  while (retainedStable(q, cutoff, loops) < target) cutoff += 1;
  return cutoff;
}

function localKey(row) {
  return `${row.side_L}|${row.coupling_x}|${row.support_links}|${row.cutoff_C}`;
}

function obstructionKey(row) {
  return `${row.q}|${row.cutoff_C}|${row.loops_N}`;
}

function reconstructLocalRows() {
  const rows = [];
  for (const cutoff of CUTOFFS) {
    const threshold = excludedCasimir(cutoff);
    for (const support of SUPPORTS) {
      for (const coupling of COUPLINGS) {
        for (const side of VOLUMES) {
          const edges = 3 * side ** 3;
          const plaquettes = 3 * side ** 3;
          const trialEnergy = 2 * coupling * plaquettes;
          const energyDensity = trialEnergy / edges;
          const bound = (support * energyDensity) / threshold;
          rows.push({
            side_L: side,
            edge_count: edges,
            plaquette_count: plaquettes,
            coupling_x: coupling,
            support_links: support,
            cutoff_C: cutoff,
            kappa_C: threshold,
            trial_energy_bound: trialEnergy,
            energy_bound_per_edge: energyDensity,
            local_tail_bound: bound,
            applicable: bound < 1,
            unit_observable_error_bound: envelope(bound),
          });
        }
      }
    }
  }
  return rows;
}

function reconstructJointRows() {
  return JOINT_SCALES.map((scale) => {
    const coupling = scale ** 4;
    const cutoff = scale ** 3;
    const bound = (2 * coupling) / excludedCasimir(cutoff);
    return {
      scale_k: scale,
      coupling_x: coupling,
      cutoff_C: cutoff,
      cutoff_squared_over_x: cutoff ** 2 / coupling,
      local_tail_bound: bound,
      applicable: bound < 1,
      unit_observable_error_bound: envelope(bound),
    };
  });
}

function reconstructObstructionRows() {
  const rows = [];
  for (const loops of PRODUCT_VOLUMES) {
    for (const cutoff of PRODUCT_CUTOFFS) {
      for (const q of PRODUCT_Q) {
        const retained = retainedStable(q, cutoff, loops);
        rows.push({
          q,
          cutoff_C: cutoff,
          loops_N: loops,
          one_loop_tail: closedOneLoopTail(q, cutoff),
          retained_global_norm_sq: retained,
          discarded_global_norm_sq: -Math.expm1(
            loops * Math.log1p(-closedOneLoopTail(q, cutoff)),
          ),
          electric_energy_per_loop: closedElectricEnergy(q),
          minimum_cutoff_epsilon_0_1: minimumCutoffSearch(loops, q, EPSILON),
        });
      }
    }
  }
  return rows;
}

function maximumNumericDifference(leftRows, rightRows, keyFunction, fields) {
  const leftMap = new Map(leftRows.map((row) => [keyFunction(row), row]));
  const rightMap = new Map(rightRows.map((row) => [keyFunction(row), row]));
  if (leftMap.size !== rightMap.size) return { keysMatch: false, maximum: Infinity };
  let maximum = 0;
  for (const [key, left] of leftMap) {
    const right = rightMap.get(key);
    if (right === undefined) return { keysMatch: false, maximum: Infinity };
    for (const field of fields) {
      const leftValue = left[field];
      const rightValue = right[field];
      if (leftValue === null || rightValue === null) {
        if (leftValue !== rightValue) return { keysMatch: true, maximum: Infinity };
      } else {
        maximum = Math.max(maximum, Math.abs(Number(leftValue) - Number(rightValue)));
      }
    }
    if (left.applicable !== right.applicable) {
      return { keysMatch: true, maximum: Infinity };
    }
  }
  return { keysMatch: true, maximum };
}

function run(output, replace) {
  for (const path of [PROTOCOL, PRIMARY_SOURCE, PRIMARY_RECEIPT]) {
    if (!existsSync(path)) throw new Error(`missing required input: ${path}`);
  }
  if (existsSync(output) && !replace) {
    throw new Error(`refusing to overwrite existing receipt: ${output}`);
  }

  const primary = loadJson(PRIMARY_RECEIPT);
  const checks = [];
  const protocolHash = digest(PROTOCOL);
  const primarySourceHash = digest(PRIMARY_SOURCE);
  addCheck(
    checks,
    "primary_protocol_binding",
    primary.inputs?.protocol?.sha256 === protocolHash,
    primary.inputs?.protocol?.sha256,
    "primary protocol hash equals the current frozen protocol",
  );
  addCheck(
    checks,
    "primary_source_binding",
    primary.inputs?.primary_source?.sha256 === primarySourceHash,
    primary.inputs?.primary_source?.sha256,
    "primary source hash equals the current primary source",
  );
  addCheck(
    checks,
    "primary_status_and_claim_boundary",
    primary.schema === "cassi.yang_mills_local_cutoff_density.v1" &&
      primary.local_cutoff_status === "PASS" &&
      primary.checks_passed === primary.checks_total &&
      primary.global_norm_uniformity === "EXCLUDED_BY_PRODUCT_FAMILY" &&
      primary.thermodynamic_limit_constructed === false &&
      primary.continuum_hypotheses_present === false &&
      primary.clay_verdict === "NULL",
    {
      status: primary.local_cutoff_status,
      checks: `${primary.checks_passed}/${primary.checks_total}`,
      clay_verdict: primary.clay_verdict,
    },
    "primary passes while every continuum and Clay field remains withheld",
  );

  const localRows = reconstructLocalRows();
  const expectedLocal = VOLUMES.length * COUPLINGS.length * SUPPORTS.length * CUTOFFS.length;
  const localApplicable = localRows.filter((row) => row.applicable).length;
  addCheck(
    checks,
    "independent_local_schedule_coverage",
    localRows.length === expectedLocal && expectedLocal === 1536,
    { rows: localRows.length, expected: expectedLocal },
    "independent reconstruction contains all 1536 local rows",
  );
  addCheck(
    checks,
    "independent_cubic_energy_density",
    localRows.every(
      (row) =>
        row.edge_count === row.plaquette_count &&
        row.edge_count === 3 * row.side_L ** 3 &&
        close(row.energy_bound_per_edge, 2 * row.coupling_x),
    ),
    { volumes: VOLUMES },
    "cubic counts and E_0/|E| <= 2x are reconstructed independently",
  );

  const volumeGroups = new Map();
  for (const row of localRows) {
    const key = `${row.coupling_x}|${row.support_links}|${row.cutoff_C}`;
    const values = volumeGroups.get(key) ?? [];
    values.push(row.local_tail_bound);
    volumeGroups.set(key, values);
  }
  const volumeSpread = Math.max(
    ...[...volumeGroups.values()].map((values) => Math.max(...values) - Math.min(...values)),
  );
  addCheck(
    checks,
    "independent_volume_invariance",
    volumeSpread <= TOLERANCE,
    volumeSpread,
    "fixed-support bound is identical across all scheduled volumes",
  );

  let localMonotonic = true;
  for (const side of VOLUMES) {
    for (const coupling of COUPLINGS) {
      for (const support of SUPPORTS) {
        const values = CUTOFFS.map(
          (cutoff) =>
            localRows.find(
              (row) =>
                row.side_L === side &&
                row.coupling_x === coupling &&
                row.support_links === support &&
                row.cutoff_C === cutoff,
            ).local_tail_bound,
        );
        localMonotonic &&= values.slice(1).every((value, index) => value < values[index]);
      }
    }
  }
  addCheck(
    checks,
    "independent_local_monotonicity",
    localMonotonic,
    localMonotonic,
    "all fixed-volume local bounds decrease strictly with cutoff",
  );
  addCheck(
    checks,
    "independent_applicability_count",
    localApplicable > 0 &&
      localApplicable < localRows.length &&
      localApplicable === primary.local_summary?.applicable,
    { attempted: localRows.length, applicable: localApplicable },
    "applicable count is nonvacuous and equals the primary receipt",
  );

  const localComparison = maximumNumericDifference(
    localRows,
    primary.local_volume_rows ?? [],
    localKey,
    [
      "edge_count",
      "plaquette_count",
      "kappa_C",
      "trial_energy_bound",
      "energy_bound_per_edge",
      "local_tail_bound",
      "unit_observable_error_bound",
    ],
  );
  addCheck(
    checks,
    "primary_independent_local_agreement",
    localComparison.keysMatch && localComparison.maximum <= TOLERANCE,
    localComparison,
    `all independent and primary local values agree within ${TOLERANCE}`,
  );

  const jointRows = reconstructJointRows();
  const jointTails = jointRows.map((row) => row.local_tail_bound);
  const jointEnvelopes = jointRows
    .map((row) => row.unit_observable_error_bound)
    .filter((value) => value !== null);
  const jointRatioError = Math.max(
    ...jointRows.map((row) => Math.abs(row.cutoff_squared_over_x - row.scale_k ** 2)),
  );
  addCheck(
    checks,
    "independent_joint_schedule",
    jointRows.length === 7 &&
      jointRatioError <= TOLERANCE &&
      jointTails.slice(1).every((value, index) => value < jointTails[index]) &&
      jointEnvelopes.slice(1).every((value, index) => value < jointEnvelopes[index]),
    { ratio_error: jointRatioError, tails: jointTails, envelopes: jointEnvelopes },
    "joint cutoff ratio is exact and applicable bounds decrease strictly",
  );
  const primaryJointMap = new Map(
    (primary.joint_cutoff_rows ?? []).map((row) => [row.scale_k, row]),
  );
  let jointDifference = 0;
  let jointMatches = primaryJointMap.size === jointRows.length;
  for (const row of jointRows) {
    const other = primaryJointMap.get(row.scale_k);
    if (other === undefined || other.applicable !== row.applicable) {
      jointMatches = false;
      continue;
    }
    for (const field of [
      "coupling_x",
      "cutoff_C",
      "cutoff_squared_over_x",
      "local_tail_bound",
    ]) {
      jointDifference = Math.max(jointDifference, Math.abs(row[field] - other[field]));
    }
    if (row.unit_observable_error_bound !== other.unit_observable_error_bound) {
      if (row.unit_observable_error_bound === null || other.unit_observable_error_bound === null) {
        jointMatches = false;
      } else {
        jointDifference = Math.max(
          jointDifference,
          Math.abs(row.unit_observable_error_bound - other.unit_observable_error_bound),
        );
      }
    }
  }
  addCheck(
    checks,
    "primary_independent_joint_agreement",
    jointMatches && jointDifference <= TOLERANCE,
    { rows_match: jointMatches, maximum_difference: jointDifference },
    `primary and independent joint rows agree within ${TOLERANCE}`,
  );

  const obstructionRows = reconstructObstructionRows();
  const expectedObstruction =
    PRODUCT_Q.length * PRODUCT_CUTOFFS.length * PRODUCT_VOLUMES.length;
  addCheck(
    checks,
    "independent_obstruction_coverage",
    obstructionRows.length === expectedObstruction && expectedObstruction === 180,
    { rows: obstructionRows.length, expected: expectedObstruction },
    "independent reconstruction contains all 180 obstruction rows",
  );

  let tailSeriesError = 0;
  let energySeriesError = 0;
  let recurrenceError = 0;
  for (const q of PRODUCT_Q) {
    energySeriesError = Math.max(
      energySeriesError,
      Math.abs(directElectricEnergy(q) - closedElectricEnergy(q)),
    );
    for (const cutoff of PRODUCT_CUTOFFS) {
      tailSeriesError = Math.max(
        tailSeriesError,
        Math.abs(directOneLoopTail(q, cutoff) - closedOneLoopTail(q, cutoff)),
      );
      for (const loops of PRODUCT_VOLUMES) {
        recurrenceError = Math.max(
          recurrenceError,
          Math.abs(retainedRecurrence(q, cutoff, loops) - retainedStable(q, cutoff, loops)),
        );
      }
    }
  }
  addCheck(
    checks,
    "independent_character_series",
    tailSeriesError <= TOLERANCE && energySeriesError <= TOLERANCE,
    { maximum_tail_error: tailSeriesError, maximum_energy_error: energySeriesError },
    `independent direct series agree with both closed forms within ${TOLERANCE}`,
  );
  addCheck(
    checks,
    "independent_global_norm_recurrence",
    recurrenceError <= TOLERANCE,
    recurrenceError,
    `independent recurrence and stable global norm agree within ${TOLERANCE}`,
  );

  let obstructionMonotonic = true;
  for (const q of PRODUCT_Q) {
    for (const cutoff of PRODUCT_CUTOFFS) {
      const values = PRODUCT_VOLUMES.map(
        (loops) =>
          obstructionRows.find(
            (row) => row.q === q && row.cutoff_C === cutoff && row.loops_N === loops,
          ).discarded_global_norm_sq,
      );
      const adjacent = values.slice(1).map((value, index) => [values[index], value]);
      obstructionMonotonic &&= adjacent.every(([left, right]) => right >= left);
      obstructionMonotonic &&= adjacent
        .filter(([left]) => left < 1 - TOLERANCE)
        .every(([left, right]) => right > left);
    }
  }
  addCheck(
    checks,
    "independent_global_growth",
    obstructionMonotonic,
    obstructionMonotonic,
    "discarded global norm grows strictly with loop count",
  );

  const obstructionComparison = maximumNumericDifference(
    obstructionRows,
    primary.global_obstruction?.rows ?? [],
    obstructionKey,
    [
      "one_loop_tail",
      "retained_global_norm_sq",
      "discarded_global_norm_sq",
      "electric_energy_per_loop",
      "minimum_cutoff_epsilon_0_1",
    ],
  );
  addCheck(
    checks,
    "primary_independent_obstruction_agreement",
    obstructionComparison.keysMatch && obstructionComparison.maximum <= TOLERANCE,
    obstructionComparison,
    `all product-family values and direct minimal cutoffs agree within ${TOLERANCE}`,
  );

  const firing = obstructionRows.find(
    (row) => row.q === 0.5 && row.cutoff_C === 2 && row.loops_N === 512,
  );
  addCheck(
    checks,
    "independent_global_uniformity_firing",
    firing !== undefined && firing.discarded_global_norm_sq > 0.999,
    firing,
    "q=1/2, C=2, N=512 rejects volume-independent global norm control",
  );

  const passed = checks.every((check) => check.passed);
  const status = passed ? "PASS" : "FAIL";
  const record = {
    schema: "cassi.yang_mills_local_cutoff_density.independent.v1",
    status,
    local_cutoff_status: status,
    global_norm_uniformity: "EXCLUDED_BY_PRODUCT_FAMILY",
    thermodynamic_limit_constructed: false,
    continuum_hypotheses_present: false,
    clay_verdict: "NULL",
    inputs: {
      protocol: { path: displayPath(PROTOCOL), sha256: protocolHash },
      independent_source: { path: displayPath(SOURCE), sha256: digest(SOURCE) },
      primary_source: { path: displayPath(PRIMARY_SOURCE), sha256: primarySourceHash },
      primary_receipt: { path: displayPath(PRIMARY_RECEIPT), sha256: digest(PRIMARY_RECEIPT) },
    },
    local_summary: {
      attempted: localRows.length,
      applicable: localApplicable,
      maximum_volume_spread: volumeSpread,
      maximum_primary_difference: localComparison.maximum,
    },
    joint_cutoff_rows: jointRows,
    global_obstruction: {
      rows: obstructionRows,
      firing_control: firing,
      maximum_tail_series_error: tailSeriesError,
      maximum_energy_series_error: energySeriesError,
      maximum_recurrence_error: recurrenceError,
      maximum_primary_difference: obstructionComparison.maximum,
    },
    checks,
    checks_passed: checks.filter((check) => check.passed).length,
    checks_total: checks.length,
    claim_boundary:
      "The independent reconstruction verifies volume-uniform fixed-support projection control and proves that electric-energy-density control alone cannot give volume-uniform global norm control. Thermodynamic convergence, continuum construction, and a physical mass gap remain absent.",
  };

  mkdirSync(dirname(output), { recursive: true });
  const temporary = `${output}.tmp`;
  writeFileSync(temporary, `${JSON.stringify(record, null, 2)}\n`, "utf8");
  renameSync(temporary, output);
  if (!passed) {
    const failed = checks.filter((check) => !check.passed).map((check) => check.name);
    throw new Error(`independent local cutoff verification failed: ${failed.join(", ")}`);
  }
  return record;
}

const { output, replace } = parseArguments(process.argv.slice(2));
const result = run(output, replace);
console.log(
  `status=${result.local_cutoff_status} clay=${result.clay_verdict} ` +
    `checks=${result.checks_passed}/${result.checks_total}`,
);
console.log(
  `local=${result.local_summary.applicable}/${result.local_summary.attempted} ` +
    `cross=${result.local_summary.maximum_primary_difference.toExponential(3)} ` +
    `firing_discarded=${result.global_obstruction.firing_control.discarded_global_norm_sq.toFixed(12)}`,
);
