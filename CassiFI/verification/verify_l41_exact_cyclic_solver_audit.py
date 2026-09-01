"""Independently verify the frozen L41 exact-cyclic solver audit."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import verification.run_l30_white_chromatic_field as l30

BOARD_SCHEMA = "cassi.l41.exact-cyclic-solver-audit-board.v1"
TRACE_SCHEMA = "cassi.l41.exact-cyclic-solver-audit-traces.v1"
VERIFICATION_SCHEMA = "cassi.l41.exact-cyclic-solver-audit-verification.v1"
OPERATOR_PROFILE = "cassi.qi-exact-cyclic-strang.v1"
PREREGISTRATION = ROOT / "designs" / "L41-EXACT-CYCLIC-SOLVER-AUDIT-PREREG.md"
DEFAULT_BOARD = ROOT / "_diag" / "l41-exact-cyclic-solver-audit" / "l41-board.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "l41-exact-cyclic-solver-audit"
DEFAULT_REPORT = DEFAULT_OUTPUT / "L41-EXACT-CYCLIC-SOLVER-AUDIT-REPORT.md"
DEFAULT_JSON = DEFAULT_OUTPUT / "l41-verification.json"
CHANNELS = 7
MODE_COUNT = 520
WIDTH = MODE_COUNT // 2
CONTROL_MODES = 4
DT = 0.05
CONTROL_STEPS = 2048
STABILITY_TICKS = 256
PHI = (1.0 + math.sqrt(5.0)) / 2.0
EXPECTED_SOURCES = {
    "designs/L41-EXACT-CYCLIC-SOLVER-AUDIT-PREREG.md",
    "cassi_qi_field.py",
    "cassi_prismatic_field.py",
    "cassi_white_chromatic_field.py",
    "cassi_cyclic_chromatic_field.py",
    "cassi_exact_cyclic_field.py",
    "tests/test_l41_exact_cyclic_solver_audit.py",
    "verification/run_l41_exact_cyclic_solver_audit.py",
    "verification/verify_l41_exact_cyclic_solver_audit.py",
}
EXPECTED_ARRAYS = {
    "schema_id",
    "laplacian",
    "expected_eigenvalues",
    "base_omega2",
    "coupling",
    "harmonic_omega2",
    "alpha",
    "nonlinear",
    "common_initial",
    "differential_initial",
    "common_velocity_initial",
    "differential_velocity_initial",
    "free_position",
    "free_velocity",
    "free_split_common",
    "free_split_differential",
    "free_split_common_velocity",
    "free_split_differential_velocity",
    "spot_position",
    "spot_velocity",
    "spot_rk4_position",
    "spot_rk4_velocity",
    "conservative_final_position",
    "conservative_final_velocity",
    "conservative_energy",
    "damped_final_position",
    "damped_final_velocity",
    "damped_energy",
    "nonlinear_final_common",
    "nonlinear_final_differential",
    "nonlinear_final_common_velocity",
    "nonlinear_final_differential_velocity",
    "nonlinear_energy",
    "roundtrip_common",
    "roundtrip_differential",
    "roundtrip_common_velocity",
    "roundtrip_differential_velocity",
    "zero_final_field",
    "stability_energy",
    "stability_drift",
    "stability_final_field",
    "clamp_counts",
}


class L41VerificationError(RuntimeError):
    """L41 evidence violates its frozen numerical contract."""


def need(condition: bool, message: str) -> None:
    if not condition:
        raise L41VerificationError(message)


def mapping(value: Any, label: str) -> Mapping[str, Any]:
    need(isinstance(value, Mapping), f"{label} must be an object")
    assert isinstance(value, Mapping)
    return value
def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise




def analytic_coordinate(modes: int, phase: float) -> np.ndarray:
    channel = np.arange(CHANNELS, dtype=np.float64).reshape(CHANNELS, 1, 1)
    mode = np.arange(modes, dtype=np.float64).reshape(1, modes, 1)
    real = 0.07 * np.cos((channel + 1.0) * (mode + 1.0) * 0.17 + phase)
    real += 0.02 * np.sin((channel + 2.0) * 0.31 - phase)
    imag = 0.05 * np.sin((channel + 1.0) * (mode + 2.0) * 0.13 - phase)
    imag -= 0.015 * np.cos((mode + 1.0) * 0.29 + phase)
    return real + 1j * imag


def laplacian(value: np.ndarray) -> np.ndarray:
    return 2.0 * value - np.roll(value, 1, axis=0) - np.roll(value, -1, axis=0)


def constants() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    progress = np.arange(CONTROL_MODES, dtype=np.float64) / float(WIDTH - 1)
    timescale = PHI ** (6.0 * progress)
    inverse_tau2 = (timescale**2) ** -1
    base_omega2 = inverse_tau2.reshape(1, CONTROL_MODES, 1)
    coupling = (0.05 * inverse_tau2).reshape(1, CONTROL_MODES, 1)
    nonlinear = (0.002 * inverse_tau2).reshape(1, CONTROL_MODES, 1)
    harmonic = np.arange(CHANNELS, dtype=np.float64).reshape(CHANNELS, 1, 1)
    harmonic_omega2 = base_omega2 + 4.0 * coupling * np.sin(
        math.pi * harmonic / CHANNELS
    ) ** 2
    alpha = (0.1 / timescale).reshape(1, CONTROL_MODES, 1)
    return base_omega2, coupling, nonlinear, harmonic_omega2, alpha


def exact_step(
    position: np.ndarray,
    velocity: np.ndarray,
    harmonic_omega2: np.ndarray,
    alpha: np.ndarray,
    step: float,
) -> tuple[np.ndarray, np.ndarray]:
    frequency = np.sqrt(np.maximum(harmonic_omega2 - alpha**2, 0.0))
    angle = frequency * step
    cosine = np.cos(angle)
    sine_over_frequency = step * np.sinc(angle / math.pi)
    decay = np.exp(-alpha * step)
    position_hat = np.fft.fft(position, axis=0, norm="ortho")
    velocity_hat = np.fft.fft(velocity, axis=0, norm="ortho")
    next_position_hat = decay * (
        (cosine + alpha * sine_over_frequency) * position_hat
        + sine_over_frequency * velocity_hat
    )
    next_velocity_hat = decay * (
        -harmonic_omega2 * sine_over_frequency * position_hat
        + (cosine - alpha * sine_over_frequency) * velocity_hat
    )
    return (
        np.fft.ifft(next_position_hat, axis=0, norm="ortho"),
        np.fft.ifft(next_velocity_hat, axis=0, norm="ortho"),
    )


def rk4_linear(
    position: np.ndarray,
    velocity: np.ndarray,
    base_omega2: np.ndarray,
    coupling: np.ndarray,
    gamma: np.ndarray,
    microsteps: int,
) -> tuple[np.ndarray, np.ndarray]:
    step = DT / microsteps

    def rhs(q: np.ndarray, v: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        return v, -base_omega2 * q - coupling * laplacian(q) - gamma * v

    q = position.copy()
    v = velocity.copy()
    for _ in range(microsteps):
        q1, v1 = rhs(q, v)
        q2, v2 = rhs(q + 0.5 * step * q1, v + 0.5 * step * v1)
        q3, v3 = rhs(q + 0.5 * step * q2, v + 0.5 * step * v2)
        q4, v4 = rhs(q + step * q3, v + step * v3)
        q += step * (q1 + 2.0 * q2 + 2.0 * q3 + q4) / 6.0
        v += step * (v1 + 2.0 * v2 + 2.0 * v3 + v4) / 6.0
    return q, v


def phase_energy_physical(
    position: np.ndarray,
    velocity: np.ndarray,
    base_omega2: np.ndarray,
    coupling: np.ndarray,
) -> float:
    stiffness = base_omega2 * position + coupling * laplacian(position)
    return float(
        0.5
        * (
            np.sum(np.abs(velocity) ** 2)
            + np.real(np.sum(np.conjugate(position) * stiffness))
        )
        / (1.0 + PHI * PHI)
    )


def phase_energy_harmonic(
    position: np.ndarray, velocity: np.ndarray, harmonic_omega2: np.ndarray
) -> float:
    q_hat = np.fft.fft(position, axis=0, norm="ortho")
    v_hat = np.fft.fft(velocity, axis=0, norm="ortho")
    return float(
        0.5
        * np.sum(np.abs(v_hat) ** 2 + harmonic_omega2 * np.abs(q_hat) ** 2)
        / (1.0 + PHI * PHI)
    )


def split_step(
    state: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
    harmonic_omega2: np.ndarray,
    nonlinear: np.ndarray,
    step: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    common, differential, common_velocity, differential_velocity = state
    radius2 = np.abs(common) ** 2 + np.abs(differential) ** 2
    common_velocity = common_velocity - 0.5 * step * nonlinear * radius2 * common
    differential_velocity = (
        differential_velocity
        - 0.5 * step * nonlinear * radius2 * differential
    )
    zero_alpha = np.zeros((1, CONTROL_MODES, 1), dtype=np.float64)
    common, common_velocity = exact_step(
        common, common_velocity, harmonic_omega2, zero_alpha, step
    )
    differential, differential_velocity = exact_step(
        differential, differential_velocity, harmonic_omega2, zero_alpha, step
    )
    radius2 = np.abs(common) ** 2 + np.abs(differential) ** 2
    common_velocity = common_velocity - 0.5 * step * nonlinear * radius2 * common
    differential_velocity = (
        differential_velocity
        - 0.5 * step * nonlinear * radius2 * differential
    )
    return common, differential, common_velocity, differential_velocity


def nonlinear_hamiltonian(
    state: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
    harmonic_omega2: np.ndarray,
    nonlinear: np.ndarray,
) -> float:
    common, differential, common_velocity, differential_velocity = state
    linear = phase_energy_harmonic(
        common, common_velocity, harmonic_omega2
    ) + phase_energy_harmonic(
        differential, differential_velocity, harmonic_omega2
    )
    radius2 = np.abs(common) ** 2 + np.abs(differential) ** 2
    return linear + float(
        0.25 * np.sum(nonlinear * radius2**2) / (1.0 + PHI * PHI)
    )


def relative_state_error(
    left: tuple[np.ndarray, ...], right: tuple[np.ndarray, ...]
) -> float:
    numerator = math.sqrt(
        sum(float(np.sum(np.abs(a - b) ** 2)) for a, b in zip(left, right, strict=True))
    )
    denominator = max(
        math.sqrt(sum(float(np.sum(np.abs(a) ** 2)) for a in left)),
        np.finfo(np.float64).eps,
    )
    return numerator / denominator


def need_close(actual: np.ndarray, expected: np.ndarray, label: str) -> None:
    need(
        bool(np.allclose(actual, expected, rtol=2.0e-11, atol=2.0e-12)),
        f"{label} mismatch",
    )


def load_trace(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        need(set(archive.files) == EXPECTED_ARRAYS, "trace array set mismatch")
        arrays = {name: archive[name] for name in archive.files}
    for name, value in arrays.items():
        if name != "schema_id":
            need(bool(np.isfinite(value).all()), f"{name} contains non-finite values")
    return arrays


def analyze(arrays: Mapping[str, np.ndarray]) -> tuple[dict[str, float | int | bool], dict[str, bool]]:
    base_omega2, coupling, nonlinear, harmonic_omega2, alpha = constants()
    common = analytic_coordinate(CONTROL_MODES, 0.1)
    differential = analytic_coordinate(CONTROL_MODES, 0.7)
    common_velocity = analytic_coordinate(CONTROL_MODES, 1.3)
    differential_velocity = analytic_coordinate(CONTROL_MODES, 1.9)
    initial = (common, differential, common_velocity, differential_velocity)
    for name, expected in (
        ("base_omega2", base_omega2),
        ("coupling", coupling),
        ("nonlinear", nonlinear),
        ("harmonic_omega2", harmonic_omega2),
        ("alpha", alpha),
        ("common_initial", common),
        ("differential_initial", differential),
        ("common_velocity_initial", common_velocity),
        ("differential_velocity_initial", differential_velocity),
    ):
        need_close(arrays[name], expected, name)

    eye = np.eye(CHANNELS, dtype=np.float64)
    expected_laplacian = laplacian(eye)
    eigenvalues = 4.0 * np.sin(math.pi * np.arange(CHANNELS) / CHANNELS) ** 2
    need_close(arrays["laplacian"], expected_laplacian, "cyclic Laplacian")
    need_close(arrays["expected_eigenvalues"], eigenvalues, "cyclic eigenvalues")
    operator_error = float(
        np.max(
            np.abs(
                np.sort(np.linalg.eigvalsh(expected_laplacian))
                - np.sort(eigenvalues)
            )
        )
    )
    physical_energy = phase_energy_physical(
        common, common_velocity, base_omega2, coupling
    )
    harmonic_energy = phase_energy_harmonic(
        common, common_velocity, harmonic_omega2
    )
    parseval_error = abs(physical_energy - harmonic_energy)

    free_position = common + DT * common_velocity
    free_velocity = common_velocity
    need_close(arrays["free_position"], free_position, "free position")
    need_close(arrays["free_velocity"], free_velocity, "free velocity")
    free_error = float(
        max(
            np.max(np.abs(arrays["free_position"] - free_position)),
            np.max(np.abs(arrays["free_velocity"] - free_velocity)),
        )
    )
    free_split_expected = (
        common + DT * common_velocity,
        differential + DT * differential_velocity,
        common_velocity,
        differential_velocity,
    )
    free_split_actual = (
        arrays["free_split_common"],
        arrays["free_split_differential"],
        arrays["free_split_common_velocity"],
        arrays["free_split_differential_velocity"],
    )
    for index, (actual, expected) in enumerate(
        zip(free_split_actual, free_split_expected, strict=True)
    ):
        need_close(actual, expected, f"free split component {index}")
    split_no_term_error = relative_state_error(free_split_actual, free_split_expected)

    expected_spot = exact_step(
        common, common_velocity, harmonic_omega2, alpha, DT
    )
    need_close(arrays["spot_position"], expected_spot[0], "exact spot position")
    need_close(arrays["spot_velocity"], expected_spot[1], "exact spot velocity")
    rk4_spot = rk4_linear(
        common,
        common_velocity,
        base_omega2,
        coupling,
        2.0 * alpha,
        4096,
    )
    need_close(arrays["spot_rk4_position"], rk4_spot[0], "runner RK4 position")
    need_close(arrays["spot_rk4_velocity"], rk4_spot[1], "runner RK4 velocity")
    rk4_error = float(
        max(
            np.max(np.abs(arrays["spot_position"] - rk4_spot[0])),
            np.max(np.abs(arrays["spot_velocity"] - rk4_spot[1])),
        )
    )

    conservative_position = common.copy()
    conservative_velocity = common_velocity.copy()
    conservative_energy = [
        phase_energy_harmonic(
            conservative_position, conservative_velocity, harmonic_omega2
        )
    ]
    zero_alpha = np.zeros_like(alpha)
    for _ in range(CONTROL_STEPS):
        conservative_position, conservative_velocity = exact_step(
            conservative_position,
            conservative_velocity,
            harmonic_omega2,
            zero_alpha,
            DT,
        )
        conservative_energy.append(
            phase_energy_harmonic(
                conservative_position, conservative_velocity, harmonic_omega2
            )
        )
    conservative_energy_array = np.asarray(conservative_energy)
    need_close(
        arrays["conservative_final_position"],
        conservative_position,
        "conservative final position",
    )
    need_close(
        arrays["conservative_final_velocity"],
        conservative_velocity,
        "conservative final velocity",
    )
    need_close(
        arrays["conservative_energy"],
        conservative_energy_array,
        "conservative energy",
    )
    conservative_drift = float(
        abs(conservative_energy_array[-1] - conservative_energy_array[0])
        / conservative_energy_array[0]
    )

    damped_position = common.copy()
    damped_velocity = common_velocity.copy()
    damped_energy = [
        phase_energy_harmonic(damped_position, damped_velocity, harmonic_omega2)
    ]
    for _ in range(CONTROL_STEPS):
        damped_position, damped_velocity = exact_step(
            damped_position, damped_velocity, harmonic_omega2, alpha, DT
        )
        damped_energy.append(
            phase_energy_harmonic(damped_position, damped_velocity, harmonic_omega2)
        )
    damped_energy_array = np.asarray(damped_energy)
    need_close(arrays["damped_final_position"], damped_position, "damped position")
    need_close(arrays["damped_final_velocity"], damped_velocity, "damped velocity")
    need_close(arrays["damped_energy"], damped_energy_array, "damped energy")
    damped_ratio = float(damped_energy_array[-1] / damped_energy_array[0])
    damped_increment = float(
        np.max(np.maximum(np.diff(damped_energy_array), 0.0))
        / damped_energy_array[0]
    )

    forward = split_step(initial, harmonic_omega2, nonlinear, DT)
    backward = split_step(forward, harmonic_omega2, nonlinear, -DT)
    roundtrip = (
        arrays["roundtrip_common"],
        arrays["roundtrip_differential"],
        arrays["roundtrip_common_velocity"],
        arrays["roundtrip_differential_velocity"],
    )
    for index, (actual, expected) in enumerate(zip(roundtrip, backward, strict=True)):
        need_close(actual, expected, f"roundtrip component {index}")
    reversibility_error = relative_state_error(initial, backward)

    nonlinear_state: tuple[
        np.ndarray, np.ndarray, np.ndarray, np.ndarray
    ] = (
        common.copy(),
        differential.copy(),
        common_velocity.copy(),
        differential_velocity.copy(),
    )
    nonlinear_energy = [
        nonlinear_hamiltonian(nonlinear_state, harmonic_omega2, nonlinear)
    ]
    for _ in range(CONTROL_STEPS):
        nonlinear_state = split_step(
            nonlinear_state, harmonic_omega2, nonlinear, DT
        )
        nonlinear_energy.append(
            nonlinear_hamiltonian(nonlinear_state, harmonic_omega2, nonlinear)
        )
    nonlinear_energy_array = np.asarray(nonlinear_energy)
    nonlinear_actual = (
        arrays["nonlinear_final_common"],
        arrays["nonlinear_final_differential"],
        arrays["nonlinear_final_common_velocity"],
        arrays["nonlinear_final_differential_velocity"],
    )
    for index, (actual, expected) in enumerate(
        zip(nonlinear_actual, nonlinear_state, strict=True)
    ):
        need_close(actual, expected, f"nonlinear final component {index}")
    need_close(arrays["nonlinear_energy"], nonlinear_energy_array, "nonlinear energy")
    nonlinear_envelope = float(
        (np.max(nonlinear_energy_array) - np.min(nonlinear_energy_array))
        / nonlinear_energy_array[0]
    )

    need(arrays["zero_final_field"].shape == (7, 9 * MODE_COUNT, 1), "zero field shape mismatch")
    need(arrays["stability_final_field"].shape == (7, 9 * MODE_COUNT, 1), "stability field shape mismatch")
    need(arrays["stability_energy"].shape == (STABILITY_TICKS + 1,), "stability energy shape mismatch")
    need(arrays["stability_drift"].shape == (STABILITY_TICKS,), "stability drift shape mismatch")
    need(arrays["clamp_counts"].shape == (2,), "clamp count shape mismatch")
    zero_nonzero = int(np.count_nonzero(arrays["zero_final_field"]))
    zero_clamps = int(arrays["clamp_counts"][0])
    driven_clamps = int(arrays["clamp_counts"][1])
    driven_finite = bool(np.isfinite(arrays["stability_final_field"]).all())
    driven_max_energy = float(np.max(arrays["stability_energy"]))
    driven_max_drift = float(np.max(np.abs(arrays["stability_drift"])))

    metrics: dict[str, float | int | bool] = {
        "operator_eigenvalue_max_error": operator_error,
        "parseval_energy_absolute_error": parseval_error,
        "free_drift_max_error": free_error,
        "split_no_term_relative_error": split_no_term_error,
        "independent_rk4_max_error": rk4_error,
        "conservative_relative_energy_drift": conservative_drift,
        "damped_final_energy_ratio": damped_ratio,
        "damped_max_positive_increment_ratio": damped_increment,
        "nonlinear_roundtrip_relative_error": reversibility_error,
        "nonlinear_hamiltonian_relative_envelope": nonlinear_envelope,
        "zero_state_nonzero_count": zero_nonzero,
        "zero_state_clamp_count": zero_clamps,
        "driven_finite": driven_finite,
        "driven_clamp_count": driven_clamps,
        "driven_maximum_dynamic_energy": driven_max_energy,
        "driven_maximum_absolute_input_energy_drift": driven_max_drift,
    }
    conditions = {
        "operator_and_parseval": operator_error <= 2.0e-12
        and parseval_error <= 2.0e-12,
        "no_term": free_error <= 1.0e-12 and split_no_term_error <= 1.0e-12,
        "independent_rk4": rk4_error <= 2.0e-10,
        "undamped_conservation": conservative_drift <= 2.0e-9,
        "damped_stability": damped_ratio < 1.0 and damped_increment <= 2.0e-10,
        "nonlinear_split": reversibility_error <= 2.0e-10
        and nonlinear_envelope <= 2.0e-5,
        "zero_state": zero_nonzero == 0 and zero_clamps == 0,
        "driven_stability": driven_finite
        and driven_clamps == 0
        and driven_max_energy <= 1.05
        and driven_max_drift <= 2.0e-5,
    }
    return metrics, conditions


def verify_board(
    board_path: Path, *, allow_smoke_device: bool = False
) -> tuple[str, dict[str, Any]]:
    board = json.loads(board_path.read_text(encoding="utf-8"))
    need(isinstance(board, dict), "board root must be an object")
    need(board.get("schema_id") == BOARD_SCHEMA, "board schema mismatch")
    need(board.get("status") == "COMPLETE", "board is not COMPLETE")
    need(board.get("operator_profile_id") == OPERATOR_PROFILE, "operator identity mismatch")
    need(board.get("trace_schema_id") == TRACE_SCHEMA, "trace schema mismatch")
    constants_board = mapping(board.get("constants"), "constants")
    need(
        constants_board
        == {
            "channels": CHANNELS,
            "mode_count": MODE_COUNT,
            "control_modes": CONTROL_MODES,
            "dt": DT,
            "control_steps": CONTROL_STEPS,
            "stability_ticks": STABILITY_TICKS,
            "stability_steps_per_tick": 8,
            "rk4_microsteps": 4096,
        },
        "constant declaration mismatch",
    )
    source = mapping(board.get("source_sha256"), "source_sha256")
    need(set(source) == EXPECTED_SOURCES, "source hash path set mismatch")
    for relative in EXPECTED_SOURCES:
        path = ROOT / relative
        need(path.is_file(), f"source path missing: {relative}")
        need(source[relative] == l30.sha256_file(path), f"source hash mismatch: {relative}")
    prereg_relative = PREREGISTRATION.relative_to(ROOT).as_posix()
    need(
        board.get("preregistration_sha256") == source[prereg_relative],
        "preregistration hash mismatch",
    )
    device = mapping(board.get("device"), "device")
    need(device.get("control_dtype") == "float64", "control dtype mismatch")
    need(device.get("stability_dtype") == "float32", "stability dtype mismatch")
    if not allow_smoke_device:
        need(device.get("type") == "cuda", "canonical device must be cuda")
        need(device.get("name") == "AMD Radeon RX 7900 XTX", "canonical GPU mismatch")
        need(isinstance(device.get("hip_version"), str), "HIP version missing")

    trace_item = mapping(board.get("trace"), "trace")
    need(trace_item.get("path") == "l41-traces.npz", "trace sibling mismatch")
    trace_path = board_path.parent / "l41-traces.npz"
    need(trace_path.is_file(), "trace artifact missing")
    need(trace_item.get("sha256") == l30.sha256_file(trace_path), "trace hash mismatch")
    arrays = load_trace(trace_path)
    need(str(arrays["schema_id"].item()) == TRACE_SCHEMA, "trace schema mismatch")
    need(trace_item.get("array_count") == len(EXPECTED_ARRAYS), "array count mismatch")
    metrics, conditions = analyze(arrays)

    declared = mapping(mapping(board.get("arms"), "arms").get("canonical"), "canonical arm")
    need(set(declared) == set(metrics), "declared metric set mismatch")
    for name, expected in metrics.items():
        actual = declared[name]
        if isinstance(expected, bool):
            need(actual is expected, f"declared metric mismatch: {name}")
        elif isinstance(expected, int):
            need(actual == expected, f"declared metric mismatch: {name}")
        else:
            need(
                isinstance(actual, (int, float))
                and math.isclose(float(actual), expected, rel_tol=2.0e-8, abs_tol=2.0e-12),
                f"declared metric mismatch: {name}",
            )
    failures = [name for name, passed in conditions.items() if not passed]
    verdict = "PASS" if not failures else "FAIL"
    return verdict, {
        "schema_id": VERIFICATION_SCHEMA,
        "verdict": verdict,
        "metrics": metrics,
        "controls": conditions,
        "failures": failures,
    }


def report_text(verdict: str, payload: Mapping[str, Any]) -> str:
    lines = [
        "# L41 Exact Cyclic Solver Audit — Verification",
        "",
        f"**Verdict: `{verdict}`**",
        "",
        "| Control | Pass |",
        "|---|---:|",
    ]
    for name, passed in mapping(payload.get("controls", {}), "controls").items():
        lines.append(f"| `{name}` | `{str(bool(passed)).lower()}` |")
    if payload.get("failures"):
        lines.extend(["", "## Failures", *[f"- {item}" for item in payload["failures"]]])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--board", type=Path, default=DEFAULT_BOARD)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--allow-smoke-device", action="store_true")
    args = parser.parse_args()
    board_path = args.board.resolve()
    if not board_path.is_file():
        verdict = "INCOMPLETE"
        payload: dict[str, Any] = {
            "schema_id": VERIFICATION_SCHEMA,
            "verdict": verdict,
            "metrics": {},
            "controls": {},
            "failures": ["board artifact is unavailable"],
        }
    else:
        try:
            verdict, payload = verify_board(
                board_path, allow_smoke_device=args.allow_smoke_device
            )
        except Exception as exc:
            verdict = "FAIL"
            payload = {
                "schema_id": VERIFICATION_SCHEMA,
                "verdict": verdict,
                "metrics": {},
                "controls": {},
                "failures": [f"{type(exc).__name__}: {exc}"],
            }
    payload = dict(payload)
    payload.update(
        {
            "board_path": (
                board_path.relative_to(ROOT).as_posix()
                if board_path.is_relative_to(ROOT)
                else str(board_path)
            ),
            "board_sha256": l30.sha256_file(board_path) if board_path.is_file() else None,
        }
    )
    atomic_write(args.json.resolve(), l30.canonical_bytes(payload))
    atomic_write(
        args.report.resolve(), report_text(verdict, payload).encode("utf-8")
    )
    print(verdict)
    print(args.report.resolve())
    print(args.json.resolve())
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
