#!/usr/bin/env python3
"""Which field modes carry the coupling into the model?

`read_floor` gates the seam's readout: the field writes a mode to the model's
channel vector only when the mode's gate reaches the floor (ops.cpp:
`read_gate >= read_floor`, and the same test on the final-scale branch).  So the
floor chooses how much of the field is legible to the model, and the profile of
that choice is measurable.

Arms:

  off          the field is disabled (STEPS 0); the reference every arm is
               differenced against.
  lesion       the same intervention with the readout gated to zero
               (`--read-floor 2.0`, above the gate's ceiling).  The seam
               suppresses the model's own recurrent-state write before filling
               it, so `off` measures that suppression and the field together;
               `lesion` is the baseline the field's own contribution is read
               against.  It carries the profile's own `--read-absolute` state,
               so a flag-on profile gets a flag-on baseline.
  read_<f>     one floor in the ladder.  Only the floor changes.

A rung is `(name, value)` or `(name, value, read_absolute)`: the third element
passes the boolean `--read-absolute` beside the knob's own flag, which is how a
floor ladder is run with the field read at its own magnitude.  A knob whose flag
takes no value is listed in VALUELESS_KNOBS, and then the rung's value only
decides whether the flag is passed at all.

Each arm records the field's own flux distribution beside the model's per-decode
logit displacement, so "how many modes were admitted" and "what the model
received" are both read from the receipt rather than inferred from the other.

A second mode answers a narrower question.  The knob mode measures a seam that
replaces the model's own recurrent-state write.  `--modulate-states` measures the
modulation seam instead, which keeps that write and adds a bounded field term to
it, so the arm's reference is the plain field-off arm and not a lesion:

  mod_<state>  one wave-support state with the field read at unit amplitude.
  mod_<state>-abs  the same state with `--read-absolute`, so the field is read
               at its own magnitude.
  mod-gain-<g> one extra gain on the first state, which shows the cap.

`--modulate-gain` is the arm's steering coefficient, and the arms above all use
it unless the name says otherwise.  The analyzer reads both modes unchanged,
because both write the same receipt keys.

The run is refused when an arm directory already exists: a profile that mixes
receipts from two runs is not a profile.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
LATENT_BINARY = ROOT / "native/llama.cpp/b8/bin/Release/test-cassi-qi-latent.exe"
DEFAULT_MODEL = ROOT / "Qwen3.8-27B-Q4_K_M.gguf"
DEFAULT_STATE = ROOT / "native/llama.cpp/_diag/s-1.0.f32"

# The ladders name the two selection knobs the seam exposes.  Each value is
# paired with the arm name it produces.
#
# `read_floor` gates one mode's readout (`read_gate >= read_floor`), and a run
# over 0.02..0.40 changed nothing in the model, so its gate saturates over that
# range.  `energy_floor` compares a mode's own energy (`rho > energy_floor`), a
# quantity with no unit ceiling, so it is the knob that can actually select how
# much of the field is legible.
#
# A requested value of 0 does not mean "no floor": the harness leaves the
# compiled default in place (read 0.05, energy 1e-6), so those arms are named
# `*_default`.
KnobRung = tuple[str, float] | tuple[str, float, bool]
ENERGY_FLOORS: tuple[KnobRung, ...] = (
    ("energy_default", 0.0),
    ("energy_1e-8", 1.0e-8),
    ("energy_1e-7", 1.0e-7),
    ("energy_1e-5", 1.0e-5),
    ("energy_1e-4", 1.0e-4),
    ("energy_1e-3", 1.0e-3),
)
LADDERS: dict[str, tuple[KnobRung, ...]] = {
    "read": (
        ("read_default", 0.0),
        ("read_0p02", 0.02),
        ("read_0p10", 0.10),
        ("read_0p20", 0.20),
        ("read_0p40", 0.40),
    ),
    "energy": ENERGY_FLOORS,
    # The wiring ladder asks whether a floor reaches the op at all.  The gate
    # is `read_gate >= read_floor` with read_gate clamped to [0, 1], so a floor
    # of 1.0 still admits a saturated mode and proves nothing; 2.0 is above the
    # ceiling and must gate every mode out, which has to erase the effect.  If
    # it survives 2.0, the value never reached this path.
    "wiring": (
        ("wiring_default", 0.0),
        ("wiring_0p5", 0.5),
        ("wiring_2p0", 2.0),
    ),
    # The energy ladder with the field read at its own magnitude: every rung
    # passes the boolean `--read-absolute` (no value) beside its floor, so
    # differencing a rung here against the same floor in `energy` isolates the
    # flag at that admission level.
    "energy-absolute": tuple(
        (f"abs_{name}", value, True) for name, value in ENERGY_FLOORS
    ),
    # The valueless knob on its own, at the compiled floors: the off rung
    # passes no flag at all and must reproduce `energy_default`, the on rung
    # passes `--read-absolute` alone.  That pair is the flag's wiring check and
    # the shipped-default contrast.
    "absolute": (("abs_off", 0.0), ("abs_on", 1.0)),
}
KNOB_FLAG = {
    "read": "--read-floor",
    "energy": "--energy-floor",
    "energy-absolute": "--energy-floor",
    "wiring": "--read-floor",
    "absolute": "--read-absolute",
}
# Knobs whose flag is a boolean: it is appended alone, and the rung's value only
# says whether it is passed.
VALUELESS_KNOBS = frozenset({"absolute"})
LESION = ("lesion", "wiring", 2.0)
PROMPT = (
    "Explain in two sentences why a field that carries its own intensity "
    "differs from one normalized to a fixed amplitude.\n"
)
PROFILE_LAYERS = (32, 34, 40, 48, 56, 63)


def sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    payload = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, path)


def load_f32(path: Path) -> np.ndarray:
    values = np.fromfile(path, dtype=np.float32)
    if values.size == 0 or not np.isfinite(values).all():
        raise RuntimeError(f"invalid F32 capture: {path}")
    return values.astype(np.float64)


def parse_receipt(stdout: str) -> dict[str, Any]:
    marker = "{\"schema\":\"cassi.qi.latent.v1\""
    start = stdout.rfind(marker)
    if start < 0:
        raise RuntimeError("latent harness emitted no cassi.qi.latent.v1 receipt")
    value, _ = json.JSONDecoder().raw_decode(stdout[start:])
    return value


def relative_delta(reference: np.ndarray, candidate: np.ndarray) -> float:
    if reference.shape != candidate.shape:
        raise RuntimeError("capture shapes differ")
    denominator = float(np.linalg.norm(reference))
    if denominator == 0.0:
        return 0.0
    return float(np.linalg.norm(candidate - reference)) / denominator


def capture_path(receipt: dict[str, Any], name: str) -> Path | None:
    for item in receipt.get("capture_files", []):
        if item.get("name") == name and item.get("path"):
            return Path(item["path"])
    return None


def capture_paths(receipt: dict[str, Any], pattern: re.Pattern[str]) -> dict[int, Path]:
    found: dict[int, Path] = {}
    for item in receipt.get("capture_files", []):
        name = str(item.get("name", ""))
        match = pattern.fullmatch(name)
        if match and item.get("path"):
            found[int(match.group(1))] = Path(item["path"])
    return found


def flux_capture_paths(receipt: dict[str, Any]) -> list[Path]:
    """Flux captures, which the harness lists under their own receipt key.

    One file holds one decode's readout, laid out as interleaved
    real/imaginary pairs, so a file describes every field mode the model could
    have read at that step.
    """
    directory = receipt.get("capture_output_dir")
    names = receipt.get("qi_flux_files") or []
    if not directory or not isinstance(names, list):
        return []
    return [Path(directory) / str(name) for name in names]


def flux_profile(
    paths: list[Path], thresholds: tuple[float, ...]
) -> dict[str, Any] | None:
    """Per-mode readout magnitude, averaged over the decoded steps.

    A mode's magnitude is the length of its real/imaginary pair.  The summary
    answers which modes carry the readout: how concentrated it is, and how many
    modes clear a given magnitude.
    """
    if not paths:
        return None
    captures = [load_f32(path) for path in paths]
    width = captures[0].size
    for capture in captures:
        if capture.size != width or width % 2:
            raise RuntimeError("flux captures disagree or are not real/imaginary pairs")
    stacked = np.stack([capture.reshape(-1, 2) for capture in captures])
    magnitude = np.sqrt(np.sum(np.square(stacked), axis=2))
    per_mode = magnitude.mean(axis=0)
    total = float(per_mode.sum())
    order = np.argsort(per_mode)[::-1]
    ranked = np.cumsum(per_mode[order]) / total if total > 0 else per_mode[order]
    return {
        "captures": len(captures),
        "modes": int(per_mode.size),
        "absmax": float(magnitude.max()),
        "rms": float(np.sqrt(np.mean(np.square(magnitude)))),
        "per_mode_mean_absmax": float(per_mode.max()),
        "per_mode_mean_rms": float(np.sqrt(np.mean(np.square(per_mode)))),
        "zero_modes": int(np.count_nonzero(per_mode == 0.0)),
        "mass_fraction_top_10": float(ranked[9]) if per_mode.size >= 10 else None,
        "mass_fraction_top_100": float(ranked[99]) if per_mode.size >= 100 else None,
        "modes_for_90pct_mass": int(np.searchsorted(ranked, 0.90) + 1),
        "top_mode_indices": [int(index) for index in order[:10]],
        "counts_above": {
            f"{threshold:g}": int(np.count_nonzero(per_mode >= threshold))
            for threshold in thresholds
        },
    }


def layer_paths(receipt: dict[str, Any]) -> dict[str, Path]:
    """Layer captures from the decode pass, never the prefill pass.

    A prefill capture is field-blind by construction (the seam writes only when
    one token is decoded), so it would read as a zero difference in every arm.
    The early-decode capture is the first decode of the generated-token window,
    which every arm reaches with the same tokens, so it is the controlled one.
    """
    preference = ("layer-%d-decode-early.f32", "layer-%d-decode.f32")
    found: dict[str, Path] = {}
    for pattern in preference:
        for item in receipt.get("captured_layers", []):
            path = item.get("path")
            if not path:
                continue
            key = str(item["layer"])
            if key in found:
                continue
            if Path(path).name == pattern % int(item["layer"]):
                found[key] = Path(path)
    return found


def decode_layers(receipt: dict[str, Any], layer: int) -> dict[int, Path]:
    found: dict[int, Path] = {}
    for item in receipt.get("captured_layers", []):
        if int(item["layer"]) != layer or not item.get("path"):
            continue
        match = re.fullmatch(r"layer-\d+-decode(?:-early)?\.f32", Path(item["path"]).name)
        if match:
            found[len(found)] = Path(item["path"])
    return found


def knob_arguments(knob: str, value: float, read_absolute: bool) -> list[str]:
    """The selection flags one rung passes, in order.

    A valueless knob's flag is appended alone, because the harness parses
    `--read-absolute` without an argument; a valued knob's flag is followed by
    its value.  A rung whose `read_absolute` is set adds that boolean flag
    beside the knob's own, which is how a floor ladder is run with the field
    read at its own magnitude; for a valueless knob the rung's value *is* that
    request.  Either way the flag is passed once.
    """
    valueless = knob in VALUELESS_KNOBS
    arguments = ["--read-absolute"] if read_absolute or (valueless and value > 0.0) else []
    if not valueless and value > 0.0:
        arguments.extend([KNOB_FLAG[knob], repr(value)])
    return arguments


def run_arm(
    args: argparse.Namespace,
    name: str,
    steps: int,
    knob: str,
    value: float,
    read_absolute: bool | None = None,
) -> dict[str, Any]:
    """Run one arm.  `read_absolute` defaults to the namespace's own flag."""
    arm_dir = args.out / name
    if arm_dir.exists():
        raise RuntimeError(f"arm directory already exists (refusing to mix runs): {arm_dir}")
    arm_dir.mkdir(parents=True)
    prompt_path = arm_dir / "prompt.txt"
    prompt_path.write_text(PROMPT, encoding="utf-8")
    if read_absolute is None:
        read_absolute = bool(getattr(args, "read_absolute", False))
    command = [
        str(args.binary),
        str(args.model),
        str(args.state),
        args.backend,
        str(prompt_path),
        str(args.layer),
        str(steps),
        str(args.alpha),
        str(args.generate_tokens),
        str(arm_dir / "captures"),
        "0",
        "0",
    ]
    if steps > 0:
        command.extend([
            "--substitute", "1.0",
            "--displacement", "3",
            "--flux-dump",
        ])
        command.extend(knob_arguments(knob, value, read_absolute))
    started = time.perf_counter()
    process = subprocess.run(
        command, text=True, encoding="utf-8", errors="replace",
        capture_output=True, timeout=args.timeout,
    )
    wall_seconds = time.perf_counter() - started
    (arm_dir / "stdout.log").write_text(process.stdout, encoding="utf-8")
    (arm_dir / "stderr.log").write_text(process.stderr, encoding="utf-8")
    if process.returncode != 0:
        raise RuntimeError(f"{name} failed with {process.returncode}; see {arm_dir}")
    receipt = parse_receipt(process.stdout)
    receipt["process_wall_seconds"] = wall_seconds
    receipt["command"] = command
    atomic_json(arm_dir / "receipt.json", receipt)
    return receipt


def run_modulate_arm(
    args: argparse.Namespace,
    name: str,
    state_path: Path,
    gain: float,
    read_absolute: bool,
) -> dict[str, Any]:
    """One modulation arm: the intact write plus the field's bounded term.

    The model's own recurrent-state write stays in the seam, so the arm is
    differenced against the plain field-off arm and no lesion is needed.  A gain
    of 0 builds the same seam and adds nothing, which is the identity control.
    """
    arm_dir = args.out / name
    if arm_dir.exists():
        raise RuntimeError(f"arm directory already exists (refusing to mix runs): {arm_dir}")
    arm_dir.mkdir(parents=True)
    prompt_path = arm_dir / "prompt.txt"
    prompt_path.write_text(PROMPT, encoding="utf-8")
    command = [
        str(args.binary),
        str(args.model),
        str(state_path),
        args.backend,
        str(prompt_path),
        str(args.layer),
        str(args.steps),
        str(args.alpha),
        str(args.generate_tokens),
        str(arm_dir / "captures"),
        "0",
        "0",
        # The seam is the modulation one, so the displacement stays 0 and the
        # substitution share stays 0: nothing may suppress the write it reads.
        "--modulate",
        "--modulate-gain", repr(gain),
        "--flux-dump",
    ]
    if read_absolute:
        command.append("--read-absolute")
    started = time.perf_counter()
    process = subprocess.run(
        command, text=True, encoding="utf-8", errors="replace",
        capture_output=True, timeout=args.timeout,
    )
    wall_seconds = time.perf_counter() - started
    (arm_dir / "stdout.log").write_text(process.stdout, encoding="utf-8")
    (arm_dir / "stderr.log").write_text(process.stderr, encoding="utf-8")
    if process.returncode != 0:
        raise RuntimeError(f"{name} failed with {process.returncode}; see {arm_dir}")
    receipt = parse_receipt(process.stdout)
    if receipt.get("qi_modulate") is not True:
        raise RuntimeError(f"{name}: --modulate did not reach the harness")
    receipt["process_wall_seconds"] = wall_seconds
    receipt["command"] = command
    receipt["state"] = str(state_path)
    receipt["state_sha256"] = sha256(state_path)
    receipt["modulate_gain_requested"] = gain
    atomic_json(arm_dir / "receipt.json", receipt)
    return receipt


def modulate_arms(args: argparse.Namespace) -> list[tuple[str, Path, float, bool]]:
    """The (name, state, gain, read_absolute) of every requested arm.

    The first state also carries the gain ladder, because the cap is a property
    of the seam and not of a state.
    """
    arms: list[tuple[str, Path, float, bool]] = []
    for index, state_path in enumerate(args.modulate_states):
        name = state_path.stem
        arms.append((f"mod-{name}", state_path, args.modulate_gain, False))
        if args.modulate_absolute:
            arms.append((f"mod-{name}-abs", state_path, args.modulate_gain, True))
        if index == 0:
            for gain in args.modulate_gains:
                if gain == args.modulate_gain:
                    continue
                arms.append((f"mod-gain-{gain:g}", state_path, gain, False))
    return arms


def modulate_profile(args: argparse.Namespace) -> dict[str, Any]:
    """Run the modulation ladder against the plain field-off arm."""
    args.out.mkdir(parents=True, exist_ok=True)
    off = run_arm(args, "off", 0, args.knob, 0.0)
    off_final = capture_path(off, "logits.f32")
    if off_final is None:
        raise RuntimeError("field-off arm produced no logits.f32")
    off_final_values = load_f32(off_final)
    off_decode = capture_paths(off, re.compile(r"decode-logits-(\d+)\.f32"))
    off_decode_values = {index: load_f32(path) for index, path in off_decode.items()}
    off_layers = layer_paths(off)

    arms: list[dict[str, Any]] = []
    for name, state_path, gain, absolute in modulate_arms(args):
        receipt = run_modulate_arm(args, name, state_path, gain, absolute)
        assert receipt.get("steps") == args.steps, receipt.get("steps")
        summary = arm_summary(
            receipt, name, gain, absolute,
            off_final_values, off_decode_values, off_layers,
        )
        summary["state"] = str(state_path)
        summary["modulate_gain"] = gain
        arms.append(summary)

    receipt_out = {
        "schema": "cassi.field-aim-profile.v1",
        "model": str(args.model),
        "model_sha256": sha256(args.model),
        "state": str(args.state),
        "state_sha256": sha256(args.state),
        "binary": str(args.binary),
        "binary_sha256": sha256(args.binary),
        "backend": args.backend,
        "layer": args.layer,
        "steps": args.steps,
        "alpha": args.alpha,
        "generate_tokens": args.generate_tokens,
        "prompt": PROMPT,
        "knob": "modulate",
        "read_absolute": bool(args.modulate_absolute),
        "modulate": {
            "gain": args.modulate_gain,
            "gains": list(args.modulate_gains),
            "states": [str(path) for path in args.modulate_states],
        },
        "ladder": [
            {"arm": name, "state": str(state_path), "value": gain,
             "read_absolute": absolute}
            for name, state_path, gain, absolute in modulate_arms(args)
        ],
        "off_reference": {
            "logits_absmax": float(np.max(np.abs(off_final_values))),
            "decode_logits_captured": sorted(off_decode_values),
            "captured_layers": sorted(layer_paths(off), key=int),
        },
        "arms": arms,
    }
    atomic_json(args.out / "profile.json", receipt_out)
    return receipt_out


def arm_summary(
    receipt: dict[str, Any],
    name: str,
    knob_value: float,
    read_absolute: bool,
    off_final_values: np.ndarray,
    off_decode_values: dict[int, np.ndarray],
    off_layers: dict[str, Path],
) -> dict[str, Any]:
    """One arm's model-side summary, always differenced against `off`."""
    final_path = capture_path(receipt, "logits.f32")
    if final_path is None:
        raise RuntimeError(f"{name} produced no logits.f32")
    final_values = load_f32(final_path)
    decode_values = {
        index: load_f32(path)
        for index, path in capture_paths(receipt, re.compile(r"decode-logits-(\d+)\.f32")).items()
    }
    per_index: dict[str, float] = {}
    flips = 0
    compared = 0
    for index in sorted(set(decode_values) & set(off_decode_values)):
        if index < 1:
            continue
        candidate = decode_values[index]
        reference = off_decode_values[index]
        per_index[str(index)] = relative_delta(reference, candidate)
        if candidate.size == reference.size:
            compared += 1
            flips += int(int(np.argmax(candidate)) != int(np.argmax(reference)))
    layer_profile: dict[str, float] = {}
    arm_layers = layer_paths(receipt)
    for layer in PROFILE_LAYERS:
        key = str(layer)
        if key in off_layers and key in arm_layers:
            layer_profile[key] = relative_delta(
                load_f32(off_layers[key]), load_f32(arm_layers[key])
            )
    return {
        "arm": name,
        "knob_value": knob_value,
        "read_absolute": read_absolute,
        "steps": int(receipt["steps"]),
        "intervention": receipt.get("intervention"),
        "read_floor_effective": receipt.get("qi_read_floor"),
        "energy_floor_effective": receipt.get("qi_energy_floor"),
        "read_absolute_effective": receipt.get("qi_read_absolute"),
        "state_field_width": receipt.get("state_field_width"),
        "graph_nodes_after_coupling": receipt.get("graph_nodes_after_coupling"),
        "wall_seconds": receipt["process_wall_seconds"],
        "logits_relative_delta": relative_delta(off_final_values, final_values),
        "decode_relative_delta": per_index,
        "decode_mean_relative_delta": (
            float(np.mean(list(per_index.values()))) if per_index else 0.0
        ),
        "decode_first_nonzero_index": next(
            (int(index) for index, value in sorted(
                ((int(k), v) for k, v in per_index.items()), key=lambda item: item[0]
            ) if value > 0.0), None
        ),
        "top1_flips": flips,
        "top1_compared_decodes": compared,
        "layer_relative_delta": layer_profile,
        "flux": flux_profile(
            flux_capture_paths(receipt), (1.0e-6, 1.0e-4, 1.0e-2, 1.0e-1)
        ),
    }


def profile(args: argparse.Namespace) -> dict[str, Any]:
    args.out.mkdir(parents=True, exist_ok=True)
    off = run_arm(args, "off", 0, args.knob, 0.0)
    off_final = capture_path(off, "logits.f32")
    if off_final is None:
        raise RuntimeError("field-off arm produced no logits.f32")
    off_final_values = load_f32(off_final)
    off_decode = capture_paths(off, re.compile(r"decode-logits-(\d+)\.f32"))
    off_decode_values = {index: load_f32(path) for index, path in off_decode.items()}
    off_layers = layer_paths(off)

    ladder = LADDERS[args.knob]
    rungs = []
    for entry in ladder:
        name, value = entry[0], entry[1]
        absolute = entry[2] if len(entry) > 2 else False
        rungs.append((name, value, absolute, knob_arguments(args.knob, value, absolute)))
    # The baseline follows the profile's flag state: a flag-on ladder is
    # referenced against a flag-on lesion, so the only difference left is the
    # readout the gate admitted.
    lesion_absolute = bool(getattr(args, "read_absolute", False)) or any(
        "--read-absolute" in arguments for _n, _v, _a, arguments in rungs
    )
    lesion_name, lesion_knob, lesion_value = LESION
    lesion_receipt = run_arm(
        args, lesion_name, args.steps, lesion_knob, lesion_value, lesion_absolute
    )
    lesion = arm_summary(
        lesion_receipt, lesion_name, lesion_value, lesion_absolute,
        off_final_values, off_decode_values, off_layers,
    )

    arms: list[dict[str, Any]] = []
    for name, value, absolute, arguments in rungs:
        receipt = run_arm(args, name, args.steps, args.knob, value, absolute)
        assert receipt.get("qi_enabled") is True, receipt.get("qi_enabled")
        assert bool(receipt.get("qi_read_absolute")) is ("--read-absolute" in arguments), (
            f"{name}: --read-absolute did not reach the harness",
            receipt.get("qi_read_absolute"),
            arguments,
        )
        arms.append(arm_summary(
            receipt, name, value, "--read-absolute" in arguments,
            off_final_values, off_decode_values, off_layers,
        ))
    receipt_out = {
        "schema": "cassi.field-aim-profile.v1",
        "model": str(args.model),
        "model_sha256": sha256(args.model),
        "state": str(args.state),
        "state_sha256": sha256(args.state),
        "binary": str(args.binary),
        "binary_sha256": sha256(args.binary),
        "backend": args.backend,
        "layer": args.layer,
        "steps": args.steps,
        "alpha": args.alpha,
        "generate_tokens": args.generate_tokens,
        "prompt": PROMPT,
        "knob": args.knob,
        "read_absolute": bool(getattr(args, "read_absolute", False)),
        "ladder": [
            {"arm": name, "value": value, "read_absolute": "--read-absolute" in arguments,
             "flags": arguments}
            for name, value, _absolute, arguments in rungs
        ],
        "lesion": lesion,
        "off_reference": {
            "logits_absmax": float(np.max(np.abs(off_final_values))),
            "decode_logits_captured": sorted(off_decode_values),
            "captured_layers": sorted(layer_paths(off), key=int),
        },
        "arms": arms,
    }
    atomic_json(args.out / "profile.json", receipt_out)
    return receipt_out


def arm_row(arm: dict[str, Any]) -> dict[str, Any]:
    return {
        "arm": arm["arm"],
        "read_absolute_effective": arm["read_absolute_effective"],
        "read_floor_effective": arm["read_floor_effective"],
        "energy_floor_effective": arm["energy_floor_effective"],
        "logits_relative_delta": round(arm["logits_relative_delta"], 6),
        "decode_mean": round(arm["decode_mean_relative_delta"], 6),
        "top1_flips": arm["top1_flips"],
        "mode_absmax": arm["flux"]["per_mode_mean_absmax"] if arm["flux"] else None,
        "modes_90pct_mass": arm["flux"]["modes_for_90pct_mass"] if arm["flux"] else None,
        "mass_top_100": (
            round(arm["flux"]["mass_fraction_top_100"], 4) if arm["flux"] else None
        ),
        "flux_counts_above": arm["flux"]["counts_above"] if arm["flux"] else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, default=LATENT_BINARY)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--backend", default="gpu")
    parser.add_argument("--layer", type=int, default=32)
    parser.add_argument("--steps", type=int, default=4)
    parser.add_argument("--alpha", type=float, default=0.01)
    parser.add_argument("--generate-tokens", type=int, default=12)
    parser.add_argument("--timeout", type=float, default=1800.0)
    parser.add_argument("--knob", choices=sorted(LADDERS), default="energy")
    parser.add_argument("--read-absolute", action="store_true")
    parser.add_argument(
        "--modulate-states", default="",
        help="comma-separated Qi state files; each one becomes a modulation arm",
    )
    parser.add_argument("--modulate-gain", type=float, default=1.0)
    parser.add_argument(
        "--modulate-absolute", action="store_true",
        help="also run every modulation state with --read-absolute",
    )
    parser.add_argument(
        "--modulate-gains", default="",
        help="comma-separated extra gains on the first modulation state",
    )
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    args.modulate_states = [
        Path(entry.strip()) for entry in args.modulate_states.split(",") if entry.strip()
    ]
    args.modulate_gains = [
        float(entry) for entry in args.modulate_gains.split(",") if entry.strip()
    ]
    if args.modulate_gain < 0.0:
        raise RuntimeError("--modulate-gain must be non-negative")
    if any(gain < 0.0 for gain in args.modulate_gains):
        raise RuntimeError("--modulate-gains entries must be non-negative")
    modulate_mode = bool(args.modulate_states)
    if args.out is None:
        suffix = "modulate" if modulate_mode else args.knob
        args.out = ROOT / f"native/llama.cpp/_diag/aim-profile-{suffix}"
    for path in (args.binary, args.model, args.state, *args.modulate_states):
        if not path.is_file():
            raise RuntimeError(f"required file is missing: {path}")
    result = modulate_profile(args) if modulate_mode else profile(args)
    print(json.dumps({
        "schema": result["schema"],
        "knob": result["knob"],
        "state": result["state"],
        # The modulation mode has no lesion arm: its seam keeps the model write,
        # so the field-off arm is already the baseline the field is read against.
        "lesion": arm_row(result["lesion"]) if "lesion" in result else None,
        "arms": [arm_row(arm) for arm in result["arms"]],
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
