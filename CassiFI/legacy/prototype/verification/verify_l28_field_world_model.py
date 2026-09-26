"""Independently verify and report the frozen L28 field-world-model board."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import asdict
from pathlib import Path
import sys

_CASSI_FI_ROOT = Path(__file__).resolve().parents[1]
for _path in (_CASSI_FI_ROOT, _CASSI_FI_ROOT / "training", _CASSI_FI_ROOT / "verification"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from cassi_fi_paths import ARTIFACT_DIR, DESIGN_DIR

import torch

from cassi_modal_torch import MODE_LAYOUT_ID, OPERATOR_PROFILE_ID, CassiModalConfig
from field_world_model import (
    BOARD_SCHEMA,
    GENERATOR_SEED,
    OPTIMIZATION_SEED,
    OPTIMIZER_LR,
    OPTIMIZER_UPDATES,
    OPTIMIZER_WEIGHT_DECAY,
    TEST_EPISODES,
    TRAIN_EPISODES,
    TRAINING_SEED,
    VALIDATION_EPISODES,
    WorldSpec,
    FieldWorldModel,
    GRUWorldModel,
    StatelessWorldModel,
    _data_bounds,
    _digest_state,
    _field_predictions,
    _metrics,
    _trajectory_bounds,
    make_dataset,
    parameter_count,
)


CHECKPOINT_SCHEMA = "cassi.l28.field-checkpoint.v1"
MANIFEST_SCHEMA = "cassi.l28.field-manifest.v1"
REQUIRED_ARMS = ("field", "stateless", "gru", "field-reset", "field-shuffled")
DATA_BOUND = 100.0
STATE_BOUND = 100.0


def _finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _expected_code_digests() -> dict[str, str]:
    return {
        "field_world_model.py": _sha256(_CASSI_FI_ROOT / "field_world_model.py"),
        "cassi_modal_torch.py": _sha256(_CASSI_FI_ROOT / "cassi_modal_torch.py"),
        "L28-FIELD-WORLD-MODEL-PREREG.md": _sha256(
            DESIGN_DIR / "L28-FIELD-WORLD-MODEL-PREREG.md"
        ),
    }


def _expected_splits() -> dict[str, list[int]]:
    return {
        "train": list(TRAIN_EPISODES),
        "validation": list(VALIDATION_EPISODES),
        "test": list(TEST_EPISODES),
    }


def _expected_optimizer() -> dict[str, float | int]:
    return {
        "updates": OPTIMIZER_UPDATES,
        "learning_rate": OPTIMIZER_LR,
        "weight_decay": OPTIMIZER_WEIGHT_DECAY,
    }


def _expected_parameter_counts(spec: WorldSpec, config: CassiModalConfig) -> dict[str, int]:
    return {
        "field": parameter_count(FieldWorldModel(spec, config)),
        "stateless": parameter_count(StatelessWorldModel(spec)),
        "gru": parameter_count(GRUWorldModel(spec)),
        "field-reset": parameter_count(FieldWorldModel(spec, config)),
        "field-shuffled": parameter_count(FieldWorldModel(spec, config)),
    }


def _expected_manifest(
    spec: WorldSpec,
    config: CassiModalConfig,
    world_fingerprint: str,
    code_digests: dict[str, str],
) -> dict:
    return {
        "schema": MANIFEST_SCHEMA,
        "board_schema": BOARD_SCHEMA,
        "generator_seed": GENERATOR_SEED,
        "training_seed": TRAINING_SEED,
        "optimization_seed": OPTIMIZATION_SEED,
        "optimizer": _expected_optimizer(),
        "mode_layout_id": MODE_LAYOUT_ID,
        "operator_profile_id": OPERATOR_PROFILE_ID,
        "config": asdict(config),
        "spec": asdict(spec),
        "world_fingerprint": world_fingerprint,
        "splits": _expected_splits(),
        "code_digests": code_digests,
    }


def _same_float(left: object, right: float, tolerance: float = 1.0e-6) -> bool:
    return _finite_number(left) and abs(float(left) - right) <= tolerance


def _declared_path(container: object, key: str) -> Path | None:
    if not isinstance(container, dict):
        return None
    value = container.get(key)
    return Path(value) if isinstance(value, str) and value else None


def _mapping(value: object) -> dict:
    return value if isinstance(value, dict) else {}



def _verdict(board: dict, failures: list[str]) -> tuple[str, list[str]]:
    if failures:
        return "FAIL", failures
    field = board["arms"]["field"]["test_mse"]
    stateless = board["arms"]["stateless"]["test_mse"]
    gru = board["arms"]["gru"]["test_mse"]
    reset = board["arms"]["field-reset"]["test_mse"]
    shuffled = board["arms"]["field-shuffled"]["test_mse"]
    if field <= 0.85 * stateless and field <= 1.05 * gru and reset >= 1.10 * field and shuffled >= 1.10 * field:
        return "SUPPORTS", ["held-out field arm and both temporal ablations satisfy the frozen thresholds"]
    if field > 1.10 * stateless and field > 1.10 * gru:
        return "CONTRADICTS", ["the field arm is more than ten percent worse than both trainable controls"]
    return "NULL", ["mechanical checks pass, but the frozen comparative thresholds are not jointly satisfied"]


def verify(board_path: Path, report_path: Path) -> tuple[str, dict]:
    board = json.loads(board_path.read_text(encoding="utf-8"))
    failures: list[str] = []
    spec = WorldSpec()
    config = CassiModalConfig()
    expected_splits = _expected_splits()
    expected_optimizer = _expected_optimizer()
    expected_code_digests = _expected_code_digests()
    expected_parameter_counts = _expected_parameter_counts(spec, config)

    if board.get("schema") != BOARD_SCHEMA:
        failures.append("board schema mismatch")
    if board.get("status") != "COMPLETE":
        failures.append("board status is not COMPLETE")
    if board.get("generator_seed") != GENERATOR_SEED:
        failures.append("generator seed mismatch")
    if board.get("training_seed") != TRAINING_SEED:
        failures.append("training seed mismatch")
    if board.get("optimization_seed") != OPTIMIZATION_SEED:
        failures.append("optimization seed mismatch")
    if board.get("optimizer") != expected_optimizer:
        failures.append("optimizer configuration mismatch")
    if board.get("mode_layout_id") != MODE_LAYOUT_ID:
        failures.append("mode layout identity mismatch")
    if board.get("operator_profile_id") != OPERATOR_PROFILE_ID:
        failures.append("operator profile identity mismatch")
    if board.get("config") != asdict(config):
        failures.append("modal configuration mismatch")
    if board.get("spec") != asdict(spec):
        failures.append("world specification mismatch")
    if board.get("splits") != expected_splits:
        failures.append("episode split declaration mismatch")
    if set(TRAIN_EPISODES) & set(VALIDATION_EPISODES) or set(TRAIN_EPISODES) & set(TEST_EPISODES) or set(VALIDATION_EPISODES) & set(TEST_EPISODES):
        failures.append("episode split overlap")
    if board.get("code_digests") != expected_code_digests:
        failures.append("source or code digest mismatch")

    arms = board.get("arms", {})
    if not isinstance(arms, dict):
        failures.append("arms declaration is not a mapping")
        arms = {}
    if tuple(sorted(arms)) != tuple(sorted(REQUIRED_ARMS)):
        failures.append("arm set mismatch")
    parameter_counts = board.get("parameter_counts")
    if parameter_counts != {name: expected_parameter_counts[name] for name in REQUIRED_ARMS}:
        failures.append("parameter count declaration mismatch")
    for name in REQUIRED_ARMS:
        arm = arms.get(name, {})
        if arm.get("parameters") != expected_parameter_counts[name]:
            failures.append(f"parameter count mismatch: {name}")
    if arms.get("field", {}).get("parameters", 0) > 0:
        field_parameters = arms["field"]["parameters"]
        for name in REQUIRED_ARMS:
            count = arms.get(name, {}).get("parameters")
            if not isinstance(count, int) or not (0.5 * field_parameters <= count <= 2.0 * field_parameters):
                failures.append(f"parameter budget mismatch: {name}")

    for name in ("field", "stateless", "gru"):
        for metric_name in ("train_mse", "validation_mse", "test_mse"):
            if not _finite_number(arms.get(name, {}).get(metric_name)):
                failures.append(f"non-finite metric: {name}.{metric_name}")
    for name in ("field-reset", "field-shuffled"):
        if not _finite_number(arms.get(name, {}).get("test_mse")):
            failures.append(f"non-finite test metric: {name}")

    mechanical = board.get("mechanical", {})
    if not isinstance(mechanical, dict):
        failures.append("mechanical declaration is not a mapping")
        mechanical = {}

    if mechanical.get("finite") is not True:
        failures.append("non-finite trajectory")
    if mechanical.get("data_finite") is not True:
        failures.append("non-finite generated data")
    if mechanical.get("data_bound") != DATA_BOUND:
        failures.append("data bound declaration mismatch")
    if not _finite_number(mechanical.get("max_abs_observation")) or float(mechanical["max_abs_observation"]) > DATA_BOUND:
        failures.append("observation bound exceeded")
    if not _finite_number(mechanical.get("max_abs_target")) or float(mechanical["max_abs_target"]) > DATA_BOUND:
        failures.append("target bound exceeded")
    if mechanical.get("state_bound") != STATE_BOUND:
        failures.append("state bound declaration mismatch")
    if not _finite_number(mechanical.get("max_abs_state")) or float(mechanical["max_abs_state"]) > STATE_BOUND:
        failures.append("state bound exceeded")
    if not _finite_number(mechanical.get("max_state_power")) or float(mechanical["max_state_power"]) < 0.0:
        failures.append("state power is not finite or non-negative")
    if mechanical.get("duplicate_match") is not True:
        failures.append("duplicate training digest mismatch")
    if mechanical.get("test_seed_overlap") is not False:
        failures.append("test split overlaps training")
    if mechanical.get("trajectory_episodes") != {"train": len(TRAIN_EPISODES), "test": len(TEST_EPISODES)}:
        failures.append("trajectory episode coverage mismatch")

    world, episodes = make_dataset(spec)
    if world.fingerprint != board.get("world_fingerprint"):
        failures.append("world generator fingerprint mismatch")
    expected_data = _data_bounds(episodes.values())
    if not _same_float(mechanical.get("max_abs_observation"), expected_data[0]):
        failures.append("observation bound does not replay")
    if not _same_float(mechanical.get("max_abs_target"), expected_data[1]):
        failures.append("target bound does not replay")
    if mechanical.get("data_finite") is not expected_data[2]:
        failures.append("data finiteness does not replay")

    expected_manifest = _expected_manifest(spec, config, world.fingerprint, expected_code_digests)
    manifest_info = board.get("manifest", {})
    if not isinstance(manifest_info, dict):
        failures.append("manifest declaration is not a mapping")
        manifest_info = {}
    expected_manifest_path = (board_path.parent / "l28-manifest.json").resolve()
    declared_manifest_path = _declared_path(manifest_info, "path")
    manifest_payload: dict | None = None
    if declared_manifest_path is None or declared_manifest_path.resolve() != expected_manifest_path:
        failures.append("manifest path is not the board sibling")
    if not expected_manifest_path.is_file():
        failures.append("manifest is missing")
    else:
        actual_manifest_sha256 = _sha256(expected_manifest_path)
        if not isinstance(manifest_info, dict) or manifest_info.get("sha256") != actual_manifest_sha256:
            failures.append("manifest digest mismatch")
        try:
            manifest_payload = json.loads(expected_manifest_path.read_text(encoding="utf-8"))
            if manifest_payload != expected_manifest:
                failures.append("manifest content mismatch")
        except Exception as exc:  # pragma: no cover - verifier reports the reason
            failures.append(f"manifest cannot be read: {type(exc).__name__}: {exc}")

    checkpoint = board.get("checkpoint", {})
    if not isinstance(checkpoint, dict):
        failures.append("checkpoint declaration is not a mapping")
        checkpoint = {}
    expected_checkpoint_path = (board_path.parent / "l28-field.pt").resolve()
    declared_checkpoint_path = _declared_path(checkpoint, "path")
    checkpoint_payload: dict | None = None
    if declared_checkpoint_path is None or declared_checkpoint_path.resolve() != expected_checkpoint_path:
        failures.append("candidate checkpoint path is not the board sibling")
    if not expected_checkpoint_path.is_file():
        failures.append("candidate checkpoint is missing")
    else:
        actual_checkpoint_sha256 = _sha256(expected_checkpoint_path)
        if not isinstance(checkpoint, dict) or checkpoint.get("sha256") != actual_checkpoint_sha256:
            failures.append("candidate checkpoint digest mismatch")
        try:
            loaded = torch.load(expected_checkpoint_path, map_location="cpu", weights_only=True)
            if not isinstance(loaded, dict):
                failures.append("checkpoint payload is not a mapping")
            else:
                checkpoint_payload = loaded
                if loaded.get("schema") != CHECKPOINT_SCHEMA:
                    failures.append("checkpoint schema mismatch")
                if loaded.get("mode_layout_id") != MODE_LAYOUT_ID or loaded.get("operator_profile_id") != OPERATOR_PROFILE_ID:
                    failures.append("checkpoint operator identity mismatch")
                if loaded.get("world_fingerprint") != world.fingerprint:
                    failures.append("checkpoint world fingerprint mismatch")
                if loaded.get("manifest_sha256") != manifest_info.get("sha256"):
                    failures.append("checkpoint manifest digest mismatch")
                if loaded.get("spec") != asdict(spec) or loaded.get("config") != asdict(config):
                    failures.append("checkpoint configuration mismatch")
                if loaded.get("parameter_count") != expected_parameter_counts["field"]:
                    failures.append("checkpoint parameter count mismatch")
                model_state = loaded.get("model_state", {})
                if not isinstance(model_state, dict):
                    failures.append("checkpoint model state is not a mapping")
                elif not all(torch.is_tensor(tensor) and torch.isfinite(tensor).all().item() for tensor in model_state.values()):
                    failures.append("checkpoint contains non-finite or invalid tensor")
        except Exception as exc:  # pragma: no cover - verifier reports the reason
            failures.append(f"checkpoint cannot be read: {type(exc).__name__}: {exc}")

    # Re-evaluate the saved candidate on the declared test split, rather than
    # trusting only the metrics copied into the board JSON.
    if checkpoint_payload is not None:
        try:
            model = FieldWorldModel(spec, config)
            model.load_state_dict(checkpoint_payload["model_state"])
            if _digest_state(model) != mechanical.get("primary_state_digest"):
                failures.append("checkpoint state digest differs from board")
            train = [episodes[seed] for seed in TRAIN_EPISODES]
            test = [episodes[seed] for seed in TEST_EPISODES]
            expected_state = _trajectory_bounds(model, train + test)
            if mechanical.get("finite") is not expected_state[2]:
                failures.append("trajectory finiteness does not replay")
            if not _same_float(mechanical.get("max_abs_state"), expected_state[0]):
                failures.append("state bound does not replay")
            if not _same_float(mechanical.get("max_state_power"), expected_state[1]):
                failures.append("state power does not replay")
            replay_field = _metrics(model, test)
            replay_reset = _metrics_from_predictions(_field_predictions(model, test, "reset"), test)
            replay_shuffled = _metrics_from_predictions(_field_predictions(model, test, "shuffled"), test)
            if abs(replay_field - arms["field"]["test_mse"]) > 1.0e-6:
                failures.append("replayed field metric differs from board")
            if abs(replay_reset - arms["field-reset"]["test_mse"]) > 1.0e-6:
                failures.append("replayed reset metric differs from board")
            if abs(replay_shuffled - arms["field-shuffled"]["test_mse"]) > 1.0e-6:
                failures.append("replayed shuffled metric differs from board")
        except Exception as exc:  # pragma: no cover - verifier reports the reason
            failures.append(f"candidate replay failed: {type(exc).__name__}: {exc}")

    verdict, reasons = _verdict(board, failures)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = _render_report(board, verdict, failures, reasons)
    report_path.write_text(report, encoding="utf-8")
    return verdict, {"verdict": verdict, "failures": failures, "reasons": reasons, "report": str(report_path)}


def _metrics_from_predictions(predictions: list[torch.Tensor], episodes: list) -> float:
    return float(sum(torch.mean((prediction - episode.targets) ** 2).item() for prediction, episode in zip(predictions, episodes)) / len(episodes))


def _format_metric(value: object) -> str:
    return f"{float(value):.10g}" if _finite_number(value) else "invalid"


def _render_report(board: dict, verdict: str, failures: list[str], reasons: list[str]) -> str:
    arms = _mapping(board.get("arms"))
    mechanical = _mapping(board.get("mechanical"))
    manifest = _mapping(board.get("manifest"))
    checkpoint = _mapping(board.get("checkpoint"))
    lines = [
        "# CassiQwen L28—field world-model identification report",
        "",
        f"- Verdict: **{verdict}**",
        f"- Board schema: `{board.get('schema', 'missing')}`",
        f"- Board status: `{board.get('status', 'missing')}`",
        f"- Mode layout: `{board.get('mode_layout_id', 'missing')}`",
        f"- Operator profile: `{board.get('operator_profile_id', 'missing')}`",
        f"- World fingerprint: `{board.get('world_fingerprint', 'missing')}`",
        f"- Manifest SHA-256: `{manifest.get('sha256', 'missing')}`",
        "",
        "## Metrics",
        "",
        "| Arm | Parameters | Train MSE | Validation MSE | Test MSE |",
        "|---|---:|---:|---:|---:|",
    ]
    for name in ("field", "stateless", "gru"):
        arm = arms.get(name, {})
        lines.append(
            f"| `{name}` | {arm.get('parameters', 'invalid')} | "
            f"{_format_metric(arm.get('train_mse'))} | "
            f"{_format_metric(arm.get('validation_mse'))} | "
            f"{_format_metric(arm.get('test_mse'))} |"
        )
    for name in ("field-reset", "field-shuffled"):
        arm = arms.get(name, {})
        lines.append(f"| `{name}` | {arm.get('parameters', 'invalid')} | — | — | {_format_metric(arm.get('test_mse'))} |")
    lines.extend([
        "",
        "## Mechanical checks",
        "",
        f"- finite trajectory: `{mechanical.get('finite', 'missing')}`",
        f"- finite generated data: `{mechanical.get('data_finite', 'missing')}`",
        f"- maximum absolute observation: `{_format_metric(mechanical.get('max_abs_observation'))}`",
        f"- maximum absolute target: `{_format_metric(mechanical.get('max_abs_target'))}`",
        f"- maximum absolute state: `{_format_metric(mechanical.get('max_abs_state'))}`",
        f"- maximum field power: `{_format_metric(mechanical.get('max_state_power'))}`",
        f"- duplicate training digest match: `{mechanical.get('duplicate_match', 'missing')}`",
        f"- checkpoint SHA-256: `{checkpoint.get('sha256', 'missing')}`",
        "",
        "## Decision",
        "",
    ])
    lines.extend(f"- {reason}" for reason in reasons)
    if failures:
        lines.extend(["", "## Failures", "", *[f"- {failure}" for failure in failures]])
    lines.extend([
        "",
        "This board is an offline field-system identification result. It does not establish language quality, multimodal understanding, Qwen intervention benefit, live engine authority, or production adoption.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--board",
        type=Path,
        default=_CASSI_FI_ROOT / "_diag" / "l28-field-world-model" / "l28-board.json",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=ARTIFACT_DIR / "l28-field-world-model" / "L28-FIELD-WORLD-MODEL-REPORT.md",
    )
    parser.add_argument(
        "--require-supports",
        action="store_true",
        help="return non-zero unless the mechanically valid board reaches SUPPORTS",
    )
    args = parser.parse_args()
    try:
        verdict, payload = verify(args.board, args.report)
    except Exception as exc:  # pragma: no cover - CLI safety boundary
        payload = {"verdict": "FAIL", "failures": [f"verifier crashed: {type(exc).__name__}: {exc}"]}
        print(json.dumps(payload, indent=2))
        return 1
    print(json.dumps(payload, indent=2))
    if verdict == "FAIL":
        return 1
    if args.require_supports and verdict != "SUPPORTS":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
