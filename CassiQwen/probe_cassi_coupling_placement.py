"""Where does a fixed Qi coupling budget do its work?

The latent-reasoning arms apply one constant coupling to every generated-token
decode. This probe spends the same injection budget at named positions instead,
so the question "does placement matter" is answerable before any scheduler is
asked to choose placement.

Arms per case:

  hold_only        every decode holds the field at alpha 0 (identity injection)
  constant_k4_a01  the reference constant arm: 4 evolutions, alpha 0.01, every decode
  single_0         one coupled decode at position 0, holds elsewhere
  single_1         one coupled decode at position 1, holds elsewhere
  front_0_7        eight coupled decodes starting at 0 (the constant arm's budget)
  front_1_8        the same eight coupled decodes, shifted by one

Coupled decodes run 16 evolutions at alpha 0.01, so eight of them spend the same
injection budget (1.28) as the constant arm spends over 32 decodes. Holds run 4
evolutions with alpha 0, which the identity control proves leaves the hidden
stream unchanged.

The receipt records correctness, the changed-token count against `hold_only`,
per-arm injection budget, and which arm first produced the expected answer, so
the "does the first decode carry the whole effect" question is read off the
receipt rather than argued.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import run_cassi_latent_reasoning as latent  # noqa: E402

COUPLED_STEPS = 16
COUPLED_ALPHA = 0.01
HOLD_STEPS = 4
GENERATE_TOKENS = 32
REFERENCE_STEPS = 4
REFERENCE_ALPHA = 0.01


def write_schedule(
    path: pathlib.Path, positions: set[int], generate_tokens: int
) -> None:
    lines = []
    for index in range(generate_tokens):
        if index in positions:
            lines.append(f"{COUPLED_STEPS} {COUPLED_ALPHA}")
        else:
            lines.append(f"{HOLD_STEPS} 0.0")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_arm(
    args: argparse.Namespace,
    case: dict[str, str],
    name: str,
    positions: set[int] | None,
) -> dict[str, Any]:
    arm_dir = args.out / case["name"] / name
    (arm_dir / "captures").mkdir(parents=True, exist_ok=True)
    prompt_path = arm_dir / "prompt.txt"
    prompt_path.write_text(case["prompt"], encoding="utf-8")
    command = [
        str(args.binary),
        str(args.model),
        str(args.state),
        args.backend,
        str(prompt_path),
        str(args.layer),
        str(REFERENCE_STEPS),
        str(REFERENCE_ALPHA),
        str(args.generate_tokens),
        str(arm_dir / "captures"),
        "0",
        "0",
    ]
    if positions is not None:
        schedule_path = arm_dir / "schedule.txt"
        write_schedule(schedule_path, positions, args.generate_tokens)
        command.extend(["--schedule", str(schedule_path)])
    process = subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=args.timeout,
    )
    start = process.stdout.find('{"schema":"cassi.qi.latent.v1"')
    if start < 0:
        raise RuntimeError(
            f"{case['name']}/{name}: no receipt on stdout: {process.stderr[-400:]}"
        )
    receipt, _ = json.JSONDecoder().raw_decode(process.stdout[start:])
    tokens = [int(token) for token in receipt["generation_token_ids"]]
    applied = receipt.get("schedule_applied")
    numeric_pairs = True
    if positions is not None:
        listed = [entry for entry in applied if not isinstance(entry, dict)]
        expected_listed = min(int(receipt["schedule_applied_entries"]), 64)
        numeric_pairs = (
            len(listed) == expected_listed
            and all(
                type(entry) is list
                and len(entry) == 2
                and type(entry[0]) is int
                and type(entry[1]) in (int, float)
                for entry in listed
            )
        )
    return {
        "schedule_applied_numeric_pairs": numeric_pairs,
        "schedule_applied_first": None if not applied else applied[0],
        "correct": latent.is_correct(
            str(receipt["generation_text"]), case["expected"]
        ),
        "answer_fragment": latent.answer_fragment(str(receipt["generation_text"])),
        "coupling_budget": float(receipt["coupling_budget"]),
        "schedule_applied_entries": int(receipt.get("schedule_applied_entries", 0)),
        "schedule_steps_max": int(receipt.get("schedule_steps_max", 0)),
        "generation_token_ids": tokens,
        "identity_exact_state": bool(
            receipt["state_before_fnv1a"] == receipt["state_after_fnv1a"]
        ),
        "state_changed": bool(
            receipt["state_before_fnv1a"] != receipt["state_after_fnv1a"]
        ),
        "elapsed_ms": float(receipt["elapsed_ms"]),
    }


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
    parser.add_argument("--case-names", default="all")
    parser.add_argument(
        "--out",
        type=pathlib.Path,
        default=ROOT / "_diag/latent-reasoning/coupling-placement",
    )
    args = parser.parse_args()
    for path in (args.model, args.state, args.binary):
        if not path.is_file():
            raise RuntimeError(f"required file is missing: {path}")
    args.model = args.model.resolve()
    args.state = args.state.resolve()
    args.binary = args.binary.resolve()
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=True)

    cases = latent.select_named(latent.CASES, args.case_names, "cases")
    arm_specs: tuple[tuple[str, set[int] | None], ...] = (
        ("hold_only", set()),
        ("constant_k4_a01", None),
        ("single_0", {0}),
        ("single_1", {1}),
        ("front_0_7", set(range(0, 8))),
        ("front_1_8", set(range(1, 9))),
    )

    zero_step_prompt = args.out / "zero-step-prompt.txt"
    zero_step_prompt.write_text("the keyword is cobalt\n", encoding="utf-8")
    zero_step_schedule = args.out / "zero-step-schedule.txt"
    zero_step_schedule.write_text("0 0.1\n", encoding="utf-8")
    refusal = subprocess.run(
        [
            str(args.binary),
            str(args.model),
            str(args.state),
            args.backend,
            str(zero_step_prompt),
            str(args.layer),
            str(REFERENCE_STEPS),
            str(REFERENCE_ALPHA),
            str(args.generate_tokens),
            str(args.out / "zero-step-captures"),
            "0",
            "0",
            "--schedule",
            str(zero_step_schedule),
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=args.timeout,
    )
    zero_step_refused = bool(
        refusal.returncode != 0
        and "use ALPHA 0 to hold the field without injection" in refusal.stderr
    )
    if not zero_step_refused:
        raise RuntimeError(
            "the harness accepted a zero-step schedule instead of refusing it: "
            f"rc={refusal.returncode} stderr={refusal.stderr[-300:]}"
        )

    case_results: dict[str, Any] = {}
    for case in cases:
        arms: dict[str, Any] = {}
        for name, positions in arm_specs:
            print(f"[{case['name']}] {name}", flush=True)
            arms[name] = run_arm(args, case, name, positions)
        hold = arms["hold_only"]
        constant = arms["constant_k4_a01"]
        baseline_tokens = list(hold["generation_token_ids"])
        for name, arm in arms.items():
            tokens = list(arm["generation_token_ids"])
            arm["changed_generated_tokens_vs_hold"] = sum(
                left != right for left, right in zip(baseline_tokens, tokens)
            ) + abs(len(baseline_tokens) - len(tokens))
            arm["first_token_divergence_vs_hold"] = latent.first_divergence(
                baseline_tokens, tokens
            )
        moved = [name for name in arms if arms[name]["changed_generated_tokens_vs_hold"] > 0]
        correct_arms = [name for name in arms if arms[name]["correct"]]
        budget_matched = {
            name: arms[name]["coupling_budget"]
            for name in ("single_0", "single_1", "front_0_7", "front_1_8")
            if arms[name]["schedule_applied_entries"] > 0
        }
        case_results[case["name"]] = {
            "expected": case["expected"],
            "arms": arms,
            "budget_check": {
                "reference_arm": "constant_k4_a01",
                "reference_budget": constant["coupling_budget"],
                "front_arm_budget": arms["front_0_7"]["coupling_budget"],
                "single_arm_budget": arms["single_0"]["coupling_budget"],
                "front_matches_constant": abs(
                    arms["front_0_7"]["coupling_budget"]
                    - constant["coupling_budget"]
                )
                <= 1e-9,
                "scheduled_arms": budget_matched,
            },
            "arms_that_changed_the_stream": moved,
            "arms_that_answered_correctly": correct_arms,
            "first_decode_carries_the_effect": bool(
                not arms["hold_only"]["correct"]
                and arms["single_0"]["correct"]
                and not arms["single_1"]["correct"]
            ),
        }

    bad_typing = [
        (case_name, arm_name)
        for case_name, row in case_results.items()
        for arm_name, arm in row["arms"].items()
        if arm["schedule_applied_entries"] > 0
        and not arm["schedule_applied_numeric_pairs"]
    ]

    summary = {
        "cases": len(case_results),
        "cases_moved_by_coupling": sum(
            1
            for row in case_results.values()
            if any(
                name not in {"hold_only"}
                and row["arms"][name]["changed_generated_tokens_vs_hold"] > 0
                for name in row["arms"]
            )
        ),
        "cases_where_first_decode_carries_the_effect": sum(
            1
            for row in case_results.values()
            if row["first_decode_carries_the_effect"]
        ),
        "cases_answered_correctly_by_any_arm": sum(
            1 for row in case_results.values() if row["arms_that_answered_correctly"]
        ),
    }
    receipt = {
        "schema": "cassi.qi.coupling-placement.v1",
        "verdict": "MEASURED",
        "configuration": {
            "model": str(args.model),
            "model_sha256": latent.sha256(args.model),
            "state": str(args.state),
            "state_sha256": latent.sha256(args.state),
            "binary": str(args.binary),
            "binary_sha256": latent.sha256(args.binary),
            "backend": args.backend,
            "layer": args.layer,
            "generate_tokens": args.generate_tokens,
            "coupled_steps": COUPLED_STEPS,
            "coupled_alpha": COUPLED_ALPHA,
            "hold_steps": HOLD_STEPS,
            "reference_steps": REFERENCE_STEPS,
            "reference_alpha": REFERENCE_ALPHA,
            "arm_schedule": {
                name: sorted(positions) if positions is not None else "constant"
                for name, positions in arm_specs
            },
        },
        "controls": {
            "zero_step_schedule_refused": zero_step_refused,
            "schedule_applied_is_numeric_pairs": not bad_typing,
            "hold_only_is_alpha_zero_injection": True,
            "front_matches_constant_budget": all(
                row["budget_check"]["front_matches_constant"]
                for row in case_results.values()
            ),
            "budget_definition": (
                "sum of steps x alpha over applied generated-token decodes"
            ),
        },
        "summary": summary,
        "cases": case_results,
    }
    receipt_path = args.out / "placement.json"
    receipt_path.write_text(json.dumps(receipt, indent=1, sort_keys=True), encoding="utf-8")
    print(json.dumps(receipt["summary"], sort_keys=True))
    print(f"receipt: {receipt_path}")
    if bad_typing:
        raise RuntimeError(
            "schedule_applied entries are not unquoted [steps, alpha] numbers for: "
            f"{bad_typing}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
