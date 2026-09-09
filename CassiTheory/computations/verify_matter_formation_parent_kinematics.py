"""Independent kinematic and coercivity verifier for notebook section 64.

This program intentionally does not import the parent matcher or the tree
verifier.  It binds the live section, frozen source snapshots, and the accepted
mathematical reviews before constructing any scientific rows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "matter-formation-parent-matching-manifest-v1"
RESULT_SCHEMA = "matter-formation-parent-matching-v1"
ROLE = "kinematics"
SECTION_PATH = "computations/matter-formation-continuum-report.md"
SECTION_HEADING = "## 64. Working notes: matching quantum conversion to the scalar action"
EXPECTED_SOURCES = {
    "computations/matter_formation_parent_matching.py",
    "computations/verify_matter_formation_parent_trees.py",
    "computations/verify_matter_formation_parent_kinematics.py",
    "foundations/particle-stationary-action-closure.md",
}
EXPECTED_REVIEW_ROLES = {"trees", "kinematics"}

# Frozen scalar inputs from section 64.  They are deliberately kept separate
# from the schedule so that a manifest/source mismatch cannot silently change
# the physical constants used by the rows.
U_RHO = 4.0
U_C = 1.0
K_CX = 1.0
E_C = 3.0 / 4.0
H_C = 2.9598260763447164
NORM_N = 1.0
A0 = 1.0 / 16.0
C0 = 1.0 / 8.0
TOL = 1.0e-9
COORD_TOL = 1.0e-7

MOMENTA: tuple[tuple[int, int, int], ...] = (
    (0, 0, 0),
    (1, 0, 0),
    (1, 2, -1),
    (8, -3, 4),
)
OFFSET = (0.3, -0.2, 0.4)


class VerificationError(RuntimeError):
    """A manifest, mathematical, or finite-output contract failure."""


def _normal_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def _sha256(path: Path) -> str:
    return hashlib.sha256(_normal_bytes(path)).hexdigest()


def _repo_path(value: str) -> Path:
    return ROOT / value


def _section_bytes(path: Path, heading: str) -> bytes:
    text = _normal_bytes(path).decode("utf-8")
    lines = text.split("\n")
    matches = [index for index, line in enumerate(lines) if line == heading]
    if len(matches) != 1:
        raise VerificationError(
            f"section heading {heading!r} occurs {len(matches)} times in {path}"
        )
    start = matches[0]
    end = next(
        (index for index in range(start + 1, len(lines)) if lines[index].startswith("## ")),
        len(lines),
    )
    # The section hash strips trailing whitespace from the extracted section as
    # a whole, then adds one LF.  Interior whitespace is source-bound.
    return ("\n".join(lines[start:end]).rstrip() + "\n").encode("utf-8")


def _section_sha(path: Path, heading: str) -> str:
    return hashlib.sha256(_section_bytes(path, heading)).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def _validate_manifest(manifest_path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - exercised by the CLI failure path
        raise VerificationError(f"cannot parse manifest: {exc}") from exc
    _require(isinstance(manifest, dict), "manifest must be a JSON object")
    _require(manifest.get("schema") == SCHEMA, "manifest schema mismatch")

    section = manifest.get("section")
    _require(isinstance(section, dict), "manifest section binding is missing")
    _require(section.get("path") == SECTION_PATH, "section path mismatch")
    _require(section.get("heading") == SECTION_HEADING, "section heading mismatch")
    section_live = _repo_path(SECTION_PATH)
    section_snapshot_value = section.get("snapshot")
    _require(isinstance(section_snapshot_value, str), "section snapshot is missing")
    section_snapshot = _repo_path(section_snapshot_value)
    expected_section_sha = section.get("sha256")
    _require(isinstance(expected_section_sha, str), "section sha256 is missing")
    _require(
        _section_sha(section_live, SECTION_HEADING) == expected_section_sha,
        "live section hash mismatch",
    )
    _require(
        _section_sha(section_snapshot, SECTION_HEADING) == expected_section_sha,
        "section snapshot hash mismatch",
    )

    sources = manifest.get("sources")
    _require(isinstance(sources, list), "manifest sources are missing")
    source_paths = [entry.get("path") for entry in sources if isinstance(entry, dict)]
    _require(len(source_paths) == len(sources), "malformed source binding")
    _require(len(source_paths) == len(set(source_paths)), "duplicate source binding")
    _require(set(source_paths) == EXPECTED_SOURCES, "source path set mismatch")
    source_bindings: list[dict[str, str]] = []
    for entry in sources:
        path_value = entry.get("path")
        snapshot_value = entry.get("snapshot")
        expected_sha = entry.get("sha256")
        _require(
            isinstance(path_value, str)
            and isinstance(snapshot_value, str)
            and isinstance(expected_sha, str),
            "malformed source binding fields",
        )
        live = _repo_path(path_value)
        snapshot = _repo_path(snapshot_value)
        _require(_sha256(live) == expected_sha, f"live source hash mismatch: {path_value}")
        _require(
            _sha256(snapshot) == expected_sha,
            f"source snapshot hash mismatch: {path_value}",
        )
        source_bindings.append(
            {"path": path_value, "snapshot": snapshot_value, "sha256": expected_sha}
        )

    reviews = manifest.get("mathematical_reviews")
    _require(isinstance(reviews, list), "mathematical reviews are missing")
    roles = [entry.get("role") for entry in reviews if isinstance(entry, dict)]
    _require(len(roles) == len(reviews), "malformed review binding")
    _require(len(roles) == len(set(roles)), "duplicate review role")
    _require(set(roles) == EXPECTED_REVIEW_ROLES, "review role set mismatch")
    review_bindings: list[dict[str, Any]] = []
    for entry in reviews:
        role = entry.get("role")
        snapshot_value = entry.get("snapshot")
        expected_sha = entry.get("sha256")
        _require(entry.get("accepted") is True, f"review {role!r} is not accepted")
        _require(
            isinstance(role, str)
            and isinstance(snapshot_value, str)
            and isinstance(expected_sha, str),
            "malformed review binding fields",
        )
        review_path = _repo_path(snapshot_value)
        review_text = review_path.read_text(encoding="utf-8").replace("\r\n", "\n")
        _require(
            "accepted: true" in review_text.splitlines(),
            f"review {role!r} lacks literal accepted: true line",
        )
        _require(
            "accepted: false" not in review_text.splitlines(),
            f"review {role!r} contains rejected acceptance line",
        )
        _require(_sha256(review_path) == expected_sha, f"review hash mismatch: {role}")
        review_bindings.append(
            {
                "role": role,
                "accepted": True,
                "snapshot": snapshot_value,
                "sha256": expected_sha,
            }
        )

    return {
        "manifest_sha256": _sha256(manifest_path),
        "section_sha256": expected_section_sha,
        "source_bindings": source_bindings,
        "review_bindings": review_bindings,
    }


def _coefficients(a: float, c: float) -> dict[str, float]:
    v = math.sqrt(NORM_N * c)
    m2 = 2.0 * U_RHO / c
    M2 = (E_C + 1.0 / (4.0 * a)) / a
    g = 2.0 * H_C / (a * v)
    g2 = g / v
    lambda3 = 3.0 * m2 / v
    lambda4 = 3.0 * m2 / (v * v)
    return {
        "v": v,
        "m2": m2,
        "M2": M2,
        "g": g,
        "g2": g2,
        "lambda3": lambda3,
        "lambda4": lambda4,
    }


def _dot(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(left, right))


def _norm(vector: Sequence[float]) -> float:
    return math.sqrt(_dot(vector, vector))


def _pair_kinematics(
    q: Sequence[float], P: Sequence[float], M2: float, speed2: float
) -> tuple[float, list[float], list[list[float]]]:
    """Pair energy, gradient and analytic Hessian for carrier momentum q."""
    r = [P[index] - q[index] for index in range(3)]
    q2 = _dot(q, q)
    r2 = _dot(r, r)
    first = math.sqrt(M2 + speed2 * q2)
    second = math.sqrt(M2 + speed2 * r2)
    gradient = [
        speed2 * q[index] / first - speed2 * r[index] / second
        for index in range(3)
    ]
    identity = [[1.0 if i == j else 0.0 for j in range(3)] for i in range(3)]
    hessian = [row[:] for row in identity]
    for i in range(3):
        for j in range(3):
            hessian[i][j] = (
                speed2 * identity[i][j] / first
                - speed2 * speed2 * q[i] * q[j] / (first**3)
                + speed2 * identity[i][j] / second
                - speed2 * speed2 * r[i] * r[j] / (second**3)
            )
    return first + second, gradient, hessian


def _pair_energy_change(
    q: Sequence[float], candidate: Sequence[float], P: Sequence[float],
    M2: float, speed2: float,
) -> float:
    """Rationalize each square-root difference before summing near a minimum."""
    displacement = [candidate[i] - q[i] for i in range(3)]
    d2 = math.fsum(value * value for value in displacement)
    other = [P[i] - q[i] for i in range(3)]
    changes = []
    for base, direction in ((q, 1.0), (other, -1.0)):
        endpoint = [base[i] + direction * displacement[i] for i in range(3)]
        before = math.sqrt(M2 + speed2 * math.fsum(value * value for value in base))
        after = math.sqrt(M2 + speed2 * math.fsum(value * value for value in endpoint))
        numerator = speed2 * math.fsum(
            [2.0 * direction * base[i] * displacement[i] for i in range(3)] + [d2]
        )
        changes.append(numerator / (after + before))
    return math.fsum(changes)


def _solve_3x3(matrix: Sequence[Sequence[float]], rhs: Sequence[float]) -> list[float]:
    """Pivoted Gaussian solve for the positive Hessian Newton step."""
    augmented = [list(matrix[index]) + [rhs[index]] for index in range(3)]
    for column in range(3):
        pivot = max(range(column, 3), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1.0e-15:
            raise VerificationError("singular analytic pair Hessian")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        scale = augmented[column][column]
        for index in range(column, 4):
            augmented[column][index] /= scale
        for row in range(3):
            if row == column:
                continue
            factor = augmented[row][column]
            for index in range(column, 4):
                augmented[row][index] -= factor * augmented[column][index]
    return [augmented[index][3] for index in range(3)]


def _independent_minimum(
    P: Sequence[float], M2: float, speed2: float
) -> tuple[list[float], float, list[float]]:
    """Newton minimization from the mandated displaced equal-sharing point."""
    q = [P[index] / 2.0 + OFFSET[index] for index in range(3)]
    for _ in range(64):
        energy, gradient, hessian = _pair_kinematics(q, P, M2, speed2)
        if _norm(gradient) < 1.0e-14:
            break
        step = _solve_3x3(hessian, gradient)
        scale = 1.0
        accepted = False
        while scale >= 2.0 ** -20:
            candidate = [q[index] - scale * step[index] for index in range(3)]
            energy_change = _pair_energy_change(q, candidate, P, M2, speed2)
            if energy_change <= 0.0:
                q = candidate
                accepted = True
                break
            scale *= 0.5
        if not accepted:
            raise VerificationError("analytic Newton minimization did not descend")
        if _norm([scale * component for component in step]) < 1.0e-14:
            break
    energy, gradient, _ = _pair_kinematics(q, P, M2, speed2)
    return q, energy, gradient


def _relative_error(left: float, right: float) -> float:
    return abs(left - right) / max(1.0, abs(right))


def _potential_values(a: float, f: float, n: float) -> tuple[float, float, float, float]:
    """Original, canonical reconstruction, lower bound, and remainder."""
    c = 2.0 * a
    coeff = _coefficients(a, c)
    v = coeff["v"]
    B = E_C + 1.0 / (4.0 * a)
    z = f * f
    original = U_RHO / 4.0 * (z - 1.0) ** 2
    original += (B - H_C * (1.0 - z)) * n + U_C / 2.0 * n * n

    sigma = v * (f - 1.0)
    phi = math.sqrt(a * n)
    canonical = coeff["m2"] / 2.0 * sigma * sigma
    canonical += coeff["M2"] * phi * phi
    canonical += coeff["lambda3"] / math.factorial(3) * sigma**3
    canonical += coeff["lambda4"] / math.factorial(4) * sigma**4
    canonical += coeff["g"] * sigma * phi * phi
    canonical += coeff["g2"] / 2.0 * sigma * sigma * phi * phi
    canonical += U_C / (2.0 * a * a) * phi**4

    q = max(H_C - B, 0.0)
    coercivity_constant = U_RHO / 4.0 + q * q / U_C
    lower_bound = U_RHO / 8.0 * f**4 + U_C / 4.0 * n * n - coercivity_constant
    return original, canonical, lower_bound, original - lower_bound


def _finite(value: Any) -> bool:
    if isinstance(value, bool):
        return True
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    if isinstance(value, list):
        return all(_finite(item) for item in value)
    if isinstance(value, dict):
        return all(_finite(item) for item in value.values())
    if isinstance(value, str) or value is None:
        return True
    return False


def _scientific_rows() -> tuple[
    list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], dict[str, Any], list[dict[str, Any]]
]:
    s = math.sqrt(U_RHO * U_C / 2.0)
    a_vac = 1.0 / (4.0 * (H_C - E_C - s))
    a_pair = 1.0
    ratio_at_vac = U_RHO * K_CX * a_vac / (1.0 + 4.0 * E_C * a_vac)
    schedule = (
        ("a_1_64", 1.0 / 64.0),
        ("a_1_32", 1.0 / 32.0),
        ("a_1_16", 1.0 / 16.0),
        ("a_vac_half", a_vac / 2.0),
        ("a_vac", a_vac),
    )

    rows: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    for a_key, a in schedule:
        c = 2.0 * a
        speed2 = 1.0 / c
        coeff = _coefficients(a, c)
        for P_int in MOMENTA:
            P = [float(item) for item in P_int]
            P2 = _dot(P, P)
            mediator_energy = math.sqrt(coeff["m2"] + speed2 * P2)
            pair_threshold = math.sqrt(4.0 * coeff["M2"] + speed2 * P2)
            deficit = pair_threshold - mediator_energy
            rationalized_deficit = (4.0 * coeff["M2"] - coeff["m2"]) / (
                pair_threshold + mediator_energy
            )
            minimizer, minimized_energy, gradient = _independent_minimum(
                P, coeff["M2"], speed2
            )
            exact_minimizer = [item / 2.0 for item in P]
            exact_energy = 2.0 * math.sqrt(coeff["M2"] + speed2 * P2 / 4.0)
            checks.append(
                {
                    "name": f"minimizer:{a_key}:{list(P_int)}",
                    "passed": max(
                        abs(minimizer[index] - exact_minimizer[index])
                        for index in range(3)
                    )
                    <= COORD_TOL
                    and _relative_error(minimized_energy, exact_energy) <= TOL
                    and _norm(gradient) <= TOL,
                }
            )
            checks.append(
                {
                    "name": f"deficit_identity:{a_key}:{list(P_int)}",
                    "passed": deficit > 0.0
                    and _relative_error(deficit, rationalized_deficit) <= TOL,
                }
            )
            rows.append(
                {
                    "a_key": a_key,
                    "a": a,
                    "P": P,
                    "c": c,
                    "speed2": speed2,
                    "m2": coeff["m2"],
                    "M2": coeff["M2"],
                    "ratio": coeff["m2"] / (4.0 * coeff["M2"]),
                    "mediator_energy": mediator_energy,
                    "pair_threshold": pair_threshold,
                    "deficit": deficit,
                    "rationalized_deficit": rationalized_deficit,
                    "minimizer": minimizer,
                    "minimized_energy": minimized_energy,
                    "gradient_at_minimum": gradient,
                }
            )

    witnesses: list[dict[str, Any]] = []
    for a_key, a in schedule:
        for f in (-2.0, 0.0, 1.0, 3.0):
            for n in (0.0, 0.25, 2.0, 8.0):
                original, canonical, lower_bound, remainder = _potential_values(a, f, n)
                checks.append(
                    {
                        "name": f"potential:{a_key}:f={f}:n={n}",
                        "passed": _relative_error(canonical, original) <= TOL
                        and remainder >= -TOL,
                    }
                )
                witnesses.append(
                    {
                        "a_key": a_key,
                        "a": a,
                        "f": f,
                        "n": n,
                        "original": original,
                        "canonical": canonical,
                        "lower_bound": lower_bound,
                        "coercivity_remainder": remainder,
                    }
                )

    a0_c = C0
    a0_coeff = _coefficients(A0, a0_c)
    m = math.sqrt(a0_coeff["m2"])
    M = math.sqrt(a0_coeff["M2"])
    pin_threshold = math.sqrt((a0_coeff["M2"] - a0_coeff["m2"]) / (1.0 / a0_c))
    pout_three = math.sqrt(((3.0 * m / 2.0) ** 2 - a0_coeff["M2"]) / (1.0 / a0_c))
    analytic_bounds = {
        "a_vac": a_vac,
        "a_pair": a_pair,
        "ratio_at_a_vac": ratio_at_vac,
    }
    reference = {
        "a": A0,
        "c": C0,
        "m": m,
        "M": M,
        "pin_threshold": pin_threshold,
        "pout_three": pout_three,
        "cold_minimum_quanta": 3,
    }
    checks.extend(
        [
            {"name": "schedule_row_count", "passed": len(rows) == 20},
            {"name": "potential_witness_count", "passed": len(witnesses) == 80},
            {"name": "vacuum_before_pair", "passed": 0.0 < a_vac < a_pair},
            {"name": "ratio_at_vac_below_one", "passed": ratio_at_vac < 1.0},
            {
                "name": "reference_masses",
                "passed": _relative_error(m, 8.0) <= TOL
                and _relative_error(M, math.sqrt(76.0)) <= TOL,
            },
            {
                "name": "reference_moving_thresholds",
                "passed": _relative_error(pin_threshold, math.sqrt(3.0 / 2.0)) <= TOL
                and _relative_error(pout_three, math.sqrt(17.0 / 2.0)) <= TOL,
            },
        ]
    )
    return rows, witnesses, analytic_bounds, reference, checks


def _failure_result(manifest_sha: str | None, error: str) -> dict[str, Any]:
    return {
        "schema": RESULT_SCHEMA,
        "role": ROLE,
        "manifest_sha256": manifest_sha,
        "source_bindings": [],
        "section_sha256": None,
        "checks": [],
        "rows": [],
        "potential_rows": [],
        "numeric_pass": False,
        "verdict": "INCONCLUSIVE",
        "complete_physical_matter_formation": False,
        "error": error,
    }


def _write_result(path: Path, result: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(result, indent=2, sort_keys=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    output = args.output
    if output.exists():
        print(json.dumps({"error": "output directory already exists", "verdict": "INCONCLUSIVE"}))
        return 1
    try:
        output.mkdir(parents=True, exist_ok=False)
    except Exception as exc:
        print(json.dumps({"error": f"cannot create output directory: {exc}", "verdict": "INCONCLUSIVE"}))
        return 1

    manifest_sha: str | None = None
    try:
        manifest_sha = _sha256(args.manifest)
        bindings = _validate_manifest(args.manifest)
        rows, potential_rows, analytic_bounds, reference, checks = _scientific_rows()
        passed = all(check["passed"] for check in checks)
        result = {
            "schema": RESULT_SCHEMA,
            "role": ROLE,
            "manifest_sha256": bindings["manifest_sha256"],
            "source_bindings": bindings["source_bindings"],
            "section_sha256": bindings["section_sha256"],
            "checks": checks,
            "rows": rows,
            "potential_rows": potential_rows,
            "analytic_bounds": analytic_bounds,
            "reference_kinematics": reference,
            "numeric_pass": passed,
            "verdict": "SUPPORTS-conditional scalar-parent production matching" if passed else "INCONCLUSIVE",
            "complete_physical_matter_formation": False,
        }
        _require(_finite(result), "nonfinite scientific output")
        _write_result(output / "result.json", result)
        print(json.dumps({"role": ROLE, "rows": 20, "potential_rows": 80, "verdict": result["verdict"]}))
        return 0 if passed else 1
    except Exception as exc:
        result = _failure_result(manifest_sha, str(exc))
        try:
            _write_result(output / "result.json", result)
        except Exception as write_exc:
            print(json.dumps({"error": f"{exc}; result write failed: {write_exc}", "verdict": "INCONCLUSIVE"}))
            return 1
        print(json.dumps({"role": ROLE, "rows": 0, "potential_rows": 0, "verdict": "INCONCLUSIVE", "error": str(exc)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
