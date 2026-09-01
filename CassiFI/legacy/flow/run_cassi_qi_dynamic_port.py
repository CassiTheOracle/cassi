"""Deterministic W11D dynamic text-port evidence and artifact writer.

This module is deliberately offline evidence code.  The only adaptive value it
uses is ``QiFieldState``; text framing and the 260-symbol codebook remain fixed
protocol data.  The runner measures complete field trajectories, then writes
content-addressed raw bytes and small canonical receipts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import struct
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import torch

from cassi_field_language import qi_state_sha256
from cassi_qi_field import QiFieldConfig, QiFieldController, QiFieldState

DYNAMIC_PORT_SCHEMA = "cassi.qi-flow-dynamic-port-frame.v1"
TEXT_OWNERSHIP_SCHEMA = "cassi.qi-flow-text-ownership.v1"
CODEBOOK_PACKING_SCHEMA = "cassi.qi-flow-text-codebook-packing.v1"
ARTIFACT_SCHEMA = "cassi.qi-flow-w11d-dynamic-port-artifact.v1"
MANIFEST_SCHEMA = "cassi.qi-flow-w11d-content-manifest.v1"
DEFAULT_OUTPUT_ROOT = Path(__file__).resolve().parent / "_diag" / "gates" / "g11d-dynamic-port"

MAX_CANDIDATES = 4096
MAX_EVIDENCE_BYTES = 65536
ALPHABET_SIZE = 260


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_hash(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))

def legacy_text_codec_fingerprint() -> str:
    """Identity of the frozen 260-symbol W11 boundary, independent of live chat."""

    return canonical_hash(
        {
            "alphabet_size": 260,
            "byte_symbols": 256,
            "end_turn_symbol": 259,
            "role_symbols": {"assistant": 258, "system": 257, "user": 256},
            "schema": "cassi.field-text-codec.v1",
        }
    )


def _f64(value: float) -> str:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("non-finite float")
    return "f64:" + struct.pack("<d", value).hex()


def _unf64(value: str) -> float:
    if not isinstance(value, str) or not value.startswith("f64:") or len(value) != 20:
        raise ValueError("invalid f64 tag")
    return struct.unpack("<d", bytes.fromhex(value[4:]))[0]


def _interval(value: float, radius: float = 0.0) -> dict[str, str]:
    value = float(value)
    radius = abs(float(radius))
    return {"value": _f64(value), "lower": _f64(max(0.0, value - radius)), "upper": _f64(value + radius)}


def _plain_interval(value: float, radius: float = 0.0) -> dict[str, str]:
    value = float(value)
    radius = abs(float(radius))
    return {"lower": _f64(max(0.0, value - radius)), "upper": _f64(value + radius)}


def _hash_without_self(value: Mapping[str, Any]) -> str:
    body = dict(value)
    body.pop("self_sha256", None)
    return canonical_hash(body)


def _float64_bytes(values: torch.Tensor) -> bytes:
    flat = values.detach().to(device="cpu", dtype=torch.float64).contiguous().reshape(-1).tolist()
    return struct.pack("<" + "d" * len(flat), *[float(item) for item in flat])


def _float32_bytes(values: torch.Tensor) -> bytes:
    flat = values.detach().to(device="cpu", dtype=torch.float32).contiguous().reshape(-1).tolist()
    return struct.pack("<" + "f" * len(flat), *[float(item) for item in flat])


@contextmanager
def _single_torch_thread() -> Iterable[None]:
    """Keep small CPU probes deterministic and avoid thread-launch jitter."""
    old = torch.get_num_threads()
    if old != 1:
        torch.set_num_threads(1)
    try:
        yield
    finally:
        if old != 1:
            torch.set_num_threads(old)


@dataclass(frozen=True)
class DynamicPortConfig:
    """Bounded calibration controls, all part of the profile identity."""

    scale_count: int = 1
    mode_count: int = 8
    n0: int = 8
    dynamic_symbols: tuple[int, ...] = tuple(range(65, 81))
    response_sample_times: tuple[float, ...] = (0.0, 0.5, 1.0)
    probe_width: int = 8
    trajectory_work_reference: float = 0.25
    rank_resolution: float = 1.0e-8
    conditioning_guard: float = 1.0e-12
    separation_threshold: float = 1.0e-7
    collision_threshold: float = 1.0e-9
    uncertainty_radius: float = 1.0e-8
    decision_uncertainty: float = 1.0e-10

    def __post_init__(self) -> None:
        if not isinstance(self.scale_count, int) or not 1 <= self.scale_count <= 4:
            raise ValueError("scale_count must be in [1, 4]")
        if not isinstance(self.mode_count, int) or self.mode_count < 4 or self.mode_count % 2:
            raise ValueError("mode_count must be even and at least four")
        if self.n0 != self.mode_count:
            raise ValueError("n0 must equal the selected fastest-sheet mode count")
        if not 1 <= len(self.dynamic_symbols) <= MAX_CANDIDATES:
            raise ValueError("dynamic_symbols must be bounded and nonempty")
        if len(set(self.dynamic_symbols)) != len(self.dynamic_symbols) or any(
            isinstance(symbol, bool) or not isinstance(symbol, int) or not 0 <= symbol < 256
            for symbol in self.dynamic_symbols
        ):
            raise ValueError("dynamic_symbols must be unique byte symbols")
        if len(self.response_sample_times) < 1 or len(self.response_sample_times) > 4096:
            raise ValueError("response_sample_times are out of bounds")
        if any(not math.isfinite(float(t)) for t in self.response_sample_times):
            raise ValueError("sample times must be finite")
        if any(a >= b for a, b in zip(self.response_sample_times, self.response_sample_times[1:])):
            raise ValueError("sample times must be strictly increasing")
        if self.response_sample_times[0] < 0.0:
            raise ValueError("sample times must be nonnegative")
        for name in (
            "trajectory_work_reference",
            "rank_resolution",
            "conditioning_guard",
            "separation_threshold",
            "collision_threshold",
            "uncertainty_radius",
            "decision_uncertainty",
        ):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and nonnegative")
        if self.trajectory_work_reference <= 0.0:
            raise ValueError("trajectory_work_reference must be positive")

    @property
    def physical_horizon(self) -> float:
        return float(self.response_sample_times[-1])

    @property
    def profile_dict(self) -> dict[str, Any]:
        return {
            "n0": self.n0,
            "mode_count": self.mode_count,
            "scale_count": self.scale_count,
            "dynamic_symbols": list(self.dynamic_symbols),
            "response_sample_times": list(self.response_sample_times),
            "probe_width": self.probe_width,
            "trajectory_work_reference": self.trajectory_work_reference,
            "rank_resolution": self.rank_resolution,
            "conditioning_guard": self.conditioning_guard,
            "separation_threshold": self.separation_threshold,
            "collision_threshold": self.collision_threshold,
            "uncertainty_radius": self.uncertainty_radius,
            "decision_uncertainty": self.decision_uncertainty,
        }

    @property
    def profile_sha256(self) -> str:
        return canonical_hash(self.profile_dict)

    def controller(self) -> QiFieldController:
        return QiFieldController(
            QiFieldConfig(
                scale_count=self.scale_count,
                mode_count=self.mode_count,
                alphabet_size=ALPHABET_SIZE,
            )
        )


@dataclass(frozen=True)
class ReactionCandidate:
    candidate_id: str
    symbol: int | None
    feasibility_lower: float
    feasibility_upper: float
    score_lower: float
    score_upper: float
    order: int = 0

    def __post_init__(self) -> None:
        if not self.candidate_id or any(ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._:-" for ch in self.candidate_id):
            raise ValueError("candidate_id is invalid")
        if self.symbol is not None and (isinstance(self.symbol, bool) or not 0 <= self.symbol < ALPHABET_SIZE):
            raise ValueError("candidate symbol is invalid")
        values = (self.feasibility_lower, self.feasibility_upper, self.score_lower, self.score_upper)
        if any(not math.isfinite(float(value)) for value in values):
            raise ValueError("candidate intervals must be finite")
        if self.feasibility_lower > self.feasibility_upper or self.score_lower > self.score_upper:
            raise ValueError("candidate intervals are reversed")

    @property
    def feasibility(self) -> str:
        if self.feasibility_lower > 0.0:
            return "feasible"
        if self.feasibility_upper <= 0.0:
            return "infeasible"
        return "abstain"

    def score_interval(self) -> dict[str, str]:
        value = (self.score_lower + self.score_upper) / 2.0
        return {"value": _f64(value), "lower": _f64(self.score_lower), "upper": _f64(self.score_upper)}


def _candidate_from(value: ReactionCandidate | Mapping[str, Any], order: int) -> ReactionCandidate:
    if isinstance(value, ReactionCandidate):
        return ReactionCandidate(**{**value.__dict__, "order": order})
    if not isinstance(value, Mapping):
        raise TypeError("candidate must be a ReactionCandidate or mapping")
    feasibility = value.get("feasibility_interval", value.get("feasibility", (1.0, 1.0)))
    score = value.get("score_interval", value.get("score", (0.0, 0.0)))
    if isinstance(feasibility, Mapping):
        fl, fu = feasibility.get("lower"), feasibility.get("upper")
    else:
        fl, fu = feasibility
    if isinstance(score, Mapping):
        sl, su = score.get("lower"), score.get("upper")
        if isinstance(sl, str):
            sl = _unf64(sl)
        if isinstance(su, str):
            su = _unf64(su)
    else:
        sl, su = score
    return ReactionCandidate(
        candidate_id=str(value["candidate_id"]),
        symbol=value.get("symbol"),
        feasibility_lower=float(fl),
        feasibility_upper=float(fu),
        score_lower=float(sl),
        score_upper=float(su),
        order=order,
    )


def _decision(candidates: Sequence[ReactionCandidate], uncertainty: float) -> dict[str, Any]:
    feasible = [candidate for candidate in candidates if candidate.feasibility == "feasible"]
    if not feasible:
        return {"kind": "abstain", "reason": "no-feasible-candidate"}
    ranked = sorted(feasible, key=lambda candidate: (-candidate.score_lower, candidate.order, candidate.candidate_id))
    winner = ranked[0]
    competitors = [candidate for candidate in feasible if candidate is not winner]
    null_lower = 0.0
    null_upper = 0.0
    if winner.score_upper <= null_lower + uncertainty:
        return {"kind": "abstain", "reason": "null-or-zero-margin"}
    for candidate in competitors:
        if candidate.score_upper + uncertainty >= winner.score_lower:
            # Equal exact intervals are a canonical tie; choose the earliest
            # registered candidate. Any nonzero enclosure overlap abstains.
            if (
                candidate.score_lower == candidate.score_upper == winner.score_lower == winner.score_upper
                and candidate.score_lower > null_upper + uncertainty
            ):
                continue
            return {"kind": "abstain", "reason": "interval-overlap"}
    result: dict[str, Any] = {"kind": "candidate", "candidate_id": winner.candidate_id}
    if winner.symbol is not None:
        result["symbol"] = winner.symbol
    return result


def evaluate_reaction_candidates(
    candidates: Sequence[ReactionCandidate | Mapping[str, Any]],
    *,
    uncertainty: float = 1.0e-10,
) -> dict[str, Any]:
    """Run exhaustive and interval-pruned reaction evaluation.

    A candidate is omitted only when its score upper bound is strictly below
    the exhaustive winner's lower bound.  Overlap, ties, empty sets, and
    unresolved feasibility remain in the complete frontier.
    """
    if len(candidates) > MAX_CANDIDATES:
        raise ValueError("candidate set exceeds bounded fanout")
    normalized = [_candidate_from(value, index) for index, value in enumerate(candidates)]
    uncertainty = float(uncertainty)
    if not math.isfinite(uncertainty) or uncertainty < 0.0:
        raise ValueError("uncertainty must be finite and nonnegative")
    exhaustive = _decision(normalized, uncertainty)
    winner = next((candidate for candidate in normalized if candidate.candidate_id == exhaustive.get("candidate_id")), None)
    kept: list[ReactionCandidate] = []
    pruned_ids: set[str] = set()
    for candidate in normalized:
        if winner is not None and candidate is not winner and candidate.score_upper + uncertainty < winner.score_lower:
            pruned_ids.add(candidate.candidate_id)
        else:
            kept.append(candidate)
    pruned = _decision(kept, uncertainty)
    if pruned != exhaustive:
        raise RuntimeError(
            "interval pruning rule failed exact exhaustive equivalence; "
            "candidate frontier was not silently restored"
        )
    outcomes = []
    for candidate in normalized:
        outcomes.append(
            {
                "candidate_id": candidate.candidate_id,
                "exhaustive_feasibility": candidate.feasibility,
                "pruned_feasibility": candidate.feasibility,
                "score_interval": candidate.score_interval(),
                "kept_by_pruning": candidate.candidate_id not in pruned_ids,
            }
        )
    exhaustive_set = [candidate.candidate_id for candidate in normalized]
    pruned_set = [candidate.candidate_id for candidate in kept]
    decision_sha = canonical_hash({"exhaustive": exhaustive, "pruned": pruned, "order": exhaustive_set})
    return {
        "exhaustive_decision": exhaustive,
        "pruned_decision": pruned,
        "decision_equivalent_to_exhaustive": pruned == exhaustive,
        "outcomes": outcomes,
        "exhaustive_candidate_set_sha256": canonical_hash(exhaustive_set),
        "pruned_candidate_set_sha256": canonical_hash(pruned_set),
        "interval_rule_sha256": canonical_hash(
            {
                "rule": "retain-overlap-ties-and-null; prune-score-upper-below-winner-lower",
                "uncertainty": uncertainty,
            }
        ),
        "decision_sha256": decision_sha,
    }


def _probe_values(state: QiFieldState, width: int) -> torch.Tensor:
    flat = state.field.permute(2, 0, 1).reshape(state.batch_size, -1)
    indices = torch.tensor([(3 + 17 * index) % flat.shape[1] for index in range(width)], dtype=torch.long)
    values = flat.index_select(1, indices)
    signs = torch.tensor([1.0 if index % 2 == 0 else -1.0 for index in range(width)], dtype=values.dtype).reshape(1, -1)
    return values * signs


def _phase_permute(state: QiFieldState, controller: QiFieldController) -> QiFieldState:
    packed = state.field.reshape(controller.config.scale_count, 9, controller.config.mode_count, state.batch_size)
    permutation = (1, 0, 3, 2, 5, 4, 7, 6, 8)
    return QiFieldState(packed[:, permutation].contiguous().reshape_as(state.field))


def _rollout(
    controller: QiFieldController,
    symbols: Sequence[int],
    config: DynamicPortConfig,
    *,
    control: str = "active",
) -> tuple[torch.Tensor, tuple[QiFieldState, ...], QiFieldState]:
    if control not in {"active", "field-off", "frozen", "phase-permuted"}:
        raise ValueError(f"unknown field control: {control}")
    with _single_torch_thread():
        state = controller.initial_state(len(symbols), dtype=torch.float64)
        source = 0.0 if control == "field-off" else 1.0
        state = controller.sense_symbols(state, list(symbols), source_trust=source)
        if control == "phase-permuted":
            state = _phase_permute(state, controller)
        samples: list[torch.Tensor] = []
        for index, _time in enumerate(config.response_sample_times):
            samples.append(_probe_values(state, config.probe_width))
            if index + 1 < len(config.response_sample_times) and control not in {"field-off", "frozen"}:
                state = controller.evolve(state, steps=1)
                state = controller.consolidate(state)
        trajectories = torch.stack(samples, dim=1).contiguous()
        endpoints = tuple(QiFieldState(state.field[:, :, index : index + 1].clone()) for index in range(state.batch_size))
        return trajectories, endpoints, state


def _time_fraction(value: float) -> dict[str, str]:
    # The profile uses tenths, avoiding decimal or host-clock ambiguity.
    numerator = int(round(float(value) * 10.0))
    denominator = 10
    gcd = math.gcd(numerator, denominator)
    return {"n": str(numerator // gcd), "d": str(denominator // gcd)}


def timed_packets(symbols: Sequence[int], config: DynamicPortConfig) -> tuple[dict[str, Any], ...]:
    packets = []
    horizon = config.physical_horizon
    for index, symbol in enumerate(symbols):
        start = config.response_sample_times[0]
        end = horizon
        packets.append(
            {
                "packet_id": f"packet-{index:04d}",
                "sequence": str(index),
                "source_symbol": int(symbol),
                "interval": {"start": _time_fraction(start), "end": _time_fraction(end)},
                "input_bytes_sha256": sha256_bytes(bytes([int(symbol)])),
                "admitted_work": {"value": _f64(1.0), "lower": _f64(1.0), "upper": _f64(1.0), "unit": "normalized"},
            }
        )
    return tuple(packets)


def _trajectory_item(
    index: int,
    symbol: int,
    predecessor_hash: str,
    endpoint_hash: str,
    raw: bytes,
    shape: Sequence[int],
) -> dict[str, Any]:
    return {
        "trajectory_id": f"traj-{index:04d}",
        "predecessor_state_sha256": predecessor_hash,
        "endpoint_state_sha256": endpoint_hash,
        "source_work_interval": {"value": _f64(1.0), "lower": _f64(1.0), "upper": _f64(1.0), "unit": "normalized"},
        "raw_trajectory": {
            "encoding": "little-endian-array-v1",
            "dtype": "f64_le",
            "shape": [str(int(item)) for item in shape],
            "byte_count": str(len(raw)),
            "sha256": sha256_bytes(raw),
        },
        "source_symbol": int(symbol),
    }


def _remove_extra_trajectory_key(item: Mapping[str, Any]) -> dict[str, Any]:
    # Registry candidate items are closed objects; source_symbol lives only in
    # the raw packet manifest, not in the canonical frame.
    result = dict(item)
    result.pop("source_symbol", None)
    return result


def _semantic_subhashes(controller: QiFieldController, config: DynamicPortConfig) -> list[dict[str, str]]:
    return [
        {"name": "state_contract_sha256", "sha256": canonical_hash({"shape": [config.scale_count, 9 * config.mode_count, 1], "adaptive": 1})},
        {"name": "boundary_action_sha256", "sha256": controller.codebook_fingerprint},
        {"name": "backend_capacity_sha256", "sha256": canonical_hash({"backend": "torch", "dtype": "float64", "n0": config.n0})},
    ]


def _build_dynamic(config: DynamicPortConfig) -> tuple[dict[str, Any], dict[str, bytes], dict[str, Any]]:
    controller = config.controller()
    symbols = tuple(config.dynamic_symbols)
    with _single_torch_thread():
        predecessor = controller.initial_state(1, dtype=torch.float64)
        predecessor_hash = qi_state_sha256(controller, predecessor)
        trajectories, endpoints, _ = _rollout(controller, symbols, config)
        null = torch.zeros_like(trajectories[:1])
        normalized = trajectories / math.sqrt(1.0 + config.trajectory_work_reference)
        response = normalized.permute(1, 2, 0).reshape(-1, len(symbols))
        singular = torch.linalg.svdvals(response)
        singular_values = [float(value) for value in singular.tolist()]
        rank = sum(value > config.rank_resolution for value in singular_values)
        if singular_values and singular_values[-1] > config.conditioning_guard:
            conditioning = singular_values[0] / singular_values[-1]
        else:
            conditioning = 0.0
        gram = response.transpose(0, 1) @ response
        diagonal = torch.sqrt(torch.clamp(torch.diag(gram), min=1.0e-30))
        cross = gram / (diagonal[:, None] * diagonal[None, :])
        cross.fill_diagonal_(0.0)
        cross_norm = float(torch.abs(cross).sum(dim=1).max().item()) if cross.numel() else 0.0
        raw_response = _float64_bytes(normalized)
        raw_cross = _float64_bytes(cross)
        raw_trajectories = b"".join(_float64_bytes(trajectories[index]) for index in range(len(symbols)))
        raw_count = len(raw_response) + len(raw_cross) + len(raw_trajectories)
        if raw_count > MAX_EVIDENCE_BYTES:
            raise ValueError("dynamic evidence exceeds the registered byte bound")
        endpoint_hashes = [qi_state_sha256(controller, endpoint) for endpoint in endpoints]
        candidate_rows = []
        reaction_candidates = []
        for index, symbol in enumerate(symbols):
            raw = _float64_bytes(trajectories[index])
            candidate_rows.append(
                _remove_extra_trajectory_key(
                    _trajectory_item(index, symbol, predecessor_hash, endpoint_hashes[index], raw, trajectories[index].shape[1:])
                )
            )
            score = float(torch.linalg.vector_norm(normalized[index]).item())
            reaction_candidates.append(
                ReactionCandidate(f"traj-{index:04d}", int(symbol), 1.0, 1.0, score, score, index)
            )
        pruning = evaluate_reaction_candidates(reaction_candidates, uncertainty=config.decision_uncertainty)
        sample_grid = [_time_fraction(value) for value in config.response_sample_times]
        response_meta = {
            "encoding": "little-endian-array-v1",
            "dtype": "f64_le",
            "shape": [str(len(config.response_sample_times)), str(config.probe_width), str(len(symbols))],
            "byte_count": str(len(raw_response)),
            "sha256": sha256_bytes(raw_response),
        }
        cross_meta = {
            "encoding": "little-endian-array-v1",
            "dtype": "f64_le",
            "shape": [str(len(symbols)), str(len(symbols))],
            "byte_count": str(len(raw_cross)),
            "sha256": sha256_bytes(raw_cross),
        }
        descriptor = {
            "port_id": "text-port-0",
            "n0": config.n0,
            "source_symbols": list(symbols),
            "receiver_probe_width": config.probe_width,
            "sample_grid": sample_grid,
            "controller_config_sha256": controller.config_fingerprint,
        }
        frame: dict[str, Any] = {
            "schema": DYNAMIC_PORT_SCHEMA,
            "contract_root_sha256": canonical_hash({"contract": "cassi-fi-w11d", "schema": DYNAMIC_PORT_SCHEMA}),
            "profile_sha256": config.profile_sha256,
            "consumed_semantic_subhashes": _semantic_subhashes(controller, config),
            "frame_id": "w11d-dynamic-text-port-0001",
            "step_sha256": canonical_hash({"sample_grid": sample_grid, "dt": controller.config.physics.dt}),
            "predecessor_head_sha256": predecessor_hash,
            "successor_head_sha256": canonical_hash(endpoint_hashes),
            "predecessor_state_sha256": predecessor_hash,
            "port_id": "text-port-0",
            "port_kind": "text",
            "scale_id": None,
            "descriptor_sha256": canonical_hash(descriptor),
            "dynamic_operator_sha256": canonical_hash({"operator": "field-trajectory-projection-v1", "probe_indices": [3 + 17 * i for i in range(config.probe_width)]}),
            "physical_horizon": _time_fraction(config.physical_horizon),
            "intervention_set_sha256": canonical_hash({"controls": ["field-off", "frozen", "phase-permuted"]}),
            "source_receiver_probe_order_sha256": canonical_hash({"sources": list(symbols), "receivers": list(range(config.probe_width))}),
            "null_source_sha256": sha256_bytes(_float64_bytes(null)),
            "candidate_trajectory_count": str(len(symbols)),
            "candidate_trajectories": candidate_rows,
            "response_sample_grid": sample_grid,
            "response_vector_width": str(config.probe_width),
            "response_vectors": response_meta,
            "rank_interval": _interval(float(rank), 0.0),
            "singular_value_intervals": [_interval(value, max(config.uncertainty_radius, value * 1.0e-9)) for value in singular_values],
            "conditioning_interval": _interval(conditioning, max(config.uncertainty_radius, conditioning * 1.0e-9)),
            "cross_talk": {
                "matrix": cross_meta,
                "induced_norm_interval": _interval(cross_norm, config.uncertainty_radius),
                "guard": _interval(config.separation_threshold, 0.0),
            },
            "sampling_refinement_sha256": canonical_hash({"samples": sample_grid, "refinement": "fixed-complete-window-v1"}),
            "no_peek_runtime_input_sha256": canonical_hash({"source_symbols": list(symbols), "packets": timed_packets(symbols, config)}),
            "pruning_proof": {
                "exhaustive_candidate_set_sha256": pruning["exhaustive_candidate_set_sha256"],
                "pruned_candidate_set_sha256": pruning["pruned_candidate_set_sha256"],
                "interval_rule_sha256": pruning["interval_rule_sha256"],
                "decision_sha256": pruning["decision_sha256"],
                "decision_equivalent_to_exhaustive": True,
                "candidate_outcomes": pruning["outcomes"],
            },
            "counts": {
                "dynamic_frame_count": "1",
                "candidate_trajectory_count": str(len(symbols)),
                "response_sample_count": str(len(config.response_sample_times)),
                "raw_evidence_byte_count": str(raw_count),
                "max_dynamic_frames_per_cycle": "1",
                "max_candidate_trajectories_per_cycle": str(MAX_CANDIDATES),
                "max_dynamic_response_bytes_per_frame": str(MAX_EVIDENCE_BYTES),
                "max_dynamic_evidence_bytes_per_cycle": str(MAX_EVIDENCE_BYTES),
            },
            "bound_identity": canonical_hash({"max_candidates": MAX_CANDIDATES, "max_evidence_bytes": MAX_EVIDENCE_BYTES}),
            "fixture_sha256": canonical_hash({"profile": config.profile_dict, "descriptor": descriptor, "packets": timed_packets(symbols, config)}),
            "independent_replay_identity": canonical_hash({"predecessor": predecessor_hash, "operator": descriptor, "response": response_meta["sha256"]}),
        }
        frame["self_sha256"] = _hash_without_self(frame)
        raw = {
            response_meta["sha256"]: raw_response,
            cross_meta["sha256"]: raw_cross,
            "trajectory-stream": raw_trajectories,
            "packet-table": canonical_json_bytes(list(timed_packets(symbols, config))),
        }
        auxiliary = {
            "controller": controller,
            "predecessor": predecessor,
            "predecessor_hash": predecessor_hash,
            "trajectories": trajectories,
            "normalized": normalized,
            "endpoint_hashes": endpoint_hashes,
            "symbols": symbols,
            "pruning": pruning,
            "descriptor": descriptor,
            "raw_trajectories": raw_trajectories,
            "rank": rank,
            "conditioning": conditioning,
        }
        return frame, raw, auxiliary


def build_dynamic_port_frame(config: DynamicPortConfig | None = None) -> dict[str, Any]:
    return _build_dynamic(config or DynamicPortConfig())[0]


def _build_ownership(config: DynamicPortConfig, dynamic: Mapping[str, Any], auxiliary: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, bytes], dict[str, Any]]:
    controller: QiFieldController = auxiliary["controller"]
    symbols = tuple(auxiliary["symbols"])
    trajectories: torch.Tensor = auxiliary["trajectories"]
    normalized: torch.Tensor = auxiliary["normalized"]
    predecessor_hash = str(auxiliary["predecessor_hash"])
    scores = [float(torch.linalg.vector_norm(normalized[index]).item()) for index in range(len(symbols))]
    active_candidates = [ReactionCandidate(f"traj-{index:04d}", int(symbol), 1.0, 1.0, score, score, index) for index, (symbol, score) in enumerate(zip(symbols, scores))]
    active = evaluate_reaction_candidates(active_candidates, uncertainty=config.decision_uncertainty)
    off_trajectories, _, _ = _rollout(controller, symbols, config, control="field-off")
    frozen_trajectories, _, _ = _rollout(controller, symbols, config, control="frozen")
    permuted_trajectories, _, _ = _rollout(controller, symbols, config, control="phase-permuted")

    def control_eval(values: torch.Tensor) -> dict[str, Any]:
        norm = values / math.sqrt(1.0 + config.trajectory_work_reference)
        rows = [ReactionCandidate(f"traj-{index:04d}", int(symbol), 1.0, 1.0, float(torch.linalg.vector_norm(norm[index]).item()), float(torch.linalg.vector_norm(norm[index]).item()), index) for index, symbol in enumerate(symbols)]
        return evaluate_reaction_candidates(rows, uncertainty=config.decision_uncertainty)

    intervention = control_eval(off_trajectories)
    controls = {"field-off": intervention, "frozen": control_eval(frozen_trajectories), "phase-permuted": control_eval(permuted_trajectories)}
    active_decision = active["exhaustive_decision"]
    intervention_decision = intervention["exhaustive_decision"]
    if active_decision.get("kind") != "candidate":
        raise ValueError("active fixture did not resolve to a byte")
    active_symbol = int(active_decision["symbol"])
    if intervention_decision.get("kind") != "abstain":
        raise ValueError("field-off fixture unexpectedly resolved")
    winner_index = symbols.index(active_symbol)
    active_score = scores[winner_index]
    active_bytes = bytes([active_symbol])
    intervention_bytes = b""
    control_bytes = canonical_json_bytes({"decision": active_decision, "controls": controls})
    intervention_control_bytes = canonical_json_bytes({"decision": intervention_decision, "control": "field-off"})
    active_run = canonical_json_bytes({"control": "active", "trajectory": normalized.tolist(), "decision": active_decision})
    intervention_run = canonical_json_bytes({"control": "field-off", "trajectory": (off_trajectories / math.sqrt(1.0 + config.trajectory_work_reference)).tolist(), "decision": intervention_decision})
    margin = max(active_score, config.decision_uncertainty)
    raw = {
        "ownership-active-run": active_run,
        "ownership-intervention-run": intervention_run,
        "ownership-active-result": active_bytes,
        "ownership-intervention-result": intervention_bytes,
        "ownership-active-controls": control_bytes,
        "ownership-intervention-controls": intervention_control_bytes,
    }
    receipt: dict[str, Any] = {
        "schema": TEXT_OWNERSHIP_SCHEMA,
        "receipt_id": "w11d-text-ownership-0001",
        "profile_sha256": config.profile_sha256,
        "state_contract_sha256": dynamic["consumed_semantic_subhashes"][0]["sha256"],
        "boundary_action_sha256": dynamic["consumed_semantic_subhashes"][1]["sha256"],
        "fixed_text_codec_identity": {"symbol_count": ALPHABET_SIZE, "codec_sha256": legacy_text_codec_fingerprint()},
        "canonical_wire_schema": "cassi.canonical-json.v1",
        "text_descriptor_sha256": dynamic["descriptor_sha256"],
        "predecessor_head_sha256": predecessor_hash,
        "matched_input_trajectory_sha256": canonical_hash(timed_packets(symbols, config)),
        "field_active_run_sha256": sha256_bytes(active_run),
        "field_intervention_run_sha256": sha256_bytes(intervention_run),
        "intervention_operator_sha256": canonical_hash({"operator": "zero-field-v1", "changed_input": "field_state_only"}),
        "active_result_bytes_sha256": sha256_bytes(active_bytes),
        "intervention_result_bytes_sha256": sha256_bytes(intervention_bytes),
        "active_control_bytes_sha256": sha256_bytes(control_bytes),
        "intervention_control_bytes_sha256": sha256_bytes(intervention_control_bytes),
        "field_necessity_interval": _plain_interval(margin, config.uncertainty_radius),
        "null_interval": _plain_interval(0.0, 0.0),
        "causal_margin_interval": _plain_interval(margin, config.uncertainty_radius),
        "uncertainty_threshold": _f64(config.decision_uncertainty),
        "consequence_class": "byte",
        "heldout_trajectory_set_sha256": canonical_hash({"heldout": list(symbols[::2]), "window": list(config.response_sample_times)}),
        "bounded_frame_count": 1,
        "bounded_evidence_bytes": sum(len(value) for value in raw.values()),
        "consumed_semantic_subhashes": dynamic["consumed_semantic_subhashes"],
    }
    if receipt["bounded_evidence_bytes"] > MAX_EVIDENCE_BYTES:
        raise ValueError("ownership evidence exceeds the registered byte bound")
    receipt["self_sha256"] = _hash_without_self(receipt)
    aux = {"controls": controls, "active": active, "intervention": intervention, "active_symbol": active_symbol, "active_score": active_score}
    return receipt, raw, aux


def _build_packing(config: DynamicPortConfig, dynamic: Mapping[str, Any], auxiliary: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, bytes], dict[str, Any]]:
    controller: QiFieldController = auxiliary["controller"]
    # The fixed text alphabet is complete even though the dynamic frame uses a
    # bounded source probe set.  Packing never feeds this trajectory back into
    # the live field or output selector.
    symbols = tuple(range(256)) + (256, 257, 258, 259)
    trajectories, _, _ = _rollout(controller, symbols, config)
    normalized = trajectories / math.sqrt(2.0 + config.trajectory_work_reference)
    flattened = normalized.reshape(len(symbols), -1)
    distances = torch.cdist(flattened, flattened)
    distances.fill_diagonal_(float("inf"))
    uncertainty = float(config.uncertainty_radius)
    lower = torch.clamp(distances - uncertainty, min=0.0)
    upper = distances + uncertainty
    threshold = config.separation_threshold
    robust_mask = lower >= torch.maximum(torch.tensor(threshold), config.decision_uncertainty * upper)
    robust_count = int(robust_mask.sum().item() // 2)
    min_lower = float(lower.min().item())
    min_upper = float(upper.min().item())
    null_distance = torch.linalg.vector_norm(flattened, dim=1)
    null_lower = float(torch.clamp(null_distance - uncertainty, min=0.0).min().item())
    null_upper = float((null_distance + uncertainty).min().item())
    raw_trajectories = _float32_bytes(trajectories)
    # Every pair is evaluated above.  Retain a content digest plus aggregate
    # interval bounds; raw trajectories remain the replayable evidence object.
    metric_digest = hashlib.sha256()
    for row in lower.tolist():
        metric_digest.update(struct.pack("<" + "f" * len(row), *[float(v) for v in row]))
    for row in upper.tolist():
        metric_digest.update(struct.pack("<" + "f" * len(row), *[float(v) for v in row]))
    metric_sha = metric_digest.hexdigest()
    trajectory_sha = sha256_bytes(raw_trajectories)
    metric_summary = canonical_json_bytes(
        {
            "candidate_count": ALPHABET_SIZE,
            "pair_count": ALPHABET_SIZE * (ALPHABET_SIZE - 1) // 2,
            "robust_pair_count": robust_count,
            "distance_lower": min_lower,
            "distance_upper": min_upper,
            "null_lower": null_lower,
            "null_upper": null_upper,
            "uncertainty_radius": uncertainty,
            "metric_sha256": metric_sha,
        }
    )
    descriptor_registry_sha = canonical_hash(controller.codebook_descriptors)
    projection_registry_sha = canonical_hash({"probe_indices": [3 + 17 * i for i in range(config.probe_width)], "width": config.probe_width})
    receipt: dict[str, Any] = {
        "schema": CODEBOOK_PACKING_SCHEMA,
        "receipt_id": "w11d-text-codebook-packing-0001",
        "profile_sha256": config.profile_sha256,
        "state_contract_sha256": dynamic["consumed_semantic_subhashes"][0]["sha256"],
        "boundary_action_sha256": dynamic["consumed_semantic_subhashes"][1]["sha256"],
        "codec_sha256": legacy_text_codec_fingerprint(),
        "codec_symbol_count": ALPHABET_SIZE,
        "descriptor_registry_sha256": descriptor_registry_sha,
        "projection_registry_sha256": projection_registry_sha,
        "trajectory_response_matrix_sha256": trajectory_sha,
        "trajectory_metric_sha256": metric_sha,
        "response_rank_interval": {"lower": int(_unf64(dynamic["rank_interval"]["lower"])), "upper": int(_unf64(dynamic["rank_interval"]["upper"]))},
        "packing_rank_interval": {"lower": int(dynamic["rank_interval"]["value"].split(":")[0] == "f64") * int(_unf64(dynamic["rank_interval"]["value"])), "upper": int(_unf64(dynamic["rank_interval"]["value"]))},
        "separation_margin_interval": _plain_interval(min_lower, uncertainty),
        "null_separation_interval": _plain_interval(null_lower, uncertainty),
        "uncertainty_threshold": _f64(config.uncertainty_radius),
        "packing_rule_sha256": canonical_hash({"rule": "work-normalized-complete-trajectory-pair-interval-v1", "delta_sep": threshold, "delta_coll": config.collision_threshold}),
        "symbol_assignment_fixture_sha256": canonical_hash({"symbols": list(symbols), "assignment": "fixed-byte-and-role-order-v1"}),
        "heldout_fixture_sha256": canonical_hash({"symbols": list(symbols[::2]), "predecessor": auxiliary["predecessor_hash"]}),
        "bounded_candidate_trajectory_count": ALPHABET_SIZE,
        "bounded_evidence_bytes": len(raw_trajectories) + len(metric_summary),
        "consumed_semantic_subhashes": dynamic["consumed_semantic_subhashes"],
    }
    if receipt["bounded_evidence_bytes"] > MAX_EVIDENCE_BYTES:
        raise ValueError("packing evidence exceeds the registered byte bound")
    receipt["self_sha256"] = _hash_without_self(receipt)
    raw = {"packing-trajectories": raw_trajectories, "packing-metric-summary": metric_summary}
    aux = {"trajectories": trajectories, "lower": lower, "upper": upper, "robust_count": robust_count, "metric_summary": metric_summary, "metric_sha": metric_sha}
    return receipt, raw, aux


def build_dynamic_port_evidence(config: DynamicPortConfig | None = None) -> dict[str, Any]:
    config = config or DynamicPortConfig()
    dynamic, raw_dynamic, auxiliary = _build_dynamic(config)
    ownership, raw_ownership, ownership_aux = _build_ownership(config, dynamic, auxiliary)
    packing, raw_packing, packing_aux = _build_packing(config, dynamic, auxiliary)
    raw: dict[str, bytes] = {}
    raw.update(raw_dynamic)
    raw.update(raw_ownership)
    raw.update(raw_packing)
    return {
        "frame": dynamic,
        "ownership": ownership,
        "packing": packing,
        "raw": raw,
        "auxiliary": {"ownership": ownership_aux, "packing": packing_aux, "profile": config.profile_dict},
    }


def _content_name(data: bytes, suffix: str) -> str:
    return f"{sha256_bytes(data)}{suffix}"


def _write_json(path: Path, value: Any) -> None:
    path.write_bytes(canonical_json_bytes(value))


def materialize_dynamic_port_artifact(output_root: Path = DEFAULT_OUTPUT_ROOT, config: DynamicPortConfig | None = None) -> dict[str, Any]:
    output_root = Path(output_root)
    if output_root.exists():
        raise FileExistsError(f"refusing to replace existing artifact root: {output_root}")
    evidence = build_dynamic_port_evidence(config)
    stage = Path(tempfile.mkdtemp(prefix=f".{output_root.name}-", dir=output_root.parent))
    try:
        raw_dir = stage / "raw"
        raw_dir.mkdir(parents=True, exist_ok=False)
        raw_manifest = {}
        for label, data in sorted(evidence["raw"].items()):
            suffix = ".json" if label.endswith("table") or label.endswith("controls") or label.endswith("run") or label.endswith("summary") else ".bin"
            name = _content_name(data, suffix)
            (raw_dir / name).write_bytes(data)
            raw_manifest[label] = {"path": f"raw/{name}", "sha256": sha256_bytes(data), "byte_count": len(data)}
        _write_json(stage / "dynamic-port-frame.json", evidence["frame"])
        _write_json(stage / "text-ownership.json", evidence["ownership"])
        _write_json(stage / "text-codebook-packing.json", evidence["packing"])
        body = {
            "schema": MANIFEST_SCHEMA,
            "artifact_schema": ARTIFACT_SCHEMA,
            "receipt_ids": [evidence["frame"]["frame_id"], evidence["ownership"]["receipt_id"], evidence["packing"]["receipt_id"]],
            "raw": raw_manifest,
            "receipts": {
                "dynamic": "dynamic-port-frame.json",
                "ownership": "text-ownership.json",
                "packing": "text-codebook-packing.json",
            },
        }
        manifest = {**body, "artifact_sha256": canonical_hash(body)}
        _write_json(stage / "manifest.json", manifest)
        status = {
            "schema": ARTIFACT_SCHEMA,
            "status": "PASS",
            "artifact_sha256": manifest["artifact_sha256"],
            "frame_self_sha256": evidence["frame"]["self_sha256"],
            "ownership_self_sha256": evidence["ownership"]["self_sha256"],
            "packing_self_sha256": evidence["packing"]["self_sha256"],
        }
        _write_json(stage / "status.json", status)
        index = {"schema": ARTIFACT_SCHEMA, "status": "PASS", "manifest": "manifest.json", "status_file": "status.json"}
        _write_json(stage / "index.json", index)
        output_root.parent.mkdir(parents=True, exist_ok=True)
        os.replace(stage, output_root)
    except BaseException:
        import shutil
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return {"status": "PASS", "output_root": output_root.as_posix(), "artifact_sha256": manifest["artifact_sha256"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args(argv)
    print(canonical_json_bytes(materialize_dynamic_port_artifact(args.out)).decode("utf-8"))
    return 0


__all__ = [
    "ALPHABET_SIZE",
    "ARTIFACT_SCHEMA",
    "CODEBOOK_PACKING_SCHEMA",
    "DYNAMIC_PORT_SCHEMA",
    "DynamicPortConfig",
    "MANIFEST_SCHEMA",
    "ReactionCandidate",
    "TEXT_OWNERSHIP_SCHEMA",
    "build_dynamic_port_evidence",
    "build_dynamic_port_frame",
    "canonical_hash",
    "canonical_json_bytes",
    "evaluate_reaction_candidates",
    "materialize_dynamic_port_artifact",
    "timed_packets",
]


if __name__ == "__main__":
    raise SystemExit(main())
