from __future__ import annotations

"""Continue one persisted CassiFI state with raw-byte math training."""

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from cassi_field_cognition import _canonical_semantic_state, semantic_cognition_kernel
from cassi_field_input import semantic_observe_request, source_observation_page
from cassi_field_owner import SourceInput
from cassi_math_language import evaluate, integer_term, parse_latex, validate_math_lessons


DEFAULT_DATASET = Path(
    "D:/carina/workspaces/cassi/datasets/inactive/gsm8k_train.txt"
)
DEFAULT_STATE_INPUT = Path("CassiFI/_diag/math/gsm8k_pilot_state.json")
_BYTE_WINDOW = 16
_OPS: tuple[tuple[str, str, str], ...] = (
    ("add", "+", "plus"),
    ("sub", "-", "minus"),
    ("mul", "*", "times"),
    ("div", "/", "divided by"),
)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    raw = value if isinstance(value, bytes) else _canonical_bytes(value)
    return hashlib.sha256(raw).hexdigest()


def _load_state_checkpoint(path: Path) -> tuple[dict[str, Any], str]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"cannot read state checkpoint {path}: {exc}") from exc
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"state checkpoint {path} is not valid UTF-8 JSON") from exc
    if not isinstance(decoded, Mapping):
        raise ValueError(f"state checkpoint {path} must contain a JSON object")
    try:
        state = _canonical_semantic_state(decoded)
    except Exception as exc:  # noqa: BLE001 - preserve checkpoint rejection detail
        raise ValueError(f"state checkpoint {path} failed semantic validation: {exc}") from exc
    return state, _sha256(raw)


def _write_json_atomic(path: Path, value: Mapping[str, Any]) -> str:
    encoded = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_bytes(encoded)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return _sha256(encoded)

DEFAULT_DATASET = Path(
    "D:/carina/workspaces/cassi/datasets/inactive/gsm8k_train.txt"
)
_BYTE_WINDOW = 16
_OPS: tuple[tuple[str, str, str], ...] = (
    ("add", "+", "plus"),
    ("sub", "-", "minus"),
    ("mul", "*", "times"),
    ("div", "/", "divided by"),
)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    raw = value if isinstance(value, bytes) else _canonical_bytes(value)
    return hashlib.sha256(raw).hexdigest()


def _step(
    state: Mapping[str, Any], request: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    transition = semantic_cognition_kernel(state, request, 4096)
    if transition.status != "done":
        raise RuntimeError(f"byte experiment operation did not finish: {transition.status}")
    return transition.state, transition.output


def _source(content: bytes) -> SourceInput:
    digest = hashlib.sha256(content).hexdigest()
    return SourceInput(
        source_id=f"gsm8k-byte-source-{digest[:16]}",
        content=content,
        media_type="application/octet-stream",
        codec="cassi.codec.opaque-bytes.v1",
        observed_timestamp="2026-09-18T00-00-00Z",
        scope="math-byte-stream",
        claim_category="dataset-bytes",
        fidelity="exact-record",
        labels=("gsm8k", "raw-bytes", "math-equation-training"),
    )


def _integer_role(name: str) -> dict[str, Any]:
    return {
        "kind": "variable",
        "name": name,
        "scope": "role",
        "type": {"kind": "atom", "name": "integer"},
    }


def _term_template(operator: str) -> dict[str, Any]:
    left = _integer_role("left")
    right = _integer_role("right")
    if operator == "sub":
        right = {
            "kind": "constructor",
            "name": "mul",
            "args": [integer_term(-1), right],
        }
        operator = "add"
    return {"kind": "constructor", "name": operator, "args": [left, right]}


def _english(operator: str, left: int, right: int) -> str:
    word = next(word for name, _, word in _OPS if name == operator)
    return f"( {left} {word} {right} )"


def generate_byte_equations(
    content: bytes,
    *,
    byte_budget: int = 524_288,
    examples_per_operator: int = 128,
    byte_offset: int = 0,
) -> dict[str, Any]:
    """Derive deterministic arithmetic rows from one disjoint raw-byte window."""

    if not isinstance(content, bytes) or not content:
        raise ValueError("content must be non-empty bytes")
    if byte_budget < 2 * _BYTE_WINDOW or byte_budget % 2:
        raise ValueError("byte_budget must be an even positive byte count")
    if examples_per_operator < 1:
        raise ValueError("examples_per_operator must be positive")
    if byte_offset < 0 or byte_offset % 64:
        raise ValueError("byte_offset must be a nonnegative multiple of 64")
    if byte_offset >= len(content):
        raise ValueError("byte_offset must be inside the source")
    available = len(content) - byte_offset
    budget = min(byte_budget, available - (available % 2))
    half = budget // 2
    if half < _BYTE_WINDOW:
        raise ValueError("source bytes are too short for the requested window")
    buckets: dict[str, dict[str, list[dict[str, Any]]]] = {
        phase: {name: [] for name, _, _ in _OPS}
        for phase in ("train", "holdout")
    }
    attempted = {"train": 0, "holdout": 0}
    for phase, start, end in (
        ("train", byte_offset, byte_offset + half),
        ("holdout", byte_offset + half, byte_offset + budget),
    ):
        for offset in range(start, end - _BYTE_WINDOW + 1, _BYTE_WINDOW):
            window = content[offset : offset + _BYTE_WINDOW]
            operator = _OPS[
                (window[8] ^ window[9] ^ (offset // _BYTE_WINDOW))
                % len(_OPS)
            ][0]
            bucket = buckets[phase][operator]
            if len(bucket) >= examples_per_operator:
                if all(
                    len(buckets[phase][name]) >= examples_per_operator
                    for name, _, _ in _OPS
                ):
                    break
                continue
            attempted[phase] += 1
            left = 10_000 + int.from_bytes(window[:4], "little") % 80_000
            right = 10_000 + int.from_bytes(window[4:8], "little") % 80_000
            if left == right:
                right += 1
            _, symbol, _ = next(spec for spec in _OPS if spec[0] == operator)
            latex = f"{left}{symbol}{right}"
            expected = evaluate(parse_latex(latex))
            bucket.append(
                {
                    "operator": operator,
                    "bindings": {"left": str(left), "right": str(right)},
                    "english": _english(operator, left, right),
                    "latex": latex,
                    "expected": str(expected),
                    "source_span": [offset, offset + _BYTE_WINDOW],
                    "window_sha256": hashlib.sha256(window).hexdigest(),
                }
            )
        if any(
            len(buckets[phase][name]) < examples_per_operator
            for name, _, _ in _OPS
        ):
            raise ValueError(f"raw bytes did not yield enough {phase} operator examples")
    rows = {
        phase: [row for name, _, _ in _OPS for row in buckets[phase][name]]
        for phase in ("train", "holdout")
    }
    digest_rows = {
        phase: [
            {
                "operator": row["operator"],
                "latex": row["latex"],
                "expected": row["expected"],
                "source_span": row["source_span"],
                "window_sha256": row["window_sha256"],
            }
            for row in rows[phase]
        ]
        for phase in rows
    }
    return {
        "byte_offset": byte_offset,
        "byte_budget": budget,
        "train_bytes": half,
        "holdout_bytes": half,
        "attempted_windows": attempted,
        "rows": rows,
        "equation_digest": _sha256(digest_rows),
    }


def _lesson(
    operator: str,
    rows: Sequence[Mapping[str, Any]],
    holdout: Sequence[Mapping[str, Any]],
    source_revision_id: str,
    source_sha256: str,
    continuation_token: str,
) -> dict[str, Any]:
    examples = [
        {key: row[key] for key in ("bindings", "english", "latex")}
        for row in rows
    ]
    heldout = [
        {key: row[key] for key in ("bindings", "english", "latex")}
        for row in holdout
    ]
    validated = validate_math_lessons(
        template=_term_template(operator),
        examples=examples,
        holdout=heldout,
    )
    span_digest = _sha256([row["source_span"] for row in rows])
    return {
        "construction_id": (
            f"byte_math_{operator}_{source_sha256[:12]}_{continuation_token}"
        ),
        "term_template": validated["term_template"],
        "examples": validated["examples"],
        "holdout": validated["holdout"],
        "operator": operator,
        "support_roots": [source_revision_id],
        "source_policy": {
            "content_admission": "raw-byte-derived-equation",
            "grants_authority": False,
            "source_sha256": source_sha256,
            "training_span_sha256": span_digest,
        },
    }


def _direct_byte_observation(
    state: dict[str, Any],
    source: SourceInput,
    *,
    train_bytes: int,
    byte_offset: int,
    page_size: int,
    operation_prefix: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    start_item = byte_offset // 64
    max_items = min(
        train_bytes // 64,
        (len(source.content) // 64) - start_item,
    )
    cursor = start_item
    end_item = start_item + max_items
    pages = 0
    rows = 0
    statuses: dict[str, int] = {}
    stream_id = f"{operation_prefix}:stream"
    while cursor < end_item:
        page = source_observation_page(
            source,
            cursor=cursor,
            page_size=min(page_size, end_item - cursor),
        )
        request = semantic_observe_request(
            page,
            operation_id=f"{operation_prefix}:observe:{pages}",
            event_id=f"{operation_prefix}:event:{pages}",
            delivery_id=f"{operation_prefix}:delivery:{pages}",
            stream_id=stream_id,
            chunk_index=pages,
        )
        state, result = _step(state, request)
        statuses[result.get("status", "unknown")] = statuses.get(
            result.get("status", "unknown"), 0
        ) + 1
        pages += 1
        rows += len(page["observations"])
        cursor += len(page["observations"])
    return state, {
        "byte_offset": byte_offset,
        "pages": pages,
        "observations": rows,
        "observed_bytes": min(train_bytes, max_items * 64),
        "statuses": statuses,
        "source_revision_id": source.revision_id,
    }


def _interpret(
    state: dict[str, Any],
    row: Mapping[str, Any],
    *,
    operation_id: str,
    support_root: str | None,
    construction_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if construction_id is None:
        request: dict[str, Any] = {
            "operation": "interpret-math",
            "operation_id": operation_id,
            "surface": "english",
            "text": row["english"],
        }
    else:
        request = {
            "operation": "express-math",
            "operation_id": operation_id,
            "construction_id": construction_id,
            "surface": "english",
            "term": row["latex"],
        }
    if support_root is not None:
        request["support_roots"] = [support_root]
    return _step(state, request)




def _evaluate_holdout(
    state: dict[str, Any],
    rows: Sequence[Mapping[str, Any]],
    *,
    support_root: str,
    operation_prefix: str,
    construction_ids: Mapping[str, str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    exact = 0
    supported = 0
    failures: list[dict[str, Any]] = []
    by_operator: dict[str, dict[str, int]] = {}
    for index, row in enumerate(rows):
        operator = str(row["operator"])
        bucket = by_operator.setdefault(
            operator,
            {"submitted": 0, "supported": 0, "exact": 0},
        )
        bucket["submitted"] += 1
        try:
            state, result = _interpret(
                state,
                row,
                operation_id=f"{operation_prefix}:holdout:{index}",
                support_root=support_root,
            )
            status = result.get("status")
            alternatives = result.get("alternatives", [])
            candidate = next(
                (
                    alternative
                    for alternative in alternatives
                    if alternative.get("construction_id")
                    == construction_ids[operator]
                ),
                None,
            )
            if not isinstance(candidate, Mapping):
                failures.append(
                    {
                        "index": index,
                        "operator": operator,
                        "reason": "construction-support-gap",
                        "status": status,
                    }
                )
                continue
            supported += 1
            bucket["supported"] += 1
            expected = evaluate(parse_latex(row["latex"]))
            actual = evaluate(candidate["term"])
            if actual != expected:
                failures.append(
                    {
                        "index": index,
                        "operator": operator,
                        "reason": "value-mismatch",
                        "expected": str(expected),
                        "actual": str(actual),
                    }
                )
                continue
            exact += 1
            bucket["exact"] += 1
        except Exception as exc:  # noqa: BLE001 - receipt records every failed row
            failures.append(
                {
                    "index": index,
                    "operator": operator,
                    "reason": type(exc).__name__,
                    "message": str(exc),
                }
            )
    return state, {
        "submitted": len(rows),
        "supported": supported,
        "exact": exact,
        "by_operator": by_operator,
        "failures": failures[:32],
        "failure_count": len(failures),
    }


def _prepare_continuation_capacity(
    state: dict[str, Any],
    *,
    observations: int,
    pages: int,
    lessons: int,
    holdout_rows: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    starting_records = sum(
        len(history) for history in state["records"].values()
    )
    starting_operations = int(state["ledger"]["transitions"])
    planned_records = starting_records + (observations * 2) + pages + lessons
    planned_operations = starting_operations + pages + lessons + holdout_rows
    before = dict(state["bounds"])
    bounds = dict(before)
    expansions: dict[str, dict[str, int]] = {}
    for name, required in (
        ("max_records", planned_records),
        ("max_operations", planned_operations),
    ):
        if required <= bounds[name]:
            continue
        if required > 65_536:
            raise ValueError(
                f"single-instance continuation exceeds {name}: "
                f"requires {required}, maximum is 65536"
            )
        expansions[name] = {"before": bounds[name], "after": required}
        bounds[name] = required
    state["bounds"] = bounds
    state = _canonical_semantic_state(state)
    return state, {
        "starting_records": starting_records,
        "planned_records": planned_records,
        "starting_operations": starting_operations,
        "planned_operations": planned_operations,
        "bounds_before": before,
        "bounds_after": dict(state["bounds"]),
        "expanded": expansions,
    }


def continue_byte_training(
    path: Path,
    *,
    state_input: Path,
    byte_budget: int = 524_288,
    examples_per_operator: int = 128,
    byte_offset: int = 0,
    page_size: int = 256,
    state_output: Path,
) -> dict[str, Any]:
    content = path.read_bytes()
    source = _source(content)
    source_sha256 = hashlib.sha256(content).hexdigest()
    state, state_input_sha256 = _load_state_checkpoint(state_input)
    starting_operations = int(state["ledger"]["transitions"])
    operation_prefix = (
        f"byte-train:{source.revision_id[:16]}:{starting_operations}"
    )
    continuation_token = f"{source_sha256[:12]}_{starting_operations}"
    generated = generate_byte_equations(
        content,
        byte_budget=byte_budget,
        examples_per_operator=examples_per_operator,
        byte_offset=byte_offset,
    )
    lessons = [
        _lesson(
            operator,
            [row for row in generated["rows"]["train"] if row["operator"] == operator],
            [row for row in generated["rows"]["holdout"] if row["operator"] == operator],
            source.revision_id,
            source_sha256,
            continuation_token,
        )
        for operator, _, _ in _OPS
    ]
    planned_observations = min(
        generated["train_bytes"] // 64,
        len(source.content) // 64,
    )
    planned_pages = (
        (planned_observations + page_size - 1) // page_size
        if planned_observations
        else 0
    )
    state, capacity = _prepare_continuation_capacity(
        state,
        observations=planned_observations,
        pages=planned_pages,
        lessons=len(lessons),
        holdout_rows=len(generated["rows"]["holdout"]),
    )
    state, direct_bytes = _direct_byte_observation(
        state,
        source,
        train_bytes=generated["train_bytes"],
        byte_offset=byte_offset,
        page_size=page_size,
        operation_prefix=operation_prefix,
    )
    lesson_statuses: dict[str, str] = {}
    for lesson in lessons:
        state, result = _step(
            state,
            {
                "operation": "learn-math",
                "operation_id": (
                    f"{operation_prefix}:learn:{lesson['operator']}"
                ),
                "construction_id": lesson["construction_id"],
                "term_template": lesson["term_template"],
                "examples": lesson["examples"],
                "holdout": lesson["holdout"],
                "support_roots": lesson["support_roots"],
                "source_policy": lesson["source_policy"],
            },
        )
        lesson_statuses[lesson["operator"]] = str(result.get("status", "unknown"))
    state, holdout = _evaluate_holdout(
        state,
        generated["rows"]["holdout"],
        support_root=source.revision_id,
        operation_prefix=operation_prefix,
        construction_ids={
            lesson["operator"]: lesson["construction_id"] for lesson in lessons
        },
    )
    state_output_sha256 = _write_json_atomic(state_output, state)
    receipt: dict[str, Any] = {
        "schema": "cassifi.math-byte-training.v2",
        "continuation": {
            "batch_id": operation_prefix,
            "state_input": str(state_input),
            "state_input_sha256": state_input_sha256,
            "state_output": str(state_output),
            "state_output_sha256": state_output_sha256,
            "starting_transitions": starting_operations,
            "final_transitions": int(state["ledger"]["transitions"]),
            "capacity": capacity,
        },
        "source": {
            "path": str(path),
            "source_id": source.source_id,
            "revision_id": source.revision_id,
            "sha256": source_sha256,
            "byte_length": len(content),
            "codec": source.codec,
        },
        "byte_split": {
            "byte_offset": generated["byte_offset"],
            "total_budget": generated["byte_budget"],
            "train_bytes": generated["train_bytes"],
            "holdout_bytes": generated["holdout_bytes"],
            "window_bytes": _BYTE_WINDOW,
        },
        "direct_byte_intake": direct_bytes,
        "generation": {
            "examples_per_operator": examples_per_operator,
            "train_rows": len(generated["rows"]["train"]),
            "holdout_rows": len(generated["rows"]["holdout"]),
            "attempted_windows": generated["attempted_windows"],
            "equation_digest": generated["equation_digest"],
            "operators": [name for name, _, _ in _OPS],
            "sample": {
                phase: {
                    operator: [
                        row
                        for row in generated["rows"][phase]
                        if row["operator"] == operator
                    ][:2]
                    for operator, _, _ in _OPS
                }
                for phase in ("train", "holdout")
            },
        },
        "learning": {
            "lessons_submitted": len(lessons),
            "lesson_statuses": lesson_statuses,
            "support_root": source.revision_id,
        },
        "holdout": holdout,
        "state_operation_count": int(state["ledger"]["transitions"]),
        "boundaries": [
            "the only adaptive state was loaded from the supplied checkpoint",
            "raw source bytes entered through the exact opaque-byte source codec",
            "equations were generated deterministically from byte windows; no GSM8K text parser was used",
            "holdout windows were disjoint from directly observed training bytes",
            "successful arithmetic replay does not establish natural-language word-problem understanding",
        ],
        "state_checkpoint": str(state_output),
    }
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument(
        "--state-input",
        type=Path,
        default=DEFAULT_STATE_INPUT,
        help="existing canonical field checkpoint to continue",
    )
    parser.add_argument("--byte-budget", type=int, default=524_288)
    parser.add_argument("--examples-per-operator", type=int, default=128)
    parser.add_argument("--byte-offset", type=int, default=0)
    parser.add_argument("--page-size", type=int, default=256)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--state-output",
        type=Path,
        required=True,
        help="successor checkpoint written atomically",
    )
    args = parser.parse_args()
    if args.byte_budget < 2 * _BYTE_WINDOW or args.byte_budget % 2:
        parser.error("--byte-budget must be an even value of at least 32")
    if args.byte_offset < 0 or args.byte_offset % 64:
        parser.error("--byte-offset must be a nonnegative multiple of 64")
    if args.examples_per_operator < 1:
        parser.error("--examples-per-operator must be positive")
    if not 1 <= args.page_size <= 256:
        parser.error("--page-size must be in 1..256")
    receipt = continue_byte_training(
        args.dataset,
        state_input=args.state_input,
        byte_budget=args.byte_budget,
        examples_per_operator=args.examples_per_operator,
        byte_offset=args.byte_offset,
        page_size=args.page_size,
        state_output=args.state_output,
    )
    encoded = json.dumps(receipt, indent=2, sort_keys=True)
    if args.output is not None:
        _write_json_atomic(args.output, receipt)
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
