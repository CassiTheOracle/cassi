"""Canonical field-owned agency and durable action journals.

The adaptive policy lives only in the supplied ``QiFieldState``.  The fixed
codec and journals below are deterministic transport/provenance machinery;
they never answer a recall or choose an action.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import math
import os
import re
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Generator, Mapping, Sequence

import torch

from cassi_qi_bootstrap import canonical_hash
from cassi_qi_field import QiFieldState


TRANSITION_RECEIPT_SCHEMA = "cassi.canonical-field-transition.v1"
ACTION_JOURNAL_SCHEMA = "cassi.action-journal.v1"
ACTION_EVENT_SCHEMA = "cassi.action-journal-event.v1"
AGENCY_CODEC_SCHEMA = "cassi.field-agency-codec.v1"
ZERO_SHA256 = "0" * 64
_SCOPE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}\Z")
_TOKEN_RE = re.compile(r"[a-z0-9]+")


class CanonicalRuntimeError(RuntimeError):
    """A canonical transition, receipt, or journal is invalid."""


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise CanonicalRuntimeError(f"value is not canonical JSON: {error}") from error


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _digest(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise CanonicalRuntimeError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _scope(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SCOPE_RE.fullmatch(value) is None:
        raise CanonicalRuntimeError(f"{label} must be a bounded canonical scope")
    return value


def _request_id(value: Any) -> str:
    return _scope(value, "request_id")


def _replace_durable(source: Path, destination: Path) -> None:
    if os.name == "nt":
        import ctypes

        replace_existing = 0x1
        write_through = 0x8
        if not ctypes.windll.kernel32.MoveFileExW(
            str(source),
            str(destination),
            replace_existing | write_through,
        ):
            raise ctypes.WinError()
        return
    os.replace(source, destination)
    descriptor = os.open(destination.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        _replace_durable(temporary, path)
    except Exception:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise


@contextlib.contextmanager
def _process_lock(path: Path) -> Generator[None, None, None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        if handle.seek(0, os.SEEK_END) == 0:
            handle.write(b"\0")
            handle.flush()
            os.fsync(handle.fileno())
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def state_sha256(state: QiFieldState) -> str:
    if not isinstance(state, QiFieldState) or not torch.is_tensor(state.field):
        raise CanonicalRuntimeError("state must be a QiFieldState")
    field = state.field.detach().cpu().contiguous()
    digest = hashlib.sha256(
        _canonical({"dtype": str(field.dtype), "shape": list(field.shape)})
    )
    digest.update(b"\x00")
    digest.update(field.numpy().tobytes(order="C"))
    return digest.hexdigest()


@dataclass(frozen=True)
class AgencyDecision:
    selected_action: str | None
    scores: Mapping[str, float]
    selection_strength: float
    margin: float
    abstained: bool
    feature_count: int
    addresses: Mapping[str, tuple[int, ...]]

    def payload(self) -> dict[str, Any]:
        return {
            "selected_action": self.selected_action,
            "scores": {key: float(self.scores[key]) for key in sorted(self.scores)},
            "selection_strength": float(self.selection_strength),
            "margin": float(self.margin),
            "abstained": self.abstained,
            "feature_count": self.feature_count,
            "addresses": {
                key: list(self.addresses[key]) for key in sorted(self.addresses)
            },
        }


class FieldAgencyController:
    """Fixed feature/action codec whose only learned values are field cells."""

    def __init__(
        self,
        baseline: QiFieldState,
        *,
        strength: float = 0.75,
        bound: float = 6.0,
        abstention_margin: float = 0.05,
        max_features: int = 48,
    ) -> None:
        if not isinstance(baseline, QiFieldState) or not torch.is_tensor(baseline.field):
            raise CanonicalRuntimeError("agency baseline must be a QiFieldState")
        if baseline.field.numel() < 256 or not bool(torch.isfinite(baseline.field).all()):
            raise CanonicalRuntimeError("agency field is too small or non-finite")
        if not 0.0 < strength <= bound or not 0.0 <= abstention_margin < bound:
            raise CanonicalRuntimeError("agency controller bounds are invalid")
        self._baseline = baseline.field.detach().clone().contiguous()
        self.strength = float(strength)
        self.bound = float(bound)
        self.abstention_margin = float(abstention_margin)
        self.max_features = int(max_features)
        self.fingerprint = canonical_hash(
            {
                "schema": AGENCY_CODEC_SCHEMA,
                "baseline_sha256": state_sha256(baseline),
                "strength": self.strength,
                "bound": self.bound,
                "abstention_margin": self.abstention_margin,
                "max_features": self.max_features,
                "feature_codec": "word-unigram-bigram",
                "address_codec": "sha256-mod-field-size",
                "selection_strength_codec": "support-times-separation-v1",
            },
            AGENCY_CODEC_SCHEMA,
        )

    def _validate(self, state: QiFieldState) -> None:
        if (
            not isinstance(state, QiFieldState)
            or not torch.is_tensor(state.field)
            or tuple(state.field.shape) != tuple(self._baseline.shape)
            or state.field.dtype != self._baseline.dtype
            or state.field.device != self._baseline.device
            or not bool(torch.isfinite(state.field).all())
        ):
            raise CanonicalRuntimeError("agency state does not match its fixed field slice")

    def features(self, text: str) -> tuple[str, ...]:
        if not isinstance(text, str) or not text.strip() or len(text.encode("utf-8")) > 16_384:
            raise CanonicalRuntimeError("agency text must be bounded nonempty UTF-8")
        words = _TOKEN_RE.findall(text.casefold())
        if not words:
            raise CanonicalRuntimeError("agency text has no encodable features")
        features = [f"w:{word}" for word in words]
        features.extend(f"b:{left}:{right}" for left, right in zip(words, words[1:]))
        # Duplicate words must not amplify a score merely by repetition.
        return tuple(dict.fromkeys(features))[: self.max_features]

    @staticmethod
    def _action(value: Any) -> str:
        return _scope(value, "action")

    def addresses(
        self,
        *,
        identity_scope: str,
        text: str,
        action: str,
    ) -> tuple[int, ...]:
        identity = _scope(identity_scope, "identity_scope")
        action = self._action(action)
        size = self._baseline.numel()
        return tuple(
            int.from_bytes(
                hashlib.sha256(
                    f"{AGENCY_CODEC_SCHEMA}\x00{identity}\x00{feature}\x00{action}".encode(
                        "utf-8"
                    )
                ).digest()[:8],
                "big",
            )
            % size
            for feature in self.features(text)
        )

    def teach(
        self,
        state: QiFieldState,
        *,
        identity_scope: str,
        text: str,
        action: str,
        polarity: float = 1.0,
    ) -> tuple[QiFieldState, dict[str, Any]]:
        self._validate(state)
        if not math.isfinite(float(polarity)) or float(polarity) not in {-1.0, 1.0}:
            raise CanonicalRuntimeError("polarity must be exactly -1 or 1")
        addresses = self.addresses(
            identity_scope=identity_scope,
            text=text,
            action=action,
        )
        field = state.field.clone()
        flat = field.reshape(-1)
        baseline = self._baseline.reshape(-1)
        delta = self.strength * float(polarity)
        for address in addresses:
            flat[address] = torch.clamp(
                flat[address] + delta,
                min=baseline[address] - self.bound,
                max=baseline[address] + self.bound,
            )
        learned = QiFieldState(field=field)
        return learned, {
            "codec_fingerprint": self.fingerprint,
            "action": self._action(action),
            "polarity": int(polarity),
            "feature_count": len(addresses),
            "unique_address_count": len(set(addresses)),
            "collision_count": len(addresses) - len(set(addresses)),
            "addresses": list(addresses),
            "field_state_in_sha256": state_sha256(state),
            "field_state_out_sha256": state_sha256(learned),
        }

    def decide(
        self,
        state: QiFieldState,
        *,
        identity_scope: str,
        text: str,
        candidates: Sequence[str],
    ) -> AgencyDecision:
        self._validate(state)
        if (
            not isinstance(candidates, Sequence)
            or isinstance(candidates, (str, bytes, bytearray))
            or not 2 <= len(candidates) <= 32
        ):
            raise CanonicalRuntimeError("candidates must contain 2..32 actions")
        actions = tuple(self._action(value) for value in candidates)
        if len(set(actions)) != len(actions):
            raise CanonicalRuntimeError("candidate actions must be unique")
        flat = state.field.reshape(-1)
        baseline = self._baseline.reshape(-1)
        scores: dict[str, float] = {}
        address_map: dict[str, tuple[int, ...]] = {}
        for action in actions:
            addresses = self.addresses(
                identity_scope=identity_scope,
                text=text,
                action=action,
            )
            address_map[action] = addresses
            values = torch.stack([flat[index] - baseline[index] for index in addresses])
            scores[action] = float(values.mean().item())
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        best_action, best_score = ranked[0]
        second_score = ranked[1][1]
        margin = best_score - second_score
        selection_strength = min(1.0, max(0.0, best_score) / self.strength) * min(
            1.0,
            max(0.0, margin) / self.strength,
        )
        abstained = best_score <= 0.0 or margin < self.abstention_margin
        return AgencyDecision(
            selected_action=None if abstained else best_action,
            scores=scores,
            selection_strength=selection_strength,
            margin=margin,
            abstained=abstained,
            feature_count=len(self.features(text)),
            addresses=address_map,
        )

    def lesion(
        self,
        state: QiFieldState,
        addresses: Sequence[int],
    ) -> QiFieldState:
        self._validate(state)
        field = state.field.clone()
        flat = field.reshape(-1)
        baseline = self._baseline.reshape(-1)
        for raw in addresses:
            if isinstance(raw, bool) or not isinstance(raw, int) or not 0 <= raw < flat.numel():
                raise CanonicalRuntimeError("lesion address is outside the field")
            flat[raw] = baseline[raw]
        return QiFieldState(field=field)


class TransitionReceiptStore:
    """Content-addressed immutable receipts; never consulted for decisions."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, receipt: Mapping[str, Any]) -> tuple[str, Path]:
        body = dict(receipt)
        if body.get("schema") != TRANSITION_RECEIPT_SCHEMA:
            raise CanonicalRuntimeError("transition receipt schema mismatch")
        digest = _sha(body)
        path = self.root / f"{digest}.json"
        payload = _canonical({"receipt": body, "receipt_sha256": digest}) + b"\n"
        if path.is_file():
            if path.read_bytes() != payload:
                raise CanonicalRuntimeError("receipt digest collision")
        else:
            _atomic_write(path, payload)
        return digest, path

    def get(self, digest: str) -> dict[str, Any]:
        digest = _digest(digest, "receipt_sha256")
        path = self.root / f"{digest}.json"
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise CanonicalRuntimeError(f"could not read transition receipt: {error}") from error
        if (
            not isinstance(envelope, dict)
            or set(envelope) != {"receipt", "receipt_sha256"}
            or envelope["receipt_sha256"] != digest
            or _sha(envelope["receipt"]) != digest
        ):
            raise CanonicalRuntimeError("transition receipt identity mismatch")
        return dict(envelope["receipt"])


class CanonicalActionJournal:
    """Atomic hash-chained lifecycle records keyed by scoped request identity."""

    STAGES = (
        "proposed",
        "authorized",
        "dispatch_intent",
        "outcome_pending",
        "consolidating",
        "observed",
        "unresolved",
    )

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._locks_guard = threading.Lock()
        self._locks: dict[str, threading.RLock] = {}

    @contextlib.contextmanager
    def _locked(self, action_instance_id: str) -> Generator[None, None, None]:
        action_instance_id = _scope(action_instance_id, "action_instance_id")
        with self._locks_guard:
            lock = self._locks.setdefault(action_instance_id, threading.RLock())
        with lock, _process_lock(self.root / f".{action_instance_id}.lock"):
            yield

    @contextlib.contextmanager
    def identity_transition(self, identity_scope: str) -> Generator[None, None, None]:
        """Serialize complete action lifecycles, including checkpoint writes."""
        key = "identity." + canonical_hash(
            _scope(identity_scope, "identity_scope"),
            "cassi.action-identity-lock.v1",
        )[:48]
        with self._locked(key):
            yield

    @staticmethod
    def action_instance_id(
        *, identity_scope: str, task_scope: str, request_id: str
    ) -> str:
        payload = {
            "identity_scope": _scope(identity_scope, "identity_scope"),
            "task_scope": _scope(task_scope, "task_scope"),
            "request_id": _request_id(request_id),
        }
        return "act." + canonical_hash(payload, "cassi.action-instance.v1")[:48]

    def path_for(self, action_instance_id: str) -> Path:
        return self.root / f"{_scope(action_instance_id, 'action_instance_id')}.json"

    @staticmethod
    def _event(stage: str, payload: Mapping[str, Any], prior: str, index: int) -> dict[str, Any]:
        if stage not in CanonicalActionJournal.STAGES:
            raise CanonicalRuntimeError("unknown action lifecycle stage")
        body = {
            "schema": ACTION_EVENT_SCHEMA,
            "index": index,
            "stage": stage,
            "prior_event_sha256": prior,
            "payload": dict(payload),
        }
        return {**body, "event_sha256": _sha(body)}

    @staticmethod
    def _validate(record: Any) -> dict[str, Any]:
        if not isinstance(record, dict) or set(record) != {
            "schema",
            "action_instance_id",
            "identity_scope",
            "task_scope",
            "request_id",
            "proposal_sha256",
            "events",
        }:
            raise CanonicalRuntimeError("action journal record fields mismatch")
        if record["schema"] != ACTION_JOURNAL_SCHEMA:
            raise CanonicalRuntimeError("action journal schema mismatch")
        _scope(record["action_instance_id"], "action_instance_id")
        _scope(record["identity_scope"], "identity_scope")
        _scope(record["task_scope"], "task_scope")
        _request_id(record["request_id"])
        _digest(record["proposal_sha256"], "proposal_sha256")
        events = record["events"]
        if not isinstance(events, list) or not events:
            raise CanonicalRuntimeError("action journal has no events")
        prior = ZERO_SHA256
        for index, event in enumerate(events):
            if not isinstance(event, dict) or set(event) != {
                "schema",
                "index",
                "stage",
                "prior_event_sha256",
                "payload",
                "event_sha256",
            }:
                raise CanonicalRuntimeError("action journal event fields mismatch")
            digest = event["event_sha256"]
            body = {key: value for key, value in event.items() if key != "event_sha256"}
            if (
                event["schema"] != ACTION_EVENT_SCHEMA
                or event["index"] != index
                or event["stage"] not in CanonicalActionJournal.STAGES
                or event["prior_event_sha256"] != prior
                or not isinstance(event["payload"], dict)
                or digest != _sha(body)
            ):
                raise CanonicalRuntimeError("action journal event chain mismatch")
            prior = digest
        return record

    def _load_unlocked(self, action_instance_id: str) -> dict[str, Any] | None:
        path = self.path_for(action_instance_id)
        if not path.is_file():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise CanonicalRuntimeError(f"could not read action journal: {error}") from error
        return self._validate(value)

    def load(self, action_instance_id: str) -> dict[str, Any] | None:
        with self._locked(action_instance_id):
            return self._load_unlocked(action_instance_id)

    def propose(
        self,
        *,
        identity_scope: str,
        task_scope: str,
        request_id: str,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        action_id = self.action_instance_id(
            identity_scope=identity_scope,
            task_scope=task_scope,
            request_id=request_id,
        )
        proposal_sha256 = _sha(payload)
        with self._locked(action_id):
            existing = self._load_unlocked(action_id)
            if existing is not None:
                if existing["proposal_sha256"] != proposal_sha256:
                    raise CanonicalRuntimeError(
                        "request identity reused with a different proposal"
                    )
                return existing
            record = {
                "schema": ACTION_JOURNAL_SCHEMA,
                "action_instance_id": action_id,
                "identity_scope": _scope(identity_scope, "identity_scope"),
                "task_scope": _scope(task_scope, "task_scope"),
                "request_id": _request_id(request_id),
                "proposal_sha256": proposal_sha256,
                "events": [self._event("proposed", payload, ZERO_SHA256, 0)],
            }
            _atomic_write(self.path_for(action_id), _canonical(record) + b"\n")
            return record

    def append(
        self,
        action_instance_id: str,
        *,
        expected: Sequence[str],
        stage: str,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        with self._locked(action_instance_id):
            record = self._load_unlocked(action_instance_id)
            if record is None:
                raise CanonicalRuntimeError("action proposal is missing")
            current = record["events"][-1]["stage"]
            if current == stage:
                if record["events"][-1]["payload"] != dict(payload):
                    raise CanonicalRuntimeError("action stage replay payload conflicts")
                return record
            if current not in set(expected):
                raise CanonicalRuntimeError(
                    f"action transition {current!r} -> {stage!r} is invalid"
                )
            events = list(record["events"])
            events.append(
                self._event(
                    stage,
                    payload,
                    events[-1]["event_sha256"],
                    len(events),
                )
            )
            updated = {**record, "events": events}
            _atomic_write(
                self.path_for(action_instance_id),
                _canonical(updated) + b"\n",
            )
            return updated

    def records(self) -> tuple[dict[str, Any], ...]:
        result = []
        for path in sorted(self.root.glob("act.*.json")):
            loaded = self.load(path.stem)
            if loaded is not None:
                result.append(loaded)
        return tuple(result)


def receipt_payload(
    *,
    operation: str,
    identity_scope: str,
    task_scope: str,
    request_id: str,
    state_in_sha256: str,
    state_out_sha256: str,
    component_in_sha256: str,
    component_out_sha256: str,
    component: str,
    request_payload: Mapping[str, Any],
    result: Mapping[str, Any],
    checkpoint_sha256: str | None,
) -> dict[str, Any]:
    return {
        "schema": TRANSITION_RECEIPT_SCHEMA,
        "operation": _scope(operation, "operation"),
        "identity_scope": _scope(identity_scope, "identity_scope"),
        "task_scope": _scope(task_scope, "task_scope"),
        "request_id": _request_id(request_id),
        "request_sha256": _sha(request_payload),
        "state_in_sha256": _digest(state_in_sha256, "state_in_sha256"),
        "state_out_sha256": _digest(state_out_sha256, "state_out_sha256"),
        "component": _scope(component, "component"),
        "component_state_in_sha256": _digest(
            component_in_sha256, "component_state_in_sha256"
        ),
        "component_state_out_sha256": _digest(
            component_out_sha256, "component_state_out_sha256"
        ),
        "causal_parent_sha256": _digest(state_in_sha256, "state_in_sha256"),
        "checkpoint_sha256": (
            None
            if checkpoint_sha256 is None
            else _digest(checkpoint_sha256, "checkpoint_sha256")
        ),
        "provider_is_adaptive_owner": True,
        "adaptive_sidecars": [],
        "external_model_calls": 0,
        "result": dict(result),
    }
