"""Verify the passive trajectory recorder's hook structure in the physics engine.

Usage:
    python research/matter_formation/verify_recorder_hooks.py [engine.gd]

The recorder dispatches into the open compute list at four points, and every one
of them is an ordering constraint rather than a single line: the hook runs after
the physics dispatch it observes, and the barrier that follows it keeps the
recorder from reading a list that is still being built. Line-count and keyword
comparisons do not see those constraints, so this script asserts them directly as
ordered subsequences inside each enclosing function.

Exit code 0 when all four hooks match, 1 with the failing pattern otherwise.
"""

import sys
from pathlib import Path

DEFAULT_ENGINE = Path(__file__).resolve().parents[2] / "scripts/cassi_physics_engine.gd"

## A required statement is a prefix string, or a tuple of alternatives when the
## engine surface itself may differ between trees.
Step = str | tuple[str, ...]

## (label, enclosing function, ordered statement prefixes that must appear in
## that order inside the function).
HOOKS = (
    (
        "start",
        "record_pending_steps",
        (
            "if trajectory_enabled and not field_particles and not _trajectory_started:",
            "_trajectory_dispatch(cl, 0.0, 0)",
            "_barrier(cl)",
            "_trajectory_started = true",
        ),
    ),
    (
        "per-step",
        "record_pending_steps",
        (
            ## The committed engine calls the step dispatch directly; the
            ## working-tree engine wraps the same call in a condition that ends
            ## the batch. The hook must follow that call either way.
            ("_step_dispatches(cl)", "if not _step_dispatches(cl):"),
            "if trajectory_enabled and not field_particles:",
            "_trajectory_dispatch(cl, 1.0, _step_count)",
            "_barrier(cl)",
        ),
    ),
    (
        "merge-cycle",
        "record_merge_if_due",
        (
            "_merge_bind_dispatch(cl, 4.0, pair_phase)",
            "if trajectory_enabled:",
            "_trajectory_dispatch(cl, 2.0, _step_count)",
            "_barrier(cl)",
            "_merge_bind_dispatch(cl, 6.0)",
        ),
    ),
    (
        "merge-hop",
        "_run_merge_pass",
        (
            "_merge_bind_dispatch(cl, 5.0, cyc + c)",
            "_rd.compute_list_add_barrier(cl)",
            "if trajectory_enabled:",
            "# Capture this hop before the next cycle",
            "_trajectory_dispatch(cl, 2.0, _step_count)",
            "_barrier(cl)",
            "_rd.compute_list_end()",
        ),
    ),
)


def function_scope(lines: list[str], name: str) -> tuple[int, int]:
    start = next(
        (i for i, line in enumerate(lines) if line.startswith(f"func {name}(")), None
    )
    if start is None:
        raise SystemExit(f"engine has no function {name}()")
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith("func ")), len(lines)
    )
    return start, end


def verify(
    lines: list[str], label: str, function: str, steps: tuple[Step, ...]
) -> bool:
    start, end = function_scope(lines, function)
    cursor = start
    for step in steps:
        alternatives = (step,) if isinstance(step, str) else step
        found = next(
            (
                i
                for i in range(cursor, end)
                if any(lines[i].strip().startswith(alt) for alt in alternatives)
            ),
            -1,
        )
        if found < 0:
            print(
                f"  {label:<12} FAIL: {function}() has no {' or '.join(map(repr, alternatives))} "
                "after the previous step"
            )
            return False
        cursor = found + 1
    print(f"  {label:<12} OK   {len(steps)} ordered statements in {function}()")
    return True


def main(argv: list[str]) -> int:
    engine = Path(argv[1]) if len(argv) > 1 else DEFAULT_ENGINE
    lines = engine.read_text(encoding="utf-8").splitlines()
    print(f"recorder hooks in {engine}:")
    results = [verify(lines, label, function, steps) for label, function, steps in HOOKS]
    print("PASS: all four hooks ordered as registered" if all(results) else "FAIL")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
