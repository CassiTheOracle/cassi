"""Measure how the canonical paired-strand field carries multiscale information.

The multiscale packet view over balanced contiguous packet paths is a fixed,
disposable view of the canonical regional field. This runner asks what that view
measures about the field: which packet scales survive the canonical damping at
the production profile, how much of a driven scale's energy leaks to other
scales and channels, whether the common and counterflow channels stay separable
when one is driven, whether the view round-trips exactly and leaves the
canonical state untouched, whether repeated bounded drives stay inside the
declared work ledger, and whether the field returns to its pre-disturbance
coefficients after a disturbance.

Every number comes from the canonical packet and workspace APIs. The runner
declares one packet path, one scale ladder inside it, one drive budget, fixed
horizons and sample ticks, and reports the measured distributions. It maps
nothing onto any task, model, or downstream consumer.

These are canonical-field numerical measurements in controlled conditions. They
do not establish task-level memory utility, semantic content, or any advantage
over alternative architectures.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass, replace
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping, Sequence

import numpy as np

from cassi_resonant_field import (
    HELICAL_PACKET_CHANNELS,
    ResonantProfile,
    advance_workspace,
    analyze_helical_packet,
    apply_helical_packet_impulse,
    compose_helical_packets,
    helical_packet_channels,
    initial_workspace,
    inspect_workspace,
    split_helical_packet,
)

SCHEMA = "cassifi.fractal-memory-exploration.v1"
EVENT_KIND = "reasoning-work"
DRIVE_SIGNAL = (1.0, 0.0)
EQUAL_SPLIT_SIGNAL = (0.7071067811865476, 0.7071067811865476)
CHANNEL_COUNT = len(HELICAL_PACKET_CHANNELS)
PACKET_PORT_CHANNEL_NAMES = ("position-common", "position-counterflow", "momentum-common", "momentum-counterflow")
# The canonical impulse surface writes momentum only: every backend that lowers
# a packet impulse builds its direction with nonzero entries in the momentum
# lanes alone. The two position channels are therefore measured as recipients.
POSITION_CHANNELS_DRIVABLE = False
# Observational ceiling for the repeated-drive boundedness question, above the
# pump ceiling the advance path enforces (1e12) and far above every measured run.
BOUNDED_ENERGY_CEILING = 1.0

BOUNDARY = (
    "Canonical-field numerical measurements in controlled conditions only. "
    "Packet coefficients are disposable views of the live field; nothing here "
    "demonstrates task-level memory utility, semantic content, retrieval by a "
    "consumer, or any advantage over alternative architectures."
)

DEFINITIONS = {
    "declared_packet_path": (
        "one balanced contiguous port path fixed for the whole run; every packet "
        "view and every analysis frame in this receipt covers exactly its support"
    ),
    "scale_ladder": (
        "nested prefix paths of the declared packet path; the scale component at "
        "each rung is the constant (block-average) direction over that rung's "
        "support, so rung width is the driven block scale"
    ),
    "coefficients": (
        "orthonormal balanced-contiguous Haar coefficients of the four "
        "position/momentum common/counterflow channels over the packet support, "
        "shape [mode, channel]; coefficient_squared_norm is the packet energy"
    ),
    "retained_projection": (
        "(c_end . u)^2 / |c_start|^2 with u the unit drive image measured "
        "immediately after the deposit: the share of the deposited packet energy "
        "still lying along the driven direction at that tick"
    ),
    "total_energy_ratio": "|c_end|^2 / |c_start|^2 of the packet coefficients",
    "retained_projection_vs_total_energy_ratio": (
        "a small retained projection at a fine rung alongside a similar total "
        "energy ratio is loss of alignment with the driven direction, not loss "
        "of energy: the packet still holds that energy, distributed across other "
        "modes and channels of the same packet"
    ),
    "packet_digest_bit_identical_after_regrouping": (
        "whether analyze -> split -> compose reproduces the parent packet digest "
        "bit for bit; it is not required to, because the recomposed coefficients "
        "are re-derived from the reconstructed channels and so differ in their "
        "last bits, and the contract is reversible regrouping within the "
        "declared allowance, for which the measured coefficient error is the "
        "comparator"
    ),
    "leakage_matrix": (
        "packet energy per (scale level, channel) cell as a share of the "
        "deposited coefficient energy; levels are the Haar tree levels of the "
        "declared packet path, level 0 being the coarsest block average"
    ),
    "channel_transfer_matrix": (
        "share of the current packet energy landing in each response channel "
        "after driving one channel; the two position rows are prepared by a "
        "declared canonical composite (bounded momentum impulse plus a declared "
        "settle window) because no canonical impulse writes position lanes"
    ),
    "ledger_closure": (
        "independently measured canonical field energy change versus the sum of "
        "the ledger increments the canonical transitions recorded for the same "
        "phases; the residual is the closure error"
    ),
    "recovery_distance": (
        "||c(t) - c_reference|| in packet coefficient space, with c_reference "
        "measured before the disturbance; the live condition also carries a "
        "no-disturbance control arm so baseline drift is separable from decay"
    ),
    "view_integrity": (
        "maximum coefficient and channel reconstruction error of "
        "analyze -> split -> compose against the declared allowance, plus "
        "canonical state digests before and after analysis-only passes"
    ),
}


@dataclass(frozen=True)
class ExplorationConfig:
    """Declared measurement settings; every number in the receipt derives from these."""

    packet_path: str = ""
    scale_paths: tuple[str, ...] = ("", "L", "LL", "LLL")
    drive_budget: float = 1e-3
    horizon_ticks: int = 256
    retention_samples: tuple[int, ...] = (32, 64, 128, 256)
    channel_settle_ticks: int = 32
    channel_samples: tuple[int, ...] = (4, 8, 16, 32, 64, 128, 256)
    altered_settings: tuple[tuple[str, Mapping[str, Any]], ...] = (
        ("damping-half", {"damping": 0.006}),
        ("damping-double", {"damping": 0.024}),
        ("damping-zero", {"damping": 0.0}),
        ("quiet-damping-double", {"quiet_damping": 32.0}),
        ("activity-tau-short", {"activity_tau": 1.0}),
        ("descriptor-only", {"arithmetic": "declared-descriptor-label"}),
    )
    live_baseline_ticks: int = 48
    cycle_count: int = 8
    cycle_ticks: int = 8
    repeated_drive_budget: float = 1e-3
    recovery_horizon_ticks: int = 4096
    recovery_stride_ticks: int = 512
    small_disturbance: float = 1e-4
    large_disturbance: float = 5e-3
    reconstruction_allowance: float = 1e-14
    ledger_closure_allowance: float = 1e-12
    integrity_paths: tuple[str, ...] = ("", "L", "LL", "LLL", "LR", "RL")

    def __post_init__(self) -> None:
        if not self.retention_samples or max(self.retention_samples) != self.horizon_ticks:
            raise ValueError("retention samples must end at the declared horizon")
        if sorted(self.retention_samples) != list(self.retention_samples):
            raise ValueError("retention samples must be increasing")
        if not self.channel_samples:
            raise ValueError("channel samples are required")
        if self.recovery_horizon_ticks % self.recovery_stride_ticks:
            raise ValueError("the recovery horizon must be a whole number of strides")
        for name in ("drive_budget", "repeated_drive_budget", "small_disturbance", "large_disturbance"):
            value = float(getattr(self, name))
            if not 0.0 < value <= 1.0:
                raise ValueError(f"{name} must lie in (0,1]")
        if any(not rung.startswith(self.packet_path) for rung in self.scale_paths):
            raise ValueError("scale ladder rungs must descend from the declared packet path")

    def as_dict(self) -> dict[str, Any]:
        return {
            "packet_path": self.packet_path,
            "scale_paths": list(self.scale_paths),
            "drive_budget": self.drive_budget,
            "horizon_ticks": self.horizon_ticks,
            "retention_samples": list(self.retention_samples),
            "channel_settle_ticks": self.channel_settle_ticks,
            "channel_samples": list(self.channel_samples),
            "altered_settings": [[name, dict(values)] for name, values in self.altered_settings],
            "live_baseline_ticks": self.live_baseline_ticks,
            "cycle_count": self.cycle_count,
            "cycle_ticks": self.cycle_ticks,
            "repeated_drive_budget": self.repeated_drive_budget,
            "recovery_horizon_ticks": self.recovery_horizon_ticks,
            "recovery_stride_ticks": self.recovery_stride_ticks,
            "small_disturbance": self.small_disturbance,
            "large_disturbance": self.large_disturbance,
            "reconstruction_allowance": self.reconstruction_allowance,
            "ledger_closure_allowance": self.ledger_closure_allowance,
            "integrity_paths": list(self.integrity_paths),
        }


def canonical_json(value: Any) -> str:
    """Canonical JSON text for digesting: sorted keys, no insignificant space."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def receipt_digest(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def page_sha256(workspace: Any) -> str:
    """Digest of the canonical field page bytes alone (no profile descriptor)."""

    return hashlib.sha256(workspace.page_bytes).hexdigest()


def coefficients(workspace: Any, path: str) -> np.ndarray:
    packet = analyze_helical_packet(workspace, path=path)
    return np.asarray(packet["coefficients"], dtype=np.float64)


def _mode_levels(modes: Sequence[Mapping[str, Any]], packet_path: str) -> tuple[list[int], dict[str, list[int]]]:
    """Return the Haar level of each coefficient row and the block width per level."""

    levels: list[int] = []
    widths: dict[str, set[int]] = {}
    for index, mode in enumerate(modes):
        width = int(mode["stop"]) - int(mode["start"])
        if index == 0:
            level = 0
        else:
            level = len(str(mode["path"])) - len(packet_path) + 1
        levels.append(level)
        widths.setdefault(str(level), set()).add(width)
    return levels, {level: sorted(values) for level, values in widths.items()}


def _distribution(
    packet_coefficients: np.ndarray,
    levels: Sequence[int],
    level_widths: Mapping[str, Sequence[int]],
    reference_energy: float | None,
) -> dict[str, Any]:
    """Energy per channel and per (level, channel) cell, with declared normalizations."""

    energy = float(np.sum(packet_coefficients * packet_coefficients))
    channel_energy = [
        float(np.sum(packet_coefficients[:, channel] ** 2)) for channel in range(CHANNEL_COUNT)
    ]
    level_channel_energy: dict[str, list[float]] = {}
    for level in sorted({str(value) for value in levels}):
        rows = np.asarray([index for index, value in enumerate(levels) if str(value) == level])
        level_channel_energy[level] = [
            float(np.sum(packet_coefficients[rows, channel] ** 2))
            for channel in range(CHANNEL_COUNT)
        ]

    def shares(denominator: float) -> dict[str, Any]:
        return {
            "total": energy / denominator,
            "channel": [value / denominator for value in channel_energy],
            "level_channel": {
                level: [value / denominator for value in row]
                for level, row in level_channel_energy.items()
            },
        }

    return {
        "energy": energy,
        "channel_energy": channel_energy,
        "level_channel_energy": level_channel_energy,
        "level_widths": {level: list(values) for level, values in level_widths.items()},
        "share_of_current": shares(energy) if energy > 0.0 else None,
        "share_of_reference": shares(reference_energy)
        if reference_energy is not None and reference_energy > 0.0
        else None,
    }


def _frame(workspace: Any, path: str) -> dict[str, Any]:
    """The declared packet frame: support, ports, mode levels, coefficients."""

    packet = dict(analyze_helical_packet(workspace, path=path))
    packet_coefficients = np.asarray(packet["coefficients"], dtype=np.float64)
    levels, widths = _mode_levels(packet["modes"], path)
    start, stop = int(packet["support"]["start"]), int(packet["support"]["stop"])
    return {
        "path": path,
        "support": {"start": start, "stop": stop},
        "ports": list(range(start, stop)),
        "port_count": int(packet["port_count"]),
        "mode_count": len(packet["modes"]),
        "levels": levels,
        "level_widths": widths,
        "channels": list(packet["channels"]),
        "basis": packet["basis"],
        "basis_sha256": packet["basis_sha256"],
        "packet_sha256": packet["packet_sha256"],
        "source_state_sha256": packet["source_state_sha256"],
        "round_trip_error": float(packet["round_trip_error"]),
        "round_trip_allowance": float(packet["round_trip_allowance"]),
        "coefficient_squared_norm": float(packet["coefficient_squared_norm"]),
        "coefficients": packet_coefficients,
    }


def _drive(
    workspace: Any,
    *,
    path: str,
    component: str,
    flow_signal: Sequence[float],
    budget: float,
    summary: bool = False,
) -> tuple[Any, dict[str, Any]]:
    successor, receipt = apply_helical_packet_impulse(
        workspace,
        path=path,
        component=component,
        flow_signal=list(flow_signal),
        work_budget=budget,
        evidence_tick=workspace.evidence_tick,
        event_kind=EVENT_KIND,
    )
    if summary:
        receipt = {
            key: receipt[key]
            for key in (
                "schema",
                "accepted",
                "event_kind",
                "basis_sha256",
                "path",
                "component",
                "support",
                "mode",
                "flow_signal",
                "requested_work",
                "applied_work",
                "impulse_amount",
                "balance_defect",
                "energy_roundoff_allowance",
                "source_state_sha256",
                "state_sha256",
            )
        }
    return successor, receipt


def _packet_run(workspace: Any, config: ExplorationConfig, samples: Sequence[int]) -> dict[str, Any]:
    """Advance unforced through the declared sample ticks, reading the packet each time."""

    rows: list[dict[str, Any]] = []
    current = workspace
    previous = 0
    for tick in samples:
        current, advance = advance_workspace(
            current, ticks=int(tick) - previous, source_enabled=False
        )
        previous = int(tick)
        rows.append(
            {
                "tick": int(tick),
                "dissipated_work": float(advance["dissipated_work"]),
                "residual_work": float(advance["residual_work"]),
                "maximum_residual_norm": float(advance["maximum_residual_norm"]),
                "nonlinear_iterations": int(advance["nonlinear_iterations"]),
                "state_sha256": current.state_sha256,
                "page_sha256": page_sha256(current),
                "coefficients": coefficients(current, config.packet_path),
            }
        )
    return {"rows": rows, "final": current}


def stage_scale_retention(config: ExplorationConfig, profile: ResonantProfile) -> dict[str, Any]:
    """(a) Deposit one bounded impulse per scale rung, then read retention and leakage."""

    arms: list[dict[str, Any]] = []
    for index, path in enumerate(config.scale_paths):
        name = f"scale-{index}"
        workspace, impulse = _drive(
            initial_workspace(profile),
            path=path,
            component="scale",
            flow_signal=DRIVE_SIGNAL,
            budget=config.drive_budget,
            summary=True,
        )
        start_frame = _frame(workspace, config.packet_path)
        start_coefficients = start_frame["coefficients"]
        start_energy = float(np.sum(start_coefficients * start_coefficients))
        direction = start_coefficients.reshape(-1)
        norm = float(np.linalg.norm(direction))
        unit = direction / norm if norm > 0.0 else direction
        levels = start_frame["levels"]
        widths = start_frame["level_widths"]
        driven_rows = [
            {
                "mode": row_index,
                "level": levels[row_index],
                "channels": [
                    channel
                    for channel in range(CHANNEL_COUNT)
                    if abs(start_coefficients[row_index, channel]) > 0.0
                ],
            }
            for row_index in range(start_coefficients.shape[0])
            if float(np.sum(np.abs(start_coefficients[row_index]))) > 0.0
        ]
        run = _packet_run(workspace, config, config.retention_samples)
        samples: list[dict[str, Any]] = []
        for row in run["rows"]:
            current = row.pop("coefficients")
            projection = float(np.dot(current.reshape(-1), unit))
            current_energy = float(np.sum(current * current))
            samples.append(
                {
                    **row,
                    "total_energy_ratio": current_energy / start_energy,
                    "retained_projection": (projection * projection) / start_energy,
                    "retained_amplitude_ratio": abs(projection) / norm,
                    "distribution": _distribution(current, levels, widths, start_energy),
                }
            )
        arms.append(
            {
                "arm": name,
                "scale_path": path,
                "scale_support": impulse["support"],
                "scale_width": int(impulse["support"]["stop"]) - int(impulse["support"]["start"]),
                "component": "scale",
                "flow_signal": impulse["flow_signal"],
                "requested_work": impulse["requested_work"],
                "impulse": impulse,
                "start_state_sha256": workspace.state_sha256,
                "start_page_sha256": page_sha256(workspace),
                "start_distribution": _distribution(start_coefficients, levels, widths, start_energy),
                "driven_packet_rows": driven_rows,
                "samples": samples,
                "final_state_sha256": run["final"].state_sha256,
            }
        )
    return {
        "declared": {
            "analysis_frame_path": config.packet_path,
            "drive_budget": config.drive_budget,
            "horizon_ticks": config.horizon_ticks,
            "sample_ticks": list(config.retention_samples),
            "drive_signal": list(DRIVE_SIGNAL),
            "normalization": "share_of_reference is relative to the deposited coefficient energy",
        },
        "frame": {
            key: value
            for key, value in _frame(initial_workspace(profile), config.packet_path).items()
            if key != "coefficients"
        },
        "arms": arms,
    }


def stage_channel_transfer(config: ExplorationConfig, profile: ResonantProfile) -> dict[str, Any]:
    """(b) Drive one channel at a time and measure cross-channel transfer."""

    arms: list[dict[str, Any]] = []
    for arm_name, driven, signal, settle in (
        ("momentum-common", "momentum-common", DRIVE_SIGNAL, 0),
        ("momentum-counterflow", "momentum-counterflow", (0.0, 1.0), 0),
        ("momentum-equal-split", None, EQUAL_SPLIT_SIGNAL, 0),
        ("position-common-prepared", "position-common", DRIVE_SIGNAL, config.channel_settle_ticks),
        (
            "position-counterflow-prepared",
            "position-counterflow",
            (0.0, 1.0),
            config.channel_settle_ticks,
        ),
    ):
        workspace, impulse = _drive(
            initial_workspace(profile),
            path=config.packet_path,
            component="scale",
            flow_signal=signal,
            budget=config.drive_budget,
            summary=True,
        )
        preparation = None
        if settle:
            workspace, preparation = advance_workspace(
                workspace, ticks=settle, source_enabled=False
            )
        frame = _frame(workspace, config.packet_path)
        start_coefficients = frame["coefficients"]
        start_energy = float(np.sum(start_coefficients * start_coefficients))
        start_distribution = _distribution(
            start_coefficients, frame["levels"], frame["level_widths"], start_energy
        )
        dominant = int(np.argmax(start_distribution["channel_energy"]))
        run = _packet_run(workspace, config, config.channel_samples)
        samples: list[dict[str, Any]] = []
        for row in run["rows"]:
            current = row.pop("coefficients")
            samples.append(
                {
                    **row,
                    "distribution": _distribution(
                        current, frame["levels"], frame["level_widths"], start_energy
                    ),
                }
            )
        arms.append(
            {
                "arm": arm_name,
                "declared_driven_channel": driven,
                "flow_signal": impulse["flow_signal"],
                "prepared_by": (
                    "bounded momentum impulse only"
                    if not settle
                    else f"bounded momentum impulse plus {settle} declared settle ticks of unforced advance"
                ),
                "preparation_settle_ticks": settle,
                "preparation_receipt": None
                if preparation is None
                else {
                    "ticks": preparation["ticks"],
                    "dissipated_work": float(preparation["dissipated_work"]),
                    "state_sha256": preparation["state_sha256"],
                },
                "impulse": impulse,
                "prepared_state_sha256": workspace.state_sha256,
                "prepared_page_sha256": page_sha256(workspace),
                "driven_channel_index": HELICAL_PACKET_CHANNELS.index(driven) if driven else None,
                "prepared_distribution": start_distribution,
                "prepared_dominant_channel": HELICAL_PACKET_CHANNELS[dominant],
                "prepared_dominant_share": start_distribution["share_of_current"]["channel"][dominant],
                "prepared_dominant_matches_declaration": (
                    driven is not None and HELICAL_PACKET_CHANNELS[dominant] == driven
                ),
                "samples": samples,
                "final_state_sha256": run["final"].state_sha256,
            }
        )

    horizon = max(config.channel_samples)
    transfer = {name: {} for name in PACKET_PORT_CHANNEL_NAMES}
    for arm in arms:
        if arm["declared_driven_channel"] is None:
            continue
        row = arm["samples"][-1]["distribution"]["share_of_current"]["channel"]
        transfer[arm["declared_driven_channel"]] = {
            name: row[index] for index, name in enumerate(HELICAL_PACKET_CHANNELS)
        }
    swapped = {
        "position-common": "position-counterflow",
        "position-counterflow": "position-common",
        "momentum-common": "momentum-counterflow",
        "momentum-counterflow": "momentum-common",
    }
    common = transfer["momentum-common"]
    counterflow = transfer["momentum-counterflow"]
    return {
        "declared": {
            "analysis_frame_path": config.packet_path,
            "drive_component": "scale",
            "drive_budget": config.drive_budget,
            "sample_ticks": list(config.channel_samples),
            "transfer_horizon_ticks": horizon,
            "position_channels_drivable": POSITION_CHANNELS_DRIVABLE,
            "position_preparation": (
                "no canonical impulse writes position lanes; the two position arms "
                "are prepared by a declared canonical composite and their prepared "
                "channel distribution is recorded"
            ),
        },
        "arms": arms,
        "transfer_matrix": transfer,
        "swap_symmetry_max_abs_residual": max(
            abs(common[name] - counterflow[swapped[name]])
            for name in PACKET_PORT_CHANNEL_NAMES
        ),
    }


def retention_arm(
    config: ExplorationConfig,
    profile: ResonantProfile,
    scale_path: str,
    horizon_ticks: int,
    budget: float,
) -> dict[str, Any]:
    """One endpoint retention measurement: deposit, advance the horizon, read the frame."""

    workspace, impulse = _drive(
        initial_workspace(profile),
        path=scale_path,
        component="scale",
        flow_signal=DRIVE_SIGNAL,
        budget=budget,
        summary=True,
    )
    start_coefficients = coefficients(workspace, config.packet_path)
    start_energy = float(np.sum(start_coefficients * start_coefficients))
    direction = start_coefficients.reshape(-1)
    unit = direction / float(np.linalg.norm(direction))
    current, advance = advance_workspace(workspace, ticks=horizon_ticks, source_enabled=False)
    end_coefficients = coefficients(current, config.packet_path)
    projection = float(np.dot(end_coefficients.reshape(-1), unit))
    end_energy = float(np.sum(end_coefficients * end_coefficients))
    frame = _frame(current, config.packet_path)
    return {
        "scale_path": scale_path,
        "horizon_ticks": horizon_ticks,
        "requested_work": budget,
        "impulse": impulse,
        "start_coefficient_squared_norm": start_energy,
        "end_coefficient_squared_norm": end_energy,
        "retained_projection": (projection * projection) / start_energy,
        "total_energy_ratio": end_energy / start_energy,
        "end_distribution": _distribution(
            end_coefficients, frame["levels"], frame["level_widths"], start_energy
        ),
        "state_sha256": current.state_sha256,
        "page_sha256": page_sha256(current),
        "advance_dissipated_work": float(advance["dissipated_work"]),
        "advance_balance_defect": float(advance["balance_defect"]),
    }


def stage_profile_dependence(config: ExplorationConfig, profile: ResonantProfile) -> dict[str, Any]:
    """(c) Repeat the endpoint retention measurement under altered declared settings."""

    profiles: list[tuple[str, Mapping[str, Any], ResonantProfile]] = [("default", {}, profile)]
    for name, values in config.altered_settings:
        profiles.append((name, dict(values), replace(profile, **dict(values))))
    arms: list[dict[str, Any]] = []
    for name, values, candidate in profiles:
        arms.append(
            {
                "arm": name,
                "settings": values,
                "profile_sha256": hashlib.sha256(canonical_json(candidate.as_dict()).encode()).hexdigest(),
                "rungs": [
                    retention_arm(config, candidate, path, config.horizon_ticks, config.drive_budget)
                    for path in config.scale_paths
                ],
            }
        )
    default = arms[0]
    comparisons = []
    for arm in arms[1:]:
        per_rung = []
        for base_rung, arm_rung in zip(default["rungs"], arm["rungs"]):
            per_rung.append(
                {
                    "scale_path": base_rung["scale_path"],
                    "total_energy_ratio_delta": arm_rung["total_energy_ratio"]
                    - base_rung["total_energy_ratio"],
                    "retained_projection_ratio": (
                        arm_rung["retained_projection"] / base_rung["retained_projection"]
                        if base_rung["retained_projection"] > 0.0
                        else None
                    ),
                    "page_identical_to_default": arm_rung["page_sha256"] == base_rung["page_sha256"],
                    "state_digest_identical_to_default": arm_rung["state_sha256"]
                    == base_rung["state_sha256"],
                }
            )
        comparisons.append(
            {
                "arm": arm["arm"],
                "settings": arm["settings"],
                "rungs": per_rung,
                "any_page_identical_to_default": all(
                    row["page_identical_to_default"] for row in per_rung
                ),
            }
        )
    return {
        "declared": {
            "horizon_ticks": config.horizon_ticks,
            "drive_budget": config.drive_budget,
            "scale_paths": list(config.scale_paths),
            "note": (
                "settings that do not enter the unforced advance path leave the "
                "canonical page bit-identical; the state digest still changes "
                "because it covers the declared profile descriptor"
            ),
        },
        "arms": arms,
        "comparisons": comparisons,
    }


def stage_view_integrity(config: ExplorationConfig, profile: ResonantProfile) -> dict[str, Any]:
    """(d) Round-trip the packet view and confirm analysis-only passes are inert."""

    baseline, _ = advance_workspace(initial_workspace(profile), ticks=config.live_baseline_ticks, source_enabled=True)
    baseline, _ = _drive(
        baseline,
        path=config.packet_path,
        component="scale",
        flow_signal=(0.6, -0.8),
        budget=config.drive_budget,
    )
    state_before = baseline.state_sha256
    page_before = page_sha256(baseline)
    rows: list[dict[str, Any]] = []
    for path in config.integrity_paths:
        parent = dict(analyze_helical_packet(baseline, path=path))
        left, right = split_helical_packet(parent)
        recomposed = compose_helical_packets(left, right)
        parent_coefficients = np.asarray(parent["coefficients"], dtype=np.float64)
        recomposed_coefficients = np.asarray(recomposed["coefficients"], dtype=np.float64)
        parent_channels = helical_packet_channels(parent)
        recomposed_channels = helical_packet_channels(recomposed)
        # Deeper regrouping: split the left sibling again, then compose the pair
        # back into the left sibling before composing the parent.
        deep_error = None
        if int(left["support"]["stop"]) - int(left["support"]["start"]) > 1:
            left_inner, right_inner = split_helical_packet(left)
            regrouped_parent = compose_helical_packets(
                compose_helical_packets(left_inner, right_inner), right
            )
            regrouped_coefficients = np.asarray(regrouped_parent["coefficients"], dtype=np.float64)
            deep_error = float(
                np.max(np.abs(parent_coefficients - regrouped_coefficients), initial=0.0)
            )
        rows.append(
            {
                "path": path,
                "support": parent["support"],
                "parent_round_trip_error": float(parent["round_trip_error"]),
                "parent_round_trip_allowance": float(parent["round_trip_allowance"]),
                "coefficient_reconstruction_error": float(
                    np.max(np.abs(parent_coefficients - recomposed_coefficients), initial=0.0)
                ),
                "channel_reconstruction_error": float(
                    np.max(np.abs(parent_channels - recomposed_channels), initial=0.0)
                ),
                "coefficient_squared_norm_delta": float(
                    abs(
                        float(np.sum(parent_coefficients**2))
                        - float(np.sum(recomposed_coefficients**2))
                    )
                ),
                "packet_digest_bit_identical_after_regrouping": bool(
                    recomposed["packet_sha256"] == parent["packet_sha256"]
                ),
                "deep_regrouping_max_coefficient_error": deep_error,
                "cross_source_composition_refused": (
                    _refuses_mixed_sources(left, profile) if path == config.packet_path else None
                ),
            }
        )
    state_after = baseline.state_sha256
    page_after = page_sha256(baseline)
    worst = max(row["coefficient_reconstruction_error"] for row in rows)
    deep_errors = [
        row["deep_regrouping_max_coefficient_error"]
        for row in rows
        if row["deep_regrouping_max_coefficient_error"] is not None
    ]
    worst_deep = max(deep_errors) if deep_errors else None
    return {
        "declared": {
            "reconstruction_allowance": config.reconstruction_allowance,
            "paths": list(config.integrity_paths),
            "comparison": (
                "maximum absolute coefficient and channel error of "
                "analyze -> split -> compose against the parent view"
            ),
        },
        "source_state_sha256": state_before,
        "source_page_sha256": page_before,
        "analysis_only_state_sha256": state_after,
        "analysis_only_page_sha256": page_after,
        "state_sha256_unchanged": state_before == state_after,
        "page_sha256_unchanged": page_before == page_after,
        "rows": rows,
        "maximum_coefficient_reconstruction_error": worst,
        "maximum_deep_regrouping_error": worst_deep,
        "within_declared_allowance": bool(
            worst <= config.reconstruction_allowance
            and (worst_deep is None or worst_deep <= config.reconstruction_allowance)
            and all(
                row["parent_round_trip_error"] <= row["parent_round_trip_allowance"]
                for row in rows
            )
        ),
    }


def _refuses_mixed_sources(left: Mapping[str, Any], profile: ResonantProfile) -> bool:
    """Confirm composition still rejects siblings taken from a different field state."""

    other, _receipt = _drive(
        initial_workspace(profile),
        path="",
        component="scale",
        flow_signal=DRIVE_SIGNAL,
        budget=1e-4,
    )
    _other_left, other_right = split_helical_packet(analyze_helical_packet(other))
    try:
        compose_helical_packets(left, other_right)
    except ValueError:
        return True
    return False


def stage_repeated_drive(config: ExplorationConfig, profile: ResonantProfile) -> dict[str, Any]:
    """(e) Deposit the bounded impulse periodically and audit the work ledger."""

    workspace = initial_workspace(profile)
    start_energy = float(inspect_workspace(workspace)["energy"])
    cycles: list[dict[str, Any]] = []
    for cycle in range(1, config.cycle_count + 1):
        workspace, impulse = _drive(
            workspace,
            path=config.packet_path,
            component="scale",
            flow_signal=DRIVE_SIGNAL,
            budget=config.repeated_drive_budget,
            summary=True,
        )
        workspace, advance = advance_workspace(
            workspace, ticks=config.cycle_ticks, source_enabled=False
        )
        measured = float(inspect_workspace(workspace)["energy"])
        page = workspace.field.reshape(-1)
        cycles.append(
            {
                "cycle": cycle,
                "field_ticks": workspace.field_ticks,
                "measured_energy": measured,
                "ledger_stored_energy": float(workspace.ledger["stored_energy"]),
                "ledger_stored_energy_minus_measured": float(workspace.ledger["stored_energy"])
                - measured,
                "impulse_applied_work": float(impulse["applied_work"]),
                "impulse_amount": float(impulse["impulse_amount"]),
                "impulse_balance_defect": float(impulse["balance_defect"]),
                "impulse_allowance": float(impulse["energy_roundoff_allowance"]),
                "advance_dissipated_work": float(advance["dissipated_work"]),
                "advance_residual_work": float(advance["residual_work"]),
                "advance_positive_heartbeat_work": float(advance["positive_heartbeat_work"]),
                "advance_extracted_heartbeat_work": float(advance["extracted_heartbeat_work"]),
                "advance_balance_defect": float(advance["balance_defect"]),
                "advance_maximum_residual_norm": float(advance["maximum_residual_norm"]),
                "ledger": {key: float(value) for key, value in workspace.ledger.items()},
                "state_finite": bool(np.isfinite(page).all()),
                "energy_below_ceiling": bool(measured < BOUNDED_ENERGY_CEILING),
                "page_sha256": page_sha256(workspace),
                "state_sha256": workspace.state_sha256,
            }
        )
    final_energy = float(inspect_workspace(workspace)["energy"])
    ledger = {key: float(value) for key, value in workspace.ledger.items()}
    increments = {
        "positive_heartbeat_work": ledger["positive_heartbeat_work"],
        "extracted_heartbeat_work": -ledger["extracted_heartbeat_work"],
        "dissipated_work": -ledger["dissipated_work"],
        "numerical_dissipated_work": -ledger["numerical_dissipated_work"],
        "residual_work": ledger["residual_work"],
        "parameter_work": ledger["parameter_work"],
        "boundary_work": ledger["boundary_work"],
        "helical_packet_work": ledger["helical_packet_work"],
        "balance_defect": ledger["balance_defect"],
    }
    measured_change = final_energy - start_energy
    closure_residual = measured_change - sum(increments.values())
    scale = max(1.0, abs(measured_change), abs(final_energy), abs(start_energy))
    return {
        "declared": {
            "packet_path": config.packet_path,
            "component": "scale",
            "flow_signal": list(DRIVE_SIGNAL),
            "budget_per_cycle": config.repeated_drive_budget,
            "cycles": config.cycle_count,
            "ticks_per_cycle": config.cycle_ticks,
            "total_ticks": config.cycle_count * config.cycle_ticks,
            "bounded_energy_ceiling": BOUNDED_ENERGY_CEILING,
            "closure_allowance_relative": config.ledger_closure_allowance,
            "closure_definition": (
                "(measured_final_energy - measured_initial_energy) - sum(ledger increments)"
            ),
        },
        "initial_measured_energy": start_energy,
        "final_measured_energy": final_energy,
        "final_ledger": ledger,
        "ledger_increments": increments,
        "measured_energy_change": measured_change,
        "ledger_increment_sum": sum(increments.values()),
        "closure_residual": closure_residual,
        "closure_residual_relative": closure_residual / scale,
        "closure_within_allowance": bool(
            abs(closure_residual) <= config.ledger_closure_allowance * scale
        ),
        "accumulated_balance_defect": ledger["balance_defect"],
        "maximum_abs_phase_defect": max(
            max(abs(row["impulse_balance_defect"]), abs(row["advance_balance_defect"]))
            for row in cycles
        ),
        "state_stayed_bounded": bool(
            all(row["state_finite"] and row["energy_below_ceiling"] for row in cycles)
        ),
        "cycles": cycles,
        "final_state_sha256": workspace.state_sha256,
        "final_page_sha256": page_sha256(workspace),
    }


def _recovery_arm(
    config: ExplorationConfig,
    reference: Any,
    reference_coefficients: np.ndarray,
    reference_norm: float,
    budget: float,
    label: str,
) -> dict[str, Any]:
    workspace = reference
    impulse = None
    if budget > 0.0:
        workspace, impulse = _drive(
            reference,
            path=config.packet_path,
            component="scale",
            flow_signal=DRIVE_SIGNAL,
            budget=budget,
            summary=True,
        )
    initial = coefficients(workspace, config.packet_path)
    initial_distance = float(np.linalg.norm(initial - reference_coefficients))
    strides = config.recovery_horizon_ticks // config.recovery_stride_ticks
    samples = [
        {
            "tick": 0,
            "distance": initial_distance,
            "relative_to_disturbance": 1.0 if initial_distance > 0.0 else None,
            "relative_to_reference": initial_distance / reference_norm
            if reference_norm > 0.0
            else None,
            "coefficient_norm": float(np.linalg.norm(initial)),
            "dissipated_work": 0.0,
        }
    ]
    current = workspace
    for index in range(1, strides + 1):
        current, advance = advance_workspace(
            current, ticks=config.recovery_stride_ticks, source_enabled=False
        )
        current_coefficients = coefficients(current, config.packet_path)
        distance = float(np.linalg.norm(current_coefficients - reference_coefficients))
        samples.append(
            {
                "tick": index * config.recovery_stride_ticks,
                "distance": distance,
                "relative_to_disturbance": distance / initial_distance
                if initial_distance > 0.0
                else None,
                "relative_to_reference": distance / reference_norm
                if reference_norm > 0.0
                else None,
                "coefficient_norm": float(np.linalg.norm(current_coefficients)),
                "dissipated_work": float(advance["dissipated_work"]),
            }
        )
    distances = [row["distance"] for row in samples]
    minimum = min(distances)
    disturbed = initial_distance > 0.0
    return {
        "arm": label,
        "disturbance_budget": budget,
        "impulse": impulse,
        "initial_distance": initial_distance,
        "final_distance": distances[-1],
        "minimum_distance": minimum,
        "minimum_tick": samples[distances.index(minimum)]["tick"],
        # An arm with no disturbance has no decay to report: null, never False,
        # so a silent control cannot read as a disturbance that failed to decay.
        "distance_decreased": bool(distances[-1] < distances[0]) if disturbed else None,
        "monotone_decreasing": (
            bool(
                all(
                    later <= earlier + 1e-15 * max(1.0, earlier)
                    for earlier, later in zip(distances, distances[1:])
                )
            )
            if disturbed
            else None
        ),
        "recovered_fraction": (1.0 - distances[-1] / initial_distance) if disturbed else None,
        "samples": samples,
        "final_state_sha256": current.state_sha256,
        "final_page_sha256": page_sha256(current),
    }


def stage_recovery(config: ExplorationConfig, profile: ResonantProfile) -> dict[str, Any]:
    """(f) Measure the distance from the pre-disturbance coefficients over the horizon."""

    resting = initial_workspace(profile)
    resting_coefficients = coefficients(resting, config.packet_path)
    resting_arms = [
        _recovery_arm(
            config,
            resting,
            resting_coefficients,
            0.0,
            budget,
            label,
        )
        for label, budget in (
            ("control", 0.0),
            ("small-disturbance", config.small_disturbance),
            ("large-disturbance", config.large_disturbance),
        )
    ]
    live, _ = advance_workspace(
        initial_workspace(profile), ticks=config.live_baseline_ticks, source_enabled=True
    )
    live_coefficients = coefficients(live, config.packet_path)
    live_norm = float(np.linalg.norm(live_coefficients))
    live_arms = [
        _recovery_arm(config, live, live_coefficients, live_norm, budget, label)
        for label, budget in (
            ("control", 0.0),
            ("small-disturbance", config.small_disturbance),
            ("large-disturbance", config.large_disturbance),
        )
    ]
    for arms in (resting_arms, live_arms):
        control = arms[0]["final_distance"]
        for arm in arms:
            arm["final_excess_over_control"] = arm["final_distance"] - control
    return {
        "declared": {
            "packet_path": config.packet_path,
            "component": "scale",
            "flow_signal": list(DRIVE_SIGNAL),
            "horizon_ticks": config.recovery_horizon_ticks,
            "stride_ticks": config.recovery_stride_ticks,
            "small_disturbance": config.small_disturbance,
            "large_disturbance": config.large_disturbance,
            "live_baseline_ticks": config.live_baseline_ticks,
            "distance": "||c(t) - c_reference|| in packet coefficient space",
        },
        "resting": {
            "reference_definition": "the untouched zero field (no source, no drive)",
            "reference_coefficient_norm": float(np.linalg.norm(resting_coefficients)),
            "arms": resting_arms,
        },
        "live": {
            "reference_definition": (
                f"the same canonical field after {config.live_baseline_ticks} sourced ticks; "
                "every arm then relaxes unforced so baseline drift is visible in the control"
            ),
            "reference_coefficient_norm": live_norm,
            "reference_state_sha256": live.state_sha256,
            "arms": live_arms,
        },
    }


def declared_block(config: ExplorationConfig, profile: ResonantProfile) -> dict[str, Any]:
    frame = _frame(initial_workspace(profile), config.packet_path)
    ladder = []
    for path in config.scale_paths:
        packet = dict(analyze_helical_packet(initial_workspace(profile), path=path))
        ladder.append(
            {
                "path": path,
                "support": packet["support"],
                "width": int(packet["support"]["stop"]) - int(packet["support"]["start"]),
                "ports": list(range(int(packet["support"]["start"]), int(packet["support"]["stop"]))),
            }
        )
    return {
        "packet_schema": frame["basis"],
        "packet_channels": list(HELICAL_PACKET_CHANNELS),
        "position_channels_drivable": POSITION_CHANNELS_DRIVABLE,
        "declared_packet_path": config.packet_path,
        "declared_packet_frame": {
            key: value for key, value in frame.items() if key != "coefficients"
        },
        "scale_ladder": ladder,
        "chain_ports": {"start": frame["support"]["start"], "stop": frame["support"]["stop"]},
        "profile": profile.as_dict(),
        "ledger_terms": [
            "positive_heartbeat_work",
            "extracted_heartbeat_work",
            "dissipated_work",
            "numerical_dissipated_work",
            "residual_work",
            "parameter_work",
            "boundary_work",
            "helical_packet_work",
            "balance_defect",
            "stored_energy",
        ],
        "config": config.as_dict(),
        "definitions": DEFINITIONS,
    }


def reading_block(body: Mapping[str, Any]) -> dict[str, Any]:
    """The headline measured numbers, in the order the questions were asked."""

    retention = body["scale_retention"]
    channels = body["channel_transfer"]
    return {
        "scale_retention_at_horizon": {
            arm["scale_path"]: {
                "scale_width": arm["scale_width"],
                "retained_projection": arm["samples"][-1]["retained_projection"],
                "total_energy_ratio": arm["samples"][-1]["total_energy_ratio"],
                "channel_shares_of_deposit": arm["samples"][-1]["distribution"][
                    "share_of_reference"
                ]["channel"],
            }
            for arm in retention["arms"]
        },
        "leakage_matrices": {
            arm["scale_path"]: {
                "at_deposit": arm["start_distribution"]["share_of_reference"]["level_channel"],
                "at_horizon": arm["samples"][-1]["distribution"]["share_of_reference"][
                    "level_channel"
                ],
            }
            for arm in retention["arms"]
        },
        "channel_transfer_matrix": channels["transfer_matrix"],
        "channel_swap_symmetry_max_abs_residual": channels["swap_symmetry_max_abs_residual"],
        "profile_dependence": {
            arm["arm"]: {
                rung["scale_path"]: rung["total_energy_ratio"] for rung in arm["rungs"]
            }
            for arm in body["profile_dependence"]["arms"]
        },
        "profile_comparisons": body["profile_dependence"]["comparisons"],
        "view_integrity": {
            "maximum_coefficient_reconstruction_error": body["view_integrity"][
                "maximum_coefficient_reconstruction_error"
            ],
            "maximum_deep_regrouping_error": body["view_integrity"][
                "maximum_deep_regrouping_error"
            ],
            "declared_allowance": body["view_integrity"]["declared"][
                "reconstruction_allowance"
            ],
            "within_declared_allowance": body["view_integrity"]["within_declared_allowance"],
            "analysis_only_state_unchanged": body["view_integrity"]["state_sha256_unchanged"],
            "analysis_only_page_unchanged": body["view_integrity"]["page_sha256_unchanged"],
        },
        "repeated_drive": {
            "measured_energy_change": body["repeated_drive"]["measured_energy_change"],
            "ledger_increment_sum": body["repeated_drive"]["ledger_increment_sum"],
            "closure_residual": body["repeated_drive"]["closure_residual"],
            "closure_residual_relative": body["repeated_drive"]["closure_residual_relative"],
            "closure_within_allowance": body["repeated_drive"]["closure_within_allowance"],
            "accumulated_balance_defect": body["repeated_drive"]["accumulated_balance_defect"],
            "state_stayed_bounded": body["repeated_drive"]["state_stayed_bounded"],
            "final_measured_energy": body["repeated_drive"]["final_measured_energy"],
        },
        "recovery": {
            condition: {
                arm["arm"]: {
                    "initial_distance": arm["initial_distance"],
                    "final_distance": arm["final_distance"],
                    "minimum_distance": arm["minimum_distance"],
                    "distance_decreased": arm["distance_decreased"],
                    "monotone_decreasing": arm["monotone_decreasing"],
                    "recovered_fraction": arm["recovered_fraction"],
                    "final_excess_over_control": arm["final_excess_over_control"],
                }
                for arm in body["recovery"][condition]["arms"]
            }
            for condition in ("resting", "live")
        },
    }


def measure(config: ExplorationConfig, profile: ResonantProfile | None = None) -> dict[str, Any]:
    """Run every declared stage and return the receipt body without its digest."""

    base = profile or ResonantProfile()
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "declared": declared_block(config, base),
        "scale_retention": stage_scale_retention(config, base),
        "channel_transfer": stage_channel_transfer(config, base),
        "profile_dependence": stage_profile_dependence(config, base),
        "view_integrity": stage_view_integrity(config, base),
        "repeated_drive": stage_repeated_drive(config, base),
        "recovery": stage_recovery(config, base),
    }
    body["reading"] = reading_block(body)
    body["boundary"] = BOUNDARY
    return body


def build_receipt(config: ExplorationConfig, profile: ResonantProfile | None = None) -> dict[str, Any]:
    body = measure(config, profile)
    return {**body, "receipt_digest": receipt_digest(body)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("_diag/fractal-memory/exploration.json")
    )
    arguments = parser.parse_args()
    config = ExplorationConfig()
    started = perf_counter()
    receipt = build_receipt(config)
    elapsed = perf_counter() - started
    print(json.dumps(receipt["reading"], indent=1, sort_keys=True))
    print(json.dumps({"boundary": receipt["boundary"]}, indent=1, sort_keys=True))
    print(f"declared packet path: {config.packet_path!r} over ports "
          f"{receipt['declared']['chain_ports']['start']}..{receipt['declared']['chain_ports']['stop'] - 1}")
    print(f"receipt_digest: {receipt['receipt_digest']}")
    print(f"elapsed_seconds: {elapsed:.2f}")
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(receipt, indent=1, sort_keys=True), encoding="utf-8"
    )
    print(f"receipt: {arguments.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
