#!/usr/bin/env python3
"""Does the modulation seam reach the model once its cap actually binds?

The modulation seam (`build_cassi_qi_state_modulated`) adds `scale * field_row` to
the model's own recurrent-state write, with `scale = min(gain, budget)` and
`budget = row_RMS / field_RMS`.  So the share of the row the field contributes is

    added_RMS / row_RMS = min(1, gain / budget)

which is 1 only when the gain reaches the measured budget.  Every modulation arm
run before this driver used the default gain 1.0, whose share is `1 / budget` and
therefore a few percent: a gain ladder that never reached the budget measured a
sub-threshold nudge, not the seam's ceiling.

This driver therefore reports the two seam scalars beside the model's response.
The harness reads both back from the graph (`modulate_budget`, `modulate_scale`),
so the ratio is measured rather than inferred, and the driver cross-checks that
`scale == min(budget, gain)`.  The field row's own RMS comes from the flux
capture, which lets `row_RMS = budget * field_RMS` be checked for stability
across the ladder.

The model-side displacement is the per-decode logit displacement.  The
`logits.f32` capture is the prompt prefill, where the seam does not act, so it is
reported as the prefill control and not as the arm's effect.

A fixture too quiet to bind below the harness gain cap builds a louder fixture
instead of being declared unmeasurable: the driver rescales the state until the
cap binds, and records every fixture it made.

  off            the field is disabled (STEPS 0); the reference.
  mod-gain-<g>   one gain on one fixture, the whole ladder on the first fixture.

The run is refused when an arm directory already exists: a profile that mixes
receipts from two runs is not a profile.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_field_aim_profile as aim

ROOT = Path(__file__).resolve().parent.parent
GAIN_CAP = 1.0e6
DEFAULT_STATES = (
    ROOT / "native/llama.cpp/_diag/tmp-amp-wave/w1.f32",
    ROOT / "native/llama.cpp/_diag/tmp-amp-wave/w1000.f32",
)
#### The rung names would collide between states, so a rung is `gain-<g>` under its own state.
#### The ladder brackets the measured budget (both fixtures sit near 5-7) and then runs
#### three orders past it, so the ramp and the saturated floor are both visible.
LADDER = (0.0, 0.25, 0.5, 1.0, 2.0, 4.0, 10.0, 100.0, 1.0e3, 1.0e4, 1.0e6)
LEGACY_PROFILES = (
    ROOT / "native/llama.cpp/_diag/aim-profile-modulate-gain/profile.json",
    ROOT / "native/llama.cpp/_diag/aim-profile-modulate-gain2/profile.json",
)


def gain_name(gain: float) -> str:
    if gain == 0.0:
        return "identity"
    return f"gain-{gain:g}"


def state_label(path: Path) -> str:
    return path.stem


def seam_ratio(receipt: dict[str, Any], gain: float) -> dict[str, float | bool | None]:
    """The measured share of the row the field added, with its own consistency checks.

    `ratio` is `scale / budget` as both were read back from the graph, so it is
    the number the seam itself produced.  `expected` is `min(1, gain / budget)`
    from the seam's documented rule, and `scale_agrees` says whether the two
    scalars the graph held satisfy `scale == min(budget, gain)`.
    """
    budget = receipt.get("modulate_budget")
    scale = receipt.get("modulate_scale")
    if not isinstance(budget, (int, float)) or not isinstance(scale, (int, float)):
        return {"budget": None, "scale": None, "ratio": None, "expected": None,
                "scale_agrees": False, "binding": False}
    if budget <= 0.0:
        return {"budget": 0.0, "scale": 0.0, "ratio": 0.0, "expected": 0.0,
                "scale_agrees": scale == 0.0, "binding": False}
    ratio = float(scale) / float(budget)
    expected = min(1.0, gain / float(budget))
    agrees = math.isclose(float(scale), min(float(budget), gain), rel_tol=1e-5, abs_tol=0.0)
    return {
        "budget": float(budget),
        "scale": float(scale),
        "ratio": ratio,
        "expected": expected,
        "scale_agrees": bool(agrees),
        "binding": ratio >= 0.99,
    }


def field_row_rms(receipt: dict[str, Any], field_width: int) -> float | None:
    """RMS of the field row the seam read, from the first decode's flux capture.

    The seam reads the newest token's flux block, which the harness dumps for the
    same decode as `qi-flux-0.f32`; the row is the block's first `field_width`
    entries.  `budget * field_row_rms` is therefore the row RMS the seam measured,
    and it is reported so the two readings can be checked against each other.
    """
    paths = aim.flux_capture_paths(receipt)
    if not paths:
        return None
    values = np.fromfile(paths[0], dtype=np.float32).astype(np.float64)
    if values.size < field_width:
        return None
    row = values[:field_width]
    return float(np.sqrt(np.mean(row * row)))


def run_ladder(args: argparse.Namespace, state: Path, gains: tuple[float, ...],
               tag: str) -> list[dict[str, Any]]:
    label = state_label(state)
    arms: list[dict[str, Any]] = []
    for gain in gains:
        name = f"{tag}-{gain_name(gain)}"
        receipt = aim.run_modulate_arm(args, name, state, gain, False)
        if int(receipt.get("steps", 0)) != args.steps:
            raise RuntimeError(f"{name}: coupling steps did not reach the harness")
        summary = aim.arm_summary(
            receipt, name, gain, False,
            args._off_final, args._off_decode, args._off_layers,
        )
        ratio = seam_ratio(receipt, gain)
        width = int(receipt.get("state_field_width") or 0)
        field_rms = field_row_rms(receipt, width) if width > 0 else None
        summary.update({
            "state": str(state),
            "state_label": label,
            "modulate_gain": gain,
            "modulate_budget": ratio["budget"],
            "modulate_scale": ratio["scale"],
            "added_row_ratio": ratio["ratio"],
            "added_row_ratio_expected": ratio["expected"],
            "scale_agrees": ratio["scale_agrees"],
            "binding": ratio["binding"],
            "field_row_rms": field_rms,
            "row_rms_inferred": (
                None if field_rms is None or ratio["budget"] is None
                else float(ratio["budget"]) * field_rms
            ),
            "prefill_logits_identical_to_off": summary["logits_relative_delta"] == 0.0,
            "generation_text": receipt.get("generation_text", ""),
            "state_after_fnv1a": receipt.get("state_after_fnv1a"),
            "state_max_abs_delta": receipt.get("state_max_abs_delta"),
            "modulate_gain_requested": gain,
        })
        arms.append(summary)
        print(
            f"  {name:<26} budget={ratio['budget']!s:>10.5} scale={ratio['scale']!s:>10.5} "
            f"ratio={ratio['ratio']!s:>7.5} dec={summary['decode_mean_relative_delta']:.6f} "
            f"flips={summary['top1_flips']}/{summary['top1_compared_decodes']}",
            flush=True,
        )
    return arms


def louder_fixture(state: Path, factor: float, tag: str, out_root: Path) -> Path:
    """A fixture whose field is `factor` times louder, so the cap binds below the gain cap."""
    values = np.fromfile(state, dtype=np.float32).astype(np.float64)
    louder = (values * factor).astype(np.float32)
    if not np.isfinite(louder).all():
        raise RuntimeError(f"louder fixture is not finite: {state} x{factor}")
    target = out_root / f"loud-{tag}.f32"
    louder.tofile(target)
    print(f"  built louder fixture {target} (x{factor:g})", flush=True)
    return target


def legacy_arms() -> list[dict[str, Any]]:
    """The gain-100 arms already on disk, which is the historical mutation control."""
    found: list[dict[str, Any]] = []
    for path in LEGACY_PROFILES:
        if not path.is_file():
            continue
        profile = json.loads(path.read_text(encoding="utf-8"))
        for arm in profile.get("arms", []):
            if arm.get("arm") != "mod-gain-100":
                continue
            found.append({
                "profile": str(path),
                "binary_sha256": profile.get("binary_sha256"),
                "state_sha256": profile.get("state_sha256"),
                "modulate_gain": arm.get("modulate_gain"),
                "logits_relative_delta": arm.get("logits_relative_delta"),
                "decode_mean_relative_delta": arm.get("decode_mean_relative_delta"),
                "decode_first_nonzero_index": arm.get("decode_first_nonzero_index"),
                "top1_flips": arm.get("top1_flips"),
            })
    return found


def binding_profile(args: argparse.Namespace) -> dict[str, Any]:
    args.out.mkdir(parents=True, exist_ok=True)
    off = aim.run_arm(args, "off", 0, "energy", 0.0)
    off_final = aim.capture_path(off, "logits.f32")
    if off_final is None:
        raise RuntimeError("field-off arm produced no logits.f32")
    args._off_final = aim.load_f32(off_final)
    args._off_decode = {
        index: aim.load_f32(path)
        for index, path in aim.capture_paths(
            off, re.compile(r"decode-logits-(\d+)\.f32")
        ).items()
    }
    args._off_layers = aim.layer_paths(off)

    states = [Path(entry) for entry in args.states if entry]
    fixtures: list[dict[str, Any]] = []
    arms: list[dict[str, Any]] = []
    for state in states:
        tag = state_label(state)
        print(f"== fixture {state}", flush=True)
        rungs = run_ladder(args, state, tuple(args.gains), tag)
        fixtures.append({"path": str(state), "tag": tag, "built": False,
                         "arms": [arm["arm"] for arm in rungs]})
        arms.extend(rungs)
        # A fixture whose quietest field needs more than the gain cap cannot bind:
        # build a louder one instead of calling the measurement impossible.
        needed = max(
            (arm["modulate_budget"] or 0.0) for arm in rungs
        ) / GAIN_CAP
        if needed > 1.0:
            factor = needed * 1.0e3
            louder = louder_fixture(state, factor, tag, args.out)
            fixtures.append({"path": str(louder), "tag": f"loud-{tag}", "built": True,
                             "source": str(state), "factor": factor, "arms": []})
            extra = run_ladder(args, louder, tuple(args.gains), f"loud-{tag}")
            fixtures[-1]["arms"] = [arm["arm"] for arm in extra]
            arms.extend(extra)

    receipt_out = {
        "schema": "cassi.field-modulation-binding.v1",
        "model": str(args.model),
        "model_sha256": aim.sha256(args.model),
        "binary": str(args.binary),
        "binary_sha256": aim.sha256(args.binary),
        "backend": args.backend,
        "layer": args.layer,
        "steps": args.steps,
        "alpha": args.alpha,
        "generate_tokens": args.generate_tokens,
        "prompt": aim.PROMPT,
        "gain_cap": GAIN_CAP,
        "gains": list(args.gains),
        "fixtures": fixtures,
        "off_reference": {
            "logits_absmax": float(np.max(np.abs(args._off_final))),
            "decode_logits_captured": sorted(args._off_decode),
        },
        "legacy_gain_100": legacy_arms(),
        "arms": arms,
    }
    aim.atomic_json(args.out / "binding.json", receipt_out)
    return receipt_out


def print_table(result: dict[str, Any]) -> None:
    print()
    print(f"{'arm':<26} {'budget':>10} {'scale':>10} {'ratio':>8} {'exp':>8} "
          f"{'dec_mean':>10} {'first':>6} {'flips':>6}")
    for arm in result["arms"]:
        print(
            f"{arm['arm']:<26} {_num(arm['modulate_budget']):>10} {_num(arm['modulate_scale']):>10} "
            f"{_num(arm['added_row_ratio']):>8} {_num(arm['added_row_ratio_expected']):>8} "
            f"{arm['decode_mean_relative_delta']:>10.6f} "
            f"{str(arm['decode_first_nonzero_index']):>6} "
            f"{arm['top1_flips']:>6}"
        )
    print()
    print("legacy gain-100 arms already on disk:")
    for arm in result["legacy_gain_100"]:
        print(
            f"  {Path(arm['profile']).parent.name:<34} binary={arm['binary_sha256'][:8]} "
            f"dec_mean={arm['decode_mean_relative_delta']:.6f}"
        )


def _num(value: Any) -> str:
    if value is None:
        return "-"
    return f"{float(value):.6g}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, default=aim.LATENT_BINARY)
    parser.add_argument("--model", type=Path, default=aim.DEFAULT_MODEL)
    parser.add_argument("--backend", default="gpu")
    parser.add_argument("--layer", type=int, default=32)
    parser.add_argument("--steps", type=int, default=4)
    parser.add_argument("--alpha", type=float, default=0.01)
    parser.add_argument("--generate-tokens", type=int, default=12)
    parser.add_argument("--timeout", type=float, default=1800.0)
    parser.add_argument(
        "--states", default=",".join(str(path) for path in DEFAULT_STATES),
        help="comma-separated Qi state fixtures; each becomes one gain ladder",
    )
    parser.add_argument(
        "--gains", default=",".join(repr(gain) for gain in LADDER),
        help="comma-separated gains; the whole ladder runs on every fixture",
    )
    parser.add_argument(
        "--out", type=Path,
        default=ROOT / "native/llama.cpp/_diag/aim-binding-gain",
    )
    args = parser.parse_args()
    args.state = Path(args.states.split(",")[0])
    args.gains = [float(entry) for entry in args.gains.split(",") if entry.strip()]
    args.states = [entry.strip() for entry in args.states.split(",") if entry.strip()]
    if not args.gains or any(not math.isfinite(gain) or gain < 0.0 for gain in args.gains):
        raise RuntimeError("every gain must be finite and non-negative")
    if any(gain > GAIN_CAP for gain in args.gains):
        raise RuntimeError(f"the harness caps --modulate-gain at {GAIN_CAP}")
    for path in (args.binary, args.model, *(Path(entry) for entry in args.states)):
        if not path.is_file():
            raise RuntimeError(f"required file is missing: {path}")
    result = binding_profile(args)
    print_table(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
