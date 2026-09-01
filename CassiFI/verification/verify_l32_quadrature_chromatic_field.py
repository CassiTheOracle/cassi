"""Independently verify the frozen L32 quadrature-chromatic recall board."""

from __future__ import annotations

import argparse
import math
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import verification.verify_l31_cyclic_chromatic_field as l31

l30 = l31.l30
BOARD_SCHEMA = "cassi.l32.quadrature-chromatic-board.v1"
TRACE_SCHEMA = "cassi.l32.quadrature-chromatic-traces.v1"
VERIFICATION_SCHEMA = "cassi.l32.quadrature-chromatic-verification.v1"
LAYOUT_PROFILE = "cassi.qi-cyclic-chromatic-coordinate-native.v1"
OPERATOR_PROFILE = "cassi.qi-quadrature-chromatic-recall.v1"
PROJECTION_PROFILE = "cassi.qi-cyclic-chromatic-projection.v1"
PREREGISTRATION = ROOT / "designs" / "L32-QUADRATURE-CHROMATIC-RECALL-PREREG.md"
DEFAULT_BOARD = ROOT / "_diag" / "l32-quadrature-chromatic-field" / "l32-board.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "l32-quadrature-chromatic-field"
DEFAULT_REPORT = DEFAULT_OUTPUT / "L32-QUADRATURE-CHROMATIC-RECALL-REPORT.md"
DEFAULT_JSON = DEFAULT_OUTPUT / "l32-verification.json"
EXPECTED_SOURCES = {
    "designs/L32-QUADRATURE-CHROMATIC-RECALL-PREREG.md",
    "cassi_white_chromatic_field.py",
    "cassi_cyclic_chromatic_field.py",
    "cassi_quadrature_chromatic_field.py",
    "verification/run_l30_white_chromatic_field.py",
    "verification/verify_l30_white_chromatic_field.py",
    "verification/run_l31_cyclic_chromatic_field.py",
    "verification/verify_l31_cyclic_chromatic_field.py",
    "verification/run_l32_quadrature_chromatic_field.py",
    "verification/verify_l32_quadrature_chromatic_field.py",
}
L30_SOURCES = {
    "designs/L30-WHITE-CHROMATIC-FIELD-PREREG.md",
    "cassi_white_chromatic_field.py",
    "verification/run_l30_white_chromatic_field.py",
    "verification/verify_l30_white_chromatic_field.py",
}


def recompute_quadrature_readout(
    differential: np.ndarray,
    normalized_velocity: np.ndarray,
    codebook: np.ndarray,
) -> dict[str, np.ndarray]:
    u = codebook[..., 0] + 1j * codebook[..., 1]
    channel_phase = np.exp(2j * np.pi * np.arange(l30.CHANNELS) / l30.CHANNELS)
    coefficient_d = np.einsum(
        "aw,swb->sba", np.conjugate(u), differential, optimize=True
    ) / l30.WIDTH
    coefficient_v = np.einsum(
        "aw,swb->sba", np.conjugate(u), normalized_velocity, optimize=True
    ) / l30.WIDTH
    aligned_d = np.conjugate(channel_phase)[:, None, None] * coefficient_d
    aligned_v = np.conjugate(channel_phase)[:, None, None] * coefficient_v
    global_d = aligned_d.sum(axis=0) / math.sqrt(l30.CHANNELS)
    global_v = aligned_v.sum(axis=0) / math.sqrt(l30.CHANNELS)
    scores = (np.abs(global_d) ** 2 + np.abs(global_v) ** 2).astype(np.float32)
    bank_scores = (np.abs(coefficient_d) ** 2 + np.abs(coefficient_v) ** 2).astype(
        np.float32
    )
    phase_energy = np.abs(differential) ** 2 + np.abs(normalized_velocity) ** 2
    rms = np.sqrt(np.mean(phase_energy, axis=1)).astype(np.float32)
    active = rms >= 1.0e-8
    active_count = active.sum(axis=0).astype(np.int64)
    available = (
        (np.mean(phase_energy, axis=(0, 1)) >= 1.0e-8) & (active_count >= 2)
    )
    symbols = np.argmax(scores, axis=1).astype(np.int64)
    winning_d = np.take_along_axis(
        aligned_d.transpose(1, 0, 2), symbols[:, None, None], axis=2
    )[:, :, 0]
    winning_v = np.take_along_axis(
        aligned_v.transpose(1, 0, 2), symbols[:, None, None], axis=2
    )[:, :, 0]
    coherence = (
        np.abs(winning_d.sum(axis=1)) ** 2
        + np.abs(winning_v.sum(axis=1)) ** 2
    ) / (
        active_count
        * (
            np.sum(np.abs(winning_d) ** 2, axis=1)
            + np.sum(np.abs(winning_v) ** 2, axis=1)
        )
        + 1.0e-12
    )
    return {
        "scores": scores,
        "bank_scores": bank_scores,
        "symbols": symbols,
        "available": available,
        "contributions": (aligned_d + 1j * aligned_v).transpose(1, 0, 2),
        "differential_rms": rms,
        "bank_energy": np.mean(phase_energy, axis=1).astype(np.float32),
        "active_bank_count": active_count,
        "white_coherence": coherence.astype(np.float32),
    }


def verify_board(
    board_path: Path, *, allow_smoke_device: bool = False
) -> tuple[str, dict[str, Any]]:
    board = l30.load_json(board_path)
    l30.need(board.get("schema_id") == BOARD_SCHEMA, "board schema mismatch")
    l30.need(board.get("status") == "COMPLETE", "board is not COMPLETE")
    l30.need(board.get("layout_profile_id") == LAYOUT_PROFILE, "layout identity mismatch")
    l30.need(
        board.get("operator_profile_id") == OPERATOR_PROFILE,
        "operator identity mismatch",
    )
    l30.need(
        board.get("projection_profile_id") == PROJECTION_PROFILE,
        "projection identity mismatch",
    )
    l30.need(board.get("trace_schema_id") == TRACE_SCHEMA, "trace schema mismatch")
    source = l30.mapping(board.get("source_sha256"), "source_sha256")
    l30.need(set(source) == EXPECTED_SOURCES, "source hash path set mismatch")
    for relative in EXPECTED_SOURCES:
        path = ROOT / relative
        l30.need(path.is_file(), f"source path missing: {relative}")
        l30.need(
            source[relative] == l30.sha256_file(path),
            f"source hash mismatch: {relative}",
        )
    prereg_relative = PREREGISTRATION.relative_to(ROOT).as_posix()
    l30.need(
        board.get("preregistration_sha256") == source[prereg_relative],
        "preregistration hash mismatch",
    )
    trace_path = l31.sibling_artifact(
        board_path, board.get("trace"), "l32-traces.npz", "trace"
    )
    png_path = l31.sibling_artifact(
        board_path, board.get("projection"), "l32-projection.png", "projection"
    )
    with np.load(trace_path, allow_pickle=False) as archive:
        evidence = {name: np.asarray(archive[name]) for name in archive.files}
    l30.need(
        evidence.get("task_read_normalized_vd", np.empty(0)).shape
        == (8, l30.CHANNELS, l30.WIDTH, l30.BATCH),
        "task quadrature trace shape mismatch",
    )
    l30.need(
        evidence.get("pre_read_normalized_vd", np.empty(0)).shape
        == (l30.CHANNELS, l30.WIDTH, l30.BATCH),
        "pre-read quadrature trace shape mismatch",
    )
    l30.need(
        bool(np.isfinite(evidence["task_read_normalized_vd"]).all())
        and bool(np.isfinite(evidence["pre_read_normalized_vd"]).all()),
        "quadrature trace contains nonfinite values",
    )

    call_index = 0

    def dispatch(differential: np.ndarray, codebook: np.ndarray) -> dict[str, np.ndarray]:
        nonlocal call_index
        if call_index < len(l30.READ_TICKS):
            expected_d = evidence["task_read_d"][call_index]
            velocity = evidence["task_read_normalized_vd"][call_index]
        else:
            expected_d = evidence["pre_target_d"]
            velocity = evidence["pre_read_normalized_vd"]
        l30.need(
            np.array_equal(differential, expected_d),
            "quadrature recomputation call order mismatch",
        )
        call_index += 1
        return recompute_quadrature_readout(differential, velocity, codebook)

    with tempfile.TemporaryDirectory(
        prefix=".l32-verify-", dir=board_path.parent
    ) as temporary_name:
        temporary = Path(temporary_name)
        compat_trace = temporary / "l30-traces.npz"
        compat_png = temporary / "l30-projection.png"
        shutil.copyfile(trace_path, compat_trace)
        shutil.copyfile(png_path, compat_png)
        compat = dict(board)
        compat.update(
            {
                "schema_id": l30.BOARD_SCHEMA,
                "layout_profile_id": l30.LAYOUT_PROFILE,
                "operator_profile_id": l30.OPERATOR_PROFILE,
                "projection_profile_id": l30.PROJECTION_PROFILE,
                "trace_schema_id": TRACE_SCHEMA,
                "preregistration_sha256": l30.sha256_file(l30.PREREGISTRATION),
                "source_sha256": {
                    relative: l30.sha256_file(ROOT / relative)
                    for relative in L30_SOURCES
                },
                "trace": {
                    "path": compat_trace.name,
                    "sha256": l30.sha256_file(compat_trace),
                    "array_count": l30.mapping(board.get("trace"), "trace").get(
                        "array_count"
                    ),
                },
                "projection": {
                    "path": compat_png.name,
                    "sha256": l30.sha256_file(compat_png),
                },
            }
        )
        compat_board = temporary / "l30-board.json"
        l30.atomic_write(compat_board, l30.canonical_bytes(compat))
        previous = (
            l30.TRACE_SCHEMA,
            l30.coordinates_from_field,
            l30.recompute_readout,
        )
        try:
            l30.TRACE_SCHEMA = TRACE_SCHEMA
            l30.coordinates_from_field = l31.native_coordinates_from_field
            l30.recompute_readout = dispatch
            verdict, payload = l30.verify_board(
                compat_board, allow_smoke_device=allow_smoke_device
            )
        finally:
            (
                l30.TRACE_SCHEMA,
                l30.coordinates_from_field,
                l30.recompute_readout,
            ) = previous
    l30.need(call_index == 9, "quadrature recomputation count mismatch")
    result = dict(payload)
    result["schema_id"] = VERIFICATION_SCHEMA
    return verdict, result


def report_text(verdict: str, payload: Mapping[str, Any]) -> str:
    explanation = {
        "ADOPT": "All frozen mechanical and functional gates passed.",
        "REJECT": "Mechanics passed; one or more preregistered functional conditions failed.",
        "INCOMPLETE": "The canonical board was interrupted or unavailable before complete verification.",
        "FAIL": "Evidence integrity or a frozen mechanical gate failed.",
    }[verdict]
    lines = [
        "# L32 Quadrature Chromatic Recall — Verification",
        "",
        f"**Verdict: `{verdict}`**",
        "",
        explanation,
    ]
    if payload.get("failures"):
        lines.extend(
            ["", "## Failures", *[f"- {item}" for item in payload["failures"]]]
        )
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
            "functional_conditions": {},
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
                "functional_conditions": {},
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
            "board_sha256": (
                l30.sha256_file(board_path) if board_path.is_file() else None
            ),
        }
    )
    l30.atomic_write(args.json.resolve(), l30.canonical_bytes(payload))
    l30.atomic_write(
        args.report.resolve(), report_text(verdict, payload).encode("utf-8")
    )
    print(verdict)
    print(args.report.resolve())
    print(args.json.resolve())
    return 0 if verdict == "ADOPT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
