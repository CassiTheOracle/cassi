"""Produce a noncanonical L42/L43 cross-device reconstruction audit."""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import verification.verify_l30_white_chromatic_field as l30

POSITION = 1
AGE_HARMONICS = (1, 2, 3, 4, 5, 6, 0)
ROUND_OFF_MULTIPLIER = 128.0
ATOL = 3.0e-5
RTOL = 2.0e-4
PREREGISTRATION = ROOT / "designs" / "HARMONIC-RECONSTRUCTION-AUDIT-PREREG.md"
SCRIPT = ROOT / "verification" / "audit_harmonic_reconstruction.py"
OUTPUT = (
    ROOT
    / "artifacts"
    / "harmonic-reconstruction-audit"
    / "harmonic-reconstruction-audit.json"
)
INPUTS = {
    "l42_board": ROOT / "_diag" / "l42-harmonic-age-ladder" / "l42-board.json",
    "l42_trace": ROOT / "_diag" / "l42-harmonic-age-ladder" / "l42-traces.npz",
    "l42_receipt": ROOT
    / "artifacts"
    / "l42-harmonic-age-ladder"
    / "l42-verification.json",
    "l43_board": ROOT / "_diag" / "l43-stable-harmonic-field" / "l43-board.json",
    "l43_trace": ROOT / "_diag" / "l43-stable-harmonic-field" / "l43-traces.npz",
    "l43_receipt": ROOT
    / "artifacts"
    / "l43-stable-harmonic-field"
    / "l43-verification.json",
}


class AuditError(RuntimeError):
    """The immutable audit inputs do not satisfy the frozen protocol."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AuditError(f"JSON root must be an object: {path}")
    return value


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    with tempfile.NamedTemporaryFile(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
    ) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def independent_age_scores(
    differential: np.ndarray, codebook: np.ndarray
) -> np.ndarray:
    d = torch.from_numpy(differential)
    parts = torch.from_numpy(codebook)
    u = torch.complex(parts[..., 0], parts[..., 1])
    angle = (
        2.0
        * math.pi
        * torch.arange(7, dtype=d.real.dtype)
        / 7.0
    )
    phase = torch.complex(torch.cos(angle), torch.sin(angle))
    harmonics = torch.tensor(AGE_HARMONICS, dtype=torch.int64)
    basis = phase.conj()[None, :].pow(harmonics[:, None]) / math.sqrt(7.0)
    collapsed = torch.einsum("hc,cwb->hwb", basis, d)
    coefficients = torch.einsum(
        "aw,hwb->hba", u.conj(), collapsed
    ) / float(differential.shape[1])
    return coefficients.abs().square().permute(1, 0, 2).numpy()


def l42_aggregate(
    differential: np.ndarray,
    codebook: np.ndarray,
    age_scores: np.ndarray,
) -> dict[str, np.ndarray]:
    base = dict(l30.recompute_readout(differential, codebook))
    age_symbols = np.argmax(age_scores, axis=2).astype(np.int64)
    age_max = np.max(age_scores, axis=2)
    age_available = base["available"][:, None] & (age_max >= np.float32(1.0e-8))
    scores = np.max(
        age_scores / np.maximum(age_max, np.float32(1.0e-8))[:, :, None],
        axis=1,
    ).astype(age_scores.dtype)
    for row in range(scores.shape[0]):
        if not base["available"][row]:
            scores[row] = base["scores"][row]
            continue
        for age in range(6, -1, -1):
            if age_available[row, age]:
                scores[row, age_symbols[row, age]] = 8 - age
    return {
        "scores": scores,
        "age_symbols": age_symbols,
        "age_available": age_available,
    }


def stable_aggregate(
    differential: np.ndarray,
    codebook: np.ndarray,
    age_scores: np.ndarray,
) -> dict[str, np.ndarray]:
    base = dict(l30.recompute_readout(differential, codebook))
    age_symbols = np.argmax(age_scores, axis=2).astype(np.int64)
    age_max = np.max(age_scores, axis=2)
    row_peak = np.max(age_max, axis=1)
    floor = np.maximum(
        np.asarray(1.0e-8, dtype=age_scores.dtype),
        row_peak
        * np.asarray(
            ROUND_OFF_MULTIPLIER * np.finfo(age_scores.dtype).eps,
            dtype=age_scores.dtype,
        ),
    )
    age_available = base["available"][:, None] & (age_max >= floor[:, None])
    normalized = np.where(
        age_available[:, :, None],
        age_scores / np.maximum(age_max, floor[:, None])[:, :, None],
        np.zeros_like(age_scores),
    )
    scores = np.max(normalized, axis=1).astype(age_scores.dtype)
    for row in range(scores.shape[0]):
        if not base["available"][row]:
            scores[row] = base["scores"][row]
            continue
        for age in range(6, -1, -1):
            if age_available[row, age]:
                scores[row, age_symbols[row, age]] = 8 - age
    return {
        "scores": scores,
        "age_symbols": age_symbols,
        "age_available": age_available,
        "floor": floor,
        "normalized": normalized,
    }


def error_metrics(actual: np.ndarray, expected: np.ndarray) -> dict[str, Any]:
    difference = np.abs(actual - expected)
    denominator = np.maximum.reduce(
        (
            np.abs(actual),
            np.abs(expected),
            np.full_like(difference, 1.0e-12),
        )
    )
    location = np.unravel_index(int(np.argmax(difference)), difference.shape)
    return {
        "maximum_absolute_error": float(np.max(difference)),
        "maximum_relative_error": float(np.max(difference / denominator)),
        "worst_index": [int(index) for index in location],
        "actual_at_worst": float(actual[location]),
        "expected_at_worst": float(expected[location]),
        "within_frozen_tolerance": bool(
            np.allclose(actual, expected, atol=ATOL, rtol=RTOL)
        ),
    }


def audit_l42(arrays: dict[str, np.ndarray]) -> dict[str, Any]:
    differential = arrays["four_post_d"][POSITION]
    codebook = arrays["codebook"]
    raw_age_scores = arrays["four_post_age_scores"][POSITION]
    raw_scores = arrays["four_post_scores"][POSITION]
    independent = independent_age_scores(differential, codebook)
    from_raw = l42_aggregate(differential, codebook, raw_age_scores)
    from_independent = l42_aggregate(differential, codebook, independent)
    age_error = error_metrics(raw_age_scores, independent)
    raw_formula_error = error_metrics(raw_scores, from_raw["scores"])
    independent_error = error_metrics(raw_scores, from_independent["scores"])
    if not raw_formula_error["within_frozen_tolerance"]:
        classification = "FORMULA_OR_SHAPE_ERROR"
    elif (
        age_error["within_frozen_tolerance"]
        and not independent_error["within_frozen_tolerance"]
    ):
        classification = "DEVICE_ROUNDING_AMPLIFIED_BY_NORMALIZATION"
    else:
        classification = "UNRESOLVED"
    return {
        "classification": classification,
        "position": POSITION,
        "raw_age_scores_vs_independent": age_error,
        "raw_aggregate_vs_raw_age_aggregation": raw_formula_error,
        "raw_aggregate_vs_independent_age_aggregation": independent_error,
    }


def audit_l43(arrays: dict[str, np.ndarray]) -> dict[str, Any]:
    differential = arrays["four_post_d"][POSITION]
    codebook = arrays["codebook"]
    raw_age_scores = arrays["four_post_age_scores"][POSITION]
    raw_scores = arrays["four_post_scores"][POSITION]
    raw_symbols = arrays["four_post_age_symbols"][POSITION]
    raw_available = arrays["four_post_age_available"][POSITION]
    independent = independent_age_scores(differential, codebook)
    from_raw = stable_aggregate(differential, codebook, raw_age_scores)
    from_independent = stable_aggregate(differential, codebook, independent)
    reconstructed_symbols = np.argmax(independent, axis=2)
    mismatch = raw_symbols != reconstructed_symbols
    available_mismatch = mismatch & raw_available
    unavailable_mismatch = mismatch & ~raw_available
    raw_top = np.max(raw_age_scores, axis=2)
    sorted_scores = np.sort(raw_age_scores, axis=2)
    margins = sorted_scores[:, :, -1] - sorted_scores[:, :, -2]
    floors = np.broadcast_to(from_raw["floor"][:, None], mismatch.shape)
    mismatch_top = raw_top[mismatch]
    mismatch_floor = floors[mismatch]
    mismatch_margin = margins[mismatch]
    raw_formula_error = error_metrics(raw_scores, from_raw["scores"])
    independent_error = error_metrics(raw_scores, from_independent["scores"])
    all_mismatches_below_floor = bool(
        mismatch_top.size > 0 and np.all(mismatch_top < mismatch_floor)
    )
    if not raw_formula_error["within_frozen_tolerance"]:
        classification = "FORMULA_OR_SHAPE_ERROR"
    elif int(available_mismatch.sum()) > 0:
        classification = "SEMANTIC_AVAILABLE_WINNER_MISMATCH"
    elif (
        int(unavailable_mismatch.sum()) > 0
        and independent_error["within_frozen_tolerance"]
        and all_mismatches_below_floor
    ):
        classification = "OVERSTRICT_UNAVAILABLE_ARGMAX"
    else:
        classification = "UNRESOLVED"
    return {
        "classification": classification,
        "position": POSITION,
        "raw_age_scores_vs_independent": error_metrics(raw_age_scores, independent),
        "raw_aggregate_vs_raw_age_aggregation": raw_formula_error,
        "raw_aggregate_vs_independent_age_aggregation": independent_error,
        "winner_mismatches": {
            "total": int(mismatch.sum()),
            "available": int(available_mismatch.sum()),
            "unavailable": int(unavailable_mismatch.sum()),
            "all_available_winners_agree": bool(int(available_mismatch.sum()) == 0),
            "all_mismatches_below_floor": all_mismatches_below_floor,
            "maximum_mismatched_top_score": (
                float(np.max(mismatch_top)) if mismatch_top.size else 0.0
            ),
            "minimum_mismatched_floor": (
                float(np.min(mismatch_floor)) if mismatch_floor.size else 0.0
            ),
            "maximum_top_to_floor_ratio": (
                float(np.max(mismatch_top / mismatch_floor))
                if mismatch_top.size
                else 0.0
            ),
            "maximum_argmax_margin": (
                float(np.max(mismatch_margin)) if mismatch_margin.size else 0.0
            ),
        },
    }


def main() -> int:
    missing = [str(path) for path in INPUTS.values() if not path.is_file()]
    if missing:
        raise AuditError(f"missing immutable inputs: {missing!r}")
    boards = {
        name: load_json(path)
        for name, path in INPUTS.items()
        if name.endswith("_board")
    }
    for name, board in boards.items():
        if board.get("status") != "COMPLETE":
            raise AuditError(f"raw board is not COMPLETE: {name}")
    receipts = {
        name: load_json(path)
        for name, path in INPUTS.items()
        if name.endswith("_receipt")
    }
    with np.load(INPUTS["l42_trace"], allow_pickle=False) as archive:
        l42_arrays = {name: np.asarray(archive[name]) for name in archive.files}
    with np.load(INPUTS["l43_trace"], allow_pickle=False) as archive:
        l43_arrays = {name: np.asarray(archive[name]) for name in archive.files}
    payload = {
        "schema_id": "cassi.harmonic-reconstruction-audit.v1",
        "status": "NONCANONICAL_DIAGNOSTIC",
        "changes_frozen_verdicts": False,
        "authorizes_rerun": False,
        "position": POSITION,
        "tolerances": {"absolute": ATOL, "relative": RTOL},
        "input_sha256": {
            name: sha256_file(path) for name, path in INPUTS.items()
        },
        "source_sha256": {
            PREREGISTRATION.relative_to(ROOT).as_posix(): sha256_file(
                PREREGISTRATION
            ),
            SCRIPT.relative_to(ROOT).as_posix(): sha256_file(SCRIPT),
        },
        "frozen_receipts": {
            name: {
                "verdict": receipt.get("verdict"),
                "failures": receipt.get("failures"),
            }
            for name, receipt in receipts.items()
        },
        "l42": audit_l42(l42_arrays),
        "l43": audit_l43(l43_arrays),
    }
    atomic_json(OUTPUT, payload)
    print(OUTPUT)
    print(payload["l42"]["classification"])
    print(payload["l43"]["classification"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
