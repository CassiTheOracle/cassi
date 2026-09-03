#!/usr/bin/env python3
"""Run the preregistered fixed-budget PA32 Q2 recovery campaign."""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import time
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import torch

import particle_stationary_bvp as source  # pyright: ignore[reportMissingImports]

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "runs" / "20260901_particle_stationary_bvp"
RUN_DIR = ROOT / "runs" / "20260902_particle_stationary_q2_recovery"
RESULTS_PATH = RUN_DIR / "results.json"
PREFLIGHT_PATH = RUN_DIR / "preflight_verification.json"
PREREG_PATH = ROOT / "computations" / "particle_stationary_q2_recovery_prereg.md"
VERIFIER_PATH = ROOT / "computations" / "verify_particle_stationary_q2_recovery.py"
SOURCE_RESULTS_PATH = SOURCE_DIR / "results.json"
SOURCE_VERIFICATION_PATH = SOURCE_DIR / "verification.json"
SOURCE_REPORT_PATH = ROOT / "computations" / "particle-stationary-bvp-report.md"
SOURCE_PREREG_PATH = ROOT / "computations" / "particle-stationary-bvp-pre-registration.md"
SOURCE_PROGRAM_PATH = ROOT / "computations" / "particle_stationary_bvp.py"
SOURCE_VERIFIER_PATH = ROOT / "computations" / "verify_particle_stationary_bvp.py"
AUTHORITY_PATHS = {
    "authority_action": ROOT / "foundations" / "particle-stationary-action-closure.md",
    "authority_core_support": ROOT / "foundations" / "core-trapped-charge-support.md",
    "authority_magnetic_boundary": ROOT
    / "foundations"
    / "nonabelian-magnetic-core-boundary.md",
    "authority_matter_boundary": ROOT / "foundations" / "matter-completion-boundary.md",
}
FIELD_KEYS = ("x", "psi_real", "psi_imag", "h", "a", "c")
EXPECTED_SHAPES = {
    "psi_real": lambda n: (n, n, n, 2),
    "psi_imag": lambda n: (n, n, n, 2),
    "h": lambda n: (n, n, n, 3),
    "a": lambda n: (n, n, n, 3, 3),
    "c": lambda n: (n, n, n),
}
CONTINUATION = {
    "max_iter": 880,
    "max_eval": 1100,
    "history_size": 20,
    "tolerance_grad": 1.0e-10,
    "tolerance_change": 1.0e-12,
    "line_search_fn": "strong_wolfe",
}
ABS_TOL = 1.0e-8
REL_TOL = 1.0e-6
ROUNDTRIP_TOL = 5.0e-12


class ArmFailure(RuntimeError):
    def __init__(self, message: str, optimizer: dict[str, Any] | None = None):
        super().__init__(message)
        self.optimizer = optimizer


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise TypeError(f"Expected a JSON object: {path}")
    return value


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    temporary.replace(path)


def close(actual: float, expected: float) -> bool:
    return abs(actual - expected) <= ABS_TOL + REL_TOL * abs(expected)


def compare_numeric_tree(
    actual: Any, expected: Any, path: str, mismatches: list[str]
) -> None:
    if isinstance(expected, bool):
        if actual is not expected:
            mismatches.append(f"{path}: expected {expected!r}, got {actual!r}")
        return
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        if not isinstance(actual, (int, float)) or isinstance(actual, bool):
            mismatches.append(f"{path}: expected numeric value, got {actual!r}")
        elif not math.isfinite(float(actual)) or not close(float(actual), float(expected)):
            mismatches.append(f"{path}: expected {expected!r}, got {actual!r}")
        return
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            mismatches.append(f"{path}: expected object")
            return
        if set(actual) != set(expected):
            mismatches.append(
                f"{path}.keys: expected {sorted(expected)}, got {sorted(actual)}"
            )
        for key, value in expected.items():
            if key in actual:
                compare_numeric_tree(actual[key], value, f"{path}.{key}", mismatches)
        return
    if actual != expected:
        mismatches.append(f"{path}: expected {expected!r}, got {actual!r}")


def source_artifact_path(source_arm: Mapping[str, Any]) -> Path:
    artifact = source_arm.get("artifact")
    if not isinstance(artifact, str):
        raise ValueError("Source arm has no artifact path")
    candidate = Path(artifact)
    if candidate.is_absolute():
        return candidate
    by_name = SOURCE_DIR / candidate.name
    return by_name if by_name.exists() else ROOT / candidate


def build_manifest(source_receipt: Mapping[str, Any]) -> dict[str, Any]:
    carried = {
        "source_preregistration": (
            SOURCE_PREREG_PATH,
            source_receipt["hashes"]["preregistration"],
        ),
        "source_program": (
            SOURCE_PROGRAM_PATH,
            source_receipt["hashes"]["primary_program"],
        ),
        "source_verifier": (
            SOURCE_VERIFIER_PATH,
            source_receipt["hashes"]["independent_verifier"],
        ),
    }
    required_mismatches: list[str] = []
    immutable: dict[str, str] = {
        "source_results": sha256(SOURCE_RESULTS_PATH),
        "source_verification": sha256(SOURCE_VERIFICATION_PATH),
        "source_report": sha256(SOURCE_REPORT_PATH),
    }
    for name, (path, expected) in carried.items():
        actual = sha256(path)
        immutable[name] = actual
        if actual != expected:
            required_mismatches.append(
                f"{name}: source receipt {expected}, current bytes {actual}"
            )
    source_artifacts: dict[str, str] = {}
    expected_arms = {f"{family}:{basin}" for family in ("P", "D") for basin in source.BASINS}
    if set(source_receipt.get("arms", {})) != expected_arms:
        required_mismatches.append("source arm inventory differs from the frozen P/D set")
    for key in sorted(expected_arms):
        arm = source_receipt.get("arms", {}).get(key)
        if not isinstance(arm, dict) or not arm.get("completed"):
            required_mismatches.append(f"{key}: source arm is missing or incomplete")
            continue
        path = source_artifact_path(arm)
        actual = sha256(path)
        expected = source_receipt["hashes"]["artifacts"].get(path.name)
        source_artifacts[path.name] = actual
        if actual != expected or actual != arm.get("artifact_sha256"):
            required_mismatches.append(f"{key}: source artifact hash mismatch")
    return {
        "immutable_source_snapshot": immutable,
        "source_artifacts": source_artifacts,
        "current_authority": {name: sha256(path) for name, path in AUTHORITY_PATHS.items()},
        "recovery_sources": {
            "preregistration": sha256(PREREG_PATH),
            "primary_program": sha256(Path(__file__).resolve()),
            "independent_verifier": sha256(VERIFIER_PATH),
        },
        "required_mismatches": required_mismatches,
    }


def expected_grid(family: str) -> np.ndarray:
    r_box, n = source.GRIDS[family]
    return np.linspace(-r_box, r_box, n, dtype=np.float64)


def relative_inf(actual: np.ndarray, expected: np.ndarray) -> float:
    numerator = float(np.max(np.abs(actual - expected)))
    denominator = max(float(np.max(np.abs(expected))), 1.0e-12)
    return numerator / denominator


def validate_npz_arrays(
    arrays: Mapping[str, np.ndarray], family: str
) -> list[str]:
    failures: list[str] = []
    r_box, n = source.GRIDS[family]
    if set(arrays) != set(FIELD_KEYS):
        failures.append(f"keys={sorted(arrays)}, expected={sorted(FIELD_KEYS)}")
        return failures
    for name in FIELD_KEYS:
        value = arrays[name]
        if value.dtype != np.float64:
            failures.append(f"{name}: dtype={value.dtype}")
        if not value.flags.c_contiguous:
            failures.append(f"{name}: array is not C-contiguous")
        if not np.all(np.isfinite(value)):
            failures.append(f"{name}: nonfinite value")
    if arrays["x"].shape != (n,):
        failures.append(f"x: shape={arrays['x'].shape}, expected={(n,)}")
    elif not np.array_equal(arrays["x"], expected_grid(family)):
        failures.append(f"x: does not equal the registered {family} grid")
    for name, shape in EXPECTED_SHAPES.items():
        expected = shape(n)
        if arrays[name].shape != expected:
            failures.append(f"{name}: shape={arrays[name].shape}, expected={expected}")
    expected_dx = 2.0 * r_box / (n - 1)
    if arrays["x"].shape == (n,) and not math.isclose(
        float(arrays["x"][1] - arrays["x"][0]), expected_dx, rel_tol=0.0, abs_tol=1.0e-15
    ):
        failures.append("x: spacing mismatch")
    return failures


def load_arrays(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        return {
            name: np.array(archive[name], copy=True, order="K")
            for name in archive.files
        }


def inverse_softplus(carrier: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    raw = torch.zeros_like(carrier)
    interior = mask.bool()
    positive = carrier[interior]
    if not bool(torch.all(positive > 0.0)):
        raise ValueError("carrier is not strictly positive on the interior")
    raw[interior] = positive + torch.log(-torch.expm1(-positive))
    if not bool(torch.all(torch.isfinite(raw))):
        raise ValueError("inverse-softplus raw carrier is nonfinite")
    return raw


def numpy_fields(
    fields: Mapping[str, torch.Tensor], grid: source.Grid
) -> dict[str, np.ndarray]:
    return {
        "x": np.ascontiguousarray(grid.x.detach().cpu().numpy()),
        "psi_real": np.ascontiguousarray(
            fields["psi_real"].detach().cpu().numpy()
        ),
        "psi_imag": np.ascontiguousarray(
            fields["psi_imag"].detach().cpu().numpy()
        ),
        "h": np.ascontiguousarray(fields["h"].detach().cpu().numpy()),
        "a": np.ascontiguousarray(fields["a"].detach().cpu().numpy()),
        "c": np.ascontiguousarray(fields["c"].detach().cpu().numpy()),
    }


def reconstruct_raw(
    arrays: Mapping[str, np.ndarray], grid: source.Grid
) -> tuple[dict[str, torch.nn.Parameter], dict[str, Any]]:
    device = grid.x.device
    tensors = {
        name: torch.tensor(arrays[name], dtype=torch.float64, device=device)
        for name in FIELD_KEYS
        if name != "x"
    }
    raw = {
        "psi_real": torch.nn.Parameter(tensors["psi_real"].clone()),
        "psi_imag": torch.nn.Parameter(tensors["psi_imag"].clone()),
        "h": torch.nn.Parameter(tensors["h"].clone()),
        "a": torch.nn.Parameter(tensors["a"].clone()),
        "w": torch.nn.Parameter(inverse_softplus(tensors["c"], grid.mask)),
    }
    fields = source.physical_fields(raw, grid)
    reconstructed = numpy_fields(fields, grid)
    errors = {
        name: relative_inf(reconstructed[name], arrays[name])
        for name in FIELD_KEYS
        if name != "x"
    }
    return raw, {
        "relative_inf": errors,
        "maximum_relative_inf": max(errors.values()),
        "raw_finite": all(bool(torch.all(torch.isfinite(value))) for value in raw.values()),
    }


def primary_preflight(
    source_receipt: Mapping[str, Any], manifest: Mapping[str, Any], device: torch.device
) -> dict[str, Any]:
    failures = list(manifest["required_mismatches"])
    source_verification = read_json(SOURCE_VERIFICATION_PATH)
    if source_receipt.get("verdict") != "INCONCLUSIVE—NUMERICAL QUALITY":
        failures.append("source receipt verdict is not the registered numerical-quality verdict")
    if not source_verification.get("pass") or source_verification.get("mismatches"):
        failures.append("source independent verification receipt is not clean")
    independent = read_json(PREFLIGHT_PATH)
    if not independent.get("pass"):
        failures.append("independent recovery preflight did not pass")
    if independent.get("manifest") != manifest:
        failures.append("independent preflight manifest differs from the primary manifest")

    arms: dict[str, Any] = {}
    for family in ("P", "D"):
        for basin in source.BASINS:
            key = f"{family}:{basin}"
            arm = source_receipt["arms"][key]
            path = source_artifact_path(arm)
            arrays = load_arrays(path)
            local_failures = validate_npz_arrays(arrays, family)
            try:
                grid = source.make_grid(family, device)
                raw, reconstruction = reconstruct_raw(arrays, grid)
                objective_value, physical_value, gauge_value, _ = source.objective(
                    raw, grid
                )
                values, _ = source.diagnostics(raw, grid)
                comparison_failures: list[str] = []
                compare_numeric_tree(
                    values, arm["diagnostics"], f"{key}.diagnostics", comparison_failures
                )
                if not all(
                    bool(torch.isfinite(value))
                    for value in (objective_value, physical_value, gauge_value)
                ):
                    local_failures.append("objective component is nonfinite")
                if not reconstruction["raw_finite"]:
                    local_failures.append("raw reconstruction is nonfinite")
                if reconstruction["maximum_relative_inf"] > ROUNDTRIP_TOL:
                    local_failures.append("field round-trip tolerance exceeded")
                local_failures.extend(comparison_failures)
            except Exception as error:  # fail closed before optimization
                reconstruction = None
                local_failures.append(f"reconstruction exception: {type(error).__name__}: {error}")
            independent_arm = independent.get("arms", {}).get(key)
            if independent_arm is None:
                local_failures.append("missing independent preflight arm")
            elif independent_arm.get("pass") is not True:
                local_failures.append("independent preflight arm failed")
            arms[key] = {
                "artifact": path.name,
                "artifact_sha256": sha256(path),
                "reconstruction": reconstruction,
                "failures": local_failures,
                "pass": not local_failures,
            }
            failures.extend(f"{key}: {failure}" for failure in local_failures)
    return {"pass": not failures, "failures": failures, "arms": arms}


def gradient_stats(raw: Mapping[str, torch.nn.Parameter]) -> tuple[float, float]:
    values = [parameter.grad.reshape(-1) for parameter in raw.values() if parameter.grad is not None]
    if not values:
        return 0.0, 0.0
    merged = torch.cat(values)
    return float(torch.sqrt(torch.mean(merged**2))), float(torch.max(torch.abs(merged)))


def continue_lbfgs(
    raw: Mapping[str, torch.nn.Parameter], grid: source.Grid
) -> dict[str, Any]:
    parameters = list(raw.values())
    optimizer = torch.optim.LBFGS(parameters, **CONTINUATION)
    history: list[dict[str, float | int]] = []
    closure_count = 0
    start = time.perf_counter()

    def closure() -> torch.Tensor:
        nonlocal closure_count
        optimizer.zero_grad(set_to_none=True)
        loss, physical, gauge, _ = source.objective(raw, grid)
        if not bool(torch.isfinite(loss)):
            raise FloatingPointError("nonfinite objective")
        loss.backward()
        rms, maximum = gradient_stats(raw)
        if not math.isfinite(rms) or not math.isfinite(maximum):
            raise FloatingPointError("nonfinite raw gradient")
        closure_count += 1
        history.append(
            {
                "closure": closure_count,
                "objective": float(loss.detach()),
                "physical_energy": float(physical.detach()),
                "gauge_fixing_energy": float(gauge.detach()),
                "raw_gradient_rms": rms,
                "raw_gradient_max": maximum,
            }
        )
        return loss

    optimizer.step(closure)
    state = optimizer.state[parameters[0]]
    optimizer.zero_grad(set_to_none=True)
    final_loss, final_physical, final_gauge, _ = source.objective(raw, grid)
    final_loss.backward()
    final_rms, final_max = gradient_stats(raw)
    if not all(
        math.isfinite(value)
        for value in (
            float(final_loss.detach()),
            float(final_physical.detach()),
            float(final_gauge.detach()),
            final_rms,
            final_max,
        )
    ):
        raise FloatingPointError("nonfinite continuation endpoint")
    return {
        "settings": CONTINUATION,
        "history": history,
        "iterations": int(state.get("n_iter", 0)),
        "closure_calls": closure_count,
        "function_evaluations": int(state.get("func_evals", closure_count)),
        "wall_seconds": time.perf_counter() - start,
        "final": {
            "objective": float(final_loss.detach()),
            "physical_energy": float(final_physical.detach()),
            "gauge_fixing_energy": float(final_gauge.detach()),
            "raw_gradient_rms": final_rms,
            "raw_gradient_max": final_max,
        },
    }


def run_recovery_arm(
    family: str,
    basin: str,
    device: torch.device,
    source_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    grid = source.make_grid(family, device)
    initial_optimizer: dict[str, Any] | None = None
    reconstruction: dict[str, Any] | None = None
    source_artifact: str | None = None
    source_artifact_sha256: str | None = None
    if family == "H":
        raw = source.raw_parameters(basin, grid)
        initial_optimizer = source.optimize_arm(raw, grid)
    else:
        source_arm = source_receipt["arms"][f"{family}:{basin}"]
        path = source_artifact_path(source_arm)
        arrays = load_arrays(path)
        raw, reconstruction = reconstruct_raw(arrays, grid)
        source_artifact = path.name
        source_artifact_sha256 = sha256(path)
    continuation = continue_lbfgs(raw, grid)
    values, fields = source.diagnostics(raw, grid)
    if not all(math.isfinite(float(value)) for value in values.values() if isinstance(value, (int, float))):
        raise ArmFailure("nonfinite final diagnostic", {"initial": initial_optimizer, "continuation": continuation})
    artifact_name = f"fields_{family}_{basin}.npz"
    artifact_path = RUN_DIR / artifact_name
    source.save_fields(artifact_path, fields, grid)
    artifact_hash = sha256(artifact_path)
    return {
        "family": family,
        "basin": basin,
        "R": grid.R,
        "N": grid.N,
        "dx": grid.dx,
        "source_artifact": source_artifact,
        "source_artifact_sha256": source_artifact_sha256,
        "reconstruction": reconstruction,
        "artifact": artifact_name,
        "artifact_sha256": artifact_hash,
        "completed": True,
        "error": None,
        "optimizer": {"initial": initial_optimizer, "continuation": continuation},
        "diagnostics": values,
        "gates": source.q1_q4(True, values),
    }


def failed_arm(
    family: str, basin: str, message: str, optimizer: dict[str, Any] | None
) -> dict[str, Any]:
    r_box, n = source.GRIDS[family]
    return {
        "family": family,
        "basin": basin,
        "R": r_box,
        "N": n,
        "dx": 2.0 * r_box / (n - 1),
        "source_artifact": None,
        "source_artifact_sha256": None,
        "reconstruction": None,
        "artifact": None,
        "artifact_sha256": None,
        "completed": False,
        "error": message,
        "optimizer": optimizer,
        "diagnostics": None,
        "gates": source.q1_q4(False, None),
    }


def select_h(arms: Mapping[str, Any]) -> dict[str, Any]:
    eligible = [
        basin
        for basin in source.STRUCTURAL
        if source.all_q1_q4(arms[f"P:{basin}"])
    ]
    if not eligible:
        return {"basin": None, "eligible": []}
    minimum = min(arms[f"P:{basin}"]["diagnostics"]["physical_energy"] for basin in eligible)
    selected = next(
        basin
        for basin in source.STRUCTURAL
        if basin in eligible
        and arms[f"P:{basin}"]["diagnostics"]["physical_energy"] <= minimum + 1.0e-10
    )
    return {"basin": selected, "eligible": eligible}


def evaluate(receipt: dict[str, Any]) -> None:
    arms = receipt["arms"]
    selected = receipt["h_selection"]["basin"]
    expected = [f"P:{basin}" for basin in source.BASINS]
    if selected is not None:
        expected.append(f"H:{selected}")
    expected.extend(f"D:{basin}" for basin in source.BASINS)
    r3 = receipt["run_order"] == expected and all(
        key in arms
        and arms[key]["completed"]
        and arms[key]["diagnostics"] is not None
        for key in expected
    )
    r5 = selected is not None
    campaign = {
        "arms": arms,
        "h_selection": receipt["h_selection"],
        "preflight": {"pass": receipt["preflight"]["pass"]},
        "gates": {},
        "pairwise_ordering_margins": {},
    }
    source.evaluate_campaign(campaign)
    receipt["source_quality_gates"] = {
        name: campaign["gates"][name]
        for name in (
            "structural_domain",
            "delocalized_control",
            "resolution",
            "quality_all",
        )
    }
    r6 = bool(campaign["gates"]["quality_all"])
    receipt["recovery_gates"] = {
        "R1": not receipt["manifest"]["required_mismatches"],
        "R2": receipt["preflight"]["pass"],
        "R3": r3,
        "R4": None,
        "R5": r5,
        "R6": r6,
    }
    if not receipt["recovery_gates"]["R1"] or not receipt["recovery_gates"]["R2"]:
        verdict = "INCONCLUSIVE—IMPLEMENTATION PREFLIGHT"
    elif not r3:
        verdict = "INCONCLUSIVE—EXECUTION OR VERIFICATION"
    elif not r5:
        verdict = "FAIL—NO Q2-QUALIFIED PRIMARY BACKGROUND"
    elif not r6:
        verdict = "PASS—Q2-QUALIFIED PRIMARY BACKGROUND"
    else:
        verdict = "PASS—Q2-QUALIFIED DOMAIN-AND-RESOLUTION BACKGROUND"
    receipt["primary_verdict"] = verdict
    receipt["status"] = "complete"


def environment_receipt(device: torch.device) -> dict[str, Any]:
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "hip": getattr(torch.version, "hip", None),
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "device": str(device),
        "device_name": torch.cuda.get_device_name(device),
        "dtype": "float64",
        "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
    }


def validate_resume(receipt: Mapping[str, Any], manifest: Mapping[str, Any]) -> None:
    if receipt.get("schema_version") != 1 or receipt.get("status") != "in_progress":
        raise RuntimeError("Existing recovery receipt is not resumable")
    if receipt.get("manifest") != manifest:
        raise RuntimeError("Recovery manifest changed; refusing resume")
    if receipt.get("continuation") != CONTINUATION:
        raise RuntimeError("Continuation schedule changed; refusing resume")
    for key, arm in receipt.get("arms", {}).items():
        artifact = arm.get("artifact")
        if artifact is not None:
            path = RUN_DIR / Path(artifact).name
            if sha256(path) != arm.get("artifact_sha256"):
                raise RuntimeError(f"{key}: completed artifact changed")


def run() -> dict[str, Any]:
    if not torch.cuda.is_available():
        raise RuntimeError("ROCm device exposed as cuda:0 is unavailable")
    if not PREFLIGHT_PATH.exists():
        raise FileNotFoundError(
            "Run verify_particle_stationary_q2_recovery.py --preflight first"
        )
    torch.set_default_dtype(torch.float64)
    torch.use_deterministic_algorithms(True)
    device = torch.device("cuda:0")
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    source_receipt = read_json(SOURCE_RESULTS_PATH)
    manifest = build_manifest(source_receipt)
    if RESULTS_PATH.exists():
        receipt = read_json(RESULTS_PATH)
        validate_resume(receipt, manifest)
    else:
        receipt = {
            "schema_version": 1,
            "status": "in_progress",
            "coefficients": source.COEFFICIENTS,
            "grids": source.GRIDS,
            "basins": list(source.BASINS),
            "structural_basins": list(source.STRUCTURAL),
            "continuation": CONTINUATION,
            "environment": environment_receipt(device),
            "manifest": manifest,
            "preflight": {},
            "run_order": [],
            "arms": {},
            "h_selection": {"basin": None, "eligible": []},
            "source_quality_gates": {},
            "recovery_gates": {},
            "primary_verdict": None,
        }
        receipt["preflight"] = primary_preflight(source_receipt, manifest, device)
        if not receipt["preflight"]["pass"]:
            receipt["status"] = "complete"
            receipt["recovery_gates"] = {
                "R1": not manifest["required_mismatches"],
                "R2": False,
                "R3": False,
                "R4": None,
                "R5": False,
                "R6": False,
            }
            receipt["primary_verdict"] = "INCONCLUSIVE—IMPLEMENTATION PREFLIGHT"
            write_json(RESULTS_PATH, receipt)
            return receipt
        write_json(RESULTS_PATH, receipt)

    def execute(family: str, basin: str) -> None:
        key = f"{family}:{basin}"
        if key in receipt["arms"]:
            return
        print(f"RUN {key}", flush=True)
        try:
            arm = run_recovery_arm(family, basin, device, source_receipt)
        except ArmFailure as failure:
            arm = failed_arm(family, basin, str(failure), failure.optimizer)
        except Exception as error:
            arm = failed_arm(
                family, basin, f"{type(error).__name__}: {error}", None
            )
        receipt["arms"][key] = arm
        receipt["run_order"].append(key)
        write_json(RESULTS_PATH, receipt)
        if arm["diagnostics"] is None:
            print(f"FAIL {key}: {arm['error']}", flush=True)
        else:
            diagnostics = arm["diagnostics"]
            print(
                f"DONE {key} E={diagnostics['physical_energy']:.9g} "
                f"grad={diagnostics['physical_gradient_rms']:.3g} "
                f"virial={diagnostics['cutoff_virial']:.3g}",
                flush=True,
            )

    for basin in source.BASINS:
        execute("P", basin)
    receipt["h_selection"] = select_h(receipt["arms"])
    write_json(RESULTS_PATH, receipt)
    selected = receipt["h_selection"]["basin"]
    if selected is not None:
        execute("H", selected)
    for basin in source.BASINS:
        execute("D", basin)
    evaluate(receipt)
    write_json(RESULTS_PATH, receipt)
    return receipt


def main() -> None:
    receipt = run()
    print(
        json.dumps(
            {
                "primary_verdict": receipt["primary_verdict"],
                "selected": receipt["h_selection"]["basin"],
                "results": str(RESULTS_PATH),
            },
            sort_keys=True,
        )
    )
    clean = receipt["primary_verdict"] not in {
        "INCONCLUSIVE—IMPLEMENTATION PREFLIGHT",
        "INCONCLUSIVE—EXECUTION OR VERIFICATION",
    }
    raise SystemExit(0 if clean else 2)


if __name__ == "__main__":
    main()
