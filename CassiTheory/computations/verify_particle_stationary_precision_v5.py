#!/usr/bin/env python3
"""Independently verify the frozen v5 precision continuation campaign."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import verify_particle_stationary_precision_v3 as verifier


ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "runs" / "20260902_particle_stationary_precision_v5"
PREFLIGHT_PATH = RUN_DIR / "preflight_verification.json"
RESULTS_PATH = RUN_DIR / "results.json"
VERIFICATION_PATH = RUN_DIR / "verification.json"
MANIFEST_PATH = ROOT / "computations" / "particle_stationary_precision_v5_manifest.json"
AUXILIARY_DIAGNOSTICS = {
    "objective_raw_gradient_rms",
    "objective_raw_gradient_max",
}
ORIGINAL_COMPARE_TREE = verifier.independent.compare_tree
ORIGINAL_VERIFY_EMBEDDED_SOURCE = verifier.verify_embedded_source


def compare_tree_v5(
    out: list[dict[str, Any]], path: str, actual: Any, expected: Any
) -> None:
    """Compare endpoint diagnostics with the frozen auxiliary receipt schema."""
    if (
        path.startswith("blocks[")
        and path.endswith("].diagnostics")
        and isinstance(actual, dict)
        and isinstance(expected, dict)
    ):
        expected_keys = set(expected) | AUXILIARY_DIAGNOSTICS
        actual_keys = set(actual)
        if actual_keys != expected_keys:
            verifier.mismatch(
                out,
                f"{path}.keys",
                sorted(expected_keys),
                sorted(actual_keys),
                "exact",
            )
            return
        for name, expected_value in expected.items():
            ORIGINAL_COMPARE_TREE(
                out, f"{path}.{name}", actual[name], expected_value
            )
        for name in sorted(AUXILIARY_DIAGNOSTICS):
            value = actual[name]
            if (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not math.isfinite(float(value))
                or float(value) < 0.0
            ):
                verifier.mismatch(
                    out,
                    f"{path}.{name}",
                    "finite nonnegative number",
                    value,
                    "schema",
                )
        return
    ORIGINAL_COMPARE_TREE(out, path, actual, expected)


def verify_embedded_source_v5(
    out: list[dict[str, Any]], reported: Any, fresh: Mapping[str, Any]
) -> None:
    """Verify the primary's direct fixed-shell source receipt."""
    ORIGINAL_VERIFY_EMBEDDED_SOURCE(out, reported, fresh)
    if not isinstance(reported, dict):
        return
    shell = reported.get("shell")
    expected_shell_keys = {"residuals", "maximum", "tolerance", "pass"}
    if not isinstance(shell, dict) or set(shell) != expected_shell_keys:
        verifier.mismatch(
            out,
            "results.source.shell.keys",
            sorted(expected_shell_keys),
            sorted(shell) if isinstance(shell, dict) else shell,
            "exact",
        )
        return
    residuals = shell["residuals"]
    expected_residual_keys = {"psi_real", "psi_imag", "h", "a", "c"}
    if not isinstance(residuals, dict) or set(residuals) != expected_residual_keys:
        verifier.mismatch(
            out,
            "results.source.shell.residuals.keys",
            sorted(expected_residual_keys),
            sorted(residuals) if isinstance(residuals, dict) else residuals,
            "exact",
        )
        return
    residual_values: list[float] = []
    for name in sorted(expected_residual_keys):
        value = residuals[name]
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(float(value))
            or float(value) < 0.0
        ):
            verifier.mismatch(
                out,
                f"results.source.shell.residuals.{name}",
                "finite nonnegative number",
                value,
                "schema",
            )
        else:
            residual_values.append(float(value))
    maximum = shell["maximum"]
    if (
        not isinstance(maximum, (int, float))
        or isinstance(maximum, bool)
        or not math.isfinite(float(maximum))
        or float(maximum) < 0.0
    ):
        verifier.mismatch(
            out,
            "results.source.shell.maximum",
            "finite nonnegative number",
            maximum,
            "schema",
        )
    else:
        if len(residual_values) == len(expected_residual_keys):
            verifier.compare_scalar(
                out,
                "results.source.shell.maximum_from_components",
                maximum,
                max(residual_values),
            )
        diagnostics = fresh.get("diagnostics")
        independent_maximum = (
            diagnostics.get("boundary_residual")
            if isinstance(diagnostics, dict)
            else None
        )
        if isinstance(independent_maximum, (int, float)) and not isinstance(
            independent_maximum, bool
        ):
            verifier.compare_scalar(
                out,
                "results.source.shell.maximum_independent",
                maximum,
                float(independent_maximum),
            )
        else:
            verifier.mismatch(
                out,
                "results.source.shell.maximum_independent",
                "independently recomputed boundary residual",
                independent_maximum,
                "schema",
            )
    if shell["tolerance"] != 1.0e-12:
        verifier.mismatch(
            out,
            "results.source.shell.tolerance",
            1.0e-12,
            shell["tolerance"],
            "exact",
        )
    if shell["pass"] is not True or not isinstance(maximum, (int, float)) or float(maximum) > 1.0e-12:
        verifier.mismatch(
            out,
            "results.source.shell.pass",
            True,
            shell["pass"],
            "gate",
        )


def configure_verifier() -> None:
    verifier.RUN_DIR = RUN_DIR
    verifier.PREFLIGHT_PATH = PREFLIGHT_PATH
    verifier.RESULTS_PATH = RESULTS_PATH
    verifier.VERIFICATION_PATH = VERIFICATION_PATH
    verifier.MANIFEST_PATH = MANIFEST_PATH
    verifier.independent.compare_tree = compare_tree_v5
    verifier.verify_embedded_source = verify_embedded_source_v5


def main(argv: Sequence[str] | None = None) -> int:
    configure_verifier()
    return verifier.main(argv)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(
            json.dumps(
                {
                    "pass": False,
                    "verdict": "INCONCLUSIVE—EXECUTION OR VERIFICATION",
                    "error": f"{type(error).__name__}: {error}",
                },
                sort_keys=True,
            ),
            flush=True,
        )
        raise SystemExit(1)
