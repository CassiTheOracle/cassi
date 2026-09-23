"""Layer-by-layer logit lens over the captured Qwen residual streams.

For every captured layer of every distinct captured state this applies the
model's own final RMS norm and its own unembedding to that layer's residual
input and reads the induced next-token distribution.  No training, no
substitute model: the lens is the model's own output map applied one or more
blocks early.

Inputs (read-only, existing captures):
    CassiQwen/native/llama.cpp/_diag/** and CassiQwen/_diag/**
    the GGUF the captures came from (unembedding + tokenizer)

Outputs (written next to this file):
    lens-states.json    the state index (dedup, labels, arm provenance)
    lens-curves-w*.npz  cached per-layer lens statistics
    lens-results.json   aggregates, commitment layers, readability, validation
    commitment-curve-*.png

Usage:
    python logit_lens.py [--width 5120] [--rebuild] [--skip-figures]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lens_common import (  # noqa: E402
    MODELS,
    WORKSPACE,
    lens,
    load_unembed,
    read_f32,
    rms_norm,
    token_text,
)

HERE = Path(__file__).resolve().parent
INVENTORY = HERE / "capture-inventory.json"
KINDS = ("prompt", "decode-early", "decode")
SUFFIX = {"prompt": "", "decode-early": "-decode-early", "decode": "-decode"}
LAYER_RE = re.compile(r"^layer-(\d+)(-decode-early|-decode)?\.f32$")


# ---------------------------------------------------------------------------
# state index
# ---------------------------------------------------------------------------

def label_file(kind: str, decode_logits_count: int) -> str:
    """The stored logits whose argmax is the model's own next token for `kind`.

    The harness captures the prompt batch's final row, the row of the pass that
    produced decode-logits-1, and the row of the pass that produced the last
    decode-logits file.  Each of those rows is exactly the state that produced
    the stored distribution, which is what makes the label exact rather than
    assumed.
    """
    if kind == "prompt":
        return "logits.f32"
    if kind == "decode-early":
        return "decode-logits-1.f32"
    return f"decode-logits-{max(decode_logits_count - 1, 0)}.f32"


def arm_of(path: str) -> str:
    parts = list(Path(path).parts)
    if "captures" in parts:
        parts = parts[: parts.index("captures")]
    for marker in ("_diag",):
        if marker in parts:
            return "/".join(parts[parts.index(marker) + 1:])
    return "/".join(parts[-3:])


def build_state_index() -> dict:
    """Group capture dirs into distinct states by full-trajectory digest."""
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    groups: dict[tuple, dict] = {}
    for record in inventory["records"]:
        raw = Path(record["capture_dir"])
        cap = raw if raw.is_absolute() else WORKSPACE / raw
        if not cap.is_dir():
            continue
        width = record["capture_width"]
        count = record["decode_logits_count"]
        for kind in KINDS:
            layers = sorted(record["layer_kinds"].get(kind, []))
            if not layers:
                continue
            digest = hashlib.sha256()
            broken = False
            for layer in layers:
                path = cap / f"layer-{layer}{SUFFIX[kind]}.f32"
                if not path.exists():
                    broken = True
                    break
                block = read_f32(path)
                if block.size != width:
                    broken = True
                    break
                digest.update(block.tobytes())
            if broken:
                continue
            group = groups.setdefault(
                (width, kind, digest.hexdigest()),
                {
                    "width": width,
                    "kind": kind,
                    "trajectory_sha256": digest.hexdigest(),
                    "layers": layers,
                    "capture_dirs": [],
                    "arms": [],
                    "models": set(),
                    "prompts": set(),
                    "generations": set(),
                    "labels": Counter(),
                    "label_logits": [],
                    "label_true_p": [],
                },
            )
            group["capture_dirs"].append(str(cap))
            group["arms"].append(arm_of(str(cap)))
            if record.get("model"):
                group["models"].add(record["model"])
            if record.get("prompt_sha256"):
                group["prompts"].add(record["prompt_sha256"])
            generation = tuple(record.get("generation_token_ids") or ())
            if generation:
                group["generations"].add(generation)
            logits_path = cap / label_file(kind, count)
            if logits_path.exists():
                stored = read_f32(logits_path)
                shifted = np.exp(stored - stored.max())
                label = int(stored.argmax())
                group["labels"][label] += 1
                group["label_logits"].append(str(logits_path))
                group["label_true_p"].append(float(shifted[label] / shifted.sum()))

    states = []
    for group in groups.values():
        labels = group["labels"]
        if labels:
            label, votes = labels.most_common(1)[0]
            agreement = votes / sum(labels.values())
        else:
            label, agreement = None, None
        states.append(
            {
                "state_id": group["trajectory_sha256"][:16],
                "width": group["width"],
                "kind": group["kind"],
                "layers": group["layers"],
                "trajectory_sha256": group["trajectory_sha256"],
                "n_dirs": len(group["capture_dirs"]),
                "capture_dirs": sorted(set(group["capture_dirs"])),
                "arms": sorted(set(group["arms"])),
                "models": sorted(group["models"]),
                "prompt_sha256": sorted(group["prompts"]),
                "generations": sorted(group["generations"])[:3],
                "label": label,
                "label_agreement": agreement,
                "label_distinct": len(labels),
                "label_logits": sorted(set(group["label_logits"]))[:3],
                "label_true_p": float(np.median(group["label_true_p"])) if group["label_true_p"] else None,
            }
        )
    states.sort(key=lambda s: (s["width"], s["kind"], s["state_id"]))
    return {"states": states, "inventory_records": len(inventory["records"])}


# ---------------------------------------------------------------------------
# lens sweep (union layer grid; captured grids are nested ranges)
# ---------------------------------------------------------------------------

def run_sweep(width: int, states: list[dict], cache: Path, rebuild: bool) -> dict:
    if cache.exists() and not rebuild:
        cached = np.load(cache, allow_pickle=True)
        meta = json.loads(str(cached["meta"]))
        if meta.get("width") == width and meta.get("state_ids") == [s["state_id"] for s in states]:
            return {"arrays": {k: cached[k] for k in cached.files if k != "meta"}, "meta": meta}

    bank = load_unembed(MODELS[width])
    union = sorted({layer for state in states for layer in state["layers"]})
    position = {layer: i for i, layer in enumerate(union)}
    n_layers = len(union)
    n_states = len(states)
    arrays = {
        "top1": np.full((n_layers, n_states), -1, dtype=np.int64),
        "top5": np.full((n_layers, n_states, 5), -1, dtype=np.int64),
        "p_top1": np.full((n_layers, n_states), np.nan),
        "p_answer": np.full((n_layers, n_states), np.nan),
        "rank_answer": np.full((n_layers, n_states), -1, dtype=np.int64),
        "entropy": np.full((n_layers, n_states), np.nan),
        "residual_l2": np.full((n_layers, n_states), np.nan),
        "residual_maxabs": np.full((n_layers, n_states), np.nan),
    }
    grids: dict[tuple, list[int]] = {}
    for index, state in enumerate(states):
        grids.setdefault(tuple(state["layers"]), []).append(index)

    meta = {
        "width": width,
        "layers": union,
        "state_ids": [state["state_id"] for state in states],
        "kinds": [state["kind"] for state in states],
        "answers": [state["label"] if state["label"] is not None else -1 for state in states],
        "unembed_tensor": bank.tensor_name,
        "unembed_type": str(bank.tensor_type),
        "n_vocab": int(bank.n_vocab),
        "n_embd": int(bank.n_embd),
    }

    for grid, members in sorted(grids.items()):
        rows = [position[layer] for layer in grid]
        stacks = []
        for index in members:
            cap = Path(states[index]["capture_dirs"][0])
            suffix = SUFFIX[states[index]["kind"]]
            stacks.append(np.stack([read_f32(cap / f"layer-{layer}{suffix}.f32") for layer in grid], axis=1))
        answers = np.array([states[index]["label"] if states[index]["label"] is not None else -1 for index in members])
        for local, layer in enumerate(grid):
            columns = np.stack([stack[:, local] for stack in stacks], axis=1)
            if columns.shape[0] != bank.n_embd:
                raise RuntimeError(f"width mismatch {columns.shape} vs {bank.n_embd}")
            normalized = rms_norm(columns, bank.norm_weight, bank.eps)
            result = lens(normalized, bank, np.maximum(answers, 0), batch=256)
            slots = np.array(members)
            row = rows[local]
            valid = answers >= 0
            arrays["top1"][row, slots] = result.top1
            arrays["top5"][row, slots] = result.top5
            arrays["p_top1"][row, slots] = np.exp(result.top1_logit - result.log_z)
            arrays["p_answer"][row, slots[valid]] = np.exp(result.answer_logit[valid] - result.log_z[valid])
            arrays["rank_answer"][row, slots[valid]] = result.answer_rank[valid]
            arrays["entropy"][row, slots] = result.entropy
            arrays["residual_l2"][row, slots] = np.linalg.norm(columns, axis=0)
            arrays["residual_maxabs"][row, slots] = np.abs(columns).max(axis=0)
            np.savez_compressed(cache, meta=json.dumps(meta), **arrays)
            print(f"  layer {layer:3d} (grid {grid[0]}..{grid[-1]}, n={len(members)}): "
                  f"top1==answer {int((result.top1[valid] == answers[valid]).sum())}/{int(valid.sum())}", flush=True)
    return {"arrays": arrays, "meta": meta}


# ---------------------------------------------------------------------------
# aggregates
# ---------------------------------------------------------------------------

def state_commitment(layers: list[int], p_answer: np.ndarray, top1: np.ndarray, answer: int) -> dict:
    """First layer whose suffix stays on the model's own next token."""
    finite = np.isfinite(p_answer)
    kept_layers = [layer for layer, keep in zip(layers, finite) if keep]
    series = p_answer[finite]
    winner = top1[finite] == answer
    if not winner.size or not winner.any():
        return {
            "commit_layer": None, "stable_run": 0, "p_at_commit": None,
            "p_before": None, "sharpness": None, "first_win_layer": None,
        }
    stable = 0
    for value in winner[::-1]:
        if not value:
            break
        stable += 1
    index = min(len(winner) - stable, len(winner) - 1)
    before = series[max(index - 1, 0)]
    first_win = kept_layers[int(np.argmax(winner))]
    return {
        "commit_layer": int(kept_layers[index]),
        "stable_run": int(stable),
        "already_top1_from_first_layer": bool(stable == len(winner)),
        "p_at_commit": float(series[index]),
        "p_before": float(before),
        "sharpness": float(series[index] - before),
        "first_win_layer": int(first_win),
        "n_layers": int(winner.size),
    }


def summarize(width: int, result: dict, states: list[dict]) -> dict:
    arrays = result["arrays"]
    layers = result["meta"]["layers"]
    answers = np.array(result["meta"]["answers"])
    labeled = answers >= 0
    out = {
        "width": width,
        "layers": layers,
        "n_states": len(states),
        "n_labeled": int(labeled.sum()),
        "unembed": {
            "tensor": result["meta"]["unembed_tensor"],
            "type": result["meta"]["unembed_type"],
            "n_vocab": result["meta"]["n_vocab"],
            "n_embd": result["meta"]["n_embd"],
        },
        "kinds": {},
    }
    labelled_states = [s for s in states if s["label"] is not None]
    for kind in KINDS:
        members = [i for i, state in enumerate(states) if state["kind"] == kind and state["label"] is not None]
        if not members:
            continue
        slots = np.array(members)
        kinds = answers[slots]
        tokens = Counter(int(a) for a in kinds)
        majority_rate = tokens.most_common(1)[0][1] / len(slots)
        rows = []
        for row, layer in enumerate(layers):
            present = np.isfinite(arrays["p_answer"][row, slots])
            if not present.any():
                continue
            here = slots[present]
            top1 = arrays["top1"][row, here]
            rank = arrays["rank_answer"][row, here]
            rows.append(
                {
                    "layer": layer,
                    "n": int(present.sum()),
                    "top1_rate": float((top1 == answers[here]).mean()),
                    "top5_rate": float((rank <= 5).mean()),
                    "median_rank": float(np.median(rank)),
                    "median_p_answer": float(np.median(arrays["p_answer"][row, here])),
                    "mean_p_answer": float(np.mean(arrays["p_answer"][row, here])),
                    "median_p_top1": float(np.median(arrays["p_top1"][row, here])),
                    "median_entropy_nats": float(np.median(arrays["entropy"][row, here])),
                    "mean_residual_l2": float(np.mean(arrays["residual_l2"][row, here])),
                }
            )
        for row in rows:
            row["readable"] = bool(row["top5_rate"] >= 0.5)
            row["beats_majority"] = bool(row["top1_rate"] > majority_rate)
        per_state = []
        for slot in slots:
            entry = state_commitment(
                layers,
                arrays["p_answer"][:, slot],
                arrays["top1"][:, slot],
                int(answers[slot]),
            )
            state = states[slot]
            per_state.append(
                {
                    "state_id": state["state_id"],
                    "n_dirs": state["n_dirs"],
                    "arms": state["arms"][:3],
                    "prompt_sha256": state["prompt_sha256"][:1],
                    "label": int(answers[slot]),
                    "label_agreement": state["label_agreement"],
                    "label_true_p": state["label_true_p"],
                    **entry,
                }
            )
        committed = [entry for entry in per_state if entry["commit_layer"] is not None]
        block = {
            "n_states": len(slots),
            "majority_rate": float(majority_rate),
            "majority_token": int(tokens.most_common(1)[0][0]),
            "label_distribution": {str(k): v for k, v in tokens.most_common(12)},
            "rows": rows,
            "per_state_commitment": per_state,
        }
        if committed:
            commit_layers = np.array([entry["commit_layer"] for entry in committed])
            block["commitment"] = {
                "n_committed": len(committed),
                "median_layer": float(np.median(commit_layers)),
                "p25_layer": float(np.percentile(commit_layers, 25)),
                "p75_layer": float(np.percentile(commit_layers, 75)),
                "min_layer": int(commit_layers.min()),
                "max_layer": int(commit_layers.max()),
                "n_stable_to_last_layer": int((commit_layers == layers[-1]).sum()),
                "median_stable_run_layers": float(np.median([e["stable_run"] for e in committed])),
                "median_p_before": float(np.median([e["p_before"] for e in committed])),
                "median_p_at_commit": float(np.median([e["p_at_commit"] for e in committed])),
                "median_sharpness": float(np.median([e["sharpness"] for e in committed])),
            }
            never = [entry["state_id"] for entry in per_state if entry["commit_layer"] is None]
            block["commitment"]["never_top1"] = never
        out["kinds"][kind] = block
    return out


# ---------------------------------------------------------------------------
# figures
# ---------------------------------------------------------------------------

def figure_curves(result: dict, states: list[dict], width: int) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    arrays = result["arrays"]
    layers = result["meta"]["layers"]
    answers = np.array(result["meta"]["answers"])
    written = []
    fig, axes = plt.subplots(1, 3, figsize=(16.5, 5.0))
    for axis, kind in zip(axes, KINDS):
        members = [i for i, state in enumerate(states) if state["kind"] == kind and state["label"] is not None]
        if not members:
            axis.axis("off")
            continue
        slots = np.array(members)
        kinds = answers[slots]
        agreement, median_answer, median_top1 = [], [], []
        xs = []
        for row, layer in enumerate(layers):
            present = np.isfinite(arrays["p_answer"][row, slots])
            if not present.any():
                continue
            here = slots[present]
            xs.append(layer)
            agreement.append(float((arrays["top1"][row, here] == answers[here]).mean()))
            median_answer.append(float(np.median(arrays["p_answer"][row, here])))
            median_top1.append(float(np.median(arrays["p_top1"][row, here])))
        axis.plot(xs, agreement, "-o", ms=3, label="lens top-1 == model's own next token", color="#1f77b4")
        axis.plot(xs, median_answer, "-s", ms=3, label="median p(model's own next token)", color="#d62728")
        axis.plot(xs, median_top1, "--", label="median p(lens top-1)", color="#7f7f7f")
        axis.axhline(0.5, color="k", lw=0.6, ls=":")
        axis.set_xlabel("layer whose residual feeds the lens")
        axis.set_title(f"{kind} position (n={len(slots)} states)")
        axis.grid(alpha=0.3)
        axis.set_ylim(-0.03, 1.0)
        if kind == "prompt":
            axis.set_ylabel("probability / agreement")
    axes[0].legend(loc="upper left", fontsize=8)
    fig.suptitle(f"Logit lens over captured residuals (width {width}): where the next token becomes readable")
    fig.tight_layout()
    path = HERE / f"commitment-curve-w{width}.png"
    fig.savefig(path, dpi=140)
    plt.close(fig)
    written.append(path.name)

    fig, axis = plt.subplots(figsize=(9, 5.2))
    members = [i for i, state in enumerate(states) if state["label"] is not None]
    slots = np.array(members)
    last = max(row for row, layer in enumerate(layers) if np.isfinite(arrays["p_answer"][row, slots]).any())
    rank = arrays["rank_answer"][last, slots]
    top1 = (arrays["top1"][last, slots] == answers[slots]).astype(float)
    truth = np.array([states[slot]["label_true_p"] for slot in slots])
    scatter = axis.scatter(truth, np.minimum(rank, 5000), c=top1, cmap="coolwarm", s=26, vmin=0, vmax=1)
    axis.set_yscale("log")
    axis.axhline(1, color="k", lw=0.6, ls=":")
    axis.set_xscale("log")
    axis.set_xlabel("model's own probability of its next token (exact stored logits)")
    axis.set_ylabel("rank of that token in the lens at the last captured layer")
    axis.set_title(f"Lens fidelity follows the model's own confidence (layer {layers[last]}, {len(slots)} states)")
    axis.grid(alpha=0.3)
    fig.colorbar(scatter, ax=axis, label="lens top-1 correct")
    fig.tight_layout()
    path = HERE / f"lens-fidelity-w{width}.png"
    fig.savefig(path, dpi=140)
    plt.close(fig)
    written.append(path.name)
    return written


def figure_arm_compare(pair_dirs: list[str], width: int, tag: str, title: str) -> dict:
    """Commitment curve on an arm directory and its twin, from the dirs alone."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    bank = load_unembed(MODELS[width])
    fig, axis = plt.subplots(figsize=(10.5, 5.4))
    table: list[dict] = []
    summaries: dict[str, dict] = {}
    for arm_dir in pair_dirs:
        cap = Path(arm_dir)
        if not cap.is_dir():
            continue
        arm = cap.parent.name if cap.name == "captures" else cap.name
        labels = {}
        for path in sorted(cap.glob("decode-logits-*.f32")):
            labels[int(path.stem.split("-")[-1])] = int(read_f32(path).argmax())
        prompt_label = int(read_f32(cap / "logits.f32").argmax()) if (cap / "logits.f32").exists() else None
        last = max(labels) if labels else None
        for kind, answer in (
            ("prompt", prompt_label),
            ("decode-early", labels.get(1)),
            ("decode", labels.get(last) if last is not None else None),
        ):
            if answer is None:
                continue
            layers = sorted(
                int(match.group(1))
                for match in (LAYER_RE.match(name) for name in os.listdir(cap))
                if match and (match.group(2) or "") == SUFFIX[kind]
            )
            if not layers:
                continue
            columns = np.stack([read_f32(cap / f"layer-{layer}{SUFFIX[kind]}.f32") for layer in layers], axis=1)
            normalized = rms_norm(columns, bank.norm_weight, bank.eps)
            result = lens(normalized, bank, np.array([answer]), batch=32)
            probs = np.exp(result.answer_logit - result.log_z)
            style = {"prompt": "-", "decode-early": "--", "decode": ":"}[kind]
            axis.plot(layers, probs, style, marker="o", ms=3, label=f"{cap.name} {kind}: p(answer)")
            axis.plot(layers, (result.top1 == answer).astype(float), style, color="k", alpha=0.3)
            winner = (result.top1 == answer)
            stable = 0
            for value in winner[::-1]:
                if not value:
                    break
                stable += 1
            keep = min(len(layers) - stable, len(layers) - 1)
            summaries[f"{arm} {kind}"] = {
                "arm": arm,
                "capture_dir": str(cap.relative_to(WORKSPACE)),
                "kind": kind,
                "answer": int(answer),
                "layers": layers,
                "top1": [int(token) for token in result.top1],
                "p_answer": probs.tolist(),
                "top1_correct": winner.astype(int).tolist(),
                "stable_run_layers": int(stable),
                "stable_layer": int(layers[keep]),
                "stable_from_first_layer": bool(stable == len(layers)),
                "p_at_stable": float(probs[keep]),
                "p_before": float(probs[max(keep - 1, 0)]),
                "already_correct_at_layer": int(layers[int(np.argmax(winner))]),
            }
            for layer, probability, correct in zip(layers, probs.tolist(), winner.astype(int).tolist()):
                table.append({
                    "capture_dir": str(cap.relative_to(WORKSPACE)),
                    "arm": arm,
                    "kind": kind,
                    "layer": int(layer),
                    "p_model_next_token": float(probability),
                    "lens_top1_is_model_next_token": int(correct),
                })
    # cross-arm reading agreement: only meaningful where both arms read the
    # same label token (an identical prompt position, or a shared context).
    agreement = {}
    keys = list(summaries)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            left, right = summaries[a], summaries[b]
            if left["kind"] != right["kind"] or left["answer"] != right["answer"]:
                continue
            if left["layers"] != right["layers"]:
                continue
            same_top1 = np.mean([int(x == y) for x, y in zip(left["top1"], right["top1"])])
            delta = np.abs(np.array(left["p_answer"]) - np.array(right["p_answer"]))
            agreement[f"{a} | {b}"] = {
                "same_label_token": True,
                "label_token": int(left["answer"]),
                "n_layers": len(left["layers"]),
                "identical_top1_layer_share": float(same_top1),
                "median_abs_dp_answer": float(np.median(delta)),
                "max_abs_dp_answer": float(delta.max()),
                "identical_p_curves": bool(np.allclose(left["p_answer"], right["p_answer"], rtol=0, atol=0)),
            }
    axis.axhline(0.5, color="k", lw=0.6, ls=":")
    axis.set_xlabel("layer")
    axis.set_ylabel("p(model's own next token); black = top-1 agreement")
    axis.set_title(title)
    axis.grid(alpha=0.3)
    axis.legend(fontsize=8)
    fig.tight_layout()
    path = HERE / f"commitment-curve-arms-{tag}-w{width}.png"
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return {"figures": [path.name], "rows": table, "summaries": summaries, "agreement": agreement}


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

TWIN_PAIRS = (
    ("CassiQwen/native/llama.cpp/_diag/steps32-on", "CassiQwen/native/llama.cpp/_diag/steps32-off"),
    ("CassiQwen/native/llama.cpp/_diag/steps8-on", "CassiQwen/native/llama.cpp/_diag/steps8-off"),
    ("CassiQwen/native/llama.cpp/_diag/steps1-on", "CassiQwen/native/llama.cpp/_diag/steps1-off"),
)

# The named twins above are byte-identical copies (measured, see twin report).
# These are real arms that differ only in whether the field ran, so a difference
# in the commitment curve there is a field effect.
ARM_PAIRS = (
    ("named",
     "steps32-on vs steps32-off (the twin the brief names)",
     ("CassiQwen/native/llama.cpp/_diag/steps32-off",
      "CassiQwen/native/llama.cpp/_diag/steps32-on")),
    ("carryp0",
     "carry-forward runs2 epoch-0: field off vs field live (same prompt, same 200-token budget)",
     ("CassiQwen/native/llama.cpp/_diag/carry-forward/runs2/epoch-0/off-p0/captures",
      "CassiQwen/native/llama.cpp/_diag/carry-forward/runs2/epoch-0/on-p0/captures")),
)


def twin_report() -> dict:
    rows = []
    for on, off in TWIN_PAIRS:
        row = {"name": Path(on).name, "on_dir": on, "off_dir": off, "on": None, "off": None}
        for tag, arm in (("on", on), ("off", off)):
            cap = WORKSPACE / arm
            if not cap.is_dir():
                row[tag] = None
                continue
            digest = hashlib.sha256()
            n_layers = 0
            decode_digest = hashlib.sha256()
            n_decode_layers = 0
            for name in sorted(os.listdir(cap)):
                match = LAYER_RE.match(name)
                if match and (match.group(2) or "") == "":
                    digest.update(read_f32(cap / name).tobytes())
                    n_layers += 1
                elif match and match.group(2) in ("-decode", "-decode-early"):
                    decode_digest.update(read_f32(cap / name).tobytes())
                    n_decode_layers += 1
            logits = read_f32(cap / "logits.f32")
            row[tag] = {
                "prompt_layer_digest": digest.hexdigest()[:16],
                "decode_layer_digest": decode_digest.hexdigest()[:16],
                "n_decode_layer_files": n_decode_layers,
                "logits_digest": hashlib.sha256(logits.tobytes()).hexdigest()[:16],
                "logits_argmax": int(logits.argmax()),
                "n_prompt_layers": n_layers,
                "n_decode_logits": len(list(cap.glob("decode-logits-*.f32"))),
            }
        if row["on"] and row["off"]:
            row["identical_residuals"] = row["on"]["prompt_layer_digest"] == row["off"]["prompt_layer_digest"]
            row["identical_logits"] = row["on"]["logits_digest"] == row["off"]["logits_digest"]
            row["identical_decode_residuals"] = (
                row["on"]["decode_layer_digest"] == row["off"]["decode_layer_digest"])
        rows.append(row)
    return {"pairs": rows}


def residual_reuse(width: int, states: list[dict]) -> dict:
    """How much of the residual is the field's, and how much is just the re-run?

    States are grouped by (prompt, next-token label, kind): the members of a group are
    re-runs of one prompt under different field settings, so at a fixed layer any
    difference between them is what the field moved.  Read at the first captured layer,
    where the two arms have seen the same text.
    """
    groups: dict[tuple, list[dict]] = {}
    for state in states:
        if state["label"] is None or not state["capture_dirs"]:
            continue
        key = (tuple(state["prompt_sha256"]), state["label"], state["kind"])
        groups.setdefault(key, []).append(state)

    rows = []
    for key, members in sorted(groups.items(), key=lambda item: -len(item[1])):
        if len(members) < 2:
            continue
        kind = key[2]
        layer = min(members[0]["layers"])
        if any(min(member["layers"]) != layer for member in members):
            continue
        vectors = [read_f32(Path(member["capture_dirs"][0]) / f"layer-{layer}{SUFFIX[kind]}.f32")
                   for member in members]
        if any(vector is None for vector in vectors):
            continue
        bank = np.stack(vectors).astype(np.float32)
        contents = {hashlib.sha256(vector.tobytes()).hexdigest() for vector in vectors}
        row_rms = float(np.mean(np.sqrt((bank.astype(np.float64) ** 2).mean(axis=1))))
        worst = 0.0
        for column in range(bank.shape[0]):
            worst = max(worst, float(np.abs(bank - bank[column]).max()))
        rows.append({
            "kind": kind,
            "layer": layer,
            "prompt_sha256": key[0][0][:16] if key[0] else None,
            "label": key[1],
            "n_captures": len(members),
            "n_distinct_byte_contents": len(contents),
            "max_abs_difference": worst,
            "mean_row_rms": row_rms,
            "max_abs_over_rms": worst / row_rms if row_rms else None,
            "arms": sorted({arm for member in members for arm in member["arms"]})[:8],
        })
    summary = {
        "n_groups": len(rows),
        "n_captures_compared": sum(row["n_captures"] for row in rows),
        "largest_group": rows[0] if rows else None,
        "max_abs_over_rms_over_groups": max((row["max_abs_over_rms"] or 0.0) for row in rows) if rows else None,
        "groups": rows,
    }
    return summary


def instrument_validation(index: dict, width: int = 5120) -> dict:
    """Does the lens reproduce the model's own next token on rows that produced
    a stored distribution?  This is the instrument's positive control."""
    states = [
        state
        for state in index["states"]
        if state["width"] == width and state["kind"] in ("decode-early", "decode") and state["label"] is not None
    ]
    if not states:
        return {}
    bank = load_unembed(MODELS[width])
    columns, answers, last_layers = [], [], []
    for state in states:
        cap = Path(state["capture_dirs"][0])
        layer = state["layers"][-1]
        columns.append(read_f32(cap / f"layer-{layer}{SUFFIX[state['kind']]}.f32"))
        answers.append(state["label"])
        last_layers.append(layer)
    normalized = rms_norm(np.stack(columns, axis=1), bank.norm_weight, bank.eps)
    result = lens(normalized, bank, np.array(answers), batch=128)
    rank = result.answer_rank
    by_kind = {}
    for kind in ("decode-early", "decode"):
        members = [i for i, state in enumerate(states) if state["kind"] == kind]
        if not members:
            continue
        slots = np.array(members)
        by_kind[kind] = {
            "n_states": len(members),
            "top1_rate": float((result.top1[slots] == np.array(answers)[slots]).mean()),
            "median_rank": float(np.median(rank[slots])),
            "median_p_answer": float(np.median(np.exp(result.answer_logit[slots] - result.log_z[slots]))),
        }
    return {
        "width": width,
        "layers_used": sorted(set(last_layers)),
        "n_states": len(states),
        "top1_rate": float((result.top1 == np.array(answers)).mean()),
        "median_rank": float(np.median(rank)),
        "p90_rank": float(np.percentile(rank, 90)),
        "by_kind": by_kind,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--width", type=int, default=0, help="0 = every captured width")
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--skip-figures", action="store_true")
    args = parser.parse_args()

    index = build_state_index()
    print(f"state index: {len(index['states'])} distinct states from {index['inventory_records']} capture dirs")
    per_kind = Counter((state["width"], state["kind"]) for state in index["states"])
    for key in sorted(per_kind):
        print(f"   width {key[0]:5d} {key[1]:13s} {per_kind[key]:4d} distinct states")
    labeled = Counter((state["width"], state["kind"]) for state in index["states"] if state["label"] is not None)
    for key in sorted(labeled):
        print(f"   labeled  width {key[0]:5d} {key[1]:13s} {labeled[key]:4d}")
    (HERE / "lens-states.json").write_text(json.dumps(index, indent=1), encoding="utf-8")

    report = {
        "state_index": {f"w{k[0]}/{k[1]}": v for k, v in sorted(per_kind.items())},
        "state_index_labeled": {f"w{k[0]}/{k[1]}": v for k, v in sorted(labeled.items())},
        "widths": {},
        "twin_pairs": twin_report(),
        "instrument_validation": {},
        "figures": [],
    }
    for pair in report["twin_pairs"]["pairs"]:
        print(f"  twin {pair['name']}: identical prompt residuals {pair.get('identical_residuals')} "
              f"identical prompt logits {pair.get('identical_logits')} "
              f"identical decode residuals {pair.get('identical_decode_residuals')}")

    widths = sorted({state["width"] for state in index["states"]})
    for width in widths:
        if args.width and width != args.width:
            continue
        states = [state for state in index["states"] if state["width"] == width]
        print(f"\n=== width {width}: lensing {len(states)} distinct states over {len({tuple(s['layers']) for s in states})} layer grid(s)")
        result = run_sweep(width, states, HERE / f"lens-curves-w{width}.npz", args.rebuild)
        summary = summarize(width, result, states)
        report["widths"][str(width)] = summary
        tokens = MODELS[width]
        for kind, block in summary["kinds"].items():
            print(f"  -- {kind}: n={block['n_states']} majority {block['majority_rate']:.3f} "
                  f"({token_text(block['majority_token'], tokens)!r})"
                  f" unreadable_layers={sum(1 for r in block['rows'] if not r['readable'])}/{len(block['rows'])}")
            if "commitment" in block:
                c = block["commitment"]
                print(f"     commitment: median layer {c['median_layer']:.0f} "
                      f"[{c['p25_layer']:.0f},{c['p75_layer']:.0f}], stable to last layer in "
                      f"{c['n_stable_to_last_layer']}/{c['n_committed']}; "
                      f"p {c['median_p_before']:.4f} -> {c['median_p_at_commit']:.4f}")
        if not args.skip_figures:
            report["figures"].extend(figure_curves(result, states, width))
        reuse = residual_reuse(width, states)
        report.setdefault("residual_reuse", {})[str(width)] = reuse
        if reuse["largest_group"]:
            group = reuse["largest_group"]
            print(f"  residual reuse w{width}: {reuse['n_groups']} groups, "
                  f"{reuse['n_captures_compared']} captures; largest group n={group['n_captures']} "
                  f"({group['kind']} L{group['layer']}, label {group['label']}): "
                  f"{group['n_distinct_byte_contents']} distinct byte contents, "
                  f"max|d| {group['max_abs_difference']:.5f} vs row rms {group['mean_row_rms']:.3f} "
                  f"({group['max_abs_over_rms'] * 100:.2f}%)")

    validation = instrument_validation(index)
    if validation:
        report["instrument_validation"] = validation
        print(f"\nvalidation: decode rows (n={validation['n_states']}), layer {validation['layers_used']}: "
              f"top1 {validation['top1_rate']:.3f}, median rank {validation['median_rank']:.0f}, "
              f"p90 rank {validation['p90_rank']:.0f}")

    if not args.skip_figures:
        report["arm_pairs"] = {}
        for tag, title, pair in ARM_PAIRS:
            block = figure_arm_compare([str(WORKSPACE / path) for path in pair], 5120, tag, title)
            report["figures"].extend(block["figures"])
            report["arm_pairs"][tag] = {"title": title, "images": block["figures"],
                                        "summaries": block["summaries"], "rows": block["rows"],
                                        "agreement": block["agreement"]}
            for name, row in block["summaries"].items():
                print(f"  arm {name}: {row['kind']:13s} stable layer {row['stable_layer']} "
                      f"(run {row['stable_run_layers']} of {len(row['layers'])}), "
                      f"p {row['p_before']:.4f} -> {row['p_at_stable']:.4f}, "
                      f"first correct layer {row['already_correct_at_layer']}")
            for name, row in block["agreement"].items():
                print(f"    agreement {name}: same top-1 at {row['identical_top1_layer_share']:.2f} of layers, "
                      f"median |dp| {row['median_abs_dp_answer']:.4f}, identical curves "
                      f"{row['identical_p_curves']} (label token {row['label_token']})")

    (HERE / "lens-results.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print("\nwrote lens-states.json, lens-results.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
