"""What the field's own readout contains: a measured pre-flight for the design note.

Three questions, all answered from artifacts already on disk (nothing is re-run,
nothing is simulated):

  A. state cells   - per (scale, mode) the field keeps EY, EI; the readout's
                     weight is q = rho^2/(rho^2+1/phi^2) with rho = |EY|^2 + EI^2.
                     How concentrated is that weight, and how much of the state
                     sits on the conserved manifold EY - phi*EI?
  B. readout cells - qi-flux-<i>.f32 is the field's own per-token readout (what
                     the seam hands back to the model).  Can those cells alone
                     name the token the model actually chose at that pass?
                     A linear probe with a shuffled-label control and the
                     most-frequent-class baseline answers it.
  C. field scores  - the receipt's generated_token_scores is the field's own
                     score of each generated token; how does it track the
                     model's own probability for that token?

Usage (run in this order; the later modes merge into the receipt the first one
writes rather than replacing it):
    python readout_preflight.py [--arms 6] [--tokens 120]
    python readout_preflight.py --binary-only
    python readout_preflight.py --absolute-ab
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lens_common import WORKSPACE, read_f32  # noqa: E402
from probe_decode import balanced_group_folds, class_targets_strict, evaluate  # noqa: E402

HERE = Path(__file__).resolve().parent
PHI = 1.618033988749895  # llama-context.cpp:226, the field's own constant
MODE_COUNT = 6144
SCALE_COUNT = 4
COMPONENTS = 9
WAVE_MODES = 3072


def receipt_table() -> dict:
    inventory = json.loads((HERE / "capture-inventory.json").read_text(encoding="utf-8"))
    table = {}
    for record in inventory["records"]:
        raw = Path(record["capture_dir"])
        cap = raw if raw.is_absolute() else WORKSPACE / raw
        table[str(cap)] = record
    return table


def state_cells(state: np.ndarray) -> dict:
    """q, coherence and availability per (scale, mode), straight from the state dump."""
    view = state.reshape(SCALE_COUNT, MODE_COUNT, COMPONENTS)
    ey_re, ey_im, ei_re, ei_im, _, _, _, _, eps2 = (view[:, :, c] for c in range(9))
    rho = np.clip(ey_re**2 + ey_im**2 + ei_re**2 + ei_im**2, 0.0, 64.0)
    inv_phi2 = 1.0 / (PHI * PHI)
    q = rho**2 / (rho**2 + inv_phi2 + np.maximum(eps2, 0.0))
    d_re, d_im = ey_re - PHI * ei_re, ey_im - PHI * ei_im
    d = np.sqrt(d_re**2 + d_im**2)
    return {"rho": rho, "q": q, "eps": np.sqrt(d_re**2 + d_im**2), "d": d}


def concentration(values: np.ndarray, fraction: float) -> float:
    flat = np.sort(values.ravel())[::-1]
    total = flat.sum()
    if total <= 0:
        return 0.0
    keep = max(1, int(len(flat) * fraction))
    return float(flat[:keep].sum() / total)


def retrieval_accuracy(features: np.ndarray, labels: np.ndarray) -> dict:
    """Leave-one-out nearest-neighbour identity retrieval (rank reading, small-n safe)."""
    centred = features - features.mean(axis=0, keepdims=True)
    norm = np.linalg.norm(centred, axis=1)
    hit = 0
    chance = 0.0
    for i in range(len(centred)):
        distance = np.linalg.norm(centred - centred[i], axis=1)
        distance[i] = np.inf
        hit += int(labels[int(np.argmin(distance))] == labels[i])
        others = len(labels) - 1
        same = int((labels == labels[i]).sum()) - 1
        chance += same / others if others else 0.0
    return {"n": int(len(labels)), "accuracy": hit / max(len(labels), 1), "chance": chance / max(len(labels), 1)}


def absolute_ab(paths: list[str], tokens: int) -> dict:
    """Read the already-captured read-absolute arms: does the magnitude axis help?"""
    arms: dict[str, dict] = {}
    vectors: dict[str, np.ndarray] = {}
    for cap in paths:
        path = Path(cap)
        ids = sorted(int(f.stem.split("-")[-1]) for f in path.glob("qi-flux-*.f32"))
        keep = [i for i in ids if (path / f"decode-logits-{i}.f32").exists()][:tokens]
        if not keep:
            continue
        features = np.stack([read_f32(path / f"qi-flux-{i}.f32") for i in keep])
        labels = np.array([int(read_f32(path / f"decode-logits-{i}.f32").argmax()) for i in keep])
        amplitude = np.abs(features)
        cell = amplitude.reshape(len(features), -1, 2)
        magnitude = np.sqrt(cell[:, :, 0] ** 2 + cell[:, :, 1] ** 2)
        top = magnitude.argmax(axis=1)
        arms[Path(cap).parent.name] = {
            "capture_dir": str(path.relative_to(WORKSPACE)),
            "n_tokens": len(keep),
            "n_distinct_next_tokens": int(len(set(labels.tolist()))),
            "zero_cell_share": float((features == 0.0).mean()),
            "mean_abs_cell": float(amplitude.mean()),
            "median_cell_energy": float(magnitude.sum(axis=1).mean()),
            "modal_top_cell_share": float(Counter(top.tolist()).most_common(1)[0][1] / len(top)),
            "n_distinct_top_cells": int(len(set(top.tolist()))),
            "identity_retrieval": retrieval_accuracy(features, labels),
            "generation_token_ids_sha": hashlib.sha256(repr(labels.tolist()).encode()).hexdigest()[:16],
        }
        vectors[Path(cap).parent.name] = features
    pairs = {}
    names = list(vectors)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if vectors[a].shape != vectors[b].shape:
                continue
            u, v = vectors[a], vectors[b]
            cosine = float(np.mean(np.sum(u * v, axis=1) /
                                   np.maximum(np.linalg.norm(u, axis=1) * np.linalg.norm(v, axis=1), 1e-12)))
            scale = float(np.mean(np.linalg.norm(u, axis=1) / np.maximum(np.linalg.norm(v, axis=1), 1e-12)))
            top_a = np.abs(u).reshape(len(u), -1, 2)
            top_b = np.abs(v).reshape(len(v), -1, 2)
            index_a = np.sqrt(top_a[:, :, 0] ** 2 + top_a[:, :, 1] ** 2).argmax(axis=1)
            index_b = np.sqrt(top_b[:, :, 0] ** 2 + top_b[:, :, 1] ** 2).argmax(axis=1)
            pairs[f"{a} vs {b}"] = {
                "mean_cosine_of_cell_vectors": cosine,
                "mean_norm_ratio": scale,
                "top_cell_index_agreement": float((index_a == index_b).mean()),
            }
    return {"arms": arms, "pairs": pairs}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arms", type=int, default=6)
    parser.add_argument("--tokens", type=int, default=120)
    parser.add_argument("--binary-only", action="store_true")
    parser.add_argument("--absolute-ab", action="store_true",
                        help="read the already-captured read-absolute A/B arm family")
    args = parser.parse_args()

    if args.absolute_ab:
        family = WORKSPACE / "CassiQwen/native/llama.cpp/_diag/aim-profile-floor-flag-canonical"
        paths = [str(family / arm / "captures") for arm in ("abs_on", "abs_off", "lesion", "off")]
        block = absolute_ab(paths, args.tokens)
        for arm, row in block["arms"].items():
            print(f"  {arm}: {row['n_tokens']} tokens, {row['n_distinct_next_tokens']} distinct labels, "
                  f"retrieval {row['identity_retrieval']['accuracy']:.3f} vs chance "
                  f"{row['identity_retrieval']['chance']:.3f}, mean |cell| {row['mean_abs_cell']:.3f}, "
                  f"zero share {row['zero_cell_share']:.3f}, modal top cell "
                  f"{row['modal_top_cell_share']:.3f} over {row['n_distinct_top_cells']} cells")
        for pair, row in block["pairs"].items():
            print(f"  {pair}: cosine {row['mean_cosine_of_cell_vectors']:+.3f}, "
                  f"norm ratio {row['mean_norm_ratio']:.3f}, top-cell agreement "
                  f"{row['top_cell_index_agreement']:.3f}")
        existing = json.loads((HERE / "readout-preflight.json").read_text(encoding="utf-8"))
        existing["absolute_ab"] = block
        (HERE / "readout-preflight.json").write_text(json.dumps(existing, indent=1), encoding="utf-8")
        print("updated readout-preflight.json (absolute A/B)")
        return 0

    receipts = receipt_table()
    rng = np.random.default_rng(20260916)
    report: dict = {"state_cells": [], "readout": {}, "field_scores": {}, "notes": []}

    if args.binary_only:
        stored = np.load(HERE / "readout-cells.npz", allow_pickle=True)
        features = stored["features"]
        labels = stored["labels"]
        groups = [str(value) for value in stored["groups"]]
        from lens_common import MODELS, token_text
        vocab = MODELS[5120]
        texts = [token_text(int(token), vocab) for token in labels]
        variants = {
            "next token starts a word (leading space)": np.array([1 if t.startswith(" ") else 0 for t in texts]),
            "next token is a newline": np.array([1 if "\n" in t else 0 for t in texts]),
        }
        block = {}
        for name, target in variants.items():
            if len(set(target.tolist())) < 2:
                continue
            output = evaluate(features, target, groups, folds=min(6, len(set(groups))), shuffles=8, rng=rng)
            block[name] = {"positive_rate": float(target.mean()), **output}
            print(f"  {name}: positive rate {target.mean():.3f} accuracy {output.get('accuracy', float('nan')):.3f} "
                  f"majority {output.get('majority', float('nan')):.3f} "
                  f"shuffled {output.get('shuffled_mean', float('nan')):.3f}+-{output.get('shuffled_sd', float('nan')):.3f}")
        report["readout"]["binary_legibility"] = block
        path = HERE / "readout-preflight.json"
        if path.exists():  # merge: this mode must not clobber the sections already measured
            existing = json.loads(path.read_text(encoding="utf-8"))
            existing.setdefault("readout", {})["binary_legibility"] = block
            report = existing
        path.write_text(json.dumps(report, indent=1), encoding="utf-8")
        print("updated readout-preflight.json (binary legibility)")
        return 0

    # ---- candidate arms: field live, flux dumped, logits per decode step
    candidates = []
    for cap, record in receipts.items():
        path = Path(cap)
        flux = sorted(path.glob("qi-flux-*.f32"))
        logits = sorted(path.glob("decode-logits-*.f32"))
        if record.get("qi_enabled") is not True or not (record.get("state_field_width") or 0):
            continue
        if len(flux) < 40 or (path / "state-after.f32").exists() is False:
            continue
        candidates.append((len(flux), cap, sorted(int(f.stem.split("-")[-1]) for f in flux),
                           sorted(int(f.stem.split("-")[-1]) for f in logits), record))
    candidates.sort(key=lambda row: -row[0])
    print(f"arms with field live, flux dumped and a state dump: {len(candidates)}")

    # ---- A. state cells
    for _, cap, _, _, record in candidates[: args.arms]:
        state = read_f32(Path(cap) / "state-after.f32")
        if state.size != MODE_COUNT * SCALE_COUNT * COMPONENTS:
            report["notes"].append(f"{cap}: unexpected state size {state.size}")
            continue
        cells = state_cells(state)
        rho, q, d = cells["rho"], cells["q"], cells["d"]
        ey = state.reshape(SCALE_COUNT, MODE_COUNT, COMPONENTS)[:, :, :2]
        ei = state.reshape(SCALE_COUNT, MODE_COUNT, COMPONENTS)[:, :, 2:4]
        ey_norm = np.sqrt(ey[:, :, 0] ** 2 + ey[:, :, 1] ** 2)
        d_rel = np.where(ey_norm > 0, np.abs((ey[:, :, 0] - PHI * ei[:, :, 0])) / np.maximum(ey_norm, 1e-9), 0.0)
        floor = float(record.get("qi_energy_floor") or 0.0)
        available = rho > floor
        report["state_cells"].append({
            "capture_dir": str(Path(cap).relative_to(WORKSPACE)),
            "energy_floor": floor,
            "n_modes_total": int(rho.size),
            "n_available": int(available.sum()),
            "available_fraction": float(available.mean()),
            "rho_max": float(rho.max()),
            "q_median": float(np.median(q)),
            "chi_median": float(np.median(q / np.maximum(rho**2 / (rho**2 + 1 / PHI**2), 1e-12))),
            "top1pct_rho_share": concentration(rho, 0.01),
            "top10pct_rho_share": concentration(rho, 0.10),
            "median_relative_d_of_ey": float(np.median(d_rel)),
            "median_abs_d_over_ey": float(np.median(d / np.maximum(ey_norm, 1e-9))),
        })

    # ---- B. do the readout cells name the model's next token?
    features, labels, groups, confidences = [], [], [], []
    per_arm = []
    arm_spans = []
    for want, cap, flux_ids, logits_ids, record in candidates[: args.arms]:
        path = Path(cap)
        rows = 0
        arm_start = len(features)
        for i in flux_ids[: args.tokens]:
            if i not in set(logits_ids):
                continue
            flux = read_f32(path / f"qi-flux-{i}.f32")
            logits = read_f32(path / f"decode-logits-{i}.f32")
            label = int(logits.argmax())
            shifted = logits - logits.max()
            p = float(np.exp(shifted[label] - np.log(np.exp(shifted).sum())))
            features.append(flux)
            labels.append(label)
            confidences.append(p)
            groups.append(str(Path(cap).relative_to(WORKSPACE)))
            rows += 1
        per_arm.append({"capture_dir": str(Path(cap).relative_to(WORKSPACE)), "n_tokens": rows,
                        "n_flux_files": len(flux_ids)})
        arm_spans.append((arm_start, len(features)))
    if features:
        features = np.stack(features)
        all_labels = np.array(labels)
        # strict classes: a catch-all "other" bucket is not a class, and folding
        # sparse tokens into one caps the probe's accuracy by construction.
        mapped, usable, target_info = class_targets_strict(all_labels, max(8, len(labels) // 40))
        kept = np.where(usable)[0]
        output = evaluate(features[kept], mapped[kept], [groups[i] for i in kept],
                          folds=min(6, len(set(groups[i] for i in kept))), shuffles=6, rng=rng)
        zero_share = float((features == 0.0).mean())
        print(f"readout cells: {features.shape[0]} tokens x {features.shape[1]} cells, "
              f"{len(set(groups))} arms, {target_info['n_classes']} classes, coverage {target_info['coverage']:.3f}")
        print(f"  probe accuracy {output.get('accuracy', float('nan')):.3f} "
              f"balanced {output.get('balanced_accuracy', float('nan')):.3f} "
              f"majority {output.get('majority', float('nan')):.3f} "
              f"shuffled {output.get('shuffled_mean', float('nan')):.3f}"
              f"+-{output.get('shuffled_sd', float('nan')):.3f}")
        # per-token cell statistics
        amplitudes = np.abs(features)
        cells = features.reshape(len(features), -1, 2)
        cell_magnitude = np.sqrt(cells[:, :, 0] ** 2 + cells[:, :, 1] ** 2)
        top1_index = cell_magnitude[:, :WAVE_MODES].argmax(axis=1)
        for row, (start, stop) in zip(per_arm, arm_spans):
            segment = top1_index[start:stop]
            common = Counter(segment.tolist()).most_common(1)[0]
            row["dominant_top_cell"] = int(common[0])
            row["modal_top_cell_share"] = float(common[1] / len(segment))
            row["n_distinct_top_cells"] = int(len(set(segment.tolist())))
        report["readout"] = {
            "n_tokens": int(features.shape[0]),
            "n_cells_floats": int(features.shape[1]),
            "n_arms": len(set(groups)),
            "arms": per_arm,
            "zero_cell_share": zero_share,
            "mean_abs_cell": float(amplitudes.mean()),
            "median_model_confidence": float(np.median(confidences)),
            "modal_top_cell_share": float(Counter(top1_index.tolist()).most_common(1)[0][1] / len(top1_index)),
            "n_distinct_top_cells": len(set(top1_index.tolist())),
            "target": target_info,
            "probe": output,
            "cell_energy_vs_confidence_spearman": float(
                _spearman(np.abs(features).sum(axis=1), np.array(confidences))),
        }
        np.savez_compressed(HERE / "readout-cells.npz", features=features.astype(np.float32),
                            labels=all_labels, groups=np.array(groups), confidences=np.array(confidences))

    # ---- C. the field's own score of the tokens the model generated
    scores_rows = []
    for want, cap, flux_ids, logits_ids, record in candidates[: args.arms]:
        path = Path(cap)
        raw = Path(record["receipt"])
        receipt_path = raw if raw.is_absolute() else WORKSPACE / raw
        if not receipt_path.exists():
            continue
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        scores = receipt.get("generated_token_scores") or []
        generation = receipt.get("generation_token_ids") or []
        probs = []
        for i, token in enumerate(generation):
            logits_path = path / f"decode-logits-{i}.f32"
            if not logits_path.exists():
                probs.append(float("nan"))
                continue
            logits = read_f32(logits_path)
            shifted = logits - logits.max()
            probs.append(float(np.exp(shifted[token] - np.log(np.exp(shifted).sum()))))
        if len(scores) < 8:
            continue
        keep = [i for i in range(len(scores)) if i < len(probs) and np.isfinite(probs[i])]
        if len(keep) < 8:
            continue
        scores_rows.append({
            "capture_dir": str(Path(cap).relative_to(WORKSPACE)),
            "n_scored": len(scores),
            "spearman_score_vs_model_probability": float(
                _spearman(np.array([scores[i] for i in keep]), np.array([probs[i] for i in keep]))),
            "score_median": float(np.median(scores)),
            "model_probability_median": float(np.median([probs[i] for i in keep])),
        })
    report["field_scores"] = {"rows": scores_rows}
    for row in scores_rows:
        print(f"  field score vs model probability ({row['capture_dir']}): "
              f"spearman {row['spearman_score_vs_model_probability']:+.3f}")

    (HERE / "readout-preflight.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print("wrote readout-preflight.json")
    return 0


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 3:
        return float("nan")
    ra = np.argsort(np.argsort(a)).astype(np.float64)
    rb = np.argsort(np.argsort(b)).astype(np.float64)
    ra -= ra.mean()
    rb -= rb.mean()
    denom = np.sqrt((ra**2).sum() * (rb**2).sum())
    return float((ra * rb).sum() / denom) if denom > 0 else float("nan")


if __name__ == "__main__":
    raise SystemExit(main())
