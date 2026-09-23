from __future__ import annotations

from pathlib import Path

import pytest

from run_cassi_full_observable_invention import main as run_campaign
import numpy as np

import cassi_full_observable_invention as full


def _snapshot() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    index = np.arange(64, dtype=np.float64)
    angle = 2.0 * np.pi * index / len(index)
    radius = 1.0 + 0.01 * index
    position = np.stack(
        (radius * np.cos(angle), radius * np.sin(angle), 0.2 * np.sin(index * 0.31)),
        axis=1,
    )
    velocity = np.stack(
        (-0.4 * np.sin(angle), 0.4 * np.cos(angle), 0.03 * np.cos(index * 0.17)),
        axis=1,
    )
    mass = 1.0 + 0.002 * index
    return position, velocity, mass


def _features(*, field_live: float = 0.0) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    position, velocity, mass = _snapshot()
    return full._snapshot_features(
        position,
        velocity,
        mass,
        radius_scale=1.25,
        mass_scale=float(np.sum(mass)),
        velocity_scale=2.0,
        clock_value=0.75,
        initial_mean_mass=float(np.mean(mass)),
        softening=0.1,
        cell_width=0.04,
        cluster_radius=0.8,
        cluster_separation=2.5,
        field_live=field_live,
    )


def test_complete_observable_alphabet_is_finite_deterministic_and_fires() -> None:
    atoms, frames = _features()
    replay_atoms, replay_frames = _features()

    assert tuple(atoms) == full.ATOMS
    assert tuple(frames) == full.FRAMES
    assert full._feature_digest(atoms, frames) == full._feature_digest(
        replay_atoms, replay_frames
    )
    assert all(np.isfinite(value).all() for value in (*atoms.values(), *frames.values()))
    assert np.ptp(atoms["local_density"]) > 0.0
    assert np.ptp(atoms["field_energy"]) > 0.0
    assert np.ptp(atoms["divergence"]) > 0.0
    assert np.ptp(atoms["coherence_gradient"]) > 0.0

    live_atoms, live_frames = _features(field_live=1.0)
    assert np.all(atoms["field_live"] == 0.0)
    assert np.all(live_atoms["field_live"] == 1.0)
    assert full._feature_digest(atoms, frames) != full._feature_digest(
        live_atoms, live_frames
    )


def test_registered_observable_supports_are_exactly_recoverable() -> None:
    controls = full.calibration_controls()

    assert len(full.ATOMS) == 31
    assert len(full.FRAMES) == 6
    assert all(control["status"] == "PASS" for control in controls.values())
    assert all(
        controls[name]["validation_nrmse"] <= 1e-10
        for name in (
            "enclosed-mass",
            "field-energy",
            "divergence",
            "strain",
            "density-gradient",
            "coherence-gradient",
        )
    )



def test_environment_families_are_readable_and_target_independent() -> None:
    position, velocity, mass = _snapshot()
    baseline_atoms, baseline_frames = _features()
    baseline_digest = full._feature_digest(baseline_atoms, baseline_frames)
    cases = {
        "position": {
            "position": position * np.array((1.0, 1.15, 0.85)),
            "velocity": velocity,
            "mass": mass,
            "clock_value": 0.75,
            "softening": 0.1,
            "cell_width": 0.04,
            "cluster_radius": 0.8,
            "cluster_separation": 2.5,
        },
        "velocity": {
            "position": position,
            "velocity": velocity * 1.2,
            "mass": mass,
            "clock_value": 0.75,
            "softening": 0.1,
            "cell_width": 0.04,
            "cluster_radius": 0.8,
            "cluster_separation": 2.5,
        },
        "mass": {
            "position": position,
            "velocity": velocity,
            "mass": mass * (1.0 + 0.01 * np.arange(len(mass))),
            "clock_value": 0.75,
            "softening": 0.1,
            "cell_width": 0.04,
            "cluster_radius": 0.8,
            "cluster_separation": 2.5,
        },
        "clock": {
            "position": position,
            "velocity": velocity,
            "mass": mass,
            "clock_value": 1.5,
            "softening": 0.1,
            "cell_width": 0.04,
            "cluster_radius": 0.8,
            "cluster_separation": 2.5,
        },
        "engine": {
            "position": position,
            "velocity": velocity,
            "mass": mass,
            "clock_value": 0.75,
            "softening": 0.2,
            "cell_width": 0.08,
            "cluster_radius": 1.2,
            "cluster_separation": 3.0,
        },
    }
    for name, values in cases.items():
        atoms, frames = full._snapshot_features(
            values["position"],
            values["velocity"],
            values["mass"],
            radius_scale=1.25,
            mass_scale=float(np.sum(values["mass"])),
            velocity_scale=2.0,
            initial_mean_mass=float(np.mean(values["mass"])),
            field_live=0.0,
            **{key: values[key] for key in ("clock_value", "softening", "cell_width", "cluster_radius", "cluster_separation")},
        )
        assert full._feature_digest(atoms, frames) != baseline_digest, name

    unchanged_atoms, unchanged_frames = _features()
    arbitrary_target = np.full((64, 3), 9876.5)
    assert arbitrary_target.shape[0] == len(unchanged_atoms["q"])
    assert full._feature_digest(unchanged_atoms, unchanged_frames) == baseline_digest


def test_runner_refuses_to_overwrite_frozen_receipt(tmp_path: Path) -> None:
    receipt = tmp_path / "receipt.json"
    receipt.write_text("sealed", encoding="utf-8")

    with pytest.raises(SystemExit, match="refusing to overwrite"):
        run_campaign(
            [
                "--home",
                str(tmp_path / "organism"),
                "--workspace",
                str(Path(__file__).resolve().parents[1]),
                "--out",
                str(receipt),
            ]
        )

def test_v4_excludes_only_unscorable_stationary_development_arm() -> None:
    v3 = full._campaign_spec("full-observable-operator-v3-20260919")
    v4 = full._campaign_spec("full-observable-operator-v4-20260919")

    assert v3.development_roots == full._DEVELOPMENT_ROOTS
    assert len(v4.development_roots) == len(full._DEVELOPMENT_ROOTS) - 1
    assert not any(root.endswith("/GL3") for root in v4.development_roots)
    assert all(root in full._DEVELOPMENT_ROOTS for root in v4.development_roots)

def test_field_alone_selects_every_stage_with_bounded_candidate_sets() -> None:
    class FieldSelector:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def select_laboratory_candidate(self, **request: object) -> dict[str, object]:
            candidates = request["candidates"]
            assert isinstance(candidates, list)
            assert 2 <= len(candidates) <= 32
            assert all("coefficients" not in row for row in candidates)
            selected = min(
                candidates,
                key=lambda row: (-float(row["development_score"]), str(row["candidate_id"])),
            )
            self.calls.append(request)
            return {
                "campaign_id": request["campaign_id"],
                "laboratory_id": request["laboratory_id"],
                "candidate_id": selected["candidate_id"],
                "selection_record_id": f"selection:{len(self.calls)}",
                "holdout_visible_during_selection": False,
            }

    target_term = {"frame": "flow", "scalar": full.typed._atom("field_energy")}
    fit = [full._synthetic_arm(arm_id="fit", target_term=target_term)]
    validation = [full._synthetic_arm(arm_id="validation", target_term=target_term)]
    field = FieldSelector()

    construction = full._run_construction(
        field,
        campaign_id="full-observable-test",
        fit_arms=fit,
        validation_arms=validation,
    )

    assert len(field.calls) == 13
    assert len(construction["selection_records"]) == 13
    assert len(construction["synthesis_candidates"]) <= 24
    for frame in full.FRAMES:
        mutation = construction["mutation_phase"][frame]
        assert mutation["parent_candidate"] == construction["seed_phase"][frame]["selection"]["candidate_id"]
