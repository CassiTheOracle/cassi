"""One public record over the universal regional field computer."""
from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass, field as dataclass_field, replace
from types import MappingProxyType
from typing import Any, Callable, Iterable, Mapping, Sequence
import base64
import numpy as np

import cassi_field_regions as _field_regions

from cassi_computation_policy import (
    METHODS,
    PolicyState,
    _profile_for,
    audit_result,
    compile_source,
    encode_regional_policy,
    initial_policy,
    regional_state as policy_regional_state,
    regional_kernel as policy_regional_kernel,
)
from cassi_constraint_field import (
    REGIONAL_KERNEL_NAME as CONSTRAINT_KERNEL,
    regional_state as constraint_regional_state,
)
from cassi_field_computer import (
    ComputerProfile,
    ComputerState,
    FieldComputer,
    FieldComputerError,
    PagedComputerState,
    _canonical_instruction,
)
from cassi_field_program import (
    SCALAR_PROCEDURE_KERNEL,
    SCALAR_REGIONAL_KERNEL,
    SCALAR_REGIONAL_STATE_SCHEMA,
    CompiledFieldProgram,
    regional_scalar_state,
)
from cassi_field_regions import RegionalProfile
from programs.model import ngram_learning as _ngram_learning
import cassi_field_regions as _regions
from cassi_field_residency import ResidencyManager, ResourceWait
from cassi_regional_catalog import STANDARD_KERNEL_CATALOG

SCHEMA = "cassifi.learning-computer.v3"
RESIDENCY_REPORT_SCHEMA = "cassifi.learning-computer-residency.v1"
RESIDENCY_WAIT_SCHEMA = "cassifi.learning-computer-residency-wait.v1"
PREVIOUS_SCHEMA = "cassifi.learning-computer.v2"
LEGACY_SCHEMA = "cassifi.learning-computer.v1"
_TASK_WORDS = 98_304
_OUTCOME_WORDS = 98_304
_RESULT_WORDS = 98_304
_POLICY_WORDS = 24_576
_SESSION_WORDS = 16_384
_CONFIG_WORDS = 1_024
_ARGUMENT_WORDS = 16_384
_FRAME_WORDS = _TASK_WORDS
INVOCATION_FRAMES_SCHEMA = "cassifi.learning-computer-invocation-frames.v2"
PREVIOUS_INVOCATION_FRAMES_SCHEMA = "cassifi.learning-computer-invocation-frames.v1"
CHILD_RETURN_SCHEMA = "cassifi.learning-computer-child-return.v2"
PREVIOUS_CHILD_RETURN_SCHEMA = "cassifi.learning-computer-child-return.v1"
REHEARSAL_SCHEMA = "cassifi.neural-membrane-rehearsal.v1"
ROOT_RESOURCE_NAMES = (
    "branch_count",
    "evidence_reads",
    "frontier_size",
    "model_calls",
    "refinement_depth",
    "storage_words",
    "work",
)

NGRAM_READOUT_FIELD_VALUE = "ngram_readout"
NGRAM_READOUT_MIGRATION_SCHEMA = "cassifi.qwen-ngram-readout-migration.v1"

class LearningComputerError(ValueError):
    """Invalid computer image or operation outside its declared bounds."""


class LearningComputerCapacityError(LearningComputerError):
    """A settled operation cannot fit its named regional allocation."""


class LearningComputerResidencyWait(LearningComputerError):
    """Bounded residency could not serve a request; the state is unchanged.

    This is a typed continuation, not a fault: the requesting stage, the exact
    page identities and versions, the declared segments under authority, the
    completed work, and the remaining allowance travel with it.  Raising the
    allowance resumes the same transition.
    """

    def __init__(
        self,
        computer_id: str,
        *,
        wait: Mapping[str, Any],
        continuation: Mapping[str, Any],
        resident_limit: int,
    ) -> None:
        self.computer_id = str(computer_id)
        self.wait = dict(wait)
        self.continuation = dict(continuation)
        self.resident_limit = int(resident_limit)
        self.pages = tuple(int(index) for index in self.continuation.get("pages", ()))
        super().__init__(
            f"computer {self.computer_id} suspended for pages "
            f"{list(self.pages)} under an allowance of {self.resident_limit}"
        )

    def as_dict(self) -> dict[str, Any]:
        """Canonical record of one suspended transition, for any caller.

        A caller that only needs to report or checkpoint the deferral gets the
        same shape a regional residency wait reports, so every class the field
        asks for room in can be recorded without special cases.
        """

        return {
            "schema": RESIDENCY_WAIT_SCHEMA,
            "kind": "learning-computer-residency-wait",
            "computer_id": self.computer_id,
            "pages": list(self.pages),
            "resident_limit": self.resident_limit,
            "wait": dict(self.wait),
            "continuation": dict(self.continuation),
        }

def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise LearningComputerError("computer value is not canonical JSON") from exc

def _resource_map(
    value: Mapping[str, Any],
    label: str,
    *,
    require_work: bool = False,
) -> dict[str, int]:
    if not isinstance(value, Mapping) or set(value) != set(ROOT_RESOURCE_NAMES):
        raise LearningComputerError(
            f"{label} must declare every root resource"
        )
    result: dict[str, int] = {}
    for name in ROOT_RESOURCE_NAMES:
        raw = value[name]
        if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
            raise LearningComputerError(
                f"{label} {name} must be a nonnegative integer"
            )
        result[name] = raw
    if require_work and result["work"] < 1:
        raise LearningComputerError(f"{label} work must be positive")
    return result


def _zero_resources() -> dict[str, int]:
    return {name: 0 for name in ROOT_RESOURCE_NAMES}


def _program_and_entries() -> tuple[tuple[dict[str, Any], ...], dict[str, int]]:
    rows: list[dict[str, Any]] = []
    entries: dict[str, int] = {}
    copy_rows: dict[str, int] = {}
    for kernel in STANDARD_KERNEL_CATALOG.names:
        entries[kernel] = len(rows)
        rows.append(
            {
                "op": "NATIVE",
                "kernel": kernel,
                "state": "task",
                "arguments": "arguments",
                "output": "outcome",
                "next": len(rows) + 1,
            }
        )
        copy_rows[kernel] = len(rows)
        rows.append(
            {
                "op": "COPY",
                "source": "outcome",
                "target": "result",
                "next": len(rows) + 1,
            }
        )
        rows.append({"op": "HALT"})
    rows[entries[SCALAR_REGIONAL_KERNEL]]["next"] = entries[
        SCALAR_PROCEDURE_KERNEL
    ]
    rows[entries[SCALAR_PROCEDURE_KERNEL]]["next"] = copy_rows[
        SCALAR_PROCEDURE_KERNEL
    ]
    for receiver_name in (
        "communication_receiver_a",
        "communication_receiver_b",
    ):
        receive_pc = len(rows)
        rows.append(
            {
                "op": "RECEIVE",
                "target": receiver_name,
                "next": receive_pc + 1,
            }
        )
        rows.append({"op": "HALT"})
    return tuple(rows), entries


_PROGRAM, _ENTRIES = _program_and_entries()


def _regional_profile(
    value: Mapping[str, Any] | None,
    *,
    max_field_bytes: int | None = None,
) -> tuple[RegionalProfile, ComputerProfile]:
    raw = dict(value or {})
    legacy_keys = {"program_capacity", "stack_capacity", "max_steps"}
    if set(raw).issubset(legacy_keys):
        try:
            scalar = ComputerProfile(**raw)
            if (
                max_field_bytes is None
                or max_field_bytes >= 65_536 * 9 * 8
            ):
                mode_count = 65_536
            else:
                if (
                    isinstance(max_field_bytes, bool)
                    or not isinstance(max_field_bytes, int)
                    or max_field_bytes < 1
                ):
                    raise LearningComputerError(
                        "max_field_bytes must be positive"
                    )
                mode_count = max(
                    2_000,
                    scalar.program_capacity,
                    scalar.stack_capacity,
                )
                if mode_count * 9 * 8 > max_field_bytes:
                    raise LearningComputerError(
                        "scalar profile exceeds max_field_bytes"
                    )
            small = mode_count < 65_536
            return (
                RegionalProfile(
                    mode_count=mode_count,
                    directory_capacity=64 if small else 256,
                    max_steps=max(1_000_000, scalar.max_steps),
                    max_events=16 if small else 256,
                    max_registry_entries=128 if small else 4096,
                    automaton_sites=8 if small else 64,
                    registry_words=1_024 if small else 24_576,
                    queue_words=256 if small else 16_384,
                    program_words=1_024 if small else 16_384,
                    ledger_words=128 if small else 2_048,
                    default_value_words=128 if small else 4_096,
                    reclaim_quantum=64 if small else 1_024,
                    max_native_work=32,
                    kernel_names=STANDARD_KERNEL_CATALOG.names,
                ),
                scalar,
            )
        except (TypeError, ValueError) as exc:
            raise LearningComputerError("invalid scalar profile") from exc
    raw.setdefault("mode_count", 65_536)
    raw.setdefault("directory_capacity", 256)
    raw.setdefault("max_native_work", 32)
    raw.setdefault("kernel_names", STANDARD_KERNEL_CATALOG.names)
    if tuple(raw["kernel_names"]) != STANDARD_KERNEL_CATALOG.names:
        raise LearningComputerError("regional profile kernel catalog is fixed")
    raw["kernel_names"] = tuple(raw["kernel_names"])
    try:
        regional = RegionalProfile(**raw)
        if (
            max_field_bytes is not None
            and regional.state_bytes > max_field_bytes
        ):
            raise LearningComputerError(
                "regional profile exceeds max_field_bytes"
            )
        scalar = ComputerProfile(max_steps=regional.max_steps)
    except (TypeError, ValueError) as exc:
        raise LearningComputerError("invalid regional profile") from exc
    return regional, scalar


def _regional_capacities(
    regional: RegionalProfile,
    values: Mapping[str, Any],
    *,
    max_field_bytes: int | None = None,
) -> dict[str, int]:
    """Plan named value regions from the resolved field workspace.

    The 65,536-mode image is the historical compatibility point.  Its
    capacities are intentionally kept as literals because changing any of
    them changes the initial field image digest.  Larger images receive the
    same resource mix at the field's actual word scale instead of falling
    through to the compact bootstrap allocation.
    """

    policy_words = (len(_canonical(values["policy"])) + 7) // 4
    if regional.mode_count < 65_536:
        capacities = {
            "arguments": 256,
            "config": 128,
            "outcome": 512,
            "result": 512,
            "policy": max(10_240, policy_words),
            "session": 256,
            "frames": 512,
            "task": 512,
        }
    elif regional.mode_count == 65_536:
        capacities = {
            "arguments": _ARGUMENT_WORDS,
            "config": _CONFIG_WORDS,
            "outcome": _OUTCOME_WORDS,
            "result": _RESULT_WORDS,
            "policy": _POLICY_WORDS,
            "session": _SESSION_WORDS,
            "frames": _FRAME_WORDS,
            "task": _TASK_WORDS,
        }
    else:
        reference_words = 65_536 * 9
        workspace_words = regional.total_words
        if max_field_bytes is not None:
            if (
                isinstance(max_field_bytes, bool)
                or not isinstance(max_field_bytes, int)
                or max_field_bytes < 1
            ):
                raise LearningComputerError("max_field_bytes must be positive")
            workspace_words = min(workspace_words, max_field_bytes // 8)

        def scaled(base: int) -> int:
            return max(
                base,
                (base * workspace_words + reference_words - 1)
                // reference_words,
            )

        capacities = {
            "arguments": scaled(_ARGUMENT_WORDS),
            "config": scaled(_CONFIG_WORDS),
            "outcome": scaled(_OUTCOME_WORDS),
            "result": scaled(_RESULT_WORDS),
            "policy": max(scaled(_POLICY_WORDS), policy_words),
            "session": scaled(_SESSION_WORDS),
            "frames": scaled(_FRAME_WORDS),
            "task": scaled(_TASK_WORDS),
        }
    if max_field_bytes is None:
        workspace_words = regional.total_words
    else:
        workspace_words = min(regional.total_words, max_field_bytes // 8)
    arena_start = 64 + 16 * regional.directory_capacity
    bootstrap_words = (
        regional.registry_words
        + regional.queue_words
        + regional.program_words
        + regional.ledger_words
        + (4 * regional.automaton_sites + 8)
        + regional.default_value_words
    )
    available_words = (
        workspace_words - arena_start - bootstrap_words - sum(capacities.values())
    )
    # The RECEIVE targets scale down with the declared workspace so small
    # images keep configuring; the historical image keeps the full default.
    receiver_words = min(regional.default_value_words, available_words // 2)
    if (
        workspace_words < arena_start + bootstrap_words
        or available_words < 0
        or receiver_words < 1
    ):
        raise LearningComputerError(
            "regional image does not fit the declared workspace"
        )
    capacities["communication_receiver_a"] = receiver_words
    capacities["communication_receiver_b"] = receiver_words
    return capacities


class NeuralMembraneEpoch:
    """One private field-plane epoch across ordered activation exchanges."""

    _DECAY = np.float32(15.0 / 16.0)
    _INJECTION = np.float32(1.0 / 16.0)

    def __init__(
        self,
        predecessor: "LearningComputer",
        computer: "LearningComputer",
        *,
        mode_count: int,
        epoch: Mapping[str, Any],
        migration: Mapping[str, Any] | None,
    ) -> None:
        if not isinstance(epoch, Mapping):
            raise LearningComputerError("neural membrane epoch must be an object")
        self.predecessor = predecessor
        self.computer = computer
        self.profile = computer.profile
        if not self.profile.neural_membrane:
            raise LearningComputerError("neural membrane epoch requires reserved planes")
        if (
            isinstance(mode_count, bool)
            or not isinstance(mode_count, int)
            or mode_count < 1
            or mode_count > self.profile.mode_count
        ):
            raise LearningComputerError(
                "neural membrane active mode count is outside its reserved field"
            )
        self._mode_count = mode_count
        self.epoch = json.loads(_canonical(dict(epoch)).decode("utf-8"))
        self.epoch_sha256 = hashlib.sha256(_canonical(self.epoch)).hexdigest()
        self.migration = None if migration is None else dict(migration)
        start = self.profile.neural_membrane_offset
        if computer.is_paged:
            view = computer.field.image.view()
            words = np.stack(
                [
                    np.asarray(
                        view[
                            start + plane * self.profile.mode_count:
                            start + plane * self.profile.mode_count + mode_count
                        ],
                        dtype=np.float64,
                    )
                    for plane in range(
                        _regions.NEURAL_MEMBRANE_PLANE_COUNT
                    )
                ]
            )
        else:
            field = computer.field._field.reshape(
                9,
                self.profile.mode_count,
            )
            words = field[
                _regions.NEURAL_MEMBRANE_FIRST_PLANE:,
                :mode_count,
            ]
        encoded = np.asarray(words, dtype="<u4")
        self._initial_words = encoded.astype(np.float64)
        self._planes = encoded.view("<f4").copy()
        if not np.isfinite(self._planes).all():
            raise LearningComputerError("neural membrane contains nonfinite activity")
        self._sites: list[dict[str, Any]] = []
        self._site_count = 0
        self._stage_records: list[dict[str, Any]] = []
        self._recorded_site_count = 0
        self._device_session = None
        self._finished = False
        self._ngram_state: Mapping[str, Any] | None = None
        self._ngram_table_vector: np.ndarray | None = None
        self._ngram_applications: list[dict[str, Any]] = []
        self._ngram_output_hash_by_site: dict[int, str] = {}
        self._ngram_pre_head: np.ndarray | None = None
        self._ngram_post_head: np.ndarray | None = None

    @property
    def mode_count(self) -> int:
        return self._mode_count

    def configure_ngram_readout(
        self,
        state: Mapping[str, Any],
        table_vector: np.ndarray,
    ) -> None:
        """Pin one field-owned readout and table vector for this token epoch."""
        if self._finished or self._site_count or self._ngram_state is not None:
            raise LearningComputerError(
                "n-gram readout must be configured once before neural exchanges"
            )
        try:
            canonical = _ngram_learning.validate_state(state)
            owned = self.computer.ngram_readout_state()
        except (TypeError, ValueError) as exc:
            raise LearningComputerError(
                f"canonical n-gram readout state is unavailable: {exc}"
            ) from exc
        if _canonical(canonical) != _canonical(owned):
            raise LearningComputerError(
                "configured n-gram readout differs from the canonical field state"
            )
        try:
            raw = np.asarray(table_vector)
        except (TypeError, ValueError) as exc:
            raise LearningComputerError("n-gram table vector is invalid") from exc
        if (
            raw.ndim != 1
            or raw.size != _ngram_learning.TABLE_VECTOR_SIZE
            or raw.dtype.kind not in "fiu"
        ):
            raise LearningComputerError(
                "n-gram table vector must be a numeric 2560-value row"
            )
        pinned = np.array(raw, dtype=np.float32, copy=True)
        if not np.isfinite(pinned).all():
            raise LearningComputerError(
                "n-gram table vector contains nonfinite values"
            )
        pinned.setflags(write=False)
        self._ngram_state = canonical
        self._ngram_table_vector = pinned

    @property
    def ngram_head_vectors(self) -> Mapping[str, np.ndarray] | None:
        """Return ephemeral pre/post head vectors for owner-side scoring."""
        if self._ngram_pre_head is None or self._ngram_post_head is None:
            return None
        return {
            "pre_head": self._ngram_pre_head.copy(),
            "post_head": self._ngram_post_head.copy(),
        }

    def bind_device(self, bank: Any) -> Any:
        """Keep one candidate field resident beside Vulkan weights for this token."""
        if self._finished:
            raise LearningComputerError("neural membrane epoch is already finished")
        if self._device_session is None:
            if self._site_count:
                raise LearningComputerError("cannot move a started neural epoch to a device")
            self._device_session = bank.device_epoch(
                self._planes,
                gain_ppm=self.profile.neural_membrane_gain_ppm,
            )
        return self._device_session

    def fork_preview(self) -> "_NeuralMembranePreview":
        """Fork the exact current plane state without finishing this epoch."""
        if self._finished:
            raise LearningComputerError("neural membrane epoch is already finished")
        device_session = None
        try:
            if self._device_session is not None:
                device_session = self._device_session.fork_preview()
            preview = object.__new__(NeuralMembraneEpoch)
            preview.profile = self.profile
            preview._mode_count = self._mode_count
            preview._planes = self._planes.copy()
            preview._site_count = self._site_count
            preview._sites = [dict(row) for row in self._sites]
            preview._finished = False
            preview._device_session = device_session
            preview._ngram_state = (
                None
                if self._ngram_state is None
                else json.loads(
                    _canonical(dict(self._ngram_state)).decode("utf-8")
                )
            )
            preview._ngram_table_vector = (
                None
                if self._ngram_table_vector is None
                else self._ngram_table_vector.copy()
            )
            preview._ngram_applications = [
                dict(row) for row in self._ngram_applications
            ]
            preview._ngram_output_hash_by_site = dict(
                self._ngram_output_hash_by_site
            )
            preview._ngram_pre_head = (
                None if self._ngram_pre_head is None else self._ngram_pre_head.copy()
            )
            preview._ngram_post_head = (
                None if self._ngram_post_head is None else self._ngram_post_head.copy()
            )
            return _NeuralMembranePreview(preview)
        except Exception as exc:
            if device_session is not None:
                try:
                    device_session.close()
                except Exception:
                    pass
            if isinstance(exc, LearningComputerError):
                raise
            raise LearningComputerError(
                f"cannot obtain an exact neural membrane preview: {exc}"
            ) from exc

    def device_exchange(self, site: str, activation: Any) -> Any:
        """Exchange an opaque Vulkan activation without host materialization."""
        if self._finished or self._device_session is None:
            raise LearningComputerError("neural membrane device epoch is unavailable")
        if (
            not isinstance(site, str)
            or not site
            or len(site.encode("utf-8")) > 512
            or any(ord(character) < 32 for character in site)
        ):
            raise LearningComputerError("neural membrane site must be bounded text")
        site_index = self._site_count
        output = self._device_session.exchange(site, activation)
        if site == "head.input" and self._ngram_state is not None:
            ordinary = self._device_session.download(output)
            steered = self._apply_ngram_readout(
                ordinary, site_index=site_index
            )
            delta = (steered - ordinary).astype(np.float32, copy=False)
            output = self._device_session.add(
                output, self._device_session.upload(delta)
            )
        self._site_count += 1
        return output

    def _record_device_sites(self) -> None:
        if self._device_session is None:
            return
        for row in self._device_session.drain_sites():
            site = row["site"]
            source = row["input"]
            output = row["output"]
            delta = row["delta"]
            site_index = len(self._sites)
            recorded_output_sha256 = self._array_sha256(output)
            if site_index in self._ngram_output_hash_by_site:
                recorded_output_sha256 = self._ngram_output_hash_by_site[
                    site_index
                ]
            chunk_count = (source.size + self.mode_count - 1) // self.mode_count
            offsets = [
                int(hashlib.sha256(f"{site}\0{index}".encode("utf-8")).hexdigest()[:16], 16)
                % self.mode_count
                for index in range(chunk_count)
            ]
            self._sites.append({
                "site": site,
                "site_sha256": hashlib.sha256(site.encode("utf-8")).hexdigest(),
                "width": int(source.size),
                "chunk_count": chunk_count,
                "mode_offset": offsets[0],
                "mode_offsets": offsets,
                "input_sha256": self._array_sha256(source),
                "output_sha256": recorded_output_sha256,
                "input_rms": float(np.sqrt(np.mean(np.square(source, dtype=np.float64)))),
                "device_scale_f32": row["scale"],
                "maximum_absolute_delta": float(np.max(np.abs(delta), initial=np.float32(0))),
                "nonzero_delta": int(np.count_nonzero(delta)),
            })
        if len(self._sites) != self._site_count:
            raise LearningComputerError("Vulkan site captures do not cover ordered exchanges")

    @staticmethod
    def _array_sha256(value: np.ndarray) -> str:
        # Hash the contiguous little-endian float32 buffer in place; the
        # digest equals the one over its ``tobytes`` copy.
        return hashlib.sha256(
            np.ascontiguousarray(value, dtype="<f4").reshape(-1).view(np.uint8)
        ).hexdigest()

    def _apply_ngram_readout(
        self,
        hidden: np.ndarray,
        *,
        site_index: int,
    ) -> np.ndarray:
        if self._ngram_state is None or self._ngram_table_vector is None:
            return hidden
        source = np.asarray(hidden, dtype=np.float32).reshape(-1)
        delta = _ngram_learning.readout(
            self._ngram_state, self._ngram_table_vector, source
        )
        output = (source + delta).astype(np.float32, copy=False)
        if not np.isfinite(output).all():
            raise LearningComputerError(
                "n-gram readout produced a nonfinite head activation"
            )
        delta_norm = float(np.linalg.norm(delta.astype(np.float64)))
        if delta_norm > 0.250001:
            raise LearningComputerError(
                "n-gram readout exceeded its bounded intervention"
            )
        record = {
            "site_index": site_index,
            "applied_site": "head.input",
            "model_id": self._ngram_state["model_id"],
            "table_id": self._ngram_state["table_id"],
            "coefficient_revision": self._ngram_state["revision"],
            "input_sha256": self._array_sha256(source),
            "output_sha256": self._array_sha256(output),
            "delta_sha256": self._array_sha256(delta),
            "delta_l2_norm": delta_norm,
            "delta_l2_bound": 0.25,
            "delta_linf": float(
                np.max(np.abs(delta), initial=np.float32(0.0))
            ),
        }
        self._ngram_applications.append(record)
        self._ngram_output_hash_by_site[site_index] = record["output_sha256"]
        self._ngram_pre_head = source.copy()
        self._ngram_post_head = output.copy()
        return output

    def _exchange_segment(
        self,
        source: np.ndarray,
        destination: slice,
        output: np.ndarray,
        *,
        scale: np.float32,
    ) -> np.ndarray:
        # Every step writes its float32 result straight into the plane rows;
        # each value equals the one from the expression form
        # ``DECAY * yang + INJECTION * max(drive, 0)`` and
        # ``gain * scale * (yang - yin)``.
        drive = self._planes[0, destination]
        yang = self._planes[1, destination]
        yin = self._planes[2, destination]
        delta = self._planes[3, destination]
        np.divide(source, scale, out=drive)
        np.tanh(drive, out=drive)
        injected = np.maximum(drive, np.float32(0.0))
        injected *= self._INJECTION
        yang *= self._DECAY
        yang += injected
        np.negative(drive, out=injected)
        np.maximum(injected, np.float32(0.0), out=injected)
        injected *= self._INJECTION
        yin *= self._DECAY
        yin += injected
        gain = np.float32(self.profile.neural_membrane_gain_ppm / 1_000_000.0)
        np.subtract(yang, yin, out=delta)
        delta *= gain * scale
        if self.profile.neural_membrane_gain_ppm == 0:
            output[...] = source
        else:
            np.add(source, delta, out=output)
        return delta

    def exchange(self, site: str, activation: np.ndarray) -> np.ndarray:
        """Let one complete activation vector write and read the field."""

        if self._finished:
            raise LearningComputerError("neural membrane epoch is already finished")
        if (
            not isinstance(site, str)
            or not site
            or len(site.encode("utf-8")) > 512
            or any(ord(character) < 32 for character in site)
        ):
            raise LearningComputerError("neural membrane site must be bounded text")
        original_shape = np.asarray(activation).shape
        source = np.asarray(activation, dtype=np.float32).reshape(-1)
        if source.size < 1:
            raise LearningComputerError("neural activation must not be empty")
        if not np.isfinite(source).all():
            raise LearningComputerError("neural activation contains nonfinite values")
        source = source.astype(np.float32, copy=False)
        if self._device_session is not None:
            activation_on_device = self._device_session.upload(source)
            output_on_device = self.device_exchange(site, activation_on_device)
            return self._device_session.download(output_on_device).reshape(original_shape)
        rms = float(
            np.sqrt(np.mean(np.square(source, dtype=np.float64)))
        )
        scale = np.float32(max(rms, 1.0e-6))
        site_sha256 = hashlib.sha256(site.encode("utf-8")).hexdigest()
        output = np.empty_like(source)
        offsets: list[int] = []
        maximum_absolute_delta = 0.0
        nonzero_delta = 0
        chunk_count = (
            source.size + self.mode_count - 1
        ) // self.mode_count
        for chunk_index in range(chunk_count):
            start = chunk_index * self.mode_count
            stop = min(source.size, start + self.mode_count)
            chunk = source[start:stop]
            chunk_sha256 = hashlib.sha256(
                f"{site}\0{chunk_index}".encode("utf-8")
            ).hexdigest()
            offset = int(chunk_sha256[:16], 16) % self.mode_count
            offsets.append(offset)
            first = min(chunk.size, self.mode_count - offset)
            delta_first = self._exchange_segment(
                chunk[:first],
                slice(offset, offset + first),
                output[start:start + first],
                scale=scale,
            )
            maximum_absolute_delta = max(
                maximum_absolute_delta,
                float(
                    np.max(
                        np.abs(delta_first),
                        initial=np.float32(0.0),
                    )
                ),
            )
            nonzero_delta += int(np.count_nonzero(delta_first))
            if first < chunk.size:
                delta_second = self._exchange_segment(
                    chunk[first:],
                    slice(0, chunk.size - first),
                    output[start + first:stop],
                    scale=scale,
                )
                maximum_absolute_delta = max(
                    maximum_absolute_delta,
                    float(
                        np.max(
                            np.abs(delta_second),
                            initial=np.float32(0.0),
                        )
                    ),
                )
                nonzero_delta += int(np.count_nonzero(delta_second))
        if site == "head.input" and self._ngram_state is not None:
            output = self._apply_ngram_readout(
                output, site_index=self._site_count
            )
        self._sites.append(
            {
                "site": site,
                "site_sha256": site_sha256,
                "width": int(source.size),
                "chunk_count": chunk_count,
                "mode_offset": offsets[0],
                "mode_offsets": offsets,
                "input_sha256": self._array_sha256(source),
                "output_sha256": self._array_sha256(output),
                "input_rms": rms,
                "maximum_absolute_delta": maximum_absolute_delta,
                "nonzero_delta": nonzero_delta,
            }
        )
        self._site_count += 1
        return output.reshape(original_shape)

    def rehearse_alternatives(
        self,
        trials: Sequence[Mapping[str, Any]],
        *,
        limit: int = 4,
    ) -> list[dict[str, Any]]:
        """Rehearse bounded alternative outcomes on a forked preview only.

        Every trial runs through a detached fork of the current planes and
        the fork is closed afterwards, so hypothetical outcomes never reach
        this epoch: its site list, site count and stage records are asserted
        unchanged before any row is returned.
        """
        bounded = list(trials)[: max(0, min(int(limit), 4))]
        if not bounded:
            return []
        sites_before = [dict(row) for row in self._sites]
        site_count_before = self._site_count
        recorded_before = self._recorded_site_count
        records_before = len(self._stage_records)
        rows: list[dict[str, Any]] = []
        preview = self.fork_preview()
        try:
            for trial in bounded:
                if not isinstance(trial, Mapping):
                    raise LearningComputerError(
                        "neural membrane rehearsal trial must be an object"
                    )
                site = trial.get("site")
                source = np.asarray(
                    trial.get("activation"), dtype=np.float32
                ).reshape(-1)
                output = np.asarray(
                    preview.exchange(site, source), dtype=np.float32
                ).reshape(-1)
                rows.append(
                    {
                        "schema": REHEARSAL_SCHEMA,
                        "status": "hypothetical",
                        "site": site,
                        **{
                            key: trial[key]
                            for key in (
                                "method_key",
                                "method_generation",
                                "specialist",
                            )
                            if key in trial
                        },
                        "width": int(source.size),
                        "input_sha256": self._array_sha256(source),
                        "output_sha256": self._array_sha256(output),
                        "input_rms": float(
                            np.sqrt(np.mean(np.square(source, dtype=np.float64)))
                        ),
                        "output_rms": float(
                            np.sqrt(np.mean(np.square(output, dtype=np.float64)))
                        ),
                        "maximum_absolute_delta": float(
                            np.max(
                                np.abs(output - source),
                                initial=np.float32(0.0),
                            )
                        ),
                    }
                )
        finally:
            preview.close_preview()
        if (
            len(self._sites) != len(sites_before)
            or self._sites != sites_before
            or self._site_count != site_count_before
            or self._recorded_site_count != recorded_before
            or len(self._stage_records) != records_before
        ):
            raise LearningComputerError(
                "neural membrane rehearsal altered the epoch it rehearsed"
            )
        return rows

    def record_stage(
        self,
        *,
        epoch: Mapping[str, Any],
        stage_result_sha256: str,
    ) -> None:
        """Bind one task stage to the ordered site range in this open epoch."""

        if self._finished:
            raise LearningComputerError("neural membrane epoch is already finished")
        if not isinstance(epoch, Mapping):
            raise LearningComputerError("neural membrane stage epoch must be an object")
        if (
            not isinstance(stage_result_sha256, str)
            or len(stage_result_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in stage_result_sha256
            )
        ):
            raise LearningComputerError("stage result digest is invalid")
        self._record_device_sites()
        if self._device_session is not None:
            self._device_session.discard_stage_tensors()
        normalized_epoch = json.loads(
            _canonical(dict(epoch)).decode("utf-8")
        )
        self._stage_records.append(
            {
                "epoch": normalized_epoch,
                "epoch_sha256": hashlib.sha256(
                    _canonical(normalized_epoch)
                ).hexdigest(),
                "stage_result_sha256": stage_result_sha256,
                "site_start": self._recorded_site_count,
                "site_stop": self._site_count,
            }
        )
        self.epoch = normalized_epoch
        self.epoch_sha256 = self._stage_records[-1]["epoch_sha256"]
        self._recorded_site_count = self._site_count

    def stage_receipts(
        self,
        final_receipt: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        """Materialize per-stage exchange bindings from the final ordered trace."""

        if not self._finished or not self._stage_records:
            raise LearningComputerError(
                "neural membrane stage receipts require a finished token epoch"
            )
        sites = final_receipt.get("sites")
        if (
            not isinstance(sites, list)
            or len(sites) != self._site_count
            or final_receipt.get("site_count") != self._site_count
        ):
            raise LearningComputerError(
                "neural membrane final site trace does not match its stage ranges"
            )
        result: list[dict[str, Any]] = []
        stage_count = len(self._stage_records)
        for stage_index, record in enumerate(self._stage_records):
            start = int(record["site_start"])
            stop = int(record["site_stop"])
            stage_sites = [
                dict(site) for site in sites[start:stop]
            ]
            stage_receipt = {
                "schema": "cassifi.neural-membrane-stage-exchange.v1",
                "kind": "neural-membrane-stage-exchange",
                "computer_id": final_receipt["computer_id"],
                "epoch": dict(record["epoch"]),
                "epoch_sha256": record["epoch_sha256"],
                "model_source_sha256": record["epoch"].get(
                    "model_source_sha256"
                ),
                "stage_result_sha256": record["stage_result_sha256"],
                "profile_sha256": final_receipt["profile_sha256"],
                "mode_count": final_receipt["mode_count"],
                "gain_ppm": final_receipt["gain_ppm"],
                "stage_index": stage_index,
                "stage_count": stage_count,
                "site_range": {"start": start, "stop": stop},
                "site_count": len(stage_sites),
                "site_trace_sha256": hashlib.sha256(
                    _canonical(stage_sites)
                ).hexdigest(),
                "sites": stage_sites,
            }
            if stage_index == stage_count - 1:
                stage_receipt = dict(final_receipt)
                stage_receipt.update(
                    {
                        "stage_index": stage_index,
                        "stage_count": stage_count,
                        "stage_site_range": {
                            "start": start,
                            "stop": stop,
                        },
                    }
                )

            result.append(stage_receipt)
        return result

    def _close_device_session(self) -> None:
        session = self._device_session
        if session is None:
            return
        close = getattr(session, "close", None)
        if not callable(close):
            raise LearningComputerError(
                "neural membrane device session cannot be closed"
            )
        close()
        self._device_session = None

    def abort(self) -> None:
        """Discard an uncommitted membrane candidate and its device session."""

        try:
            self._close_device_session()
        finally:
            if not self._finished:
                self._finished = True
                self._planes = np.empty((0, 0), dtype=np.float32)
                self._sites.clear()
                self._stage_records.clear()
                self._site_count = 0
                self._recorded_site_count = 0


    def _finish_paged(
        self,
        encoded: np.ndarray,
        computer: "LearningComputer",
    ) -> tuple[PagedComputerState, Mapping[str, Any]]:
        image = computer.field.image
        staging = image.stage(stage="neural-membrane")
        base = self.profile.neural_membrane_offset
        page_words = _regions.PERSISTENCE_PAGE_WORDS
        for plane in range(_regions.NEURAL_MEMBRANE_PLANE_COUNT):
            source = encoded[plane]
            start = base + plane * self.profile.mode_count
            stop = start + self.mode_count
            changed = np.flatnonzero(
                source != self._initial_words[plane]
            )
            page_indices = np.unique((start + changed) // page_words)
            for page_index in page_indices:
                page_index = int(page_index)
                page_start = page_index * page_words
                write_start = max(start, page_start)
                write_stop = min(stop, page_start + page_words)
                page = staging.stage_page(page_index)
                page[
                    write_start - page_start:write_stop - page_start
                ] = source[write_start - start:write_stop - start]
        successor, storage = staging.commit(
            blocks={
                "schema": _regions.NEURAL_MEMBRANE_SCHEMA,
                "epoch_sha256": self.epoch_sha256,
            }
        )
        return (
            PagedComputerState(successor, self.profile.fingerprint),
            storage,
        )

    def finish(
        self,
        *,
        stage_result_sha256: str,
        computer: "LearningComputer | None" = None,
    ) -> tuple["LearningComputer", Mapping[str, Any]]:
        """Freeze candidate planes into the latest private computer successor."""

        if self._finished:
            raise LearningComputerError("neural membrane epoch is already finished")
        if (
            not isinstance(stage_result_sha256, str)
            or len(stage_result_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in stage_result_sha256
            )
        ):
            raise LearningComputerError("stage result digest is invalid")
        self._record_device_sites()
        if self._stage_records and (
            self._recorded_site_count != self._site_count
            or self._stage_records[-1]["stage_result_sha256"]
            != stage_result_sha256
        ):
            raise LearningComputerError(
                "neural membrane token stage trace is incomplete"
            )
        target_computer = self.computer if computer is None else computer
        if (
            not isinstance(target_computer, LearningComputer)
            or target_computer.computer_id != self.computer.computer_id
            or target_computer.profile.fingerprint != self.profile.fingerprint
            or target_computer.is_paged != self.computer.is_paged
        ):
            raise LearningComputerError(
                "neural membrane successor does not match its epoch computer"
            )
        if self._ngram_state is not None and not self._ngram_applications:
            raise LearningComputerError(
                "configured n-gram readout did not reach head.input"
            )
        if self._device_session is not None:
            self._planes = self._device_session.finish()
        self._finished = True
        encoded = self._planes.astype("<f4", copy=False).view("<u4").astype(
            np.float64
        )
        changed_words = int(np.count_nonzero(encoded != self._initial_words))
        storage: Mapping[str, Any] | None = None
        if target_computer.is_paged:
            state, storage = self._finish_paged(encoded, target_computer)
        else:
            field = np.array(target_computer.field._field, copy=True)
            field.reshape(9, self.profile.mode_count)[
                _regions.NEURAL_MEMBRANE_FIRST_PLANE:,
                :self.mode_count,
            ] = encoded
            state = ComputerState(field, self.profile.fingerprint)
        successor = replace(target_computer, field=state)
        site_trace_sha256 = hashlib.sha256(_canonical(self._sites)).hexdigest()
        receipt = {
            "schema": _regions.NEURAL_MEMBRANE_SCHEMA,
            "kind": "neural-membrane-epoch",
            "computer_id": target_computer.computer_id,
            "epoch": dict(self.epoch),
            "epoch_sha256": self.epoch_sha256,
            "model_source_sha256": self.epoch.get("model_source_sha256"),
            "stage_result_sha256": stage_result_sha256,
            "predecessor_state_sha256": self.predecessor.state_sha256,
            "state_sha256": successor.state_sha256,
            "predecessor_profile_sha256": self.predecessor.profile.fingerprint,
            "profile_sha256": self.profile.fingerprint,
            "mode_count": self.mode_count,
            "gain_ppm": self.profile.neural_membrane_gain_ppm,
            "site_count": self._site_count,
            "site_trace_sha256": site_trace_sha256,
            "sites": [dict(row) for row in self._sites],
            "changed_words": changed_words,
            "migration": self.migration,
            "storage": None if storage is None else dict(storage),
            **(
                {
                    "ngram_readout": {
                        "schema": "cassifi.qwen-ngram-readout-application.v1",
                        "model_id": self._ngram_state["model_id"],
                        "table_id": self._ngram_state["table_id"],
                        "coefficient_revision": self._ngram_state["revision"],
                        "applied_site": "head.input",
                        "application_count": len(self._ngram_applications),
                        "applications": [
                            dict(row) for row in self._ngram_applications
                        ],
                    }
                }
                if self._ngram_state is not None
                else {}
            ),
        }
        self._close_device_session()
        return successor, receipt



class _NeuralMembranePreview:
    """Exchange-only view of a detached neural epoch; it can never publish."""

    __slots__ = ("__epoch", "__closed")

    def __init__(self, epoch: NeuralMembraneEpoch) -> None:
        self.__epoch = epoch
        self.__closed = False

    def exchange(self, site: str, activation: Any) -> np.ndarray:
        if self.__closed:
            raise LearningComputerError("neural membrane preview is closed")
        return self.__epoch.exchange(site, activation)

    def close_preview(self) -> None:
        if self.__closed:
            return
        self.__closed = True
        epoch = self.__epoch
        epoch._finished = True
        device_session = epoch._device_session
        epoch._device_session = None
        try:
            if device_session is not None:
                device_session.close()
        finally:
            epoch._planes = np.empty((4, 0), dtype=np.float32)
            epoch._sites.clear()
            epoch._ngram_state = None
            epoch._ngram_table_vector = None
            epoch._ngram_applications.clear()
            epoch._ngram_output_hash_by_site.clear()
            epoch._ngram_pre_head = None
            epoch._ngram_post_head = None

    def __del__(self) -> None:  # pragma: no cover - interpreter shutdown path
        try:
            self.close_preview()
        except Exception:
            pass


@dataclass(frozen=True, slots=True)
class LearningComputer:
    """Task-oriented view of one authoritative regional field image."""

    computer_id: str
    profile: RegionalProfile
    field: ComputerState | PagedComputerState
    _legacy_field_descriptor: Mapping[str, Any] | None = dataclass_field(
        default=None,
        init=False,
        repr=False,
        compare=False,
    )
    _machine: FieldComputer = dataclass_field(
        init=False,
        repr=False,
        compare=False,
    )
    # Dense images are immutable bytes, so their chunk pages are computed once
    # per computer; each owner publication otherwise re-chunked, recompressed
    # and rehashed every unchanged computer.
    _dense_persistence: tuple[Mapping[str, Any], Mapping[str, bytes]] | None = dataclass_field(
        default=None,
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        if (
            not isinstance(self.computer_id, str)
            or not self.computer_id
            or len(self.computer_id) > 256
        ):
            raise LearningComputerError(
                "computer_id must be a nonempty bounded string"
            )
        if not isinstance(self.profile, RegionalProfile):
            raise LearningComputerError("regional profile required")
        machine = FieldComputer.regional(
            self.profile, catalog=STANDARD_KERNEL_CATALOG
        )
        object.__setattr__(self, "_machine", machine)
        try:
            self.validate()
        except _regions.ResidencyWait as wait:
            image = self.field.image
            raise LearningComputerResidencyWait(
                self.computer_id,
                wait=wait.as_dict(),
                continuation=_regions.residency_continuation(
                    wait, root_sha256=image.root_sha256
                ),
                resident_limit=image.resident_limit,
            ) from wait
        except ResourceWait:
            # Physical room, not a corrupt image: validating the successor state
            # reads its pages, and a read that cannot reserve reports a wait.
            # The callers above are wait-aware, so it must reach them instead of
            # being read as an invalid image (ResourceWait is a ValueError, so
            # the shape conversion below would otherwise swallow it).
            raise
        except (TypeError, ValueError) as exc:
            raise LearningComputerError("invalid regional computer image") from exc

    def _controller(self) -> FieldComputer:
        return self._machine

    def validate(self) -> None:
        """Validate the retained state against the running kernel catalog."""

        if isinstance(self.field, PagedComputerState):
            self._machine.validate_paged(self.field)
        else:
            self._machine.validate(self.field)

    # -- bounded residency -------------------------------------------------
    #
    # A computer may hold its regional image under a page residency allowance
    # instead of a resident dense tensor.  The log, the program, the values,
    # and every transition are identical; only the storage placement changes,
    # so the dense and paged forms of the same task produce the same image.
    # A request that cannot be served inside the allowance suspends as
    # :class:`LearningComputerResidencyWait` with the state unchanged.

    @property
    def is_paged(self) -> bool:
        return isinstance(self.field, PagedComputerState)

    @property
    def resident_limit(self) -> int | None:
        if not self.is_paged:
            return None
        return self.field.image.resident_limit

    def residency(self) -> dict[str, Any]:
        """Bounded read-only residency identity of this computer."""

        if not self.is_paged:
            return {
                "schema": RESIDENCY_REPORT_SCHEMA,
                "paged": False,
                "computer_id": self.computer_id,
                "logical_bytes": self.nbytes,
                "resident_limit": None,
                "root_sha256": None,
                "page_count": None,
                "residency": None,
            }
        image = self.field.image
        return {
            "schema": RESIDENCY_REPORT_SCHEMA,
            "paged": True,
            "computer_id": self.computer_id,
            "logical_bytes": self.nbytes,
            "resident_limit": image.resident_limit,
            "root_sha256": image.root_sha256,
            "page_count": image.page_count,
            "residency": image.residency_report(),
        }

    def adopt_paged(
        self, *, resident_limit: int = _regions.DEFAULT_RESIDENT_PAGES,
        resource_limits: Mapping[str, Any] | None = None,
        objects: Mapping[str, bytes] | None = None,
    ) -> LearningComputer:
        """Adopt this exact image under a bounded page residency allowance."""

        if self.is_paged:
            return self
        state, _record = self._controller().paged_state(
            self.field, resident_limit=resident_limit,
            resource_limits=resource_limits, objects=objects,
        )
        return replace(self, field=state)

    def with_object_store(
        self, store: Mapping[str, bytes]
    ) -> LearningComputer:
        """A twin of this paged image backed by the given object store."""

        if not self.is_paged:
            raise LearningComputerError("computer does not use bounded residency")
        image = self.field.image.with_backing(store)
        if image is self.field.image:
            return self
        return replace(self, field=self._controller()._paged_state(image))

    def with_resident_limit(
        self, resident_limit: int, *,
        resource_limits: Mapping[str, Any] | None = None,
    ) -> LearningComputer:
        """A twin operating under a different page allowance, same root."""

        if not self.is_paged:
            raise LearningComputerError("computer does not use bounded residency")
        state = self._controller().resume_paged(
            self.field, resident_limit=resident_limit,
            resource_limits=resource_limits,
        )
        if state is self.field:
            return self
        return replace(self, field=state)
    def with_resource_manager(
        self,
        manager: ResidencyManager,
        *,
        program_id: str | None = None,
    ) -> "LearningComputer":
        if not self.is_paged:
            return self
        image = self.field.image.with_resource_manager(
            manager, program_id=program_id
        )
        return replace(self, field=self._controller()._paged_state(image))

    def _bind_page_tier_store(self, store: Any) -> None:
        """Bind durable page I/O to this paged image without changing its identity."""

        if not self.is_paged:
            raise LearningComputerError("computer does not use bounded residency")
        self.field.image._tier_store = store


    def place_pages(
        self,
        pages: Sequence[int],
        tier: str,
        *,
        root_sha256: str | None = None,
        max_pages: int = 16,
        continuation: Mapping[str, Any] | None = None,
        tier_store: Any | None = None,
    ) -> Mapping[str, Any]:
        """Move bounded logical pages between RAM, backing storage, and operator-classified NVMe/HDD tiers.

        Placement changes where the same committed pages live, never the
        logical image.  The bounded report carries the version binding and a
        resumable continuation for an interrupted move.
        """

        if not self.is_paged:
            raise LearningComputerError("computer does not use bounded residency")
        return self._controller().place_pages(
            self.field,
            pages,
            tier,
            root_sha256=root_sha256,
            max_pages=max_pages,
            continuation=continuation,
            tier_store=tier_store,
        )

    def resources(self) -> Mapping[str, Any] | None:
        """Measured physical reservations of this computer's paged backing."""

        if not self.is_paged:
            return None
        manager = getattr(self.field.image, "resource_manager", None)
        return None if manager is None else manager.report()

    def _residency_wait(
        self, wait: "_regions.ResidencyWait"
    ) -> LearningComputerResidencyWait:
        """The typed wait for one raw resource suspension of this computer."""

        image = self.field.image
        return LearningComputerResidencyWait(
            self.computer_id,
            wait=wait.as_dict(),
            continuation=_regions.residency_continuation(
                wait, root_sha256=image.root_sha256
            ),
            resident_limit=image.resident_limit,
        )

    def _bounded(self, operation: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Run one bounded paged host call, translating a resource wait."""

        try:
            return operation(*args, **kwargs)
        except _regions.ResidencyWait as wait:
            raise self._residency_wait(wait) from wait

    def _suspend(
        self, receipt: Mapping[str, Any], *, resident_limit: int | None = None
    ) -> None:
        """Raise the typed wait a paged phase reports, or return silently."""

        if receipt.get("kind") != "residency-wait":
            return
        raise LearningComputerResidencyWait(
            self.computer_id,
            wait=receipt["wait"],
            continuation=receipt["continuation"],
            resident_limit=(
                resident_limit
                if resident_limit is not None
                else int(receipt["wait"].get("allowance") or 0)
            ),
        )

    def _flat(self) -> Any:
        if self.is_paged:
            return self.field.image.view()
        return self.field._field.reshape(-1)

    def _state_sha256(self) -> str:
        if self.is_paged:
            return self._bounded(self.field.image.state_identity_sha256)
        return self._controller().state_sha256(self.field)

    def _descriptor(self) -> dict[str, Any]:
        if self.is_paged:
            return self._bounded(
                self._controller().descriptor_paged, self.field
            )
        return self._controller().descriptor(self.field)

    def _inspect(self) -> dict[str, Any]:
        if self.is_paged:
            return self._bounded(self._controller().inspect_paged, self.field)
        return self._controller().inspect(self.field)

    def _named_values(self, names: Any) -> Mapping[str, Any]:
        names = tuple(names)
        if self.is_paged:
            return self._bounded(_regions.named_values_paged, self.field.image, names)
        return self._controller().named_values(self.field, names)

    def _named_value(self, name: str) -> Any:
        return self._named_values((name,))[name]

    def _write_named_value(
        self, name: str, value: Any
    ) -> tuple[ComputerState | PagedComputerState, dict[str, Any]]:
        if self.is_paged:
            state, receipt = self._bounded(
                self._controller().write_named_value_paged, self.field, name, value
            )
            self._suspend(receipt, resident_limit=self.field.image.resident_limit)
            return state, receipt
        return self._controller().write_named_value(self.field, name, value)

    def _restart(
        self,
        *,
        entry: int = 0,
        values: Mapping[str, Any] | None = None,
    ) -> tuple[ComputerState | PagedComputerState, dict[str, Any]]:
        if self.is_paged:
            state, receipt = self._bounded(
                self._controller().restart_paged,
                self.field,
                entry=entry,
                values=values,
            )
            self._suspend(receipt, resident_limit=self.field.image.resident_limit)
            return state, receipt
        return self._controller().restart(self.field, entry=entry, values=values)

    def _grow(
        self, *, mode_count: int, max_steps: int | None = None,
        resource_limits: Mapping[str, Any] | None = None,
        relocate_regions: bool = False,
    ) -> tuple[FieldComputer, ComputerState | PagedComputerState, dict[str, Any]]:
        if self.is_paged:
            return self._bounded(
                self._controller().grow_paged,
                self.field,
                mode_count=mode_count,
                max_steps=max_steps,
                resource_limits=resource_limits,
                relocate_regions=relocate_regions,
            )
        return self._controller().grow(
            self.field, mode_count=mode_count, max_steps=max_steps
        )

    def begin_neural_membrane_epoch(
        self,
        *,
        minimum_modes: int,
        epoch: Mapping[str, Any],
        gain_ppm: int = _regions.NEURAL_MEMBRANE_DEFAULT_GAIN_PPM,
        max_field_bytes: int | None = None,
        resource_manager: ResidencyManager | None = None,
    ) -> NeuralMembraneEpoch:
        """Create a private membrane candidate; no owner state is published."""

        if (
            isinstance(minimum_modes, bool)
            or not isinstance(minimum_modes, int)
            or minimum_modes < 1
        ):
            raise LearningComputerError("minimum membrane modes must be positive")
        if max_field_bytes is not None and (
            isinstance(max_field_bytes, bool)
            or not isinstance(max_field_bytes, int)
            or max_field_bytes < 1
        ):
            raise LearningComputerError("max_field_bytes must be positive")
        current_workspace = self.profile.workspace_words
        target_modes = max(
            minimum_modes,
            self.profile.mode_count if self.profile.neural_membrane else 0,
            (
                current_workspace
                + _regions.NEURAL_MEMBRANE_FIRST_PLANE
                - 1
            )
            // _regions.NEURAL_MEMBRANE_FIRST_PLANE,
        )
        target_modes = (
            (
                target_modes
                + _regions.NEURAL_MEMBRANE_MODE_QUANTUM
                - 1
            )
            // _regions.NEURAL_MEMBRANE_MODE_QUANTUM
            * _regions.NEURAL_MEMBRANE_MODE_QUANTUM
        )
        if (
            max_field_bytes is not None
            and target_modes * 9 * np.dtype(np.float64).itemsize
            > max_field_bytes
        ):
            raise LearningComputerCapacityError(
                "neural membrane exceeds the computer workspace limit"
            )
        migration: Mapping[str, Any] | None = None
        computer = self
        if (
            not self.profile.neural_membrane
            or self.profile.mode_count < target_modes
            or self.profile.neural_membrane_gain_ppm != gain_ppm
        ):
            try:
                source = (
                    self.field.image.materialise()
                    if self.is_paged
                    else self.field._field
                )
                profile, successor, migration_row = (
                    _regions.enable_neural_membrane(
                        source,
                        self.profile,
                        STANDARD_KERNEL_CATALOG,
                        minimum_modes=minimum_modes,
                        gain_ppm=gain_ppm,
                    )
                )
                page_words = _regions.PERSISTENCE_PAGE_WORDS
                first_membrane_page = (
                    profile.neural_membrane_offset // page_words
                )
                last_membrane_page = (
                    profile.neural_membrane_offset
                    + profile.neural_membrane_words
                    - 1
                ) // page_words
                resident_limit = max(
                    _regions.DEFAULT_RESIDENT_PAGES,
                    last_membrane_page - first_membrane_page + 1,
                )
                image, storage = _regions.migrate_flat_to_paged(
                    successor,
                    profile=profile,
                    catalog=STANDARD_KERNEL_CATALOG,
                    transition={
                        "kind": "numerical-law",
                        "operation": "enable-neural-membrane",
                        "epoch_sha256": hashlib.sha256(
                            _canonical(dict(epoch))
                        ).hexdigest(),
                    },
                    resident_limit=resident_limit,
                )
                # The epoch stages under the declared share of the computer
                # that opened it: an image left to make its own manager
                # reserves under the placeholder defaults while the
                # declaration sits unused on the predecessor.
                manager = (
                    resource_manager
                    if resource_manager is not None
                    else (
                        self.field.image.resource_manager
                        if self.is_paged
                        else None
                    )
                )
                if manager is not None:
                    image = image.with_resource_manager(
                        manager,
                        program_id=(
                            self.field.image.program_id if self.is_paged else None
                        ),
                    )
                state: ComputerState | PagedComputerState = (
                    PagedComputerState(image, profile.fingerprint)
                )
                migration = {
                    **dict(migration_row),
                    "storage": dict(storage),
                }
                computer = replace(self, profile=profile, field=state)
                if self.is_paged:
                    # Materialising the source filled this image's cache, and
                    # the successor computer owns the field from here: the
                    # replaced image gives its pages back to the manager.
                    self.field.image.release_resident()
            except _regions.RegionalFieldError as exc:
                raise LearningComputerError(
                    f"neural membrane migration failed: {exc}"
                ) from exc
        return NeuralMembraneEpoch(
            self,
            computer,
            mode_count=minimum_modes,
            epoch=epoch,
            migration=migration,
        )

    def _run(
        self, *, steps: int | None = None
    ) -> tuple[ComputerState | PagedComputerState, dict[str, Any]]:
        """Run bounded transitions, reporting the dense transition summary.

        The paged path reports the same fields as the dense path plus its page
        root and residency.  A resource suspension raises the typed wait and
        leaves this computer exactly as it was.
        """

        machine = self._controller()
        if not self.is_paged:
            return machine.run(self.field, steps=steps)
        successor, summary = machine.run_paged(self.field, steps=steps)
        if summary.get("stop") == "wait":
            self._suspend(
                {
                    "kind": "residency-wait",
                    "wait": summary["wait"],
                    "continuation": summary["continuation"],
                },
                resident_limit=self.field.image.resident_limit,
            )
        # A transition that changed nothing returns the identical state object.
        if isinstance(successor, PagedComputerState):
            image = successor.image
        else:
            image = successor
            successor = machine._paged_state(image)
        inspection = machine.inspect_paged(successor)
        return successor, {
            "schema": _regions.REGIONAL_SCHEMA,
            "paged": True,
            "initial_state_sha256": self.field.image.state_identity_sha256(),
            "state_sha256": successor.image.state_identity_sha256(),
            "status": inspection["status"],
            "reason": inspection["reason"],
            "paused": summary["stop"] == "step-budget",
            "transitions_executed": summary["steps"],
            "transition_receipts": [dict(row) for row in summary["transitions"]],
            "root_sha256": image.root_sha256,
            "residency": summary["residency"],
        }

    @classmethod
    def initial(
        cls,
        computer_id: str,
        profile: Mapping[str, Any] | None = None,
        *,
        max_field_bytes: int | None = None,
    ) -> LearningComputer:
        regional, scalar = _regional_profile(
            profile, max_field_bytes=max_field_bytes
        )
        machine = FieldComputer.regional(
            regional, catalog=STANDARD_KERNEL_CATALOG
        )
        values = {
            "arguments": {},
            "config": {
                "schema": "cassifi.learning-computer-config.v1",
                "scalar_profile": scalar.as_dict(),
            },
            "communication_receiver_a": None,
            "communication_receiver_b": None,
            "outcome": None,
            "result": None,
            "frames": {
                "schema": INVOCATION_FRAMES_SCHEMA,
                "allowances": {},
                "consumed_returns": [],
                "max_depth": regional.max_scope_depth,
                "stack": [],
            },
            "policy": encode_regional_policy(initial_policy()),
            "session": {
                "schema": "cassifi.learning-computer-session.v1",
                "kind": "idle",
                "status": "idle",
            },
            "task": {
                "schema": "cassifi.learning-computer-idle.v1",
                "status": "idle",
            },
        }
        capacities = _regional_capacities(
            regional, values, max_field_bytes=max_field_bytes
        )
        receiver_names = ("communication_receiver_a", "communication_receiver_b")
        while True:
            try:
                state = machine.initial(
                    _PROGRAM,
                    entry=1,
                    values=values,
                    value_capacities=capacities,
                )
                break
            except (TypeError, ValueError) as exc:
                # A compact workspace can hold the image but not the full
                # RECEIVE scratch beside it: halve both receiver targets and
                # rebuild.  Historical images fit on the first attempt and
                # keep the full default capacities (image digest unchanged).
                if (
                    "payload arena is exhausted" not in str(exc)
                    or all(capacities.get(name, 1) <= 1 for name in receiver_names)
                ):
                    raise LearningComputerError(
                        "regional image does not fit the declared workspace"
                    ) from exc
                for name in receiver_names:
                    capacities[name] = max(1, capacities[name] // 2)
        return cls(computer_id, regional, state)

    @property
    def nbytes(self) -> int:
        return self.field.nbytes

    @property
    def state_sha256(self) -> str:
        return self._state_sha256()

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "computer_id": self.computer_id,
            "field": self._descriptor(),
        }
    def persistence_dict(self) -> tuple[dict[str, Any], Mapping[str, bytes]]:
        """Return a logical descriptor plus independently shared pages."""
        if self._legacy_field_descriptor is not None:
            return {
                "schema": SCHEMA,
                "computer_id": self.computer_id,
                "field": dict(self._legacy_field_descriptor),
            }, {}
        controller = self._controller()
        if self.is_paged:
            descriptor, objects = controller.paged_chunks(self.field)
        else:
            cached = self._dense_persistence
            if cached is None:
                descriptor, objects = _field_regions.chunked_descriptor(
                    self.field._field,
                    self.profile,
                    STANDARD_KERNEL_CATALOG,
                    _input_validated=True,
                    _state_sha256=controller.state_sha256(self.field),
                )
                cached = (descriptor, MappingProxyType(dict(objects)))
                object.__setattr__(self, "_dense_persistence", cached)
            # Callers only read the shared descriptor and page map.
            descriptor, objects = cached
        return {
            "schema": SCHEMA,
            "computer_id": self.computer_id,
            "placement": (
                _field_regions.PAGED_STATE_KIND_ROOT
                if self.is_paged
                else _field_regions.PAGED_STATE_KIND_FLAT
            ),
            "field": descriptor,
        }, objects

    @classmethod
    def from_persistence_dict(
        cls,
        value: Mapping[str, Any],
        objects: Mapping[str, bytes],
        *,
        accept_recorded_catalog: bool = False,
    ) -> LearningComputer:
        """Hydrate one verified computer from its independently addressed pages.

        A catalog revision re-identifies the recorded image after checking its
        original digest and every page. Paged fields undergo this full audit
        once before they are re-encoded under the running catalog.
        """

        if (
            not isinstance(value, Mapping)
            or set(value) not in (
                {"schema", "computer_id", "field"},
                {"schema", "computer_id", "field", "placement"},
            )
            or value.get("schema") != SCHEMA
        ):
            raise LearningComputerError("invalid persistent learning computer record")
        placement = value.get("placement")
        if placement is not None and placement not in {
            _field_regions.PAGED_STATE_KIND_ROOT,
            _field_regions.PAGED_STATE_KIND_FLAT,
        }:
            raise LearningComputerError("invalid persistent learning computer placement")
        try:
            field_descriptor = value["field"]
            if (
                isinstance(field_descriptor, Mapping)
                and not isinstance(field_descriptor.get("chunks"), list)
            ):
                profile_payload = dict(field_descriptor["profile"])
                profile_payload["kernel_names"] = list(STANDARD_KERNEL_CATALOG.names)
                decoded_profile = RegionalProfile.from_dict(profile_payload)
                flat = np.zeros(decoded_profile.total_words, dtype=np.float64)
                previous = -1
                for page in field_descriptor["field_pages"]:
                    if not isinstance(page, Mapping) or set(page) != {
                        "index", "words", "data_b64"
                    }:
                        raise LearningComputerError("invalid legacy field page")
                    index = int(page["index"])
                    words = int(page["words"])
                    if index <= previous or words < 1:
                        raise LearningComputerError("invalid legacy field page geometry")
                    raw = base64.b64decode(page["data_b64"], validate=True)
                    if len(raw) != words * 8:
                        raise LearningComputerError("invalid legacy field page bytes")
                    start = index * int(field_descriptor["page_words"])
                    flat[start:start + words] = np.frombuffer(raw, dtype="<f8")
                    previous = index
                flat[_field_regions.H_PROFILE_SHA:_field_regions.H_PROFILE_SHA + 8] = (
                    _field_regions._sha_words(decoded_profile.fingerprint)
                )
                flat[_field_regions.H_CATALOG_SHA:_field_regions.H_CATALOG_SHA + 8] = (
                    _field_regions._sha_words(STANDARD_KERNEL_CATALOG.fingerprint)
                )
                field = flat.reshape(decoded_profile.shape)
                _field_regions.validate_field(
                    field, decoded_profile, STANDARD_KERNEL_CATALOG
                )
                machine = FieldComputer.regional(
                    decoded_profile, catalog=STANDARD_KERNEL_CATALOG
                )
                state = ComputerState(field, decoded_profile.fingerprint)
                result = cls(str(value["computer_id"]), decoded_profile, state)
                object.__setattr__(
                    result, "_legacy_field_descriptor", dict(field_descriptor)
                )
                return result
            profile = RegionalProfile.from_dict(field_descriptor["profile"])
            machine = FieldComputer.regional(
                profile, catalog=STANDARD_KERNEL_CATALOG
            )
            paged = (
                profile.neural_membrane
                if placement is None
                else placement == _field_regions.PAGED_STATE_KIND_ROOT
            )
            if paged:
                if (
                    accept_recorded_catalog
                    and field_descriptor.get("catalog_sha256")
                    != STANDARD_KERNEL_CATALOG.fingerprint
                ):
                    _, field = _field_regions.from_chunked_descriptor(
                        field_descriptor,
                        objects,
                        STANDARD_KERNEL_CATALOG,
                        accept_recorded_catalog=True,
                    )
                    image = _field_regions.PagedFieldImage.from_dense(
                        field,
                        profile,
                        STANDARD_KERNEL_CATALOG,
                        resident_limit=field_descriptor.get(
                            "resident_limit", _field_regions.DEFAULT_RESIDENT_PAGES
                        ),
                        dirty_limit=field_descriptor.get(
                            "dirty_limit", _field_regions.DEFAULT_DIRTY_PAGES
                        ),
                    )
                else:
                    image = _field_regions.PagedFieldImage.from_chunked_descriptor(
                        field_descriptor,
                        objects,
                        STANDARD_KERNEL_CATALOG,
                    )
                state = machine._paged_state(image)
                machine.validate_paged(state)
            else:
                _, field = _field_regions.from_chunked_descriptor(
                    field_descriptor,
                    objects,
                    STANDARD_KERNEL_CATALOG,
                    accept_recorded_catalog=accept_recorded_catalog,
                )
                state = ComputerState(field, profile.fingerprint)
                machine.validate(state)
            return cls(str(value["computer_id"]), profile, state)
        except LearningComputerError:
            raise
        except (TypeError, ValueError) as exc:
            raise LearningComputerError(
                "invalid persistent learning computer field"
            ) from exc

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> LearningComputer:
        if (
            not isinstance(value, Mapping)
            or set(value) != {"schema", "computer_id", "field"}
            or value.get("schema") != SCHEMA
        ):
            if isinstance(value, Mapping) and value.get("schema") in {
                PREVIOUS_SCHEMA,
                LEGACY_SCHEMA,
            }:
                raise LearningComputerError(
                    "legacy computer requires explicit migrate_legacy"
                )
            raise LearningComputerError("invalid learning computer record")
        try:
            machine, state = FieldComputer.from_descriptor(
                value["field"], catalog=STANDARD_KERNEL_CATALOG
            )
            if not machine.is_regional:
                raise LearningComputerError("regional field descriptor required")
            return cls(str(value["computer_id"]), machine.profile, state)
        except (TypeError, ValueError) as exc:
            raise LearningComputerError("invalid learning computer field") from exc

    @classmethod
    def migrate_legacy(cls, value: Mapping[str, Any]) -> LearningComputer:
        """Explicitly translate a safe v1/v2 checkpoint into the v3 image."""

        if not isinstance(value, Mapping) or value.get("schema") not in {
            PREVIOUS_SCHEMA,
            LEGACY_SCHEMA,
        }:
            raise LearningComputerError("legacy computer record required")
        if value.get("continuation") is not None:
            raise LearningComputerError(
                "active legacy solver continuation has no safe migration boundary"
            )
        try:
            profile_value = dict(value["profile"])
            policy = PolicyState.from_dict(value["policy"])
            successor = cls.initial(str(value["computer_id"]), profile_value)
            field, _receipt = successor._write_named_value(
                "policy", encode_regional_policy(policy)
            )
            successor = replace(successor, field=field)
            descriptor = value.get("machine")
            if descriptor is None:
                return successor
            legacy_machine, legacy_state = FieldComputer.from_descriptor(
                descriptor
            )
            inspected = legacy_machine.inspect(legacy_state)
            parts = legacy_state._field.reshape(
                1, 9, legacy_machine.profile.mode_count, 1
            )[0, :, :, 0]
            program = tuple(
                (
                    int(parts[0, index]),
                    int(parts[1, index]),
                    int(parts[2, index]),
                    int(parts[3, index]),
                    int(parts[4, index]),
                )
                for index in range(int(inspected["program_length"]))
            )
            compiled = CompiledFieldProgram(
                program=program,
                entry=int(inspected["pc"]),
                left=tuple(inspected["left"]),
                right=tuple(inspected["right"]),
                source_sha256=hashlib.sha256(
                    _canonical({"program": program})
                ).hexdigest(),
                source_nodes=len(program),
            )
            task = regional_scalar_state(compiled, legacy_machine.profile)
            task.update(
                {
                    "accumulator": int(inspected["accumulator"]),
                    "status": str(inspected["status"]),
                    "reason": str(inspected["reason"]),
                    "transitions": int(
                        inspected["resource_ledger"]["transitions"]
                    ),
                    "stack_reads": int(
                        inspected["resource_ledger"]["stack_reads"]
                    ),
                    "stack_writes": int(
                        inspected["resource_ledger"]["stack_writes"]
                    ),
                    "field_cells_copied": int(
                        inspected["resource_ledger"]["field_cells_copied"]
                    ),
                    "pc_observations": list(
                        inspected["execution_learning"]["pc_observations"]
                    ),
                    "outcome": (
                        None
                        if inspected["status"] == "running"
                        else inspected
                    ),
                }
            )
            state, _receipt = controller.restart(
                successor.field,
                entry=_ENTRIES[SCALAR_REGIONAL_KERNEL],
                values={
                    "task": task,
                    "outcome": task["outcome"],
                    "result": task["outcome"],
                    "session": {
                        "schema": "cassifi.learning-computer-session.v1",
                        "kind": "scalar",
                        "status": inspected["status"],
                    },
                },
            )
            return replace(successor, field=state)
        except (KeyError, TypeError, ValueError) as exc:
            raise LearningComputerError("legacy migration failed") from exc
    def _region_capacity(self) -> dict[str, dict[str, int]]:
        """Return named-value allocation data from the live controller image."""
        machine = self._inspect()
        by_slot = {
            int(row["slot"]): row
            for row in machine.get("regions", ())
            if isinstance(row, Mapping) and "slot" in row
        }
        named = machine.get("named_values", {})
        if not isinstance(named, Mapping):
            raise LearningComputerError("regional named-value metadata is invalid")
        flat = self._flat()
        capacities: dict[str, dict[str, int]] = {}
        for name, object_id in named.items():
            if not isinstance(name, str):
                raise LearningComputerError("regional named-value name is invalid")
            try:
                reference = _field_regions._resolve_object(
                    flat,
                    self.profile,
                    int(object_id),
                )
            except (TypeError, ValueError, _field_regions.RegionalFieldError) as exc:
                raise LearningComputerError(
                    "regional named-value reference is invalid"
                ) from exc
            row = by_slot.get(int(reference.slot))
            if row is None:
                raise LearningComputerError(
                    "regional named-value region is missing from inspection"
                )
            used = int(row["used_words"])
            capacity = int(row["capacity_words"])
            capacities[name] = {
                "used_words": used,
                "capacity_words": capacity,
                "available_words": max(0, capacity - used),
            }
        return capacities

    @staticmethod
    def _settled_no_progress(receipt: Mapping[str, Any]) -> bool:
        run = receipt.get("run", receipt)
        if not isinstance(run, Mapping):
            return False
        transitions = run.get("transition_receipts")
        return (
            isinstance(transitions, Sequence)
            and bool(transitions)
            and isinstance(transitions[-1], Mapping)
            and transitions[-1].get("kind") == "no-ready-event"
        )

    @staticmethod
    def _settled_transitions(receipt: Mapping[str, Any]) -> int:
        run = receipt.get("run", receipt)
        if not isinstance(run, Mapping):
            return 0
        value = run.get("transitions_executed", 0)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise LearningComputerError("settled run transition accounting is invalid")
        return value

    def _settled_request_complete(self) -> bool:
        task = self._value("task")
        continuation = (
            task.get("continuation") if isinstance(task, Mapping) else None
        )
        return (
            isinstance(continuation, Mapping)
            and continuation.get("request") is None
            and not bool(continuation.get("partial"))
            and self._value("result") is not None
        )

    def _check_settled_capacity(
        self,
        before: Mapping[str, Mapping[str, int]],
        after: Mapping[str, Mapping[str, int]],
        reserve_fraction: float,
    ) -> None:
        for name, current in after.items():
            prior = before.get(name)
            if prior is None:
                continue
            capacity = int(current["capacity_words"])
            available = int(current["available_words"])
            reserve_words = int(math.ceil(capacity * reserve_fraction))
            participated = (
                int(current["used_words"]) != int(prior["used_words"])
                or int(current["capacity_words"]) != int(prior["capacity_words"])
            )
            if not participated:
                continue
            if available <= 0 and int(prior["available_words"]) > 0:
                raise LearningComputerCapacityError(
                    f"regional value {name!r} reached capacity"
                )
            if available < reserve_words:
                raise LearningComputerCapacityError(
                    f"regional value {name!r} entered its reserved capacity"
                )


    def _value(self, name: str) -> Any:
        return self._named_value(name)

    def named_value(self, name: str) -> Any:
        """Read one named computer value without rendering the whole computer.

        ``inspect`` renders the task, session, and policy records and digests
        each of them; a caller that only needs the current task should not pay
        for that.  The returned value is the same one ``inspect`` reports.
        """

        return self._named_value(name)

    def enable_ngram_readout(
        self,
        model_id: str,
        table_id: str,
        width: int = 2048,
        rank: int = 8,
    ) -> tuple["LearningComputer", dict[str, Any]]:
        """Opt in to a dedicated, restart-persistent n-gram readout value."""
        try:
            state = dict(
                _ngram_learning.initial_state(
                    model_id, table_id, width=width, rank=rank
                )
            )
            capacity_words = _ngram_learning.state_capacity_words(state)
        except (TypeError, ValueError) as exc:
            raise LearningComputerError(
                f"invalid n-gram readout declaration: {exc}"
            ) from exc
        capacities = self._region_capacity()
        existing = capacities.get(NGRAM_READOUT_FIELD_VALUE)
        if existing is not None:
            try:
                current = _ngram_learning.validate_state(
                    self.named_value(NGRAM_READOUT_FIELD_VALUE)
                )
            except (TypeError, ValueError) as exc:
                raise LearningComputerError(
                    "canonical n-gram readout field value is invalid"
                ) from exc
            if any(
                current[key] != state[key]
                for key in ("model_id", "table_id", "width", "rank")
            ):
                raise LearningComputerError(
                    "n-gram readout is already bound to another model or table"
                )
            return self, {
                "schema": NGRAM_READOUT_MIGRATION_SCHEMA,
                "kind": "ngram-readout-already-enabled",
                "computer_id": self.computer_id,
                "field_value": NGRAM_READOUT_FIELD_VALUE,
                "changed": False,
                "model_id": current["model_id"],
                "table_id": current["table_id"],
                "revision": current["revision"],
                "coefficient_sha256": current["coefficients"]["sha256"],
                "state_sha256": self.state_sha256,
            }
        try:
            if self.is_paged:
                image, migration = self._bounded(
                    _regions.declare_named_value_paged,
                    self.field.image,
                    NGRAM_READOUT_FIELD_VALUE,
                    state,
                    capacity_words,
                )
                self._suspend(
                    migration, resident_limit=self.field.image.resident_limit
                )
                field: ComputerState | PagedComputerState = PagedComputerState(
                    image, self.profile.fingerprint
                )
            else:
                raw_field, migration = _regions.declare_named_value(
                    self.field._field,
                    self.profile,
                    STANDARD_KERNEL_CATALOG,
                    NGRAM_READOUT_FIELD_VALUE,
                    state,
                    capacity_words,
                )
                field = ComputerState(raw_field, self.profile.fingerprint)
        except (_regions.RegionalFieldError, FieldComputerError) as exc:
            raise LearningComputerCapacityError(
                f"n-gram readout field allocation failed: {exc}"
            ) from exc
        successor = replace(self, field=field)
        return successor, {
            "schema": NGRAM_READOUT_MIGRATION_SCHEMA,
            "kind": "ngram-readout-enabled",
            "computer_id": self.computer_id,
            "field_value": NGRAM_READOUT_FIELD_VALUE,
            "model_id": state["model_id"],
            "table_id": state["table_id"],
            "width": state["width"],
            "rank": state["rank"],
            "revision": state["revision"],
            "coefficient_sha256": state["coefficients"]["sha256"],
            "capacity_words": capacity_words,
            "predecessor_state_sha256": self.state_sha256,
            "state_sha256": successor.state_sha256,
            "field_transition": dict(migration),
        }

    def ngram_readout_state(self) -> dict[str, Any]:
        """Read the validated n-gram coefficients from their canonical field slot."""
        if NGRAM_READOUT_FIELD_VALUE not in self._region_capacity():
            raise LearningComputerError("n-gram readout is not enabled in this field")
        try:
            return _ngram_learning.validate_state(
                self.named_value(NGRAM_READOUT_FIELD_VALUE)
            )
        except (TypeError, ValueError) as exc:
            raise LearningComputerError(
                "canonical n-gram readout field value is invalid"
            ) from exc

    def learn_ngram_readout(
        self,
        table_vector: Sequence[float] | np.ndarray,
        hidden: Sequence[float] | np.ndarray,
        feedback: Mapping[str, Any],
    ) -> tuple["LearningComputer", dict[str, Any]]:
        """Learn once from an identified token margin and publish in the field."""
        current = self.ngram_readout_state()
        try:
            raw_table = np.asarray(table_vector)
            raw_hidden = np.asarray(hidden)
        except (TypeError, ValueError) as exc:
            raise LearningComputerError(
                "n-gram learning vectors must be numeric sequences"
            ) from exc
        if (
            raw_table.ndim != 1
            or raw_table.size != _ngram_learning.TABLE_VECTOR_SIZE
            or raw_table.dtype.kind not in "fiu"
            or raw_hidden.ndim != 1
            or raw_hidden.size != int(current["width"])
            or raw_hidden.dtype.kind not in "fiu"
        ):
            raise LearningComputerError(
                "n-gram learning vectors have an invalid numeric layout"
            )
        try:
            table_values = np.asarray(raw_table, dtype=np.float32)
            hidden_values = np.asarray(raw_hidden, dtype=np.float32)
        except (TypeError, ValueError, OverflowError) as exc:
            raise LearningComputerError(
                "n-gram learning vectors cannot be represented as float32"
            ) from exc
        if not np.isfinite(table_values).all() or not np.isfinite(hidden_values).all():
            raise LearningComputerError(
                "n-gram learning vectors contain nonfinite values"
            )
        try:
            updated = dict(
                _ngram_learning.learn(
                    current, table_values, hidden_values, feedback
                )
            )
        except (TypeError, ValueError) as exc:
            raise LearningComputerError(
                f"n-gram readout learning was rejected: {exc}"
            ) from exc
        try:
            field, transition = self._write_named_value(
                NGRAM_READOUT_FIELD_VALUE, updated
            )
        except (_regions.RegionalFieldError, FieldComputerError) as exc:
            raise LearningComputerCapacityError(
                f"n-gram readout field update failed: {exc}"
            ) from exc
        successor = replace(self, field=field)
        last = updated["last_feedback"]
        return successor, {
            "schema": NGRAM_READOUT_MIGRATION_SCHEMA,
            "kind": "ngram-readout-learned",
            "computer_id": self.computer_id,
            "field_value": NGRAM_READOUT_FIELD_VALUE,
            "model_id": updated["model_id"],
            "table_id": updated["table_id"],
            "feedback_id": last["id"],
            "context_sha256": last["context_sha256"],
            "next_token_id": last["next_token_id"],
            "competitor_token_id": last["competitor_token_id"],
            "advantage": last["advantage"],
            "revision_before": current["revision"],
            "revision_after": updated["revision"],
            "coefficient_sha256_before": current["coefficients"]["sha256"],
            "coefficient_sha256_after": updated["coefficients"]["sha256"],
            "predecessor_state_sha256": self.state_sha256,
            "state_sha256": successor.state_sha256,
            "field_transition": dict(transition),
        }
    def begin_model_cycle(self, task_id: str) -> ResidentModelCycle:
        """Advance the resident model graph privately until its token boundary."""
        return ResidentModelCycle(self, task_id)


    def inspect(self) -> dict[str, Any]:
        machine = self._inspect()
        values = self._named_values(
            ("frames", "task", "session", "policy", "outcome", "result")
        )
        task = values["task"]
        session = values["session"]
        policy = values["policy"]
        frames = self._invocation_frames(values["frames"])
        return {
            "schema": SCHEMA,
            "computer_id": self.computer_id,
            "field_bytes": self.nbytes,
            "state_sha256": machine["state_sha256"],
            "status": machine["status"],
            "logical_transition": machine["logical_transition"],
            "task": task,
            "task_state_sha256": hashlib.sha256(_canonical(task)).hexdigest(),
            "session": session,
            "session_state_sha256": hashlib.sha256(
                _canonical(session)
            ).hexdigest(),
            "policy_state_sha256": hashlib.sha256(
                _canonical(policy)
            ).hexdigest(),
            "outcome": values["outcome"],
            "consumed_result": values["result"],
            "invocation_depth": len(frames["stack"]),
            "invocation_frames": frames,
            "active_invocation": (
                None
                if not frames["stack"]
                else {
                    "call_id": frames["stack"][-1]["call_id"],
                    "dependencies": frames["stack"][-1]["dependencies"],
                    "return_binding": frames["stack"][-1]["return_binding"],
                }
            ),
            "resource_ledger": machine["resource_ledger"],
            "region_capacity": self._region_capacity(),
        }

    def explain(
        self,
        source: Mapping[str, Any],
        *,
        budget: int = 2000,
        explore: bool = True,
    ) -> Mapping[str, Any]:
        """Project the prospective policy selection without publishing state."""

        del explore
        task = policy_regional_state(
            source,
            learn=False,
            lifetime_budget=budget,
            max_field_bytes=self.nbytes,
            policy=self._value("policy"),
        )
        transition = policy_regional_kernel(task, {}, 1)
        if transition.status != "done" or not isinstance(
            transition.output, Mapping
        ):
            raise LearningComputerError(
                "policy projection did not produce a selection"
            )
        selection = transition.output.get("selection")
        method = transition.output.get("method")
        if not isinstance(selection, Mapping) or not isinstance(method, str):
            raise LearningComputerError("policy selection is unavailable")
        return {
            "selected_method": method,
            "selection": dict(selection),
            "policy_state_sha256": self.inspect()["policy_state_sha256"],
        }

    def _scalar_profile(self) -> ComputerProfile:
        config = self._value("config")
        if not isinstance(config, Mapping):
            raise LearningComputerError("computer configuration is invalid")
        try:
            return ComputerProfile(**dict(config["scalar_profile"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise LearningComputerError("scalar profile is invalid") from exc

    def _invocation_frames(self, value: Any | None = None) -> dict[str, Any]:
        try:
            raw = self._value("frames") if value is None else value
        except (TypeError, ValueError) as exc:
            raise LearningComputerError(
                "computer image predates resident invocation frames"
            ) from exc
        if not isinstance(raw, Mapping):
            raise LearningComputerError("resident invocation frames are invalid")
        frames = json.loads(_canonical(raw).decode("utf-8"))
        if frames.get("schema") == PREVIOUS_INVOCATION_FRAMES_SCHEMA:
            legacy_frame_keys = {
                "arguments",
                "call_id",
                "dependencies",
                "kernel",
                "outcome",
                "result",
                "return_binding",
                "session",
                "task",
            }
            if (
                set(frames) != {"schema", "max_depth", "stack"}
                or not isinstance(frames["stack"], list)
                or any(
                    not isinstance(frame, dict)
                    or set(frame) != legacy_frame_keys
                    for frame in frames["stack"]
                )
            ):
                raise LearningComputerError(
                    "legacy resident invocation frames are invalid"
                )
            frames = {
                "schema": INVOCATION_FRAMES_SCHEMA,
                "allowances": {},
                "consumed_returns": [],
                "max_depth": frames["max_depth"],
                "stack": [
                    {
                        **frame,
                        "allowance_id": None,
                        "dispatch_work": 0,
                        "expected_return": {},
                        "phase": "running-child",
                        "request_sha256": hashlib.sha256(
                            _canonical(
                                {
                                    "arguments": frame.get("arguments"),
                                    "call_id": frame.get("call_id"),
                                    "dependencies": frame.get("dependencies"),
                                    "kernel": frame.get("kernel"),
                                    "return_binding": frame.get(
                                        "return_binding"
                                    ),
                                    "task": frame.get("task"),
                                }
                            )
                        ).hexdigest(),
                        "reservation": None,
                        "reservation_sha256": None,
                    }
                    for frame in frames["stack"]
                ],
            }
        if (
            set(frames)
            != {
                "allowances",
                "consumed_returns",
                "max_depth",
                "schema",
                "stack",
            }
            or frames.get("schema") != INVOCATION_FRAMES_SCHEMA
            or frames.get("max_depth") != self.profile.max_scope_depth
            or not isinstance(frames.get("allowances"), dict)
            or not isinstance(frames.get("consumed_returns"), list)
            or not isinstance(frames.get("stack"), list)
            or len(frames["stack"]) > self.profile.max_scope_depth
        ):
            raise LearningComputerError("resident invocation frames are invalid")
        for allowance_id, raw_allowance in frames["allowances"].items():
            if (
                not isinstance(allowance_id, str)
                or not allowance_id
                or len(allowance_id.encode("utf-8")) > 512
                or not isinstance(raw_allowance, dict)
                or set(raw_allowance)
                != {
                    "charged",
                    "consumed_call_ids",
                    "limits",
                    "reserved",
                }
                or not isinstance(raw_allowance["consumed_call_ids"], list)
                or len(set(raw_allowance["consumed_call_ids"]))
                != len(raw_allowance["consumed_call_ids"])
                or any(
                    not isinstance(call_id, str) or not call_id
                    for call_id in raw_allowance["consumed_call_ids"]
                )
            ):
                raise LearningComputerError(
                    "resident root allowance is invalid"
                )
            limits = _resource_map(
                raw_allowance["limits"], "root allowance limits", require_work=True
            )
            charged = _resource_map(
                raw_allowance["charged"], "root allowance charged resources"
            )
            reserved = _resource_map(
                raw_allowance["reserved"], "root allowance reservations"
            )
            if any(
                charged[name] + reserved[name] > limits[name]
                for name in ROOT_RESOURCE_NAMES
            ):
                raise LearningComputerError(
                    "resident root allowance exceeds its limits"
                )
        consumed_ids: set[str] = set()
        for marker in frames["consumed_returns"]:
            if (
                not isinstance(marker, dict)
                or set(marker)
                != {"call_id", "child_return_sha256", "return_binding"}
                or not isinstance(marker["call_id"], str)
                or not marker["call_id"]
                or marker["call_id"] in consumed_ids
                or not isinstance(marker["return_binding"], str)
                or not marker["return_binding"]
                or not isinstance(marker["child_return_sha256"], str)
                or len(marker["child_return_sha256"]) != 64
            ):
                raise LearningComputerError(
                    "resident consumed-return marker is invalid"
                )
            consumed_ids.add(marker["call_id"])
        required_frame_keys = {
            "allowance_id",
            "arguments",
            "call_id",
            "dependencies",
            "dispatch_work",
            "expected_return",
            "kernel",
            "outcome",
            "phase",
            "request_sha256",
            "reservation",
            "reservation_sha256",
            "result",
            "return_binding",
            "session",
            "task",
        }
        for frame in frames["stack"]:
            if (
                not isinstance(frame, dict)
                or set(frame) != required_frame_keys
                or not isinstance(frame["call_id"], str)
                or not frame["call_id"]
                or frame["call_id"] in consumed_ids
                or not isinstance(frame["dependencies"], list)
                or not isinstance(frame["kernel"], str)
                or frame["kernel"] not in _ENTRIES
                or not isinstance(frame["return_binding"], str)
                or not frame["return_binding"]
                or not isinstance(frame["session"], dict)
                or not isinstance(frame["task"], dict)
                or not isinstance(frame["arguments"], dict)
                or not isinstance(frame["expected_return"], dict)
                or frame["phase"] != "running-child"
                or not isinstance(frame["request_sha256"], str)
                or len(frame["request_sha256"]) != 64
                or isinstance(frame["dispatch_work"], bool)
                or not isinstance(frame["dispatch_work"], int)
                or frame["dispatch_work"] < 0
            ):
                raise LearningComputerError(
                    "resident invocation frame is invalid"
                )
            allowance_id = frame["allowance_id"]
            if allowance_id is None:
                if (
                    frame["reservation"] is not None
                    or frame["reservation_sha256"] is not None
                ):
                    raise LearningComputerError(
                        "unbudgeted invocation frame carries a reservation"
                    )
            else:
                if (
                    allowance_id not in frames["allowances"]
                    or not isinstance(frame["reservation"], dict)
                    or not isinstance(frame["reservation_sha256"], str)
                    or len(frame["reservation_sha256"]) != 64
                ):
                    raise LearningComputerError(
                        "budgeted invocation frame is invalid"
                    )
                reservation = _resource_map(
                    frame["reservation"],
                    "resident invocation reservation",
                    require_work=True,
                )
                if (
                    hashlib.sha256(_canonical(reservation)).hexdigest()
                    != frame["reservation_sha256"]
                    or frame["dispatch_work"] > reservation["work"]
                ):
                    raise LearningComputerError(
                        "resident invocation reservation diverges"
                    )
        return frames

    def call(
        self,
        *,
        call_id: str,
        kernel: str,
        state: Mapping[str, Any] | None = None,
        return_binding: str,
        arguments: Mapping[str, Any] | None = None,
        dependencies: Sequence[Mapping[str, Any]] = (),
        kind: str | None = None,
        steps: int = 1,
        allowance_id: str | None = None,
        allowance: Mapping[str, Any] | None = None,
        reservation: Mapping[str, Any] | None = None,
        expected_return: Mapping[str, Any] | None = None,
        request_identity: Mapping[str, Any] | None = None,
    ) -> tuple[LearningComputer, Mapping[str, Any]]:
        """Suspend the resident caller and run a child in the same image."""

        if (
            not isinstance(call_id, str)
            or not call_id
            or len(call_id.encode("utf-8")) > 512
            or not isinstance(return_binding, str)
            or not return_binding
            or len(return_binding.encode("utf-8")) > 512
        ):
            raise LearningComputerError(
                "call and return-binding identities must be bounded text"
            )
        if kernel not in STANDARD_KERNEL_CATALOG.names:
            raise LearningComputerError("kernel is not in the fixed catalog")
        if state is not None and not isinstance(state, Mapping):
            raise LearningComputerError("child task state must be a mapping")
        if arguments is not None and not isinstance(arguments, Mapping):
            raise LearningComputerError("child arguments must be a mapping")
        if expected_return is not None and not isinstance(
            expected_return, Mapping
        ):
            raise LearningComputerError("expected child return must be a mapping")
        if request_identity is not None and not isinstance(
            request_identity, Mapping
        ):
            raise LearningComputerError("child request identity must be a mapping")
        if (
            isinstance(dependencies, (str, bytes))
            or not isinstance(dependencies, Sequence)
            or any(not isinstance(item, Mapping) for item in dependencies)
        ):
            raise LearningComputerError(
                "child dependencies must be typed mappings"
            )
        if isinstance(steps, bool) or not isinstance(steps, int) or steps < 1:
            raise LearningComputerError("child steps must be a positive integer")
        resident = self._named_values(
            ("arguments", "frames", "outcome", "result", "session", "task")
        )
        parent_session = resident["session"]
        parent_task = resident["task"]
        if (
            not isinstance(parent_session, Mapping)
            or not isinstance(parent_session.get("kernel"), str)
            or not isinstance(parent_task, Mapping)
        ):
            raise LearningComputerError(
                "no fixed-catalog regional caller is resident"
            )
        child_state = dict(parent_task) if state is None else dict(state)
        normalized_arguments = dict(arguments or {})
        normalized_dependencies = [
            json.loads(_canonical(item).decode("utf-8"))
            for item in dependencies
        ]
        normalized_expected_return = json.loads(
            _canonical(dict(expected_return or {})).decode("utf-8")
        )
        request = json.loads(
            _canonical(
                dict(
                    request_identity
                    or {
                        "arguments": normalized_arguments,
                        "call_id": call_id,
                        "dependencies": normalized_dependencies,
                        "kernel": kernel,
                        "return_binding": return_binding,
                        "state": child_state,
                    }
                )
            ).decode("utf-8")
        )
        request_sha256 = hashlib.sha256(_canonical(request)).hexdigest()
        frames = self._invocation_frames(resident["frames"])
        if len(frames["stack"]) >= frames["max_depth"]:
            raise LearningComputerError("resident invocation depth is exhausted")
        if (
            any(frame["call_id"] == call_id for frame in frames["stack"])
            or any(
                marker["call_id"] == call_id
                for marker in frames["consumed_returns"]
            )
        ):
            raise LearningComputerError("resident call identity is duplicated")
        normalized_reservation: dict[str, int] | None = None
        reservation_sha256: str | None = None
        if allowance_id is None:
            if allowance is not None or reservation is not None:
                raise LearningComputerError(
                    "root allowance identity is required for reservations"
                )
        else:
            if (
                not isinstance(allowance_id, str)
                or not allowance_id
                or len(allowance_id.encode("utf-8")) > 512
            ):
                raise LearningComputerError(
                    "root allowance identity must be bounded text"
                )
            if reservation is None:
                raise LearningComputerError(
                    "budgeted child call requires a reservation"
                )
            if allowance_id not in frames["allowances"]:
                if allowance is None:
                    raise LearningComputerError(
                        "new root allowance requires explicit limits"
                    )
                frames["allowances"][allowance_id] = {
                    "charged": _zero_resources(),
                    "consumed_call_ids": [],
                    "limits": _resource_map(
                        allowance, "root allowance limits", require_work=True
                    ),
                    "reserved": _zero_resources(),
                }
            elif allowance is not None:
                supplied_allowance = _resource_map(
                    allowance, "root allowance limits", require_work=True
                )
                if (
                    supplied_allowance
                    != frames["allowances"][allowance_id]["limits"]
                ):
                    raise LearningComputerError(
                        "root allowance limits cannot be reset"
                    )
            root_allowance = frames["allowances"][allowance_id]
            normalized_reservation = _resource_map(
                reservation, "child reservation", require_work=True
            )
            if any(
                root_allowance["charged"][name]
                + root_allowance["reserved"][name]
                + normalized_reservation[name]
                > root_allowance["limits"][name]
                for name in ROOT_RESOURCE_NAMES
            ):
                raise LearningComputerError("root allowance is exhausted")
            for name in ROOT_RESOURCE_NAMES:
                root_allowance["reserved"][name] += normalized_reservation[name]
            reservation_sha256 = hashlib.sha256(
                _canonical(normalized_reservation)
            ).hexdigest()
        frame = {
            "allowance_id": allowance_id,
            "arguments": resident["arguments"],
            "call_id": call_id,
            "dependencies": normalized_dependencies,
            "dispatch_work": 0,
            "expected_return": normalized_expected_return,
            "kernel": parent_session["kernel"],
            "outcome": resident["outcome"],
            "phase": "running-child",
            "request_sha256": request_sha256,
            "reservation": normalized_reservation,
            "reservation_sha256": reservation_sha256,
            "result": resident["result"],
            "return_binding": return_binding,
            "session": dict(parent_session),
            "task": dict(parent_task),
        }
        frames["stack"].append(frame)
        field, frame_receipt = self._write_named_value("frames", frames)
        staged = replace(self, field=field)
        session_kind = kernel if kind is None else kind
        if (
            not isinstance(session_kind, str)
            or not session_kind
            or len(session_kind) > 256
        ):
            raise LearningComputerError(
                "child task kind must be a bounded string"
            )
        scheduled, admission = staged._schedule(
            kernel,
            child_state,
            {
                "schema": "cassifi.learning-computer-session.v1",
                "kind": session_kind,
                "kernel": kernel,
                "parent_call_id": call_id,
                "status": "running",
                "task_sha256": hashlib.sha256(
                    _canonical(child_state)
                ).hexdigest(),
            },
            normalized_arguments,
        )
        successor, run = scheduled.advance(steps=steps)
        return successor, {
            "schema": "cassifi.learning-computer-call-receipt.v2",
            "call_id": call_id,
            "kernel": kernel,
            "request_sha256": request_sha256,
            "reservation_sha256": reservation_sha256,
            "return_binding": return_binding,
            "frame": frame_receipt,
            "admission": admission,
            "run": run,
            "state_sha256": successor.state_sha256,
        }

    def _active_child_return(
        self,
        frames: Mapping[str, Any],
        *,
        status: str,
        run_receipt: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if (
            status
            not in {
                "cancelled",
                "counter-exhausted",
                "exhausted",
                "faulted",
                "halted",
            }
            or not frames["stack"]
        ):
            raise LearningComputerError("active child return status is invalid")
        frame = frames["stack"][-1]
        resident = self._named_values(
            ("arguments", "outcome", "result", "session", "task")
        )
        task = resident["task"]
        continuation = self.as_dict()
        resources = _zero_resources()
        resources["work"] = int(frame["dispatch_work"])
        resources["storage_words"] = (
            len(_canonical(continuation)) + 3
        ) // 4
        for source in (resident["result"], resident["outcome"], task):
            if not isinstance(source, Mapping):
                continue
            raw_resources = source.get("resources")
            if not isinstance(raw_resources, Mapping):
                continue
            for name in ROOT_RESOURCE_NAMES:
                if name in {"storage_words", "work"}:
                    continue
                raw = raw_resources.get(name)
                if (
                    not isinstance(raw, bool)
                    and isinstance(raw, int)
                    and raw >= 0
                ):
                    resources[name] = max(resources[name], raw)
        task_sha256 = hashlib.sha256(_canonical(task)).hexdigest()
        return {
            "schema": CHILD_RETURN_SCHEMA,
            "arguments": resident["arguments"],
            "call_id": frame["call_id"],
            "continuation": continuation,
            "continuation_sha256": self.state_sha256,
            "dependencies": frame["dependencies"],
            "kernel": (
                resident["session"].get("kernel")
                if isinstance(resident["session"], Mapping)
                else None
            ),
            "outcome": resident["outcome"],
            "request_sha256": frame["request_sha256"],
            "resources": resources,
            "result": resident["result"],
            "run": dict(run_receipt or {}),
            "session": resident["session"],
            "state_sha256": self.state_sha256,
            "status": status,
            "task": task,
            "task_sha256": task_sha256,
        }

    def cancel_call(
        self, *, call_id: str
    ) -> tuple[LearningComputer, Mapping[str, Any]]:
        """Return one active child with an exact resumable continuation."""

        frames = self._invocation_frames()
        if not frames["stack"] or frames["stack"][-1]["call_id"] != call_id:
            raise LearningComputerError("active resident call does not match")
        return self._return_from_call(
            frames,
            self._active_child_return(frames, status="cancelled"),
        )

    def _return_from_call(
        self,
        frames: dict[str, Any],
        child_return: Mapping[str, Any],
    ) -> tuple[LearningComputer, Mapping[str, Any]]:
        required_return_keys = {
            "arguments",
            "call_id",
            "continuation",
            "continuation_sha256",
            "dependencies",
            "kernel",
            "outcome",
            "request_sha256",
            "resources",
            "result",
            "run",
            "session",
            "schema",
            "state_sha256",
            "status",
            "task",
            "task_sha256",
        }
        if (
            not frames["stack"]
            or not isinstance(child_return, Mapping)
            or set(child_return) != required_return_keys
            or child_return.get("schema") != CHILD_RETURN_SCHEMA
        ):
            raise LearningComputerError("child return envelope is invalid")
        frame = frames["stack"][-1]
        if (
            child_return.get("call_id") != frame["call_id"]
            or child_return.get("request_sha256") != frame["request_sha256"]
            or child_return.get("status")
            not in {
                "cancelled",
                "counter-exhausted",
                "exhausted",
                "faulted",
                "halted",
            }
            or not isinstance(child_return.get("continuation"), Mapping)
            or not isinstance(child_return.get("run"), Mapping)
        ):
            raise LearningComputerError("child return identity is invalid")
        restored_child = LearningComputer.from_dict(
            child_return["continuation"]
        )
        if (
            restored_child.computer_id != self.computer_id
            or restored_child.profile != self.profile
            or restored_child.state_sha256
            != child_return.get("continuation_sha256")
            or child_return.get("state_sha256")
            != child_return.get("continuation_sha256")
        ):
            raise LearningComputerError(
                "child continuation does not match its return envelope"
            )
        for name, expected in frame["expected_return"].items():
            actual = child_return.get(name)
            if isinstance(expected, list):
                matched = actual in expected
            else:
                matched = actual == expected
            if not matched:
                raise LearningComputerError(
                    f"child return violates expected {name}"
                )
        resources = _resource_map(
            child_return["resources"], "child return resources"
        )
        if frame["allowance_id"] is not None:
            reservation = _resource_map(
                frame["reservation"],
                "resident invocation reservation",
                require_work=True,
            )
            exceeded = [
                name
                for name in ROOT_RESOURCE_NAMES
                if resources[name] > reservation[name]
            ]
            if exceeded:
                raise LearningComputerError(
                    "child return exceeds its root reservation: "
                    + ", ".join(exceeded)
                )
            root_allowance = frames["allowances"][frame["allowance_id"]]
            for name in ROOT_RESOURCE_NAMES:
                root_allowance["reserved"][name] -= reservation[name]
                root_allowance["charged"][name] += resources[name]
            root_allowance["consumed_call_ids"].append(frame["call_id"])
        child_return_sha256 = hashlib.sha256(
            _canonical(child_return)
        ).hexdigest()
        compact_return = {
            key: json.loads(_canonical(value).decode("utf-8"))
            for key, value in child_return.items()
            if key != "continuation"
        }
        compact_return["child_return_sha256"] = child_return_sha256
        compact_return["continuation"] = {
            "computer_id": restored_child.computer_id,
            "profile_sha256": restored_child.profile.fingerprint,
            "state_sha256": restored_child.state_sha256,
        }
        frames["consumed_returns"].append(
            {
                "call_id": frame["call_id"],
                "child_return_sha256": child_return_sha256,
                "return_binding": frame["return_binding"],
            }
        )
        frames["stack"].pop()
        parent_task = dict(frame["task"])
        returns = parent_task.get("invocation_returns", {})
        if not isinstance(returns, Mapping):
            raise LearningComputerError(
                "resident caller return bindings are invalid"
            )
        bound_returns = dict(returns)
        if frame["return_binding"] in bound_returns:
            raise LearningComputerError(
                "resident return binding is already occupied"
            )
        bound_returns[frame["return_binding"]] = compact_return
        parent_task["invocation_returns"] = bound_returns
        state, receipt = self._restart(
            entry=_ENTRIES[frame["kernel"]],
            values={
                "arguments": frame["arguments"],
                "frames": frames,
                "outcome": frame["outcome"],
                "result": frame["result"],
                "session": {
                    **frame["session"],
                    "status": "running",
                    "returned_call_id": frame["call_id"],
                },
                "task": parent_task,
            },
        )
        successor = replace(self, field=state)
        return successor, {
            "schema": "cassifi.learning-computer-return-receipt.v2",
            "call_id": frame["call_id"],
            "child_return": dict(child_return),
            "child_return_sha256": child_return_sha256,
            "return_binding": frame["return_binding"],
            "remaining_depth": len(frames["stack"]),
            "resources": resources,
            "restart": receipt,
            "status": child_return["status"],
            "state_sha256": successor.state_sha256,
        }

    def _schedule(
        self,
        kernel: str,
        task: Mapping[str, Any],
        session: Mapping[str, Any],
        arguments: Mapping[str, Any] | None = None,
    ) -> tuple[LearningComputer, dict[str, Any]]:
        if kernel not in _ENTRIES:
            raise LearningComputerError("kernel is not in the fixed catalog")
        state, receipt = self._restart(
            entry=_ENTRIES[kernel],
            values={
                "arguments": dict(arguments or {}),
                "task": task,
                "outcome": None,
                "result": None,
                "session": session,
            },
        )
        return replace(self, field=state), receipt

    def load(
        self,
        program: Sequence[Sequence[int]],
        *,
        left: Sequence[int] = (),
        right: Sequence[int] = (),
        entry: int = 0,
    ) -> tuple[LearningComputer, dict[str, Any]]:
        try:
            previous_task = self._value("task")
            transferable: Sequence[Mapping[str, Any]] = ()
            if (
                isinstance(previous_task, Mapping)
                and previous_task.get("schema") == SCALAR_REGIONAL_STATE_SCHEMA
                and isinstance(previous_task.get("procedure_learning"), Mapping)
            ):
                raw_transferable = previous_task["procedure_learning"].get(
                    "transferable", ()
                )
                if not isinstance(raw_transferable, list):
                    raise LearningComputerError(
                        "stored transferable procedure library is invalid"
                    )
                transferable = raw_transferable
            rows = tuple(tuple(row) for row in program)
            if not rows:
                raise LearningComputerError("program must not be empty")
            normalized = tuple(
                _canonical_instruction(
                    row, len(rows), f"program[{index}]"
                )
                for index, row in enumerate(rows)
            )
            scalar_profile = self._scalar_profile()
            compiled = CompiledFieldProgram(
                program=normalized,
                entry=int(entry),
                left=tuple(int(value) for value in left),
                right=tuple(int(value) for value in right),
                source_sha256=hashlib.sha256(
                    _canonical(
                        {
                            "program": normalized,
                            "entry": entry,
                            "left": list(left),
                            "right": list(right),
                        }
                    )
                ).hexdigest(),
                source_nodes=len(normalized),
            )
            task = regional_scalar_state(
                compiled,
                scalar_profile,
                transferable_procedures=transferable,
            )
        except (TypeError, ValueError) as exc:
            raise LearningComputerError("invalid scalar program") from exc
        return self._schedule(
            SCALAR_REGIONAL_KERNEL,
            task,
            {
                "schema": "cassifi.learning-computer-session.v1",
                "kind": "scalar",
                "status": "running",
                "source_sha256": compiled.source_sha256,
            },
        )
    def submit(
        self,
        *,
        kernel: str,
        state: Mapping[str, Any],
        kind: str | None = None,
        arguments: Mapping[str, Any] | None = None,
        steps: int = 1,
    ) -> tuple[LearningComputer, Mapping[str, Any]]:
        """Validate and start one typed task through its fixed kernel."""

        if kernel not in STANDARD_KERNEL_CATALOG.names:
            raise LearningComputerError("kernel is not in the fixed catalog")
        if not isinstance(state, Mapping):
            raise LearningComputerError(
                "regional task state must be a mapping"
            )
        if arguments is not None and not isinstance(arguments, Mapping):
            raise LearningComputerError(
                "regional task arguments must be a mapping"
            )
        if isinstance(steps, bool) or not isinstance(steps, int) or steps < 1:
            raise LearningComputerError(
                "regional admission steps must be a positive integer"
            )
        session_kind = kernel if kind is None else kind
        if (
            not isinstance(session_kind, str)
            or not session_kind
            or len(session_kind) > 256
        ):
            raise LearningComputerError(
                "regional task kind must be a bounded string"
            )
        scheduled, admission = self._schedule(
            kernel,
            state,
            {
                "schema": "cassifi.learning-computer-session.v1",
                "kind": session_kind,
                "kernel": kernel,
                "status": "running",
                "task_sha256": hashlib.sha256(
                    _canonical(state)
                ).hexdigest(),
            },
            arguments,
        )
        successor, run = scheduled.advance(steps=steps)
        return successor, {
            "schema": "cassifi.learning-computer-submit-receipt.v1",
            "kernel": kernel,
            "kind": session_kind,
            "admission": admission,
            "run": run,
            "state_sha256": successor.state_sha256,
        }

    def invoke(
        self,
        *,
        arguments: Mapping[str, Any],
        steps: int = 1,
    ) -> tuple[LearningComputer, Mapping[str, Any]]:
        """Resume resident state without crossing an authority boundary."""

        if not isinstance(arguments, Mapping):
            raise LearningComputerError(
                "regional task arguments must be a mapping"
            )
        if (
            arguments.get("operation")
            in {"authorize-action", "dispatch-action"}
            or "authority" in arguments
        ):
            raise LearningComputerError(
                "action authorization and dispatch require the owner boundary"
            )
        return self._invoke_resident(arguments=arguments, steps=steps)

    def invoke_settled(
        self,
        *,
        arguments: Mapping[str, Any],
        steps: int = 4096,
        reserve_fraction: float = 0.20,
    ) -> tuple[LearningComputer, Mapping[str, Any]]:
        """Run one request to a terminal regional state on an immutable successor."""
        if not isinstance(arguments, Mapping):
            raise LearningComputerError("regional task arguments must be a mapping")
        if (
            arguments.get("operation")
            in {"authorize-action", "dispatch-action"}
            or "authority" in arguments
        ):
            raise LearningComputerError(
                "action authorization and dispatch require the owner boundary"
            )
        if isinstance(steps, bool) or not isinstance(steps, int) or steps < 1:
            raise LearningComputerError(
                "settled invocation steps must be a positive integer"
            )
        if (
            isinstance(reserve_fraction, bool)
            or not isinstance(reserve_fraction, (int, float))
            or not math.isfinite(float(reserve_fraction))
            or not 0.0 <= float(reserve_fraction) < 1.0
        ):
            raise LearningComputerError(
                "settled reserve_fraction must be finite in [0, 1)"
            )
        reserve_fraction = float(reserve_fraction)
        original = self
        before_capacity = original._region_capacity()
        argument_capacity = before_capacity.get("arguments")
        if argument_capacity is not None:
            required_words = len(_field_regions._json_words(dict(arguments)))
            if required_words > int(argument_capacity["capacity_words"]):
                raise LearningComputerCapacityError(
                    "settled invocation arguments exceed regional capacity"
                )
        task_before = self._value("task")
        continuation = (
            task_before.get("continuation")
            if isinstance(task_before, Mapping)
            else None
        )
        continuation_partial = (
            isinstance(continuation, Mapping)
            and (
                continuation.get("request") is not None
                or bool(continuation.get("partial"))
            )
        )
        status_partial = (
            isinstance(task_before, Mapping)
            and not isinstance(continuation, Mapping)
            and task_before.get("status") in {"running", "yield", "faulted"}
        )
        if continuation_partial or status_partial:
            raise LearningComputerError(
                "settled invocation refuses an already-partial task"
            )
        remaining = steps
        try:
            local, receipt = self._invoke_resident(
                arguments=arguments,
                steps=1,
            )
        except FieldComputerError as exc:
            raise self._settled_capacity_error(exc) from exc
        except LearningComputerError as exc:
            cause = exc.__cause__
            if isinstance(cause, FieldComputerError):
                raise self._settled_capacity_error(cause) from exc
            raise
        consumed = self._settled_transitions(receipt)
        remaining -= consumed
        first_status = str(
            receipt.get("status", receipt.get("run", {}).get("status"))
        )
        if first_status == "faulted" or receipt.get("run", {}).get("status") == "faulted":
            raise LearningComputerError(
                "settled invocation encountered a kernel fault"
            )
        if (
            consumed < 1
            or local.state_sha256 == original.state_sha256
            or self._settled_no_progress(receipt)
        ):
            transitions = receipt.get("run", {}).get("transition_receipts", [])
            blocked = transitions[-1].get("blocked_reasons") if transitions else None
            raise LearningComputerError(
                f"settled invocation made no regional progress (blocked={blocked})"
            )
        receipts = [dict(receipt)]
        while True:
            if local._settled_request_complete():
                break
            status = str(receipt.get("status", receipt.get("run", {}).get("status")))
            if status in {
                "halted",
                "exhausted",
                "counter-exhausted",
                "returned",
            }:
                break
            if status == "faulted" or receipt.get("run", {}).get("status") == "faulted":
                raise LearningComputerError(
                    "settled invocation encountered a kernel fault"
                )
            if remaining <= 0:
                raise LearningComputerError(
                    "settled invocation transition budget exhausted"
                )
            before_capacity = local._region_capacity()
            previous_hash = local.state_sha256
            try:
                local, receipt = local.advance(steps=remaining)
            except LearningComputerError as exc:
                cause = exc.__cause__
                if isinstance(cause, FieldComputerError):
                    raise self._settled_capacity_error(cause) from exc
                raise
            consumed = self._settled_transitions(receipt)
            if (
                consumed < 1
                or local.state_sha256 == previous_hash
                or self._settled_no_progress(receipt)
            ):
                transitions = receipt.get("transition_receipts", [])
                blocked = transitions[-1].get("blocked_reasons") if transitions else None
                raise LearningComputerError(
                    f"settled invocation made no regional progress (blocked={blocked})"
                )
            self._check_settled_capacity(
                before_capacity,
                local._region_capacity(),
                reserve_fraction,
            )
            remaining -= consumed
            receipts.append(dict(receipt))
        self._check_settled_capacity(
            original._region_capacity(),
            local._region_capacity(),
            reserve_fraction,
        )
        return local, {
            "schema": "cassifi.learning-computer-invoke-settled-receipt.v1",
            "status": str(receipt.get("status")),
            "run": dict(receipt.get("run", {})),
            "quanta": len(receipts),
            "transitions_executed": int(steps) - remaining,
            "receipts": receipts,
            "consumed_result": local._value("result"),
            "state_sha256": local.state_sha256,
        }

    def _authorized_invoke(
        self,
        *,
        arguments: Mapping[str, Any],
        steps: int = 1,
    ) -> tuple[LearningComputer, Mapping[str, Any]]:
        """Cross the atlas-owned authority boundary for an exact action phase."""

        if (
            not isinstance(arguments, Mapping)
            or arguments.get("operation")
            not in {"authorize-action", "dispatch-action"}
            or not isinstance(arguments.get("authority"), Mapping)
        ):
            raise LearningComputerError(
                "authorized invocation requires an owner-bound action phase"
            )
        return self._invoke_resident(arguments=arguments, steps=steps)

    def _invoke_resident(
        self,
        *,
        arguments: Mapping[str, Any],
        steps: int = 1,
    ) -> tuple[LearningComputer, Mapping[str, Any]]:
        """Resume resident family state with one typed operation request."""
        session = self._value("session")
        task = self._value("task")
        if (
            not isinstance(session, Mapping)
            or not isinstance(task, Mapping)
            or not isinstance(session.get("kernel"), str)
        ):
            raise LearningComputerError(
                "no fixed-catalog regional task is resident"
            )
        if not isinstance(arguments, Mapping):
            raise LearningComputerError(
                "regional task arguments must be a mapping"
            )
        if isinstance(steps, bool) or not isinstance(steps, int) or steps < 1:
            raise LearningComputerError(
                "regional invocation steps must be a positive integer"
            )
        kernel = str(session["kernel"])
        scheduled, admission = self._schedule(
            kernel,
            task,
            {
                **dict(session),
                "status": "running",
                "invocation_sha256": hashlib.sha256(
                    _canonical(dict(arguments))
                ).hexdigest(),
            },
            arguments,
        )
        successor, run = scheduled.advance(steps=steps)
        return successor, {
            "schema": "cassifi.learning-computer-invoke-receipt.v1",
            "kernel": kernel,
            "admission": admission,
            "run": run,
            "state_sha256": successor.state_sha256,
        }

    def enqueue_event(
        self, event: Mapping[str, Any]
    ) -> tuple[LearningComputer, Mapping[str, Any]]:
        """Admit a versioned runnable event through this computer's one queue."""

        if not isinstance(event, Mapping):
            raise LearningComputerError("regional event must be an object")
        try:
            if self.is_paged:
                state, receipt = self._bounded(
                    self._controller().enqueue_event_paged, self.field, event
                )
            else:
                state, receipt = self._controller().enqueue_event(self.field, event)
            successor = replace(self, field=state)
        except FieldComputerError as exc:
            raise LearningComputerError(f"event admission failed: {exc}") from exc
        return successor, {
            **receipt,
            "computer_id": self.computer_id,
            "state_sha256": successor.state_sha256,
        }

    def cancel_communication(
        self, *, event_id: int, intent_sha256: str,
    ) -> tuple[LearningComputer, Mapping[str, Any]]:
        """Commit cancellation of one still-pending field communication."""
        try:
            if self.is_paged:
                state, receipt = self._bounded(
                    self._controller().cancel_communication,
                    self.field, event_id, intent_sha256,
                )
            else:
                state, receipt = self._controller().cancel_communication(
                    self.field, event_id, intent_sha256,
                )
        except FieldComputerError as exc:
            raise LearningComputerError(f"communication cancellation failed: {exc}") from exc
        successor = replace(self, field=state)
        return successor, {
            **receipt,
            "computer_id": self.computer_id,
            "state_sha256": successor.state_sha256,
        }

    def advance(
        self, *, steps: int
    ) -> tuple[LearningComputer, Mapping[str, Any]]:
        task_before = self._value("task")
        if (
            not isinstance(task_before, Mapping)
            or task_before.get("status") == "idle"
        ):
            raise LearningComputerError("no task is loaded")
        try:
            state, receipt = self._run(steps=steps)
            successor = replace(self, field=state)
            resident = successor._named_values(
                ("frames", "outcome", "result", "task", "session")
            )
            task = resident["task"]
            session = resident["session"]
            frames = successor._invocation_frames(resident["frames"])
            if frames["stack"]:
                run_work = receipt.get("work", 0)
                if (
                    isinstance(run_work, bool)
                    or not isinstance(run_work, int)
                    or run_work < 0
                ):
                    raise LearningComputerError(
                        "child run work accounting is invalid"
                    )
                frames["stack"][-1]["dispatch_work"] += run_work
                if receipt.get("status") in {
                    "halted",
                    "exhausted",
                    "faulted",
                    "counter-exhausted",
                }:
                    child_return = successor._active_child_return(
                        frames,
                        status=str(receipt["status"]),
                        run_receipt=receipt,
                    )
                    successor, returned = successor._return_from_call(
                        frames, child_return
                    )
                    return successor, {
                        **dict(receipt),
                        "paused": True,
                        "return": returned,
                        "state_sha256": successor.state_sha256,
                        "status": "returned",
                    }
                state, _ = successor._write_named_value("frames", frames)
                successor = replace(successor, field=state)
            if isinstance(session, Mapping) and isinstance(task, Mapping):
                scalar_session = session.get("kind") == "scalar"
                regional_session = (
                    session.get("kernel") in STANDARD_KERNEL_CATALOG.names
                    and receipt.get("status") in {
                        "running", "halted", "waiting", "exhausted",
                        "faulted", "counter-exhausted",
                    }
                )
                if scalar_session or regional_session:
                    task_status = (
                        task.get("status", "running")
                        if scalar_session else receipt["status"]
                    )
                    updated_session = {
                        **dict(session),
                        "status": task_status,
                    }
                    state, _ = successor._write_named_value(
                        "session", updated_session
                    )
                    successor = replace(successor, field=state)
            outcome = dict(receipt)
            outcome["state_sha256"] = successor.state_sha256
            if isinstance(task, Mapping):
                projected_status = task.get(
                    "status", outcome.get("status")
                )
                outcome["status"] = projected_status
                outcome["reason"] = task.get(
                    "reason", outcome.get("reason")
                )
                outcome["paused"] = projected_status in {
                    "running", "yield", "waiting"
                }
                terminal = task.get("outcome")
                if isinstance(terminal, Mapping):
                    specialization = terminal.get("specialization")
                    if isinstance(specialization, Mapping):
                        outcome["specialization"] = dict(specialization)
            return successor, outcome
        except LearningComputerResidencyWait:
            raise
        except (ResourceWait, _field_regions.ResidencyWait):
            # A wait for physical room is a request to free or widen, never a
            # fault in the advance: it keeps its continuation for the caller.
            raise
        except (TypeError, ValueError) as exc:
            raise LearningComputerError(f"computer advance failed: {exc}") from exc
    @staticmethod
    def _settled_capacity_error(exc: FieldComputerError) -> LearningComputerError:
        detail = str(exc)
        if (
            "capacity" in detail.lower()
            or "arena" in detail.lower()
            or "queue is exhausted" in detail.lower()
        ):
            return LearningComputerCapacityError(detail)
        return LearningComputerError(detail)

    def restart(
        self,
        *,
        left: Sequence[int] = (),
        right: Sequence[int] = (),
        entry: int = 0,
    ) -> tuple[LearningComputer, Mapping[str, Any]]:
        task = self._value("task")
        if (
            isinstance(task, Mapping)
            and task.get("schema") != SCALAR_REGIONAL_STATE_SCHEMA
        ):
            try:
                state, receipt = self._restart(
                    entry=int(entry),
                    values=None,
                )
            except LearningComputerResidencyWait:
                raise
            except (TypeError, ValueError) as exc:
                raise LearningComputerError("regional computer restart failed") from exc
            return replace(self, field=state), receipt
        if (
            not isinstance(task, Mapping)
            or task.get("schema") != SCALAR_REGIONAL_STATE_SCHEMA
        ):
            raise LearningComputerError("no scalar program is loaded")
        compiled = CompiledFieldProgram(
            program=tuple(
                (
                    int(row[0]),
                    int(row[1]),
                    int(row[2]),
                    int(row[3]),
                    int(row[4]),
                )
                for row in task["program"]
            ),
            entry=int(entry),
            left=tuple(int(value) for value in left),
            right=tuple(int(value) for value in right),
            source_sha256=hashlib.sha256(
                _canonical({"program": task["program"]})
            ).hexdigest(),
            source_nodes=len(task["program"]),
        )
        prepared = regional_scalar_state(compiled, self._scalar_profile())
        prepared["pc_observations"] = [
            int(value) for value in task["pc_observations"]
        ]
        prepared["procedure_learning"] = json.loads(
            _canonical(task["procedure_learning"]).decode("utf-8")
        )
        return self._schedule(
            SCALAR_REGIONAL_KERNEL,
            prepared,
            {
                "schema": "cassifi.learning-computer-session.v1",
                "kind": "scalar",
                "status": "running",
                "source_sha256": compiled.source_sha256,
            },
        )

    def grow(
        self,
        *,
        stack_capacity: int,
        max_steps: int | None = None,
        relocate_regions: bool = False,
        resource_limits: Mapping[str, Any] | None = None,
    ) -> tuple[LearningComputer, Mapping[str, Any]]:
        scalar = self._scalar_profile()
        try:
            scalar = ComputerProfile(
                program_capacity=scalar.program_capacity,
                stack_capacity=int(stack_capacity),
                max_steps=scalar.max_steps if max_steps is None else int(max_steps),
            )
            controller = self._controller()
            current = self
            field_growth: Mapping[str, Any] | None = None
            if (
                (max_steps is not None and max_steps > self.profile.max_steps)
                or stack_capacity > self.profile.mode_count
                or (relocate_regions and self.is_paged)
            ):
                controller, state, field_growth = self._grow(
                    mode_count=max(self.profile.mode_count, stack_capacity),
                    max_steps=max_steps,
                    resource_limits=resource_limits,
                    relocate_regions=relocate_regions,
                )
                current = replace(
                    self, profile=controller.profile, field=state
                )
            config = {
                "schema": "cassifi.learning-computer-config.v1",
                "scalar_profile": scalar.as_dict(),
            }
            state, config_receipt = current._write_named_value("config", config)
            current = replace(current, field=state)
            task = current._value("task")
            resumed: Mapping[str, Any] | None = None
            if (
                isinstance(task, Mapping)
                and task.get("schema")
                == SCALAR_REGIONAL_STATE_SCHEMA
            ):
                updated_task = {**dict(task), "profile": scalar.as_dict()}
                if task.get("status") == "exhausted" and task.get(
                    "reason"
                ) in {"stack_capacity", "step_budget"}:
                    updated_task.update(
                        {"status": "running", "reason": "running", "outcome": None}
                    )
                    session = current._value("session")
                    if not isinstance(session, Mapping):
                        raise LearningComputerError(
                            "scalar session is invalid"
                        )
                    current, resumed = current._schedule(
                        SCALAR_REGIONAL_KERNEL,
                        updated_task,
                        {**dict(session), "status": "running"},
                    )
                else:
                    state, resumed = current._write_named_value(
                        "task", updated_task
                    )
                    current = replace(current, field=state)
            return current, {
                "schema": SCHEMA,
                "kind": "growth",
                "field_growth": (
                    None
                    if field_growth is None
                    else dict(field_growth)
                ),
                "configuration": config_receipt,
                "resumed_task": (
                    None if resumed is None else dict(resumed)
                ),
            }
        except LearningComputerResidencyWait:
            raise
        except (TypeError, ValueError) as exc:
            raise LearningComputerError("computer growth failed") from exc

    def _select(
        self,
        source: Mapping[str, Any],
        *,
        budget: int,
        method: str | None,
    ) -> tuple[LearningComputer, Mapping[str, Any]]:
        task = policy_regional_state(
            source,
            policy=self._value("policy"),
            learn=False,
            method=method,
            lifetime_budget=budget,
        )
        compiled = compile_source(source)
        current, _ = self._schedule(
            "learning.computation-policy",
            task,
            {
                "schema": "cassifi.learning-computer-session.v1",
                "kind": "selection",
                "status": "running",
                "source_sha256": compiled.sha256,
            },
        )
        state, _ = current._run()
        current = replace(current, field=state)
        outcome = current._value("outcome")
        if not isinstance(outcome, Mapping) or outcome.get("status") != "selected":
            raise LearningComputerError("method selection did not complete")
        return current, outcome

    def _finish_solver(
        self,
        source: Mapping[str, Any],
        *,
        elapsed_ns: int,
    ) -> tuple[LearningComputer, Mapping[str, Any]]:
        task = self._value("task")
        session = self._value("session")
        if not isinstance(task, Mapping) or not isinstance(session, Mapping):
            raise LearningComputerError("solver state is invalid")
        result = task.get("result")
        if not isinstance(result, Mapping):
            raise LearningComputerError("solver terminal result is absent")
        compiled = compile_source(source)
        audit = audit_result(compiled, result)
        current = self
        observation = None
        if bool(session.get("learn")):
            feedback_id = hashlib.sha256(
                _canonical(
                    {
                        "computer_id": self.computer_id,
                        "source_sha256": compiled.sha256,
                        "method": session["method"],
                        "result_sha256": hashlib.sha256(
                            _canonical(result)
                        ).hexdigest(),
                        "predecessor": session["selection_state_sha256"],
                    }
                )
            ).hexdigest()
            policy_task = policy_regional_state(
                source,
                policy=self._value("policy"),
                learn=True,
                method=str(session["method"]),
                lifetime_budget=int(session["lifetime_budget"]),
                feedback={
                    "id": feedback_id,
                    "method": session["method"],
                    "status": result["status"],
                    "elapsed_ns": max(1, int(elapsed_ns)),
                    "work": int(session["spent_work"]),
                },
            )
            current, _ = self._schedule(
                "learning.computation-policy",
                policy_task,
                {
                    **dict(session),
                    "status": "learning",
                    "feedback_id": feedback_id,
                },
            )
            field, _ = current._run()
            current = replace(current, field=field)
            completed_policy = current._value("task")
            observation = completed_policy["result"]["observation"]
            field, _ = current._write_named_value(
                "policy",
                completed_policy["continuation"]["policy"],
            )
            current = replace(current, field=field)
        terminal_session = {
            **dict(session),
            "status": "terminal",
            "result_status": result["status"],
            "learning_applied": observation is not None,
        }
        field, _ = current._write_named_value("session", terminal_session)
        current = replace(current, field=field)
        field, _ = current._write_named_value("outcome", result)
        current = replace(current, field=field)
        return current, {
            "schema": "cassifi.learning-computer-solve-receipt.v3",
            "status": result["status"],
            "method": session["method"],
            "selection": session["selection"],
            "result": result,
            "audit": audit,
            "observation": observation,
            "continuation": None,
            "state_sha256": current.state_sha256,
        }

    def _run_solver(
        self,
        source: Mapping[str, Any],
        *,
        budget: int,
    ) -> tuple[LearningComputer, Mapping[str, Any]]:
        if isinstance(budget, bool) or not isinstance(budget, int) or budget < 1:
            raise LearningComputerError("budget must be a positive integer")
        session = self._value("session")
        if not isinstance(session, Mapping) or session.get("kind") != "solve":
            raise LearningComputerError("no regional solver task is active")
        started = time.perf_counter_ns()
        field, run_receipt = self._run(steps=budget)
        elapsed = max(1, time.perf_counter_ns() - started)
        current = replace(self, field=field)
        task = current._value("task")
        if not isinstance(task, Mapping):
            raise LearningComputerError("regional solver task is invalid")
        spent = int(task["ledger"]["primitive_work"])
        updated_session = {**dict(session), "spent_work": spent}
        field, _ = current._write_named_value("session", updated_session)
        current = replace(current, field=field)
        if task.get("result") is None:
            return current, {
                "schema": "cassifi.learning-computer-solve-receipt.v3",
                "status": "running",
                "method": session["method"],
                "selection": session["selection"],
                "result": None,
                "audit": None,
                "observation": None,
                "continuation": {
                    "source_sha256": session["source_sha256"],
                    "method": session["method"],
                    "spent_work": spent,
                    "remaining_lifetime_budget": max(
                        0, int(session["lifetime_budget"]) - spent
                    ),
                    "learning_deferred": bool(session["learn"]),
                },
                "run": run_receipt,
                "state_sha256": current.state_sha256,
            }
        return current._finish_solver(source, elapsed_ns=elapsed)

    def solve(
        self,
        source: Mapping[str, Any],
        *,
        budget: int = 2000,
        learn: bool = True,
        method: str | None = None,
        max_field_bytes: int = 134_217_728,
        lifetime_budget: int = 4096,
    ) -> tuple[LearningComputer, Mapping[str, Any]]:
        if method is not None and method not in METHODS:
            raise LearningComputerError("unknown computation method")
        compiled = compile_source(source)
        selected_computer, selection = self._select(
            source, budget=budget, method=method
        )
        selected_method = str(selection["method"])
        try:
            solver_profile = _profile_for(
                compiled,
                selected_method,
                hybrid_budget=lifetime_budget,
                search_budget=lifetime_budget,
                max_field_bytes=max_field_bytes,
            )
            task = constraint_regional_state(compiled, solver_profile)
        except (TypeError, ValueError) as exc:
            raise LearningComputerError("regional solver admission failed") from exc
        current, _ = selected_computer._schedule(
            CONSTRAINT_KERNEL,
            task,
            {
                "schema": "cassifi.learning-computer-session.v1",
                "kind": "solve",
                "status": "running",
                "source_sha256": compiled.sha256,
                "method": selected_method,
                "selection": selection["selection"],
                "selection_state_sha256": selected_computer.state_sha256,
                "learn": bool(learn),
                "lifetime_budget": int(lifetime_budget),
                "spent_work": 0,
                "replaced_task": (
                    isinstance(self._value("session"), Mapping)
                    and self._value("session").get("status") == "running"
                ),
            },
        )
        return current._run_solver(source, budget=budget)

    def continue_solve(
        self,
        source: Mapping[str, Any],
        *,
        budget: int = 2000,
        max_field_bytes: int = 134_217_728,
    ) -> tuple[LearningComputer, Mapping[str, Any]]:
        del max_field_bytes
        session = self._value("session")
        compiled = compile_source(source)
        if (
            not isinstance(session, Mapping)
            or session.get("kind") != "solve"
            or session.get("status") != "running"
        ):
            raise LearningComputerError("no solver continuation is available")
        if session.get("source_sha256") != compiled.sha256:
            raise LearningComputerError(
                "continued source differs from retained solver source"
            )
        return self._run_solver(source, budget=budget)


class ResidentModelCycle:
    """One field-owned task cycle with a single regional write at the boundary.

    The existing program and model kernels still choose and admit every stage.
    Only the repeated full-field serialization between stages is deferred; the
    owner keeps the neural membrane candidate private over the same interval.
    """

    def __init__(self, computer: LearningComputer, task_id: str) -> None:
        from programs.runtime.kernel import REGIONAL_KERNEL_NAME, REGIONAL_STATE_SCHEMA

        session, task = (
            computer.named_value("session"),
            computer.named_value("task"),
        )
        model_task = task.get("tasks", {}).get(task_id) if isinstance(task, Mapping) else None
        if (
            not isinstance(session, Mapping)
            or session.get("kernel") != REGIONAL_KERNEL_NAME
            or not isinstance(task, dict)
            or task.get("schema") != REGIONAL_STATE_SCHEMA
            or not isinstance(model_task, dict)
            or model_task.get("kind") != "model"
            or not isinstance(model_task.get("state"), dict)
        ):
            raise LearningComputerError("resident model cycle has no field-owned model task")
        self._computer = computer
        self._task_id = task_id
        self._task = task
        self._work = 0
        self._dispatches = 0
        self._closed = False

    @property
    def runtime_state(self) -> Mapping[str, Any]:
        return self._task

    def advance(
        self, *, arguments: Mapping[str, Any], quantum: int
    ) -> Mapping[str, Any]:
        from programs.runtime.kernel import _advance_task

        if self._closed:
            raise LearningComputerError("resident model cycle has already committed")
        if not isinstance(arguments, Mapping) or not isinstance(quantum, int) or isinstance(quantum, bool) or quantum < 1:
            raise LearningComputerError("resident model cycle requires typed positive work")
        try:
            _, work, _ = _advance_task(
                self._task, self._task_id,
                arguments=arguments, quantum=quantum, project=False,
            )
        except (ResourceWait, LearningComputerResidencyWait):
            raise
        except ValueError as exc:
            raise LearningComputerError(f"resident model cycle fault: {exc}") from exc
        self._work += work
        self._dispatches += 1
        model_task = self._task["tasks"][self._task_id]
        return {
            "status": model_task["status"],
            "phase": model_task["state"]["phase"],
            "work": work,
        }

    def finish(self) -> tuple[LearningComputer, Mapping[str, Any]]:
        from programs.runtime.kernel import REGIONAL_KERNEL_NAME

        if self._closed or not self._dispatches:
            raise LearningComputerError("resident model cycle has no unsettled work")
        try:
            state, _ = self._computer._write_named_value("task", self._task)
            successor = replace(self._computer, field=state)
            session = successor.named_value("session")
            task_status = self._task["tasks"][self._task_id]["status"]
            if session.get("status") != task_status:
                state, _ = successor._write_named_value(
                    "session", {**session, "status": task_status},
                )
                successor = replace(successor, field=state)
        except (ResourceWait, LearningComputerResidencyWait):
            raise
        except ValueError as exc:
            if "region value exceeds allocated capacity" in str(exc):
                raise LearningComputerCapacityError(str(exc)) from exc
            raise LearningComputerError(f"resident model cycle commit failed: {exc}") from exc
        self._closed = True
        return successor, {
            "schema": "cassifi.learning-computer-invoke-receipt.v1",
            "kernel": REGIONAL_KERNEL_NAME,
            "admission": {"task_id": self._task_id, "dispatches": self._dispatches},
            "run": {"status": task_status, "work": self._work},
            "state_sha256": successor.state_sha256,
        }