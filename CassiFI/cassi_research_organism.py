"""One continuing field-owned research organism.

The resident, frontier, campaign ledger, member fields, and publication pointer
are deliberately composed from the existing CassiFI owner path.  This module is
the orchestration boundary: it does not create a second adaptive model or use
caller-supplied scores as evidence.  Every candidate is executed against a
world adapter, its raw trace is archived, and all adaptive summaries are
registered back into the corresponding regional field.
"""
import ast
import contextlib
import hashlib
import json
from dataclasses import asdict, dataclass
import math
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from cassi_field_atlas import (
    FieldIntelligenceError,
    FieldProgram,
    PrimitiveStep,
    canonical_json_bytes,
    sha256_value,
)
from cassi_field_affect import affect_context
from cassi_field_cognition import (
    PACKET_REASONING_EPISODE_SCHEMA,
    PACKET_RESOURCE_NAMES,
    semantic_cognition_state,
)
from cassi_field_owner import FieldIntelligenceOwner
from cassi_field_hive import ExperienceCandidate, ExperienceEvidence, Review
from cassi_field_input import CODEC_JSON
from cassi_field_owner import SourceInput
from cassi_field_program import (
    SCHEMA as STRUCTURED_FIELD_PROGRAM_SCHEMA,
    FieldProgramError,
    compile_structured_program,
    regional_scalar_state,
    semantic_program_payload,
)
from cassi_hive_collective import (
    AFFECT_REPORT_SCHEMA,
    AffectReport,
    COLLABORATION_ASSIGNMENT_SCHEMA,
    COLLABORATION_REQUEST_SCHEMA,
    COLLABORATION_RESPONSE_SCHEMA,
    COLLECTIVE_SYNTHESIS_SCHEMA,
    REPRESENTATION_TRANSLATION_SCHEMA,
    CollaborationAssignment,
    CollaborationRequest,
    CollaborationResponse,
    CollectiveSynthesis,
    CollectiveHiveError,
    ExecutableMethod,
    HiveOffer,
    HiveQuery,
    MethodCompositionSpec,
    MethodConnection,
    MethodInterface,
    MethodOutputBinding,
    MethodPort,
    RepresentationTranslation,
    compile_collaborative_method,
)
from cassi_hive_coordinator import HiveCoordinator
from cassi_research_residency import (
    DEFAULT_PROFILE,
    ResearchResidency,
    ResidencyError,
    attach_research_residency,
    open_research_residency,
)

SCHEMA = "cassifi.research-organism.v1"
MANIFEST_SCHEMA = "cassifi.research-organism-manifest.v1"
FRONTIER_SCHEMA = "cassifi.research-organism-frontier.v1"
CAMPAIGN_SCHEMA = "cassifi.research-organism-campaign.v1"
BUNDLE_SCHEMA = "cassifi.research-organism-bundle.v1"
EFFECT_SCHEMA = "cassifi.research-organism-effect.v1"
PUBLICATION_SCHEMA = "cassifi.research-organism-publication.v1"
POINTER_SCHEMA = "cassifi.research-organism-pointer.v1"
EXPERIENCE_SCHEMA = "cassifi.research-organism-experience.v1"
EXPERIENCE_RECEIPT_SCHEMA = "cassifi.research-organism-experience-receipt.v1"
ORGANISM_ID = "organism:identity"
FRONTIER_ID = "organism:frontier"
COHORT_SCHEMA = "cassifi.research-organism-cohort.v1"
COHORT_MIGRATION_SCHEMA = "cassifi.research-organism-cohort-migration.v1"
RESOURCE_ALLOCATION_SCHEMA = "cassifi.research-organism-resource-allocation.v1"
COLLABORATION_VIEW_SCHEMA = "cassifi.research-organism-collaboration-view.v1"
COLLABORATIVE_CAPABILITY_GAP_SCHEMA = (
    "cassifi.research-organism-collaborative-capability-gap.v1"
)
COLLABORATIVE_MEMBER_CAPABILITY_SCHEMA = (
    "cassifi.research-organism-member-capability.v1"
)
COLLABORATIVE_CAPABILITY_DISPATCH_SCHEMA = (
    "cassifi.research-organism-capability-dispatch.v1"
)
COLLABORATIVE_MEMBER_CAPABILITY_METHOD_SCHEMA = (
    "cassifi.research-organism-member-capability-method.v1"
)
COLLABORATIVE_MEMBER_CAPABILITY_OBLIGATION_SCHEMA = (
    "cassifi.research-organism-member-capability-obligation.v1"
)
COLLABORATIVE_CAPABILITY_AGENDA_RESPONSE_SCHEMA = (
    "cassifi.research-organism-capability-agenda-response.v1"
)
COLLECTIVE_INVESTIGATION_SCHEMA = (
    "cassifi.research-organism-collective-investigation.v1"
)
COLLABORATIVE_METHOD_EXECUTION_SCHEMA = (
    "cassifi.research-organism-collaborative-method-execution.v1"
)
COLLECTIVE_METHOD_CONTINUATION_SCHEMA = (
    "cassifi.organism.collective-method-continuation.v1"
)
COLLECTIVE_METHOD_RESULT_SCHEMA = "cassifi.organism.collective-method-result.v1"
COLLECTIVE_NEXT_ACTION_SCHEMA = (
    "cassifi.research-organism-collective-next-action.v1"
)
COLLECTIVE_METHOD_ADAPTER = "cassi.collective-method"
ROOT_RESEARCH_METHOD_SCHEMA = (
    "cassifi.research-organism-root-research-method.v1"
)
ROOT_RESEARCH_METHOD_EXECUTION_SCHEMA = (
    "cassifi.research-organism-root-research-method-execution.v1"
)
ROOT_RESEARCH_METHOD_PROPOSAL_SCHEMA = (
    "cassi.entity.root-research-method-proposal.v1"
)
ROOT_GUEST_METHOD_SCHEMA = "cassifi.research-organism-root-guest-method.v1"
ROOT_GUEST_METHOD_PROPOSAL_SCHEMA = "cassi.entity.root-guest-method-proposal.v1"
ROOT_GUEST_EXECUTION_SCHEMA = "cassifi.research-organism-root-guest-execution.v1"
ROOT_GUEST_DERIVATION_SCHEMA = "cassifi.research-organism-root-guest-derivation.v1"
METHODS_ID = "organism:methods"
MEMBERS_ID = "organism:members"
CAMPAIGN_PREFIX = "organism:campaign:"
PROGRAM_PREFIX = "organism:program:"
AFFECT_PROJECT_ID = "research-organism"


_MAX_MEMBERS = 16
NUMERICAL_INSTRUMENT_STRUCTURED_STATE_SCHEMA = (
    "cassifi.numerical-instrument-structured-state.v1"
)
_MAX_FRONTIER = 128
_MAX_TRACE = 256
_MAX_RESULT_BYTES = 1_048_576
_COLLECTIVE_RESULT_WORD_BOUND = (_MAX_RESULT_BYTES + 3) // 4 + 2_048
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


class OrganismError(RuntimeError):
    """Raised when the continuing organism cannot make a safe transition."""


def _plain(value: Any) -> Any:
    return json.loads(canonical_json_bytes(value).decode("utf-8"))


def _digest(value: Any) -> str:
    return sha256_value(value)
def _foreign_source_view(value: Any) -> Any:
    """Preserve foreign provenance labels without asserting local ownership."""
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, nested in value.items():
            if key == "source_revision_id":
                result["origin_source_revision_id"] = _plain(nested)
            elif key == "source_revision_ids":
                result["origin_source_revision_ids"] = _plain(nested)
            else:
                result[str(key)] = _foreign_source_view(nested)
        return result
    if isinstance(value, list):
        return [_foreign_source_view(item) for item in value]
    if isinstance(value, tuple):
        return [_foreign_source_view(item) for item in value]
    return _plain(value)




def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise OrganismError(f"{label} must be a bounded identifier")
    return value


def _text(value: Any, label: str, *, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OrganismError(f"{label} must be nonempty text")
    if len(value.encode("utf-8")) > maximum:
        raise OrganismError(f"{label} exceeds its byte bound")
    return value


def _atomic_bytes(path: Path, content: bytes, *, immutable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = path.read_bytes()
        if immutable and existing != content:
            raise OrganismError(f"immutable organism artifact changed: {path}")
        if existing == content:
            return
    temporary = path.with_name(f".{path.name}.{os.getpid()}.pending")
    try:
        with temporary.open("wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _atomic_json(path: Path, value: Mapping[str, Any], *, immutable: bool = False) -> None:
    _atomic_bytes(path, canonical_json_bytes(value) + b"\n", immutable=immutable)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OrganismError(f"organism artifact is unreadable: {path}") from exc
    if not isinstance(value, dict):
        raise OrganismError(f"organism artifact is not an object: {path}")
    return value


@dataclass(frozen=True, slots=True)
class Construction:
    """A typed, executable construction candidate in the resident frontier."""

    candidate_id: str
    parent_ids: tuple[str, ...]
    operations: tuple[Mapping[str, Any], ...]
    program: Mapping[str, Any]
    applicability: Mapping[str, Any]
    status: str = "proposed"
    evidence: Mapping[str, Any] | None = None
    problem_roots: tuple[str, ...] = ()
    holes: tuple[Mapping[str, Any], ...] = ()
    assumptions: Mapping[str, Any] | None = None
    effects: Mapping[str, Any] | None = None
    search_program_version: str = "bootstrap:v1"
    consumed_work: int = 0
    counterexamples: tuple[Mapping[str, Any], ...] = ()
    novelty: tuple[str, ...] = ()
    def __post_init__(self) -> None:
        _identifier(self.candidate_id, "candidate_id")
        if len(self.parent_ids) > 8 or any(
            not isinstance(item, str) or not _IDENTIFIER.fullmatch(item)
            for item in self.parent_ids
        ):
            raise OrganismError("construction parent identities are invalid")
        if not self.operations or len(self.operations) > 32:
            raise OrganismError("construction requires 1..32 typed operations")
        for operation in self.operations:
            if not isinstance(operation, Mapping) or not isinstance(
                operation.get("op"), str
            ):
                raise OrganismError("construction operations must be typed objects")
        if not isinstance(self.program, Mapping):
            raise OrganismError("construction program must be an object")
        _text(self.status, "construction status", maximum=64)
        if any(not isinstance(root, str) or not root for root in self.problem_roots):
            raise OrganismError("construction problem roots are invalid")
        if any(not isinstance(hole, Mapping) for hole in self.holes):
            raise OrganismError("construction holes must be typed objects")
        _identifier(self.search_program_version, "search_program_version")
        if (
            isinstance(self.consumed_work, bool)
            or not isinstance(self.consumed_work, int)
            or self.consumed_work < 0
        ):
            raise OrganismError("construction consumed work must be nonnegative")
        if any(not isinstance(item, Mapping) for item in self.counterexamples):
            raise OrganismError("construction counterexamples must be objects")
        if any(not isinstance(item, str) or not item for item in self.novelty):
            raise OrganismError("construction novelty axes are invalid")

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "parent_ids": list(self.parent_ids),
            "operations": [_plain(item) for item in self.operations],
            "program": _plain(self.program),
            "applicability": _plain(self.applicability),
            "status": self.status,
            "evidence": None if self.evidence is None else _plain(self.evidence),
            "problem_roots": list(self.problem_roots),
            "holes": [_plain(item) for item in self.holes],
            "assumptions": {} if self.assumptions is None else _plain(self.assumptions),
            "effects": {} if self.effects is None else _plain(self.effects),
            "search_program_version": self.search_program_version,
            "consumed_work": self.consumed_work,
            "counterexamples": [_plain(item) for item in self.counterexamples],
            "novelty": list(self.novelty),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Construction":
        if not isinstance(value, Mapping):
            raise OrganismError("frontier construction must be an object")
        operations = value.get("operations")
        if not isinstance(operations, list):
            raise OrganismError("frontier construction operations must be a list")
        parents = value.get("parent_ids", [])
        roots = value.get("problem_roots", [])
        holes = value.get("holes", [])
        counterexamples = value.get("counterexamples", [])
        novelty = value.get("novelty", [])
        if not all(
            isinstance(items, list)
            for items in (parents, roots, holes, counterexamples, novelty)
        ):
            raise OrganismError("frontier construction sequence fields are invalid")
        return cls(
            candidate_id=_identifier(value.get("candidate_id"), "candidate_id"),
            parent_ids=tuple(str(item) for item in parents),
            operations=tuple(_plain(item) for item in operations),
            program=_plain(value.get("program", {})),
            applicability=_plain(value.get("applicability", {})),
            status=str(value.get("status", "proposed")),
            evidence=(
                None
                if value.get("evidence") is None
                else _plain(value["evidence"])
            ),
            problem_roots=tuple(str(item) for item in roots),
            holes=tuple(_plain(item) for item in holes),
            assumptions=_plain(value.get("assumptions", {})),
            effects=_plain(value.get("effects", {})),
            search_program_version=str(
                value.get("search_program_version", "bootstrap:v1")
            ),
            consumed_work=int(value.get("consumed_work", 0)),
            counterexamples=tuple(_plain(item) for item in counterexamples),
            novelty=tuple(str(item) for item in novelty),
        )


class EffectJournal:
    """Content-addressed external-effect acknowledgments that survive rollback."""

    def __init__(self, home: Path) -> None:
        self.home = Path(home)
        self.home.mkdir(parents=True, exist_ok=True)

    def _path(self, effect_id: str) -> Path:
        return self.home / hashlib.sha256(effect_id.encode("utf-8")).hexdigest()

    def get(self, effect_id: str) -> dict[str, Any] | None:
        path = self._path(_identifier(effect_id, "effect_id"))
        if not path.exists():
            return None
        value = _read_json(path)
        declared = value.pop("effect_sha256", None)
        if declared != _digest(value):
            raise OrganismError(f"external effect journal digest mismatch: {path}")
        value["effect_sha256"] = declared
        return value

    def record(
        self,
        effect_id: str,
        *,
        actor: str,
        request: Mapping[str, Any],
        result: Mapping[str, Any],
    ) -> dict[str, Any]:
        effect_id = _identifier(effect_id, "effect_id")
        actor = _identifier(actor, "effect actor")
        body: dict[str, Any] = {
            "schema": EFFECT_SCHEMA,
            "effect_id": effect_id,
            "actor": actor,
            "request": _plain(request),
            "result": _plain(result),
        }
        body["effect_sha256"] = _digest(body)
        path = self._path(effect_id)
        if path.exists():
            current = self.get(effect_id)
            if current != body:
                raise OrganismError("effect identity was reused with different bytes")
            return current
        _atomic_json(path, body, immutable=True)
        return body

    def count(self) -> int:
        return sum(1 for path in self.home.iterdir() if path.is_file())


class PublicationLedger:
    """Immutable field/source generations with an atomic current pointer."""

    def __init__(self, home: Path) -> None:
        self.home = Path(home)
        self.generations = self.home / "generations"
        self.bundles = self.home / "field-bundles"
        self.generations.mkdir(parents=True, exist_ok=True)
        self.bundles.mkdir(parents=True, exist_ok=True)
        self.pointer = self.home / "current.json"

    @staticmethod
    def _generation_number(value: str) -> int:
        if not re.fullmatch(r"g[0-9]{4,}", value):
            raise OrganismError("publication generation identity is invalid")
        return int(value[1:])

    def _source_manifest(self, workspace: Path, paths: Sequence[str]) -> list[dict[str, str]]:
        result: list[dict[str, str]] = []
        root = Path(workspace).resolve(strict=True)
        for raw in paths:
            relative = _text(raw, "source path", maximum=240).replace("\\", "/")
            path = (root / relative).resolve()
            if not path.is_relative_to(root) or not path.is_file():
                raise OrganismError(f"publication source is unavailable: {relative}")
            result.append(
                {
                    "path": relative,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
        return sorted(result, key=lambda item: item["path"])

    def _next_generation(self) -> str:
        values = [
            self._generation_number(path.stem)
            for path in self.generations.glob("g*.json")
            if re.fullmatch(r"g[0-9]{4,}", path.stem)
        ]
        return f"g{(max(values, default=0) + 1):04d}"

    def publish(
        self,
        *,
        workspace: Path,
        source_paths: Sequence[str],
        field_bundle: bytes,
        field_state_sha256: str,
        campaign_id: str,
        program_ids: Sequence[str],
        method_state: Mapping[str, Any],
        parent_generation: str | None = None,
    ) -> dict[str, Any]:
        generation_id = self._next_generation()
        bundle_sha256 = hashlib.sha256(field_bundle).hexdigest()
        bundle_path = self.bundles / bundle_sha256
        _atomic_bytes(bundle_path, field_bundle, immutable=True)
        body: dict[str, Any] = {
            "schema": PUBLICATION_SCHEMA,
            "generation_id": generation_id,
            "parent_generation": parent_generation,
            "source_manifest": self._source_manifest(workspace, source_paths),
            "field_state_sha256": _text(field_state_sha256, "field_state_sha256", maximum=64),
            "field_bundle_sha256": bundle_sha256,
            "campaign_id": campaign_id,
            "program_ids": sorted(set(program_ids)),
            "method_state": _plain(method_state),
        }
        body["generation_sha256"] = _digest(body)
        generation_path = self.generations / f"{generation_id}.json"
        _atomic_json(generation_path, body, immutable=True)
        pointer = {
            "schema": POINTER_SCHEMA,
            "generation_id": generation_id,
            "generation_sha256": body["generation_sha256"],
        }
        _atomic_json(self.pointer, pointer)
        return body

    def current(self) -> dict[str, Any] | None:
        if not self.pointer.exists():
            return None
        pointer = _read_json(self.pointer)
        if pointer.get("schema") != POINTER_SCHEMA:
            raise OrganismError("publication pointer schema is invalid")
        generation = self.read(str(pointer.get("generation_id")))
        if generation["generation_sha256"] != pointer.get("generation_sha256"):
            raise OrganismError("publication pointer digest does not match generation")
        return generation

    def read(self, generation_id: str) -> dict[str, Any]:
        generation_id = _identifier(generation_id, "generation_id")
        path = self.generations / f"{generation_id}.json"
        value = _read_json(path)
        declared = value.pop("generation_sha256", None)
        if declared != _digest(value):
            raise OrganismError("publication generation digest mismatch")
        value["generation_sha256"] = declared
        if value.get("generation_id") != generation_id:
            raise OrganismError("publication generation identity mismatch")
        return value

    def rollback(self, generation_id: str) -> dict[str, Any]:
        generation = self.read(generation_id)
        _atomic_json(
            self.pointer,
            {
                "schema": POINTER_SCHEMA,
                "generation_id": generation_id,
                "generation_sha256": generation["generation_sha256"],
            },
        )
        return generation

class ResearchOrganism:
    """A persistent root field coordinating independently learning members."""

    def __init__(
        self,
        home: Path,
        *,
        workspace: Path | None = None,
        mission: str = "Understand and improve Cassi",
        member_ids: Sequence[str] = ("member-000", "member-001"),
        hive_home: Path | None = None,
        root_owner: FieldIntelligenceOwner | None = None,
        root_lock: Any | None = None,
    ) -> None:
        self.home = Path(home).resolve()
        self.workspace = None if workspace is None else Path(workspace).resolve()
        self.mission = mission
        self.member_ids = tuple(member_ids)
        self.hive_home = None if hive_home is None else Path(hive_home).resolve()
        self.root_owner = root_owner
        self.root_lock = root_lock
        self.journal = EffectJournal(self.home / "effects")
        self.publications = PublicationLedger(self.home / "publications")

    @property
    def manifest_path(self) -> Path:
        return self.home / "manifest.json"

    @property
    def cohort_path(self) -> Path:
        return self.home / "cohort.json"

    @property
    def cohort_migrations_home(self) -> Path:
        return self.home / "cohort-migrations"

    def _cohort(self) -> dict[str, Any]:
        if not self.cohort_path.exists():
            manifest = self._load_manifest()
            return {
                "schema": COHORT_SCHEMA,
                "generation": 0,
                "active_member_ids": list(manifest["member_ids"]),
                "migration_id": None,
            }
        cohort = _read_json(self.cohort_path)
        if (
            cohort.get("schema") != COHORT_SCHEMA
            or not isinstance(cohort.get("active_member_ids"), list)
            or not isinstance(cohort.get("generation"), int)
        ):
            raise OrganismError("research organism cohort is malformed")
        return cohort

    def _active_member_ids(self) -> tuple[str, ...]:
        return tuple(
            _identifier(item, "active member_id")
            for item in self._cohort()["active_member_ids"]
        )

    def organize_membership(self) -> dict[str, Any]:
        """Make every authenticated member-to-member collaboration contiguous."""
        cohort = self._cohort()
        order = [
            _identifier(item, "active member_id")
            for item in cohort["active_member_ids"]
        ]
        active = set(order)
        acknowledged: dict[tuple[str, str], list[str]] = {}
        with self._open_residencies(include_members=True) as (root, members):
            for residency in (root, *members.values()):
                for sender, targets in self._communication_adjacency(
                    residency
                ).items():
                    if sender not in active:
                        continue
                    for receiver, edge in targets.items():
                        if (
                            receiver not in active
                            or receiver == sender
                            or not isinstance(edge, Mapping)
                        ):
                            continue
                        uses = acknowledged.setdefault((sender, receiver), [])
                        for use in edge.get("uses", []):
                            if isinstance(use, str) and use not in uses:
                                uses.append(use)
        if not acknowledged:
            return {
                "organized": False,
                "reason": "no-authenticated-collaboration",
            }
        neighbors: dict[str, set[str]] = {}
        for left, right in acknowledged:
            neighbors.setdefault(left, set()).add(right)
            neighbors.setdefault(right, set()).add(left)
        position = {member_id: index for index, member_id in enumerate(order)}
        clusters: list[list[str]] = []
        seen: set[str] = set()
        for member_id in order:
            if member_id not in neighbors or member_id in seen:
                continue
            seen.add(member_id)
            component = [member_id]
            cursor = 0
            while cursor < len(component):
                for linked in sorted(neighbors[component[cursor]]):
                    if linked not in seen:
                        seen.add(linked)
                        component.append(linked)
                cursor += 1
            clusters.append(sorted(component, key=position.__getitem__))
        clusters.sort(key=lambda cluster: min(cluster))
        use_sha256s = [
            use
            for pair in sorted(acknowledged)
            for use in acknowledged[pair]
        ]
        receipt = {
            "before": list(order),
            "after": list(order),
            "clusters": [list(cluster) for cluster in clusters],
            "use_sha256s": use_sha256s,
        }
        if all(
            position[cluster[-1]] - position[cluster[0]] == len(cluster) - 1
            for cluster in clusters
        ):
            return {"organized": False, "reason": "already-co-located", **receipt}
        clustered = {member_id for cluster in clusters for member_id in cluster}
        organized = [
            member_id for cluster in clusters for member_id in cluster
        ] + [member_id for member_id in order if member_id not in clustered]
        _atomic_json(
            self.cohort_path,
            {
                "schema": COHORT_SCHEMA,
                "generation": int(cohort["generation"]) + 1,
                "active_member_ids": organized,
                "migration_id": cohort.get("migration_id"),
            },
        )
        receipt["after"] = organized
        return {"organized": True, **receipt}

    @property
    def root_home(self) -> Path:
        return self.home / "root"

    @property
    def collective_hive_home(self) -> Path:
        """One shared exchange for the root and every independent member."""

        return (self.hive_home or self.home / "hive") / "collective"

    def member_home(self, member_id: str) -> Path:
        return self.home / "members" / _identifier(member_id, "member_id")

    def _load_manifest(self) -> dict[str, Any]:
        if not self.manifest_path.exists():
            raise OrganismError("research organism is not initialized")
        manifest = _read_json(self.manifest_path)
        if manifest.get("schema") != MANIFEST_SCHEMA:
            raise OrganismError("research organism manifest schema is unsupported")
        return manifest

    def _source_paths(self, workspace: Path) -> list[str]:
        """Return the complete local import closure of the organism runtime."""
        if (workspace / "CassiFI").is_dir():
            source_root = workspace / "CassiFI"
            prefix = "CassiFI/"
        else:
            source_root = workspace
            prefix = ""
        pending = [
            "cassi_research_organism.py",
            "cassi_research_residency.py",
            "cassi_research_worlds.py",
            "cassi_research_laboratories.py",
            "run_cassi_research_laboratories.py",
            "verify_cassi_research_laboratories.py",
            "run_cassi_research_organism.py",
            "cassi_equation_discovery.py",
            "run_cassi_equation_discovery.py",
            "verify_cassi_equation_discovery.py",
            "cassi_field_operator_invention.py",
            "run_cassi_field_operator_invention.py",
            "verify_cassi_field_operator_invention.py",
            "cassi_full_observable_invention.py",
            "run_cassi_full_observable_invention.py",
            "verify_cassi_full_observable_invention.py",
            "cassi_temporal_residual_authority.py",
        ]
        closure: set[str] = set()
        while pending:
            relative = pending.pop()
            if relative in closure:
                continue
            path = source_root / relative
            if not path.is_file():
                continue
            closure.add(relative)
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (OSError, UnicodeError, SyntaxError) as exc:
                raise OrganismError(f"organism source dependency is unreadable: {path}") from exc
            modules: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    modules.update(alias.name.split(".", 1)[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    modules.add(node.module.split(".", 1)[0])
            for module in sorted(modules):
                if module.startswith("cassi_") and (source_root / f"{module}.py").is_file():
                    pending.append(f"{module}.py")
        if not closure:
            raise OrganismError("organism runtime source closure is unavailable")
        return [prefix + item for item in sorted(closure)]

    @staticmethod
    def _bootstrap_work() -> list[dict[str, Any]]:
        return [
            {
                "id": "organism:instrument:bootstrap",
                "summary": "Observe a delayed instrument with an explicit context cue.",
                "request": {
                    "kind": "instrument_world_step",
                    "scenario": {
                        "steps": 32,
                        "change_at": 16,
                        "delay": 3,
                        "low": 0.0,
                        "high": 1.0,
                        "context_available": True,
                    },
                    "program": {"strategy": "hold-last", "window": 1},
                },
            }
        ]

    @staticmethod
    def _initial_frontier() -> dict[str, Any]:
        baseline = Construction(
            candidate_id="construction:baseline",
            parent_ids=(),
            operations=(
                {"op": "observe", "name": "delayed-measurement"},
                {"op": "emit", "name": "last-observation"},
            ),
            program={"strategy": "hold-last", "window": 1},
            applicability={
                "world": "instrument_world_step",
                "requires": ["measurement"],
            },
            status="incumbent",
            problem_roots=("organism:instrument:bootstrap",),
            effects={"world": "read-only-simulated-instrument"},
            novelty=("bootstrap-incumbent",),
        )
        temporal_hole = Construction(
            candidate_id="construction:temporal-hole",
            parent_ids=(baseline.candidate_id,),
            operations=(
                {"op": "observe", "name": "delayed-measurement"},
                {
                    "op": "hole",
                    "name": "discriminating-context",
                    "type": "observable-coordinate",
                },
            ),
            program={},
            applicability={
                "world": "instrument_world_step",
                "requires": ["measurement"],
            },
            status="incomplete",
            problem_roots=("organism:instrument:bootstrap",),
            holes=(
                {
                    "hole_id": "discriminating-context",
                    "accepts": ["observable-coordinate", "guard", "composition"],
                    "purpose": "separate histories with different futures",
                },
            ),
            assumptions={"hidden_answers": False, "world_is_resettable": True},
            effects={"world": "read-only-simulated-instrument"},
            search_program_version="bootstrap:v1",
            consumed_work=0,
            novelty=("new-composition", "new-learned-representation"),
        )
        return {
            "schema": FRONTIER_SCHEMA,
            "version": 1,
            "method_generation": 0,
            "next_index": 1,
            "entries": [baseline.as_dict(), temporal_hole.as_dict()],
        }
    @staticmethod
    def _program_record_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
        normalized = _plain(payload)
        program = normalized.get("program")
        if isinstance(program, Mapping) and program.get("schema") == "cassifi.semantic-program-payload.v1":
            return normalized
        return {
            "program": semantic_program_payload(
                program_kind="procedure",
                body={"organism_payload": normalized},
                reads=["field-records", "world-evidence"],
                emits=["research-proposal"],
                max_work=64,
                max_horizon=256,
                applicability={"owner": "research-organism"},
            ),
            "program_role": "development-method",
            "organism_payload": normalized,
        }

    @staticmethod
    def _unwrap_program_record(payload: Mapping[str, Any]) -> dict[str, Any]:
        if isinstance(payload.get("organism_payload"), Mapping):
            return _plain(payload["organism_payload"])
        return _plain(payload)


    def _ensure_record(
        self,
        residency: ResearchResidency,
        *,
        record_id: str,
        kind: str,
        payload: Mapping[str, Any],
        status: str = "active",
        epistemic_kind: str = "asserted",
    ) -> None:
        existing = residency._record(record_id)
        normalized = _plain(payload)
        if kind == "Program":
            normalized = self._program_record_payload(normalized)
        if existing is not None:
            if _plain(existing.get("payload")) != normalized:
                raise OrganismError(f"resident record differs: {record_id}")
            return
        residency._register(
            f"organism:seed:{hashlib.sha256(record_id.encode()).hexdigest()[:24]}",
            record_id,
            kind,
            normalized,
            status=status,
            epistemic_kind=epistemic_kind,
        )

    def _write_record(
        self,
        residency: ResearchResidency,
        *,
        record_id: str,
        kind: str,
        payload: Mapping[str, Any],
        status: str = "active",
        epistemic_kind: str = "derived",
    ) -> None:
        normalized = _plain(payload)
        if kind == "Program":
            normalized = self._program_record_payload(normalized)
        operation_id = f"organism:record:{hashlib.sha256(canonical_json_bytes({'record_id': record_id, 'payload': normalized})).hexdigest()[:32]}"
        residency._register(
            operation_id,
            record_id,
            kind,
            normalized,
            status=status,
            epistemic_kind=epistemic_kind,
        )

    def _root_residency(self) -> ResearchResidency:
        if self.root_owner is not None:
            return attach_research_residency(
                self.root_owner,
                self.root_home,
                hive_home=self.collective_hive_home,
                role="research-organism-root",
            )
        return open_research_residency(
            self.root_home,
            hive_home=self.collective_hive_home,
            import_skills=True,
            export_skills=True,
        )


    @contextlib.contextmanager
    def _open_residencies(
        self,
        *,
        include_members: bool = True,
    ) -> Iterator[tuple[ResearchResidency, dict[str, ResearchResidency]]]:
        self._load_manifest()
        lock = self.root_lock or contextlib.nullcontext()
        with lock:
            with contextlib.ExitStack() as stack:
                root = stack.enter_context(self._root_residency())
                members: dict[str, ResearchResidency] = {}
                if include_members:
                    for member_id in self._active_member_ids():
                        members[member_id] = stack.enter_context(
                            open_research_residency(
                                self.member_home(member_id),
                                hive_home=self.collective_hive_home,
                                import_skills=True,
                                export_skills=True,
                            )
                        )
                yield root, members

    def initialize(
        self,
        *,
        workspace: Path | None = None,
        mission: str | None = None,
        member_ids: Sequence[str] | None = None,
        profile: Mapping[str, int] | None = None,
    ) -> dict[str, Any]:
        """Create or resume the root and all independent member fields."""
        chosen_workspace = Path(workspace or self.workspace or Path.cwd()).resolve(strict=True)
        chosen_mission = _text(mission or self.mission, "mission", maximum=1024)
        chosen_members = tuple(member_ids or self.member_ids)
        if not chosen_members or len(chosen_members) > _MAX_MEMBERS:
            raise OrganismError(f"member_ids must contain 1..{_MAX_MEMBERS} members")
        chosen_members = tuple(_identifier(item, "member_id") for item in chosen_members)
        if len(set(chosen_members)) != len(chosen_members):
            raise OrganismError("member_ids must be unique")
        manifest = {
            "schema": MANIFEST_SCHEMA,
            "organism_schema": SCHEMA,
            "organism_id": "research-organism",
            "mission": chosen_mission,
            "workspace": str(chosen_workspace),
            "member_ids": list(chosen_members),
            "source_paths": self._source_paths(chosen_workspace),
            "authority": {
                "live_source_replacement": False,
                "external_actions": False,
                "network": False,
            },
        }
        if self.manifest_path.exists():
            current = self._load_manifest()
            for key in ("mission", "workspace", "member_ids", "authority"):
                if current.get(key) != manifest[key]:
                    raise OrganismError(f"existing organism has different {key}")
            manifest = current
        else:
            _atomic_json(self.manifest_path, manifest, immutable=True)
        if not self.cohort_path.exists():
            _atomic_json(
                self.cohort_path,
                {
                    "schema": COHORT_SCHEMA,
                    "generation": 0,
                    "active_member_ids": list(chosen_members),
                    "migration_id": None,
                },
            )
        effective_profile = dict(DEFAULT_PROFILE if profile is None else profile)
        work = self._bootstrap_work()
        self.root_home.mkdir(parents=True, exist_ok=True)
        lock = self.root_lock or contextlib.nullcontext()
        with lock:
            with self._root_residency() as root:
                root.initialize(
                    workspace=chosen_workspace,
                    mission=chosen_mission,
                    work=work,
                    profile=effective_profile,
                )
        for member_id in self._active_member_ids():
            member_home = self.member_home(member_id)
            with open_research_residency(
                member_home,
                hive_home=self.collective_hive_home,
                import_skills=True,
                export_skills=True,
            ) as member:
                member.initialize(
                    workspace=chosen_workspace,
                    mission=f"{chosen_mission} / independent member {member_id}",
                    work=work,
                    profile=effective_profile,
                )
        with self._open_residencies(include_members=True) as (root, members):
            self._ensure_record(
                root,
                record_id=ORGANISM_ID,
                kind="Value",
                payload={"schema": SCHEMA, "manifest": manifest},
            )
            self._ensure_record(
                root,
                record_id=FRONTIER_ID,
                kind="Program",
                payload=self._initial_frontier(),
            )
            self._ensure_record(
                root,
                record_id=METHODS_ID,
                kind="Program",
                payload={
                    "schema": "cassifi.research-organism-methods.v1",
                    "generation": 0,
                    "methods": [
                        "field-agenda",
                        "typed-construction",
                        "independent-world-comparison",
                        "evidence-conditioned-transfer",
                    ],
                },
            )
            self._ensure_record(
                root,
                record_id=MEMBERS_ID,
                kind="Binding",
                payload={
                    "schema": "cassifi.research-organism-members.v1",
                    "members": [
                        {
                            "member_id": member_id,
                            "field_home": str(self.member_home(member_id).relative_to(self.home)),
                            "role": "independent-researcher",
                        }
                        for member_id in chosen_members
                    ],
                },
            )
            for member_id, member in members.items():
                self._ensure_record(
                    member,
                    record_id=ORGANISM_ID,
                    kind="Value",
                    payload={
                        "schema": SCHEMA,
                        "member_id": member_id,
                        "root_organism_id": manifest["organism_id"],
                        "role": "independent-researcher",
                    },
                )
        return self.inspect()

    def _frontier(self, root: ResearchResidency) -> dict[str, Any]:
        record = root._record(FRONTIER_ID)
        if record is None:
            raise OrganismError("field construction frontier is missing")
        payload = self._unwrap_program_record(_plain(record["payload"]))
        if payload.get("schema") != FRONTIER_SCHEMA or not isinstance(payload.get("entries"), list):
            raise OrganismError("field construction frontier is malformed")
        entries = [Construction.from_dict(item).as_dict() for item in payload["entries"]]
        if len(entries) > _MAX_FRONTIER:
            raise OrganismError("field construction frontier exceeds its bound")
        payload["entries"] = entries
        return payload
    @staticmethod
    def _bounded_unit(value: Any, *, default: float = 0.0) -> float:
        """Normalize a construction-derived affect feature to [0, 1]."""
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = default
        if number != number:
            number = default
        return max(0.0, min(1.0, number))

    @classmethod
    def _construction_affect(cls, entry: Construction) -> dict[str, Any]:
        """Describe candidate affect without introducing host-side adaptive state."""
        evidence = entry.evidence
        expected_gain = 0.0
        if isinstance(evidence, Mapping):
            metrics = evidence.get("metrics")
            if isinstance(metrics, Mapping):
                expected_gain = metrics.get("accuracy", 0.0)
            elif isinstance(evidence.get("expected_gain"), (int, float)):
                expected_gain = evidence["expected_gain"]
        elif isinstance(evidence, (int, float)):
            expected_gain = evidence
        uncertainty = (
            len(entry.holes)
            + (1 if evidence is None else 0)
            + (0 if entry.assumptions else 1)
        ) / 4.0
        return {
            "project_id": AFFECT_PROJECT_ID,
            "object_id": entry.candidate_id,
            "novelty": cls._bounded_unit(len(entry.novelty) / 4.0),
            "uncertainty": cls._bounded_unit(uncertainty),
            "cost": cls._bounded_unit(entry.consumed_work / 32.0),
            "expected_gain": cls._bounded_unit(expected_gain),
        }

    def _affect_state(
        self,
        residency: ResearchResidency,
        *,
        object_id: str | None = None,
    ) -> dict[str, Any]:
        """Read affect context without publishing an inspect operation."""
        state = residency._task()
        try:
            return _plain(
                affect_context(
                    state,
                    project_id=AFFECT_PROJECT_ID,
                    object_id=object_id,
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise OrganismError("resident affect state is malformed") from exc

    def _affect_projection(
        self,
        residency: ResearchResidency,
        *,
        object_id: str | None = None,
    ) -> dict[str, Any]:
        """Project current basis, selected strategy, actions, and consequence."""
        state = residency._task()
        context = self._affect_state(residency, object_id=object_id)
        choices: list[Mapping[str, Any]] = []
        for record_id in state.get("current", {}).get("Event", {}):
            history = state.get("records", {}).get(record_id)
            if not isinstance(history, list) or not history:
                continue
            record = history[-1]
            if not isinstance(record, Mapping):
                continue
            value = record.get("payload", {}).get("affect_regulation")
            if (
                isinstance(value, Mapping)
                and value.get("project_id") == AFFECT_PROJECT_ID
                and (object_id is None or value.get("object_id") == object_id)
            ):
                choices.append(record)
        choices.sort(
            key=lambda row: (
                int(row.get("created_at", 0)),
                str(row.get("id", "")),
            )
        )
        if not choices:
            return {"context": context, "selected_strategy": None}
        choice = choices[-1]
        strategy = _plain(choice["payload"]["affect_regulation"])
        obligation_ref = strategy.get("outcome_obligation_ref")
        consequence = None
        if isinstance(obligation_ref, Mapping):
            obligation = residency._record(str(obligation_ref.get("id", "")))
            if obligation is not None:
                consequence = {
                    "state": obligation.get("payload", {}).get("state"),
                    "actual_action_refs": _plain(
                        obligation.get("payload", {}).get(
                            "actual_action_refs", []
                        )
                    ),
                    "actual_result_refs": _plain(
                        obligation.get("payload", {}).get(
                            "actual_result_refs", []
                        )
                    ),
                    "assessment_ref": _plain(
                        obligation.get("payload", {}).get(
                            "consequence_assessment_ref"
                        )
                    ),
                }
        return {
            "context": context,
            "selected_strategy": {
                "choice_ref": {
                    "id": choice["id"],
                    "kind": "Event",
                    "content_version": int(choice["content_version"]),
                },
                "mode": strategy.get("mode"),
                "selected_program_ref": _plain(
                    strategy.get("selected_program_ref")
                ),
                "proposed_actions": _plain(
                    strategy.get("proposed_actions", [])
                ),
                "expected_consequence": _plain(
                    strategy.get("expected_consequence")
                ),
                "outcome": consequence,
            },
        }


    def _sync_frontier_obligations(
        self,
        root: ResearchResidency,
        frontier: Mapping[str, Any],
    ) -> None:
        for raw in frontier["entries"]:
            entry = Construction.from_dict(raw)
            obligation_id = f"organism:frontier:obligation:{entry.candidate_id}"
            if entry.status != "proposed":
                existing = root._record(obligation_id)
                if (
                    existing is not None
                    and existing.get("status") != "resolved"
                ):
                    self._write_record(
                        root,
                        record_id=obligation_id,
                        kind="Obligation",
                        payload={
                            "purpose": "research-construction",
                            "candidate_id": entry.candidate_id,
                            "summary": entry.candidate_id,
                            "status": "resolved",
                            "resolution": f"frontier-status:{entry.status}",
                        },
                        status="resolved",
                        epistemic_kind="derived",
                    )
                continue
            self._write_record(
                root,
                record_id=obligation_id,
                kind="Obligation",
                payload={
                    "purpose": "research-construction",
                    "candidate_id": entry.candidate_id,
                    "object_id": entry.candidate_id,
                    "summary": entry.candidate_id,
                    "status": "pending",
                    "program": entry.program,
                    "expected_gain": entry.evidence,
                    "consumed_work": entry.consumed_work,
                    "novelty": list(entry.novelty),
                    "affect": self._construction_affect(entry),
                },
                status="pending",
                epistemic_kind="proposed",
            )

    def frontier(self) -> dict[str, Any]:
        with self._open_residencies(include_members=False) as (root, _):
            return self._frontier(root)

    def _expand_frontier_locked(
        self,
        root: ResearchResidency,
        frontier: dict[str, Any],
        *,
        discovery: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._sync_frontier_obligations(root, frontier)
        method_generation = int(frontier.get("method_generation", 0))
        root.semantic(
            {
                "operation": "autonomous-agenda",
                "operation_id": f"organism:frontier:agenda:affect:{method_generation:08d}",
                "project_id": AFFECT_PROJECT_ID,
                "goal": {
                    "objective": self.mission,
                    "focus": "expand a typed construction from admitted evidence",
                },
                "obligation_prefix": "organism:frontier:obligation:",
                "max_items": 32,
            }
        )
        ids = {item["candidate_id"] for item in frontier["entries"]}
        incomplete = next(
            (
                item
                for item in frontier["entries"]
                if item.get("status") == "incomplete"
                and item.get("candidate_id") == "construction:temporal-hole"
            ),
            None,
        )
        candidate: Construction | None = None
        if incomplete is not None and "construction:context-gated" not in ids:
            if discovery is None:
                raise OrganismError(
                    "the first construction expansion requires admitted world evidence"
                )
            learned = discovery.get("learning")
            if not isinstance(learned, Mapping):
                raise OrganismError("construction evidence has no field learning result")
            evidence = {
                "source_revision_id": discovery["source_revision_id"],
                "discovery_output_sha256": discovery["output_sha256"],
                "learning_status": learned.get("status"),
                "representation": learned.get("representation"),
                "metrics": _plain(discovery["metrics"]),
            }
            candidate = Construction(
                candidate_id="construction:context-gated",
                parent_ids=(
                    "construction:baseline",
                    "construction:temporal-hole",
                ),
                operations=(
                    {"op": "observe", "name": "delayed-measurement"},
                    {
                        "op": "introduce",
                        "name": "context-cue",
                        "type": "observable-coordinate",
                    },
                    {"op": "split-context", "name": "context-cue-present"},
                    {
                        "op": "compose",
                        "name": "cue-to-current-level",
                        "output": "instrument-level",
                    },
                ),
                program={"strategy": "context-gated", "window": 1},
                applicability={
                    "world": "instrument_world_step",
                    "requires": ["measurement", "context-cue"],
                },
                evidence=evidence,
                problem_roots=("organism:instrument:bootstrap",),
                assumptions={
                    "context_cue_is_observed": True,
                    "hidden_answers": False,
                },
                effects={"world": "read-only-simulated-instrument"},
                search_program_version="bootstrap:v1",
                consumed_work=int(discovery["metrics"]["steps"]),
                novelty=("new-composition", "new-learned-representation"),
            )
            incomplete["status"] = "expanded"
            incomplete["evidence"] = evidence
        else:
            accepted = [
                item for item in frontier["entries"] if item.get("status") == "accepted"
            ]
            if accepted and "construction:context-gated-v2" not in ids:
                parent = accepted[-1]
                candidate = Construction(
                    candidate_id="construction:context-gated-v2",
                    parent_ids=(parent["candidate_id"],),
                    operations=(
                        {"op": "reuse", "name": "context-gated"},
                        {"op": "parameterize", "name": "window", "value": 2},
                        {"op": "guard", "name": "context-cue-present"},
                    ),
                    program={"strategy": "context-gated", "window": 2},
                    applicability={
                        "world": "instrument_world_step",
                        "requires": ["context-cue"],
                    },
                    evidence=parent.get("evidence"),
                    problem_roots=tuple(parent.get("problem_roots", [])),
                    assumptions={"context_cue_is_observed": True},
                    effects={"world": "read-only-simulated-instrument"},
                    search_program_version="bootstrap:v2",
                    consumed_work=1,
                    novelty=("new-parameter", "new-search-method"),
                )
        if candidate is not None:
            frontier["entries"].append(candidate.as_dict())
            frontier["next_index"] = int(frontier.get("next_index", 0)) + 1
            frontier["method_generation"] = method_generation + 1
            history = list(frontier.get("construction_history", []))
            history.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "parent_ids": list(candidate.parent_ids),
                    "search_program_version": candidate.search_program_version,
                    "work": candidate.consumed_work,
                }
            )
            frontier["construction_history"] = history[-_MAX_FRONTIER:]
            self._write_record(
                root,
                record_id=FRONTIER_ID,
                kind="Program",
                payload=frontier,
                epistemic_kind="induced",
            )
            self._sync_frontier_obligations(root, frontier)
        return frontier

    def expand_frontier(self) -> dict[str, Any]:
        """Generate the next typed construction from field-resident history."""
        with self._open_residencies(include_members=False) as (root, _):
            frontier = self._frontier(root)
            needs_evidence = any(
                item.get("candidate_id") == "construction:temporal-hole"
                and item.get("status") == "incomplete"
                for item in frontier["entries"]
            )
            discovery = None
            if needs_evidence:
                baseline = next(
                    Construction.from_dict(item)
                    for item in frontier["entries"]
                    if item["candidate_id"] == "construction:baseline"
                )
                discovery = self._run_candidate(
                    root,
                    actor="root",
                    candidate=baseline,
                    scenario=self._scenario(0, "root", "construction-frontier"),
                    split="construction-frontier",
                    round_index=0,
                )
            return self._expand_frontier_locked(
                root,
                frontier,
                discovery=discovery,
            )

    @staticmethod
    def _scenario(round_index: int, actor: str, split: str) -> dict[str, Any]:
        token = int(hashlib.sha256(f"{round_index}:{actor}:{split}".encode()).hexdigest()[:8], 16)
        return {
            "steps": 32,
            "change_at": 10 + token % 13,
            "delay": 2 + token % 4,
            "low": -0.5,
            "high": 1.5,
            "context_available": True,
            "tolerance": 1e-12,
        }

    @staticmethod
    def _derive_metrics(output: Mapping[str, Any]) -> dict[str, Any]:
        evidence = output.get("evidence")
        if not isinstance(evidence, Mapping):
            raise OrganismError("world output has no evidence envelope")
        trace = evidence.get("trace")
        declared_trace = evidence.get("trace_sha256")
        if not isinstance(trace, list) or not isinstance(declared_trace, str):
            raise OrganismError("world output has no raw trace")
        if _digest(trace) != declared_trace:
            raise OrganismError("world trace digest does not match its rows")
        if not trace:
            raise OrganismError("world trace is empty")
        correct = sum(bool(row.get("correct")) for row in trace if isinstance(row, Mapping))
        errors = [float(row["absolute_error"]) for row in trace if isinstance(row, Mapping)]
        if len(errors) != len(trace):
            raise OrganismError("world trace contains malformed error rows")
        return {
            "accuracy": correct / len(trace),
            "correct_steps": correct,
            "mean_abs_error": sum(errors) / len(errors),
            "steps": len(trace),
            "trace_sha256": declared_trace,
        }

    def _appraise_assessment(
        self,
        residency: ResearchResidency,
        *,
        assessment_id: str,
        candidate_id: str,
    ) -> dict[str, Any]:
        """Appraise one resident Assessment, recovering idempotently on replay."""
        record = residency._record(assessment_id)
        if record is None:
            raise OrganismError(f"assessment is missing for affect appraisal: {assessment_id}")
        if (
            record.get("kind") != "Assessment"
            or record.get("epistemic_kind") != "assessed"
        ):
            raise OrganismError("affect evidence is not an assessed Assessment")
        payload = _plain(record.get("payload", {}))
        if (
            payload.get("schema") != CAMPAIGN_SCHEMA
            or payload.get("learning_mode") != "development"
        ):
            raise OrganismError("only assessed development outcomes may feed affect")
        metrics = payload.get("metrics")
        if (
            not isinstance(metrics, Mapping)
            or not isinstance(payload.get("source_revision_id"), str)
            or not payload.get("source_revision_id")
            or not isinstance(payload.get("output_sha256"), str)
            or not payload.get("output_sha256")
        ):
            raise OrganismError("development assessment is not admissible to affect")
        result = residency.semantic(
            {
                "operation": "appraise-experience",
                "operation_id": (
                    f"organism:affect:appraise:{assessment_id}:v"
                    f"{int(record['content_version'])}"
                ),
                "evidence": {
                    "id": assessment_id,
                    "kind": "Assessment",
                    "content_version": int(record["content_version"]),
                },
                "project_id": AFFECT_PROJECT_ID,
                "object_id": candidate_id,
            }
        )
        context = result.get("context")
        appraisal = result.get("appraisal")
        regulation = result.get("regulation")
        if (
            not isinstance(context, Mapping)
            or not isinstance(appraisal, Mapping)
            or not isinstance(regulation, Mapping)
        ):
            raise OrganismError("appraise-experience returned malformed affect result")
        return _plain(result)

    def _run_candidate(
        self,
        residency: ResearchResidency,
        *,
        actor: str,
        candidate: Construction,
        scenario: Mapping[str, Any],
        split: str,
        round_index: int,
        learning_mode: str = "development",
    ) -> dict[str, Any]:
        if learning_mode not in {"development", "frozen-reporting"}:
            raise OrganismError("candidate learning mode is unsupported")
        operation_key = {
            "actor": actor,
            "candidate": candidate.candidate_id,
            "scenario": scenario,
            "split": split,
            "round": round_index,
            "learning_mode": learning_mode,
        }
        token = hashlib.sha256(canonical_json_bytes(operation_key)).hexdigest()[:32]
        operation_id = f"organism:world:{token}"
        journaled = self.journal.get(operation_id)
        if journaled is None:
            from cassi_research_worlds import execute_work

            request = {
                "kind": "instrument_world_step",
                "operation_id": operation_id,
                "scenario": _plain(scenario),
                "program": _plain(candidate.program),
            }
            output = execute_work(
                request,
                workspace=Path(self._load_manifest()["workspace"]),
                artifact_home=self.home / "world-artifacts" / actor / split,
            )
            if not isinstance(output, Mapping):
                raise OrganismError("world adapter did not return an object")
            journaled = self.journal.record(
                operation_id,
                actor=actor,
                request=request,
                result=dict(output),
            )
        output = journaled["result"]
        if not isinstance(output, Mapping):
            raise OrganismError("journaled world result is malformed")
        metrics = self._derive_metrics(output)
        assessment_id = f"organism:assessment:{token}"
        existing = residency._record(assessment_id)
        if existing is not None:
            payload = _plain(existing["payload"])
            if payload.get("output_sha256") != _digest(output):
                raise OrganismError("resident assessment differs from effect journal")
            recorded_learning_mode = payload.get("learning_mode", learning_mode)
            affect = (
                self._appraise_assessment(
                    residency,
                    assessment_id=assessment_id,
                    candidate_id=candidate.candidate_id,
                )
                if recorded_learning_mode == "development"
                else None
            )
            return {
                "actor": actor,
                "candidate_id": candidate.candidate_id,
                "split": split,
                "output_sha256": _digest(output),
                "metrics": payload["metrics"],
                "source_revision_id": payload["source_revision_id"],
                "field_state_sha256": residency.owner.state.state_sha256,
                "learning": payload.get("learning"),
                "learning_mode": recorded_learning_mode,
                "affect": affect,
                "replayed": True,
            }
        content = canonical_json_bytes(output)
        if len(content) > _MAX_RESULT_BYTES:
            raise OrganismError("world output exceeds the organism evidence bound")
        source = SourceInput(
            source_id=operation_id,
            content=content,
            media_type="application/json",
            codec=CODEC_JSON,
            observed_timestamp=operation_id,
            scope=f"research-organism:{actor}",
            claim_category="research-world-outcome",
            fidelity="exact-observed-bytes",
            labels=("research-organism", actor, split),
        )
        archive = residency.owner.archive_source(
            operation_id=f"{operation_id}:archive",
            source=source,
            context={
                "actor": actor,
                "candidate_id": candidate.candidate_id,
                "split": split,
            },
            event_kind="research-world-outcome",
        )
        revision_id = archive["source"]["revision_id"]
        evidence = output["evidence"]
        trace = evidence["trace"]
        observations = [
            {
                "subject": f"{operation_id}:step:{row['step']}",
                "attribute": "prediction-error",
                "value": row["absolute_error"],
                "frame": {"split": split, "candidate_id": candidate.candidate_id},
            }
            for row in trace[:_MAX_TRACE]
        ]
        residency.semantic(
            {
                "operation": "observe",
                "operation_id": f"{operation_id}:observe",
                "delivery_id": f"{operation_id}:delivery",
                "event_id": f"{operation_id}:event",
                "observations": observations,
                "source": {"source_revision_id": revision_id},
                "support_roots": [revision_id],
            }
        )
        learning: Mapping[str, Any] | None = None
        opportunities = output.get("learning_opportunities")
        if (
            learning_mode == "development"
            and isinstance(opportunities, list)
            and opportunities
        ):
            learning = residency.semantic(
                {
                    "operation": "autonomous-learn",
                    "operation_id": f"{operation_id}:learn",
                    "goal": {
                        "objective": "retain a reusable method for this world boundary",
                        "candidate_id": candidate.candidate_id,
                    },
                    "opportunities": [
                        item for item in opportunities if isinstance(item, Mapping)
                    ],
                }
            )
        elif learning_mode == "frozen-reporting":
            learning = {
                "status": "disabled",
                "reason": "frozen-knowledge-evaluation",
            }
        payload = {
            "schema": CAMPAIGN_SCHEMA,
            "actor": actor,
            "candidate_id": candidate.candidate_id,
            "split": split,
            "round": round_index,
            "output_sha256": _digest(output),
            "source_revision_id": revision_id,
            "evidence_sha256": evidence.get("evidence_sha256"),
            "metrics": metrics,
            "learning": learning,
            "learning_mode": learning_mode,
        }
        self._write_record(
            residency,
            record_id=assessment_id,
            kind="Assessment",
            payload=payload,
            epistemic_kind="assessed",
        )
        affect = (
            self._appraise_assessment(
                residency,
                assessment_id=assessment_id,
                candidate_id=candidate.candidate_id,
            )
            if learning_mode == "development"
            else None
        )
        return {
            "actor": actor,
            "candidate_id": candidate.candidate_id,
            "split": split,
            "output_sha256": _digest(output),
            "metrics": metrics,
            "source_revision_id": revision_id,
            "field_state_sha256": residency.owner.state.state_sha256,
            "learning": learning,
            "learning_mode": learning_mode,
            "affect": affect,
            "replayed": False,
        }

    @staticmethod
    def _compare(candidate: Mapping[str, Any], baseline: Mapping[str, Any]) -> dict[str, Any]:
        candidate_metrics = candidate["metrics"]
        baseline_metrics = baseline["metrics"]
        delta_accuracy = float(candidate_metrics["accuracy"]) - float(baseline_metrics["accuracy"])
        delta_error = float(baseline_metrics["mean_abs_error"]) - float(candidate_metrics["mean_abs_error"])
        supported = delta_accuracy > 1e-12 or delta_error > 1e-12
        return {
            "candidate_accuracy": float(candidate_metrics["accuracy"]),
            "baseline_accuracy": float(baseline_metrics["accuracy"]),
            "delta_accuracy": delta_accuracy,
            "candidate_mean_abs_error": float(candidate_metrics["mean_abs_error"]),
            "baseline_mean_abs_error": float(baseline_metrics["mean_abs_error"]),
            "delta_error_reduction": delta_error,
            "supported": supported,
            "comparison_basis": "raw-trace-derived-metrics",
        }

    def _select_candidate(
        self,
        root: ResearchResidency,
        frontier: dict[str, Any],
        *,
        round_index: int,
    ) -> tuple[Construction, dict[str, Any]]:
        pending = [
            Construction.from_dict(item)
            for item in frontier["entries"]
            if item.get("status") == "proposed"
        ]
        if not pending:
            baseline = next(
                (
                    Construction.from_dict(item)
                    for item in frontier["entries"]
                    if item["candidate_id"] == "construction:baseline"
                ),
                None,
            )
            if baseline is None:
                raise OrganismError("field frontier incumbent is missing")
            discovery = self._run_candidate(
                root,
                actor="root",
                candidate=baseline,
                scenario=self._scenario(round_index, "root", "construction"),
                split="construction",
                round_index=round_index,
            )
            frontier = self._expand_frontier_locked(
                root,
                frontier,
                discovery=discovery,
            )
            pending = [
                Construction.from_dict(item)
                for item in frontier["entries"]
                if item.get("status") == "proposed"
            ]
        if not pending:
            raise OrganismError("field construction search produced no executable proposal")
        self._sync_frontier_obligations(root, frontier)
        operation_id = f"organism:campaign:{round_index:08d}:agenda:affect"
        agenda = root.semantic(
            {
                "operation": "autonomous-agenda",
                "operation_id": operation_id,
                "project_id": AFFECT_PROJECT_ID,
                "goal": {
                    "objective": self.mission,
                    "focus": "select an unfamiliar construction",
                },
                "obligation_prefix": "organism:frontier:obligation:",
                "max_items": 32,
            }
        )
        selected_item = agenda.get("selected")
        selected_ref = (
            selected_item.get("obligation")
            if isinstance(selected_item, Mapping)
            else None
        )
        selected_obligation_id = (
            selected_ref.get("id")
            if isinstance(selected_ref, Mapping)
            else None
        )
        candidates_by_obligation = {
            f"organism:frontier:obligation:{candidate.candidate_id}": candidate
            for candidate in pending
        }
        selected = candidates_by_obligation.get(str(selected_obligation_id))
        if selected is None:
            raise OrganismError(
                "field agenda did not select an executable construction"
            )
        selection = {
            "method": "semantic.autonomous-agenda",
            "operation_id": operation_id,
            "event": agenda.get("event"),
            "selected": selected_item,
            "candidate_id": selected.candidate_id,
            "agenda": agenda.get("agenda", []),
        }
        return selected, selection

    def _assess_selected_affect_outcome(
        self,
        residency: ResearchResidency,
        *,
        campaign_id: str,
        selection: Mapping[str, Any],
        accepted: bool,
    ) -> dict[str, Any] | None:
        """Join the agenda's committed regulation choice to the completed campaign."""
        selected = selection.get("selected")
        if not isinstance(selected, Mapping):
            return None
        choice_ref = selected.get("affect_regulation")
        obligation_ref = selected.get("affect_outcome_obligation")
        if not isinstance(choice_ref, Mapping) or not isinstance(
            obligation_ref, Mapping
        ):
            return None
        choice = residency._record(str(choice_ref.get("id", "")))
        obligation = residency._record(str(obligation_ref.get("id", "")))
        campaign = residency._record(campaign_id)
        if choice is None or obligation is None or campaign is None:
            raise OrganismError("agenda affect outcome references are incomplete")
        obligation_payload = obligation.get("payload", {})
        if not isinstance(obligation_payload, Mapping):
            raise OrganismError("agenda affect outcome obligation is malformed")
        if obligation_payload.get("state") != "pending":
            assessment_ref = obligation_payload.get("consequence_assessment_ref")
            return (
                None
                if not isinstance(assessment_ref, Mapping)
                else _plain(assessment_ref)
            )
        regulation = choice.get("payload", {}).get("affect_regulation")
        if not isinstance(regulation, Mapping):
            raise OrganismError("agenda affect regulation choice is malformed")
        actions = regulation.get("proposed_actions")
        if not isinstance(actions, list) or not actions:
            raise OrganismError("agenda affect regulation proposed no action")
        action = actions[0]
        if not isinstance(action, Mapping):
            raise OrganismError("agenda affect action is malformed")
        action_record_id = (
            "event:organism-affect-action:"
            + hashlib.sha256(
                canonical_json_bytes({
                    "campaign_id": campaign_id,
                    "choice_ref": choice_ref,
                    "action_id": action.get("action_id"),
                })
            ).hexdigest()
        )
        action_record = residency._record(action_record_id)
        if action_record is None:
            residency.semantic({
                "operation": "register",
                "operation_id": f"{action_record_id}:register",
                "record_id": action_record_id,
                "kind": "Event",
                "payload": {
                    "affect_action": {
                        "schema": "cassifi.affect-action.v1",
                        "episode_id": regulation.get("episode_id"),
                        "action_id": action.get("action_id"),
                        "operation": action.get("operation"),
                        "status": "executed",
                        "execution": {
                            "campaign_id": campaign_id,
                            "candidate_id": selection.get("candidate_id"),
                            "selection_operation_id": selection.get("operation_id"),
                        },
                    }
                },
                "status": "active",
            })
            action_record = residency._record(action_record_id)
        if action_record is None:
            raise OrganismError("agenda affect action was not committed")
        outcome = residency.semantic({
            "operation": "assess-affect-outcome",
            "operation_id": f"organism:affect-outcome:{campaign_id}",
            "outcome_obligation_ref": {
                "id": obligation["id"],
                "kind": "Obligation",
                "content_version": int(obligation["content_version"]),
            },
            "actual_action_refs": [{
                "id": action_record_id,
                "kind": "Event",
                "content_version": int(action_record["content_version"]),
            }],
            "actual_result_refs": [{
                "id": campaign_id,
                "kind": "Assessment",
                "content_version": int(campaign["content_version"]),
            }],
            "consequence": {
                "status": "observed",
                "progress": 1.0 if accepted else 0.0,
                "information_gain": 1.0,
                "capability_change": 1.0 if accepted else 0.0,
                "cost": {"population_rounds": 1},
                "limitations": ["comparative campaign association"],
            },
            "attribution": "comparative-support",
        })
        assessment = outcome.get("assessment")
        if not isinstance(assessment, Mapping):
            raise OrganismError("affect outcome assessment is malformed")
        return _plain(assessment)

    def _bundle(self, candidate: Construction, root_result: Mapping[str, Any], campaign_id: str) -> dict[str, Any]:
        body = {
            "schema": BUNDLE_SCHEMA,
            "campaign_id": campaign_id,
            "candidate": candidate.as_dict(),
            "root_result": _plain(root_result),
            "source_scope": "root-field-derived-world-evidence",
        }
        body["bundle_id"] = _digest(body)
        path = self.home / "bundles" / body["bundle_id"]
        _atomic_json(path, body, immutable=True)
        return body

    def _adopt_bundle(
        self,
        member: ResearchResidency,
        *,
        member_id: str,
        bundle: Mapping[str, Any],
    ) -> dict[str, Any]:
        bundle_id = _identifier(bundle["bundle_id"], "bundle_id")
        content = canonical_json_bytes(bundle)
        source = SourceInput(
            source_id=f"{bundle_id}:{member_id}:lesson",
            content=content,
            media_type="application/json",
            codec=CODEC_JSON,
            observed_timestamp=str(bundle["campaign_id"]),
            scope=f"research-organism:{member_id}",
            claim_category="attributed-root-lesson",
            fidelity="exact-bundle-bytes",
            labels=("research-organism", "lesson", member_id),
        )
        archive = member.owner.archive_source(
            operation_id=f"organism:adopt:{bundle_id[:32]}:{member_id}:archive",
            source=source,
            context={
                "bundle_id": bundle_id,
                "campaign_id": bundle["campaign_id"],
                "origin": "root-field",
            },
            epistemic_type="asserted",
            event_kind="research-lesson",
        )
        revision_id = archive["source"]["revision_id"]
        candidate = Construction.from_dict(
            _foreign_source_view(bundle["candidate"])
        )
        program_id = PROGRAM_PREFIX + bundle_id[:32]
        self._write_record(
            member,
            record_id=program_id,
            kind="Program",
            payload={
                "schema": BUNDLE_SCHEMA,
                "bundle_id": bundle_id,
                "candidate": candidate.as_dict(),
                "recipient": member_id,
                "root_result_sha256": _digest(bundle["root_result"]),
                "source_revision_id": revision_id,
            },
            epistemic_kind="attributed",
        )
        self._write_record(
            member,
            record_id=f"organism:binding:{bundle_id[:32]}",
            kind="Binding",
            payload={
                "schema": "cassifi.research-organism-adoption.v1",
                "bundle_id": bundle_id,
                "program_id": program_id,
                "origin": "root-field",
                "recipient": member_id,
                "mode": "replay-then-verify",
                "source_revision_id": revision_id,
            },
            epistemic_kind="attributed",
        )
        return {
            "bundle_id": bundle_id,
            "program_id": program_id,
            "source_revision_id": revision_id,
            "bundle_sha256": hashlib.sha256(content).hexdigest(),
            "status": "adopted",
        }
    def _admit_member_report(
        self,
        root: ResearchResidency,
        *,
        campaign_id: str,
        member_id: str,
        candidate: Mapping[str, Any],
        baseline: Mapping[str, Any],
        comparison: Mapping[str, Any],
        adoption: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Archive one member's complete report, then expose a root-owned view."""
        report = {
            "schema": "cassifi.research-organism-member-report.v1",
            "campaign_id": campaign_id,
            "member_id": member_id,
            "candidate": _plain(candidate),
            "baseline": _plain(baseline),
            "comparison": _plain(comparison),
            "adoption": _plain(adoption),
        }
        content = canonical_json_bytes(report)
        if len(content) > _MAX_RESULT_BYTES:
            raise OrganismError("member report exceeds the organism evidence bound")
        report_digest = hashlib.sha256(content).hexdigest()
        source = SourceInput(
            source_id=f"{campaign_id}:{member_id}:report",
            content=content,
            media_type="application/json",
            codec=CODEC_JSON,
            observed_timestamp=campaign_id,
            scope="research-organism:root",
            claim_category="attributed-member-report",
            fidelity="exact-member-report-bytes",
            labels=("research-organism", "member-report", member_id),
        )
        archive = root.owner.archive_source(
            operation_id=f"{campaign_id}:{member_id}:report:archive",
            source=source,
            context={
                "campaign_id": campaign_id,
                "member_id": member_id,
                "report_sha256": report_digest,
            },
            epistemic_type="asserted",
        )
        return {
            "member_id": member_id,
            "candidate_output_sha256": candidate["output_sha256"],
            "baseline_output_sha256": baseline["output_sha256"],
            "candidate_metrics": _plain(candidate["metrics"]),
            "baseline_metrics": _plain(baseline["metrics"]),
            "comparison": _plain(comparison),
            "adoption": _foreign_source_view(adoption),
            "member_field_state_sha256": candidate["field_state_sha256"],
            "report_sha256": report_digest,
            "source_revision_id": archive["source"]["revision_id"],
        }
    def _member_evaluation_branch(
        self,
        *,
        campaign_id: str,
        member_id: str,
        branch: str,
    ) -> Path:
        """Materialize one immutable-once member checkpoint branch."""
        branch = _identifier(branch, "evaluation branch")
        token = hashlib.sha256(campaign_id.encode("utf-8")).hexdigest()[:24]
        target = self.home / "evaluation-branches" / token / member_id / branch
        if target.exists():
            return target
        target.parent.mkdir(parents=True, exist_ok=True)
        staging = target.with_name(f".{target.name}.{os.getpid()}.pending")
        if staging.exists():
            raise OrganismError(f"stale evaluation branch staging path: {staging}")
        try:
            shutil.copytree(self.member_home(member_id), staging)
            os.replace(staging, target)
        except Exception:
            if staging.exists():
                shutil.rmtree(staging)
            raise
        return target




    def run_population_round(self, round_index: int | None = None) -> dict[str, Any]:
        """Run one root discovery, independent member transfer, and assessment."""
        manifest = self._load_manifest()
        if round_index is None:
            current = self.publications.current()
            round_index = 0 if current is None else int(current["generation_id"][1:])
        if isinstance(round_index, bool) or not isinstance(round_index, int) or round_index < 0:
            raise OrganismError("round_index must be a nonnegative integer")
        campaign_id = f"{CAMPAIGN_PREFIX}{round_index:08d}"
        with self._open_residencies(include_members=False) as (root, _):
            prior = root._record(campaign_id)
            if prior is not None:
                campaign = _plain(prior["payload"])
                if campaign.get("phase") == "assessed" and campaign.get("verdict") == "accepted":
                    campaign["publication"] = self._publish_locked(root, campaign)
                    campaign["phase"] = "complete"
                    self._write_record(
                        root,
                        record_id=campaign_id,
                        kind="Assessment",
                        payload=campaign,
                        status="active",
                        epistemic_kind="assessed",
                    )
                affect_outcome = self._assess_selected_affect_outcome(
                    root,
                    campaign_id=campaign_id,
                    selection=campaign.get("selection", {}),
                    accepted=campaign.get("verdict") == "accepted",
                )
                if campaign.get("affect_outcome_assessment") != affect_outcome:
                    campaign["affect_outcome_assessment"] = affect_outcome
                    self._write_record(
                        root,
                        record_id=campaign_id,
                        kind="Assessment",
                        payload=campaign,
                        status="active",
                        epistemic_kind="assessed",
                    )
                return campaign
            frontier = self._frontier(root)
            candidate, selection = self._select_candidate(
                root,
                frontier,
                round_index=round_index,
            )
            baseline = next(
                (Construction.from_dict(item) for item in frontier["entries"] if item["candidate_id"] == "construction:baseline"),
                None,
            )
            if baseline is None:
                raise OrganismError("frontier incumbent is missing")
            root_scenario = self._scenario(round_index, "root", "holdout")
            root_candidate = self._run_candidate(
                root,
                actor="root",
                candidate=candidate,
                scenario=root_scenario,
                split="holdout",
                round_index=round_index,
            )
            root_baseline = self._run_candidate(
                root,
                actor="root",
                candidate=baseline,
                scenario=root_scenario,
                split="holdout-baseline",
                round_index=round_index,
            )
            root_comparison = self._compare(root_candidate, root_baseline)
            bundle = self._bundle(candidate, root_candidate, campaign_id)
            member_reports: list[dict[str, Any]] = []
            branch_token = hashlib.sha256(campaign_id.encode("utf-8")).hexdigest()[:24]
            for raw_member_id in manifest["member_ids"]:
                member_id = _identifier(raw_member_id, "member_id")
                member_hive = (
                    (self.hive_home or self.home / "hive") / member_id
                )
                with open_research_residency(
                    self.member_home(member_id),
                    hive_home=member_hive,
                ) as member:
                    parent_state_sha256 = member.owner.state.state_sha256
                control_home = self._member_evaluation_branch(
                    campaign_id=campaign_id,
                    member_id=member_id,
                    branch="control",
                )
                candidate_home = self._member_evaluation_branch(
                    campaign_id=campaign_id,
                    member_id=member_id,
                    branch="candidate",
                )
                scenario = self._scenario(round_index, member_id, "holdout")
                with open_research_residency(
                    control_home,
                    hive_home=(
                        self.home
                        / "evaluation-hives"
                        / branch_token
                        / member_id
                        / "control"
                    ),
                ) as control:
                    if control.owner.state.state_sha256 != parent_state_sha256:
                        raise OrganismError(
                            "control branch does not match the member checkpoint"
                        )
                    member_baseline = self._run_candidate(
                        control,
                        actor=f"{member_id}.control",
                        candidate=baseline,
                        scenario=scenario,
                        split="transfer-baseline",
                        round_index=round_index,
                        learning_mode="frozen-reporting",
                    )
                with open_research_residency(
                    candidate_home,
                    hive_home=(
                        self.home
                        / "evaluation-hives"
                        / branch_token
                        / member_id
                        / "candidate"
                    ),
                ) as treatment:
                    if treatment.owner.state.state_sha256 != parent_state_sha256:
                        raise OrganismError(
                            "candidate branch does not match the member checkpoint"
                        )
                    branch_adoption = self._adopt_bundle(
                        treatment,
                        member_id=member_id,
                        bundle=bundle,
                    )
                    member_candidate = self._run_candidate(
                        treatment,
                        actor=f"{member_id}.candidate",
                        candidate=candidate,
                        scenario=scenario,
                        split="transfer-holdout",
                        round_index=round_index,
                        learning_mode="frozen-reporting",
                    )
                with open_research_residency(
                    self.member_home(member_id),
                    hive_home=member_hive,
                ) as member:
                    if member.owner.state.state_sha256 != parent_state_sha256:
                        raise OrganismError(
                            "member changed while its evaluation branches ran"
                        )
                    adoption = self._adopt_bundle(
                        member,
                        member_id=member_id,
                        bundle=bundle,
                    )
                    actual_post_state_sha256 = member.owner.state.state_sha256
                adoption["evaluation"] = {
                    "mode": "matched-checkpoint-frozen-knowledge",
                    "parent_field_state_sha256": parent_state_sha256,
                    "control_field_state_sha256": member_baseline[
                        "field_state_sha256"
                    ],
                    "candidate_field_state_sha256": member_candidate[
                        "field_state_sha256"
                    ],
                    "actual_recipient_state_sha256": actual_post_state_sha256,
                    "branch_adoption": _foreign_source_view(branch_adoption),
                }
                comparison = self._compare(member_candidate, member_baseline)
                member_reports.append(
                    self._admit_member_report(
                        root,
                        campaign_id=campaign_id,
                        member_id=member_id,
                        candidate=member_candidate,
                        baseline=member_baseline,
                        comparison=comparison,
                        adoption=adoption,
                    )
                )
            independent_support = [
                report["comparison"]["supported"] for report in member_reports
            ]
            accepted = bool(root_comparison["supported"] and (not independent_support or any(independent_support)))
            entry_rows = []
            for raw in frontier["entries"]:
                if raw["candidate_id"] == candidate.candidate_id:
                    updated = dict(raw)
                    updated["status"] = "accepted" if accepted else "rejected"
                    updated["evidence"] = {
                        "campaign_id": campaign_id,
                        "root_comparison": root_comparison,
                        "independent_member_support": sum(independent_support),
                    }
                    entry_rows.append(updated)
                else:
                    entry_rows.append(raw)
            frontier["entries"] = entry_rows
            frontier["accepted"] = [
                item["candidate_id"] for item in entry_rows if item.get("status") == "accepted"
            ]
            self._write_record(
                root,
                record_id=FRONTIER_ID,
                kind="Program",
                payload=frontier,
                epistemic_kind="induced",
            )
            if accepted:
                frontier = self._expand_frontier_locked(root, frontier)
            campaign = {
                "schema": CAMPAIGN_SCHEMA,
                "campaign_id": campaign_id,
                "round": round_index,
                "candidate_id": candidate.candidate_id,
                "selection": selection,
                "bundle_id": bundle["bundle_id"],
                "root": {"candidate": root_candidate, "baseline": root_baseline, "comparison": root_comparison},
                "members": member_reports,
                "verdict": "accepted" if accepted else "rejected",
                "phase": "assessed" if accepted else "complete",
                "publication": None,
                "feedback_boundary": {
                    "development_feedback": "entered-root-field",
                    "reporting_evaluation": "not-adaptive-input",
                },
            }
            self._write_record(
                root,
                record_id=campaign_id,
                kind="Assessment",
                payload=campaign,
                status="active",
                epistemic_kind="assessed",
            )
            if accepted:
                campaign["publication"] = self._publish_locked(root, campaign)
                campaign["phase"] = "complete"
                self._write_record(
                    root,
                    record_id=campaign_id,
                    kind="Assessment",
                    payload=campaign,
                    status="active",
                    epistemic_kind="assessed",
                )
            affect_outcome = self._assess_selected_affect_outcome(
                root,
                campaign_id=campaign_id,
                selection=selection,
                accepted=accepted,
            )
            campaign["affect_outcome_assessment"] = affect_outcome
            self._write_record(
                root,
                record_id=campaign_id,
                kind="Assessment",
                payload=campaign,
                status="active",
                epistemic_kind="assessed",
            )
            return campaign
    def exercise_boundaries(self, round_index: int = 0) -> dict[str, Any]:
        """Exercise negative transfer, unavailable-world, and failed-publication paths."""
        if (
            isinstance(round_index, bool)
            or not isinstance(round_index, int)
            or round_index < 0
        ):
            raise OrganismError("round_index must be a nonnegative integer")
        campaign_id = f"{CAMPAIGN_PREFIX}{round_index:08d}"
        record_id = f"organism:boundary-assessment:{round_index:08d}"
        manifest = self._load_manifest()
        with self._open_residencies(include_members=False) as (root, _):
            prior = root._record(record_id)
            if prior is not None:
                return _plain(prior["payload"])
            campaign = root._record(campaign_id)
            if campaign is None:
                raise OrganismError("population round must complete before boundary exercise")
            campaign_payload = _plain(campaign["payload"])
            frontier = self._frontier(root)
            candidate = next(
                (
                    Construction.from_dict(item)
                    for item in frontier["entries"]
                    if item["candidate_id"] == campaign_payload["candidate_id"]
                ),
                None,
            )
            baseline = next(
                (
                    Construction.from_dict(item)
                    for item in frontier["entries"]
                    if item["candidate_id"] == "construction:baseline"
                ),
                None,
            )
            if candidate is None or baseline is None:
                raise OrganismError("boundary exercise cannot resolve campaign programs")
            scenario = self._scenario(round_index, "root", "negative-transfer")
            scenario["context_available"] = False
            negative_candidate = self._run_candidate(
                root,
                actor="root",
                candidate=candidate,
                scenario=scenario,
                split="negative-transfer-candidate",
                round_index=round_index,
                learning_mode="frozen-reporting",
            )
            negative_baseline = self._run_candidate(
                root,
                actor="root",
                candidate=baseline,
                scenario=scenario,
                split="negative-transfer-baseline",
                round_index=round_index,
                learning_mode="frozen-reporting",
            )
            negative_comparison = self._compare(
                negative_candidate,
                negative_baseline,
            )

            from cassi_research_worlds import PHYSICS_KIND, execute_work

            unavailable_request = {
                "kind": PHYSICS_KIND,
                "operation_id": (
                    f"organism:boundary:{round_index:08d}:unavailable-world"
                ),
                "cmd": "state",
                "fields": ["step", "t"],
                "host": "127.0.0.1",
                "port": 1,
                "timeout": 0.05,
            }
            unavailable_output = execute_work(
                unavailable_request,
                workspace=Path(manifest["workspace"]),
                artifact_home=(
                    self.home
                    / "world-artifacts"
                    / "boundary"
                    / f"{round_index:08d}"
                ),
            )
            unavailable_content = canonical_json_bytes(unavailable_output)
            unavailable_source = SourceInput(
                source_id=unavailable_request["operation_id"],
                content=unavailable_content,
                media_type="application/json",
                codec=CODEC_JSON,
                observed_timestamp=campaign_id,
                scope="research-organism:root",
                claim_category="world-availability",
                fidelity="exact-adapter-output",
                labels=("research-organism", "availability"),
            )
            unavailable_archive = root.owner.archive_source(
                operation_id=f"{unavailable_request['operation_id']}:archive",
                source=unavailable_source,
                context={"campaign_id": campaign_id},
                event_kind="research-world-availability",
            )

            pointer_before = self.publications.current()
            missing_path = (
                "CassiFI/__organism_missing_generation__.py"
                if (Path(manifest["workspace"]) / "CassiFI").is_dir()
                else "__organism_missing_generation__.py"
            )
            publication_error: str | None = None
            try:
                self.publications.publish(
                    workspace=Path(manifest["workspace"]),
                    source_paths=[
                        *manifest.get("source_paths", []),
                        missing_path,
                    ],
                    field_bundle=root.owner.export_bundle(),
                    field_state_sha256=root.owner.state.state_sha256,
                    campaign_id=campaign_id,
                    program_ids=[candidate.candidate_id],
                    method_state={"intent": "negative-publication-control"},
                    parent_generation=(
                        None
                        if pointer_before is None
                        else pointer_before["generation_id"]
                    ),
                )
            except OrganismError as exc:
                publication_error = str(exc)
            if publication_error is None:
                raise OrganismError("invalid source generation was unexpectedly published")
            pointer_after = self.publications.current()
            pointer_preserved = _digest(pointer_before) == _digest(pointer_after)
            if not pointer_preserved:
                raise OrganismError("failed publication moved the active generation")
            result = {
                "schema": "cassifi.research-organism-boundaries.v1",
                "campaign_id": campaign_id,
                "negative_transfer": {
                    "comparison": negative_comparison,
                    "status": (
                        "no-detected-gain"
                        if not negative_comparison["supported"]
                        else "unexpected-gain"
                    ),
                    "context_available": False,
                },
                "unavailable_world": {
                    "status": unavailable_output.get("status"),
                    "source_revision_id": unavailable_archive["source"][
                        "revision_id"
                    ],
                    "output_sha256": hashlib.sha256(
                        unavailable_content
                    ).hexdigest(),
                },
                "failed_publication": {
                    "status": "rejected",
                    "reason": publication_error,
                    "active_pointer_preserved": pointer_preserved,
                    "active_generation": (
                        None
                        if pointer_after is None
                        else pointer_after["generation_id"]
                    ),
                },
            }
            self._write_record(
                root,
                record_id=record_id,
                kind="Assessment",
                payload=result,
                epistemic_kind="assessed",
            )
            return result


    def _publish_locked(
        self,
        root: ResearchResidency,
        campaign: Mapping[str, Any],
    ) -> dict[str, Any]:
        manifest = self._load_manifest()
        current = self.publications.current()
        if current is not None and current.get("campaign_id") == campaign["campaign_id"]:
            return current
        bundle = root.owner.export_bundle()
        return self.publications.publish(
            workspace=Path(manifest["workspace"]),
            source_paths=manifest.get("source_paths", []),
            field_bundle=bundle,
            field_state_sha256=root.owner.state.state_sha256,
            campaign_id=str(campaign["campaign_id"]),
            program_ids=[str(campaign["candidate_id"])],
            method_state={
                "frontier_generation": self._frontier(root).get("method_generation", 0),
                "campaign_verdict": campaign.get("verdict"),
            },
            parent_generation=None if current is None else current["generation_id"],
        )

    def select_laboratory_candidate(
        self,
        *,
        campaign_id: str,
        laboratory_id: str,
        objective: str,
        candidates: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        """Let the root field choose from development-only laboratory evidence."""

        campaign_id = _identifier(campaign_id, "campaign_id")
        laboratory_id = _identifier(laboratory_id, "laboratory_id")
        objective = _text(objective, "objective", maximum=1024)
        normalized = [_plain(candidate) for candidate in candidates]
        if len(normalized) < 2 or len(normalized) > 32:
            raise OrganismError("laboratory selection requires 2..32 candidates")
        candidate_ids = [
            _identifier(candidate.get("candidate_id"), "candidate_id")
            for candidate in normalized
        ]
        if len(set(candidate_ids)) != len(candidate_ids):
            raise OrganismError("laboratory candidate identities must be unique")
        selection_record_id = (
            f"organism:lab:{campaign_id}:{laboratory_id}:selection"
        )
        prefix = f"organism:lab:{campaign_id}:{laboratory_id}:obligation:"
        with self._open_residencies(include_members=False) as (root, _):
            state_before = root.owner.state.state_sha256
            prior_selection = root._record(selection_record_id)
            if prior_selection is not None:
                selection = _plain(prior_selection["payload"])
                if (
                    selection.get("campaign_id") != campaign_id
                    or selection.get("laboratory_id") != laboratory_id
                    or selection.get("candidate_ids") != candidate_ids
                    or selection.get("candidate_id") not in candidate_ids
                    or selection.get("holdout_visible_during_selection") is not False
                ):
                    raise OrganismError(
                        "resident laboratory selection differs from replay request"
                    )
                selection["field_state_sha256_after"] = root.owner.state.state_sha256
                return selection
            for candidate_id, candidate in zip(candidate_ids, normalized, strict=True):
                program_id = f"organism:lab:{campaign_id}:{laboratory_id}:program:{candidate_id}"
                evidence_id = f"organism:lab:{campaign_id}:{laboratory_id}:evidence:{candidate_id}"
                self._write_record(
                    root,
                    record_id=evidence_id,
                    kind="Assessment",
                    payload={
                        "campaign_id": campaign_id,
                        "laboratory_id": laboratory_id,
                        "candidate_id": candidate_id,
                        "development_score": candidate.get("development_score"),
                        "development_cost": candidate.get("development_cost"),
                        "development_evidence": candidate.get("development_evidence"),
                        "holdout_visible": False,
                    },
                    epistemic_kind="assessed",
                )
                self._write_record(
                    root,
                    record_id=program_id,
                    kind="Program",
                    payload={
                        "campaign_id": campaign_id,
                        "laboratory_id": laboratory_id,
                        "candidate_id": candidate_id,
                        "objective": objective,
                        "evidence_id": evidence_id,
                    },
                    epistemic_kind="proposed",
                )
                self._write_record(
                    root,
                    record_id=prefix + candidate_id,
                    kind="Obligation",
                    payload={
                        "purpose": "laboratory-candidate-selection",
                        "campaign_id": campaign_id,
                        "laboratory_id": laboratory_id,
                        "candidate_id": candidate_id,
                        "summary": f"{laboratory_id}:{candidate_id}",
                        "status": "pending",
                        "program_id": program_id,
                        "priority": candidate.get("development_score"),
                        "expected_gain": {
                            "development_score": candidate.get("development_score"),
                            "development_cost": candidate.get("development_cost"),
                        },
                        "support_roots": [evidence_id],
                    },
                    status="pending",
                    epistemic_kind="proposed",
                )
            request = {
                "operation": "autonomous-agenda",
                "operation_id": f"organism:lab:{campaign_id}:{laboratory_id}:agenda:affect",
                "project_id": AFFECT_PROJECT_ID,
                "goal": {
                    "objective": objective,
                    "focus": "select a representation from development evidence before holdout disclosure",
                },
                "obligation_prefix": prefix,
                "max_items": len(normalized),
            }
            agenda = root.semantic(request)
            selected_item = agenda.get("selected")
            selected_ref = (
                selected_item.get("obligation")
                if isinstance(selected_item, Mapping)
                else None
            )
            selected_obligation = (
                selected_ref.get("id")
                if isinstance(selected_ref, Mapping)
                else None
            )
            if not isinstance(selected_obligation, str) or not selected_obligation.startswith(prefix):
                raise OrganismError("root field did not select a laboratory candidate")
            selected_id = selected_obligation[len(prefix):]
            if selected_id not in candidate_ids:
                raise OrganismError("root field selected an unknown laboratory candidate")
            for candidate_id in candidate_ids:
                self._write_record(
                    root,
                    record_id=prefix + candidate_id,
                    kind="Obligation",
                    payload={
                        "purpose": "laboratory-candidate-selection",
                        "campaign_id": campaign_id,
                        "laboratory_id": laboratory_id,
                        "candidate_id": candidate_id,
                        "summary": f"{laboratory_id}:{candidate_id}",
                        "status": "resolved",
                        "resolution": (
                            "selected-before-holdout"
                            if candidate_id == selected_id
                            else "not-selected-before-holdout"
                        ),
                    },
                    status="resolved",
                    epistemic_kind="derived",
                )
            selection = {
                "campaign_id": campaign_id,
                "laboratory_id": laboratory_id,
                "candidate_id": selected_id,
                "selection_record_id": selection_record_id,
                "candidate_ids": candidate_ids,
                "holdout_visible_during_selection": False,
                "agenda_event": agenda.get("event"),
                "field_state_sha256_before": state_before,
                "field_state_sha256_after": root.owner.state.state_sha256,
            }
            self._write_record(
                root,
                record_id=selection_record_id,
                kind="Assessment",
                payload=selection,
                epistemic_kind="assessed",
            )
            selection["field_state_sha256_after"] = root.owner.state.state_sha256
            return selection


    def admit_laboratory_outcome(
        self,
        *,
        campaign_id: str,
        laboratory_id: str,
        candidate_id: str,
        selected_result: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Persist a revealed holdout outcome in the canonical root field."""

        campaign_id = _identifier(campaign_id, "campaign_id")
        laboratory_id = _identifier(laboratory_id, "laboratory_id")
        candidate_id = _identifier(candidate_id, "candidate_id")
        result = _plain(selected_result)
        result_sha256 = _digest(result)
        record_id = f"organism:lab:{campaign_id}:{laboratory_id}:outcome"
        with self._open_residencies(include_members=False) as (root, _):
            state_before = root.owner.state.state_sha256
            payload = {
                "campaign_id": campaign_id,
                "laboratory_id": laboratory_id,
                "candidate_id": candidate_id,
                "selected_result": result,
                "selected_result_sha256": result_sha256,
                "holdout_revealed_after_selection": True,
            }
            self._write_record(
                root,
                record_id=record_id,
                kind="Assessment",
                payload=payload,
                epistemic_kind="assessed",
            )
            return {
                "record_id": record_id,
                "selected_result_sha256": result_sha256,
                "field_state_sha256_before": state_before,
                "field_state_sha256_after": root.owner.state.state_sha256,
            }

    @staticmethod
    def _normalize_experience_lessons(
        lessons: Sequence[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        rows = [_plain(lesson) for lesson in lessons]
        if not 2 <= len(rows) <= 16:
            raise OrganismError("hive experience requires 2..16 candidate lessons")
        identities: set[str] = set()
        normalized: list[dict[str, Any]] = []
        for row in rows:
            lesson_id = _identifier(row.get("lesson_id"), "lesson_id")
            if lesson_id in identities:
                raise OrganismError("hive lesson identities must be unique")
            identities.add(lesson_id)
            statement = _text(row.get("statement"), "lesson statement")
            score = row.get("development_score")
            if (
                isinstance(score, bool)
                or not isinstance(score, (int, float))
                or not math.isfinite(float(score))
                or not 0.0 <= float(score) <= 1.0
            ):
                raise OrganismError(
                    "lesson development_score must be finite and in [0, 1]"
                )
            cost = row.get("development_cost", 1.0)
            if (
                isinstance(cost, bool)
                or not isinstance(cost, (int, float))
                or not math.isfinite(float(cost))
                or float(cost) < 0.0
            ):
                raise OrganismError(
                    "lesson development_cost must be finite and nonnegative"
                )
            evidence = row.get("development_evidence", {})
            if not isinstance(evidence, Mapping):
                raise OrganismError("lesson development_evidence must be an object")
            normalized.append(
                {
                    "candidate_id": lesson_id,
                    "lesson_id": lesson_id,
                    "statement": statement,
                    "development_score": float(score),
                    "development_cost": float(cost),
                    "development_evidence": _plain(evidence),
                }
            )
        if len(canonical_json_bytes(normalized)) > 65_536:
            raise OrganismError("candidate lessons exceed the hive evidence bound")
        return normalized

    @staticmethod
    def _normalize_member_experience(
        result: Mapping[str, Any],
        *,
        lesson_ids: Sequence[str],
    ) -> dict[str, Any]:
        if not isinstance(result, Mapping):
            raise OrganismError("member experience result must be an object")
        normalized = _plain(result)
        if len(canonical_json_bytes(normalized)) > _MAX_RESULT_BYTES:
            raise OrganismError("member experience result exceeds its byte bound")
        if not isinstance(normalized.get("controls_passed"), bool):
            raise OrganismError(
                "member experience result must declare controls_passed"
            )
        raw_scores = normalized.get("lesson_scores")
        if not isinstance(raw_scores, Mapping) or set(raw_scores) != set(lesson_ids):
            raise OrganismError(
                "member lesson_scores must cover every candidate lesson exactly"
            )
        scores: dict[str, float] = {}
        for lesson_id in lesson_ids:
            value = raw_scores[lesson_id]
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or not 0.0 <= float(value) <= 1.0
            ):
                raise OrganismError(
                    "member lesson scores must be finite and in [0, 1]"
                )
            scores[lesson_id] = float(value)
        normalized["lesson_scores"] = scores
        return normalized

    def _archive_experience_result(
        self,
        residency: ResearchResidency,
        *,
        experiment_id: str,
        actor: str,
        result: Mapping[str, Any],
    ) -> dict[str, Any]:
        token = _digest(
            {"actor": actor, "experiment_id": experiment_id}
        )[:32]
        content = canonical_json_bytes(result)
        source = SourceInput(
            source_id=f"organism:experience:{token}:source",
            content=content,
            media_type="application/json",
            codec=CODEC_JSON,
            observed_timestamp=experiment_id,
            scope=f"research-organism:experience:{actor}",
            claim_category="hive-experiment-evidence",
            fidelity="exact-observed-bytes",
            labels=("research-organism", "hive-experience", actor),
        )
        archived = residency.owner.archive_source(
            operation_id=f"organism:experience:{token}:archive",
            source=source,
            context={
                "actor": actor,
                "experiment_id": experiment_id,
                "result_sha256": hashlib.sha256(content).hexdigest(),
            },
            epistemic_type="asserted",
            event_kind="hive-experiment-evidence",
        )
        return {
            "revision_id": str(archived["source"]["revision_id"]),
            "transition": _plain(archived),
        }

    def _select_member_experience_lesson(
        self,
        residency: ResearchResidency,
        *,
        experiment_id: str,
        member_id: str,
        objective: str,
        lessons: Sequence[Mapping[str, Any]],
        result: Mapping[str, Any],
        source_revision_id: str,
    ) -> dict[str, Any]:
        lesson_ids = [str(lesson["lesson_id"]) for lesson in lessons]
        token = _digest(
            {"experiment_id": experiment_id, "member_id": member_id}
        )[:24]
        prefix = f"organism:experience:{token}:obligation:"
        selection_id = f"organism:experience:{token}:selection"
        prior = residency._record(selection_id)
        if prior is not None:
            selection = _plain(prior["payload"])
            if (
                selection.get("experiment_id") != experiment_id
                or selection.get("member_id") != member_id
                or selection.get("lesson_ids") != lesson_ids
                or selection.get("lesson_id") not in lesson_ids
            ):
                raise OrganismError(
                    "member experience selection differs from replay request"
                )
            return selection

        state_before = residency.owner.state.state_sha256
        scores = result["lesson_scores"]
        for lesson in lessons:
            lesson_id = str(lesson["lesson_id"])
            evidence_id = f"organism:experience:{token}:evidence:{lesson_id}"
            self._write_record(
                residency,
                record_id=evidence_id,
                kind="Assessment",
                payload={
                    "schema": EXPERIENCE_SCHEMA,
                    "experiment_id": experiment_id,
                    "member_id": member_id,
                    "lesson_id": lesson_id,
                    "lesson_score": scores[lesson_id],
                    "controls_passed": result["controls_passed"],
                    "source_revision_id": source_revision_id,
                },
                epistemic_kind="assessed",
            )
            self._write_record(
                residency,
                record_id=prefix + lesson_id,
                kind="Obligation",
                payload={
                    "purpose": "independent-hive-experience-challenge",
                    "experiment_id": experiment_id,
                    "member_id": member_id,
                    "lesson_id": lesson_id,
                    "summary": lesson["statement"],
                    "status": "pending",
                    "priority": scores[lesson_id],
                    "expected_gain": {
                        "independent_score": scores[lesson_id],
                        "controls_passed": result["controls_passed"],
                    },
                    "support_roots": [evidence_id, source_revision_id],
                },
                status="pending",
                epistemic_kind="proposed",
            )
        agenda = residency.semantic(
            {
                "operation": "autonomous-agenda",
                "operation_id": f"organism:experience:{token}:agenda",
                "project_id": AFFECT_PROJECT_ID,
                "goal": {
                    "objective": objective,
                    "focus": "independently challenge a root-field lesson",
                },
                "obligation_prefix": prefix,
                "max_items": len(lessons),
            }
        )
        selected = agenda.get("selected")
        selected_ref = (
            selected.get("obligation")
            if isinstance(selected, Mapping)
            else None
        )
        selected_obligation = (
            selected_ref.get("id")
            if isinstance(selected_ref, Mapping)
            else None
        )
        if (
            not isinstance(selected_obligation, str)
            or not selected_obligation.startswith(prefix)
        ):
            raise OrganismError("member field did not select an experience lesson")
        selected_lesson = selected_obligation[len(prefix):]
        if selected_lesson not in lesson_ids:
            raise OrganismError("member field selected an unknown experience lesson")
        for lesson_id in lesson_ids:
            self._write_record(
                residency,
                record_id=prefix + lesson_id,
                kind="Obligation",
                payload={
                    "purpose": "independent-hive-experience-challenge",
                    "experiment_id": experiment_id,
                    "member_id": member_id,
                    "lesson_id": lesson_id,
                    "status": "resolved",
                    "resolution": (
                        "independently-selected"
                        if lesson_id == selected_lesson
                        else "independently-not-selected"
                    ),
                },
                status="resolved",
                epistemic_kind="derived",
            )
        selection = {
            "schema": "cassifi.research-organism-member-selection.v1",
            "experiment_id": experiment_id,
            "member_id": member_id,
            "lesson_id": selected_lesson,
            "lesson_ids": lesson_ids,
            "agenda_event": agenda.get("event"),
            "source_revision_id": source_revision_id,
            "field_state_sha256_before": state_before,
            "field_state_sha256_after": residency.owner.state.state_sha256,
        }
        self._write_record(
            residency,
            record_id=selection_id,
            kind="Assessment",
            payload=selection,
            epistemic_kind="assessed",
        )
        selection["field_state_sha256_after"] = (
            residency.owner.state.state_sha256
        )
        return selection

    @staticmethod
    def _sync_collective(
        residents: Mapping[str, ResearchResidency],
    ) -> dict[str, Any]:
        reports: dict[str, Any] = {}
        for resident_id, residency in residents.items():
            report = residency.session.sync()
            if report.blocked or report.errors:
                raise OrganismError(
                    f"hive synchronization failed for {resident_id}"
                )
            reports[resident_id] = report.as_dict()
        return reports

    def assimilate_experiment(
        self,
        *,
        experiment_id: str,
        laboratory_id: str,
        objective: str,
        root_result: Mapping[str, Any],
        lessons: Sequence[Mapping[str, Any]],
        member_results: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any]:
        """Turn one experiment into selected, challenged, adopted hive knowledge.

        The root and every member retain their own field state. The root selects
        one candidate lesson from its evidence; each member independently
        selects from its own evidence; only a supported lesson is promoted as a
        real ``KnowledgeBundle`` and adopted through ``HiveField``.
        """

        experiment_id = _identifier(experiment_id, "experiment_id")
        laboratory_id = _identifier(laboratory_id, "laboratory_id")
        objective = _text(objective, "objective", maximum=1024)
        normalized_lessons = self._normalize_experience_lessons(lessons)
        lesson_ids = [str(lesson["lesson_id"]) for lesson in normalized_lessons]
        normalized_root = _plain(root_result)
        if len(canonical_json_bytes(normalized_root)) > _MAX_RESULT_BYTES:
            raise OrganismError("root experience result exceeds its byte bound")
        manifest = self._load_manifest()
        expected_members = tuple(str(item) for item in manifest["member_ids"])
        if set(member_results) != set(expected_members):
            raise OrganismError(
                "hive experience requires one independent result from every member"
            )
        normalized_members = {
            member_id: self._normalize_member_experience(
                member_results[member_id],
                lesson_ids=lesson_ids,
            )
            for member_id in expected_members
        }
        input_document = {
            "experiment_id": experiment_id,
            "laboratory_id": laboratory_id,
            "objective": objective,
            "root_result": normalized_root,
            "lessons": normalized_lessons,
            "member_results": normalized_members,
        }
        input_sha256 = _digest(input_document)
        receipt_path = (
            self.home
            / "experiences"
            / f"{_digest(experiment_id)[:32]}.json"
        )
        if receipt_path.exists():
            prior = _read_json(receipt_path)
            if (
                prior.get("schema") != EXPERIENCE_RECEIPT_SCHEMA
                or prior.get("input_sha256") != input_sha256
            ):
                raise OrganismError(
                    "existing hive experience differs from replay request"
                )
            return prior

        selection = self.select_laboratory_candidate(
            campaign_id=experiment_id,
            laboratory_id=laboratory_id,
            objective=objective,
            candidates=normalized_lessons,
        )
        selected_lesson_id = str(selection["candidate_id"])
        selected_lesson = next(
            lesson
            for lesson in normalized_lessons
            if lesson["lesson_id"] == selected_lesson_id
        )
        with self._open_residencies(include_members=True) as (root, members):
            initial_sync = self._sync_collective(
                {"root": root, **members}
            )
            root_archive = self._archive_experience_result(
                root,
                experiment_id=experiment_id,
                actor="root",
                result=normalized_root,
            )
            root_revision = str(root_archive["revision_id"])
            lesson_payload = {
                "schema": "cassifi.research-organism-learned-experience.v1",
                "experiment_id": experiment_id,
                "laboratory_id": laboratory_id,
                "objective": objective,
                "lesson": selected_lesson,
                "root_result_sha256": _digest(normalized_root),
                "source_revision_id": root_revision,
                "selection_event": selection.get("agenda_event"),
            }
            program_id = "hive-experience-" + _digest(lesson_payload)[:48]
            program = FieldProgram(
                program_id=program_id,
                version=1,
                roles=(),
                steps=(
                    PrimitiveStep(
                        operation="constant",
                        output="lesson",
                        literal=lesson_payload,
                    ),
                ),
                outputs=("lesson",),
                prefix_code_bits=max(
                    1, len(canonical_json_bytes(lesson_payload)) * 8
                ),
            )
            existing_capsules = [
                capsule
                for capsule in root.session.hive.list_capsules()
                if capsule.candidate.kind == "field-program"
                and isinstance(capsule.candidate.object.get("program"), Mapping)
                and capsule.candidate.object["program"].get("program_id")
                == program_id
            ]
            if len(existing_capsules) > 1:
                raise OrganismError(
                    "hive experience has multiple source capsules"
                )
            if existing_capsules:
                capsule = existing_capsules[0]
            else:
                capsule = root.session.publish_experience(
                    transition=root_archive["transition"],
                    task_id=experiment_id,
                    context={
                        "domain": laboratory_id,
                        "experiment_id": experiment_id,
                        "objective": objective,
                        "source_revision_id": root_revision,
                    },
                    action={
                        "operation": "configure-program",
                        "program_id": program_id,
                    },
                    prediction={"lesson_id": selected_lesson_id},
                    outcome={
                        "lesson_id": selected_lesson_id,
                        "result_sha256": _digest(normalized_root),
                    },
                    candidate=ExperienceCandidate(
                        kind="field-program",
                        object={
                            "portable_transfer": True,
                            "program": program.as_dict(),
                        },
                        operation_plan=(
                            {
                                "operation": "configure-program",
                                "program": program.as_dict(),
                            },
                        ),
                        guards=(),
                        dependencies=(),
                    ),
                    evidence=ExperienceEvidence(
                        support_event_ids=(_digest(normalized_root),),
                        assessment_ids=(_digest(selection),),
                        held_out_results=(
                            {
                                "lesson_id": selected_lesson_id,
                                "development_evidence": selected_lesson[
                                    "development_evidence"
                                ],
                                "result_sha256": _digest(normalized_root),
                            },
                        ),
                        counterexamples=tuple(
                            {
                                "lesson_id": lesson["lesson_id"],
                                "development_score": lesson[
                                    "development_score"
                                ],
                            }
                            for lesson in normalized_lessons
                            if lesson["lesson_id"] != selected_lesson_id
                        ),
                        derivation_roots=(root_revision,),
                    ),
                )

            coordinator = HiveCoordinator(
                root.session.hive,
                leader_instance_id=root.session.identity.instance_id,
            )
            groups = [
                group
                for group in coordinator.groups()
                if any(
                    item.object_id == capsule.object_id
                    for item in group.capsules
                )
            ]
            if len(groups) != 1:
                raise OrganismError(
                    "published experience candidate group is unavailable"
                )
            candidate_group = groups[0]
            member_reviews: list[dict[str, Any]] = []
            review_values: list[Review] = []
            for member_id in expected_members:
                member = members[member_id]
                member_result = normalized_members[member_id]
                member_archive = self._archive_experience_result(
                    member,
                    experiment_id=experiment_id,
                    actor=member_id,
                    result=member_result,
                )
                member_revision = str(member_archive["revision_id"])
                member_selection = self._select_member_experience_lesson(
                    member,
                    experiment_id=experiment_id,
                    member_id=member_id,
                    objective=objective,
                    lessons=normalized_lessons,
                    result=member_result,
                    source_revision_id=member_revision,
                )
                if not member_result["controls_passed"]:
                    review_result = "inconclusive"
                elif member_selection["lesson_id"] == selected_lesson_id:
                    review_result = "supports"
                else:
                    review_result = "refutes"
                evidence_ids = tuple(
                    dict.fromkeys(
                        (
                            _digest(member_result),
                            member_revision,
                            _digest(member_selection),
                        )
                    )
                )
                review = Review(
                    reviewer_instance_id=member.session.identity.instance_id,
                    review_type="independent-reproduction",
                    result=review_result,
                    evidence_ids=evidence_ids,
                )
                coordinator.review(
                    review,
                    candidate_id=candidate_group.candidate_id,
                    source_experience_ids=(capsule.object_id,),
                )
                review_values.append(review)
                member_reviews.append(
                    {
                        "member_id": member_id,
                        "hive_instance_id": member.session.identity.instance_id,
                        "result_sha256": _digest(member_result),
                        "source_revision_id": member_revision,
                        "selection": member_selection,
                        "review": review.as_dict(),
                    }
                )

            quorum = min(2, len(expected_members))
            support_count = sum(
                review.result == "supports"
                for review in review_values
            )
            existing_bundle = next(
                (
                    bundle
                    for bundle in root.session.hive.list_bundles()
                    if capsule.object_id in bundle.source_experience_ids
                ),
                None,
            )
            bundle = existing_bundle
            if bundle is None and support_count >= quorum:
                bundle = coordinator.promote(
                    candidate_id=candidate_group.candidate_id,
                    reviews=review_values,
                    minimum_support_reviews=quorum,
                )

            adoptions: dict[str, Any] = {}
            if bundle is not None:
                for resident_id, residency in {
                    "root": root,
                    **members,
                }.items():
                    adoption = residency.session.adopt(
                        bundle_ids=(bundle.object_id,)
                    )
                    if adoption.blocked or adoption.errors:
                        raise OrganismError(
                            f"hive experience adoption failed for {resident_id}"
                        )
                    learned = next(
                        (
                            item
                            for item in residency.owner.state.programs
                            if item.program_id == program_id
                        ),
                        None,
                    )
                    if (
                        learned is None
                        or learned.as_dict() != program.as_dict()
                    ):
                        raise OrganismError(
                            f"hive lesson bytes differ for {resident_id}"
                        )
                    adoptions[resident_id] = {
                        "sync": adoption.as_dict(),
                        "field_state_sha256": (
                            residency.owner.state.state_sha256
                        ),
                        "program_sha256": _digest(learned.as_dict()),
                    }

            status = "promoted" if bundle is not None else "contested"
            population_record = {
                "schema": EXPERIENCE_SCHEMA,
                "experiment_id": experiment_id,
                "laboratory_id": laboratory_id,
                "selected_lesson_id": selected_lesson_id,
                "capsule_id": capsule.object_id,
                "bundle_id": (
                    None if bundle is None else bundle.object_id
                ),
                "status": status,
                "quorum": quorum,
                "support_count": support_count,
                "member_reviews": member_reviews,
            }
            self._write_record(
                root,
                record_id=(
                    "organism:experience:"
                    + _digest(experiment_id)[:24]
                    + ":population"
                ),
                kind="Assessment",
                payload=_foreign_source_view(population_record),
                epistemic_kind="assessed",
            )
            receipt = {
                "schema": EXPERIENCE_RECEIPT_SCHEMA,
                "experiment_id": experiment_id,
                "laboratory_id": laboratory_id,
                "objective": objective,
                "input_sha256": input_sha256,
                "status": status,
                "selection": selection,
                "selected_lesson": selected_lesson,
                "root_result_sha256": _digest(normalized_root),
                "root_source_revision_id": root_revision,
                "program_id": program_id,
                "program_sha256": _digest(program.as_dict()),
                "capsule_id": capsule.object_id,
                "candidate_group_id": candidate_group.candidate_id,
                "bundle_id": (
                    None if bundle is None else bundle.object_id
                ),
                "quorum": quorum,
                "support_count": support_count,
                "reviews": member_reviews,
                "initial_sync": initial_sync,

                "adoptions": adoptions,
                "hive_generation": root.session.hive.current_generation,
                "collective_hive_home": str(self.collective_hive_home),
                "root_field_state_sha256": root.owner.state.state_sha256,
            }
            _atomic_json(receipt_path, receipt, immutable=True)
            return receipt


    def allocate_resources(
        self,
        allocation_id: str,
        *,
        member_id: str,
        objective: Mapping[str, Any],
        budgets: Mapping[str, int],
        mission_account_id: str = "mission:research-organism",
        reservation_id: str | None = None,
        work_order_id: str | None = None,
        parent_allocation_id: str | None = None,
        predicted_cost: Mapping[str, int] | None = None,
        scientific_relevance: Mapping[str, Any] | None = None,
        lease_expires_ns: int | None = None,
    ) -> dict[str, Any]:
        """Persist predicted field priorities bound to a host resource reservation."""
        allocation_id = _identifier(allocation_id, "allocation_id")
        member_id = _identifier(member_id, "member_id")
        mission_account_id = _identifier(mission_account_id, "mission_account_id")
        reservation_id = _identifier(
            allocation_id if reservation_id is None else reservation_id,
            "reservation_id",
        )
        work_order_id = _identifier(
            f"member-work:{allocation_id}" if work_order_id is None else work_order_id,
            "work_order_id",
        )
        if parent_allocation_id is not None:
            parent_allocation_id = _identifier(
                parent_allocation_id, "parent_allocation_id",
            )
        if (
            lease_expires_ns is not None
            and (
                isinstance(lease_expires_ns, bool)
                or not isinstance(lease_expires_ns, int)
                or lease_expires_ns < 0
            )
        ):
            raise OrganismError("resource lease expiry must be a nonnegative integer")
        if member_id not in self._active_member_ids():
            raise OrganismError("resource allocation target is not an active member")
        normalized_budgets: dict[str, int] = {}
        for name, value in dict(budgets).items():
            key = _identifier(name, "resource budget")
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise OrganismError("resource budgets must be nonnegative integers")
            normalized_budgets[key] = value
        if not normalized_budgets or normalized_budgets.get("resident_steps", 0) < 1:
            raise OrganismError("resource allocation requires resident_steps")
        normalized_prediction = {
            _identifier(name, "predicted resource"): value
            for name, value in dict(
                normalized_budgets if predicted_cost is None else predicted_cost
            ).items()
            if not isinstance(value, bool) and isinstance(value, int) and value >= 0
        }
        if len(normalized_prediction) != len(
            normalized_budgets if predicted_cost is None else predicted_cost
        ):
            raise OrganismError("predicted costs must be nonnegative integers")
        payload = {
            "schema": RESOURCE_ALLOCATION_SCHEMA,
            "allocation_id": allocation_id,
            "mission_account_id": mission_account_id,
            "reservation_id": reservation_id,
            "work_order_id": work_order_id,
            "parent_allocation_id": parent_allocation_id,
            "member_id": member_id,
            "objective": _plain(objective),
            "scientific_relevance": _plain(scientific_relevance or {}),
            "predicted_cost": normalized_prediction,
            "budgets": normalized_budgets,
            "consumed": {name: 0 for name in normalized_budgets},
            "remaining": dict(normalized_budgets),
            "lease": {
                "expires_ns": lease_expires_ns,
                "fence": 1,
                "state": "open",
            },
            "settlement": {
                "status": "unsettled",
                "settlement_id": None,
                "measured_consumption": {},
            },
            "state": "active",
            "generation": 1,
        }
        with self._open_residencies(include_members=True) as (root, members):
            record_id = f"organism:resource:{allocation_id}"
            if root._record(record_id) is not None:
                raise OrganismError("resource allocation identity already exists")
            self._write_record(
                root, record_id=record_id, kind="Value", payload=payload,
                epistemic_kind="asserted",
            )
            self._write_record(
                members[member_id],
                record_id=record_id,
                kind="Value",
                payload={**payload, "authority": "root-allocation"},
                epistemic_kind="attributed",
            )
            return _plain(payload)

    def advance_member(
        self, member_id: str, allocation_id: str, *, steps: int = 1,
    ) -> dict[str, Any]:
        """Advance one member only when a live allocation can pay for the work."""
        member_id = _identifier(member_id, "member_id")
        allocation_id = _identifier(allocation_id, "allocation_id")
        if isinstance(steps, bool) or not isinstance(steps, int) or not 1 <= steps <= 256:
            raise OrganismError("member steps must be in [1, 256]")
        with self._open_residencies(include_members=True) as (root, members):
            member = members.get(member_id)
            if member is None:
                raise OrganismError("scheduled member is not active")
            control = root._record(f"organism:member-control:{member_id}")
            if (
                control is not None
                and control["payload"].get("state") == "paused"
            ):
                raise OrganismError("scheduled member is paused")
            record_id = f"organism:resource:{allocation_id}"
            record = root._record(record_id)
            if record is None:
                raise OrganismError("resource allocation is unavailable")
            allocation = _plain(record["payload"])
            if (
                allocation.get("schema") != RESOURCE_ALLOCATION_SCHEMA
                or allocation.get("state") != "active"
                or allocation.get("lease", {}).get("state") != "open"
                or allocation.get("settlement", {}).get("status") != "unsettled"
            ):
                raise OrganismError("resource allocation cannot authorize this member")
            remaining = int(allocation["remaining"].get("resident_steps", 0))
            if remaining < steps:
                raise OrganismError("resource allocation is exhausted")
            before = member.owner.state.state_sha256
            result = member.inspect()
            for _ in range(steps):
                result = member.advance()
            after = member.owner.state.state_sha256
            allocation["consumed"]["resident_steps"] += steps
            allocation["remaining"]["resident_steps"] -= steps
            allocation["generation"] += 1
            if allocation["remaining"]["resident_steps"] == 0:
                allocation["state"] = "exhausted"
            self._write_record(
                root, record_id=record_id, kind="Value", payload=allocation,
            )
            self._write_record(
                member,
                record_id=record_id,
                kind="Value",
                payload={**allocation, "authority": "root-allocation"},
                epistemic_kind="attributed",
            )
            execution = {
                "schema": "cassifi.research-organism-member-execution.v1",
                "allocation_id": allocation_id,
                "member_id": member_id,
                "steps": steps,
                "field_state_sha256_before": before,
                "field_state_sha256_after": after,
                "reservation_id": allocation["reservation_id"],
                "mission_account_id": allocation["mission_account_id"],
                "lease_fence": allocation["lease"]["fence"],
                "resident": result,
            }
            self._write_record(
                member,
                record_id=(
                    f"organism:member-execution:{allocation_id}:"
                    f"{allocation['generation']:08d}"
                ),
                kind="Event",
                payload=execution,
                epistemic_kind="observed",
            )
            return execution

    def request_collaboration(self, request: CollaborationRequest) -> str:
        with self._open_residencies(include_members=False) as (root, _):
            document_id = root.session.collective.record_collaboration_request(request)
            self._write_record(
                root,
                record_id=f"organism:collaboration-request:{request.request_id}",
                kind="Obligation",
                payload={
                    "schema": COLLABORATION_REQUEST_SCHEMA,
                    "document_id": document_id,
                    **request.as_dict(),
                    "state": "pending",
                },
                epistemic_kind="asserted",
            )
            return document_id
    def control_member(
        self,
        control_id: str,
        *,
        member_id: str,
        action: str,
        reason: str,
    ) -> dict[str, Any]:
        """Pause or reopen a member without replacing its field lifetime."""
        control_id = _identifier(control_id, "member control_id")
        member_id = _identifier(member_id, "member_id")
        if action not in {"pause", "resume"}:
            raise OrganismError("member control action must be pause or resume")
        if member_id not in self._active_member_ids():
            raise OrganismError("member control target is not active")
        reason = _text(reason, "member control reason", maximum=1024)
        state = "paused" if action == "pause" else "active"
        payload = {
            "schema": "cassifi.research-organism-member-control.v1",
            "control_id": control_id,
            "member_id": member_id,
            "action": action,
            "state": state,
            "reason": reason,
        }
        with self._open_residencies(include_members=True) as (root, members):
            event_id = f"organism:member-control-event:{control_id}"
            prior = root._record(event_id)
            if prior is not None:
                if prior["payload"] != payload:
                    raise OrganismError("member control identity was reused")
                return _plain(payload)
            self._write_record(
                root, record_id=event_id, kind="Event", payload=payload,
                epistemic_kind="asserted",
            )
            state_id = f"organism:member-control:{member_id}"
            self._write_record(
                root, record_id=state_id, kind="Value", payload=payload,
                epistemic_kind="asserted",
            )
            self._write_record(
                members[member_id], record_id=state_id, kind="Value",
                payload={**payload, "authority": "root-control"},
                epistemic_kind="attributed",
            )
            return _plain(payload)

    def settle_resource_allocation(
        self,
        allocation_id: str,
        settlement_id: str,
        *,
        measured_consumption: Mapping[str, int],
        status: str,
    ) -> dict[str, Any]:
        """Settle one reservation exactly once while retaining all spent work."""
        allocation_id = _identifier(allocation_id, "allocation_id")
        settlement_id = _identifier(settlement_id, "settlement_id")
        if status not in {"completed", "released", "failed", "cancelled"}:
            raise OrganismError("resource settlement status is invalid")
        measured: dict[str, int] = {}
        for name, value in dict(measured_consumption).items():
            key = _identifier(name, "measured resource")
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise OrganismError("measured consumption must be nonnegative integers")
            measured[key] = value
        with self._open_residencies(include_members=True) as (root, members):
            record_id = f"organism:resource:{allocation_id}"
            record = root._record(record_id)
            if record is None:
                raise OrganismError("resource allocation is unavailable")
            allocation = _plain(record["payload"])
            prior = allocation.get("settlement", {})
            if prior.get("status") != "unsettled":
                if (
                    prior.get("settlement_id") == settlement_id
                    and prior.get("measured_consumption") == measured
                    and allocation.get("state") == status
                ):
                    return allocation
                raise OrganismError("resource allocation is already settled")
            allocation["settlement"] = {
                "status": status,
                "settlement_id": settlement_id,
                "measured_consumption": measured,
            }
            allocation["lease"] = {
                **allocation["lease"],
                "state": "closed",
                "fence": int(allocation["lease"]["fence"]) + 1,
            }
            allocation["state"] = status
            allocation["generation"] = int(allocation["generation"]) + 1
            self._write_record(
                root, record_id=record_id, kind="Value", payload=allocation,
            )
            member_id = str(allocation["member_id"])
            if member_id in members:
                self._write_record(
                    members[member_id], record_id=record_id, kind="Value",
                    payload={**allocation, "authority": "root-allocation"},
                    epistemic_kind="attributed",
                )
            self._write_record(
                root,
                record_id=f"organism:resource-settlement:{settlement_id}",
                kind="Event",
                payload={
                    "schema": "cassifi.research-organism-resource-settlement.v1",
                    "allocation_id": allocation_id,
                    "reservation_id": allocation["reservation_id"],
                    "mission_account_id": allocation["mission_account_id"],
                    **allocation["settlement"],
                    "lease_fence": allocation["lease"]["fence"],
                },
                epistemic_kind="observed",
            )
            return allocation


    def assign_collaboration(self, assignment: CollaborationAssignment) -> str:
        if assignment.assignee_instance_id not in self._active_member_ids():
            raise OrganismError("collaboration assignee is not an active member")
        with self._open_residencies(include_members=True) as (root, members):
            allocation = root._record(
                f"organism:resource:{assignment.resource_allocation_id}"
            )
            if (
                allocation is None
                or allocation["payload"].get("member_id") != assignment.assignee_instance_id
                or allocation["payload"].get("state") != "active"
            ):
                raise OrganismError("collaboration assignment lacks active resources")
            document_id = root.session.collective.record_collaboration_assignment(
                assignment
            )
            self._write_record(
                members[assignment.assignee_instance_id],
                record_id=f"organism:collaboration-assignment:{assignment.assignment_id}",
                kind="Obligation",
                payload={
                    "schema": COLLABORATION_ASSIGNMENT_SCHEMA,
                    "document_id": document_id,
                    **assignment.as_dict(),
                    "state": "pending",
                },
                epistemic_kind="attributed",
            )
            return document_id

    def record_collaboration_response(
        self, response: CollaborationResponse,
    ) -> str:
        if response.responder_instance_id not in self._active_member_ids():
            raise OrganismError("collaboration responder is not an active member")
        with self._open_residencies(include_members=True) as (root, members):
            document_id = root.session.collective.record_collaboration_response(
                response
            )
            self._write_record(
                members[response.responder_instance_id],
                record_id=f"organism:collaboration-response:{response.response_id}",
                kind="Assessment",
                payload={
                    "schema": COLLABORATION_RESPONSE_SCHEMA,
                    "document_id": document_id,
                    **response.as_dict(),
                },
                epistemic_kind="assessed",
            )
            self._write_record(
                root,
                record_id=f"organism:attributed-response:{response.response_id}",
                kind="Assessment",
                payload={
                    "schema": COLLABORATION_RESPONSE_SCHEMA,
                    "document_id": document_id,
                    "reporter_instance_id": response.responder_instance_id,
                    "report": response.as_dict(),
                },
                epistemic_kind="attributed",
            )
            root.semantic({
                "operation": "match-relevance",
                "operation_id": (
                    "organism:collaboration-response:memory:"
                    f"{response.response_id}"
                ),
                "event_id": f"hive-response:{response.response_id}",
                "context": {
                    "assignment_id": response.assignment_id,
                    "responder_instance_id": response.responder_instance_id,
                    "response_status": response.status,
                    "representation": response.representation,
                    "attribution": "hive-member",
                },
                "maximum": 32,
            })
        self._reconcile_collective_capability_dispatches(
            response_id=response.response_id,
        )
        return document_id

    def record_affect_report(self, report: AffectReport) -> dict[str, Any]:
        """Archive, attribute, and locally appraise one cooperative-affect report."""
        if not isinstance(report, AffectReport):
            raise OrganismError("affect report has the wrong type")
        active = set(self._active_member_ids())
        if report.sender_instance_id not in active | {"root"}:
            raise OrganismError("affect report sender is not part of the active organism")
        if report.recipient_scope not in active | {"root"}:
            raise OrganismError("affect report recipient is not part of the active organism")
        if report.sender_instance_id == report.recipient_scope:
            raise OrganismError("cooperative affect report must cross an owner boundary")
        with self._open_residencies(include_members=True) as (root, members):
            document_id = root.session.collective.record_affect_report(report)
            recipient = (
                root if report.recipient_scope == "root"
                else members[report.recipient_scope]
            )
            record_id = f"event:affect-report:{sha256_value(report.message_id)}"
            payload = {
                "schema": AFFECT_REPORT_SCHEMA,
                **report.as_dict(),
                "transport": {
                    "document_id": document_id,
                    "sender_instance_id": report.sender_instance_id,
                    "recipient_scope": report.recipient_scope,
                },
                "support_authority": "attributed-cooperation-only",
            }
            self._write_record(
                recipient,
                record_id=record_id,
                kind="Event",
                payload=payload,
                epistemic_kind="attributed",
            )
            received = recipient._record(record_id)
            if received is None:
                raise OrganismError("affect report receipt was not committed")
            receipt_ref = {
                "id": record_id,
                "kind": "Event",
                "content_version": int(received["content_version"]),
            }
            appraisal = recipient.semantic({
                "operation": "appraise-experience",
                "operation_id": f"organism:affect-report:appraise:{report.message_id}",
                "evidence": receipt_ref,
                "project_id": AFFECT_PROJECT_ID,
                "object_id": f"cooperation:{report.sender_instance_id}",
            })
            return {
                "schema": "cassifi.research-organism-affect-report-receipt.v1",
                "document_id": document_id,
                "receipt_ref": receipt_ref,
                "appraisal": _plain(appraisal),
            }


    def record_representation_translation(
        self, translation: RepresentationTranslation,
    ) -> str:
        with self._open_residencies(include_members=False) as (root, _):
            document_id = root.session.collective.record_representation_translation(
                translation
            )
            program_ref: dict[str, Any] | None = None
            if translation.method is not None:
                program_id = (
                    f"program:collaboration-translation:{translation.translation_id}"
                )
                self._write_record(
                    root,
                    record_id=program_id,
                    kind="Program",
                    payload={
                        "schema": REPRESENTATION_TRANSLATION_SCHEMA,
                        "collaboration_program_role": (
                            "executable-representation-translation"
                        ),
                        "document_id": document_id,
                        "method": translation.method.as_dict(),
                        "program_role": "procedure",
                        "translation": translation.as_dict(),
                    },
                    epistemic_kind=(
                        "assessed"
                        if translation.validation_status == "validated"
                        else "attributed"
                    ),
                )
                program_record = root._record(program_id)
                if program_record is None:
                    raise OrganismError("translation program was not committed")
                program_ref = {
                    "id": program_id,
                    "kind": "Program",
                    "content_version": int(program_record["content_version"]),
                }
            self._write_record(
                root,
                record_id=(
                    "binding:collaboration-translation:"
                    f"{translation.translation_id}"
                ),
                kind="Binding",
                payload={
                    "schema": (
                        "cassifi.hive.representation-translation-binding.v1"
                    ),
                    "document_id": document_id,
                    "executable": program_ref is not None,
                    "program_ref": program_ref,
                    "source_owner": translation.translator_instance_id,
                    "source_representation": translation.source_representation,
                    "source_response_id": translation.source_response_id,
                    "target_representation": translation.target_representation,
                    "validation_status": translation.validation_status,
                },
                epistemic_kind="attributed",
            )
        self._reconcile_collective_capability_dispatches(
            translation_id=translation.translation_id,
        )
        return document_id

    def record_collective_synthesis(self, synthesis: CollectiveSynthesis) -> str:
        with self._open_residencies(include_members=False) as (root, _):
            compilation = root.session.collective.compile_collective_synthesis(
                synthesis
            )
            assessment_id = f"organism:synthesis:{synthesis.synthesis_id}"
            program_id = (
                f"program:collaboration-synthesis:{synthesis.synthesis_id}"
            )
            gap_id = (
                "obligation:collaboration-capability-gap:"
                f"{synthesis.synthesis_id}"
            )
            existing_assessment = root._record(assessment_id)
            existing_program = root._record(program_id)
            if existing_assessment is not None:
                prior = _plain(existing_assessment["payload"])
                if (
                    prior.get("request_id") != synthesis.request_id
                    or prior.get("synthesizer_instance_id")
                    != synthesis.synthesizer_instance_id
                ):
                    raise OrganismError(
                        "collective synthesis identity changed its owner or request"
                    )
            if existing_program is not None:
                resident_payload = self._unwrap_program_record(
                    existing_program["payload"]
                )
                if (
                    compilation.method is None
                    or resident_payload.get("method")
                    != compilation.method.as_dict()
                    or resident_payload.get("synthesis")
                    != synthesis.as_dict()
                ):
                    raise OrganismError(
                        "an admitted collective synthesis is immutable"
                    )
            document_id = root.session.collective.record_collective_synthesis(
                synthesis
            )
            binding_refs: list[dict[str, Any]] = []
            for translation_id in synthesis.translation_ids:
                binding_id = f"binding:collaboration-translation:{translation_id}"
                binding = root._record(binding_id)
                if binding is None:
                    raise OrganismError(
                        "collective synthesis lacks an admitted translation binding"
                    )
                binding_refs.append(
                    {
                        "id": binding_id,
                        "kind": "Binding",
                        "content_version": int(binding["content_version"]),
                    }
                )
            request_record = root._record(
                f"organism:collaboration-request:{synthesis.request_id}"
            )
            request_maximum_work = (
                None
                if request_record is None
                else request_record["payload"].get("maximum_work")
            )
            if (
                isinstance(request_maximum_work, bool)
                or not isinstance(request_maximum_work, int)
                or request_maximum_work < 1
            ):
                raise OrganismError(
                    "collective synthesis lacks its resident request work bound"
                )
            lineage_sha256 = _digest(
                {
                    "request_id": synthesis.request_id,
                    "synthesis_id": synthesis.synthesis_id,
                    "synthesizer_instance_id": (
                        synthesis.synthesizer_instance_id
                    ),
                }
            )
            existing_gap = root._record(gap_id)
            executable_program_ref: dict[str, Any] | None = None
            capability_gap_ref: dict[str, Any] | None = None
            if compilation.method is not None:
                self._write_record(
                    root,
                    record_id=program_id,
                    kind="Program",
                    payload={
                        "schema": COLLECTIVE_SYNTHESIS_SCHEMA,
                        "collaboration_program_role": (
                            "executable-partial-method-composition"
                        ),
                        "document_id": document_id,
                        "method": compilation.method.as_dict(),
                        "program_role": "procedure",
                        "provenance": [
                            dict(item) for item in compilation.provenance
                        ],
                        "synthesis": synthesis.as_dict(),
                    },
                    epistemic_kind="derived",
                )
                program_record = root._record(program_id)
                if program_record is None:
                    raise OrganismError(
                        "collaborative synthesis program was not committed"
                    )
                executable_program_ref = {
                    "id": program_id,
                    "kind": "Program",
                    "content_version": int(program_record["content_version"]),
                }
                if (
                    existing_gap is not None
                    and existing_gap["payload"].get("state") == "open"
                ):
                    predecessor_gap_ref = {
                        "id": gap_id,
                        "kind": "Obligation",
                        "content_version": int(
                            existing_gap["content_version"]
                        ),
                    }
                    self._write_record(
                        root,
                        record_id=gap_id,
                        kind="Obligation",
                        payload={
                            **_plain(existing_gap["payload"]),
                            "gap_lineage_sha256": lineage_sha256,
                            "resolved_by_program_ref": executable_program_ref,
                            "resolved_from_gap_ref": predecessor_gap_ref,
                            "resolution_document_id": document_id,
                            "state": "resolved",
                        },
                        status="resolved",
                        epistemic_kind="derived",
                    )
            elif synthesis.composition is not None:
                predecessor_gap_ref = (
                    None
                    if existing_gap is None
                    else {
                        "id": gap_id,
                        "kind": "Obligation",
                        "content_version": int(
                            existing_gap["content_version"]
                        ),
                    }
                )
                self._write_record(
                    root,
                    record_id=gap_id,
                    kind="Obligation",
                    payload={
                        "schema": COLLABORATIVE_CAPABILITY_GAP_SCHEMA,
                        "document_id": document_id,
                        "gap_lineage_sha256": lineage_sha256,
                        "gaps": [dict(item) for item in compilation.gaps],
                        "component_provenance": [
                            dict(item) for item in compilation.provenance
                        ],
                        "maximum_work": request_maximum_work,
                        "predecessor_gap_ref": predecessor_gap_ref,
                        "request_id": synthesis.request_id,
                        "state": "open",
                        "synthesis_id": synthesis.synthesis_id,
                    },
                    status="pending",
                    epistemic_kind="derived",
                )
                gap_record = root._record(gap_id)
                if gap_record is None:
                    raise OrganismError(
                        "collaborative capability gap was not committed"
                    )
                capability_gap_ref = {
                    "id": gap_id,
                    "kind": "Obligation",
                    "content_version": int(gap_record["content_version"]),
                }
            self._write_record(
                root,
                record_id=assessment_id,
                kind="Assessment",
                payload={
                    "schema": COLLECTIVE_SYNTHESIS_SCHEMA,
                    "attribution": {
                        "response_ids": list(synthesis.response_ids),
                        "synthesizer_instance_id": (
                            synthesis.synthesizer_instance_id
                        ),
                    },
                    "capability_gap_ref": capability_gap_ref,
                    "compilation": compilation.as_dict(),
                    "document_id": document_id,
                    "executable_program_ref": executable_program_ref,
                    "gap_lineage_sha256": lineage_sha256,
                    "translation_binding_refs": binding_refs,
                    **synthesis.as_dict(),
                },
                epistemic_kind="derived",
            )
        if capability_gap_ref is not None:
            self.dispatch_collective_capability_gaps()
        elif executable_program_ref is not None:
            self._wake_collective_method_continuations(synthesis.synthesis_id)
        return document_id

    @staticmethod
    def _capability_dispatch_record_id(
        synthesis_id: str,
        gap: Mapping[str, Any],
    ) -> str:
        return (
            "organism:capability-dispatch:"
            f"{_digest({'synthesis_id': synthesis_id, 'gap': _plain(gap)})[:32]}"
        )

    @staticmethod
    def _member_capability_record_id(
        member_id: str,
        capability_id: str,
    ) -> str:
        return (
            "organism:member-capability:"
            f"{_digest({'member_id': member_id, 'capability_id': capability_id})[:32]}"
        )

    @staticmethod
    def _collaboration_request_from_payload(
        payload: Mapping[str, Any],
    ) -> CollaborationRequest:
        fields = (
            "desired_roles",
            "input_artifact_ids",
            "maximum_members",
            "maximum_work",
            "objective",
            "request_id",
            "requester_instance_id",
            "required_interface",
            "source_representation",
            "target_representation",
        )
        try:
            return CollaborationRequest.from_dict(
                {field: payload[field] for field in fields}
            )
        except (CollectiveHiveError, KeyError, TypeError, ValueError) as exc:
            raise OrganismError(
                "resident collaboration request is malformed"
            ) from exc

    @staticmethod
    def _ports_are_compatible(source: MethodPort, target: MethodPort) -> bool:
        return (
            source.value_kind == target.value_kind
            and source.representation == target.representation
            and source.unit == target.unit
        )

    def _put_capability_dispatch(
        self,
        root: ResearchResidency,
        *,
        record_id: str,
        payload: Mapping[str, Any],
    ) -> None:
        existing = root._record(record_id)
        normalized = _plain(payload)
        if existing is not None and _plain(existing["payload"]) == normalized:
            return
        self._write_record(
            root,
            record_id=record_id,
            kind="Obligation",
            payload=normalized,
            status=(
                "resolved"
                if normalized.get("state") in {"admitted", "completed"}
                else "pending"
            ),
            epistemic_kind="derived",
        )

    def _member_capability_offers(
        self,
        root: ResearchResidency,
    ) -> dict[str, tuple[str, Mapping[str, Any], HiveOffer]]:
        active = set(self._active_member_ids())
        offers: dict[str, tuple[str, Mapping[str, Any], HiveOffer]] = {}
        for record_id, history in root._task()["records"].items():
            if not record_id.startswith("organism:member-capability:"):
                continue
            payload = history[-1].get("payload")
            if (
                not isinstance(payload, Mapping)
                or payload.get("schema")
                != COLLABORATIVE_MEMBER_CAPABILITY_SCHEMA
                or payload.get("state") != "active"
                or payload.get("member_id") not in active
            ):
                continue
            try:
                offer = HiveOffer(**dict(payload["offer"]))
            except (
                CollectiveHiveError,
                KeyError,
                TypeError,
                ValueError,
            ) as exc:
                raise OrganismError(
                    "resident member capability offer is malformed"
                ) from exc
            if offer.provider_instance_id != payload["member_id"]:
                raise OrganismError(
                    "resident member capability has the wrong provider"
                )
            offers[offer.offer_id] = (record_id, _plain(payload), offer)
        return offers

    @staticmethod
    def _member_is_schedulable(
        root: ResearchResidency,
        member_id: str,
    ) -> bool:
        control = root._record(f"organism:member-control:{member_id}")
        return (
            control is None
            or control["payload"].get("state") == "active"
        )

    def register_member_capability(
        self,
        capability_id: str,
        *,
        member_id: str,
        roles: Sequence[str],
        kind: str,
        domain: str,
        reliability: float,
        work_units: int,
        branch_id: str = "main",
        diversity_keys: Sequence[str] = (),
        method: ExecutableMethod | None = None,
    ) -> dict[str, Any]:
        """Register a bounded offer, optionally anchored to a member Program."""
        capability_id = _identifier(capability_id, "member capability_id")
        member_id = _identifier(member_id, "member capability member_id")
        if member_id not in self._active_member_ids():
            raise OrganismError("capability member is not active")
        if isinstance(roles, (str, bytes)):
            raise OrganismError("capability roles must be a sequence")
        normalized_roles = tuple(
            _text(item, "capability role", maximum=128) for item in roles
        )
        if not normalized_roles:
            raise OrganismError("capability requires at least one role")
        if isinstance(diversity_keys, (str, bytes)):
            raise OrganismError("capability diversity keys must be a sequence")
        normalized_diversity = tuple(
            _text(item, "capability diversity key", maximum=128)
            for item in diversity_keys
        )
        normalized_kind = _text(kind, "capability kind", maximum=128)
        normalized_domain = _text(
            domain, "capability domain", maximum=128
        )
        if method is not None:
            if not isinstance(method, ExecutableMethod):
                raise OrganismError(
                    "capability method must be an executable method"
                )
            if not method.interface.outputs:
                raise OrganismError(
                    "capability method requires an output port"
                )
            if any(
                port.representation != normalized_domain
                for port in method.interface.outputs
            ):
                raise OrganismError(
                    "capability method outputs must match its offer domain"
                )
        offer_key = _digest(
            {"member_id": member_id, "capability_id": capability_id}
        )[:32]
        offer = HiveOffer(
            offer_id=f"capability-offer:{offer_key}",
            provider_instance_id=member_id,
            candidate_id=f"member-capability:{offer_key}",
            kind=normalized_kind,
            domain=normalized_domain,
            branch_id=_text(branch_id, "capability branch_id", maximum=128),
            reliability=reliability,
            work_units=work_units,
            roles=normalized_roles,
            diversity_keys=normalized_diversity,
        )
        record_id = self._member_capability_record_id(member_id, capability_id)
        method_program_id = f"program:member-capability:{offer_key}"
        method_sha256 = (
            None if method is None else _digest(method.as_dict())
        )
        payload: dict[str, Any] = {
            "schema": COLLABORATIVE_MEMBER_CAPABILITY_SCHEMA,
            "capability_id": capability_id,
            "member_id": member_id,
            "offer": offer.as_dict(),
            "offer_id": offer.offer_id,
            "state": "active",
        }
        with self._open_residencies(include_members=True) as (root, members):
            method_ref: dict[str, Any] | None = None
            if method is not None:
                self._ensure_record(
                    members[member_id],
                    record_id=method_program_id,
                    kind="Program",
                    payload={
                        "schema": (
                            COLLABORATIVE_MEMBER_CAPABILITY_METHOD_SCHEMA
                        ),
                        "capability_id": capability_id,
                        "method": method.as_dict(),
                        "method_sha256": method_sha256,
                        "offer_id": offer.offer_id,
                    },
                    epistemic_kind="asserted",
                )
                method_record = members[member_id]._record(method_program_id)
                if method_record is None:
                    raise OrganismError(
                        "member capability method was not committed"
                    )
                method_ref = {
                    "content_version": int(method_record["content_version"]),
                    "id": method_program_id,
                    "kind": "Program",
                }
                payload.update(
                    {
                        "method_ref": method_ref,
                        "method_sha256": method_sha256,
                    }
                )
            existing = root._record(record_id)
            if (
                existing is not None
                and _plain(existing["payload"]) != _plain(payload)
            ):
                raise OrganismError("member capability identity was reused")
            root.session.collective.publish_offer(offer)
            self._ensure_record(
                root,
                record_id=record_id,
                kind="Value",
                payload=payload,
                epistemic_kind="attributed",
            )
            member_payload = {
                **payload,
                "root_capability_record_id": record_id,
            }
            self._ensure_record(
                members[member_id],
                record_id=f"organism:capability-offer:{offer_key}",
                kind="Value",
                payload=member_payload,
                epistemic_kind="asserted",
            )
        dispatches = self.dispatch_collective_capability_gaps()
        return {
            **_plain(payload),
            "dispatches": dispatches,
        }

    def _capability_dispatch_payload(
        self,
        *,
        dispatch_id: str,
        gap_payload: Mapping[str, Any],
        gap: Mapping[str, Any],
        request: CollaborationRequest,
        query: HiveQuery,
        state: str,
        offer: HiveOffer | None = None,
        assignment_id: str | None = None,
        resource_allocation_id: str | None = None,
        role: str | None = None,
        capability_ref: Mapping[str, Any] | None = None,
        hypothetical_alternatives: Sequence[Mapping[str, Any]] = (),
    ) -> dict[str, Any]:
        return {
            "capability_ref": (
                None if capability_ref is None else _plain(capability_ref)
            ),
            "schema": COLLABORATIVE_CAPABILITY_DISPATCH_SCHEMA,
            "assignment_id": assignment_id,
            "gap": _plain(gap),
            "gap_ref": {
                "id": (
                    "obligation:collaboration-capability-gap:"
                    f"{gap_payload['synthesis_id']}"
                ),
                "kind": "Obligation",
            },
            "offer": None if offer is None else offer.as_dict(),
            "hypothetical_alternatives": [
                _plain(item) for item in hypothetical_alternatives[:3]
            ],
            "query": query.as_dict(),
            "request_id": request.request_id,
            "resource_allocation_id": resource_allocation_id,
            "role": role,
            "state": state,
            "synthesis_id": gap_payload["synthesis_id"],
            "dispatch_id": dispatch_id,
        }

    def _open_capability_gaps(
        self,
        root: ResearchResidency,
    ) -> list[dict[str, Any]]:
        gaps: list[dict[str, Any]] = []
        for record_id, history in root._task()["records"].items():
            if not record_id.startswith(
                "obligation:collaboration-capability-gap:"
            ):
                continue
            payload = history[-1].get("payload")
            if (
                isinstance(payload, Mapping)
                and payload.get("schema")
                == COLLABORATIVE_CAPABILITY_GAP_SCHEMA
                and payload.get("state") == "open"
            ):
                gaps.append(_plain(payload))
        return sorted(gaps, key=lambda item: str(item["synthesis_id"]))

    @staticmethod
    def _member_capability_obligation_id(dispatch_id: str) -> str:
        return (
            "obligation:capability-dispatch:"
            f"{_digest({'dispatch_id': dispatch_id})[:32]}"
        )

    def _member_capability_method_locked(
        self,
        root: ResearchResidency,
        member: ResearchResidency,
        dispatch: Mapping[str, Any],
    ) -> tuple[ExecutableMethod, Mapping[str, Any], Mapping[str, Any]] | None:
        capability_ref = dispatch.get("capability_ref")
        if not isinstance(capability_ref, Mapping):
            return None
        record_id = _identifier(
            capability_ref.get("id"),
            "capability reference id",
        )
        capability_record = root._record(record_id)
        if capability_record is None:
            raise OrganismError("capability reference is no longer resident")
        if (
            int(capability_record["content_version"])
            != int(capability_ref.get("content_version"))
        ):
            raise OrganismError("capability reference changed after dispatch")
        capability = _plain(capability_record["payload"])
        if (
            capability.get("schema")
            != COLLABORATIVE_MEMBER_CAPABILITY_SCHEMA
            or capability.get("member_id")
            != dispatch["offer"]["provider_instance_id"]
        ):
            raise OrganismError(
                "capability reference does not belong to its dispatched member"
            )
        method_ref = capability.get("method_ref")
        if not isinstance(method_ref, Mapping):
            return None
        method_record_id = _identifier(
            method_ref.get("id"),
            "capability method reference id",
        )
        method_record = member._record(method_record_id)
        if method_record is None:
            raise OrganismError("member capability method is no longer resident")
        if int(method_record["content_version"]) != int(
            method_ref.get("content_version")
        ):
            raise OrganismError(
                "member capability method changed after dispatch"
            )
        method_payload = self._unwrap_program_record(
            method_record["payload"]
        )
        if (
            method_payload.get("schema")
            != COLLABORATIVE_MEMBER_CAPABILITY_METHOD_SCHEMA
            or method_payload.get("capability_id")
            != capability["capability_id"]
            or method_payload.get("offer_id") != capability["offer_id"]
        ):
            raise OrganismError("member capability method provenance is invalid")
        try:
            method = ExecutableMethod.from_dict(method_payload["method"])
        except (
            CollectiveHiveError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise OrganismError("member capability method is malformed") from exc
        method_sha256 = _digest(method.as_dict())
        if (
            method_payload.get("method_sha256") != method_sha256
            or capability.get("method_sha256") != method_sha256
        ):
            raise OrganismError(
                "member capability method digest does not match its offer"
            )
        return method, _plain(method_ref), capability

    def _seed_member_capability_obligation(
        self,
        dispatch: Mapping[str, Any],
        assignment: CollaborationAssignment,
    ) -> Mapping[str, Any] | None:
        """Give an executable offer to its member's own agenda as an obligation."""
        with self._open_residencies(include_members=True) as (root, members):
            member = members[assignment.assignee_instance_id]
            method_row = self._member_capability_method_locked(
                root,
                member,
                dispatch,
            )
            if method_row is None:
                return None
            _method, method_ref, capability = method_row
            obligation_id = self._member_capability_obligation_id(
                str(dispatch["dispatch_id"])
            )
            payload = {
                "schema": COLLABORATIVE_MEMBER_CAPABILITY_OBLIGATION_SCHEMA,
                "assignment_id": assignment.assignment_id,
                "capability_ref": _plain(dispatch["capability_ref"]),
                "dispatch_id": dispatch["dispatch_id"],
                "method_ref": method_ref,
                "method_sha256": capability["method_sha256"],
                "priority": max(
                    -1.0,
                    min(1.0, float(capability["offer"]["reliability"])),
                ),
                "purpose": "collaborative-procedure-response",
                "state": "pending",
                "synthesis_id": dispatch["synthesis_id"],
            }
            existing = member._record(obligation_id)
            if existing is not None:
                current = _plain(existing["payload"])
                for key in (
                    "assignment_id",
                    "capability_ref",
                    "dispatch_id",
                    "method_ref",
                    "method_sha256",
                    "synthesis_id",
                ):
                    if current.get(key) != payload[key]:
                        raise OrganismError(
                            "member capability obligation was reused"
                        )
            else:
                self._ensure_record(
                    member,
                    record_id=obligation_id,
                    kind="Obligation",
                    payload=payload,
                    status="pending",
                    epistemic_kind="attributed",
                )
                existing = member._record(obligation_id)
            if existing is None:
                raise OrganismError(
                    "member capability obligation was not committed"
                )
            return {
                "content_version": int(existing["content_version"]),
                "id": obligation_id,
                "kind": "Obligation",
            }
    def _charge_capability_agenda_locked(
        self,
        root: ResearchResidency,
        member: ResearchResidency,
        *,
        dispatch: Mapping[str, Any],
        agenda_event: Mapping[str, Any],
        field_state_sha256_before: str,
    ) -> dict[str, Any]:
        member_id = _identifier(
            dispatch["offer"]["provider_instance_id"],
            "capability agenda member_id",
        )
        allocation_id = _identifier(
            dispatch["resource_allocation_id"],
            "capability agenda allocation_id",
        )
        control = root._record(f"organism:member-control:{member_id}")
        if (
            control is not None
            and control["payload"].get("state") == "paused"
        ):
            raise OrganismError("scheduled member is paused")
        record_id = f"organism:resource:{allocation_id}"
        record = root._record(record_id)
        if record is None:
            raise OrganismError("resource allocation is unavailable")
        allocation = _plain(record["payload"])
        if (
            allocation.get("schema") != RESOURCE_ALLOCATION_SCHEMA
            or allocation.get("member_id") != member_id
            or allocation.get("state") != "active"
            or allocation.get("lease", {}).get("state") != "open"
            or allocation.get("settlement", {}).get("status") != "unsettled"
        ):
            raise OrganismError(
                "resource allocation cannot authorize this agenda"
            )
        if int(allocation["remaining"].get("resident_steps", 0)) < 1:
            raise OrganismError("resource allocation is exhausted")
        allocation["consumed"]["resident_steps"] += 1
        allocation["remaining"]["resident_steps"] -= 1
        allocation["generation"] += 1
        if allocation["remaining"]["resident_steps"] == 0:
            allocation["state"] = "exhausted"
        self._write_record(
            root,
            record_id=record_id,
            kind="Value",
            payload=allocation,
        )
        self._write_record(
            member,
            record_id=record_id,
            kind="Value",
            payload={**allocation, "authority": "root-allocation"},
            epistemic_kind="attributed",
        )
        receipt = {
            "schema": COLLABORATIVE_CAPABILITY_AGENDA_RESPONSE_SCHEMA,
            "agenda_event": _plain(agenda_event),
            "allocation_id": allocation_id,
            "dispatch_id": dispatch["dispatch_id"],
            "field_state_sha256_after": member.owner.state.state_sha256,
            "field_state_sha256_before": field_state_sha256_before,
            "lease_fence": allocation["lease"]["fence"],
            "member_id": member_id,
            "reservation_id": allocation["reservation_id"],
        }
        self._write_record(
            member,
            record_id=(
                "event:member-capability-agenda:"
                f"{_digest({'dispatch_id': dispatch['dispatch_id'], 'agenda': agenda_event})[:32]}"
            ),
            kind="Event",
            payload=receipt,
            epistemic_kind="observed",
        )
        return receipt

    def _mark_member_capability_obligation(
        self,
        *,
        dispatch_id: str,
        response_id: str | None,
        state: str,
    ) -> None:
        if state not in {"failed", "fulfilled", "selected"}:
            raise OrganismError("member capability obligation state is invalid")
        with self._open_residencies(include_members=True) as (root, members):
            dispatch_record = root._record(dispatch_id)
            if dispatch_record is None:
                raise OrganismError(
                    "capability dispatch disappeared during agenda completion"
                )
            dispatch = _plain(dispatch_record["payload"])
            offer = dispatch.get("offer")
            obligation_ref = dispatch.get("member_obligation_ref")
            if (
                not isinstance(offer, Mapping)
                or not isinstance(obligation_ref, Mapping)
            ):
                raise OrganismError(
                    "capability dispatch lacks its member agenda obligation"
                )
            member_id = _identifier(
                offer.get("provider_instance_id"),
                "capability obligation member_id",
            )
            obligation_id = _identifier(
                obligation_ref.get("id"),
                "member capability obligation id",
            )
            member = members[member_id]
            obligation = member._record(obligation_id)
            if obligation is None:
                raise OrganismError(
                    "member capability obligation disappeared"
                )
            payload = _plain(obligation["payload"])
            learned_intent = None
            if payload.get("state") not in {"fulfilled", "failed"}:
                use_generation = payload.get("use_generation")
                payload["state"] = state
                if response_id is not None:
                    payload["response_id"] = _identifier(
                        response_id,
                        "member capability response_id",
                    )
                self._write_record(
                    member,
                    record_id=obligation_id,
                    kind="Obligation",
                    payload=payload,
                    status=(
                        "resolved"
                        if state in {"failed", "fulfilled"}
                        else "pending"
                    ),
                    epistemic_kind="derived",
                )
                if state == "fulfilled":
                    intent_ref = dispatch.get("communication_intent_ref")
                    if (
                        isinstance(intent_ref, Mapping)
                        and isinstance(intent_ref.get("id"), str)
                    ):
                        intent_record = root._record(intent_ref["id"])
                        if intent_record is not None:
                            from cassi_field_communication import (
                                FieldIntent,
                                RECORD_RESULT_SCHEMA,
                            )

                            intent = FieldIntent.from_dict(
                                intent_record["payload"]["intent"]
                            )
                            intent_generation = intent_record["payload"].get(
                                "owner_generation"
                            )
                            delay = 0
                            if isinstance(use_generation, int) and isinstance(
                                intent_generation, int
                            ):
                                delay = max(0, use_generation - intent_generation)
                            updated_obligation = member._record(obligation_id)
                            record_sha256 = _digest(
                                _plain(updated_obligation["payload"])
                            )
                            result_ref = {
                                "schema": RECORD_RESULT_SCHEMA,
                                "operation_id": (
                                    f"organism:capability-record-result:"
                                    f"{obligation_id}"
                                ),
                                "id": obligation_id,
                                "kind": "Obligation",
                                "content_version": int(
                                    updated_obligation["content_version"]
                                ),
                                "status": "fulfilled",
                                "record_sha256": record_sha256,
                                "output": {"result_sha256": record_sha256},
                            }
                            root.acknowledge_communication_use(
                                intent=intent,
                                result_ref=result_ref,
                                delay=delay,
                            )
                            learned_intent = intent
            agenda = dict(dispatch.get("agenda", {}))
            agenda["state"] = (
                "responded" if state == "fulfilled" else "failed"
            )
            if response_id is not None:
                agenda["response_id"] = response_id
            dispatch["agenda"] = agenda
            if state == "failed" and dispatch.get("state") == "assigned":
                dispatch["state"] = "blocked"
            self._put_capability_dispatch(
                root,
                record_id=dispatch_id,
                payload=dispatch,
            )
            if learned_intent is not None:
                updated_dispatch = root._record(dispatch_id)
                root._learn_communication_topology(
                    f"organism:capability-topology:{obligation_id}",
                    outcome_ref={
                        "id": dispatch_id,
                        "kind": "Obligation",
                        "content_version": int(
                            updated_dispatch["content_version"]
                        ),
                    },
                    route=(
                        f"{learned_intent.sender}->"
                        f"{learned_intent.receiver}:{learned_intent.kind}"
                    ),
                    question_id=dispatch_id,
                    compiler_family="capability-collaboration",
                    result_status="observed",
                )

    def advance_collective_capability_programs(
        self,
        *,
        maximum_members: int = _MAX_MEMBERS,
        member_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Let each member field agenda select one executable Hive obligation."""
        if (
            isinstance(maximum_members, bool)
            or not isinstance(maximum_members, int)
            or not 1 <= maximum_members <= _MAX_MEMBERS
        ):
            raise OrganismError(
                f"maximum_members must be in [1, {_MAX_MEMBERS}]"
            )
        target_member_id = (
            None
            if member_id is None
            else _identifier(member_id, "capability agenda member_id")
        )
        self.dispatch_collective_capability_gaps()
        pending_responses: list[
            tuple[str, CollaborationResponse]
        ] = []
        results: list[dict[str, Any]] = []
        with self._open_residencies(include_members=True) as (root, members):
            by_member: dict[str, dict[str, Mapping[str, Any]]] = {}
            for record_id, history in root._task()["records"].items():
                payload = history[-1].get("payload")
                if (
                    not record_id.startswith("organism:capability-dispatch:")
                    or not isinstance(payload, Mapping)
                    or payload.get("schema")
                    != COLLABORATIVE_CAPABILITY_DISPATCH_SCHEMA
                    or payload.get("state") != "assigned"
                ):
                    continue
                dispatch = _plain(payload)
                offer = dispatch.get("offer")
                obligation_ref = dispatch.get("member_obligation_ref")
                if (
                    not isinstance(offer, Mapping)
                    or not isinstance(obligation_ref, Mapping)
                ):
                    continue
                member_id = offer.get("provider_instance_id")
                obligation_id = obligation_ref.get("id")
                if (
                    not isinstance(member_id, str)
                    or member_id not in members
                    or not isinstance(obligation_id, str)
                ):
                    continue
                member_obligation = members[member_id]._record(obligation_id)
                if (
                    member_obligation is None
                    or member_obligation["payload"].get("state")
                    in {"failed", "fulfilled"}
                ):
                    continue
                by_member.setdefault(member_id, {})[obligation_id] = dispatch
            responses, translations = self._collaboration_artifact_maps(root)
            eligible_members = sorted(by_member)
            if target_member_id is not None:
                eligible_members = [
                    candidate
                    for candidate in eligible_members
                    if candidate == target_member_id
                ]
            for member_id in eligible_members[:maximum_members]:
                member = members[member_id]
                field_state_before = member.owner.state.state_sha256
                agenda = member.semantic(
                    {
                        "operation": "autonomous-agenda",
                        "operation_id": (
                            "organism:capability-agenda:"
                            f"{_digest({'member_id': member_id, 'field': field_state_before})[:32]}"
                        ),
                        "goal": {
                            "objective": (
                                "select the most valuable bounded Hive "
                                "capability contribution"
                            )
                        },
                        "max_items": 1,
                        "obligation_prefix": (
                            "obligation:capability-dispatch:"
                        ),
                    }
                )
                selected = agenda.get("selected")
                obligation = (
                    selected.get("obligation")
                    if isinstance(selected, Mapping)
                    else None
                )
                obligation_id = (
                    obligation.get("id")
                    if isinstance(obligation, Mapping)
                    else None
                )
                dispatch = (
                    by_member[member_id].get(obligation_id)
                    if isinstance(obligation_id, str)
                    else None
                )
                if dispatch is None:
                    results.append(
                        {
                            "member_id": member_id,
                            "state": "not-selected",
                        }
                    )
                    continue
                agenda_event = agenda.get("event")
                if not isinstance(agenda_event, Mapping):
                    raise OrganismError(
                        "member agenda did not retain its selection event"
                    )
                method_row = self._member_capability_method_locked(
                    root,
                    member,
                    dispatch,
                )
                if method_row is None:
                    raise OrganismError(
                        "agenda-selected capability lacks its member method"
                    )
                method, method_ref, capability = method_row
                response_id = (
                    "capability-response:"
                    f"{_digest({'dispatch_id': dispatch['dispatch_id'], 'method_sha256': capability['method_sha256']})[:32]}"
                )
                response = CollaborationResponse(
                    response_id=response_id,
                    assignment_id=dispatch["assignment_id"],
                    responder_instance_id=member_id,
                    status="completed",
                    representation=capability["offer"]["domain"],
                    content={
                        "schema": (
                            COLLABORATIVE_CAPABILITY_AGENDA_RESPONSE_SCHEMA
                        ),
                        "agenda_event": _plain(agenda_event),
                        "dispatch_id": dispatch["dispatch_id"],
                        "method_ref": method_ref,
                        "method_sha256": capability["method_sha256"],
                    },
                    evidence_ids=(
                        (str(agenda_event["id"]),)
                        if isinstance(agenda_event.get("id"), str)
                        else ()
                    ),
                    method=method,
                )
                candidate_responses = dict(responses)
                candidate_responses[response.response_id] = response
                candidate = self._automatic_synthesis_candidate(
                    root,
                    dispatch=dispatch,
                    contribution_kind="response",
                    contribution_id=response.response_id,
                    method=method,
                    responses=candidate_responses,
                    translations=translations,
                )
                execution = self._charge_capability_agenda_locked(
                    root,
                    member,
                    dispatch=dispatch,
                    agenda_event=agenda_event,
                    field_state_sha256_before=field_state_before,
                )
                use_generation = root.owner.state.generation
                member_obligation = member._record(str(obligation_id))
                if member_obligation is None:
                    raise OrganismError(
                        "agenda-selected obligation disappeared"
                    )
                obligation_payload = _plain(member_obligation["payload"])
                not_composable = candidate is None
                obligation_payload.update(
                    {
                        "agenda_event": _plain(agenda_event),
                        "agenda_execution": execution,
                        "use_generation": use_generation,
                        "state": (
                            "failed" if not_composable else "selected"
                        ),
                    }
                )
                self._write_record(
                    member,
                    record_id=str(obligation_id),
                    kind="Obligation",
                    payload=obligation_payload,
                    status="resolved" if not_composable else "pending",
                    epistemic_kind="derived",
                )
                root_dispatch = root._record(str(dispatch["dispatch_id"]))
                if root_dispatch is None:
                    raise OrganismError(
                        "capability dispatch disappeared after agenda selection"
                    )
                dispatch_payload = _plain(root_dispatch["payload"])
                dispatch_payload["agenda"] = {
                    "event": _plain(agenda_event),
                    "execution": execution,
                    "member_id": member_id,
                    "state": (
                        "not-composable" if not_composable else "selected"
                    ),
                }
                if not_composable:
                    dispatch_payload["state"] = "blocked"
                self._put_capability_dispatch(
                    root,
                    record_id=str(dispatch["dispatch_id"]),
                    payload=dispatch_payload,
                )
                if not_composable:
                    results.append(
                        {
                            "dispatch_id": dispatch["dispatch_id"],
                            "member_id": member_id,
                            "state": "not-composable",
                        }
                    )
                    continue
                pending_responses.append(
                    (str(dispatch["dispatch_id"]), response)
                )
        for dispatch_id, response in pending_responses:
            self.record_collaboration_response(response)
            self._mark_member_capability_obligation(
                dispatch_id=dispatch_id,
                response_id=response.response_id,
                state="fulfilled",
            )
            results.append(
                {
                    "dispatch_id": dispatch_id,
                    "member_id": response.responder_instance_id,
                    "response_id": response.response_id,
                    "state": "responded",
                }
            )
        return sorted(
            results,
            key=lambda item: (
                str(item.get("member_id", "")),
                str(item.get("dispatch_id", "")),
            ),
        )

    def _record_capability_collaboration_intent(
        self,
        root: ResearchResidency,
        *,
        dispatch_id: str,
        request_id: str,
        provider_instance_id: str,
    ) -> dict[str, Any] | None:
        """Record a Send FieldIntent from a real member requester to its provider.

        Returns None (recording nothing) when the request was not itself made
        by an authenticated member -- root-initiated dispatches have no second
        member endpoint to route between.
        """
        request_record_id = f"organism:collaboration-request:{request_id}"
        request_record = root._record(request_record_id)
        if request_record is None:
            return None
        requester_instance_id = request_record["payload"].get("requester_instance_id")
        if (
            not isinstance(requester_instance_id, str)
            or requester_instance_id not in self._active_member_ids()
            or requester_instance_id == provider_instance_id
        ):
            return None
        from cassi_field_communication import FieldIntent

        intent = FieldIntent(
            kind="send",
            sender=requester_instance_id,
            receiver=provider_instance_id,
            payload_ref={
                "id": request_record_id,
                "kind": str(request_record["kind"]),
                "content_version": int(request_record["content_version"]),
            },
            dependency_versions=(),
            urgency="background",
            consumer_use_id=f"organism:capability-intent:{dispatch_id}",
        )
        intent_record_id = f"organism:collaboration-intent:{dispatch_id}"
        self._write_record(
            root,
            record_id=intent_record_id,
            kind="Event",
            payload={
                "schema": "cassifi.research-organism-capability-intent.v1",
                "intent": intent.as_dict(),
                "owner_generation": root.owner.state.generation,
            },
            epistemic_kind="derived",
        )
        intent_record = root._record(intent_record_id)
        return {
            "id": intent_record_id,
            "kind": "Event",
            "content_version": int(intent_record["content_version"]),
        }

    def _activate_capability_dispatch(
        self,
        dispatch: Mapping[str, Any],
    ) -> dict[str, Any]:

        try:
            offer = HiveOffer(**dict(dispatch["offer"]))
            allocation_id = _identifier(
                dispatch["resource_allocation_id"],
                "capability allocation_id",
            )
            assignment_id = _identifier(
                dispatch["assignment_id"],
                "capability assignment_id",
            )
            member_id = offer.provider_instance_id
            allocation = self.allocate_resources(
                allocation_id,
                member_id=member_id,
                objective={
                    "dispatch_id": dispatch["dispatch_id"],
                    "synthesis_id": dispatch["synthesis_id"],
                    "kind": "collaborative-capability-completion",
                },
                budgets={"resident_steps": offer.work_units},
                reservation_id=(
                    f"capability-reservation:"
                    f"{_digest(dispatch['dispatch_id'])[:24]}"
                ),
                work_order_id=(
                    f"capability-work:"
                    f"{_digest(dispatch['dispatch_id'])[:24]}"
                ),
            )
            assignment = CollaborationAssignment(
                assignment_id=assignment_id,
                request_id=str(dispatch["request_id"]),
                assignee_instance_id=member_id,
                role=str(dispatch["role"]),
                task={
                    "schema": COLLABORATIVE_CAPABILITY_DISPATCH_SCHEMA,
                    "dispatch_id": dispatch["dispatch_id"],
                    "gap": _plain(dispatch["gap"]),
                    "synthesis_id": dispatch["synthesis_id"],
                    "completion": (
                        "submit a completed response or validated translation "
                        "with an executable method"
                    ),
                },
                resource_allocation_id=allocation_id,
            )
            document_id = self.assign_collaboration(assignment)
            member_obligation_ref = self._seed_member_capability_obligation(
                dispatch,
                assignment,
            )
        except (CollectiveHiveError, OrganismError) as exc:
            with self._open_residencies(include_members=False) as (root, _):
                record_id = str(dispatch["dispatch_id"])
                current = root._record(record_id)
                if current is None:
                    raise OrganismError(
                        "capability dispatch disappeared during activation"
                    ) from exc
                payload = _plain(current["payload"])
                if payload.get("state") != "admitted":
                    payload.update(
                        {
                            "last_error": _text(
                                str(exc),
                                "capability dispatch error",
                                maximum=1024,
                            ),
                            "state": "parked",
                        }
                    )
                    self._put_capability_dispatch(
                        root,
                        record_id=record_id,
                        payload=payload,
                    )
            return {
                "dispatch_id": dispatch["dispatch_id"],
                "state": "parked",
            }
        with self._open_residencies(include_members=False) as (root, _):
            record_id = str(dispatch["dispatch_id"])
            current = root._record(record_id)
            if current is None:
                raise OrganismError(
                    "capability dispatch disappeared after allocation"
                )
            payload = _plain(current["payload"])
            if payload.get("state") != "admitted":
                update = {
                    "assignment": assignment.as_dict(),
                    "assignment_document_id": document_id,
                    "resource_allocation": {
                        "id": allocation_id,
                        "remaining": _plain(allocation["remaining"]),
                    },
                    "member_obligation_ref": member_obligation_ref,
                    "state": "assigned",
                }
                intent_ref = self._record_capability_collaboration_intent(
                    root,
                    dispatch_id=record_id,
                    request_id=str(dispatch["request_id"]),
                    provider_instance_id=member_id,
                )
                if intent_ref is not None:
                    update["communication_intent_ref"] = intent_ref
                payload.update(update)
                self._put_capability_dispatch(
                    root,
                    record_id=record_id,
                    payload=payload,
                )
            return {
                "assignment_id": assignment_id,
                "dispatch_id": dispatch["dispatch_id"],
                "state": "assigned",
            }

    @staticmethod
    def _communication_adjacency(root: ResearchResidency) -> dict[str, dict[str, Any]]:
        """Project authenticated actual-use routes into bounded member adjacency."""
        from cassi_field_communication import ACK_SCHEMA, LOCALITY_SCHEMA

        payload = root._communication_locality()
        if (
            not isinstance(payload, Mapping)
            or payload.get("schema") != LOCALITY_SCHEMA
            or not isinstance(payload.get("routes"), Mapping)
            or not isinstance(payload.get("observations"), list)
        ):
            return {}
        observations = payload["observations"][-64:]
        acknowledged: dict[str, tuple[str, Mapping[str, Any]]] = {}
        for observation in observations:
            if not isinstance(observation, Mapping):
                continue
            use_sha256 = observation.get("use_sha256")
            route = observation.get("route")
            if not isinstance(use_sha256, str) or not isinstance(route, str):
                continue
            ack = root._record("communication:use:" + use_sha256[:40])
            ack_payload = ack.get("payload") if isinstance(ack, Mapping) else None
            if (
                not isinstance(ack_payload, Mapping)
                or ack_payload.get("schema") != ACK_SCHEMA
                or ack_payload.get("status") != "used"
                or ack_payload.get("use_sha256") != use_sha256
            ):
                continue
            acknowledged[use_sha256] = (route, ack_payload)
        adjacency: dict[str, dict[str, Any]] = {}
        for use_sha256, (route, ack_payload) in acknowledged.items():
            if "->" not in route or ":" not in route:
                continue
            sender, remainder = route.split("->", 1)
            receiver, kind = remainder.rsplit(":", 1)
            if not sender or not receiver or not kind:
                continue
            result_ref = ack_payload.get("result_ref")
            output = (
                result_ref.get("output", result_ref)
                if isinstance(result_ref, Mapping)
                else None
            )
            if not isinstance(output, Mapping):
                continue
            edge = adjacency.setdefault(sender, {}).setdefault(
                receiver,
                {
                    "uses": [], "outcomes": [], "kinds": [], "routes": [],
                    "work_observations": [],
                },
            )
            edge["uses"].append(use_sha256)
            outcome = output.get("result_sha256")
            if isinstance(outcome, str) and outcome not in edge["outcomes"]:
                edge["outcomes"].append(outcome)
            work_outcome = ack_payload.get("work_outcome")
            if (
                isinstance(work_outcome, Mapping)
                and work_outcome.get("status") == "observed"
                and isinstance(work_outcome.get("work_unblocked"), bool)
                and isinstance(work_outcome.get("completed"), bool)
            ):
                edge["work_observations"].append({
                    "use_sha256": use_sha256,
                    "work_unblocked": work_outcome["work_unblocked"],
                    "completed": work_outcome["completed"],
                })
            if kind not in edge["kinds"]:
                edge["kinds"].append(kind)
            if route not in edge["routes"]:
                edge["routes"].append(route)
        actual_uses = list(acknowledged.items())
        for left, right in zip(actual_uses, actual_uses[1:]):
            left_use, (left_route, left_ack) = left
            right_use, (right_route, right_ack) = right
            if (
                "->" not in left_route
                or ":" not in left_route
                or "->" not in right_route
                or ":" not in right_route
            ):
                continue
            left_sender, left_tail = left_route.split("->", 1)
            left_receiver = left_tail.rsplit(":", 1)[0]
            right_sender, right_tail = right_route.split("->", 1)
            if left_receiver != right_sender:
                continue
            left_ref = left_ack.get("result_ref")
            right_ref = right_ack.get("result_ref")
            left_output = left_ref.get("output", left_ref) if isinstance(left_ref, Mapping) else None
            right_output = right_ref.get("output", right_ref) if isinstance(right_ref, Mapping) else None
            if not isinstance(left_output, Mapping) or not isinstance(right_output, Mapping):
                continue
            chain = {
                "chain_id": _digest({"uses": [left_use, right_use]}),
                "uses": [left_use, right_use],
                "outcomes": [
                    left_output.get("result_sha256"),
                    right_output.get("result_sha256"),
                ],
            }
            edge = adjacency[left_sender][left_receiver]
            edge.setdefault("chains", []).append(chain)
        for targets in adjacency.values():
            for edge in targets.values():
                edge["chains"] = edge.get("chains", [])[-64:]
        return adjacency

    @classmethod
    def _locality_member_rank(
        cls,
        root: ResearchResidency,
        provider_instance_id: str,
    ) -> tuple[int, int, float, int]:
        """Rank Hive providers by observed outcomes, then admitted route hints."""
        from cassi_field_communication import LOCALITY_SCHEMA, anticipate_routes

        locality = root._communication_locality()
        route_rank = 4
        if (
            isinstance(locality, Mapping)
            and locality.get("schema") == LOCALITY_SCHEMA
            and isinstance(locality.get("routes"), Mapping)
        ):
            route_names = tuple(locality["routes"])
            if route_names:
                anticipated = anticipate_routes(
                    locality,
                    route_names,
                    limit=min(4, len(route_names)),
                )
                for index, route in enumerate(anticipated):
                    if "->" not in route or ":" not in route:
                        continue
                    sender, remainder = route.split("->", 1)
                    receiver = remainder.rsplit(":", 1)[0]
                    if provider_instance_id in {sender, receiver}:
                        route_rank = min(route_rank, index)
        adjacency = cls._communication_adjacency(root)
        linked: list[tuple[Mapping[str, Any], str]] = []
        for sender, targets in adjacency.items():
            for receiver, edge in targets.items():
                if provider_instance_id in {sender, receiver}:
                    linked.extend((edge, route) for route in edge.get("routes", []))
        if not linked:
            return (3, route_rank, 0.0, 0)
        topology = root._communication_topology(require_current=True)
        preferences = (
            topology.get("routes")
            if isinstance(topology, Mapping)
            and isinstance(topology.get("routes"), Mapping)
            else {}
        )
        weighted = [
            (len(edge.get("uses", [])), preferences.get(route))
            for edge, route in linked
        ]
        observed = [
            (uses, value)
            for uses, value in weighted
            if isinstance(value, Mapping)
            and isinstance(value.get("successful"), int)
            and isinstance(value.get("unsuccessful"), int)
        ]
        work_observations = [
            item
            for edge, _ in linked
            for item in edge.get("work_observations", [])
            if isinstance(item, Mapping)
        ]
        if not observed:
            if not work_observations:
                return (1, route_rank, 0.5, -sum(uses for uses, _ in weighted))
            unblocked = sum(item.get("work_unblocked") is True for item in work_observations)
            completed = sum(item.get("completed") is True for item in work_observations)
            score = (completed + 0.5 * (unblocked - completed) + 1) / (
                len(work_observations) + 2
            )
            category = 0 if completed else (1 if unblocked else 4)
            return (category, route_rank, -score, -sum(uses for uses, _ in weighted))
        successes = sum(int(value["successful"]) for _, value in observed)
        failures = sum(int(value["unsuccessful"]) for _, value in observed)
        score = (successes + 1) / (successes + failures + 2)
        if score < 0.5:
            category = 4
        elif score > 0.5 and successes:
            category = 0
        else:
            category = 1
        return (
            category,
            route_rank,
            -score,
            -sum(uses for uses, _ in weighted),
        )

    def dispatch_collective_capability_gaps(
        self,
        *,
        synthesis_id: str | None = None,
        gap_sha256: str | None = None,
    ) -> list[dict[str, Any]]:
        """Route open typed gaps, optionally one selected contribution."""
        target_synthesis_id = (
            None
            if synthesis_id is None
            else _identifier(synthesis_id, "capability synthesis_id")
        )
        if gap_sha256 is not None and (
            not isinstance(gap_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", gap_sha256) is None
        ):
            raise OrganismError("capability gap_sha256 must be a SHA-256 digest")
        plans: list[dict[str, Any]] = []
        results: list[dict[str, Any]] = []
        with self._open_residencies(include_members=False) as (root, _):
            active_members = set(self._active_member_ids())
            capability_offers = self._member_capability_offers(root)
            assignments = [
                CollaborationAssignment.from_dict(document["content"])
                for document in root.session.collective.list_collaboration(
                    COLLABORATION_ASSIGNMENT_SCHEMA
                )
            ]
            assigned_by_request: dict[str, set[str]] = {}
            for assignment in assignments:
                assigned_by_request.setdefault(
                    assignment.request_id, set()
                ).add(assignment.assignee_instance_id)
            for gap_payload in self._open_capability_gaps(root):
                if (
                    target_synthesis_id is not None
                    and gap_payload["synthesis_id"] != target_synthesis_id
                ):
                    continue
                request_record = root._record(
                    "organism:collaboration-request:"
                    f"{gap_payload['request_id']}"
                )
                if request_record is None:
                    raise OrganismError(
                        "capability gap lacks its resident collaboration request"
                    )
                request = self._collaboration_request_from_payload(
                    request_record["payload"]
                )
                maximum_work = int(gap_payload["maximum_work"])
                for gap in gap_payload["gaps"]:
                    if gap_sha256 is not None and _digest(gap) != gap_sha256:
                        continue
                    dispatch_id = self._capability_dispatch_record_id(
                        str(gap_payload["synthesis_id"]),
                        gap,
                    )
                    existing = root._record(dispatch_id)
                    existing_payload = (
                        None
                        if existing is None
                        else _plain(existing["payload"])
                    )
                    if (
                        existing_payload is not None
                        and existing_payload.get("state")
                        in {"assigned", "admitted", "completed", "blocked"}
                    ):
                        continue
                    if (
                        existing_payload is not None
                        and existing_payload.get("state") == "prepared"
                    ):
                        plans.append(existing_payload)
                        continue
                    expected = gap.get("expected")
                    domain = (
                        str(expected["representation"])
                        if isinstance(expected, Mapping)
                        and isinstance(expected.get("representation"), str)
                        else request.target_representation
                    )
                    query = HiveQuery(
                        query_id=(
                            "capability-query:"
                            f"{_digest({'dispatch_id': dispatch_id})[:24]}"
                        ),
                        requester_instance_id="organism-root",
                        kinds=("procedure",),
                        domains=(domain,),
                        maximum_work=maximum_work,
                        desired_roles=request.desired_roles,
                    )
                    root.session.collective.record_query(query)
                    available = [
                        offer
                        for offer in root.session.collective.router.match(query)
                        if offer.offer_id in capability_offers
                        and offer.provider_instance_id in active_members
                        and self._member_is_schedulable(
                            root, offer.provider_instance_id
                        )
                        and (
                            offer.provider_instance_id
                            in assigned_by_request.setdefault(
                                request.request_id, set()
                            )
                            or len(
                                assigned_by_request[request.request_id]
                            )
                            < request.maximum_members
                        )
                    ]
                    available[:] = [
                        offer
                        for _, offer in sorted(
                            enumerate(available),
                            key=lambda indexed: (
                                *self._locality_member_rank(
                                    root, indexed[1].provider_instance_id
                                ),
                                indexed[0],
                            ),
                        )
                    ]
                    if not available:
                        payload = self._capability_dispatch_payload(
                            dispatch_id=dispatch_id,
                            gap_payload=gap_payload,
                            gap=gap,
                            request=request,
                            query=query,
                            state="parked",
                        )
                        self._put_capability_dispatch(
                            root,
                            record_id=dispatch_id,
                            payload=payload,
                        )
                        results.append(
                            {
                                "dispatch_id": dispatch_id,
                                "state": "parked",
                            }
                        )
                        continue
                    offer = available[0]
                    shared_roles = sorted(
                        set(request.desired_roles).intersection(offer.roles)
                    )
                    role = (
                        shared_roles[0]
                        if shared_roles
                        else sorted(offer.roles)[0]
                    )
                    key = _digest({"dispatch_id": dispatch_id})[:24]
                    capability_record_id, _capability_payload, _ = (
                        capability_offers[offer.offer_id]
                    )
                    capability_record = root._record(capability_record_id)
                    if capability_record is None:
                        raise OrganismError(
                            "selected member capability disappeared"
                        )
                    hypothetical_alternatives = [
                        {
                            "status": "hypothetical-unexecuted",
                            "offer_id": alternative.offer_id,
                            "provider_instance_id": alternative.provider_instance_id,
                            "historical_locality_rank": list(
                                self._locality_member_rank(
                                    root, alternative.provider_instance_id
                                )
                            ),
                        }
                        for alternative in available[1:4]
                    ]
                    capability_ref = {
                        "content_version": int(
                            capability_record["content_version"]
                        ),
                        "id": capability_record_id,
                        "kind": "Value",
                    }
                    payload = self._capability_dispatch_payload(
                        dispatch_id=dispatch_id,
                        gap_payload=gap_payload,
                        gap=gap,
                        request=request,
                        query=query,
                        state="prepared",
                        offer=offer,
                        assignment_id=f"capability-assignment:{key}",
                        resource_allocation_id=f"capability-allocation:{key}",
                        role=role,
                        capability_ref=capability_ref,
                        hypothetical_alternatives=hypothetical_alternatives,
                    )
                    self._put_capability_dispatch(
                        root,
                        record_id=dispatch_id,
                        payload=payload,
                    )
                    assigned_by_request[request.request_id].add(
                        offer.provider_instance_id
                    )
                    plans.append(payload)
        for plan in plans:
            results.append(self._activate_capability_dispatch(plan))
        return sorted(results, key=lambda item: str(item["dispatch_id"]))

    @staticmethod
    def _collective_synthesis_from_payload(
        payload: Mapping[str, Any],
    ) -> CollectiveSynthesis:
        fields = (
            "agreements",
            "composition",
            "disagreements",
            "request_id",
            "response_ids",
            "result",
            "synthesis_id",
            "synthesizer_instance_id",
            "translation_ids",
            "unresolved",
        )
        try:
            return CollectiveSynthesis.from_dict(
                {field: payload[field] for field in fields}
            )
        except (CollectiveHiveError, KeyError, TypeError, ValueError) as exc:
            raise OrganismError(
                "resident collective synthesis is malformed"
            ) from exc

    def _collective_investigation_view(
        self,
        root: ResearchResidency,
        synthesis_id: str,
    ) -> dict[str, Any]:
        """Project one evolving composition as a durable staged investigation."""
        synthesis_id = _identifier(
            synthesis_id,
            "collective investigation synthesis_id",
        )
        history = root._task()["records"].get(
            f"organism:synthesis:{synthesis_id}"
        )
        if not isinstance(history, list) or not history:
            raise OrganismError("collective investigation is unavailable")
        previous_components: set[str] = set()
        stages: list[dict[str, Any]] = []
        latest_synthesis: CollectiveSynthesis | None = None
        latest_payload: Mapping[str, Any] | None = None
        for record in history:
            payload = record.get("payload")
            if not isinstance(payload, Mapping):
                raise OrganismError(
                    "collective investigation contains malformed history"
                )
            synthesis = self._collective_synthesis_from_payload(payload)
            components = set(
                synthesis.composition.component_ids
                if synthesis.composition is not None
                else (
                    *synthesis.response_ids,
                    *synthesis.translation_ids,
                )
            )
            capability_dispatch = synthesis.result.get(
                "capability_dispatch"
            )
            dispatch_view: dict[str, Any] | None = None
            if isinstance(capability_dispatch, Mapping):
                dispatch_id = capability_dispatch.get("dispatch_id")
                if isinstance(dispatch_id, str):
                    dispatch_record = root._record(dispatch_id)
                    dispatch_payload = (
                        dispatch_record.get("payload")
                        if dispatch_record is not None
                        else None
                    )
                    offer = (
                        dispatch_payload.get("offer")
                        if isinstance(dispatch_payload, Mapping)
                        else None
                    )
                    dispatch_view = {
                        "contribution_id": capability_dispatch.get(
                            "contribution_id"
                        ),
                        "dispatch_id": dispatch_id,
                        "member_id": (
                            offer.get("provider_instance_id")
                            if isinstance(offer, Mapping)
                            else None
                        ),
                        "state": (
                            dispatch_payload.get("state")
                            if isinstance(dispatch_payload, Mapping)
                            else None
                        ),
                    }
            executable_program_ref = payload.get(
                "executable_program_ref"
            )
            capability_gap_ref = payload.get("capability_gap_ref")
            stage = {
                "added_component_ids": sorted(
                    components - previous_components
                ),
                "component_count": len(components),
                "content_version": int(record["content_version"]),
                "dispatch": dispatch_view,
                "state": (
                    "ready"
                    if isinstance(executable_program_ref, Mapping)
                    else (
                        "assembling"
                        if isinstance(capability_gap_ref, Mapping)
                        else "recorded"
                    )
                ),
            }
            stages.append(stage)
            if len(stages) > _MAX_TRACE:
                stages.pop(0)
            previous_components = components
            latest_synthesis = synthesis
            latest_payload = payload
        if latest_synthesis is None or latest_payload is None:
            raise OrganismError("collective investigation has no synthesis")
        final_stage = stages[-1]
        return {
            "schema": COLLECTIVE_INVESTIGATION_SCHEMA,
            "component_count": final_stage["component_count"],
            "contributed_stage_count": sum(
                1 for stage in stages if stage["dispatch"] is not None
            ),
            "executable_program_ref": latest_payload.get(
                "executable_program_ref"
            ),
            "request_id": latest_synthesis.request_id,
            "remaining_capability_gap_ref": latest_payload.get(
                "capability_gap_ref"
            ),
            "stage_count": len(stages),
            "stages": stages,
            "state": final_stage["state"],
            "synthesis_id": synthesis_id,
        }

    def _collaboration_artifact_maps(
        self,
        root: ResearchResidency,
    ) -> tuple[
        dict[str, CollaborationResponse],
        dict[str, RepresentationTranslation],
    ]:
        responses: dict[str, CollaborationResponse] = {}
        translations: dict[str, RepresentationTranslation] = {}
        try:
            for document in root.session.collective.list_collaboration(
                COLLABORATION_RESPONSE_SCHEMA
            ):
                response = CollaborationResponse.from_dict(document["content"])
                responses[response.response_id] = response
            for document in root.session.collective.list_collaboration(
                REPRESENTATION_TRANSLATION_SCHEMA
            ):
                translation = RepresentationTranslation.from_dict(
                    document["content"]
                )
                translations[translation.translation_id] = translation
        except (
            CollectiveHiveError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise OrganismError(
                "resident collaboration artifacts are malformed"
            ) from exc
        return responses, translations

    @staticmethod
    def _synthesis_component_methods(
        synthesis: CollectiveSynthesis,
        responses: Mapping[str, CollaborationResponse],
        translations: Mapping[str, RepresentationTranslation],
    ) -> dict[str, ExecutableMethod]:
        methods: dict[str, ExecutableMethod] = {}
        for response_id in synthesis.response_ids:
            response = responses.get(response_id)
            if response is not None and response.method is not None:
                methods[response_id] = response.method
        for translation_id in synthesis.translation_ids:
            translation = translations.get(translation_id)
            if translation is not None and translation.method is not None:
                methods[translation_id] = translation.method
        return methods

    @staticmethod
    def _method_port_signature(port: MethodPort) -> tuple[str, str, str]:
        return (port.value_kind, port.representation, port.unit)

    def _capability_development_opportunities(
        self,
        root: ResearchResidency,
        *,
        dispatches: Sequence[Mapping[str, Any]],
        actions: Sequence[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        """Expose exact parked gaps that an active member can learn to close."""

        active_members = tuple(
            member_id
            for member_id in self._active_member_ids()
            if self._member_is_schedulable(root, member_id)
        )
        if not active_members:
            return []
        dispatch_by_id = {
            str(row["dispatch_id"]): row
            for row in dispatches
            if isinstance(row.get("dispatch_id"), str)
        }
        outcomes_by_member: dict[str, dict[str, int]] = {
            member_id: {
                "attempts": 0,
                "failed": 0,
                "pending": 0,
                "succeeded": 0,
            }
            for member_id in active_members
        }
        for action in actions:
            if action.get("kind") != "develop-capability-gap":
                continue
            candidate = action.get("candidate")
            if not isinstance(candidate, Mapping):
                continue
            member_id = candidate.get("member_id")
            dispatch_id = candidate.get("dispatch_id")
            if (
                not isinstance(member_id, str)
                or member_id not in outcomes_by_member
                or not isinstance(dispatch_id, str)
            ):
                continue
            bucket = outcomes_by_member[member_id]
            bucket["attempts"] += 1
            dispatch = dispatch_by_id.get(dispatch_id)
            state = dispatch.get("state") if dispatch is not None else None
            if state in {"admitted", "completed"}:
                bucket["succeeded"] += 1
            elif state == "blocked":
                bucket["failed"] += 1
            else:
                bucket["pending"] += 1

        try:
            assignments = [
                CollaborationAssignment.from_dict(document["content"])
                for document in root.session.collective.list_collaboration(
                    COLLABORATION_ASSIGNMENT_SCHEMA
                )
            ]
        except (
            CollectiveHiveError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise OrganismError(
                "resident collaboration assignments are malformed"
            ) from exc
        responses, translations = self._collaboration_artifact_maps(root)
        opportunities: list[dict[str, Any]] = []
        for dispatch in sorted(
            dispatches,
            key=lambda row: str(row.get("dispatch_id", "")),
        ):
            if dispatch.get("state") != "parked":
                continue
            dispatch_id = dispatch.get("dispatch_id")
            synthesis_id = dispatch.get("synthesis_id")
            gap = dispatch.get("gap")
            request_id = dispatch.get("request_id")
            if (
                not isinstance(dispatch_id, str)
                or not isinstance(synthesis_id, str)
                or not isinstance(gap, Mapping)
                or not isinstance(request_id, str)
            ):
                continue
            expected_payload = gap.get("expected")
            if not isinstance(expected_payload, Mapping):
                continue
            try:
                expected = MethodPort.from_dict(expected_payload)
            except (CollectiveHiveError, TypeError, ValueError):
                continue
            request_record = root._record(
                f"organism:collaboration-request:{request_id}"
            )
            synthesis_record = root._record(
                f"organism:synthesis:{synthesis_id}"
            )
            if request_record is None or synthesis_record is None:
                continue
            request = self._collaboration_request_from_payload(
                request_record["payload"]
            )
            if request.required_interface is None:
                continue
            synthesis = self._collective_synthesis_from_payload(
                synthesis_record["payload"]
            )
            if synthesis.composition is None:
                continue
            methods = self._synthesis_component_methods(
                synthesis,
                responses,
                translations,
            )
            component_ids = set(synthesis.composition.component_ids)
            source_ports = [
                ("$request", port)
                for port in request.required_interface.inputs
            ]
            source_ports.extend(
                (component_id, port)
                for component_id, method in methods.items()
                if component_id in component_ids
                for port in method.interface.outputs
            )
            signature_counts: dict[tuple[str, str, str], int] = {}
            for _component_id, port in source_ports:
                signature = self._method_port_signature(port)
                signature_counts[signature] = (
                    signature_counts.get(signature, 0) + 1
                )
            unique_sources: list[dict[str, Any]] = []
            for component_id, port in source_ports:
                if (
                    signature_counts[self._method_port_signature(port)]
                    != 1
                ):
                    continue
                source_body = {
                    "component_id": component_id,
                    "port": port.as_dict(),
                }
                unique_sources.append(
                    {
                        **source_body,
                        "source_id": (
                            f"source:{_digest(source_body)[:24]}"
                        ),
                        "symbol": f"source_{len(unique_sources)}",
                    }
                )
            used_work = sum(
                method.maximum_work
                for component_id, method in methods.items()
                if component_id in component_ids
            )
            maximum_work = request.maximum_work - used_work
            if not unique_sources or maximum_work < 1:
                continue
            assigned_members = {
                assignment.assignee_instance_id
                for assignment in assignments
                if assignment.request_id == request_id
            }
            eligible_members = [
                member_id
                for member_id in active_members
                if (
                    member_id in assigned_members
                    or len(assigned_members) < request.maximum_members
                )
            ]
            for member_id in eligible_members:
                history = outcomes_by_member[member_id]
                terminal = history["succeeded"] + history["failed"]
                reliability = (
                    history["succeeded"] + 1
                ) / (terminal + 2)
                body = {
                    "dispatch_id": dispatch_id,
                    "expected": expected.as_dict(),
                    "gap_sha256": _digest(gap),
                    "maximum_work": maximum_work,
                    "member_id": member_id,
                    "provider_outcomes": {
                        **history,
                        "reliability": reliability,
                    },
                    "request_id": request_id,
                    "role": request.desired_roles[0],
                    "sources": unique_sources,
                    "synthesis_id": synthesis_id,
                }
                opportunities.append(
                    {
                        **body,
                        "opportunity_sha256": _digest(body),
                    }
                )
        return sorted(
            opportunities,
            key=lambda row: (
                str(row["synthesis_id"]),
                str(row["gap_sha256"]),
                -float(row["provider_outcomes"]["reliability"]),
                str(row["member_id"]),
            ),
        )

    def _automatic_synthesis_candidate(
        self,
        root: ResearchResidency,
        *,
        dispatch: Mapping[str, Any],
        contribution_kind: str,
        contribution_id: str,
        method: ExecutableMethod,
        responses: Mapping[str, CollaborationResponse],
        translations: Mapping[str, RepresentationTranslation],
    ) -> CollectiveSynthesis | None:
        synthesis_id = _identifier(
            dispatch["synthesis_id"],
            "capability dispatch synthesis_id",
        )
        assessment = root._record(f"organism:synthesis:{synthesis_id}")
        if assessment is None:
            raise OrganismError("capability dispatch lacks its synthesis")
        synthesis = self._collective_synthesis_from_payload(
            assessment["payload"]
        )
        if synthesis.composition is None:
            return None
        request_record = root._record(
            f"organism:collaboration-request:{synthesis.request_id}"
        )
        if request_record is None:
            raise OrganismError(
                "capability dispatch lacks its collaboration request"
            )
        request = self._collaboration_request_from_payload(
            request_record["payload"]
        )
        spec = synthesis.composition
        component_ids = list(spec.component_ids)
        response_ids = list(synthesis.response_ids)
        translation_ids = list(synthesis.translation_ids)
        if contribution_kind == "response":
            if contribution_id not in response_ids:
                response_ids.append(contribution_id)
        elif contribution_kind == "translation":
            if contribution_id not in translation_ids:
                translation_ids.append(contribution_id)
        else:
            raise OrganismError("capability contribution kind is invalid")
        if contribution_id not in component_ids:
            component_ids.append(contribution_id)
        methods = self._synthesis_component_methods(
            CollectiveSynthesis(
                synthesis_id=synthesis.synthesis_id,
                request_id=synthesis.request_id,
                synthesizer_instance_id=synthesis.synthesizer_instance_id,
                response_ids=tuple(response_ids),
                translation_ids=tuple(translation_ids),
                result=synthesis.result,
                agreements=synthesis.agreements,
                disagreements=synthesis.disagreements,
                unresolved=synthesis.unresolved,
                composition=spec,
            ),
            responses,
            translations,
        )
        methods[contribution_id] = method
        connections = list(spec.connections)
        outputs = list(spec.outputs)
        connected_targets = {
            (item.target_component_id, item.target_port)
            for item in connections
        }
        source_ports: list[tuple[str, MethodPort]] = []
        if request.required_interface is not None:
            source_ports.extend(
                ("$request", port)
                for port in request.required_interface.inputs
            )
        source_ports.extend(
            (component_id, port)
            for component_id, component_method in methods.items()
            if component_id != contribution_id
            for port in component_method.interface.outputs
        )
        for input_port in method.interface.inputs:
            target = (contribution_id, input_port.name)
            if target in connected_targets:
                continue
            component_matches = [
                (source_component_id, source_port)
                for source_component_id, source_port in source_ports
                if (
                    source_component_id != "$request"
                    and self._ports_are_compatible(source_port, input_port)
                )
            ]
            request_matches = [
                (source_component_id, source_port)
                for source_component_id, source_port in source_ports
                if (
                    source_component_id == "$request"
                    and self._ports_are_compatible(source_port, input_port)
                )
            ]
            compatible = (
                component_matches
                if component_matches
                else request_matches
            )
            if len(compatible) != 1:
                return None
            source_component_id, source_port = compatible[0]
            connections.append(
                MethodConnection(
                    source_component_id,
                    source_port.name,
                    contribution_id,
                    input_port.name,
                )
            )
            connected_targets.add(target)
        resolved = False
        for gap in (dispatch["gap"],):
            expected = gap.get("expected")
            if not isinstance(expected, Mapping):
                continue
            try:
                expected_port = MethodPort.from_dict(expected)
            except (CollectiveHiveError, TypeError, ValueError):
                return None
            compatible_outputs = [
                port
                for port in method.interface.outputs
                if self._ports_are_compatible(port, expected_port)
            ]
            if len(compatible_outputs) != 1:
                continue
            source_port = compatible_outputs[0]
            if gap.get("kind") == "missing-output-binding":
                if any(
                    output.output_port == expected_port.name
                    for output in outputs
                ):
                    continue
                outputs.append(
                    MethodOutputBinding(
                        expected_port.name,
                        contribution_id,
                        source_port.name,
                    )
                )
                resolved = True
            elif gap.get("kind") == "missing-input-binding":
                target_component_id = gap.get("component_id")
                if (
                    not isinstance(target_component_id, str)
                    or target_component_id == contribution_id
                    or (target_component_id, expected_port.name)
                    in connected_targets
                ):
                    continue
                connections.append(
                    MethodConnection(
                        contribution_id,
                        source_port.name,
                        target_component_id,
                        expected_port.name,
                    )
                )
                connected_targets.add((target_component_id, expected_port.name))
                resolved = True
        if not resolved:
            return None
        try:
            baseline = compile_collaborative_method(
                request,
                tuple(
                    responses[response_id]
                    for response_id in synthesis.response_ids
                ),
                tuple(
                    translations[translation_id]
                    for translation_id in synthesis.translation_ids
                ),
                synthesis,
            )
        except (CollectiveHiveError, KeyError):
            return None
        candidate = CollectiveSynthesis(
            synthesis_id=synthesis.synthesis_id,
            request_id=synthesis.request_id,
            synthesizer_instance_id=synthesis.synthesizer_instance_id,
            response_ids=tuple(response_ids),
            translation_ids=tuple(translation_ids),
            result={
                **dict(synthesis.result),
                "capability_dispatch": {
                    "contribution_id": contribution_id,
                    "dispatch_id": dispatch["dispatch_id"],
                },
            },
            agreements=synthesis.agreements,
            disagreements=synthesis.disagreements,
            unresolved=synthesis.unresolved,
            composition=MethodCompositionSpec(
                program_id=spec.program_id,
                component_ids=tuple(component_ids),
                connections=tuple(connections),
                outputs=tuple(outputs),
                maximum_work=request.maximum_work,
                maximum_prefix_code_bits=spec.maximum_prefix_code_bits,
            ),
        )
        try:
            compiled = compile_collaborative_method(
                request,
                tuple(responses[response_id] for response_id in response_ids),
                tuple(
                    translations[translation_id]
                    for translation_id in translation_ids
                ),
                candidate,
            )
        except (CollectiveHiveError, KeyError):
            return None
        if len(compiled.gaps) >= len(baseline.gaps):
            return None
        return candidate

    def _reconcile_collective_capability_dispatches(
        self,
        *,
        response_id: str | None = None,
        translation_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if response_id is not None:
            response_id = _identifier(
                response_id,
                "capability response_id",
            )
        if translation_id is not None:
            translation_id = _identifier(
                translation_id,
                "capability translation_id",
            )
        candidates: list[
            tuple[
                str,
                str,
                str,
                CollectiveSynthesis,
            ]
        ] = []
        with self._open_residencies(include_members=False) as (root, _):
            responses, translations = self._collaboration_artifact_maps(root)
            for record_id, history in root._task()["records"].items():
                payload = history[-1].get("payload")
                if (
                    not record_id.startswith("organism:capability-dispatch:")
                    or not isinstance(payload, Mapping)
                    or payload.get("schema")
                    != COLLABORATIVE_CAPABILITY_DISPATCH_SCHEMA
                    or payload.get("state") != "assigned"
                ):
                    continue
                dispatch = _plain(payload)
                offer_payload = dispatch.get("offer")
                assignment = dispatch.get("assignment")
                if (
                    not isinstance(offer_payload, Mapping)
                    or not isinstance(assignment, Mapping)
                    or not isinstance(dispatch.get("assignment_id"), str)
                ):
                    continue
                provider_id = offer_payload.get("provider_instance_id")
                if not isinstance(provider_id, str):
                    continue
                possible: list[tuple[str, str, ExecutableMethod]] = []
                for response in responses.values():
                    if (
                        response.assignment_id == dispatch["assignment_id"]
                        and response.responder_instance_id == provider_id
                        and response.status in {"completed", "partial"}
                        and response.method is not None
                        and (
                            response_id is None
                            or response.response_id == response_id
                        )
                    ):
                        possible.append(
                            ("response", response.response_id, response.method)
                        )
                assessment = root._record(
                    f"organism:synthesis:{dispatch['synthesis_id']}"
                )
                if assessment is None:
                    continue
                synthesis = self._collective_synthesis_from_payload(
                    assessment["payload"]
                )
                for translation in translations.values():
                    if (
                        translation.translator_instance_id == provider_id
                        and translation.validation_status == "validated"
                        and translation.method is not None
                        and translation.source_response_id
                        in synthesis.response_ids
                        and (
                            translation_id is None
                            or translation.translation_id == translation_id
                        )
                    ):
                        possible.append(
                            (
                                "translation",
                                translation.translation_id,
                                translation.method,
                            )
                        )
                for kind, contribution_id, method in sorted(
                    possible,
                    key=lambda item: (item[0], item[1]),
                ):
                    candidate = self._automatic_synthesis_candidate(
                        root,
                        dispatch=dispatch,
                        contribution_kind=kind,
                        contribution_id=contribution_id,
                        method=method,
                        responses=responses,
                        translations=translations,
                    )
                    if candidate is not None:
                        candidates.append(
                            (
                                record_id,
                                kind,
                                contribution_id,
                                candidate,
                            )
                        )
                        break
        admitted: list[dict[str, Any]] = []
        for dispatch_id, kind, contribution_id, candidate in candidates:
            document_id = self.record_collective_synthesis(candidate)
            with self._open_residencies(include_members=False) as (root, _):
                dispatch = root._record(dispatch_id)
                if dispatch is None:
                    raise OrganismError(
                        "capability dispatch disappeared during reconciliation"
                    )
                payload = _plain(dispatch["payload"])
                if payload.get("state") == "assigned":
                    payload.update(
                        {
                            "admission_document_id": document_id,
                            "contribution": {
                                "id": contribution_id,
                                "kind": kind,
                            },
                            "state": "admitted",
                        }
                    )
                    self._put_capability_dispatch(
                        root,
                        record_id=dispatch_id,
                        payload=payload,
                    )
                admitted.append(
                    {
                        "contribution_id": contribution_id,
                        "dispatch_id": dispatch_id,
                        "state": "admitted",
                    }
                )
        return admitted

    def _wake_collective_method_continuations(
        self,
        synthesis_id: str,
    ) -> list[dict[str, Any]]:
        synthesis_id = _identifier(synthesis_id, "wake synthesis_id")
        with self._open_residencies(include_members=False) as (root, _):
            continuations = [
                row["continuation_id"]
                for row in self._collaboration_view(root)["continuations"]
                if (
                    row.get("synthesis_id") == synthesis_id
                    and row.get("status") == "ready"
                )
            ]
        return [
            self.resume_collective_method_continuation(continuation_id)
            for continuation_id in continuations
        ]

    def maintain_collective_capability_gaps(self) -> dict[str, Any]:
        """Recover routing and admitted completions after any interruption."""
        routed = self.dispatch_collective_capability_gaps()
        admitted = self._reconcile_collective_capability_dispatches()
        rerouted = self.dispatch_collective_capability_gaps()
        organized = self.organize_membership()
        return {
            "schema": COLLABORATIVE_CAPABILITY_DISPATCH_SCHEMA,
            "admitted": admitted,
            "routed": routed,
            "rerouted": rerouted,
            "organized": organized,
        }

    @staticmethod
    def _record_reference(record: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "content_version": int(record["content_version"]),
            "id": str(record["id"]),
            "kind": str(record["kind"]),
        }

    def _execute_collective_synthesis(
        self,
        root: ResearchResidency,
        *,
        synthesis_id: str,
        execution_id: str,
        bindings: Mapping[str, Any],
        expected_program_ref: Mapping[str, Any] | None = None,
        maximum_work: int | None = None,
    ) -> dict[str, Any]:
        synthesis_id = _identifier(synthesis_id, "synthesis_id")
        execution_id = _identifier(execution_id, "execution_id")
        normalized_bindings = _plain(bindings)
        if not isinstance(normalized_bindings, dict):
            raise OrganismError("collaborative method bindings must be a mapping")
        if len(canonical_json_bytes(normalized_bindings)) > _MAX_RESULT_BYTES:
            raise OrganismError("collaborative method bindings exceed their bound")
        gap = root._record(
            f"obligation:collaboration-capability-gap:{synthesis_id}"
        )
        if gap is not None and gap["payload"].get("state") == "open":
            raise OrganismError(
                "collective synthesis has unresolved capability gaps"
            )
        program_id = f"program:collaboration-synthesis:{synthesis_id}"
        program_record = root._record(program_id)
        if program_record is None:
            raise OrganismError(
                "collective synthesis has no executable resident program"
            )
        program_ref = self._record_reference(program_record)
        if (
            expected_program_ref is not None
            and _plain(expected_program_ref) != program_ref
        ):
            raise OrganismError(
                "collective continuation method changed after suspension"
            )
        payload = self._unwrap_program_record(program_record["payload"])
        method_payload = payload.get("method")
        if not isinstance(method_payload, Mapping):
            raise OrganismError(
                "collective synthesis resident program is malformed"
            )
        try:
            method = ExecutableMethod.from_dict(method_payload)
        except CollectiveHiveError as exc:
            raise OrganismError(
                "collective synthesis resident program is malformed"
            ) from exc
        if maximum_work is None:
            execution_work_bound = method.maximum_work
        elif (
            isinstance(maximum_work, bool)
            or not isinstance(maximum_work, int)
            or maximum_work < 1
        ):
            raise OrganismError("collaborative execution work bound is invalid")
        else:
            execution_work_bound = maximum_work
        if execution_work_bound < method.maximum_work:
            raise OrganismError(
                "collective method exceeds the declared execution work bound"
            )
        bindings_sha256 = _digest(normalized_bindings)
        method_sha256 = _digest(method.as_dict())
        record_id = f"event:collaboration-execution:{execution_id}"
        existing = root._record(record_id)
        if existing is not None:
            prior = _plain(existing["payload"])
            if (
                prior.get("schema") != COLLABORATIVE_METHOD_EXECUTION_SCHEMA
                or prior.get("bindings_sha256") != bindings_sha256
                or prior.get("method_sha256") != method_sha256
                or prior.get("program_ref") != program_ref
                or prior.get("synthesis_id") != synthesis_id
                or prior.get("maximum_work", method.maximum_work)
                != execution_work_bound
            ):
                raise OrganismError(
                    "collaborative execution identity was reused"
                )
            return prior
        try:
            outputs = method.execute(normalized_bindings)
        except CollectiveHiveError as exc:
            raise OrganismError(
                "collaborative method rejected its bindings"
            ) from exc
        receipt = {
            "schema": COLLABORATIVE_METHOD_EXECUTION_SCHEMA,
            "bindings": normalized_bindings,
            "bindings_sha256": bindings_sha256,
            "execution_id": execution_id,
            "maximum_work": execution_work_bound,
            "method_sha256": method_sha256,
            "outputs": _plain(outputs),
            "program_ref": program_ref,
            "synthesis_id": synthesis_id,
            "work": max(1, len(method.program.steps)),
        }
        if len(canonical_json_bytes(receipt)) > _MAX_RESULT_BYTES:
            raise OrganismError("collaborative method result exceeds its bound")
        self._write_record(
            root,
            record_id=record_id,
            kind="Event",
            payload=receipt,
            epistemic_kind="observed",
        )
        return receipt

    def execute_collective_synthesis(
        self,
        synthesis_id: str,
        execution_id: str,
        bindings: Mapping[str, Any],
        *,
        expected_program_ref: Mapping[str, Any] | None = None,
        maximum_work: int | None = None,
    ) -> dict[str, Any]:
        """Execute one resident collaborative method within its declared bound."""

        with self._open_residencies(include_members=False) as (root, _):
            return self._execute_collective_synthesis(
                root,
                synthesis_id=synthesis_id,
                execution_id=execution_id,
                bindings=bindings,
                expected_program_ref=expected_program_ref,
                maximum_work=maximum_work,
            )

    @staticmethod
    def _root_method_value_kind(value: Any) -> str:
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int):
            return "integer"
        if isinstance(value, float):
            return "scalar"
        if isinstance(value, str):
            return "text"
        if isinstance(value, Mapping):
            return "mapping"
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            if all(
                isinstance(item, (int, float))
                and not isinstance(item, bool)
                and math.isfinite(float(item))
                for item in value
            ):
                return "vector"
            return "sequence"
        return "json"

    @staticmethod
    def _root_method_authorship(root: ResearchResidency) -> dict[str, str]:
        identity = getattr(root.session, "identity", None)
        hive = getattr(root.session, "hive", None)
        owner_instance_id = getattr(identity, "instance_id", None)
        hive_id = getattr(hive, "hive_id", None)
        branch = getattr(hive, "branch", None)
        if any(
            not isinstance(value, str) or not value
            for value in (owner_instance_id, hive_id, branch)
        ):
            raise OrganismError("root field owner identity is unavailable")
        return {
            "owner_instance_id": owner_instance_id,
            "hive_id": hive_id,
            "branch": branch,
            "role": "root-research-brain",
        }

    @staticmethod
    def _root_method_sources(
        sources: Sequence[Mapping[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        if (
            not isinstance(sources, Sequence)
            or isinstance(sources, (str, bytes))
            or len(sources) > 64
        ):
            raise OrganismError("root research method sources are invalid")
        normalized: dict[str, dict[str, Any]] = {}
        required_identity = {
            "program_id",
            "key",
            "kind",
            "version",
            "source_refs",
            "dependencies",
            "value_sha256",
        }
        for raw in sources:
            if not isinstance(raw, Mapping):
                raise OrganismError("root research method source is malformed")
            source_id = _identifier(raw.get("source_id"), "root method source_id")
            identity = _plain(raw.get("identity"))
            value = _plain(raw.get("value"))
            if (
                not isinstance(identity, dict)
                or set(identity) != required_identity
                or not isinstance(identity.get("program_id"), str)
                or not isinstance(identity.get("key"), str)
                or not isinstance(identity.get("kind"), str)
                or not isinstance(identity.get("source_refs"), list)
                or not isinstance(identity.get("dependencies"), list)
                or identity.get("value_sha256") != _digest(value)
                or source_id != _digest(identity)
            ):
                raise OrganismError(
                    "root research method source identity does not match its value"
                )
            _identifier(identity["program_id"], "root method source program_id")
            _text(identity["key"], "root method source key", maximum=512)
            _text(identity["kind"], "root method source kind", maximum=128)
            field_revision = raw.get("field_revision")
            if field_revision is not None:
                _text(
                    field_revision,
                    "root method source field_revision",
                    maximum=128,
                )
            entry = {
                "source_id": source_id,
                "identity": identity,
                "field_revision": field_revision,
                "value": value,
            }
            prior = normalized.get(source_id)
            if prior is not None and prior != entry:
                raise OrganismError("root research method source identity collides")
            normalized[source_id] = entry
        if len(canonical_json_bytes(normalized)) > _MAX_RESULT_BYTES:
            raise OrganismError("root research method sources exceed their bound")
        return dict(sorted(normalized.items()))

    def root_research_method_perspective(
        self,
        *,
        program_id: str,
        sources: Sequence[Mapping[str, Any]],
        maximum: int = 8,
    ) -> dict[str, Any]:
        """Return retained root methods whose exact input sources are still current."""
        program_id = _identifier(program_id, "research program_id")
        if (
            isinstance(maximum, bool)
            or not isinstance(maximum, int)
            or not 1 <= maximum <= 32
        ):
            raise OrganismError("root research method maximum is invalid")
        current_sources = self._root_method_sources(sources)
        if any(
            source["identity"]["program_id"] != program_id
            for source in current_sources.values()
        ):
            raise OrganismError(
                "root research method sources belong to another program"
            )
        methods: list[dict[str, Any]] = []
        with self._open_residencies(include_members=False) as (root, _):
            root_authorship = self._root_method_authorship(root)
            records = root._task().get("records", {})
            if not isinstance(records, Mapping):
                raise OrganismError("root research method field records are malformed")
            for record_id in sorted(records):
                if not isinstance(record_id, str) or not record_id.startswith(
                    "program:root-research-method:"
                ):
                    continue
                record = root._record(record_id)
                if record is None or record.get("status") != "active":
                    continue
                payload = self._unwrap_program_record(record.get("payload", {}))
                if not isinstance(payload, Mapping):
                    continue
                if (
                    payload.get("schema") != ROOT_RESEARCH_METHOD_SCHEMA
                    or payload.get("program_id") != program_id
                    or payload.get("state") != "retained"
                    or payload.get("authorship") != root_authorship
                ):
                    continue
                method_payload = payload.get("method")
                if not isinstance(method_payload, Mapping):
                    raise OrganismError("retained root research method is malformed")
                try:
                    method = ExecutableMethod.from_dict(method_payload)
                except CollectiveHiveError as exc:
                    raise OrganismError(
                        "retained root research method is malformed"
                    ) from exc
                method_sha256 = _digest(method.as_dict())
                if payload.get("method_sha256") != method_sha256:
                    raise OrganismError(
                        "retained root research method digest is inconsistent"
                    )
                input_sources = payload.get("input_sources")
                source_observations = payload.get("source_observations")
                if (
                    not isinstance(input_sources, Mapping)
                    or set(input_sources)
                    != {port.name for port in method.interface.inputs}
                    or not isinstance(source_observations, Mapping)
                ):
                    raise OrganismError(
                        "retained root research method source bindings are malformed"
                    )
                required_ids = {
                    str(source_id) for source_id in input_sources.values()
                }
                if not required_ids:
                    continue
                if any(
                    source_id not in current_sources
                    or source_id not in source_observations
                    or not isinstance(source_observations[source_id], Mapping)
                    or source_observations[source_id].get("identity")
                    != current_sources[source_id]["identity"]
                    for source_id in required_ids
                ):
                    continue
                candidate: dict[str, Any] = {
                    "method_id": payload["method_id"],
                    "method_sha256": method_sha256,
                    "program_id": program_id,
                    "program_ref": self._record_reference(record),
                    "summary": payload["summary"],
                    "origin_question_id": payload["question_id"],
                    "origin_question": payload["question"],
                    "source_ids": sorted(required_ids),
                    "source_identity_sha256": payload[
                        "source_identity_sha256"
                    ],
                    "input_ports": [
                        port.as_dict() for port in method.interface.inputs
                    ],
                    "output_ports": [
                        port.as_dict() for port in method.interface.outputs
                    ],
                    "maximum_work": method.maximum_work,
                    "work": len(method.program.steps),
                }
                candidate["candidate_sha256"] = _digest(candidate)
                methods.append(candidate)
                if len(methods) >= maximum:
                    break
        return {
            "schema": ROOT_RESEARCH_METHOD_SCHEMA,
            "program_id": program_id,
            "methods": methods,
            "method_count": len(methods),
        }

    @staticmethod
    def _root_method_from_proposal(
        proposal: Mapping[str, Any],
        *,
        program_id: str,
        question_id: str,
        question: str,
        sources: Mapping[str, Mapping[str, Any]],
    ) -> tuple[str, dict[str, Any], ExecutableMethod, dict[str, Any]]:
        normalized = _plain(proposal)
        expected = {
            "schema",
            "summary",
            "source_ids",
            "steps",
            "assumptions",
            "preconditions",
            "effects",
            "uncertainty",
        }
        if not isinstance(normalized, dict) or set(normalized) != expected:
            raise OrganismError("root research method proposal is malformed")
        if normalized.get("schema") != ROOT_RESEARCH_METHOD_PROPOSAL_SCHEMA:
            raise OrganismError("root research method proposal schema is invalid")
        summary = _text(
            normalized.get("summary"),
            "root research method summary",
            maximum=512,
        )
        source_ids = normalized.get("source_ids")
        raw_steps = normalized.get("steps")
        if (
            not isinstance(source_ids, list)
            or not 1 <= len(source_ids) <= 8
            or any(
                not isinstance(source_id, str) or source_id not in sources
                for source_id in source_ids
            )
            or len(set(source_ids)) != len(source_ids)
            or not isinstance(raw_steps, list)
            or not 1 <= len(raw_steps) <= 32
        ):
            raise OrganismError(
                "root research method sources or steps exceed their bound"
            )
        for name in ("assumptions", "preconditions", "effects"):
            values = normalized.get(name)
            if (
                not isinstance(values, list)
                or len(values) > 8
                or any(
                    not isinstance(value, str)
                    or not value.strip()
                    or len(value.encode("utf-8")) > 512
                    for value in values
                )
            ):
                raise OrganismError(
                    f"root research method {name} are malformed"
                )
        uncertainty = normalized.get("uncertainty")
        if (
            isinstance(uncertainty, bool)
            or not isinstance(uncertainty, (int, float))
            or not math.isfinite(float(uncertainty))
            or not 0.0 <= float(uncertainty) <= 1.0
        ):
            raise OrganismError("root research method uncertainty is invalid")
        try:
            steps: list[PrimitiveStep] = []
            for raw_step in raw_steps:
                if (
                    not isinstance(raw_step, Mapping)
                    or set(raw_step)
                    != {"operation", "output", "inputs", "literal"}
                ):
                    raise OrganismError(
                        "root research method step is malformed"
                    )
                step = PrimitiveStep.from_dict(dict(raw_step))
                if step.operation not in {"constant", "convert"} and (
                    step.literal is not None
                ):
                    raise OrganismError(
                        "root research method step has an unused literal"
                    )
                steps.append(step)
            field_program = FieldProgram(
                program_id="field-research-method:"
                + _digest(
                    {
                        "program_id": program_id,
                        "question_id": question_id,
                        "question_sha256": _digest(question),
                        "proposal": normalized,
                    }
                )[:32],
                version=1,
                roles=tuple(source_ids),
                steps=tuple(steps),
                outputs=(steps[-1].output,),
                status="candidate",
            )
            interface = MethodInterface(
                inputs=tuple(
                    MethodPort(
                        name=source_id,
                        value_kind=ResearchOrganism._root_method_value_kind(
                            sources[source_id]["value"]
                        ),
                        representation=str(
                            sources[source_id]["identity"]["kind"]
                        ),
                        unit="1",
                        symbol=source_id,
                    )
                    for source_id in source_ids
                ),
                outputs=(
                    MethodPort(
                        name=steps[-1].output,
                        value_kind="json",
                        representation="field-program-result",
                        unit="1",
                        symbol=steps[-1].output,
                    ),
                ),
            )
            method = ExecutableMethod(
                program=field_program,
                interface=interface,
                assumptions=tuple(
                    {"statement": item} for item in normalized["assumptions"]
                ),
                preconditions=tuple(
                    {"statement": item}
                    for item in normalized["preconditions"]
                ),
                effects=tuple(normalized["effects"]),
                maximum_work=len(steps),
                uncertainty=float(uncertainty),
            )
        except (CollectiveHiveError, FieldIntelligenceError, KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, OrganismError):
                raise
            raise OrganismError(
                "root research method failed typed Hive admission"
            ) from exc
        used_source_ids = [str(source_id) for source_id in source_ids]
        source_observations = {
            source_id: {
                "identity": _plain(sources[source_id]["identity"]),
            }
            for source_id in used_source_ids
        }
        source_identity_sha256 = _digest(
            {
                source_id: source_observations[source_id]["identity"]
                for source_id in sorted(used_source_ids)
            }
        )
        proposal_sha256 = _digest(normalized)
        method_id = "root-research-method:" + _digest(
            {
                "program_id": program_id,
                "question_id": question_id,
                "question_sha256": _digest(question),
                "proposal_sha256": proposal_sha256,
                "source_identity_sha256": source_identity_sha256,
            }
        )[:32]
        method_payload = method.as_dict()
        method_sha256 = _digest(method_payload)
        payload = {
            "schema": ROOT_RESEARCH_METHOD_SCHEMA,
            "program_role": "root-authored-research-method",
            "state": "retained",
            "method_id": method_id,
            "method_sha256": method_sha256,
            "method": method_payload,
            "summary": summary,
            "program_id": program_id,
            "question_id": question_id,
            "question": question,
            "question_sha256": _digest(question),
            "source_identity_sha256": source_identity_sha256,
            "source_observations": source_observations,
            "input_sources": {
                source_id: source_id for source_id in used_source_ids
            },
            "proposal_sha256": proposal_sha256,
            "authorship": {
                "owner_instance_id": None,
                "hive_id": "main",
                "branch": "main",
                "role": "root-research-brain",
            },
        }
        return method_id, payload, method, source_observations

    def _execute_root_research_method(
        self,
        root: ResearchResidency,
        *,
        method_record: Mapping[str, Any],
        operation_id: str,
        program_id: str,
        question_id: str,
        question: str,
        sources: Mapping[str, Mapping[str, Any]],
        prepared_outputs: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        operation_id = _identifier(operation_id, "root method operation_id")
        payload = self._unwrap_program_record(method_record.get("payload", {}))
        if payload.get("schema") != ROOT_RESEARCH_METHOD_SCHEMA:
            raise OrganismError("root research method Program is malformed")
        method_payload = payload.get("method")
        if not isinstance(method_payload, Mapping):
            raise OrganismError("root research method has no typed method")
        try:
            method = ExecutableMethod.from_dict(method_payload)
        except CollectiveHiveError as exc:
            raise OrganismError("root research method Program is malformed") from exc
        method_sha256 = _digest(method.as_dict())
        if (
            payload.get("method_sha256") != method_sha256
            or payload.get("program_id") != program_id
        ):
            raise OrganismError("root research method identity changed")
        input_sources = payload.get("input_sources")
        source_observations = payload.get("source_observations")
        if (
            not isinstance(input_sources, Mapping)
            or set(input_sources) != {port.name for port in method.interface.inputs}
            or not isinstance(source_observations, Mapping)
            or any(
                not isinstance(source_id, str) or source_id not in source_observations
                for source_id in input_sources.values()
            )
        ):
            raise OrganismError("root research method source bindings are malformed")
        if payload.get("authorship") != self._root_method_authorship(root):
            raise OrganismError("root research method belongs to another field owner")
        bindings: dict[str, Any] = {}
        source_ids = sorted(set(input_sources.values()))
        source_provenance: dict[str, Any] = {}
        for source_id in source_ids:
            stored = source_observations.get(source_id)
            if (
                not isinstance(stored, Mapping)
                or not isinstance(stored.get("identity"), Mapping)
            ):
                raise OrganismError(
                    "root research method source observations are malformed"
                )
            source_provenance[source_id] = {
                "identity_sha256": _digest(stored["identity"]),
                "source_refs": _plain(stored["identity"]["source_refs"]),
                "dependencies": _plain(stored["identity"]["dependencies"]),
            }
        for port in method.interface.inputs:
            source_id = input_sources.get(port.name)
            if not isinstance(source_id, str) or source_id not in sources:
                raise OrganismError(
                    "root research method requires an unavailable source"
                )
            stored = source_observations.get(source_id)
            if (
                not isinstance(stored, Mapping)
                or stored.get("identity") != sources[source_id]["identity"]
            ):
                raise OrganismError(
                    "root research method source identity is stale"
                )
            bindings[port.name] = sources[source_id]["value"]
        if len(canonical_json_bytes(bindings)) > _MAX_RESULT_BYTES:
            raise OrganismError("root research method bindings exceed their bound")
        source_identity_sha256 = _digest(
            {
                source_id: source_observations[source_id]["identity"]
                for source_id in source_ids
            }
        )
        if payload.get("source_identity_sha256") != source_identity_sha256:
            raise OrganismError("root research method source digest is inconsistent")
        program_ref = self._record_reference(method_record)
        record_id = f"event:root-research-method-execution:{operation_id}"
        question_sha256 = _digest(question)
        execution_identity = {
            "schema": ROOT_RESEARCH_METHOD_EXECUTION_SCHEMA,
            "operation_id": operation_id,
            "method_id": payload["method_id"],
            "method_sha256": method_sha256,
            "research_program_id": program_id,
            "question_id": question_id,
            "question": question,
            "question_sha256": question_sha256,
            "source_identity_sha256": source_identity_sha256,
            "source_ids": source_ids,
            "source_provenance": source_provenance,
            "bindings_sha256": _digest(bindings),
            "program_ref": program_ref,
            "maximum_work": method.maximum_work,
            "work": len(method.program.steps),
            "support_status": "supported",
        }
        existing = root._record(record_id)
        if existing is not None:
            prior = _plain(existing.get("payload", {}))
            if any(
                prior.get(key) != value
                for key, value in execution_identity.items()
            ):
                raise OrganismError(
                    "root research method execution identity was reused"
                )
            outputs = prior.get("outputs")
            if not isinstance(outputs, Mapping):
                raise OrganismError("root research method execution is malformed")
            execution_payload = prior
            execution_record = existing
        else:
            try:
                outputs = (
                    _plain(prepared_outputs)
                    if prepared_outputs is not None
                    else _plain(method.execute(bindings))
                )
            except CollectiveHiveError as exc:
                raise OrganismError(
                    "root research method rejected its typed bindings"
                ) from exc
            execution_payload = {
                **execution_identity,
                "outputs": outputs,
            }
            if len(canonical_json_bytes(execution_payload)) > _MAX_RESULT_BYTES:
                raise OrganismError(
                    "root research method execution exceeds its result bound"
                )
            self._write_record(
                root,
                record_id=record_id,
                kind="Event",
                payload=execution_payload,
                epistemic_kind="observed",
            )
            execution_record = root._record(record_id)
            if execution_record is None:
                raise OrganismError("root research method execution was not recorded")
        execution_ref = self._record_reference(execution_record)
        output_observations = [
            {
                "subject": f"{operation_id}:output:{name}",
                "attribute": "root-research-method-output",
                "value": {"sha256": _digest(value)},
                "frame": {
                    "method_id": payload["method_id"],
                    "method_sha256": method_sha256,
                    "program_ref": program_ref,
                },
            }
            for name, value in sorted(outputs.items())
        ]
        residency_result = {
            "status": "supported",
            "summary": (
                f"Executed retained root research method {payload['method_id']}."
            ),
            "outputs": _plain(outputs),
            "observations": output_observations,
            "evidence": {
                **execution_identity,
                "execution_event_ref": execution_ref,
            },
        }
        assessment = root.record_root_method_assessment(
            operation_id,
            result=residency_result,
            program_ref=program_ref,
            execution_event_ref=execution_ref,
        )
        return {
            **residency_result,
            "schema": ROOT_RESEARCH_METHOD_EXECUTION_SCHEMA,
            "method_id": payload["method_id"],
            "method_sha256": method_sha256,
            "program_ref": program_ref,
            "execution_event_ref": execution_ref,
            "assessment": assessment,
        }

    def create_root_research_method(
        self,
        *,
        operation_id: str,
        program_id: str,
        question_id: str,
        question: str,
        proposal: Mapping[str, Any],
        sources: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        """Admit and execute one bounded method authored by the root research brain."""
        operation_id = _identifier(operation_id, "root method operation_id")
        program_id = _identifier(program_id, "research program_id")
        question_id = _identifier(question_id, "research question_id")
        question = _text(question, "research method question", maximum=2_000)
        current_sources = self._root_method_sources(sources)
        if not current_sources:
            raise OrganismError("root research method requires selected source records")
        if any(
            source["identity"]["program_id"] != program_id
            for source in current_sources.values()
        ):
            raise OrganismError(
                "root research method sources belong to another program"
            )
        if len(canonical_json_bytes(proposal)) > 65_536:
            raise OrganismError("root research method proposal exceeds its bound")
        method_id, payload, method, source_observations = (
            self._root_method_from_proposal(
                proposal,
                program_id=program_id,
                question_id=question_id,
                question=question,
                sources=current_sources,
            )
        )
        record_id = f"program:{method_id}"
        with self._open_residencies(include_members=False) as (root, _):
            payload["authorship"] = self._root_method_authorship(root)
            existing = root._record(record_id)
            prepared_outputs: Mapping[str, Any] | None = None
            if existing is not None:
                prior = self._unwrap_program_record(existing.get("payload", {}))
                if prior != payload:
                    raise OrganismError(
                        "root research method identity was reused"
                    )
            else:
                bindings = {
                    port.name: current_sources[
                        payload["input_sources"][port.name]
                    ]["value"]
                    for port in method.interface.inputs
                }
                try:
                    prepared_outputs = _plain(method.execute(bindings))
                except CollectiveHiveError as exc:
                    raise OrganismError(
                        "root research method rejected its typed bindings"
                    ) from exc
                self._write_record(
                    root,
                    record_id=record_id,
                    kind="Program",
                    payload=payload,
                    epistemic_kind="asserted",
                )
                existing = root._record(record_id)
                if existing is None:
                    raise OrganismError("root research method was not admitted")
            return self._execute_root_research_method(
                root,
                method_record=existing,
                operation_id=operation_id,
                program_id=program_id,
                question_id=question_id,
                question=question,
                sources=current_sources,
                prepared_outputs=prepared_outputs,
            )

    def execute_retained_root_research_method(
        self,
        *,
        method_id: str,
        method_sha256: str,
        operation_id: str,
        program_id: str,
        question_id: str,
        question: str,
        sources: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        """Execute an exact retained root method against its unchanged inputs."""
        method_id = _identifier(method_id, "root research method_id")
        method_sha256 = _identifier(
            method_sha256, "root research method_sha256"
        )
        if len(method_sha256) != 64:
            raise OrganismError("root research method digest is invalid")
        operation_id = _identifier(operation_id, "root method operation_id")
        program_id = _identifier(program_id, "research program_id")
        question_id = _identifier(question_id, "research question_id")
        question = _text(question, "research method question", maximum=2_000)
        current_sources = self._root_method_sources(sources)
        if not method_id.startswith("root-research-method:"):
            raise OrganismError("root research method identity is invalid")
        with self._open_residencies(include_members=False) as (root, _):
            record = root._record(f"program:{method_id}")
            if record is None or record.get("status") != "active":
                raise OrganismError("retained root research method is unavailable")
            payload = self._unwrap_program_record(record.get("payload", {}))
            if (
                payload.get("schema") != ROOT_RESEARCH_METHOD_SCHEMA
                or payload.get("method_id") != method_id
                or payload.get("method_sha256") != method_sha256
                or payload.get("program_id") != program_id
                or payload.get("state") != "retained"
            ):
                raise OrganismError("retained root research method identity changed")
            return self._execute_root_research_method(
                root,
                method_record=record,
                operation_id=operation_id,
                program_id=program_id,
                question_id=question_id,
                question=question,
                sources=current_sources,
            )

    @staticmethod
    def _root_guest_kind(value: Any) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "bool"
        if isinstance(value, (int, float)):
            return "number"
        if isinstance(value, str):
            return "string"
        if isinstance(value, list):
            return "list"
        if isinstance(value, dict):
            return "dict"
        raise OrganismError("guest method source is not a JSON value")

    def _root_guest_proposal(
        self,
        proposal: Mapping[str, Any],
        sources: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any]:
        if not isinstance(proposal, Mapping):
            raise OrganismError("root guest method proposal is malformed")
        candidate = _plain(proposal)
        if set(candidate) != {
            "schema", "summary", "source_ids", "source", "assumptions",
            "preconditions", "effects", "uncertainty",
        } or candidate["schema"] != ROOT_GUEST_METHOD_PROPOSAL_SCHEMA:
            raise OrganismError("root guest method proposal schema is invalid")
        _text(candidate["summary"], "root guest summary", maximum=512)
        code = candidate["source"]
        if not isinstance(code, str) or not code.strip() or len(code.encode("utf-8")) > 65_536:
            raise OrganismError("root guest source must be nonempty and at most 65536 bytes")
        ids = candidate["source_ids"]
        if (
            not isinstance(ids, list) or not 1 <= len(ids) <= 8
            or any(not isinstance(item, str) or item not in sources for item in ids)
            or len(set(ids)) != len(ids)
        ):
            raise OrganismError("root guest source_ids must name 1..8 distinct selected sources")
        for key in ("assumptions", "preconditions", "effects"):
            values = candidate[key]
            if not isinstance(values, list) or len(values) > 8:
                raise OrganismError(f"root guest {key} is malformed")
            for item in values:
                _text(item, f"root guest {key}", maximum=512)
        uncertainty = candidate["uncertainty"]
        if (
            isinstance(uncertainty, bool)
            or not isinstance(uncertainty, (int, float))
            or not math.isfinite(float(uncertainty))
            or not 0 <= float(uncertainty) <= 1
        ):
            raise OrganismError("root guest uncertainty is invalid")
        return candidate

    @staticmethod
    def _supported_root_guest_methods(
        root: ResearchResidency,
    ) -> set[tuple[str, str, str, int]]:
        """Identify methods supported by an assessment of their origin execution."""
        supported: set[tuple[str, str, str, int]] = set()
        for assessment_id in root._task().get("records", {}):
            if not str(assessment_id).startswith("research:root-method-assessment:"):
                continue
            assessment = root._record(assessment_id)
            if assessment is None or assessment.get("status") != "active":
                continue
            payload = assessment.get("payload", {})
            if not isinstance(payload, Mapping):
                continue
            method_id = payload.get("method_id")
            method_sha256 = payload.get("method_sha256")
            program_ref = payload.get("program_ref")
            event_ref = payload.get("execution_event_ref")
            if (
                payload.get("schema") != "cassifi.research-residency-root-method-assessment.v1"
                or payload.get("status") != "supported"
                or not isinstance(method_id, str)
                or not isinstance(method_sha256, str)
                or not isinstance(program_ref, Mapping)
                or program_ref.get("id") != "program:" + method_id
                or program_ref.get("kind") != "Program"
                or not isinstance(program_ref.get("content_version"), int)
                or not isinstance(event_ref, Mapping)
            ):
                continue
            method_record = root._record(program_ref["id"])
            event = root._record(event_ref.get("id")) if isinstance(event_ref.get("id"), str) else None
            if (
                method_record is None or method_record.get("status") != "active"
                or event is None or event.get("status") != "active"
                or any(method_record.get(key) != program_ref.get(key) for key in ("id", "kind", "content_version"))
                or any(event.get(key) != event_ref.get(key) for key in ("id", "kind", "content_version"))
            ):
                continue
            method_payload = ResearchOrganism._unwrap_program_record(method_record.get("payload", {}))
            event_payload = event.get("payload", {})
            identity = event_payload.get("identity", {})
            if (
                method_payload.get("schema") != ROOT_GUEST_METHOD_SCHEMA
                or method_payload.get("method_id") != method_id
                or method_payload.get("method_sha256") != method_sha256
                or payload.get("research_program_id") != method_payload.get("program_id")
                or event_payload.get("status") != "completed"
                or identity.get("schema") != ROOT_GUEST_EXECUTION_SCHEMA
                or identity.get("method_id") != method_id
                or identity.get("method_sha256") != method_sha256
                or identity.get("program_id") != method_payload.get("program_id")
                or identity.get("program_ref") != program_ref
            ):
                continue
            supported.add((method_id, method_sha256, program_ref["id"], program_ref["content_version"]))
        return supported

    def root_guest_method_perspective(
        self,
        program_id: str,
        sources: Sequence[Mapping[str, Any]],
        maximum: int = 8,
    ) -> dict[str, Any]:
        program_id = _identifier(program_id, "research program_id")
        if isinstance(maximum, bool) or not isinstance(maximum, int) or not 1 <= maximum <= 32:
            raise OrganismError("root guest maximum is invalid")
        current = self._root_method_sources(sources)
        if any(row["identity"]["program_id"] != program_id for row in current.values()):
            raise OrganismError("root guest sources belong to another program")
        kinds = [self._root_guest_kind(row["value"]) for row in current.values()]
        methods: list[dict[str, Any]] = []
        with self._open_residencies(include_members=False) as (root, _):
            authorship = self._root_method_authorship(root)
            records = root._task().get("records", {})
            supported = self._supported_root_guest_methods(root)
            for record_id in sorted(records):
                if not str(record_id).startswith("program:root-guest-method:"):
                    continue
                record = root._record(record_id)
                if record is None or record.get("status") != "active":
                    continue
                payload = self._unwrap_program_record(record.get("payload", {}))
                if (
                    payload.get("schema") != ROOT_GUEST_METHOD_SCHEMA
                    or not isinstance(payload.get("program_id"), str)
                    or payload.get("authorship") != authorship
                ):
                    continue
                self._validate_root_guest_record(payload)
                program_ref = self._record_reference(record)
                if (
                    payload["method_id"], payload["method_sha256"],
                    program_ref["id"], program_ref["content_version"],
                ) not in supported:
                    continue
                if any(payload["input_signature"].count(kind) > kinds.count(kind)
                       for kind in set(payload["input_signature"])):
                    continue
                row = {
                    "method_id": payload["method_id"],
                    "method_sha256": payload["method_sha256"],
                    "program_id": payload["program_id"],
                    "program_ref": program_ref,
                    "summary": payload["summary"],
                    "input_names": payload["input_names"],
                    "input_signature": payload["input_signature"],
                    "source_ids": payload["origin_source_ids"],
                    "origin_question_id": payload["question_id"],
                    "assumptions": payload["assumptions"],
                    "preconditions": payload["preconditions"],
                    "effects": payload["effects"],
                    "uncertainty": payload["uncertainty"],
                }
                row["candidate_sha256"] = _digest(row)
                methods.append(row)
                if len(methods) >= maximum:
                    break
        return {
            "schema": ROOT_GUEST_METHOD_SCHEMA,
            "program_id": program_id,
            "methods": methods,
            "method_count": len(methods),
        }

    @staticmethod
    def _validate_root_guest_record(payload: Mapping[str, Any]) -> None:
        code = payload.get("source")
        names = payload.get("input_names")
        kinds = payload.get("input_signature")
        if (
            not isinstance(code, str) or not code.strip()
            or len(code.encode("utf-8")) > 65_536
            or payload.get("source_sha256") != hashlib.sha256(code.encode("utf-8")).hexdigest()
            or not isinstance(names, list) or not 1 <= len(names) <= 8
            or names != [f"input_{index}" for index in range(len(names))]
            or not isinstance(kinds, list) or len(kinds) != len(names)
            or any(kind not in {"number", "string", "bool", "list", "dict", "null"} for kind in kinds)
            or not isinstance(payload.get("origin_sources"), Mapping)
            or not isinstance(payload.get("authorship"), Mapping)
        ):
            raise OrganismError("retained root guest method is malformed")
        digest_payload = {
            key: payload[key] for key in (
                "source", "source_sha256", "input_names", "input_signature",
                "origin_source_ids", "origin_sources", "program_id", "question_id",
                "question", "summary", "assumptions", "preconditions", "effects",
                "uncertainty", "authorship",
            )
        }
        if "produced_by" in payload:
            produced_by = payload["produced_by"]
            if (
                not isinstance(produced_by, Mapping)
                or set(produced_by) != {
                    "generator_method_id", "generator_method_sha256",
                    "generator_program_ref", "generator_execution_event_ref",
                    "output_sha256",
                }
                or any(
                    not isinstance(produced_by[key], str)
                    or not produced_by[key]
                    for key in ("generator_method_id", "generator_method_sha256", "output_sha256")
                )
                or any(
                    not isinstance(produced_by[key], Mapping)
                    or set(produced_by[key]) != {"id", "kind", "content_version"}
                    or produced_by[key]["kind"] != kind
                    or not isinstance(produced_by[key]["content_version"], int)
                    or produced_by[key]["content_version"] < 1
                    for key, kind in (
                        ("generator_program_ref", "Program"),
                        ("generator_execution_event_ref", "Event"),
                    )
                )
                or any(
                    not isinstance(produced_by[key], str)
                    or not re.fullmatch(r"[0-9a-f]{64}", produced_by[key])
                    for key in ("generator_method_sha256", "output_sha256")
                )
                or produced_by["generator_program_ref"]["id"]
                != "program:" + produced_by["generator_method_id"]
            ):
                raise OrganismError("retained root guest method provenance is malformed")
            digest_payload["produced_by"] = _plain(produced_by)
        method_sha = _digest(digest_payload)
        if (
            payload.get("method_sha256") != method_sha
            or payload.get("method_id") != "root-guest-method:" + method_sha[:32]
            or not isinstance(payload.get("program_id"), str)
            or not isinstance(payload.get("origin_source_ids"), list)
            or len(payload["origin_source_ids"]) != len(names)
            or any(not isinstance(source_id, str) for source_id in payload["origin_source_ids"])
            or len(set(payload["origin_source_ids"])) != len(names)
            or set(payload["origin_source_ids"]) != set(payload["origin_sources"])
            or any(
                not isinstance(source_id, str)
                or not isinstance(payload["origin_sources"][source_id], Mapping)
                or not isinstance(payload["origin_sources"][source_id].get("identity"), Mapping)
                or payload["origin_sources"][source_id]["identity"].get("program_id") != payload["program_id"]
                or _digest(payload["origin_sources"][source_id]["identity"]) != source_id
                for source_id in payload["origin_source_ids"]
            )
        ):
            raise OrganismError("retained root guest method digest or origin is inconsistent")

    def _execute_root_guest_method(
        self,
        root: ResearchResidency,
        *,
        method_record: Mapping[str, Any],
        payload: Mapping[str, Any],
        operation_id: str,
        program_id: str,
        question_id: str,
        question: str,
        sources: Mapping[str, Mapping[str, Any]],
        bindings: Mapping[str, str],
        runtime: Any,
        member_id: str,
    ) -> dict[str, Any]:
        from programs.python.runtime import RuntimeError as GuestRuntimeError, read_global

        names = payload["input_names"]
        if not isinstance(bindings, Mapping) or set(bindings) != set(names):
            raise OrganismError("root guest input bindings are incomplete")
        if len(set(bindings.values())) != len(names):
            raise OrganismError("root guest input bindings must be distinct")
        for name, kind in zip(names, payload["input_signature"]):
            source_id = bindings[name]
            if not isinstance(source_id, str) or source_id not in sources:
                raise OrganismError("root guest input source is not selected")
            if self._root_guest_kind(sources[source_id]["value"]) != kind:
                raise OrganismError("root guest input source kind is incompatible")
        program_ref = self._record_reference(method_record)
        source_ids = [bindings[name] for name in names]
        provenance = {
            source_id: {
                "identity_sha256": _digest(sources[source_id]["identity"]),
                "source_refs": sources[source_id]["identity"]["source_refs"],
                "dependencies": sources[source_id]["identity"]["dependencies"],
                "field_revision": sources[source_id]["field_revision"],
            }
            for source_id in source_ids
        }
        event_id = f"event:root-guest-method-execution:{operation_id}"
        identity = {
            "schema": ROOT_GUEST_EXECUTION_SCHEMA,
            "operation_id": operation_id,
            "method_id": payload["method_id"],
            "method_sha256": payload["method_sha256"],
            "program_id": program_id,
            "question_id": question_id,
            "question": question,
            "question_sha256": _digest(question),
            "bindings": dict(bindings),
            "source_ids": source_ids,
            "source_provenance": provenance,
            "source_identity_sha256": _digest(provenance),
            "program_ref": program_ref,
            "member_id": member_id,
        }
        if program_id != payload["program_id"]:
            identity["origin_program_id"] = payload["program_id"]
        existing = root._record(event_id)
        if existing is not None:
            prior = existing.get("payload", {})
            if not isinstance(prior, Mapping) or prior.get("identity") != identity:
                raise OrganismError("root guest operation identity was reused")
        else:
            self._write_record(
                root, record_id=event_id, kind="Event",
                payload={"identity": identity, "status": "pending"},
                epistemic_kind="observed",
            )
        task_id = "root-guest:" + hashlib.sha256(operation_id.encode("utf-8")).hexdigest()[:32]
        if existing is not None and existing["payload"].get("status") in {"faulted", "cancelled"}:
            return {
                "status": existing["payload"]["status"],
                "method_id": payload["method_id"],
                "method_sha256": payload["method_sha256"],
                "task_id": task_id,
                "program_ref": program_ref,
                "execution_event_ref": self._record_reference(existing),
                "unfinished_reason": existing["payload"].get("reason"),
            }
        if existing is None or existing["payload"].get("status") != "completed":
            # The scheduler compares the full initial guest state digest on
            # duplicate task IDs, including the exact admitted input values.
            # Re-submit only; steps=0 never replays a suspended guest.
            runtime.start_python(
                member_id, payload["source"], mode="exec",
                inputs={name: sources[bindings[name]]["value"] for name in names},
                capabilities=(), limits={"max_source_bytes": 65_536},
                operation_id=task_id, task_id=task_id, steps=0,
            )
            boundary = runtime.run_to_boundary(member_id, task_id=task_id)
            status = boundary["view"]["status"]
            reason = boundary["view"].get("unfinished_reason")
            if status == "completed":
                try:
                    result = read_global(runtime.raw_state(member_id, task_id=task_id), "result")
                    outputs = {"result": result}
                    if len(canonical_json_bytes(outputs)) > _MAX_RESULT_BYTES:
                        raise GuestRuntimeError("root guest result exceeds its bound")
                except GuestRuntimeError as exc:
                    status = "faulted"
                    reason = str(exc)
                else:
                    self._write_record(
                        root, record_id=event_id, kind="Event",
                        payload={"identity": identity, "status": "completed", "outputs": outputs},
                        epistemic_kind="observed",
                    )
            if status != "completed":
                if status not in {"running", "paused", "resource-paused", "waiting", "faulted", "cancelled"}:
                    raise OrganismError("root guest task has an unknown status")
                self._write_record(
                    root, record_id=event_id, kind="Event",
                    payload={"identity": identity, "status": status, "reason": reason},
                    epistemic_kind="observed",
                )
                return {
                    "status": status, "method_id": payload["method_id"],
                    "method_sha256": payload["method_sha256"], "task_id": task_id,
                    "program_ref": program_ref,
                    "execution_event_ref": self._record_reference(root._record(event_id)),
                    "unfinished_reason": reason,
                }
        event = root._record(event_id)
        outputs = event["payload"]["outputs"]
        event_ref = self._record_reference(event)
        receipt = {
            "status": "supported",
            "summary": f"Executed root guest method {payload['method_id']}",
            "outputs": outputs,
            "evidence": {
                "support_status": "supported",
                "research_program_id": program_id,
                "question_id": question_id,
                "question": question,
                "question_sha256": _digest(question),
                "method_id": payload["method_id"],
                "method_sha256": payload["method_sha256"],
                "source_identity_sha256": identity["source_identity_sha256"],
                "source_ids": source_ids,
                "source_provenance": provenance,
                "program_ref": program_ref,
            },
        }
        assessment = root.record_root_method_assessment(
            operation_id, result=receipt, program_ref=program_ref,
            execution_event_ref=event_ref,
        )
        return {
            **receipt, "method_id": payload["method_id"],
            "origin_program_id": payload["program_id"],
            "method_sha256": payload["method_sha256"],
            "program_ref": program_ref, "execution_event_ref": event_ref,
            "assessment": assessment,
        }

    def create_root_guest_research_method(
        self,
        operation_id: str,
        program_id: str,
        question_id: str,
        question: str,
        proposal: Mapping[str, Any],
        sources: Sequence[Mapping[str, Any]],
        runtime: Any,
        member_id: str,
        *,
        produced_by: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        operation_id = _identifier(operation_id, "root guest operation_id")
        program_id = _identifier(program_id, "research program_id")
        question_id = _identifier(question_id, "research question_id")
        question = _text(question, "root guest question", maximum=2_000)
        member_id = _identifier(member_id, "root guest member_id")
        current = self._root_method_sources(sources)
        if any(row["identity"]["program_id"] != program_id for row in current.values()):
            raise OrganismError("root guest sources belong to another program")
        candidate = self._root_guest_proposal(proposal, current)
        if produced_by is not None:
            # The optional lineage is a field-backed generator receipt, never
            # proposal-authored metadata.
            produced_by = _plain(produced_by)
            if (
                not isinstance(produced_by, dict)
                or set(produced_by) != {
                    "generator_method_id", "generator_method_sha256",
                    "generator_program_ref", "generator_execution_event_ref",
                    "output_sha256",
                }
                or any(
                    not isinstance(produced_by.get(key), dict)
                    or set(produced_by[key]) != {"id", "kind", "content_version"}
                    or not isinstance(produced_by[key].get("id"), str)
                    for key in ("generator_program_ref", "generator_execution_event_ref")
                )
                or any(
                    not isinstance(produced_by.get(key), str)
                    for key in ("generator_method_id", "generator_method_sha256", "output_sha256")
                )
            ):
                raise OrganismError("root guest generator provenance is malformed")
        ids = candidate["source_ids"]
        names = [f"input_{index}" for index in range(len(ids))]
        with self._open_residencies(include_members=False) as (root, _):
            if produced_by is not None:
                generator_record = root._record(produced_by["generator_program_ref"]["id"])
                generator_event = root._record(produced_by["generator_execution_event_ref"]["id"])
                if (
                    generator_record is None
                    or generator_event is None
                    or generator_record.get("status") != "active"
                    or generator_event.get("status") != "active"
                    or self._record_reference(generator_record) != produced_by["generator_program_ref"]
                    or self._record_reference(generator_event) != produced_by["generator_execution_event_ref"]
                ):
                    raise OrganismError("root guest generator field references changed")
                generator_payload = self._unwrap_program_record(generator_record["payload"])
                event_payload = generator_event["payload"]
                event_identity = event_payload.get("identity", {})
                generator_output = event_payload.get("outputs", {}).get("result")
                if (
                    generator_payload.get("schema") != ROOT_GUEST_METHOD_SCHEMA
                    or generator_payload.get("method_id") != produced_by["generator_method_id"]
                    or generator_payload.get("method_sha256") != produced_by["generator_method_sha256"]
                    or generator_payload.get("authorship") != self._root_method_authorship(root)
                    or event_identity.get("program_id") != program_id
                    or event_identity.get("program_ref") != produced_by["generator_program_ref"]
                    or event_identity.get("schema") != ROOT_GUEST_EXECUTION_SCHEMA
                    or event_identity.get("method_id") != produced_by["generator_method_id"]
                    or event_identity.get("method_sha256") != produced_by["generator_method_sha256"]
                    or event_identity.get("question_id") != question_id
                    or event_identity.get("question") != question
                    or event_payload.get("status") != "completed"
                    or generator_output != candidate
                    or _digest(generator_output) != produced_by["output_sha256"]
                    or event_identity.get("origin_program_id", generator_payload.get("program_id")) != generator_payload.get("program_id")
                ):
                    raise OrganismError("root guest generator provenance does not support proposal")
                self._validate_root_guest_record(generator_payload)
                if (
                    generator_payload["program_id"] != program_id
                    and (
                        produced_by["generator_method_id"],
                        produced_by["generator_method_sha256"],
                        generator_record["id"], generator_record["content_version"],
                    ) not in self._supported_root_guest_methods(root)
                ):
                    raise OrganismError("root guest generator lacks origin support")
                generator_bindings = event_identity.get("bindings")
                generator_provenance = event_identity.get("source_provenance")
                if (
                    not isinstance(generator_bindings, Mapping)
                    or not isinstance(generator_provenance, Mapping)
                    or set(generator_bindings) != set(generator_payload["input_names"])
                    or event_identity.get("source_ids") != [
                        generator_bindings[name] for name in generator_payload["input_names"]
                    ]
                    or event_identity.get("source_identity_sha256") != _digest(generator_provenance)
                    or any(
                        not isinstance(source_id, str)
                        or source_id not in current
                        or generator_provenance.get(source_id) != {
                            "identity_sha256": _digest(current[source_id]["identity"]),
                            "source_refs": current[source_id]["identity"]["source_refs"],
                            "dependencies": current[source_id]["identity"]["dependencies"],
                            "field_revision": current[source_id]["field_revision"],
                        }
                        for source_id in generator_bindings.values()
                    )
                ):
                    raise OrganismError("root guest generator source bindings changed")
            body = {
                "source": candidate["source"],
                "source_sha256": hashlib.sha256(candidate["source"].encode("utf-8")).hexdigest(),
                "input_names": names,
                "input_signature": [self._root_guest_kind(current[source_id]["value"]) for source_id in ids],
                "origin_source_ids": ids,
                "origin_sources": {source_id: {
                    "identity": current[source_id]["identity"],
                    "field_revision": current[source_id]["field_revision"],
                } for source_id in ids},
                "program_id": program_id,
                "question_id": question_id,
                "question": question,
                "summary": candidate["summary"],
                "assumptions": candidate["assumptions"],
                "preconditions": candidate["preconditions"],
                "effects": candidate["effects"],
                "uncertainty": candidate["uncertainty"],
                "authorship": self._root_method_authorship(root),
            }
            if produced_by is not None:
                body["produced_by"] = produced_by
            method_sha = _digest(body)
            method_id = "root-guest-method:" + method_sha[:32]
            payload = {
                "schema": ROOT_GUEST_METHOD_SCHEMA, "method_id": method_id,
                "method_sha256": method_sha, **body,
            }
            self._validate_root_guest_record(payload)
            prior_execution = root._record(
                f"event:root-guest-method-execution:{operation_id}"
            )
            if prior_execution is not None:
                prior_identity = prior_execution.get("payload", {}).get("identity", {})
                if (
                    prior_identity.get("method_sha256") != method_sha
                    or prior_identity.get("method_id") != method_id
                    or prior_identity.get("program_id") != program_id
                    or prior_identity.get("question_id") != question_id
                    or prior_identity.get("question") != question
                    or prior_identity.get("bindings") != dict(zip(names, ids))
                ):
                    raise OrganismError("root guest operation identity was reused")
            record_id = "program:" + method_id
            record = root._record(record_id)
            if record is None:
                from programs.python.compiler import CompilerError, compile_python

                try:
                    compile_python(
                        candidate["source"], mode="exec",
                        max_source_bytes=65_536,
                    )
                except CompilerError as exc:
                    raise OrganismError("root guest source cannot be compiled") from exc
                self._write_record(
                    root, record_id=record_id, kind="Program",
                    payload=payload, epistemic_kind="asserted",
                )
                record = root._record(record_id)
            elif self._unwrap_program_record(record.get("payload", {})) != payload:
                raise OrganismError("root guest method identity was reused")
            return self._execute_root_guest_method(
                root, method_record=record, payload=payload,
                operation_id=operation_id, program_id=program_id,
                question_id=question_id, question=question,
                sources=current, bindings=dict(zip(names, ids)), runtime=runtime,
                member_id=member_id,
            )

    def execute_retained_root_guest_research_method(
        self,
        method_id: str,
        method_sha256: str,
        operation_id: str,
        program_id: str,
        question_id: str,
        question: str,
        sources: Sequence[Mapping[str, Any]],
        bindings: Mapping[str, str],
        runtime: Any,
        member_id: str,
    ) -> dict[str, Any]:
        method_id = _identifier(method_id, "root guest method_id")
        method_sha256 = _identifier(method_sha256, "root guest method_sha256")
        operation_id = _identifier(operation_id, "root guest operation_id")
        program_id = _identifier(program_id, "research program_id")
        question_id = _identifier(question_id, "research question_id")
        question = _text(question, "root guest question", maximum=2_000)
        member_id = _identifier(member_id, "root guest member_id")
        current = self._root_method_sources(sources)
        if any(row["identity"]["program_id"] != program_id for row in current.values()):
            raise OrganismError("root guest sources belong to another program")
        with self._open_residencies(include_members=False) as (root, _):
            record = root._record("program:" + method_id)
            if record is None or record.get("status") != "active":
                raise OrganismError("retained root guest method is unavailable")
            payload = self._unwrap_program_record(record.get("payload", {}))
            if (
                payload.get("schema") != ROOT_GUEST_METHOD_SCHEMA
                or payload.get("method_id") != method_id
                or payload.get("method_sha256") != method_sha256
                or not isinstance(payload.get("program_id"), str)
                or payload.get("authorship") != self._root_method_authorship(root)
            ):
                raise OrganismError("retained root guest method identity changed")
            self._validate_root_guest_record(payload)
            if (
                payload["program_id"] != program_id
                and (
                    method_id, method_sha256, record["id"], record["content_version"],
                ) not in self._supported_root_guest_methods(root)
            ):
                raise OrganismError("retained root guest method lacks origin support")
            return self._execute_root_guest_method(
                root, method_record=record, payload=payload,
                operation_id=operation_id, program_id=program_id,
                question_id=question_id, question=question,
                sources=current, bindings=bindings, runtime=runtime, member_id=member_id,
            )

    def derive_root_guest_research_method(
        self,
        generator_method_id: str,
        generator_method_sha256: str,
        operation_id: str,
        program_id: str,
        question_id: str,
        question: str,
        sources: Sequence[Mapping[str, Any]],
        bindings: Mapping[str, str],
        runtime: Any,
        member_id: str,
    ) -> dict[str, Any]:
        """Run a retained generator, admit only its exact proposal, and run its child."""
        generator_method_id = _identifier(generator_method_id, "root guest generator method_id")
        generator_method_sha256 = _identifier(
            generator_method_sha256, "root guest generator method_sha256"
        )
        operation_id = _identifier(operation_id, "root guest derivation operation_id")
        generator_operation = _identifier(operation_id + ":generator", "generator operation_id")
        derived_operation = _identifier(operation_id + ":derived", "derived operation_id")
        program_id = _identifier(program_id, "research program_id")
        question_id = _identifier(question_id, "research question_id")
        question = _text(question, "root guest question", maximum=2_000)
        member_id = _identifier(member_id, "root guest member_id")
        current = self._root_method_sources(sources)
        if any(row["identity"]["program_id"] != program_id for row in current.values()):
            raise OrganismError("root guest sources belong to another program")
        if not isinstance(bindings, Mapping):
            raise OrganismError("root guest generator bindings are invalid")
        selected_bindings = _plain(bindings)
        if not isinstance(selected_bindings, dict):
            raise OrganismError("root guest generator bindings are invalid")
        event_id = f"event:root-guest-method-derivation:{operation_id}"
        with self._open_residencies(include_members=False) as (root, _):
            generator_record = root._record("program:" + generator_method_id)
            if generator_record is None or generator_record.get("status") != "active":
                raise OrganismError("retained root guest generator is unavailable")
            generator_payload = self._unwrap_program_record(generator_record.get("payload", {}))
            if (
                generator_payload.get("schema") != ROOT_GUEST_METHOD_SCHEMA
                or generator_payload.get("method_id") != generator_method_id
                or generator_payload.get("method_sha256") != generator_method_sha256
                or not isinstance(generator_payload.get("program_id"), str)
                or generator_payload.get("authorship") != self._root_method_authorship(root)
            ):
                raise OrganismError("retained root guest generator identity changed")
            self._validate_root_guest_record(generator_payload)
            if (
                generator_payload["program_id"] != program_id
                and (
                    generator_method_id, generator_method_sha256,
                    generator_record["id"], generator_record["content_version"],
                ) not in self._supported_root_guest_methods(root)
            ):
                raise OrganismError("retained root guest generator lacks origin support")
            names = generator_payload["input_names"]
            if (
                set(selected_bindings) != set(names)
                or any(not isinstance(value, str) for value in selected_bindings.values())
                or len(set(selected_bindings.values())) != len(names)
            ):
                raise OrganismError("root guest generator bindings are incomplete")
            for name, kind in zip(names, generator_payload["input_signature"]):
                source_id = selected_bindings[name]
                if not isinstance(source_id, str) or source_id not in current:
                    raise OrganismError("root guest generator source is not selected")
                if self._root_guest_kind(current[source_id]["value"]) != kind:
                    raise OrganismError("root guest generator source kind is incompatible")
            identity = {
                "schema": ROOT_GUEST_DERIVATION_SCHEMA,
                "operation_id": operation_id,
                "generator_method_id": generator_method_id,
                "generator_method_sha256": generator_method_sha256,
                "generator_program_ref": self._record_reference(generator_record),
                "program_id": program_id,
                "question_id": question_id,
                "question": question,
                "bindings": selected_bindings,
                "selected_sources": {
                    source_id: {
                        "identity": row["identity"],
                        "field_revision": row["field_revision"],
                    }
                    for source_id, row in current.items()
                },
                "member_id": member_id,
            }
            if program_id != generator_payload["program_id"]:
                identity["origin_program_id"] = generator_payload["program_id"]
            existing = root._record(event_id)
            if existing is not None:
                if existing.get("payload", {}).get("identity") != identity:
                    raise OrganismError("root guest derivation operation identity was reused")
            else:
                self._write_record(
                    root, record_id=event_id, kind="Event",
                    payload={"identity": identity, "status": "pending"},
                    epistemic_kind="observed",
                )

        generator = self.execute_retained_root_guest_research_method(
            generator_method_id, generator_method_sha256, generator_operation,
            program_id, question_id, question, sources, selected_bindings,
            runtime, member_id,
        )
        provenance: dict[str, Any] | None = None
        if generator["status"] != "supported":
            with self._open_residencies(include_members=False) as (root, _):
                self._write_record(
                    root, record_id=event_id, kind="Event",
                    payload={"identity": identity, "status": generator["status"],
                             "generator_execution_event_ref": generator.get("execution_event_ref"),
                             "reason": generator.get("unfinished_reason")},
                    epistemic_kind="observed",
                )
            return {
                "status": generator["status"], "generator": generator,
                "produced_by": None,
                "unfinished_reason": generator.get("unfinished_reason"),
            }

        proposal = generator["outputs"]["result"]
        provenance = {
            "generator_method_id": generator_method_id,
            "generator_method_sha256": generator_method_sha256,
            "generator_program_ref": generator["program_ref"],
            "generator_execution_event_ref": generator["execution_event_ref"],
            "output_sha256": _digest(proposal),
        }
        try:
            candidate = self._root_guest_proposal(proposal, current)
        except OrganismError as exc:
            with self._open_residencies(include_members=False) as (root, _):
                self._write_record(
                    root, record_id=event_id, kind="Event",
                    payload={"identity": identity, "status": "faulted",
                             "stage": "proposal-invalid",
                             "produced_by": provenance, "reason": str(exc)},
                    epistemic_kind="observed",
                )
            return {
                "status": "faulted", "generator": generator,
                "produced_by": provenance, "unfinished_reason": str(exc),
            }
        with self._open_residencies(include_members=False) as (root, _):
            existing = root._record(event_id)
            prior = existing["payload"]
            if prior.get("produced_by") is not None and prior["produced_by"] != provenance:
                raise OrganismError("root guest derivation output identity changed")
            if prior.get("status") == "faulted" and prior.get("stage") == "proposal-invalid":
                return {
                    "status": "faulted", "generator": generator,
                    "produced_by": provenance, "unfinished_reason": prior.get("reason"),
                }
            if prior.get("produced_by") is not None:
                if prior.get("source_ids") != candidate["source_ids"]:
                    raise OrganismError("root guest derivation proposal identity changed")
            else:
                self._write_record(
                    root, record_id=event_id, kind="Event",
                    payload={"identity": identity, "status": "proposed",
                             "produced_by": provenance, "source_ids": candidate["source_ids"]},
                    epistemic_kind="observed",
                )
        try:
            child = self.create_root_guest_research_method(
                derived_operation, program_id, question_id, question,
                candidate, sources, runtime, member_id, produced_by=provenance,
            )
        except OrganismError as exc:
            if str(exc) != "root guest source cannot be compiled":
                raise
            with self._open_residencies(include_members=False) as (root, _):
                self._write_record(
                    root, record_id=event_id, kind="Event",
                    payload={"identity": identity, "status": "faulted",
                             "stage": "proposal-invalid",
                             "produced_by": provenance, "reason": str(exc)},
                    epistemic_kind="observed",
                )
            return {
                "status": "faulted", "generator": generator,
                "produced_by": provenance, "unfinished_reason": str(exc),
            }
        with self._open_residencies(include_members=False) as (root, _):
            self._write_record(
                root, record_id=event_id, kind="Event",
                payload={"identity": identity, "status": child["status"],
                         "produced_by": provenance, "source_ids": candidate["source_ids"],
                         "child_program_ref": child.get("program_ref"),
                         "child_execution_event_ref": child.get("execution_event_ref")},
                epistemic_kind="observed",
            )
        return {**child, "generator": generator, "produced_by": provenance}


    @staticmethod
    def _collective_continuation_operation_id(
        continuation_id: str,
        action: str,
        identity: str = "",
    ) -> str:
        suffix = _digest(
            {
                "action": action,
                "continuation_id": continuation_id,
                "identity": identity,
            }
        )[:32]
        return f"organism:collective-continuation:{action}:{suffix}"

    @staticmethod
    def _collective_episode_id(continuation_id: str) -> str:
        continuation_id = _identifier(
            continuation_id, "collective continuation_id"
        )
        return _identifier(
            f"collective:{continuation_id}",
            "collective reasoning episode",
        )

    def _collective_synthesis_state(
        self,
        root: ResearchResidency,
        synthesis_id: str,
    ) -> dict[str, Any]:
        synthesis_id = _identifier(synthesis_id, "synthesis_id")
        program_id = f"program:collaboration-synthesis:{synthesis_id}"
        gap_id = (
            "obligation:collaboration-capability-gap:"
            f"{synthesis_id}"
        )
        assessment_id = f"organism:synthesis:{synthesis_id}"
        program = root._record(program_id)
        gap = root._record(gap_id)
        assessment = root._record(assessment_id)
        assessment_payload = (
            {}
            if assessment is None
            else _plain(assessment["payload"])
        )
        lineage_sha256 = assessment_payload.get("gap_lineage_sha256")
        if gap is not None:
            gap_payload = _plain(gap["payload"])
            if (
                gap_payload.get("schema")
                != COLLABORATIVE_CAPABILITY_GAP_SCHEMA
            ):
                raise OrganismError(
                    "collective synthesis capability gap is malformed"
                )
            lineage_sha256 = gap_payload.get(
                "gap_lineage_sha256", lineage_sha256
            )
            if gap_payload.get("state") == "open":
                maximum_work = gap_payload.get("maximum_work")
                if (
                    isinstance(maximum_work, bool)
                    or not isinstance(maximum_work, int)
                    or maximum_work < 1
                ):
                    raise OrganismError(
                        "collective synthesis capability gap lacks a work bound"
                    )
                return {
                    "assessment": assessment,
                    "gap": gap,
                    "gap_ref": self._record_reference(gap),
                    "lineage_sha256": lineage_sha256,
                    "maximum_work": maximum_work,
                    "method": None,
                    "program": None,
                    "program_ref": None,
                }
        if program is None:
            raise OrganismError(
                "collective synthesis has no executable resident program"
            )
        program_ref = self._record_reference(program)
        program_payload = self._unwrap_program_record(program["payload"])
        method_payload = program_payload.get("method")
        if not isinstance(method_payload, Mapping):
            raise OrganismError(
                "collective synthesis resident program is malformed"
            )
        try:
            method = ExecutableMethod.from_dict(method_payload)
        except CollectiveHiveError as exc:
            raise OrganismError(
                "collective synthesis resident program is malformed"
            ) from exc
        if gap is not None:
            gap_payload = _plain(gap["payload"])
            if (
                gap_payload.get("state") != "resolved"
                or gap_payload.get("resolved_by_program_ref") != program_ref
            ):
                raise OrganismError(
                    "collective synthesis gap resolution is inconsistent"
                )
        return {
            "assessment": assessment,
            "gap": gap,
            "gap_ref": (
                None if gap is None else self._record_reference(gap)
            ),
            "lineage_sha256": lineage_sha256,
            "maximum_work": method.maximum_work,
            "method": method,
            "program": program,
            "program_ref": program_ref,
        }

    def _collective_continuation_record(
        self,
        root: ResearchResidency,
        continuation_id: str,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        episode_id = self._collective_episode_id(continuation_id)
        record = root._record(f"obligation:reasoning:{episode_id}")
        if record is None:
            raise OrganismError("collective continuation does not exist")
        payload = _plain(record["payload"])
        if payload.get("schema") != PACKET_REASONING_EPISODE_SCHEMA:
            raise OrganismError("collective continuation record is malformed")
        work_items = payload.get("work_items")
        matches = (
            []
            if not isinstance(work_items, list)
            else [
                item
                for item in work_items
                if isinstance(item, Mapping)
                and item.get("kind") == "collective"
            ]
        )
        if len(matches) != 1:
            raise OrganismError("collective continuation work item is malformed")
        invocation = matches[0].get("invocation")
        request = (
            None
            if not isinstance(invocation, Mapping)
            else invocation.get("request")
        )
        if (
            not isinstance(invocation, Mapping)
            or invocation.get("adapter") != COLLECTIVE_METHOD_ADAPTER
            or not isinstance(request, Mapping)
            or request.get("schema")
            != COLLECTIVE_METHOD_CONTINUATION_SCHEMA
            or request.get("continuation_id") != continuation_id
        ):
            raise OrganismError(
                "collective continuation invocation is malformed"
            )
        return record, payload, dict(request)

    def _collective_continuation_view(
        self,
        root: ResearchResidency,
        continuation_id: str,
    ) -> dict[str, Any]:
        record, payload, request = self._collective_continuation_record(
            root, continuation_id
        )
        synthesis_id = _identifier(
            request.get("synthesis_id"),
            "collective continuation synthesis_id",
        )
        synthesis_state = self._collective_synthesis_state(
            root, synthesis_id
        )
        event = root._record(
            f"event:reasoning:{self._collective_episode_id(continuation_id)}"
        )
        active = payload.get("active")
        call = (
            None
            if not isinstance(active, Mapping)
            else {
                "call_id": active.get("call_id"),
                "request_sha256": active.get("request_sha256"),
                "return_binding": active.get("return_binding"),
            }
        )
        result = (
            None
            if event is None
            else _plain(event["payload"]).get("result")
        )
        wait_reason: str | None = None
        if payload.get("phase") == "terminal":
            accepted = (
                result.get("accepted")
                if isinstance(result, Mapping)
                else None
            )
            disposition = "completed" if accepted is True else "blocked"
        elif synthesis_state["gap"] is not None and (
            synthesis_state["gap"]["payload"].get("state") == "open"
        ):
            disposition = "waiting"
            wait_reason = "capability-gap"
        elif (
            request.get("expected_program_ref") is not None
            and request.get("expected_program_ref")
            != synthesis_state["program_ref"]
        ):
            disposition = "stale"
            wait_reason = "method-version-changed"
        else:
            disposition = "ready"
            wait_reason = "explicit-resume"
        gap_payload = (
            None
            if synthesis_state["gap"] is None
            else _plain(synthesis_state["gap"]["payload"])
        )
        return {
            "schema": COLLECTIVE_METHOD_CONTINUATION_SCHEMA,
            "assessment": payload.get("assessment"),
            "bindings_sha256": request.get("bindings_sha256"),
            "call": call,
            "capability_gap": (
                None
                if gap_payload is None
                or gap_payload.get("state") != "open"
                else {
                    "gaps": gap_payload.get("gaps", []),
                    "ref": synthesis_state["gap_ref"],
                }
            ),
            "continuation_id": continuation_id,
            "continuation_ref": self._record_reference(record),
            "episode_id": self._collective_episode_id(continuation_id),
            "field_state_sha256": root.owner.state.state_sha256,
            "phase": payload.get("phase"),
            "program_ref": synthesis_state["program_ref"],
            "result": result,
            "status": disposition,
            "synthesis_id": synthesis_id,
            "wait_reason": wait_reason,
        }

    def begin_collective_method_continuation(
        self,
        synthesis_id: str,
        continuation_id: str,
        bindings: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Suspend an exact resident caller at one collective-method invocation."""

        synthesis_id = _identifier(synthesis_id, "synthesis_id")
        continuation_id = _identifier(
            continuation_id, "collective continuation_id"
        )
        episode_id = self._collective_episode_id(continuation_id)
        normalized_bindings = _plain(bindings)
        if not isinstance(normalized_bindings, dict):
            raise OrganismError("collective method bindings must be a mapping")
        if len(canonical_json_bytes(normalized_bindings)) > _MAX_RESULT_BYTES:
            raise OrganismError("collective method bindings exceed their bound")
        bindings_sha256 = _digest(normalized_bindings)
        with self._open_residencies(include_members=False) as (root, _):
            existing = root._record(f"obligation:reasoning:{episode_id}")
            if existing is not None:
                _, _, request = (
                    self._collective_continuation_record(
                        root, continuation_id
                    )
                )
                if (
                    request.get("synthesis_id") != synthesis_id
                    or request.get("bindings_sha256") != bindings_sha256
                ):
                    raise OrganismError(
                        "collective continuation identity was reused"
                    )
                return self._collective_continuation_view(
                    root, continuation_id
                )
            synthesis_state = self._collective_synthesis_state(
                root, synthesis_id
            )
            expected_program_ref = synthesis_state["program_ref"]
            awaited_gap_ref = (
                synthesis_state["gap_ref"]
                if synthesis_state["program_ref"] is None
                else None
            )
            invocation_request = {
                "schema": COLLECTIVE_METHOD_CONTINUATION_SCHEMA,
                "awaited_gap_ref": awaited_gap_ref,
                "bindings": normalized_bindings,
                "bindings_sha256": bindings_sha256,
                "continuation_id": continuation_id,
                "expected_program_ref": expected_program_ref,
                "gap_lineage_sha256": synthesis_state["lineage_sha256"],
                "synthesis_id": synthesis_id,
            }
            maximum_work = int(synthesis_state["maximum_work"])
            allocation = {
                name: 0 for name in PACKET_RESOURCE_NAMES
            }
            allocation.update(
                {
                    "frontier_size": 1,
                    "storage_words": _COLLECTIVE_RESULT_WORD_BOUND,
                    "work": maximum_work,
                }
            )
            reservation = {
                name: 0 for name in PACKET_RESOURCE_NAMES
            }
            reservation.update(
                {
                    "storage_words": _COLLECTIVE_RESULT_WORD_BOUND,
                    "work": maximum_work,
                }
            )
            begin_request = {
                "operation": "begin-reasoning",
                "operation_id": self._collective_continuation_operation_id(
                    continuation_id, "begin"
                ),
                "episode_id": episode_id,
                "question": {
                    "kind": "collective-method",
                    "synthesis_id": synthesis_id,
                },
                "allocation": allocation,
                "dependencies": (
                    []
                    if expected_program_ref is None
                    else [expected_program_ref]
                ),
                "program": {
                    "selection": {
                        "method": "baseline",
                        "selector": None,
                    },
                    "stopping": {"max_dispatches": 1},
                    "work_items": [
                        {
                            "dependencies": [],
                            "invocation": {
                                "adapter": COLLECTIVE_METHOD_ADAPTER,
                                "arguments": {},
                                "expected_return": {
                                    "schema": (
                                        COLLECTIVE_METHOD_RESULT_SCHEMA
                                    ),
                                },
                                "request": invocation_request,
                                "reservation": reservation,
                            },
                            "item_id": "collective-method",
                            "kind": "collective",
                            "priority": 1,
                            "scope": {
                                "continuation_id": continuation_id,
                                "synthesis_id": synthesis_id,
                            },
                        }
                    ],
                },
            }
            try:
                root.semantic(begin_request)
            except ResidencyError as exc:
                raise OrganismError(
                    "collective continuation could not be admitted"
                ) from exc
            return self._collective_continuation_view(
                root, continuation_id
            )

    def resume_collective_method_continuation(
        self,
        continuation_id: str,
    ) -> dict[str, Any]:
        """Wake a suspended collective call when its exact method is available."""

        continuation_id = _identifier(
            continuation_id, "collective continuation_id"
        )
        with self._open_residencies(include_members=False) as (root, _):
            _, payload, request = self._collective_continuation_record(
                root, continuation_id
            )
            episode_id = self._collective_episode_id(continuation_id)
            if payload.get("phase") == "terminal":
                try:
                    root.semantic(
                        {
                            "operation": "finish-reasoning",
                            "operation_id": (
                                self._collective_continuation_operation_id(
                                    continuation_id, "finish"
                                )
                            ),
                            "episode_id": episode_id,
                        }
                    )
                except ResidencyError as exc:
                    raise OrganismError(
                        "collective continuation could not be finalized"
                    ) from exc
                return self._collective_continuation_view(
                    root, continuation_id
                )
            active = payload.get("active")
            if not isinstance(active, Mapping):
                raise OrganismError(
                    "collective continuation has no suspended invocation"
                )
            synthesis_id = _identifier(
                request.get("synthesis_id"),
                "collective continuation synthesis_id",
            )
            synthesis_state = self._collective_synthesis_state(
                root, synthesis_id
            )
            if synthesis_state["program_ref"] is None:
                if (
                    request.get("gap_lineage_sha256")
                    != synthesis_state["lineage_sha256"]
                ):
                    raise OrganismError(
                        "collective continuation capability-gap lineage changed"
                    )
                return self._collective_continuation_view(
                    root, continuation_id
                )
            expected_program_ref = request.get("expected_program_ref")
            if expected_program_ref is None:
                if (
                    request.get("gap_lineage_sha256")
                    != synthesis_state["lineage_sha256"]
                ):
                    raise OrganismError(
                        "collective continuation capability-gap lineage changed"
                    )
                resolved_gap = synthesis_state["gap"]
                if (
                    resolved_gap is None
                    or resolved_gap["payload"].get("state") != "resolved"
                    or resolved_gap["payload"].get(
                        "resolved_by_program_ref"
                    )
                    != synthesis_state["program_ref"]
                ):
                    raise OrganismError(
                        "collective continuation gap resolution is missing"
                    )
                expected_program_ref = synthesis_state["program_ref"]
            elif expected_program_ref != synthesis_state["program_ref"]:
                raise OrganismError(
                    "collective continuation method changed after suspension"
                )
            bindings = request.get("bindings")
            if not isinstance(bindings, Mapping):
                raise OrganismError(
                    "collective continuation bindings are malformed"
                )
            execution_id = (
                "collective-continuation-"
                + _digest(
                    {
                        "call_id": active["call_id"],
                        "continuation_id": continuation_id,
                    }
                )[:32]
            )
            child_status = "halted"
            try:
                execution = self._execute_collective_synthesis(
                    root,
                    synthesis_id=synthesis_id,
                    execution_id=execution_id,
                    bindings=bindings,
                    expected_program_ref=expected_program_ref,
                )
                execution_record = root._record(
                    f"event:collaboration-execution:{execution_id}"
                )
                if execution_record is None:
                    raise OrganismError(
                        "collective continuation execution was not committed"
                    )
                child_result = {
                    "schema": COLLECTIVE_METHOD_RESULT_SCHEMA,
                    "accepted": True,
                    "execution_ref": self._record_reference(
                        execution_record
                    ),
                    "method_sha256": execution["method_sha256"],
                    "outputs": execution["outputs"],
                    "program_ref": execution["program_ref"],
                    "status": "supported",
                    "synthesis_id": synthesis_id,
                }
                actual_work = int(execution.get("work", 1))
            except OrganismError as exc:
                if "rejected its bindings" not in str(exc):
                    raise
                child_status = "faulted"
                child_result = {
                    "schema": COLLECTIVE_METHOD_RESULT_SCHEMA,
                    "accepted": False,
                    "error": "invalid-bindings",
                    "program_ref": expected_program_ref,
                    "status": "failed",
                    "synthesis_id": synthesis_id,
                }
                actual_work = 1
            resources = {
                name: 0 for name in PACKET_RESOURCE_NAMES
            }
            resources["storage_words"] = (
                len(canonical_json_bytes(child_result)) + 3
            ) // 4
            resources["work"] = actual_work
            external_return = {
                "schema": "cassifi.learning-computer-child-return.v2",
                "call_id": active["call_id"],
                "request_sha256": active["request_sha256"],
                "resources": resources,
                "result": child_result,
                "state_sha256": None,
                "status": child_status,
                "task": {
                    "continuation_id": continuation_id,
                    "program_ref": expected_program_ref,
                    "synthesis_id": synthesis_id,
                },
            }
            try:
                root.semantic(
                    {
                        "operation": "advance-reasoning",
                        "operation_id": (
                            self._collective_continuation_operation_id(
                                continuation_id,
                                "return",
                                str(active["call_id"]),
                            )
                        ),
                        "episode_id": episode_id,
                        "expected_return": external_return,
                    }
                )
                root.semantic(
                    {
                        "operation": "finish-reasoning",
                        "operation_id": (
                            self._collective_continuation_operation_id(
                                continuation_id, "finish"
                            )
                        ),
                        "episode_id": episode_id,
                    }
                )
            except ResidencyError as exc:
                raise OrganismError(
                    "collective continuation could not consume its return"
                ) from exc
            return self._collective_continuation_view(
                root, continuation_id
            )

    @staticmethod
    def _developed_capability_method(
        opportunity: Mapping[str, Any],
        development: Mapping[str, Any],
    ) -> ExecutableMethod:
        """Materialize a brain proposal as one strictly bounded field Program."""

        normalized = _plain(development)
        if (
            not isinstance(normalized, dict)
            or normalized.get("schema")
            != "cassi.entity.collective-capability-development.v1"
        ):
            raise OrganismError(
                "collective capability development schema is invalid"
            )
        summary = _text(
            normalized.get("summary"),
            "collective capability development summary",
            maximum=512,
        )
        sources = opportunity.get("sources")
        source_ids = normalized.get("source_ids")
        steps_payload = normalized.get("steps")
        if (
            not isinstance(sources, list)
            or not isinstance(source_ids, list)
            or not source_ids
            or len(source_ids) != len(set(source_ids))
            or not isinstance(steps_payload, list)
            or not steps_payload
        ):
            raise OrganismError(
                "collective capability development is malformed"
            )
        maximum_work = opportunity.get("maximum_work")
        if (
            isinstance(maximum_work, bool)
            or not isinstance(maximum_work, int)
            or maximum_work < 1
            or len(steps_payload) > min(maximum_work, 32)
        ):
            raise OrganismError(
                "collective capability development exceeds its work bound"
            )
        sources_by_id: dict[str, Mapping[str, Any]] = {}
        for source in sources:
            if not isinstance(source, Mapping):
                raise OrganismError(
                    "collective capability source is malformed"
                )
            source_id = _identifier(
                source.get("source_id"),
                "collective capability source_id",
            )
            sources_by_id[source_id] = source
        if any(
            not isinstance(source_id, str)
            or source_id not in sources_by_id
            for source_id in source_ids
        ):
            raise OrganismError(
                "collective capability development selected an unknown source"
            )
        inputs: list[MethodPort] = []
        roles: list[str] = []
        try:
            for source_id in source_ids:
                source = sources_by_id[str(source_id)]
                port_payload = source.get("port")
                if not isinstance(port_payload, Mapping):
                    raise OrganismError(
                        "collective capability source port is malformed"
                    )
                port = MethodPort.from_dict(port_payload)
                symbol = _identifier(
                    source.get("symbol"),
                    "collective capability source symbol",
                )
                roles.append(symbol)
                inputs.append(
                    MethodPort(
                        name=symbol,
                        value_kind=port.value_kind,
                        representation=port.representation,
                        unit=port.unit,
                        symbol=symbol,
                    )
                )
            expected_payload = opportunity.get("expected")
            if not isinstance(expected_payload, Mapping):
                raise OrganismError(
                    "collective capability expected port is malformed"
                )
            expected = MethodPort.from_dict(expected_payload)
            steps = tuple(
                PrimitiveStep.from_dict(step)
                for step in steps_payload
                if isinstance(step, Mapping)
            )
            if len(steps) != len(steps_payload):
                raise OrganismError(
                    "collective capability step is malformed"
                )
            program = FieldProgram(
                program_id=(
                    "collective-development:"
                    f"{_digest({'opportunity': opportunity.get('opportunity_sha256'), 'development': normalized})[:32]}"
                ),
                version=1,
                roles=tuple(roles),
                steps=steps,
                outputs=(steps[-1].output,),
                prefix_code_bits=max(1, len(steps)),
            )
            interface = MethodInterface(
                inputs=tuple(inputs),
                outputs=(
                    MethodPort(
                        name=expected.name,
                        value_kind=expected.value_kind,
                        representation=expected.representation,
                        unit=expected.unit,
                        symbol=steps[-1].output,
                    ),
                ),
            )
        except (CollectiveHiveError, FieldIntelligenceError) as exc:
            raise OrganismError(
                "collective capability development is not executable"
            ) from exc

        def statements(name: str) -> tuple[Mapping[str, Any], ...]:
            values = normalized.get(name)
            if not isinstance(values, list):
                raise OrganismError(
                    f"collective capability {name} must be a list"
                )
            return tuple(
                {
                    "statement": _text(
                        value,
                        f"collective capability {name} statement",
                        maximum=512,
                    )
                }
                for value in values
            )

        effects_payload = normalized.get("effects")
        if not isinstance(effects_payload, list):
            raise OrganismError(
                "collective capability effects must be a list"
            )
        effects = tuple(
            _text(
                value,
                "collective capability effect",
                maximum=256,
            )
            for value in effects_payload
        )
        uncertainty = normalized.get("uncertainty")
        if (
            isinstance(uncertainty, bool)
            or not isinstance(uncertainty, (int, float))
            or not math.isfinite(float(uncertainty))
            or not 0.0 <= float(uncertainty) <= 1.0
        ):
            raise OrganismError(
                "collective capability uncertainty is invalid"
            )
        return ExecutableMethod(
            program=program,
            interface=interface,
            assumptions=(
                {
                    "kind": "development-summary",
                    "statement": summary,
                },
                *statements("assumptions"),
            ),
            preconditions=statements("preconditions"),
            effects=effects,
            maximum_work=len(steps),
            uncertainty=float(uncertainty),
        )

    def advance_collective_investigation(
        self,
        *,
        operation_id: str,
        candidate: Mapping[str, Any],
        development: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Perform one exact Hive next step selected from the live view."""
        operation_id = _identifier(
            operation_id, "collective action operation_id"
        )
        if not isinstance(candidate, Mapping):
            raise OrganismError("collective action candidate must be a mapping")
        normalized_candidate = _plain(candidate)
        if not isinstance(normalized_candidate, dict):
            raise OrganismError("collective action candidate is malformed")
        candidate_sha256 = normalized_candidate.get("candidate_sha256")
        candidate_body = {
            key: value
            for key, value in normalized_candidate.items()
            if key != "candidate_sha256"
        }
        if (
            not isinstance(candidate_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", candidate_sha256) is None
            or _digest(candidate_body) != candidate_sha256
        ):
            raise OrganismError("collective action candidate digest is invalid")
        action_id = _identifier(
            candidate_body.get("action_id"), "collective action_id"
        )
        kind = candidate_body.get("kind")
        if kind not in {
            "develop-capability-gap",
            "route-capability-gap",
            "resume-continuation",
        }:
            raise OrganismError("collective action kind is unsupported")
        if kind == "develop-capability-gap":
            if not isinstance(development, Mapping):
                raise OrganismError(
                    "capability development action lacks a method proposal"
                )
            normalized_development = _plain(development)
            development_sha256 = _digest(normalized_development)
        else:
            if development is not None:
                raise OrganismError(
                    "non-development collective action received a method"
                )
            normalized_development = None
            development_sha256 = None
        synthesis_id = _identifier(
            candidate_body.get("synthesis_id"),
            "collective action synthesis_id",
        )
        record_id = (
            "event:collective-next:"
            f"{_digest({'operation_id': operation_id})[:32]}"
        )
        with self._open_residencies(include_members=False) as (root, _):
            existing = root._record(record_id)
            if existing is not None:
                payload = _plain(existing["payload"])
                if (
                    payload.get("schema") != COLLECTIVE_NEXT_ACTION_SCHEMA
                    or payload.get("operation_id") != operation_id
                    or payload.get("candidate") != normalized_candidate
                    or payload.get("development_sha256")
                    != development_sha256
                ):
                    raise OrganismError(
                        "collective action operation identity was reused"
                    )
                return payload

        if kind == "route-capability-gap":
            gap_sha256 = candidate_body.get("gap_sha256")
            if (
                not isinstance(gap_sha256, str)
                or re.fullmatch(r"[0-9a-f]{64}", gap_sha256) is None
            ):
                raise OrganismError(
                    "capability-route candidate lacks a gap digest"
                )
            with self._open_residencies(include_members=False) as (root, _):
                matching_gaps = [
                    gap
                    for gap_payload in self._open_capability_gaps(root)
                    if gap_payload["synthesis_id"] == synthesis_id
                    for gap in gap_payload["gaps"]
                    if _digest(gap) == gap_sha256
                ]
                states = sorted(
                    {
                        str(dispatch["state"])
                        for dispatch in self._collaboration_view(root)[
                            "capability_dispatches"
                        ]
                        if dispatch.get("synthesis_id") == synthesis_id
                        and isinstance(dispatch.get("gap"), Mapping)
                        and _digest(dispatch["gap"]) == gap_sha256
                        and isinstance(dispatch.get("state"), str)
                    }
                )
            if not matching_gaps:
                outcome = {
                    "effects": {"dispatches": []},
                    "reason": "capability-gap-no-longer-open",
                    "status": "waiting",
                }
            elif any(
                state in {
                    "assigned",
                    "prepared",
                    "admitted",
                    "completed",
                    "blocked",
                }
                for state in states
            ):
                outcome = {
                    "effects": {"dispatches": []},
                    "reason": (
                        "capability-dispatch-"
                        f"{states[0] if states else 'unavailable'}"
                    ),
                    "status": "waiting",
                }
            else:
                dispatches = self.dispatch_collective_capability_gaps(
                    synthesis_id=synthesis_id,
                    gap_sha256=gap_sha256,
                )
                result_states = {
                    item.get("state")
                    for item in dispatches
                    if isinstance(item.get("state"), str)
                }
                if "assigned" in result_states:
                    status = "routed"
                    reason = "member-assigned"
                elif "parked" in result_states:
                    status = "waiting"
                    reason = "no-schedulable-member"
                else:
                    status = "waiting"
                    reason = "capability-gap-no-longer-routable"
                outcome = {
                    "effects": {"dispatches": _plain(dispatches)},
                    "reason": reason,
                    "status": status,
                }
        elif kind == "develop-capability-gap":
            opportunity_sha256 = candidate_body.get(
                "opportunity_sha256"
            )
            member_id = candidate_body.get("member_id")
            dispatch_id = candidate_body.get("dispatch_id")
            if (
                not isinstance(opportunity_sha256, str)
                or re.fullmatch(r"[0-9a-f]{64}", opportunity_sha256)
                is None
                or not isinstance(member_id, str)
                or not isinstance(dispatch_id, str)
            ):
                raise OrganismError(
                    "capability development candidate is malformed"
                )
            member_id = _identifier(
                member_id, "capability development member_id"
            )
            dispatch_id = _identifier(
                dispatch_id, "capability development dispatch_id"
            )
            with self._open_residencies(
                include_members=False
            ) as (root, _):
                opportunities = [
                    row
                    for row in self._collaboration_view(root)[
                        "capability_development_opportunities"
                    ]
                    if row.get("opportunity_sha256")
                    == opportunity_sha256
                    and row.get("member_id") == member_id
                    and row.get("dispatch_id") == dispatch_id
                    and row.get("synthesis_id") == synthesis_id
                ]
            if len(opportunities) != 1:
                outcome = {
                    "effects": {
                        "advancement": [],
                        "capability": None,
                        "continuations": [],
                        "dispatch": None,
                    },
                    "reason": (
                        "capability-development-no-longer-actionable"
                    ),
                    "status": "waiting",
                }
            else:
                opportunity = opportunities[0]
                if not isinstance(normalized_development, Mapping):
                    raise OrganismError(
                        "capability development payload is malformed"
                    )
                method = self._developed_capability_method(
                    opportunity,
                    normalized_development,
                )
                role = _text(
                    opportunity.get("role"),
                    "capability development role",
                    maximum=128,
                )
                history = opportunity.get("provider_outcomes")
                reliability = (
                    history.get("reliability")
                    if isinstance(history, Mapping)
                    else 0.5
                )
                if (
                    isinstance(reliability, bool)
                    or not isinstance(reliability, (int, float))
                    or not math.isfinite(float(reliability))
                ):
                    reliability = 0.5
                reliability = min(1.0, max(0.0, float(reliability)))
                capability_id = (
                    "developed-capability:"
                    f"{_digest({'opportunity_sha256': opportunity_sha256, 'method_sha256': method.program_sha256})[:32]}"
                )
                capability = self.register_member_capability(
                    capability_id,
                    member_id=member_id,
                    roles=(role,),
                    kind="procedure",
                    domain=method.interface.outputs[0].representation,
                    reliability=reliability,
                    work_units=method.maximum_work,
                    branch_id="main",
                    diversity_keys=(
                        "autonomous-development",
                        f"gap:{str(opportunity['gap_sha256'])[:24]}",
                    ),
                    method=method,
                )
                advancement = (
                    self.advance_collective_capability_programs(
                        maximum_members=1,
                        member_id=member_id,
                    )
                )
                with self._open_residencies(
                    include_members=False
                ) as (root, _):
                    view = self._collaboration_view(root)
                    matching_dispatches = [
                        row
                        for row in view["capability_dispatches"]
                        if row.get("dispatch_id") == dispatch_id
                    ]
                    continuations = [
                        row
                        for row in view["continuations"]
                        if row.get("synthesis_id") == synthesis_id
                    ]
                current_dispatch = (
                    matching_dispatches[0]
                    if len(matching_dispatches) == 1
                    else None
                )
                dispatch_state = (
                    current_dispatch.get("state")
                    if isinstance(current_dispatch, Mapping)
                    else None
                )
                if dispatch_state in {"admitted", "completed"}:
                    if any(
                        row.get("status") == "completed"
                        for row in continuations
                    ):
                        status = "recovered"
                        reason = (
                            "developed-method-executed-and-continuation-"
                            "completed"
                        )
                    else:
                        status = "developed"
                        reason = "developed-method-admitted"
                elif dispatch_state == "blocked":
                    status = "blocked"
                    reason = "developed-method-not-composable"
                elif dispatch_state == "assigned":
                    status = "developing"
                    reason = "member-development-obligation-pending"
                else:
                    status = "waiting"
                    reason = "developed-capability-not-routed"
                outcome = {
                    "effects": {
                        "advancement": _plain(advancement),
                        "capability": _plain(capability),
                        "continuations": _plain(continuations),
                        "dispatch": _plain(current_dispatch),
                        "method_sha256": method.program_sha256,
                    },
                    "reason": reason,
                    "status": status,
                }
        else:
            continuation_id = candidate_body.get("continuation_id")
            if not isinstance(continuation_id, str):
                raise OrganismError(
                    "continuation candidate lacks a continuation_id"
                )
            continuation_id = _identifier(
                continuation_id, "collective continuation_id"
            )
            with self._open_residencies(include_members=False) as (root, _):
                continuations = [
                    row
                    for row in self._collaboration_view(root)["continuations"]
                    if row.get("continuation_id") == continuation_id
                    and row.get("synthesis_id") == synthesis_id
                ]
            if not continuations:
                outcome = {
                    "effects": {"continuation": None},
                    "reason": "continuation-unavailable",
                    "status": "waiting",
                }
            elif continuations[0].get("status") != "ready":
                outcome = {
                    "effects": {"continuation": _plain(continuations[0])},
                    "reason": (
                        "continuation-"
                        f"{continuations[0].get('status', 'unavailable')}"
                    ),
                    "status": "waiting",
                }
            else:
                continuation = self.resume_collective_method_continuation(
                    continuation_id
                )
                outcome = {
                    "effects": {"continuation": _plain(continuation)},
                    "reason": (
                        "continuation-"
                        f"{continuation.get('status', 'resumed')}"
                    ),
                    "status": "resumed",
                }

        receipt = {
            "action_id": action_id,
            "candidate": normalized_candidate,
            "effects": outcome["effects"],
            "development_sha256": development_sha256,
            "kind": kind,
            "operation_id": operation_id,
            "reason": outcome["reason"],
            "schema": COLLECTIVE_NEXT_ACTION_SCHEMA,
            "status": outcome["status"],
            "synthesis_id": synthesis_id,
        }
        with self._open_residencies(include_members=False) as (root, _):
            existing = root._record(record_id)
            if existing is not None:
                payload = _plain(existing["payload"])
                if (
                    payload.get("schema") != COLLECTIVE_NEXT_ACTION_SCHEMA
                    or payload.get("operation_id") != operation_id
                    or payload.get("candidate") != normalized_candidate
                    or payload.get("development_sha256")
                    != development_sha256
                ):
                    raise OrganismError(
                        "collective action operation identity was reused"
                    )
                return payload
            self._write_record(
                root,
                record_id=record_id,
                kind="Event",
                payload=receipt,
                epistemic_kind="observed",
            )
        return receipt

    def _collaboration_view(self, root: ResearchResidency) -> dict[str, Any]:
        collective = root.session.collective
        records = root._task()["records"]
        resources = [
            _plain(history[-1]["payload"])
            for record_id, history in records.items()
            if record_id.startswith("organism:resource:")
        ]
        capability_gaps = [
            _plain(history[-1]["payload"])
            for record_id, history in records.items()
            if record_id.startswith(
                "obligation:collaboration-capability-gap:"
            )
            and history[-1]["payload"].get("state") == "open"
        ]
        member_capabilities = [
            _plain(history[-1]["payload"])
            for record_id, history in records.items()
            if record_id.startswith("organism:member-capability:")
            and history[-1]["payload"].get("schema")
            == COLLABORATIVE_MEMBER_CAPABILITY_SCHEMA
        ]
        capability_dispatches = [
            _plain(history[-1]["payload"])
            for record_id, history in records.items()
            if record_id.startswith("organism:capability-dispatch:")
            and history[-1]["payload"].get("schema")
            == COLLABORATIVE_CAPABILITY_DISPATCH_SCHEMA
        ]
        collective_actions = [
            {
                **_plain(history[-1]["payload"]),
                "created_at": history[-1].get("created_at"),
                "record_id": record_id,
            }
            for record_id, history in records.items()
            if record_id.startswith("event:collective-next:")
            and history[-1]["payload"].get("schema")
            == COLLECTIVE_NEXT_ACTION_SCHEMA
        ]
        executable_syntheses = [
            {
                "content_version": int(history[-1]["content_version"]),
                "id": record_id,
                "kind": "Program",
            }
            for record_id, history in records.items()
            if record_id.startswith("program:collaboration-synthesis:")
        ]
        investigations = [
            self._collective_investigation_view(
                root,
                record_id.removeprefix("organism:synthesis:"),
            )
            for record_id in records
            if record_id.startswith("organism:synthesis:")
        ]
        continuation_ids: list[str] = []
        for history in records.values():
            latest = history[-1]
            payload = latest.get("payload")
            if (
                latest.get("kind") != "Obligation"
                or not isinstance(payload, Mapping)
                or payload.get("schema") != PACKET_REASONING_EPISODE_SCHEMA
            ):
                continue
            for item in payload.get("work_items", []):
                invocation = (
                    item.get("invocation")
                    if isinstance(item, Mapping)
                    else None
                )
                request = (
                    invocation.get("request")
                    if isinstance(invocation, Mapping)
                    else None
                )
                if (
                    isinstance(request, Mapping)
                    and request.get("schema")
                    == COLLECTIVE_METHOD_CONTINUATION_SCHEMA
                ):
                    continuation_ids.append(
                        str(request["continuation_id"])
                    )
                    break
        return {
            "schema": COLLABORATION_VIEW_SCHEMA,
            "affect_reports": list(
                collective.list_collaboration(AFFECT_REPORT_SCHEMA)
            ),
            "assignments": list(
                collective.list_collaboration(COLLABORATION_ASSIGNMENT_SCHEMA)
            ),
            "capability_gaps": sorted(
                capability_gaps,
                key=lambda item: str(item["synthesis_id"]),
            ),
            "capability_dispatches": sorted(
                capability_dispatches,
                key=lambda item: str(item["dispatch_id"]),
            ),
            "capability_development_opportunities": (
                self._capability_development_opportunities(
                    root,
                    dispatches=capability_dispatches,
                    actions=collective_actions,
                )
            ),
            "collective_actions": sorted(
                collective_actions,
                key=lambda item: (
                    str(item.get("created_at", "")),
                    str(item.get("operation_id", "")),
                ),
            ),
            "member_capabilities": sorted(
                member_capabilities,
                key=lambda item: (
                    str(item["member_id"]),
                    str(item["capability_id"]),
                ),
            ),
            "investigations": sorted(
                investigations,
                key=lambda item: str(item["synthesis_id"]),
            ),
            "continuations": [
                self._collective_continuation_view(root, continuation_id)
                for continuation_id in sorted(set(continuation_ids))
            ],
            "executable_syntheses": sorted(
                executable_syntheses,
                key=lambda item: str(item["id"]),
            ),
            "requests": list(
                collective.list_collaboration(COLLABORATION_REQUEST_SCHEMA)
            ),
            "resource_allocations": sorted(
                resources,
                key=lambda item: str(item["allocation_id"]),
            ),
            "responses": list(
                collective.list_collaboration(COLLABORATION_RESPONSE_SCHEMA)
            ),
            "syntheses": list(
                collective.list_collaboration(COLLECTIVE_SYNTHESIS_SCHEMA)
            ),
            "translations": list(
                collective.list_collaboration(
                    REPRESENTATION_TRANSLATION_SCHEMA
                )
            ),
        }

    def collaboration_view(self) -> dict[str, Any]:
        with self._open_residencies(include_members=False) as (root, _):
            return self._collaboration_view(root)

    def migrate_cohort(
        self,
        migration_id: str,
        *,
        member_ids: Sequence[str],
        reason: str,
        profile: Mapping[str, int] | None = None,
    ) -> dict[str, Any]:
        """Prepare independent owners, synchronize public knowledge, then switch."""
        migration_id = _identifier(migration_id, "cohort migration_id")
        target = tuple(_identifier(item, "cohort member_id") for item in member_ids)
        if not target or len(target) > _MAX_MEMBERS or len(set(target)) != len(target):
            raise OrganismError("target cohort must contain unique bounded members")
        reason = _text(reason, "cohort migration reason", maximum=1024)
        receipt_path = self.cohort_migrations_home / f"{migration_id}.json"
        if receipt_path.exists():
            receipt = _read_json(receipt_path)
            if receipt.get("target_member_ids") != list(target):
                raise OrganismError("cohort migration identity was reused")
            return receipt
        current = self._cohort()
        manifest = self._load_manifest()
        workspace = Path(manifest["workspace"])
        effective_profile = dict(DEFAULT_PROFILE if profile is None else profile)
        work = self._bootstrap_work()
        source_closure = [
            {
                "path": path,
                "sha256": hashlib.sha256((workspace / path).read_bytes()).hexdigest(),
            }
            for path in manifest["source_paths"]
        ]
        runtime = {
            "python_implementation": sys.implementation.name,
            "python_version": list(sys.version_info[:3]),
            "source_closure_sha256": _digest(source_closure),
        }
        schema_closure = {
            "organism": SCHEMA,
            "manifest": MANIFEST_SCHEMA,
            "cohort": COHORT_SCHEMA,
            "migration": COHORT_MIGRATION_SCHEMA,
            "resource_allocation": RESOURCE_ALLOCATION_SCHEMA,
            "semantic_state": semantic_cognition_state()["schema"],
        }
        prepared: dict[str, str] = {}
        owner_manifests: dict[str, dict[str, Any]] = {}
        with contextlib.ExitStack() as stack:
            stack.enter_context(self.root_lock or contextlib.nullcontext())
            root = stack.enter_context(self._root_residency())
            residents: dict[str, ResearchResidency] = {"root": root}
            all_member_ids = tuple(dict.fromkeys([
                *current["active_member_ids"], *target,
            ]))
            for member_id in all_member_ids:
                residents[member_id] = stack.enter_context(
                    open_research_residency(
                        self.member_home(member_id),
                        hive_home=self.collective_hive_home,
                        import_skills=True,
                        export_skills=True,
                    )
                )
            source_snapshots = {
                owner_id: {
                    "field_state_sha256": resident.owner.state.state_sha256,
                    "continuation": _plain(resident._cursor()),
                    "record_ids": sorted(resident._task()["records"]),
                }
                for owner_id, resident in residents.items()
                if owner_id == "root" or owner_id in current["active_member_ids"]
            }
            for member_id in target:
                member = residents[member_id]
                existing_identity = (
                    None
                    if member._computer() is None
                    else member._record(ORGANISM_ID)
                )
                disposition = (
                    "retained-compatible-owner"
                    if existing_identity is not None else "new-independent-owner"
                )
                if existing_identity is None:
                    member.initialize(
                        workspace=workspace,
                        mission=f"{manifest['mission']} / independent member {member_id}",
                        work=work,
                        profile=effective_profile,
                    )
                    self._ensure_record(
                        member,
                        record_id=ORGANISM_ID,
                        kind="Value",
                        payload={
                            "schema": SCHEMA,
                            "member_id": member_id,
                            "root_organism_id": manifest["organism_id"],
                            "role": "independent-researcher",
                        },
                    )
                prepared[member_id] = member.owner.state.state_sha256
                task = member._task()
                prior_ids = set(
                    source_snapshots.get(member_id, {}).get("record_ids", [])
                )
                owner_manifests[member_id] = {
                    "owner_id": member_id,
                    "disposition": disposition,
                    "predecessor_field_state_sha256": (
                        source_snapshots.get(member_id, {}).get(
                            "field_state_sha256"
                        )
                    ),
                    "prepared_field_state_sha256": prepared[member_id],
                    "runtime": runtime,
                    "schemas": schema_closure,
                    "continuation": _plain(member._cursor()),
                    "policy": {
                        "collective_import": True,
                        "collective_export": True,
                        "authority": manifest["authority"],
                        "requested_profile": (
                            effective_profile
                            if disposition == "new-independent-owner" else None
                        ),
                    },
                    "record_mapping": [
                        {
                            "source_id": record_id if record_id in prior_ids else None,
                            "target_id": record_id,
                            "disposition": (
                                "preserved" if record_id in prior_ids else "created"
                            ),
                        }
                        for record_id in sorted(task["records"])
                    ],
                    "effect_journal": {
                        "path": str(self.member_home(member_id) / "effects"),
                        "cursor": EffectJournal(
                            self.member_home(member_id) / "effects"
                        ).count(),
                    },
                }
            sync = self._sync_collective({
                "root": root,
                **{member_id: residents[member_id] for member_id in target},
            })
            for member_id in target:
                member = residents[member_id]
                final_task = member._task()
                final_digest = member.owner.state.state_sha256
                prepared[member_id] = final_digest
                owner_manifests[member_id]["prepared_field_state_sha256"] = final_digest
                owner_manifests[member_id]["continuation"] = _plain(member._cursor())
                prior_ids = {
                    item["source_id"]
                    for item in owner_manifests[member_id]["record_mapping"]
                    if item["source_id"] is not None
                }
                owner_manifests[member_id]["record_mapping"] = [
                    {
                        "source_id": record_id if record_id in prior_ids else None,
                        "target_id": record_id,
                        "disposition": (
                            "preserved" if record_id in prior_ids else "created"
                        ),
                    }
                    for record_id in sorted(final_task["records"])
                ]
            root_task = root._task()
            allocations = [
                _plain(history[-1]["payload"])
                for record_id, history in root_task["records"].items()
                if record_id.startswith("organism:resource:")
            ]
            owner_manifests["root"] = {
                "owner_id": "root",
                "disposition": "retained-compatible-owner",
                "predecessor_field_state_sha256": source_snapshots["root"][
                    "field_state_sha256"
                ],
                "prepared_field_state_sha256": root.owner.state.state_sha256,
                "runtime": runtime,
                "schemas": schema_closure,
                "continuation": _plain(root._cursor()),
                "policy": {
                    "authority": manifest["authority"],
                    "collective_import": True,
                    "collective_export": True,
                },
                "allocations": allocations,
                "effect_journal": {
                    "path": str(self.journal.home),
                    "cursor": self.journal.count(),
                },
            }
            migration_payload = {
                "schema": COHORT_MIGRATION_SCHEMA,
                "migration_id": migration_id,
                "reason": reason,
                "source_generation": current["generation"],
                "source_member_ids": current["active_member_ids"],
                "target_member_ids": list(target),
                "prepared_field_state_sha256": prepared,
                "owner_manifests": owner_manifests,
                "source_closure": source_closure,
                "runtime": runtime,
                "schemas": schema_closure,
                "pending_allocations": allocations,
                "publication_boundary": {
                    "state": "quiesced-for-switch",
                    "in_flight_effects": 0,
                    "late_results": "retain-as-evidence-require-current-fence",
                },
                "collective_sync": sync,
                "transfer": "public-hive-artifacts-only",
                "adaptive_state_copied": False,
                "status": "prepared",
            }
            self._write_record(
                root,
                record_id=f"organism:cohort-migration:{migration_id}",
                kind="Event",
                payload=migration_payload,
                epistemic_kind="observed",
            )
        _atomic_json(receipt_path, migration_payload, immutable=True)
        _atomic_json(
            self.cohort_path,
            {
                "schema": COHORT_SCHEMA,
                "generation": int(current["generation"]) + 1,
                "active_member_ids": list(target),
                "migration_id": migration_id,
            },
        )
        return migration_payload

    def recover_cohort_migration(self, migration_id: str) -> dict[str, Any]:
        """Complete a prepared switch after interruption without copying a field."""
        migration_id = _identifier(migration_id, "cohort migration_id")
        receipt = _read_json(self.cohort_migrations_home / f"{migration_id}.json")
        if receipt.get("schema") != COHORT_MIGRATION_SCHEMA:
            raise OrganismError("cohort migration receipt is malformed")
        for source in receipt.get("source_closure", []):
            path = Path(self._load_manifest()["workspace"]) / str(source["path"])
            if (
                not path.is_file()
                or hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]
            ):
                raise OrganismError("cohort recovery source closure has changed")
        current = self._cohort()
        if current.get("migration_id") == migration_id:
            return current
        if int(current["generation"]) != int(receipt["source_generation"]):
            raise OrganismError("cohort recovery source generation has changed")
        for member_id in receipt["target_member_ids"]:
            with open_research_residency(
                self.member_home(member_id),
                hive_home=self.collective_hive_home,
                import_skills=True,
                export_skills=True,
            ) as member:
                member.inspect()
                expected = receipt["owner_manifests"][member_id][
                    "prepared_field_state_sha256"
                ]
                if member.owner.state.state_sha256 != expected:
                    raise OrganismError(
                        "cohort recovery target advanced beyond its prepared fence"
                    )
        recovered = {
            "schema": COHORT_SCHEMA,
            "generation": int(current["generation"]) + 1,
            "active_member_ids": list(receipt["target_member_ids"]),
            "migration_id": migration_id,
        }
        _atomic_json(self.cohort_path, recovered)
        return recovered

    def advance_resident(self, steps: int = 1) -> dict[str, Any]:
        """Advance the root's ordinary resident lifecycle without hidden host state."""
        if isinstance(steps, bool) or not isinstance(steps, int) or not 1 <= steps <= 256:
            raise OrganismError("steps must be in [1, 256]")
        self.maintain_collective_capability_gaps()
        self.advance_collective_capability_programs()
        with self._open_residencies(include_members=False) as (root, _):
            result = root.inspect()
            for _ in range(steps):
                result = root.advance()
            return result

    def advance_working_field(
        self,
        operation_id: str,
        *,
        field_id: str,
        action: str,
        update: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Apply one scoped program transition to the canonical root owner."""
        operation_id = _identifier(operation_id, "working-field operation_id")
        field_id = _identifier(field_id, "working-field field_id")
        if not isinstance(action, str) or not isinstance(update, Mapping):
            raise OrganismError("working-field action and update are required")
        with self._open_residencies(include_members=False) as (root, _):
            field = root.advance_working_field(
                operation_id,
                field_id=field_id,
                action=action,
                update=update,
            )
            return {
                "status": "supported",
                "field": field,
                "program_ref": field["program_ref"],
                "owner_state_sha256": root.owner.state.state_sha256,
                "generation": root.owner.state.generation,
            }
    def numerical_instrument_context(self, program_id: str) -> dict[str, Any]:
        """Return configured host-owned numerical availability for one program."""
        program_id = _identifier(program_id, "numerical instrument program_id")
        with self._open_residencies(include_members=False) as (root, _):
            report = dict(root.owner.program_resources(program_id))
            if not report.get("configured"):
                return {"status": "unconfigured", "program_id": program_id}
            computer_id = report.get("computer_id")
            if not isinstance(computer_id, str) or not computer_id:
                return {"status": "unavailable", "program_id": program_id}
            return {
                "status": "available",
                "program_id": program_id,
                "limits": asdict(root.owner.resource_limits(computer_id)),
                "generation": root.owner.state.generation,
            }

    def submit_numerical_instrument(
        self,
        operation_id: str,
        *,
        program_id: str,
        work_id: str,
        kernel: str,
        state: Mapping[str, Any],
        arguments: Mapping[str, Any] | None = None,
        kind: str | None = None,
        steps: int = 1,
        source_revision_ids: Sequence[str] = (),
        assumptions: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Submit owner state or compile compact structured source for its configured host."""
        operation_id = _identifier(operation_id, "numerical instrument operation_id")
        program_id = _identifier(program_id, "numerical instrument program_id")
        work_id = _identifier(work_id, "numerical instrument work_id")
        if not work_id.startswith(f"{program_id}:numerical:"):
            raise OrganismError("numerical work identity must be scoped to its program")
        with self._open_residencies(include_members=False) as (root, _):
            report = root.owner.program_resources(program_id)
            if not report.get("configured"):
                raise OrganismError("program numerical residency is not configured")
            computer_id = report.get("computer_id")
            if not isinstance(computer_id, str) or not computer_id:
                raise OrganismError("program numerical residency has no host computer")
            submitted_state = state
            if state.get("schema") == NUMERICAL_INSTRUMENT_STRUCTURED_STATE_SCHEMA:
                if set(state) != {"schema", "source"}:
                    raise OrganismError("structured numerical state has invalid keys")
                source = state.get("source")
                if (
                    not isinstance(source, Mapping)
                    or source.get("schema") != STRUCTURED_FIELD_PROGRAM_SCHEMA
                ):
                    raise OrganismError("structured numerical state source is invalid")
                computer = next(
                    (
                        item
                        for item in root.owner.state.computers
                        if item.computer_id == computer_id
                    ),
                    None,
                )
                if computer is None:
                    raise OrganismError("program host computer is unavailable")
                try:
                    profile = computer._scalar_profile()
                    compiled = compile_structured_program(
                        source, max_instructions=profile.program_capacity
                    )
                    submitted_state = regional_scalar_state(compiled, profile)
                except (FieldProgramError, ValueError) as exc:
                    raise OrganismError(
                        f"structured numerical state is invalid: {exc}"
                    ) from exc
            view = root.owner.submit_numerical_work(
                work_id,
                computer_id=computer_id,
                kernel=kernel,
                state=submitted_state,
                arguments=arguments,
                kind=kind,
                steps=steps,
                source_revision_ids=source_revision_ids,
                assumptions=assumptions,
            )
            dependencies = view.get("dependencies")
            if (
                not isinstance(dependencies, Mapping)
                or dependencies.get("computer_id") != computer_id
            ):
                raise OrganismError("numerical work is bound to another host computer")
            return {
                **dict(view),
                "program_id": program_id,
                "submit_operation_id": operation_id,
                "owner_state_sha256": root.owner.state.state_sha256,
                "generation": root.owner.state.generation,
            }

    def collect_numerical_instrument(
        self, operation_id: str, *, program_id: str, work_id: str,
        expected_computer_id: str,
    ) -> dict[str, Any]:
        """Collect a program-scoped work item using its durable submit identity."""
        operation_id = _identifier(operation_id, "numerical instrument operation_id")
        program_id = _identifier(program_id, "numerical instrument program_id")
        work_id = _identifier(work_id, "numerical instrument work_id")
        expected_computer_id = _identifier(expected_computer_id, "numerical submit computer_id")
        if not work_id.startswith(f"{program_id}:numerical:"):
            raise OrganismError("numerical work identity must be scoped to its program")
        with self._open_residencies(include_members=False) as (root, _):
            report = root.owner.program_resources(program_id)
            if not report.get("configured"):
                raise OrganismError("program numerical residency is not configured")
            computer_id = report.get("computer_id")
            if not isinstance(computer_id, str) or not computer_id:
                raise OrganismError("program numerical residency has no host computer")
            if computer_id != expected_computer_id:
                raise OrganismError("program host computer changed since numerical submission")
            view = root.owner.collect_numerical_work(work_id, operation_id=operation_id)
            dependencies = view.get("dependencies")
            if (
                not isinstance(dependencies, Mapping)
                or dependencies.get("computer_id") != computer_id
            ):
                raise OrganismError("numerical work is bound to another host computer")
            artifact = view.get("artifact")
            if isinstance(artifact, Mapping):
                artifact_dependencies = artifact.get("dependencies")
                if (
                    not isinstance(artifact_dependencies, Mapping)
                    or artifact_dependencies.get("computer_id") != computer_id
                ):
                    raise OrganismError("numerical result belongs to another host computer")
            return {
                **dict(view),
                "program_id": program_id,
                "owner_state_sha256": root.owner.state.state_sha256,
                "generation": root.owner.state.generation,
            }

    def cancel_numerical_instrument(
        self, operation_id: str, *, program_id: str, work_id: str,
        expected_computer_id: str,
    ) -> dict[str, Any]:
        """Cancel only a program-scoped work item on its configured host."""
        operation_id = _identifier(operation_id, "numerical instrument operation_id")
        program_id = _identifier(program_id, "numerical instrument program_id")
        work_id = _identifier(work_id, "numerical instrument work_id")
        expected_computer_id = _identifier(expected_computer_id, "numerical submit computer_id")
        if not work_id.startswith(f"{program_id}:numerical:"):
            raise OrganismError("numerical work identity must be scoped to its program")
        with self._open_residencies(include_members=False) as (root, _):
            report = root.owner.program_resources(program_id)
            if not report.get("configured"):
                raise OrganismError("program numerical residency is not configured")
            computer_id = report.get("computer_id")
            if not isinstance(computer_id, str) or not computer_id:
                raise OrganismError("program numerical residency has no host computer")
            if computer_id != expected_computer_id:
                raise OrganismError("program host computer changed since numerical submission")
            view = root.owner.cancel_numerical_work(work_id)
            dependencies = view.get("dependencies")
            if (
                not isinstance(dependencies, Mapping)
                or dependencies.get("computer_id") != computer_id
            ):
                raise OrganismError("numerical work is bound to another host computer")
            return {
                **dict(view),
                "program_id": program_id,
                "owner_state_sha256": root.owner.state.state_sha256,
                "generation": root.owner.state.generation,
            }

    def working_field_circulation_modulation(
        self, eligible_work_order: Sequence[str]
    ) -> dict[str, Any] | None:
        """Read owner-bounded circulation for this exact eligible agenda order."""
        if (
            not isinstance(eligible_work_order, (list, tuple))
            or len(eligible_work_order) > 128
            or any(not isinstance(item, str) or not item for item in eligible_work_order)
            or len(set(eligible_work_order)) != len(eligible_work_order)
        ):
            raise OrganismError("eligible working-field order is invalid")
        if not eligible_work_order:
            return None
        events = [{"sequence": index} for index in range(len(eligible_work_order))]
        with self._open_residencies(include_members=False) as (root, _):
            modulation = root.owner.circulation_modulation(events)
            return None if modulation is None else _plain(modulation)

    def inspect_embodied_field(self) -> dict[str, Any]:
        """Expose the current bounded owner projection for source-aware exchange."""
        with self._open_residencies(include_members=False) as (root, _):
            return {
                **_plain(root.owner.inspect_embodied_field()),
                "owner_state_sha256": root.owner.state.state_sha256,
                "generation": root.owner.state.generation,
            }

    def bind_regional_assessment(
        self,
        operation_id: str,
        *,
        regional_memory: Any,
        assessment_ref: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Bind an owner-verified regional Assessment to the root field."""
        operation_id = _identifier(operation_id, "regional assessment operation_id")
        if not isinstance(assessment_ref, Mapping):
            raise OrganismError("regional assessment reference must be typed")
        with self._open_residencies(include_members=False) as (root, _):
            with root.owner._lock:
                return root._register_regional_assessment(
                    operation_id,
                    regional_memory=regional_memory,
                    assessment_ref=assessment_ref,
                )

    def inspect_working_fields(self, *, limit: int = 32) -> dict[str, Any]:
        """Capture bounded working topology from the canonical root field only."""
        with self._open_residencies(include_members=False) as (root, _):
            projection = root.working_fields(limit=limit)
            return {
                **projection,
                "owner_state_sha256": root.owner.state.state_sha256,
                "generation": root.owner.state.generation,
            }

    def publish_current(self) -> dict[str, Any]:
        with self._open_residencies(include_members=False) as (root, _):
            campaign_records = [
                record
                for record_id, history in root._task()["records"].items()
                if record_id.startswith(CAMPAIGN_PREFIX)
                for record in history[-1:]
            ]
            if not campaign_records:
                raise OrganismError("no campaign is available for publication")
            campaign = _plain(campaign_records[-1]["payload"])
            publication = self._publish_locked(root, campaign)
            campaign["publication"] = publication
            self._write_record(root, record_id=campaign["campaign_id"], kind="Assessment", payload=campaign, epistemic_kind="assessed")
            return publication

    def rollback(self, generation_id: str) -> dict[str, Any]:
        """Move only the publication pointer; the external effect journal remains."""
        generation = self.publications.rollback(generation_id)
        return {
            "schema": POINTER_SCHEMA,
            "generation_id": generation["generation_id"],
            "generation_sha256": generation["generation_sha256"],
            "effect_journal_entries": self.journal.count(),
        }

    def inspect(self) -> dict[str, Any]:
        manifest = self._load_manifest()
        with self._open_residencies(include_members=True) as (root, members):
            member_status = {
                member_id: {
                    "field_state_sha256": member.owner.state.state_sha256,
                    "common_generation": member.session.status()["common_generation"],
                    "resident": member.inspect(),
                }
                for member_id, member in members.items()
            }
            affect = self._affect_projection(root)
            root_hive = _plain(root.session.status())
            return {
                "schema": SCHEMA,
                "manifest": manifest,
                "root": root.inspect(),
                "frontier": self._frontier(root),
                "affect_context": affect["context"],
                "affect": affect,
                "cohort": self._cohort(),
                "collaboration": self._collaboration_view(root),
                "members": member_status,
                "collective_hive": {
                    "home": str(self.collective_hive_home),
                    "status": root_hive["hive"],
                    "root_common_generation": root_hive["common_generation"],
                    "member_common_generations": {
                        member_id: status["common_generation"]
                        for member_id, status in member_status.items()
                    },
                },
                "publication": self.publications.current(),
                "effect_journal_entries": self.journal.count(),
            }

    def close(self) -> None:
        """Compatibility hook for callers that manage an organism explicitly."""
        return None

    def __enter__(self) -> "ResearchOrganism":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()


@contextlib.contextmanager
def open_research_organism(
    home: Path,
    *,
    workspace: Path | None = None,
    mission: str = "Understand and improve Cassi",
    member_ids: Sequence[str] = ("member-000", "member-001"),
    hive_home: Path | None = None,
) -> Iterator[ResearchOrganism]:
    organism = ResearchOrganism(
        home,
        workspace=workspace,
        mission=mission,
        member_ids=member_ids,
        hive_home=hive_home,
    )
    try:
        yield organism
    finally:
        organism.close()


__all__ = [
    "BUNDLE_SCHEMA",
    "CAMPAIGN_SCHEMA",
    "EXPERIENCE_RECEIPT_SCHEMA",
    "EXPERIENCE_SCHEMA",
    "Construction",
    "EffectJournal",
    "FRONTIER_SCHEMA",
    "MANIFEST_SCHEMA",
    "OrganismError",
    "PublicationLedger",
    "ResearchOrganism",
    "SCHEMA",
    "open_research_organism",
]
