#!/usr/bin/env python3
"""Does carrying the field state forward change how the model writes?

The modulation seam adds a bounded field term to the model's own recurrent-state
write, and the harness writes the resulting Qi field state to `state-after.f32`.
This driver threads that file back in as the next run's input state, so the field
is no longer a fixed fixture: every generation it produces is fed to the field,
which changes the model's hidden activations, which changes the field in turn.

Two arms run the same prompts in the same order with the same output bound:

  on    the modulation seam at the gain the binding ladder measured as saturating
        its cap (`run_field_modulation_binding.py`: gain 100 puts the field's
        added RMS at the model row's own RMS), with `state-after.f32` carried
        forward.
  off   the identical pipeline at gain 0.  No seam is built, so the graph is the
        plain write; the carry loop still runs.  This arm is therefore a null
        control on the carry alone: its prose must repeat exactly, epoch after
        epoch, because nothing in the graph reads the state.

Tics are counted per generation from an explicit lexicon, normalised to words, so
a drift in how the prose is written is visible beside the field state's own
evolution (rho and the memory tail's energy per epoch).

The blind read happens in two steps so the labels cannot be read backwards: the
generation step writes `blind/epoch-<e>-<label>.txt` and the label mapping in
`blind/mapping.json`; the guess is written to `blind/guess.json` before the
mapping is opened, and `--score` is the only step that opens it.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_field_aim_profile as aim

ROOT = Path(__file__).resolve().parent.parent
INITIAL_STATE = ROOT / "native/llama.cpp/_diag/tmp-amp-wave/w1.f32"

#### The gain the binding ladder measured as saturating the cap on this fixture:
#### budget = 6.335, so every gain at or above it adds a field row as loud as the
#### model's own row (added_RMS/row_RMS = 1.0).
FIELD_GAIN = 100.0
STEPS = 4
EPOCHS = 6
GENERATE_TOKENS = 200

PROMPTS: tuple[tuple[str, str], ...] = (
    ("reread",
     "Describe what you notice when you reread a paragraph you wrote a year ago. "
     "Answer in at most 120 words.\n"),
    ("river",
     "Explain why a river's shape and its flow cannot be described separately. "
     "Answer in at most 120 words.\n"),
    ("workshop",
     "Describe a workshop where every tool is left where it was last used. "
     "Answer in at most 120 words.\n"),
)

ARMS: tuple[tuple[str, float], ...] = (("on", FIELD_GAIN), ("off", 0.0))

MODE_COUNT = 6144
SCALE_COUNT = 4
COMPONENT_COUNT = 9
RANGES: tuple[tuple[str, int, int], ...] = (
    ("wave", 0, 3072),
    ("mid", 3072, 5120),
    # Persistence lives in the tail beyond the wave support.
    ("memory_tail", 5120, 6144),
)

#### The tic lexicon.  Each entry is (name, regex); the count is the number of
#### matches in one generation, reported beside the generation's word count.
TICS: tuple[tuple[str, str], ...] = (
    ("not_just_but", r"\bnot\s+(?:just|only)\b[^.!?]{0,80}?\bbut\b"),
    ("em_dash", r"—|\s-\s"),
    ("parenthetical", r"\("),
    ("tricolon", r"\b[\w'-]+(?:,[^,.;:!?]{0,40}){2},?\s+and\b"),
    ("lets", r"\b(?:Let|let)['\u2019]s\b"),
    ("heres_the_thing", r"\bhere['\u2019]s the thing\b"),
    ("worth_noting", r"\bit['\u2019]s worth noting\b|\bworth noting\b"),
    ("delve", r"\bdelv(?:e|es|ed|ing)\b"),
    ("closing_summary", r"(?:^|[.!?]\s+)(?:In conclusion|In summary|In short|Overall|"
                       r"Ultimately|To sum up|All in all|The key takeaway|In the end)\b"),
    ("additive_connective", r"\b(?:Moreover|Furthermore|Additionally)\b"),
)


def count_tics(text: str) -> dict[str, int]:
    return {name: len(re.findall(pattern, text)) for name, pattern in TICS}


def state_metrics(path: Path) -> dict[str, Any]:
    """rho and energy of a Qi state file, per mode range.

    The state layout is `[scale][mode][component]` in C order, so a mode's
    amplitude is the largest component magnitude it holds and `rho` is the
    largest amplitude in the range.
    """
    values = np.fromfile(path, dtype=np.float32)
    expected = MODE_COUNT * SCALE_COUNT * COMPONENT_COUNT
    if values.size != expected:
        raise RuntimeError(f"state file has {values.size} floats, expected {expected}: {path}")
    if not np.isfinite(values).all():
        raise RuntimeError(f"state file is not finite: {path}")
    grid = values.astype(np.float64).reshape(SCALE_COUNT, MODE_COUNT, COMPONENT_COUNT)
    amplitude = np.abs(grid).max(axis=(0, 2))
    ranges: dict[str, Any] = {}
    for name, low, high in RANGES:
        block = grid[:, low:high, :]
        ranges[name] = {
            "rho_max": float(amplitude[low:high].max()),
            "energy": float(np.mean(block * block)),
        }
    return {
        "rho_max": float(amplitude.max()),
        "energy_total": float(np.mean(grid * grid)),
        "ranges": ranges,
        "sha256": aim.sha256(path),
    }


def run_generation(args: argparse.Namespace, run_dir: Path, prompt_path: Path,
                   state_in: Path, gain: float) -> dict[str, Any]:
    run_dir.mkdir(parents=True)
    captures = run_dir / "captures"
    captures.mkdir()
    command = [
        str(args.binary), str(args.model), str(state_in), args.backend,
        str(prompt_path), str(args.layer), str(STEPS), str(args.alpha),
        str(args.generate_tokens), str(captures), "0", "0",
        # The modulation seam keeps the model's own write, so the displacement
        # stays 0 and the substitution share stays 0 in both arms.
        "--modulate", "--modulate-gain", repr(gain), "--flux-dump",
    ]
    started = time.perf_counter()
    process = subprocess.run(
        command, text=True, encoding="utf-8", errors="replace",
        capture_output=True, timeout=args.timeout,
    )
    wall_seconds = time.perf_counter() - started
    (run_dir / "stdout.log").write_text(process.stdout, encoding="utf-8")
    (run_dir / "stderr.log").write_text(process.stderr, encoding="utf-8")
    if process.returncode != 0:
        raise RuntimeError(f"run failed with {process.returncode}; see {run_dir}")
    receipt = aim.parse_receipt(process.stdout)
    if receipt.get("qi_modulate") is not True:
        raise RuntimeError(f"--modulate did not reach the harness: {run_dir}")
    if int(receipt.get("steps", 0)) != STEPS:
        raise RuntimeError(f"coupling steps did not reach the harness: {run_dir}")
    receipt["command"] = command
    receipt["process_wall_seconds"] = wall_seconds
    receipt["state_in"] = str(state_in)
    receipt["state_in_sha256"] = aim.sha256(state_in)
    receipt["modulate_gain_requested"] = gain
    aim.atomic_json(run_dir / "receipt.json", receipt)
    return receipt


def flux_row_rms(receipt: dict[str, Any], field_width: int) -> float | None:
    paths = aim.flux_capture_paths(receipt)
    if not paths:
        return None
    values = np.fromfile(paths[0], dtype=np.float32).astype(np.float64)
    if values.size < field_width:
        return None
    row = values[:field_width]
    return float(np.sqrt(np.mean(row * row)))


def draw_mapping(rng: random.Random, arms: tuple[str, ...]) -> list[str]:
    order = list(arms)
    rng.shuffle(order)
    return order


def blind_order(epochs: int, arms: tuple[str, ...], seed: int) -> list[list[str]]:
    """A per-epoch label order that is not constant and never repeats four times.

    A run whose labels sit in the same order every epoch cannot be read blind:
    the earlier blind attempt had four identically ordered epochs in a row, so
    the order drawn here is required to vary within the run and to change at
    least every third epoch.
    """
    for attempt in range(200):
        rng = random.Random(seed + attempt)
        orders = [draw_mapping(rng, arms) for _ in range(epochs)]
        if len({tuple(order) for order in orders}) < 2:
            continue
        longest = 1
        run = 1
        for previous, current in zip(orders, orders[1:]):
            run = run + 1 if current == previous else 1
            longest = max(longest, run)
        if longest <= 2:
            return orders
    raise RuntimeError("could not draw a label order that varies across epochs")


def carry_forward(args: argparse.Namespace) -> dict[str, Any]:
    args.out.mkdir(parents=True, exist_ok=True)
    blind = args.out / "blind"
    blind.mkdir(exist_ok=True)
    prompt_paths: list[Path] = []
    prompts_dir = args.out / "prompts"
    prompts_dir.mkdir(exist_ok=True)
    for index, (name, text) in enumerate(PROMPTS):
        path = prompts_dir / f"{index:02d}-{name}.txt"
        path.write_text(text, encoding="utf-8")
        prompt_paths.append(path)

    arm_names = tuple(name for name, _gain in ARMS)
    orders = blind_order(args.epochs, arm_names, args.blind_seed)
    mapping = {str(epoch): dict(zip("AB", order)) for epoch, order in enumerate(orders)}
    aim.atomic_json(blind / "mapping.json", {
        "seed": args.blind_seed,
        "labels": ["A", "B"],
        "order_per_epoch": {str(epoch): order for epoch, order in enumerate(orders)},
        "mapping": mapping,
        "distinct_orders": len({tuple(order) for order in orders}),
    })
    print(f"blind labels drawn: {len({tuple(o) for o in orders})} distinct orders over "
          f"{args.epochs} epochs", flush=True)

    # Each arm's chain: the state the next run of that arm reads.
    chain_state = {name: args.state for name, _gain in ARMS}
    rows: list[dict[str, Any]] = []
    for epoch in range(args.epochs):
        for prompt_index, prompt_path in enumerate(prompt_paths):
            for arm, gain in ARMS:
                label = next(letter for letter, name in mapping[str(epoch)].items() if name == arm)
                run_dir = args.out / "runs" / f"epoch-{epoch}" / f"{label}-{arm}-p{prompt_index}"
                state_in = chain_state[arm]
                receipt = run_generation(args, run_dir, prompt_path, state_in, gain)
                state_out = run_dir / "captures" / "state-after.f32"
                if not state_out.is_file():
                    raise RuntimeError(f"no state-after.f32 written: {run_dir}")
                text = receipt.get("generation_text", "")
                words = len(text.split())
                tics = count_tics(text)
                metrics = state_metrics(state_out)
                width = int(receipt.get("state_field_width") or 0)
                row = {
                    "epoch": epoch,
                    "arm": arm,
                    "label": label,
                    "gain": gain,
                    "prompt_index": prompt_index,
                    "prompt_name": PROMPTS[prompt_index][0],
                    "run_dir": str(run_dir),
                    "state_in": str(state_in),
                    "state_out": str(state_out),
                    "state_out_sha256": metrics["sha256"],
                    "generation_text": text,
                    "generation_chars": len(text),
                    "generation_words": words,
                    "tics": tics,
                    "tics_per_100_words": {
                        name: (100.0 * value / words) if words else 0.0
                        for name, value in tics.items()
                    },
                    "modulate_budget": receipt.get("modulate_budget"),
                    "modulate_scale": receipt.get("modulate_scale"),
                    "field_row_rms": flux_row_rms(receipt, width) if width else None,
                    "state_rho_max": metrics["rho_max"],
                    "state_energy_total": metrics["energy_total"],
                    "state_ranges": metrics["ranges"],
                    "state_max_abs_delta": receipt.get("state_max_abs_delta"),
                    "wall_seconds": receipt["process_wall_seconds"],
                }
                rows.append(row)
                chain_state[arm] = state_out
                print(
                    f"  epoch {epoch} p{prompt_index} {arm:<3} label {label} words={words:>3} "
                    f"rho={metrics['rho_max']:.4g} tail_E={metrics['ranges']['memory_tail']['energy']:.4g} "
                    f"tics={sum(tics.values())}", flush=True,
                )

    per_arm: dict[str, Any] = {}
    for arm, _gain in ARMS:
        arm_rows = [row for row in rows if row["arm"] == arm]
        per_arm[arm] = {
            "generations": len(arm_rows),
            "words": int(sum(row["generation_words"] for row in arm_rows)),
            "tic_totals": {
                name: int(sum(row["tics"][name] for row in arm_rows))
                for name, _pattern in TICS
            },
            # One entry per prompt: how many distinct answers the arm produced for
            # it across the epochs.  The field-off arm answers a prompt from the
            # state alone, so its entry must be 1; a carry loop that moved the
            # prose by itself would raise it.
            "distinct_texts_per_prompt": {
                str(prompt_index): len({
                    row["generation_text"] for row in arm_rows
                    if row["prompt_index"] == prompt_index
                })
                for prompt_index in range(len(PROMPTS))
            },
            "state_rho_per_epoch": [row["state_rho_max"] for row in arm_rows],
            "memory_tail_energy_per_epoch": [
                row["state_ranges"]["memory_tail"]["energy"] for row in arm_rows
            ],
        }

    receipt_out = {
        "schema": "cassi.field-carry-forward.v1",
        "model": str(args.model),
        "model_sha256": aim.sha256(args.model),
        "binary": str(args.binary),
        "binary_sha256": aim.sha256(args.binary),
        "backend": args.backend,
        "layer": args.layer,
        "steps": STEPS,
        "alpha": args.alpha,
        "generate_tokens": args.generate_tokens,
        "epochs": args.epochs,
        "field_gain": FIELD_GAIN,
        "initial_state": str(args.state),
        "initial_state_sha256": aim.sha256(args.state),
        "initial_state_metrics": state_metrics(args.state),
        "blind_seed": args.blind_seed,
        "tic_lexicon": {name: pattern for name, pattern in TICS},
        "per_arm": per_arm,
        "rows": rows,
    }
    aim.atomic_json(args.out / "carry.json", receipt_out)
    return receipt_out


def score(args: argparse.Namespace) -> int:
    """Report the blind guesses against the mapping this step is first to open."""
    mapping_path = args.out / "blind" / "mapping.json"
    guess_path = args.out / "blind" / "guess.json"
    if not mapping_path.is_file() or not guess_path.is_file():
        raise RuntimeError("both blind/mapping.json and blind/guess.json are required")
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    guesses = json.loads(guess_path.read_text(encoding="utf-8"))
    if "mapping" not in mapping:
        raise RuntimeError("blind/mapping.json carries no mapping")
    order = mapping["order_per_epoch"]
    print(f"blind seed {mapping['seed']}; distinct orders {mapping['distinct_orders']}")
    correct = 0
    epochs = sorted(order, key=int)
    for epoch in epochs:
        label = str(guesses[epoch])
        truth = mapping["mapping"][epoch]
        hit = truth.get(label) == "on"
        correct += int(hit)
        print(
            f"  epoch {epoch}: guessed {label} = {truth.get(label):<3} "
            f"{'correct' if hit else 'wrong'}   order {order[epoch]}"
        )
    total = len(epochs)
    print(f"guessed the field arm in {correct}/{total} epochs")
    expected = total / 2.0
    print(f"chance level {expected:.1f}/{total}")
    return 0


def load_state(path: Path) -> np.ndarray:
    values = np.fromfile(path, dtype=np.float32)
    expected = MODE_COUNT * SCALE_COUNT * COMPONENT_COUNT
    if values.size != expected:
        raise RuntimeError(f"state file has {values.size} floats, expected {expected}: {path}")
    return values.astype(np.float64).reshape(SCALE_COUNT, MODE_COUNT, COMPONENT_COUNT)


def state_shape_metrics(grid: np.ndarray) -> dict[str, Any]:
    """Amplitude, saturation and sign structure of one state.

    The Qi state is a saturating integrator: every entry is clamped to +/-64 on
    each read, so a long generation pins most of the state at the clamp and the
    information left is *which* entries are pinned and with which sign.  rho
    alone cannot see that, so the saturated fraction and the sign pattern are
    reported beside it.
    """
    out: dict[str, Any] = {}
    for name, low, high in RANGES:
        block = grid[:, low:high, :]
        out[name] = {
            "rho_max": float(np.abs(block).max()),
            "energy": float(np.mean(block * block)),
            "saturated_fraction": float(np.mean(np.abs(block) >= 63.999)),
        }
    return out


def sign_pattern(grid: np.ndarray, low: int, high: int) -> np.ndarray:
    signs = np.sign(grid[:, low:high, :])
    return signs.ravel()


def compare_states(a: np.ndarray, b: np.ndarray) -> dict[str, float]:
    """How far apart two states are in value and in sign pattern."""
    delta = a - b
    denominator = float(np.linalg.norm(a))
    same_sign = float(np.mean(np.sign(a) == np.sign(b)))
    return {
        "relative_l2": float(np.linalg.norm(delta)) / denominator if denominator else 0.0,
        "sign_agreement": same_sign,
        "max_abs_delta": float(np.abs(delta).max()),
    }


def analyze(args: argparse.Namespace) -> int:
    """Read the receipts already on disk and report the carry loop's own evolution."""
    carry_path = args.out / "carry.json"
    if not carry_path.is_file():
        raise RuntimeError(f"no carry receipt to analyze: {carry_path}")
    carry = json.loads(carry_path.read_text(encoding="utf-8"))
    rows = carry["rows"]
    by_key = {(row["epoch"], row["prompt_index"], row["arm"]): row for row in rows}

    #### The checkpoint carried into the next epoch is the state after the last
    #### prompt of the epoch, so the epoch table reads that state.
    last_prompt = max(row["prompt_index"] for row in rows)
    checkpoints: dict[str, list[np.ndarray]] = {arm: [] for arm, _gain in ARMS}
    table: list[dict[str, Any]] = []
    for epoch in range(carry["epochs"]):
        entry: dict[str, Any] = {"epoch": epoch, "arms": {}}
        for arm, _gain in ARMS:
            row = by_key[(epoch, last_prompt, arm)]
            grid = load_state(Path(row["state_out"]))
            checkpoints[arm].append(grid)
            shape = state_shape_metrics(grid)
            entry["arms"][arm] = {
                "run": f"epoch-{epoch}/p{last_prompt}/{arm}",
                "state_out": row["state_out"],
                "sha256": row["state_out_sha256"],
                "rho_max": float(np.abs(grid).max()),
                "energy_total": float(np.mean(grid * grid)),
                "ranges": shape,
            }
        on_grid = checkpoints["on"][-1]
        off_grid = checkpoints["off"][-1]
        entry["on_vs_off"] = compare_states(on_grid, off_grid)
        entry["on_vs_off"]["memory_tail_sign_agreement"] = float(
            np.mean(sign_pattern(on_grid, *RANGES[-1][1:]) == sign_pattern(off_grid, *RANGES[-1][1:]))
        )
        entry["on_vs_off_previous_epoch"] = (
            compare_states(checkpoints["on"][-1], checkpoints["on"][-2])
            if len(checkpoints["on"]) > 1 else None
        )
        entry["off_vs_previous_epoch"] = (
            compare_states(checkpoints["off"][-1], checkpoints["off"][-2])
            if len(checkpoints["off"]) > 1 else None
        )
        table.append(entry)

    tic_table = {
        arm: {
            str(epoch): {
                name: int(sum(
                    row["tics"][name] for row in rows
                    if row["arm"] == arm and row["epoch"] == epoch
                ))
                for name, _pattern in TICS
            }
            for epoch in range(carry["epochs"])
        }
        for arm, _gain in ARMS
    }
    words_table = {
        arm: {
            str(epoch): int(sum(
                row["generation_words"] for row in rows
                if row["arm"] == arm and row["epoch"] == epoch
            ))
            for epoch in range(carry["epochs"])
        }
        for arm, _gain in ARMS
    }
    result = {
        "schema": "cassi.field-carry-forward-analysis.v1",
        "source": str(carry_path),
        "epochs": carry["epochs"],
        "checkpoint_prompt_index": last_prompt,
        "epoch_table": table,
        "tic_table": tic_table,
        "words_table": words_table,
        "tic_lexicon": carry["tic_lexicon"],
    }
    aim.atomic_json(args.out / "carry-analysis.json", result)

    print(f"checkpoint state = state after prompt {last_prompt} of each epoch")
    print()
    print(f"{'epoch':>5} | {'on rho':>10} {'on sat':>7} {'on tailE':>10} | "
          f"{'off rho':>10} {'off sat':>7} {'off tailE':>10} | {'on/off L2':>10} {'sign agree':>10} | "
          f"{'on drift':>10} {'off drift':>10}")
    for entry in table:
        on = entry["arms"]["on"]
        off = entry["arms"]["off"]
        tail = RANGES[-1][0]
        comparison = entry["on_vs_off"]
        on_prev = entry["on_vs_off_previous_epoch"]
        off_prev = entry["off_vs_previous_epoch"]
        print(
            f"{entry['epoch']:>5} | {on['rho_max']:>10.4g} {on['ranges'][tail]['saturated_fraction']:>7.3f} "
            f"{on['ranges'][tail]['energy']:>10.4g} | {off['rho_max']:>10.4g} "
            f"{off['ranges'][tail]['saturated_fraction']:>7.3f} {off['ranges'][tail]['energy']:>10.4g} | "
            f"{comparison['relative_l2']:>10.4g} {comparison['sign_agreement']:>10.4f} | "
            f"{(on_prev['relative_l2'] if on_prev else float('nan')):>10.4g} "
            f"{(off_prev['relative_l2'] if off_prev else float('nan')):>10.4g}"
        )
    print()
    print("wave range (modes 0-3071) saturation, the range the seam's readout reads:")
    for entry in table:
        print(f"  epoch {entry['epoch']}: on {entry['arms']['on']['ranges']['wave']['saturated_fraction']:.3f} "
              f"saturated, rho {entry['arms']['on']['ranges']['wave']['rho_max']:.4g}; "
              f"off {entry['arms']['off']['ranges']['wave']['saturated_fraction']:.3f} "
              f"saturated, rho {entry['arms']['off']['ranges']['wave']['rho_max']:.4g}")
    print()
    names = [name for name, _pattern in TICS]
    print("per generation (generation x arm x tic type):")
    print(f"{'run':<26}" + " ".join(f"{name[:9]:>9}" for name in names) + f"{'total':>7}{'words':>7}")
    for row in rows:
        counts = row["tics"]
        tag = f"e{row['epoch']}p{row['prompt_index']}-{row['arm']}"
        print(f"{tag:<26}" + " ".join(f"{counts[name]:>9}" for name in names)
              + f"{sum(counts.values()):>7}{row['generation_words']:>7}")
    print()
    for arm, _gain in ARMS:
        print(f"tics per generation set, arm {arm} (3 generations per epoch):")
        print("  epoch " + " ".join(f"{name[:9]:>9}" for name in names) + f"{'total':>8}{'words':>8}")
        for epoch in range(carry["epochs"]):
            counts = tic_table[arm][str(epoch)]
            total = sum(counts.values())
            words = words_table[arm][str(epoch)]
            print(f"  {epoch:>5} " + " ".join(f"{counts[name]:>9}" for name in names)
                  + f"{total:>8}{words:>8}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, default=aim.LATENT_BINARY)
    parser.add_argument("--model", type=Path, default=aim.DEFAULT_MODEL)
    parser.add_argument("--state", type=Path, default=INITIAL_STATE)
    parser.add_argument("--backend", default="gpu")
    parser.add_argument("--layer", type=int, default=32)
    parser.add_argument("--alpha", type=float, default=0.01)
    parser.add_argument("--generate-tokens", type=int, default=GENERATE_TOKENS)
    parser.add_argument("--epochs", type=int, default=EPOCHS)
    parser.add_argument("--blind-seed", type=int, default=20260916)
    parser.add_argument("--timeout", type=float, default=1800.0)
    parser.add_argument("--out", type=Path,
                        default=ROOT / "native/llama.cpp/_diag/carry-forward")
    parser.add_argument("--score", action="store_true",
                        help="score blind/guess.json against blind/mapping.json")
    parser.add_argument("--analyze", action="store_true",
                        help="report the carry loop's own evolution and the tic tables from carry.json")
    args = parser.parse_args()
    if args.epochs < 2:
        raise RuntimeError("the carry loop needs at least two epochs")
    if args.score:
        return score(args)
    if args.analyze:
        return analyze(args)
    for path in (args.binary, args.model, args.state):
        if not path.is_file():
            raise RuntimeError(f"required file is missing: {path}")
    result = carry_forward(args)
    print()
    print(f"{'epoch':>5} {'p':>2} {'arm':>4} {'words':>6} {'ticks':>6} {'rho':>10} {'tail_E':>12}")
    for row in result["rows"]:
        print(
            f"{row['epoch']:>5} {row['prompt_index']:>2} {row['arm']:>4} "
            f"{row['generation_words']:>6} {sum(row['tics'].values()):>6} "
            f"{row['state_rho_max']:>10.4g} {row['state_ranges']['memory_tail']['energy']:>12.4g}"
        )
    print()
    for arm, summary in result["per_arm"].items():
        print(f"{arm}: {summary['generations']} generations, {summary['words']} words, "
              f"tics {summary['tic_totals']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
