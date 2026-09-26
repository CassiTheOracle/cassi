#!/usr/bin/env python3
"""Gate autonomous CassiMindField promotions on the live responsibility owner."""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import unquote

_MODULE_ROOT = Path(__file__).resolve().parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

from redesign_lab import (  # noqa: E402
    MutationRejected,
    _FieldOwnerClient,
    _assert_responsibility_evidence_successor,
    _atomic_json,
    _field_owner_client,
    _load_responsibility_snapshot,
    _owner_program_row,
    _read,
    _read_owner_link,
    _rewrite_outcome_reports,
    _responsibility_last_observed,
    _responsibility_snapshot_digest,
    _save_owner_link,
    _summarize_responsibility_snapshot,
    _utc_now,
    _validate_responsibility_summary,
    digest,
)

_CONTINUITY_FILE = "field-owner-continuity.json"
_CONTINUITY_SCHEMA = "cassimindfield.field-owner-continuity.v1"
_REVIEW_SCHEMA = "cassimindfield.field-owner-review.v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MAX_GENERATION = 2**31 - 1


def _generation(value: Any, label: str) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
        or value > _MAX_GENERATION
    ):
        raise MutationRejected(f"{label} is not a valid generation")
    return value


def _identifier(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > 256
        or not value.isprintable()
    ):
        raise MutationRejected(f"{label} is not a bounded identifier")
    return value


class PendingRewriteReview(MutationRejected):
    """The owner has an open assessment that must be addressed before selection."""

class LocalFieldOwnerClient(_FieldOwnerClient):
    """Use the same owner API inside an entity research cycle without HTTP re-entry."""

    def __init__(self, entity: Any) -> None:
        self.entity = entity

    def _request(
        self, method: str, route: str, body: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        if method == "GET" and route == "/v1/responsibilities/snapshot" and body is None:
            result = self.entity.research_responsibility_snapshot()
        elif method == "POST" and route == "/v1/programs" and isinstance(body, Mapping):
            result = self.entity.create_research_program(**body)
        elif (
            method == "POST"
            and re.fullmatch(r"/v1/programs/[^/]+/consequences", route)
            and isinstance(body, Mapping)
        ):
            program_id = unquote(route.split("/")[3])
            result = self.entity.record_research_consequence(program_id=program_id, **body)
        else:
            raise MutationRejected("unsupported local field-owner operation")
        if not isinstance(result, Mapping):
            raise MutationRejected("local field owner returned a non-object response")
        return dict(result)



class RewriteOwnerGate:
    """Require a fresh, monotonic field-owner review around every promotion."""

    def __init__(
        self,
        root: Path,
        *,
        field_owner_url: str,
        owner_client: _FieldOwnerClient | None = None,
    ) -> None:
        self.root = Path(root).resolve()
        self._link_path = self.root / "field-owner-link.json"
        self._continuity_path = self.root / _CONTINUITY_FILE
        self._client = owner_client if owner_client is not None else _field_owner_client(field_owner_url)
        self._link, _ = self._client.bind_campaign(self.root)
        campaign_id = digest({"data_home": str(self.root.resolve())})[:24]
        self._link = _read_owner_link(self._link_path, campaign_id)
        self._last_observed = self._load_baseline()

        self._recover_inflight()
        self._client.flush_reports(self.root, self._link)
        self._fresh_snapshot(require_no_outstanding=False)

    def _current_pointer(self) -> dict[str, Any] | None:
        path = self.root / "current.json"
        if not path.is_file():
            return None
        pointer = _read(path)
        generation = _generation(pointer.get("generation"), "current pointer generation")
        if not isinstance(pointer.get("schema"), str):
            raise MutationRejected("current pointer schema is invalid")
        if generation > 0:
            manifest_sha256 = pointer.get("manifest_sha256")
            if not isinstance(manifest_sha256, str) or not _SHA256.fullmatch(manifest_sha256):
                raise MutationRejected("current pointer manifest digest is invalid")
        return pointer

    def _verify_target_files(self, target: int, manifest: Mapping[str, Any]) -> None:
        workspace_root = self.root.resolve()
        generation_root = (workspace_root / "generations" / f"g{target:04d}").resolve()
        try:
            generation_root.relative_to(workspace_root)
        except ValueError as exc:
            raise MutationRejected("promoted generation directory escapes the workspace") from exc
        verified = 0

        def verify(relative: Any, expected_sha256: Any, expected_bytes: Any = None) -> None:
            nonlocal verified
            if (
                not isinstance(relative, str)
                or not relative
                or len(relative) > 512
                or not isinstance(expected_sha256, str)
                or not _SHA256.fullmatch(expected_sha256)
            ):
                raise MutationRejected("promoted manifest contains an invalid source-file digest")
            relative_path = Path(relative)
            if relative_path.is_absolute() or ".." in relative_path.parts:
                raise MutationRejected("promoted manifest contains an unsafe source path")
            path = (generation_root / relative_path).resolve()
            try:
                path.relative_to(generation_root)
            except ValueError as exc:
                raise MutationRejected("promoted source file escapes its generation") from exc
            if not path.is_file():
                raise MutationRejected("promoted source file is missing")
            size = path.stat().st_size
            if expected_bytes is not None and (
                isinstance(expected_bytes, bool)
                or not isinstance(expected_bytes, int)
                or expected_bytes < 0
                or size != expected_bytes
            ):
                raise MutationRejected("promoted source file size does not match its manifest")
            hasher = hashlib.sha256()
            with path.open("rb") as source:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    hasher.update(block)
            if hasher.hexdigest() != expected_sha256:
                raise MutationRejected("promoted source file does not match its manifest digest")
            verified += 1

        source_relative = manifest.get("source_relative")
        source_sha256 = manifest.get("source_sha256")
        if source_relative is not None or source_sha256 is not None:
            verify(source_relative, source_sha256, manifest.get("source_bytes"))
        files = manifest.get("files")
        if files is not None:
            if not isinstance(files, Mapping) or not files or len(files) > 4096:
                raise MutationRejected("promoted manifest file index is invalid")
            for relative, row in files.items():
                if not isinstance(row, Mapping):
                    raise MutationRejected("promoted manifest file entry is invalid")
                verify(relative, row.get("sha256"), row.get("bytes"))
        if not verified:
            raise MutationRejected("promoted manifest contains no verifiable source-file hashes")

    def _read_target_manifest(
        self, pointer: Mapping[str, Any], target_generation: int
    ) -> tuple[dict[str, Any], str, str]:
        target = _generation(target_generation, "target generation")
        current = _generation(pointer.get("generation"), "current pointer generation")
        manifest_sha256 = pointer.get("manifest_sha256")
        if current != target:
            raise MutationRejected("current pointer does not select the promotion target")
        if not isinstance(manifest_sha256, str) or not _SHA256.fullmatch(manifest_sha256):
            raise MutationRejected("current pointer does not bind a valid manifest digest")
        manifest_path = self.root / "generations" / f"g{target:04d}" / "manifest.json"
        manifest = _read(manifest_path)
        if digest(manifest) != manifest_sha256:
            raise MutationRejected("target manifest does not match the current pointer digest")
        if _generation(manifest.get("generation"), "target manifest generation") != target:
            raise MutationRejected("target manifest generation does not match the current pointer")
        candidate_id = _identifier(manifest.get("candidate_id"), "manifest candidate_id")
        evidence = manifest.get("responsibility_continuity")
        if not isinstance(evidence, Mapping):
            raise MutationRejected("promoted manifest lacks field-owner continuity evidence")
        last_observed = _responsibility_last_observed(manifest)
        if not isinstance(last_observed, Mapping):
            raise MutationRejected("promoted manifest lacks its field-owner snapshot summary")
        self._verify_target_files(target, manifest)
        return manifest, manifest_sha256, candidate_id

    def _load_baseline(self) -> dict[str, Any] | None:
        if self._continuity_path.is_file():
            sidecar = _read(self._continuity_path)
            if set(sidecar) != {"schema", "last_observed", "last_observed_sha256"}:
                raise MutationRejected("field-owner continuity sidecar schema is invalid")
            summary = sidecar.get("last_observed")
            if (
                sidecar.get("schema") != _CONTINUITY_SCHEMA
                or not isinstance(summary, Mapping)
                or sidecar.get("last_observed_sha256") != digest(summary)
            ):
                raise MutationRejected("field-owner continuity sidecar failed its hash guard")
            _validate_responsibility_summary(summary)
            return dict(summary)

        pointer = self._current_pointer()
        if pointer is None:
            return None
        generation = _generation(pointer.get("generation"), "current pointer generation")
        if generation == 0:
            return None
        manifest_path = self.root / "generations" / f"g{generation:04d}" / "manifest.json"
        manifest = _read(manifest_path)
        if digest(manifest) != pointer.get("manifest_sha256"):
            raise MutationRejected("current manifest does not match the current pointer digest")
        if _generation(manifest.get("generation"), "current manifest generation") != generation:
            raise MutationRejected("current manifest generation does not match the pointer")
        summary = _responsibility_last_observed(manifest)
        if summary is None:
            # Older, independently verified generations predate owner evidence.
            # Establish continuity from this fresh live snapshot without rewriting history.
            return None
        if not isinstance(summary, Mapping):
            raise MutationRejected("current manifest responsibility baseline is invalid")
        _validate_responsibility_summary(summary)
        return dict(summary)

    def _save_last_observed(self, summary: Mapping[str, Any]) -> None:
        _validate_responsibility_summary(summary)
        value = dict(summary)
        _atomic_json(
            self._continuity_path,
            {
                "schema": _CONTINUITY_SCHEMA,
                "last_observed": value,
                "last_observed_sha256": digest(value),
            },
        )
        self._last_observed = value

    def _program_assessments(self, snapshot: Mapping[str, Any]) -> list[Any]:
        row = _owner_program_row(snapshot, self._link["program_id"])
        payload = row["record"].get("payload")
        declaration = payload.get("responsibility") if isinstance(payload, Mapping) else None
        if not isinstance(declaration, Mapping):
            raise MutationRejected("field-owner program responsibility declaration is unavailable")
        assessments = declaration.get("outstanding_assessments")
        if not isinstance(assessments, list) or len(assessments) > 4096:
            raise MutationRejected("field-owner outstanding assessment index is invalid")
        return assessments

    def _fresh_snapshot(
        self, *, require_no_outstanding: bool
    ) -> tuple[
        dict[str, Any],
        dict[str, Any],
        dict[str, Any] | None,
        dict[str, Any] | None,
    ]:
        snapshot = self._client.responsibility_snapshot()
        snapshot = _load_responsibility_snapshot(snapshot) or {}
        self._client._assert_program_bound(snapshot, self._link)
        current = _summarize_responsibility_snapshot(snapshot)
        previous = self._last_observed
        comparison = (
            None
            if previous is None
            else _assert_responsibility_evidence_successor(previous, current)
        )
        self._save_last_observed(current)
        pending = self._program_assessments(snapshot)
        if require_no_outstanding and pending:
            raise PendingRewriteReview(
                f"field owner has {len(pending)} outstanding affected-group assessments"
            )
        return snapshot, current, comparison, previous

    @staticmethod
    def _attempt_generation(link: Mapping[str, Any]) -> int | None:
        attempt = link.get("inflight_attempt")
        if attempt is None:
            return None
        if not isinstance(attempt, Mapping) or set(attempt) != {"generation", "started_at"}:
            raise MutationRejected("field-owner link has a malformed in-flight attempt")
        generation = _generation(attempt.get("generation"), "in-flight target generation")
        started_at = attempt.get("started_at")
        if (
            generation < 1
            or not isinstance(started_at, str)
            or not started_at
            or len(started_at) > 64
        ):
            raise MutationRejected("field-owner link has an invalid in-flight attempt")
        return generation

    def _queue_reports(self, reports: list[dict[str, Any]]) -> None:
        attempt = self._link.get("inflight_attempt")
        if not isinstance(attempt, Mapping):
            raise MutationRejected("cannot queue owner reports without an in-flight attempt")
        observed_at = attempt.get("started_at")
        if not isinstance(observed_at, str) or not observed_at:
            raise MutationRejected("in-flight owner attempt has no stable report timestamp")
        existing: set[str] = set()
        for row in self._link["pending_reports"]:
            if not isinstance(row, Mapping):
                raise MutationRejected("field-owner pending report queue is malformed")
            request_id = row.get("request_id")
            if not isinstance(request_id, str):
                raise MutationRejected("field-owner pending report has no request id")
            existing.add(request_id)
        queued = []
        for row in reports:
            request_id = row.get("request_id")
            if not isinstance(request_id, str):
                raise MutationRejected("generated field-owner report has no request id")
            if request_id in existing:
                continue
            stable = dict(row)
            stable["observed_at"] = observed_at
            queued.append(stable)
            existing.add(request_id)
        self._link["pending_reports"].extend(queued)

    def _recover_inflight(self) -> None:
        target = self._attempt_generation(self._link)
        if target is None:
            return
        pointer = self._current_pointer()
        if pointer is None:
            raise MutationRejected("cannot recover an owner attempt without a current pointer")
        current = _generation(pointer.get("generation"), "current pointer generation")
        if current == target - 1:
            reports = _rewrite_outcome_reports(
                self._link,
                generation=target,
                receipt=None,
                interrupted=True,
            )
        elif current == target:
            manifest, manifest_sha256, candidate_id = self._read_target_manifest(pointer, target)
            manifest_summary = _responsibility_last_observed(manifest)
            if not isinstance(manifest_summary, Mapping) or self._last_observed is None:
                raise MutationRejected("committed owner attempt lacks a continuity baseline")
            _assert_responsibility_evidence_successor(manifest_summary, self._last_observed)
            reports = _rewrite_outcome_reports(
                self._link,
                generation=target,
                receipt={
                    "content_sha256": manifest_sha256,
                    "selected_candidate_id": candidate_id,
                },
            )
        else:
            raise MutationRejected(
                "in-flight owner attempt cannot be bound to the current promotion pointer"
            )
        self._queue_reports(reports)
        self._link["inflight_attempt"] = None
        _save_owner_link(self._link_path, self._link)

    def _continuity_evidence(
        self,
        snapshot: Mapping[str, Any],
        current: Mapping[str, Any],
        comparison: Mapping[str, Any] | None,
        baseline: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        return {
            "schema": current["schema"],
            "status": "baseline" if comparison is None else "monotonic",
            "reason": "first-read-only-field-snapshot" if comparison is None else "fresh-snapshot-monotonic",
            "scope": "read-only-entity-snapshot; not a live field-home mutation",
            "current_snapshot_sha256": _responsibility_snapshot_digest(snapshot),
            "baseline": None if baseline is None else dict(baseline),
            "last_observed": dict(current),
            "comparison": None if comparison is None else dict(comparison),
        }

    def start(self, generation: int) -> None:
        current_generation = _generation(generation, "selection generation")
        target = current_generation + 1
        if target > _MAX_GENERATION:
            raise MutationRejected("target generation exceeds the supported bound")
        pointer = self._current_pointer()
        if pointer is None or _generation(pointer.get("generation"), "current pointer generation") != current_generation:
            raise MutationRejected("selection generation does not match the current pointer")
        if self._attempt_generation(self._link) is not None:
            raise MutationRejected("a field-owner rewrite attempt is already in flight")
        self._fresh_snapshot(require_no_outstanding=True)
        self._link["inflight_attempt"] = {
            "generation": target,
            "started_at": _utc_now(),
        }
        _save_owner_link(self._link_path, self._link)

    def before_promotion(self, generation: int) -> dict[str, Any]:
        target = _generation(generation, "promotion generation")
        if self._attempt_generation(self._link) != target:
            raise MutationRejected("promotion target does not match the in-flight owner attempt")
        pointer = self._current_pointer()
        if pointer is None or _generation(pointer.get("generation"), "current pointer generation") != target - 1:
            raise MutationRejected("current pointer advanced before owner promotion review")
        snapshot, current, comparison, baseline = self._fresh_snapshot(
            require_no_outstanding=True
        )
        return self._continuity_evidence(snapshot, current, comparison, baseline)

    def abort(self, generation: int) -> None:
        current_generation = _generation(generation, "aborted selection generation")
        target = current_generation + 1
        attempt_target = self._attempt_generation(self._link)
        if attempt_target is None:
            return
        if attempt_target != target:
            raise MutationRejected("abort generation does not match the in-flight owner attempt")
        pointer = self._current_pointer()
        if pointer is None:
            raise MutationRejected("cannot safely abort without the current pointer")
        pointer_generation = _generation(pointer.get("generation"), "current pointer generation")
        if pointer_generation != current_generation:
            if pointer_generation >= target:
                return
            raise MutationRejected("current pointer changed before owner attempt abort")
        self._link["inflight_attempt"] = None
        _save_owner_link(self._link_path, self._link)

    def promoted(self, generation: int) -> dict[str, Any]:
        target = _generation(generation, "promoted generation")
        if self._attempt_generation(self._link) != target:
            raise MutationRejected("promoted generation does not match the in-flight owner attempt")
        pointer = self._current_pointer()
        if pointer is None:
            raise MutationRejected("promoted generation has no current pointer")
        manifest, manifest_sha256, candidate_id = self._read_target_manifest(pointer, target)
        manifest_summary = _responsibility_last_observed(manifest)
        if (
            not isinstance(manifest_summary, Mapping)
            or self._last_observed is None
            or digest(manifest_summary) != digest(self._last_observed)
        ):
            raise MutationRejected(
                "promotion manifest continuity does not match its pre-promotion owner check"
            )
        reports = _rewrite_outcome_reports(
            self._link,
            generation=target,
            receipt={
                "content_sha256": manifest_sha256,
                "selected_candidate_id": candidate_id,
            },
        )
        self._queue_reports(reports)
        _save_owner_link(self._link_path, self._link)
        self._client.flush_reports(self.root, self._link)
        snapshot, current, _comparison, _baseline = self._fresh_snapshot(
            require_no_outstanding=False
        )
        pending = self._program_assessments(snapshot)
        review = {
            "schema": _REVIEW_SCHEMA,
            "status": "reports_submitted",
            "program_id": _identifier(self._link.get("program_id"), "owner program id"),
            "generation": target,
            "candidate_id": candidate_id,
            "manifest_sha256": manifest_sha256,
            "report_count": len(reports),
            "outstanding_assessment_count": len(pending),
            "outstanding_assessments_sha256": digest(pending),
            "snapshot_sha256": _responsibility_snapshot_digest(snapshot),
            "records_sha256": current["records_sha256"],
        }
        self._link["inflight_attempt"] = None
        _save_owner_link(self._link_path, self._link)
        return review
