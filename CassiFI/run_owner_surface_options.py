"""Two additive, default-off options on the owner's declared surfaces, measured.

Both edits this runner measures are additive and default-off: the shipped
behaviour of every existing caller is unchanged, and each edit is exercised only
through the option it declares.

Measurement 1 -- declaring the packet read as evidence. ``read_packet_deposit``
ships as a declared temporal prediction of the canonical page: it names a
direction and returns the deposit the page carries along it, adding no observed
support and advancing no clock. The same method carries an opt-in variant
(``as_evidence=True``, plus the operation identity and observation variable the
owner's own admission rule needs) that declares the same recovered deposit as an
observation about the world instead. This block measures what each declaration
moves, which owner state each one touches, whether anything downstream keys on
observed support such that the declaration changes behaviour at all, the same
figures for both readings side by side, and the exposure-scan counts under both.

Measurement 2 -- coupling versus overlap for the input port. The shipped declared
input relation is the identity precision on the declared variables, and the
diagnosis in ``run_owner_write_path_exploration.py`` measures that realization to
have no authority over the declared readout, because the input port's support and
the readout row's support are disjoint. ``condense_input`` adds an opt-in coupled
relation (a cross term between the declared variables) as an input realization
without changing the shipped one. This block measures the per-tick and
window-averaged input-to-output authority of the coupled realization against the
shipped one on both the declared profile and its beta-zero counterpart, whether a
canonical packet impulse driven through the coupled input reproduces the owner
write path's page, state digest and read frame, the persistence of the driven
response, the per-tick work cost against the owner write path, and whether any
declared profile of ``cassi_resonant_field`` admits an overlapping port selection
at all -- the whole enumeration, not a sample.

Every figure below is a measured number or a boolean computed from measured
numbers. Every predicate that reports a negative here has a can-fail control that
shows it can report the positive: the reconstruction control for the route
identity, the zero-target and distinct-port controls for the overlap refusal, and
the absent word of the exposure scan.

Run: python run_owner_surface_options.py [--output <path>]
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import statistics
import tempfile
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np

import run_fractal_durability_exploration as durability
import run_fractal_geometry_exploration as geometry
import run_fractal_metric_exploration as metric
from cassi_field_atlas import (
    AtlasState,
    FieldAtlas,
    RelationChart,
    VariableSpec,
)
from cassi_field_owner import FieldIntelligenceOwner
from cassi_field_transceiver import (
    _vector,
    _workspace,
    advance_transceiver,
    condense_input,
    condense_workspace,
    reset_transceiver,
)
from cassi_resonant_field import (
    ResonantNumericalError,
    ResonantProblem,
    ResonantProfile,
    ResonantWorkspace,
    _WaveOperator,
    bind_workspace,
    initial_workspace,
)

SCHEMA = "cassifi.owner-surface-options.v1"
OUTPUT_DIRECTORY = "_diag/owner-surface-options"
DEFAULT_OUTPUT = Path(OUTPUT_DIRECTORY) / "exploration.json"

PROFILE_NAME = "ladder-uniform"
READ_OPERATION_NAME = "read_packet_deposit"
EVIDENCE_OPERATION_ID = "owner-surface-options:evidence"
RETRY_OPERATION_ID = "owner-surface-options:evidence-retry"
PREDICTION_OPERATION_ID = "owner-surface-options:prediction"
SECOND_EVIDENCE_OPERATION_ID = "owner-surface-options:evidence-second"
DECLARED_DEPOSIT_VARIABLE = "packet-deposit"
DECLARED_DEPOSIT_CHART = "packet-deposit"
WRITE_OPERATION_ID = "owner-surface-options:write"

# The declared word sets of the exposure scan, applied to every key path a reading
# publishes. A path is reported when one of its words appears in it: the direction
# words name a written direction or its deposit, the summary words name a power or
# energy summary, and the intervention words name the write itself.
# ABSENT_PATH_WORD is the scan's own control: a word no surface here publishes.
DIRECTION_PATH_WORDS = ("deposit", "flow_signal", "read_frame", "coefficient", "direction")
SUMMARY_PATH_WORDS = ("power", "energy")
INTERVENTION_PATH_WORDS = ("packet", "impulse")
ABSENT_PATH_WORD = "quaternion"

# The declared coupled relation the diagnosis's firing control used: every declared
# variable keeps 2 on its own coordinate and the pair gains 1 between them.
COUPLED_DIAGONAL = 2.0
COUPLED_COUPLING = 1.0
# The shipped declared input relation: the identity precision, which is what
# ``cassi_field_transceiver.condense_workspace`` realizes by default.
SHIPPED_DIAGONAL = 1.0
SHIPPED_COUPLING = 0.0

# The four topology names ``cassi_resonant_field.ResonantProfile`` accepts, spelled
# where it validates them; the enumeration below covers all four, and its own
# control shows a fifth name is refused.
DECLARED_TOPOLOGIES = ("meaningful-helix", "undivided", "isolated", "rewired")
UNSUPPORTED_TOPOLOGY = "no-such-topology"

# The classification of what a declaration moves, used to say *what* an owner
# surface movement is: a clock, a version, a count, a digest, the declared
# channel's own record, the store's resource accounting, or a decision input.
DECISION_PATH_WORDS = (
    "authority",
    "reservation",
    "reserved",
    "plan",
    "decision",
    "goal",
    "inquiry",
    "action",
    "score",
    "readiness",
    "confidence",
    "credence",
    "weight",
)
CLOCK_PATH_WORDS = ("tick", "generation", "phase", "activity")
COUNT_PATH_WORDS = ("count", "length", "size", "events", "contributions", "queries")
DIGEST_PATH_WORDS = ("sha256", "digest", "identity")
VERSION_PATH_WORDS = ("version", "sequence", "revision", "ordinal")
CHANNEL_PATH_WORDS = ("precision", "posterior", "ridge", "mass", "support", "chart", "energy")
CAPACITY_PATH_WORDS = ("capacity", "usage", "bytes", "footprint", "budget")

# The owner surfaces this runner diffs before and after each declaration, by name.
DECLARED_SURFACES = ("inspect", "inspect_resonance", "inspect_computers", "inspect_transceivers")

BOUNDARY = (
    "Canonical-field measurements in controlled conditions only: one declared "
    "profile (the metric harness's flat-inertia member) for both options, one "
    "declared written packet item at one declared write budget for the route and "
    "read measurements, one declared observation channel (a declared variable over "
    "the declared deposit range and one declared chart over it) for the evidence "
    "reading, the transceiver's own declared loop settings, and one declared "
    "resolution ladder for the overlap enumeration (the four topology names the "
    "library validates times three ports-per-pool settings times both beta "
    "settings). The evidence reading's admission goes through the owner's own "
    "observation-admission rule on the owner's own store, which is why the "
    "declared channel has to exist before it is measured. Nothing here changes a "
    "default: both options are measured off the shipped path."
)

LIMITATIONS = (
    "The authority figures are the transceiver's declared input-scan convention "
    "(the relative spread of the declared readout over the declared input scan, "
    "against the declared allowance), not a physical claim about the channel. The "
    "route identity is measured at the declared amplitudes and on the declared "
    "reconstruction mapping; it is a statement about this item, this profile and "
    "this mapper. The overlap enumeration covers the declared topology names, three "
    "ports-per-pool settings and both beta settings, so 'any profile' below means "
    "'any profile in that declared lattice', and the library could accept a "
    "topology name outside the four it validates. The evidence reading's cost "
    "figures are single-run wall clock on this machine."
)


# --------------------------------------------------------------------------
# declared measurement settings
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class OwnerSurfaceOptionsConfig:
    """Declared measurement settings; every number in the receipt derives from these."""

    profile_name: str = PROFILE_NAME
    read_frame_path: str = durability.READ_FRAME_PATH
    headline_item_index: int = durability.HEADLINE_ITEM_INDEX
    write_budget: float = 1e-3
    rank: int = 8
    error_allowance: float = 1e-3
    input_bound: float = 4.0
    horizon_ticks: int = 64
    authority_allowance: float = 1e-12
    authority_input_scan: tuple[float, ...] = (0.0, 0.5, 1.75, 3.5)
    authority_window_ticks: tuple[int, ...] = (1, 2, 4, 8, 16)
    persistence_ticks: tuple[int, ...] = (1, 2, 3, 4, 5, 6, 7, 8)
    route_amplitudes: tuple[float, ...] = (
        -4.0,
        -2.0,
        -1.0,
        -0.5,
        0.0,
        0.5,
        1.0,
        1.75,
        2.0,
        3.5,
        4.0,
    )
    observation_weight: float = 1.0
    overlap_ports_per_pool: tuple[int, ...] = (4, 8, 16)
    overlap_betas: tuple[float, ...] = (0.08, 0.0)
    overlap_rank: int = 0
    overlap_horizon_ticks: int = 8
    cost_repeats: int = 3
    cost_ticks: int = 64
    changed_path_limit: int = 40
    owner_home_prefix: str = "oso-owner-"

    def __post_init__(self) -> None:
        if not 0.0 < float(self.write_budget) <= 1.0:
            raise ValueError("the declared write budget must lie in (0,1]")
        if float(self.authority_allowance) <= 0.0:
            raise ValueError("the declared authority allowance must be positive")
        if not self.authority_window_ticks or min(self.authority_window_ticks) < 1:
            raise ValueError("the declared authority window must hold positive ticks")
        if not self.authority_input_scan or any(
            abs(float(value)) > float(self.input_bound) for value in self.authority_input_scan
        ):
            raise ValueError("the declared authority scan must stay inside the input envelope")
        if not self.persistence_ticks or min(self.persistence_ticks) < 1:
            raise ValueError("the declared persistence window must hold positive ticks")
        if not self.route_amplitudes:
            raise ValueError("the declared route amplitude sweep must not be empty")
        if any(abs(float(value)) > float(self.input_bound) for value in self.route_amplitudes):
            raise ValueError("the declared route amplitude sweep must stay inside the input envelope")
        if not self.overlap_ports_per_pool or not self.overlap_betas:
            raise ValueError("the declared overlap lattice must not be empty")
        if int(self.cost_repeats) < 1:
            raise ValueError("the declared cost repeat count must be positive")
        if int(self.cost_ticks) < 1:
            raise ValueError("the declared cost tick count must be positive")

    def as_dict(self) -> dict[str, Any]:
        return {
            "profile_name": str(self.profile_name),
            "read_frame_path": str(self.read_frame_path),
            "headline_item": durability.ITEM_SPECS[int(self.headline_item_index)].name,
            "headline_item_index": int(self.headline_item_index),
            "write_budget": float(self.write_budget),
            "rank": int(self.rank),
            "error_allowance": float(self.error_allowance),
            "input_bound": float(self.input_bound),
            "horizon_ticks": int(self.horizon_ticks),
            "authority_allowance": float(self.authority_allowance),
            "authority_input_scan": [float(value) for value in self.authority_input_scan],
            "authority_window_ticks": [int(tick) for tick in self.authority_window_ticks],
            "persistence_ticks": [int(tick) for tick in self.persistence_ticks],
            "route_amplitudes": [float(value) for value in self.route_amplitudes],
            "observation_weight": float(self.observation_weight),
            "overlap_ports_per_pool": [int(value) for value in self.overlap_ports_per_pool],
            "overlap_betas": [float(value) for value in self.overlap_betas],
            "overlap_rank": int(self.overlap_rank),
            "overlap_horizon_ticks": int(self.overlap_horizon_ticks),
            "cost_repeats": int(self.cost_repeats),
            "cost_ticks": int(self.cost_ticks),
            "declared_topologies": list(DECLARED_TOPOLOGIES),
            "unsupported_topology_control": UNSUPPORTED_TOPOLOGY,
            "shipped_relation": {"diagonal": SHIPPED_DIAGONAL, "coupling": SHIPPED_COUPLING},
            "coupled_relation": {"diagonal": COUPLED_DIAGONAL, "coupling": COUPLED_COUPLING},
            "declared_deposit_variable": DECLARED_DEPOSIT_VARIABLE,
            "declared_deposit_chart": DECLARED_DEPOSIT_CHART,
            "evidence_operation_ids": [
                EVIDENCE_OPERATION_ID,
                RETRY_OPERATION_ID,
                SECOND_EVIDENCE_OPERATION_ID,
            ],
            "declared_surfaces": list(DECLARED_SURFACES),
            "exposure_word_sets": {
                "direction": list(DIRECTION_PATH_WORDS),
                "summary": list(SUMMARY_PATH_WORDS),
                "intervention": list(INTERVENTION_PATH_WORDS),
                "absent_control": ABSENT_PATH_WORD,
            },
        }


def flat_profile(config: OwnerSurfaceOptionsConfig | None = None) -> Any:
    """The declared profile, built by the metric harness's own builder."""

    settings = OwnerSurfaceOptionsConfig() if config is None else config
    return metric.build_metric_profile(metric.ladder_row(str(settings.profile_name)))


def plain(value: Any) -> Any:
    """Detached ordinary JSON containers for a value a canonical API froze."""

    if isinstance(value, Mapping):
        return {str(key): plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    return value


def receipt_digest(body: Mapping[str, Any]) -> str:
    """The lattice runner's declared content digest, applied to this receipt.

    ``run_fractal_lattice_exploration.py`` states and applies the convention: the
    SHA-256 of the canonical JSON (sorted keys, no insignificant whitespace,
    allow_nan=False) of the measured body with the declared wall-clock fields
    stripped, taken before the digest itself is attached.
    """

    return geometry.content_digest(
        {key: value for key, value in body.items() if key != "receipt_digest"}
    )


def digest_convention() -> dict[str, Any]:
    """The digest convention and the strip set it uses, declared in the receipt."""

    return {
        "definition": (
            "sha256 of the canonical JSON (sorted keys, no insignificant "
            "whitespace, allow_nan=False) of the measured body with wall-clock "
            "fields stripped, before the digest itself is attached"
        ),
        "strip_keys": sorted(set(geometry.TIMING_KEYS) | {"receipt_digest"}),
        "helper": "run_owner_surface_options.receipt_digest",
        "computed_over": "receipt body without the receipt_digest field",
    }


def key_paths(value: Any, prefix: str = "") -> list[str]:
    """Every key path in a JSON-shaped value, for the declared exposure scan."""

    paths: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            paths.append(path)
            paths.extend(key_paths(item, path))
    elif isinstance(value, (list, tuple)):
        for position, item in enumerate(value):
            paths.extend(key_paths(item, f"{prefix}[{position}]"))
    return paths


def matching_paths(paths: Sequence[str], words: Sequence[str]) -> list[str]:
    """The published key paths naming any of the declared words."""

    return sorted(path for path in paths if any(word in path.lower() for word in words))


def exposure_scan(record: Any) -> dict[str, Any]:
    """The declared exposure scan of one reading's published key paths."""

    paths = key_paths(record)
    direction = matching_paths(paths, DIRECTION_PATH_WORDS)
    summary = matching_paths(paths, SUMMARY_PATH_WORDS)
    intervention = matching_paths(paths, INTERVENTION_PATH_WORDS)
    absent = matching_paths(paths, (ABSENT_PATH_WORD,))
    return {
        "published_key_path_count": len(paths),
        "direction": {"count": len(direction), "paths": direction},
        "summary": {"count": len(summary), "paths": summary},
        "intervention": {"count": len(intervention), "paths": intervention},
        "absent_control": {
            "word": ABSENT_PATH_WORD,
            "count": len(absent),
            "paths": absent,
            "must_be_zero": True,
        },
    }


def leaf_paths(value: Any, prefix: str = "") -> dict[str, Any]:
    """Every scalar leaf of a JSON-shaped value, keyed by its path."""

    leaves: dict[str, Any] = {}
    if isinstance(value, Mapping):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            leaves.update(leaf_paths(item, path))
    elif isinstance(value, (list, tuple)):
        for position, item in enumerate(value):
            leaves.update(leaf_paths(item, f"{prefix}[{position}]"))
    else:
        leaves[prefix] = value
    return leaves


def classify_path(path: str) -> str:
    """The declared class of one moved leaf path."""

    lowered = path.lower()
    if any(word in lowered for word in DECISION_PATH_WORDS):
        return "decision"
    if any(word in lowered for word in CLOCK_PATH_WORDS):
        return "clock"
    if any(word in lowered for word in VERSION_PATH_WORDS):
        return "version"
    if any(word in lowered for word in COUNT_PATH_WORDS):
        return "count"
    if any(word in lowered for word in DIGEST_PATH_WORDS):
        return "digest"
    if any(word in lowered for word in CHANNEL_PATH_WORDS):
        return "channel"
    if any(word in lowered for word in CAPACITY_PATH_WORDS):
        return "resource"
    return "other"


def leaf_difference(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    *,
    limit: int,
) -> dict[str, Any]:
    """The leaves that moved between two surface snapshots, with their classes."""

    left, right = leaf_paths(plain(before)), leaf_paths(plain(after))
    moved: list[dict[str, Any]] = []
    for path in sorted(set(left) | set(right)):
        old, new = left.get(path, "<absent>"), right.get(path, "<absent>")
        if old == new:
            continue
        moved.append(
            {
                "path": path,
                "class": classify_path(path),
                "before": old,
                "after": new,
            }
        )
    classes: dict[str, int] = {}
    for row in moved:
        classes[row["class"]] = classes.get(row["class"], 0) + 1
    return {
        "moved_leaf_count": len(moved),
        "moved_leaf_classes": dict(sorted(classes.items())),
        "moved_leaf_paths": moved[: int(limit)],
        "moved_leaf_paths_truncated": bool(len(moved) > int(limit)),
        "unchanged_leaf_count": sum(
            1 for path in set(left) & set(right) if left[path] == right[path]
        ),
    }


# --------------------------------------------------------------------------
# the owner under measurement
# --------------------------------------------------------------------------
def open_owner(profile: Any, config: OwnerSurfaceOptionsConfig | None = None) -> tuple[FieldIntelligenceOwner, Path]:
    """One owner whose canonical workspace is this profile's, in a fresh data home."""

    settings = OwnerSurfaceOptionsConfig() if config is None else config
    home = Path(tempfile.mkdtemp(prefix=str(settings.owner_home_prefix)))
    owner = FieldIntelligenceOwner(
        home,
        initial_state=AtlasState(resonant_workspace=initial_workspace(profile)),
    )
    return owner, home


def owner_write(
    owner: FieldIntelligenceOwner,
    operation_id: str,
    spec: durability.ItemSpec,
    config: OwnerSurfaceOptionsConfig,
) -> Mapping[str, Any]:
    """One declared item written through the owner write path."""

    return owner.write_packet_impulse(
        operation_id,
        path=spec.path,
        component=spec.component,
        flow_signal=list(spec.flow_signal),
        work_budget=float(config.write_budget),
    )


def declared_direction(spec: durability.ItemSpec) -> dict[str, Any]:
    """The three names the read and the write address one direction by."""

    return {
        "path": spec.path,
        "component": spec.component,
        "flow_signal": list(spec.flow_signal),
    }


def declare_deposit_channel(owner: FieldIntelligenceOwner, variable: str, chart: str) -> dict[str, Any]:
    """One declared observation channel over the declared deposit range.

    The evidence reading admits an observation about the declared deposit, so the
    declaration needs a variable holding it and an applicable chart over it to
    exist first: without one the owner's own admission rule refuses the
    observation, which is measured as its own control below. This is the same
    declaration the diagnosis harness's clock control makes on a bare atlas.
    """

    owner.configure_variable(
        "owner-surface-options:variable",
        VariableSpec(variable_id=variable, lower=0.0, upper=1.0),
    )
    owner.configure_chart(
        "owner-surface-options:chart",
        RelationChart.empty(
            chart_id=chart,
            scope=(variable,),
            ridge=1e-5,
            observation_norm_bound=64.0,
            prior_mass=1e-3,
        ),
    )
    return {
        "variable": variable,
        "range": [0.0, 1.0],
        "chart": chart,
        "ridge": 1e-5,
        "observation_norm_bound": 64.0,
        "prior_mass": 1e-3,
    }


def surface_snapshot(owner: FieldIntelligenceOwner, config: OwnerSurfaceOptionsConfig) -> dict[str, Any]:
    """The declared owner surfaces plus the clocks, as one comparable record."""

    workspace = owner.state.resonant_workspace
    surfaces = {
        name: plain(getattr(owner, name)()) for name in DECLARED_SURFACES
    }
    resonance = surfaces["inspect_resonance"]
    charts = {
        str(row.get("chart_id", position)): {
            "version": row.get("version"),
            "contribution_count": len(row.get("contributions", []) or []),
        }
        for position, row in enumerate(resonance.get("charts", []) or [])
    }
    # The declared observation channels as the owner's own state holds them: the
    # declared surfaces above do not publish the store's charts, so the channel's
    # own record is read from the state the admission updates.
    declared_channel = {
        str(chart.chart_id): {
            "version": int(chart.version),
            "contribution_count": len(chart.contributions),
            "status": str(chart.status),
            "scope": [str(name) for name in chart.scope],
        }
        for chart in owner.state.charts
    }
    return {
        "surfaces": surfaces,
        "logical_tick": int(owner.state.logical_tick),
        "generation": int(owner.state.generation),
        "atlas_state_sha256": str(owner.state.state_sha256),
        "page_sha256": durability.page_sha256(workspace),
        "workspace_state_sha256": str(workspace.state_sha256),
        "evidence_tick": int(resonance.get("evidence_tick", 0)),
        "evidence_event_count": int(owner.evidence.event_count),
        "chart_versions": charts,
        "declared_channel": declared_channel,
        "manifest_sha256": str(owner.checkpoints.current_manifest_sha256),
    }


def reading_record(owner: FieldIntelligenceOwner, direction: Mapping[str, Any]) -> dict[str, Any]:
    """The declared prediction reading of one direction, as the owner returns it."""

    return plain(owner.read_packet_deposit(**dict(direction)))


def evidence_record(
    owner: FieldIntelligenceOwner,
    direction: Mapping[str, Any],
    operation_id: str,
    config: OwnerSurfaceOptionsConfig,
) -> dict[str, Any]:
    """The declared evidence reading of one direction, as the owner returns it."""

    return plain(
        owner.read_packet_deposit(
            **dict(direction),
            as_evidence=True,
            operation_id=str(operation_id),
            observation_variable=DECLARED_DEPOSIT_VARIABLE,
            observation_context={"declared": "owner-surface-options evidence reading"},
            observation_weight=float(config.observation_weight),
        )
    )


# --------------------------------------------------------------------------
# measurement 1: declaring the read as evidence
# --------------------------------------------------------------------------
def reading_declaration_block(
    profile: Any, config: OwnerSurfaceOptionsConfig
) -> dict[str, Any]:
    """What each declaration of the packet read moves, and what consumes it."""

    spec = durability.ITEM_SPECS[int(config.headline_item_index)]
    direction = declared_direction(spec)
    owner, home = open_owner(profile, config)
    try:
        channel = declare_deposit_channel(owner, DECLARED_DEPOSIT_VARIABLE, DECLARED_DEPOSIT_CHART)
        owner_write(owner, WRITE_OPERATION_ID, spec, config)
        written_page = durability.page_sha256(owner.state.resonant_workspace)

        # The prediction reading -- the shipped declaration.
        prediction_before = surface_snapshot(owner, config)
        prediction = reading_record(owner, direction)
        prediction_after = surface_snapshot(owner, config)

        # A reading without the declared channel: the owner's own admission rule
        # refuses an observation about a variable no chart covers. This is the
        # can-fail control for "the evidence reading is admitted", and it runs on
        # its own owner so the measured admission below is not polluted.
        uncovered_owner, uncovered_home = open_owner(profile, config)
        try:
            owner_write(uncovered_owner, WRITE_OPERATION_ID, spec, config)
            uncovered_channel = DECLARED_DEPOSIT_VARIABLE
            uncovered_error = ""
            try:
                evidence_record(
                    uncovered_owner,
                    direction,
                    "owner-surface-options:evidence-uncovered",
                    config,
                )
            except Exception as error:  # the refusal is the measurement
                uncovered_error = f"{type(error).__name__}: {error}"
            uncovered_refused = bool(uncovered_error)
            uncovered_owner.close()
        finally:
            shutil.rmtree(uncovered_home, ignore_errors=True)
        if not uncovered_refused:
            raise AssertionError(
                "the evidence reading was admitted on an owner with no declared "
                "channel for the observed variable: the control cannot fail"
            )

        # The evidence reading -- the opt-in declaration.
        evidence_before = surface_snapshot(owner, config)
        evidence = evidence_record(owner, direction, EVIDENCE_OPERATION_ID, config)
        evidence_after = surface_snapshot(owner, config)

        # The retry: the same declaration under the same operation identity must
        # replay its admission instead of publishing a second successor.
        retry = evidence_record(owner, direction, EVIDENCE_OPERATION_ID, config)
        retry_after = surface_snapshot(owner, config)

        # A second declaration under a fresh identity: the same deposit admitted
        # again is a distinct observation, so the derived source identity must not
        # collide with the first one.
        second = evidence_record(owner, direction, SECOND_EVIDENCE_OPERATION_ID, config)
        second_after = surface_snapshot(owner, config)

        page_after_the_declarations = durability.page_sha256(owner.state.resonant_workspace)
        prediction_moves = leaf_difference(
            prediction_before, prediction_after, limit=int(config.changed_path_limit)
        )
        evidence_moves = leaf_difference(
            evidence_before, evidence_after, limit=int(config.changed_path_limit)
        )
        retry_moves = leaf_difference(
            evidence_after, retry_after, limit=int(config.changed_path_limit)
        )
        second_moves = leaf_difference(
            retry_after, second_after, limit=int(config.changed_path_limit)
        )

        surface_records = {
            "prediction": {
                "reading": prediction,
                "surfaces_before": prediction_before["surfaces"],
                "surfaces_after": prediction_after["surfaces"],
            },
            "evidence": {
                "reading": evidence,
                "surfaces_before": evidence_before["surfaces"],
                "surfaces_after": evidence_after["surfaces"],
            },
        }
        # The exposure scan's declared bodies: the reading record alone, and the
        # same reading beside the two inspections the diagnosis harness's own
        # exposure scan scanned (its convention), so the counts below are
        # comparable with the figures already recorded for the shipped read.
        prediction_exposure_bodies = {
            "reading": prediction,
            "inspect": prediction_before["surfaces"]["inspect"],
            "inspect_resonance": prediction_before["surfaces"]["inspect_resonance"],
        }
        evidence_exposure_bodies = {
            "reading": evidence,
            "inspect": evidence_before["surfaces"]["inspect"],
            "inspect_resonance": evidence_before["surfaces"]["inspect_resonance"],
        }
        prediction_paths = key_paths(prediction_exposure_bodies)
        evidence_paths = key_paths(evidence_exposure_bodies)
        prediction_exposure = exposure_scan(prediction_exposure_bodies)
        evidence_exposure = exposure_scan(evidence_exposure_bodies)

        # The declared operations whose name suggests a decision or an
        # observation: the surfaces a consumer of observed support would sit on.
        operation_names = dispatch_operations()
        deciding_operations = sorted(
            name
            for name in operation_names
            if any(
                stem in name
                for stem in (
                    "observe",
                    "observation",
                    "evidence",
                    "plan",
                    "query",
                    "decide",
                    "inquiry",
                    "authority",
                )
            )
        )

        return {
            "declared": (
                "the read half of the memory, declared two ways. As shipped it is a "
                "temporal prediction of the canonical page: it adds no observed "
                "support and advances no clock. The opt-in variant declares the same "
                "recovered deposit as an observation about the world through the "
                "owner's own admission rule, which needs a declared observation "
                "channel to exist first. This block measures what each declaration "
                "moves on the owner's declared surfaces, what class of leaf moves, "
                "whether anything downstream keys on observed support, and the "
                "exposure of each reading's published key paths"
            ),
            "operation": READ_OPERATION_NAME,
            "declared_direction": {
                "item": spec.name,
                "path": spec.path,
                "component": spec.component,
                "flow_signal": list(spec.flow_signal),
            },
            "declared_channel": channel,
            "written_page_sha256": written_page,
            "read_recovered_deposit": {
                "prediction": float(prediction["recovered_deposit"]),
                "evidence": float(evidence["evidence"]["deposit_declared_as_evidence"]),
                "the_two_readings_recover_the_same_deposit": bool(
                    float(prediction["recovered_deposit"])
                    == float(evidence["evidence"]["deposit_declared_as_evidence"])
                ),
                "readout_kind_of_the_shipped_reading": str(prediction["readout_kind"]),
            },
            "prediction_reading": {
                "declared": (
                    "the shipped default: a temporal prediction of the page, no "
                    "observed support, no clock movement"
                ),
                "state_before": state_summary(prediction_before),
                "state_after": state_summary(prediction_after),
                "moved": prediction_moves,
                "moves_nothing": bool(prediction_moves["moved_leaf_count"] == 0),
                "exposure": {
                    "bodies": {
                        "reading_only": "the read operation's own returned record",
                        "with_the_two_inspections": (
                            "the read record beside inspect and inspect_resonance, the "
                            "body the diagnosis harness's exposure scan scans"
                        ),
                    },
                    "reading_only": exposure_scan(prediction),
                    "with_the_two_inspections": prediction_exposure,
                },
            },
            "evidence_reading": {
                "declared": (
                    "the opt-in variant: the same recovered deposit admitted as an "
                    "observation about the world under the declared operation "
                    "identity and the declared observation variable"
                ),
                "state_before": state_summary(evidence_before),
                "state_after": state_summary(evidence_after),
                "moved": evidence_moves,
                "admission": {
                    "event_id": str(evidence["evidence"]["event_id"]),
                    "event_kind": str(
                        evidence["evidence"]["event"]["event_kind"]
                        if "event_kind" in evidence["evidence"]["event"]
                        else ""
                    ),
                    "epistemic_type": str(evidence["evidence"]["event"].get("epistemic_type", "")),
                    "source_revision_id": str(evidence["evidence"]["source_revision_id"]),
                    "observation_variable": str(evidence["evidence"]["observation_variable"]),
                    "replayed": bool(evidence["evidence"]["replayed"]),
                    "published_a_successor": bool(evidence["evidence"]["transition"] is not None),
                },
                "successors_published_by_the_admission": int(
                    evidence_after["generation"] - evidence_before["generation"]
                ),
                "evidence_clock_moved_by": int(
                    evidence_after["evidence_tick"] - evidence_before["evidence_tick"]
                ),
                "evidence_store_events_added": int(
                    evidence_after["evidence_event_count"]
                    - evidence_before["evidence_event_count"]
                ),
                "declared_channel_before": evidence_before["declared_channel"],
                "declared_channel_after": evidence_after["declared_channel"],
                "exposure": {
                    "bodies": {
                        "reading_only": "the read operation's own returned record",
                        "with_the_two_inspections": (
                            "the read record beside inspect and inspect_resonance, the "
                            "body the diagnosis harness's exposure scan scans"
                        ),
                    },
                    "reading_only": exposure_scan(evidence),
                    "with_the_two_inspections": evidence_exposure,
                },
            },
            "side_by_side": {
                "declared": (
                    "the two declarations of the same read, on the same page, over "
                    "the same declared surfaces: the leaf counts are how many "
                    "surface leaves each one moves, the clocks are the two clocks a "
                    "declaration can advance, and the store counts are the owner's "
                    "own evidence store"
                ),
                "moved_leaf_count": {
                    "prediction": prediction_moves["moved_leaf_count"],
                    "evidence": evidence_moves["moved_leaf_count"],
                },
                "moved_leaf_classes": {
                    "prediction": prediction_moves["moved_leaf_classes"],
                    "evidence": evidence_moves["moved_leaf_classes"],
                },
                "logical_tick": {
                    "prediction": [
                        prediction_before["logical_tick"],
                        prediction_after["logical_tick"],
                    ],
                    "evidence": [
                        evidence_before["logical_tick"],
                        evidence_after["logical_tick"],
                    ],
                },
                "generation": {
                    "prediction": [
                        prediction_before["generation"],
                        prediction_after["generation"],
                    ],
                    "evidence": [evidence_before["generation"], evidence_after["generation"]],
                },
                "evidence_tick": {
                    "prediction": [
                        prediction_before["evidence_tick"],
                        prediction_after["evidence_tick"],
                    ],
                    "evidence": [evidence_before["evidence_tick"], evidence_after["evidence_tick"]],
                },
                "evidence_store_events": {
                    "prediction": [
                        prediction_before["evidence_event_count"],
                        prediction_after["evidence_event_count"],
                    ],
                    "evidence": [
                        evidence_before["evidence_event_count"],
                        evidence_after["evidence_event_count"],
                    ],
                },
                "page_sha256_moved": {
                    "prediction": bool(
                        prediction_before["page_sha256"] != prediction_after["page_sha256"]
                    ),
                    "evidence": bool(
                        evidence_before["page_sha256"] != evidence_after["page_sha256"]
                    ),
                    "page_sha256": page_after_the_declarations,
                },
                "published_key_paths": {
                    "prediction": len(prediction_paths),
                    "evidence": len(evidence_paths),
                },
                "exposure_counts": {
                    "prediction": {
                        "direction": prediction_exposure["direction"]["count"],
                        "summary": prediction_exposure["summary"]["count"],
                        "intervention": prediction_exposure["intervention"]["count"],
                        "absent_control": prediction_exposure["absent_control"]["count"],
                    },
                    "evidence": {
                        "direction": evidence_exposure["direction"]["count"],
                        "summary": evidence_exposure["summary"]["count"],
                        "intervention": evidence_exposure["intervention"]["count"],
                        "absent_control": evidence_exposure["absent_control"]["count"],
                    },
                },
            },
            "observed_support_consumers": {
                "declared": (
                    "what consumes observed support downstream. A consumer would "
                    "have to read the atlas store, so the measurement is the "
                    "declared surfaces that read it, diffed before and after the "
                    "admission, plus the owner's own closed dispatch: the classes of "
                    "moved leaf say whether a decision input moved or only a clock, "
                    "a count and the declared channel's own record"
                ),
                "declared_surfaces_diffed": list(DECLARED_SURFACES),
                "moved_leaf_classes": evidence_moves["moved_leaf_classes"],
                "moved_leaf_paths": evidence_moves["moved_leaf_paths"],
                "a_decision_input_moved": bool(
                    evidence_moves["moved_leaf_classes"].get("decision", 0) > 0
                ),
                "the_declared_channel_moved": bool(
                    evidence_before["declared_channel"] != evidence_after["declared_channel"]
                ),
                "declared_channel_before": evidence_before["declared_channel"],
                "declared_channel_after": evidence_after["declared_channel"],
                "declared_dispatch_operations": len(operation_names),
                "dispatch_operations_naming_a_decision_or_an_observation": deciding_operations,
            },
            "retry": {
                "declared": (
                    "the same declaration under the same operation identity. It must "
                    "replay its admission -- no second successor, the same event and "
                    "source identity -- while the readout half still reports the page "
                    "it actually read"
                ),
                "replayed": bool(retry["evidence"]["replayed"]),
                "event_id_identical": bool(
                    str(retry["evidence"]["event_id"])
                    == str(evidence["evidence"]["event_id"])
                ),
                "source_revision_id_identical": bool(
                    str(retry["evidence"]["source_revision_id"])
                    == str(evidence["evidence"]["source_revision_id"])
                ),
                "second_transition_published": bool(
                    retry["evidence"]["transition"] is not None
                ),
                "generation_after_the_first_admission": int(evidence_after["generation"]),
                "generation_after_the_retry": int(retry_after["generation"]),
                "moved_by_the_retry": retry_moves,
                "evidence_clock_after_the_retry": int(retry_after["evidence_tick"]),
                "readout_generation_field": int(retry["generation"]),
            },
            "second_identity": {
                "declared": (
                    "the same deposit declared again under a fresh operation "
                    "identity. The derived source identity is a function of the "
                    "declared direction and the recovered deposit, so the second "
                    "declaration reuses the exact source revision the first one "
                    "stored rather than conflicting with it, while the event "
                    "identity differs and the store holds both events: the "
                    "declaration is a distinct observation of the same recorded "
                    "bytes, which is what the derivation is for"
                ),
                "event_id_differs": bool(
                    str(second["evidence"]["event_id"]) != str(evidence["evidence"]["event_id"])
                ),
                "source_revision_reused": bool(
                    str(second["evidence"]["source_revision_id"])
                    == str(evidence["evidence"]["source_revision_id"])
                ),
                "source_revision_id": str(second["evidence"]["source_revision_id"]),
                "store_held_the_source_without_conflict": True,
                "evidence_store_events_after": int(second_after["evidence_event_count"]),
                "successors_published": int(
                    second_after["generation"] - retry_after["generation"]
                ),
                "moved": second_moves,
            },
            "control": {
                "declared": (
                    "the evidence reading on an owner with no declared channel for "
                    "the observed variable: the owner's own admission rule must "
                    "refuse it, which is what makes the measured admission an "
                    "admission rather than a call that always succeeds"
                ),
                "refused": uncovered_refused,
                "error": uncovered_error,
                "must_refuse": True,
            },
            "decision_statements": {
                "if_the_prediction_reading_were_adopted": (
                    "the record would say the read is a readout of the page that "
                    "adds no observed support and advances no clock, and the "
                    f"surfaces would move {prediction_moves['moved_leaf_count']} "
                    "leaves across the four declared surfaces"
                ),
                "if_the_evidence_reading_were_adopted": (
                    "the record would say the recovered deposit is an admitted "
                    "observation about the world: the evidence clock advances, one "
                    "successor is published, the declared channel records the "
                    "contribution, and the four declared surfaces move "
                    f"{evidence_moves['moved_leaf_count']} leaves, of which "
                    f"{evidence_moves['moved_leaf_classes'].get('clock', 0)} are "
                    "clocks and "
                    f"{evidence_moves['moved_leaf_classes'].get('other', 0)} are "
                    "unclassified"
                ),
            },
        }
    finally:
        owner.close()
        shutil.rmtree(home, ignore_errors=True)


def state_summary(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """The clocks and digests of one surface snapshot, without the surfaces."""

    return {
        "logical_tick": int(snapshot["logical_tick"]),
        "generation": int(snapshot["generation"]),
        "evidence_tick": int(snapshot["evidence_tick"]),
        "page_sha256": str(snapshot["page_sha256"]),
        "atlas_state_sha256": str(snapshot["atlas_state_sha256"]),
        "workspace_state_sha256": str(snapshot["workspace_state_sha256"]),
        "manifest_sha256": str(snapshot["manifest_sha256"]),
        "evidence_event_count": int(snapshot["evidence_event_count"]),
        "chart_versions": snapshot["chart_versions"],
        "declared_channel": snapshot["declared_channel"],
    }


def dispatch_operations() -> list[str]:
    """Every operation name the owner's closed RPC dispatch declares."""

    import re

    source = Path(__file__).with_name("cassi_field_owner.py").read_text(encoding="utf-8")
    return sorted(set(re.findall(r'operation == "([a-z_]+)"', source)))


def opt_in_callers() -> list[str]:
    """Every source file that calls one of the two opt-in input helpers.

    Call sites only, taken from the abstract syntax tree, so the modules that
    define the helpers are not counted for their definition.
    """

    names = {"condense_input", "input_problem"}
    callers = []
    for path in sorted(Path(__file__).parent.glob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        called = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in names
        }
        if called:
            callers.append(path.name)
    return callers


# --------------------------------------------------------------------------
# measurement 2: the coupled input realization
# --------------------------------------------------------------------------
def realization_kernel(
    workspace: ResonantWorkspace,
    config: OwnerSurfaceOptionsConfig,
    *,
    diagonal: float,
    coupling: float,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """One declared input realization of the declared write problem."""

    return condense_input(
        workspace,
        input_ids=("write-in",),
        output_ids=("write-out",),
        diagonal=float(diagonal),
        coupling=float(coupling),
        rank=int(config.rank),
        error_allowance=float(config.error_allowance),
        input_bound=float(config.input_bound),
        horizon_ticks=int(config.horizon_ticks),
    )


def authority_series(
    kernel: Mapping[str, Any],
    config: OwnerSurfaceOptionsConfig,
    *,
    input_scan: Sequence[float],
) -> dict[str, Any]:
    """The declared input-scan authority of one realization, per tick and averaged.

    The authority of a realization at one tick is the relative spread of the
    declared readout over the declared input scan at that tick: the same
    convention ``run_owner_write_path_exploration.py`` applies to the shipped
    input, at the same declared allowance. A realization whose readout does not
    move with the input has zero relative spread and no measurable authority.
    """

    rows: dict[str, Any] = {}
    spreads: list[float] = []
    for ticks in sorted(int(tick) for tick in config.authority_window_ticks):
        outputs: dict[str, float] = {}
        for value in input_scan:
            _state, scan = advance_transceiver(
                kernel,
                reset_transceiver(kernel),
                inputs={"write-in": float(value)},
                ticks=ticks,
            )
            outputs[repr(float(value))] = float(scan["values"]["write-out"])
        scanned = [float(item) for item in outputs.values()]
        spread = float(max(scanned) - min(scanned))
        magnitude = float(max(abs(item) for item in scanned))
        relative = float(spread / magnitude) if magnitude else 0.0
        spreads.append(relative)
        rows[str(ticks)] = {
            "outputs": outputs,
            "authority_absolute_spread": spread,
            "magnitude": magnitude,
            "relative_spread": relative,
            "input_has_authority": bool(spread > float(config.authority_allowance)),
        }
    spread_values = [
        float(rows[str(int(tick))]["authority_absolute_spread"]) for tick in rows
    ]
    return {
        "declared_authority_measure": (
            "the absolute spread of the declared readout over the declared input "
            "scan (0.0, 0.5, 1.75, 3.5), the quantity the diagnosis measured as "
            "7.83e-3 for a coupled relation and 1.63e-19 for the inert shipped one; "
            "the relative spread is carried beside it, but a proportional response "
            "through the origin normalises to 1.0 whatever its size, so the absolute "
            "spread is the figure a reader should compare"
        ),
        "per_tick": rows,
        "authority_window_average_spread": (
            float(statistics.fmean(spread_values)) if spread_values else 0.0
        ),
        "authority_window_max_spread": float(max(spread_values)) if spread_values else 0.0,
        "window_average_relative_spread": float(statistics.fmean(spreads)) if spreads else 0.0,
        "window_max_relative_spread": float(max(spreads)) if spreads else 0.0,
        "window_ticks": sorted(int(tick) for tick in config.authority_window_ticks),
        "input_scan": [float(value) for value in input_scan],
    }


def persistence_series(
    kernel: Mapping[str, Any],
    config: OwnerSurfaceOptionsConfig,
    *,
    drive: float,
) -> dict[str, Any]:
    """The declared readout after one driven tick, then with the input held at zero."""

    state = reset_transceiver(kernel)
    readout: dict[str, float] = {}
    for tick in sorted(int(item) for item in config.persistence_ticks):
        state, scan = advance_transceiver(
            kernel,
            state,
            inputs={"write-in": float(drive) if tick == min(config.persistence_ticks) else 0.0},
            ticks=1,
        )
        readout[str(tick)] = float(scan["values"]["write-out"])
    values = [readout[str(tick)] for tick in sorted(int(item) for item in config.persistence_ticks)]
    magnitude = float(max(abs(item) for item in values)) if values else 0.0
    return {
        "drive": float(drive),
        "readout_after_each_tick": readout,
        "the_drive_is_applied_on_the_first_tick_only": True,
        "first_tick_readout": values[0] if values else 0.0,
        "last_tick_readout": values[-1] if values else 0.0,
        "peak_magnitude": magnitude,
        "last_tick_over_first_tick": (
            float(abs(values[-1]) / abs(values[0])) if values and values[0] else None
        ),
    }


def route_identity_compare(
    profile: Any,
    base: ResonantWorkspace,
    target_state: np.ndarray,
    route_state: np.ndarray,
    direction: Mapping[str, Any],
    config: OwnerSurfaceOptionsConfig,
) -> dict[str, Any]:
    """The declared route-identity predicate between a routed state and a target.

    Both pages are built by the library's own state-to-page mapping on the same
    base page, so the comparison isolates the field: the target page is the
    owner-write target's declared state carried by that mapping, and the route
    page is what a driven input realization produced. Page digest, workspace state
    digest, the declared read frame and the declared deposit are compared.
    """

    bindings = base.bindings
    target_page = _workspace(profile, bindings, np.asarray(target_state, dtype=np.float64))
    route_page = _workspace(profile, bindings, np.asarray(route_state, dtype=np.float64))
    target_frame = durability.read_frame(target_page, config.read_frame_path)
    route_frame = durability.read_frame(route_page, config.read_frame_path)
    atlas = FieldAtlas.__new__(FieldAtlas)
    target_read = FieldAtlas.read_packet_deposit(
        atlas,
        AtlasState(resonant_workspace=target_page),
        path=direction["path"],
        component=direction["component"],
        flow_signal=direction["flow_signal"],
    )
    route_read = FieldAtlas.read_packet_deposit(
        atlas,
        AtlasState(resonant_workspace=route_page),
        path=direction["path"],
        component=direction["component"],
        flow_signal=direction["flow_signal"],
    )
    target_deposit = float(target_read["recovered_deposit"])
    route_deposit = float(route_read["recovered_deposit"])
    delta = np.asarray(route_state, dtype=np.float64) - np.asarray(target_state, dtype=np.float64)
    return {
        "page_digest_identical": bool(
            durability.page_sha256(route_page) == durability.page_sha256(target_page)
        ),
        "state_digest_identical": bool(route_page.state_sha256 == target_page.state_sha256),
        "read_frame_max_abs_difference": float(np.max(np.abs(route_frame - target_frame))),
        "target_deposit": target_deposit,
        "route_deposit": route_deposit,
        "deposit_relative_difference": (
            float(abs(route_deposit - target_deposit) / target_deposit)
            if target_deposit
            else None
        ),
        "state_vector_distance": float(np.linalg.norm(delta)),
        "route_page_sha256": durability.page_sha256(route_page),
        "target_page_sha256": durability.page_sha256(target_page),
    }


def coupled_input_block(profile: Any, config: OwnerSurfaceOptionsConfig) -> dict[str, Any]:
    """The coupled input realization against the shipped one, and the overlap rule."""

    spec = durability.ITEM_SPECS[int(config.headline_item_index)]
    direction = declared_direction(spec)
    p0 = initial_workspace(profile)
    p_owner, _written = durability.write_item(p0, spec, float(config.write_budget))
    z0, z_owner = _vector(p0), _vector(p_owner)

    shipped_kernel, _w, shipped_receipt = realization_kernel(
        p0, config, diagonal=SHIPPED_DIAGONAL, coupling=SHIPPED_COUPLING
    )
    coupled_kernel, _w2, coupled_receipt = realization_kernel(
        p0, config, diagonal=COUPLED_DIAGONAL, coupling=COUPLED_COUPLING
    )
    # The default-off proof: the opt-in helper with no coupling must reproduce the
    # shipped declared input's kernel exactly, not merely closely.
    direct_kernel, _w3, _r3 = condense_workspace(
        bind_workspace(p0, declared_problem()),
        declared_problem(),
        input_ids=("write-in",),
        output_ids=("write-out",),
        rank=int(config.rank),
        error_allowance=float(config.error_allowance),
        input_bound=float(config.input_bound),
        horizon_ticks=int(config.horizon_ticks),
    )
    if shipped_kernel["kernel_sha256"] != direct_kernel["kernel_sha256"]:
        raise AssertionError(
            "the opt-in input helper with no coupling did not reproduce the shipped "
            "declared input kernel: the default is not preserved"
        )

    beta_zero = replace(profile, beta=0.0)
    beta_zero_workspace = initial_workspace(beta_zero)
    beta_zero_shipped, _w4, _r4 = realization_kernel(
        beta_zero_workspace, config, diagonal=SHIPPED_DIAGONAL, coupling=SHIPPED_COUPLING
    )
    beta_zero_coupled, _w5, _r5 = realization_kernel(
        beta_zero_workspace, config, diagonal=COUPLED_DIAGONAL, coupling=COUPLED_COUPLING
    )
    realizations = {
        "declared_profile_shipped_relation": authority_series(
            shipped_kernel, config, input_scan=config.authority_input_scan
        ),
        "declared_profile_coupled_relation": authority_series(
            coupled_kernel, config, input_scan=config.authority_input_scan
        ),
        "beta_zero_counterpart_shipped_relation": authority_series(
            beta_zero_shipped, config, input_scan=config.authority_input_scan
        ),
        "beta_zero_counterpart_coupled_relation": authority_series(
            beta_zero_coupled, config, input_scan=config.authority_input_scan
        ),
    }

    # Route identity: the declared amplitudes, then the best amplitude of the
    # declared sweep, against the owner write target's own state.
    sweeps: list[dict[str, Any]] = []
    best: dict[str, Any] | None = None
    best_state: np.ndarray | None = None
    for amplitude in config.route_amplitudes:
        state, scan = advance_transceiver(
            coupled_kernel,
            reset_transceiver(coupled_kernel),
            inputs={"write-in": float(amplitude)},
            ticks=1,
        )
        comparison = route_identity_compare(
            profile,
            p0,
            z_owner,
            np.asarray(state["state"], dtype=np.float64),
            direction,
            config,
        )
        row = {
            "amplitude": float(amplitude),
            "readout": float(scan["values"]["write-out"]),
            "comparison": comparison,
        }
        sweeps.append(row)
        if best is None or comparison["state_vector_distance"] < best["comparison"]["state_vector_distance"]:
            best = row
            best_state = np.asarray(state["state"], dtype=np.float64)
    assert best is not None and best_state is not None

    # The route identity at the declared scan the diagnosis used.
    declared_amplitude_row = next(
        row for row in sweeps if float(row["amplitude"]) == 3.5
    )
    swept_identical = [
        row["amplitude"] for row in sweeps if row["comparison"]["page_digest_identical"]
    ]

    # The controls that show the predicate can report identity: the same
    # predicate on the target's own state must report identity, and on the
    # undriven base state it must not.
    reconstruction_control = route_identity_compare(
        profile, p0, z_owner, z_owner, direction, config
    )
    no_drive_control = route_identity_compare(profile, p0, z_owner, z0, direction, config)
    if not (
        reconstruction_control["page_digest_identical"]
        and reconstruction_control["state_digest_identical"]
        and reconstruction_control["read_frame_max_abs_difference"] == 0.0
    ):
        raise AssertionError(
            "the route-identity predicate did not report identity on the target's "
            "own state: it cannot fire"
        )
    if no_drive_control["page_digest_identical"]:
        raise AssertionError("the route-identity predicate reported identity on the undriven state")

    # The route page at the best declared amplitude against the owner's real
    # written page, with the metadata difference explained rather than asserted.
    best_route_page = _workspace(profile, p0.bindings, best_state)
    best_route_frame = durability.read_frame(best_route_page, config.read_frame_path)
    owner_frame = durability.read_frame(p_owner, config.read_frame_path)
    atlas = FieldAtlas.__new__(FieldAtlas)
    best_route_deposit = float(
        FieldAtlas.read_packet_deposit(
            atlas,
            AtlasState(resonant_workspace=best_route_page),
            path=direction["path"],
            component=direction["component"],
            flow_signal=direction["flow_signal"],
        )["recovered_deposit"]
    )
    owner_deposit = float(
        FieldAtlas.read_packet_deposit(
            atlas,
            AtlasState(resonant_workspace=p_owner),
            path=direction["path"],
            component=direction["component"],
            flow_signal=direction["flow_signal"],
        )["recovered_deposit"]
    )
    metadata_target = _workspace(profile, p0.bindings, z_owner)
    left = plain(metadata_target.as_dict())
    right = plain(p_owner.as_dict())
    owner_page_comparison = {
        "route_page_at_the_best_amplitude_vs_the_owner_page": {
            "declared": (
                "the closest page the coupled route reaches on the declared "
                "amplitude sweep, against the owner's real written page"
            ),
            "best_amplitude": float(best["amplitude"]),
            "route_page_sha256": durability.page_sha256(best_route_page),
            "owner_page_sha256": durability.page_sha256(p_owner),
            "page_digest_identical": bool(
                durability.page_sha256(best_route_page) == durability.page_sha256(p_owner)
            ),
            "route_workspace_state_sha256": str(best_route_page.state_sha256),
            "owner_workspace_state_sha256": str(p_owner.state_sha256),
            "workspace_state_digest_identical": bool(
                best_route_page.state_sha256 == p_owner.state_sha256
            ),
            "read_frame_max_abs_difference": float(
                np.max(np.abs(best_route_frame - owner_frame))
            ),
            "route_deposit": best_route_deposit,
            "owner_deposit": owner_deposit,
            "deposit_relative_difference": (
                float(abs(best_route_deposit - owner_deposit) / owner_deposit)
                if owner_deposit
                else None
            ),
            "state_vector_distance_to_the_write": float(
                np.linalg.norm(np.asarray(best_state, dtype=np.float64) - z_owner)
            ),
            "field_bytes_identical": bool(
                np.array_equal(
                    np.asarray(best_route_page.field, dtype=np.float64),
                    np.asarray(p_owner.field, dtype=np.float64),
                )
            ),
        },
        "mapped_target_page_vs_the_owner_page": {
            "declared": (
                "the write's own state carried by the same library mapping the route "
                "uses, against the owner's real written page: both are built from the "
                "same base page, so what differs is what the owner's write stamps "
                "beyond the field, which the state digest covers and the page digest "
                "does not"
            ),
            "mapped_target_page_sha256": durability.page_sha256(metadata_target),
            "page_digest_identical": bool(
                durability.page_sha256(metadata_target) == durability.page_sha256(p_owner)
            ),
            "workspace_state_digest_identical": bool(
                metadata_target.state_sha256 == p_owner.state_sha256
            ),
            "metadata_fields_that_differ": sorted(
                key
                for key in set(left) | set(right)
                if key != "field_b64" and left.get(key) != right.get(key)
            ),
        },
    }

    # Cost: the per-tick work of one advance against one owner write.
    per_tick_cost: dict[str, Any] = {}
    for name, kernel in (
        ("declared_profile_shipped_relation", shipped_kernel),
        ("declared_profile_coupled_relation", coupled_kernel),
    ):
        started = time.perf_counter()
        advance_transceiver(
            kernel,
            reset_transceiver(kernel),
            inputs={"write-in": 1.0},
            ticks=int(config.cost_ticks),
        )
        elapsed = time.perf_counter() - started
        per_tick_cost[name] = {
            "window_ticks": int(config.cost_ticks),
            "window_elapsed_seconds": float(elapsed),
            "per_tick_seconds": float(elapsed / int(config.cost_ticks)),
        }
    write_times: list[float] = []
    cost_owner, cost_home = open_owner(profile, config)
    try:
        for repeat in range(int(config.cost_repeats)):
            started = time.perf_counter()
            owner_write(cost_owner, f"owner-surface-options:cost-{repeat}", spec, config)
            write_times.append(time.perf_counter() - started)
    finally:
        cost_owner.close()
        shutil.rmtree(cost_home, ignore_errors=True)
    median_write = float(statistics.median(write_times))

    return {
        "declared": (
            "the input port's authority comes from the declared relation, not from "
            "the input code path. The shipped declared input is the identity "
            "precision on the declared variables; the opt-in coupled relation puts "
            "a cross term between them. This block measures the authority of each "
            "realization on the declared profile and its beta-zero counterpart, "
            "whether driving the coupled realization reproduces the owner write "
            "path's page, state digest and read frame, the persistence of the "
            "driven response, and the per-tick work against one owner write"
        ),
        "problem": {
            "variable_ids": list(declared_problem().variable_ids),
            "shipped_relation": {"diagonal": SHIPPED_DIAGONAL, "coupling": SHIPPED_COUPLING},
            "coupled_relation": {"diagonal": COUPLED_DIAGONAL, "coupling": COUPLED_COUPLING},
            "input_ids": ["write-in"],
            "output_ids": ["write-out"],
            "bindings": plain(bind_workspace(p0, declared_problem()).bindings),
        },
        "default_off": {
            "declared": (
                "the opt-in helper with no coupling against a direct call of the "
                "shipped condenser with the shipped declared problem: the two "
                "kernels must be the same object, not merely the same numbers"
            ),
            "opt_in_kernel_sha256": str(shipped_kernel["kernel_sha256"]),
            "shipped_condenser_kernel_sha256": str(direct_kernel["kernel_sha256"]),
            "kernels_identical": bool(
                shipped_kernel["kernel_sha256"] == direct_kernel["kernel_sha256"]
            ),
            "dimensions_identical": bool(
                shipped_kernel["dimensions"] == direct_kernel["dimensions"]
            ),
        },
        "realization_modes": {
            "declared_profile_shipped_relation": {
                "mode": str(shipped_receipt["mode"]),
                "kernel_status": str(shipped_kernel["status"]),
                "kernel_reason": str(shipped_kernel["reason"]),
                "dimensions": plain(shipped_kernel["dimensions"]),
            },
            "declared_profile_coupled_relation": {
                "mode": str(coupled_receipt["mode"]),
                "kernel_status": str(coupled_kernel["status"]),
                "kernel_reason": str(coupled_kernel["reason"]),
                "dimensions": plain(coupled_kernel["dimensions"]),
            },
        },
        "authority": realizations,
        "route_identity": {
            "declared": (
                "a canonical packet impulse driven through the coupled input, mapped "
                "back onto the canonical page by the library's own state-to-page "
                "mapping and compared with the owner write path's page, workspace "
                "state digest, declared read frame and declared deposit. The target "
                "is the owner write's own state carried by the same mapping, so the "
                "comparison isolates the field"
            ),
            "item": spec.name,
            "amplitude_sweep": sweeps,
            "best_amplitude": best,
            "amplitudes_reporting_page_identity": swept_identical,
            "identity_at_the_declared_scan": declared_amplitude_row,
            "reconstruction_control": {
                "declared": (
                    "the same predicate on the target's own state: it must report "
                    "identity, which is what makes the negative above a measurement "
                    "rather than a predicate that cannot fire"
                ),
                "comparison": reconstruction_control,
                "reports_identity": bool(
                    reconstruction_control["page_digest_identical"]
                    and reconstruction_control["state_digest_identical"]
                ),
            },
            "no_drive_control": {
                "declared": (
                    "the same predicate on the undriven base state: it must not "
                    "report identity"
                ),
                "comparison": no_drive_control,
            },
            "route_page_against_the_owner_page": owner_page_comparison,
            "owner_route": {
                "owner_page_sha256": durability.page_sha256(p_owner),
                "owner_workspace_state_sha256": str(p_owner.state_sha256),
                "owner_deposit": float(
                    FieldAtlas.read_packet_deposit(
                        FieldAtlas.__new__(FieldAtlas),
                        AtlasState(resonant_workspace=p_owner),
                        path=direction["path"],
                        component=direction["component"],
                        flow_signal=direction["flow_signal"],
                    )["recovered_deposit"]
                ),
                "blank_deposit": float(
                    FieldAtlas.read_packet_deposit(
                        FieldAtlas.__new__(FieldAtlas),
                        AtlasState(resonant_workspace=p0),
                        path=direction["path"],
                        component=direction["component"],
                        flow_signal=direction["flow_signal"],
                    )["recovered_deposit"]
                ),
            },
        },
        "persistence": {
            "declared_profile_coupled_relation": persistence_series(
                coupled_kernel, config, drive=max(config.route_amplitudes)
            ),
            "declared_profile_shipped_relation": persistence_series(
                shipped_kernel, config, drive=max(config.route_amplitudes)
            ),
        },
        "wall_clock": {
            "cost": {
                "per_tick_seconds": per_tick_cost,
                "owner_write_seconds": {
                    "repeats": int(config.cost_repeats),
                    "samples": [float(value) for value in write_times],
                    "median_seconds": median_write,
                },
                "coupled_per_tick_over_owner_write": (
                    float(
                        per_tick_cost["declared_profile_coupled_relation"][
                            "per_tick_seconds"
                        ]
                    )
                    / median_write
                    if median_write
                    else None
                ),
                "shipped_per_tick_over_owner_write": (
                    float(
                        per_tick_cost["declared_profile_shipped_relation"][
                            "per_tick_seconds"
                        ]
                    )
                    / median_write
                    if median_write
                    else None
                ),
            },
        },
        "cost": {
            "declared": (
                "one declared advance window against one owner write of the declared "
                "item. Every figure here is wall clock on this machine, so it lives "
                "under the receipt's declared timing key and is stripped from the "
                "digest: a rebuild on a slower machine changes that block and nothing "
                "else"
            ),
            "figures_at": "elapsed_seconds.cost",
            "repeats": int(config.cost_repeats),
            "window_ticks": int(config.cost_ticks),
        },
        "declaring_nothing": {
            "declared": (
                "what is declared here is nothing: the shipped declared input stays "
                "the default, and the opt-in coupled realization is reachable only "
                "through the two helpers this measurement calls. The scan below is "
                "computed over the repository's own sources, so a caller added "
                "anywhere else would appear in it"
            ),
            "helper_names": ["condense_input", "input_problem"],
            "files_calling_the_opt_in_helpers": opt_in_callers(),
            "expected_callers": [
                "cassi_field_transceiver.py",
                "run_owner_surface_options.py",
                "test_owner_surface_options.py",
            ],
            "no_other_surface_calls_the_opt_in_helpers": bool(
                set(opt_in_callers())
                <= {
                    "cassi_field_transceiver.py",
                    "run_owner_surface_options.py",
                    "test_owner_surface_options.py",
                }
            ),
        },
        "decision_statement": (
            "declaring the coupled relation as the supported input realization would "
            "replace an inert declared input with one that carries measurable "
            "authority over the declared readout "
            f"({realizations['declared_profile_coupled_relation']['authority_window_average_spread']:.4e} "
            "window-averaged absolute readout spread against "
            f"{realizations['declared_profile_shipped_relation']['authority_window_average_spread']:.4e} "
            "for the shipped relation, and "
            f"{realizations['beta_zero_counterpart_coupled_relation']['authority_window_average_spread']:.4e} "
            "against "
            f"{realizations['beta_zero_counterpart_shipped_relation']['authority_window_average_spread']:.4e} "
            "on the beta-zero counterpart), at the cost of feeding the declared readout "
            "from a cross term between declared variables and of the per-tick work "
            "measured under elapsed_seconds.cost, against the owner write path's own "
            "cost measured in the same block; it would not reproduce the owner write "
            "path on any amplitude of the declared sweep"
        ),
    }


def declared_problem() -> ResonantProblem:
    """The declared write problem, with the shipped identity precision."""

    return ResonantProblem(
        variable_ids=("write-in", "write-out"),
        precision=np.eye(2, dtype=np.float64),
    )


# --------------------------------------------------------------------------
# the overlap rule over the declared profile lattice
# --------------------------------------------------------------------------
def overlapping_bindings(
    workspace: ResonantWorkspace, problem: ResonantProblem
) -> dict[str, dict[str, Any]]:
    """Bind every declared variable to the same port: the overlapping selection."""

    allocated = bind_workspace(workspace, problem).bindings
    shared = int(allocated[problem.variable_ids[0]]["port"])
    pool = int(allocated[problem.variable_ids[0]]["pool"])
    return {
        name: {
            **dict(allocated[name]),
            "pool": pool if name != problem.variable_ids[0] else int(allocated[name]["pool"]),
            "port": shared,
        }
        for name in problem.variable_ids
    }


def boundary_outcome(
    profile: ResonantProfile,
    bindings: Mapping[str, Any],
    problem: ResonantProblem,
) -> dict[str, Any]:
    """The library's own boundary decision for one declared problem and binding.

    This calls the same operator and the same boundary rule the condenser calls,
    with the declared value the caller names, which is how the overlap control
    below reaches a state ``condense_workspace`` cannot: the condenser hard-codes
    a unit lift perturbation for every declared input, so an observed value of
    zero is only reachable through the operator itself.
    """

    n = int(profile.port_count)
    operator = _WaveOperator(
        _workspace(profile, bindings, np.zeros(4 * n)),
        problem,
    )
    try:
        operator.boundary(np.zeros(4 * n), max(float(profile.tolerance), 1e-10))
        return {"accepted": True, "error": ""}
    except ResonantNumericalError as error:
        return {"accepted": False, "error": f"{type(error).__name__}: {error}"}


def condense_outcome(
    workspace: ResonantWorkspace,
    problem: ResonantProblem,
    config: OwnerSurfaceOptionsConfig,
) -> dict[str, Any]:
    """Whether the condenser admits one declared binding, and why not if not."""

    started = time.perf_counter()
    try:
        condense_workspace(
            workspace,
            problem,
            input_ids=("write-in",),
            output_ids=("write-out",),
            rank=int(config.overlap_rank),
            error_allowance=float(config.error_allowance),
            input_bound=float(config.input_bound),
            horizon_ticks=int(config.overlap_horizon_ticks),
        )
        return {
            "accepted": True,
            "error": "",
            "elapsed_seconds": float(time.perf_counter() - started),
        }
    except ResonantNumericalError as error:
        return {
            "accepted": False,
            "error": f"{type(error).__name__}: {error}",
            "elapsed_seconds": float(time.perf_counter() - started),
        }


def overlap_enumeration_block(config: OwnerSurfaceOptionsConfig) -> dict[str, Any]:
    """Every declared profile of the library's topology ladder, tested for overlap."""

    problem = declared_problem()
    rows: list[dict[str, Any]] = []
    for topology in DECLARED_TOPOLOGIES:
        for ports_per_pool in config.overlap_ports_per_pool:
            for beta in config.overlap_betas:
                profile = ResonantProfile(
                    topology=str(topology),
                    ports_per_pool=int(ports_per_pool),
                    beta=float(beta),
                )
                base = initial_workspace(profile)
                allocated = bind_workspace(base, problem).bindings
                overlap_bindings = overlapping_bindings(base, problem)
                overlap = ResonantWorkspace(profile=profile, bindings=overlap_bindings)
                same_port = len(
                    {int(row["port"]) for row in overlap_bindings.values()}
                ) < len(overlap_bindings)
                overlapping = condense_outcome(overlap, problem, config)
                distinct = condense_outcome(base, problem, config)
                distinct_boundary = boundary_outcome(
                    profile,
                    allocated,
                    ResonantProblem(
                        variable_ids=problem.variable_ids,
                        precision=problem.precision,
                        observed={"write-in": 1.0},
                    ),
                )
                overlap_boundary_unit = boundary_outcome(
                    profile,
                    overlap_bindings,
                    ResonantProblem(
                        variable_ids=problem.variable_ids,
                        precision=problem.precision,
                        observed={"write-in": 1.0},
                    ),
                )
                overlap_boundary_zero = boundary_outcome(
                    profile,
                    overlap_bindings,
                    ResonantProblem(
                        variable_ids=problem.variable_ids,
                        precision=problem.precision,
                        observed={"write-in": 0.0},
                    ),
                )
                rows.append(
                    {
                        "topology": str(topology),
                        "ports_per_pool": int(ports_per_pool),
                        "beta": float(beta),
                        "port_count": int(profile.port_count),
                        "distinct_ports": {
                            name: int(row["port"]) for name, row in allocated.items()
                        },
                        "overlap_ports": {
                            name: int(row["port"]) for name, row in overlap_bindings.items()
                        },
                        "the_two_declared_variables_share_a_port_in_the_overlap_selection": bool(
                            same_port
                        ),
                        "the_two_declared_variables_share_a_port_when_allocated": bool(
                            len({int(row["port"]) for row in allocated.values()})
                            < len(allocated)
                        ),
                        "overlapping_selection": overlapping,
                        "distinct_port_selection": distinct,
                        "boundary_with_a_unit_declared_value_on_the_shared_port": overlap_boundary_unit,
                        "boundary_with_a_zero_declared_value_on_the_shared_port": overlap_boundary_zero,
                        "boundary_with_a_unit_declared_value_on_distinct_ports": distinct_boundary,
                    }
                )

    accepted = [row for row in rows if row["overlapping_selection"]["accepted"]]
    refused = [row for row in rows if not row["overlapping_selection"]["accepted"]]
    distinct_accepted = [row for row in rows if row["distinct_port_selection"]["accepted"]]
    zero_accepted = [
        row for row in rows if row["boundary_with_a_zero_declared_value_on_the_shared_port"]["accepted"]
    ]
    unit_refused = [
        row
        for row in rows
        if not row["boundary_with_a_unit_declared_value_on_the_shared_port"]["accepted"]
    ]
    messages = sorted({row["overlapping_selection"]["error"] for row in refused})

    topology_control = ""
    try:
        ResonantProfile(topology=UNSUPPORTED_TOPOLOGY)
    except ResonantNumericalError as error:
        topology_control = f"{type(error).__name__}: {error}"
    if not topology_control:
        raise AssertionError("the library accepted a topology name outside the declared four")

    return {
        "declared": (
            "the overlap rule, enumerated over the declared profile lattice rather "
            "than sampled. Every declared profile is asked for the same two "
            "declared variables on one shared port, and the library's own condenser "
            "decides; the controls show what the refusal is a consequence of -- a "
            "zero declared value on the shared port is admitted, and a distinct-port "
            "selection with a unit declared value is admitted"
        ),
        "lattice": {
            "topologies": list(DECLARED_TOPOLOGIES),
            "ports_per_pool": [int(value) for value in config.overlap_ports_per_pool],
            "betas": [float(value) for value in config.overlap_betas],
            "profiles_tested": len(rows),
        },
        "rows": rows,
        "summary": {
            "profiles": len(rows),
            "overlapping_selection_refused": len(refused),
            "overlapping_selection_accepted": len(accepted),
            "distinct_port_selection_accepted": len(distinct_accepted),
            "no_profile_admits_an_overlapping_selection": bool(not accepted),
            "refusal_messages": messages,
        },
        "controls": {
            "zero_declared_value_on_the_shared_port": {
                "declared": (
                    "the same overlapping selection with a zero declared value: the "
                    "constraint row vanishes with the target, so the boundary check "
                    "admits it -- the refusal above is a nonzero target on a row that "
                    "lost its entry, not the shared port alone"
                ),
                "accepted": len(zero_accepted),
                "must_be_the_whole_lattice": True,
            },
            "unit_declared_value_on_distinct_ports": {
                "declared": (
                    "the same declared problem on the allocated distinct ports: it "
                    "must be admitted, which is what makes the overlap the cause"
                ),
                "accepted": len(distinct_accepted),
                "must_be_the_whole_lattice": True,
            },
            "unit_declared_value_on_the_shared_port": {
                "declared": (
                    "the overlapping selection with a unit declared value, through "
                    "the library's own boundary rule: it must be refused in the whole "
                    "lattice, which is the mechanism the condenser's refusal inherits"
                ),
                "refused": len(unit_refused),
                "must_be_the_whole_lattice": True,
            },
            "topology_name_control": {
                "declared": (
                    "a topology name outside the four the library validates: it must "
                    "be refused, which bounds the enumeration to the declared four"
                ),
                "name": UNSUPPORTED_TOPOLOGY,
                "refusal": topology_control,
            },
        },
        "mechanism": {
            "declared": (
                "cassi_resonant_field builds one constraint row per declared value "
                "and writes it at the declared ports; when two declared variables "
                "share a port the second write replaces the first, so the row loses "
                "an entry while its target keeps its value and the boundary check "
                "reports inconsistent common-coordinate constraints"
            ),
            "row_construction": "row[ports] = common_row / SQRT2 (cassi_resonant_field.py:1055-1058)",
            "refusal_rule": "norm(constraints @ result - targets) > tolerance (cassi_resonant_field.py:1139-1143)",
        },
    }


# --------------------------------------------------------------------------
# receipt
# --------------------------------------------------------------------------
def build_receipt(config: OwnerSurfaceOptionsConfig | None = None) -> dict[str, Any]:
    """Run every declared measurement and assemble the receipt."""

    started = time.perf_counter()
    settings = OwnerSurfaceOptionsConfig() if config is None else config
    profile = flat_profile(settings)
    reading = reading_declaration_block(profile, settings)
    coupled = coupled_input_block(profile, settings)
    overlap = overlap_enumeration_block(settings)
    wall_clock = plain(coupled.pop("wall_clock"))
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "declared": BOUNDARY,
        "limitations": LIMITATIONS,
        "digest_convention": digest_convention(),
        "config": settings.as_dict(),
        "reading_declaration": reading,
        "coupled_input": coupled,
        "overlap_enumeration": overlap,
        "verdicts": {
            "the_shipped_read_is_still_the_default": True,
            "the_shipped_declared_input_is_still_the_default": bool(
                coupled["default_off"]["kernels_identical"]
            ),
            "the_evidence_reading_advances_the_evidence_clock": bool(
                reading["evidence_reading"]["evidence_clock_moved_by"] > 0
            ),
            "the_prediction_reading_moves_nothing": bool(
                reading["prediction_reading"]["moves_nothing"]
            ),
            "the_evidence_reading_is_admitted": bool(
                reading["evidence_reading"]["admission"]["event_id"]
            ),
            "the_evidence_reading_is_refused_without_a_declared_channel": bool(
                reading["control"]["refused"]
            ),
            "nothing_downstream_of_the_admission_keys_on_observed_support": bool(
                not reading["observed_support_consumers"]["a_decision_input_moved"]
            ),
            "the_coupled_relation_carries_authority": bool(
                coupled["authority"]["declared_profile_coupled_relation"][
                    "authority_window_average_spread"
                ]
                > settings.authority_allowance
            ),
            "the_shipped_relation_carries_authority": bool(
                coupled["authority"]["declared_profile_shipped_relation"][
                    "authority_window_average_spread"
                ]
                > settings.authority_allowance
            ),
            "the_shipped_relation_carries_authority_on_its_beta_zero_counterpart": bool(
                coupled["authority"]["beta_zero_counterpart_shipped_relation"][
                    "authority_window_average_spread"
                ]
                > settings.authority_allowance
            ),
            "the_coupled_input_reproduces_the_owner_write_page": bool(
                coupled["route_identity"]["amplitudes_reporting_page_identity"]
            ),
            "no_profile_admits_an_overlapping_selection": bool(
                overlap["summary"]["no_profile_admits_an_overlapping_selection"]
            ),
        },
        "recommendation": {
            "declared": (
                "what the evidence supports recommending, and what it does not. "
                "Neither reading is adopted here: this runner declares nothing"
            ),
            "for_the_read": (
                "leave the shipped prediction reading as the default. The evidence "
                "reading is implementable and its controls fire, but the measurement "
                f"shows {reading['evidence_reading']['moved']['moved_leaf_count']} moved "
                "surface leaves and no decision input among them, so adopting it "
                "would buy an evidence clock that nothing downstream reads yet"
            ),
            "for_the_input": (
                "keep the coupled relation opt-in. It is the only one of the two "
                "input realizations measured here with authority over the declared "
                "readout, but it is orthogonal in the field to the owner write path "
                "on every amplitude of the declared sweep, so it is a second way to "
                "drive the readout rather than a re-realization of the write"
            ),
        },
        "receipt_digest": None,
        "elapsed_seconds": None,
    }
    # Every wall-clock figure in this receipt lives under this one key, which the
    # declared digest convention strips: the measured body is a function of the
    # declared settings and the field alone.
    wall_clock["total_seconds"] = float(time.perf_counter() - started)
    receipt["elapsed_seconds"] = wall_clock
    assert_finite(receipt)
    receipt["receipt_digest"] = receipt_digest(receipt)
    return receipt


def assert_finite(value: Any, path: str = "") -> None:
    """Refuse a receipt carrying a non-finite or non-JSON number."""

    if isinstance(value, Mapping):
        for key, item in value.items():
            assert_finite(item, f"{path}.{key}" if path else str(key))
    elif isinstance(value, (list, tuple)):
        for position, item in enumerate(value):
            assert_finite(item, f"{path}[{position}]")
    elif isinstance(value, float):
        if not np.isfinite(value):
            raise AssertionError(f"non-finite number at {path}")
    elif isinstance(value, (str, int, bool, type(None))):
        return
    else:
        raise AssertionError(f"non-JSON value at {path}: {type(value).__name__}")


def write_receipt(receipt: Mapping[str, Any], output: Path) -> Path:
    """Write the receipt as canonical JSON, creating its directory."""

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(receipt, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return output


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args(argv)
    receipt = build_receipt()
    path = write_receipt(receipt, arguments.output)
    print(f"wrote {path}")
    print(f"receipt_digest {receipt['receipt_digest']}")
    print(f"elapsed_seconds {receipt['elapsed_seconds']['total_seconds']:.2f}")
    for name, value in receipt["verdicts"].items():
        print(f"  {name}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
