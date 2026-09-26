"""Does the field own the recurrent-state write that the displacement suppresses?

`--cassi-qi-displacement 3` removes the recurrent-state write at the Qi layer:
the layer keeps the state it held, so the model's own history stops advancing
there. `--cassi-qi-substitute F` fills that same write from the field's readout
of the layer's input, blended by `F` against the window the model would have
written. The write is the layer's SSM `qkv` convolution state, so the blend is
positional: the field addresses the leading `n_embd` channels by index, without a
learned projection. At `F` above zero the field runs at the Qi layer with the
additive injection left out, so the state write is its only channel there.

Arms (one harness run each, greedy, fixed prompt, no additive injection):

  no_field            Qi off; the plain model stream
  write_intact        displacement 0; the unlesioned graph
  lesion              displacement 3, substitute 0; the suppression alone
  relocated           displacement 3, substitute 1e-6; the blend is inert
  seam_half           displacement 3, substitute 0.5
  seam_full           displacement 3, substitute 1.0
  seam_full_shuffled  as seam_full, with a matched-norm phase shuffle after the
                      prompt; the field-content control

Every arm runs intervention zero, so the suppression gate compares runs with the
same injection placement, and `seam_full` against `relocated` isolates the seam:
those two differ only in the blend, so an identical stream means the seam does
not reach the computation. The seam's reach is read from the first decode that
reads its write with the same input tokens in every arm; the last decode's
captures are reported beside it and carry the drift the seam then caused. A guard
run checks that the binary refuses a substitution aimed at a configuration that
suppresses nothing. Every arm's receipt echoes the `displacement` and
`substitute` it ran with, so a silently dropped flag shows up as identical arms
instead of as a pass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import run_cassi_latent_reasoning as latent  # noqa: E402

FIELD_STEPS = 4
# The probe runs the field with no additive injection, so the seam is the only
# channel the field has at the layer and a dose difference is the seam's alone.
FIELD_ALPHA = 0.0
GENERATE_TOKENS = 200
PROMPT = (
    "A lighthouse keeper writes in the log that the fog lifted at dawn, that the "
    "gulls returned to the rocks, and that the lamp needed no oil. The next entry "
    "begins:"
)

# Arms that differ only in the blend. Their field share is the one variable.
RELOCATION_FAMILY: tuple[str, ...] = ("relocated", "seam_half", "seam_full")
# The shuffle runs after the prompt decode, so these arms still share prompt captures.
PROMPT_IDENTITY_FAMILY: tuple[str, ...] = RELOCATION_FAMILY + ("seam_full_shuffled",)

# The suppression gate compares arms that share an injection placement, so every arm
# runs intervention 0. The seam arms then differ from the lesion only by the seam.
INTERVENTION = 0

# name, Qi steps, displacement, substitute, phase shuffle after prompt
ARM_SPECS: tuple[tuple[str, int, int, float, bool], ...] = (
    ("no_field", 0, 0, 0.0, False),
    ("write_intact", FIELD_STEPS, 0, 0.0, False),
    ("lesion", FIELD_STEPS, 3, 0.0, False),
    ("relocated", FIELD_STEPS, 3, 1.0e-6, False),
    ("seam_half", FIELD_STEPS, 3, 0.5, False),
    ("seam_full", FIELD_STEPS, 3, 1.0, False),
    ("seam_full_shuffled", FIELD_STEPS, 3, 1.0, True),
)


def stream_differences(first: list[int], second: list[int]) -> int:
    """Positions where two greedy streams disagree, counting any length excess."""
    shared = min(len(first), len(second))
    differing = sum(1 for index in range(shared) if first[index] != second[index])
    return differing + abs(len(first) - len(second))


def token_sha256(tokens: list[int]) -> str:
    payload = ",".join(str(token) for token in tokens).encode()
    return hashlib.sha256(payload).hexdigest()


def params_match(requested_displacement: int, requested_substitute: float,
                  displacement: int, substitute: float) -> bool:
    """Whether a receipt echoed the parameters it was asked to run.

    The context stores the share as f32, so the comparison carries that
    precision; a dropped or ignored flag still lands orders of magnitude away.
    """
    tolerance = 1.0e-6 * max(1.0, abs(requested_substitute))
    return displacement == requested_displacement and abs(substitute - requested_substitute) <= tolerance


def evaluate(arms: dict[str, dict[str, Any]], guard: dict[str, Any],
             captures: dict[str, Any]) -> dict[str, Any]:
    """Turn the arm receipts into named checks that a silent no-op would fail."""
    echo = {
        name: params_match(
            int(arm["requested_displacement"]), float(arm["requested_substitute"]),
            int(arm["displacement"]), float(arm["substitute"]))
        for name, arm in arms.items()
    }
    # only a field-on arm has a placement; the gate compares the two comparison arms
    interventions = {name: arm["intervention"] for name, arm in arms.items()
                     if arm["intervention"] is not None}
    checks = {
        "params_echoed_in_receipts": {
            "passed": all(echo.values()),
            "echoed": echo,
        },
        "guard_refuses_unsuppressed_substitution": {
            "passed": bool(guard["refused"]),
            "exit_code": guard["exit_code"],
            "stderr_tail": guard["stderr_tail"],
        },
        "suppression_is_live_at_layer": {
            # The suppression is a graph fact: the layer's own state write is gone, so the
            # node counts differ.  A token difference is reported beside it because a
            # prompt can be insensitive to the write while the write is still absent.
            "passed": bool(
                interventions["lesion"] == interventions["write_intact"]
                and int(arms["lesion"]["graph_nodes"]) != int(arms["write_intact"]["graph_nodes"])),
            "interventions": {
                "lesion": interventions["lesion"],
                "write_intact": interventions["write_intact"],
            },
            "graph_nodes": {
                "lesion": int(arms["lesion"]["graph_nodes"]),
                "write_intact": int(arms["write_intact"]["graph_nodes"]),
            },
            "token_difference_count": arms["lesion"]["difference_vs_write_intact"],
        },
        "seam_is_decode_only": {
            "passed": bool(captures["prompt_identical"]),
            "max_prompt_relative_delta": captures["max_prompt_relative_delta"],
        },
        "seam_share_is_the_only_difference": {
            # the early decode sees the seam's write with the same input tokens, so a
            # differing first token would break the comparison the reach rests on
            "passed": bool(captures["shared_first_token"]),
            "first_tokens": {
                name: arms[name]["generation_token_ids"][0] if arms[name]["generation_token_ids"] else None
                for name in RELOCATION_FAMILY
            },
        },
        "seam_dose_response_in_decode_captures": {
            "passed": bool(
                captures["early_reach"]["seam_half"] > 0.0
                and captures["early_reach"]["seam_full"] >= 1.5 * captures["early_reach"]["seam_half"]),
            "early_reach": captures["early_reach"],
            "early_reach_deepest_layer": captures["early_reach_deepest_layer"],
            "late_reach": captures["reach_late"],
            "committed_token_changes_vs_relocated": {
                "seam_full": arms["seam_full"]["difference_vs_relocated"],
                "seam_half": arms["seam_half"]["difference_vs_relocated"],
                "lesion": arms["lesion"]["difference_vs_relocated"],
            },
        },
        "field_evolves_while_it_supplies_the_state_write": {
            "passed": bool(arms["seam_full"]["state_evolved"]),
            "seam_full_state_max_abs_delta": arms["seam_full"]["state_max_abs_delta"],
            "lesion_state_max_abs_delta": arms["lesion"]["state_max_abs_delta"],
        },
    }
    return {
        "checks": checks,
        "verdict": "PASS" if all(check["passed"] for check in checks.values()) else "FAIL",
    }


def run_harness(
    binary: pathlib.Path,
    model: pathlib.Path,
    state: pathlib.Path,
    backend: str,
    layer: int,
    steps: int,
    displacement: int,
    substitute: float,
    prompt_path: pathlib.Path,
    captures_dir: pathlib.Path,
    generate_tokens: int,
    timeout: int,
    intervention: int | None = None,
    phase_shuffle: bool = False,
    wave_modes: int = 0,
    row_width: int = 0,
) -> dict[str, Any]:
    captures_dir.mkdir(parents=True, exist_ok=True)
    command = [
        str(binary),
        str(model),
        str(state),
        backend,
        str(prompt_path),
        str(layer),
        str(steps),
        str(FIELD_ALPHA),
        str(generate_tokens),
        str(captures_dir),
        "0",
        "1" if phase_shuffle else "0",
    ]
    if displacement != 0:
        command.extend(["--displacement", str(displacement)])
    if wave_modes > 0:
        command.extend(["--wave-modes", str(wave_modes)])
    if row_width > 0:
        command.extend(["--row-width", str(row_width)])
    if substitute > 0.0:
        command.extend(["--substitute", repr(float(substitute))])
    if intervention is not None:
        command.extend(["--intervention", str(intervention)])
    process = subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
    )
    start = process.stdout.find('{"schema":"cassi.qi.latent.v1"')
    if start < 0:
        raise RuntimeError(
            f"no receipt on stdout (exit {process.returncode}): {process.stderr[-500:]}"
        )
    receipt, _ = json.JSONDecoder().raw_decode(process.stdout[start:])
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=pathlib.Path, default=ROOT / "Qwen3.5-0.8B-Q4_0.gguf")
    parser.add_argument(
        "--state",
        type=pathlib.Path,
        default=ROOT / "_diag/latent-reasoning/zero-state-4scale.f32",
    )
    parser.add_argument("--binary", type=pathlib.Path, default=latent.LATENT_BINARY)
    parser.add_argument("--backend", default="cpu")
    parser.add_argument("--layer", type=int, default=12)
    parser.add_argument("--generate-tokens", type=int, default=GENERATE_TOKENS)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--wave-modes", type=int, default=0,
                        help="Qi wave modes; 0 keeps the engine default and the identity control")
    parser.add_argument("--row-width", type=int, default=0,
                        help="channels the seam addresses; 0 keeps n_embd, capped by the flux block")
    parser.add_argument("--prompt-file", type=pathlib.Path, default=None,
                        help="prompt text to run instead of the built-in one; a model that "
                             "repeats on an instruction prompt needs a continuation prompt "
                             "for the suppression to show in the stream")
    parser.add_argument(
        "--out",
        type=pathlib.Path,
        default=ROOT / "_diag/cassi-field-attestation/substitution-probe.json",
    )
    args = parser.parse_args()
    for path in (args.model, args.state, args.binary):
        if not path.is_file():
            raise RuntimeError(f"required file is missing: {path}")
    args.model = args.model.resolve()
    args.state = args.state.resolve()
    args.binary = args.binary.resolve()
    args.out = args.out.resolve()

    # keyed off the receipt name, not the parent, so two models writing into one
    # directory cannot overwrite each other's prompts and captures
    work = args.out.parent / args.out.stem
    work.mkdir(parents=True, exist_ok=True)
    prompt_path = work / "prompt.txt"
    prompt_text = PROMPT
    if args.prompt_file is not None:
        if not args.prompt_file.is_file():
            raise RuntimeError(f"prompt file is missing: {args.prompt_file}")
        prompt_text = args.prompt_file.read_text(encoding="utf-8")
    prompt_path.write_text(prompt_text, encoding="utf-8")

    arms: dict[str, dict[str, Any]] = {}
    for name, steps, displacement, substitute, phase_shuffle in ARM_SPECS:
        receipt = run_harness(
            args.binary, args.model, args.state, args.backend, args.layer,
            steps, displacement, substitute, prompt_path,
            work / name / "captures", args.generate_tokens, args.timeout,
            intervention=INTERVENTION if steps > 0 else None,
            phase_shuffle=phase_shuffle,
            wave_modes=args.wave_modes,
            row_width=args.row_width,
        )
        tokens = [int(token) for token in receipt["generation_token_ids"]]
        print(f"[{name}] {len(tokens)} tokens  {receipt['generation_text'][:60]!r}", flush=True)
        arms[name] = {
            "requested_displacement": displacement,
            "requested_substitute": substitute,
            "steps": steps,
            "phase_shuffle_after_prompt": phase_shuffle,
            "displacement": int(receipt["displacement"]),
            "substitute": float(receipt["substitute"]),
            # a field-off arm has no injection placement to report
            "intervention": (None if receipt["intervention"] is None
                             else int(receipt["intervention"])),
            "graph_nodes": int(receipt["graph_nodes"]),
            "state_field_width": int(receipt["state_field_width"]),
            "state_row_width": int(receipt["state_row_width"]),
            "wave_modes": int(receipt["wave_modes"]),
            "row_width_requested": int(receipt["row_width_requested"]),
            "elapsed_ms": float(receipt["elapsed_ms"]),
            "token_count": len(tokens),
            "token_sha256": token_sha256(tokens),
            "state_evolved": bool(
                int(receipt["state_before_fnv1a"]) != int(receipt["state_after_fnv1a"])),
            "state_max_abs_delta": float(receipt["state_max_abs_delta"]),
            "generation_token_ids": tokens,
            "generation_text": str(receipt["generation_text"]),
            "prompt_captures": receipt["captured_layers"],
            "decode_captures": receipt["decode_captured_layers"],
            "early_decode_captures": receipt["early_decode_captured_layers"],
        }

    for name, arm in arms.items():
        for other in ("write_intact", "lesion", "relocated", "seam_full"):
            arm[f"difference_vs_{other}"] = stream_differences(
                arm["generation_token_ids"], arms[other]["generation_token_ids"])

    def capture_values(key: str, name: str) -> list[tuple[int, Any]]:
        return [(int(entry["layer"]), latent.load_f32(str(entry["path"])))
                for entry in arms[name][key]]

    # The seam writes the state a single-token decode reads, so its reach shows up in
    # the decode captures.  Decode 0 reads the state the prefill wrote, so decode 1 is
    # the first pass that reads the seam's write with the same input tokens in every
    # arm; the late captures are reported for the drift they include, not for the seam.
    reaches: dict[str, float] = {}
    early_reaches: dict[str, float] = {}
    early_deepest: dict[str, float] = {}
    early_curves: dict[str, dict[int, float]] = {}
    prompt_identical = True
    max_prompt_relative_delta = 0.0
    reference_prompt = capture_values("prompt_captures", "relocated")
    reference_decode = capture_values("decode_captures", "relocated")
    reference_early = capture_values("early_decode_captures", "relocated")
    if not reference_early:
        raise RuntimeError("the reference arm produced no early decode capture")
    compared: list[str] = []
    for name in arms:
        if not arms[name]["early_decode_captures"]:
            continue  # a field-off arm has no layer captures to compare
        compared.append(name)
        decode = capture_values("decode_captures", name)
        early = capture_values("early_decode_captures", name)
        prompt = capture_values("prompt_captures", name)
        if name not in PROMPT_IDENTITY_FAMILY:
            continue
        if len(decode) != len(reference_decode) or len(prompt) != len(reference_prompt):
            raise RuntimeError(f"{name}: capture sets differ in length from the reference arm")
        if len(early) != len(reference_early):
            raise RuntimeError(f"{name}: early capture set differs in length from the reference arm")
        if name in RELOCATION_FAMILY:
            reach = 0.0
            for (layer, values), (ref_layer, ref_values) in zip(decode, reference_decode):
                if layer != ref_layer:
                    raise RuntimeError(f"{name}: decode capture layer {layer} does not match {ref_layer}")
                reach = max(reach, float(latent.vector_delta(ref_values, values)["relative_delta"]))
            reaches[name] = reach
            early_curve: dict[int, float] = {}
            for (layer, values), (ref_layer, ref_values) in zip(early, reference_early):
                if layer != ref_layer:
                    raise RuntimeError(f"{name}: early capture layer {layer} does not match {ref_layer}")
                early_curve[layer] = float(latent.vector_delta(ref_values, values)["relative_delta"])
            early_curves[name] = early_curve
            deepest_layer = max(early_curve)
            early_reaches[name] = max(early_curve.values())
            early_deepest[name] = early_curve[deepest_layer]
        for (layer, values), (ref_layer, ref_values) in zip(prompt, reference_prompt):
            if layer != ref_layer:
                raise RuntimeError(f"{name}: prompt capture layer {layer} does not match {ref_layer}")
            delta = float(latent.vector_delta(ref_values, values)["relative_delta"])
            max_prompt_relative_delta = max(max_prompt_relative_delta, delta)
            prompt_identical = prompt_identical and bool(
                latent.vector_delta(ref_values, values)["exact"])
    first_tokens = {
        name: (arms[name]["generation_token_ids"][0] if arms[name]["generation_token_ids"] else None)
        for name in RELOCATION_FAMILY
    }
    shared_first_token = len(set(first_tokens.values())) == 1 and None not in first_tokens.values()
    shuffled_early_curve = {
        layer: float(latent.vector_delta(ref_values, values)["relative_delta"])
        for (layer, values), (_, ref_values) in zip(
            capture_values("early_decode_captures", "seam_full_shuffled"), reference_early)
    }
    captures = {
        "compared_arms": compared,
        "early_reach": early_reaches,
        "early_reach_deepest_layer": early_deepest,
        "early_curve_by_layer": {name: {str(k): v for k, v in curve.items()}
                                 for name, curve in early_curves.items()},
        "reach_late": reaches,
        "shared_first_token": shared_first_token,
        "first_tokens": first_tokens,
        "prompt_identical": prompt_identical,
        "max_prompt_relative_delta": max_prompt_relative_delta,
        "field_content_control": {
            "note": (
                "seam_full_shuffled runs the same share with a matched-norm phase-shuffled "
                "field; the early-capture delta against seam_full is the content "
                "discriminator, since a stream can be insensitive where the activations "
                "are not"
            ),
            "shuffled_early_reach": max(shuffled_early_curve.values()),
            "seam_full_early_reach": early_reaches["seam_full"],
            "shuffled_vs_seam_full_early_reach": (
                max(latent.vector_delta(res_full, shuffled_full)["relative_delta"]
                    for res_full, shuffled_full in zip(
                        [values for _, values in capture_values("early_decode_captures", "seam_full")],
                        [values for _, values in capture_values("early_decode_captures", "seam_full_shuffled")]))
            ),
            "committed_token_changes_shuffled_vs_seam_full":
                arms["seam_full_shuffled"]["difference_vs_seam_full"],
            "committed_token_changes_shuffled_vs_relocated":
                arms["seam_full_shuffled"]["difference_vs_relocated"],
            "shuffled_prompt_identical": bool(
                all(latent.vector_delta(ref_values, values)["exact"]
                    for (_, values), (_, ref_values) in
                    zip(capture_values("prompt_captures", "seam_full_shuffled"), reference_prompt))),
            # reported beside the shuffled comparisons because a shuffled arm matching the
            # relocated arm does not mean the share leaves the stream unchanged
            "full_share_vs_relocated_token_changes":
                arms["seam_full"]["difference_vs_relocated"],
            "half_share_vs_full_share_token_changes":
                arms["seam_half"]["difference_vs_seam_full"],
        },
    }
    print("early reach (max relative delta at the first matched decode, vs relocated): "
          + ", ".join(f"{name}={value:.3e}" for name, value in early_reaches.items()), flush=True)
    print("late reach (max, includes stream drift): "
          + ", ".join(f"{name}={value:.3e}" for name, value in reaches.items()), flush=True)
    print("field content control: shuffled vs seam_full token changes = "
          f"{arms['seam_full_shuffled']['difference_vs_seam_full']}", flush=True)

    guard_dir = work / "guard"
    guard_dir.mkdir(parents=True, exist_ok=True)
    guard_process = subprocess.run(
        [
            str(args.binary), str(args.model), str(args.state), args.backend,
            str(prompt_path), str(args.layer), str(FIELD_STEPS), str(FIELD_ALPHA),
            str(args.generate_tokens), str(guard_dir / "captures"), "0", "0",
            "--substitute", "0.5",
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=args.timeout,
    )
    guard = {
        "refused": guard_process.returncode != 0 and "SUBSTITUTE requires" in guard_process.stderr,
        "exit_code": guard_process.returncode,
        "stderr_tail": guard_process.stderr[-200:],
    }
    print(f"[guard] exit {guard['exit_code']} refused={guard['refused']}", flush=True)

    evaluated = evaluate(arms, guard, captures)
    receipt = {
        "schema": "cassi.qi.substitution.v1",
        "probe": "one greedy harness run per arm; the seam's own arm is compared with the relocation arm",
        "binary": str(args.binary),
        "binary_sha256": hashlib.sha256(args.binary.read_bytes()).hexdigest(),
        "model": args.model.name,
        "state": args.state.name,
        "config": {
            "backend": args.backend,
            "layer": args.layer,
            "field_steps": FIELD_STEPS,
            "field_alpha": FIELD_ALPHA,
            "generate_tokens": args.generate_tokens,
            "prompt": prompt_text,
        },
        "arms": arms,
        "guard": guard,
        "captures": captures,
        **evaluated,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    failed = [name for name, check in receipt["checks"].items() if not check["passed"]]
    print(f"verdict: {receipt['verdict']}" + (f"  failed: {', '.join(failed)}" if failed else ""))
    print(f"receipt: {args.out}")
    return 0 if receipt["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
