#!/usr/bin/env python3
"""Verify the frozen moving-multigroup radiation schedule."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np
import sympy as sp
from scipy.integrate import quad

from moving_multigroup_radiation import (
    advance_isotropic_doppler,
    compact_energy_primitive,
    compact_photon_primitive,
    compact_spectrum,
    doppler_factor,
    exact_extensive_group_energy,
    frequency_edge_four_flux,
    group_frequency_rhs,
    observer_group_intensity,
    observer_specific_intensity,
    require_third_moment_closure,
    validate_frequency_edges,
    validate_group_energy,
    validate_shared_interfaces,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "cassi-moving-multigroup-radiation-verification-v1"
DEFAULT_OUTPUT = ROOT / "runs" / "moving_multigroup_radiation" / "verification.json"
SOURCE_PATHS = (
    Path("computations/moving-multigroup-radiation-prereg.md"),
    Path("turbulence/moving-multigroup-radiation-closure.md"),
    Path("computations/moving_multigroup_radiation.py"),
    Path("computations/verify_moving_multigroup_radiation.py"),
)
TOL = 2.0e-13


@dataclass
class CheckBook:
    checks: dict[str, dict[str, Any]] = field(default_factory=dict)

    def add(self, name: str, passed: bool, **evidence: Any) -> None:
        if name in self.checks:
            raise KeyError(f"duplicate check name: {name}")
        self.checks[name] = {"passed": bool(passed), "evidence": json_value(evidence)}

    def exact(self, name: str, expression: sp.Expr | sp.MatrixBase) -> None:
        simplified = sp.simplify(expression)
        if isinstance(simplified, sp.MatrixBase):
            passed = all(sp.simplify(value) == 0 for value in simplified)
        else:
            passed = simplified == 0
        self.add(name, passed, simplified=str(simplified))

    def close(self, name: str, actual: Any, expected: Any, tolerance: float = TOL) -> None:
        left = np.asarray(actual, dtype=np.float64)
        right = np.asarray(expected, dtype=np.float64)
        error = float(np.linalg.norm(left - right))
        scale = max(1.0, float(np.linalg.norm(right)))
        normalized = error / scale
        self.add(
            name,
            math.isfinite(normalized) and normalized <= tolerance,
            actual=left,
            expected=right,
            normalized_error=normalized,
            tolerance=tolerance,
        )

    def rejected(self, name: str, operation: Callable[[], Any]) -> None:
        error: str | None = None
        try:
            operation()
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        self.add(name, error is not None, error=error)

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(row["passed"] for row in self.checks.values())

    @property
    def failed(self) -> list[str]:
        return [name for name, row in self.checks.items() if not row["passed"]]


def json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    if isinstance(value, np.ndarray):
        return json_value(value.tolist())
    if isinstance(value, np.generic):
        return json_value(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("receipt contains a nonfinite value")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prepare_evidence(output: Path) -> tuple[Path, Path, dict[str, dict[str, Any]]]:
    target = output.resolve()
    if ROOT != target and ROOT not in target.parents:
        raise ValueError("output must remain inside the CassiTheory root")
    manifest_path = target.with_name("input_manifest.json")
    snapshot_root = target.parent / "source_snapshots"
    for path in (target, manifest_path, snapshot_root):
        if path.exists():
            raise FileExistsError(f"refusing existing evidence path: {path}")
    target.parent.mkdir(parents=True, exist_ok=True)
    snapshot_root.mkdir()
    manifest: dict[str, dict[str, Any]] = {}
    for relative in SOURCE_PATHS:
        source = ROOT / relative
        destination = snapshot_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        manifest[relative.as_posix()] = {
            "path": relative.as_posix(),
            "snapshot": destination.relative_to(ROOT).as_posix(),
            "bytes": source.stat().st_size,
            "sha256": sha256(source),
            "snapshot_sha256": sha256(destination),
        }
    manifest_path.write_text(
        json.dumps(
            {"schema": SCHEMA, "sources": manifest},
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return target, manifest_path, manifest


def symbolic_controls(book: CheckBook) -> dict[str, str]:
    phi0, phi1, phi2, phi3, phi4 = sp.symbols("Phi_0:5", real=True)
    contributions = sp.Matrix(
        [-(phi1 - phi0), -(phi2 - phi1), -(phi3 - phi2), -(phi4 - phi3)]
    )
    book.exact("symbolic.internal_edge_telescoping", sum(contributions) - (phi0 - phi4))

    t, nu, hubble = sp.symbols("t nu H", real=True)
    initial = sp.Function("E_0")
    scale = sp.exp(hubble * t)
    spectrum = scale ** -3 * initial(scale * nu)
    residual = sp.diff(spectrum, t) + 3 * hubble * spectrum - hubble * nu * sp.diff(spectrum, nu)
    book.exact("symbolic.isotropic_spectral_solution", residual)

    a = sp.symbols("a", positive=True)
    energy0, photons0 = sp.symbols("E_0 N_0", positive=True)
    book.exact("symbolic.energy_density_scaling", a**4 * (energy0 / a**4) - energy0)
    book.exact("symbolic.photon_density_scaling", a**3 * (photons0 / a**3) - photons0)

    lo, hi = sp.symbols("nu_l nu_h", positive=True)
    primitive = lambda x: x**3 / 3 - x**4 / 2 + x**5 / 5
    shape = lambda x: x**2 * (1 - x) ** 2
    group = sp.exp(-hubble * t) * (primitive(scale * hi) - primitive(scale * lo))
    group0 = primitive(hi) - primitive(lo)
    derivative = sp.diff(group, t).subs(t, 0)
    expected = -hubble * group0 + hubble * (hi * shape(hi) - lo * shape(lo))
    book.exact("symbolic.group_extensive_derivative", derivative - expected)

    factor, rest_intensity, rest_frequency = sp.symbols("D I_0 nu_0", positive=True)
    observer_intensity = factor**3 * rest_intensity
    observer_frequency = factor * rest_frequency
    book.exact(
        "symbolic.intensity_invariant",
        observer_intensity / observer_frequency**3 - rest_intensity / rest_frequency**3,
    )

    gradient = sp.zeros(4, 4)
    third = sp.MutableDenseNDimArray.zeros(4, 4, 4)
    zero_flux = []
    for alpha in range(4):
        zero_flux.append(
            sum(third[alpha, beta, gamma] * gradient[beta, gamma] for beta in range(4) for gamma in range(4))
        )
    book.exact("symbolic.uniform_boost_zero_operator", sp.Matrix(zero_flux))

    return {
        "isotropic_solution": "a**(-3)*E_0(a*nu)",
        "energy_scaling": "a**(-4)",
        "photon_scaling": "a**(-3)",
        "edge_flux": "-nu*M^(alpha beta gamma)*grad_gamma(U_beta/c)",
    }


def four_momentum_controls(book: CheckBook) -> dict[str, Any]:
    closed = np.asarray(
        [
            [0.0, 0.0, 0.0, 0.0],
            [0.3, -0.2, 0.1, 0.4],
            [-0.5, 0.7, -0.1, 0.2],
            [0.9, 0.2, 0.6, -0.3],
            [0.0, 0.0, 0.0, 0.0],
        ],
        dtype=np.float64,
    )
    closed_rhs = group_frequency_rhs(closed)
    book.close("four_momentum.closed_internal_edges", np.sum(closed_rhs, axis=0), np.zeros(4))

    opened = closed.copy()
    opened[0] = np.asarray([0.1, -0.4, 0.2, 0.7])
    opened[-1] = np.asarray([-0.6, 0.3, 0.8, -0.2])
    open_rhs = group_frequency_rhs(opened)
    expected = opened[0] - opened[-1]
    book.close("four_momentum.outer_edge_ledger", np.sum(open_rhs, axis=0), expected)

    edges = np.asarray([0.0, 0.25, 0.7, 1.0])
    moments = np.arange(edges.size * 4 * 4 * 4, dtype=np.float64).reshape(edges.size, 4, 4, 4) / 97.0
    gradient = np.asarray(
        [
            [0.0, 0.1, -0.2, 0.0],
            [0.3, -0.1, 0.0, 0.2],
            [0.0, 0.4, 0.2, -0.1],
            [-0.2, 0.0, 0.1, 0.3],
        ]
    )
    flux = frequency_edge_four_flux(edges, moments, gradient)
    direct = np.empty_like(flux)
    for edge in range(edges.size):
        for alpha in range(4):
            direct[edge, alpha] = -edges[edge] * sum(
                moments[edge, alpha, beta, gamma] * gradient[beta, gamma]
                for beta in range(4)
                for gamma in range(4)
            )
    book.close("four_momentum.tensor_contraction", flux, direct)

    zero = frequency_edge_four_flux(edges, moments, np.zeros((4, 4)))
    book.close("four_momentum.zero_gradient", zero, np.zeros_like(zero))

    validate_shared_interfaces(closed[1:-1], closed[1:-1])
    book.add("four_momentum.shared_interface_identity", True, interfaces=3)

    return {
        "closed_sum": np.sum(closed_rhs, axis=0),
        "open_sum": np.sum(open_rhs, axis=0),
        "expected_outer_ledger": expected,
        "maximum_tensor_contraction_error": float(np.max(np.abs(flux - direct))),
    }


def doppler_controls(book: CheckBook) -> dict[str, Any]:
    results: dict[str, Any] = {}
    final_time = 0.25
    for name, rate in (("expansion", 0.2), ("compression", -0.2)):
        errors: list[float] = []
        minima: list[float] = []
        ledgers: list[float] = []
        means: list[tuple[float, float]] = []
        step_counts: list[int] = []
        for groups in (32, 64, 128, 256):
            edges = np.linspace(0.0, 1.2, groups + 1)
            initial = exact_extensive_group_energy(edges, 1.0)
            advanced = advance_isotropic_doppler(initial, edges, rate, final_time)
            exact = exact_extensive_group_energy(edges, math.exp(rate * final_time))
            errors.append(float(np.sum(np.abs(advanced.energy - exact))))
            minima.append(advanced.minimum_energy)
            ledgers.append(advanced.maximum_ledger_residual)
            centers = 0.5 * (edges[:-1] + edges[1:])
            means.append(
                (
                    float(np.dot(centers, initial) / np.sum(initial)),
                    float(np.dot(centers, advanced.energy) / np.sum(advanced.energy)),
                )
            )
            step_counts.append(advanced.steps)

        direction_ok = all(after < before for before, after in means) if rate > 0.0 else all(
            after > before for before, after in means
        )
        book.add(
            f"doppler.{name}.nonnegative",
            min(minima) >= 0.0,
            minimum_energy=min(minima),
        )
        book.add(
            f"doppler.{name}.frequency_direction",
            direction_ok,
            mean_frequencies=means,
        )
        book.add(
            f"doppler.{name}.ledger",
            max(ledgers) <= TOL,
            maximum_residual=max(ledgers),
            tolerance=TOL,
        )
        book.add(
            f"doppler.{name}.strict_refinement",
            errors[1] < errors[0] and errors[2] < errors[1] and errors[3] < errors[2],
            l1_errors=errors,
        )
        book.add(
            f"doppler.{name}.resolution_reduction",
            errors[-1] <= 0.35 * errors[0],
            coarse_error=errors[0],
            fine_error=errors[-1],
            ratio=errors[-1] / errors[0],
            limit=0.35,
        )
        results[name] = {
            "l1_errors": errors,
            "minimum_energies": minima,
            "maximum_ledger_residuals": ledgers,
            "mean_frequencies": means,
            "step_counts": step_counts,
        }
    return results


def remap_controls(book: CheckBook) -> dict[str, Any]:
    results: dict[str, Any] = {}
    energy0 = float(compact_energy_primitive(1.0))
    photons0 = float(compact_photon_primitive(1.0))
    for scale in (0.8, 1.0, 1.25):
        upper = 1.5 / scale
        energy_density = quad(
            lambda nu: scale**-3 * float(compact_spectrum(scale * nu)),
            0.0,
            upper,
            epsabs=1.0e-14,
            epsrel=1.0e-14,
        )[0]
        photon_density = quad(
            lambda nu: 0.0
            if nu == 0.0
            else scale**-3 * float(compact_spectrum(scale * nu)) / nu,
            0.0,
            upper,
            epsabs=1.0e-14,
            epsrel=1.0e-14,
        )[0]
        book.close(f"remap.energy_scaling_a{scale}", energy_density, energy0 / scale**4)
        book.close(f"remap.photon_scaling_a{scale}", photon_density, photons0 / scale**3)
        results[str(scale)] = {
            "energy_density": energy_density,
            "expected_energy_density": energy0 / scale**4,
            "photon_density": photon_density,
            "expected_photon_density": photons0 / scale**3,
        }

    edges = np.linspace(0.0, 1.2, 41)
    identity = exact_extensive_group_energy(edges, 1.0)
    direct = np.diff(np.asarray(compact_energy_primitive(edges), dtype=np.float64))
    book.close("remap.identity_groups", identity, direct)
    return results


def lorentz_controls(book: CheckBook) -> dict[str, Any]:
    edges = np.asarray([0.0, 0.2, 0.5, 0.8, 1.4])
    maximum_group_error = 0.0
    maximum_invariant_error = 0.0
    maximum_frequency_roundtrip = 0.0
    maximum_intensity_roundtrip = 0.0
    cases = 0

    for beta in (0.0, 0.03, 0.2):
        for cosine in (-1.0, -0.3, 0.0, 0.8, 1.0):
            factor = doppler_factor(beta, cosine)
            exact = observer_group_intensity(edges, beta, cosine)
            direct = np.asarray(
                [
                    quad(
                        lambda nu: observer_specific_intensity(nu, beta, cosine),
                        edges[index],
                        edges[index + 1],
                        epsabs=2.0e-14,
                        epsrel=2.0e-14,
                        points=[factor] if edges[index] < factor < edges[index + 1] else None,
                    )[0]
                    for index in range(edges.size - 1)
                ]
            )
            maximum_group_error = max(
                maximum_group_error,
                float(np.linalg.norm(direct - exact)) / max(1.0, float(np.linalg.norm(exact))),
            )

            for rest_frequency in (0.1, 0.3, 0.5, 0.7, 0.9):
                rest_intensity = float(compact_spectrum(rest_frequency))
                observer_frequency = factor * rest_frequency
                observer_intensity = observer_specific_intensity(observer_frequency, beta, cosine)
                invariant_error = abs(
                    observer_intensity / observer_frequency**3
                    - rest_intensity / rest_frequency**3
                )
                maximum_invariant_error = max(maximum_invariant_error, invariant_error)
                recovered_frequency = observer_frequency / factor
                recovered_intensity = observer_intensity / factor**3
                maximum_frequency_roundtrip = max(
                    maximum_frequency_roundtrip, abs(recovered_frequency - rest_frequency)
                )
                maximum_intensity_roundtrip = max(
                    maximum_intensity_roundtrip, abs(recovered_intensity - rest_intensity)
                )
            cases += 1

    book.add(
        "lorentz.observer_group_remap",
        maximum_group_error <= 2.0e-12,
        cases=cases,
        maximum_normalized_error=maximum_group_error,
        tolerance=2.0e-12,
    )
    book.add(
        "lorentz.intensity_invariant",
        maximum_invariant_error <= TOL,
        maximum_error=maximum_invariant_error,
        tolerance=TOL,
    )
    book.add(
        "lorentz.frequency_roundtrip",
        maximum_frequency_roundtrip <= TOL,
        maximum_error=maximum_frequency_roundtrip,
        tolerance=TOL,
    )
    book.add(
        "lorentz.intensity_roundtrip",
        maximum_intensity_roundtrip <= TOL,
        maximum_error=maximum_intensity_roundtrip,
        tolerance=TOL,
    )

    return {
        "cases": cases,
        "maximum_group_error": maximum_group_error,
        "maximum_invariant_error": maximum_invariant_error,
        "maximum_frequency_roundtrip": maximum_frequency_roundtrip,
        "maximum_intensity_roundtrip": maximum_intensity_roundtrip,
    }


def rejection_controls(book: CheckBook) -> dict[str, Any]:
    book.rejected(
        "reject.unordered_edges", lambda: validate_frequency_edges(np.asarray([0.0, 0.5, 0.4]))
    )
    book.rejected(
        "reject.negative_edge", lambda: validate_frequency_edges(np.asarray([-0.1, 0.5, 1.0]))
    )
    book.rejected(
        "reject.nonfinite_energy", lambda: validate_group_energy(np.asarray([1.0, np.nan]), 2)
    )
    book.rejected(
        "reject.negative_energy", lambda: validate_group_energy(np.asarray([1.0, -0.1]), 2)
    )
    book.rejected("reject.superluminal_beta", lambda: doppler_factor(1.0, 0.0))
    book.rejected("reject.missing_third_moment", lambda: require_third_moment_closure(None))
    book.rejected(
        "reject.inconsistent_shared_edge",
        lambda: validate_shared_interfaces(np.asarray([[1.0, 2.0]]), np.asarray([[1.0, 2.1]])),
    )
    book.rejected(
        "reject.malformed_third_moment",
        lambda: frequency_edge_four_flux(
            np.asarray([0.0, 1.0]), np.zeros((2, 4, 4)), np.zeros((4, 4))
        ),
    )
    return {"cases": 8}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    try:
        target, manifest_path, sources = prepare_evidence(output)
    except Exception as exc:
        print(f"EVIDENCE PREREQUISITE FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    book = CheckBook()
    results: dict[str, Any] = {}
    error: str | None = None
    try:
        results["symbolic"] = symbolic_controls(book)
        results["four_momentum"] = four_momentum_controls(book)
        results["doppler"] = doppler_controls(book)
        results["remap"] = remap_controls(book)
        results["lorentz"] = lorentz_controls(book)
        results["rejections"] = rejection_controls(book)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        book.add("verification.completed_without_exception", False, error=error)

    passed_count = sum(row["passed"] for row in book.checks.values())
    total_count = len(book.checks)
    status = "PASS" if error is None and book.passed else "FAIL"
    receipt = {
        "schema": SCHEMA,
        "status": status,
        "scientific_classification": (
            "SUPPORTS-conditional moving multigroup radiation closure"
            if status == "PASS"
            else "CONTRADICTS"
        ),
        "checks": {
            "passed": passed_count,
            "total": total_count,
            "failed": book.failed,
            "items": book.checks,
        },
        "results": results,
        "input_manifest": manifest_path.relative_to(ROOT).as_posix(),
        "sources": sources,
        "error": error,
        "scope": {
            "supported": [
                "covariant spectral frequency-flux identity",
                "componentwise conservative group-edge telescoping",
                "homogeneous isotropic Doppler expansion and compression",
                "material-frame energy and photon-number scalings",
                "Lorentz spectral invariance and observer-group remapping",
                "first-order nonnegative reference frequency update",
            ],
            "unestablished": [
                "Cassi field to baryonic material map",
                "physical opacity and species data",
                "production spatial angular and spectral convergence",
                "general-relativistic implementation",
                "live CassiCosmos implementation",
            ],
        },
    }
    target.write_text(
        json.dumps(json_value(receipt), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"MOVING MULTIGROUP RADIATION RESULT: {status} "
        f"({passed_count}/{total_count} checks)"
    )
    print(f"receipt: {target.relative_to(ROOT).as_posix()}")
    if book.failed:
        print("failed checks: " + ", ".join(book.failed))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
