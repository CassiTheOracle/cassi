"""Independent semantic verifier for :mod:`cassi_field_computer`.

The reference machines in this file are deliberately small and boring.  They
are written from the public instruction/Turing-machine vocabulary rather than
from implementation constants or private state, and are used to compare every
observable primitive transition and every compiled-TM boundary.  For each
arbitrary finite table, the boundary loop checks the base configuration and
then one generated instruction block at a time; that is the compiler
simulation induction relevant to universality, not a finite-run claim about a
hardcoded universal toy.
The command line entry point prints one JSON verification report and returns
non-zero when any semantic or integrity check fails::

    python verify_field_computer.py [--json PATH]
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from cassi_field_computer import ComputerProfile, FieldComputer, compile_turing_machine


# Public vocabulary copied from the written contract, not imported from the
# implementation.  Keeping these here makes the reference executable if an
# implementation accidentally changes or omits its exports.
REF_HALT = 0
REF_PUSH = 1
REF_POP = 2
REF_BRANCH = 3
REF_PUSH_ACC = 4
REF_JUMP = 5
REF_EMPTY = 256
REF_ALPHABET = range(256)


class ReferenceError_(ValueError):
    """The independent reference does not define a malformed input."""


@dataclass(frozen=True)
class RefState:
    program: tuple[tuple[int, int, int, int, int], ...]
    pc: int
    left: tuple[int, ...]
    right: tuple[int, ...]
    accumulator: int
    status: str = "running"
    reason: str | None = None
    transitions: int = 0
    stack_reads: int = 0
    stack_writes: int = 0


def _canonical_instruction(row: Sequence[int]) -> tuple[int, int, int, int, int]:
    if len(row) != 5:
        raise ReferenceError_(f"instruction must contain five integers: {row!r}")
    if any(isinstance(original, bool) or not isinstance(original, int) for original in row):
        raise ReferenceError_(f"instruction contains a non-integral value: {row!r}")
    values = tuple(int(value) for value in row)
    opcode, a, b, c, d = values
    if opcode not in (REF_HALT, REF_PUSH, REF_POP, REF_BRANCH, REF_PUSH_ACC, REF_JUMP):
        raise ReferenceError_(f"unknown opcode {opcode}")
    if opcode == REF_HALT and values != (REF_HALT, 0, 0, 0, 0):
        raise ReferenceError_("HALT has unused operands")
    if opcode == REF_PUSH and (a not in (0, 1) or b not in REF_ALPHABET or d != 0):
        raise ReferenceError_("malformed PUSH")
    if opcode == REF_POP and (a not in (0, 1) or c != 0 or d != 0):
        raise ReferenceError_("malformed POP")
    if opcode == REF_BRANCH and (a not in (*REF_ALPHABET, REF_EMPTY) or d != 0):
        raise ReferenceError_("malformed BRANCH")
    if opcode == REF_PUSH_ACC and (a not in (0, 1) or c != 0 or d != 0):
        raise ReferenceError_("malformed PUSH_ACC")
    if opcode == REF_JUMP and (a < 0 or b != 0 or c != 0 or d != 0):
        raise ReferenceError_("malformed JUMP")
    return (values[0], values[1], values[2], values[3], values[4])


def validate_reference_program(
    program: Sequence[Sequence[int]], *, program_capacity: int | None = None
) -> tuple[tuple[int, int, int, int, int], ...]:
    rows = tuple(_canonical_instruction(row) for row in program)
    if not rows:
        raise ReferenceError_("program is empty")
    if program_capacity is not None and len(rows) > program_capacity:
        raise ReferenceError_("program exceeds capacity")
    for index, row in enumerate(rows):
        opcode, a, b, c, d = row
        targets: tuple[int, ...]
        if opcode == REF_PUSH:
            targets = (c,)
        elif opcode == REF_POP:
            targets = (b,)
        elif opcode == REF_BRANCH:
            targets = (b, c)
        elif opcode == REF_JUMP:
            targets = (a,)
        else:
            targets = ()
        for target in targets:
            if not 0 <= target < len(rows):
                raise ReferenceError_(f"instruction {index} targets {target}")
    return rows


def reference_initial(
    program: Sequence[Sequence[int]],
    *,
    left: Sequence[int] = (),
    right: Sequence[int] = (),
    entry: int = 0,
    max_steps: int = 1_000_000,
    stack_capacity: int = 4_096,
) -> RefState:
    rows = validate_reference_program(program)
    if not 0 <= entry < len(rows):
        raise ReferenceError_("entry outside program")
    if max_steps < 0 or stack_capacity <= 0:
        raise ReferenceError_("limits must be nonnegative/positive")
    if len(left) > stack_capacity or len(right) > stack_capacity:
        raise ReferenceError_("initial stack exceeds capacity")
    for stack in (left, right):
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value not in REF_ALPHABET
            for value in stack
        ):
            raise ReferenceError_("invalid stack symbol")
    initial_status = (
        "exhausted" if max_steps == 0 and rows[entry][0] != REF_HALT
        else ("halted" if rows[entry][0] == REF_HALT else "running")
    )
    initial_reason = (
        "max_steps" if initial_status == "exhausted"
        else ("halt" if initial_status == "halted" else None)
    )
    return RefState(
        rows,
        entry,
        tuple(int(value) for value in left),
        tuple(int(value) for value in right),
        REF_EMPTY,
        status=initial_status,
        reason=initial_reason,
    )


def reference_step(state: RefState, *, max_steps: int = 1_000_000, stack_capacity: int = 4_096) -> RefState:
    """Execute one reference transition, including deterministic faults/bounds."""

    if state.status != "running":
        return state
    if state.transitions >= max_steps:
        return replace(state, status="exhausted", reason="max_steps")
    if not 0 <= state.pc < len(state.program):
        return replace(state, status="faulted", reason="pc_out_of_range")

    opcode, a, b, c, d = state.program[state.pc]
    _ = d
    common = dict(transitions=state.transitions + 1)
    if opcode == REF_HALT:
        return replace(state, status="halted", reason="halt", **common)
    if opcode == REF_PUSH:
        stack = state.left if a == 0 else state.right
        if len(stack) >= stack_capacity:
            return replace(state, status="exhausted", reason="stack_capacity")
        updated = stack + (b,)
        common["stack_writes"] = state.stack_writes + 1
        if a == 0:
            return replace(state, pc=c, left=updated, **common)
        return replace(state, pc=c, right=updated, **common)
    if opcode == REF_POP:
        stack = state.left if a == 0 else state.right
        common["stack_reads"] = state.stack_reads + 1
        if stack:
            accumulator = stack[-1]
            updated = stack[:-1]
        else:
            accumulator = REF_EMPTY
            updated = stack
        if a == 0:
            return replace(state, pc=b, left=updated, accumulator=accumulator, **common)
        return replace(state, pc=b, right=updated, accumulator=accumulator, **common)
    if opcode == REF_BRANCH:
        return replace(state, pc=b if state.accumulator == a else c, **common)
    if opcode == REF_PUSH_ACC:
        if state.accumulator == REF_EMPTY:
            return replace(state, status="faulted", reason="push_empty", **common)
        stack = state.left if a == 0 else state.right
        if len(stack) >= stack_capacity:
            return replace(state, status="exhausted", reason="stack_capacity")
        updated = stack + (state.accumulator,)
        common["stack_writes"] = state.stack_writes + 1
        if a == 0:
            return replace(state, pc=b, left=updated, **common)
        return replace(state, pc=b, right=updated, **common)
    if opcode == REF_JUMP:
        return replace(state, pc=a, **common)
    raise ReferenceError_(f"unreachable opcode {opcode}")


def _info(machine: FieldComputer, state: Any) -> dict[str, Any]:
    info = machine.inspect(state)
    if not isinstance(info, Mapping):
        raise AssertionError("inspect() did not return a mapping")
    required = ("status", "pc", "accumulator", "left", "right", "resource_ledger", "field_bytes")
    missing = [key for key in required if key not in info]
    if missing:
        raise AssertionError(f"inspect() missing keys {missing}")
    ledger = info["resource_ledger"]
    if not isinstance(ledger, Mapping):
        raise AssertionError("resource_ledger is not a mapping")
    for key in ("transitions", "stack_reads", "stack_writes", "field_cells_copied"):
        if key not in ledger:
            raise AssertionError(f"resource ledger missing {key}")
    if hasattr(state, "nbytes") and int(info["field_bytes"]) != int(state.nbytes):
        raise AssertionError("inspect field_bytes disagrees with state.nbytes")
    return dict(info)


def semantic_snapshot(info: Mapping[str, Any]) -> tuple[Any, ...]:
    ledger = info["resource_ledger"]
    return (
        str(info["status"]),
        int(info["pc"]),
        int(info["accumulator"]),
        tuple(int(value) for value in info["left"]),
        tuple(int(value) for value in info["right"]),
        int(ledger["transitions"]),
        int(ledger["stack_reads"]),
        int(ledger["stack_writes"]),
    )


def reference_snapshot(state: RefState) -> tuple[Any, ...]:
    return (
        state.status,
        state.pc,
        state.accumulator,
        state.left,
        state.right,
        state.transitions,
        state.stack_reads,
        state.stack_writes,
    )

def _assert_semantics(machine: FieldComputer, state: Any, ref: RefState, label: str) -> None:
    actual_info = _info(machine, state)
    actual = semantic_snapshot(actual_info)
    expected = reference_snapshot(ref)
    if actual != expected:
        raise AssertionError(f"{label}: actual {actual!r} != reference {expected!r}")
    if actual_info["status"] != "running" and not actual_info.get("reason"):
        raise AssertionError(f"{label}: terminal status has no reason")
def _run_primitive_equivalence(
    program: Sequence[Sequence[int]],
    *,
    left: Sequence[int] = (),
    right: Sequence[int] = (),
    max_steps: int = 1_000,
    stack_capacity: int = 64,
    label: str = "program",
) -> dict[str, Any]:
    profile = ComputerProfile(
        program_capacity=max(32, len(program) + 4),
        stack_capacity=stack_capacity,
        max_steps=max_steps,
    )
    machine = FieldComputer(profile)
    state = machine.initial(program, left=left, right=right)
    ref = reference_initial(
        program,
        left=left,
        right=right,
        max_steps=max_steps,
        stack_capacity=stack_capacity,
    )
    _assert_semantics(machine, state, ref, f"{label}/initial")
    previous_copy = _counter_value(_info(machine, state), "field_cells_copied")
    visited = 0
    while True:
        status = _info(machine, state)["status"]
        if status != "running":
            break
        state, event = machine.step(state)
        if event is None:
            raise AssertionError(f"{label}: step returned no event")
        ref = reference_step(ref, max_steps=max_steps, stack_capacity=stack_capacity)
        visited += 1
        current_copy = _counter_value(_info(machine, state), "field_cells_copied")
        if current_copy <= previous_copy:
            raise AssertionError(f"{label}: field copy ledger did not advance")
        previous_copy = current_copy
        _assert_semantics(machine, state, ref, f"{label}/step-{visited}")
        if visited > max_steps + 20:
            raise AssertionError(f"{label}: primitive run did not terminate at its bound")
    final = _info(machine, state)
    if final["status"] not in ("halted", "exhausted", "faulted"):
        raise AssertionError(f"{label}: invalid terminal status {final['status']!r}")
    return {"steps": visited, "status": final["status"], "pc": final["pc"]}


def _expect_rejection(call: Callable[[], Any]) -> str | None:
    try:
        call()
    except Exception as exc:  # validation type is intentionally public-API agnostic
        return type(exc).__name__
    return None


def _counter_value(info: Mapping[str, Any], key: str) -> int:
    return int(info["resource_ledger"][key])


# ---------------------------------------------------------------------------
# Independent Turing-machine model and boundary codec
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RefTM:
    state: int
    head: int
    tape: tuple[tuple[int, int], ...]  # sparse, sorted (position, symbol)

    def value(self, position: int, blank: int) -> int:
        return dict(self.tape).get(position, blank)

    def write(self, position: int, symbol: int) -> "RefTM":
        cells = dict(self.tape)
        cells[position] = symbol
        return RefTM(self.state, self.head, tuple(sorted(cells.items())))


def tm_step(
    current: RefTM,
    transitions: Mapping[tuple[int, int], tuple[int, int, str]],
    *,
    blank: int,
    halt_states: Sequence[int],
) -> RefTM:
    if current.state in halt_states:
        return current
    symbol = current.value(current.head, blank)
    try:
        next_state, write_symbol, direction = transitions[(current.state, symbol)]
    except KeyError as exc:
        raise ReferenceError_(f"missing transition {(current.state, symbol)!r}") from exc
    result = current.write(current.head, int(write_symbol))
    delta = {"L": -1, "R": 1, "S": 0}[str(direction)]
    return RefTM(int(next_state), current.head + delta, result.tape)


def _expected_stacks(model: RefTM, *, blank: int) -> tuple[tuple[int, ...], tuple[int, ...]]:
    cells = dict(model.tape)
    nonblank = [position for position, symbol in cells.items() if symbol != blank]
    minimum = min(nonblank + [model.head])
    maximum = max(nonblank + [model.head])
    left = tuple(cells.get(position, blank) for position in range(minimum, model.head))
    right_top_first = tuple(cells.get(position, blank) for position in range(model.head, maximum + 1))
    return left, right_top_first


def _canonical_boundary(info: Mapping[str, Any], *, blank: int) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Drop only far-edge implicit blanks, retaining the head cell and left edge."""
    left = list(int(value) for value in info["left"])
    right_top_first = list(reversed(tuple(int(value) for value in info["right"]))) or [blank]
    while left and left[0] == blank:
        left.pop(0)
    while len(right_top_first) > 1 and right_top_first[-1] == blank:
        right_top_first.pop()
    return tuple(left), tuple(right_top_first)


def _run_tm_case(
    name: str,
    transitions: Mapping[tuple[int, int], tuple[int, int, str]],
    tape: Sequence[int],
    *,
    blank: int,
    alphabet_size: int,
    start_state: int = 0,
    halt_states: Sequence[int] = (1,),
    max_steps: int = 20_000,
    expect_status: str | None = "halted",
    tm_steps: int | None = None,
) -> dict[str, Any]:
    if tm_steps is not None and tm_steps < 0:
        raise ValueError("tm_steps must be nonnegative")
    compiled = compile_turing_machine(
        transitions,
        start_state=start_state,
        halt_states=tuple(halt_states),
        blank=blank,
        alphabet_size=alphabet_size,
    )
    if not isinstance(compiled.program, tuple) or not isinstance(compiled.state_entries, Mapping):
        raise AssertionError(f"{name}: compiler result is not a public compiled machine")
    profile = ComputerProfile(
        program_capacity=max(128, len(compiled.program) + 8),
        stack_capacity=max(32, len(tape) + 16),
        max_steps=max_steps,
    )
    machine = FieldComputer(profile)
    # The public stack contract is bottom-to-top.  The TM contract says the
    # head is the top of stack 1, so a head-right input is reversed here.
    state = machine.initial(compiled.program, right=tuple(reversed(tuple(tape))), entry=compiled.entry)
    reverse_entries = {int(pc): int(tm_state) for tm_state, pc in compiled.state_entries.items()}
    expected = RefTM(start_state, 0, tuple((index, int(symbol)) for index, symbol in enumerate(tape)))
    boundaries = 0
    primitive_steps = 0
    while primitive_steps <= max_steps + 100:
        info = _info(machine, state)
        status = str(info["status"])
        if status != "running":
            if expect_status is not None and status != expect_status:
                raise AssertionError(f"{name}: expected {expect_status}, got {status}")
            if status == "halted" and (
                expected.state not in halt_states or reverse_entries.get(int(info["pc"])) != expected.state
            ):
                raise AssertionError(f"{name}: terminal control state differs from reference")
            expected_left, expected_right = _expected_stacks(expected, blank=blank)
            actual = _canonical_boundary(info, blank=blank)
            expected_canonical = (
                tuple(expected_left),
                tuple(expected_right),
            )
            if actual != expected_canonical:
                raise AssertionError(f"{name}: terminal tape {actual!r} != {expected_canonical!r}")
            break
        pc = int(info["pc"])
        if pc in reverse_entries:
            observed_tm_state = reverse_entries[pc]
            if observed_tm_state != expected.state:
                raise AssertionError(
                    f"{name}: boundary state {observed_tm_state} != reference {expected.state}"
                )
            expected_left, expected_right = _expected_stacks(expected, blank=blank)
            actual = _canonical_boundary(info, blank=blank)
            if actual != (expected_left, expected_right):
                raise AssertionError(
                    f"{name}: boundary tape {actual!r} != {(expected_left, expected_right)!r}"
                )
            boundaries += 1
            if tm_steps is not None and boundaries > tm_steps:
                return {
                    "primitive_steps": primitive_steps,
                    "boundaries": boundaries,
                    "status": status,
                    "final_pc": info["pc"],
                }
            if expected.state in halt_states:
                if tuple(compiled.program[pc]) != (REF_HALT, 0, 0, 0, 0):
                    raise AssertionError(f"{name}: halting boundary is not a HALT instruction")
            else:
                expected = tm_step(
                    expected,
                    transitions,
                    blank=blank,
                    halt_states=halt_states,
                )
        state, event = machine.step(state)
        if event is None:
            raise AssertionError(f"{name}: compiler step returned no event")
        primitive_steps += 1
    else:
        raise AssertionError(f"{name}: compiler did not reach terminal status within bound")
    return {
        "primitive_steps": primitive_steps,
        "boundaries": boundaries,
        "status": _info(machine, state)["status"],
        "final_pc": _info(machine, state)["pc"],
    }


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


class Report:
    def __init__(self) -> None:
        self.checks: list[dict[str, Any]] = []

    def add(self, name: str, fn: Callable[[], Mapping[str, Any] | None]) -> None:
        try:
            detail = dict(fn() or {})
        except Exception as exc:  # a crashed check is itself a failed result
            self.checks.append(
                {
                    "name": name,
                    "passed": False,
                    "detail": {"error": f"{type(exc).__name__}: {exc}", "crashed": True},
                }
            )
        else:
            self.checks.append({"name": name, "passed": True, "detail": detail})


def check_two_stack_semantics() -> Mapping[str, Any]:
    # The first program exercises empty POP/EMPTY BRANCH, target selection,
    # ordinary pushes, and a non-empty POP path.  The second exercises all
    # stack directions and PUSH_ACC after two consecutive transfers.
    programs = [
        (
            (REF_POP, 0, 1, 0, 0),
            (REF_BRANCH, REF_EMPTY, 2, 4, 0),
            (REF_PUSH, 1, 42, 3, 0),
            (REF_JUMP, 6, 0, 0, 0),
            (REF_PUSH, 0, 7, 5, 0),
            (REF_JUMP, 6, 0, 0, 0),
            (REF_HALT, 0, 0, 0, 0),
        ),
        (
            (REF_POP, 0, 1, 0, 0),
            (REF_PUSH_ACC, 1, 2, 0, 0),
            (REF_POP, 1, 3, 0, 0),
            (REF_PUSH_ACC, 0, 4, 0, 0),
            (REF_HALT, 0, 0, 0, 0),
        ),
        (
            (REF_PUSH, 0, 0, 1, 0),
            (REF_PUSH, 0, 255, 2, 0),
            (REF_POP, 0, 3, 0, 0),
            (REF_BRANCH, 255, 4, 5, 0),
            (REF_PUSH_ACC, 1, 6, 0, 0),
            (REF_JUMP, 6, 0, 0, 0),
            (REF_HALT, 0, 0, 0, 0),
        ),
    ]
    outcomes = []
    for index, program in enumerate(programs):
        outcomes.append(
            _run_primitive_equivalence(
                program,
                left=(9,) if index in (0, 1) else (),
                right=(8,) if index == 1 else (),
                label=f"program-{index}",
            )
        )
    return {"programs": len(programs), "outcomes": outcomes}


def check_step_run_and_counters() -> Mapping[str, Any]:
    program = (
        (REF_PUSH, 0, 11, 1, 0),
        (REF_PUSH, 1, 22, 2, 0),
        (REF_POP, 1, 3, 0, 0),
        (REF_PUSH_ACC, 0, 4, 0, 0),
        (REF_HALT, 0, 0, 0, 0),
    )
    profile = ComputerProfile(program_capacity=16, stack_capacity=16, max_steps=100)
    by_step = FieldComputer(profile)
    state_a = by_step.initial(program)
    for _ in range(3):
        state_a, event = by_step.step(state_a)
        if event is None:
            raise AssertionError("step event missing")
    run_machine = FieldComputer(profile)
    state_b = run_machine.initial(program)
    state_b, receipt = run_machine.run(state_b, steps=3)
    if semantic_snapshot(_info(by_step, state_a)) != semantic_snapshot(_info(run_machine, state_b)):
        raise AssertionError("run(steps=3) diverges from three public step calls")
    if not isinstance(receipt, Mapping):
        raise AssertionError("run receipt is not a mapping")
    before = by_step.state_sha256(state_a)
    state_c, zero_receipt = by_step.run(state_a, steps=0)
    if by_step.state_sha256(state_c) != before or semantic_snapshot(_info(by_step, state_c)) != semantic_snapshot(
        _info(by_step, state_a)
    ):
        raise AssertionError("run(steps=0) changed state")
    if not isinstance(zero_receipt, Mapping):
        raise AssertionError("zero-step run receipt is not a mapping")
    ledger = _info(by_step, state_a)["resource_ledger"]
    if int(ledger["transitions"]) != 3 or int(ledger["stack_reads"]) != 1 or int(ledger["stack_writes"]) != 2:
        raise AssertionError(f"incorrect observable counters {ledger!r}")
    return {"partial_receipt_keys": sorted(str(key) for key in receipt), "transitions": int(ledger["transitions"])}


def check_capacity_and_resize() -> Mapping[str, Any]:
    push_twice = (
        (REF_PUSH, 0, 1, 1, 0),
        (REF_PUSH, 0, 2, 2, 0),
        (REF_HALT, 0, 0, 0, 0),
    )
    machine = FieldComputer(ComputerProfile(program_capacity=8, stack_capacity=1, max_steps=20))
    state = machine.initial(push_twice)
    state, _ = machine.run(state)
    exhausted = _info(machine, state)
    if exhausted["status"] != "exhausted" or tuple(exhausted["left"]) != (1,):
        raise AssertionError(f"stack exhaustion did not preserve work: {exhausted}")
    grown_machine, grown_state = machine.resize(state, stack_capacity=2)
    resumed = _info(grown_machine, grown_state)
    if resumed["status"] != "running" or tuple(resumed["left"]) != (1,):
        raise AssertionError("stack resize did not resume the relevant exhaustion")
    grown_state, _ = grown_machine.run(grown_state)
    if _info(grown_machine, grown_state)["status"] != "halted" or tuple(
        _info(grown_machine, grown_state)["left"]
    ) != (1, 2):
        raise AssertionError("resized stack did not finish the push program")

    loop = ((REF_JUMP, 0, 0, 0, 0),)
    bounded = FieldComputer(ComputerProfile(program_capacity=4, stack_capacity=4, max_steps=3))
    loop_state = bounded.initial(loop)
    loop_state, _ = bounded.run(loop_state)
    if _info(bounded, loop_state)["status"] != "exhausted":
        raise AssertionError("nonhalting program did not exhaust its finite budget")
    unchanged_machine, unchanged_state = bounded.resize(loop_state, stack_capacity=5)
    if _info(unchanged_machine, unchanged_state)["status"] != "exhausted":
        raise AssertionError("irrelevant stack resize revived step exhaustion")
    resumed_machine, resumed_state = bounded.resize(loop_state, stack_capacity=5, max_steps=6)
    if _info(resumed_machine, resumed_state)["status"] != "running":
        raise AssertionError("max-step resize did not resume relevant exhaustion")
    return {"stack_exhausted": exhausted["status"], "resumed_status": _info(grown_machine, grown_state)["status"]}


def check_descriptor_and_immutability() -> Mapping[str, Any]:
    program = (
        (REF_PUSH, 0, 13, 1, 0),
        (REF_POP, 0, 2, 0, 0),
        (REF_PUSH_ACC, 1, 3, 0, 0),
        (REF_HALT, 0, 0, 0, 0),
    )
    machine = FieldComputer(ComputerProfile(program_capacity=16, stack_capacity=16, max_steps=20))
    state = machine.initial(program, left=(5,), right=(6,))
    descriptor = machine.descriptor(state)
    states = [state]
    for _ in range(3):
        states.append(machine.step(states[-1])[0])
    paused_state, pause_receipt = machine.run(state, steps=1)
    if not isinstance(pause_receipt, Mapping) or not pause_receipt.get("paused", False):
        raise AssertionError("run(steps=1) did not report a paused checkpoint")
    if semantic_snapshot(_info(machine, paused_state)) != semantic_snapshot(_info(machine, states[1])):
        raise AssertionError("paused run differs from one primitive transition")
    round_trips = 0
    for checkpoint in states:
        checkpoint_digest = machine.state_sha256(checkpoint)
        descriptor = machine.descriptor(checkpoint)
        if not isinstance(descriptor, Mapping):
            raise AssertionError("descriptor is not a mapping")
        json.dumps(descriptor, sort_keys=True)
        restored_machine, restored = FieldComputer.from_descriptor(copy.deepcopy(descriptor))
        if restored_machine.state_sha256(restored) != checkpoint_digest:
            raise AssertionError("descriptor round trip changed state digest")
        if semantic_snapshot(_info(restored_machine, restored)) != semantic_snapshot(
            _info(machine, checkpoint)
        ):
            raise AssertionError("descriptor round trip changed computational state")
        round_trips += 1

    field = state.field
    before = machine.state_sha256(state)
    try:
        field.setflags(write=True)
        field.flat[0] = field.flat[0] + 1
    except (TypeError, ValueError, AttributeError, RuntimeError):
        pass
    if machine.state_sha256(state) != before:
        raise AssertionError("state digest changed through field alias")

    tampered = 0
    for key in ("schema", "layout", "profile", "state_sha256", "profile_sha256", "field_b64"):
        altered = dict(copy.deepcopy(machine.descriptor(state)))
        value = altered[key]
        if isinstance(value, Mapping):
            altered[key] = dict(value)
            altered[key]["tampered"] = 1
        elif isinstance(value, str):
            altered[key] = "tampered"
        else:
            altered[key] = None
        if _expect_rejection(lambda altered=altered: FieldComputer.from_descriptor(altered)) is None:
            raise AssertionError(f"tampered descriptor key {key!r} was accepted")
        tampered += 1
    return {"descriptor_keys": len(descriptor), "round_trips": round_trips, "tampered_fields": tampered, "state_sha256": before}


def check_validation() -> Mapping[str, Any]:
    profile = ComputerProfile(program_capacity=4, stack_capacity=4, max_steps=4)
    machine = FieldComputer(profile)
    malformed = [
        (),
        ((7, 0, 0, 0, 0),),
        ((6, 2, 0, 0, 0),),
        ((6, 0, 1, 0, 0),),
        ((6, 0, 0, 1, 0),),
        ((REF_HALT, 1, 0, 0, 0),),
        ((REF_PUSH, 2, 1, 1, 0),),
        ((REF_PUSH, 0, REF_EMPTY, 1, 0),),
        ((REF_PUSH, 0, 1, 9, 0),),
        ((REF_POP, 0, 9, 0, 0),),
        ((REF_BRANCH, 0, 1, 9, 0),),
        ((REF_PUSH_ACC, 0, 1, 7, 0),),
        ((REF_JUMP, -1, 0, 0, 0),),
        ((REF_PUSH, 0, 1, -1, 0),),
        ((REF_POP, 0, -1, 0, 0),),
        ((REF_BRANCH, 0, -1, 0, 0),),
        ((REF_PUSH_ACC, 0, -1, 0, 0),),
    ]
    outcomes = []
    for program in malformed:
        error = _expect_rejection(lambda program=program: machine.initial(program))
        if error is None:
            raise AssertionError(f"malformed program accepted: {program!r}")
        outcomes.append(error)
    if _expect_rejection(lambda: ComputerProfile(program_capacity=0, stack_capacity=1, max_steps=1)) is None:
        raise AssertionError("zero program capacity accepted")
    if _expect_rejection(lambda: ComputerProfile(program_capacity=1, stack_capacity=0, max_steps=1)) is None:
        raise AssertionError("zero stack capacity accepted")

    zero_profile = ComputerProfile(program_capacity=1, stack_capacity=1, max_steps=0)
    zero_machine = FieldComputer(zero_profile)
    zero_state = zero_machine.initial(((REF_PUSH, 0, 1, 0, 0),))
    if _info(zero_machine, zero_state)["status"] != "exhausted":
        raise AssertionError("zero step budget did not create an exhausted initial state")

    if _expect_rejection(
        lambda: machine.initial(((REF_HALT, 0, 0, 0, 0),), left=(REF_EMPTY,))
    ) is None:
        raise AssertionError("EMPTY was accepted as an initial stack symbol")
    if _expect_rejection(
        lambda: machine.initial(tuple((REF_HALT, 0, 0, 0, 0) for _ in range(5)))
    ) is None:
        raise AssertionError("program capacity overflow accepted")
    if _expect_rejection(
        lambda: machine.initial(((REF_HALT, 0, 0, 0, 0),), entry=1)
    ) is None:
        raise AssertionError("entry outside program accepted")

    transitions = {(0, 0): (1, 0, "R")}
    compiler_errors = [
        lambda: compile_turing_machine({}, alphabet_size=2),
        lambda: compile_turing_machine(
            {(0, 0): (1, 0, "X"), (0, 1): (1, 0, "R")},
            alphabet_size=2,
        ),
        lambda: compile_turing_machine(
            {(0, 0): (1, 2, "R"), (0, 1): (1, 0, "R")},
            alphabet_size=2,
        ),
        lambda: compile_turing_machine({(0, 0): (1, 0, "R")}, halt_states=(0,), alphabet_size=2),
        lambda: compile_turing_machine(transitions, alphabet_size=0),
    ]
    for call in compiler_errors:
        if _expect_rejection(call) is None:
            raise AssertionError("malformed TM descriptor accepted")
    return {"malformed_programs": len(malformed), "compiler_refusals": len(compiler_errors)}


def check_turing_machine_boundaries() -> Mapping[str, Any]:
    # Unary increment extends the right edge through an implicit blank.
    unary = {
        (0, 0): (1, 1, "S"),
        (0, 1): (0, 1, "R"),
    }
    # Scan and complement a variable-length binary word, then halt on blank.
    complement = {
        (0, 0): (0, 1, "R"),
        (0, 1): (0, 0, "R"),
        (0, 2): (1, 2, "S"),
    }
    # Binary increment, least significant bit at the right edge.  The carry
    # machine also covers a leading blank/left extension for all-one inputs.
    increment = {
        (0, 0): (0, 0, "R"),
        (0, 1): (0, 1, "R"),
        (0, 2): (2, 2, "L"),
        (2, 0): (1, 1, "S"),
        (2, 1): (2, 0, "L"),
        (2, 2): (1, 1, "S"),
    }
    # A left-edge extension specifically distinguishes a correct L move from
    # a right move or a dropped blank cell.
    left_extend = {
        (0, 0): (1, 1, "S"),
        (0, 1): (2, 1, "L"),
        (2, 0): (1, 1, "S"),
        (2, 1): (1, 1, "S"),
    }
    remapped = {
        (4, 0): (6, 1, "S"),
        (4, 1): (6, 0, "S"),
        (4, 2): (6, 2, "S"),
        (6, 0): (99, 0, "S"),
        (6, 1): (99, 1, "S"),
        (6, 2): (99, 2, "S"),
    }
    seeded = {
        (10, 0): (10, 1, "R"),
        (10, 1): (10, 0, "R"),
        (10, 2): (20, 2, "L"),
        (10, 3): (20, 3, "S"),
        (20, 0): (30, 0, "S"),
        (20, 1): (30, 1, "S"),
        (20, 2): (30, 2, "S"),
        (20, 3): (30, 3, "S"),
    }
    two_halt = {
        (0, 0): (1, 0, "S"),
        (0, 1): (2, 1, "S"),
    }
    halt_zero = _run_tm_case(
        "distinct_halt_zero",
        two_halt,
        (0,),
        blank=0,
        alphabet_size=2,
        halt_states=(1, 2),
    )
    halt_one = _run_tm_case(
        "distinct_halt_one",
        two_halt,
        (1,),
        blank=0,
        alphabet_size=2,
        halt_states=(1, 2),
    )
    if halt_zero["final_pc"] == halt_one["final_pc"]:
        raise AssertionError("distinct halt states collapsed to one HALT PC")
    outcomes = [
        _run_tm_case("unary_increment", unary, (1,) * 12, blank=0, alphabet_size=2),
        _run_tm_case("unary_empty", unary, (), blank=0, alphabet_size=2),
        _run_tm_case("complement", complement, (0, 1, 0, 1, 1, 0, 1, 0, 1), blank=2, alphabet_size=3),
        _run_tm_case("binary_increment", increment, (1, 1, 1, 1), blank=2, alphabet_size=3),
        _run_tm_case("left_extension", left_extend, (1,), blank=0, alphabet_size=2),
        _run_tm_case(
            "remapped_states",
            remapped,
            (0, 1, 0, 1),
            start_state=4,
            halt_states=(99,),
            blank=2,
            alphabet_size=3,
        ),
        _run_tm_case(
            "seeded_arbitrary_states",
            seeded,
            (0, 1, 2),
            start_state=10,
            halt_states=(30,),
            blank=3,
            alphabet_size=4,
        ),
    ]
    return {
        "machines": len(outcomes),
        "outcomes": outcomes,
        "distinct_halt_pcs": [halt_zero["final_pc"], halt_one["final_pc"]],
    }

def check_generated_tm_tables() -> Mapping[str, Any]:
    """Exhaust all one-work-state/two-symbol tables, at a short TM horizon."""
    options = tuple(
        (next_state, write_symbol, direction)
        for next_state in (0, 1)
        for write_symbol in (0, 1)
        for direction in ("L", "R", "S")
    )
    tables = 0
    runs = 0
    primitive_steps = 0
    for first in options:
        for second in options:
            table = {(0, 0): first, (0, 1): second}
            tables += 1
            for initial_symbol in (0, 1):
                outcome = _run_tm_case(
                    f"generated-{tables}-{initial_symbol}",
                    table,
                    (initial_symbol,),
                    blank=0,
                    alphabet_size=2,
                    max_steps=300,
                    expect_status=None,
                    tm_steps=3,
                )
                if outcome["boundaries"] < 1:
                    raise AssertionError("generated TM did not expose its initial boundary")
                runs += 1
                primitive_steps += int(outcome["primitive_steps"])
    if tables != 144 or runs != 288:
        raise AssertionError(f"generated coverage count mismatch: tables={tables}, runs={runs}")
    return {"tables": tables, "runs": runs, "primitive_steps": primitive_steps, "tm_horizon": 3}


def check_nonhalting_and_field_budget() -> Mapping[str, Any]:
    transitions = {
        (0, 0): (0, 0, "R"),
        (0, 1): (0, 1, "L"),
    }
    compiled = compile_turing_machine(transitions, halt_states=(9,), blank=0, alphabet_size=2)
    profile = ComputerProfile(program_capacity=len(compiled.program) + 16, stack_capacity=32, max_steps=40)
    machine = FieldComputer(profile)
    state = machine.initial(compiled.program, entry=compiled.entry, right=(1,))
    partial, receipt = machine.run(state, steps=7)
    if _info(machine, partial)["status"] != "running":
        raise AssertionError("explicit finite run should be a partial running state")
    if _counter_value(_info(machine, partial), "transitions") != 7:
        raise AssertionError("explicit finite run did not charge each primitive step")
    terminal, receipt2 = machine.run(partial)
    terminal_info = _info(machine, terminal)
    if terminal_info["status"] != "exhausted":
        raise AssertionError("bounded nonhalting TM did not exhaust")
    if _counter_value(terminal_info, "transitions") != 40:
        raise AssertionError("step-budget exhaustion charged the wrong number of transitions")
    if not isinstance(receipt, Mapping) or not isinstance(receipt2, Mapping):
        raise AssertionError("run receipts are not mappings")
    return {"partial_transitions": 7, "terminal_transitions": 40, "status": terminal_info["status"]}

def check_batched_and_specialized_execution() -> Mapping[str, Any]:
    program = (
        (REF_PUSH, 0, 7, 1, 0),
        (REF_POP, 0, 2, 0, 0),
        (REF_PUSH_ACC, 1, 3, 0, 0),
        (REF_HALT, 0, 0, 0, 0),
    )
    profile = ComputerProfile(program_capacity=8, stack_capacity=8, max_steps=20)
    machine = FieldComputer(profile)
    initial = machine.initial(program)
    stepped = initial
    step_copy_cells = 0
    while _info(machine, stepped)["status"] == "running":
        stepped, event = machine.step(stepped)
        physical = event.get("physical_copy_work")
        if not isinstance(physical, Mapping):
            raise AssertionError("step omitted physical copy accounting")
        step_copy_cells += int(physical["working_copy_cells"]) + int(physical["sealed_copy_cells"])
    batched, batch_receipt = machine.run(initial)
    if machine.state_sha256(batched) != machine.state_sha256(stepped):
        raise AssertionError("one-seal run differs from repeated public steps")
    physical = batch_receipt.get("physical_copy_work")
    if not isinstance(physical, Mapping):
        raise AssertionError("batched run omitted physical copy accounting")
    batch_copy_cells = int(physical["working_copy_cells"]) + int(physical["sealed_copy_cells"])
    if batch_copy_cells != 2 * profile.field_cells or step_copy_cells != 8 * profile.field_cells:
        raise AssertionError("copy/seal accounting does not match actual immutable boundaries")
    cold_specialization = batch_receipt.get("specialization")
    if (
        not isinstance(cold_specialization, Mapping)
        or cold_specialization.get("derived_blocks") != 0
        or cold_specialization.get("derivation_deferred") is not True
        or cold_specialization.get("block_invocations") != 0
    ):
        raise AssertionError(
            "cold execution did not defer block derivation"
        )

    warm = initial
    for cycle in range(8):
        warm, _ = machine.run(warm, use_blocks=False)
        if cycle < 7:
            warm, _ = machine.restart(warm)
    observations = _info(machine, warm).get("execution_learning")
    if not isinstance(observations, Mapping) or observations.get("pc_observations") != [8, 8, 8, 8]:
        raise AssertionError("instruction heat did not persist in the field across restarts")
    restarted, restart_receipt = machine.restart(warm, left=(9,))
    restart_copy = restart_receipt.get("physical_copy_work")
    if (
        restart_receipt.get("retained_execution_observations") != 32
        or not isinstance(restart_copy, Mapping)
        or sum(int(value) for value in restart_copy.values()) != 2 * profile.field_cells
    ):
        raise AssertionError("restart did not retain heat with one copy and one seal")
    specialized, fast_receipt = machine.run(restarted, use_blocks=True)
    plain, plain_receipt = machine.run(restarted, use_blocks=False)
    if machine.state_sha256(specialized) != machine.state_sha256(plain):
        raise AssertionError("hot-block execution changed the full field checkpoint")
    for key in (
        "status",
        "reason",
        "paused",
        "transitions_executed",
        "resource_ledger",
    ):
        if fast_receipt.get(key) != plain_receipt.get(key):
            raise AssertionError(
                f"hot-block receipt changed {key}"
            )
    fast = fast_receipt.get("specialization")
    slow = plain_receipt.get("specialization")
    if (
        not isinstance(fast, Mapping)
        or not isinstance(slow, Mapping)
        or int(fast.get("block_invocations", 0)) < 1
        or int(fast.get("derived_blocks", 0)) < 1
        or fast.get("derivation_deferred") is not False
        or int(slow.get("block_invocations", -1)) != 0
        or int(slow.get("derived_blocks", -1)) != 0
    ):
        raise AssertionError("field heat did not control reusable block execution")
    fast_paused, fast_pause_receipt = machine.run(
        restarted,
        steps=2,
        use_blocks=True,
    )
    plain_paused, plain_pause_receipt = machine.run(
        restarted,
        steps=2,
        use_blocks=False,
    )
    if machine.state_sha256(fast_paused) != machine.state_sha256(
        plain_paused
    ):
        raise AssertionError(
            "hot block crossed an explicit pause boundary"
        )
    pause_specialization = fast_pause_receipt.get(
        "specialization"
    )
    if (
        not isinstance(pause_specialization, Mapping)
        or fast_pause_receipt.get("paused") is not True
        or fast_pause_receipt.get("transitions_executed") != 2
        or fast_pause_receipt.get("resource_ledger")
        != plain_pause_receipt.get("resource_ledger")
        or pause_specialization.get("block_invocations") != 1
    ):
        raise AssertionError(
            "hot block pause receipt is not primitive-equivalent"
        )
    return {
        "transitions": int(batch_receipt["transitions_executed"]),
        "step_copy_cells": step_copy_cells,
        "batch_copy_cells": batch_copy_cells,
        "copy_reduction_ratio": step_copy_cells / batch_copy_cells,
        "retained_execution_observations": 32,
        "block_invocations": int(fast["block_invocations"]),
        "full_field_equal": True,
        "cold_derivation_deferred": True,
        "hot_pause_equivalent": True,
    }


def run_suite() -> dict[str, Any]:
    report = Report()
    checks: tuple[tuple[str, Callable[[], Mapping[str, Any]]], ...] = (
        ("two_stack_semantics", check_two_stack_semantics),
        ("step_run_and_counters", check_step_run_and_counters),
        ("capacity_and_resize", check_capacity_and_resize),
        ("descriptor_and_immutability", check_descriptor_and_immutability),
        ("validation", check_validation),
        ("turing_machine_boundaries", check_turing_machine_boundaries),
        ("generated_tm_coverage", check_generated_tm_tables),
        ("nonhalting_and_field_budget", check_nonhalting_and_field_budget),
        ("batched_and_specialized_execution", check_batched_and_specialized_execution),
    )
    for name, check in checks:
        report.add(name, check)
    failed = [row["name"] for row in report.checks if not row["passed"]]
    return {
        "suite": "verify_field_computer",
        "subject": "cassi_field_computer.py",
        "checks": report.checks,
        "check_count": len(report.checks),
        "failed_checks": failed,
        "passed": not failed,
        "reference": {
            "instruction_model": "independent canonical two-stack transition function",
            "tm_model": "independent sparse single-tape transition function",
            "boundary_comparison": "every compiled state-entry boundary plus terminal tape",
            "scope_note": "arbitrary finite TM instances exercise compiler simulation; no finite-run universality claim",
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Independent verifier for cassi_field_computer.py")
    parser.add_argument("--json", dest="json_path", default=None, help="write the JSON report to PATH")
    args = parser.parse_args(list(argv) if argv is not None else None)
    started = time.time()
    summary = run_suite()
    summary["elapsed_seconds"] = round(time.time() - started, 3)
    print(json.dumps(summary, indent=2, sort_keys=True))
    if args.json_path:
        output_path = Path(args.json_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2, sort_keys=True)
            handle.write("\n")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
