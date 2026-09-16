"""Run the atlas-owned learning computer through its public operation surface.

Input may be a structured field-language document, a raw ``program`` of
five-integer instruction rows, or a ``turing_machine`` declaration. Structured
functions and control forms compile deterministically into the same closed six
primitive instructions. Raw/Turing documents retain their optional stack and
entry fields. No program can invoke host files, networks, or processes.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from cassi_field_input import CODEC_TEXT
from cassi_field_owner import (
    FieldIntelligenceError,
    FieldIntelligenceOwner,
    FieldIntelligenceSurface,
    RPC_SCHEMA,
    SourceInput,
)


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("input must be a JSON object")
    return value


def program_arguments(value: Mapping[str, Any]) -> dict[str, Any]:
    from cassi_field_program import SCHEMA as STRUCTURED_SCHEMA, compile_structured_program
    if value.get("schema") == STRUCTURED_SCHEMA:
        compiled = compile_structured_program(value)
        return {
            "program": compiled.program,
            "entry": compiled.entry,
            "left": compiled.left,
            "right": compiled.right,
        }
    if "turing_machine" not in value:
        if "program" not in value or set(value) - {"program", "left", "right", "entry"}:
            raise ValueError("program document has invalid keys")
        return dict(value)
    if set(value) - {"turing_machine", "tape", "left"}:
        raise ValueError("Turing program document has invalid keys")
    from cassi_field_computer import compile_turing_machine
    source = value["turing_machine"]
    if not isinstance(source, Mapping) or "transitions" not in source:
        raise ValueError("turing_machine requires transition rows")
    if set(source) - {"transitions", "start_state", "halt_states", "blank", "alphabet_size"}:
        raise ValueError("Turing machine declaration has invalid keys")
    transitions = {}
    for row in source["transitions"]:
        if not isinstance(row, (tuple, list)) or len(row) != 5:
            raise ValueError("transition must be [state, symbol, next, write, direction]")
        key = (row[0], row[1])
        if key in transitions:
            raise ValueError("duplicate Turing transition")
        transitions[key] = (row[2], row[3], row[4])
    options = {key: item for key, item in source.items() if key != "transitions"}
    compiled = compile_turing_machine(transitions, **options)
    tape = value.get("tape", [])
    left = value.get("left", [])
    alphabet_size = source.get("alphabet_size", 2)
    for name, symbols in (("tape", tape), ("left", left)):
        if not isinstance(symbols, list) or any(
            isinstance(symbol, bool) or not isinstance(symbol, int) or not 0 <= symbol < alphabet_size
            for symbol in symbols
        ):
            raise ValueError(f"{name} must contain only declared alphabet symbols")
    return {"program": compiled.program, "entry": compiled.entry,
            "left": left, "right": list(reversed(tape))}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-home", type=Path, required=True, help="persistent atlas directory")
    parser.add_argument("--computer-id", default="main")
    parser.add_argument("--operation-id", help="reuse this identity when retrying the exact same operation")
    parser.add_argument("--expected-state-sha256")
    parser.add_argument("--output", type=Path, help="write the complete JSON response here")
    actions = parser.add_subparsers(dest="action", required=True)
    configure = actions.add_parser("configure")
    configure.add_argument("--program-capacity", type=int, default=1024)
    configure.add_argument("--stack-capacity", type=int, default=4096)
    configure.add_argument(
        "--max-steps",
        type=int,
        default=1000000,
        help=(
            "lifetime primitive-transition ceiling for a loaded program; "
            "grow it to resume step-budget exhaustion"
        ),
    )
    load = actions.add_parser("load")
    load.add_argument("program", type=Path)
    advance = actions.add_parser("advance")
    advance.add_argument(
        "--steps",
        type=int,
        default=4096,
        help=(
            "per-operation transition allowance; the owner operator limit "
            "may be lower than the computer's lifetime --max-steps"
        ),
    )
    submit = actions.add_parser(
        "submit",
        help="start one typed fixed-catalog regional task",
    )
    submit.add_argument("kernel")
    submit.add_argument("state", type=Path)
    submit.add_argument("--kind")
    submit.add_argument("--steps", type=int, default=1)
    submit.add_argument(
        "--arguments",
        type=Path,
        help="JSON operation arguments delivered with the first kernel transition",
    )
    invoke = actions.add_parser(
        "invoke",
        help="resume the resident regional family state with typed arguments",
    )
    invoke.add_argument("arguments", type=Path)
    invoke.add_argument("--steps", type=int, default=1)
    authorized = actions.add_parser(
        "authorized-invoke",
        help="resume a pending machine proposal through the owner authority boundary",
    )
    authorized.add_argument("arguments", type=Path)
    authorized.add_argument("grant", type=Path)
    authorized.add_argument("target")
    authorized.add_argument("scope")
    authorized.add_argument("--steps", type=int, default=1)
    restart = actions.add_parser("restart")
    restart.add_argument("--left", type=int, action="append", default=[])
    restart.add_argument("--right", type=int, action="append", default=[])
    restart.add_argument("--entry", type=int, default=0)
    grow = actions.add_parser("grow")
    grow.add_argument("--stack-capacity", type=int, required=True)
    grow.add_argument("--max-steps", type=int)
    source_input = actions.add_parser(
        "input",
        help="store exact bytes and admit one bounded typed page to cognition",
    )
    source_input.add_argument("source", help="source file, or - for standard input")
    source_input.add_argument("--codec", default=CODEC_TEXT)
    source_input.add_argument("--media-type", default="text/plain")
    source_input.add_argument("--source-id")
    source_input.add_argument("--observed-timestamp")
    source_input.add_argument("--scope", default="world")
    source_input.add_argument("--claim-category", default="observation")
    source_input.add_argument("--fidelity", default="exact")
    source_input.add_argument("--parent-revision-id")
    source_input.add_argument("--label", action="append", default=[])
    source_input.add_argument("--cursor", type=int, default=0)
    source_input.add_argument("--page-size", type=int, default=128)
    source_input.add_argument("--shape", type=int, nargs="*")
    source_input.add_argument("--dtype")
    source_input.add_argument("--unit", action="append", default=[])
    source_input.add_argument("--stream-id")
    source_input.add_argument("--chunk-index", type=int)
    source_input.add_argument("--steps", type=int, default=4096)
    solve = actions.add_parser("solve")
    solve.add_argument("source", type=Path)
    solve.add_argument(
        "--budget",
        type=int,
        default=2000,
        help=(
            "shared selector, inference, search, and controller work ceiling; "
            "also bounded by the owner's operator limit"
        ),
    )
    solve.add_argument("--no-learn", action="store_true")
    solve.add_argument("--method", help="force one supported method instead of field selection")
    continuation = actions.add_parser(
        "continue-solve",
        help="resume the exact retained solver field",
    )
    continuation.add_argument("source", type=Path)
    continuation.add_argument(
        "--budget",
        type=int,
        default=2000,
        help="work allowance for this continuation episode",
    )
    actions.add_parser("inspect")
    explain = actions.add_parser(
        "explain",
        help="project the field evidence and next method without changing state",
    )
    explain.add_argument("source", type=Path)
    explain.add_argument("--budget", type=int, default=2000)
    explain.add_argument(
        "--no-explore",
        action="store_true",
        help="show the empirical/incumbent choice without a challenger",
    )
    args = parser.parse_args(argv)
    try:
        arguments: dict[str, Any] = {}
        if args.action == "configure":
            arguments["profile"] = {"program_capacity": args.program_capacity,
                                    "stack_capacity": args.stack_capacity, "max_steps": args.max_steps}
        elif args.action == "load":
            arguments = program_arguments(_object(args.program))
        elif args.action == "advance":
            arguments = {"steps": args.steps}
        elif args.action == "submit":
            arguments = {
                "kernel": args.kernel,
                "state": _object(args.state),
                "steps": args.steps,
            }
            if args.kind is not None:
                arguments["kind"] = args.kind
            if args.arguments is not None:
                arguments["arguments"] = _object(args.arguments)
        elif args.action == "invoke":
            arguments = {
                "arguments": _object(args.arguments),
                "steps": args.steps,
            }
        elif args.action == "authorized-invoke":
            arguments = {
                "arguments": _object(args.arguments),
                "grant": _object(args.grant),
                "target": args.target,
                "scope": args.scope,
                "steps": args.steps,
            }
        elif args.action == "restart":
            arguments = {"left": args.left, "right": args.right, "entry": args.entry}
        elif args.action == "grow":
            arguments = {"stack_capacity": args.stack_capacity}
            if args.max_steps is not None:
                arguments["max_steps"] = args.max_steps
        elif args.action == "input":
            source_path = str(args.source)
            if source_path == "-":
                content = sys.stdin.buffer.read()
                default_source_id = "stdin"
            else:
                input_path = Path(source_path)
                content = input_path.read_bytes()
                default_source_id = input_path.as_posix()
            exact_source = SourceInput(
                source_id=args.source_id or default_source_id,
                content=content,
                media_type=args.media_type,
                codec=args.codec,
                observed_timestamp=(
                    args.observed_timestamp
                    or datetime.now(timezone.utc).isoformat()
                ),
                scope=args.scope,
                claim_category=args.claim_category,
                fidelity=args.fidelity,
                parent_revision_id=args.parent_revision_id,
                labels=tuple(args.label),
            )
            arguments = {
                "source": exact_source.as_dict(),
                "cursor": args.cursor,
                "page_size": args.page_size,
                "shape": args.shape,
                "dtype": args.dtype,
                "units": args.unit,
                "stream_id": args.stream_id,
                "chunk_index": args.chunk_index,
                "steps": args.steps,
            }
        elif args.action == "solve":
            arguments = {"source": _object(args.source), "budget": args.budget,
                         "learn": not args.no_learn, "method": args.method}
        elif args.action == "continue-solve":
            arguments = {
                "source": _object(args.source),
                "budget": args.budget,
            }
        elif args.action == "explain":
            arguments = {
                "source": _object(args.source),
                "budget": args.budget,
                "explore": not args.no_explore,
            }
        operation_id = args.operation_id or "computer:" + uuid.uuid4().hex
        if args.action == "inspect":
            operation, params = "inspect_computers", {}
        elif args.action == "explain":
            operation = "inspect_computer_policy"
            params = {
                "computer_id": args.computer_id,
                **arguments,
            }
        elif args.action == "input":
            operation = "computer_input"
            params = {
                "operation_id": operation_id,
                "computer_id": args.computer_id,
                **arguments,
                "expected_state_sha256": args.expected_state_sha256,
            }
        else:
            operation = "computer"
            params = {
                "operation_id": operation_id,
                "computer_id": args.computer_id,
                "action": args.action,
                "arguments": arguments,
                "expected_state_sha256": args.expected_state_sha256,
            }
        started = time.perf_counter_ns()
        with FieldIntelligenceOwner(args.data_home) as owner:
            response = FieldIntelligenceSurface(owner).handle({
                "schema": RPC_SCHEMA, "request_id": operation_id,
                "operation": operation, "params": params,
            })
        output = {"response": response, "invocation_elapsed_ns": time.perf_counter_ns() - started}
        encoded = json.dumps(output, sort_keys=True, indent=2) + "\n"
        if args.output is None:
            print(encoded, end="")
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(encoded, encoding="utf-8")
            print(json.dumps({"output": str(args.output), "operation_id": operation_id}))
        return 0
    except (FieldIntelligenceError, OSError, TypeError, ValueError) as exc:
        print(json.dumps({"error": getattr(exc, "code", type(exc).__name__), "message": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
