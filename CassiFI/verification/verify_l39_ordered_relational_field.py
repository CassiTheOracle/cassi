"""Independently verify and classify the frozen L39 ordered recall board."""

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

import verification.verify_l30_white_chromatic_field as l30

BOARD_SCHEMA = "cassi.l39.ordered-relational-board.v1"
TRACE_SCHEMA = "cassi.l39.ordered-relational-traces.v1"
VERIFICATION_SCHEMA = "cassi.l39.ordered-relational-verification.v1"
LAYOUT_PROFILE = "cassi.qi-cyclic-chromatic-coordinate-native.v1"
OPERATOR_PROFILE = "cassi.qi-ordered-relational-chromatic-recall.v1"
PROJECTION_PROFILE = "cassi.qi-cyclic-chromatic-projection.v1"
PREREGISTRATION = ROOT / "designs" / "L39-ORDERED-RELATIONAL-RECALL-PREREG.md"
DEFAULT_BOARD = ROOT / "_diag" / "l39-ordered-relational-field" / "l39-board.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "l39-ordered-relational-field"
DEFAULT_REPORT = DEFAULT_OUTPUT / "L39-ORDERED-RELATIONAL-RECALL-REPORT.md"
DEFAULT_JSON = DEFAULT_OUTPUT / "l39-verification.json"
EXPECTED_SOURCES = {
    "designs/L39-ORDERED-RELATIONAL-RECALL-PREREG.md",
    "cassi_white_chromatic_field.py",
    "cassi_cyclic_chromatic_field.py",
    "cassi_relational_chromatic_field.py",
    "cassi_ordered_relational_field.py",
    "verification/run_l30_white_chromatic_field.py",
    "verification/verify_l30_white_chromatic_field.py",
    "verification/run_l31_cyclic_chromatic_field.py",
    "verification/verify_l31_cyclic_chromatic_field.py",
    "verification/run_l39_ordered_relational_field.py",
    "verification/verify_l39_ordered_relational_field.py",
}
L30_SOURCES = {
    "designs/L30-WHITE-CHROMATIC-FIELD-PREREG.md",
    "cassi_white_chromatic_field.py",
    "verification/run_l30_white_chromatic_field.py",
    "verification/verify_l30_white_chromatic_field.py",
}
_BASE_RECOMPUTE_READOUT = l30.recompute_readout
_COMMON_QUEUE: list[np.ndarray] = []


def native_coordinates_from_field(
    field: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    parts = field.reshape(l30.CHANNELS, 9, l30.MODES, field.shape[2])
    return (
        parts[:, 0, : l30.WIDTH] + 1j * parts[:, 1, : l30.WIDTH],
        parts[:, 2, : l30.WIDTH] + 1j * parts[:, 3, : l30.WIDTH],
        parts[:, 4, : l30.WIDTH] + 1j * parts[:, 5, : l30.WIDTH],
        parts[:, 6, : l30.WIDTH] + 1j * parts[:, 7, : l30.WIDTH],
    )


def ordered_readout(
    differential: np.ndarray, codebook: np.ndarray
) -> dict[str, np.ndarray]:
    l30.need(bool(_COMMON_QUEUE), "ordered common-coordinate queue exhausted")
    common = _COMMON_QUEUE.pop(0)
    result = dict(_BASE_RECOMPUTE_READOUT(differential, codebook))
    current_scores = result["scores"]
    current_symbols = result["symbols"]
    u = codebook[..., 0] + 1j * codebook[..., 1]
    harmonic = np.exp(
        2j * math.pi * np.arange(l30.CHANNELS) / l30.CHANNELS
    )
    common_carrier = common.sum(axis=0) / math.sqrt(l30.CHANNELS)
    differential_carrier = (
        np.conjugate(harmonic)[:, None, None] * differential
    ).sum(axis=0) / math.sqrt(l30.CHANNELS)
    relational = -common_carrier * differential_carrier
    coefficient = np.einsum(
        "aw,wb->ab", np.conjugate(u), relational, optimize=True
    ) / l30.WIDTH
    relational_scores = (np.abs(coefficient) ** 2).T.astype(np.float32)
    relational_symbols = np.argmax(relational_scores, axis=1).astype(np.int64)
    floor = np.float32(1.0e-8)
    current_scale = np.maximum(
        np.max(current_scores, axis=1, keepdims=True), floor
    )
    relational_max = np.max(relational_scores, axis=1, keepdims=True)
    relational_scale = np.maximum(relational_max, floor)
    ordered_scores = np.maximum(
        current_scores / current_scale,
        relational_scores / relational_scale,
    ).astype(np.float32)
    relational_available = result["available"] & (relational_max[:, 0] >= floor)
    for row in range(ordered_scores.shape[0]):
        if not result["available"][row]:
            ordered_scores[row] = current_scores[row]
            continue
        if (
            relational_available[row]
            and relational_symbols[row] != current_symbols[row]
        ):
            ordered_scores[row, relational_symbols[row]] = np.float32(2.0)
        ordered_scores[row, current_symbols[row]] = np.float32(3.0)
    result.update({"scores": ordered_scores, "symbols": current_symbols})
    return result


def sibling_artifact(
    board_path: Path, value: Any, expected_name: str, label: str
) -> Path:
    item = l30.mapping(value, label)
    name = item.get("path")
    l30.need(
        isinstance(name, str)
        and Path(name).name == name
        and name == expected_name,
        f"{label} must be sibling basename {expected_name}",
    )
    assert isinstance(name, str)
    path = board_path.parent / name
    l30.need(path.is_file(), f"{label} artifact missing")
    l30.need(item.get("sha256") == l30.sha256_file(path), f"{label} hash mismatch")
    return path


def verify_board(
    board_path: Path, *, allow_smoke_device: bool = False
) -> tuple[str, dict[str, Any]]:
    board = l30.load_json(board_path)
    l30.need(board.get("schema_id") == BOARD_SCHEMA, "board schema mismatch")
    l30.need(board.get("status") == "COMPLETE", "board is not COMPLETE")
    l30.need(board.get("layout_profile_id") == LAYOUT_PROFILE, "layout identity mismatch")
    l30.need(board.get("operator_profile_id") == OPERATOR_PROFILE, "operator identity mismatch")
    l30.need(board.get("projection_profile_id") == PROJECTION_PROFILE, "projection identity mismatch")
    l30.need(board.get("trace_schema_id") == TRACE_SCHEMA, "trace schema mismatch")

    source = l30.mapping(board.get("source_sha256"), "source_sha256")
    l30.need(set(source) == EXPECTED_SOURCES, "source hash path set mismatch")
    for relative in EXPECTED_SOURCES:
        path = ROOT / relative
        l30.need(path.is_file(), f"source path missing: {relative}")
        l30.need(source[relative] == l30.sha256_file(path), f"source hash mismatch: {relative}")
    prereg_relative = PREREGISTRATION.relative_to(ROOT).as_posix()
    l30.need(
        board.get("preregistration_sha256") == source[prereg_relative],
        "preregistration hash mismatch",
    )
    trace_path = sibling_artifact(board_path, board.get("trace"), "l39-traces.npz", "trace")
    png_path = sibling_artifact(
        board_path, board.get("projection"), "l39-projection.png", "projection"
    )
    with np.load(trace_path, allow_pickle=False) as archive:
        l30.need("task_read_c" in archive.files, "task common-coordinate trace missing")
        l30.need("pre_target_c" in archive.files, "pre-target common-coordinate trace missing")
        common_queue = [archive["task_read_c"][index] for index in range(8)]
        common_queue.append(archive["pre_target_c"])

    with tempfile.TemporaryDirectory(
        prefix=".l39-verify-", dir=board_path.parent
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
        global _COMMON_QUEUE
        _COMMON_QUEUE = common_queue
        try:
            l30.TRACE_SCHEMA = TRACE_SCHEMA
            l30.coordinates_from_field = native_coordinates_from_field
            l30.recompute_readout = ordered_readout
            verdict, payload = l30.verify_board(
                compat_board, allow_smoke_device=allow_smoke_device
            )
            l30.need(not _COMMON_QUEUE, "ordered common-coordinate queue not consumed")
        finally:
            (
                l30.TRACE_SCHEMA,
                l30.coordinates_from_field,
                l30.recompute_readout,
            ) = previous
            _COMMON_QUEUE = []

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
        "# L39 Ordered Relational Recall — Verification",
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
            "board_sha256": l30.sha256_file(board_path) if board_path.is_file() else None,
        }
    )
    l30.atomic_write(args.json.resolve(), l30.canonical_bytes(payload))
    l30.atomic_write(args.report.resolve(), report_text(verdict, payload).encode("utf-8"))
    print(verdict)
    print(args.report.resolve())
    print(args.json.resolve())
    return 0 if verdict == "ADOPT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
