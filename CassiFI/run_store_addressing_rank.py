"""Is a crowded store rank-deficient, and does item-specific placement restore rank?

DECLARED BEFORE THE FIRST RUN -- statistic, discriminator, decision rule, controls.

THE QUESTION. The store-scale receipt measured a crowded store whose cross-item
cells are degenerate: every declared item's deposit agrees to ~3e-15 relative,
while a page holding one item separates from the others at ~4e+32. This runner asks
whether that degeneracy is in the store or in the read instrument, and whether
item-dependent placement restores what a shared placement cannot carry.

DECLARED STATISTIC -- the deposit map. On one page state, ``J`` is the finite
difference of the read vector with respect to the declared write, one probe at a
time: with the declared item placements P(i) and the declared probe work ``a``,
``J[i][j] = (read_at(P(i)) after a probe write at P(j) -- before) / a``. ``J`` is N x
N over the declared items; its singular values are the deposit-difference
spectrum, ``sigma_1 >= ... >= sigma_N``. Each probe starts from a fresh owner on the
same page, so probes never accumulate. The same reading is taken at a second probe
work ``a/2``, which measures the finite-difference error floor:

    tol(J) = max(FLOOR_FACTOR * sigma_1(J(a) - J(a/2)), EPS_FACTOR * sigma_1(J(a)))
    rank(J) = #{k : sigma_k > tol}

with FLOOR_FACTOR and EPS_FACTOR declared below. Report the deposits themselves and
their first differences, whose kernel is the constant vector: a deposit vector whose
first differences are at the declared floor is constant, i.e. carries no item
identity at all.

DECLARED DISCRIMINATOR -- pairwise separation. ``Jn = J / mean(diag(J))``, so an
orthogonal pair is predicted at exactly 1 (diagonal 1, off-diagonal 0) and a
duplicated pair at exactly 0. The separation of items i and k is
``s(i,k) = max_j |Jn[i][j] - Jn[k][j]|``; the separation of the probe directions j and
l is ``t(j,l) = max_i |Jn[i][j] - Jn[i][l]|``. A pair is distinguishable when its
separation exceeds CONTRAST_FLOOR.

DECLARED DECISION RULE.
  Part 1, on the crowded store state and on a one-item reference state:
    * rank(J) == N at the crowded state  -> the store carries every declared item
      and the degeneracy sits in the readout, not in the map; the deposit vector's
      own constancy is measured separately and reported as its own predicate, and is
      not assumed either way by this branch;
    * rank(J) < N at the crowded state while rank(J) == N at the reference state
      -> the store cannot carry those items at that operating point;
    * any other combination -> undetermined, reported with its numbers.
    Wording amendment, made after the first run and before the receipt that is
    reported: this branch was declared as "the store carries every item and only the
    readout is collapsed". The branch structure, every threshold and every control
    are unchanged; "collapsed" is now stated as the read/deposit *cells* the
    store-scale receipt reported, because the receipt measures the deposit vector's
    own constancy as a separate predicate and at the crowded state it is false. The
    originally declared wording would have asserted a scalar collapse the measurement
    does not support, so it is corrected rather than kept.
  Part 2, three placement arms at the same crowded page state, same items:
    * specific  -- item i is addressed at its own declared placement;
    * shared    -- every item is addressed at one declared placement (item 0's);
    * duplicate -- item 1 is addressed at item 0's placement, everything else
      specific; this is the declared structural control.
    Item-specific placement restores the rank iff rank(specific) == N,
    rank(shared) < N, rank(duplicate) == N - 1, every specific-arm pair is
    distinguishable, no shared-arm pair is, and the duplicated pair's separation is
    at the floor. If the specific arm does not separate every pair, the answer is no
    at this operating point and is reported as the primary negative.

DECLARED CONTROLS, each measured in the same run.
  * duplicated item -> zero separation: the duplicate arm's pair (0, 1) must sit at
    the floor, and its rank must be exactly N - 1;
  * a separated pair must show the separation the control predicts: the specific
    arm's pairs must reach 1 - LOSS_ALLOWANCE of the predicted 1;
  * the shared arm must separate no pair (the addressing-structure control);
  * the firing control for the rank predicate: the duplicate arm's deficiency is
    the instance that proves the rank reading can fall below N at all;
  * a zero-work probe must move no read (the finite difference is not being
    manufactured by the probe bookkeeping);
  * the read on a page nothing was written to must be zero;
  * the finite-difference floor is measured on the arm that carries the page's own
    half-probe sweep -- the specific arm at the crowded written page, the crowded
    arm at the crowded held state and the reference arm at the reference state --
    and that measured floor is reused, as a declared value, by the other arms at the
    same page; an arm's own largest singular value always supplies its own scale
    term, so only the floor term is shared.

Everything is CPU, in-process, on the declared eight declared items; the crowded
state is the store-scale runner's own held store, reused through its own machinery.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

import run_fractal_durability_exploration as durability
import run_fractal_feedback_exploration as feedback
import run_memory_consumer_path as consumer
import run_memory_store_scale as scale

SCHEMA = "cassifi.store-addressing-rank.v1"
RECEIPT_PATH = Path("_diag/store-addressing-rank/exploration.json")

ITEM_INDICES = tuple(range(8))
HOLD_TICKS = 2
PROBE_BUDGET = 1e-3
FLOOR_FACTOR = 10.0
EPS_FACTOR = 1e-9
CONTRAST_FLOOR = 1e-3
LOSS_ALLOWANCE = 0.05
PAGE_MOVE_ALLOWANCE = 1e-12

PLACEMENT_MODES = ("specific", "shared", "duplicate")


@dataclass(frozen=True)
class AddressingRankConfig:
    """Declared measurement settings; every number in the receipt derives from these."""

    item_indices: tuple[int, ...] = ITEM_INDICES
    hold_ticks: int = HOLD_TICKS
    probe_budget: float = PROBE_BUDGET
    floor_factor: float = FLOOR_FACTOR
    epsilon_factor: float = EPS_FACTOR
    contrast_floor: float = CONTRAST_FLOOR
    loss_allowance: float = LOSS_ALLOWANCE
    owner_home_prefix: str = "srank-owner-"
    store_config: scale.StoreScaleConfig = field(
        default_factory=lambda: scale.StoreScaleConfig(
            part_a=False,
            part_b=True,
            item_indices=ITEM_INDICES,
            rounds=1,
            hold_horizon_ticks=HOLD_TICKS,
            neutrality_probe_items=(),
        )
    )

    def as_dict(self) -> dict[str, Any]:
        return {
            "item_indices": [int(index) for index in self.item_indices],
            "item_names": [
                durability.ITEM_SPECS[int(index)].name for index in self.item_indices
            ],
            "hold_ticks": int(self.hold_ticks),
            "probe_budget": float(self.probe_budget),
            "probe_budget_half": float(self.probe_budget) / 2.0,
            "floor_factor": float(self.floor_factor),
            "epsilon_factor": float(self.epsilon_factor),
            "contrast_floor": float(self.contrast_floor),
            "loss_allowance": float(self.loss_allowance),
            "placement_modes": list(PLACEMENT_MODES),
            "declared_placements": {
                durability.ITEM_SPECS[int(index)].name: {
                    "path": durability.ITEM_SPECS[int(index)].path,
                    "component": durability.ITEM_SPECS[int(index)].component,
                    "flow_signal": [
                        float(value)
                        for value in durability.ITEM_SPECS[int(index)].flow_signal
                    ],
                }
                for index in self.item_indices
            },
            "shared_placement_item": durability.ITEM_SPECS[
                int(self.item_indices[0])
            ].name,
        }


# --------------------------------------------------------------------------
# placement, reads and writes
# --------------------------------------------------------------------------
def placement_spec(index: int, mode: str, config: AddressingRankConfig) -> durability.ItemSpec:
    """The declared placement an arm addresses item ``index`` at."""

    spec = durability.ITEM_SPECS[int(index)]
    if mode == "specific":
        return spec
    if mode == "shared":
        return durability.ITEM_SPECS[int(config.item_indices[0])]
    if mode == "duplicate":
        return (
            durability.ITEM_SPECS[int(config.item_indices[0])]
            if int(index) == int(config.item_indices[1])
            else spec
        )
    raise ValueError(f"undeclared placement mode: {mode!r}")


def read_at(owner: Any, spec: durability.ItemSpec) -> dict[str, Any]:
    """The owner's own read along one declared placement."""

    reading = scale.plain(
        owner.read_packet_deposit(
            path=spec.path,
            component=spec.component,
            flow_signal=[float(value) for value in spec.flow_signal],
        )
    )
    return {
        "spec": f"{spec.name}",
        "recovered_deposit": float(reading["recovered_deposit"]),
        "readout_kind": str(reading["readout_kind"]),
    }


def write_at(
    owner: Any, spec: durability.ItemSpec, *, label: str, budget: float
) -> dict[str, Any]:
    """One owner write along one declared placement."""

    result = scale.plain(
        owner.write_packet_impulse(
            label,
            path=spec.path,
            component=spec.component,
            flow_signal=[float(value) for value in spec.flow_signal],
            work_budget=float(budget),
        )
    )
    receipt = scale.plain(result["impulse_receipt"])
    return {
        "requested_work": float(receipt["requested_work"]),
        "applied_work": float(receipt["applied_work"]),
        "impulse_amount": float(receipt["impulse_amount"]),
        "accepted": bool(receipt["accepted"]),
    }


def page_with(
    profile: Any,
    config: AddressingRankConfig,
    indices: Sequence[int],
    *,
    mode: str,
    label: str,
) -> tuple[Any, dict[str, Any]]:
    """One page built from the declared writes at the arm's own placements."""

    owner, home = consumer.open_owner(profile, prefix=config.owner_home_prefix)
    try:
        blank_page = durability.page_sha256(owner.state.resonant_workspace)
        writes = {}
        for index in indices:
            spec = placement_spec(int(index), mode, config)
            writes[durability.ITEM_SPECS[int(index)].name] = write_at(
                owner,
                spec,
                label=f"{label}:write:{int(index)}",
                budget=float(config.probe_budget),
            )
        page = owner.state.resonant_workspace
        written_page = durability.page_sha256(page)
        snapshot = scale.surface_snapshot(owner)
    finally:
        owner.close()
        shutil.rmtree(home, ignore_errors=True)
    return page, {
        "mode": str(mode),
        "blank_page_sha256": blank_page,
        "written_page_sha256": written_page,
        "the_writes_move_the_page": bool(blank_page != written_page),
        "writes": writes,
        "snapshot": snapshot,
    }


def deposit_vector(
    profile: Any,
    config: AddressingRankConfig,
    page: Any,
    *,
    mode: str,
) -> dict[str, Any]:
    """Every declared item's read on one page, at the arm's own placements."""

    indices = tuple(int(index) for index in config.item_indices)
    owner, home = consumer.open_owner(
        profile, workspace=page, prefix=config.owner_home_prefix
    )
    try:
        values = {
            durability.ITEM_SPECS[index].name: read_at(
                owner, placement_spec(index, mode, config)
            )["recovered_deposit"]
            for index in indices
        }
        repeats = {
            durability.ITEM_SPECS[index].name: read_at(
                owner, placement_spec(index, mode, config)
            )["recovered_deposit"]
            for index in indices
        }
    finally:
        owner.close()
        shutil.rmtree(home, ignore_errors=True)
    return {"values": values, "repeats": repeats}


def difference_reading(value: Mapping[str, Any], config: AddressingRankConfig) -> dict[str, Any]:
    """The deposit vector's first differences: the kernel of the difference map."""

    names = list(value["values"])
    deposits = [float(value["values"][name]) for name in names]
    repeats = [float(value["repeats"][name]) for name in names]
    differences = [
        deposits[position + 1] - deposits[position]
        for position in range(len(deposits) - 1)
    ]
    mean_magnitude = (
        sum(abs(item) for item in deposits) / float(len(deposits)) if deposits else 0.0
    )
    repeat_greatest = max(
        (abs(a - b) for a, b in zip(deposits, repeats)), default=0.0
    )
    greatest_difference = max((abs(item) for item in differences), default=0.0)
    tolerance = max(
        float(config.floor_factor) * float(repeat_greatest),
        float(config.epsilon_factor) * float(mean_magnitude),
    )
    # The declared difference map is the (N-1) x N first-difference operator; its
    # kernel is the constant vector, so its rank is N-1 on any non-constant deposit
    # vector. What the crowded state changes is the data: how much of the deposit
    # vector lies inside that kernel.
    operator = np.zeros((max(len(deposits) - 1, 0), len(deposits)), dtype=np.float64)
    for row in range(operator.shape[0]):
        operator[row, row] = -1.0
        operator[row, row + 1] = 1.0
    singular = (
        np.linalg.svd(operator, compute_uv=False).tolist() if operator.size else []
    )
    return {
        "item_names": names,
        "deposits": deposits,
        "repeats": repeats,
        "first_differences": differences,
        "mean_deposit_magnitude": float(mean_magnitude),
        "repeat_greatest_difference": float(repeat_greatest),
        "greatest_first_difference": float(greatest_difference),
        "tolerance": float(tolerance),
        "difference_operator_singular_values": [float(value) for value in singular],
        "difference_operator_rank": int(
            len([value for value in singular if float(value) > 1e-12])
        ),
        "the_deposit_vector_is_constant_at_the_tolerance": bool(
            greatest_difference <= tolerance
        ),
        "the_deposit_vector_relative_difference": (
            float(greatest_difference) / float(mean_magnitude)
            if mean_magnitude > 0.0
            else 0.0
        ),
    }


# --------------------------------------------------------------------------
# the deposit map: finite differences, singular values, rank
# --------------------------------------------------------------------------
def jacobian(
    profile: Any,
    config: AddressingRankConfig,
    page: Any,
    *,
    mode: str,
    amplitude: float,
    zero_probe: bool = False,
) -> dict[str, Any]:
    """The finite-difference deposit map at one page, one fresh owner per probe."""

    indices = tuple(int(index) for index in config.item_indices)
    names = [durability.ITEM_SPECS[index].name for index in indices]
    columns: list[list[float]] = []
    baselines: list[dict[str, float]] = []
    probes: list[dict[str, Any]] = []
    for probe_index in indices:
        probe_spec = placement_spec(probe_index, mode, config)
        owner, home = consumer.open_owner(
            profile, workspace=page, prefix=config.owner_home_prefix
        )
        try:
            before = {
                durability.ITEM_SPECS[index].name: read_at(
                    owner, placement_spec(index, mode, config)
                )["recovered_deposit"]
                for index in indices
            }
            budget = 0.0 if zero_probe else float(amplitude)
            write = write_at(
                owner,
                probe_spec,
                label=f"srank:{mode}:probe:{probe_index}",
                budget=budget,
            )
            after = {
                durability.ITEM_SPECS[index].name: read_at(
                    owner, placement_spec(index, mode, config)
                )["recovered_deposit"]
                for index in indices
            }
            page_after = durability.page_sha256(owner.state.resonant_workspace)
        finally:
            owner.close()
            shutil.rmtree(home, ignore_errors=True)
        baselines.append(before)
        probes.append(
            {
                "probe_item": durability.ITEM_SPECS[probe_index].name,
                "probe_item_index": int(probe_index),
                "probe_placement_item": probe_spec.name,
                "write": write,
                "page_moved": bool(page_after != durability.page_sha256(page)),
            }
        )
        columns.append(
            [
                (
                    float(after[name]) - float(before[name])
                )
                / (float(amplitude) if float(amplitude) != 0.0 else 1.0)
                for name in names
            ]
        )
    matrix = np.asarray(columns, dtype=np.float64).T  # rows = read items, cols = probes
    singular = np.linalg.svd(matrix, compute_uv=False).tolist() if matrix.size else []
    return {
        "mode": str(mode),
        "amplitude": float(amplitude),
        "zero_probe": bool(zero_probe),
        "item_names": names,
        "matrix": matrix.tolist(),
        "singular_values": [float(value) for value in singular],
        "largest_singular_value": float(singular[0]) if singular else 0.0,
        "smallest_singular_value": float(singular[-1]) if singular else 0.0,
        "baselines": baselines,
        "probes": probes,
        "probe_page_sha256": durability.page_sha256(page),
        "zero_work_probes_are_rejected": bool(
            zero_probe and all(not probe["write"]["accepted"] for probe in probes)
        ),
    }


def tolerance(
    declared: Mapping[str, Any],
    config: AddressingRankConfig,
    *,
    half: Mapping[str, Any] | None = None,
    floor_value: float | None = None,
) -> dict[str, Any]:
    """The declared rank tolerance: the finite-difference floor and the scale floor."""

    if half is not None:
        difference = np.asarray(declared["matrix"], dtype=np.float64) - np.asarray(
            half["matrix"], dtype=np.float64
        )
        consistency = (
            float(np.linalg.svd(difference, compute_uv=False)[0])
            if difference.size
            else 0.0
        )
        source = "measured on this arm's own two probe works"
    else:
        if floor_value is None:
            raise ValueError("a rank tolerance needs either the half probe or a measured floor")
        consistency = float(floor_value)
        source = "reused from the measured floor of the arm carrying this page's half probe"
    scale_floor = float(config.epsilon_factor) * float(declared["largest_singular_value"])
    floor = float(config.floor_factor) * consistency
    return {
        "declared": (
            "tol = max(FLOOR_FACTOR * sigma_1(J(a) - J(a/2)), EPS_FACTOR * sigma_1(J)): "
            "the first term is the measured finite-difference floor from the two probe "
            "works, the second the declared numerical floor relative to the map's own "
            "scale"
        ),
        "finite_difference_floor": consistency,
        "finite_difference_floor_source": source,
        "finite_difference_term": floor,
        "scale_term": scale_floor,
        "tolerance": max(floor, scale_floor),
        "relative_to_the_largest_singular_value": (
            max(floor, scale_floor) / float(declared["largest_singular_value"])
            if float(declared["largest_singular_value"]) > 0.0
            else 0.0
        ),
    }


def rank_reading(
    declared: Mapping[str, Any],
    config: AddressingRankConfig,
    *,
    half: Mapping[str, Any] | None = None,
    floor_value: float | None = None,
) -> dict[str, Any]:
    """The declared rank reading at one state or arm."""

    matrix = np.asarray(declared["matrix"], dtype=np.float64)
    count = int(matrix.shape[0])
    declared_tolerance = tolerance(
        declared, config, half=half, floor_value=floor_value
    )
    values = [float(value) for value in declared["singular_values"]]
    above = [value for value in values if value > declared_tolerance["tolerance"]]
    return {
        "items": count,
        "singular_values": values,
        "singular_values_half_probe": (
            [float(value) for value in half["singular_values"]] if half is not None else None
        ),
        "tolerance": declared_tolerance,
        "rank": int(len(above)),
        "rank_deficiency": int(count - len(above)),
        "the_map_is_full_rank": bool(len(above) == count),
        "smallest_singular_value_against_tolerance": (
            float(values[-1]) / float(declared_tolerance["tolerance"])
            if values and float(declared_tolerance["tolerance"]) > 0.0
            else None
        ),
    }


def separation_reading(declared: Mapping[str, Any], config: AddressingRankConfig) -> dict[str, Any]:
    """The declared pairwise separation of items and of probe directions."""

    matrix = np.asarray(declared["matrix"], dtype=np.float64)
    names = list(declared["item_names"])
    diagonal = np.diag(matrix)
    scale_factor = float(np.mean(diagonal)) if diagonal.size else 0.0
    normalized = matrix / scale_factor if scale_factor != 0.0 else matrix
    rows = {
        left: {
            right: float(np.max(np.abs(normalized[i] - normalized[k])))
            for k, right in enumerate(names)
        }
        for i, left in enumerate(names)
    }
    columns = {
        left: {
            right: float(np.max(np.abs(normalized[:, j] - normalized[:, l])))
            for l, right in enumerate(names)
        }
        for j, left in enumerate(names)
    }
    row_pairs = [
        (left, right, value)
        for left, row in rows.items()
        for right, value in row.items()
        if left != right
    ]
    column_pairs = [
        (left, right, value)
        for left, row in columns.items()
        for right, value in row.items()
        if left != right
    ]
    distinguishable_rows = [
        pair for pair in row_pairs if float(pair[2]) > float(config.contrast_floor)
    ]
    return {
        "declared": (
            "Jn = J / mean(diag(J)); the separation of items i and k is the largest "
            "absolute difference between their normalized rows, and the separation of "
            "probe directions j and l the same between their columns. An orthogonal "
            "pair is predicted at 1 and a duplicated pair at 0"
        ),
        "normalization": float(scale_factor),
        "normalized_matrix": normalized.tolist(),
        "item_separation_matrix": rows,
        "probe_separation_matrix": columns,
        "item_pairs": [
            {"left": left, "right": right, "separation": value}
            for left, right, value in row_pairs
        ],
        "probe_pairs": [
            {"left": left, "right": right, "separation": value}
            for left, right, value in column_pairs
        ],
        "least_item_separation": min((float(pair[2]) for pair in row_pairs), default=None),
        "least_probe_separation": min(
            (float(pair[2]) for pair in column_pairs), default=None
        ),
        "greatest_item_separation": max((float(pair[2]) for pair in row_pairs), default=None),
        "distinguishable_item_pairs": len(distinguishable_rows),
        "item_pairs_measured": len(row_pairs),
        "every_item_pair_is_distinguishable": bool(
            len(distinguishable_rows) == len(row_pairs) and len(row_pairs) > 0
        ),
        "no_item_pair_is_distinguishable": bool(len(distinguishable_rows) == 0),
        "the_rows_are_identical": bool(
            len(row_pairs) > 0
            and all(float(pair[2]) <= float(config.contrast_floor) for pair in row_pairs)
        ),
        "the_columns_are_identical": bool(
            len(column_pairs) > 0
            and all(
                float(pair[2]) <= float(config.contrast_floor) for pair in column_pairs
            )
        ),
        "contrast_floor": float(config.contrast_floor),
        "predicted_separation_of_an_orthogonal_pair": 1.0,
        "predicted_separation_of_a_duplicated_pair": 0.0,
    }


def arm_block(
    profile: Any,
    config: AddressingRankConfig,
    page: Any,
    *,
    mode: str,
    label: str,
    page_record: Mapping[str, Any],
    with_zero: bool = False,
    floor_value: float | None = None,
) -> dict[str, Any]:
    """One arm's own readings at one page state.

    The half-probe sweep is run exactly when this arm is the one that measures the
    page's finite-difference floor; an arm handed a measured floor skips it and
    reuses that floor as its declared tolerance term.
    """

    declared = jacobian(
        profile,
        config,
        page,
        mode=mode,
        amplitude=float(config.probe_budget),
    )
    half = (
        jacobian(
            profile,
            config,
            page,
            mode=mode,
            amplitude=float(config.probe_budget) / 2.0,
        )
        if floor_value is None
        else None
    )
    zero = (
        jacobian(profile, config, page, mode=mode, amplitude=0.0, zero_probe=True)
        if with_zero
        else None
    )
    reading = rank_reading(
        declared, config, half=half, floor_value=floor_value if half is None else None
    )
    separation = separation_reading(declared, config)
    return {
        "label": str(label),
        "mode": str(mode),
        "page": dict(page_record),
        "map": declared,
        "map_at_half_probe": half,
        "zero_probe_map": zero,
        "rank": reading,
        "separation": separation,
        "zero_probe_greatest_response": (
            None
            if zero is None
            else max(
                (abs(float(value)) for row in zero["matrix"] for value in row), default=0.0
            )
        ),
    }


# --------------------------------------------------------------------------
# the crowded store state, through the store-scale runner's own machinery
# --------------------------------------------------------------------------
def hold_settings(
    profile: Any, config: AddressingRankConfig
) -> tuple[Any, float, float, dict[int, Any]]:
    """The measured hold settings the store-scale runner's store episode needs."""

    store_config = replace(
        config.store_config,
        item_indices=tuple(int(index) for index in config.item_indices),
        hold_horizon_ticks=int(config.hold_ticks),
        neutrality_probe_items=(),
    )
    capture_sequences = durability.capture_items(
        durability.DurabilityConfig(write_budget=float(store_config.write_budget)), profile
    )
    phase_reference = consumer.phase_reference_for(profile, capture_sequences)
    refinement = consumer.neutral_gain_refinement(
        profile,
        capture_sequences,
        phase_reference,
        consumer.MemoryConsumerConfig(write_budget=float(store_config.write_budget)),
    )
    gain = float(refinement["measured_gain"])
    loop = feedback.FeedbackConfig()
    indices = tuple(int(index) for index in config.item_indices)
    readouts = feedback.item_phase_readouts(
        loop,
        capture_sequences,
        profile,
        ticks=int(store_config.store_phase_readout_ticks),
        indices=indices,
    )
    per_item = feedback.per_item_phase_references(
        loop, capture_sequences, readouts, indices
    )
    return capture_sequences, gain, float(loop.neutral_gain_phase_degrees), per_item


def held_state(
    profile: Any,
    config: AddressingRankConfig,
    *,
    indices: Sequence[int],
    gain: float,
    phase_degrees: float,
    phase_references: Mapping[int, Mapping[str, Any]],
    captures: Sequence[Mapping[str, Any]],
    label: str,
) -> dict[str, Any]:
    """One held store state, built by the store-scale runner's own store episode."""

    store_config = replace(
        config.store_config,
        item_indices=tuple(int(index) for index in indices),
        hold_horizon_ticks=int(config.hold_ticks),
        neutrality_probe_items=(),
    )
    record, page = scale.store_episode(
        profile,
        captures,
        store_config,
        gain=float(gain),
        phase_degrees=float(phase_degrees),
        phase_references=phase_references,
    )
    return {
        "label": str(label),
        "item_indices": [int(index) for index in indices],
        "held_page_sha256": str(record["held_page_sha256"]),
        "held_page_object": page,
        "measured_deposits": dict(record["measured_deposits"]),
        "reads_after_the_hold": dict(record["reads_after_the_hold"]),
        "hold_horizon_ticks": int(record["horizon_ticks"]),
        "hold_horizon_parity": str(record["horizon_parity"]),
        "drive_calls": int(record["drive_calls"]),
        "frame_energy_ratio_at_horizon": float(record["frame_energy_ratio_at_horizon"]),
        "owner_route_reproduces_the_declared_loop": bool(
            record["owner_route_against_the_declared_loop"][
                "the_owner_route_reproduces_the_declared_loop"
            ]
        ),
    }


def part_one(
    profile: Any,
    config: AddressingRankConfig,
    *,
    crowded: Mapping[str, Any],
    reference: Mapping[str, Any],
    reference_arm: Mapping[str, Any],
) -> dict[str, Any]:
    """Part one: the rank reading at the crowded state against the reference state."""

    crowded_rank = crowded["rank"]
    reference_rank = reference_arm["rank"]
    items = int(crowded_rank["items"])
    crowded_full = bool(crowded_rank["the_map_is_full_rank"])
    reference_full = bool(reference_rank["the_map_is_full_rank"])
    deposit_constant = bool(
        crowded["deposits"]["the_deposit_vector_is_constant_at_the_tolerance"]
    )
    relative_spread = float(crowded["deposits"]["the_deposit_vector_relative_difference"])
    if crowded_full and reference_full and not deposit_constant:
        verdict = (
            "the degeneracy is in the readout cells, not in the map: the deposit map "
            "at the crowded held state is full rank and separates items at "
            f"{crowded['arm']['separation']['least_item_separation']!r}, so the store "
            "carries every declared item at this operating point, and the deposit "
            f"vector itself is not constant either (relative spread {relative_spread:.3e}); "
            "the cross-item cells the store-scale receipt reported as degenerate are "
            "read/deposit ratios whose denominator is the equal written deposit"
        )
    elif crowded_full and reference_full and deposit_constant:
        verdict = (
            "readout-only collapse, in the strict sense: the map is full rank at the "
            "crowded state and the deposit vector is constant at the declared tolerance, "
            "so the store carries every item and only the scalar deposit is constant"
        )
    elif not crowded_full and reference_full:
        verdict = "the store cannot carry the declared items at the crowded operating point"
    elif not reference_full:
        verdict = "undetermined: the reference state is not full rank either, so the rank reading separates nothing here"
    else:
        verdict = "undetermined: the crowded state is full rank but the reference state is not"
    return {
        "declared": (
            "the rank reading of the declared deposit map at the crowded store state "
            "(the store-scale runner's own held store over the declared items) and at a "
            "one-item reference state built by the same machinery; the deposit vector "
            "itself and its first differences are read the same way"
        ),
        "items": items,
        "crowded": {
            "state": crowded["state"],
            "rank": crowded_rank,
            "deposit_differences": crowded["deposits"],
            "separation": crowded["arm"]["separation"],
        },
        "reference": {
            "state": reference,
            "rank": reference_rank,
            "deposit_differences": reference_arm["deposits"],
        },
        "verdict": verdict,
        "the_crowded_state_is_full_rank": crowded_full,
        "the_reference_state_is_full_rank": reference_full,
        "the_crowded_deposit_vector_is_constant_at_the_tolerance": deposit_constant,
        "the_crowded_deposit_vector_relative_difference": relative_spread,
        "the_verdict_locates_the_degeneracy_outside_the_map": bool(
            crowded_full and reference_full
        ),
        "the_verdict_is_a_store_limitation": bool(not crowded_full and reference_full),
    }


def part_two(arms: Mapping[str, Mapping[str, Any]], config: AddressingRankConfig) -> dict[str, Any]:
    """Part two: placement, pairwise separation and rank across the declared arms."""

    indices = tuple(int(index) for index in config.item_indices)
    shared = arms["shared"]
    specific = arms["specific"]
    duplicate = arms["duplicate"]
    duplicated_pair = (
        durability.ITEM_SPECS[indices[0]].name,
        durability.ITEM_SPECS[indices[1]].name,
    )
    duplicate_pair_row = [
        pair
        for pair in duplicate["separation"]["item_pairs"]
        if {pair["left"], pair["right"]} == set(duplicated_pair)
    ]
    duplicate_pair_value = (
        float(duplicate_pair_row[0]["separation"]) if duplicate_pair_row else None
    )
    specific_tolerance = float(specific["rank"]["tolerance"]["tolerance"])
    predicted = (
        1.0 - float(config.loss_allowance)
    )
    predicates = {
        "the_specific_arm_is_full_rank": bool(specific["rank"]["the_map_is_full_rank"]),
        "the_shared_arm_is_rank_deficient": bool(
            not shared["rank"]["the_map_is_full_rank"]
        ),
        "the_duplicate_arm_has_rank_one_below_the_item_count": bool(
            int(duplicate["rank"]["rank"]) == int(duplicate["rank"]["items"]) - 1
        ),
        "the_specific_arm_separates_every_pair": bool(
            specific["separation"]["every_item_pair_is_distinguishable"]
        ),
        "the_specific_arm_reaches_the_predicted_separation": bool(
            specific["separation"]["least_item_separation"] is not None
            and float(specific["separation"]["least_item_separation"]) >= predicted
        ),
        "the_shared_arm_separates_no_pair": bool(
            shared["separation"]["no_item_pair_is_distinguishable"]
        ),
        "the_duplicated_pair_shows_zero_separation": bool(
            duplicate_pair_value is not None
            and float(duplicate_pair_value) <= float(config.contrast_floor)
        ),
        "the_rank_reading_fires_on_the_duplicated_placement": bool(
            int(duplicate["rank"]["rank"]) < int(duplicate["rank"]["items"])
        ),
    }
    restores = bool(
        predicates["the_specific_arm_is_full_rank"]
        and predicates["the_shared_arm_is_rank_deficient"]
        and predicates["the_duplicate_arm_has_rank_one_below_the_item_count"]
        and predicates["the_specific_arm_separates_every_pair"]
        and predicates["the_shared_arm_separates_no_pair"]
        and predicates["the_duplicated_pair_shows_zero_separation"]
    )
    if restores:
        verdict = (
            "item-specific placement is the addressing: at the same page state the "
            "specific arm carries every item and separates every pair at the predicted "
            "separation, while the shared arm carries one direction and the duplicated "
            "placement costs exactly one dimension"
        )
    elif not predicates["the_specific_arm_separates_every_pair"]:
        verdict = (
            "no at this operating point: item-specific placement does not separate "
            "every pair of declared items at the crowded page state"
        )
    else:
        verdict = "partial: the placement arms disagree with the declared rule; the failing predicates are listed"
    return {
        "declared": (
            "the same crowded page state addressed three ways: every item at its own "
            "declared placement, every item at one shared placement, and the declared "
            "duplicate control in which the second item is addressed at the first's "
            "placement; each arm reports its deposit map, its rank reading and its "
            "pairwise separation matrices"
        ),
        "crowded_page_sha256": specific["page"]["written_page_sha256"],
        "the_three_arms_read_one_page": bool(
            shared["page"]["written_page_sha256"]
            == specific["page"]["written_page_sha256"]
            == duplicate["page"]["written_page_sha256"]
        ),
        "duplicated_pair": {
            "items": list(duplicated_pair),
            "separation": duplicate_pair_value,
            "contrast_floor": float(config.contrast_floor),
        },
        "specific_tolerance": specific_tolerance,
        "predicted_separation_of_an_orthogonal_pair": 1.0,
        "required_separation_for_the_specific_arm": predicted,
        "arms": {
            name: {
                "mode": arm["mode"],
                "label": arm["label"],
                "page": arm["page"],
                "map": arm["map"],
                "map_at_half_probe": arm["map_at_half_probe"],
                "zero_probe_map": arm["zero_probe_map"],
                "rank": arm["rank"],
                "separation": arm["separation"],
                "zero_probe_greatest_response": arm["zero_probe_greatest_response"],
            }
            for name, arm in arms.items()
        },
        "predicates": predicates,
        "item_specific_placement_restores_the_rank": restores,
        "verdict": verdict,
        "failing_predicates": [
            name for name, value in predicates.items() if not value
        ],
    }


# --------------------------------------------------------------------------
# receipt
# --------------------------------------------------------------------------
def build_receipt(config: AddressingRankConfig | None = None) -> dict[str, Any]:
    """Every declared measurement, assembled into one receipt."""

    settings = config or AddressingRankConfig()
    started = time.perf_counter()
    profile = scale.flat_profile()
    indices = tuple(int(index) for index in settings.item_indices)
    if len(indices) < 3:
        raise ValueError("the declared measurement needs at least three declared items")

    captures, gain, phase_degrees, per_item = hold_settings(profile, settings)
    crowded_record = held_state(
        profile,
        settings,
        indices=indices,
        gain=gain,
        phase_degrees=phase_degrees,
        phase_references=per_item,
        captures=captures,
        label="crowded-held-store",
    )
    reference_record = held_state(
        profile,
        settings,
        indices=indices[:1],
        gain=gain,
        phase_degrees=phase_degrees,
        phase_references=per_item,
        captures=captures,
        label="one-item-reference",
    )
    crowded_page = crowded_record.pop("held_page_object")
    reference_page = reference_record.pop("held_page_object")

    # The arms all address one page built from the declared writes, so the only
    # thing that changes between them is the placement.
    page, page_record = page_with(
        profile, settings, indices, mode="specific", label="srank:crowded-written"
    )
    arms = {
        "specific": arm_block(
            profile,
            settings,
            page,
            mode="specific",
            label="crowded-written-specific",
            page_record=page_record,
            with_zero=True,
        )
    }
    measured_floor = float(
        arms["specific"]["rank"]["tolerance"]["finite_difference_floor"]
    )
    for mode in ("shared", "duplicate"):
        arms[mode] = arm_block(
            profile,
            settings,
            page,
            mode=mode,
            label=f"crowded-written-{mode}",
            page_record=page_record,
            floor_value=measured_floor,
        )

    crowded_deposits = deposit_vector(profile, settings, crowded_page, mode="specific")
    reference_deposits = deposit_vector(profile, settings, reference_page, mode="specific")
    crowded_arm = arm_block(
        profile,
        settings,
        crowded_page,
        mode="specific",
        label="crowded-held-specific",
        page_record={"held_page_sha256": crowded_record["held_page_sha256"]},
    )
    reference_arm = arm_block(
        profile,
        settings,
        reference_page,
        mode="specific",
        label="one-item-reference-specific",
        page_record={"held_page_sha256": reference_record["held_page_sha256"]},
    )
    blank_owner, blank_home = consumer.open_owner(
        profile, prefix=settings.owner_home_prefix
    )
    try:
        blank_page_digest = durability.page_sha256(blank_owner.state.resonant_workspace)
        blank_page_reads = {
            durability.ITEM_SPECS[index].name: read_at(
                blank_owner, placement_spec(index, "specific", settings)
            )["recovered_deposit"]
            for index in indices
        }
    finally:
        blank_owner.close()
        shutil.rmtree(blank_home, ignore_errors=True)
    part_1 = part_one(
        profile,
        settings,
        crowded={
            "state": {
                **crowded_record,
                "deposits": crowded_deposits["values"],
            },
            "rank": crowded_arm["rank"],
            "deposits": difference_reading(crowded_deposits, settings),
            "arm": crowded_arm,
        },
        reference={
            **reference_record,
            "deposits": reference_deposits["values"],
        },
        reference_arm={
            "rank": reference_arm["rank"],
            "deposits": difference_reading(reference_deposits, settings),
        },
    )
    part_1["reference"]["arm"] = {
        "rank": reference_arm["rank"],
        "separation": reference_arm["separation"],
        "zero_probe_greatest_response": reference_arm["zero_probe_greatest_response"],
    }
    part_2 = part_two(arms, settings)
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "question": (
            "inside a crowded store, is the item-to-deposit map rank-deficient, and "
            "does item-dependent placement restore the rank a shared placement cannot "
            "carry?"
        ),
        "declared": {
            "config": settings.as_dict(),
            "statistic": (
                "J[i][j] = (read at item i's placement after a probe write at item j's "
                "placement minus the same read before) / probe work, one fresh owner per "
                "probe on one page; tol = max(FLOOR_FACTOR * sigma_1(J(a) - J(a/2)), "
                "EPS_FACTOR * sigma_1(J)); rank = the count of singular values above tol"
            ),
            "discriminator": (
                "Jn = J / mean(diag(J)); item separation s(i,k) = max_j |Jn[i][j] - "
                "Jn[k][j]| and probe separation t(j,l) = max_i |Jn[i][j] - Jn[i][l]|; a "
                "pair is distinguishable when its separation exceeds CONTRAST_FLOOR"
            ),
            "decision_rule": (
                "part 1: full rank at the crowded state means the store carries every "
                "item and the degeneracy sits in the readout rather than in the map; the "
                "deposit vector's own constancy is measured and reported as its own "
                "predicate. A crowded deficiency with a full-rank reference means the "
                "store cannot carry the items there. part 2: item-specific placement "
                "restores the rank iff the specific arm is full rank and separates every "
                "pair at 1 - LOSS_ALLOWANCE, the shared arm separates no pair and is "
                "deficient, the duplicate arm has rank one below the item count, and the "
                "duplicated pair sits at CONTRAST_FLOOR"
            ),
            "controls": {
                "duplicated_item": (
                    "the duplicate arm addresses the second declared item at the first's "
                    "placement: its pair must sit at the contrast floor and its rank must "
                    "be exactly one below the item count"
                ),
                "predicted_separation": (
                    "an orthogonal pair is predicted at 1.0 after normalization and the "
                    "specific arm must reach 1 - LOSS_ALLOWANCE of it"
                ),
                "shared_placement": (
                    "the shared arm addresses every item at one placement: no pair may be "
                    "distinguishable"
                ),
                "rank_firing_control": (
                    "the duplicate arm's deficiency is the measured instance that proves "
                    "the rank reading can fall below the item count"
                ),
                "zero_work_probe": (
                    "a probe at zero work must move no read and must be rejected: the "
                    "declared instance is the specific arm at the crowded written page, "
                    "where every probe is repeated at zero work"
                ),
                "unwritten_page": (
                    "the read on a page nothing was written to is reported against the "
                    "same placements"
                ),
                "finite_difference_floor": (
                    "the finite-difference floor is measured on the arm that carries each "
                    "page's half probe -- the specific arm at the crowded written page, "
                    "the crowded arm at the crowded held state, the reference arm at the "
                    "reference state -- and that measured floor is reused by the other "
                    "arms at the same page, with each arm's own largest singular value "
                    "supplying its own scale term"
                ),
            },
            "content_digest_definition": (
                "the store-scale runner's declared content digest, reused here: sha256 of "
                "the canonical JSON of the body with the declared clock leaves and the "
                "declared clock-derived digests stripped, taken before the digest is "
                "attached"
            ),
            "content_digest_strip_keys": list(scale.STRIP_KEYS),
            "content_digest_strip_keys_source": (
                "run_memory_store_scale.STRIP_KEYS (the geometry harness's clock leaves "
                "plus the declared clock-derived digests), reused rather than re-derived"
            ),
            "content_digest_rule": (
                "the same declared rule as the store-scale receipt: derived-from-stripped "
                "values are stripped as a class"
            ),
        },
        "part_one": part_1,
        "part_two": part_2,
        "blank_page_reads": {
            "declared": (
                "every declared placement read on a fresh owner's blank page, with the "
                "same read call the arms use"
            ),
            "page_sha256": blank_page_digest,
            "readings": blank_page_reads,
            "greatest_read": max(
                (abs(float(value)) for value in blank_page_reads.values()), default=0.0
            ),
            "the_blank_page_reads_nothing": bool(
                max(
                    (abs(float(value)) for value in blank_page_reads.values()),
                    default=0.0,
                )
                <= float(settings.epsilon_factor)
            ),
        },
        "runtime_seconds": float(time.perf_counter() - started),
    }
    body["reading"] = reading_block(body)
    scale.assert_finite(body)
    body["receipt_digest"] = scale.receipt_digest(body)
    return body


def reading_block(body: Mapping[str, Any]) -> dict[str, Any]:
    """What the measured blocks say, in one reading."""

    part_1 = body["part_one"]
    part_2 = body["part_two"]
    return {
        "part_one_verdict": part_1["verdict"],
        "part_two_verdict": part_2["verdict"],
        "predicate": (
            "the declared decision predicates: in part two the rank, separation, "
            "control and firing predicates of the three placement arms, and the joint "
            "restoration predicate they compose. Every one of these must hold for the "
            "declared rule to hold"
        ),
        "verdicts": {
            **part_2["predicates"],
            "item_specific_placement_restores_the_rank": part_2[
                "item_specific_placement_restores_the_rank"
            ],
        },
        "measured_flags": {
            "declared": (
                "flags whose value is a measurement rather than a requirement: a false "
                "here is a finding, not a failed predicate, and the two verdict texts "
                "above are selected from them"
            ),
            "the_crowded_state_is_full_rank": part_1["the_crowded_state_is_full_rank"],
            "the_reference_state_is_full_rank": part_1[
                "the_reference_state_is_full_rank"
            ],
            "the_crowded_deposit_vector_is_constant_at_the_tolerance": part_1[
                "the_crowded_deposit_vector_is_constant_at_the_tolerance"
            ],
            "the_verdict_locates_the_degeneracy_outside_the_map": part_1[
                "the_verdict_locates_the_degeneracy_outside_the_map"
            ],
            "the_verdict_is_a_store_limitation": part_1[
                "the_verdict_is_a_store_limitation"
            ],
        },
        "limitations": [
            "the crowded state is one declared operating point: the declared items, the "
            "declared write budget, the declared hold horizon and this profile; nothing "
            "here measures a distribution over densities, gates or profiles",
            "the rank reading is a finite-difference reading of a deterministic map, so "
            "its floor is the measured finite-difference floor plus the declared relative "
            "numerical floor, and a deficiency below that floor would not be visible",
            "the shared arm's zero separation is the declared structural control: when "
            "every item is addressed at one placement the read is the same call, so the "
            "arm measures the addressing semantics rather than a dynamical collapse",
            "the arms address one written page; the store-scale hold's own doubling is "
            "not exercised in the placement arms, only at the crowded held state of part "
            "one",
        ],
        "not_shown": [
            "which dynamical property of the field the collapse tracks (density, gate "
            "value, local rate) is not measured here",
        ],
    }


def report(receipt: Mapping[str, Any]) -> str:
    """The receipt's own figures, verdict first."""

    lines = [f"schema: {receipt['schema']}"]
    part_1 = receipt["part_one"]
    part_2 = receipt["part_two"]
    lines.append(f"part 1 verdict: {part_1['verdict']}")
    lines.append(f"part 2 verdict: {part_2['verdict']}")
    lines.append("figures:")
    crowded = part_1["crowded"]
    lines.append(
        f"  crowded held store: rank {crowded['rank']['rank']}/{crowded['rank']['items']}, "
        f"sigma_min {crowded['rank']['singular_values'][-1]!r}, tol "
        f"{crowded['rank']['tolerance']['tolerance']!r}, "
        f"sigma_min/tol {crowded['rank']['smallest_singular_value_against_tolerance']!r}"
    )
    lines.append(
        "  crowded deposits " + ", ".join(
            f"{name}={value!r}" for name, value in crowded["state"]["deposits"].items()
        )
    )
    lines.append(
        "  crowded deposit first differences "
        f"{crowded['deposit_differences']['first_differences']!r} (tolerance "
        f"{crowded['deposit_differences']['tolerance']!r}, constant "
        f"{crowded['deposit_differences']['the_deposit_vector_is_constant_at_the_tolerance']}, "
        f"relative spread "
        f"{crowded['deposit_differences']['the_deposit_vector_relative_difference']:.3e})"
    )
    lines.append(
        "  crowded item separation "
        f"least {crowded['separation']['least_item_separation']!r} greatest "
        f"{crowded['separation']['greatest_item_separation']!r}"
    )
    reference = part_1["reference"]
    lines.append(
        f"  one-item reference: rank {reference['rank']['rank']}/{reference['rank']['items']}, "
        f"sigma_min {reference['rank']['singular_values'][-1]!r}, tol "
        f"{reference['rank']['tolerance']['tolerance']!r}"
    )
    for name, arm in part_2["arms"].items():
        rank = arm["rank"]
        separation = arm["separation"]
        lines.append(
            f"  arm {name:<10} rank {rank['rank']}/{rank['items']} "
            f"least item separation {separation['least_item_separation']!r} "
            f"distinguishable pairs {separation['distinguishable_item_pairs']}/"
            f"{separation['item_pairs_measured']} "
            f"zero-probe {arm['zero_probe_greatest_response']!r}"
        )
    lines.append(
        "  duplicated pair " + str(part_2["duplicated_pair"])
    )
    lines.append("verdicts:")
    for name, value in receipt["reading"]["verdicts"].items():
        lines.append(f"  {name}: {value}")
    lines.append("measured flags:")
    for name, value in receipt["reading"]["measured_flags"].items():
        if name == "declared":
            continue
        lines.append(f"  {name}: {value}")
    lines.append(f"receipt_digest: {receipt['receipt_digest']}")
    lines.append(f"runtime_seconds: {receipt['runtime_seconds']:.2f}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=RECEIPT_PATH)
    parser.add_argument("--items", type=int, default=len(ITEM_INDICES))
    arguments = parser.parse_args(argv)
    indices = tuple(range(int(arguments.items)))
    settings = AddressingRankConfig(
        item_indices=indices,
        store_config=replace(
            AddressingRankConfig().store_config,
            item_indices=indices,
            neutrality_probe_items=(),
        ),
    )
    receipt = build_receipt(settings)
    output = Path(arguments.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(receipt, indent=1, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(report(receipt))
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
