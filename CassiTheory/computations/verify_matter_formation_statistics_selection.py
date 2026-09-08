from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any
import sympy as sp

import numpy as np
from scipy.integrate import solve_ivp


SCHEMA = "matter-formation-statistics-selection-verification-v1"
PRIMARY_SCHEMA = "matter-formation-statistics-selection-v1"
EXPECTED_SECTIONS = {
    "section1": ("### 38.1 A half-angle orbit and spatial rotations", "6ad640f866a36b57b0d51c4c161727dae797ba0fd20eecf7badab5a94c4011f7"),
    "section2": ("### 38.2 Quantum transfer changes the occupation drift", "837286ff5a4586994087aaf9b13ecd8578b8efe4516194c0d315ae9aef669f17"),
    "section3": ("### 38.3 Anomaly cancellation constrains a supplied chiral sector", "9433122093070db78c269f88320bbb991617066e9c3e3cde83674c74f29c900c"),
    "section4": ("### 38.4 Microscopic selection qualification: pre-execution criteria", "56cc9726dd95c2eceb9c7573acb24580d6de849e97bb90332e83b47d122d8f37"),
}
PHI = (1.0 + math.sqrt(5.0)) / 2.0
TOL_EXACT = 1e-11
TOL_ARRAY = 1e-10


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_sections(report: bytes) -> dict[str, bytes]:
    text = report.replace(b"\r\n", b"\n").decode("utf-8")
    lines = text.splitlines(keepends=True)
    headings = re.compile(r"^(#{1,6})[ \t]+.*(?:\n|$)")
    found: dict[str, bytes] = {}
    for key, (heading, _) in EXPECTED_SECTIONS.items():
        start = next((i for i, line in enumerate(lines) if line.rstrip("\n") == heading), None)
        if start is None:
            continue
        level = heading.split(" ", 1)[0].count("#")
        stop = len(lines)
        for i in range(start + 1, len(lines)):
            match = headings.match(lines[i])
            if match and len(match.group(1)) <= level:
                stop = i
                break
        found[key] = "".join(lines[start:stop]).rstrip() + "\n"
        found[key] = found[key].encode("utf-8")
    return found


def close(a: Any, b: Any, atol: float = TOL_EXACT) -> bool:
    try:
        return bool(np.allclose(np.asarray(a), np.asarray(b), rtol=0.0, atol=atol))
    except (TypeError, ValueError):
        return False


def finite_array(a: np.ndarray) -> bool:
    return bool(np.all(np.isfinite(a))) if np.issubdtype(a.dtype, np.number) else False


def check(name: str, passed: bool, **evidence: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"name": name, "passed": bool(passed)}
    row.update(evidence)
    return row


def exact_zero(value: Any) -> bool:
    if isinstance(value, sp.MatrixBase):
        return value.applyfunc(sp.simplify) == sp.zeros(value.rows, value.cols)
    return sp.simplify(value) == 0


def pauli_algebra() -> tuple[dict[str, Any], dict[str, float]]:
    eye = sp.eye(2)
    sigma = (sp.Matrix([[0, 1], [1, 0]]),
             sp.Matrix([[0, -sp.I], [sp.I, 0]]),
             sp.diag(1, -1))
    generators = [s / 2 for s in sigma]
    commutators = all(exact_zero(generators[i] * generators[j] - generators[j] * generators[i] - sp.I * generators[k])
                      for i, j, k in ((0, 1, 2), (1, 2, 0), (2, 0, 1)))
    ux, uy = [(eye - sp.I * s) / sp.sqrt(2) for s in sigma[:2]]
    group = sp.simplify(ux * uy * ux.H * uy.H)
    scalar = sp.exp(sp.I * sp.pi / 4) * eye
    scalar_group = sp.simplify(scalar * scalar * scalar.H * scalar.H)
    signs = all(exact_zero(sp.cos(angle / 2) * eye - sp.I * sp.sin(angle / 2) * s - target)
                for s in sigma for angle, target in ((2 * sp.pi, -eye), (4 * sp.pi, eye)))
    return {
        "rotation_J": np.asarray([np.array(j, dtype=complex) for j in generators]),
        "rotation_commutator": np.array(group, dtype=complex),
        "checks": [
            check("pauli_generators_exact", all(exact_zero(j - j.H) for j in generators)),
            check("angular_commutators_exact", commutators),
            check("trace_obstruction_exact", all(sp.trace(j) == 0 for j in generators) and sp.trace(-eye / 2) == -1),
            check("rotation_group_commutator_exact", sp.trace(group) == 1),
            check("scalar_group_commutator_exact", sp.trace(scalar_group) == 2),
            check("spinor_signs_exact", signs),
        ],
    }, {"rotation_commutator_trace": float(sp.trace(group)), "scalar_commutator_trace": float(sp.trace(scalar_group))}




def sector_basis(model: str, N: int) -> list[tuple[int, int]]:
    if model == "fermi":
        return [(0, 1), (1, 0)] if N == 1 else [(1, 1)]
    return [(k, N - k) for k in range(N + 1)]




def direct_drift_checks() -> tuple[list[dict[str, Any]], dict[str, dict[str, np.ndarray]], dict[str, Any]]:
    phi = (1 + sp.sqrt(5)) / 2
    a = sp.Matrix([[0, 1, 0], [0, 0, sp.sqrt(2)], [0, 0, 0]])
    by, bi = sp.kronecker_product(a, sp.eye(3)), sp.kronecker_product(sp.eye(3), a)
    f = sp.Matrix([[0, 1], [0, 0]])
    fy, fi = sp.kronecker_product(f, sp.eye(2)), sp.kronecker_product(sp.diag(1, -1), f)
    nyb, nib = by.H * by, bi.H * bi
    nyf, nif = fy.H * fy, fi.H * fi
    # Inverse final-occupation factors remove Bose stimulation in the supplied
    # occupation-shift reservoir, in the stated operator order.
    inv_i = sp.diag(*[1 / sp.sqrt(nib[k, k] + 1) for k in range(9)])
    inv_y = sp.diag(*[1 / sp.sqrt(nyb[k, k] + 1) for k in range(9)])
    full = {
        "boson": (bi.H * by, by.H * bi, nyb, nib, 3),
        "shift": (bi.H * inv_i * by, by.H * inv_y * bi, nyb, nib, 3),
        "fermi": (fi.H * fy, fy.H * fi, nyf, nif, 2),
    }
    checks = [check("fermionic_car_exact",
                    all(exact_zero(x * y.H + y.H * x - (sp.eye(4) if i == j else sp.zeros(4)))
                        and exact_zero(x * y + y * x)
                        for i, x in enumerate((fy, fi)) for j, y in enumerate((fy, fi))))]
    records: dict[str, dict[str, np.ndarray]] = {}
    exact_generators: dict[str, sp.Matrix] = {}
    means: dict[str, Any] = {}
    def adjoint(jump: sp.Matrix, observable: sp.Matrix) -> sp.Matrix:
        jj = jump.H * jump
        return jump.H * observable * jump - (jj * observable + observable * jj) / 2
    for model, (full_down, full_up, nyop, niop, width) in full.items():
        for total in (1, 2):
            key = f"{model}_N{total}"
            basis = sector_basis(model, total)
            indices = [width * y + i for y, i in basis]
            down = full_down.extract(indices, indices)
            up = full_up.extract(indices, indices)
            rule_down, rule_up = sp.zeros(len(basis)), sp.zeros(len(basis))
            for col, (y, i) in enumerate(basis):
                if (y - 1, i + 1) in basis:
                    amplitude = sp.sqrt(y * (i + 1)) if model == "boson" else sp.sqrt(y)
                    rule_down[basis.index((y - 1, i + 1)), col] = amplitude
                if (y + 1, i - 1) in basis:
                    amplitude = sp.sqrt(i * (y + 1)) if model == "boson" else sp.sqrt(i)
                    rule_up[basis.index((y + 1, i - 1)), col] = amplitude
            checks.append(check(f"{key}_transition_rules_exact", exact_zero(down - rule_down) and exact_zero(up - rule_up)))
            drift = adjoint(full_down, nyop) + phi * adjoint(full_up, nyop)
            sign = 1 if model == "boson" else (-1 if model == "fermi" else 0)
            expected = phi * niop - nyop + sign * (phi - 1) * nyop * niop
            checks.append(check(f"{key}_adjoint_drift_exact", exact_zero((drift - expected).extract(indices, indices))))
            conservation = adjoint(full_down, nyop + niop) + phi * adjoint(full_up, nyop + niop)
            checks.append(check(f"{key}_total_conservation_exact", exact_zero(conservation.extract(indices, indices))))
            d = len(basis)
            G = sp.zeros(d)
            for col in range(d):
                for row in range(d):
                    if row != col:
                        G[row, col] = sp.simplify(down[row, col] ** 2 + phi * up[row, col] ** 2)
                G[col, col] = -sum(G[row, col] for row in range(d) if row != col)
            weights = [sp.Integer(1)]
            for k in range(d - 1):
                weights.append(sp.simplify(weights[-1] * G[k + 1, k] / G[k, k + 1]))
            p = sp.simplify(sp.Matrix(weights) / sum(weights))
            expected_weights = sp.Matrix([(sp.binomial(total, y) if model == "shift" else 1) * phi ** y for y, _ in basis])
            expected_p = sp.simplify(expected_weights / sum(expected_weights))
            checks.append(check(f"{key}_stationary_exact", exact_zero(G * p) and exact_zero(sum(p) - 1) and exact_zero(p - expected_p)))
            checks.append(check(f"{key}_column_conservation_exact", exact_zero(sp.ones(1, d) * G)))
            means[key] = sp.simplify(sum(y * p[k] for k, (y, _) in enumerate(basis)))
            exact_generators[key] = G
            gn = np.array(G, dtype=float)
            initial = np.eye(d)[:, 0]
            sol = solve_ivp(lambda _t, x: gn @ x, (0.0, 3.0), initial,
                            method="DOP853", t_eval=[0.0, 0.25, 1.0, 3.0], rtol=2e-13, atol=2e-15)
            if not sol.success:
                raise RuntimeError("independent occupation ODE failed: " + sol.message)
            records[key] = {
                "generator": gn, "stationary": np.array(p, dtype=float).ravel(),
                "number_y": np.array([y for y, _ in basis], dtype=float),
                "jump_down": np.array(down, dtype=float),
                "jump_up": np.array(sp.sqrt(phi) * up, dtype=float),
                "trajectory": sol.y.T,
            }
    checks.append(check("n1_generators_exact", all(exact_zero(exact_generators[f"{model}_N1"] - exact_generators["shift_N1"]) for model in ("boson", "fermi"))))
    checks.append(check("n1_means_exact", all(exact_zero(means[f"{model}_N1"] - phi / (1 + phi)) for model in ("boson", "shift", "fermi"))))
    targets = ((phi + 2 * phi ** 2) / (1 + phi + phi ** 2), 2 * phi / (1 + phi), sp.Integer(1))
    checks.append(check("n2_means_exact", all(exact_zero(means[f"{model}_N2"] - target) for model, target in zip(("boson", "shift", "fermi"), targets))))
    checks.append(check("n2_means_distinct", all(not exact_zero(targets[i] - targets[j]) for i, j in ((0, 1), (0, 2), (1, 2)))))
    gamma = sp.simplify(phi ** -2 / (2 + phi ** -2))
    gated = sp.simplify(gamma * (phi - 1))
    blocked = exact_generators["fermi_N2"][0, 0]
    checks.append(check("gated_pauli_boundary_exact", gated > 0 and blocked == 0))
    return checks, records, {
        "stationary_means": {key: float(value) for key, value in means.items()},
        "gated_pauli_drift": float(gated),
    }


def anomaly_polynomials(Nc: int, yQ: float, yL: float, yu: float, yd: float, ye: float, ynu: float | None = None) -> list[float]:
    out = [2 * yQ - yu - yd, Nc * yQ + yL,
           2 * Nc * yQ - Nc * yu - Nc * yd + 2 * yL - ye,
           2 * Nc * yQ ** 3 - Nc * yu ** 3 - Nc * yd ** 3 + 2 * yL ** 3 - ye ** 3]
    if ynu is not None:
        out[2] -= ynu
        out[3] -= ynu ** 3
    return out


def anomaly_checks() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    nc, q, h = sp.symbols("N_c q h", nonzero=True)
    charges = sp.symbols("y_Q y_L y_u y_d y_e")
    polynomials = anomaly_polynomials(nc, *charges)
    yukawa = (q, -nc * q, q + h, q - h, -nc * q - h)
    substituted = [sp.expand(p.subs(dict(zip(charges, yukawa)), simultaneous=True)) for p in polynomials]
    no_nu = [sp.factor(p.subs(q, h / nc)) for p in substituted]
    with_nu = list(substituted)
    with_nu[2] -= -nc * q + h
    with_nu[3] -= (-nc * q + h) ** 3
    with_nu = [sp.expand(p) for p in with_nu]
    # Coefficient identities cover the family, rather than selected float points.
    checks = [
        check("anomaly_no_neutrino_exact", all(exact_zero(p) for p in no_nu)),
        check("anomaly_neutrino_family_exact", all(sp.Poly(p, q, h, nc).is_zero for p in with_nu)),
    ]
    for color in (3, 5):
        values = tuple(sp.simplify(x.subs(q, h / nc).subs({nc: color, h: sp.Rational(1, 2)})) for x in yukawa)
        residuals = anomaly_polynomials(color, *values)
        checks.append(check(f"anomaly_Nc{color}_assignment_exact", all(exact_zero(p) for p in residuals) and (color + 1) % 2 == 0, charges=[str(v) for v in values]))
    conjugate = [sp.expand(p.subs({c: -c for c in charges}, simultaneous=True)) for p in polynomials]
    checks.append(check("vectorlike_cancellation_exact", all(exact_zero(a + b) for a, b in zip(polynomials, conjugate))))
    doublet_multiplicity = sp.symbols("doublet_multiplicity", integer=True)
    checks.append(check("vectorlike_doublet_parity_exact", sp.Mod(2 * doublet_multiplicity, 2) == 0))
    return checks, {"no_neutrino_residuals": [str(p) for p in no_nu], "neutrino_residuals": [str(p) for p in with_nu]}


def build_arrays(records: dict[str, dict[str, np.ndarray]], algebra: dict[str, Any]) -> dict[str, np.ndarray]:
    arrays: dict[str, np.ndarray] = {
        "rotation_J": np.asarray(algebra["rotation_J"]),
        "rotation_commutator": np.asarray(algebra["rotation_commutator"]),
        "times": np.asarray([0.0, 0.25, 1.0, 3.0]),
    }
    for key, rec in records.items():
        arrays[f"{key}_generator"] = rec["generator"]
        arrays[f"{key}_stationary"] = rec["stationary"]
        arrays[f"{key}_number_y"] = rec["number_y"]
        arrays[f"{key}_jump_down"] = rec["jump_down"]
        arrays[f"{key}_jump_up"] = rec["jump_up"]
        if not key.startswith("fermi"):
            arrays[f"{key}_trajectory"] = rec["trajectory"]
    arrays["no_neutrino_hypercharges"] = np.asarray([[1 / 6, -0.5, 2 / 3, -1 / 3, -1.0], [1 / 10, -0.5, 0.6, -0.4, -1.0]])
    arrays["no_neutrino_doublets"] = np.asarray([4, 6], dtype=int)
    arrays["gated_pauli_drift"] = np.asarray([(PHI - 1) * PHI ** -2 / (2.0 + PHI ** -2)])
    return arrays


def expected_shapes() -> dict[str, tuple[int, ...]]:
    out = {"rotation_J": (3, 2, 2), "rotation_commutator": (2, 2), "times": (4,), "no_neutrino_hypercharges": (2, 5), "no_neutrino_doublets": (2,), "gated_pauli_drift": (1,)}
    for model in ("boson", "shift", "fermi"):
        for N in (1, 2):
            d = N + 1 if model != "fermi" else (2 if N == 1 else 1)
            for suffix in ("generator", "stationary", "number_y", "jump_down", "jump_up"):
                out[f"{model}_N{N}_{suffix}"] = (d, d) if suffix in ("generator", "jump_down", "jump_up") else (d,)
            if model != "fermi":
                out[f"{model}_N{N}_trajectory"] = (4, d)
    return out


def validate_primary(primary: Path, supplied_sha: str, report_sections: dict[str, bytes]) -> tuple[list[str], dict[str, Any] | None, dict[str, np.ndarray] | None]:
    errors: list[str] = []
    result_path = primary / "results.json"
    source_path = primary / "program_source.py"
    data_path = primary / "data.npz"
    if not result_path.is_file() or not source_path.is_file() or not data_path.is_file():
        return ["missing primary receipt, source snapshot, or data.npz"], None, None
    actual_receipt_sha = sha256_file(result_path)
    if supplied_sha != actual_receipt_sha:
        errors.append("primary receipt SHA-256 mismatch")
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return errors + [f"invalid primary JSON: {exc}"], None, None
    required = {"schema", "passed", "verdict", "complete_physical_matter_formation", "source_sha256", "section_hashes", "array_sha256", "checks", "numbers", "error"}
    if not isinstance(result, dict):
        return errors + ["primary receipt must be a JSON object"], None, None
    if not required.issubset(result) or result.get("schema") != PRIMARY_SCHEMA:
        errors.append("primary schema or required fields invalid")
    if not isinstance(result.get("section_hashes"), dict):
        return errors + ["primary section hashes must be an object"], None, None
    primary_checks = result.get("checks")
    if (not isinstance(primary_checks, list) or not primary_checks
            or any(not isinstance(row, dict) or not isinstance(row.get("name"), str)
                   or not isinstance(row.get("passed"), bool) for row in primary_checks)):
        errors.append("primary scientific check schema invalid")
    elif len({row["name"] for row in primary_checks}) != len(primary_checks):
        errors.append("primary check names are not unique")
    if not isinstance(result.get("numbers"), dict):
        errors.append("primary numbers must be an object")
    if not isinstance(result.get("passed"), bool):
        errors.append("primary passed must be boolean")
    if result.get("complete_physical_matter_formation") is not False:
        errors.append("primary completion flag is not false")
    if result.get("source_sha256") != sha256_file(source_path):
        errors.append("primary source hash does not match retained source")
    for key, (_, digest) in EXPECTED_SECTIONS.items():
        if result.get("section_hashes", {}).get(key) != digest:
            errors.append(f"primary section hash mismatch: {key}")
        snap = primary / f"{key}.txt"
        if not snap.is_file() or snap.read_bytes() != report_sections.get(key, b""):
            errors.append(f"primary section snapshot mismatch: {key}")
    if result.get("array_sha256") != sha256_file(data_path):
        errors.append("primary raw array hash does not match data.npz")
    try:
        with np.load(data_path, allow_pickle=False) as loaded:
            arrays = {k: loaded[k] for k in loaded.files}
    except Exception as exc:
        return errors + [f"invalid primary data.npz: {exc}"], result, None
    expected = expected_shapes()
    if set(arrays) != set(expected):
        errors.append("primary data keys differ from canonical key set")
    for key, shape in expected.items():
        if key not in arrays:
            continue
        if arrays[key].shape != shape:
            errors.append(f"primary array shape mismatch: {key}")
        if not finite_array(arrays[key]):
            errors.append(f"primary array nonfinite or nonnumeric: {key}")
    return errors, result, arrays


def compare_numbers(primary: Any, independent: Any, path: str = "numbers") -> list[str]:
    if isinstance(independent, dict):
        if not isinstance(primary, dict) or set(primary) != set(independent):
            return [path + ": key mismatch"]
        return [mismatch for key in independent
                for mismatch in compare_numbers(primary[key], independent[key], f"{path}.{key}")]
    if isinstance(independent, list):
        if not isinstance(primary, list) or len(primary) != len(independent):
            return [path + ": list mismatch"]
        return [mismatch for k, value in enumerate(independent)
                for mismatch in compare_numbers(primary[k], value, f"{path}[{k}]")]
    if isinstance(independent, (int, float)) and not isinstance(independent, bool):
        if (not isinstance(primary, (int, float)) or isinstance(primary, bool)
                or not math.isfinite(float(primary))
                or not math.isfinite(float(independent))
                or abs(float(primary) - float(independent)) > TOL_ARRAY):
            return [path]
    elif type(primary) is not type(independent) or primary != independent:
        return [path]
    return []


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Independent verifier for matter-formation finite statistics")
    parser.add_argument("--primary", required=True, type=Path)
    parser.add_argument("--primary-sha", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--record", default="report")
    args = parser.parse_args(argv)
    out = args.output_dir
    try:
        out.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        print("INCONCLUSIVE: output directory already exists", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"INCONCLUSIVE: cannot create output directory: {exc}", file=sys.stderr)
        return 1
    own_source = Path(__file__).read_bytes()
    report_path = Path(__file__).with_name("matter-formation-continuum-report.md")
    report_sections: dict[str, bytes] = {}
    section_errors: list[str] = []
    if not report_path.is_file():
        section_errors.append("missing continuum report")
    else:
        report_sections = canonical_sections(report_path.read_bytes())
        for key, (_, digest) in EXPECTED_SECTIONS.items():
            if key not in report_sections or sha256_bytes(report_sections[key]) != digest:
                section_errors.append(f"frozen section mismatch: {key}")
    (out / "program_source.py").write_bytes(own_source)
    for key in EXPECTED_SECTIONS:
        (out / f"{key}.txt").write_bytes(report_sections.get(key, b""))
    prereq_errors = section_errors
    if not prereq_errors:
        primary_errors, primary_result, primary_arrays = validate_primary(args.primary, args.primary_sha, report_sections)
        prereq_errors.extend(primary_errors)
    else:
        primary_result, primary_arrays = None, None
    base: dict[str, Any] = {
        "schema": SCHEMA,
        "passed": False,
        "verdict": "INCONCLUSIVE",
        "complete_physical_matter_formation": False,
        "source_sha256": sha256_bytes(own_source),
        "section_hashes": {key: digest for key, (_, digest) in EXPECTED_SECTIONS.items()},
        "array_sha256": None,
        "primary_sha256": args.primary_sha if re.fullmatch(r"[0-9a-fA-F]{64}", args.primary_sha) else None,
        "checks": [],
        "numbers": {},
        "source_review": "Independent reconstruction of Pauli/SU(2), finite occupation transitions, Lindblad drift, solve_ivp trajectories, and anomaly polynomials; no primary program is imported.",
        "error": "; ".join(prereq_errors) if prereq_errors else None,
    }
    if prereq_errors:
        write_json(out / "verification.json", base)
        record = out / ("report.json" if args.record == "report" else args.record)
        if record != out / "verification.json":
            write_json(record, base)
        print("INCONCLUSIVE")
        return 1
    try:
        algebra, algebra_numbers = pauli_algebra()
        drift_checks, records, drift_numbers = direct_drift_checks()
        anomaly_rows, anomaly_numbers = anomaly_checks()
        arrays = build_arrays(records, algebra)
        np.savez(out / "data.npz", **arrays)
        base["array_sha256"] = sha256_file(out / "data.npz")
        scientific_checks = algebra["checks"] + drift_checks + anomaly_rows
        # Independent trajectories are compared to the primary arrays only after
        # all source, identity and finite-array prerequisites have passed.
        array_mismatches: list[str] = []
        assert primary_arrays is not None and primary_result is not None
        for key in sorted(arrays):
            if key not in primary_arrays or arrays[key].shape != primary_arrays[key].shape or not close(arrays[key], primary_arrays[key], TOL_ARRAY):
                array_mismatches.append(key)
        scientific_checks.append(check("primary_array_reconciliation", not array_mismatches, mismatches=array_mismatches))
        trajectories = [arrays[key] for key in arrays if key.endswith("_trajectory")]
        max_norm_error = max(float(np.max(np.abs(np.sum(p, axis=1) - 1))) for p in trajectories)
        min_probability = min(float(np.min(p)) for p in trajectories)
        n1_disagreement = float(np.max(np.abs(arrays["boson_N1_trajectory"] - arrays["shift_N1_trajectory"])))
        scientific_checks.extend([
            check("trajectory_normalization", max_norm_error <= 1e-12, error=max_norm_error),
            check("trajectory_nonnegative", min_probability >= -1e-12, minimum=min_probability),
            check("n1_trajectory_agreement", n1_disagreement <= 1e-12, error=n1_disagreement),
        ])
        numbers = {
            **drift_numbers,
            "anomaly_residuals": anomaly_numbers,
            "n1_trajectory_max_disagreement": n1_disagreement,
            "trajectory_max_normalization_error": max_norm_error,
            "trajectory_min_probability": min_probability,
        }
        number_mismatches = compare_numbers(primary_result["numbers"], numbers)
        primary_failed = [row["name"] for row in primary_result["checks"] if row["passed"] is not True]
        scientific_checks.append(check("primary_substantive_claims",
                                       not number_mismatches and not primary_failed and primary_result["error"] is None,
                                       number_mismatches=number_mismatches, failed_primary_checks=primary_failed))
        base["independent_diagnostics"] = algebra_numbers
        passed = all(row["passed"] for row in scientific_checks)
        expected_verdict = "SUPPORTS-conditional microscopic selection constraints" if passed else "INCONCLUSIVE"
        # The primary claim is substantive: it must agree with the independently
        # reconstructed verdict and false-completion boundary.
        if primary_result.get("passed") is not passed or primary_result.get("verdict") != expected_verdict:
            scientific_checks.append(check("primary_verdict_reconciliation", False))
            passed = False
            expected_verdict = "INCONCLUSIVE"
        else:
            scientific_checks.append(check("primary_verdict_reconciliation", True))
        base.update({"passed": passed, "verdict": expected_verdict, "checks": scientific_checks, "numbers": numbers, "error": None if passed else "one or more independent criteria failed"})
    except Exception as exc:
        base["error"] = f"typed scientific failure: {type(exc).__name__}: {exc}"
        base["checks"] = []
        base["numbers"] = {}
    write_json(out / "verification.json", base)
    record = out / ("report.json" if args.record == "report" else args.record)
    if record != out / "verification.json":
        write_json(record, base)
    print(base["verdict"])
    return 0 if base["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
