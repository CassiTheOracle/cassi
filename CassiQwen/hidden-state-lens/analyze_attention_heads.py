"""Template-stratified probes and position summaries for frozen attention captures.

This is an offline analysis of the attention tensors produced by the read-only
llama.cpp latent campaign.  It never loads model weights or calls llama.cpp.
Each attention head is evaluated three ways:

* pooled grouped cross-validation across all prompt templates;
* grouped cross-validation separately within each template;
* leave-one-template-out transfer.

The receipt also reports where each head places its last-query mass, including
label-conditioned differences and the dominant token pieces at each position.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[1]
PROBE_DIAG = WORKSPACE / "CassiQwen" / "native" / "llama.cpp" / "_diag" / "probe-campaign"
SELECTION_PATH = PROBE_DIAG / "selection.json"
ATTENTION_ROOT = PROBE_DIAG / "attention"
DECODER_RECEIPT = PROBE_DIAG / "decoder" / "decoder-receipt.json"
DEFAULT_OUT = PROBE_DIAG / "decoder" / "attention-head-analysis.json"

# These helpers are the tested, read-only loaders and grouped ridge evaluator
# used by train_latent_decoders.py.
import train_latent_decoders as trainer  # noqa: E402
from lens_common import MODELS, token_text  # noqa: E402


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
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def exact_campaign_rows() -> list[dict[str, Any]]:
    selected = trainer.selection_rows()
    rows = trainer.campaign_rows(selected)
    exact = [row for row in rows if row["screen_text_reproduced"]]
    if len(exact) < 4:
        raise SystemExit(f"need at least four exact campaign rows, got {len(exact)}")
    return exact


def profile_matrix(
    members: list[tuple[dict[str, Any], np.ndarray]],
    head: int,
) -> np.ndarray:
    max_keys = max(profile.shape[0] for _, profile in members)
    matrix = np.zeros((len(members), max_keys), dtype=np.float32)
    for index, (_, profile) in enumerate(members):
        if head >= profile.shape[1]:
            raise SystemExit(f"head {head} exceeds profile width {profile.shape[1]}")
        matrix[index, :profile.shape[0]] = profile[:, head]
    if not np.isfinite(matrix).all():
        raise SystemExit("non-finite attention profile")
    return matrix


def target_arrays(rows: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray, list[str], list[str]]:
    register = np.array([1 if row["label"] == "hedge" else 0 for row in rows], dtype=np.int64)
    template = np.array([1 if row["template"] == "brief" else 0 for row in rows], dtype=np.int64)
    groups = [row["id"] for row in rows]
    templates = [row["template"] for row in rows]
    return register, template, groups, templates


def top_positions(values: np.ndarray, limit: int = 5) -> list[dict[str, Any]]:
    order = np.argsort(values)[::-1][:limit]
    return [
        {"position": int(index), "value": float(values[index])}
        for index in order
    ]


def token_piece_counts(rows: list[dict[str, Any]], position: int) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    vocab = MODELS[5120]
    for row in rows:
        receipt = load_json(row["capture_receipt"])
        ids = (receipt or {}).get("prompt_token_ids") or []
        if position >= len(ids):
            continue
        try:
            piece = token_text(int(ids[position]), vocab)
        except (OSError, RuntimeError, ValueError):
            continue
        counts[piece] += 1
    return [
        {"text": text, "count": int(count)}
        for text, count in counts.most_common(5)
    ]


def position_summary(
    members: list[tuple[dict[str, Any], np.ndarray]],
    head: int,
) -> dict[str, Any]:
    rows = [row for row, _ in members]
    matrix = profile_matrix(members, head)
    labels = np.array([1 if row["label"] == "hedge" else 0 for row in rows], dtype=np.int64)
    templates = np.array([1 if row["template"] == "brief" else 0 for row in rows], dtype=np.int64)
    all_mean = matrix.mean(axis=0)
    direct_mean = matrix[labels == 0].mean(axis=0) if np.any(labels == 0) else None
    hedge_mean = matrix[labels == 1].mean(axis=0) if np.any(labels == 1) else None
    qa_mean = matrix[templates == 0].mean(axis=0) if np.any(templates == 0) else None
    brief_mean = matrix[templates == 1].mean(axis=0) if np.any(templates == 1) else None
    label_delta = (hedge_mean - direct_mean) if direct_mean is not None and hedge_mean is not None else np.zeros_like(all_mean)
    template_delta = (brief_mean - qa_mean) if brief_mean is not None and qa_mean is not None else np.zeros_like(all_mean)
    positions = []
    for position in range(matrix.shape[1]):
        positions.append({
            "position": position,
            "mean_attention": float(all_mean[position]),
            "direct_mean": float(direct_mean[position]) if direct_mean is not None else None,
            "hedge_mean": float(hedge_mean[position]) if hedge_mean is not None else None,
            "hedge_minus_direct": float(label_delta[position]),
            "qa_mean": float(qa_mean[position]) if qa_mean is not None else None,
            "brief_mean": float(brief_mean[position]) if brief_mean is not None else None,
            "brief_minus_qa": float(template_delta[position]),
            "token_pieces": token_piece_counts(rows, position),
        })
    return {
        "n_samples": len(rows),
        "n_prompt_key_positions": matrix.shape[1],
        "positions": positions,
        "top_by_mean": top_positions(all_mean),
        "top_hedge_enrichment": top_positions(label_delta),
        "top_direct_enrichment": top_positions(-label_delta),
        "top_brief_enrichment": top_positions(template_delta),
        "top_qa_enrichment": top_positions(-template_delta),
    }


def supported_balanced(block: dict[str, Any] | None) -> float | None:
    if not block or not block.get("supported"):
        return None
    value = block.get("balanced_accuracy")
    return float(value) if value is not None else None


def head_record(
    layer: int,
    head: int,
    members: list[tuple[dict[str, Any], np.ndarray]],
    folds: int,
    shuffles: int,
    seed: int,
) -> dict[str, Any]:
    rows = [row for row, _ in members]
    features = profile_matrix(members, head)
    register, _, groups, templates = target_arrays(rows)
    pooled = trainer.evaluate_cv(features, register, groups, folds, shuffles, seed, trainer.TARGET_NAMES)
    within: dict[str, Any] = {}
    for template in sorted(set(templates)):
        indices = [index for index, value in enumerate(templates) if value == template]
        subset_features = features[indices]
        subset_groups = [groups[index] for index in indices]
        within[template] = trainer.evaluate_cv(
            subset_features,
            register[indices],
            subset_groups,
            folds,
            shuffles,
            seed + sum(ord(char) for char in template),
            trainer.TARGET_NAMES,
        )
    transfer = trainer.evaluate_template_holdout(
        features, register, templates, groups, shuffles, seed + 7919, trainer.TARGET_NAMES
    )
    return {
        "layer": layer,
        "head": head,
        "n_samples": len(rows),
        "pooled_group_cv": pooled,
        "within_template_group_cv": within,
        "leave_template_out": transfer,
        "position_summary": position_summary(members, head),
    }


def rank_records(records: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    def score(record: dict[str, Any]) -> tuple[float, float, float]:
        if field == "within_template":
            values = [
                supported_balanced(value)
                for value in (record.get("within_template_group_cv") or {}).values()
            ]
        else:
            values = [
                supported_balanced(value)
                for value in (record.get("leave_template_out") or {}).values()
            ]
        valid = [value for value in values if value is not None]
        if not valid:
            return (-1.0, -1.0, -1.0)
        return (min(valid), float(np.mean(valid)), max(valid))

    ranked = sorted(
        records,
        key=lambda record: (*score(record), record.get("layer", -1), record.get("head", -1)),
        reverse=True,
    )
    return [
        {
            "layer": record["layer"],
            "head": record["head"],
            "min_balanced_accuracy": score(record)[0],
            "mean_balanced_accuracy": score(record)[1],
            "max_balanced_accuracy": score(record)[2],
        }
        for record in ranked[:10]
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--folds", type=int, default=3)
    parser.add_argument("--shuffles", type=int, default=32)
    parser.add_argument("--seed", type=int, default=20260917)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    rows = exact_campaign_rows()
    by_layer, coverage = trainer.attention_profiles(rows)
    receipt: dict[str, Any] = {
        "schema": "cassi.attention-head-analysis.v1",
        "model_unchanged": True,
        "model_input": "frozen read-only attention probability captures",
        "protocol": {
            "sample_unit": "one prompt trajectory, last prompt query per-head key profile",
            "register_target": "screen-time lexical continuation label: direct=0, hedge=1",
            "within_template": f"{args.folds} grouped folds separately for each prompt template",
            "transfer": "train on one prompt template and test on the other",
            "controls": ["majority-class baseline", "within-training-fold shuffled labels"],
            "seed": args.seed,
        },
        "source": {
            "selection": rel(SELECTION_PATH),
            "selection_sha256": sha256_file(SELECTION_PATH),
            "attention_root": rel(ATTENTION_ROOT),
            "decoder_receipt": rel(DECODER_RECEIPT),
            "decoder_receipt_sha256": sha256_file(DECODER_RECEIPT),
            "trainer": rel(HERE / "train_latent_decoders.py"),
            "trainer_sha256": sha256_file(HERE / "train_latent_decoders.py"),
        },
        "coverage": {
            "selected_prompts": len(rows),
            "independent_groups": len({row["id"] for row in rows}),
            "class_counts": dict(Counter(row["label"] for row in rows)),
            "template_counts": dict(Counter(row["template"] for row in rows)),
            **coverage,
        },
        "layers": {},
    }

    all_records: list[dict[str, Any]] = []
    for layer in sorted(by_layer):
        members = by_layer[layer]
        n_heads = min(profile.shape[1] for _, profile in members)
        layer_records = [
            head_record(
                layer,
                head,
                members,
                args.folds,
                args.shuffles,
                args.seed + layer * 1009 + head,
            )
            for head in range(n_heads)
        ]
        all_records.extend(layer_records)
        receipt["layers"][str(layer)] = {
            "n_heads": n_heads,
            "n_samples": len(members),
            "heads": layer_records,
        }

    receipt["headline"] = {
        "head_count": len(all_records),
        "best_within_template": rank_records(all_records, "within_template"),
        "best_leave_template_out": rank_records(all_records, "leave_template_out"),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=1, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "out": rel(args.out),
        "rows": len(rows),
        "layers": coverage["probability_layers"],
        "heads": len(all_records),
        "headline": receipt["headline"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
