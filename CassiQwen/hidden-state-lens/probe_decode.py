"""Linear probes on the captured residuals, one per layer, with controls.

Targets come free from the captures: the model's own next token is the argmax
of the stored logits for that exact state (see logit_lens.py for why the stored
distribution belongs to the captured row).  Two targets are probed:

  1. next-token identity: the model's own next token, coarse-classed
  2. continuation stance: whether the model's own continuation opens as a
     hedge/qualifier or as a direct claim, labelled by lexical rules over the
     captured continuation text

Every layer is probed with group-aware cross validation (a group is one
trajectory: prompt + its generation), against two controls reported side by
side: the always-most-frequent-class baseline and a shuffled-label control that
must land at chance.

Usage:
    python probe_decode.py [--width 5120] [--folds 5] [--shuffles 8]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lens_common import MODELS, WORKSPACE, decode_tokens, read_f32  # noqa: E402
from logit_lens import SUFFIX, build_state_index, label_file  # noqa: E402

HERE = Path(__file__).resolve().parent

HEDGE_PATTERNS = (
    " may", " might", " could", " likely", " probably", " perhaps", " possibly",
    " suggest", " seems", " appear", " roughly", " approximately", " somewhat",
    " tends", " generally", " typically", " in principle", " depends", " unclear",
    " not necessarily", " if ", " unless", " however", " but ", " can be",
    " would be", " should be", " assume", " tends to", " we cannot", " isn't",
    " don't", " cannot", " is not ", " varies",
)
CLAIM_PATTERNS = (
    " is ", " are ", " differs", " equals", " the ", " this ", " it ", " a ",
    " that ",
)


# ---------------------------------------------------------------------------
# folds
# ---------------------------------------------------------------------------

def balanced_group_folds(groups: list[str], n_splits: int) -> list[np.ndarray]:
    """Deterministic, size-balanced split by group."""
    index_of = {group: i for i, group in enumerate(sorted(set(groups)))}
    members: dict[int, list[int]] = defaultdict(list)
    for row, group in enumerate(groups):
        members[index_of[group]].append(row)
    order = sorted(members.values(), key=len, reverse=True)
    folds: list[list[int]] = [[] for _ in range(min(n_splits, len(order)))]
    load = [0] * len(folds)
    for rows in order:
        target = int(np.argmin(load))
        folds[target].extend(rows)
        load[target] += len(rows)
    return [np.array(sorted(fold)) for fold in folds if fold]


try:  # scipy's triangular solve is not affected by the LAPACK getrf pathology below
    from scipy.linalg import solve_triangular as _solve_triangular
except ImportError:  # pragma: no cover
    _solve_triangular = None


def solve_spd(matrix: np.ndarray, rhs: np.ndarray) -> np.ndarray:
    """Solve an SPD system without LAPACK getrf.

    `np.linalg.solve` / `np.linalg.inv` (LAPACK getrf/getri) run at ~0.5 MFLOPS on
    this Windows build once the operand exceeds ~100 rows (measured: 5.8 s for a
    200x200 solve), which makes a dual ridge probe intractable.  Cholesky plus two
    triangular solves is the same solution for an SPD kernel and runs ~4000x faster.
    A float32 kernel built from duplicated capture rows can still be numerically
    indefinite, so jitter is escalated and a clipped eigendecomposition is the last
    resort.  Also set OMP_NUM_THREADS=1 if the matmuls feel slow; that alone
    restores the dense solve here.
    """
    matrix = np.asarray(matrix, dtype=np.float64)
    rhs = np.asarray(rhs, dtype=np.float64)
    scale = float(np.trace(matrix)) / max(matrix.shape[0], 1) or 1.0
    eye = np.eye(matrix.shape[0])
    jitter = 0.0
    for _ in range(10):
        try:
            chol = np.linalg.cholesky(matrix + jitter * eye)
            break
        except np.linalg.LinAlgError:
            jitter = 1e-9 * scale if jitter == 0.0 else jitter * 10.0
    else:
        values, vectors = np.linalg.eigh(matrix)
        spectrum = np.maximum(values, 1e-12 * scale)
        return vectors @ ((vectors.T @ rhs) / spectrum[:, None])
    if _solve_triangular is not None:
        return _solve_triangular(chol, _solve_triangular(chol, rhs, lower=True, trans="T"), lower=True)
    return np.linalg.solve(chol.T, np.linalg.solve(chol, rhs))


def ridge_dual(Ztr: np.ndarray, Ytr: np.ndarray, lam: float) -> np.ndarray:
    kernel = Ztr @ Ztr.T
    gram = solve_spd(kernel + lam * np.eye(kernel.shape[0]), Ytr)
    return Ztr.T @ gram


def fit_predict(
    features: np.ndarray,
    labels: np.ndarray,
    train: np.ndarray,
    test: np.ndarray,
    groups: list[str] | None,
    lams: tuple[float, ...] = (0.03, 0.3, 3.0, 30.0),
    inner_splits: int = 3,
) -> np.ndarray:
    """Ridge probe with standardized features; lambda chosen inside train."""
    # float64 throughout: the kernel is built from residual rows that can repeat
    # across arms, and a float32 kernel is where the Cholesky above gave up.
    Xtr = np.asarray(features[train], dtype=np.float64)
    Xte = np.asarray(features[test], dtype=np.float64)
    mu = Xtr.mean(axis=0)
    sd = Xtr.std(axis=0) + 1e-6
    Ztr = (Xtr - mu) / sd
    Zte = (Xte - mu) / sd
    classes = sorted(set(labels[train].tolist()))
    lookup = {value: i for i, value in enumerate(classes)}
    Ytr = np.zeros((len(train), len(classes)), dtype=np.float64)
    Ytr[np.arange(len(train)), [lookup[int(v)] for v in labels[train]]] = 1.0

    if len(classes) < 2:
        return np.full(len(test), classes[0] if classes else -1)
    if groups is None or len(set(groups[i] for i in train)) < inner_splits:
        inner = [(np.arange(len(train)), np.arange(len(train)))]
    else:
        inner_groups = [groups[i] for i in train]
        pieces = balanced_group_folds(inner_groups, inner_splits)
        inner = []
        for piece in pieces:
            mask = np.ones(len(train), dtype=bool)
            mask[piece] = False
            inner.append((np.where(mask)[0], piece))

    best_lam, best_score = lams[0], -1.0
    for lam in lams:
        correct = total = 0
        for inner_train, inner_test in inner:
            weights = ridge_dual(Ztr[inner_train], Ytr[inner_train], lam)
            scores = Ztr[inner_test] @ weights
            correct += int((np.array(classes)[scores.argmax(axis=1)] == labels[train][inner_test]).sum())
            total += len(inner_test)
        score = correct / max(total, 1)
        if score > best_score:
            best_lam, best_score = lam, score
    weights = ridge_dual(Ztr, Ytr, best_lam)
    scores = Zte @ weights
    return np.array(classes)[scores.argmax(axis=1)]


def balanced_accuracy(predicted: np.ndarray, truth: np.ndarray) -> float:
    """Mean per-class recall over the classes actually present in this test fold."""
    classes = sorted(set(truth.tolist()))
    recalls = []
    for value in classes:
        rows = truth == value
        if rows.sum():
            recalls.append(float((predicted[rows] == value).mean()))
    return float(np.mean(recalls)) if recalls else float("nan")


def evaluate(
    features: np.ndarray,
    labels: np.ndarray,
    groups: list[str],
    folds: int,
    shuffles: int,
    rng: np.random.Generator,
) -> dict:
    partitions = balanced_group_folds(groups, folds)
    accuracies, majorities, shuffled = [], [], []
    balanced, shuffled_balanced = [], []
    counts = Counter(labels.tolist())
    for test in partitions:
        mask = np.ones(len(labels), dtype=bool)
        mask[test] = False
        train = np.where(mask)[0]
        if len(train) < 4 or len(set(labels[train].tolist())) < 2:
            continue
        predicted = fit_predict(features, labels, train, test, groups)
        accuracies.append(float((predicted == labels[test]).mean()))
        balanced.append(balanced_accuracy(predicted, labels[test]))
        train_counts = Counter(labels[train].tolist())
        majorities.append(train_counts.most_common(1)[0][1] / len(train))
        for _ in range(shuffles):
            permuted = labels.copy()
            permuted[train] = rng.permutation(labels[train])
            control = fit_predict(features, permuted, train, test, groups)
            shuffled.append(float((control == labels[test]).mean()))
            shuffled_balanced.append(balanced_accuracy(control, labels[test]))
    if not accuracies:
        return {}
    return {
        "accuracy": float(np.mean(accuracies)),
        "accuracy_folds": accuracies,
        "balanced_accuracy": float(np.nanmean(balanced)),
        "balanced_folds": balanced,
        "majority": float(np.mean(majorities)),
        "majority_global": float(counts.most_common(1)[0][1] / len(labels)),
        "class_counts": {str(k): v for k, v in counts.most_common()},
        "shuffled_mean": float(np.mean(shuffled)),
        "shuffled_sd": float(np.std(shuffled)),
        "shuffled_balanced_mean": float(np.nanmean(shuffled_balanced)),
        "shuffled_balanced_sd": float(np.nanstd(shuffled_balanced)),
        "shuffled_n": len(shuffled),
        "n_test_folds": len(accuracies),
        "beats_majority": bool(np.mean(accuracies) > np.mean(majorities) + 2 * np.std(accuracies) / max(np.sqrt(len(accuracies)), 1)),
        "above_shuffled": bool(np.mean(accuracies) > np.mean(shuffled) + 3 * (np.std(shuffled) + 1e-9)),
        "balanced_above_shuffled": bool(np.nanmean(balanced) > np.nanmean(shuffled_balanced) +
                                        3 * (np.nanstd(shuffled_balanced) + 1e-9)),
    }


# ---------------------------------------------------------------------------
# targets
# ---------------------------------------------------------------------------

def class_targets_strict(labels: np.ndarray, min_count: int) -> tuple[np.ndarray, np.ndarray, dict]:
    """Keep only states whose label is one of the well-populated classes.

    An earlier version of this probe folded every rare token into one catch-all
    index.  That is not a class: two states in it share no target, so a probe can
    never be right on it and the accuracy of the whole run is capped by how much
    of the sample is rare.  Here those states are dropped instead, and coverage
    is reported.
    """
    counts = Counter(int(value) for value in labels)
    kept = sorted([value for value, count in counts.items() if count >= min_count])
    lookup = {value: i for i, value in enumerate(kept)}
    mask = np.array([int(value) in lookup for value in labels])
    mapped = np.array([lookup.get(int(value), -1) for value in labels])
    return mapped, mask, {
        "kept_classes": kept,
        "n_classes": len(kept),
        "coverage": float(mask.mean()),
        "counts": {str(value): counts[value] for value in kept},
        "n_dropped": int((~mask).sum()),
        "min_count": min_count,
    }


def is_prompt_echo(record: dict) -> bool:
    """True when a receipt's `generation_token_ids` is really the prompt.

    The field name is not used consistently across arms: some receipts store the
    generated continuation and some store the tokenized prompt.  Four matching
    leading tokens is treated as an echo.
    """
    generation = list(record.get("generation_token_ids") or [])
    prompt = list(record.get("prompt_token_ids") or [])
    if len(generation) < 4 or len(prompt) < 4:
        return False
    return generation[:4] == prompt[:4]


def stance(text: str) -> int | None:
    """1 = hedge/qualifier opening, 0 = direct claim, None = not classifiable."""
    stripped = text.strip()
    if len(stripped) < 8:
        return None
    head = " " + stripped[:80].lower()
    hedges = sum(1 for pattern in HEDGE_PATTERNS if pattern in head)
    claims = sum(1 for pattern in CLAIM_PATTERNS if pattern in head)
    if hedges and not claims:
        return 1
    if claims and not hedges:
        return 0
    return None


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def trajectory_census(states: list[dict], groups: list[str], receipts: dict) -> dict:
    """How many independent trajectories do these states actually hold?

    A capture battery can hold hundreds of directories and still only a handful of
    independent trajectories, because arms re-run the same prompt under different
    field settings.  A trained read can only be evaluated across trajectories it
    has not seen, so the trajectory count -- not the directory count -- is the
    sample size, and it is reported here rather than assumed.
    """
    census = {}
    for kind in sorted({state["kind"] for state in states}):
        members = [i for i, state in enumerate(states) if state["kind"] == kind]
        prompts = Counter(tuple(states[i]["prompt_sha256"] or []) for i in members)
        generations = Counter(
            tuple(receipts.get(states[i]["capture_dirs"][0], {}).get("generation_token_ids") or [])[:6]
            for i in members
        )
        census[kind] = {
            "states": len(members),
            "capture_dirs": len({states[i]["capture_dirs"][0] for i in members}),
            "distinct_prompts": len(prompts),
            "largest_prompt_repeat": int(prompts.most_common(1)[0][1]),
            "distinct_generation_prefixes": len(generations),
            "largest_generation_repeat": int(generations.most_common(1)[0][1]),
            "independent_trajectories": len({groups[i] for i in members}),
        }
    return census


def too_few_trajectories(n_groups: int, min_groups: int, n_classes: int) -> str:
    """Gate for a cross-trajectory probe claim."""
    if n_classes < 2:
        return "one class remains after dropping sparse labels"
    if n_groups < min_groups:
        return (f"only {n_groups} independent trajectories (< --min-groups {min_groups}); the next-token "
                f"target is constant within a trajectory, so a held-out trajectory carries a class the "
                f"probe has never seen and the shuffled control cannot land at chance in a meaningful "
                f"sense")
    return ""


def fold_vacuity(targets: np.ndarray, groups: list[str], folds: int) -> list[dict]:
    """Per fold: does the held-out fold hold a class the training fold never saw?

    When the target is constant within a trajectory, every fold that holds out a
    trajectory holds out a class as well.  The probe then cannot be right, and the
    shuffled-label control cannot land at chance either -- it lands wherever the
    remaining classes put it, so the control stops being a control.  Recording
    this is what turns a 0.000 into a finding.
    """
    out = []
    for test in balanced_group_folds(groups, folds):
        train = np.setdiff1d(np.arange(len(targets)), test)
        train_classes = set(int(v) for v in targets[train].tolist())
        test_classes = sorted({int(v) for v in targets[test].tolist()})
        out.append({
            "fold_size": int(test.size),
            "held_out_classes": test_classes,
            "classes_absent_from_train": [c for c in test_classes if c not in train_classes],
            "train_states": int(train.size),
        })
    return out


def receipt_table() -> dict:
    inventory = json.loads((HERE / "capture-inventory.json").read_text(encoding="utf-8"))
    table = {}
    for record in inventory["records"]:
        raw = Path(record["capture_dir"])
        cap = raw if raw.is_absolute() else WORKSPACE / raw
        table[str(cap)] = record
    return table


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--width", type=int, default=0)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--shuffles", type=int, default=8)
    parser.add_argument("--min-class", type=int, default=8)
    parser.add_argument("--min-groups", type=int, default=20,
                        help="independent trajectories required before a per-layer probe is reported")
    args = parser.parse_args()

    rng = np.random.default_rng(20260916)
    index = build_state_index()
    receipts = receipt_table()
    report = {
        "mapper": ("strict per-kind classes: only labels with >= --min-class states are classes; "
                   "states outside them are dropped and counted, never folded into a catch-all"),
        "min_groups": args.min_groups,
        "probes": {},
        "capture_census": {},
        "label_consistency": {},
        "notes": [],
    }

    for width in sorted({state["width"] for state in index["states"]}):
        if args.width and width != args.width:
            continue
        states = [state for state in index["states"] if state["width"] == width and state["label"] is not None]
        if not states:
            continue
        grid_counts = Counter(tuple(state["layers"]) for state in states)
        grid = grid_counts.most_common(1)[0][0]
        dropped = sum(count for layers, count in grid_counts.items() if layers != grid)
        if dropped:
            report["notes"].append(f"width {width}: {dropped} states dropped (different layer grid)")
        states = [state for state in states if tuple(state["layers"]) == grid]
        layers = list(grid)
        position = {layer: i for i, layer in enumerate(layers)}
        token_map = MODELS[width]

        # --- provenance: which index of the receipt's generation does each
        # captured row's own stored distribution point at?  Measured, not
        # assumed: the stored argmax is looked up inside the receipt's token list
        # and the index is reported as an offset from the place the capture
        # claims.  A receipt whose `generation_token_ids` merely echoes the
        # prompt is excluded -- the field name is not used consistently across
        # arms, so each arm is classified before it is trusted.
        agree: dict[str, Counter] = defaultdict(Counter)
        reference = {"prompt": 0, "decode-early": 2, "decode": None}
        matched_index: dict[int, int] = {}
        echo_arms: set[str] = set()
        for state in states:
            record = receipts.get(state["capture_dirs"][0], {})
            generation = list(record.get("generation_token_ids") or [])
            if not generation:
                continue
            if is_prompt_echo(record):
                echo_arms.add(state["capture_dirs"][0])
                continue
            count = record.get("decode_logits_count") or len(
                list(Path(state["capture_dirs"][0]).glob("decode-logits-*.f32")))
            stored = int(read_f32(Path(state["capture_dirs"][0]) / label_file(state["kind"], count)).argmax())
            expect = reference[state["kind"]]
            expect = count if expect is None else expect
            hits = [j for j, token in enumerate(generation) if token == stored]
            if not hits:
                agree[state["kind"]]["absent_from_token_list"] += 1
                continue
            best = min(hits, key=lambda j: (abs(j - expect), j))
            matched_index[id(state)] = best
            agree[state["kind"]][best - expect] += 1
        offset_table = {kind: {str(delta): counts[delta] for delta in sorted(counts, key=str)} for kind, counts in agree.items()}
        report["label_consistency"][str(width)] = {
            "offset_from_expected_token_list_index": offset_table,
            "reference_index": {"prompt": 0, "decode-early": 2, "decode": "decode_logits_count"},
            "n_states_checked": {kind: sum(counts.values()) for kind, counts in agree.items()},
            "n_arms_with_prompt_echo_receipts": len(echo_arms),
            "prompt_echo_arms": sorted(echo_arms)[:6],
            "note": ("decode-logits-i predicts the token after index i, so the last decode row's own "
                     "next token is normally absent from a generation list of exactly count entries"),
        }
        print(f"width {width}: captured-row label position, offset from expected token-list index: "
              f"{ {k: dict(v) for k, v in offset_table.items()} }; "
              f"{len(echo_arms)} arm(s) excluded as prompt-echo receipts")
        report["notes"].append(
            f"width {width}: the captured row's own stored distribution lands on the index its capture "
            f"claims for {offset_table} (arms whose receipt token list echoes the prompt are excluded)"
        )

        features = np.full((len(layers), len(states), width), np.nan, dtype=np.float32)
        for column, state in enumerate(states):
            cap = Path(state["capture_dirs"][0])
            suffix = SUFFIX[state["kind"]]
            for layer in state["layers"]:
                features[position[layer], column] = read_f32(cap / f"layer-{layer}{suffix}.f32")

        labels = np.array([state["label"] for state in states], dtype=np.int64)
        kinds = np.array([state["kind"] for state in states], dtype=object)
        groups = []
        continuations = []
        for state in states:
            record = receipts.get(state["capture_dirs"][0], {})
            generation = list(record.get("generation_token_ids") or [])
            start = matched_index.get(id(state), 0)
            trusted = generation and not is_prompt_echo(record)
            continuations.append(decode_tokens(generation[start:], token_map) if trusted else "")
            prompt = (state["prompt_sha256"] or ["?"])[0]
            groups.append(f"{prompt}:{hashlib.sha256(repr(generation[:8]).encode()).hexdigest()[:12]}")

        census = trajectory_census(states, groups, receipts)
        report["capture_census"][str(width)] = census
        print(f"width {width}: states per kind { {k: v['states'] for k, v in census.items()} }; "
              f"independent trajectories { {k: v['independent_trajectories'] for k, v in census.items()} }; "
              f"largest repeat of one prompt {max(v['largest_prompt_repeat'] for v in census.values())}")

        # ---- target 1: next-token identity, per capture kind.
        # Pooling the three kinds would let the probe score by telling a first
        # decode row from a last one, which is not the question; and a pooled
        # target mixes three different majority tokens.
        for kind in sorted(set(kinds.tolist())):
            member = kinds == kind
            mapped, usable, target_info = class_targets_strict(labels[member], args.min_class)
            subset = np.where(member)[0][usable]
            targets = mapped[usable]
            subset_groups = [groups[i] for i in subset]
            n_groups = len(set(subset_groups))
            blocked = too_few_trajectories(n_groups, args.min_groups, target_info["n_classes"])
            print(f"width {width} {kind}: next-token probe: {target_info['n_classes']} classes "
                  f"({target_info['counts']}), coverage {target_info['coverage']:.3f}, "
                  f"n={len(subset)} of {int(member.sum())}, trajectories={n_groups}"
                  + (f" -> not supported: {blocked}" if blocked else ""))
            rows: list[dict] = []
            if blocked:
                report["notes"].append(f"width {width} {kind}: next-token probe not supported - {blocked}")
            for li, layer in enumerate(layers):
                keep = np.isfinite(features[li][subset]).all(axis=1)
                if int(keep.sum()) < 12 or len(set(targets[keep].tolist())) < 2:
                    rows.append({"layer": layer, "skipped": int(keep.sum())})
                    continue
                result = evaluate(features[li][subset][keep], targets[keep],
                                  [g for g, use in zip(subset_groups, keep) if use],
                                  args.folds, args.shuffles, rng)
                if result:
                    rows.append({"layer": layer, "n_states": int(keep.sum()), **result})
            report["probes"][f"next_token_{kind}_w{width}"] = {
                "kind": kind,
                "n_states": int(subset.size),
                "n_groups": n_groups,
                "trajectories": census[kind]["independent_trajectories"],
                "target": target_info,
                "not_supported": blocked,
                "rows": rows if not blocked else [],
                "rows_measured_but_not_supported": rows if blocked else [],
                "fold_vacuity": fold_vacuity(targets, subset_groups, args.folds) if blocked else [],
            }
        # pooled run over all kinds: documented as a comparison, not a headline
        mapped, usable, target_info = class_targets_strict(labels, args.min_class)
        subset = np.where(usable)[0]
        pooled_groups = [groups[i] for i in subset]
        n_groups = len(set(pooled_groups))
        blocked = too_few_trajectories(n_groups, args.min_groups, target_info["n_classes"])
        print(f"width {width} pooled: next-token probe: {target_info['n_classes']} classes "
              f"({target_info['counts']}), coverage {target_info['coverage']:.3f}, "
              f"n={int(usable.sum())}, trajectories={n_groups}"
              + (f" -> not supported: {blocked}" if blocked else ""))
        pooled_rows: list[dict] = []
        if blocked:
            report["notes"].append(f"width {width} pooled: next-token probe not supported - {blocked}")
        for li, layer in enumerate(layers):
            keep = np.isfinite(features[li][subset]).all(axis=1)
            if int(keep.sum()) < 12 or len(set(mapped[subset][keep].tolist())) < 2:
                pooled_rows.append({"layer": layer, "skipped": int(keep.sum())})
                continue
            result = evaluate(features[li][subset][keep], mapped[subset][keep],
                              [g for g, use in zip(pooled_groups, keep) if use],
                              args.folds, args.shuffles, rng)
            if result:
                pooled_rows.append({"layer": layer, "n_states": int(keep.sum()), **result})
        report["probes"][f"next_token_pooled_w{width}"] = {
            "kind": "pooled",
            "n_states": int(subset.size),
            "n_groups": n_groups,
            "target": target_info,
            "not_supported": blocked,
            "rows": pooled_rows if not blocked else [],
            "rows_measured_but_not_supported": pooled_rows if blocked else [],
            "fold_vacuity": fold_vacuity(mapped[subset], pooled_groups, args.folds) if blocked else [],
        }

        # ---- target 2: continuation stance
        stance_labels = np.array([stance(text) if text else None for text in continuations], dtype=object)
        present = np.array([value is not None for value in stance_labels])
        counts = Counter(int(value) for value in stance_labels[present])
        stance_groups_all = [g for g, keep in zip(groups, present) if keep]
        stance_groups_n = len(set(stance_groups_all))
        print(f"width {width}: stance probe: {int(present.sum())}/{len(states)} classifiable, "
              f"counts {dict(counts)}, trajectories {stance_groups_n}")
        if (present.sum() >= 24 and len(counts) >= 2 and all(count >= 8 for count in counts.values())
                and stance_groups_n >= args.min_groups):
            stance_rows = []
            stance_y = np.array([int(value) for value in stance_labels[present]])
            stance_groups = stance_groups_all
            for li, layer in enumerate(layers):
                keep = np.isfinite(features[li][present]).all(axis=1)
                if int(keep.sum()) < 16 or len(set(stance_y[keep].tolist())) < 2:
                    stance_rows.append({"layer": layer, "skipped": int(keep.sum())})
                    continue
                result = evaluate(features[li][present][keep], stance_y[keep],
                                  [g for g, use in zip(stance_groups, keep) if use],
                                  args.folds, args.shuffles, rng)
                if result:
                    stance_rows.append({"layer": layer, "n_states": int(keep.sum()), **result})
            report["probes"][f"stance_w{width}"] = {
                "n_states": int(present.sum()),
                "n_groups": stance_groups_n,
                "counts": {str(k): v for k, v in counts.items()},
                "examples": {str(k): [t[:70] for t in continuations if t and stance(t) == k][:3] for k in counts},
                "rows": stance_rows,
            }
        else:
            report["probes"][f"stance_w{width}"] = {
                "n_states": int(present.sum()),
                "n_groups": stance_groups_n,
                "counts": {str(k): v for k, v in counts.items()},
                "skipped": (f"not supported by these captures: {int(present.sum())} of "
                            f"{len(states)} continuations classifiable, counts {dict(counts)}, "
                            f"{stance_groups_n} independent trajectories "
                            f"(< --min-groups {args.min_groups})"),
                "rows": [],
            }
            report["notes"].append(
                f"width {width}: stance probe skipped, {int(present.sum())} of {len(states)} continuations "
                f"classifiable with counts {dict(counts)} over {stance_groups_n} trajectories"
            )

    (HERE / "probe-results.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    for key, block in report["probes"].items():
        if not block["rows"]:
            if block.get("not_supported"):
                measured = [row for row in block.get("rows_measured_but_not_supported", []) if "accuracy" in row]
                print(f"{key}: NOT SUPPORTED - {block['not_supported']}")
                if measured:
                    best = max(measured, key=lambda row: row["accuracy"])
                    print(f"    measured anyway at layer {best['layer']}: accuracy {best['accuracy']:.3f} "
                          f"balanced {best['balanced_accuracy']:.3f} majority {best['majority']:.3f} "
                          f"shuffled {best['shuffled_mean']:.3f}+-{best['shuffled_sd']:.3f} "
                          f"(kept only as evidence that this control cannot land at chance)")
                continue
            print(f"{key}: no rows ({block.get('skipped', 'n/a')})")
            continue
        rows = [row for row in block["rows"] if "accuracy" in row]
        best = max(rows, key=lambda row: row["accuracy"])
        print(f"{key}: n={block['n_states']} classes={block['target'].get('n_classes', '?')} "
              f"trajectories={block.get('n_groups', '?')} "
              f"best layer {best['layer']} ({best.get('n_states', '?')} states) "
              f"accuracy {best['accuracy']:.3f} balanced {best.get('balanced_accuracy', float('nan')):.3f} "
              f"majority {best['majority']:.3f} shuffled {best['shuffled_mean']:.3f}+-{best['shuffled_sd']:.3f}")
    print("wrote probe-results.json (mapper: strict per-kind classes, no catch-all bucket)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
