"""Mid-stack probe over the campaign captures.

Two reads are measured, both with group-aware folds that hold out whole trajectories:

  next-token  label = the token the model itself generated next at that step, so the
              label is not constant inside a trajectory and a held-out trajectory does
              not automatically hide a class.  The reference ceilings are the same probe
              at the last captured layer and the model's own top-1 from the step logits.
  register    label = the register of the model's own continuation for that prompt,
              hedge or direct, with the two surface templates held apart so a probe
              trained on one template can be tested on the other.

Every reported row carries the trajectory count, the shuffled-label control, and the
most-frequent baseline beside the accuracy.  A row that fails the trajectory gate is
reported as blocked, never as a number.

Usage:
    python probe_midlayer.py [--folds 5] [--shuffles 8] [--min-class 8]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
LENS = HERE.parent
WORKSPACE = HERE.parents[2]
DIAG = WORKSPACE / "CassiQwen" / "native" / "llama.cpp" / "_diag" / "probe-campaign"
sys.path.insert(0, str(LENS))
import probe_decode as P  # noqa: E402  the existing ridge-probe instrument

MIN_TRAJECTORIES = 20


def read_row(path: Path, width: int) -> np.ndarray:
    values = np.fromfile(path, dtype="<f4")
    if values.size != width:
        raise SystemExit(f"{path}: expected {width} floats, found {values.size}")
    if not np.isfinite(values).all():
        raise SystemExit(f"{path}: non-finite value")
    return values


def summary() -> dict:
    path = DIAG / "capture-summary.json"
    if not path.exists():
        raise SystemExit("capture-summary.json is missing: run the capture stage first")
    return json.loads(path.read_text(encoding="utf-8"))


def layer_ids(caps: dict) -> list[int]:
    first = int(caps["field_layer"])
    last = max(int(row["prompt_captures"]) for row in caps["rows"]) + first - 1
    return list(range(first, last + 1))


def step_dataset(caps: dict, layer: int, width: int) -> tuple[np.ndarray, np.ndarray, list[str]]:
    features, labels, groups = [], [], []
    for row in caps["rows"]:
        base = Path(row["capture_dir"])
        tokens = row["generation_token_ids"]
        for step in range(int(row["decodes"])):
            if step + 1 >= len(tokens):
                continue
            path = base / f"layer-{layer}-step-{step}.f32"
            if not path.exists():
                continue
            features.append(read_row(path, width))
            labels.append(int(tokens[step + 1]))
            groups.append(row["id"])
    return np.array(features, dtype=np.float32), np.array(labels), groups


def prompt_dataset(caps: dict, layer: int, width: int) -> tuple[np.ndarray, np.ndarray, list[str]]:
    features, labels, groups = [], [], []
    for row in caps["rows"]:
        path = Path(row["capture_dir"]) / f"layer-{layer}.f32"
        if not path.exists():
            raise SystemExit(f"missing prompt capture: {path}")
        features.append(read_row(path, width))
        labels.append(0 if row["label"] == "direct" else 1)
        groups.append(row["id"])
    return np.array(features, dtype=np.float32), np.array(labels), groups


def logits_top1(caps: dict) -> dict:
    """The model's own answer accuracy at each step, as the natural reference."""
    per_step = {}
    for row in caps["rows"]:
        base = Path(row["capture_dir"])
        tokens = row["generation_token_ids"]
        for step in range(int(row["decodes"])):
            if step + 1 >= len(tokens):
                continue
            path = base / f"decode-logits-{step}.f32"
            if not path.exists():
                continue
            logits = np.fromfile(path, dtype="<f4")
            per_step[(row["id"], step)] = int(np.argmax(logits)) == int(tokens[step + 1])
    return per_step


def cross_template(caps: dict, layer: int, width: int, args, rng) -> dict:
    features, labels, groups = prompt_dataset(caps, layer, width)
    templates = np.array([row["template"] for row in caps["rows"]])
    out = {}
    for train_template, test_template in (("qa", "brief"), ("brief", "qa")):
        train = np.where(templates == train_template)[0]
        test = np.where(templates == test_template)[0]
        if len(train) < 4 or len(test) < 4 or len(set(labels[train].tolist())) < 2:
            continue
        predicted = P.fit_predict(features, labels, train, test, groups)
        out[f"{train_template}_to_{test_template}"] = {
            "accuracy": float((predicted == labels[test]).mean()),
            "balanced_accuracy": P.balanced_accuracy(predicted, labels[test]),
            "majority": max(Counter(labels[train].tolist()).values()) / len(train),
            "train_rows": int(len(train)),
            "test_rows": int(len(test)),
        }
    return out


def probe_layers(caps: dict, width: int, layers: list[int], dataset, args, rng) -> dict:
    table = {}
    for layer in layers:
        features, labels, groups = dataset(caps, layer, width)
        if len(labels) == 0:
            continue
        mapped, mask, class_info = P.class_targets_strict(labels, args.min_class)
        features, labels, groups = features[mask], mapped[mask], [g for g, m in zip(groups, mask) if m]
        n_groups = len(set(groups))
        entry = {
            "states": int(len(labels)),
            "trajectories": n_groups,
            "class_info": class_info,
            "blocked": "",
        }
        if n_groups < MIN_TRAJECTORIES:
            entry["blocked"] = f"{n_groups} independent trajectories (< {MIN_TRAJECTORIES})"
        elif class_info["n_classes"] < 2:
            entry["blocked"] = "one class remains after dropping sparse labels"
        if not entry["blocked"]:
            entry.update(P.evaluate(features, labels, groups, args.folds, args.shuffles, rng))
            entry["fold_vacuity"] = P.fold_vacuity(labels, groups, args.folds)
        table[str(layer)] = entry
        print(
            f"  L{layer}: " + (entry["blocked"] or
                f"acc={entry['accuracy']:.3f} bal={entry['balanced_accuracy']:.3f} "
                f"maj={entry['majority']:.3f} shuf={entry['shuffled_mean']:.3f} "
                f"groups={n_groups} classes={class_info['n_classes']}"),
            flush=True,
        )
    return table


def register_verdict(table: dict) -> dict:
    """Earliest layer clearing both baselines, with the cross-template number beside it."""
    clearing = []
    for layer in sorted(table, key=int):
        entry = table[layer]
        if entry.get("blocked"):
            continue
        if entry["beats_majority"] and entry["above_shuffled"] and entry["balanced_above_shuffled"]:
            clearing.append(int(layer))
    return {
        "layers_clearing_both_baselines": clearing,
        "earliest_layer": clearing[0] if clearing else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--shuffles", type=int, default=8)
    parser.add_argument("--min-class", type=int, default=8)
    parser.add_argument("--width", type=int, default=5120)
    args = parser.parse_args()

    rng = np.random.default_rng(20260916)
    caps = summary()
    layers = layer_ids(caps)
    report = {
        "schema": "cassi.probe-campaign.probe.v1",
        "capture_summary": {key: caps[key] for key in
                            ("model_sha256", "executable_sha256", "field_layer", "tokens")},
        "gate": {
            "min_trajectories": MIN_TRAJECTORIES,
            "class_counts": caps["class_counts"],
            "independent_trajectories": caps["independent_trajectories"],
            "class_counts_by_template": caps["class_counts_by_template"],
            "screen_label_reproduced": caps["screen_label_reproduced"],
            "trajectories_total": len(caps["rows"]),
        },
        "layers": layers,
        "min_class": args.min_class,
        "probes": {},
    }

    print("register probe", flush=True)
    register = probe_layers(caps, args.width, layers, prompt_dataset, args, rng)
    for layer in sorted(register, key=int):
        register[layer]["cross_template"] = cross_template(caps, int(layer), args.width, args, rng)
    report["probes"]["register"] = {
        "labels": "0 = direct claim, 1 = hedge or qualifier, from the model's own continuation",
        "groups": "one prompt per group, so every fold holds out whole trajectories",
        "cross_template": "trained on one surface template, tested on the other with disjoint questions",
        "verdict": register_verdict(register),
        "layers": register,
    }

    print("next-token probe", flush=True)
    reference = logits_top1(caps)
    next_token = probe_layers(caps, args.width, layers, step_dataset, args, rng)
    for entry in next_token.values():
        entry["logits_top1_accuracy"] = (
            float(np.mean([v for v in reference.values()])) if reference else None)
    report["probes"]["next_token"] = {
        "labels": "the token the model generated at the next step, not constant in a trajectory",
        "groups": "one prompt per group",
        "reference": {
            "logits_top1_accuracy": float(np.mean(list(reference.values()))) if reference else None,
            "logits_steps": len(reference),
            "top1_by_trajectory": {
                row["id"]: float(np.mean([v for (pid, _), v in reference.items() if pid == row["id"]]))
                for row in caps["rows"]
                if any(pid == row["id"] for pid, _ in reference)
            },
        },
        "layers": next_token,
    }

    out = DIAG / "probe-report.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print("wrote", out, flush=True)
    print(json.dumps(report["probes"]["register"]["verdict"]), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
