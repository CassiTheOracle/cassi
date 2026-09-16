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
        "cassi_field_atlas.py",
        "cassi_field_cognition.py",
        "cassi_field_computer.py",
        "cassi_field_owner.py",
        "cassi_field_program.py",
        "cassi_field_regions.py",
        "cassi_field_transceiver.py",
        "cassi_general_matched_field.py",
        "cassi_hybrid_inference.py",
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

from cassi_field_cognition import SEMANTIC_STATE_SCHEMA, semantic_cognition_state
from cassi_field_owner import CapacityLimits, FieldIntelligenceOwner, SourceInput
from cassi_field_regions import RegionalProfile, named_object_id
from cassi_regional_catalog import STANDARD_KERNEL_CATALOG


MEMORY_SCHEMA = "cassi.field-qwen.memory-record.v2"
RECALL_SCHEMA = "cassi.field-qwen.recall.v2"
OWNERSHIP_SCHEMA = "cassi.field-qwen.ownership.v2"
REGIONAL_RECEIPT_SCHEMA = "cassi.field-qwen.regional-field-receipt.v2"
PUBLICATION_GATE_SCHEMA = "cassi.field-qwen.publication-gate.v1"
CONTINUATION_SCHEMA = "cassi.field-qwen.continuation-receipt.v1"
COGNITION_KERNEL = "cognition.field"
COMPUTER_ID = "field-qwen:work-memory"
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
    # compatibility image.  The current CassiTheory corpus reached the
    # 196,608-word task boundary; 196,608 modes provide a 294,912-word
    # task region while preserving a bounded, reopen-checked field image.
    "mode_count": 196_608,
    "directory_capacity": 256,
    "max_native_work": 32,
}
SEMANTIC_BOUNDS: Mapping[str, int] = {
    "max_alternatives": 1,
    "max_observations": 1,
    "max_records": 4_096,
    "max_timeline": 4_096,
    "max_operations": 4_096,
    "max_versions": 8,
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

_CONTEXT_VALUE_TYPES = (str, int, bool, type(None))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


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

    def __init__(self, data_home: Path, *, limits: CapacityLimits | None = None) -> None:
        self.data_home = Path(data_home).resolve()
        self.owner = FieldIntelligenceOwner(self.data_home, limits=limits)
        self._closed = False
        self._ensure_regional_computer()

    def __enter__(self) -> "CassiFieldWorkMemory":
        return self

    def __exit__(self, _exc_type: Any, _exc: Any, _traceback: Any) -> None:
        self.close()

    def close(self) -> None:
        if not self._closed:
            self.owner.close()
            self._closed = True

    @staticmethod
    def _profile() -> RegionalProfile:
        return RegionalProfile(
            **dict(COMPUTER_PROFILE),
            kernel_names=STANDARD_KERNEL_CATALOG.names,
        )

    @classmethod
    def _profile_dict(cls) -> Mapping[str, Any]:
        profile = cls._profile()
        return profile.as_dict()

    def _computer_row(self) -> Any:
        rows = tuple(self.owner.state.computers)
        _require(
            len(rows) == 1 and rows[0].computer_id == COMPUTER_ID,
            "CassiFI work memory requires exactly one current regional computer",
        )
        row = rows[0]
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
        _require(
            isinstance(rows, list)
            and len(rows) == 1
            and isinstance(rows[0], Mapping)
            and rows[0].get("computer_id") == COMPUTER_ID,
            "CassiFI work memory regional computer inspection is incomplete",
        )
        return rows[0]

    def _named_value_region(self, name: str) -> Mapping[str, int]:
        """Return measured allocation and occupancy for one named value."""
        row = self._computer_row()
        controller = row._controller()
        object_id = named_object_id(
            row.field._field,
            row.profile,
            STANDARD_KERNEL_CATALOG,
            name,
        )
        raw = controller.inspect(row.field)
        regions = raw.get("regions") if isinstance(raw, Mapping) else None
        if isinstance(regions, list):
            for region in regions:
                if isinstance(region, Mapping) and int(region.get("slot", -1)) == object_id:
                    return {
                        "capacity_words": int(region["capacity_words"]),
                        "used_words": int(region["used_words"]),
                    }
        raise RuntimeError(f"regional named value region is unavailable: {name}")

    def _ensure_regional_computer(self) -> None:
        usage = self.owner.inspect().get("capacity", {}).get("usage", {})
        existing = tuple(self.owner.state.computers)
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
            configured = self.owner.operate_computer(
                "field-qwen:computer:configure:v2",
                computer_id=COMPUTER_ID,
                action="configure",
                arguments={"profile": self._profile_dict()},
                expected_state_sha256=self.owner.state.state_sha256,
            )
            _require(
                configured.get("receipt", {}).get("action") == "configure",
                "regional work-memory computer configuration was not committed",
            )
        self._computer_row()
        task = self._computer_inspect().get("task")
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

    def _submit_semantic_state(self) -> Mapping[str, Any]:
        semantic_operation_id = self._semantic_operation_id("initialize", SEMANTIC_FRAME)
        state = semantic_cognition_state(
            scope=SEMANTIC_SCOPE,
            frame=SEMANTIC_FRAME,
            bounds=SEMANTIC_BOUNDS,
        )
        result = self.owner.operate_computer(
            self._owner_operation_id("computer-submit", SEMANTIC_FRAME),
            computer_id=COMPUTER_ID,
            action="submit",
            arguments={
                "kernel": COGNITION_KERNEL,
                "state": state,
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
    ) -> Mapping[str, Any]:
        """Drain a bounded semantic continuation through the owner surface."""
        current = inspected
        for continuation_index in range(SEMANTIC_SETTLEMENT_LIMIT):
            task = current.get("task")
            _require(
                isinstance(task, Mapping)
                and task.get("schema") == SEMANTIC_STATE_SCHEMA,
                "regional work-memory semantic task disappeared during settlement",
            )
            if current.get("status") in {
                "faulted",
                "exhausted",
                "counter-exhausted",
            }:
                raise RuntimeError(
                    "regional work-memory semantic request faulted before settlement"
                )
            continuation = task.get("continuation")
            _require(
                isinstance(continuation, Mapping),
                "regional work-memory semantic continuation is unavailable",
            )
            if continuation.get("request") is None:
                return current
            before = self.owner.state.state_sha256
            self.owner.operate_computer(
                self._owner_operation_id(
                    "computer-advance",
                    f"{label}:{continuation_index}",
                ),
                computer_id=COMPUTER_ID,
                action="advance",
                arguments={"steps": 1},
                expected_state_sha256=before,
            )
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
        before = self.owner.state.state_sha256
        result = self.owner.operate_computer(
            self._owner_operation_id("computer-invoke", label),
            computer_id=COMPUTER_ID,
            action="invoke",
            arguments={"arguments": dict(request), "steps": 1},
            expected_state_sha256=before,
        )
        inspect = self._settle_semantic(
            label=label,
            inspected=self._computer_inspect(),
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
        self, inspected: Mapping[str, Any] | None = None
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
                row.get("id") == record_id
                and row.get("kind") == "Binding"
                and row.get("status") == "active",
                "CassiFI semantic binding reference is not active",
            )
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
            "candidate_binding_ids": [str(row.get("id")) for row in candidates],
            "excluded_ineligible": ineligible,
            "excluded_ineligible_count": len(ineligible),
            "inspect_receipt": inspect_result,
            "query_receipts": query_receipts,
            "field_state_before_sha256": before,
            "field_state_after_sha256": after["field_state_sha256"],
            "field_generation": after["logical_transition"],
            "checkpoint_receipt": after["checkpoint_receipt"],
            "regional_field": after,
        }

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
        task_region = self._named_value_region("task")
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
            "validation": "LearningComputer.inspect validated the persisted regional field",
            "checkpoint_receipt": checkpoint,
        }

    def state_receipt(self) -> Mapping[str, Any]:
        """Return the persisted owner and regional-field receipt."""

        regional = self.regional_field_receipt()
        owner_inspect = self.owner.inspect()
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
            "semantic_bounds": regional["semantic_bounds"],
            "semantic_transitions": regional["semantic_transitions"],
            "active_source_revisions": len(active_sources),
            "all_source_revisions": len(self.owner.evidence.all_revision_ids()),
            "revocation_generation": owner_inspect.get("revocation_generation"),
            "evidence_events": self.owner.evidence.event_count,
            "persistent_bytes": _tree_bytes(self.data_home),
            "workspace_bytes": usage.get("workspace_bytes"),
            "unsettled_coupled_transactions": self.pending_publications(),
            "all_finite": regional["all_finite"],
            "validation": regional["validation"],
            "checkpoint_receipt": regional["checkpoint_receipt"],
        }

class LocalQwenClient:
    """Minimal deterministic client for a separately launched loopback llama.cpp server."""

    def __init__(self, base_url: str, *, model_path: Path) -> None:
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
        status, models, raw = self.request("GET", "/v1/models", timeout=60.0)
        _require(status == 200, f"model discovery returned HTTP {status}: {raw}")
        entries = models.get("data", [])
        _require(
            isinstance(entries, list) and len(entries) == 1,
            "server must expose exactly one model",
        )
        model_id = entries[0].get("id")
        _require(
            isinstance(model_id, str) and Path(model_id).name == self.model_path.name,
            "served model does not match requested model",
        )
        self.model_id = model_id

    def request(
        self,
        method: str,
        path: str,
        body: Mapping[str, Any] | None = None,
        *,
        timeout: float = 600.0,
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
    ) -> Mapping[str, Any]:
        """Complete one prompt under the documented offline request policy.

        Thinking defaults off. A thinking model charged for its reasoning inside
        a short answer budget emits nothing at all once the reasoning outruns the
        cap, so the policy disables it; requesting it here returns the reasoning
        trace beside the answer, which a receipt must carry to show what the
        budget bought.
        """

        request_body = {
            "model": self.model_id,
            "messages": [
                {
                    "role": "system",
                    "content": "Complete the work accurately. Follow the requested output format. Return only the answer, with no analysis or markdown fence.",
                },
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
        started = time.perf_counter_ns()
        status, body, raw = self.request("POST", "/v1/chat/completions", request_body)
        elapsed_ns = time.perf_counter_ns() - started
        _require(status == 200, f"Qwen completion returned HTTP {status}: {raw}")
        choices = body.get("choices")
        if not isinstance(choices, list) or len(choices) != 1:
            raise RuntimeError("Qwen response has no single choice")
        choice = choices[0]
        if not isinstance(choice, Mapping):
            raise RuntimeError("Qwen response choice is not an object")
        message = choice.get("message")
        if not isinstance(message, Mapping) or not isinstance(message.get("content"), str):
            raise RuntimeError("Qwen response content is missing")
        content = message["content"]
        return {
            "content": content,
            "reasoning_content": message.get("reasoning_content", ""),
            "thinking": bool(thinking),
            "logprobs": choice.get("logprobs"),
            # What was actually sent, so a receipt can record evidence rather
            # than a restatement of the policy the caller meant to apply.
            "generation_parameters": {
                key: value
                for key, value in request_body.items()
                if key not in {"model", "messages"}
            },
            "elapsed_ns": elapsed_ns,
            "usage": body.get("usage", {}),
            "timings": body.get("timings", {}),
            "server_cassi_receipt": body.get("cassi"),
        }

    def probe_request_policy(self, *, max_tokens: int = 64) -> Mapping[str, Any]:
        """Separate what this server is from what it does about `enable_thinking`.

        `/props` reports the loaded template text and the jinja language caps,
        neither of which answers the question: the server computes
        `enable_reasoning != 0 && use_jinja && template_supports_thinking` for
        itself and reports no thinking flag. The identity fields below come from
        the endpoint; the operative answer comes from two identical requests
        that differ only in the flag.
        """

        status, props, raw = self.request("GET", "/props")
        _require(status == 200, f"/props returned HTTP {status}: {raw}")
        caps = props.get("chat_template_caps")
        caps = (
            {str(key): bool(value) for key, value in sorted(caps.items())}
            if isinstance(caps, Mapping)
            else {}
        )
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

        quiet_reading = reading(quiet)
        loud_reading = reading(loud)
        flag_effective = (
            quiet_reading["content_chars"] > 0
            and quiet_reading["reasoning_chars"] == 0
            and not quiet_reading["think_tag_in_content"]
            and (
                loud_reading["reasoning_chars"] > 0
                or loud_reading["think_tag_in_content"]
                or loud_reading["completion_tokens"] > quiet_reading["completion_tokens"]
            )
        )
        return {
            "identity": {
                "build_info": str(props.get("build_info") or ""),
                "chat_template_sha256": _sha256_text(template),
                "chat_template_chars": len(template),
                "chat_template_has_enable_thinking": "enable_thinking" in template,
                "chat_template_caps": caps,
            },
            "probe": {"thinking_off": quiet_reading, "thinking_on": loud_reading},
            "flag_effective": flag_effective,
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
