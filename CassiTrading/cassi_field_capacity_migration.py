"""Migrate a saturated CassiTrading field to a wider wave profile.

The migration is explicit and receipt-backed. It never copies raw modes into a
new codebook: each active differential bank is demodulated into shared symbol
coordinates and reconstructed through the target codebook. The epsilon history
is linearly resampled along the mode axis. A bounded semantic probe is recorded
before the migrated checkpoint is used for further training.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import torch

from cassi_trading_foundry import (  # noqa: E402
    REFINEMENT_SCHEMA,
    RefinementField,
    digest_value,
)
from cassi_qi_field import QiFieldState  # noqa: E402
from cassi_raw_event_field import RawEventLearner  # noqa: E402


MIGRATION_SCHEMA = "cassi.trading-field-capacity-migration.v1"
MIGRATION_ID = "demodulate-shared-symbols-reconstruct-target-codebook-bounded-retune-v2"
_PROBE_SIGNATURES = ("drawdown", "cost", "edge", "flat", "stable")
_PROBE_MUTATIONS = (
    "fast_up",
    "fast_down",
    "breakout",
    "mean_reversion",
    "entry_up",
    "exit_down",
)


def _sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _reconstruct_bank(
    old_controller: Any,
    new_controller: Any,
    old_tensor: torch.Tensor,
    new_tensor: torch.Tensor,
    *,
    scale: int,
    old_width: int,
    new_width: int,
    real_index: int,
    imag_index: int,
    real_other: int,
    imag_other: int,
    phi: float,
) -> None:
    old_re = old_tensor[scale, real_index, :old_width, 0] - phi * old_tensor[
        scale, real_other, :old_width, 0
    ]
    old_im = old_tensor[scale, imag_index, :old_width, 0] - phi * old_tensor[
        scale, imag_other, :old_width, 0
    ]
    coefficients_re, coefficients_im, source_rms = old_controller._demodulate_bank(
        old_re.unsqueeze(1), old_im.unsqueeze(1), scale
    )
    target_codes = new_controller.codebook(
        scale, device="cpu", dtype=torch.float64
    )
    target_re = (
        torch.einsum("ab,aw->wb", coefficients_re, target_codes[:, :, 0])
        - torch.einsum("ab,aw->wb", coefficients_im, target_codes[:, :, 1])
    ) * source_rms
    target_im = (
        torch.einsum("ab,aw->wb", coefficients_re, target_codes[:, :, 1])
        + torch.einsum("ab,aw->wb", coefficients_im, target_codes[:, :, 0])
    ) * source_rms
    denominator = 1.0 + phi * phi
    new_tensor[scale, real_index, :new_width, 0].copy_(
        target_re[:, 0] / denominator
    )
    new_tensor[scale, imag_index, :new_width, 0].copy_(
        target_im[:, 0] / denominator
    )
    new_tensor[scale, real_other, :new_width, 0].copy_(
        -phi * target_re[:, 0] / denominator
    )
    new_tensor[scale, imag_other, :new_width, 0].copy_(
        -phi * target_im[:, 0] / denominator
    )


def migrate_field(
    field: RefinementField,
    *,
    target_wave_width: int,
    target_provisional_gain: float | None = None,
    target_consolidation_gain: float | None = None,
    target_amplitude_scale: float = 1.0,
) -> tuple[RefinementField, dict[str, Any]]:
    old_profile = field.learner.profile
    if target_wave_width < old_profile.wave_width:
        raise ValueError("target wave width must not shrink the source width")
    if (
        target_wave_width == old_profile.wave_width
        and target_provisional_gain is None
        and target_consolidation_gain is None
        and target_amplitude_scale == 1.0
    ):
        raise ValueError("migration must change width, gains, or amplitude")
    if target_wave_width > old_profile.mode_count * 2:
        raise ValueError("target wave width exceeds the bounded profile expansion")
    if not 0.0 < target_amplitude_scale <= 1.0:
        raise ValueError("target amplitude scale must be in (0, 1]")

    target_profile = replace(
        old_profile,
        wave_width=int(target_wave_width),
        provisional_gain=(
            old_profile.provisional_gain
            if target_provisional_gain is None
            else float(target_provisional_gain)
        ),
        consolidation_gain=(
            old_profile.consolidation_gain
            if target_consolidation_gain is None
            else float(target_consolidation_gain)
        ),
    )
    old_controller = field.learner.controller
    target_learner = RawEventLearner(profile=target_profile)
    target_controller = target_learner.controller
    old_tensor = field.learner.state.field.reshape(
        4, 9, old_profile.mode_count, 1
    )
    target_tensor = target_learner.state.field.reshape(
        4, 9, target_profile.mode_count, 1
    )
    old_width = old_profile.wave_width
    new_width = target_profile.wave_width
    phi = float(old_controller.config.phi)

    with torch.no_grad():
        for scale in range(4):
            _reconstruct_bank(
                old_controller,
                target_controller,
                old_tensor,
                target_tensor,
                scale=scale,
                old_width=old_width,
                new_width=new_width,
                real_index=0,
                imag_index=1,
                real_other=2,
                imag_other=3,
                phi=phi,
            )
            _reconstruct_bank(
                old_controller,
                target_controller,
                old_tensor,
                target_tensor,
                scale=scale,
                old_width=old_width,
                new_width=new_width,
                real_index=4,
                imag_index=5,
                real_other=6,
                imag_other=7,
                phi=phi,
            )
            old_epsilon = old_tensor[scale, 8, :old_width, 0]
            target_tensor[scale, 8, :new_width, 0].copy_(
                torch.nn.functional.interpolate(
                    old_epsilon.reshape(1, 1, old_width),
                    size=new_width,
                    mode="linear",
                    align_corners=True,
                ).reshape(new_width)
            )
    pre_scale_max_abs = float(target_tensor.abs().max().item())
    automatic_bound_scale = 1.0
    if pre_scale_max_abs > target_profile.component_limit:
        automatic_bound_scale = target_profile.component_limit / pre_scale_max_abs
    amplitude_scale = automatic_bound_scale * target_amplitude_scale
    if amplitude_scale != 1.0:
        with torch.no_grad():
            target_tensor.mul_(amplitude_scale)


    migrated_learner = RawEventLearner(
        profile=target_profile,
        state=QiFieldState(target_tensor.reshape(4, 9 * target_profile.mode_count, 1)),
    )
    migrated_field = RefinementField(learner=migrated_learner)
    probe_rows: list[dict[str, Any]] = []
    for signature in _PROBE_SIGNATURES:
        for mutation in _PROBE_MUTATIONS:
            before = field.predict(signature, mutation)
            after = migrated_field.predict(signature, mutation)
            probe_rows.append(
                {
                    "signature": signature,
                    "mutation": mutation,
                    "before_status": before.get("status"),
                    "after_status": after.get("status"),
                    "before_outcome": before.get("outcome"),
                    "after_outcome": after.get("outcome"),
                    "before_score": before.get("score"),
                    "after_score": after.get("score"),
                }
            )
    score_pairs = [
        (float(row["before_score"]), float(row["after_score"]))
        for row in probe_rows
        if isinstance(row["before_score"], (int, float))
        and isinstance(row["after_score"], (int, float))
    ]
    status_matches = sum(
        row["before_status"] == row["after_status"] for row in probe_rows
    )
    outcome_matches = sum(
        row["before_outcome"] == row["after_outcome"] for row in probe_rows
    )
    semantic_probe = {
        "probe_count": len(probe_rows),
        "status_matches": status_matches,
        "outcome_matches": outcome_matches,
        "status_match_ratio": status_matches / len(probe_rows),
        "outcome_match_ratio": outcome_matches / len(probe_rows),
        "max_absolute_score_delta": max(
            (abs(before - after) for before, after in score_pairs), default=0.0
        ),
    }
    receipt = {
        "schema": MIGRATION_SCHEMA,
        "migration_id": MIGRATION_ID,
        "source_refinement_schema": REFINEMENT_SCHEMA,
        "source_profile": old_profile.as_dict(),
        "target_profile": target_profile.as_dict(),
        "source_field": field.learner.snapshot(),
        "mapping": {
            "differential_banks": "demodulate-shared-symbol-coordinates",
            "target_wave": "reconstruct-through-target-codebook",
            "epsilon2_ema": "linear-mode-axis-resample",
            "inactive_modes": "zero-initialized",
            "automatic_bound_scale": automatic_bound_scale,
            "requested_amplitude_scale": target_amplitude_scale,
            "amplitude_scale": amplitude_scale,
            "pre_scale_max_abs": pre_scale_max_abs,
        },
        "semantic_probe": semantic_probe,
    }
    receipt["content_sha256"] = digest_value(receipt)
    return migrated_field, receipt


def migrate_checkpoint(
    source_path: Path,
    target_path: Path,
    receipt_path: Path,
    *,
    target_wave_width: int,
    target_provisional_gain: float | None = None,
    target_consolidation_gain: float | None = None,
    target_amplitude_scale: float = 1.0,
) -> dict[str, Any]:
    source_bytes = source_path.read_bytes()
    source_field = RefinementField.restore(source_bytes)
    migrated_field, receipt = migrate_field(
        source_field,
        target_wave_width=target_wave_width,
        target_provisional_gain=target_provisional_gain,
        target_consolidation_gain=target_consolidation_gain,
        target_amplitude_scale=target_amplitude_scale,
    )
    target_bytes = migrated_field.learner.checkpoint_bytes()
    receipt = {
        **receipt,
        "source_checkpoint_sha256": _sha256(source_bytes),
        "target_checkpoint_sha256": _sha256(target_bytes),
        "target_checkpoint_bytes": len(target_bytes),
    }
    receipt["content_sha256"] = digest_value(
        {key: value for key, value in receipt.items() if key != "content_sha256"}
    )
    target_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(target_bytes)
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--target-wave-width", type=int, required=True)
    parser.add_argument("--target-provisional-gain", type=float)
    parser.add_argument("--target-consolidation-gain", type=float)
    parser.add_argument("--target-amplitude-scale", type=float, default=1.0)
    args = parser.parse_args()
    receipt = migrate_checkpoint(
        args.source,
        args.target,
        args.receipt,
        target_wave_width=args.target_wave_width,
        target_provisional_gain=args.target_provisional_gain,
        target_consolidation_gain=args.target_consolidation_gain,
        target_amplitude_scale=args.target_amplitude_scale,
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
