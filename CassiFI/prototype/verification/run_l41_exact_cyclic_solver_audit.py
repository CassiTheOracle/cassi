"""Run the frozen L41 numerical audit of the immutable L34 solver."""

from __future__ import annotations

import argparse
import math
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import Tensor

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import verification.run_l30_white_chromatic_field as l30
from cassi_exact_cyclic_field import ExactCyclicFieldConfig, ExactCyclicFieldController
from cassi_prismatic_field import PHI

BOARD_SCHEMA = "cassi.l41.exact-cyclic-solver-audit-board.v1"
TRACE_SCHEMA = "cassi.l41.exact-cyclic-solver-audit-traces.v1"
PREREGISTRATION = ROOT / "designs" / "L41-EXACT-CYCLIC-SOLVER-AUDIT-PREREG.md"
RUNNER = ROOT / "verification" / "run_l41_exact_cyclic_solver_audit.py"
VERIFIER = ROOT / "verification" / "verify_l41_exact_cyclic_solver_audit.py"
TEST = ROOT / "tests" / "test_l41_exact_cyclic_solver_audit.py"
OUTPUT_DIR = ROOT / "_diag" / "l41-exact-cyclic-solver-audit"
BOARD_NAME = "l41-board.json"
TRACE_NAME = "l41-traces.npz"
CHANNELS = 7
MODE_COUNT = 520
CONTROL_MODES = 4
DT = 0.05
CONTROL_STEPS = 2048
STABILITY_TICKS = 256
SOURCE_PATHS = (
    PREREGISTRATION,
    ROOT / "cassi_qi_field.py",
    ROOT / "cassi_prismatic_field.py",
    ROOT / "cassi_white_chromatic_field.py",
    ROOT / "cassi_cyclic_chromatic_field.py",
    ROOT / "cassi_exact_cyclic_field.py",
    TEST,
    RUNNER,
    VERIFIER,
)


class L41RunnerError(RuntimeError):
    """The canonical L41 audit could not be completed."""


def analytic_coordinate(
    modes: int,
    *,
    phase: float,
    device: torch.device,
    dtype: torch.dtype,
) -> Tensor:
    channel = torch.arange(CHANNELS, device=device, dtype=dtype).reshape(
        CHANNELS, 1, 1
    )
    mode = torch.arange(modes, device=device, dtype=dtype).reshape(1, modes, 1)
    real = 0.07 * torch.cos((channel + 1.0) * (mode + 1.0) * 0.17 + phase)
    real = real + 0.02 * torch.sin((channel + 2.0) * 0.31 - phase)
    imag = 0.05 * torch.sin((channel + 1.0) * (mode + 2.0) * 0.13 - phase)
    imag = imag - 0.015 * torch.cos((mode + 1.0) * 0.29 + phase)
    return torch.complex(real, imag)


def cyclic_laplacian(value: Tensor) -> Tensor:
    return 2.0 * value - torch.roll(value, 1, 0) - torch.roll(value, -1, 0)
def rk4_linear(
    position: Tensor,
    velocity: Tensor,
    base_omega2: Tensor,
    coupling: Tensor,
    gamma: Tensor,
    *,
    step: float,
    microsteps: int,
) -> tuple[Tensor, Tensor]:
    microstep = step / microsteps

    def rhs(q: Tensor, v: Tensor) -> tuple[Tensor, Tensor]:
        return (
            v,
            -base_omega2 * q - coupling * cyclic_laplacian(q) - gamma * v,
        )

    q = position.clone()
    v = velocity.clone()
    for _ in range(microsteps):
        q1, v1 = rhs(q, v)
        q2, v2 = rhs(q + 0.5 * microstep * q1, v + 0.5 * microstep * v1)
        q3, v3 = rhs(q + 0.5 * microstep * q2, v + 0.5 * microstep * v2)
        q4, v4 = rhs(q + microstep * q3, v + microstep * v3)
        q = q + microstep * (q1 + 2.0 * q2 + 2.0 * q3 + q4) / 6.0
        v = v + microstep * (v1 + 2.0 * v2 + 2.0 * v3 + v4) / 6.0
    return q, v




def phase_energy_physical(
    position: Tensor,
    velocity: Tensor,
    base_omega2: Tensor,
    coupling: Tensor,
) -> Tensor:
    stiffness_position = base_omega2 * position + coupling * cyclic_laplacian(
        position
    )
    return 0.5 * (
        velocity.abs().square().sum()
        + (position.conj() * stiffness_position).real.sum()
    ) / (1.0 + PHI * PHI)


def phase_energy_harmonic(
    position: Tensor, velocity: Tensor, harmonic_omega2: Tensor
) -> Tensor:
    position_hat = torch.fft.fft(position, dim=0, norm="ortho")
    velocity_hat = torch.fft.fft(velocity, dim=0, norm="ortho")
    return 0.5 * (
        velocity_hat.abs().square() + harmonic_omega2 * position_hat.abs().square()
    ).sum() / (1.0 + PHI * PHI)


def undamped_exact(
    harmonic_omega2: Tensor, step: float
) -> tuple[Tensor, Tensor, Tensor, Tensor, Tensor]:
    frequency = torch.sqrt(harmonic_omega2)
    angle = frequency * step
    zero = torch.zeros_like(harmonic_omega2)
    one = torch.ones_like(harmonic_omega2)
    return (
        harmonic_omega2,
        zero,
        torch.cos(angle),
        step * torch.sinc(angle / math.pi),
        one,
    )


def free_exact(
    shape: tuple[int, int, int],
    *,
    step: float,
    device: torch.device,
    dtype: torch.dtype,
) -> tuple[Tensor, Tensor, Tensor, Tensor, Tensor]:
    zero = torch.zeros(shape, device=device, dtype=dtype)
    one = torch.ones(shape, device=device, dtype=dtype)
    return zero, zero, one, torch.full_like(zero, step), one


def split_step(
    controller: ExactCyclicFieldController,
    common: Tensor,
    differential: Tensor,
    common_velocity: Tensor,
    differential_velocity: Tensor,
    exact: tuple[Tensor, Tensor, Tensor, Tensor, Tensor],
    nonlinear: Tensor,
    step: float,
) -> tuple[Tensor, Tensor, Tensor, Tensor]:
    radius2 = common.abs().square() + differential.abs().square()
    common_velocity = common_velocity - 0.5 * step * nonlinear * radius2 * common
    differential_velocity = (
        differential_velocity - 0.5 * step * nonlinear * radius2 * differential
    )
    common, common_velocity = controller._linear_exact_step(
        common, common_velocity, exact
    )
    differential, differential_velocity = controller._linear_exact_step(
        differential, differential_velocity, exact
    )
    radius2 = common.abs().square() + differential.abs().square()
    common_velocity = common_velocity - 0.5 * step * nonlinear * radius2 * common
    differential_velocity = (
        differential_velocity - 0.5 * step * nonlinear * radius2 * differential
    )
    return common, differential, common_velocity, differential_velocity


def nonlinear_hamiltonian(
    common: Tensor,
    differential: Tensor,
    common_velocity: Tensor,
    differential_velocity: Tensor,
    harmonic_omega2: Tensor,
    nonlinear: Tensor,
) -> Tensor:
    linear = phase_energy_harmonic(
        common, common_velocity, harmonic_omega2
    ) + phase_energy_harmonic(
        differential, differential_velocity, harmonic_omega2
    )
    radius2 = common.abs().square() + differential.abs().square()
    potential = 0.25 * (nonlinear * radius2.square()).sum() / (
        1.0 + PHI * PHI
    )
    return linear + potential


def relative_state_error(left: tuple[Tensor, ...], right: tuple[Tensor, ...]) -> float:
    numerator = torch.sqrt(
        torch.stack(
            [(a - b).abs().square().sum() for a, b in zip(left, right, strict=True)]
        ).sum()
    )
    denominator = torch.sqrt(
        torch.stack([a.abs().square().sum() for a in left]).sum()
    ).clamp_min(torch.finfo(left[0].real.dtype).eps)
    return float((numerator / denominator).item())


def to_numpy(value: Tensor) -> np.ndarray:
    return value.detach().cpu().numpy()


def run_audit(
    device: torch.device,
    *,
    control_steps: int = CONTROL_STEPS,
    stability_ticks: int = STABILITY_TICKS,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    controller = ExactCyclicFieldController(
        ExactCyclicFieldConfig(mode_count=MODE_COUNT)
    )
    state64 = controller.new_state(device=device, dtype=torch.float64)
    omega2_full, alpha_full, cosine_full, sine_full, decay_full = (
        controller._exact_constants(state64)
    )
    exact = (
        omega2_full[:, :CONTROL_MODES],
        alpha_full[:, :CONTROL_MODES],
        cosine_full[:, :CONTROL_MODES],
        sine_full[:, :CONTROL_MODES],
        decay_full[:, :CONTROL_MODES],
    )
    constants = controller._constants(state64)
    base_omega2 = constants["omega2"][:, :CONTROL_MODES]
    coupling = constants["edge_weight"][0:1, :CONTROL_MODES]
    nonlinear = constants["nonlinear"][:, :CONTROL_MODES]
    harmonic_omega2 = exact[0]

    common = analytic_coordinate(
        CONTROL_MODES, phase=0.1, device=device, dtype=torch.float64
    )
    differential = analytic_coordinate(
        CONTROL_MODES, phase=0.7, device=device, dtype=torch.float64
    )
    common_velocity = analytic_coordinate(
        CONTROL_MODES, phase=1.3, device=device, dtype=torch.float64
    )
    differential_velocity = analytic_coordinate(
        CONTROL_MODES, phase=1.9, device=device, dtype=torch.float64
    )

    eye = torch.eye(CHANNELS, device=device, dtype=torch.float64)
    laplacian = cyclic_laplacian(eye)
    expected_eigenvalues = 4.0 * torch.sin(
        math.pi
        * torch.arange(CHANNELS, device=device, dtype=torch.float64)
        / CHANNELS
    ).square()
    actual_eigenvalues = torch.linalg.eigvalsh(laplacian)
    operator_error = float(
        (
            torch.sort(actual_eigenvalues).values
            - torch.sort(expected_eigenvalues).values
        )
        .abs()
        .max()
        .item()
    )
    physical_energy = phase_energy_physical(
        common, common_velocity, base_omega2, coupling
    )
    harmonic_energy = phase_energy_harmonic(
        common, common_velocity, harmonic_omega2
    )
    parseval_error = float((physical_energy - harmonic_energy).abs().item())

    free = free_exact(
        (CHANNELS, CONTROL_MODES, 1),
        step=DT,
        device=device,
        dtype=torch.float64,
    )
    free_position, free_velocity = controller._linear_exact_step(
        common, common_velocity, free
    )
    expected_free_position = common + DT * common_velocity
    free_error = float(
        max(
            (free_position - expected_free_position).abs().max().item(),
            (free_velocity - common_velocity).abs().max().item(),
        )
    )
    zero_nonlinear = torch.zeros_like(nonlinear)
    free_split = split_step(
        controller,
        common,
        differential,
        common_velocity,
        differential_velocity,
        free,
        zero_nonlinear,
        DT,
    )
    free_linear_common = controller._linear_exact_step(
        common, common_velocity, free
    )
    free_linear_differential = controller._linear_exact_step(
        differential, differential_velocity, free
    )
    free_linear = (
        free_linear_common[0],
        free_linear_differential[0],
        free_linear_common[1],
        free_linear_differential[1],
    )
    split_no_term_error = relative_state_error(free_split, free_linear)

    spot_position, spot_velocity = controller._linear_exact_step(
        common, common_velocity, exact
    )
    rk4_position, rk4_velocity = rk4_linear(
        common,
        common_velocity,
        base_omega2,
        coupling,
        2.0 * exact[1],
        step=DT,
        microsteps=4096,
    )
    independent_rk4_error = float(
        max(
            (spot_position - rk4_position).abs().max().item(),
            (spot_velocity - rk4_velocity).abs().max().item(),
        )
    )


    conservative_exact = undamped_exact(harmonic_omega2, DT)
    conservative_position = common.clone()
    conservative_velocity = common_velocity.clone()
    conservative_energies = [
        phase_energy_harmonic(
            conservative_position, conservative_velocity, harmonic_omega2
        )
    ]
    for _ in range(control_steps):
        conservative_position, conservative_velocity = (
            controller._linear_exact_step(
                conservative_position, conservative_velocity, conservative_exact
            )
        )
        conservative_energies.append(
            phase_energy_harmonic(
                conservative_position, conservative_velocity, harmonic_omega2
            )
        )
    conservative_energy = torch.stack(conservative_energies)
    conservative_drift = float(
        (
            (conservative_energy[-1] - conservative_energy[0]).abs()
            / conservative_energy[0]
        ).item()
    )

    damped_position = common.clone()
    damped_velocity = common_velocity.clone()
    damped_energies = [
        phase_energy_harmonic(damped_position, damped_velocity, harmonic_omega2)
    ]
    for _ in range(control_steps):
        damped_position, damped_velocity = controller._linear_exact_step(
            damped_position, damped_velocity, exact
        )
        damped_energies.append(
            phase_energy_harmonic(
                damped_position, damped_velocity, harmonic_omega2
            )
        )
    damped_energy = torch.stack(damped_energies)
    damped_positive_increment = float(
        torch.clamp_min(damped_energy[1:] - damped_energy[:-1], 0.0).max().item()
        / damped_energy[0].item()
    )

    initial_split = (
        common.clone(),
        differential.clone(),
        common_velocity.clone(),
        differential_velocity.clone(),
    )
    forward = split_step(
        controller, *initial_split, conservative_exact, nonlinear, DT
    )
    backward = split_step(
        controller,
        *forward,
        undamped_exact(harmonic_omega2, -DT),
        nonlinear,
        -DT,
    )
    reversibility_error = relative_state_error(initial_split, backward)
    nonlinear_state = initial_split
    nonlinear_energies = [
        nonlinear_hamiltonian(
            *nonlinear_state, harmonic_omega2, nonlinear
        )
    ]
    for _ in range(control_steps):
        nonlinear_state = split_step(
            controller,
            *nonlinear_state,
            conservative_exact,
            nonlinear,
            DT,
        )
        nonlinear_energies.append(
            nonlinear_hamiltonian(
                *nonlinear_state, harmonic_omega2, nonlinear
            )
        )
    nonlinear_energy = torch.stack(nonlinear_energies)
    nonlinear_envelope = float(
        ((nonlinear_energy.max() - nonlinear_energy.min()) / nonlinear_energy[0]).item()
    )

    state32 = controller.new_state(device=device, dtype=torch.float32)
    zero_state, zero_clamps = controller._evolve_unchecked(state32, control_steps)
    zero_nonzero = int(torch.count_nonzero(zero_state.field).item())

    driven_state, heartbeat = controller.heartbeat(
        controller.new_state(device=device, dtype=torch.float32)
    )
    stability_energy = [controller.dynamic_energy(driven_state)]
    stability_drift: list[Tensor] = []
    stability_clamps = heartbeat.clamp_count
    for tick_index in range(stability_ticks):
        symbols = (
            ((37 + 17 * (tick_index // 8)) % 260,)
            if tick_index % 8 == 0
            else None
        )
        tick = controller.tick(driven_state, symbols=symbols, steps=8)
        driven_state = tick.state
        stability_energy.append(controller.dynamic_energy(driven_state))
        stability_drift.append(tick.input_energy_drift)
        stability_clamps += tick.clamp_count
    stability_energy_tensor = torch.stack(stability_energy)[:, 0]
    stability_drift_tensor = torch.stack(stability_drift)[:, 0]

    arrays = {
        "schema_id": np.asarray(TRACE_SCHEMA),
        "laplacian": to_numpy(laplacian),
        "expected_eigenvalues": to_numpy(expected_eigenvalues),
        "base_omega2": to_numpy(base_omega2),
        "coupling": to_numpy(coupling),
        "harmonic_omega2": to_numpy(harmonic_omega2),
        "alpha": to_numpy(exact[1]),
        "nonlinear": to_numpy(nonlinear),
        "common_initial": to_numpy(common),
        "differential_initial": to_numpy(differential),
        "common_velocity_initial": to_numpy(common_velocity),
        "differential_velocity_initial": to_numpy(differential_velocity),
        "free_position": to_numpy(free_position),
        "free_velocity": to_numpy(free_velocity),
        "free_split_common": to_numpy(free_split[0]),
        "free_split_differential": to_numpy(free_split[1]),
        "free_split_common_velocity": to_numpy(free_split[2]),
        "free_split_differential_velocity": to_numpy(free_split[3]),
        "spot_position": to_numpy(spot_position),
        "spot_velocity": to_numpy(spot_velocity),
        "spot_rk4_position": to_numpy(rk4_position),
        "spot_rk4_velocity": to_numpy(rk4_velocity),
        "conservative_final_position": to_numpy(conservative_position),
        "conservative_final_velocity": to_numpy(conservative_velocity),
        "conservative_energy": to_numpy(conservative_energy),
        "damped_final_position": to_numpy(damped_position),
        "damped_final_velocity": to_numpy(damped_velocity),
        "damped_energy": to_numpy(damped_energy),
        "nonlinear_final_common": to_numpy(nonlinear_state[0]),
        "nonlinear_final_differential": to_numpy(nonlinear_state[1]),
        "nonlinear_final_common_velocity": to_numpy(nonlinear_state[2]),
        "nonlinear_final_differential_velocity": to_numpy(nonlinear_state[3]),
        "nonlinear_energy": to_numpy(nonlinear_energy),
        "roundtrip_common": to_numpy(backward[0]),
        "roundtrip_differential": to_numpy(backward[1]),
        "roundtrip_common_velocity": to_numpy(backward[2]),
        "roundtrip_differential_velocity": to_numpy(backward[3]),
        "zero_final_field": to_numpy(zero_state.field),
        "stability_energy": to_numpy(stability_energy_tensor),
        "stability_drift": to_numpy(stability_drift_tensor),
        "stability_final_field": to_numpy(driven_state.field),
        "clamp_counts": np.asarray(
            (zero_clamps, stability_clamps), dtype=np.int64
        ),
    }
    metrics = {
        "operator_eigenvalue_max_error": operator_error,
        "parseval_energy_absolute_error": parseval_error,
        "free_drift_max_error": free_error,
        "split_no_term_relative_error": split_no_term_error,
        "independent_rk4_max_error": independent_rk4_error,
        "conservative_relative_energy_drift": conservative_drift,
        "damped_final_energy_ratio": float(
            (damped_energy[-1] / damped_energy[0]).item()
        ),
        "damped_max_positive_increment_ratio": damped_positive_increment,
        "nonlinear_roundtrip_relative_error": reversibility_error,
        "nonlinear_hamiltonian_relative_envelope": nonlinear_envelope,
        "zero_state_nonzero_count": zero_nonzero,
        "zero_state_clamp_count": zero_clamps,
        "driven_finite": bool(torch.isfinite(driven_state.field).all().item()),
        "driven_clamp_count": stability_clamps,
        "driven_maximum_dynamic_energy": float(stability_energy_tensor.max().item()),
        "driven_maximum_absolute_input_energy_drift": float(
            stability_drift_tensor.abs().max().item()
        ),
    }
    return metrics, arrays


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    device = torch.device(args.device)
    output_dir = args.output_dir.resolve()
    board_path = output_dir / BOARD_NAME
    trace_path = output_dir / TRACE_NAME
    missing = [str(path) for path in SOURCE_PATHS if not path.is_file()]
    if missing:
        raise L41RunnerError(f"missing bound source files: {missing!r}")
    hashes = {
        path.relative_to(ROOT).as_posix(): l30.sha256_file(path)
        for path in SOURCE_PATHS
    }
    board: dict[str, Any] = {
        "schema_id": BOARD_SCHEMA,
        "status": "INCOMPLETE",
        "operator_profile_id": "cassi.qi-exact-cyclic-strang.v1",
        "trace_schema_id": TRACE_SCHEMA,
        "preregistration_sha256": hashes[
            PREREGISTRATION.relative_to(ROOT).as_posix()
        ],
        "source_sha256": hashes,
        "device": {
            "requested": str(device),
            "type": device.type,
            "name": (
                torch.cuda.get_device_name(device)
                if device.type == "cuda" and torch.cuda.is_available()
                else str(device)
            ),
            "torch_version": torch.__version__,
            "hip_version": torch.version.hip,
            "control_dtype": "float64",
            "stability_dtype": "float32",
        },
        "constants": {
            "channels": CHANNELS,
            "mode_count": MODE_COUNT,
            "control_modes": CONTROL_MODES,
            "dt": DT,
            "control_steps": CONTROL_STEPS,
            "stability_ticks": STABILITY_TICKS,
            "stability_steps_per_tick": 8,
            "rk4_microsteps": 4096,
        },
        "trace": {"path": TRACE_NAME, "sha256": None},
        "arms": {},
    }
    l30.atomic_json(board_path, board)
    try:
        started = time.perf_counter()
        metrics, arrays = run_audit(device)
        l30.atomic_npz(trace_path, arrays)
        board["arms"]["canonical"] = metrics
        board["trace"] = {
            "path": TRACE_NAME,
            "sha256": l30.sha256_file(trace_path),
            "array_count": len(arrays),
        }
        board["resources"] = {
            "wall_seconds": float(time.perf_counter() - started),
            "peak_allocated_bytes": (
                int(torch.cuda.max_memory_allocated(device))
                if device.type == "cuda" and torch.cuda.is_available()
                else 0
            ),
        }
        board["status"] = "COMPLETE"
        l30.atomic_json(board_path, board)
    except Exception as exc:
        board["error"] = f"{type(exc).__name__}: {exc}"
        l30.atomic_json(board_path, board)
        raise
    print(board_path)
    print(trace_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
