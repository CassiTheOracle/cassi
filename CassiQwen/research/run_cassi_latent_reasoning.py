#!/usr/bin/env python3
"""Measure additive mid-trunk Qi dynamics against causal controls."""

from __future__ import annotations

import argparse
import hashlib
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

LATENT_BINARY_CANDIDATES = (
    ROOT / "native/llama.cpp/b8/bin/Release/test-cassi-qi-latent.exe",
    ROOT / "native/llama.cpp/build-qi/bin/Release/test-cassi-qi-latent.exe",
)
LATENT_BINARY = next(
    (
        candidate
        for candidate in LATENT_BINARY_CANDIDATES
        if candidate.is_file()
    ),
    LATENT_BINARY_CANDIDATES[0],
)

CASES = (
    {
        "name": "reversible_digits",
        "expected": "92",
        "prompt": (
            "A box starts at 12. Multiply it by 3, subtract 7, then reverse the two "
            "decimal digits. Work it out and finish with a line containing only the final integer."
        ),
    },
    {
        "name": "ordered_composition",
        "expected": "mira",
        "prompt": (
            "Four people stand in one line. Mira is before Sol. Taro is after Sol. "
            "Ivo is before Mira. Work out who is second and finish with a line containing only that name."
        ),
    },
    {
        "name": "delayed_cue",
        "expected": "cobalt",
        "prompt": (
            "Keep the key word COBALT in mind. Distractors: a triangle has three sides; "
            "water freezes at zero Celsius; cedar is a tree; seven is prime; Mars has two moons. "
            "Ignore the distractors. Finish with a line containing only the original key word."
        ),
    },
    {
        "name": "reversible_state",
        "expected": "17",
        "prompt": (
            "A register starts at 5. Add 8. Double the result. Undo only the doubling. "
            "Then add 4. Work it out and finish with a line containing only the register value."
        ),
    },
    {
        "name": "toggle_parity",
        "expected": "on",
        "prompt": (
            "A lamp starts OFF. Toggle it seven times, one after another. Work out its final state "
            "and finish with a line containing only ON or OFF."
        ),
    },
    {
        "name": "shortest_route",
        "expected": "b",
        "prompt": (
            "An undirected graph has edges A-B, B-D, A-C, C-E, and E-D. Starting at A, "
            "take a route with the fewest edges to D. Finish with a line containing only the first "
            "node visited after A."
        ),
    },
)

ARMS = (
    {"name": "field_off", "steps": 0, "alpha": 0.0, "reset": False},
    {"name": "live_identity", "steps": 1, "alpha": 0.0, "reset": False},
    {"name": "k1_a001", "steps": 1, "alpha": 0.001, "reset": False},
    {"name": "k1_a003", "steps": 1, "alpha": 0.003, "reset": False},
    {"name": "k1_a01", "steps": 1, "alpha": 0.01, "reset": False},
    {"name": "k1_a03", "steps": 1, "alpha": 0.03, "reset": False},
    {"name": "k1_a1", "steps": 1, "alpha": 0.1, "reset": False},
    {"name": "k1_a100", "steps": 1, "alpha": 1.0, "reset": False},
    {"name": "k4_a001", "steps": 4, "alpha": 0.001, "reset": False},
    {"name": "k4_a003", "steps": 4, "alpha": 0.003, "reset": False},
    {"name": "k4_a003_reset", "steps": 4, "alpha": 0.003, "reset": True},
    {"name": "k4_a01", "steps": 4, "alpha": 0.01, "reset": False},
    {"name": "k4_a01_reset", "steps": 4, "alpha": 0.01, "reset": True},
    {"name": "k4_a03", "steps": 4, "alpha": 0.03, "reset": False},
    {"name": "k4_a03_reset", "steps": 4, "alpha": 0.03, "reset": True},
    {"name": "k4_a1", "steps": 4, "alpha": 0.1, "reset": False},
    {"name": "k4_a1_reset", "steps": 4, "alpha": 0.1, "reset": True},
    {"name": "k4_a100", "steps": 4, "alpha": 1.0, "reset": False},
    {"name": "k4_a100_reset", "steps": 4, "alpha": 1.0, "reset": True},
    {"name": "k16_a003", "steps": 16, "alpha": 0.003, "reset": False},
    {"name": "k16_a03", "steps": 16, "alpha": 0.03, "reset": False},
    {"name": "k16_a100", "steps": 16, "alpha": 1.0, "reset": False},
    {"name": "k16_a100_reset", "steps": 16, "alpha": 1.0, "reset": True},
    {"name": "k16_a100_shuffle", "steps": 16, "alpha": 1.0, "reset": False, "shuffle": True},
    # Placement arms. Arm names carry the coupling: k4_a01 is 4 evolutions at
    # alpha 0.01, so a full generation spends 32 x 4 x 0.01 = 1.28. A placement
    # arm decodes the prompt with the same coupling and then spends that same
    # 1.28 on eight of the generated-token decodes at 16 x 0.01, holding the
    # rest at alpha 0. Held decodes still evolve the field, so only the
    # injection placement differs. run() asserts the matched budgets.
    {"name": "place_front16", "steps": 4, "alpha": 0.01, "reset": False,
     "schedule": {"coupled_steps": 16, "coupled_alpha": 0.01, "hold_steps": 4,
                  "positions": list(range(0, 8))}},
    {"name": "place_back16", "steps": 4, "alpha": 0.01, "reset": False,
     "schedule": {"coupled_steps": 16, "coupled_alpha": 0.01, "hold_steps": 4,
                  "positions": list(range(24, 32))}},
    {"name": "place_spread16", "steps": 4, "alpha": 0.01, "reset": False,
     "schedule": {"coupled_steps": 16, "coupled_alpha": 0.01, "hold_steps": 4,
                  "positions": list(range(0, 32, 4))}},
    {"name": "place_digest16", "steps": 4, "alpha": 0.01, "reset": False,
     "schedule": {"coupled_steps": 16, "coupled_alpha": 0.01, "hold_steps": 4,
                  "positions": [1, 5, 6, 12, 17, 21, 27, 30]}},
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    payload = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, path)


def parse_receipt(stdout: str) -> dict[str, Any]:
    marker = "{\"schema\":\"cassi.qi.latent.v1\""
    start = stdout.rfind(marker)
    if start < 0:
        raise RuntimeError("latent harness emitted no cassi.qi.latent.v1 receipt")
    value, _ = json.JSONDecoder().raw_decode(stdout[start:])
    if not isinstance(value, dict) or value.get("schema") != "cassi.qi.latent.v1":
        raise RuntimeError("latent harness receipt has the wrong schema")
    return value


def answer_fragment(text: str) -> str:
    text = re.sub(r"<\|[^|]*\|>", "", text.lower().replace("</think>", "\n"))
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    return re.sub(r"[^a-z0-9]+", "", lines[-1])


def is_correct(text: str, expected: str) -> bool:
    answer = answer_fragment(text)
    expected = expected.lower()
    return answer == expected or answer.endswith(expected)


def first_divergence(left: list[int], right: list[int]) -> int | None:
    for index, (a, b) in enumerate(zip(left, right)):
        if a != b:
            return index
    return min(len(left), len(right)) if len(left) != len(right) else None


def load_f32(path: str) -> np.ndarray:
    values = np.fromfile(path, dtype=np.float32)
    if values.size == 0 or not np.isfinite(values).all():
        raise RuntimeError(f"invalid F32 capture: {path}")
    return values.astype(np.float64)


def vector_delta(reference: np.ndarray, candidate: np.ndarray) -> dict[str, float | bool]:
    if reference.shape != candidate.shape:
        raise RuntimeError("capture shapes differ")
    delta = candidate - reference
    ref_norm = float(np.linalg.norm(reference))
    candidate_norm = float(np.linalg.norm(candidate))
    delta_norm = float(np.linalg.norm(delta))
    denominator = ref_norm * candidate_norm
    cosine = float(np.dot(reference, candidate) / denominator) if denominator else 1.0
    cosine = max(-1.0, min(1.0, cosine))
    return {
        "exact": bool(np.array_equal(reference, candidate)),
        "reference_l2": ref_norm,
        "candidate_l2": candidate_norm,
        "delta_l2": delta_norm,
        "relative_delta": delta_norm / ref_norm if ref_norm else 0.0,
        "cosine": cosine,
        "angle_degrees": math.degrees(math.acos(cosine)),
        "max_abs_delta": float(np.max(np.abs(delta))),
    }


def schedule_lines(schedule: dict[str, Any], generate_tokens: int) -> list[str]:
    """One `STEPS ALPHA` line per generated-token decode.

    Coupled positions carry the arm's coupled coupling; every other decode holds
    the field with alpha 0, which the identity control shows leaves the decoded
    stream unchanged.
    """

    positions = {int(position) for position in schedule["positions"]}
    outside = [position for position in positions if position >= generate_tokens]
    if outside:
        raise RuntimeError(
            f"schedule positions outside the generation window: {sorted(outside)}"
        )
    hold_steps = int(schedule["hold_steps"])
    if hold_steps < 1:
        raise RuntimeError("schedule hold_steps must be at least 1")
    lines = []
    for index in range(generate_tokens):
        if index in positions:
            lines.append(
                f"{int(schedule['coupled_steps'])} {schedule['coupled_alpha']}"
            )
        else:
            lines.append(f"{hold_steps} 0.0")
    return lines


def check_coupling_budgets(
    comparisons: dict[str, dict[str, Any]], reference_name: str = "k4_a01"
) -> dict[str, Any] | None:
    """Match every scheduled arm's injection budget to the constant reference.

    A scheduled arm that spends a different budget is not a placement
    comparison, so this refuses rather than reporting a confounded result.
    """

    scheduled = {
        name: row
        for name, row in comparisons.items()
        if int(row["schedule_applied_entries"]) > 0
    }
    if not scheduled:
        return None
    if reference_name not in comparisons:
        raise RuntimeError(
            "placement arms need the constant "
            f"{reference_name} arm in the same run to match budgets"
        )
    reference_budget = float(comparisons[reference_name]["coupling_budget"])
    if reference_budget <= 0.0:
        raise RuntimeError("the constant reference arm spent no coupling budget")
    mismatched = {
        name: row["coupling_budget"]
        for name, row in scheduled.items()
        if abs(float(row["coupling_budget"]) - reference_budget) > 1e-9
    }
    if mismatched:
        raise RuntimeError(
            "scheduled arms do not match the constant reference budget "
            f"{reference_budget}: {mismatched}"
        )
    return {
        "reference_arm": reference_name,
        "reference_budget": reference_budget,
        "reference_steps": int(comparisons[reference_name]["field_steps"]),
        "reference_alpha": float(comparisons[reference_name]["alpha"]),
        "matched_arms": sorted(scheduled),
    }


def run_arm(args: argparse.Namespace, case: dict[str, str], arm: dict[str, Any], out: Path) -> dict[str, Any]:
    arm_dir = out / case["name"] / arm["name"]
    arm_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = arm_dir / "prompt.txt"
    prompt_path.write_text(case["prompt"], encoding="utf-8")
    command = [
        str(args.binary),
        str(args.model),
        str(args.state),
        args.backend,
        str(prompt_path),
        str(args.layer),
        str(arm["steps"]),
        str(arm["alpha"]),
        str(args.generate_tokens),
        str(arm_dir / "captures"),
        "1" if arm["reset"] else "0",
        "1" if arm.get("shuffle", False) else "0",
    ]
    if args.wave_modes > 0:
        command.extend(["--wave-modes", str(args.wave_modes)])
    if args.row_width > 0:
        command.extend(["--row-width", str(args.row_width)])
    if arm.get("schedule") is not None:
        lines = schedule_lines(arm["schedule"], args.generate_tokens)
        schedule_path = arm_dir / "schedule.txt"
        schedule_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        command.extend(["--schedule", str(schedule_path)])
    started = time.perf_counter()
    process = subprocess.run(command, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=args.timeout)
    wall_seconds = time.perf_counter() - started
    (arm_dir / "stdout.log").write_text(process.stdout, encoding="utf-8")
    (arm_dir / "stderr.log").write_text(process.stderr, encoding="utf-8")
    if process.returncode != 0:
        raise RuntimeError(f"{case['name']}/{arm['name']} failed with {process.returncode}; see {arm_dir}")
    receipt = parse_receipt(process.stdout)
    receipt["process_wall_seconds"] = wall_seconds
    receipt["correct"] = is_correct(str(receipt["generation_text"]), case["expected"])
    receipt["answer_fragment"] = answer_fragment(str(receipt["generation_text"]))
    receipt["expected"] = case["expected"]
    atomic_json(arm_dir / "receipt.json", receipt)
    return receipt


def compare_case(case: dict[str, str], receipts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    reference = receipts["field_off"]
    reference_layers = {int(item["layer"]): item for item in reference["captured_layers"]}
    comparisons: dict[str, Any] = {}
    for arm_name, receipt in receipts.items():
        layers: dict[str, Any] = {}
        for item in receipt["captured_layers"]:
            layer = int(item["layer"])
            base_path = reference_layers[layer]["path"]
            arm_path = item["path"]
            if base_path is None or arm_path is None:
                continue
            layers[str(layer)] = vector_delta(load_f32(base_path), load_f32(arm_path))
        reference_logits_path = next(
            item["path"] for item in reference["capture_files"] if item["name"] == "logits.f32"
        )
        arm_logits_path = next(item["path"] for item in receipt["capture_files"] if item["name"] == "logits.f32")
        reference_tokens = list(reference["generation_token_ids"])
        arm_tokens = list(receipt["generation_token_ids"])
        comparisons[arm_name] = {
            "correct": bool(receipt["correct"]),
            "answer_fragment": receipt["answer_fragment"],
            "first_token_divergence": first_divergence(reference_tokens, arm_tokens),
            "changed_generated_tokens": sum(a != b for a, b in zip(reference_tokens, arm_tokens))
            + abs(len(reference_tokens) - len(arm_tokens)),
            "logits": vector_delta(load_f32(reference_logits_path), load_f32(arm_logits_path)),
            "layers": layers,
            "state_changed": bool(receipt["state_before_fnv1a"] != receipt["state_after_fnv1a"]),
            "phase_shuffled_after_prompt": bool(receipt.get("phase_shuffle_after_prompt", False)),
            "field_steps": int(receipt["steps"]),
            "alpha": float(receipt["alpha"]),
            "elapsed_ms": float(receipt["elapsed_ms"]),
            "coupling_budget": float(receipt["coupling_budget"]),
            "schedule_entries": int(receipt.get("schedule_entries", 0)),
            "schedule_applied_entries": int(
                receipt.get("schedule_applied_entries", 0)
            ),
            "schedule_steps_max": int(receipt.get("schedule_steps_max", 0)),
            "graph_nodes_after_coupling": int(
                receipt.get("graph_nodes_after_coupling", -1)
            ),
            "generated_token_scores": [
                float(value)
                for value in receipt.get("generated_token_scores", [])
            ],
        }
    identity = comparisons["live_identity"]
    identity_exact = identity["logits"]["exact"] and all(item["exact"] for item in identity["layers"].values())
    budget_check = check_coupling_budgets(comparisons)
    return {
        "name": case["name"],
        "expected": case["expected"],
        "field_off_correct": bool(reference["correct"]),
        "identity_exact": identity_exact,
        "budget_check": budget_check,
        "arms": comparisons,
    }


def select_named(values: tuple[dict[str, Any], ...], requested: str, label: str) -> tuple[dict[str, Any], ...]:
    if requested == "all":
        return values
    names = [item.strip() for item in requested.split(",") if item.strip()]
    index = {str(item["name"]): item for item in values}
    unknown = [name for name in names if name not in index]
    if unknown:
        raise RuntimeError(f"unknown {label}: {', '.join(unknown)}")
    selected = tuple(index[name] for name in names)
    if not selected:
        raise RuntimeError(f"no {label} selected")
    return selected


def run(args: argparse.Namespace) -> dict[str, Any]:
    args.model = args.model.resolve()
    args.state = args.state.resolve()
    args.binary = args.binary.resolve()
    args.out = args.out.resolve()
    for path in (args.model, args.state, args.binary):
        if not path.is_file():
            raise RuntimeError(f"required file is missing: {path}")
    args.out.mkdir(parents=True, exist_ok=True)
    selected_cases = select_named(CASES, args.case_names, "cases")
    selected_arms = select_named(ARMS, args.arm_names, "arms")
    selected_arm_names = {str(arm["name"]) for arm in selected_arms}
    required_controls = {"field_off", "live_identity"}
    if not required_controls.issubset(selected_arm_names):
        raise RuntimeError("--arm-names must include field_off and live_identity")


    all_receipts: dict[str, dict[str, dict[str, Any]]] = {}
    for case in selected_cases:
        case_receipts: dict[str, dict[str, Any]] = {}
        for arm in selected_arms:
            print(f"[{case['name']}] {arm['name']}", flush=True)
            case_receipts[arm["name"]] = run_arm(args, case, arm, args.out)
        all_receipts[case["name"]] = case_receipts

    cases = [compare_case(case, all_receipts[case["name"]]) for case in selected_cases]
    arm_summary: dict[str, Any] = {}
    for arm in selected_arms:
        name = arm["name"]  # arm summary key
        arm_summary[name] = {
            "correct_cases": sum(case["arms"][name]["correct"] for case in cases),
            "changed_cases": sum(case["arms"][name]["first_token_divergence"] is not None for case in cases),
            "changed_generated_tokens": sum(case["arms"][name]["changed_generated_tokens"] for case in cases),
            "mean_elapsed_ms": sum(case["arms"][name]["elapsed_ms"] for case in cases) / len(cases),
            "coupling_budget": sum(case["arms"][name]["coupling_budget"] for case in cases),
            "schedule_applied_entries": sum(
                case["arms"][name]["schedule_applied_entries"] for case in cases
            ),
        }

    identity_exact = all(case["identity_exact"] for case in cases)
    field_state_bytes = 9 * 6144 * 4 * 4
    result = {
        "schema": "cassi.qi.latent-reasoning.v1",
        "verdict": "MEASURED",
        "configuration": {
            "model": str(args.model),
            "model_sha256": sha256(args.model),
            "model_bytes": args.model.stat().st_size,
            "state": str(args.state),
            "state_sha256": sha256(args.state),
            "binary": str(args.binary),
            "binary_sha256": sha256(args.binary),
            "backend": args.backend,
            "layer": args.layer,
            "generate_tokens": args.generate_tokens,
            "cases": [case["name"] for case in selected_cases],
            "arms": list(selected_arms),
        },
        "controls": {
            "live_identity_exact_across_all_cases": identity_exact,
            "identity_definition": "Qi executes and evolves, but alpha=0 leaves the Qwen hidden stream unchanged.",
        },
        "ownership_receipt": {
            "intervention": "inpL + alpha * first_n_embd(Qi_flux), immediately before the selected Qwen layer",
            "field_state_bytes_per_sequence": field_state_bytes,
            "native_dynamic_state_bytes_removed": 0,
            "native_qwen_layers_skipped": 0,
            "native_qwen_ops_skipped": 0,
            "native_output_rows_skipped": 0,
            "qwen_weight_bytes_avoided_per_token": 0,
            "claim": "causal additive field steering; no native replacement or displacement",
        },
        "arm_summary": arm_summary,
        "cases": cases,
        "source_sha256": {
            "runner": sha256(Path(__file__).resolve()),
            "qwen_graph": sha256(ROOT / "native/llama.cpp/src/models/qwen35.cpp"),
            "context": sha256(ROOT / "native/llama.cpp/src/llama-context.cpp"),
            "harness": sha256(ROOT / "native/llama.cpp/tests/test-cassi-qi-latent.cpp"),
        },
    }
    atomic_json(args.out / "verification.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, default=ROOT / "Qwen3.5-0.8B-Q4_0.gguf")
    parser.add_argument("--state", type=Path, default=ROOT / "_diag/latent-reasoning/zero-state-4scale.f32")
    parser.add_argument("--binary", type=Path, default=LATENT_BINARY)
    parser.add_argument("--out", type=Path, default=ROOT / "_diag/latent-reasoning/campaign")
    parser.add_argument("--backend", choices=("cpu", "gpu"), default="cpu")
    parser.add_argument("--layer", type=int, default=12)
    parser.add_argument("--wave-modes", type=int, default=0,
                        help="Qi wave modes; 0 keeps the engine default")
    parser.add_argument("--row-width", type=int, default=0,
                        help="channels the substitution seam addresses; 0 keeps n_embd, capped by the flux block")
    parser.add_argument("--generate-tokens", type=int, default=32)
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--case-names", default="all")
    parser.add_argument("--arm-names", default="all")
    args = parser.parse_args()
    try:
        result = run(args)
    except Exception as error:
        print(json.dumps({"verdict": "ERROR", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({"verdict": result["verdict"], "arm_summary": result["arm_summary"], "artifact": str(args.out / "verification.json")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
