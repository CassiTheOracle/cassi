"""Offline probes for frozen Qwen residual and attention captures.

This script never loads or changes model weights.  It fits small ridge readouts on
one prompt-level sample per independent campaign trajectory.  The primary target
is the screen-time continuation register (hedge/direct); a secondary template
readout is a surface sanity check.  Every result has grouped cross-validation,
majority and shuffled-label controls, and a leave-template-out read for the
register target.

Usage::

    python train_latent_decoders.py --mode residual
    python train_latent_decoders.py --mode attention
    python train_latent_decoders.py --mode all

The attention files are ggml tensors with ne[0] as the fastest dimension.  Their
prompt probability shape is normally [key_capacity, prompt_tokens, heads], so the
last prompt query is converted to a per-head key-position profile before fitting.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[1]
PROBE_DIAG = WORKSPACE / "CassiQwen" / "native" / "llama.cpp" / "_diag" / "probe-campaign"
SELECTION_PATH = PROBE_DIAG / "selection.json"
SCREEN_ROOT = PROBE_DIAG / "screen"
CAPTURE_ROOT = PROBE_DIAG / "captures"
CAPTURE_RECEIPT_ROOT = PROBE_DIAG / "capture"
ATTENTION_ROOT = PROBE_DIAG / "attention"
DEFAULT_OUT = PROBE_DIAG / "decoder" / "decoder-receipt.json"

# Reuse the already-tested grouped ridge implementation.  Importing this module
# has no run-time side effects; its CLI is guarded by __main__.
sys.path.insert(0, str(HERE))
from probe_decode import balanced_accuracy, balanced_group_folds, fit_predict  # noqa: E402

LAYER_RE = re.compile(r"^layer-(\d+)\.f32$")
ATTENTION_RE = re.compile(r"^layer-(\d+)-attn-probs-prompt\.f32$")
TARGET_NAMES = {0: "direct", 1: "hedge"}
TEMPLATE_NAMES = {0: "qa", 1: "brief"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(WORKSPACE.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def finite_float(value: float) -> float | None:
    return float(value) if math.isfinite(float(value)) else None


def class_counts(labels: np.ndarray, names: dict[int, str]) -> dict[str, int]:
    return {names.get(int(value), str(int(value))): int(count)
            for value, count in sorted(Counter(labels.tolist()).items())}


def selection_rows() -> dict[str, dict[str, Any]]:
    selection = load_json(SELECTION_PATH)
    if not selection:
        raise SystemExit(f"missing selection manifest: {SELECTION_PATH}")
    rows: dict[str, dict[str, Any]] = {}
    for family, family_rows in (selection.get("rows") or {}).items():
        if family not in TARGET_NAMES.values():
            continue
        for row in family_rows:
            prompt_id = str(row["id"])
            if prompt_id in rows:
                raise SystemExit(f"duplicate prompt in selection: {prompt_id}")
            rows[prompt_id] = {
                "id": prompt_id,
                "label": family,
                "template": str(row.get("template", "unknown")),
                "prompt_sha256": row.get("prompt_sha256"),
                "screen_generation_text": row.get("generation_text", ""),
                "markers": list(row.get("markers", [])),
            }
    if not rows:
        raise SystemExit("selection manifest has no usable hedge/direct rows")
    return rows


def receipt_for(stage_root: Path, prompt_id: str) -> dict[str, Any] | None:
    return load_json(stage_root / prompt_id / "receipt.json")


def layer_files(directory: Path) -> dict[int, Path]:
    out: dict[int, Path] = {}
    if not directory.is_dir():
        return out
    for path in directory.iterdir():
        match = LAYER_RE.fullmatch(path.name)
        if match:
            out[int(match.group(1))] = path
    return out


def campaign_rows(selected: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for prompt_id in sorted(selected):
        meta = selected[prompt_id]
        screen = receipt_for(SCREEN_ROOT, prompt_id)
        capture = receipt_for(CAPTURE_RECEIPT_ROOT, prompt_id)
        capture_dir = CAPTURE_ROOT / prompt_id
        if screen is None or capture is None:
            continue
        screen_text = screen.get("generation_text", "")
        capture_text = capture.get("generation_text", "")
        fresh = capture.get("register") or {}
        rows.append({
            **meta,
            "screen_receipt": SCREEN_ROOT / prompt_id / "receipt.json",
            "capture_receipt": CAPTURE_RECEIPT_ROOT / prompt_id / "receipt.json",
            "capture_dir": capture_dir,
            "capture_layers": layer_files(capture_dir),
            "screen_text_reproduced": screen_text == capture_text,
            "capture_label": fresh.get("label"),
            "capture_generation_text": capture_text,
            "prompt_tokens": len(capture.get("prompt_token_ids") or []),
            "generation_tokens": len(capture.get("generation_token_ids") or []),
        })
    return rows


def evaluate_cv(
    features: np.ndarray,
    labels: np.ndarray,
    groups: list[str],
    folds: int,
    shuffles: int,
    seed: int,
    names: dict[int, str],
) -> dict[str, Any]:
    """Evaluate a probe without allowing rows from one prompt into both sides."""
    n = int(len(labels))
    unique_groups = sorted(set(groups))
    if n < 4 or len(unique_groups) < 2:
        return {
            "supported": False,
            "reason": f"need at least 4 samples and 2 prompt groups (got {n}, {len(unique_groups)})",
            "n_samples": n,
            "n_groups": len(unique_groups),
            "class_counts": class_counts(labels, names),
        }
    if len(set(labels.tolist())) < 2:
        return {
            "supported": False,
            "reason": "only one target class is present",
            "n_samples": n,
            "n_groups": len(unique_groups),
            "class_counts": class_counts(labels, names),
        }

    partitions = balanced_group_folds(groups, min(max(int(folds), 2), len(unique_groups)))
    measured: list[dict[str, Any]] = []
    n_shuffles = max(0, int(shuffles))
    shuffle_accuracy_runs: list[list[float]] = [[] for _ in range(n_shuffles)]
    shuffle_balanced_runs: list[list[float]] = [[] for _ in range(n_shuffles)]
    rng = np.random.default_rng(seed)
    for fold_index, test in enumerate(partitions):
        train = np.setdiff1d(np.arange(n), test)
        train_classes = set(labels[train].tolist())
        test_classes = set(labels[test].tolist())
        if len(train) < 4 or len(train_classes) < 2:
            measured.append({
                "fold": fold_index,
                "supported": False,
                "reason": "training fold does not contain both target classes",
                "test_groups": [groups[i] for i in test],
                "test_class_counts": class_counts(labels[test], names),
            })
            continue
        try:
            predicted = fit_predict(features, labels, train, test, groups)
        except (FloatingPointError, np.linalg.LinAlgError, ValueError) as error:
            measured.append({
                "fold": fold_index,
                "supported": False,
                "reason": f"ridge fit failed: {error}",
            })
            continue
        majority = Counter(labels[train].tolist()).most_common(1)[0][0]
        shuffled_scores: list[float] = []
        shuffled_balanced: list[float] = []
        for shuffle_index in range(n_shuffles):
            shuffled_labels = labels.copy()
            shuffled_labels[train] = rng.permutation(labels[train])
            try:
                shuffled_predicted = fit_predict(
                    features, shuffled_labels, train, test, groups)
            except (FloatingPointError, np.linalg.LinAlgError, ValueError):
                continue
            score = float((shuffled_predicted == labels[test]).mean())
            balanced_score = balanced_accuracy(shuffled_predicted, labels[test])
            shuffled_scores.append(score)
            shuffled_balanced.append(balanced_score)
            shuffle_accuracy_runs[shuffle_index].append(score)
            shuffle_balanced_runs[shuffle_index].append(balanced_score)
        measured.append({
            "fold": fold_index,
            "supported": True,
            "test_groups": [groups[i] for i in test],
            "test_class_counts": class_counts(labels[test], names),
            "accuracy": float((predicted == labels[test]).mean()),
            "balanced_accuracy": balanced_accuracy(predicted, labels[test]),
            "majority_accuracy": float((labels[test] == majority).mean()),
            "shuffled_accuracy": shuffled_scores,
            "shuffled_balanced_accuracy": shuffled_balanced,
        })

    valid = [row for row in measured if row.get("supported")]
    if not valid:
        return {
            "supported": False,
            "reason": "no cross-validation fold had two train classes",
            "n_samples": n,
            "n_groups": len(unique_groups),
            "class_counts": class_counts(labels, names),
            "folds": measured,
        }
    shuffled = [
        float(np.mean(run))
        for run in shuffle_accuracy_runs
        if len(run) == len(valid)
    ]
    shuffled_balanced = [
        float(np.mean(run))
        for run in shuffle_balanced_runs
        if len(run) == len(valid)
    ]
    accuracy = float(np.mean([row["accuracy"] for row in valid]))
    majority = float(np.mean([row["majority_accuracy"] for row in valid]))
    shuffled_mean = float(np.mean(shuffled)) if shuffled else None
    shuffled_sd = float(np.std(shuffled)) if shuffled else None
    balanced = float(np.mean([row["balanced_accuracy"] for row in valid]))
    shuffled_balanced_mean = float(np.mean(shuffled_balanced)) if shuffled_balanced else None
    shuffled_balanced_sd = float(np.std(shuffled_balanced)) if shuffled_balanced else None
    return {
        "supported": True,
        "n_samples": n,
        "n_groups": len(unique_groups),
        "class_counts": class_counts(labels, names),
        "n_measured_folds": len(valid),
        "accuracy": accuracy,
        "balanced_accuracy": balanced,
        "majority_accuracy": majority,
        "shuffled_accuracy_mean": shuffled_mean,
        "shuffled_accuracy_sd": shuffled_sd,
        "shuffled_balanced_accuracy_mean": shuffled_balanced_mean,
        "shuffled_balanced_accuracy_sd": shuffled_balanced_sd,
        "shuffled_accuracy_runs": shuffled,
        "shuffled_balanced_accuracy_runs": shuffled_balanced,
        "shuffled_n": len(shuffled),
        "beats_majority": bool(accuracy > majority),
        "above_shuffled": bool(
            shuffled_mean is not None and accuracy > shuffled_mean + 3.0 * (shuffled_sd or 0.0)
        ),
        "folds": measured,
    }


def evaluate_template_holdout(
    features: np.ndarray,
    labels: np.ndarray,
    templates: list[str],
    groups: list[str],
    shuffles: int,
    seed: int,
    names: dict[int, str],
) -> dict[str, Any]:
    """Train on one prompt surface and test on the other."""
    rows: dict[str, Any] = {}
    for held_out in sorted(set(templates)):
        test = np.array([i for i, value in enumerate(templates) if value == held_out])
        train = np.array([i for i, value in enumerate(templates) if value != held_out])
        if len(test) == 0 or len(train) < 4 or len(set(labels[train].tolist())) < 2:
            rows[held_out] = {
                "supported": False,
                "reason": "held-out split has no samples or training lacks both classes",
                "train_samples": int(len(train)),
                "test_samples": int(len(test)),
            }
            continue
        # Reuse the same fitting/control semantics on this fixed split.  The
        # groups remain prompt IDs, so no prompt can leak across the boundary.
        rng = np.random.default_rng(seed + sum(ord(c) for c in held_out))
        predicted = fit_predict(features, labels, train, test, groups)
        majority = Counter(labels[train].tolist()).most_common(1)[0][0]
        shuffled_scores: list[float] = []
        shuffled_balanced: list[float] = []
        for _ in range(max(0, int(shuffles))):
            shuffled_labels = labels.copy()
            shuffled_labels[train] = rng.permutation(labels[train])
            shuffled_predicted = fit_predict(features, shuffled_labels, train, test, groups)
            shuffled_scores.append(float((shuffled_predicted == labels[test]).mean()))
            shuffled_balanced.append(balanced_accuracy(shuffled_predicted, labels[test]))
        accuracy = float((predicted == labels[test]).mean())
        shuffled_mean = float(np.mean(shuffled_scores)) if shuffled_scores else None
        shuffled_sd = float(np.std(shuffled_scores)) if shuffled_scores else None
        rows[held_out] = {
            "supported": True,
            "train_samples": int(len(train)),
            "test_samples": int(len(test)),
            "train_class_counts": class_counts(labels[train], names),
            "test_class_counts": class_counts(labels[test], names),
            "accuracy": accuracy,
            "balanced_accuracy": balanced_accuracy(predicted, labels[test]),
            "majority_accuracy": float((labels[test] == majority).mean()),
            "shuffled_accuracy_mean": shuffled_mean,
            "shuffled_accuracy_sd": shuffled_sd,
            "shuffled_balanced_accuracy_mean": (
                float(np.mean(shuffled_balanced)) if shuffled_balanced else None
            ),
            "shuffled_balanced_accuracy_sd": (
                float(np.std(shuffled_balanced)) if shuffled_balanced else None
            ),
            "shuffled_n": len(shuffled_scores),
            "beats_majority": bool(accuracy > float((labels[test] == majority).mean())),
            "above_shuffled": bool(
                shuffled_mean is not None and accuracy > shuffled_mean + 3.0 * (shuffled_sd or 0.0)
            ),
        }
    return rows


def probe_block(
    features: np.ndarray,
    target_values: np.ndarray,
    groups: list[str],
    templates: list[str],
    folds: int,
    shuffles: int,
    seed: int,
    names: dict[int, str],
    include_template_holdout: bool,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "feature_dim": int(features.shape[1]),
        "target": class_counts(target_values, names),
        "group_cv": evaluate_cv(features, target_values, groups, folds, shuffles, seed, names),
    }
    if include_template_holdout:
        result["template_holdout"] = evaluate_template_holdout(
            features, target_values, templates, groups, shuffles, seed + 7919, names
        )
    return result


def ggml_tensor(path: Path, shape: tuple[int, ...]) -> np.ndarray | None:
    raw = np.fromfile(path, dtype=np.float32)
    expected = int(math.prod(shape))
    if expected <= 0 or raw.size != expected or not np.isfinite(raw).all():
        return None
    if len(shape) == 3:
        # ggml stores ne[0] fastest; NumPy's C-order has the last axis fastest.
        return raw.reshape(tuple(reversed(shape))).transpose(2, 1, 0)
    if len(shape) == 2:
        return raw.reshape((shape[1], shape[0])).T
    return None


def attention_prompt_files(row: dict[str, Any]) -> tuple[dict[int, Path], tuple[int, ...]]:
    receipt = receipt_for(ATTENTION_ROOT, row["id"])
    if not receipt:
        return {}, ()
    info = receipt.get("attention_prompt") or {}
    shape = tuple(int(value) for value in (info.get("probs_shape") or []))
    if len(shape) != 3:
        return {}, shape
    files: dict[int, Path] = {}
    for entry in info.get("probs_files") or []:
        try:
            layer = int(entry["layer"])
            name = str(entry["name"])
        except (KeyError, TypeError, ValueError):
            continue
        path = ATTENTION_ROOT / row["id"] / name
        if path.is_file():
            files[layer] = path
    return files, shape


def attention_profiles(rows: list[dict[str, Any]]) -> tuple[dict[int, list[tuple[dict[str, Any], np.ndarray]]], dict[str, Any]]:
    by_layer: dict[int, list[tuple[dict[str, Any], np.ndarray]]] = {}
    malformed = 0
    for row in rows:
        files, shape = attention_prompt_files(row)
        if not files:
            continue
        n_prompt = max(1, int(row.get("prompt_tokens") or 1))
        for layer, path in files.items():
            tensor = ggml_tensor(path, shape)
            if tensor is None:
                malformed += 1
                continue
            key_count = min(n_prompt, tensor.shape[0])
            query_index = min(n_prompt, tensor.shape[1]) - 1
            profile = np.asarray(tensor[:key_count, query_index, :], dtype=np.float32)
            if profile.ndim != 2 or not np.isfinite(profile).all():
                malformed += 1
                continue
            by_layer.setdefault(layer, []).append((row, profile))
    coverage = {
        "attention_rows_with_any_probs": len({item[0]["id"] for values in by_layer.values() for item in values}),
        "probability_layers": sorted(by_layer),
        "malformed_files": malformed,
    }
    return by_layer, coverage


def attention_block(
    rows: list[dict[str, Any]],
    folds: int,
    shuffles: int,
    seed: int,
) -> dict[str, Any]:
    by_layer, coverage = attention_profiles(rows)
    result: dict[str, Any] = {
        "coverage": coverage,
        "layers": {},
        "head_rankings": {},
    }
    for layer in sorted(by_layer):
        members = by_layer[layer]
        if len(members) < 4:
            result["layers"][str(layer)] = {
                "supported": False,
                "reason": f"only {len(members)} prompt profiles",
            }
            continue
        n_heads = min(profile.shape[1] for _, profile in members)
        max_keys = max(profile.shape[0] for _, profile in members)
        selected = [(row, profile[:, :n_heads]) for row, profile in members]
        layer_rows = [row for row, _ in selected]
        groups = [row["id"] for row in layer_rows]
        templates = [row["template"] for row in layer_rows]
        register = np.array([1 if row["label"] == "hedge" else 0 for row in layer_rows], dtype=np.int64)
        template_target = np.array([1 if value == "brief" else 0 for value in templates], dtype=np.int64)
        all_features = np.zeros((len(selected), max_keys * n_heads), dtype=np.float32)
        head_features = [np.zeros((len(selected), max_keys), dtype=np.float32) for _ in range(n_heads)]
        for index, (_, profile) in enumerate(selected):
            for head in range(n_heads):
                values = profile[:, head]
                all_features[index, head * max_keys:head * max_keys + len(values)] = values
                head_features[head][index, :len(values)] = values
        layer_result = {
            "n_samples": len(selected),
            "n_groups": len(set(groups)),
            "n_heads": n_heads,
            "max_prompt_keys": max_keys,
            "register": probe_block(
                all_features, register, groups, templates, folds, shuffles,
                seed + layer * 101, TARGET_NAMES, True,
            ),
            "template": probe_block(
                all_features, template_target, groups, templates, folds, shuffles,
                seed + layer * 101 + 1, TEMPLATE_NAMES, False,
            ),
        }
        head_rows: list[dict[str, Any]] = []
        for head, features in enumerate(head_features):
            block = probe_block(
                features, register, groups, templates, folds, shuffles,
                seed + layer * 1009 + head + 17, TARGET_NAMES, True,
            )
            cv = block["group_cv"]
            head_rows.append({
                "head": head,
                "mean_entropy": float(np.mean([
                    -float(np.sum(np.where(values > 0, values * np.log(np.maximum(values, 1e-30)), 0.0)))
                    for values in features
                ])),
                **block,
            })
        head_rows.sort(
            key=lambda item: (
                item["group_cv"].get("above_shuffled", False),
                item["group_cv"].get("balanced_accuracy", -1.0),
                item["group_cv"].get("accuracy", -1.0),
            ),
            reverse=True,
        )
        result["layers"][str(layer)] = layer_result
        result["head_rankings"][str(layer)] = head_rows
    return result


def residual_block(rows: list[dict[str, Any]], folds: int, shuffles: int, seed: int) -> dict[str, Any]:
    usable = [row for row in rows if row["screen_text_reproduced"] and row["capture_layers"]]
    layer_sets = [set(row["capture_layers"]) for row in usable]
    common_layers = sorted(set.intersection(*layer_sets)) if layer_sets else []
    groups = [row["id"] for row in usable]
    templates = [row["template"] for row in usable]
    register = np.array([1 if row["label"] == "hedge" else 0 for row in usable], dtype=np.int64)
    template_target = np.array([1 if value == "brief" else 0 for value in templates], dtype=np.int64)
    out: dict[str, Any] = {
        "n_selected_rows": len(rows),
        "n_usable_rows": len(usable),
        "n_groups": len(set(groups)),
        "common_layers": common_layers,
        "layers": {},
    }
    for layer in common_layers:
        vectors = [np.fromfile(row["capture_layers"][layer], dtype=np.float32) for row in usable]
        widths = {int(vector.size) for vector in vectors}
        if len(widths) != 1 or not all(np.isfinite(vector).all() for vector in vectors):
            out["layers"][str(layer)] = {"supported": False, "reason": "width mismatch or non-finite residual"}
            continue
        features = np.stack(vectors).astype(np.float32, copy=False)
        out["layers"][str(layer)] = {
            "n_samples": int(features.shape[0]),
            "feature_dim": int(features.shape[1]),
            "register": probe_block(
                features, register, groups, templates, folds, shuffles,
                seed + layer * 101, TARGET_NAMES, True,
            ),
            "template": probe_block(
                features, template_target, groups, templates, folds, shuffles,
                seed + layer * 101 + 1, TEMPLATE_NAMES, False,
            ),
        }
    return out


def best_rows(block: dict[str, Any], target: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for layer, values in (block.get("layers") or {}).items():
        probe = values.get(target) or {}
        cv = probe.get("group_cv") or {}
        if cv.get("supported"):
            rows.append({
                "layer": int(layer),
                "accuracy": cv.get("accuracy"),
                "balanced_accuracy": cv.get("balanced_accuracy"),
                "majority_accuracy": cv.get("majority_accuracy"),
                "shuffled_accuracy_mean": cv.get("shuffled_accuracy_mean"),
                "above_shuffled": cv.get("above_shuffled"),
            })
    rows.sort(key=lambda row: (
        row.get("balanced_accuracy") if row.get("balanced_accuracy") is not None else -1.0,
        row.get("accuracy") if row.get("accuracy") is not None else -1.0,
    ), reverse=True)
    return rows[:5]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("residual", "attention", "all"), default="all")
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--shuffles", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20260917)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    selected = selection_rows()
    rows = campaign_rows(selected)
    exact = [row for row in rows if row["screen_text_reproduced"]]
    label_drift = Counter(
        (row["label"], row["capture_label"] or "missing")
        for row in rows
    )
    summary_path = PROBE_DIAG / "capture-summary.json"
    inventory_path = HERE / "capture-inventory.json"
    receipt: dict[str, Any] = {
        "schema": "cassi.hidden-state-decoder.v1",
        "model_unchanged": True,
        "model_input": "frozen read-only captures",
        "protocol": {
            "sample_unit": "one prompt trajectory, prompt-final residual or last-query attention profile",
            "group": "prompt id; no continuation tokens are separate samples",
            "targets": {
                "register": "screen-time lexical continuation label: direct=0, hedge=1",
                "template": "prompt surface: qa=0, brief=1",
            },
            "controls": ["majority-class baseline", "within-training-fold shuffled labels"],
            "cross_validation": f"{args.folds} grouped folds plus leave-template-out for register",
            "seed": args.seed,
        },
        "source": {
            "selection": rel(SELECTION_PATH),
            "selection_sha256": sha256_file(SELECTION_PATH) if SELECTION_PATH.is_file() else None,
            "screen_root": rel(SCREEN_ROOT),
            "capture_root": rel(CAPTURE_ROOT),
            "attention_root": rel(ATTENTION_ROOT),
            "capture_summary": rel(summary_path),
            "capture_summary_sha256": sha256_file(summary_path) if summary_path.is_file() else None,
            "capture_inventory": rel(inventory_path),
            "capture_inventory_sha256": sha256_file(inventory_path) if inventory_path.is_file() else None,
            "trainer_sha256": sha256_file(HERE / "train_latent_decoders.py"),
        },
        "coverage": {
            "selected_prompts": len(selected),
            "capture_receipts": len(rows),
            "exact_screen_reproductions": len(exact),
            "screen_reproduction_rate": (len(exact) / len(rows)) if rows else None,
            "independent_groups": len({row["id"] for row in exact}),
            "screen_class_counts": dict(Counter(row["label"] for row in exact)),
            "capture_label_pairs": {f"{a}->{b}": count for (a, b), count in sorted(label_drift.items())},
            "capture_label_drift_is_lexical_marker_only": bool(
                rows and all(row["screen_text_reproduced"] for row in rows)
            ),
        },
    }
    if args.mode in ("residual", "all"):
        receipt["residual"] = residual_block(exact, args.folds, args.shuffles, args.seed)
    if args.mode in ("attention", "all"):
        receipt["attention"] = attention_block(exact, args.folds, args.shuffles, args.seed + 50000)

    # A small machine-readable index keeps the headline easy to inspect without
    # discarding the complete per-layer and per-head fold evidence.
    receipt["headline"] = {}
    for name in ("residual", "attention"):
        block = receipt.get(name)
        if not block:
            continue
        receipt["headline"][name] = {
            "best_register_layers": best_rows(block, "register"),
            "best_template_layers": best_rows(block, "template"),
        }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=1, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "out": rel(args.out),
        "selected": len(selected),
        "capture_receipts": len(rows),
        "exact_reproductions": len(exact),
        "mode": args.mode,
        "headline": receipt["headline"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
