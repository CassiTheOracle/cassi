#!/usr/bin/env python3
"""Bounded-projector qualification of working-notebook section 72.

Command line:
    python computations/verify_matter_formation_quantum_transfer_bound.py
        --manifest PATH --output FRESH_DIR --left DIR --right DIR

``--left`` and ``--right`` are the two preparation-bound output directories, in
either order.  Nothing else is computed: the program reads only the two retained
(80,20) coupled archives, the accepted prior residual receipt and the two accepted
preparation receipts.  No trajectory, basis, parameter, duration or threshold is
generated or varied, and section 70's first-derivative verdict is not relabelled.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SELF_PATH = "computations/verify_matter_formation_quantum_transfer_bound.py"
REPORT = "computations/matter-formation-continuum-report.md"
HEADING = ("## 72. Working notes: higher-order preparation error on retained "
           "quantum states")
SOURCE_PATHS = {
    "source_primary": "computations/matter_formation_quantum_preparation.py",
    "source_preparation": "computations/verify_matter_formation_quantum_preparation.py",
    "source_observable": SELF_PATH,
}
LABELS = set(SOURCE_PATHS) | {"archive_primary", "archive_coordinate", "prior_audit"}
FILE_FIELDS = {"path", "snapshot", "sha256", "canonical"}

SCHEMA = "matter-formation-quantum-preparation-v1"
MANIFEST_SCHEMA = "matter-formation-quantum-preparation-manifest-v1"
PRIOR_SCHEMA = "matter-formation-quantum-backreaction-audit-v1"
PREPARATION_ROLES = frozenset({"primary", "preparation"})
PREPARATION_VERDICT = "SUPPORTS-conditional preparation truncation bound"
VERDICT_SUPPORTS = ("SUPPORTS-conditional finite-mode quantum transfer "
                    "with a controlled preparation bound")
VERDICT_INCONCLUSIVE = "INCONCLUSIVE"

# Frozen section 70.4/72.3 inputs.  Nothing here is adjustable at run time.
J, N = 80, 20
TIME_SAMPLES, TIME_HORIZON = 513, 16.0
DELTA = math.log(math.sqrt(1.5))
PRIOR_KEY = "coupled_80_20"
PRIOR_CHECK_COUNT = 507
PRIOR_PREPARATION_FAILURES = frozenset((
    "coupled_80_20:primary:preparation_upper_gate",
    "coupled_80_20:primary:independent_preparation_upper_gate",
    "coupled_80_20:independent:preparation_upper_gate",
    "coupled_80_20:independent:independent_preparation_upper_gate",
))
METHODS = (("primary", "archive_primary"), ("independent", "archive_coordinate"))
EVOLUTION_FIELDS = ("evolution_upper", "independent_evolution_upper")
SOURCE_ORDER = ("primary", "coordinate")
PREPARATION_ROW_FIELDS = frozenset({"source", "preparation_upper", "derivative_integrals",
                                    "remainder", "source_reconstruction_error", "generator_error"})

PREPARATION_BOUND = 1e-6
GENERATOR_BOUND = 1e-11
SOURCE_STATE_BOUND = 1e-10
PROBABILITY_BOUND = 1e-9
PRIOR_AGREEMENT_BOUND = 1e-8
NORM_BOUND = 1e-10
TIME_GRID_BOUND = 1e-12
TRANSFER_FLOOR = 1e-3

RECEIPT_CHECKS = ("numeric_pass", "checks_true", "verdict", "preparation_bounds", "quality_gates")
METHOD_CHECKS = ("finite", "time_grid", "state_norms", "probability_reconstruction",
                 "reference_reconstruction", "gain_reconstruction", "gain_lower_bound")
REQUIRED_CHECKS = frozenset(
    ("guards", "prior_verdict", "prior_failure_set", "prior_basis", "allowance_components")
    + tuple(flag + ":" + name for flag in ("left", "right") for name in RECEIPT_CHECKS)
    + tuple(method + ":" + name for method, _label in METHODS for name in METHOD_CHECKS))

SCOPE = ("Exact inequalities of section 72, evaluated in floating-point arithmetic on the two retained "
         "(80,20) archives, with no interval-arithmetic certificate.  The allowance is the worst case "
         "2*(B_prep + b_evol + b_0) of section 72.2, taken over both preparation programs, both source "
         "records and both evolution estimates.  The compared initial reference is the finite variational "
         "state g_P, the lowest eigenvector of the J by N compression of one specified finite spatial-mode "
         "Hamiltonian; the qualified number is a difference of reference-basis pair probabilities, so no "
         "distance from the exact ground state, no exact-vacuum statement, no spectral-gap or "
         "continuum-limit claim, no spatial localization or nonradial persistence result, and no "
         "particle-identity or asymptotic out-particle count follows.  The section 70 first-derivative "
         "calculation keeps its INCONCLUSIVE verdict.  Complete physical matter formation remains "
         "unresolved.")


class GuardError(Exception):
    """A manifest, section, review, receipt, prior-qualification or archive-identity failure."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GuardError(message)


def rooted(value, label: str) -> Path:
    require(isinstance(value, str) and bool(value) and "\x00" not in value,
            f"{label}: expected a non-empty path")
    require(not Path(value).is_absolute() and "\\" not in value,
            f"{label}: expected a repository-relative path: {value}")
    path = (ROOT / Path(value)).resolve()
    require(path == ROOT or ROOT in path.parents, f"{label}: escapes the repository root")
    return path


def digest(path: Path, canonical: bool = False) -> str:
    if canonical:
        return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def reject_constant(token: str):
    raise ValueError(f"nonfinite JSON constant: {token}")


def load_json(path: Path, label: str) -> dict:
    require(path.is_file(), f"{label}: missing file {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    except ValueError as exc:
        raise GuardError(f"{label}: not strict finite JSON: {exc}") from exc
    require(isinstance(value, dict), f"{label}: expected a JSON object")
    return value


def number(value, label: str) -> float:
    require(isinstance(value, (int, float)) and not isinstance(value, bool),
            f"{label}: expected a number")
    result = float(value)
    require(math.isfinite(result), f"{label}: expected a finite number")
    return result


def hash_string(value, label: str) -> str:
    require(isinstance(value, str) and len(value) == 64
            and all(char in "0123456789abcdef" for char in value),
            f"{label}: expected a lowercase SHA-256")
    return value


def validate_manifest(path: Path) -> dict:
    """Prove every shared prerequisite before any receipt or archive is opened."""
    manifest = load_json(path, "manifest")
    require(manifest.get("schema") == MANIFEST_SCHEMA, "manifest schema mismatch")
    require({"files", "section", "reviews"} <= set(manifest), "manifest is missing a required member")
    files = manifest["files"]
    require(isinstance(files, dict) and set(files) == LABELS, "manifest file labels mismatch")
    for label, item in files.items():
        require(isinstance(item, dict) and FILE_FIELDS <= set(item), f"{label}: manifest entry fields")
        require(type(item["canonical"]) is bool, f"{label}: canonical flag is not a bool")
        # Archive bytes are hashed raw: a canonical fold would describe different bytes.
        require(not item["path"].endswith(".npz") or item["canonical"] is False,
                f"{label}: archive bytes must be hashed raw")
        if label in SOURCE_PATHS:
            require(item["path"] == SOURCE_PATHS[label], f"{label}: source path mismatch")
        live = rooted(item["path"], label)
        snapshot = rooted(item["snapshot"], label)
        require(live.is_file() and snapshot.is_file(), f"{label}: manifest file is missing")
        require(digest(live, item["canonical"]) == item["sha256"], f"{label}: live identity mismatch")
        require(digest(snapshot, item["canonical"]) == item["sha256"], f"{label}: snapshot mismatch")
    section = manifest["section"]
    require(isinstance(section, dict)
            and set(section) == {"path", "heading", "snapshot", "sha256"}, "section entry fields")
    require(section["path"] == REPORT and section["heading"] == HEADING, "section identity mismatch")
    lines = rooted(REPORT, "section").read_text(encoding="utf-8").splitlines()
    starts = [index for index, line in enumerate(lines) if line == HEADING]
    require(len(starts) == 1, "section heading must occur exactly once")
    first = starts[0]
    last = next((index for index in range(first + 1, len(lines)) if lines[index].startswith("## ")),
                len(lines))
    live = ("\n".join(lines[first:last]) + "\n").encode("utf-8")
    require(hashlib.sha256(live).hexdigest() == section["sha256"], "live section mismatch")
    require(digest(rooted(section["snapshot"], "section snapshot"), True) == section["sha256"],
            "section snapshot mismatch")
    reviews = manifest["reviews"]
    require(isinstance(reviews, dict) and set(reviews) == {"preparation", "observable"},
            "review roles mismatch")
    for role, review in reviews.items():
        require(isinstance(review, dict) and set(review) == {"snapshot", "sha256", "accepted"},
                f"review {role}: entry fields")
        require(review["accepted"] is True, f"review is not accepted: {role}")
        snapshot = rooted(review["snapshot"], f"review {role}")
        require(digest(snapshot, True) == review["sha256"], f"review {role}: identity mismatch")
        acceptance = [line.strip() for line in snapshot.read_text(encoding="utf-8").splitlines()
                      if line.strip().startswith("accepted:")]
        require(acceptance == ["accepted: true"], f"review {role}: acceptance line mismatch")
    return manifest


def validate_receipt(directory: Path, flag: str, manifest_sha256: str) -> dict:
    """Check one preparation receipt's identity, then report its numerical decisions."""
    receipt_path = Path(directory) / "result.json"
    arrays_path = Path(directory) / "arrays.npz"
    receipt = load_json(receipt_path, f"{flag} preparation receipt")
    require(receipt.get("schema") == SCHEMA, f"{flag}: preparation receipt schema mismatch")
    require(receipt.get("manifest_sha256") == manifest_sha256,
            f"{flag}: preparation receipt manifest identity mismatch")
    require(receipt.get("complete_physical_matter_formation") is False,
            f"{flag}: preparation receipt claims matter formation")
    role = receipt.get("role")
    require(role in PREPARATION_ROLES, f"{flag}: unexpected preparation receipt role {role}")
    rows = receipt.get("rows")
    require(isinstance(rows, list) and len(rows) == 2, f"{flag}: expected exactly two source rows")
    parsed = []
    for row, source in zip(rows, SOURCE_ORDER):
        require(isinstance(row, dict) and set(row) == PREPARATION_ROW_FIELDS,
                f"{flag}: row {source} fields mismatch")
        require(row["source"] == source, f"{flag}: rows must be ordered primary then coordinate")
        integrals = row["derivative_integrals"]
        require(isinstance(integrals, list) and len(integrals) == 4,
                f"{flag}: row {source} needs four derivative integrals")
        parsed.append(dict(
            source=source,
            preparation_upper=number(row["preparation_upper"], f"{flag}: {source} preparation_upper"),
            remainder=number(row["remainder"], f"{flag}: {source} remainder"),
            generator_error=number(row["generator_error"], f"{flag}: {source} generator_error"),
            source_reconstruction_error=number(row["source_reconstruction_error"],
                                               f"{flag}: {source} source_reconstruction_error"),
            derivative_integrals=[number(value, f"{flag}: {source} derivative_integrals")
                                  for value in integrals]))
    checks = receipt.get("checks")
    require(isinstance(checks, dict) and checks
            and all(isinstance(value, bool) for value in checks.values()),
            f"{flag}: preparation receipt checks must be a non-empty bool dict")
    require(arrays_path.is_file(), f"{flag}: arrays.npz is missing")
    arrays_digest = digest(arrays_path)
    require(receipt.get("arrays_sha256") == arrays_digest,
            f"{flag}: arrays.npz is not the raw-hash-bound file")
    return dict(flag=flag, role=role, directory=str(Path(directory).resolve()),
                verdict=receipt.get("verdict"),
                numeric_pass=receipt.get("numeric_pass") is True,
                checks_true=all(checks.values()), checks=len(checks),
                manifest_sha256=receipt.get("manifest_sha256"),
                result_raw_sha256=digest(receipt_path),
                arrays_raw_sha256=arrays_digest, rows=parsed)


def validate_prior(entry: dict) -> dict:
    """Read the prior qualification exactly as section 72.3 describes it."""
    path = rooted(entry["path"], "prior_audit")
    prior = load_json(path, "prior audit")
    require(prior.get("schema") == PRIOR_SCHEMA, "prior audit schema mismatch")
    require(prior.get("role") == "residuals", "prior audit role mismatch")
    require(prior.get("complete_physical_matter_formation") is False,
            "prior audit claims matter formation")
    checks = prior.get("checks")
    require(isinstance(checks, dict) and len(checks) == PRIOR_CHECK_COUNT
            and all(isinstance(value, bool) for value in checks.values()),
            f"prior audit checks are not a {PRIOR_CHECK_COUNT}-entry bool dict")
    rows = prior.get("rows")
    require(isinstance(rows, list), "prior audit rows are missing")
    matches = [row for row in rows if isinstance(row, dict) and row.get("key") == PRIOR_KEY]
    require(len(matches) == 1, "prior audit must carry exactly one coupled_80_20 row")
    row = matches[0]
    require({"J", "N", "delta", "methods"} <= set(row), "prior audit row fields")
    methods = row["methods"]
    require(isinstance(methods, dict) and set(methods) == {name for name, _label in METHODS},
            "prior audit methods mismatch")
    parsed = {}
    for name, _label in METHODS:
        item = methods[name]
        require(isinstance(item, dict) and {"archive_sha256", "bounds", "reconstructed"} <= set(item),
                f"prior audit {name} method fields")
        bounds, reconstructed = item["bounds"], item["reconstructed"]
        require(isinstance(bounds, dict) and isinstance(reconstructed, dict),
                f"prior audit {name} bounds or reconstructed is not an object")
        require({"evolution_upper", "independent_evolution_upper", "full_space_duhamel"} <= set(bounds)
                and {"ground_pair_probability", "peak_pair_probability_gain"} <= set(reconstructed),
                f"prior audit {name} lacks a required bound or reconstructed quantity")
        parsed[name] = dict(
            archive_sha256=hash_string(item["archive_sha256"], f"prior audit {name} archive hash"),
            evolution_upper=number(bounds["evolution_upper"], f"prior {name} evolution_upper"),
            independent_evolution_upper=number(bounds["independent_evolution_upper"],
                                               f"prior {name} independent_evolution_upper"),
            full_space_duhamel=number(bounds["full_space_duhamel"], f"prior {name} full_space_duhamel"),
            ground_pair_probability=number(reconstructed["ground_pair_probability"],
                                           f"prior {name} ground_pair_probability"),
            peak_pair_probability_gain=number(reconstructed["peak_pair_probability_gain"],
                                              f"prior {name} peak_pair_probability_gain"))
    return dict(path=entry["path"], raw_sha256=digest(path),
                verdict=prior.get("verdict"), numeric_pass=prior.get("numeric_pass"),
                error=prior.get("error"),
                failures=sorted(name for name, value in checks.items() if value is not True),
                basis=dict(J=row["J"], N=row["N"], delta=row["delta"]), methods=parsed)


def qualify(receipts: dict, manifest: dict, prior: dict, result: dict) -> None:
    """Evaluate the raw observables and the joint section 72.2 decision."""
    checks = result["checks"]
    prep = 0.0
    for flag in ("left", "right"):
        receipt = receipts[flag]
        rows = receipt["rows"]
        uppers = [row["preparation_upper"] for row in rows]
        nonneg = ([row["remainder"] for row in rows]
                  + [value for row in rows for value in row["derivative_integrals"]])
        checks[flag + ":numeric_pass"] = receipt["numeric_pass"]
        checks[flag + ":checks_true"] = receipt["checks_true"]
        checks[flag + ":verdict"] = receipt["verdict"] == PREPARATION_VERDICT
        checks[flag + ":preparation_bounds"] = (all(0.0 <= value < PREPARATION_BOUND
                                                    for value in uppers + nonneg))
        checks[flag + ":quality_gates"] = all(row["generator_error"] <= GENERATOR_BOUND
                                              and row["source_reconstruction_error"] <= SOURCE_STATE_BOUND
                                              for row in rows)
        prep = max([prep] + uppers)
    checks["prior_verdict"] = (prior["verdict"] == VERDICT_INCONCLUSIVE
                              and prior["numeric_pass"] is False and prior["error"] is None)
    checks["prior_failure_set"] = prior["failures"] == sorted(PRIOR_PREPARATION_FAILURES)
    checks["prior_basis"] = (prior["basis"]["J"] == J and prior["basis"]["N"] == N
                             and abs(number(prior["basis"]["delta"], "prior delta") - DELTA) <= 1e-12)
    evol = max(value for method, _label in METHODS for name in EVOLUTION_FIELDS
               for value in [prior["methods"][method][name]])
    zero = max(prior["methods"][method]["full_space_duhamel"] for method, _label in METHODS)
    allowance = 2.0 * (prep + evol + zero)
    checks["allowance_components"] = (0.0 <= prep < PREPARATION_BOUND and 0.0 <= evol
                                      and 0.0 <= zero and math.isfinite(allowance))

    mask = np.tile((np.arange(N) >= 1).astype(np.float64), J)
    expected_times = np.linspace(0.0, TIME_HORIZON, TIME_SAMPLES)
    for method, label in METHODS:
        entry = prior["methods"][method]
        path = rooted(manifest["files"][label]["path"], label)
        raw = digest(path)
        require(raw == entry["archive_sha256"],
                f"{method}: archive raw hash is not the prior audit method entry")
        with np.load(path, allow_pickle=False) as archive:
            states = np.asarray(archive["state"])
            times = np.asarray(archive["time"], dtype=np.float64)
            ground = np.asarray(archive["ground"])
            stored = np.asarray(archive["pair_probability"], dtype=np.float64)
        require(states.shape == (TIME_SAMPLES, J * N) and times.shape == (TIME_SAMPLES,)
                and ground.shape == (J * N,) and stored.shape == (TIME_SAMPLES,),
                f"{method}: archive array shapes are not (513,1600), (513,), (1600,), (513,)")
        probability = np.abs(states.reshape(TIME_SAMPLES, J * N)) ** 2
        reference = float((np.abs(ground) ** 2) @ mask)
        pair = probability @ mask
        norms = np.sqrt(probability.sum(axis=1))
        peak = int(np.argmax(pair))
        gain = float(pair[peak] - reference)
        reconstruction_error = float(np.max(np.abs(pair - stored)))
        lower_bound = gain - allowance
        finite = (bool(np.isfinite(probability).all()) and bool(np.isfinite(pair).all())
                  and bool(np.isfinite(norms).all()) and bool(np.isfinite(times).all())
                  and bool(np.isfinite(stored).all()) and bool(np.isfinite(ground).all())
                  and all(math.isfinite(value) for value in
                          (reference, gain, reconstruction_error, lower_bound,
                           float(pair[peak]), float(times[peak]))))
        checks[method + ":finite"] = (finite and 0.0 <= reference <= 1.0
                                      and bool(((pair >= 0.0) & (pair <= 1.0)).all()))
        require(checks[method + ":finite"], f"{method}: nonfinite or out-of-range probability")
        checks[method + ":time_grid"] = (bool(np.max(np.abs(times - expected_times)) <= TIME_GRID_BOUND)
                                         and bool(np.diff(times).min() > 0.0))
        norm_defect = max([abs(float(norms.max()) - 1.0), abs(float(norms.min()) - 1.0),
                           abs(float(np.linalg.norm(ground)) - 1.0)])
        checks[method + ":state_norms"] = norm_defect <= NORM_BOUND
        checks[method + ":probability_reconstruction"] = reconstruction_error <= PROBABILITY_BOUND
        checks[method + ":reference_reconstruction"] = (
            abs(reference - entry["ground_pair_probability"]) <= PRIOR_AGREEMENT_BOUND)
        checks[method + ":gain_reconstruction"] = (
            abs(gain - entry["peak_pair_probability_gain"]) <= PRIOR_AGREEMENT_BOUND)
        checks[method + ":gain_lower_bound"] = lower_bound > TRANSFER_FLOOR
        result["rows"].append(dict(
            method=method, archive=manifest["files"][label]["path"], archive_sha256=raw,
            reference_pair_probability=reference, peak_pair_probability=float(pair[peak]),
            peak_time=float(times[peak]), peak_gain=gain,
            probability_reconstruction_error=reconstruction_error,
            state_norm_defect=float(norm_defect),
            allowance=allowance, lower_bound=lower_bound))


def emit(output: Path, result: dict) -> None:
    (output / "result.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--left", type=Path, required=True)
    parser.add_argument("--right", type=Path, required=True)
    args = parser.parse_args()
    result = dict(schema=SCHEMA, role="observable", verdict=VERDICT_INCONCLUSIVE,
                  numeric_pass=False, error=None, checks={}, rows=[],
                  complete_physical_matter_formation=False, scope=SCOPE)
    try:
        args.output.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        print(json.dumps(dict(role="observable", verdict=VERDICT_INCONCLUSIVE, numeric_pass=False,
                              error=f"output directory must be newly created: {exc}",
                              complete_physical_matter_formation=False), allow_nan=False))
        return 1
    try:
        manifest = validate_manifest(args.manifest)
        manifest_sha256 = digest(args.manifest)
        receipts = {flag: validate_receipt(directory, flag, manifest_sha256)
                    for flag, directory in (("left", args.left), ("right", args.right))}
        require({receipts["left"]["role"], receipts["right"]["role"]} == PREPARATION_ROLES,
                "preparation receipt roles are not exactly primary and preparation")
        prior = validate_prior(manifest["files"]["prior_audit"])
        result["manifest_sha256"] = manifest_sha256
        result["inputs"] = dict(
            prior_audit=dict(path=prior["path"], raw_sha256=prior["raw_sha256"],
                             verdict=prior["verdict"], numeric_pass=prior["numeric_pass"],
                             error=prior["error"], failed_checks=prior["failures"]),
            receipts={flag: {name: receipt[name] for name in
                             ("role", "directory", "verdict", "numeric_pass", "checks_true", "checks",
                              "manifest_sha256", "result_raw_sha256", "arrays_raw_sha256")}
                      for flag, receipt in receipts.items()},
            archives={method: manifest["files"][label]["path"] for method, label in METHODS})
        result["checks"]["guards"] = True
    except Exception as exc:
        # A failed prerequisite is never reported as a scientific row.
        result.update(verdict=VERDICT_INCONCLUSIVE, numeric_pass=False, rows=[], checks={},
                      error=f"{type(exc).__name__}: {exc}")
        emit(args.output, result)
        print(json.dumps({key: result[key] for key in
                          ("role", "verdict", "numeric_pass", "error")}, allow_nan=False))
        return 1
    try:
        qualify(receipts, manifest, prior, result)
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    checks = result["checks"]
    result["numeric_pass"] = (result["error"] is None and set(checks) == set(REQUIRED_CHECKS)
                              and all(checks.values()))
    result["verdict"] = VERDICT_SUPPORTS if result["numeric_pass"] else VERDICT_INCONCLUSIVE
    emit(args.output, result)
    print(json.dumps(dict(role=result["role"], verdict=result["verdict"],
                          numeric_pass=result["numeric_pass"], error=result["error"],
                          lower_bounds={row["method"]: row["lower_bound"] for row in result["rows"]}),
                      allow_nan=False))
    return 0 if result["numeric_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
