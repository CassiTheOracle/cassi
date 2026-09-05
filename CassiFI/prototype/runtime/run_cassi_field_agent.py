"""Run grounded actions, predictions, explanations, and queries through Qi."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import torch

from cassi_field_agent import CassiFieldAgent
from cassi_fi_paths import ARTIFACT_DIR, CONFIG_DIR
from cassi_grounded_language import GROUND_TIME_HELDOUT_QUESTIONS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=CONFIG_DIR / "cassi-qi-corpus-language.json",
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=ARTIFACT_DIR / "cassi-qi-discourse-language" / "field-state.pt",
    )
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=ARTIFACT_DIR / "cassi-qi-discourse-language" / "sessions",
    )
    parser.add_argument("--session-id", default="grounded-agent.0")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--instruction",
        action="append",
        help="Instruction to execute; repeat for a multi-turn session.",
    )
    parser.add_argument(
        "--predict",
        action="append",
        metavar="INSTRUCTION",
        help="Predict an instruction's action and world change without executing it.",
    )
    parser.add_argument(
        "--question",
        action="append",
        help="Spatial question to answer; repeat for multiple queries.",
    )
    parser.add_argument(
        "--bind",
        action="append",
        metavar="NAME::STATEMENT",
        help="Bind a temporary name through a natural statement; repeatable.",
    )
    parser.add_argument(
        "--reference-query",
        action="append",
        metavar="SUBJECT::COMPARISON::QUESTION",
        help="Resolve two field references, then answer their spatial question.",
    )
    parser.add_argument(
        "--explain-last",
        action="store_true",
        help="Explain the cause and change in the last executed transition.",
    )
    parser.add_argument(
        "--order-last",
        choices=("before", "after"),
        help="Locate the before or after state in the last transition.",
    )
    parser.add_argument(
        "--order-presentation",
        choices=("forward", "reverse"),
        default="forward",
        help="Present the last transition in forward or reverse order.",
    )
    parser.add_argument("--no-consolidate", action="store_true")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--torch-threads", type=int, default=1)
    parser.add_argument("--json", action="store_true")
    return parser

def _parts(specification: str, count: int, label: str) -> tuple[str, ...]:
    parts = tuple(part.strip() for part in specification.split("::", count - 1))
    if len(parts) != count or any(not part for part in parts):
        raise SystemExit(f"{label} must contain {count} nonempty '::'-separated parts")
    return parts




def main() -> int:
    arguments = build_parser().parse_args()
    if arguments.torch_threads < 1:
        raise SystemExit("--torch-threads must be positive")
    instructions = arguments.instruction or []
    predictions = arguments.predict or []
    questions = arguments.question or []
    bindings = [
        _parts(specification, 2, "--bind") for specification in arguments.bind or []
    ]
    reference_specs = [
        _parts(specification, 3, "--reference-query")
        for specification in arguments.reference_query or []
    ]
    if not any(
        (
            instructions,
            predictions,
            questions,
            bindings,
            reference_specs,
            arguments.explain_last,
            arguments.order_last,
        )
    ):
        questions = ["please decide if red is left or right of blue"]
    torch.set_num_threads(arguments.torch_threads)
    with CassiFieldAgent.open(
        config_path=arguments.config,
        checkpoint_path=arguments.checkpoint,
        state_dir=arguments.state_dir,
        session_id=arguments.session_id,
        seed=arguments.seed,
        device=arguments.device,
    ) as agent:
        binding_receipts = [
            agent.bind_reference(name, statement).receipt_dict()
            for name, statement in bindings
        ]
        prediction_receipts = [
            agent.predict_action(instruction).receipt_dict()
            for instruction in predictions
        ]
        steps = [
            agent.step(
                instruction,
                consolidate=not arguments.no_consolidate,
            ).receipt_dict()
            for instruction in instructions
        ]
        queries = [agent.query(question).receipt_dict() for question in questions]
        reference_queries = [
            agent.query_reference(subject, comparison, question).receipt_dict()
            for subject, comparison, question in reference_specs
        ]
        explanations = (
            [agent.explain_last_transition().receipt_dict()]
            if arguments.explain_last
            else []
        )
        orderings = (
            [
                agent.order_last_transition(
                    GROUND_TIME_HELDOUT_QUESTIONS[f"time.{arguments.order_last}"],
                    presentation=arguments.order_presentation,
                ).receipt_dict()
            ]
            if arguments.order_last
            else []
        )
    if arguments.json:
        print(
            json.dumps(
                {
                    "bindings": binding_receipts,
                    "explanations": explanations,
                    "orderings": orderings,
                    "predictions": prediction_receipts,
                    "queries": queries,
                    "reference_queries": reference_queries,
                    "status": "ok",
                    "steps": steps,
                },
                sort_keys=True,
            )
        )
    else:
        for binding in binding_receipts:
            print(
                f"tick={binding['tick']} bind={binding['name']!r} "
                f"reference={binding['reference_id']} margin={binding['margin']:.6f} "
                f"events={binding['event_count']} "
                f"elapsed={binding['elapsed_seconds']:.3f}s"
            )
        for prediction in prediction_receipts:
            print(
                f"tick={prediction['tick']} predict={prediction['instruction']!r} "
                f"action={prediction['action_id']} "
                f"change={prediction['predicted_change']} "
                f"world_unchanged={prediction['world_unchanged']} "
                f"elapsed={prediction['elapsed_seconds']:.3f}s"
            )
        for step in steps:
            print(
                f"tick={step['tick']} instruction={step['instruction']!r} "
                f"action={step['action_id']} margin={step['margin']:.6f} "
                f"effect={step['world_effect']} "
                f"elapsed={step['elapsed_seconds']:.3f}s"
            )
        for query in queries:
            print(
                f"tick={query['tick']} question={query['question']!r} "
                f"answer={query['answer']} family={query['family_id']} "
                f"margin={query['margin']:.6f} "
                f"elapsed={query['elapsed_seconds']:.3f}s"
            )
        for query in reference_queries:
            print(
                f"tick={query['tick']} subject={query['subject_surface']!r}"
                f"->{query['subject_reference']} "
                f"comparison={query['comparison_surface']!r}"
                f"->{query['comparison_reference']} "
                f"answer={query['answer']} family={query['family_id']} "
                f"margin={query['margin']:.6f} "
                f"elapsed={query['elapsed_seconds']:.3f}s"
            )
        for explanation in explanations:
            print(
                f"tick={explanation['tick']} "
                f"explanation={explanation['explanation']!r} "
                f"before={tuple(explanation['before'])} "
                f"after={tuple(explanation['after'])} "
                f"elapsed={explanation['elapsed_seconds']:.3f}s"
            )
        for ordering in orderings:
            print(
                f"tick={ordering['tick']} target={ordering['target_id']} "
                f"position={ordering['position_id']} "
                f"presentation={ordering['presentation']} "
                f"elapsed={ordering['elapsed_seconds']:.3f}s"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
