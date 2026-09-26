#!/usr/bin/env python3
"""Compare the displacement vectors, not only their sizes.

A stable relative displacement can hide a changing direction: a write that
carries one aggregate direction and a write that carries content both move the
logits by a similar amount.  This reads a profile receipt's captures and
reports, per decode index, how far each arm moved the logits and how the arms'
displacement vectors line up with one another.  Cosines near 1 across arms whose
field composition differs by orders of magnitude mean the model consumes one
aggregate direction; lower cosines mean the composition is visible in the
motion, which the scalar summary could not show.

The position half of the aiming question comes from the same reads: the
displacement at each decode index says where in the generated window the write
still has effect.
"""

from __future__ import annotations

import argparse
import itertools
import json
import pathlib
import re
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import run_field_aim_profile as aim  # noqa: E402


def decode_captures(profile_dir: pathlib.Path, arm: str) -> dict[int, np.ndarray]:
    captures: dict[int, np.ndarray] = {}
    for path in (profile_dir / arm / "captures").glob("decode-logits-*.f32"):
        index = int(re.search(r"decode-logits-(\d+)", path.name).group(1))
        captures[index] = aim.load_f32(path)
    return captures


def cosine(left: np.ndarray, right: np.ndarray) -> float:
    denominator = float(np.linalg.norm(left)) * float(np.linalg.norm(right))
    if denominator == 0.0:
        return 1.0
    return float(np.dot(left, right) / denominator)


def analyze(profile_dir: pathlib.Path, arms: list[str] | None = None, lesion: str | None = None) -> dict:
    """Displacements, optionally measured against a lesion arm instead of off.

    The seam suppresses the model's own recurrent-state write before filling the
    window, so a field-off reference measures the suppression and the field
    together.  Passing the arm whose readout is zeroed (`--read-floor 2.0`)
    removes the suppression, leaving the field's own contribution.
    """
    profile = json.loads((profile_dir / "profile.json").read_text(encoding="utf-8"))
    names = arms or [arm["arm"] for arm in profile["arms"]]
    reference = decode_captures(profile_dir, lesion or "off")
    deltas: dict[str, dict[int, np.ndarray]] = {}
    for name in names:
        captures = decode_captures(profile_dir, name)
        deltas[name] = {
            index: captures[index] - reference[index]
            for index in sorted(set(captures) & set(reference))
        }
    indices = sorted(set.intersection(*(set(d) for d in deltas.values()))) if deltas else []
    position: dict[str, dict[str, float]] = {}
    for name in names:
        position[name] = {
            str(index): float(np.linalg.norm(deltas[name][index]) / np.linalg.norm(reference[index]))
            for index in indices
            if np.linalg.norm(reference[index]) > 0
        }
    alignment: dict[str, dict[str, float]] = {}
    for left, right in itertools.combinations(names, 2):
        per_index = {
            str(index): cosine(deltas[left][index], deltas[right][index])
            for index in indices
        }
        alignment[f"{left} vs {right}"] = {
            "cosine_min": min(per_index.values()),
            "cosine_mean": float(np.mean(list(per_index.values()))),
            "cosine_per_index": per_index,
        }
    return {
        "profile": str(profile_dir),
        "knob": profile["knob"],
        "lesion_reference": lesion,
        "knob_values": {arm["arm"]: arm["knob_value"] for arm in profile["arms"]},
        "decode_indices": indices,
        "position_relative_delta": position,
        "alignment": alignment,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=pathlib.Path)
    parser.add_argument("--arms", default="")
    parser.add_argument("--lesion", default=None)
    parser.add_argument("--out", type=pathlib.Path, default=None)
    args = parser.parse_args()
    names = [name.strip() for name in args.arms.split(",") if name.strip()]
    result = analyze(args.profile, names or None, args.lesion or None)
    if args.out is not None:
        args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"knob: {result['knob']}  lesion reference: {result['lesion_reference'] or 'off (field disabled)'}"
          f"  decode indices: {result['decode_indices']}")
    print("\nposition relative delta (decode index -> |delta| / |reference|)")
    for name, row in result["position_relative_delta"].items():
        print(f"  {name:16s} " + " ".join(f"{value:.5f}" for value in row.values()))
    print("\ndelta alignment between arms")
    for name, row in result["alignment"].items():
        print(f"  {name:34s} cosine mean {row['cosine_mean']:.6f}  min {row['cosine_min']:.6f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
