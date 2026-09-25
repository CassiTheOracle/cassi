"""CassiQwen's exact work-memory boundary over the current CassiFI field.

The adapter deliberately has two ownership paths:

* exact source bytes are archived by :class:`FieldIntelligenceOwner`;
* semantic indexing, selection, and query state live in one owner-operated
  ``LearningComputer`` running the current ``cognition.field`` kernel.

The archive is evidence, not adaptive memory.  The regional computer is the
only adaptive field path used by this adapter; no legacy atlas/chart relation
is configured or queried here.
"""

from __future__ import annotations

import base64
import threading
import hashlib
import http.client
import json
import math
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence, cast
from urllib.parse import urlparse
from cassi_model_instrument import (
    AdapterCapabilities,
    CoupledTransactionJournal,
    NumericEnvelope,
    QwenNativeInstrument,
    UnsupportedCapability,
    differential_field_state,
)
from surface.visual_adapter import analyze_field_surface_page


_CASSIFI_ROOT = Path(__file__).resolve().parents[1] / "CassiFI"
_REQUIRED_CASSIFI_FILES = tuple(
    _CASSIFI_ROOT / name
    for name in (
        "cassi_alias_cut_field.py",
        "cassi_alias_exact_one_field.py",
        "cassi_alias_obstruction.py",
        "cassi_clause_field.py",
        "cassi_computation_policy.py",
        "cassi_constraint_dynamics.py",
        "cassi_constraint_field.py",
        "cassi_constraint_implication.py",
        "cassi_cubic_reduction.py",
        "cassi_field_affect.py",
        "cassi_field_atlas.py",
        "cassi_field_cognition.py",
        "cassi_field_open_vocab.py",
        "cassi_math_language.py",
        "cassi_field_computer.py",
        "cassi_field_owner.py",
        "cassi_field_program.py",
        "cassi_field_regions.py",
        "cassi_field_transceiver.py",
        "cassi_general_matched_field.py",
        "cassi_hybrid_inference.py",
        "cassi_python_universal.py",
        "cassi_learning_computer.py",
        "cassi_mixed_exact_one_field.py",
        "cassi_regional_catalog.py",
        "cassi_resonant_field.py",
        "cassi_temporal_field.py",
        "cassi_temporal_inquiry.py",
        "cassi_variational_field.py",
    )
)
if not all(path.is_file() for path in _REQUIRED_CASSIFI_FILES):
    raise RuntimeError("CassiFI current regional implementation is unavailable")
if str(_CASSIFI_ROOT) not in sys.path:
    sys.path.insert(0, str(_CASSIFI_ROOT))

from cassi_field_cognition import (
    SEMANTIC_STATE_SCHEMA,
    semantic_cognition_state,
    semantic_cognition_kernel,
    semantic_cognition_state,
)
from cassi_field_owner import CapacityLimits, FieldIntelligenceOwner, SourceInput
from cassi_field_regions import (
    RegionalProfile,
    resolve_semantic_record,
)
from cassi_resonant_field import REGIONAL_KERNEL_NAME, ResonantProfile, regional_state
from cassi_regional_catalog import STANDARD_KERNEL_CATALOG


MEMORY_SCHEMA = "cassi.field-qwen.memory-record.v2"
RECALL_SCHEMA = "cassi.field-qwen.recall.v2"
OWNERSHIP_SCHEMA = "cassi.field-qwen.ownership.v2"
REGIONAL_RECEIPT_SCHEMA = "cassi.field-qwen.regional-field-receipt.v2"
PUBLICATION_GATE_SCHEMA = "cassi.field-qwen.publication-gate.v1"
CONTINUATION_SCHEMA = "cassi.field-qwen.continuation-receipt.v1"
COGNITION_KERNEL = "cognition.field"
COMPUTER_ID = "field-qwen:work-memory"
EMBODIED_CIRCULATION_COMPUTER_ID = "field-qwen:embodied-circulation"
EMBODIED_CIRCULATION_MODE_COUNT = 65_536
FIELD_RESOURCE_FEEDBACK_SCHEMA = "cassi.field-qwen-resource-feedback.v1"
RESIDENT_BRAIN_RESOURCE_FEEDBACK_SCHEMA = "cassi.resident-qwen-resource-feedback.v1"
SEMANTIC_SCOPE = "field-qwen-work-memory"
SEMANTIC_FRAME = "cassi-field-qwen-regional-memory-v2"
# Fixed boundary transducer used when the field's own recalled records must
# reach the emitter; it adds no adaptive state and the caller cannot override
# the field-selected memory block.
EMISSION_OUTPUT_CONTRACT = (
    "Reply with the requested value only, using the field work memory."
)

# The emitter decodes the frame into a 256-token context and appends generated
# tokens, so the frame is fitted to a measured token ceiling.  Fitting uses the
# runtime's own tokenizer because bytes-per-token varies from 2.3 to 4.8 with
# content (hex digests tokenize far more finely than prose).
EMISSION_FRAME_TOKEN_CEILING = 224

# These are the production defaults resolved by LearningComputer for a
# mapping profile.  Keeping the requested profile explicit makes reopen fail
# closed if a different computer is found under this adapter's identity.
COMPUTER_PROFILE: Mapping[str, Any] = {
    # LearningComputer scales named regions above its 65,536-mode
    # compatibility image.  The persistent semantic state is the mind and
    # lives in one task region whose capacity is 1.5 words per mode; this
    # allocation held 1.26 MB of registered state in measurement, which is a
    # sustained research program's worth of cycles.  A program that writes past
    # it is answered by growing the field in 50% steps up to the owner's
    # workspace budget
    # (CassiFieldWorkMemory._try_grow_region_capacity), and a reopen adopts
    # that grown allocation only while the rest of this profile still
    # fingerprints identically.
    "mode_count": 196_608,
    "directory_capacity": 256,
    "max_native_work": 32,
}
SEMANTIC_BOUNDS: Mapping[str, int] = {
    # Research frontiers need alternatives, learned procedures need multi-step
    # trajectories, and a continuing resident research program legitimately
    # revises one semantic identity across many cycles. Keep that history
    # bounded but large enough for a sustained program rather than exhausting
    # after eight ordinary decisions.
    "max_observations": 32,
    "max_operations": 4_096,
    "max_records": 4_096,
    "max_timeline": 4_096,
    "max_versions": 128,
    "max_work": 4_096,
}
SEMANTIC_SETTLEMENT_LIMIT = (
    (
        int(SEMANTIC_BOUNDS["max_work"])
        + int(COMPUTER_PROFILE["max_native_work"])
        - 1
    )
    // int(COMPUTER_PROFILE["max_native_work"])
    + 2
)

# The persistent semantic graph is the owner's adaptive memory, so recovery
# from a faulted or exhausted regional computer re-seats the state that was
# already there instead of a fresh frame.  These are the keys the regional
# semantic constructor installs; runtime additions such as the task's
# continuation diagnostics are deliberately excluded.
SEMANTIC_STATE_KEYS = (
    "schema",
    "family",
    "status",
    "scope",
    "frame",
    "invocation_returns",
    "invalidation",
    "records",
    "current",
    "indexes",
    "time",
    "beliefs",
    "libraries",
    "continuation",
    "last_result",
    "ledger",
    "bounds",
)
FAULT_DISPOSITIONS = ("faulted", "exhausted", "counter-exhausted")
# A capacity fault is answered by growing the field, and the grown allocation
# must still hold the state that did not fit, so a few bounded growth steps are
# attempted before the recovery reports the field as unrecoverable.
RECOVERY_GROWTH_STEPS = 3

_CONTEXT_VALUE_TYPES = (str, int, bool, type(None))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


_DIAGNOSIS_KEYS = (
    "error",
    "error_code",
    "code",
    "diagnosis",
    "failure",
    "reason",
    "message",
    "status",
)


def _semantic_diagnosis(inspected: Mapping[str, Any]) -> str:
    """Render the kernel's own account of a faulted semantic task.

    A faulted request is only actionable if the kernel's failure code reaches
    the caller, so the task, session, and outcome values are scanned for the
    first bounded diagnosis instead of reporting a bare status.
    """

    found: list[str] = []

    def visit(node: Any, depth: int = 0) -> None:
        if depth > 3 or len(found) >= 4:
            return
        if isinstance(node, Mapping):
            for key in _DIAGNOSIS_KEYS:
                value = node.get(key)
                if isinstance(value, str) and value:
                    found.append(f"{key}={value[:200]}")
                elif isinstance(value, Mapping):
                    for inner in _DIAGNOSIS_KEYS:
                        text = value.get(inner)
                        if isinstance(text, str) and text:
                            found.append(f"{key}.{inner}={text[:200]}")
            for value in node.values():
                if isinstance(value, (Mapping, list)):
                    visit(value, depth + 1)
        elif isinstance(node, list):
            for value in node[:4]:
                if isinstance(value, (Mapping, list)):
                    visit(value, depth + 1)

    for container in ("task", "session", "outcome", "consumed_result"):
        visit(inspected.get(container))
    return "; ".join(found[:4]) if found else "no diagnosis reported"


def _receipt_fault_detail(result: Any) -> str | None:
    """Return the regional fault a computer receipt reports, if any.

    A regional dispatch that raises inside its instruction does not reach the
    caller as an exception: the operation returns a paused receipt whose
    transition rows carry the instruction's own failure text.  Reading it is
    what distinguishes a capacity fault from an invalid operation.
    """

    if not isinstance(result, Mapping):
        return None
    receipt = result.get("receipt")
    if not isinstance(receipt, Mapping):
        receipt = result
    for entry in receipt.get("transition_receipts") or ():
        if not isinstance(entry, Mapping):
            continue
        detail = entry.get("fault_detail")
        if isinstance(detail, str) and detail:
            return detail
    if receipt.get("reason") == "kernel-fault":
        return "kernel-fault"
    return None


def _json_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a JSON object")
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    decoded = json.loads(encoded)
    if not isinstance(decoded, dict):
        raise ValueError(f"{label} must be a JSON object")
    return decoded


def _context(value: Mapping[str, Any]) -> dict[str, Any]:
    row = _json_object(value, "memory context")
    if not row:
        raise ValueError("memory context must be nonempty")
    for key, item in row.items():
        if (
            not isinstance(key, str)
            or not key
            or not isinstance(item, _CONTEXT_VALUE_TYPES)
            or isinstance(item, float) and not math.isfinite(item)
        ):
            raise ValueError("memory context values must be finite JSON scalars")
    return row


def _tree_bytes(root: Path) -> int:
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cassifi_source_identity() -> Mapping[str, Any]:
    """Hash the complete current production closure used by this adapter."""

    rows = {path.name: _sha256_path(path) for path in _REQUIRED_CASSIFI_FILES}
    return {
        "root": str(_CASSIFI_ROOT),
        "implementation": "field-intelligence-owner-plus-regional-learning-computer",
        "kernel": COGNITION_KERNEL,
        "files": rows,
        "aggregate_sha256": hashlib.sha256(
            json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
    }


@dataclass(frozen=True, slots=True)
class WorkMemoryRecord:
    """One exact, revisable work record admitted into CassiFI."""

    source_id: str
    context: Mapping[str, Any]
    payload: Mapping[str, Any]
    observed_timestamp: str
    labels: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or not self.source_id:
            raise ValueError("source_id must be nonempty")
        if not isinstance(self.observed_timestamp, str) or not self.observed_timestamp:
            raise ValueError("observed_timestamp must be nonempty")
        object.__setattr__(self, "context", _context(self.context))
        object.__setattr__(self, "payload", _json_object(self.payload, "memory payload"))
        object.__setattr__(self, "labels", tuple(str(value) for value in self.labels))

    def document(self) -> Mapping[str, Any]:
        return {
            "context": dict(self.context),
            "observed_timestamp": self.observed_timestamp,
            "payload": dict(self.payload),
            "schema": MEMORY_SCHEMA,
            "source_id": self.source_id,
        }


class CassiFieldWorkMemory:
    """Exact evidence plus one owner-operated semantic regional computer."""

    def __init__(
        self,
        data_home: Path,
        *,
        limits: CapacityLimits | None = None,
        resource_limits: Mapping[str, Any] | Any | None = None,
        profile_overrides: Mapping[str, int] | None = None,
    ) -> None:
        requested_profile = dict(COMPUTER_PROFILE)
        if profile_overrides is not None:
            unknown = set(profile_overrides) - set(requested_profile)
            if unknown:
                raise ValueError(
                    f"unknown regional profile overrides: {sorted(unknown)}"
                )
            for name, value in profile_overrides.items():
                if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                    raise ValueError(
                        f"regional profile override {name!r} must be a positive integer"
                    )
                requested_profile[name] = value
        self.data_home = Path(data_home).resolve()
        self._profile_values = requested_profile
        if resource_limits is None:
            self._resource_limits: Mapping[str, Any] | None = None
        elif hasattr(resource_limits, "as_dict") and callable(resource_limits.as_dict):
            self._resource_limits = dict(resource_limits.as_dict())
        elif isinstance(resource_limits, Mapping):
            self._resource_limits = dict(resource_limits)
        else:
            raise TypeError("resource_limits must be a mapping or resource policy")
        self.owner = FieldIntelligenceOwner(self.data_home, limits=limits)
        # A field that was grown to survive a capacity fault stays grown: the
        # stored allocation is the authority whenever it exceeds the request,
        # otherwise reopen would reject the very field it is opening.
        stored = tuple(
            row
            for row in self.owner.state.computers
            if row.computer_id == COMPUTER_ID
        )
        if stored:
            self._profile_values["mode_count"] = max(
                int(self._profile_values["mode_count"]),
                int(stored[0].profile.mode_count),
            )
        self._embodied_circulation_lock = threading.Lock()
        self._closed = False
        self._ensure_regional_computer()
        if self._resource_limits is not None and stored:
            self._update_resource_policy(self._resource_limits)
    
    def __enter__(self) -> "CassiFieldWorkMemory":
        return self

    def __exit__(self, _exc_type: Any, _exc: Any, _traceback: Any) -> None:
        self.close()

    def open_hive(
        self,
        *,
        hive_home: Path | None = None,
        hive_id: str = "main",
        branch: str = "main",
        instance_id: str = "auto",
        session_id: str = "auto",
        role: str = "worker",
        mode: str = "isolated",
        metadata: Mapping[str, Any] | None = None,
        **policy_overrides: Any,
    ) -> Any:
        """Attach this workbench to the durable Cassi Hive control plane.

        The workbench remains the owner of the adaptive field.  The returned
        session owns only the hive store and closes without closing this
        workbench, so callers can use it as a nested context manager.
        """

        from cassi_hive_runtime import HiveField

        return HiveField.attach(
            self,
            field_home=self.data_home,
            hive_home=hive_home,
            hive_id=hive_id,
            branch=branch,
            instance_id=instance_id,
            session_id=session_id,
            role=role,
            mode=mode,
            profile_sha256=self._profile().fingerprint,
            metadata=metadata,
            **policy_overrides,
        )

    def close(self) -> None:
        if not self._closed:
            self.owner.close()
            self._closed = True

    def computer_resources(
        self, computer_id: str = COMPUTER_ID
    ) -> Mapping[str, Any]:
        """Read the configured policy and measured residency for one computer.

        The work-memory field is the default, so its own callers name no
        computer while the entity asks about any computer the owner holds.
        """

        return dict(self.owner.computer_resources(computer_id))

    def ensure_embodied_circulation(self) -> Mapping[str, Any]:
        """Ensure the entity's owner-resident resonant spectrum is circulating.

        Formation is a declared host activation, not an observation or a
        research outcome. The bounded impulse is charged by the resonant
        kernel; later assessed outcomes tune this measured exchange.
        """
        with self._embodied_circulation_lock:
            existing = tuple(
                row
                for row in self.owner.state.computers
                if row.computer_id == EMBODIED_CIRCULATION_COMPUTER_ID
            )
            if len(existing) > 1:
                raise RuntimeError(
                    "entity circulation computer identity is ambiguous"
                )
            if existing:
                diagnostics = self.owner.circulation_diagnostics(
                    EMBODIED_CIRCULATION_COMPUTER_ID
                )
                regional = diagnostics.get("regional_circulation")
                spectrum = (
                    regional.get("spectrum")
                    if isinstance(regional, Mapping)
                    else None
                )
                history = (
                    spectrum.get("history")
                    if isinstance(spectrum, Mapping)
                    else None
                )
                ledger = (
                    regional.get("ledger")
                    if isinstance(regional, Mapping)
                    else None
                )
                if (
                    not isinstance(history, Sequence)
                    or isinstance(history, (str, bytes))
                    or not any(
                        isinstance(exchange, Mapping)
                        and exchange.get("kind") == "exchange"
                        for exchange in history
                    )
                    or not isinstance(ledger, Mapping)
                    or float(ledger.get("exchanges", 0.0)) <= 0.0
                ):
                    raise RuntimeError(
                        "persisted entity circulation computer has no measured "
                        "exchange; refusing to replace its regional state"
                    )
                return diagnostics

            configure_arguments: dict[str, Any] = {
                "profile": {"mode_count": EMBODIED_CIRCULATION_MODE_COUNT}
            }
            if self._resource_limits is not None:
                configure_arguments["resource_limits"] = dict(self._resource_limits)
            configured = self.owner.operate_computer(
                "field-qwen:embodied-circulation:configure:v1",
                computer_id=EMBODIED_CIRCULATION_COMPUTER_ID,
                action="configure",
                arguments=configure_arguments,
                expected_state_sha256=self.owner.state.state_sha256,
            )
            _require(
                configured.get("receipt", {}).get("action") == "configure",
                "entity circulation computer configuration was not committed",
            )
            profile = ResonantProfile(ports_per_pool=4)
            state = regional_state(
                profile=profile,
                impulse={
                    "pool_signal": [1.0, 0.5, -0.5, 0.25, -0.25, 0.75, -1.0],
                    "work_budget": 0.25,
                    "evidence_tick": 0,
                    "event_kind": "formation",
                },
                circulation=True,
            )
            submitted = self.owner.operate_computer(
                "field-qwen:embodied-circulation:formation:v1",
                computer_id=EMBODIED_CIRCULATION_COMPUTER_ID,
                action="submit",
                arguments={
                    "kernel": REGIONAL_KERNEL_NAME,
                    "state": state,
                    "arguments": {"operation": "circulate", "ticks": 1},
                    "steps": 4096,
                },
                expected_state_sha256=self.owner.state.state_sha256,
            )
            _require(
                submitted.get("receipt", {}).get("action") == "submit",
                "entity circulation formation was not committed",
            )
            diagnostics = self.owner.circulation_diagnostics(
                EMBODIED_CIRCULATION_COMPUTER_ID
            )
            regional = diagnostics.get("regional_circulation")
            spectrum = (
                regional.get("spectrum")
                if isinstance(regional, Mapping)
                else None
            )
            history = (
                spectrum.get("history")
                if isinstance(spectrum, Mapping)
                else None
            )
            ledger = (
                regional.get("ledger")
                if isinstance(regional, Mapping)
                else None
            )
            if (
                not isinstance(history, Sequence)
                or isinstance(history, (str, bytes))
                or not any(
                    isinstance(exchange, Mapping)
                    and exchange.get("kind") == "exchange"
                    for exchange in history
                )
                or not isinstance(ledger, Mapping)
                or float(ledger.get("exchanges", 0.0)) <= 0.0
            ):
                raise RuntimeError(
                    "entity circulation formation did not produce a measured "
                    "spectral exchange"
                )
            return diagnostics

    def resident_resource_feedback(
        self,
        brain_feedback: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        """Pair measured resident-Qwen work with live field limits and usage.

        The brain receipt contains no model text; it is a source-bound runtime
        measurement. The field report remains the owner's read-only resource
        view and is not changed by composing the two observations.
        """
        brain = _json_object(brain_feedback, "resident brain resource feedback")
        if brain.get("schema") != RESIDENT_BRAIN_RESOURCE_FEEDBACK_SCHEMA:
            raise ValueError("resident brain resource feedback schema is unsupported")
        model_id = brain.get("model_id")
        source_sha256 = brain.get("source_sha256")
        backend = brain.get("backend")
        task_id = brain.get("task_id")
        operation_id = brain.get("operation_id")
        activity_id = brain.get("activity_id")
        measured = brain.get("measured")
        if (
            not isinstance(model_id, str)
            or not model_id
            or not isinstance(source_sha256, str)
            or len(source_sha256) != 64
            or any(character not in "0123456789abcdef" for character in source_sha256)
            or not isinstance(backend, str)
            or backend not in {"cpu", "vulkan"}
            or not isinstance(task_id, str)
            or not task_id
            or not isinstance(operation_id, str)
            or len(operation_id) != 64
            or any(character not in "0123456789abcdef" for character in operation_id)
            or (
                activity_id is not None
                and (
                    not isinstance(activity_id, str)
                    or not activity_id.strip()
                    or len(activity_id.encode("utf-8")) > 512
                )
            )
            or not isinstance(measured, Mapping)
        ):
            raise ValueError("resident brain resource feedback identity is invalid")
        metric_names = (
            "elapsed_ns",
            "segment_count",
            "segment_work_ns",
            "max_segment_ns",
            "scheduler_yield_ns",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
        )
        if "warm_request_cost_ns" in measured:
            metric_names += ("warm_request_cost_ns",)
        for name in metric_names:
            value = measured.get(name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"resident brain resource metric {name!r} is invalid")
        if (
            measured["total_tokens"]
            != measured["prompt_tokens"] + measured["completion_tokens"]
        ):
            raise ValueError("resident brain token totals are inconsistent")
        placement = brain.get("placement")
        if placement is not None:
            if (
                not isinstance(placement, Mapping)
                or placement.get("requested") not in {"cpu", "vulkan", "auto"}
                or placement.get("actual") != backend
                or not isinstance(placement.get("reason"), str)
                or not placement["reason"]
            ):
                raise ValueError("resident brain placement feedback is invalid")
        normalized_brain = {
            "schema": RESIDENT_BRAIN_RESOURCE_FEEDBACK_SCHEMA,
            "task_id": task_id,
            "operation_id": operation_id,
            "activity_id": activity_id,
            "model_id": model_id,
            "source_sha256": source_sha256,
            "backend": backend,
            "measured": {name: measured[name] for name in metric_names},
        }
        if placement is not None:
            normalized_brain["placement"] = dict(placement)
        return {
            "schema": FIELD_RESOURCE_FEEDBACK_SCHEMA,
            "resident_brain": normalized_brain,
            "field_computer": dict(self.computer_resources()),
        }


    def _update_resource_policy(
        self,
        resource_limits: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        limits = dict(resource_limits)
        before = self.owner.state.state_sha256
        result = self.owner.operate_computer(
            self._owner_operation_id(
                "computer-resources",
                f"{before}:{json.dumps(limits, sort_keys=True, separators=(',', ':'))}",
            ),
            computer_id=COMPUTER_ID,
            action="resources",
            arguments={"limits": limits},
            expected_state_sha256=before,
        )
        receipt = result.get("receipt")
        committed = receipt.get("resource_limits") if isinstance(receipt, Mapping) else None
        _require(
            isinstance(receipt, Mapping)
            and receipt.get("action") == "resources"
            and receipt.get("computer_id") == COMPUTER_ID
            and isinstance(committed, Mapping)
            and all(committed.get(key) == value for key, value in limits.items()),
            "regional work-memory resource policy was not committed",
        )
        return result

    def operate_computer(
        self,
        operation_id: str,
        *,
        computer_id: str = COMPUTER_ID,
        action: str,
        arguments: Mapping[str, Any] | None = None,
        expected_state_sha256: str | None = None,
    ) -> Mapping[str, Any]:
        """Forward one owner-computer operation through the workbench."""

        return self.owner.operate_computer(
            operation_id,
            computer_id=computer_id,
            action=action,
            arguments=arguments,
            expected_state_sha256=expected_state_sha256,
        )

    def place_pages(
        self,
        operation_id: str,
        *,
        pages: Sequence[Any],
        tier: str,
        root_sha256: str | None = None,
        max_pages: int | None = None,
        continuation: Mapping[str, Any] | None = None,
        expected_state_sha256: str | None = None,
    ) -> Mapping[str, Any]:
        """Place authorized field pages and return the ordinary owner receipt."""

        normalized_pages = [
            dict(page) if isinstance(page, Mapping) else page for page in pages
        ]
        arguments: dict[str, Any] = {"pages": normalized_pages, "tier": tier}
        if root_sha256 is not None:
            arguments["root_sha256"] = root_sha256
        if max_pages is not None:
            arguments["max_pages"] = max_pages
        if continuation is not None:
            arguments["continuation"] = dict(continuation)
        return self.operate_computer(
            operation_id,
            action="place",
            arguments=arguments,
            expected_state_sha256=expected_state_sha256,
        )

    def surface_page_features(
        self, publication: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        """Read an immutable visual page from the field owner as bounded cues.

        The page stays in the owner and the derived features are an ephemeral
        measurement, not a parallel store or a claim that the brain saw pixels.
        """
        if self._closed:
            raise RuntimeError("work-memory field is closed")
        return analyze_field_surface_page(self.owner, publication)


    def admit_surface_guidance(self, event: Mapping[str, Any]) -> Mapping[str, Any]:
        """Archive an entity-authenticated research delivery and observe it in the field.

        The entity passes the stored ``delivery_event`` only after its route
        authentication and source-publication checks. This method independently
        validates the append-only event digest and canonical guidance payload,
        then binds both the exact source record and a semantic Event to that
        publication revision.
        """
        if self._closed:
            raise RuntimeError("work-memory field is closed")
        _require(
            isinstance(event, Mapping),
            "surface guidance event must be a mapping",
        )

        def text(value: Any, label: str) -> str:
            _require(
                isinstance(value, str)
                and bool(value)
                and len(value.encode("utf-8")) <= 512
                and not any(ord(character) < 32 for character in value),
                f"surface guidance {label} must be bounded nonempty text",
            )
            return value

        def integer(value: Any, label: str, minimum: int = 0) -> int:
            _require(
                isinstance(value, int)
                and not isinstance(value, bool)
                and value >= minimum,
                f"surface guidance {label} must be an integer >= {minimum}",
            )
            return value

        event_digest = text(event.get("digest"), "event digest")
        _require(
            len(event_digest) == 64
            and all(character in "0123456789abcdef" for character in event_digest),
            "surface guidance event digest is not lowercase SHA-256",
        )
        event_body = {key: value for key, value in event.items() if key != "digest"}
        event_body_bytes = json.dumps(
            event_body, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        _require(
            hashlib.sha256(event_body_bytes).hexdigest() == event_digest,
            "surface guidance research event digest does not match its body",
        )
        _require(
            event.get("schema") == "cassi.entity.research-event.v1"
            and event.get("kind") == "program-guidance",
            "surface guidance must be a stored program-guidance research event",
        )
        event_id = text(event.get("event_id"), "event identity")
        program_id = text(event.get("program_id"), "program identity")
        integer(event.get("sequence"), "event sequence", 1)
        recorded_at = text(event.get("recorded_at"), "event recorded time")
        event_payload = event.get("payload")
        _require(
            isinstance(event_payload, Mapping),
            "surface guidance event payload is invalid",
        )
        request_id = text(event_payload.get("request_id"), "request identity")
        _require(
            event_id == f"{request_id}:program-guidance",
            "surface guidance event identity does not match its request",
        )
        integer(event_payload.get("generation"), "program generation", 1)
        content = event_payload.get("content")
        _require(
            isinstance(content, str) and bool(content),
            "surface guidance content is missing",
        )
        try:
            guidance = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError("surface guidance content is not JSON") from exc
        _require(
            isinstance(guidance, Mapping)
            and json.dumps(
                guidance, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            )
            == content,
            "surface guidance content must be canonical JSON",
        )
        _require(
            guidance.get("schema") == "cassi.surface.guidance.v1",
            "surface guidance content has an unsupported schema",
        )
        instruction = guidance.get("instruction")
        _require(
            isinstance(instruction, str) and bool(instruction.strip()),
            "surface guidance instruction must be nonempty text",
        )
        source = guidance.get("source")
        _require(isinstance(source, Mapping), "surface guidance source is invalid")
        source_identity = {
            "binding_id": text(source.get("binding_id"), "binding identity"),
            "source_id": text(source.get("source_id"), "source identity"),
            "source_instance": text(source.get("source_instance"), "source instance"),
            "environment_incarnation": text(
                source.get("environment_incarnation"), "environment incarnation"
            ),
            "source_generation": integer(
                source.get("source_generation"), "source generation", 1
            ),
            "source_epoch": integer(source.get("source_epoch"), "source epoch", 1),
            "geometry_revision": integer(
                source.get("geometry_revision"), "geometry revision"
            ),
            "width": integer(source.get("width"), "source width", 1),
            "height": integer(source.get("height"), "source height", 1),
            "pixel_format": text(source.get("pixel_format"), "pixel format"),
            "sample_time_ns": (
                None
                if source.get("sample_time_ns") is None
                else integer(source.get("sample_time_ns"), "sample time")
            ),
            "receipt_time_ns": integer(source.get("receipt_time_ns"), "receipt time"),
        }
        _require("annotation" in source, "surface guidance source annotation is missing")

        source_event_ref = {
            "event_id": event_id,
            "kind": "program-guidance",
            "digest": event_digest,
        }
        source_id = "surface-guidance:" + hashlib.sha256(
            f"{event_id}\0{event_digest}".encode("utf-8")
        ).hexdigest()
        record = WorkMemoryRecord(
            source_id=source_id,
            context={
                "kind": "surface-guidance",
                "binding_id": source_identity["binding_id"],
                "source_id": source_identity["source_id"],
                "source_generation": source_identity["source_generation"],
                "source_epoch": source_identity["source_epoch"],
                "geometry_revision": source_identity["geometry_revision"],
            },
            payload={
                "schema": "cassi.surface.guidance.v1",
                "guidance": dict(guidance),
                "source_event_ref": source_event_ref,
                "program_id": program_id,
                "request_id": request_id,
            },
            observed_timestamp=recorded_at,
            labels=("surface-guidance",),
        )
        learned = self.learn(record)
        source_revision_id = learned.get("source_revision_id")
        _require(
            isinstance(source_revision_id, str) and bool(source_revision_id),
            "surface guidance archive did not return a source revision",
        )
        guidance_observation = {
            "schema": "cassi.surface.guidance.v1",
            "instruction": instruction,
            "annotation": source["annotation"],
            "source_event_ref": source_event_ref,
            "source_revision_id": source_revision_id,
            **source_identity,
        }
        semantic_source = {
            "kind": "surface-guidance",
            "source_revision_id": source_revision_id,
            "source_event_ref": source_event_ref,
            "observation": {"surface_guidance": guidance_observation},
        }
        semantic_result = self.semantic(
            {
                "operation": "observe",
                "operation_id": self._semantic_operation_id(
                    "surface-guidance-observe", source_revision_id
                ),
                "delivery_id": self._semantic_operation_id(
                    "surface-guidance-delivery", source_revision_id
                ),
                "event_id": self._semantic_operation_id(
                    "surface-guidance-event", source_revision_id
                ),
                "source": semantic_source,
                "observations": [
                    {
                        "binding_id": f"surface-guidance:{source_revision_id}",
                        "subject": program_id,
                        "attribute": "human-marked-moment",
                        "value": {
                            "instruction": instruction,
                            "annotation": source["annotation"],
                            "source_event_ref": source_event_ref,
                        },
                    }
                ],
                "support_roots": [source_revision_id],
            },
            operation_label=f"surface-guidance-observe:{source_revision_id}",
        )
        observed = semantic_result.get("result")
        _require(
            isinstance(observed, Mapping) and observed.get("status") == "supported",
            "surface guidance semantic observation was not supported",
        )
        raw_event_ref = observed.get("event")
        _require(
            isinstance(raw_event_ref, Mapping)
            and raw_event_ref.get("kind") == "Event"
            and isinstance(raw_event_ref.get("id"), str)
            and isinstance(raw_event_ref.get("content_version"), int)
            and not isinstance(raw_event_ref.get("content_version"), bool)
            and raw_event_ref.get("content_version", 0) >= 1,
            "surface guidance observation did not return a semantic Event reference",
        )
        event_ref = {
            "id": raw_event_ref["id"],
            "kind": "Event",
            "content_version": raw_event_ref["content_version"],
        }
        inspection = self._computer_inspect().get("task")
        _require(
            isinstance(inspection, Mapping),
            "surface guidance semantic state is unavailable",
        )
        current = inspection.get("current")
        records = inspection.get("records")
        _require(
            isinstance(current, Mapping)
            and isinstance(records, Mapping)
            and isinstance(current.get("Event"), Mapping),
            "surface guidance semantic Event index is unavailable",
        )
        current_ref = current["Event"].get(event_ref["id"])
        _require(
            isinstance(current_ref, Mapping)
            and current_ref.get("content_version") == event_ref["content_version"],
            "surface guidance semantic Event is not current",
        )
        event_record = resolve_semantic_record(
            records, current_ref, require_current=True
        )
        _require(
            event_record.get("kind") == "Event"
            and event_record.get("status") == "active"
            and event_record.get("epistemic_kind") == "observed"
            and source_revision_id in event_record.get("support_roots", []),
            "surface guidance semantic Event is not an active source-supported observation",
        )
        persisted_payload = event_record.get("payload")
        persisted_source = (
            persisted_payload.get("source")
            if isinstance(persisted_payload, Mapping)
            else None
        )
        _require(
            isinstance(persisted_source, Mapping)
            and isinstance(persisted_source.get("observation"), Mapping)
            and persisted_source["observation"].get("surface_guidance")
            == guidance_observation,
            "surface guidance semantic Event did not preserve its source identity",
        )
        experience = {
            "event_ref": event_ref,
            "source_revision_id": source_revision_id,
            "semantic_receipt": semantic_result,
        }
        return {
            "schema": "cassi.field-qwen.surface-guidance.v1",
            "status": "admitted",
            "event_ref": event_ref,
            "experience": experience,
            "source_event_ref": source_event_ref,
            "source_revision_id": source_revision_id,
            "binding_id": source_identity["binding_id"],
            "source_id": source_identity["source_id"],
            "source_instance": source_identity["source_instance"],
            "environment_incarnation": source_identity["environment_incarnation"],
            "source_generation": source_identity["source_generation"],
            "source_epoch": source_identity["source_epoch"],
            "geometry_revision": source_identity["geometry_revision"],
            "verification": {
                "research_event_digest": "self-consistent",
                "guidance_content": "canonical",
                "semantic_event": "active-observed",
            },
        }

    def _profile(self) -> RegionalProfile:
        return RegionalProfile(
            **self._profile_values,
            kernel_names=STANDARD_KERNEL_CATALOG.names,
        )

    def _profile_dict(self) -> Mapping[str, Any]:
        return self._profile().as_dict()

    def _computer_row(self) -> Any:
        matches = tuple(
            row
            for row in self.owner.state.computers
            if row.computer_id == COMPUTER_ID
        )
        _require(
            len(matches) == 1,
            "CassiFI work memory requires one current work-memory computer",
        )
        row = matches[0]
        _require(
            row.profile.fingerprint == self._profile().fingerprint,
            "CassiFI work-memory regional profile differs from the current implementation",
        )
        _require(
            row.profile.catalog_sha256 == self._profile().catalog_sha256,
            "CassiFI work-memory kernel catalog differs from the current implementation",
        )
        return row

    def _computer_inspect(self) -> Mapping[str, Any]:
        inspection = self.owner.inspect_computers()
        rows = inspection.get("computers") if isinstance(inspection, Mapping) else None
        matches = (
            [
                row
                for row in rows
                if isinstance(row, Mapping)
                and row.get("computer_id") == COMPUTER_ID
            ]
            if isinstance(rows, list)
            else []
        )
        _require(
            len(matches) == 1,
            "CassiFI work memory regional computer inspection is incomplete",
        )
        return matches[0]

    def inspect_current_obligations(
        self, *, prefix: str
    ) -> list[Mapping[str, Any]]:
        """Read latest current obligation records without publishing a transition."""
        task = self._computer_inspect().get("task")
        _require(
            isinstance(task, Mapping)
            and isinstance(task.get("current"), Mapping)
            and isinstance(task.get("records"), Mapping),
            "regional semantic obligation state is unavailable",
        )
        current = task["current"]
        obligations = current.get("Obligation")
        records = task["records"]
        _require(
            isinstance(obligations, Mapping),
            "regional current obligation family is unavailable",
        )
        result: list[Mapping[str, Any]] = []
        for identity in sorted(
            str(value) for value in obligations
            if isinstance(value, str) and value.startswith(prefix)
        ):
            history = records.get(identity)
            if not isinstance(history, list) or not history:
                continue
            record = history[-1]
            if isinstance(record, Mapping):
                result.append({
                    "id": identity,
                    "status": record.get("status"),
                    "payload": record.get("payload"),
                })
        return result

    def _named_value_region(
        self,
        name: str,
        *,
        inspected: Mapping[str, Any] | None = None,
    ) -> Mapping[str, int]:
        """Return allocation and occupancy from the public computer inspection."""
        measured = self._computer_inspect() if inspected is None else inspected
        capacities = measured.get("region_capacity")
        region = capacities.get(name) if isinstance(capacities, Mapping) else None
        if isinstance(region, Mapping):
            return {
                "capacity_words": int(region["capacity_words"]),
                "used_words": int(region["used_words"]),
            }
        raise RuntimeError(f"regional named value region is unavailable: {name}")

    def _preserved_semantic_state(
        self,
        inspected: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        """Return the semantic state currently seated in the task, if any."""

        task = inspected.get("task")
        if not isinstance(task, Mapping) or task.get("schema") != SEMANTIC_STATE_SCHEMA:
            return None
        preserved = {
            key: task[key] for key in SEMANTIC_STATE_KEYS if key in task
        }
        return preserved if preserved.get("records") is not None else None

    @staticmethod
    def _void_pending_continuation(preserved: Mapping[str, Any]) -> dict[str, Any]:
        """Return the preserved state with any in-flight operation dropped.

        A restart discards the pending event.  The operation that was in flight
        when the field faulted never landed, and what it left in the task can be
        the partial write that crossed the region boundary in the first place.
        The settled state -- records, current appraisals, indexes, ledger -- is
        what recovery re-seats; the continuation returns to idle so the larger
        allocation receives a state that is valid on its own terms.
        """

        state = dict(preserved)
        continuation = state.get("continuation")
        if not (isinstance(continuation, Mapping) and continuation.get("request") is not None):
            return state
        state["status"] = "waiting"
        state["continuation"] = {
            "cursor": 0,
            "operation_id": None,
            "partial": {},
            "proposal": None,
            "request": None,
            "request_sha256": None,
        }
        # The lost operation's result is no more real than its continuation, and
        # the state validates a last result against the ledger.  The last
        # operation that did land is the honest one to report.
        ledger = state.get("ledger")
        receipts = ledger.get("operation_receipts") if isinstance(ledger, Mapping) else None
        indexes = state.get("indexes")
        operations = indexes.get("operations") if isinstance(indexes, Mapping) else None
        settled = None
        if isinstance(receipts, list) and receipts and isinstance(operations, Mapping):
            row = operations.get(receipts[-1].get("operation_id"))
            if isinstance(row, Mapping) and isinstance(row.get("result"), Mapping):
                settled = dict(row["result"])
        state["last_result"] = settled or semantic_cognition_state()["last_result"]
        return state

    @staticmethod
    def _fault_disposition(inspected: Mapping[str, Any]) -> str | None:
        """Name the disposition that blocks settlement, computer or session."""

        status = inspected.get("status")
        if status in FAULT_DISPOSITIONS:
            return f"computer:{status}"
        session = inspected.get("session")
        if isinstance(session, Mapping) and session.get("status") in FAULT_DISPOSITIONS:
            return f"session:{session['status']}"
        return None

    def _try_grow_region_capacity(self, *, label: str) -> int | None:
        """Grow the work-memory field so its task region can hold the state.

        A semantic write that exceeds the allocated region faults the field,
        and the regional implementation's own remedy for that is growth: the
        field is re-laid into a larger allocation with its header, regions and
        records copied.  The owner's action takes the regional stack capacity,
        which is the field's mode count.  The grown allocation is adopted here
        so reopen, fingerprint checks and later growth steps agree on one
        profile.  Growth is refused, not raised, when the owner's workspace
        budget is already met: the caller can still restart and keep the mind
        it has.
        """

        row = self._computer_row()
        current = int(row.profile.mode_count)
        step = max(65_536, current // 2)
        target = current + step
        limit = int(getattr(self.owner.limits, "max_workspace_bytes", 0) or 0)
        bytes_per_mode = max(1, int(row.nbytes) // max(1, current))
        if limit:
            allowed = max(1, (limit - 1) // bytes_per_mode)
            target = min(target, allowed)
        if target <= current:
            return None
        before = self.owner.state.state_sha256
        self.owner.operate_computer(
            self._owner_operation_id("computer-grow", f"{label}:{before}"),
            computer_id=COMPUTER_ID,
            action="grow",
            arguments={"stack_capacity": target},
            expected_state_sha256=before,
        )
        self._profile_values["mode_count"] = target
        grown = self._computer_row()
        _require(
            int(grown.profile.mode_count) == target,
            "regional work-memory field growth was not committed",
        )
        return target

    def _recover_faulted_computer(
        self,
        *,
        label: str,
        detail: str | None = None,
    ) -> Mapping[str, Any]:
        """Restart the regional computer after a fault and re-seat its state.

        A faulted regional computer keeps reporting its fault until it is
        restarted, so every later request would fail without touching the
        faulted operation.  The semantic state is preserved across the
        restart: the field's memory is the mind's, and a recovery that
        discarded it would silently reset the program.  A fault that names
        regional capacity is answered by growing the field, which is the
        regional implementation's own remedy, and by resubmitting the
        preserved state into the larger allocation.
        """

        inspected = self._computer_inspect()
        preserved = self._preserved_semantic_state(inspected)
        if preserved is not None:
            preserved = self._void_pending_continuation(preserved)
        capacity_hint = detail is not None and "capacity" in detail.lower()
        growth = "regional work-memory field is at its workspace growth limit"
        last_error: str | None = None
        for attempt in range(RECOVERY_GROWTH_STEPS + 1):
            if attempt or capacity_hint:
                target = self._try_grow_region_capacity(label=f"{label}:grow:{attempt}")
                if target is None:
                    growth = (
                        "regional work-memory field cannot grow further within "
                        "its workspace limit"
                    )
                else:
                    growth = None
                    inspection = self._computer_inspect()
                    grown = self._preserved_semantic_state(inspection)
                    if grown is not None:
                        preserved = self._void_pending_continuation(grown)
            before = self.owner.state.state_sha256
            self.owner.operate_computer(
                self._owner_operation_id(
                    "computer-restart",
                    f"{label}:{before}",
                ),
                computer_id=COMPUTER_ID,
                action="restart",
                arguments={"entry": 0},
                expected_state_sha256=before,
            )
            inspection = self._computer_inspect()
            session = inspection.get("session")
            session_faulted = (
                isinstance(session, Mapping)
                and session.get("status") in FAULT_DISPOSITIONS
            )
            task = inspection.get("task")
            seated = (
                isinstance(task, Mapping)
                and task.get("schema") == SEMANTIC_STATE_SCHEMA
            )
            if not seated or session_faulted or self._fault_disposition(inspection):
                digest = hashlib.sha256(
                    json.dumps(
                        preserved,
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=False,
                        default=str,
                    ).encode("utf-8")
                ).hexdigest()[:12]
                try:
                    self._submit_semantic_state(
                        label=f"{label}:restore:{digest}:{attempt}",
                        state=preserved,
                    )
                except Exception as error:  # a state too large to seat is a capacity fault
                    last_error = f"{type(error).__name__}: {error}"[:300]
                    capacity_hint = True
                    continue
                inspection = self._computer_inspect()
            fault = self._fault_disposition(inspection)
            if fault is None:
                if preserved is None:
                    return inspection
                restored = self._preserved_semantic_state(inspection)
                _require(
                    isinstance(restored, Mapping)
                    and restored.get("records") == preserved.get("records")
                    and restored.get("current") == preserved.get("current"),
                    "regional work-memory recovery did not preserve the semantic state",
                )
                return inspection
            last_error = fault
            capacity_hint = True
        raise RuntimeError(
            "regional work-memory computer could not recover: "
            f"detail={detail or last_error or 'none'} "
            f"growth={growth or 'grown'} "
            f"diagnosis={_semantic_diagnosis(inspected)}"
        )

    def _adopt_stored_growth(self) -> None:
        """Adopt a work-memory field the mind has already grown in place.

        A capacity fault is answered by growing the regional field, which
        re-lays the same profile into a larger allocation.  A reopen must
        recognize that field as its own, so the stored allocation is adopted
        when the rest of the profile still fingerprints identically; a
        genuinely different computer under this identity still fails closed.
        """

        matches = tuple(
            row
            for row in self.owner.state.computers
            if row.computer_id == COMPUTER_ID
        )
        if len(matches) != 1:
            return
        stored = matches[0].profile
        current = int(self._profile_values["mode_count"])
        if int(stored.mode_count) <= current:
            return
        candidate = dict(self._profile_values)
        candidate["mode_count"] = int(stored.mode_count)
        probe = RegionalProfile(
            **candidate,
            kernel_names=STANDARD_KERNEL_CATALOG.names,
        )
        _require(
            probe.fingerprint == stored.fingerprint
            and probe.catalog_sha256 == stored.catalog_sha256,
            "CassiFI work-memory regional profile differs from the current implementation",
        )
        self._profile_values = candidate

    def _ensure_regional_computer(self) -> None:
        usage = self.owner.inspect().get("capacity", {}).get("usage", {})
        existing = tuple(
            row for row in self.owner.state.computers
            if row.computer_id == COMPUTER_ID
        )
        self._adopt_stored_growth()
        if not existing:
            adaptive_keys = (
                "variables",
                "charts",
                "programs",
                "predictions",
                "plans",
                "macros",
            )
            if any(int(usage.get(key, 0)) for key in adaptive_keys):
                raise RuntimeError(
                    "CassiFI work memory contains legacy adaptive state; refusing an implicit atlas migration"
                )
            configure_arguments: dict[str, Any] = {"profile": self._profile_dict()}
            if self._resource_limits is not None:
                configure_arguments["resource_limits"] = dict(self._resource_limits)
            configured = self.owner.operate_computer(
                "field-qwen:computer:configure:v2",
                computer_id=COMPUTER_ID,
                action="configure",
                arguments=configure_arguments,
                expected_state_sha256=self.owner.state.state_sha256,
            )
            _require(
                configured.get("receipt", {}).get("action") == "configure",
                "regional work-memory computer configuration was not committed",
            )
        row = self._computer_row()
        if not row.is_paged and row.nbytes >= 256 * 1024 * 1024:
            # A grown semantic field is mostly empty; retain its exact image
            # while limiting each future transition to the pages it touches.
            adopted = self.owner.operate_computer(
                "field-qwen:computer:adopt-paged:v1",
                computer_id=COMPUTER_ID,
                action="adopt-paged",
                arguments={"resident_pages": 96},
                expected_state_sha256=self.owner.state.state_sha256,
            )
            _require(
                adopted.get("receipt", {}).get("paged") is True,
                "regional work-memory computer did not adopt bounded residency",
            )
        inspection = self._computer_inspect()
        if self._fault_disposition(inspection) is not None:
            inspection = self._recover_faulted_computer(
                label=f"{SEMANTIC_FRAME}:open"
            )
        task = inspection.get("task")
        if not isinstance(task, Mapping):
            raise RuntimeError("regional work-memory computer task is unavailable")
        if task.get("schema") == "cassifi.learning-computer-idle.v1":
            self._submit_semantic_state()
        else:
            _require(
                task.get("schema") == SEMANTIC_STATE_SCHEMA,
                "regional work-memory computer is not running cognition.field semantic state",
            )

    def _owner_operation_id(self, kind: str, label: str) -> str:
        token = hashlib.sha256(label.encode("utf-8")).hexdigest()[:32]
        return f"field-qwen:{kind}:{token}"

    def _semantic_operation_id(self, kind: str, label: str) -> str:
        token = hashlib.sha256(label.encode("utf-8")).hexdigest()[:40]
        return f"field-qwen:semantic:{kind}:{token}"

    def _semantic_state_request(self, operation_id: str) -> Mapping[str, Any]:
        return {
            "operation": "inspect",
            "operation_id": operation_id,
        }

    def _submit_semantic_state(
        self,
        *,
        label: str = SEMANTIC_FRAME,
        state: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        semantic_operation_id = self._semantic_operation_id("initialize", label)
        if state is None:
            seats = semantic_cognition_state(
                scope=SEMANTIC_SCOPE,
                frame=SEMANTIC_FRAME,
                bounds=SEMANTIC_BOUNDS,
            )
        else:
            seats = dict(state)
            seats["status"] = "waiting"
        result = self.owner.operate_computer(
            self._owner_operation_id("computer-submit", label),
            computer_id=COMPUTER_ID,
            action="submit",
            arguments={
                "kernel": COGNITION_KERNEL,
                "state": seats,
                "arguments": self._semantic_state_request(semantic_operation_id),
                "steps": 1,
            },
            expected_state_sha256=self.owner.state.state_sha256,
        )
        task = self._computer_inspect().get("task")
        _require(
            isinstance(task, Mapping) and task.get("schema") == SEMANTIC_STATE_SCHEMA,
            "regional work-memory semantic state was not installed",
        )
        return result

    def _settle_semantic(
        self,
        *,
        label: str,
        inspected: Mapping[str, Any],
        detail: str | None = None,
    ) -> tuple[Mapping[str, Any], int]:
        """Drain a bounded semantic continuation through the owner surface.

        Returns the settled inspection together with the number of recoveries
        performed: a recovery restarts the regional program, which discards
        the events that were pending for it, so a caller with an in-flight
        request must reissue it rather than treat the drained task as its
        answer.
        """

        current = inspected
        recoveries = 0
        for continuation_index in range(SEMANTIC_SETTLEMENT_LIMIT):
            task = current.get("task")
            _require(
                isinstance(task, Mapping)
                and task.get("schema") == SEMANTIC_STATE_SCHEMA,
                "regional work-memory semantic task disappeared during settlement",
            )
            fault = self._fault_disposition(current)
            if fault is not None:
                # A capacity fault can recur after one growth step while the
                # state still does not fit, so recovery is bounded by the
                # number of growth steps rather than by the loop position.
                if recoveries <= RECOVERY_GROWTH_STEPS:
                    recoveries += 1
                    self._recover_faulted_computer(
                        label=f"{label}:recover:{recoveries}",
                        detail=detail,
                    )
                    current = self._computer_inspect()
                    continue
                raise RuntimeError(
                    "regional work-memory semantic request faulted before "
                    f"settlement: disposition={fault} detail={detail or 'none'} "
                    f"diagnosis={_semantic_diagnosis(current)}"
                )
            continuation = task.get("continuation")
            _require(
                isinstance(continuation, Mapping),
                "regional work-memory semantic continuation is unavailable",
            )
            if continuation.get("request") is None:
                return current, recoveries
            before = self.owner.state.state_sha256
            advance = self.owner.operate_computer(
                self._owner_operation_id(
                    "computer-advance",
                    f"{label}:{continuation_index}:{before}",
                ),
                computer_id=COMPUTER_ID,
                action="advance",
                arguments={"steps": int(SEMANTIC_BOUNDS["max_work"])},
                expected_state_sha256=before,
            )
            detail = _receipt_fault_detail(advance) or detail
            current = self._computer_inspect()
        raise RuntimeError(
            "regional work-memory semantic request exceeded its bounded settlement budget"
        )

    def _invoke_semantic(
        self,
        *,
        label: str,
        request: Mapping[str, Any],
    ) -> tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]]:
        """Invoke one semantic request and settle it to a real answer.

        A recovery during settlement restarts the regional program, which
        discards the events pending for it, so the request is reissued under
        its own semantic operation identity (an exact replay of an already
        executed request returns its recorded result) until the settle
        completes without a recovery.
        """

        result: Mapping[str, Any] | None = None
        for attempt in range(RECOVERY_GROWTH_STEPS + 2):
            _settled, _ = self._settle_semantic(
                label=label,
                inspected=self._computer_inspect(),
            )
            before = self.owner.state.state_sha256
            result = self.owner.operate_computer(
                self._owner_operation_id(
                    "computer-invoke",
                    f"{label}:{attempt}:{before}",
                ),
                computer_id=COMPUTER_ID,
                action="invoke",
                arguments={"arguments": dict(request), "steps": 1},
                expected_state_sha256=before,
            )
            inspect, recoveries = self._settle_semantic(
                label=label,
                inspected=self._computer_inspect(),
                detail=_receipt_fault_detail(result),
            )
            if not recoveries:
                break
        else:
            raise RuntimeError(
                "regional work-memory semantic request was discarded by field "
                "recovery after every bounded reissue: "
                f"operation={dict(request).get('operation')!r} "
                f"label={label}"
            )
        task = inspect.get("task")
        _require(
            isinstance(task, Mapping) and task.get("schema") == SEMANTIC_STATE_SCHEMA,
            "regional work-memory semantic task disappeared after invocation",
        )
        last_result = task.get("last_result")
        _require(
            isinstance(last_result, Mapping),
            "regional work-memory semantic invocation produced no result",
        )
        return result, last_result, inspect

    def _active_source_for_id(self, source_id: str) -> Any | None:
        matches = []
        for revision_id in self.owner.evidence.active_revision_ids():
            source = self.owner.evidence.source(revision_id)
            if source.source_id == source_id:
                matches.append(source)
        if len(matches) > 1:
            raise RuntimeError(f"CassiFI has multiple active revisions for {source_id}")
        return matches[0] if matches else None

    def _active_source(self, revision_id: str) -> Any:
        active_ids = set(self.owner.evidence.active_revision_ids())
        _require(revision_id in active_ids, "semantic result named a non-active evidence revision")
        source = self.owner.evidence.source(revision_id)
        _require(source.status == "active", "semantic result named a non-active source")
        return source

    def _current_bindings(
        self,
        inspected: Mapping[str, Any] | None = None,
        *,
        include_dormant: bool = False,
    ) -> tuple[Mapping[str, Any], ...]:
        task = (self._computer_inspect() if inspected is None else inspected).get("task")
        if not isinstance(task, Mapping):
            return ()
        current = task.get("current", {})
        records = task.get("records", {})
        refs = current.get("Binding", {}) if isinstance(current, Mapping) else {}
        if not isinstance(refs, Mapping) or not isinstance(records, Mapping):
            return ()
        resolved: list[Mapping[str, Any]] = []
        for reference in refs.values():
            if not isinstance(reference, Mapping):
                continue
            record_id = reference.get("id")
            version = reference.get("content_version")
            history = records.get(record_id)
            if (
                not isinstance(record_id, str)
                or isinstance(version, bool)
                or not isinstance(version, int)
                or version < 1
                or not isinstance(history, list)
                or version > len(history)
                or not isinstance(history[version - 1], Mapping)
            ):
                raise RuntimeError("CassiFI semantic binding reference is not resolvable")
            row = history[version - 1]
            _require(
                row.get("id") == record_id and row.get("kind") == "Binding",
                "CassiFI semantic binding reference is mistyped",
            )
            status = row.get("status")
            if status == "active" or (include_dormant and status == "dormant"):
                resolved.append(row)
        return tuple(resolved)

    def _active_binding(
        self,
        context: Mapping[str, Any],
        *,
        source_id: str | None = None,
    ) -> Mapping[str, Any] | None:
        matches: list[Mapping[str, Any]] = []
        for value in self._current_bindings():
            scope = value.get("scope")
            payload = value.get("payload")
            if not isinstance(scope, Mapping) or not isinstance(payload, Mapping):
                continue
            if scope.get("kind") != SEMANTIC_SCOPE:
                continue
            if scope.get("context") != dict(context):
                continue
            if source_id is not None and payload.get("source_id") != source_id:
                continue
            matches.append(value)
        if len(matches) > 1:
            raise RuntimeError("CassiFI work memory has multiple bindings for one source and context")
        return matches[0] if matches else None

    def archive_research_result(
        self,
        *,
        operation_id: str,
        program_id: str,
        content: bytes,
        observed_timestamp: str,
    ) -> Mapping[str, str]:
        """Archive an exact research result through the same serialized memory seam."""
        source = SourceInput(
            source_id=f"entity-research-result:{operation_id}",
            content=content,
            media_type="application/json",
            codec="utf-8",
            observed_timestamp=observed_timestamp,
            scope="entity-research",
            claim_category="tool-result",
            fidelity="exact-record",
        )
        self.owner.archive_source(
            operation_id=f"{operation_id}:archive-result",
            source=source,
            context={"program_id": program_id, "operation_id": operation_id},
            event_kind="entity-research-result",
        )
        return {
            "source_id": source.source_id,
            "source_revision_id": source.revision_id,
            "source_content_sha256": hashlib.sha256(content).hexdigest(),
        }

    def _archive_record(
        self,
        record: WorkMemoryRecord,
        source: SourceInput,
    ) -> Mapping[str, Any]:
        return self.owner.archive_source(
            operation_id=self._owner_operation_id("archive", source.revision_id),
            source=source,
            context={
                "adapter": "cassi-field-qwen",
                "record_context": dict(record.context),
                "source_id": record.source_id,
            },
            epistemic_type="observed",
            event_kind="work-memory",
        )

    def _binding_request(
        self,
        *,
        record: WorkMemoryRecord,
        source: SourceInput,
        operation_id: str,
    ) -> Mapping[str, Any]:
        return {
            "operation": "register",
            "operation_id": operation_id,
            "record_id": f"field-qwen:binding:{record.source_id}",
            "kind": "Binding",
            "payload": {
                "source_id": record.source_id,
                "source_revision_id": source.revision_id,
                "schema": MEMORY_SCHEMA,
            },
            "scope": {
                "kind": SEMANTIC_SCOPE,
                "context": dict(record.context),
            },
            "support_roots": [source.revision_id],
            "epistemic_kind": "observed",
        }

    def learn(self, record: WorkMemoryRecord) -> Mapping[str, Any]:
        """Archive exact bytes, then register one binding in cognition.field."""
        content = json.dumps(
            record.document(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        prior = self._active_source_for_id(record.source_id)
        prior_binding = (
            None
            if prior is None
            else self._active_binding(
                record.context,
                source_id=record.source_id,
            )
        )
        prior_binding_ref = (
            None
            if not isinstance(prior_binding, Mapping)
            else {
                "id": prior_binding["id"],
                "kind": prior_binding["kind"],
                "content_version": prior_binding["content_version"],
            }
        )
        affected_relevance: list[Mapping[str, Any]] = []
        if prior_binding_ref is not None:
            task = self._computer_inspect().get("task")
            if isinstance(task, Mapping):
                current_programs = task.get("current", {}).get("Program", {})
                records = task.get("records", {})
                if isinstance(current_programs, Mapping) and isinstance(
                    records, Mapping
                ):
                    for reference in current_programs.values():
                        candidate = resolve_semantic_record(
                            records, reference, require_current=True
                        )
                        payload = candidate.get("payload", {})
                        if (
                            payload.get("memory_role")
                            == "relevance-condition"
                            and prior_binding_ref
                            in payload.get("target_refs", [])
                        ):
                            affected_relevance.append(dict(payload))
        if prior is not None and self.owner.evidence.read(prior) == content:
            binding = self._active_binding(record.context, source_id=record.source_id)
            if (
                isinstance(binding, Mapping)
                and binding.get("payload", {}).get("source_revision_id") == prior.revision_id
            ):
                regional = self.regional_field_receipt()
                return {
                    "schema": MEMORY_SCHEMA,
                    "status": "unchanged",
                    "source_revision_id": prior.revision_id,
                    "binding_id": binding.get("id"),
                    "event_id": (
                        self.owner.evidence.events_for_source(prior.revision_id)[-1].event_id
                        if self.owner.evidence.events_for_source(prior.revision_id)
                        else None
                    ),
                    "state_sha256": regional["field_state_sha256"],
                    "generation": self.owner.state.generation,
                    "regional_field": regional,
                }

        source = SourceInput(
            source_id=record.source_id,
            content=content,
            media_type="application/json",
            codec="utf-8",
            observed_timestamp=record.observed_timestamp,
            scope=SEMANTIC_SCOPE,
            claim_category="work-record",
            fidelity="exact-record",
            parent_revision_id=None if prior is None else prior.revision_id,
            labels=record.labels,
        )
        archive = self._archive_record(record, source)
        semantic_id = self._semantic_operation_id("register", source.revision_id)
        _, semantic_result, computer = self._invoke_semantic(
            label=f"register:{source.revision_id}",
            request=self._binding_request(
                record=record,
                source=source,
                operation_id=semantic_id,
            ),
        )
        binding = self._active_binding(record.context, source_id=record.source_id)
        _require(
            isinstance(binding, Mapping)
            and binding.get("payload", {}).get("source_revision_id") == source.revision_id,
            "new record is not the current cognition.field binding",
        )
        binding_ref = {
            "id": binding["id"],
            "kind": binding["kind"],
            "content_version": binding["content_version"],
        }
        rebound_relevance: list[Mapping[str, Any]] = []
        for condition_payload in affected_relevance:
            targets = [
                binding_ref if target == prior_binding_ref else dict(target)
                for target in condition_payload["target_refs"]
            ]
            rebound_relevance.append(
                self.register_relevance(
                    condition_id=str(condition_payload["condition_id"]),
                    condition=condition_payload["condition"],
                    target_refs=targets,
                    reason=condition_payload["reason"],
                    priority=float(condition_payload["priority"]),
                    cooldown_events=int(
                        condition_payload["cooldown_events"]
                    ),
                    operation_label=(
                        "source-correction-rebind:"
                        f"{source.revision_id}:"
                        f"{condition_payload['condition_id']}"
                    ),
                )
            )
        reconsideration = None
        if prior is not None:
            reconsideration = self.match_relevance(
                event_id=f"source-correction:{source.revision_id}",
                context={
                    "event_kind": "source-correction",
                    "source_id": record.source_id,
                    "prior_source_revision_id": prior.revision_id,
                    "source_revision_id": source.revision_id,
                    "workspace": record.context.get("workspace"),
                    "project_id": record.context.get("project_id"),
                },
                maximum=32,
                operation_label=f"source-correction:{source.revision_id}",
            )
        regional = self.regional_field_receipt()
        event = archive.get("event", {})
        return {
            "schema": MEMORY_SCHEMA,
            "status": "corrected" if prior is not None else "learned",
            "source_revision_id": source.revision_id,
            "superseded_revision_id": None if prior is None else prior.revision_id,
            "binding_id": binding.get("id"),
            "event_id": event.get("event_id"),
            "archive_receipt": archive,
            "semantic_receipt": semantic_result,
            "computer_receipt": computer,
            "memory_reconsideration": reconsideration,
            "rebound_relevance_conditions": rebound_relevance,
            "state_sha256": regional["field_state_sha256"],
            "generation": self.owner.state.generation,
            "regional_field": regional,
        }

    def _document_for_revision(self, revision_id: str) -> Mapping[str, Any] | None:
        source = self._active_source(revision_id)
        raw = self.owner.exact_recall(
            revision_id=revision_id,
            allowed_labels=frozenset(source.labels),
            span=source.span,
            allow_historical=False,
        )
        _require(raw.get("status") == "active", "exact source recall returned a non-active source")
        selected = base64.b64decode(raw["bytes_base64"], validate=True)
        _require(
            hashlib.sha256(selected).hexdigest() == raw["content_sha256"],
            "exact source recall content digest mismatch",
        )
        _require(
            hashlib.sha256(self.owner.evidence.read(source)).hexdigest()
            == raw["full_revision_sha256"],
            "exact source recall full-revision digest mismatch",
        )
        decoded = json.loads(selected.decode("utf-8"))
        return decoded if isinstance(decoded, Mapping) else None

    @staticmethod
    def _publication_gate(operation_id: str) -> Mapping[str, Any]:
        """Name the paired transaction that must commit before this record is usable."""
        return {
            "schema": PUBLICATION_GATE_SCHEMA,
            "kind": "coupled-transaction",
            "operation_id": operation_id,
        }

    def _publication_journal(self) -> CoupledTransactionJournal:
        return CoupledTransactionJournal(self.data_home / "coupled-transactions")

    def _publication_eligibility(
        self, document: Mapping[str, Any]
    ) -> Mapping[str, Any] | None:
        """Return journal eligibility for a gated record, or None when ungated."""
        payload = document.get("payload")
        gate = payload.get("publication") if isinstance(payload, Mapping) else None
        if not isinstance(gate, Mapping) or gate.get("kind") != "coupled-transaction":
            return None
        operation_id = gate.get("operation_id")
        _require(
            isinstance(operation_id, str) and bool(operation_id),
            "gated record does not name its coupled transaction",
        )
        return self._publication_journal().publication_status(operation_id)

    def pending_publications(self) -> Mapping[str, Any]:
        """Report paired transactions that never reached a durable commit."""
        rows = self._publication_journal().unsettled()
        return {
            "schema": "cassi.field-qwen.pending-publications.v1",
            "count": len(rows),
            "transactions": [dict(row) for row in rows],
            "recovery": (
                "An unsettled transaction never became recallable; its archived "
                "payload stays ineligible until it is rejected explicitly."
            ),
        }

    def continuation_receipt(
        self, operation_id: str, *, instrument: QwenNativeInstrument, mode: str
    ) -> Mapping[str, Any]:
        """Report whether this instrument can continue a committed transaction exactly.

        The native backend is part of trial identity and changes coupled-mode
        arithmetic, so a continuation is exact only when the committed
        transaction was produced by this same instrument.
        """

        capabilities = instrument.capabilities(mode)
        journal = self._publication_journal()
        try:
            transaction = journal._read(operation_id)
        except KeyError:
            return {
                "schema": CONTINUATION_SCHEMA,
                "operation_id": operation_id,
                "status": "transaction-missing",
                "exact": False,
                "reason": "no committed transaction for this operation",
            }
        recovered = journal.recover(
            operation_id, field_root=self.owner.state.state_sha256
        )
        identity_matches = (
            transaction.get("adapter_identity_sha256") == instrument.identity.fingerprint
        )
        committed_native = transaction.get("native_successor") or {}
        coupling_matches = committed_native.get("effective_coupling") == dict(
            instrument.coupling
        )
        native_context = committed_native.get("native_context")
        context_path = None if native_context is None else Path(native_context["path"])
        exact = bool(
            recovered["status"] == "exact-pair"
            and identity_matches
            and coupling_matches
            and capabilities.supports("exact-native-resume")
            and context_path is not None
            and context_path.is_file()
        )
        return {
            "schema": CONTINUATION_SCHEMA,
            "operation_id": operation_id,
            "status": recovered["status"],
            "exact": exact,
            "mode": mode,
            "committed_continuation_class": transaction.get("continuation_class"),
            "identity_matches": identity_matches,
            "coupling_matches": coupling_matches,
            "committed_effective_coupling": committed_native.get("effective_coupling"),
            "effective_coupling": dict(instrument.coupling),
            "committed_identity_sha256": transaction.get("adapter_identity_sha256"),
            "instrument_identity_sha256": instrument.identity.fingerprint,
            "native_context": None
            if native_context is None
            else {
                "path": str(context_path),
                "sha256": native_context["sha256"],
                "bytes": int(native_context["bytes"]),
            },
            "reason": (
                "instrument identity, field root, successor state, and native "
                "context all match the committed transaction"
                if exact
                else "continuation is not exact for this instrument or mode"
            ),
        }

    def recall(self, context: Mapping[str, Any], *, operation_label: str) -> Mapping[str, Any]:
        """Query cognition.field, then read only its active exact source roots."""

        normalized = _context(context)
        before = self.regional_field_receipt()["field_state_sha256"]
        _, inspect_result, inspected = self._invoke_semantic(
            label=f"inspect:{operation_label}",
            request=self._semantic_state_request(
                self._semantic_operation_id("inspect", operation_label)
            ),
        )
        discovered_candidates: list[Mapping[str, Any]] = []
        for value in self._current_bindings(inspected, include_dormant=True):
            scope = value.get("scope")
            if (
                isinstance(scope, Mapping)
                and scope.get("kind") == SEMANTIC_SCOPE
                and scope.get("context") == normalized
            ):
                discovered_candidates.append(value)
        discovered_candidates.sort(key=lambda value: str(value.get("id", "")))
        restored: list[Mapping[str, Any]] = []
        restoration_failures: list[Mapping[str, Any]] = []
        for binding in discovered_candidates:
            if binding.get("status") != "dormant":
                continue
            memory_ref = {
                "id": str(binding["id"]),
                "kind": str(binding["kind"]),
                "content_version": int(binding["content_version"]),
            }
            expansion_label = (
                f"{operation_label}:expand:{binding['id']}:"
                f"{binding['content_version']}"
            )
            try:
                expansion = self.expand_memory(
                    memory_ref=memory_ref,
                    operation_label=expansion_label,
                    reason="relevant-recall",
                )
                expanded_ref = expansion.get("result", {}).get("memory")
                restored.append(
                    {
                        "demoted_ref": memory_ref,
                        "expanded_ref": expanded_ref,
                        "operation_label": expansion_label,
                    }
                )
            except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
                restoration_failures.append(
                    {
                        "memory_ref": memory_ref,
                        "kind": "demoted-detail-unavailable",
                        "reason": f"{type(exc).__name__}: {exc}"[:600],
                    }
                )
        post_expansion_inspect: Mapping[str, Any] | None = None
        if restored:
            _, post_expansion_inspect, inspected = self._invoke_semantic(
                label=f"inspect:{operation_label}:expanded",
                request=self._semantic_state_request(
                    self._semantic_operation_id(
                        "inspect-expanded", operation_label
                    )
                ),
            )
        candidates: list[Mapping[str, Any]] = []
        for value in self._current_bindings(inspected):
            scope = value.get("scope")
            if (
                isinstance(scope, Mapping)
                and scope.get("kind") == SEMANTIC_SCOPE
                and scope.get("context") == normalized
            ):
                candidates.append(value)
        candidates.sort(key=lambda value: str(value.get("id", "")))

        rows: list[Mapping[str, Any]] = []
        query_receipts: list[Mapping[str, Any]] = []
        selected_revisions: set[str] = set()
        ineligible: list[Mapping[str, Any]] = []
        for binding in candidates:
            payload = binding.get("payload")
            if not isinstance(payload, Mapping):
                continue
            revision_id = payload.get("source_revision_id")
            if not isinstance(revision_id, str):
                continue
            query_label = f"{operation_label}:{binding.get('id', '')}"
            _, query_result, _ = self._invoke_semantic(
                label=f"query:{query_label}",
                request={
                    "operation": "query",
                    "operation_id": self._semantic_operation_id("query", query_label),
                    "query": {
                        "kind": "binding",
                        "binding_id": binding.get("id"),
                    },
                },
            )
            query_receipts.append(query_result)
            answer = query_result.get("answer") if isinstance(query_result, Mapping) else None
            returned_binding = query_result.get("binding")
            _require(
                isinstance(returned_binding, Mapping)
                and returned_binding.get("id") == binding.get("id")
                and returned_binding.get("content_version")
                == binding.get("content_version"),
                "cognition.field query returned a different binding",
            )
            roots = binding.get("support_roots", [])
            _require(
                isinstance(roots, list),
                "cognition.field binding support roots are unavailable",
            )
            for root in roots:
                if isinstance(root, str):
                    selected_revisions.add(root)
        for revision_id in sorted(selected_revisions):
            document = self._document_for_revision(revision_id)
            if document is None or document.get("schema") != MEMORY_SCHEMA:
                continue
            record_context = document.get("context")
            if not isinstance(record_context, Mapping) or any(
                normalized.get(key) != value for key, value in record_context.items()
            ):
                continue
            eligibility = self._publication_eligibility(document)
            if eligibility is not None and not eligibility["eligible"]:
                ineligible.append(
                    {
                        "source_revision_id": revision_id,
                        "source_id": document.get("source_id"),
                        "operation_id": eligibility["operation_id"],
                        "transaction_status": eligibility["status"],
                        "reason": eligibility["reason"],
                    }
                )
                continue
            source = self._active_source(revision_id)
            rows.append(
                {
                    "content_sha256": source.content_sha256,
                    "context": dict(record_context),
                    "payload": document["payload"],
                    "source_id": source.source_id,
                    "source_revision_id": revision_id,
                    "publication_status": (
                        "ungated" if eligibility is None else eligibility["status"]
                    ),
                }
            )
        rows.sort(key=lambda row: (str(row["source_id"]), str(row["source_revision_id"])))
        eligible_revisions = {
            str(row["source_revision_id"]) for row in rows
        }
        selected_refs = [
            {
                "id": str(binding["id"]),
                "kind": str(binding["kind"]),
                "content_version": int(binding["content_version"]),
            }
            for binding in candidates
            if isinstance(binding.get("payload"), Mapping)
            and binding["payload"].get("source_revision_id")
            in eligible_revisions
        ]
        recall_gaps: list[Mapping[str, Any]] = [
            {
                "kind": "demoted-detail-unavailable",
                "memory_ref": row["memory_ref"],
            }
            for row in restoration_failures
        ]
        if not rows and not recall_gaps:
            recall_gaps.append(
                {
                    "kind": "no-support-located-within-searched-scope",
                    "scope": normalized,
                }
            )
        recall_limitations: list[Mapping[str, Any]] = []
        if ineligible:
            recall_limitations.append(
                {
                    "kind": "publication-ineligible",
                    "count": len(ineligible),
                }
            )
        if restoration_failures:
            recall_limitations.append(
                {
                    "kind": "demoted-detail-unavailable",
                    "count": len(restoration_failures),
                    "failures": restoration_failures,
                }
            )
        recall_token = hashlib.sha256(
            operation_label.encode("utf-8")
        ).hexdigest()
        _, living_result, _ = self._invoke_semantic(
            label=f"living-recall:{operation_label}",
            request={
                "operation": "recall-request",
                "operation_id": self._semantic_operation_id(
                    "recall-request", operation_label
                ),
                "episode_id": recall_token,
                "question": {
                    "kind": "workspace-recall",
                    "operation_label": operation_label,
                },
                "context": normalized,
                "intended_use": {
                    "kind": "field-brain-workspace",
                    "operation_label": operation_label,
                },
                "fidelity": {
                    "requested": "exact-source",
                    "delivered": "exact-source" if rows else "none",
                },
                "allowance": {
                    "candidate_bindings": len(discovered_candidates),
                    "evidence_reads": len(selected_revisions),
                    "restoration_attempts": len(restored)
                    + len(restoration_failures),
                },
                "selected_refs": selected_refs,
                "cue_refs": [],
                "search": {
                    "scope": normalized,
                    "candidate_bindings": len(discovered_candidates),
                    "active_candidate_bindings": len(candidates),
                    "queried_bindings": len(query_receipts),
                    "source_roots": len(selected_revisions),
                    "restored_bindings": len(restored),
                },
                "gaps": recall_gaps,
                "limitations": recall_limitations,
            },
        )
        after = self.regional_field_receipt()
        return {
            "schema": RECALL_SCHEMA,
            "status": "supported" if rows else "support-gap",
            "query_id": self._semantic_operation_id("recall", operation_label),
            "context": normalized,
            "records": rows,
            "selected_source_revision_ids": sorted(
                row["source_revision_id"] for row in rows
            ),
            "candidate_binding_ids": [
                str(row.get("id")) for row in discovered_candidates
            ],
            "active_candidate_binding_ids": [
                str(row.get("id")) for row in candidates
            ],
            "restored_memories": restored,
            "restoration_failures": restoration_failures,
            "excluded_ineligible": ineligible,
            "excluded_ineligible_count": len(ineligible),
            "inspect_receipt": inspect_result,
            "post_expansion_inspect_receipt": post_expansion_inspect,
            "query_receipts": query_receipts,
            "living_memory": living_result,
            "selected_semantic_records": [
                {
                    "ref": ref,
                    "source_revision_id": str(binding["payload"]["source_revision_id"]),
                }
                for binding, ref in zip(
                    [
                        candidate
                        for candidate in candidates
                        if isinstance(candidate.get("payload"), Mapping)
                        and candidate["payload"].get("source_revision_id")
                        in eligible_revisions
                    ],
                    selected_refs,
                    strict=True,
                )
            ],
            "field_state_before_sha256": before,
            "field_state_after_sha256": after["field_state_sha256"],
            "field_generation": after["logical_transition"],
            "checkpoint_receipt": after["checkpoint_receipt"],
            "regional_field": after,
        }
    def use_recall(
        self,
        *,
        episode_ref: Mapping[str, Any],
        consumer: Mapping[str, Any],
        operation_label: str,
        selected_refs: Sequence[Mapping[str, Any]] | None = None,
    ) -> Mapping[str, Any]:
        """Bind a delivered recollection to the consumer that actually used it."""

        request: dict[str, Any] = {
            "operation": "recall-use",
            "operation_id": self._semantic_operation_id(
                "recall-use", operation_label
            ),
            "episode_ref": dict(episode_ref),
            "use_id": hashlib.sha256(
                operation_label.encode("utf-8")
            ).hexdigest(),
            "consumer": dict(consumer),
        }
        if selected_refs is not None:
            request["selected_refs"] = [dict(row) for row in selected_refs]
        return self.semantic(request, operation_label=operation_label)

    def assess_recall(
        self,
        *,
        episode_ref: Mapping[str, Any],
        outcome_id: str,
        consequence: Mapping[str, Any],
        usefulness: float,
        operation_label: str,
        renewal: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        """Admit one actual consequence and settle its pending recall use once."""

        request: dict[str, Any] = {
            "operation": "recall-outcome",
            "operation_id": self._semantic_operation_id(
                "recall-outcome", operation_label
            ),
            "episode_ref": dict(episode_ref),
            "outcome_id": outcome_id,
            "consequence": dict(consequence),
            "usefulness": usefulness,
        }
        if renewal is not None:
            request["renewal"] = dict(renewal)
        return self.semantic(request, operation_label=operation_label)

    def memory_awareness(
        self,
        *,
        operation_label: str,
        episode_ref: Mapping[str, Any] | None = None,
        scope: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        request: dict[str, Any] = {
            "operation": "memory-awareness",
            "operation_id": self._semantic_operation_id(
                "memory-awareness", operation_label
            ),
        }
        if episode_ref is not None:
            request["episode_ref"] = dict(episode_ref)
        if scope is not None:
            request["scope"] = dict(scope)
        return self.semantic(request, operation_label=operation_label)

    def autobiography(
        self,
        *,
        operation_label: str,
        limit: int = 32,
        include_unsettled: bool = True,
    ) -> Mapping[str, Any]:
        return self.semantic(
            {
                "operation": "autobiography",
                "operation_id": self._semantic_operation_id(
                    "autobiography", operation_label
                ),
                "limit": limit,
                "include_unsettled": include_unsettled,
            },
            operation_label=operation_label,
        )

    def cancel_recall(
        self,
        *,
        episode_ref: Mapping[str, Any],
        reason: Mapping[str, Any] | str,
        operation_label: str,
    ) -> Mapping[str, Any]:
        """Settle an unused or abandoned recall without inventing usefulness."""

        return self.semantic(
            {
                "operation": "recall-cancel",
                "operation_id": self._semantic_operation_id(
                    "recall-cancel", operation_label
                ),
                "episode_ref": dict(episode_ref),
                "reason": reason,
            },
            operation_label=operation_label,
        )

    def register_relevance(
        self,
        *,
        condition_id: str,
        condition: Mapping[str, Any],
        target_refs: Sequence[Mapping[str, Any]],
        reason: Mapping[str, Any] | str,
        operation_label: str,
        priority: float = 0.5,
        cooldown_events: int = 0,
    ) -> Mapping[str, Any]:
        """Retain one field-owned prospective memory condition."""

        return self.semantic(
            {
                "operation": "register-relevance",
                "operation_id": self._semantic_operation_id(
                    "register-relevance", operation_label
                ),
                "condition_id": condition_id,
                "condition": dict(condition),
                "target_refs": [dict(row) for row in target_refs],
                "reason": reason,
                "priority": priority,
                "cooldown_events": cooldown_events,
            },
            operation_label=operation_label,
        )

    def match_relevance(
        self,
        *,
        event_id: str,
        context: Mapping[str, Any],
        operation_label: str,
        maximum: int = 32,
        cursor: int = 0,
    ) -> Mapping[str, Any]:
        """Evaluate one bounded page of prospective memory conditions."""

        return self.semantic(
            {
                "operation": "match-relevance",
                "operation_id": self._semantic_operation_id(
                    "match-relevance", operation_label
                ),
                "event_id": event_id,
                "context": dict(context),
                "maximum": maximum,
                "cursor": cursor,
            },
            operation_label=operation_label,
        )

    def reinterpret_memory(
        self,
        *,
        interpretation_id: str,
        source_refs: Sequence[Mapping[str, Any]],
        interpretation: Mapping[str, Any],
        applicability: Mapping[str, Any],
        operation_label: str,
        epistemic_kind: str = "derived",
        support_roots: Sequence[str] = (),
    ) -> Mapping[str, Any]:
        """Create a versioned interpretation without altering its evidence."""

        return self.semantic(
            {
                "operation": "reinterpret-memory",
                "operation_id": self._semantic_operation_id(
                    "reinterpret-memory", operation_label
                ),
                "interpretation_id": interpretation_id,
                "source_refs": [dict(row) for row in source_refs],
                "interpretation": dict(interpretation),
                "applicability": dict(applicability),
                "epistemic_kind": epistemic_kind,
                "support_roots": list(support_roots),
            },
            operation_label=operation_label,
        )

    def quiet_synthesis(
        self,
        *,
        synthesis_id: str,
        concern_ref: Mapping[str, Any],
        source_refs: Sequence[Mapping[str, Any]],
        candidate: Mapping[str, Any],
        resources: Mapping[str, Any],
        operation_label: str,
    ) -> Mapping[str, Any]:
        """Retain a bounded recombination as hypothetical research material."""

        return self.semantic(
            {
                "operation": "quiet-synthesis",
                "operation_id": self._semantic_operation_id(
                    "quiet-synthesis", operation_label
                ),
                "synthesis_id": synthesis_id,
                "concern_ref": dict(concern_ref),
                "source_refs": [dict(row) for row in source_refs],
                "candidate": dict(candidate),
                "resources": dict(resources),
            },
            operation_label=operation_label,
        )

    def maintain_memory(
        self,
        *,
        purpose: Mapping[str, Any] | str,
        operation_label: str,
        target_refs: Sequence[Mapping[str, Any]] = (),
        allowance: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        """Assess bounded resident memory work through the canonical field."""

        request: dict[str, Any] = {
            "operation": "maintain-memory",
            "operation_id": self._semantic_operation_id(
                "maintain-memory", operation_label
            ),
            "purpose": purpose,
            "target_refs": [dict(row) for row in target_refs],
        }
        if allowance is not None:
            request["allowance"] = dict(allowance)
        result = self.semantic(request, operation_label=operation_label)
        purpose_kind = (
            purpose
            if isinstance(purpose, str)
            else purpose.get("kind")
        )
        if purpose_kind != "integrity-scrub":
            return result
        scrub_cursor = 0
        scrub_maximum = 64
        if allowance is not None:
            scrub_cursor = int(allowance.get("cursor", scrub_cursor))
            scrub_maximum = int(
                allowance.get("maximum_objects", scrub_maximum)
            )
        return {
            **result,
            "storage_scrub": self.owner.scrub_memory_storage(
                cursor=scrub_cursor,
                maximum=scrub_maximum,
            ),
        }

    def inspect_living_memory(
        self,
        *,
        scope: Mapping[str, Any] | str | None = None,
        limit: int = 32,
        include_unsettled: bool = True,
    ) -> Mapping[str, Any]:
        """Read memory meaning and storage without publishing a field transition."""

        task = self._computer_inspect().get("task")
        _require(
            isinstance(task, Mapping)
            and task.get("schema") == SEMANTIC_STATE_SCHEMA,
            "regional semantic state is unavailable",
        )
        receipt = self.state_receipt()
        view_key = hashlib.sha256(
            json.dumps(
                {
                    "state_sha256": receipt["state_sha256"],
                    "scope": scope,
                    "limit": limit,
                    "include_unsettled": include_unsettled,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

        def preview(request: Mapping[str, Any]) -> Mapping[str, Any]:
            copied = json.loads(
                json.dumps(
                    task,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
            transition = semantic_cognition_kernel(copied, request, 4096)
            _require(
                transition.status == "done"
                and isinstance(transition.output, Mapping),
                "living-memory inspection exceeded its bounded work",
            )
            return dict(transition.output)

        awareness_request: dict[str, Any] = {
            "operation": "memory-awareness",
            "operation_id": f"inspect:memory-awareness:{view_key}",
        }
        if scope is not None:
            awareness_request["scope"] = scope
        awareness = preview(awareness_request)
        autobiography = preview(
            {
                "operation": "autobiography",
                "operation_id": f"inspect:autobiography:{view_key}",
                "limit": limit,
                "include_unsettled": include_unsettled,
            }
        )
        circulation = self.owner.circulation_diagnostics(COMPUTER_ID)
        after = self.state_receipt()
        _require(
            after["state_sha256"] == receipt["state_sha256"]
            and after["generation"] == receipt["generation"],
            "living-memory inspection changed canonical state",
        )
        return {
            "schema": "cassi.field-qwen.living-memory-view.v1",
            "field_state_sha256": receipt["state_sha256"],
            "field_generation": receipt["generation"],
            "awareness": awareness,
            "autobiography": autobiography,
            "storage": self.owner.memory_storage_diagnostics(),
            "circulation": circulation,
        }

    def _semantic_record(
        self, reference: Mapping[str, Any], *, require_current: bool = True
    ) -> Mapping[str, Any]:
        task = self._computer_inspect().get("task")
        _require(
            isinstance(task, Mapping)
            and isinstance(task.get("records"), Mapping),
            "regional semantic records are unavailable",
        )
        return resolve_semantic_record(
            task["records"], reference, require_current=require_current
        )

    def demote_memory(
        self,
        *,
        memory_ref: Mapping[str, Any],
        summary: Mapping[str, Any],
        operation_label: str,
        reason: str = "bounded-active-residency",
    ) -> Mapping[str, Any]:
        """Archive exact payload bytes, then replace active detail with a cue."""

        record = self._semantic_record(memory_ref)
        content = json.dumps(
            record["payload"],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        content_sha256 = hashlib.sha256(content).hexdigest()
        source = SourceInput(
            source_id=(
                f"living-memory:{record['kind']}:{record['id']}:"
                f"{record['content_version']}:{content_sha256[:16]}"
            ),
            content=content,
            media_type="application/json",
            codec="utf-8",
            observed_timestamp="1970-01-01T00:00:00Z",
            scope=SEMANTIC_SCOPE,
            claim_category="memory-backing",
            fidelity="exact-record-payload",
            labels=("living-memory-backing",),
        )
        archive = self.owner.archive_source(
            operation_id=self._owner_operation_id(
                "archive-memory", source.revision_id
            ),
            source=source,
            context={
                "adapter": "cassi-field-qwen",
                "memory_ref": dict(memory_ref),
            },
            epistemic_type="observed",
            event_kind="memory-backing",
        )
        backing = {
            "codec": "utf-8-json",
            "content_sha256": content_sha256,
            "object_sha256": content_sha256,
            "recoverable": True,
            "source_revision_id": source.revision_id,
        }
        result = self.semantic(
            {
                "operation": "demote-memory",
                "operation_id": self._semantic_operation_id(
                    "demote-memory", operation_label
                ),
                "memory_ref": dict(memory_ref),
                "backing": backing,
                "summary": dict(summary),
                "fidelity": "exact",
                "reason": reason,
            },
            operation_label=operation_label,
        )
        return {**dict(result), "archive_receipt": archive}

    def expand_memory(
        self,
        *,
        memory_ref: Mapping[str, Any],
        operation_label: str,
        reason: str = "relevant-recall",
    ) -> Mapping[str, Any]:
        """Restore one demoted payload only after exact-source verification."""

        record = self._semantic_record(memory_ref)
        backing = record["payload"].get("memory_backing")
        _require(
            isinstance(backing, Mapping)
            and backing.get("recoverable") is True
            and isinstance(backing.get("source_revision_id"), str),
            "memory does not carry independently recoverable backing",
        )
        source = self._active_source(str(backing["source_revision_id"]))
        content = self.owner.evidence.read(source)
        _require(
            hashlib.sha256(content).hexdigest() == backing.get("content_sha256"),
            "memory backing content digest mismatch",
        )
        try:
            payload = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("memory backing is not canonical JSON") from exc
        _require(
            isinstance(payload, Mapping),
            "memory backing did not decode to a semantic payload",
        )
        return self.semantic(
            {
                "operation": "expand-memory",
                "operation_id": self._semantic_operation_id(
                    "expand-memory", operation_label
                ),
                "memory_ref": dict(memory_ref),
                "restored_payload": dict(payload),
                "reason": reason,
            },
            operation_label=operation_label,
        )

    def semantic(
        self,
        request: Mapping[str, Any],
        *,
        operation_label: str | None = None,
    ) -> Mapping[str, Any]:
        """Invoke one fixed semantic operation through the field owner."""

        operation = request.get("operation")
        _require(
            isinstance(operation, str) and bool(operation),
            "semantic request must name an operation",
        )
        operation_id = request.get("operation_id")
        _require(
            isinstance(operation_id, str) and bool(operation_id),
            "semantic request must carry an operation identity",
        )
        _receipt, result, inspected = self._invoke_semantic(
            label=operation_label or cast(str, operation_id),
            request=request,
        )
        return {
            "schema": "cassi.field-qwen.semantic-operation.v1",
            "operation": operation,
            "operation_id": operation_id,
            "result": result,
            "field_state_sha256": inspected.get("state_sha256"),
            "checkpoint_receipt": inspected.get("checkpoint_receipt"),
        }

    def _run_resident_invocation(
        self,
        *,
        label: str,
        invocation: Mapping[str, Any],
        steps: int,
    ) -> Mapping[str, Any]:
        """Execute one declared child while its caller stays in field frames."""

        before = self.owner.state.state_sha256
        self.owner.operate_computer(
            self._owner_operation_id("computer-call", label),
            computer_id=COMPUTER_ID,
            action="call",
            arguments={**dict(invocation), "steps": steps},
            expected_state_sha256=before,
        )
        for continuation_index in range(SEMANTIC_SETTLEMENT_LIMIT):
            inspected = self._computer_inspect()
            depth = inspected.get("invocation_depth")
            _require(
                isinstance(depth, int) and depth >= 0,
                "regional invocation depth is unavailable",
            )
            if depth == 0:
                return inspected
            before = self.owner.state.state_sha256
            self.owner.operate_computer(
                self._owner_operation_id(
                    "computer-call-advance",
                    f"{label}:{continuation_index}",
                ),
                computer_id=COMPUTER_ID,
                action="advance",
                arguments={"steps": steps},
                expected_state_sha256=before,
            )
        raise RuntimeError("resident invocation exceeded its bounded settlement budget")

    def reason(
        self,
        *,
        episode_id: str,
        question: Mapping[str, Any],
        request: Mapping[str, Any],
        allocation: Mapping[str, int],
        dependencies: Sequence[Mapping[str, Any]] = (),
        support_roots: Sequence[str] = (),
        assemblies: Sequence[Mapping[str, Any]] = (),
        cues: Sequence[Mapping[str, Any]] = (),
        hierarchy: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        """Run one packet-aware reasoning episode through retained child frames."""

        begin_request: dict[str, Any] = {
            "operation": "begin-reasoning",
            "operation_id": self._semantic_operation_id(
                "reasoning-begin", episode_id
            ),
            "episode_id": episode_id,
            "question": dict(question),
            "request": dict(request),
            "allocation": dict(allocation),
            "dependencies": [dict(value) for value in dependencies],
            "support_roots": list(support_roots),
        }
        if assemblies:
            begin_request["assemblies"] = [
                dict(value) for value in assemblies
            ]
        if cues:
            begin_request["cues"] = [dict(value) for value in cues]
        if hierarchy is not None:
            begin_request["hierarchy"] = dict(hierarchy)
        _receipt, episode, _inspect = self._invoke_semantic(
            label=f"reasoning-begin:{episode_id}",
            request=begin_request,
        )
        child_steps = max(1, int(allocation.get("work", 1)))
        transported = 0
        kernel: Any = None
        while True:
            phase = episode.get("phase")
            invocation = episode.get("invocation")
            if isinstance(invocation, Mapping):
                kernel = invocation.get("kernel")
                self._run_resident_invocation(
                    label=f"reasoning-child:{episode_id}:{transported}",
                    invocation=cast(Mapping[str, Any], invocation),
                    steps=child_steps,
                )
                transported += 1
                if transported > SEMANTIC_SETTLEMENT_LIMIT:
                    raise RuntimeError(
                        "reasoning episode exceeded its bounded transport budget"
                    )
            if phase == "terminal" or not isinstance(invocation, Mapping):
                break
            _receipt, episode, _inspect = self._invoke_semantic(
                label=f"reasoning-advance:{episode_id}:{transported}",
                request={
                    "operation": "advance-reasoning",
                    "operation_id": self._semantic_operation_id(
                        "reasoning-advance", f"{episode_id}:{transported}"
                    ),
                    "episode_id": episode_id,
                },
            )
        _receipt, result, inspected = self._invoke_semantic(
            label=f"reasoning-finish:{episode_id}",
            request={
                "operation": "finish-reasoning",
                "operation_id": self._semantic_operation_id(
                    "reasoning-finish", episode_id
                ),
                "episode_id": episode_id,
            },
        )
        return {
            "schema": "cassi.field-qwen.reasoning-result.v1",
            "status": result.get("status"),
            "episode_id": episode_id,
            "question": dict(question),
            "result": result.get("result"),
            "assessment": result.get("assessment"),
            "field_state_sha256": inspected.get("state_sha256"),
            "transports": transported,
            "ownership": {
                "semantic_work": "cassifi-cognition-field",
                "child_executor": kernel,
                "model_calls": int(allocation.get("model_calls", 0)),
                "host_answer_script": False,
            },
        }

    def develop(
        self,
        *,
        episode_id: str,
        specification: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        """Run one bounded named self-development method in the same image."""

        request = {
            **dict(specification),
            "operation": "start-development",
            "operation_id": self._semantic_operation_id(
                "development-start", episode_id
            ),
            "episode_id": episode_id,
        }
        _receipt, begun, _inspect = self._invoke_semantic(
            label=f"development-start:{episode_id}",
            request=request,
        )
        invocation = begun.get("invocation")
        _require(
            begun.get("status") == "supported"
            and isinstance(invocation, Mapping),
            "development episode did not produce a resident invocation",
        )
        allocation = specification.get("allocation", {})
        _require(
            isinstance(allocation, Mapping),
            "development allocation is unavailable",
        )
        self._run_resident_invocation(
            label=f"development-child:{episode_id}",
            invocation=cast(Mapping[str, Any], invocation),
            steps=max(1, int(allocation.get("work", 1))),
        )
        _receipt, result, inspected = self._invoke_semantic(
            label=f"development-finish:{episode_id}",
            request={
                "operation": "finish-development",
                "operation_id": self._semantic_operation_id(
                    "development-finish", episode_id
                ),
                "episode_id": episode_id,
            },
        )
        return {
            "schema": "cassi.field-qwen.development-result.v1",
            "status": result.get("status"),
            "episode_id": episode_id,
            "selected_skill": begun.get("selected_skill"),
            "result": result.get("result"),
            "assessment": result.get("assessment"),
            "field_state_sha256": inspected.get("state_sha256"),
            "ownership": {
                "method_state": "cassifi-cognition-field",
                "selector": "supplied-balanced-v1",
                "external_capabilities": dict(
                    specification.get("capabilities", {})
                ),
            },
        }

    def admit_model_observation(
        self,
        envelope: NumericEnvelope | Mapping[str, Any],
        *,
        capabilities: AdapterCapabilities,
        identity_sha256: str,
        observed_timestamp: str,
    ) -> Mapping[str, Any]:
        """Validate and admit one attributed model observation exactly once."""

        parsed: NumericEnvelope = (
            envelope
            if isinstance(envelope, NumericEnvelope)
            else NumericEnvelope.from_dict(envelope)
        )
        parsed.validate(
            max_elements=capabilities.max_elements,
            allow_nonfinite_fault=False,
        )
        site = parsed.meaning.get("site")
        _require(isinstance(site, str), "model observation site is unavailable")
        capabilities.require("activation-observation", site=site)
        _require(
            parsed.state_dependency.get("adapter_identity")
            == identity_sha256,
            "model observation adapter identity does not match its session",
        )
        producer = parsed.routing.get("producer_identity")
        _require(
            producer == identity_sha256,
            "model observation producer identity does not match its session",
        )
        source_id = (
            "model-observation:"
            + hashlib.sha256(
                json.dumps(
                    {
                        "operation": parsed.routing.get("operation"),
                        "payload": parsed.payload_sha256,
                        "producer": producer,
                        "site": site,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
        )
        result = self.learn(
            WorkMemoryRecord(
                source_id=source_id,
                context={
                    "kind": "model-observation",
                    "site": site,
                    "frame": str(parsed.meaning.get("frame")),
                    "episode": str(parsed.routing.get("episode")),
                },
                payload={
                    "envelope": parsed.as_dict(),
                    "attribution": "computational-instrument-observation",
                },
                observed_timestamp=observed_timestamp,
                labels=("model-instrument", "numeric-observation"),
            )
        )
        return {
            "schema": "cassi.field-qwen.model-observation-admission.v1",
            "status": result["status"],
            "source_id": source_id,
            "source_revision_id": result["source_revision_id"],
            "payload_sha256": parsed.payload_sha256,
            "site": site,
            "adapter_identity_sha256": identity_sha256,
            "field_state_sha256": result["state_sha256"],
        }

    def execute_native(
        self,
        *,
        operation_id: str,
        instrument: QwenNativeInstrument,
        mode: str,
        prompt: str,
        tokens: int,
        sequence: int,
        semantic_context: Mapping[str, Any] | None = None,
        output_contract: str = EMISSION_OUTPUT_CONTRACT,
        differential_reference: str | None = None,
    ) -> Mapping[str, Any]:
        """Stage, field-admit, and publish one native trial as a paired result.

        A differential reference is explicit and coupled-only.  When present,
        the real task frame and caller-supplied reference prompt seed an
        experimental numerical contrast, and that exact artifact is passed as
        the native trial state.
        """

        if differential_reference is not None:
            if mode != "coupled":
                raise ValueError("differential_reference applies only to coupled mode")
            if not isinstance(differential_reference, str) or not differential_reference:
                raise ValueError("differential_reference must be a nonempty string")
            if differential_reference == prompt:
                raise ValueError("differential_reference must differ from prompt")
        started_ns = time.perf_counter_ns()
        capabilities = instrument.capabilities(mode)
        if mode == "field":
            capabilities.require("field-owned-emission")
        field_predecessor = self.owner.state.state_sha256
        transitions_before = int(self.regional_field_receipt()["semantic_transitions"])
        journal = self._publication_journal()
        routing = {
            "principal": SEMANTIC_SCOPE,
            "session": COMPUTER_ID,
            "episode": operation_id,
            "operation": operation_id,
            "sequence": sequence,
        }
        differential_requested = differential_reference is not None
        seed_runs = 2 if differential_requested else 0
        model_calls = 1 if mode == "coupled" else 0
        reservation = {
            "model_calls": model_calls,
            "native_tokens": tokens,
            "native_forward_passes": (tokens + 2) if mode == "coupled" else 0,
            "field_work": 1,
            "differential_seed_runs": seed_runs,
        }
        original_seed = {
            "path": str(instrument.state),
            "sha256": _sha256_path(instrument.state),
            "bytes": instrument.state.stat().st_size,
            "kind": "native-field-state-seed",
        }
        journal.reserve(
            operation_id=operation_id,
            routing=routing,
            identity=instrument.identity,
            field_predecessor=field_predecessor,
            native_predecessor=original_seed,
            reservation=reservation,
            continuation_class=instrument.continuation_class(mode),
        )
        try:
            recall: Mapping[str, Any] | None = None
            emission_prompt = prompt
            frame: Mapping[str, Any] | None = None
            frame_fit_ns = 0
            recall_started_ns = time.perf_counter_ns()
            if semantic_context is not None:
                recall = self.recall(
                    semantic_context,
                    operation_label=f"field-emission:{operation_id}",
                )
                recall_elapsed_ns = time.perf_counter_ns() - recall_started_ns
                fit_started_ns = time.perf_counter_ns()
                token_ceiling = min(
                    ceiling for ceiling in (
                        EMISSION_FRAME_TOKEN_CEILING,
                        instrument.prompt_token_room(mode, tokens),
                    ) if ceiling is not None
                )
                frame = fit_emission_frame(
                    task=prompt,
                    output_contract=output_contract,
                    recall=recall,
                    token_ceiling=token_ceiling,
                    count_tokens=instrument.count_prompt_tokens,
                )
                emission_prompt = frame["prompt"]
                # The explicit differential reference is already the caller's
                # exact counterfactual prompt; only the task arm receives the
                # recalled/composed frame.
                frame_fit_ns = time.perf_counter_ns() - fit_started_ns
            else:
                recall_elapsed_ns = time.perf_counter_ns() - recall_started_ns

            trial_root = (
                self.data_home
                / "native-trials"
                / hashlib.sha256(operation_id.encode("utf-8")).hexdigest()
            )
            state_in: Path | None = None
            differential_started_ns = time.perf_counter_ns()
            differential_result: Mapping[str, Any] | None = None
            if differential_requested:
                differential_result = differential_field_state(
                    instrument=instrument,
                    frame=emission_prompt,
                    reference=cast(str, differential_reference),
                    trial_dir=trial_root / "differential",
                    output=trial_root / "differential-state.f32",
                )
                state_in = Path(differential_result["state"]["path"])
                differential_elapsed_ns = time.perf_counter_ns() - differential_started_ns
                preparation = {
                    "kind": "differential-field-state",
                    "composition_method": differential_result["composition_method"],
                    "original_seed": differential_result["original_seed"],
                    "sources": list(differential_result["sources"]),
                    "state": dict(differential_result["state"]),
                    "effective_coupling": dict(instrument.coupling),
                    "work": dict(differential_result["preparation_work"]),
                }
            else:
                differential_elapsed_ns = 0
                preparation = {
                    "kind": "raw-seed",
                    "composition_method": "raw-native-seed",
                    "original_seed": original_seed,
                    "sources": [
                        {
                            "role": "raw",
                            "prompt_sha256": hashlib.sha256(
                                emission_prompt.encode("utf-8")
                            ).hexdigest(),
                            "prompt_bytes": len(emission_prompt.encode("utf-8")),
                            "path": original_seed["path"],
                            "sha256": original_seed["sha256"],
                            "bytes": original_seed["bytes"],
                        },
                    ],
                    "state": dict(original_seed),
                    "effective_coupling": dict(instrument.coupling),
                    "work": {"field_seed_runs": 0, "field_seed_forward_passes": 0},
                }
            native_predecessor = (
                dict(differential_result["state"])
                if differential_result is not None
                else dict(original_seed)
            )
            preparation_work = dict(preparation["work"])
            pre_timings = {
                "recall_ns": recall_elapsed_ns,
                "frame_fit_ns": frame_fit_ns,
                "differential_preparation_ns": differential_elapsed_ns,
            }
            journal.stage(
                operation_id,
                trial={"preparation": preparation},
                measured_lower=0,
                measured_upper=0,
                exact=False,
                work={
                    "differential_seed_runs": seed_runs,
                    "differential_seed_forward_passes": int(
                        preparation_work.get("field_seed_forward_passes", 0)
                    ),
                },
                timings=pre_timings,
                native_predecessor=native_predecessor,
                preparation=preparation,
            )
            native = instrument.execute(
                mode=mode,
                prompt=emission_prompt,
                tokens=tokens,
                trial_dir=trial_root / "native",
                state_in=state_in,
            )
            receipt = native["receipt"]
            native_state = native["state_successor"]
            native_context = native_state.get("native_context")
            generated_tokens = len(receipt.get("generation_token_ids", [])) or tokens
            native_forward_passes = int(receipt.get("qwen_forward_passes", 0))
            measured = native_forward_passes + generated_tokens + seed_runs
            source_prompts = {
                str(source["role"]): {
                    "sha256": str(source["prompt_sha256"]),
                    "bytes": int(source["prompt_bytes"]),
                    "tokens": int(source.get("prompt_tokens", 0)),
                }
                for source in preparation["sources"]
            }
            if not differential_requested:
                source_prompts["raw"]["tokens"] = int(receipt.get("prompt_tokens", 0))
            lineage = {
                "native_predecessor": dict(native["state_predecessor"]),
                "source_states": list(preparation["sources"]),
                "source_prompts": source_prompts,
                "original_seed": dict(preparation["original_seed"]),
                "composition_method": preparation["composition_method"],
                "effective_coupling": dict(instrument.coupling),
                "preparation_work": preparation_work,
            }
            timings = {
                **pre_timings,
                "native_execute_ns": int(native["elapsed_ns"]),
            }
            work = {
                "native_forward_passes": native_forward_passes,
                "emitted_tokens": generated_tokens,
                "model_logits_read": int(receipt.get("model_logits_read", 0) or 0),
                "field_logits_read": int(receipt.get("field_logits_read", 0) or 0),
                "lm_head_rows_computed": int(
                    receipt.get("lm_head_rows_computed", 0) or 0
                ),
                "lm_head_rows_skipped": int(
                    receipt.get("lm_head_rows_skipped", 0) or 0
                ),
                "sampler_steps": int(receipt.get("sampler_steps", 0) or 0),
                "qwen_tensor_bytes_loaded": int(
                    receipt.get("qwen_tensor_bytes_loaded", 0) or 0
                ),
                "native_state_bytes": int(native_state["bytes"]),
                "native_context_bytes": (
                    0 if native_context is None else int(native_context["bytes"])
                ),
                "field_recall_records": 0 if recall is None else len(recall["records"]),
                "field_recall_queries": 0 if recall is None else len(recall["query_receipts"]),
                "emission_memory_bytes": 0 if frame is None else int(frame["memory_bytes"]),
                "emission_records_dropped": 0 if frame is None else int(frame["records_dropped"]),
                "native_prompt_tokens": int(receipt.get("prompt_tokens", 0)),
                "differential_seed_runs": seed_runs,
                "differential_seed_forward_passes": int(
                    preparation_work.get("field_seed_forward_passes", 0)
                ),
            }
            journal.stage(
                operation_id,
                trial={
                    "native_result_sha256": hashlib.sha256(
                        json.dumps(
                            native,
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode("utf-8")
                    ).hexdigest(),
                    "state_successor": native_state,
                    "lineage": lineage,
                },
                measured_lower=measured,
                measured_upper=measured,
                exact=True,
                work=work,
                timings=timings,
                native_predecessor=native["state_predecessor"],
                preparation=preparation,
            )
            admission_started_ns = time.perf_counter_ns()
            admission = self.learn(
                WorkMemoryRecord(
                    source_id=f"native-result:{operation_id}",
                    context={
                        "kind": "native-model-result",
                        "mode": mode,
                        "operation": operation_id,
                    },
                    payload={
                        "identity_sha256": instrument.identity.fingerprint,
                        "output": native["output"],
                        "ownership": native["ownership"],
                        "receipt": receipt,
                        "publication": self._publication_gate(operation_id),
                        "native_lineage": lineage,
                        "emission": {
                            "task_frame": prompt,
                            "emission_prompt_sha256": hashlib.sha256(
                                emission_prompt.encode("utf-8")
                            ).hexdigest(),
                            "field_owned_input": semantic_context is not None,
                            "differential_reference_sha256": (
                                None
                                if differential_reference is None
                                else hashlib.sha256(
                                    cast(str, differential_reference).encode("utf-8")
                                ).hexdigest()
                            ),
                            "frame": None
                            if frame is None
                            else {
                                "prompt_bytes": int(frame["prompt_bytes"]),
                                "memory_bytes": int(frame["memory_bytes"]),
                                "prompt_tokens": int(frame["prompt_tokens"]),
                                "token_ceiling": int(frame["token_ceiling"]),
                                "records_included": int(frame["records_included"]),
                                "records_dropped": int(frame["records_dropped"]),
                                "dropped_source_revision_ids": list(
                                    frame["dropped_source_revision_ids"]
                                ),
                                "native_prompt_tokens": int(
                                    receipt.get("prompt_tokens", 0)
                                ),
                            },
                            "field_recall": None
                            if recall is None
                            else {
                                "status": recall["status"],
                                "candidate_binding_ids": recall["candidate_binding_ids"],
                                "context": recall["context"],
                                "excluded_ineligible_count": recall[
                                    "excluded_ineligible_count"
                                ],
                                "selected_source_revision_ids": recall[
                                    "selected_source_revision_ids"
                                ],
                            },
                        },
                    },
                    observed_timestamp=f"logical-sequence:{sequence}",
                    labels=("native-instrument", mode),
                )
            )
            admission_elapsed_ns = time.perf_counter_ns() - admission_started_ns
            field_successor = self.owner.state.state_sha256
            seal_started_ns = time.perf_counter_ns()
            journal.seal(
                operation_id,
                field_successor=field_successor,
                native_successor=native_state,
                delivery={
                    "delivery_id": f"native-delivery:{operation_id}",
                    "output_sha256": hashlib.sha256(
                        native["output"].encode("utf-8")
                    ).hexdigest(),
                },
                admission={
                    "source_id": f"native-result:{operation_id}",
                    "source_revision_id": admission["source_revision_id"],
                    "binding_id": admission.get("binding_id"),
                    "event_id": admission.get("event_id"),
                    "gate": dict(self._publication_gate(operation_id)),
                },
            )
            committed = journal.commit(operation_id)
            seal_commit_elapsed_ns = time.perf_counter_ns() - seal_started_ns
            transitions_after = int(
                self.regional_field_receipt()["semantic_transitions"]
            )
            settled = journal.publication_status(operation_id)
            return {
                **dict(native),
                "status": "committed",
                "field_admission": admission,
                "field_predecessor": field_predecessor,
                "field_successor": field_successor,
                "field_recall": None if recall is None else dict(recall),
                "emission_frame": None if frame is None else dict(frame),
                "differential_preparation": (
                    None if differential_result is None else dict(differential_result)
                ),
                "native_lineage": lineage,
                "emission_prompt_sha256": hashlib.sha256(
                    emission_prompt.encode("utf-8")
                ).hexdigest(),
                "publication": dict(settled),
                "measured": {
                    "semantic_transitions": transitions_after - transitions_before,
                    "native_forward_passes": native_forward_passes,
                    "differential_seed_runs": seed_runs,
                    "admission_ns": admission_elapsed_ns,
                    "seal_commit_ns": seal_commit_elapsed_ns,
                    "total_ns": time.perf_counter_ns() - started_ns,
                },
                "timings": {**timings, "admission_ns": admission_elapsed_ns},
                "coupled_transaction": committed,
            }
        except Exception as error:
            try:
                journal.reject(operation_id, reason=str(error))
            except Exception:
                pass
            raise

    def regional_field_receipt(self) -> Mapping[str, Any]:
        """Return measured identity and state for the current regional field."""

        row = self._computer_row()
        inspected = self._computer_inspect()
        task = inspected.get("task")
        _require(isinstance(task, Mapping), "regional field task is unavailable")
        _require(
            task.get("schema") == SEMANTIC_STATE_SCHEMA,
            "regional field is not running the current semantic cognition state",
        )
        current = task.get("current", {})
        family_counts = {
            str(kind): len(values)
            for kind, values in current.items()
            if isinstance(values, Mapping)
        } if isinstance(current, Mapping) else {}
        active_bindings = family_counts.get("Binding", 0)
        ledger = task.get("ledger", {})
        bounds = task.get("bounds")
        _require(isinstance(bounds, Mapping), "regional semantic bounds are unavailable")
        transitions = int(ledger.get("transitions", 0)) if isinstance(ledger, Mapping) else 0
        profile = row.profile
        task_region = self._named_value_region("task", inspected=inspected)
        checkpoint = inspected.get("checkpoint_receipt")
        return {
            "schema": REGIONAL_RECEIPT_SCHEMA,
            "implementation": "cassifi-learning-computer-v3",
            "kernel": COGNITION_KERNEL,
            "computer_id": row.computer_id,
            "computer_schema": "cassifi.learning-computer.v3",
            "field_state_sha256": inspected.get("state_sha256"),
            "task_state_sha256": inspected.get("task_state_sha256"),
            "task_used_words": task_region["used_words"],
            "task_capacity_words": task_region["capacity_words"],
            "field_bytes": profile.state_bytes,
            "profile": profile.as_dict(),
            "profile_sha256": profile.fingerprint,
            "catalog_sha256": profile.catalog_sha256,
            "kernel_catalog_sha256": STANDARD_KERNEL_CATALOG.fingerprint,
            "semantic_state_schema": task.get("schema"),
            "semantic_family_counts": family_counts,
            "semantic_active_bindings": active_bindings,
            "semantic_bounds": dict(bounds),
            "semantic_transitions": transitions,
            "logical_transition": inspected.get("logical_transition"),
            "status": inspected.get("status"),
            "all_finite": True,
            "resources": self.computer_resources(),
            "validation": "LearningComputer.inspect validated the persisted regional field",
            "checkpoint_receipt": checkpoint,
        }
    def state_receipt(self) -> Mapping[str, Any]:
        """Return the persisted owner and regional-field receipt."""

        regional = self.regional_field_receipt()
        owner_inspect = self.owner.inspect()
        resources = self.computer_resources()
        residency = resources.get("residency")
        # The owner may report residency directly, nested, or not at all; a
        # report that has no numbers yet is still a report.
        nested = residency.get("residency") if isinstance(residency, Mapping) else None
        residency_usage = (
            nested
            if isinstance(nested, Mapping)
            else residency
            if isinstance(residency, Mapping)
            else {}
        )
        usage_report = resources.get("resources")
        if not isinstance(usage_report, Mapping):
            usage_report = {}
        usage = owner_inspect.get("capacity", {}).get("usage", {})
        active_sources = self.owner.evidence.active_revision_ids()
        return {
            "schema": "cassi.field-qwen.regional-state-receipt.v2",
            "implementation": regional["implementation"],
            "kernel": regional["kernel"],
            "computer_id": regional["computer_id"],
            "state_sha256": regional["field_state_sha256"],
            "regional_state_sha256": regional["field_state_sha256"],
            "task_state_sha256": regional["task_state_sha256"],
            "task_used_words": regional["task_used_words"],
            "task_capacity_words": regional["task_capacity_words"],
            "generation": owner_inspect.get("field_generation"),
            "regional_logical_transition": regional["logical_transition"],
            "owner_state_sha256": owner_inspect.get("field_state_sha256"),
            "checkpoint_manifest_sha256": owner_inspect.get("checkpoint_manifest_sha256"),
            "field_bytes": regional["field_bytes"],
            "profile_sha256": regional["profile_sha256"],
            "catalog_sha256": regional["catalog_sha256"],
            "kernel_catalog_sha256": regional["kernel_catalog_sha256"],
            "semantic_state_schema": regional["semantic_state_schema"],
            "semantic_family_counts": regional["semantic_family_counts"],
            "semantic_active_bindings": regional["semantic_active_bindings"],
            "semantic_transitions": regional["semantic_transitions"],
            "active_source_revisions": len(active_sources),
            "all_source_revisions": len(self.owner.evidence.all_revision_ids()),
            "evidence_events": int(self.owner.evidence.event_count),
            "persistent_bytes": _tree_bytes(self.data_home),
            "workspace_bytes": _tree_bytes(self.data_home),
            "revocation_generation": owner_inspect.get("revocation_generation"),
            "resource_limits": resources.get("resource_limits"),
            "device": resources.get("device"),
            "logical_bytes": resources.get("logical_bytes"),
            "residency": residency,
            "ram_bytes": residency_usage.get("ram_bytes"),
            "vram_bytes": residency_usage.get("vram_bytes"),
            "storage_bytes": residency_usage.get("storage_bytes"),
            "scratch_bytes": usage_report.get("scratch_bytes"),
            "transfer_bytes": usage_report.get("transfer_bytes"),
            "pending_moves": usage_report.get("pending_moves"),
            "pending_growth": usage_report.get("pending_growth"),
            "unsettled_coupled_transactions": self.pending_publications(),
            "all_finite": regional["all_finite"],
            "validation": regional["validation"],
            "checkpoint_receipt": regional["checkpoint_receipt"],
        }

class ResearchWorkbench:
    """Adapter for the owner-backed programmable research workspace.

    The adapter never owns a second field.  A standalone workbench creates one
    :class:`ProgrammableSwarm` computer against ``memory.owner``; an entity
    supplies its already-installed swarm and therefore shares its exact
    workspace task and owner revision.
    """

    def __init__(
        self,
        memory: Any,
        *,
        runtime: Any | None = None,
        member_id: str | None = None,
        computer_id: str | None = None,
        principal: str | None = None,
    ) -> None:
        if memory is None:
            raise ValueError("memory is required")
        self.memory = memory
        self.principal = principal or "research-workbench"
        if runtime is None:
            from cassi_programmable_swarm import ProgrammableSwarm

            owner = getattr(memory, "owner", None)
            if owner is None:
                raise ValueError("standalone workbench memory must expose owner")
            runtime = ProgrammableSwarm()
            member_id = member_id or "research-workbench"
            computer_id = computer_id or f"research-workbench:{member_id}"
            runtime.add_member(
                member_id,
                owner,
                computer_id=computer_id,
                placement="logical-cpu",
            )
            runtime.ensure_computer(member_id)
            runtime.ensure_program_runtime(member_id)
        # Keep the shared adapter discoverable by Director construction.  This
        # is deliberately host-side metadata; it does not enter field state.
        try:
            setattr(memory, "workbench", self)
        except (AttributeError, TypeError):
            # Entity-owned protocol wrappers may expose immutable memory
            # handles; the explicit constructor argument remains authoritative.
            pass
        self.runtime = runtime
        self.member_id = member_id or "research-workbench"
        self.computer_id = computer_id or f"research-workbench:{self.member_id}"

    @staticmethod
    def _program_id(program: str | Mapping[str, Any]) -> str:
        if isinstance(program, str):
            if not program:
                raise ValueError("program_id must be nonempty text")
            return program
        if isinstance(program, Mapping):
            value = program.get("program_id", program.get("id"))
            if isinstance(value, str) and value:
                return value
        raise ValueError("program must be a program id or mapping with program_id")

    @staticmethod
    def _task_id(program_id: str) -> str:
        digest = hashlib.sha256(program_id.encode("utf-8")).hexdigest()[:24]
        return f"program:{digest}:workspace"

    def _workspace_task(self, program_id: str, *, create: bool) -> str:
        task_id = self._task_id(program_id)
        rows = self.runtime.list_tasks(self.member_id)
        if task_id in {row.get("task_id") for row in rows if isinstance(row, Mapping)}:
            return task_id
        if not create:
            raise ValueError(f"unknown research workspace for program {program_id!r}")
        self.runtime.start_workspace(
            self.member_id,
            workspace_id=program_id,
            principal=self.principal,
            task_id=task_id,
        )
        return task_id

    def _raw_state(self, program_id: str, *, create: bool = False) -> Mapping[str, Any]:
        task_id = self._workspace_task(program_id, create=create)
        return self.runtime.raw_state(self.member_id, task_id=task_id)

    @staticmethod
    def _unwrap(value: Mapping[str, Any]) -> Mapping[str, Any]:
        """Return the core row, not the swarm scheduler receipt envelope.

        A workspace command travels through the member's field computer, so its
        reply arrives wrapped in the scheduler's transition receipt.  The core's
        own row is the last output of that transition; the unwrap follows it
        instead of returning the envelope, which would hide ``wakeups``,
        ``invalidated`` and the other workspace results from the caller.
        """

        def core_row(row: Mapping[str, Any]) -> bool:
            schema = str(row.get("schema", ""))
            return schema.startswith(("cassi.workspace", "cassifi.workspace")) or any(
                key in row
                for key in ("field_revision", "selected", "required", "wakeups")
            )

        def last_output(run: Any) -> Mapping[str, Any] | None:
            receipts = run.get("transition_receipts") if isinstance(run, Mapping) else None
            if (
                isinstance(receipts, Sequence)
                and not isinstance(receipts, (str, bytes))
                and receipts
                and isinstance(receipts[-1], Mapping)
            ):
                output = receipts[-1].get("output")
                nested = output.get("last_output") if isinstance(output, Mapping) else None
                return nested if isinstance(nested, Mapping) else None
            return None

        current: Mapping[str, Any] = value
        for _ in range(8):
            receipt = current.get("receipt")
            run = current.get("run")
            candidates = [
                current.get("result"),
                receipt,
                receipt.get("run") if isinstance(receipt, Mapping) else None,
                run,
                last_output(receipt.get("run") if isinstance(receipt, Mapping) else None),
                last_output(run),
            ]
            advanced = None
            for candidate in candidates:
                if isinstance(candidate, Mapping) and core_row(candidate):
                    advanced = candidate
                    break
            if advanced is None:
                break
            current = advanced
        return dict(current)

    def sync(
        self,
        program: str | Mapping[str, Any],
        *,
        operation_id: str,
        outcome: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        if not isinstance(operation_id, str) or not operation_id:
            raise ValueError("operation_id must be nonempty text")
        program_id = self._program_id(program)
        self._workspace_task(program_id, create=True)
        # The core keeps the program name as the request's identity and reads
        # the program's own state from the outcome payload, so the projection
        # is folded there and the step's own outcome wins wherever both speak.
        projection = dict(program) if isinstance(program, Mapping) else {}
        payload: dict[str, Any] = (
            dict(outcome) if isinstance(outcome, Mapping) else {}
        )
        for key, value in projection.items():
            payload.setdefault(key, value)
        if projection:
            payload["candidate_program"] = projection
        payload.setdefault("program_status", projection.get("status"))
        payload.setdefault("mission", projection.get("mission"))
        payload.setdefault("question", projection.get("question"))
        payload.setdefault("question_id", projection.get("current_question_id"))
        command: dict[str, Any] = {
            "operation": "sync-workbench",
            "request_id": operation_id,
            "program": program_id,
            "outcome": payload,
        }
        result = self.runtime.workspace_command(
            self.member_id,
            command,
            task_id=self._task_id(program_id),
        )
        return self._unwrap(result)

    def context(
        self,
        program: str | Mapping[str, Any],
        *,
        question: str,
        question_id: str | None = None,
        maximum: int = 64,
    ) -> Mapping[str, Any]:
        program_id = self._program_id(program)
        if not isinstance(question, str) or not question:
            raise ValueError("question must be nonempty text")
        state = self._raw_state(program_id)
        from programs.workspace.runtime import select_context

        return dict(
            select_context(
                state,
                question,
                question_id=question_id,
                maximum=maximum,
            )
        )

    def inspect(self, program_id: str) -> Mapping[str, Any]:
        program_id = self._program_id(program_id)
        task_id = self._workspace_task(program_id, create=False)
        view = self.runtime.inspect(
            self.member_id,
            task_id=task_id,
            principal=self.principal,
            category="workbench",
            offset=0,
            limit=64,
        )
        resources = self.program_resources(program_id)
        return {
            "schema": "cassi.research-workbench-view.v1",
            "program_id": program_id,
            "workspace_task_id": task_id,
            "view": dict(view),
            "resources": dict(resources),
        }

    def command(
        self,
        program_id: str,
        command: str,
        *,
        operation_id: str,
        arguments: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        program_id = self._program_id(program_id)
        if not isinstance(command, str) or not command:
            raise ValueError("workspace command must be nonempty text")
        if arguments is not None and not isinstance(arguments, Mapping):
            raise ValueError("workspace command arguments must be an object")
        if not isinstance(operation_id, str) or not operation_id:
            raise ValueError("operation_id must be nonempty text")
        task_id = self._workspace_task(program_id, create=True)
        payload: dict[str, Any] = {"operation": command, "request_id": operation_id}
        if arguments is not None:
            payload.update(dict(arguments))
        payload["operation"] = command
        payload["request_id"] = operation_id
        result = self.runtime.workspace_command(
            self.member_id,
            payload,
            task_id=task_id,
        )
        return self._unwrap(result)

    def configure(
        self,
        program_id: str,
        *,
        computer_id: str | None = None,
        policy: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        owner = self._owner()
        method = getattr(owner, "configure_program_residency", None)
        if not callable(method):
            raise RuntimeError("owner does not expose program residency configuration")
        return dict(
            method(
                program_id,
                computer_id=computer_id or self.computer_id,
                policy=None if policy is None else dict(policy),
            )
        )

    def activate(self, program: str | Mapping[str, Any]) -> Mapping[str, Any]:
        program_id = self._program_id(program)
        method = getattr(self._owner(), "activate_program_residency", None)
        if not callable(method):
            raise RuntimeError("owner does not expose program residency activation")
        return dict(method(program_id))

    def release(self, program_id: str) -> Mapping[str, Any]:
        program_id = self._program_id(program_id)
        method = getattr(self._owner(), "release_program_residency", None)
        if not callable(method):
            raise RuntimeError("owner does not expose program residency release")
        return dict(method(program_id))

    def prefetch(
        self,
        program_id: str,
        dependencies: Sequence[Mapping[str, Any]],
        *,
        maximum_bytes: int | None = None,
    ) -> Mapping[str, Any]:
        """Warm exact workbench pages without changing logical field state."""
        program_id = self._program_id(program_id)
        if not isinstance(dependencies, Sequence) or isinstance(dependencies, (str, bytes)):
            raise ValueError("dependencies must be a sequence of context references")
        if maximum_bytes is not None and (
            isinstance(maximum_bytes, bool)
            or not isinstance(maximum_bytes, int)
            or maximum_bytes < 0
        ):
            raise ValueError("maximum_bytes must be a nonnegative integer")

        def page_rows(value: Any) -> list[Mapping[str, Any]]:
            if isinstance(value, bool):
                return []
            if isinstance(value, int) and value >= 0:
                return [{"index": value}]
            if isinstance(value, Mapping):
                return [dict(value)]
            if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
                return [
                    (
                        {"index": item}
                        if isinstance(item, int) and not isinstance(item, bool)
                        else dict(item)
                    )
                    for item in value
                    if isinstance(item, Mapping)
                    or (
                        isinstance(item, int)
                        and not isinstance(item, bool)
                        and item >= 0
                    )
                ]
            return []

        resource_pages: list[Mapping[str, Any]] = []
        resource_error: str | None = None
        try:
            resources: Mapping[str, Any] = self.program_resources(program_id)
        except Exception as exc:
            # A resource report that cannot be read leaves the pages unknown;
            # the receipt says so instead of guessing a page layout.
            resources = {}
            resource_error = f"{type(exc).__name__}: {exc}"[:400]
        for key in ("pages", "page_indexes", "resident_pages", "workbench_pages"):
            resource_pages.extend(page_rows(resources.get(key)))
        nested = resources.get("program") if isinstance(resources, Mapping) else None
        if isinstance(nested, Mapping):
            resource_pages.extend(page_rows(nested.get("pages")))
        expected_root = next(
            (
                resources.get(key)
                for key in (
                    "workspace_root_sha256",
                    "program_root_sha256",
                    "root_sha256",
                    "workspace_root",
                )
                if isinstance(resources.get(key), str) and len(resources[key]) == 64
            ),
            None,
        )
        page_bytes = lambda page: max(
            0,
            int(
                page.get("bytes", page.get("nbytes", page.get("size", page.get("byte_count", 0)))) or 0
            ),
        )
        state = self._raw_state(program_id)
        workbench = state.get("workbench")
        programs = workbench.get("programs", {}) if isinstance(workbench, Mapping) else {}
        program_state = programs.get(program_id, {}) if isinstance(programs, Mapping) else {}
        records = program_state.get("records", {}) if isinstance(program_state, Mapping) else {}
        if not isinstance(records, Mapping):
            records = {}

        rows: list[dict[str, Any]] = []
        pages: list[Mapping[str, Any]] = []
        roots: set[str] = set()
        discarded = 0
        for dependency in dependencies:
            key = dependency.get("key") if isinstance(dependency, Mapping) else None
            report: dict[str, Any] = {
                "key": key,
                "resolved": False,
                "pages": [],
                "bytes": 0,
                "reason": None,
            }
            if not isinstance(dependency, Mapping):
                report["reason"] = "dependency is not an object"
                rows.append(report)
                continue
            matched = None
            explicit = dependency.get("pages", dependency.get("page", dependency.get("page_ref")))
            for raw in records.values():
                if not isinstance(raw, Mapping):
                    continue
                raw_value = raw.get("value")
                canonical = all(
                    dependency.get(field) == raw.get(field)
                    for field in ("key", "kind", "value", "source_refs", "dependencies")
                )
                path_version = (
                    isinstance(raw_value, Mapping)
                    and dependency.get("path") == raw_value.get("path")
                    and dependency.get("version") == raw_value.get("version")
                )
                if not canonical and not path_version:
                    continue
                raw_explicit = raw.get("pages", raw.get("page", raw.get("page_ref")))
                if raw_explicit is None and isinstance(raw_value, Mapping):
                    raw_explicit = raw_value.get("pages", raw_value.get("page", raw_value.get("page_ref")))
                if explicit is not None and raw_explicit is not None:
                    if page_rows(explicit) != page_rows(raw_explicit):
                        continue
                elif explicit is not None and raw_explicit is None:
                    continue
                matched = raw
                break
            if matched is None:
                report["reason"] = "dependency is not an exact selected context reference"
                rows.append(report)
                continue
            # An explicit page is already validated above; absent page metadata
            # deliberately falls through to this program's resource page set.
            explicit = dependency.get("pages", dependency.get("page", dependency.get("page_ref")))
            resolved_pages = page_rows(explicit) or [dict(page) for page in resource_pages]
            if not resolved_pages:
                report["reason"] = "program has no resident workbench pages"
                rows.append(report)
                continue
            page_roots = {
                str(page.get("root_sha256"))
                for page in resolved_pages
                if isinstance(page.get("root_sha256"), str)
            }
            if not page_roots and isinstance(expected_root, str):
                page_roots.add(expected_root)
            if not page_roots:
                report["reason"] = "workspace root is unavailable"
                rows.append(report)
                continue
            if expected_root is not None and any(root != expected_root for root in page_roots):
                discarded += 1
                report["reason"] = "stale workspace root"
                report["discarded"] = True
                rows.append(report)
                continue
            if len(page_roots) > 1:
                discarded += 1
                report["reason"] = "dependency pages have multiple roots"
                report["discarded"] = True
                rows.append(report)
                continue
            roots.update(page_roots)
            pages.extend(resolved_pages)
            report["resolved"] = True
            report["pages"] = resolved_pages
            report["page"] = resolved_pages[0] if len(resolved_pages) == 1 else None
            report["bytes"] = sum(page_bytes(page) for page in resolved_pages)
            rows.append(report)

        if len(roots) > 1:
            # A mixed-root batch must never reach the owner; stale pages are
            # reported explicitly rather than warming a logically inconsistent set.
            for report in rows:
                if report["resolved"]:
                    report["resolved"] = False
                    report["reason"] = "dependency pages have multiple roots"
                    report["discarded"] = True
            discarded += sum(1 for report in rows if report.get("discarded"))
            pages = []
            roots.clear()
        loaded = 0
        owner_report: Mapping[str, Any] = {}
        method = getattr(self._owner(), "prefetch_program_pages", None)
        if pages and callable(method):
            root = next(iter(roots), expected_root)
            if isinstance(root, str) and len(root) == 64:
                owner_pages = [
                    page["index"]
                    if isinstance(page, Mapping) and isinstance(page.get("index"), int)
                    else page
                    for page in pages
                ]
                try:
                    owner_report = dict(
                        method(
                            program_id,
                            owner_pages,
                            expected_root_sha256=root,
                            max_bytes=maximum_bytes,
                        )
                    )
                except Exception as exc:
                    if "STALE_ROOT" not in str(exc).upper():
                        raise
                    for report in rows:
                        if report["resolved"]:
                            report["resolved"] = False
                            report["discarded"] = True
                            report["reason"] = "stale workspace root"
                    discarded += sum(1 for report in rows if report.get("discarded"))
                    owner_report = {"status": "discarded", "reason": "stale workspace root"}
                loaded = int(
                    owner_report.get(
                        "loaded_bytes",
                        owner_report.get("bytes", owner_report.get("loaded", 0)),
                    )
                    or 0
                )
        elif pages and not callable(method):
            for report in rows:
                if report["resolved"]:
                    report["resolved"] = False
                    report["reason"] = "owner does not expose program page prefetch"
        resolved_count = sum(1 for report in rows if report["resolved"])
        page_count = len({json.dumps(dict(page), sort_keys=True) for page in pages})
        requested = sum(int(report.get("bytes", 0) or 0) for report in rows)
        return {
            **owner_report,
            "schema": "cassi.research-workbench-prefetch.v1",
            "program_id": program_id,
            "rows": rows,
            "dependencies": len(rows),
            "unresolved": sum(1 for report in rows if not report["resolved"]),
            "pages": (
                int(owner_report["pages"])
                if isinstance(owner_report.get("pages"), (int, float))
                else page_count
            ),
            "loaded_bytes": loaded,
            "skipped_bytes": max(0, requested - loaded),
            "discarded": discarded + int(owner_report.get("discarded", 0) or 0),
            **(
                {"resource_report_error": resource_error}
                if resource_error
                else {}
            ),
        }

    def program_resources(self, program_id: str | None = None) -> Mapping[str, Any]:
        method = getattr(self._owner(), "program_resources", None)
        if not callable(method):
            raise RuntimeError("owner does not expose program resource inspection")
        if program_id is None:
            return dict(method(None))
        # A program with no configured residency still has a computer: the one
        # this workbench runs its workspaces on.  The owner derives the default
        # report for that computer instead of the first one it happens to list.
        return dict(
            method(
                self._program_id(program_id),
                computer_id=self.computer_id,
            )
        )

    def _owner(self) -> Any:
        """Use the runtime's serialized owner when an entity supplied one."""
        members = getattr(self.runtime, "_members", None)
        if isinstance(members, Mapping):
            member = members.get(self.member_id)
            owner = getattr(member, "owner", None)
            if owner is not None:
                return owner
        owner = getattr(self.memory, "owner", None)
        if owner is None:
            raise RuntimeError("workbench owner is unavailable")
        return owner


class LocalQwenClient:
    """Loopback llama.cpp client with verified local image input."""
    _VISION_PROBE_PNG_BASE64 = (
        "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAIAAAD8GO2jAAAAKklEQVR4nGOQeGBAU8QwasGoBaMWjFowasGoBaMWjFowasGoBaMWDBULAFDFoD1Ig7cqAAAAAElFTkSuQmCC"
    )

    def __init__(
        self,
        base_url: str,
        *,
        model_path: Path,
    ) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise ValueError("Qwen server must be loopback HTTP")
        self.host = parsed.hostname
        self.port = parsed.port or 80
        self.prefix = parsed.path.rstrip("/")
        self.model_path = Path(model_path).resolve()
        if not self.model_path.is_file():
            raise FileNotFoundError(self.model_path)
        self.model_sha256 = _sha256_path(self.model_path)
        self.model_id = self._discover_model(timeout=60.0)

    def _discover_model(self, *, timeout: float) -> str:
        status, models, raw = self.request("GET", "/v1/models", timeout=timeout)
        _require(status == 200, f"model discovery returned HTTP {status}: {raw}")
        entries = models.get("data", [])
        _require(isinstance(entries, list) and len(entries) == 1, "server must expose exactly one model")
        model_id = entries[0].get("id") if isinstance(entries[0], Mapping) else None
        _require(isinstance(model_id, str) and Path(model_id).name == self.model_path.name,
                 "served model does not match requested model")
        return model_id

    def request(
        self, method: str, path: str, body: Mapping[str, Any] | None = None,
        *, timeout: float = 600.0,
    ) -> tuple[int, dict[str, Any], str]:
        connection = http.client.HTTPConnection(self.host, self.port, timeout=timeout)
        payload = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers = {} if payload is None else {"content-type": "application/json"}
        try:
            connection.request(method, self.prefix + path, body=payload, headers=headers)
            response = connection.getresponse()
            raw = response.read().decode("utf-8")
            status = response.status
        finally:
            connection.close()
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"server returned non-JSON response: {raw[:200]}") from exc
        _require(isinstance(value, dict), "server JSON response is not an object")
        return status, value, raw

    def complete(
        self,
        *,
        prompt: str,
        max_tokens: int,
        thinking: bool = False,
        response_format: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        request_body: dict[str, Any] = {
            "model": self.model_id,
            "messages": [
                {"role": "system", "content": "Complete the work accurately. Follow the requested output format. Return only the answer, with no analysis or markdown fence."},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": 0,
            "stream": False,
            "reasoning_format": "deepseek",
            "logprobs": True,
            "top_logprobs": 20,
            "chat_template_kwargs": {"enable_thinking": bool(thinking)},
        }
        if response_format is not None:
            request_body["response_format"] = dict(response_format)
        started = time.perf_counter_ns()
        status, body, raw = self.request(
            "POST", "/v1/chat/completions", request_body, timeout=1_800.0
        )
        elapsed_ns = time.perf_counter_ns() - started
        _require(status == 200, f"Qwen completion returned HTTP {status}: {raw}")
        choices = body.get("choices")
        if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], Mapping):
            raise RuntimeError("Qwen response has no single choice")
        choice = choices[0]
        message = choice.get("message")
        if not isinstance(message, Mapping) or not isinstance(message.get("content"), str):
            raise RuntimeError("Qwen response content is missing")
        return {
            "content": message["content"],
            "reasoning_content": message.get("reasoning_content", ""),
            "thinking": bool(thinking),
            "finish_reason": choice.get("finish_reason"),
            "logprobs": choice.get("logprobs"),
            "generation_parameters": {key: value for key, value in request_body.items() if key not in {"model", "messages"}},
            "elapsed_ns": elapsed_ns,
            "usage": body.get("usage", {}),
            "timings": body.get("timings", {}),
            "server_cassi_receipt": body.get("cassi"),
        }

    def count_completion_input_tokens(
        self,
        *,
        prompt: str,
        max_tokens: int,
        thinking: bool = False,
        response_format: Mapping[str, Any] | None = None,
    ) -> int:
        """Ask llama.cpp for the exact token count of one completion request."""
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be nonempty text")
        if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens < 1:
            raise ValueError("max_tokens must be a positive integer")
        body: dict[str, Any] = {
            "model": self.model_id,
            "messages": [
                {"role": "system", "content": "Complete the work accurately. Follow the requested output format. Return only the answer, with no analysis or markdown fence."},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": 0,
            "stream": False,
            "reasoning_format": "deepseek",
            "logprobs": True,
            "top_logprobs": 20,
            "chat_template_kwargs": {"enable_thinking": bool(thinking)},
        }
        if response_format is not None:
            body["response_format"] = dict(response_format)
        status, result, raw = self.request("POST", "/v1/chat/completions/input_tokens", body)
        _require(status == 200, f"Qwen input-token count returned HTTP {status}: {raw}")
        value = result.get("input_tokens")
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise RuntimeError("Qwen input-token response is invalid")
        return value

    def probe_request_policy(self, *, max_tokens: int = 64) -> Mapping[str, Any]:
        status, props, raw = self.request("GET", "/props")
        _require(status == 200, f"/props returned HTTP {status}: {raw}")
        caps = props.get("chat_template_caps")
        caps = ({str(key): bool(value) for key, value in sorted(caps.items())}
                if isinstance(caps, Mapping) else {})
        template = str(props.get("chat_template") or "")
        prompt = 'Return only this JSON: {"sum": 5}'
        quiet = self.complete(prompt=prompt, max_tokens=max_tokens, thinking=False)
        loud = self.complete(prompt=prompt, max_tokens=max_tokens, thinking=True)

        def reading(result: Mapping[str, Any]) -> dict[str, Any]:
            content = str(result.get("content") or "")
            return {
                "completion_tokens": int((result.get("usage") or {}).get("completion_tokens") or 0),
                "content_chars": len(content),
                "reasoning_chars": len(str(result.get("reasoning_content") or "")),
                "think_tag_in_content": "<think" in content,
            }

        quiet_reading, loud_reading = reading(quiet), reading(loud)
        return {
            "identity": {
                "build_info": str(props.get("build_info") or ""),
                "chat_template_sha256": _sha256_text(template),
                "chat_template_chars": len(template),
                "chat_template_has_enable_thinking": "enable_thinking" in template,
                "chat_template_caps": caps,
            },
            "probe": {"thinking_off": quiet_reading, "thinking_on": loud_reading},
            "flag_effective": (
                quiet_reading["content_chars"] > 0
                and quiet_reading["reasoning_chars"] == 0
                and not quiet_reading["think_tag_in_content"]
                and (loud_reading["reasoning_chars"] > 0
                     or loud_reading["think_tag_in_content"]
                     or loud_reading["completion_tokens"] > quiet_reading["completion_tokens"])
            ),
        }
def emitter_record(record: Mapping[str, Any]) -> Mapping[str, Any]:
    """Project one recalled record into the knowledge the emitter consumes.

    Provenance digests stay in the transaction receipt; the frame carries the
    asserted knowledge, because two 64-character digests per record cost more
    emitter tokens than the fact itself.
    """

    return {
        "source_id": record.get("source_id"),
        "context": record.get("context"),
        "payload": record.get("payload"),
    }


def emission_frame(
    *,
    task: str,
    output_contract: str,
    recall: Mapping[str, Any] | None,
    records: Sequence[Mapping[str, Any]] | None = None,
) -> Mapping[str, Any]:
    """Compose the fixed emitter frame and name exactly which records it carries.

    The emitter owns a fixed context, so the frame that carries field-recalled
    knowledge must stay inside it.  A frame is composed here and fitted by
    measurement in :func:`fit_emission_frame`; the accounting returned here
    makes a shortened frame visible instead of silent.

    Each carried record also yields a character span in ``segments``, and
    ``memory_segment`` covers the memory block itself, so a position in the
    composed frame resolves back to the record it came from.  Token offsets are
    a separate measurement: pass the frame to :func:`measure_segment_tokens`
    with the emitter's own counter.
    """

    all_records = [] if recall is None else list(recall.get("records", ()))
    included = all_records if records is None else list(records)
    dropped = all_records[len(included) :]
    projected = [emitter_record(record) for record in included]
    encoded = [
        json.dumps(
            row,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        for row in projected
    ]
    memory = "[" + ",".join(encoded) + "]"
    prompt = (
        "Perform this work using only facts in the task and FIELD_WORK_MEMORY. "
        "FIELD_WORK_MEMORY is authoritative when present. If a required private fact is absent, use the literal string UNKNOWN; do not guess.\n\n"
        f"FIELD_WORK_MEMORY={memory}\n\n"
        f"TASK={task}\n\n"
        f"OUTPUT_CONTRACT={output_contract}"
    )
    memory_start = prompt.index("FIELD_WORK_MEMORY=") + len("FIELD_WORK_MEMORY=")
    cursor = memory_start + 1
    segments = []
    for record, text in zip(included, encoded):
        segments.append(
            {
                "source_revision_id": str(record.get("source_revision_id")),
                "start": cursor,
                "stop": cursor + len(text),
            }
        )
        cursor += len(text) + 1
    return {
        "prompt": prompt,
        "prompt_bytes": len(prompt.encode("utf-8")),
        "memory_bytes": len(memory.encode("utf-8")),
        "memory_segment": {
            "start": memory_start,
            "stop": memory_start + len(memory),
        },
        "segments": segments,
        "records_included": len(included),
        "records_dropped": len(dropped),
        "included_source_revision_ids": [
            str(record.get("source_revision_id")) for record in included
        ],
        "dropped_source_revision_ids": [
            str(record.get("source_revision_id")) for record in dropped
        ],
    }


def fit_emission_frame(
    *,
    task: str,
    output_contract: str,
    recall: Mapping[str, Any] | None,
    token_ceiling: int,
    count_tokens: Callable[[str], int],
) -> Mapping[str, Any]:
    """Fit the emitter frame to a measured token ceiling.

    Recorded knowledge is dropped from the tail of the recall until the runtime's
    own tokenizer measures the frame inside the ceiling, and every dropped record
    is named in the returned accounting.  A frame that cannot fit even without
    recalled knowledge is refused rather than sent to a context that cannot hold it.

    Frame cost grows with each admitted record, so the surviving prefix is found
    by bisection and every measurement is reused.
    """

    if not isinstance(token_ceiling, int) or isinstance(token_ceiling, bool) or token_ceiling < 1:
        raise ValueError("emission frame token ceiling must be a positive integer")
    records = [] if recall is None else list(recall.get("records", ()))
    measured: dict[int, int] = {}

    def tokens_for(kept: int) -> int:
        if kept not in measured:
            frame = emission_frame(
                task=task,
                output_contract=output_contract,
                recall=recall,
                records=records[:kept],
            )
            measured[kept] = int(count_tokens(frame["prompt"]))
        return measured[kept]

    if tokens_for(0) > token_ceiling:
        raise RuntimeError(
            f"emission frame needs {measured[0]} tokens even without recalled "
            f"knowledge, over the {token_ceiling}-token emitter ceiling"
        )
    low, high = 0, len(records)
    while low < high:
        middle = (low + high + 1) // 2
        if tokens_for(middle) <= token_ceiling:
            low = middle
        else:
            high = middle - 1
    return {
        **emission_frame(
            task=task,
            output_contract=output_contract,
            recall=recall,
            records=records[:low],
        ),
        "prompt_tokens": tokens_for(low),
        "token_ceiling": token_ceiling,
    }


def measure_segment_tokens(
    frame: Mapping[str, Any],
    *,
    count_tokens: Callable[[str], int],
) -> list[dict[str, Any]]:
    """Bind each frame segment to token offsets measured on the composed prompt.

    Char offsets are exact at composition; token offsets depend on the runtime's
    tokenizer, so the caller supplies it and pays one prefix measurement per
    segment boundary. A token that straddles a boundary stays on the earlier side.
    """

    prompt = str(frame["prompt"])
    return [
        {
            **segment,
            "token_start": int(count_tokens(prompt[: int(segment["start"])])),
            "token_stop": int(count_tokens(prompt[: int(segment["stop"])])),
        }
        for segment in frame["segments"]
    ]


def _encode_memory_block(records: Sequence[Mapping[str, Any]]) -> str:
    return json.dumps(
        list(records),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def work_prompt(
    *,
    task: str,
    output_contract: str,
    recall: Mapping[str, Any] | None,
) -> str:
    return emission_frame(
        task=task, output_contract=output_contract, recall=recall
    )["prompt"]


def ownership_receipt(
    *,
    model_path: Path,
    model_sha256: str,
    recalls: Sequence[Mapping[str, Any]],
    qwen_results: Sequence[Mapping[str, Any]],
    state: Mapping[str, Any],
) -> Mapping[str, Any]:
    selected = sum(len(row.get("selected_source_revision_ids", ())) for row in recalls)
    generated = sum(
        int(row.get("usage", {}).get("completion_tokens", 0))
        for row in qwen_results
    )
    model_bytes = Path(model_path).stat().st_size
    return {
        "schema": OWNERSHIP_SCHEMA,
        "intervention": "off-graph-current-cassifi-work-memory",
        "native_dynamic_state_bytes_removed": 0,
        "remaining_native_state_footprint": "unchanged full Qwen context/KV path",
        "native_ops_skipped": 0,
        "native_layers_skipped": 0,
        "native_output_rows_skipped": 0,
        "qwen_weight_bytes_touched_per_token": None,
        "qwen_weight_bytes_upper_bound_per_decode": model_bytes,
        "qwen_weight_bytes_touched_per_generated_token_estimate": model_bytes,
        "qwen_weight_bytes_touched_for_generated_tokens_estimate": model_bytes * generated,
        "qwen_weight_bytes_estimate_assumption": (
            "Dense autoregressive decode is assumed to touch approximately the full resident checkpoint weight region "
            "once per emitted token. Model-file bytes are used as a proxy and include non-weight metadata; prompt "
            "processing weight traffic is not included. Exact backend memory transactions were not instrumented."
        ),
        "qwen_model_sha256": model_sha256,
        "qwen_generated_tokens": generated,
        "field_owned_decisions": {
            "source_revision_selections": selected,
            "durable_record_updates": int(state["evidence_events"]),
            "token_emissions": 0,
            "reasoning_steps": 0,
        },
        "qwen_owned_decisions": {
            "token_emissions": generated,
            "natural_language_reasoning": True,
            "native_graph": True,
        },
        "field_state": dict(state),
        "cassifi_source_identity": cassifi_source_identity(),
        "claim_boundary": "CassiFI owns the owner-operated cognition.field regional state, semantic binding/query decisions, persistent work memory, and exact source exposure; Qwen owns the full native graph and emitted tokens.",
    }
def qwen_enabled() -> bool:
    return os.environ.get("CASSI_QWEN_ENABLE", "0") == "1"
