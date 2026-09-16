#!/usr/bin/env python3
"""Finite, exact Galerkin recovery diagnostic for the eight-link SU(2) bowtie.

This is deliberately a one-sided finite diagnostic.  It uses the physical
spin-network basis and the exact Haar/CG tensor contractions from the frozen
bowtie verifier, but it is not an interacting-vacuum conditional-recovery
 theorem and it is not continuum evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import platform
import time
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np
from scipy.linalg import eigh

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(__file__).resolve()
BOWTIE = ROOT / "computations" / "verify_yang_mills_bowtie_fibre.py"
ALGEBRA = ROOT / "computations" / "yang_mills_conditional_algebra.py"
REFERENCE = ROOT / "computations" / "verify_yang_mills_exact_block_spectrum.py"
PROTOCOL = ROOT / "computations" / "yang-mills-bowtie-fibre-prereg.md"
RUN_ROOT = ROOT / "runs" / "yang_mills_bowtie_recovery_diagnostic"

CUTOFFS = (1, 2, 3)
COUPLINGS = (0.25, 1.0, 4.0, 16.0)
BLOCK_LINKS = (0, 1, 2, 3)
EXTERIOR_LINKS = (4, 5, 6, 7)
ALL_LINKS = tuple(range(8))
PSD_TOL = 2.0e-9
HERM_TOL = 2.0e-8
RANK_REL_TOL = 1.0e-10

_spec = importlib.util.spec_from_file_location("ym_bowtie_frozen", BOWTIE)
if _spec is None or _spec.loader is None:
    raise ImportError(f"cannot import frozen bowtie verifier: {BOWTIE}")
bt = importlib.util.module_from_spec(_spec)
# The frozen module's postponed annotations still resolve names while
# definitions are created; provide its historical typing namespace without
# touching the frozen source file.
bt.Any = Any
bt.Callable = Callable
bt.Sequence = Sequence
_spec.loader.exec_module(bt)
ym = bt.ym


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def complex_list(value: np.ndarray) -> dict[str, Any]:
    arr = np.asarray(value, dtype=complex)
    return {"real": arr.real.tolist(), "imag": arr.imag.tolist()}


def array_hash(value: np.ndarray) -> str:
    arr = np.ascontiguousarray(np.asarray(value))
    return hashlib.sha256(arr.tobytes()).hexdigest()


def matrix_summary(value: np.ndarray, include_values: bool = False) -> dict[str, Any]:
    arr = np.asarray(value)
    if np.iscomplexobj(arr):
        finite = bool(np.all(np.isfinite(arr.real)) and np.all(np.isfinite(arr.imag)))
        eig = np.linalg.eigvalsh((arr + arr.conj().T) / 2) if arr.ndim == 2 and arr.shape[0] == arr.shape[1] else np.array([])
    else:
        finite = bool(np.all(np.isfinite(arr)))
        eig = np.linalg.eigvalsh((arr + arr.T) / 2) if arr.ndim == 2 and arr.shape[0] == arr.shape[1] else np.array([])
    out: dict[str, Any] = {
        "shape": list(arr.shape),
        "dtype": str(arr.dtype),
        "sha256": array_hash(arr),
        "finite": finite,
    }
    if eig.size:
        out["spectrum"] = [float(v) for v in eig]
        out["min_eigenvalue"] = float(eig[0])
        out["max_eigenvalue"] = float(eig[-1])
    if include_values:
        out["real"] = arr.real.tolist()
        out["imag"] = arr.imag.tolist() if np.iscomplexobj(arr) else None
    return out


def _character_factors(net: Any, plaquette: int, n: int, tag: str, dagger: bool = False) -> dict[int, tuple[Any, Any, bool]]:
    """Exact trace-character factors, with representation label ``n``.

    This is the frozen bowtie ``loop_factors`` construction with the
    representation label made explicit, so n>1 characters are still exact
    CG/Haar contractions rather than products or sampled traces.
    """
    labs = [net.label(f"{tag}l{k}", (n,)) for k in range(4)]
    out: dict[int, tuple[Any, Any, bool]] = {}
    for k, (edge, orientation) in enumerate(bt.PLAQUETTES[plaquette]):
        x, y = labs[k], labs[(k + 1) % 4]
        if orientation > 0:
            out[edge] = (x, y, False != dagger)
        else:
            out[edge] = (y, x, True != dagger)
    return out


def _assemble(
    coefficients: dict[tuple[int, int, int], complex],
    specs: Sequence[tuple[str, Any, bool, int | None, Sequence[int]]],
    integrated: Sequence[int],
    characters: Sequence[tuple[int, int, bool]] = (),
    label: str = "G",
    open_axes: bool = False,
) -> Any:
    """Assemble the frozen network while allowing arbitrary SU(2) characters."""
    net = ym.Network()
    copies: list[tuple[bool, Any]] = []
    opened: list[Any] = []
    for k, (kind, state, conjugated, generator, generator_links) in enumerate(specs):
        if kind == "omega":
            copy = bt.add_bowtie_omega(net, coefficients, f"{label}C{k}")
        elif kind == "combo":
            copy = bt.add_bowtie_omega(net, state, f"{label}C{k}")
        elif kind == "batch":
            link = generator_links[0] if generator is not None and generator_links else None
            copy = bt.add_batch_copy(net, state, f"{label}C{k}", generator, link, conjugated)
            opened.append(copy.r_axis)
            generator = None
        else:
            copy = bt.add_bowtie_copy(net, state, f"{label}C{k}")
        if generator is not None:
            for edge in generator_links:
                copy.add_generator(edge, generator, conjugated)
        copies.append((conjugated, copy))

    loop_factors: dict[int, list[tuple[Any, Any, bool]]] = {}
    for k, (plaquette, n, dagger) in enumerate(characters):
        for edge, factor in _character_factors(net, int(plaquette), int(n), f"{label}P{k}", bool(dagger)).items():
            loop_factors.setdefault(edge, []).append(factor)

    integrated_set = set(integrated)
    for edge in ALL_LINKS:
        factors: list[tuple[Any, Any, bool]] = []
        for conjugated, copy in copies:
            m, n = copy.factors()[edge]
            factors.append((m, n, conjugated))
        factors.extend(loop_factors.get(edge, ()))
        if edge in integrated_set:
            ym.link_integral(net, factors, f"{label}L{edge}")
        else:
            raise ValueError("all links must be integrated in this diagnostic")
    return net.contract(tuple(opened)) if open_axes else complex(net.contract())


def _expectation_matrix(
    coefficients: dict[tuple[int, int, int], complex],
    tests: Sequence[tuple[int, int, int]],
    label: str,
) -> np.ndarray:
    """Compute the Gram matrix in bounded open-axis batches.

    Opening both test axes at once scales the intermediate tensor like the
    square of the physical basis size.  Exactness is unchanged by splitting
    the first axis into small batches, while the peak contraction memory stays
    bounded at the weak-coupling cutoffs.
    """
    n = len(tests)
    if n == 0:
        return np.empty((0, 0), dtype=complex)
    batch_size = n if n <= 5 else 2
    rows: list[np.ndarray] = []
    for start in range(0, n, batch_size):
        left = tuple(tests[start:start + batch_size])
        value = _assemble(
            coefficients,
            [
                ("omega", None, False, None, BLOCK_LINKS),
                ("omega", None, True, None, BLOCK_LINKS),
                ("batch", left, True, None, BLOCK_LINKS),
                ("batch", tests, False, None, BLOCK_LINKS),
            ],
            ALL_LINKS,
            label=f"{label}R{start}",
            open_axes=True,
        )
        block = np.asarray(value, dtype=complex)
        expected_shape = (len(left), n)
        if block.shape != expected_shape:
            raise RuntimeError(
                f"unexpected batched Gram shape {block.shape}; "
                f"expected {expected_shape}"
            )
        rows.append(block)
    return np.vstack(rows)


def _expectation_vector(coefficients: dict[tuple[int, int, int], complex], tests: Sequence[tuple[int, int, int]], characters: Sequence[tuple[int, int, bool]], label: str) -> np.ndarray:
    value = _assemble(
        coefficients,
        [
            ("omega", None, False, None, BLOCK_LINKS),
            ("omega", None, True, None, BLOCK_LINKS),
            ("batch", tests, False, None, BLOCK_LINKS),
        ],
        ALL_LINKS,
        characters=characters,
        label=label,
        open_axes=True,
    )
    return np.asarray(value, dtype=complex)


def _expectation_scalar(coefficients: dict[tuple[int, int, int], complex], characters: Sequence[tuple[int, int, bool]], label: str) -> complex:
    return _assemble(
        coefficients,
        [("omega", None, False, None, BLOCK_LINKS), ("omega", None, True, None, BLOCK_LINKS)],
        ALL_LINKS,
        characters=characters,
        label=label,
    )


def _character_gramian(coefficients: dict[tuple[int, int, int], complex], characters: Sequence[tuple[int, int]], label: str) -> tuple[float, np.ndarray, np.ndarray, np.ndarray]:
    """Return Z, centered exterior Gram E, means, and uncentered E."""
    z = float(np.real(_expectation_scalar(coefficients, (), f"{label}Z")))
    means = np.array([_expectation_scalar(coefficients, ((p, n, False),), f"{label}M{k}") / z for k, (p, n) in enumerate(characters)], dtype=complex)
    raw = np.empty((len(characters), len(characters)), dtype=complex)
    for i, (pi, ni) in enumerate(characters):
        for j, (pj, nj) in enumerate(characters):
            raw[i, j] = _expectation_scalar(coefficients, ((pi, ni, True), (pj, nj, False)), f"{label}E{i}_{j}") / z
    centered = raw - np.outer(np.conj(means), means)
    return z, centered, means, raw


def _physical_data(coefficients: dict[tuple[int, int, int], complex], tests: Sequence[tuple[int, int, int]], label: str) -> tuple[float, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    z = float(np.real(_expectation_scalar(coefficients, (), f"{label}Z")))
    means = _expectation_vector(coefficients, tests, (), f"{label}M") / z
    raw = _expectation_matrix(coefficients, tests, f"{label}G") / z
    gram = raw - np.outer(np.conj(means), means)
    return z, gram, means, raw, np.asarray(raw - raw.conj().T)


def _residual_diagnostics(gram: np.ndarray, residual: np.ndarray) -> dict[str, Any]:
    gram = np.asarray(gram, dtype=complex)
    residual = np.asarray(residual, dtype=complex)
    herm_g = float(np.max(np.abs(gram - gram.conj().T), initial=0.0))
    herm_r = float(np.max(np.abs(residual - residual.conj().T), initial=0.0))
    gs = np.linalg.eigvalsh((gram + gram.conj().T) / 2)
    rs = np.linalg.eigvalsh((residual + residual.conj().T) / 2)
    scale_g = max(1.0, float(np.max(np.abs(gs), initial=0.0)))
    scale_r = max(1.0, float(np.max(np.abs(rs), initial=0.0)))
    rank = int(np.sum(gs > RANK_REL_TOL * scale_g))
    support = gs > RANK_REL_TOL * scale_g
    gamma = 0.0
    generalized_residual = 0.0
    if np.any(support):
        vg, V = np.linalg.eigh((gram + gram.conj().T) / 2)
        B = V[:, support] / np.sqrt(vg[support])
        reduced = B.conj().T @ ((residual + residual.conj().T) / 2) @ B
        values = np.linalg.eigvalsh(reduced)
        gamma = float(values[0])
        generalized_residual = float(np.linalg.norm(reduced - reduced.conj().T))
    return {
        "hermiticity_residual": max(herm_g, herm_r),
        "gram_hermiticity_residual": herm_g,
        "residual_hermiticity_residual": herm_r,
        "gram_spectrum": [float(v) for v in gs],
        "residual_spectrum": [float(v) for v in rs],
        "gram_rank": rank,
        "residual_rank": int(np.sum(rs > RANK_REL_TOL * scale_r)),
        "gram_min_eigenvalue": float(gs[0]),
        "residual_min_eigenvalue": float(rs[0]),
        "gram_psd": bool(float(gs[0]) >= -PSD_TOL * scale_g),
        "residual_psd": bool(float(rs[0]) >= -PSD_TOL * scale_r),
        "gamma_Gal": max(0.0, gamma) if abs(gamma) <= PSD_TOL * scale_r else gamma,
        "gamma_Gal_raw": gamma,
        "generalized_support_dimension": int(np.sum(support)),
        "condition_number_gram_support": float(np.max(gs[support]) / np.min(gs[support])) if np.any(support) else None,
        "generalized_hermiticity_residual": generalized_residual,
    }


def _pseudoinverse(matrix: np.ndarray) -> tuple[np.ndarray, int, np.ndarray]:
    values, vectors = np.linalg.eigh((matrix + matrix.conj().T) / 2)
    scale = max(1.0, float(np.max(np.abs(values), initial=0.0)))
    keep = values > RANK_REL_TOL * scale
    inverse = (vectors[:, keep] / values[keep]) @ vectors[:, keep].conj().T if np.any(keep) else np.zeros_like(matrix)
    return inverse, int(np.sum(keep)), values


def _character_record(plaquette: int, n: int) -> dict[str, int]:
    return {"plaquette": int(plaquette), "n": int(n), "representation": f"chi_{n}(W_{plaquette})"}


def _validate_psd(matrix: np.ndarray, name: str) -> dict[str, Any]:
    arr = np.asarray(matrix, dtype=complex)
    if not (np.all(np.isfinite(arr.real)) and np.all(np.isfinite(arr.imag))):
        raise FloatingPointError(f"nonfinite matrix: {name}")
    herm = float(np.max(np.abs(arr - arr.conj().T), initial=0.0))
    values = np.linalg.eigvalsh((arr + arr.conj().T) / 2)
    scale = max(1.0, float(np.max(np.abs(values), initial=0.0)))
    if float(values[0]) < -PSD_TOL * scale:
        raise FloatingPointError(f"negative PSD eigenvalue beyond tolerance in {name}")
    keep = values > RANK_REL_TOL * scale
    return {
        "hermiticity_residual": herm,
        "spectrum": [float(v) for v in values],
        "min_eigenvalue": float(values[0]) if values.size else 0.0,
        "rank": int(np.sum(keep)),
        "psd": bool(float(values[0]) >= -PSD_TOL * scale) if values.size else True,
        "condition_number_support": float(np.max(values[keep]) / np.min(values[keep])) if np.any(keep) else None,
    }
def compute_row(J: int, x: float) -> dict[str, Any]:
    space = bt.Space(J)
    extended = bt.Space(J + 1)


    ritz = bt.ritz(space, x, extended)
    tests = tuple(space.states)
    coefficients = dict(zip(tests, ritz["vector"], strict=True))
    z, gram, means, raw_gram, _ = _physical_data(coefficients, tests, f"J{J}x{x:g}P")
    if not np.isfinite(z) or z <= 0:
        raise FloatingPointError("nonpositive or nonfinite interacting vacuum norm")
    gram_diagnostics = _validate_psd(gram, "physical centered Gram")

    covers = {
        "block_A": 1,  # exterior is B, so use W_B characters
        "block_B": 0,  # exterior is A, so use W_A characters
    }
    je_values = (J, 2 * J, 3 * J, 4 * J)
    je_rows: list[dict[str, Any]] = []
    for JE in je_values:
        ext_by_cover = {
            name: tuple((plaquette, n) for n in range(JE + 1))
            for name, plaquette in covers.items()
        }
        matrices: dict[str, dict[str, Any]] = {}
        cache: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]] = {}
        for cover_name in ("block_A", "block_B"):
            ext_chars = ext_by_cover[cover_name]
            _, E, ext_means, _ = _character_gramian(
                coefficients, ext_chars, f"J{J}x{x:g}E{JE}{cover_name}"
            )
            E_diagnostics = _validate_psd(E, f"{cover_name} exterior Gram")
            C = np.empty((len(ext_chars), len(tests)), dtype=complex)
            for alpha, (p, n) in enumerate(ext_chars):
                C[alpha, :] = (
                    _expectation_vector(
                        coefficients,
                        tests,
                        ((p, n, True),),
                        f"J{J}x{x:g}C{JE}{cover_name}{alpha}",
                    )
                    / z
                )
                C[alpha, :] -= np.conj(ext_means[alpha]) * means
            Eplus, erank, _ = _pseudoinverse(E)
            residual = gram - C.conj().T @ Eplus @ C
            if not (np.all(np.isfinite(C)) and np.all(np.isfinite(residual))):
                raise FloatingPointError("nonfinite Galerkin matrix")
            diagnostics = _residual_diagnostics(gram, residual)
            if not diagnostics["gram_psd"] or not diagnostics["residual_psd"]:
                raise FloatingPointError(
                    f"negative PSD eigenvalue beyond tolerance in {cover_name}"
                )
            matrices[cover_name] = {
                "exterior_characters": [
                    _character_record(p, n) for p, n in ext_chars
                ],
                "E": matrix_summary(E),
                "E_diagnostics": E_diagnostics,
                "C": matrix_summary(C),
                "E_pseudoinverse_rank": erank,
                "residual": matrix_summary(residual),
                "diagnostics": diagnostics,
            }
            cache[cover_name] = (E, C, residual, matrices[cover_name])

        # The physical cover is the sum of block residuals, not a projection
        # onto the union of the two exterior character spaces.
        residual_cover = cache["block_A"][2] + cache["block_B"][2]
        residual_cover = 0.5 * (
            residual_cover + residual_cover.conj().T
        )
        cover_diagnostics = _residual_diagnostics(gram, residual_cover)
        if not cover_diagnostics["gram_psd"] or not cover_diagnostics["residual_psd"]:
            raise FloatingPointError("negative PSD eigenvalue in covered residual")
        matrices["covered"] = {
            "construction": "R_block_A + R_block_B",
            "component_residuals": {
                "block_A": matrix_summary(cache["block_A"][2]),
                "block_B": matrix_summary(cache["block_B"][2]),
            },
            "residual": matrix_summary(residual_cover),
            "diagnostics": cover_diagnostics,
        }

        incomplete: dict[str, Any] = {}
        for cover_name in ("block_A", "block_B"):
            ext_chars = tuple(pair for pair in ext_by_cover[cover_name] if pair[1] != 1)
            _, E, ext_means, _ = _character_gramian(coefficients, ext_chars, f"J{J}x{x:g}E{JE}{cover_name}omit1")
            E_diagnostics = _validate_psd(E, f"{cover_name} incomplete exterior Gram")
            C = np.empty((len(ext_chars), len(tests)), dtype=complex)
            for alpha, (p, n) in enumerate(ext_chars):
                C[alpha, :] = _expectation_vector(coefficients, tests, ((p, n, True),), f"J{J}x{x:g}C{JE}{cover_name}omit1{alpha}") / z
                C[alpha, :] -= np.conj(ext_means[alpha]) * means
            Eplus, erank, _ = _pseudoinverse(E)
            residual = gram - C.conj().T @ Eplus @ C
            diag = _residual_diagnostics(gram, residual)
            if not diag["gram_psd"] or not diag["residual_psd"]:
                raise FloatingPointError("negative PSD eigenvalue in incomplete exterior control")
            incomplete[cover_name] = {
                "omitted": _character_record(covers[cover_name], 1),
                "exterior_characters": [_character_record(p, n) for p, n in ext_chars],
                "E": matrix_summary(E),
                "E_diagnostics": E_diagnostics,
                "C": matrix_summary(C),
                "E_pseudoinverse_rank": erank,
                "residual": matrix_summary(residual),
                "diagnostics": diag,
                "classification": "QUALIFICATION_CONTROL_ONLY_NO_NEGATIVE_CLAIM_FROM_GAMMA_CHANGE",
            }

        omitted_controls: dict[str, Any] = {}
        for cover_name, exterior_plaquette in covers.items():
            E, C, _, _ = cache[cover_name]
            target = (0, 1, 0) if cover_name == "block_A" else (1, 0, 0)
            represented = target in space.index
            control: dict[str, Any] = {
                "character": _character_record(exterior_plaquette, 1),
                "physical_state": list(target),
                "represented": represented,
                "classification": "NOT_REPRESENTED",
            }
            if represented:
                idx = space.index[target]
                variance = float(np.real(gram[idx, idx]))
                Eplus, _, _ = _pseudoinverse(E)
                residual = gram - C.conj().T @ Eplus @ C
                residual_norm = float(np.linalg.norm(residual[:, idx]))
                rayleigh = float(np.real(residual[idx, idx]))
                control.update({"variance": variance, "residual_column_norm": residual_norm, "residual_quadratic": rayleigh})
                if variance <= PSD_TOL:
                    control["classification"] = "DEGENERATE_UNTESTABLE_NO_NULL_INFERENCE"
                elif abs(rayleigh) <= PSD_TOL * max(1.0, variance) and residual_norm <= math.sqrt(PSD_TOL) * max(1.0, math.sqrt(variance)):
                    control["classification"] = "REPRESENTED_EXTERIOR_CHARACTER_NULL_CONTROL"
                else:
                    control["classification"] = "REPRESENTED_NOT_NULL_WITHIN_TOLERANCE"
            omitted_controls[cover_name] = control

        perm = np.array([space.index[(s[1], s[0], s[2])] for s in tests], dtype=int)
        EA, CA, RA, _ = cache["block_A"]
        EB, CB, RB, _ = cache["block_B"]
        swap_error = float(np.max(np.abs(RA - RB[np.ix_(perm, perm)]), initial=0.0))
        swap_gamma_error = abs(float(matrices["block_A"]["diagnostics"]["gamma_Gal"]) - float(matrices["block_B"]["diagnostics"]["gamma_Gal"]))
        swap = {"residual_max_abs_error": swap_error, "gamma_abs_error": swap_gamma_error, "pass": bool(swap_error <= HERM_TOL)}

        je_rows.append({
            "J_E": JE,
            "G": matrix_summary(gram),
            "G_diagnostics": gram_diagnostics,
            "G_raw": matrix_summary(raw_gram),
            "vacuum_mean": complex_list(means),
            "vacuum_partition": z,
            "covers": matrices,
            "omitted_character_controls": omitted_controls,
            "incomplete_exterior_controls": incomplete,
            "block_swap_symmetry": swap,
        })


    return {
        "J": J, "x": x, "tests": [list(s) for s in tests],
        "ritz": ritz, "vacuum_partition": z,
        "rows": je_rows,
        "classification": "GALERKIN_RECOVERY_DIAGNOSTIC",
        "scope": "Finite non-Gaussian one-sided Galerkin residuals on the eight-link SU(2) bowtie; a positive Galerkin floor does not prove the exact interacting conditional recovery floor or continuum recovery.",
    }


def default_output() -> Path:
    return RUN_ROOT / f"verification-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{os.getpid()}.json"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None, help="receipt path (must not already exist)")
    parser.add_argument("--J", type=int, choices=CUTOFFS, default=None, help="run one cutoff instead of the frozen schedule")
    parser.add_argument("--x", type=float, choices=COUPLINGS, default=None, help="run one coupling instead of the frozen schedule")
    args = parser.parse_args(argv)
    if (args.J is None) != (args.x is None):
        parser.error("--J and --x must be supplied together")
    output = (args.output or default_output()).resolve()
    if output.exists():
        raise SystemExit(f"refusing to overwrite existing receipt: {output}")
    schedule = ((args.J, args.x),) if args.J is not None else tuple((J, x) for J in CUTOFFS for x in COUPLINGS)
    started = time.perf_counter()
    results = [compute_row(int(J), float(x)) for J, x in schedule]
    receipt = {
        "schema": "cassi.yang-mills-bowtie-recovery-diagnostic.v1",
        "verdict": "PASS",
        "classification": "GALERKIN_RECOVERY_DIAGNOSTIC",
        "scope": "This finite exact-Haar/CG diagnostic is one-sided. It does not represent an exact interacting-vacuum conditional recovery theorem and gives no continuum evidence.",
        "protocol": PROTOCOL.relative_to(ROOT).as_posix(),
        "protocol_sha256": sha256(PROTOCOL),
        "source": SOURCE.relative_to(ROOT).as_posix(),
        "source_sha256": sha256(SOURCE),
        "dependencies": {p.relative_to(ROOT).as_posix(): sha256(p) for p in (BOWTIE, ALGEBRA, REFERENCE)},
        "python": platform.python_version(), "numpy": np.__version__,
        "schedule": [{"J": int(J), "x": float(x)} for J, x in schedule],
        "tolerances": {"psd": PSD_TOL, "hermiticity": HERM_TOL, "rank_relative": RANK_REL_TOL},
        "elapsed_seconds": time.perf_counter() - started,
        "rows": results,
    }
    payload = json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
    except FileExistsError as exc:
        raise SystemExit(f"refusing to overwrite existing receipt: {output}") from exc
    print(json.dumps({"verdict": receipt["verdict"], "classification": receipt["classification"], "rows": len(results), "output": output.as_posix()}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
