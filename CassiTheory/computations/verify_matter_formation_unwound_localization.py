#!/usr/bin/env python3
"""Independent PA12 reconstruction for the section-49 unwound droplet witness."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "matter-formation-unwound-localization-verification-v1"
PRIMARY_SCHEMA = "matter-formation-unwound-localization-v1"
INCONCLUSIVE = "INCONCLUSIVE"
SECTION_HEADING = "## 49. Working notes:"
COMPONENT_NAMES = (
    "fundamental_gradient",
    "adjoint_gradient",
    "gauge_energy",
    "density_potential",
    "composition_potential",
    "adjoint_potential",
    "carrier_gradient",
    "carrier_interaction",
    "carrier_quartic",
)
RADII = (0.0, 1.0, 4.0, 16.0, 64.0)
VOLUME_FACTORS = (1.0, 2.0, 8.0)
QUADRATURES = (4, 8)

RHO0 = 1.2
KX = 0.83
KCX = 1.0
LAMBDA_RHO = 1.0
LAMBDA_C = 1.0
ETA = 1.0
V_Q = 0.9
LAMBDA_PHI = 1.0
LAMBDA_H = 1.0
H = 1.0
EPSILON = 1.0e-10
ZERO_EPSILON = 1.0e-12


def canonical_bytes(path: Path) -> bytes:
    data = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return data if data.endswith(b"\n") else data + b"\n"


def raw_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finite(value: Any) -> bool:
    if isinstance(value, bool) or value is None:
        return value is not None
    if isinstance(value, (int, float, np.integer, np.floating)):
        return math.isfinite(float(value))
    if isinstance(value, complex):
        return math.isfinite(value.real) and math.isfinite(value.imag)
    if isinstance(value, dict):
        return all(finite(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return all(finite(v) for v in value)
    return True


def check(checks: dict[str, Any], name: str, passed: bool, **evidence: Any) -> None:
    checks[name] = {"pass": bool(passed), **evidence}


def constants() -> dict[str, float]:
    s_star = RHO0 * math.sqrt(LAMBDA_RHO / (2.0 * LAMBDA_C))
    mu_star = RHO0 * (math.sqrt(LAMBDA_RHO * LAMBDA_C / 2.0) - ETA)
    alpha = ETA * ETA / LAMBDA_RHO - LAMBDA_C / 2.0
    sobolev_constant = (4.0 / math.pi**2) ** (1.0 / 3.0) / math.sqrt(3.0)
    n_low = KCX ** 1.5 / (2.0 * alpha * sobolev_constant**3 * math.sqrt(-2.0 * mu_star))
    return {
        "rho0": RHO0,
        "Kx": KX,
        "KCx": KCX,
        "lambda_rho": LAMBDA_RHO,
        "lambda_C": LAMBDA_C,
        "eta": ETA,
        "s_star": s_star,
        "mu_star": mu_star,
        "alpha": alpha,
        "sobolev_constant": sobolev_constant,
        "N_low": n_low,
        "h": H,
    }


def verify_manifest(manifest_path: Path, checks: dict[str, Any]) -> str:
    manifest_sha = raw_sha256(manifest_path)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    check(checks, "manifest_schema", data.get("schema") == "matter-formation-unwound-localization-manifest-v1", actual=data.get("schema"))
    section = data.get("section")
    sources = data.get("sources")
    check(checks, "manifest_shape", isinstance(section, dict) and isinstance(sources, list), section_type=type(section).__name__, source_count=len(sources) if isinstance(sources, list) else -1)
    if not isinstance(section, dict) or not isinstance(sources, list):
        return manifest_sha
    expected_sources = {
        "computations/matter_formation_unwound_localization.py",
        "computations/verify_matter_formation_unwound_localization.py",
        "foundations/particle-stationary-action-closure.md",
    }
    actual_sources = {item.get("path") for item in sources if isinstance(item, dict)}
    check(checks, "manifest_source_paths", actual_sources == expected_sources and len(sources) == len(expected_sources), expected=sorted(expected_sources), actual=sorted(actual_sources))
    section_path = ROOT / str(section.get("path", ""))
    section_snapshot = manifest_path.parent / str(section.get("snapshot", ""))
    try:
        live_canonical = canonical_bytes(section_path)
        snap_canonical = canonical_bytes(section_snapshot)
        expected_section_sha = str(section.get("sha256", ""))
        check(checks, "section_snapshot_hash", hashlib.sha256(snap_canonical).hexdigest() == expected_section_sha, expected=expected_section_sha, actual=hashlib.sha256(snap_canonical).hexdigest())
        check(checks, "section_live_presence", snap_canonical in live_canonical, snapshot_bytes=len(snap_canonical), live_bytes=len(live_canonical))
        check(checks, "section_path", section.get("path") == "computations/matter-formation-continuum-report.md", actual=section.get("path"))
        check(checks, "section_heading", section.get("heading") == SECTION_HEADING, actual=section.get("heading"))
    except Exception as exc:
        check(checks, "section_files", False, error=f"{type(exc).__name__}: {exc}")
    for index, item in enumerate(sources):
        label = f"source_{index}"
        try:
            path = ROOT / str(item["path"])
            snapshot = manifest_path.parent / str(item["snapshot"])
            expected = str(item["sha256"])
            live_hash = raw_sha256(path)
            snapshot_hash = raw_sha256(snapshot)
            check(checks, f"{label}_live_hash", live_hash == expected, expected=expected, actual=live_hash, path=str(item["path"]))
            check(checks, f"{label}_snapshot_hash", snapshot_hash == expected, expected=expected, actual=snapshot_hash, snapshot=str(item["snapshot"]))
        except Exception as exc:
            check(checks, f"{label}_files", False, error=f"{type(exc).__name__}: {exc}")
    return manifest_sha


def gauss_segment(order: int, lo: float, hi: float, radius_offset: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    nodes, weights = np.polynomial.legendre.leggauss(order)
    x = 0.5 * (hi - lo) * nodes + 0.5 * (hi + lo)
    w = 0.5 * (hi - lo) * weights
    r = radius_offset + x
    return r, w * (4.0 * math.pi * r * r)


def integrate_witness(R: float, volume_factor: float, order: int, arrays: dict[str, np.ndarray]) -> dict[str, Any]:
    scale = volume_factor ** (1.0 / 3.0)
    radius = R * scale
    thickness = H * scale
    direction = np.array([1.0 / math.sqrt((1.0 + math.sqrt(5.0)) / 2.0), 1.0 / ((1.0 + math.sqrt(5.0)) / 2.0)], dtype=np.complex128)
    s_star = constants()["s_star"]
    if radius == 0.0:
        core_r = np.empty(0, dtype=np.float64)
        core_w = np.empty(0, dtype=np.float64)
    else:
        core_r, core_w = gauss_segment(order, 0.0, radius)
    wall_r, wall_w = gauss_segment(order, 0.0, thickness, radius_offset=radius)
    wall_t = (wall_r - radius) / thickness
    core_u = np.zeros_like(core_r)
    core_du = np.zeros_like(core_r)
    core_c = np.full_like(core_r, math.sqrt(s_star))
    core_dc = np.zeros_like(core_r)
    wall_u = math.sqrt(RHO0) * wall_t
    wall_du = np.full_like(wall_t, math.sqrt(RHO0) / thickness)
    wall_c = math.sqrt(s_star) * (1.0 - wall_t)
    wall_dc = np.full_like(wall_t, -math.sqrt(s_star) / thickness)

    def block(r: np.ndarray, weights: np.ndarray, u: np.ndarray, du: np.ndarray, c: np.ndarray, dc: np.ndarray, part: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        psi = u[:, None] * direction[None, :]
        dpsi = du[:, None] * direction[None, :]
        adjoint = np.zeros((len(r), 3), dtype=np.float64)
        adjoint[:, 2] = V_Q
        rho = np.real(np.einsum("ni,ni->n", psi.conj(), psi))
        pauli = np.array([[[0, 1], [1, 0]], [[0, -1j], [1j, 0]], [[1, 0], [0, -1]]], dtype=np.complex128)
        spin = np.stack([np.real(np.einsum("ni,ij,nj->n", psi.conj(), matrix, psi)) for matrix in pauli], axis=1)
        composition = 0.5 * ((1.0 - ((1.0 + math.sqrt(5.0)) / 2.0)) * rho + (1.0 + ((1.0 + math.sqrt(5.0)) / 2.0)) * (adjoint[:, 2] * spin[:, 2] / V_Q))
        currents = np.stack([np.imag(np.einsum("ni,ij,nj->n", psi.conj(), matrix / 2.0, dpsi)) for matrix in pauli], axis=1)
        density = np.column_stack((
            0.5 * KX * np.real(np.einsum("ni,ni->n", dpsi.conj(), dpsi)),
            np.zeros(len(r)),
            np.zeros(len(r)),
            LAMBDA_RHO / 4.0 * (rho - RHO0) ** 2,
            LAMBDA_PHI / 2.0 * composition**2,
            LAMBDA_H / 4.0 * (np.real(np.einsum("ni,ni->n", adjoint, adjoint)) - V_Q**2) ** 2,
            0.5 * KCX * dc**2,
            -ETA * (RHO0 - rho) * c**2,
            0.5 * LAMBDA_C * c**4,
        ))
        prefix = f"R{int(R)}_v{int(volume_factor)}_q{order}_{part}"
        arrays[f"{prefix}_r"] = r.astype(np.float64)
        arrays[f"{prefix}_weights"] = weights.astype(np.float64)
        arrays[f"{prefix}_Psi"] = psi
        arrays[f"{prefix}_dPsi"] = dpsi
        arrays[f"{prefix}_adjoint"] = adjoint
        arrays[f"{prefix}_c"] = c.astype(np.float64)
        arrays[f"{prefix}_dc"] = dc.astype(np.float64)
        arrays[f"{prefix}_composition"] = composition.astype(np.float64)
        arrays[f"{prefix}_gauge_currents"] = currents.astype(np.float64)
        arrays[f"{prefix}_component_density"] = density.astype(np.float64)
        return weights, density, composition, currents

    core_weights, core_density, core_composition, core_currents = block(core_r, core_w, core_u, core_du, core_c, core_dc, "core")
    wall_weights, wall_density, wall_composition, wall_currents = block(wall_r, wall_w, wall_u, wall_du, wall_c, wall_dc, "wall")
    component = np.sum(core_weights[:, None] * core_density, axis=0) + np.sum(wall_weights[:, None] * wall_density, axis=0)
    population = float(np.dot(core_weights, core_c**2) + np.dot(wall_weights, wall_c**2))
    gradient = float(component[0] + component[1] + component[2] + component[6])
    energy = float(np.sum(component))
    mu_star = constants()["mu_star"]
    return {
        "R": R,
        "population": population,
        "components": component.tolist(),
        "gradient_energy": gradient,
        "energy": energy,
        "excess_energy": energy - mu_star * population,
        "energy_per_population": energy / population,
        "dilation": {"volume_factor": volume_factor, "population": population, "components": component.tolist(), "gradient_energy": gradient, "energy": energy, "excess_energy": energy - mu_star * population},
        "max_composition": float(max(np.max(np.abs(core_composition), initial=0.0), np.max(np.abs(wall_composition), initial=0.0))),
        "max_current": float(max(np.max(np.abs(core_currents), initial=0.0), np.max(np.abs(wall_currents), initial=0.0))),
    }


def exact_checks(checks: dict[str, Any], exact_expressions: dict[str, str]) -> None:
    x, y, rho, lr, lc, eta = sp.symbols("x y rho lambda_rho lambda_C eta", positive=True)
    alpha = eta**2 / lr - lc / 2
    w = lr / 4 * (x - rho) ** 2 + eta * (x - rho) * y + lc / 2 * y**2
    square = sp.expand(w + alpha * y**2 - lr / 4 * (x - rho + 2 * eta * y / lr) ** 2)
    chemical = rho * (sp.sqrt(lr * lc / 2) - eta)
    coexistence = sp.simplify(w - chemical*y
                             - (sp.sqrt(lr)*(x-rho)/2 + sp.sqrt(lc/2)*y)**2
                             - (eta-sp.sqrt(lr*lc/2))*x*y)
    exact_expressions["pointwise_square"] = str(sp.factor(square))
    exact_expressions["coexistence_square"] = str(sp.factor(coexistence))
    check(checks, "pointwise_square_identity", square == 0, expression=str(sp.factor(square)))
    check(checks, "coexistence_square_identity", coexistence == 0, expression=str(sp.factor(coexistence)))

    threshold = sp.Rational(3, 5)
    control_results: dict[str, bool] = {}
    for control in (sp.Integer(2), sp.Integer(4)):
        alpha_control = sp.Integer(1) - control / 2
        low_ok = bool(alpha_control <= 0)
        high = sp.Rational(1, 4) * sp.Rational(6, 5) ** 2 - sp.Rational(6, 5) * y + control / 2 * y**2
        vertex = sp.solve(sp.diff(high, y), y)[0]
        high_at_threshold = sp.factor(high.subs(y, threshold))
        high_monotone = bool(vertex <= threshold)
        control_results[str(int(control))] = low_ok and high_monotone and bool(high_at_threshold >= 0)
        exact_expressions[f"control_{int(control)}_piecewise"] = f"y<=3/5: {sp.factor(-alpha_control*y**2)}; y>=3/5: {sp.factor(high)}"
        check(checks, f"control_lambda_C_{int(control)}", control_results[str(int(control))], low_coefficient=str(-alpha_control), vertex=str(vertex), value_at_threshold=str(high_at_threshold))

    rr = sp.symbols("r", nonnegative=True)
    talenti = (1 + rr**2) ** sp.Rational(-1, 2)
    norm_integral = sp.simplify(4 * sp.pi * sp.integrate(rr**2 * talenti**6, (rr, 0, sp.oo)))
    gradient_integral = sp.simplify(4 * sp.pi * sp.integrate(rr**2 * sp.diff(talenti, rr) ** 2, (rr, 0, sp.oo)))
    exact_expressions["talenti_norm_integral"] = str(norm_integral)
    exact_expressions["talenti_gradient_integral"] = str(gradient_integral)
    check(checks, "talenti_norm_integral", norm_integral == sp.pi**2 / 4, actual=str(norm_integral), expected=str(sp.pi**2 / 4))
    check(checks, "talenti_gradient_integral", gradient_integral == 3 * sp.pi**2 / 4, actual=str(gradient_integral), expected=str(3 * sp.pi**2 / 4))


def compare_scalar(checks: dict[str, Any], name: str, actual: float, reference: Any) -> None:
    try:
        ref = float(reference)
        err = abs(float(actual) - ref) / max(1.0, abs(ref))
        check(checks, name, math.isfinite(err) and err <= EPSILON, actual=float(actual), reference=ref, normalized_error=err)
    except Exception as exc:
        check(checks, name, False, actual=actual, reference=reference, error=f"{type(exc).__name__}: {exc}")


def compare_row(checks: dict[str, Any], prefix: str, actual: dict[str, Any], reference: dict[str, Any], dilation: bool = False) -> None:
    fields = ("population", "gradient_energy", "energy", "excess_energy")
    for field in fields:
        compare_scalar(checks, f"{prefix}_{field}", actual[field], reference.get(field))
    for index, name in enumerate(COMPONENT_NAMES):
        compare_scalar(checks, f"{prefix}_{name}", actual["components"][index], reference.get("components", [])[index])
    if not dilation:
        compare_scalar(checks, f"{prefix}_energy_per_population", actual["energy_per_population"], reference.get("energy_per_population"))


def exact_trial(R: float) -> tuple[float, float, float]:
    c = constants()
    A = KX * RHO0 + KCX * c["s_star"]
    D = LAMBDA_RHO * RHO0**2 / 2.0 + ETA * RHO0 * c["s_star"]
    N = 4.0 * math.pi * c["s_star"] * (R**3 / 3.0 + H * R**2 / 3.0 + H**2 * R / 6.0 + H**3 / 30.0)
    surface = 4.0 * math.pi * ((A / (2.0 * H) + D * H / 30.0) * R**2 + (A / 2.0 + D * H**2 / 30.0) * R + A * H / 6.0 + D * H**3 / 105.0)
    return N, surface, c["mu_star"] * N + surface


def load_primary(path: Path) -> dict[str, Any]:
    result_path = path / "result.json"
    if not result_path.is_file():
        raise FileNotFoundError(result_path)
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError("primary result is not an object")
    return result


def write_json_exclusive(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    checks: dict[str, Any] = {}
    arrays: dict[str, np.ndarray] = {}
    rows: list[dict[str, Any]] = []
    exact_expressions: dict[str, str] = {}
    c = constants()
    manifest_sha = ""
    failures: list[str] = []
    try:
        manifest_sha = verify_manifest(args.manifest.resolve(), checks)
        primary = load_primary(args.input.resolve())
        check(checks, "primary_schema", primary.get("schema") == PRIMARY_SCHEMA, actual=primary.get("schema"))
        check(checks, "primary_complete_flag", primary.get("complete_physical_matter_formation") is False, actual=primary.get("complete_physical_matter_formation"))
        check(checks, "primary_manifest_identity", primary.get("manifest_sha256") == manifest_sha, expected=manifest_sha, actual=primary.get("manifest_sha256"))
        for name, value in c.items():
            if isinstance(primary.get("constants"), dict):
                compare_scalar(checks, f"constant_{name}", value, primary["constants"].get(name))
        exact_checks(checks, exact_expressions)
        primary_rows = primary.get("rows")
        check(checks, "primary_rows_shape", isinstance(primary_rows, list) and len(primary_rows) == len(RADII), actual=len(primary_rows) if isinstance(primary_rows, list) else None)
        for row_index, R in enumerate(RADII):
            measured = {(v, q): integrate_witness(R, v, q, arrays)
                        for v in VOLUME_FACTORS for q in QUADRATURES}
            base = measured[(1.0, 8)]
            base["dilations"] = [measured[(v, 8)]["dilation"] for v in VOLUME_FACTORS[1:]]
            rows.append({key: base[key] for key in ("R", "population", "components", "gradient_energy", "energy", "excess_energy", "energy_per_population", "dilations")})
            exact_population, exact_surface, exact_energy = exact_trial(R)
            compare_scalar(checks, f"trial_R{int(R)}_population_identity", base["population"], exact_population)
            compare_scalar(checks, f"trial_R{int(R)}_surface_identity", base["excess_energy"], exact_surface)
            compare_scalar(checks, f"trial_R{int(R)}_energy_identity", base["energy"], exact_energy)
            reference = primary_rows[row_index]
            check(checks, f"row_R{int(R)}_identity", reference.get("R") == R, actual=reference.get("R"), expected=R)
            for volume_index, volume_factor in enumerate(VOLUME_FACTORS):
                expected = reference if volume_index == 0 else reference["dilations"][volume_index - 1]
                for order in QUADRATURES:
                    actual = measured[(volume_factor, order)]
                    prefix = f"R{int(R)}_v{int(volume_factor)}_q{order}"
                    if volume_index:
                        compare_scalar(checks, f"{prefix}_volume_factor", volume_factor, expected["volume_factor"])
                    compare_row(checks, prefix, actual, expected, dilation=bool(volume_index))
                    check(checks, f"{prefix}_composition_zero", actual["max_composition"] <= ZERO_EPSILON, maximum=actual["max_composition"])
                    check(checks, f"{prefix}_gauge_current_zero", actual["max_current"] <= ZERO_EPSILON, maximum=actual["max_current"])
                    for unused_index in (1, 2, 4, 5):
                        value = actual["components"][unused_index]
                        check(checks, f"{prefix}_{COMPONENT_NAMES[unused_index]}_zero", abs(value) <= ZERO_EPSILON, value=value)
                    if volume_index:
                        undilated = measured[(1.0, order)]
                        expected_energy = volume_factor*undilated["energy"] - (volume_factor-volume_factor**(1/3))*undilated["gradient_energy"]
                        compare_scalar(checks, f"{prefix}_dilation_identity", actual["energy"], expected_energy)
                compare_row(checks, f"quadrature_R{int(R)}_v{int(volume_factor)}", measured[(volume_factor, 4)], measured[(volume_factor, 8)])
            if R in (16.0, 64.0):
                check(checks, f"negative_binding_R{int(R)}", base["energy"] < 0.0, energy=base["energy"])
        all_finite = finite(rows) and finite(c) and all(np.all(np.isfinite(value)) for value in arrays.values())
        check(checks, "finite_scientific_payload", all_finite)
    except Exception as exc:
        failures.append(f"{type(exc).__name__}: {exc}")
        check(checks, "execution", False, error=failures[-1])
    numeric_pass = not failures and all(bool(item.get("pass")) for item in checks.values())
    if not numeric_pass and not failures:
        failures.append("one or more retained checks failed")
    result = {
        "schema": SCHEMA,
        "verdict": "PASS" if numeric_pass else INCONCLUSIVE,
        "numeric_pass": bool(numeric_pass),
        "checks": checks,
        "rows": rows,
        "constants": c,
        "component_names": list(COMPONENT_NAMES),
        "exact_expressions": exact_expressions,
        "manifest_sha256": manifest_sha,
        "complete_physical_matter_formation": False,
        "failures": failures,
    }
    arrays_path = output / "arrays.npz"
    if not arrays_path.exists():
        np.savez(arrays_path, **arrays)
    result["raw_arrays_sha256"] = raw_sha256(arrays_path)
    write_json_exclusive(output / "verification.json", result)
    print(json.dumps({"verdict": result["verdict"], "numeric_pass": result["numeric_pass"],
                      "rows": len(rows), "checks": len(checks), "failures": failures,
                      "complete_physical_matter_formation": False}, allow_nan=False))
    return 0 if numeric_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
