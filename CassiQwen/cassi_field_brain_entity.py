"""Persistent field–brain entity runtime for the explicit ``field-brain`` profile.

The entity has one adaptive lifetime: ``CassiFieldWorkMemory`` and its
``FieldIntelligenceOwner``.  The llama.cpp brain is deliberately live in this
profile, but it never becomes another persistent memory or a fallback: every
accepted message and brain contribution is admitted through the same field
owner, and an unavailable brain is reported as unavailable work.

This module is intentionally separate from CassiQwen's field-only runtime
profiles.  It is the entity-service foundation described in
``../CASSI-ENTITY-DESIGN.md``.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import posixpath
import re
import sys
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Protocol, Sequence

from cassi_autonomous_researcher import AutonomousResearchDirector, ResearchRuntimeConfig
from cassi_field_qwen_workbench import CassiFieldWorkMemory, LocalQwenClient, WorkMemoryRecord

ENTITY_SCHEMA = "cassi.field-brain.entity.v1"
ENTITY_EVENT_SCHEMA = "cassi.field-brain.event.v1"
ENTITY_JOURNAL_SCHEMA = "cassi.field-brain.journal.v1"
TURN_SCHEMA = "cassi.field-brain.turn.v1"
TURN_EVENT_SCHEMA = "cassi.field-brain.turn-event.v1"
ENTITY_PROFILE = "field-brain"
ENTITY_REGIONAL_PROFILE_OVERRIDES = {"mode_count": 393_216}

_MAX_CONTENT_BYTES = 32_768
_MAX_AUXILIARY_PROMPT_BYTES = 48_000
_MAX_WORKSPACE_RECORDS = 8
_MAX_CAPABILITY_FILE_BYTES = 1_048_576
_FILE_SHA256_CAPABILITY = "file-sha256"
_THEORY_EXCERPT_CAPABILITY = "theory-excerpt"
_MAX_THEORY_EXCERPT_BYTES = 12_288
_MAX_THEORY_STUDY_SEGMENT_BYTES = 6_144
_MAX_THEORY_SEGMENT_BYTES = 18_432
_MAX_TYPED_TOOL_RESULT_PROMPT_BYTES = 10_000
class _SerializedFieldMemory:
    """Serialize field transitions shared by foreground and resident work."""

    def __init__(self, memory: Any, lock: threading.RLock) -> None:
        self._memory = memory
        self._lock = lock

    def _call(self, name: str, *args: Any, **kwargs: Any) -> Any:
        with self._lock:
            return getattr(self._memory, name)(*args, **kwargs)

    def learn(self, record: WorkMemoryRecord) -> Mapping[str, Any]:
        return self._call("learn", record)

    def recall(self, context: Mapping[str, Any], *, operation_label: str) -> Mapping[str, Any]:
        return self._call("recall", context, operation_label=operation_label)

    def state_receipt(self) -> Mapping[str, Any]:
        return self._call("state_receipt")

    def close(self) -> None:
        self._call("close")

    def __getattr__(self, name: str) -> Any:
        attribute = getattr(self._memory, name)
        if not callable(attribute):
            return attribute

        def call(*args: Any, **kwargs: Any) -> Any:
            with self._lock:
                return attribute(*args, **kwargs)

        return call



_DWARF_OBSERVATION_SOURCES = (
    {
        "source_id": "mcconnachie-2012-structural-catalog",
        "catalog": "J/AJ/144/4",
        "citation": "McConnachie 2012, AJ 144, 4",
        "objects": (
            "Segue 1", "Segue 2", "Willman 1", "Bootes I", "Coma Berenices", "Draco", "Sculptor", "Fornax",
        ),
        "likelihood_roles": ("structural-photometry candidate frame", "catalog kinematic context"),
        "artifacts": (
            ("mcconnachie2012-table3.dat", 102, "https://cdsarc.cds.unistra.fr/ftp/cats/J/AJ/144/4/table3.dat"),
            ("mcconnachie2012-table4.dat", 102, "https://cdsarc.cds.unistra.fr/ftp/cats/J/AJ/144/4/table4.dat"),
            ("mcconnachie2012-ReadMe", None, "https://cdsarc.cds.unistra.fr/ftp/cats/J/AJ/144/4/ReadMe"),
        ),
    },
    {
        "source_id": "simon-2011-segue-1-velocities",
        "catalog": "J/ApJ/733/46",
        "citation": "Simon et al. 2011, ApJ 733, 46",
        "objects": ("Segue 1",),
        "likelihood_roles": ("per-measurement line-of-sight velocity", "velocity uncertainty", "membership", "repeat-epoch binary evidence"),
        "artifacts": (
            ("segue1-simon2011-table3.dat", 522, "https://cdsarc.cds.unistra.fr/ftp/cats/J/ApJ/733/46/table3.dat"),
            ("segue1-simon2011-ReadMe", None, "https://cdsarc.cds.unistra.fr/ftp/cats/J/ApJ/733/46/ReadMe"),
        ),
    },
    {
        "source_id": "walker-2009-fornax-sculptor-velocities",
        "catalog": "J/AJ/137/3100",
        "citation": "Walker, Mateo & Olszewski 2009, AJ 137, 3100",
        "objects": ("Fornax", "Sculptor"),
        "likelihood_roles": ("per-measurement line-of-sight velocity", "velocity uncertainty", "probabilistic membership"),
        "artifacts": (
            ("fornax-walker2009-table3.dat", 3150, "https://cdsarc.cds.unistra.fr/ftp/cats/J/AJ/137/3100/table3.dat"),
            ("sculptor-walker2009-table4.dat", 1818, "https://cdsarc.cds.unistra.fr/ftp/cats/J/AJ/137/3100/table4.dat"),
            ("walker2009-ReadMe", None, "https://cdsarc.cds.unistra.fr/ftp/cats/J/AJ/137/3100/ReadMe"),
        ),
    },
    {
        "source_id": "kleyna-2002-draco-velocities",
        "catalog": "J/MNRAS/330/792",
        "citation": "Kleyna et al. 2002, MNRAS 330, 792",
        "objects": ("Draco",),
        "likelihood_roles": ("member-star line-of-sight velocity", "velocity uncertainty"),
        "artifacts": (
            ("draco-kleyna2002-table1.dat", 159, "https://cdsarc.cds.unistra.fr/ftp/cats/J/MNRAS/330/792/table1.dat"),
            ("draco-kleyna2002-ReadMe", None, "https://cdsarc.cds.unistra.fr/ftp/cats/J/MNRAS/330/792/ReadMe"),
        ),
    },
    {
        "source_id": "kirby-2013-segue-2-velocities",
        "catalog": "J/ApJ/770/16",
        "citation": "Kirby et al. 2013, ApJ 770, 16",
        "objects": ("Segue 2",),
        "likelihood_roles": ("per-target line-of-sight velocity", "velocity uncertainty", "membership classification"),
        "artifacts": (
            ("segue2-kirby2013-table2.dat", 647, "https://cdsarc.cds.unistra.fr/ftp/cats/J/ApJ/770/16/table2.dat"),
            ("segue2-kirby2013-ReadMe", None, "https://cdsarc.cds.unistra.fr/ftp/cats/J/ApJ/770/16/ReadMe"),
        ),
    },
    {
        "source_id": "koposov-2011-bootes-1-velocities",
        "catalog": "J/ApJ/736/146",
        "citation": "Koposov et al. 2011, ApJ 736, 146",
        "objects": ("Bootes I",),
        "likelihood_roles": ("per-target line-of-sight velocity", "velocity uncertainty", "membership flag", "velocity-variability probability"),
        "artifacts": (
            ("bootes1-koposov2011-table1.dat", 118, "https://cdsarc.cds.unistra.fr/ftp/cats/J/ApJ/736/146/table1.dat"),
            ("bootes1-koposov2011-ReadMe", None, "https://cdsarc.cds.unistra.fr/ftp/cats/J/ApJ/736/146/ReadMe"),
        ),
    },
    {
        "source_id": "simon-geha-2007-coma-berenices-velocities",
        "catalog": "author-hosted Simon & Geha 2007 table",
        "citation": "Simon & Geha 2007, ApJ 670, 313",
        "objects": ("Coma Berenices",),
        "likelihood_roles": ("author-hosted individual velocity and metallicity table", "membership-coded target sample"),
        "artifacts": (
            ("comaber-simongeha2007-velocities.dat", 102, "https://users.obs.carnegiescience.edu/jsimon/data/CB_feh.dat"),
            ("comaber-simon-data-page.html", None, "https://users.obs.carnegiescience.edu/jsimon/data.html"),
        ),
    },
)

_DWARF_STELLAR_POPULATION_SOURCES = (
    {
        "source_id": "martin-2008-structural-stellar-masses",
        "citation": "Martin, de Jong & Rix 2008, ApJ 684, 1075",
        "objects": ("Segue 1", "Bootes I", "Coma Berenices"),
        "evidence_role": (
            "CMD-shot-noise-aware luminosity and stellar-mass estimates under explicit population-model assumptions"
        ),
        "artifact": (
            "martin2008-structural-stellar-masses.pdf",
            "https://arxiv.org/pdf/0805.2945",
        ),
    },
    {
        "source_id": "frebel-2014-segue-1-population",
        "citation": "Frebel, Simon & Kirby 2014, ApJ 786, 74",
        "objects": ("Segue 1",),
        "evidence_role": "high-resolution chemical evidence for a short, early star-formation episode",
        "artifact": ("frebel2014-segue1-population.pdf", "https://arxiv.org/pdf/1403.6116"),
    },
    {
        "source_id": "kirby-2013-segue-2-population",
        "citation": "Kirby et al. 2013, ApJ 770, 16",
        "objects": ("Segue 2",),
        "evidence_role": "luminosity, metallicity distribution, and minimum star-formation duration",
        "artifact": ("kirby2013-segue2-population.pdf", "https://arxiv.org/pdf/1304.6080"),
    },
    {
        "source_id": "brown-2014-ultrafaint-star-formation",
        "citation": "Brown et al. 2014, ApJ 796, 91",
        "objects": ("Bootes I", "Coma Berenices"),
        "evidence_role": "HST resolved-CMD star-formation histories and population-age constraints",
        "artifact": ("brown2014-ultrafaint-star-formation.pdf", "https://arxiv.org/pdf/1410.0681"),
    },
    {
        "source_id": "gennaro-2018-coma-imf",
        "citation": "Gennaro et al. 2018, ApJ 863, 38",
        "objects": ("Coma Berenices",),
        "evidence_role": "deep HST low-mass initial-mass-function constraint",
        "artifact": ("gennaro2018-coma-imf.pdf", "https://arxiv.org/pdf/1806.08380"),
    },
    {
        "source_id": "aparicio-2001-draco-star-formation",
        "citation": "Aparicio, Carrera & Martinez-Delgado 2001, AJ 122, 2524",
        "objects": ("Draco",),
        "evidence_role": "resolved-CMD star-formation history and retention-assumption-dependent stellar-plus-remnant estimate",
        "artifact": ("aparicio2001-draco-star-formation.pdf", "https://arxiv.org/pdf/astro-ph/0108159"),
    },
    {
        "source_id": "deboer-2012-sculptor-star-formation",
        "citation": "de Boer et al. 2012, arXiv:1201.2408",
        "objects": ("Sculptor",),
        "evidence_role": "resolved-CMD star-formation history and aperture-defined total mass formed",
        "artifact": ("deboer2012-sculptor-star-formation.pdf", "https://arxiv.org/pdf/1201.2408"),
    },
    {
        "source_id": "deboer-2012-fornax-star-formation",
        "citation": "de Boer et al. 2012, arXiv:1206.6968",
        "objects": ("Fornax",),
        "evidence_role": "resolved-CMD star-formation history and aperture-defined total mass formed",
        "artifact": ("deboer2012-fornax-star-formation.pdf", "https://arxiv.org/pdf/1206.6968"),
    },
)
_DWARF_STELLAR_MASS_CONSTRAINTS = {
    "Segue 1": {
        "source_id": "martin-2008-structural-stellar-masses",
        "table": "Table 1",
        "quantity": "CMD stellar-mass estimate",
        "scope": "whole system represented by the source's SDSS structural model",
        "remnant_treatment": "not reported; this is not an admitted present-day stellar-plus-remnant mass",
        "imf_conditionals": (
            {"imf": "Kroupa", "central_msun": 600.0, "lower_1sigma_msun": 105.0, "upper_1sigma_msun": 115.0},
            {"imf": "Salpeter", "central_msun": 1300.0, "lower_1sigma_msun": 200.0, "upper_1sigma_msun": 200.0},
        ),
    },
    "Bootes I": {
        "source_id": "martin-2008-structural-stellar-masses",
        "table": "Table 1",
        "quantity": "CMD stellar-mass estimate",
        "scope": "whole system represented by the source's SDSS structural model",
        "remnant_treatment": "not reported; this is not an admitted present-day stellar-plus-remnant mass",
        "imf_conditionals": (
            {"imf": "Kroupa", "central_msun": 34_000.0, "lower_1sigma_msun": 3_000.0, "upper_1sigma_msun": 3_000.0},
            {"imf": "Salpeter", "central_msun": 67_000.0, "lower_1sigma_msun": 6_000.0, "upper_1sigma_msun": 6_000.0},
        ),
    },
    "Coma Berenices": {
        "source_id": "martin-2008-structural-stellar-masses",
        "table": "Table 1",
        "quantity": "CMD stellar-mass estimate",
        "scope": "whole system represented by the source's SDSS structural model",
        "remnant_treatment": "not reported; this is not an admitted present-day stellar-plus-remnant mass",
        "imf_conditionals": (
            {"imf": "Kroupa", "central_msun": 4_800.0, "lower_1sigma_msun": 900.0, "upper_1sigma_msun": 900.0},
            {"imf": "Salpeter", "central_msun": 9_200.0, "lower_1sigma_msun": 1_700.0, "upper_1sigma_msun": 1_700.0},
        ),
    },
    "Draco": {
        "source_id": "aparicio-2001-draco-star-formation",
        "table": "Table 5; Section 5.1",
        "quantity": "total mass in stars and stellar remnants",
        "scope": "elliptical semi-major-axis apertures",
        "retention_rule": "0.8 of the integrated source star-formation history remains locked in stars or stellar remnants",
        "aperture_conditionals": (
            {"semi_major_axis_arcmin": 7.5, "central_msun": 210_000.0},
            {"semi_major_axis_arcmin": 30.0, "central_msun": 430_000.0, "source_interpretation": "good estimate of the total real value"},
            {"semi_major_axis_arcmin": 42.0, "central_msun": 530_000.0},
        ),
        "posterior_status": "source-conditional estimate without posterior samples or reported uncertainty",
    },
    "Sculptor": {
        "source_id": "deboer-2012-sculptor-star-formation",
        "quantity": "total mass formed in stars",
        "scope": "within 1 degree elliptical radius (1.5 kpc)",
        "central_msun": 7_800_000.0,
        "posterior_status": "formed mass; no retained present-day stellar-plus-remnant mass",
    },
    "Fornax": {
        "source_id": "deboer-2012-fornax-star-formation",
        "quantity": "total mass formed in stars",
        "scope": "within 0.8 degree elliptical radius (1.9 kpc)",
        "central_msun": 43_000_000.0,
        "posterior_status": "formed mass; no retained present-day stellar-plus-remnant mass",
    },
}

class BrainUnavailable(RuntimeError):
    """The explicitly required pretrained brain could not perform an operation."""


class TurnNotFound(LookupError):
    """A requested typed turn does not exist in the entity journal."""


class TurnConflict(RuntimeError):
    """A typed turn cannot accept the requested lifecycle transition."""



class CapabilityApprovalRequired(PermissionError):
    """A bounded external capability lacks its required explicit approval."""

class BrainClient(Protocol):
    """The model boundary used by the entity, intentionally without memory methods."""

    model_id: str
    model_sha256: str

    def complete(
        self,
        *,
        prompt: str,
        max_tokens: int,
        thinking: bool = False,
        response_format: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]: ...


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > 256:
        raise ValueError(f"{label} must be bounded nonempty text")
    if any(ord(character) < 32 for character in value):
        raise ValueError(f"{label} contains a control character")
    return value


def _content(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be nonempty text")
    if len(value.encode("utf-8")) > _MAX_CONTENT_BYTES:
        raise ValueError(f"{label} exceeds {_MAX_CONTENT_BYTES} UTF-8 bytes")
    return value


def _timestamp(value: str | None) -> str:
    if value is None:
        return datetime.now(UTC).isoformat(timespec="microseconds")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("observed_at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("observed_at must include a UTC offset")
    return parsed.astimezone(UTC).isoformat(timespec="microseconds")


def _relative_target(value: Any, *, root: Path) -> tuple[str, Path]:
    """Resolve one bounded file target without permitting a path escape."""
    target = _identifier(value, "target_path")
    candidate = Path(target)
    if candidate.is_absolute():
        raise ValueError("target_path must be relative to the capability root")
    resolved = (root / candidate).resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("target_path escapes the capability root") from exc
    if not resolved.is_file():
        raise ValueError("target_path must identify an existing regular file")
    size = resolved.stat().st_size
    if size > _MAX_CAPABILITY_FILE_BYTES:
        raise ValueError(f"target_path exceeds {_MAX_CAPABILITY_FILE_BYTES} bytes")
    return relative.as_posix(), resolved


def _bounded_int(value: Any, label: str, *, minimum: int, maximum: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
        raise ValueError(f"{label} must be an integer in {minimum}..{maximum}")
    return value


def _theory_target(value: Any, *, root: Path) -> tuple[str, Path]:
    return _relative_target(value, root=root)



def _utf8_segments(source: bytes, *, maximum_bytes: int = _MAX_THEORY_SEGMENT_BYTES) -> list[tuple[int, int, str]]:
    """Split a complete UTF-8 source into bounded, lossless prompt segments."""
    _bounded_int(maximum_bytes, "maximum_bytes", minimum=1, maximum=_MAX_THEORY_SEGMENT_BYTES)
    segments: list[tuple[int, int, str]] = []
    start = 0
    while start < len(source):
        end = min(start + maximum_bytes, len(source))
        while end > start:
            try:
                text = source[start:end].decode("utf-8")
                break
            except UnicodeDecodeError:
                end -= 1
        else:
            raise ValueError("theory source cannot be segmented as UTF-8")
        segments.append((start, end, text))
        start = end
    return segments

_FOUNDATIONAL_REGISTRY_PATHS = (
    "reading-guide.md",
    "open-questions-cassi-answers.md",
    "parameter-inventory.md",
    "predictions/falsifiable-predictions.md",
)


def _section_role(heading: str) -> str:
    """Classify a heading's explicit documentary role without inferring its content."""
    lowered = heading.casefold()
    if "status" in lowered:
        return "status"
    if any(word in lowered for word in ("open question", "question", "unknown", "problem")):
        return "open-question"
    if any(word in lowered for word in ("prediction", "falsif", "test", "experiment", "observation")):
        return "empirical-obligation"
    if any(word in lowered for word in ("equation", "parameter", "field", "law", "operator", "model")):
        return "mathematical-object"
    return "section"


def _markdown_section_anchors(source: bytes) -> list[Mapping[str, Any]]:
    """Return citable Markdown heading spans while preserving byte-exact provenance."""
    text = source.decode("utf-8")
    headings: list[tuple[int, int, str]] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        match = re.match(r"^(#{1,6})[ \t]+(.+?)\s*$", line)
        if match is not None:
            headings.append((offset, len(match.group(1)), match.group(2).strip()))
        offset += len(line.encode("utf-8"))
    anchors: list[Mapping[str, Any]] = []
    for index, (start, level, heading) in enumerate(headings):
        end = len(source)
        for next_start, next_level, _next_heading in headings[index + 1 :]:
            if next_level <= level:
                end = next_start
                break
        anchors.append(
            {
                "heading": heading,
                "level": level,
                "structural_role": _section_role(heading),
                "byte_start": start,
                "byte_end": end,
                "content_sha256": hashlib.sha256(source[start:end]).hexdigest(),
            }
        )
    return anchors

_MARKDOWN_DOCUMENT_REFERENCE = re.compile(
    rb"\]\(([^)#\s]+\.md)(?:#[^)]*)?\)|`([^`\s]+\.md)(?:#[^`]*)?`"
)


def _resolve_theory_reference(source_path: str, reference: bytes, known_paths: set[str]) -> str | None:
    """Resolve one Markdown-local source reference only when it stays in this atlas."""
    try:
        target = reference.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if "://" in target or target.startswith("/"):
        return None
    resolved = posixpath.normpath((PurePosixPath(source_path).parent / target).as_posix())
    return resolved if resolved in known_paths else None


def _anchor_node_id(source_path: str, byte_start: int) -> str:
    return f"{source_path}:{byte_start:012d}"


def _foundation_documents(root: Path) -> dict[str, Path]:
    """Select CassiTheory's foundations and the canonical registries once."""
    foundation_root = root / "foundations"
    documents = (
        {
            path.relative_to(root).as_posix(): path
            for path in foundation_root.rglob("*.md")
            if path.is_file()
        }
        if foundation_root.is_dir()
        else {}
    )
    for relative in _FOUNDATIONAL_REGISTRY_PATHS:
        candidate = root / relative
        if candidate.is_file():
            documents[relative] = candidate
    return documents

@dataclass(frozen=True, slots=True)
class EntityConfig:
    """Fixed execution policy for one explicit field–brain lifetime."""

    data_home: Path
    capability_root: Path | None = None
    theory_root: Path | None = None
    entity_id: str = "cassi"
    max_response_tokens: int = 384
    max_question_tokens: int = 192
    brain_thinking: bool = False
    research_home: Path | None = None
    research_roots: tuple[Path, ...] | None = None
    research_network_hosts: tuple[str, ...] = ()
    research_cycle_interval_seconds: float = 1.0
    research_default_tools: tuple[str, ...] = (
        "list_files",
        "read_file",
        "search_text",
        "write_artifact",
        "inspect_artifact",
    )
    research_python_executable: str | None = None
    research_resident_enabled: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "data_home", Path(self.data_home).resolve())
        root = Path.cwd() if self.capability_root is None else Path(self.capability_root)
        object.__setattr__(self, "capability_root", root.resolve())
        theory_root = (
            (Path.cwd().parent / "CassiTheory") if self.theory_root is None else Path(self.theory_root)
        )
        object.__setattr__(self, "theory_root", theory_root.resolve())
        research_home = (
            self.data_home / "research" if self.research_home is None else Path(self.research_home)
        )
        object.__setattr__(self, "research_home", research_home.resolve())
        research_roots = (
            (self.capability_root,) if self.research_roots is None else tuple(Path(path).resolve() for path in self.research_roots)
        )
        object.__setattr__(self, "research_roots", research_roots)
        object.__setattr__(
            self,
            "research_network_hosts",
            tuple(dict.fromkeys(host.lower().strip() for host in self.research_network_hosts if host.strip())),
        )
        object.__setattr__(
            self,
            "research_python_executable",
            self.research_python_executable or sys.executable,
        )
        if self.research_cycle_interval_seconds <= 0:
            raise ValueError("research_cycle_interval_seconds must be positive")
        if not isinstance(self.research_resident_enabled, bool):
            raise ValueError("research_resident_enabled must be boolean")
        _identifier(self.entity_id, "entity_id")
        if self.max_response_tokens < 1 or self.max_question_tokens < 1:
            raise ValueError("model token budgets must be positive")
        if not isinstance(self.brain_thinking, bool):
            raise ValueError("brain_thinking must be boolean")


class EntityJournal:
    """Durable nonadaptive delivery and idempotency journal.

    Field records remain the entity's semantic memory.  This journal only
    remembers request digests, public event ordering, and already-delivered
    result envelopes, so replaying an HTTP request cannot generate another
    model turn or count an experience twice.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.RLock()
        self._requests: dict[str, Mapping[str, Any]] = {}
        self._executions: dict[str, Mapping[str, Any]] = {}
        self._proposals: dict[str, Mapping[str, Any]] = {}
        self._approvals: dict[str, Mapping[str, Any]] = {}
        self._events: list[Mapping[str, Any]] = []
        self._turns: dict[str, Mapping[str, Any]] = {}
        self._turn_events: dict[str, list[Mapping[str, Any]]] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                row = json.loads(line)
                if not isinstance(row, dict) or row.get("schema") != ENTITY_JOURNAL_SCHEMA:
                    raise RuntimeError(f"invalid entity journal row {line_number}")
                request = row.get("request")
                events = row.get("events")
                if not isinstance(request, Mapping) or not isinstance(events, list):
                    raise RuntimeError(f"incomplete entity journal row {line_number}")
                request_id = _identifier(request.get("request_id"), "journal request_id")
                if request_id in self._requests:
                    raise RuntimeError(f"duplicate entity journal request {request_id}")
                self._requests[request_id] = row
                for event in events:
                    if not isinstance(event, Mapping):
                        raise RuntimeError(f"invalid entity event in row {line_number}")
                    self._events.append(dict(event))
                turn_id = row.get("turn_id")
                raw_turn_events = row.get("turn_events")
                if turn_id is not None or raw_turn_events is not None:
                    turn_id = _identifier(turn_id, "turn_id")
                    turn = row.get("turn")
                    if turn is not None:
                        if not isinstance(turn, Mapping) or turn.get("turn_id") != turn_id:
                            raise RuntimeError(f"entity turn is invalid at line {line_number}")
                        self._turns[turn_id] = dict(turn)
                    if not isinstance(raw_turn_events, list):
                        raise RuntimeError(f"entity turn events are invalid at line {line_number}")
                    target = self._turn_events.setdefault(turn_id, [])
                    for event in raw_turn_events:
                        if (
                            not isinstance(event, Mapping)
                            or event.get("schema") != TURN_EVENT_SCHEMA
                            or event.get("turn_id") != turn_id
                        ):
                            raise RuntimeError(f"invalid entity turn event at line {line_number}")
                        target.append(dict(event))
                result = row.get("result")
                if not isinstance(result, Mapping):
                    raise RuntimeError(f"entity journal result is invalid at row {line_number}")
                definition = result.get("proposal_definition")
                if isinstance(definition, Mapping):
                    proposal_id = _identifier(definition.get("proposal_id"), "proposal_id")
                    self._proposals[proposal_id] = dict(definition)
                approval = result.get("approval")
                if isinstance(approval, Mapping):
                    proposal_id = _identifier(approval.get("proposal_id"), "approval proposal_id")
                    self._approvals[proposal_id] = dict(approval)
                if "proposal_id" in result and isinstance(result.get("outcome"), Mapping):
                    proposal_id = _identifier(result.get("proposal_id"), "execution proposal_id")
                    self._executions[proposal_id] = dict(result)
        expected = list(range(1, len(self._events) + 1))
        actual = [event.get("cursor") for event in self._events]
        if actual != expected:
            raise RuntimeError("entity event cursor is not contiguous")
        for turn_id, events in self._turn_events.items():
            expected = list(range(1, len(events) + 1))
            actual = [event.get("cursor") for event in events]
            if actual != expected:
                raise RuntimeError(f"entity turn cursor is not contiguous for {turn_id}")

    def lookup(self, request_id: str, payload_sha256: str) -> Mapping[str, Any] | None:
        with self._lock:
            prior = self._requests.get(request_id)
            if prior is None:
                return None
            request = prior["request"]
            if request.get("payload_sha256") != payload_sha256:
                raise ValueError("request_id was already used with different content")
            result = prior.get("result")
            if not isinstance(result, Mapping):
                raise RuntimeError("entity journal request lacks result")
            return dict(result)

    def commit(
        self,
        *,
        request_id: str,
        payload_sha256: str,
        event_specs: Sequence[Mapping[str, Any]],
        result: Mapping[str, Any],
        turn: Mapping[str, Any] | None = None,
        turn_id: str | None = None,
        turn_event_specs: Sequence[Mapping[str, Any]] = (),
        allow_turn_update: bool = False,
    ) -> Mapping[str, Any]:
        with self._lock:
            prior = self.lookup(request_id, payload_sha256)
            if prior is not None:
                return prior
            normalized_turn = None
            resolved_turn_id = None if turn_id is None else _identifier(turn_id, "turn_id")
            if turn is not None:
                normalized_turn = json.loads(_canonical(turn))
                embedded_turn_id = _identifier(normalized_turn.get("turn_id"), "turn_id")
                if resolved_turn_id is not None and embedded_turn_id != resolved_turn_id:
                    raise ValueError("turn_id does not match the typed turn")
                resolved_turn_id = embedded_turn_id
            if turn_event_specs and resolved_turn_id is None:
                raise ValueError("typed turn events require a turn_id")
            if resolved_turn_id is not None:
                existing_turn = self._turns.get(resolved_turn_id)
                if normalized_turn is not None and existing_turn is not None and not allow_turn_update:
                    raise ValueError("turn_id was already committed with different content")
                if normalized_turn is None and existing_turn is None:
                    raise ValueError("typed turn does not exist")
            events: list[dict[str, Any]] = []
            for spec in event_specs:
                kind = _identifier(spec.get("kind"), "event kind")
                payload = spec.get("payload")
                if not isinstance(payload, Mapping):
                    raise ValueError("event payload must be an object")
                cursor = len(self._events) + len(events) + 1
                events.append(
                    {
                        "schema": ENTITY_EVENT_SCHEMA,
                        "cursor": cursor,
                        "event_id": f"entity-event:{cursor:016d}",
                        "kind": kind,
                        "payload": json.loads(_canonical(payload)),
                    }
                )
            turn_events: list[dict[str, Any]] = []
            for spec in turn_event_specs:
                if resolved_turn_id is None:
                    raise ValueError("typed turn event has no turn_id")
                kind = _identifier(spec.get("kind"), "turn event kind")
                payload = spec.get("payload")
                if not isinstance(payload, Mapping):
                    raise ValueError("turn event payload must be an object")
                cursor = len(self._turn_events.get(resolved_turn_id, ())) + len(turn_events) + 1
                turn_events.append(
                    {
                        "schema": TURN_EVENT_SCHEMA,
                        "turn_id": resolved_turn_id,
                        "cursor": cursor,
                        "event_id": f"turn-event:{resolved_turn_id}:{cursor:016d}",
                        "kind": kind,
                        "payload": json.loads(_canonical(payload)),
                    }
                )
            row: dict[str, Any] = {
                "schema": ENTITY_JOURNAL_SCHEMA,
                "request": {"request_id": request_id, "payload_sha256": payload_sha256},
                "events": events,
                "result": json.loads(_canonical(result)),
            }
            if resolved_turn_id is not None:
                row["turn_id"] = resolved_turn_id
            if normalized_turn is not None:
                row["turn"] = normalized_turn
            if turn_events:
                row["turn_events"] = turn_events
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            self._requests[request_id] = row
            self._events.extend(events)
            if normalized_turn is not None and resolved_turn_id is not None:
                self._turns[resolved_turn_id] = normalized_turn
            if turn_events and resolved_turn_id is not None:
                self._turn_events.setdefault(resolved_turn_id, []).extend(turn_events)
            definition = result.get("proposal_definition")
            if isinstance(definition, Mapping):
                proposal_id = _identifier(definition.get("proposal_id"), "proposal_id")
                self._proposals[proposal_id] = dict(definition)
            approval = result.get("approval")
            if isinstance(approval, Mapping):
                proposal_id = _identifier(approval.get("proposal_id"), "approval proposal_id")
                self._approvals[proposal_id] = dict(approval)
            if "proposal_id" in result and isinstance(result.get("outcome"), Mapping):
                proposal_id = _identifier(result.get("proposal_id"), "execution proposal_id")
                self._executions[proposal_id] = dict(result)
            return dict(result)

    def turn(self, turn_id: str) -> Mapping[str, Any] | None:
        turn_id = _identifier(turn_id, "turn_id")
        with self._lock:
            turn = self._turns.get(turn_id)
            return None if turn is None else dict(turn)

    def turn_events_after(self, turn_id: str, cursor: int) -> list[Mapping[str, Any]]:
        turn_id = _identifier(turn_id, "turn_id")
        if not isinstance(cursor, int) or cursor < 0:
            raise ValueError("turn event cursor must be a nonnegative integer")
        with self._lock:
            if turn_id not in self._turns:
                raise TurnNotFound(f"unknown typed turn {turn_id}")
            return [
                dict(event)
                for event in self._turn_events.get(turn_id, ())
                if int(event["cursor"]) > cursor
            ]

    def turn_latest_cursor(self, turn_id: str) -> int:
        turn_id = _identifier(turn_id, "turn_id")
        with self._lock:
            if turn_id not in self._turns:
                raise TurnNotFound(f"unknown typed turn {turn_id}")
            return len(self._turn_events.get(turn_id, ()))
    def events_after(self, cursor: int) -> list[Mapping[str, Any]]:
        if not isinstance(cursor, int) or cursor < 0:
            raise ValueError("event cursor must be a nonnegative integer")
        with self._lock:
            return [dict(event) for event in self._events if int(event["cursor"]) > cursor]

    @property
    def latest_cursor(self) -> int:
        with self._lock:
            return len(self._events)

    def proposal(self, proposal_id: str) -> Mapping[str, Any]:
        with self._lock:
            proposal = self._proposals.get(_identifier(proposal_id, "proposal_id"))
            if proposal is None:
                raise ValueError("unknown capability proposal")
            return dict(proposal)

    def approval(self, proposal_id: str) -> Mapping[str, Any] | None:
        with self._lock:
            approval = self._approvals.get(_identifier(proposal_id, "proposal_id"))
            return None if approval is None else dict(approval)

    def execution(self, proposal_id: str) -> Mapping[str, Any] | None:
        with self._lock:
            execution = self._executions.get(_identifier(proposal_id, "proposal_id"))
            return None if execution is None else dict(execution)


class FieldBrainEntity:

    """One durable entity with a field-owned lifetime and a required live brain."""

    def __init__(
        self,
        config: EntityConfig,
        *,
        brain: BrainClient,
        memory: CassiFieldWorkMemory | None = None,
    ) -> None:
        self.config = config
        self.brain = brain
        self._lock = threading.RLock()
        self._field_lock = threading.RLock()
        raw_memory = memory or CassiFieldWorkMemory(
            config.data_home / "field",
            profile_overrides=ENTITY_REGIONAL_PROFILE_OVERRIDES,
        )
        self.memory = _SerializedFieldMemory(raw_memory, self._field_lock)
        self._owns_memory = memory is None
        self.journal = EntityJournal(config.data_home / "entity-events.jsonl")
        self.researcher = AutonomousResearchDirector(
            ResearchRuntimeConfig(
                home=self.config.research_home,
                allowed_roots=self.config.research_roots,
                allowed_network_hosts=self.config.research_network_hosts,
                python_executable=self.config.research_python_executable,
                cycle_interval_seconds=self.config.research_cycle_interval_seconds,
                default_tools=self.config.research_default_tools,
            ),
            brain=self.brain,
            memory=self.memory,
        )
        self._closed = False

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            try:
                self.researcher.stop()
            finally:
                if self._owns_memory:
                    self.memory.close()
                self._closed = True

    def __enter__(self) -> "FieldBrainEntity":
        return self

    def __exit__(self, _exc_type: Any, _exc: Any, _traceback: Any) -> None:
        self.close()

    def _context(self, conversation_id: str, project_id: str) -> Mapping[str, Any]:
        return {
            "conversation_id": conversation_id,
            "entity_id": self.config.entity_id,
            "project_id": project_id,
        }

    def _record(
        self,
        *,
        source_id: str,
        context: Mapping[str, Any],
        observed_at: str,
        kind: str,
        payload: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        return self.memory.learn(
            WorkMemoryRecord(
                source_id=source_id,
                context=context,
                observed_timestamp=observed_at,
                labels=("field-brain", kind),
                payload={"entity_schema": ENTITY_SCHEMA, "kind": kind, **dict(payload)},
            )
        )

    def _workspace(
        self,
        *,
        context: Mapping[str, Any],
        operation_label: str,
        exclude_source_ids: Sequence[str] = (),
    ) -> Mapping[str, Any]:
        predecessor = self.memory.state_receipt().get("state_sha256")
        if not isinstance(predecessor, str) or len(predecessor) != 64:
            raise RuntimeError("field work memory did not expose a state fingerprint")
        recalled = self.memory.recall(
            context,
            operation_label=f"{operation_label}:{predecessor}",
        )
        rows = recalled.get("records", [])
        if not isinstance(rows, list):
            raise RuntimeError("field work memory returned invalid workspace records")
        excluded = set(exclude_source_ids)
        selected = rows[-_MAX_WORKSPACE_RECORDS:]
        return {
            "context": dict(context),
            "field_state_sha256": recalled.get("field_state_after_sha256"),
            "records": [
                {
                    "source_id": row.get("source_id"),
                    "payload": row.get("payload"),
                    "source_revision_id": row.get("source_revision_id"),
                }
                for row in selected
                if isinstance(row, Mapping) and row.get("source_id") not in excluded
            ],
        }

    @staticmethod
    def _workspace_prompt(workspace: Mapping[str, Any], instruction: str) -> str:
        return (
            "You are the pretrained brain participating in the continuing Cassi entity. "
            "Treat WORKSPACE records as attributed material: proposed model text is not an observed fact. "
            "Do not claim external actions were performed. Give a concrete, evidence-aware response.\n\n"
            f"WORKSPACE:\n{json.dumps(workspace, ensure_ascii=False, sort_keys=True)}\n\n"
            f"TASK:\n{instruction}"
        )

    def _complete(
        self,
        *,
        prompt: str,
        max_tokens: int,
        thinking: bool,
        response_format: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        try:
            response = self.brain.complete(
                prompt=prompt,
                max_tokens=max_tokens,
                thinking=thinking,
                response_format=response_format,
            )
        except Exception as exc:
            raise BrainUnavailable(f"required llama.cpp brain is unavailable: {exc}") from exc
        content = response.get("content")
        if not isinstance(content, str) or not content.strip():
            raise BrainUnavailable("required llama.cpp brain returned no usable content")
        return dict(response)


    def auxiliary(
        self,
        *,
        request_id: str,
        purpose: str,
        prompt: str,
        max_tokens: int,
    ) -> Mapping[str, Any]:
        """Run one non-learning Harness auxiliary request through the live brain."""
        request_id = _identifier(request_id, "request_id")
        if purpose not in {"compaction", "session-title"}:
            raise ValueError("purpose must be compaction or session-title")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be nonempty text")
        if len(prompt.encode("utf-8")) > _MAX_AUXILIARY_PROMPT_BYTES:
            raise ValueError(f"prompt exceeds {_MAX_AUXILIARY_PROMPT_BYTES} UTF-8 bytes")
        if not isinstance(max_tokens, int) or isinstance(max_tokens, bool) or not 1 <= max_tokens <= 4_096:
            raise ValueError("max_tokens must be an integer in 1..4096")
        try:
            response = self.brain.complete(
                prompt=prompt,
                max_tokens=max_tokens,
                thinking=self.config.brain_thinking,
                response_format=None,
            )
        except Exception as exc:
            raise BrainUnavailable(f"required llama.cpp brain is unavailable: {exc}") from exc
        content = response.get("content")
        if not isinstance(content, str) or not content.strip():
            raise BrainUnavailable("required llama.cpp brain returned no usable auxiliary content")
        return {
            "schema": "cassi.field-brain.auxiliary.v1",
            "request_id": request_id,
            "purpose": purpose,
            "response": content.strip(),
            "model": {
                "id": getattr(self.brain, "model_id", "unidentified"),
                "sha256": getattr(self.brain, "model_sha256", "unidentified"),
            },
            "usage": dict(response.get("usage", {}))
            if isinstance(response.get("usage"), Mapping)
            else {},
            "learning": False,
        }

    @staticmethod
    def _brain_json(response: Mapping[str, Any], *, fields: frozenset[str]) -> Mapping[str, str]:
        raw = response["content"]
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise BrainUnavailable("required llama.cpp brain returned invalid structured content") from exc
        if (
            not isinstance(decoded, dict)
            or set(decoded) != fields
            or any(not isinstance(decoded[name], str) or not decoded[name].strip() for name in fields)
        ):
            raise BrainUnavailable(
                "required llama.cpp brain returned an incompatible structured contribution"
            )
        return {name: decoded[name] for name in fields}

    @staticmethod
    def _response_schema(
        fields: frozenset[str], *, max_length: int = 1024
    ) -> Mapping[str, Any]:
        """Ask llama.cpp to enforce the small response object at decode time."""
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "field_brain_response",
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": sorted(fields),
                    "properties": {
                        field: {"type": "string", "maxLength": max_length}
                        for field in sorted(fields)
                    },
                },
            },
        }

    @staticmethod
    def _typed_action(response: Mapping[str, Any]) -> Mapping[str, Any]:
        contribution = FieldBrainEntity._brain_json(
            response,
            fields=frozenset({"action", "response", "tool_name", "tool_arguments"}),
        )
        action = contribution["action"]
        if action not in {"respond", "call_tool"}:
            raise BrainUnavailable(f"required llama.cpp brain returned unsupported typed-turn action {action!r}")
        if action == "respond":
            if contribution["tool_name"] != "none" or contribution["tool_arguments"] != "{}":
                raise BrainUnavailable("typed response action carried a tool operation")
            return {
                "action": action,
                "response": contribution["response"],
            }
        if contribution["tool_name"] == "none":
            raise BrainUnavailable("typed tool action omitted its tool name")
        try:
            arguments = json.loads(contribution["tool_arguments"])
        except json.JSONDecodeError as exc:
            raise BrainUnavailable("typed tool action carried invalid JSON arguments") from exc
        if not isinstance(arguments, dict):
            raise BrainUnavailable("typed tool action arguments must be a JSON object")
        return {
            "action": action,
            "response": contribution["response"],
            "tool_name": contribution["tool_name"],
            "arguments": json.loads(_canonical(arguments)),
        }

    @staticmethod
    def _typed_catalog(tool_catalog: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
        """Keep the model-facing catalog within the live brain's context budget."""
        def compact_schema(value: Any) -> Any:
            if isinstance(value, Mapping):
                return {
                    key: compact_schema(item)
                    for key, item in value.items()
                    if key not in {"description", "examples", "default", "title"}
                }
            if isinstance(value, list):
                return [compact_schema(item) for item in value]
            return value

        compact: list[Mapping[str, Any]] = []
        for item in tool_catalog:
            if not isinstance(item, Mapping) or not isinstance(item.get("name"), str):
                continue
            entry: dict[str, Any] = {"name": item["name"]}
            description = item.get("description")
            if isinstance(description, str) and description:
                entry["description"] = description[:256]
            parameters = item.get("parameters")
            if isinstance(parameters, Mapping):
                entry["parameters"] = compact_schema(parameters)
            compact.append(entry)
        return compact

    @staticmethod
    def _typed_tool_result_for_prompt(tool_result: Mapping[str, Any]) -> Mapping[str, Any]:
        encoded = _canonical(tool_result)
        if len(encoded) <= _MAX_TYPED_TOOL_RESULT_PROMPT_BYTES:
            return tool_result
        text = encoded.decode("utf-8")
        half = 3_800
        bounded = {
            "call_id": tool_result.get("call_id"),
            "name": tool_result.get("name"),
            "arguments": tool_result.get("arguments"),
            "is_error": tool_result.get("is_error"),
            "prompt_truncated": True,
            "full_result_sha256": hashlib.sha256(encoded).hexdigest(),
            "content": [{
                "type": "text",
                "text": (
                    "[tool result truncated for the brain context; the full result is retained by the entity]\n"
                    f"{text[:half]}\n...\n{text[-half:]}"
                ),
            }],
        }
        return bounded

    @staticmethod
    def _typed_instruction(
        content: str,
        tool_catalog: Sequence[Mapping[str, Any]],
        *,
        tool_result: Mapping[str, Any] | None = None,
    ) -> str:
        catalog = json.dumps(FieldBrainEntity._typed_catalog(tool_catalog), ensure_ascii=False, sort_keys=True)
        if tool_result is None:
            continuation = (
                "Choose `call_tool` only when the newest user message requires one of the listed "
                "tools. Choose `respond` when no tool is needed. Do not claim a tool ran; the host "
                "will execute a proposed call."
            )
        else:
            continuation = (
                "A host tool has returned the result below. Use it as observed input and now choose "
                "`respond` or one next `call_tool`; do not repeat the completed call unless the "
                "returned error requires a deliberate retry."
            )
        instruction = (
            "This is a typed turn in the continuing Cassi entity.\n"
            "Return ONLY a JSON object with exactly four string keys: `action`, `response`, "
            "`tool_name`, and `tool_arguments`.\n"
            "For `respond`, set action to `respond`, put the user-facing answer in `response`, "
            "set tool_name to `none`, and set tool_arguments to `{}`.\n"
            "For `call_tool`, set action to `call_tool`, set response to `none`, put an exact "
            "catalog tool name in tool_name, and put a JSON object encoded as a string in "
            "tool_arguments.\n"
            f"ORIGINAL USER MESSAGE:\n{content}\n"
            f"TOOL CATALOG:\n{catalog}\n"
            f"{continuation}"
        )
        if tool_result is not None:
            instruction += (
                f"\nTOOL RESULT:\n{json.dumps(FieldBrainEntity._typed_tool_result_for_prompt(tool_result), ensure_ascii=False, sort_keys=True)}"
            )
        return instruction

    @staticmethod
    def _typed_tool_call_id(turn_id: str, ordinal: int, name: str, arguments: Mapping[str, Any]) -> str:
        digest = _sha256(
            {
                "turn_id": turn_id,
                "ordinal": ordinal,
                "name": name,
                "arguments": arguments,
            }
        )
        return f"cassi-tool-call:{digest[:48]}"

    @staticmethod
    def _normalize_tool_result(result: Mapping[str, Any]) -> Mapping[str, Any]:
        call_id = _identifier(result.get("call_id"), "tool result call_id")
        name = _identifier(result.get("name"), "tool result name")
        arguments = result.get("arguments")
        if not isinstance(arguments, Mapping):
            raise ValueError("tool result arguments must be an object")
        content = result.get("content")
        if content is None:
            raise ValueError("tool result content is required")
        normalized_content = json.loads(_canonical(content))
        if len(_canonical(normalized_content)) > _MAX_CONTENT_BYTES:
            raise ValueError(f"tool result content exceeds {_MAX_CONTENT_BYTES} bytes")
        is_error = result.get("is_error", False)
        if not isinstance(is_error, bool):
            raise ValueError("tool result is_error must be boolean")
        return {
            "call_id": call_id,
            "name": name,
            "arguments": json.loads(_canonical(arguments)),
            "content": normalized_content,
            "is_error": is_error,
        }

    def receive_message(

        self,
        *,
        request_id: str,
        conversation_id: str,
        project_id: str,
        content: str,
        observed_at: str | None = None,
    ) -> Mapping[str, Any]:
        """Admit one turn, invoke the brain, and retain its attributed response."""
        request_id = _identifier(request_id, "request_id")
        conversation_id = _identifier(conversation_id, "conversation_id")
        project_id = _identifier(project_id, "project_id")
        content = _content(content, "message content")
        occurred = _timestamp(observed_at)
        payload = {
            "conversation_id": conversation_id,
            "project_id": project_id,
            "content": content,
            "observed_at": occurred,
            "kind": "message",
        }
        digest = _sha256(payload)
        with self._lock:
            cached = self.journal.lookup(request_id, digest)
            if cached is not None:
                return {**cached, "idempotent_replay": True}
            context = self._context(conversation_id, project_id)
            message = self._record(
                source_id=f"entity:message:{request_id}",
                context=context,
                observed_at=occurred,
                kind="message",
                payload={"content": content, "request_id": request_id},
            )
            workspace = self._workspace(context=context, operation_label=f"message:{request_id}")
            brain = self._complete(
                prompt=self._workspace_prompt(
                    workspace,
                    "Return ONLY a JSON object with exactly one key, `response`. "
                    "Its string value directly answers the newest user message. "
                    "Do not reproduce the workspace or claim an external action occurred.",
                ),
                max_tokens=self.config.max_response_tokens,
                thinking=self.config.brain_thinking,
                response_format=self._response_schema(frozenset({"response"})),
            )
            contribution = self._brain_json(brain, fields=frozenset({"response"}))
            brain_record = self._record(
                source_id=f"entity:brain-response:{request_id}",
                context=context,
                observed_at=occurred,
                kind="brain-response",
                payload={
                    "content": contribution["response"],
                    "raw_content": brain["content"],
                    "model_id": getattr(self.brain, "model_id", "unidentified"),
                    "model_sha256": getattr(self.brain, "model_sha256", "unidentified"),
                    "message_source_revision_id": message.get("source_revision_id"),
                    "request_id": request_id,
                    "usage": brain.get("usage", {}),
                },
            )
            result = {
                "schema": ENTITY_SCHEMA,
                "entity_id": self.config.entity_id,
                "request_id": request_id,
                "conversation_id": conversation_id,
                "project_id": project_id,
                "response": contribution["response"],
                "model": {
                    "id": getattr(self.brain, "model_id", "unidentified"),
                    "sha256": getattr(self.brain, "model_sha256", "unidentified"),
                },
                "field_state_sha256": brain_record.get("state_sha256"),
                "message_source_revision_id": message.get("source_revision_id"),
                "brain_source_revision_id": brain_record.get("source_revision_id"),
                "usage": brain.get("usage", {}),
                "idempotent_replay": False,
            }
            return self.journal.commit(
                request_id=request_id,
                payload_sha256=digest,
                event_specs=(
                    {
                        "kind": "message-admitted",
                        "payload": {
                            "request_id": request_id,
                            "conversation_id": conversation_id,
                            "project_id": project_id,
                            "source_revision_id": message.get("source_revision_id"),
                        },
                    },
                    {
                        "kind": "brain-response",
                        "payload": {
                            "request_id": request_id,
                            "source_revision_id": brain_record.get("source_revision_id"),
                            "model_id": result["model"]["id"],
                        },
                    },
                ),
                result=result,
            )

    def receive_turn(
        self,
        *,
        turn_id: str,
        request_id: str,
        conversation_id: str,
        project_id: str,
        content: str,
        kind: str = "user-message",
        source: Mapping[str, Any] | None = None,
        tool_catalog: Sequence[Mapping[str, Any]] | None = None,
        host_scope: Mapping[str, Any] | None = None,
        observed_at: str | None = None,
    ) -> Mapping[str, Any]:
        """Admit one typed conversation turn without duplicating legacy messages."""
        turn_id = _identifier(turn_id, "turn_id")
        request_id = _identifier(request_id, "request_id")
        conversation_id = _identifier(conversation_id, "conversation_id")
        project_id = _identifier(project_id, "project_id")
        content = _content(content, "turn content")
        kind = _identifier(kind, "turn kind")
        if kind not in {"user-message", "continuation"}:
            raise ValueError("turn kind must be user-message or continuation")
        occurred = _timestamp(observed_at)
        if source is None:
            normalized_source: Mapping[str, Any] = {}
        elif isinstance(source, Mapping):
            normalized_source = json.loads(_canonical(source))
        else:
            raise ValueError("turn source must be an object")
        normalized_catalog: list[Mapping[str, Any]] = []
        if tool_catalog is not None:
            if not isinstance(tool_catalog, Sequence) or isinstance(tool_catalog, (str, bytes)):
                raise ValueError("turn tool_catalog must be an array")
            seen_tools: set[str] = set()
            for item in tool_catalog:
                if not isinstance(item, Mapping):
                    raise ValueError("each turn tool_catalog entry must be an object")
                name = _identifier(item.get("name"), "turn tool name")
                if name in seen_tools:
                    raise ValueError(f"turn tool_catalog contains duplicate tool {name!r}")
                seen_tools.add(name)
                normalized_catalog.append(json.loads(_canonical(item)))
        tool_capable_catalog = bool(normalized_catalog) and all(
            isinstance(item.get("parameters"), Mapping) for item in normalized_catalog
        )
        if host_scope is None:
            normalized_scope: Mapping[str, Any] = {}
        elif isinstance(host_scope, Mapping):
            normalized_scope = json.loads(_canonical(host_scope))
        else:
            raise ValueError("turn host_scope must be an object")
        turn_payload = {
            "turn_id": turn_id,
            "request_id": request_id,
            "conversation_id": conversation_id,
            "project_id": project_id,
            "content": content,
            "kind": kind,
            "source": normalized_source,
            "tool_catalog": normalized_catalog,
            "host_scope": normalized_scope,
            "observed_at": occurred,
        }
        turn_digest = _sha256(turn_payload)
        turn_journal_request_id = (
            f"turn:{hashlib.sha256(request_id.encode('utf-8')).hexdigest()}"
        )
        message_payload = {
            "conversation_id": conversation_id,
            "project_id": project_id,
            "content": content,
            "observed_at": occurred,
            "kind": "message",
        }
        message_digest = _sha256(message_payload)
        with self._lock:
            cached = self.journal.lookup(turn_journal_request_id, turn_digest)
            if cached is not None:
                return {**cached, "idempotent_replay": True}
            prior_turn = self.journal.turn(turn_id)
            if prior_turn is not None and prior_turn.get("request_id") != request_id:
                raise ValueError("turn_id is already bound to another request")
            if tool_capable_catalog:
                try:
                    context = self._context(conversation_id, project_id)
                    message = self._record(
                        source_id=f"entity:message:{request_id}",
                        context=context,
                        observed_at=occurred,
                        kind="message",
                        payload={"content": content, "request_id": request_id},
                    )
                    workspace = self._workspace(context=context, operation_label=f"turn:{request_id}")
                    brain = self._complete(
                        prompt=self._workspace_prompt(
                            workspace,
                            self._typed_instruction(content, normalized_catalog),
                        ),
                        max_tokens=self.config.max_response_tokens,
                        thinking=self.config.brain_thinking,
                        response_format=self._response_schema(
                            frozenset({"action", "response", "tool_name", "tool_arguments"}),
                            max_length=8_192,
                        ),
                    )
                    action = self._typed_action(brain)
                    catalog_names = {
                        item.get("name")
                        for item in normalized_catalog
                        if isinstance(item.get("name"), str)
                    }
                    pending_tool: Mapping[str, Any] | None = None
                    if action["action"] == "call_tool":
                        if action["tool_name"] not in catalog_names:
                            raise BrainUnavailable(
                                f"typed tool action named unavailable tool {action['tool_name']!r}"
                            )
                        pending_tool = {
                            "call_id": self._typed_tool_call_id(
                                turn_id,
                                0,
                                action["tool_name"],
                                action["arguments"],
                            ),
                            "name": action["tool_name"],
                            "arguments": action["arguments"],
                        }
                    brain_record = self._record(
                        source_id=f"entity:brain-response:{request_id}",
                        context=context,
                        observed_at=occurred,
                        kind="brain-response",
                        payload={
                            "content": action["response"],
                            "raw_content": brain["content"],
                            "action": action["action"],
                            **({"tool_call": pending_tool} if pending_tool is not None else {}),
                            "model_id": getattr(self.brain, "model_id", "unidentified"),
                            "model_sha256": getattr(self.brain, "model_sha256", "unidentified"),
                            "message_source_revision_id": message.get("source_revision_id"),
                            "request_id": request_id,
                            "usage": brain.get("usage", {}),
                        },
                    )
                    model = {
                        "id": getattr(self.brain, "model_id", "unidentified"),
                        "sha256": getattr(self.brain, "model_sha256", "unidentified"),
                    }
                    turn = {
                        "schema": TURN_SCHEMA,
                        "turn_id": turn_id,
                        "request_id": request_id,
                        "conversation_id": conversation_id,
                        "project_id": project_id,
                        "kind": kind,
                        "content": content,
                        "source": normalized_source,
                        "tool_catalog": normalized_catalog,
                        "host_scope": normalized_scope,
                        "observed_at": occurred,
                        "status": "awaiting-tool" if pending_tool is not None else "committed",
                        **({"pending_tool": pending_tool} if pending_tool is not None else {}),
                        "tool_results": [],
                        **({"response": action["response"]} if pending_tool is None else {}),
                        "model": model,
                        "usage": dict(brain.get("usage", {})) if isinstance(brain.get("usage"), Mapping) else {},
                        "field_state_sha256": brain_record.get("state_sha256"),
                        "message_source_revision_id": message.get("source_revision_id"),
                        "brain_source_revision_id": brain_record.get("source_revision_id"),
                    }
                    return self.journal.commit(
                        request_id=turn_journal_request_id,
                        payload_sha256=turn_digest,
                        event_specs=(),
                        turn=turn,
                        turn_event_specs=(
                            {
                                "kind": "turn-accepted",
                                "payload": {
                                    "turn_id": turn_id,
                                    "request_id": request_id,
                                    "conversation_id": conversation_id,
                                    "project_id": project_id,
                                    "kind": kind,
                                },
                            },
                            {
                                "kind": "turn-tool-proposed" if pending_tool is not None else "turn-committed",
                                "payload": {
                                    "turn_id": turn_id,
                                    "request_id": request_id,
                                    **(
                                        {
                                            "call_id": pending_tool["call_id"],
                                            "name": pending_tool["name"],
                                            "arguments": pending_tool["arguments"],
                                        }
                                        if pending_tool is not None
                                        else {
                                            "response": action["response"],
                                            "model": model,
                                            "usage": turn["usage"],
                                            "field_state_sha256": turn["field_state_sha256"],
                                        }
                                    ),
                                },
                            },
                        ),
                        result={**turn, "idempotent_replay": False},
                    )
                except BrainUnavailable as exc:
                    turn = {
                        "schema": TURN_SCHEMA,
                        "turn_id": turn_id,
                        "request_id": request_id,
                        "conversation_id": conversation_id,
                        "project_id": project_id,
                        "kind": kind,
                        "content": content,
                        "source": normalized_source,
                        "tool_catalog": normalized_catalog,
                        "host_scope": normalized_scope,
                        "observed_at": occurred,
                        "status": "failed",
                        "error": {"code": "brain-unavailable", "message": str(exc)},
                    }
                    return self.journal.commit(
                        request_id=turn_journal_request_id,
                        payload_sha256=turn_digest,
                        event_specs=(),
                        turn=turn,
                        turn_event_specs=(
                            {
                                "kind": "turn-accepted",
                                "payload": {
                                    "turn_id": turn_id,
                                    "request_id": request_id,
                                    "conversation_id": conversation_id,
                                    "project_id": project_id,
                                    "kind": kind,
                                },
                            },
                            {
                                "kind": "turn-failed",
                                "payload": {
                                    "turn_id": turn_id,
                                    "request_id": request_id,
                                    "error": turn["error"],
                                },
                            },
                        ),
                        result={**turn, "idempotent_replay": False},
                    )
            prior_message = self.journal.lookup(request_id, message_digest)
            try:
                message_result = (
                    prior_message
                    if prior_message is not None
                    else self.receive_message(
                        request_id=request_id,
                        conversation_id=conversation_id,
                        project_id=project_id,
                        content=content,
                        observed_at=occurred,
                    )
                )
            except BrainUnavailable as exc:
                turn = {
                    "schema": TURN_SCHEMA,
                    "turn_id": turn_id,
                    "request_id": request_id,
                    "conversation_id": conversation_id,
                    "project_id": project_id,
                    "kind": kind,
                    "content": content,
                    "source": normalized_source,
                    "tool_catalog": normalized_catalog,
                    "host_scope": normalized_scope,
                    "observed_at": occurred,
                    "status": "failed",
                    "error": {"code": "brain-unavailable", "message": str(exc)},
                }
                return self.journal.commit(
                    request_id=turn_journal_request_id,
                    payload_sha256=turn_digest,
                    event_specs=(),
                    turn=turn,
                    turn_event_specs=(
                        {
                            "kind": "turn-accepted",
                            "payload": {
                                "turn_id": turn_id,
                                "request_id": request_id,
                                "conversation_id": conversation_id,
                                "project_id": project_id,
                                "kind": kind,
                            },
                        },
                        {
                            "kind": "turn-failed",
                            "payload": {
                                "turn_id": turn_id,
                                "request_id": request_id,
                                "error": turn["error"],
                            },
                        },
                    ),
                    result={**turn, "idempotent_replay": False},
                )
            response = message_result.get("response")
            if not isinstance(response, str) or not response.strip():
                raise RuntimeError("typed turn source message has no committed response")
            model = message_result.get("model")
            usage = message_result.get("usage")
            turn = {
                "schema": TURN_SCHEMA,
                "turn_id": turn_id,
                "request_id": request_id,
                "conversation_id": conversation_id,
                "project_id": project_id,
                "kind": kind,
                "content": content,
                "source": normalized_source,
                "tool_catalog": normalized_catalog,
                "host_scope": normalized_scope,
                "observed_at": occurred,
                "status": "committed",
                "response": response,
                "model": dict(model) if isinstance(model, Mapping) else {},
                "usage": dict(usage) if isinstance(usage, Mapping) else {},
                "field_state_sha256": message_result.get("field_state_sha256"),
                "message_source_revision_id": message_result.get("message_source_revision_id"),
                "brain_source_revision_id": message_result.get("brain_source_revision_id"),
            }
            return self.journal.commit(
                request_id=turn_journal_request_id,
                payload_sha256=turn_digest,
                event_specs=(),
                turn=turn,
                turn_event_specs=(
                    {
                        "kind": "turn-accepted",
                        "payload": {
                            "turn_id": turn_id,
                            "request_id": request_id,
                            "conversation_id": conversation_id,
                            "project_id": project_id,
                            "kind": kind,
                        },
                    },
                    {
                        "kind": "turn-committed",
                        "payload": {
                            "turn_id": turn_id,
                            "request_id": request_id,
                            "response": response,
                            "model": turn["model"],
                            "usage": turn["usage"],
                            "field_state_sha256": turn["field_state_sha256"],
                        },
                    },
                ),
                result={**turn, "idempotent_replay": False},
            )

    def inspect_turn(self, turn_id: str) -> Mapping[str, Any]:
        turn = self.journal.turn(turn_id)
        if turn is None:
            raise TurnNotFound(f"unknown typed turn {turn_id}")
        return {
            "schema": TURN_SCHEMA,
            "turn": turn,
            "latest_cursor": self.journal.turn_latest_cursor(turn_id),
        }

    def turn_events(
        self,
        turn_id: str,
        *,
        after: int = 0,
        wait_seconds: float = 0.0,
    ) -> list[Mapping[str, Any]]:
        if wait_seconds < 0 or not math.isfinite(wait_seconds):
            raise ValueError("turn event wait must be finite and nonnegative")
        deadline = time.monotonic() + min(wait_seconds, 60.0)
        while True:
            events = self.journal.turn_events_after(turn_id, after)
            if events or wait_seconds == 0 or time.monotonic() >= deadline:
                return events
            time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))

    def cancel_turn(
        self,
        *,
        turn_id: str,
        request_id: str,
        observed_at: str | None = None,
    ) -> Mapping[str, Any]:
        turn_id = _identifier(turn_id, "turn_id")
        request_id = _identifier(request_id, "request_id")
        occurred = _timestamp(observed_at)
        payload = {"turn_id": turn_id, "request_id": request_id, "observed_at": occurred}
        digest = _sha256(payload)
        journal_request_id = f"turn-cancel:{hashlib.sha256(request_id.encode('utf-8')).hexdigest()}"
        with self._lock:
            cached = self.journal.lookup(journal_request_id, digest)
            if cached is not None:
                return {**cached, "idempotent_replay": True}
            turn = self.journal.turn(turn_id)
            if turn is None:
                raise TurnNotFound(f"unknown typed turn {turn_id}")
            if turn.get("status") not in {"committed", "failed", "cancelled"}:
                raise TurnConflict("typed turn cancellation requires an explicit in-flight disposition")
            result = {
                "schema": "cassi.field-brain.turn-cancel.v1",
                "turn_id": turn_id,
                "request_id": request_id,
                "turn_status": turn.get("status"),
                "status": "already-terminal",
                "observed_at": occurred,
                "idempotent_replay": False,
            }
            return self.journal.commit(
                request_id=journal_request_id,
                payload_sha256=digest,
                event_specs=(),
                turn_id=turn_id,
                turn_event_specs=(
                    {
                        "kind": "turn-cancel-reconciled",
                        "payload": {
                            "turn_id": turn_id,
                            "request_id": request_id,
                            "turn_status": turn.get("status"),
                            "status": "already-terminal",
                        },
                    },
                ),
                result=result,
            )

    def submit_turn_tool_results(
        self,
        *,
        turn_id: str,
        request_id: str,
        results: Sequence[Mapping[str, Any]],
        observed_at: str | None = None,
    ) -> Mapping[str, Any]:
        turn_id = _identifier(turn_id, "turn_id")
        request_id = _identifier(request_id, "request_id")
        if not isinstance(results, Sequence) or isinstance(results, (str, bytes)):
            raise ValueError("turn tool results must be an array")
        if any(not isinstance(item, Mapping) for item in results):
            raise ValueError("each turn tool result must be an object")
        if len(results) != 1:
            existing = self.journal.turn(turn_id)
            if existing is None:
                raise TurnNotFound(f"unknown typed turn {turn_id}")
            if existing.get("status") != "awaiting-tool":
                raise TurnConflict("typed turn has no pending Harness-owned tool operation")
            raise ValueError("typed turn continuation currently accepts exactly one tool result")
        occurred = _timestamp(observed_at)
        normalized_results = [self._normalize_tool_result(item) for item in results]
        digest = _sha256({"turn_id": turn_id, "results": normalized_results})
        journal_request_id = f"turn-tool-results:{hashlib.sha256(request_id.encode('utf-8')).hexdigest()}"
        with self._lock:
            cached = self.journal.lookup(journal_request_id, digest)
            if cached is not None:
                return {**cached, "idempotent_replay": True}
            turn = self.journal.turn(turn_id)
            if turn is None:
                raise TurnNotFound(f"unknown typed turn {turn_id}")
            if turn.get("status") != "awaiting-tool":
                raise TurnConflict("typed turn has no pending Harness-owned tool operation")
            pending = turn.get("pending_tool")
            if not isinstance(pending, Mapping):
                raise TurnConflict("typed turn is awaiting a tool but has no durable pending call")
            tool_result = normalized_results[0]
            if tool_result["call_id"] != pending.get("call_id"):
                raise TurnConflict("tool result call_id does not match the pending typed call")
            if tool_result["name"] != pending.get("name"):
                raise TurnConflict("tool result name does not match the pending typed call")
            if _canonical(tool_result["arguments"]) != _canonical(pending.get("arguments")):
                raise TurnConflict("tool result arguments do not match the pending typed call")
            context = self._context(str(turn["conversation_id"]), str(turn["project_id"]))
            tool_record = self._record(
                source_id=f"entity:tool-result:{request_id}",
                context=context,
                observed_at=occurred,
                kind="tool-result",
                payload={
                    "turn_id": turn_id,
                    "request_id": request_id,
                    "result": tool_result,
                },
            )
            prior_results = turn.get("tool_results", [])
            if not isinstance(prior_results, list):
                raise RuntimeError("typed turn tool_results is invalid")
            tool_results = [*prior_results, tool_result]
            catalog = turn.get("tool_catalog", [])
            if not isinstance(catalog, list):
                raise RuntimeError("typed turn tool_catalog is invalid")
            try:
                workspace = self._workspace(
                    context=context,
                    operation_label=f"tool-result:{request_id}",
                    exclude_source_ids=(f"entity:tool-result:{request_id}",),
                )
                brain = self._complete(
                    prompt=self._workspace_prompt(
                        workspace,
                        self._typed_instruction(
                            str(turn["content"]),
                            catalog,
                            tool_result=tool_result,
                        ),
                    ),
                    max_tokens=self.config.max_response_tokens,
                    thinking=self.config.brain_thinking,
                    response_format=self._response_schema(
                        frozenset({"action", "response", "tool_name", "tool_arguments"}),
                        max_length=8_192,
                    ),
                )
                action = self._typed_action(brain)
                catalog_names = {
                    item.get("name")
                    for item in catalog
                    if isinstance(item, Mapping) and isinstance(item.get("name"), str)
                }
                next_tool: Mapping[str, Any] | None = None
                if action["action"] == "call_tool":
                    if action["tool_name"] not in catalog_names:
                        raise BrainUnavailable(
                            f"typed tool action named unavailable tool {action['tool_name']!r}"
                        )
                    next_tool = {
                        "call_id": self._typed_tool_call_id(
                            turn_id,
                            len(tool_results),
                            action["tool_name"],
                            action["arguments"],
                        ),
                        "name": action["tool_name"],
                        "arguments": action["arguments"],
                    }
                brain_record = self._record(
                    source_id=f"entity:brain-response:tool:{request_id}",
                    context=context,
                    observed_at=occurred,
                    kind="brain-response",
                    payload={
                        "content": action["response"],
                        "raw_content": brain["content"],
                        "action": action["action"],
                        **({"tool_call": next_tool} if next_tool is not None else {}),
                        "model_id": getattr(self.brain, "model_id", "unidentified"),
                        "model_sha256": getattr(self.brain, "model_sha256", "unidentified"),
                        "tool_result_source_revision_id": tool_record.get("source_revision_id"),
                        "request_id": request_id,
                        "usage": brain.get("usage", {}),
                    },
                )
                updated_turn = dict(turn)
                updated_turn["status"] = "awaiting-tool" if next_tool is not None else "committed"
                updated_turn["tool_results"] = tool_results
                updated_turn.pop("pending_tool", None)
                if next_tool is not None:
                    updated_turn["pending_tool"] = next_tool
                    updated_turn.pop("response", None)
                else:
                    updated_turn["response"] = action["response"]
                updated_turn["model"] = {
                    "id": getattr(self.brain, "model_id", "unidentified"),
                    "sha256": getattr(self.brain, "model_sha256", "unidentified"),
                }
                updated_turn["usage"] = (
                    dict(brain.get("usage", {}))
                    if isinstance(brain.get("usage"), Mapping)
                    else {}
                )
                updated_turn["field_state_sha256"] = brain_record.get("state_sha256")
                updated_turn["brain_source_revision_id"] = brain_record.get("source_revision_id")
                updated_turn["last_tool_result_request_id"] = request_id
                result = {
                    **updated_turn,
                    "idempotent_replay": False,
                    "tool_result_request_id": request_id,
                    "observed_at": occurred,
                }
                return self.journal.commit(
                    request_id=journal_request_id,
                    payload_sha256=digest,
                    event_specs=(),
                    turn=updated_turn,
                    turn_id=turn_id,
                    allow_turn_update=True,
                    turn_event_specs=(
                        {
                            "kind": "turn-tool-result-admitted",
                            "payload": {
                                "turn_id": turn_id,
                                "request_id": request_id,
                                "call_id": tool_result["call_id"],
                                "name": tool_result["name"],
                                "is_error": tool_result["is_error"],
                                "source_revision_id": tool_record.get("source_revision_id"),
                            },
                        },
                        {
                            "kind": "turn-tool-proposed" if next_tool is not None else "turn-committed",
                            "payload": {
                                "turn_id": turn_id,
                                "request_id": request_id,
                                **(
                                    {
                                        "call_id": next_tool["call_id"],
                                        "name": next_tool["name"],
                                        "arguments": next_tool["arguments"],
                                    }
                                    if next_tool is not None
                                    else {
                                        "response": action["response"],
                                        "model": updated_turn["model"],
                                        "usage": updated_turn["usage"],
                                        "field_state_sha256": updated_turn["field_state_sha256"],
                                    }
                                ),
                            },
                        },
                    ),
                    result=result,
                )
            except BrainUnavailable as exc:
                updated_turn = dict(turn)
                updated_turn["status"] = "failed"
                updated_turn["tool_results"] = tool_results
                updated_turn.pop("pending_tool", None)
                updated_turn["last_tool_result_request_id"] = request_id
                updated_turn["error"] = {"code": "brain-unavailable", "message": str(exc)}
                result = {
                    **updated_turn,
                    "idempotent_replay": False,
                    "tool_result_request_id": request_id,
                    "observed_at": occurred,
                }
                return self.journal.commit(
                    request_id=journal_request_id,
                    payload_sha256=digest,
                    event_specs=(),
                    turn=updated_turn,
                    turn_id=turn_id,
                    allow_turn_update=True,
                    turn_event_specs=(
                        {
                            "kind": "turn-tool-result-admitted",
                            "payload": {
                                "turn_id": turn_id,
                                "request_id": request_id,
                                "call_id": tool_result["call_id"],
                                "name": tool_result["name"],
                                "is_error": tool_result["is_error"],
                                "source_revision_id": tool_record.get("source_revision_id"),
                            },
                        },
                        {
                            "kind": "turn-failed",
                            "payload": {
                                "turn_id": turn_id,
                                "request_id": request_id,
                                "error": updated_turn["error"],
                            },
                        },
                    ),
                    result=result,
                )

    def think(
        self,
        *,
        request_id: str,
        conversation_id: str,
        project_id: str,
        observed_at: str | None = None,
    ) -> Mapping[str, Any]:
        """Run a bounded self-questioning cycle against the current field workspace."""
        request_id = _identifier(request_id, "request_id")
        conversation_id = _identifier(conversation_id, "conversation_id")
        project_id = _identifier(project_id, "project_id")
        occurred = _timestamp(observed_at)
        payload = {
            "conversation_id": conversation_id,
            "project_id": project_id,
            "observed_at": occurred,
            "kind": "self-question",
        }
        digest = _sha256(payload)
        with self._lock:
            cached = self.journal.lookup(request_id, digest)
            if cached is not None:
                return {**cached, "idempotent_replay": True}
            context = self._context(conversation_id, project_id)
            workspace = self._workspace(context=context, operation_label=f"think:{request_id}")
            if not workspace["records"]:
                raise ValueError("self-questioning requires an admitted experience in this scope")
            brain = self._complete(
                prompt=self._workspace_prompt(
                    workspace,
                    "Return ONLY a JSON object with exactly two keys, `question` and `reason`. "
                    "The question must identify one specific uncertainty worth reducing, and "
                    "the reason must say why it matters. Do not claim to answer or act on it.",
                ),
                max_tokens=self.config.max_question_tokens,
                thinking=self.config.brain_thinking,
                response_format=self._response_schema(frozenset({"question", "reason"})),
            )
            contribution = self._brain_json(brain, fields=frozenset({"question", "reason"}))
            question = self._record(
                source_id=f"entity:self-question:{request_id}",
                context=context,
                observed_at=occurred,
                kind="self-question",
                payload={
                    "question": contribution["question"],
                    "reason": contribution["reason"],
                    "raw_content": brain["content"],
                    "model_id": getattr(self.brain, "model_id", "unidentified"),
                    "request_id": request_id,
                },
            )
            result = {
                "schema": ENTITY_SCHEMA,
                "entity_id": self.config.entity_id,
                "request_id": request_id,
                "conversation_id": conversation_id,
                "project_id": project_id,
                "question": contribution["question"],
                "reason": contribution["reason"],
                "field_state_sha256": question.get("state_sha256"),
                "question_source_revision_id": question.get("source_revision_id"),
                "idempotent_replay": False,
            }
            return self.journal.commit(
                request_id=request_id,
                payload_sha256=digest,
                event_specs=(
                    {
                        "kind": "self-question",
                        "payload": {
                            "request_id": request_id,
                            "source_revision_id": question.get("source_revision_id"),
                        },
                    },
                ),
                result=result,
            )

    def create_commitment(
        self,
        *,
        request_id: str,
        commitment_id: str,
        conversation_id: str,
        project_id: str,
        title: str,
        purpose: str,
        observed_at: str | None = None,
    ) -> Mapping[str, Any]:
        """Retain one durable intention through the field-owned lifetime."""
        request_id = _identifier(request_id, "request_id")
        commitment_id = _identifier(commitment_id, "commitment_id")
        conversation_id = _identifier(conversation_id, "conversation_id")
        project_id = _identifier(project_id, "project_id")
        title = _content(title, "commitment title")
        purpose = _content(purpose, "commitment purpose")
        occurred = _timestamp(observed_at)
        payload = {
            "commitment_id": commitment_id,
            "conversation_id": conversation_id,
            "project_id": project_id,
            "title": title,
            "purpose": purpose,
            "observed_at": occurred,
            "kind": "commitment",
        }
        digest = _sha256(payload)
        with self._lock:
            cached = self.journal.lookup(request_id, digest)
            if cached is not None:
                return {**cached, "idempotent_replay": True}
            commitment = self._record(
                source_id=f"entity:commitment:{commitment_id}",
                context=self._context(conversation_id, project_id),
                observed_at=occurred,
                kind="commitment",
                payload={
                    "commitment_id": commitment_id,
                    "title": title,
                    "purpose": purpose,
                    "request_id": request_id,
                    "status": "active",
                },
            )
            result = {
                "schema": ENTITY_SCHEMA,
                "entity_id": self.config.entity_id,
                "request_id": request_id,
                "commitment_id": commitment_id,
                "status": "active",
                "commitment_source_revision_id": commitment.get("source_revision_id"),
                "field_state_sha256": commitment.get("state_sha256"),
                "idempotent_replay": False,
            }
            return self.journal.commit(
                request_id=request_id,
                payload_sha256=digest,
                event_specs=(
                    {
                        "kind": "commitment-created",
                        "payload": {
                            "request_id": request_id,
                            "commitment_id": commitment_id,
                            "source_revision_id": commitment.get("source_revision_id"),
                        },
                    },
                ),
                result=result,
            )

    def advance_commitment(
        self,
        *,
        request_id: str,
        commitment_id: str,
        conversation_id: str,
        project_id: str,
        observed_at: str | None = None,
    ) -> Mapping[str, Any]:
        """Execute the commitment's declared, bounded read-only field observation."""
        request_id = _identifier(request_id, "request_id")
        commitment_id = _identifier(commitment_id, "commitment_id")
        conversation_id = _identifier(conversation_id, "conversation_id")
        project_id = _identifier(project_id, "project_id")
        occurred = _timestamp(observed_at)
        payload = {
            "commitment_id": commitment_id,
            "conversation_id": conversation_id,
            "project_id": project_id,
            "observed_at": occurred,
            "kind": "commitment-cycle",
        }
        digest = _sha256(payload)
        with self._lock:
            cached = self.journal.lookup(request_id, digest)
            if cached is not None:
                return {**cached, "idempotent_replay": True}
            context = self._context(conversation_id, project_id)
            workspace = self._workspace(context=context, operation_label=f"commitment-cycle:{request_id}")
            if not any(
                row.get("source_id") == f"entity:commitment:{commitment_id}"
                for row in workspace["records"]
                if isinstance(row, Mapping)
            ):
                raise ValueError("commitment is not available in this field workspace")
            plan = {
                "next_step": "Observe the current field state for this commitment.",
                "reason": "The capability is predeclared, read-only, and leaves a real outcome in the shared field lifetime.",
            }
            plan_record = self._record(
                source_id=f"entity:commitment-plan:{request_id}",
                context=context,
                observed_at=occurred,
                kind="commitment-plan",
                payload={
                    "commitment_id": commitment_id,
                    "next_step": plan["next_step"],
                    "reason": plan["reason"],
                    "capability": "field-state-observation",
                    "request_id": request_id,
                },
            )
            state = self.memory.state_receipt()
            outcome = self._record(
                source_id=f"entity:world-observation:{request_id}",
                context=context,
                observed_at=occurred,
                kind="world-observation",
                payload={
                    "commitment_id": commitment_id,
                    "capability": "field-state-observation",
                    "outcome": {
                        "field_generation": state.get("generation"),
                        "field_state_sha256": state.get("state_sha256"),
                    },
                    "plan_source_revision_id": plan_record.get("source_revision_id"),
                    "request_id": request_id,
                },
            )
            result = {
                "schema": ENTITY_SCHEMA,
                "entity_id": self.config.entity_id,
                "request_id": request_id,
                "commitment_id": commitment_id,
                "next_step": plan["next_step"],
                "reason": plan["reason"],
                "capability": "field-state-observation",
                "outcome_source_revision_id": outcome.get("source_revision_id"),
                "field_state_sha256": outcome.get("state_sha256"),
                "idempotent_replay": False,
            }
            return self.journal.commit(
                request_id=request_id,
                payload_sha256=digest,
                event_specs=(
                    {
                        "kind": "commitment-cycle-planned",
                        "payload": {
                            "request_id": request_id,
                            "commitment_id": commitment_id,
                            "source_revision_id": plan_record.get("source_revision_id"),
                        },
                    },
                    {
                        "kind": "world-observation",
                        "payload": {
                            "request_id": request_id,
                            "commitment_id": commitment_id,
                            "capability": "field-state-observation",
                            "source_revision_id": outcome.get("source_revision_id"),
                        },
                    },
                ),
                result=result,
            )

    def inspect(self) -> Mapping[str, Any]:
        """Read the entity without creating a learning or model event."""
        with self._lock:
            receipt = self.memory.state_receipt()
            return {
                "schema": ENTITY_SCHEMA,
                "entity_id": self.config.entity_id,
                "profile": ENTITY_PROFILE,
                "field_state_sha256": receipt.get("state_sha256"),
                "field_generation": receipt.get("generation"),
                "latest_event_cursor": self.journal.latest_cursor,
                "brain": {
                    "id": getattr(self.brain, "model_id", "unidentified"),
                    "sha256": getattr(self.brain, "model_sha256", "unidentified"),
                },
                "generation_policy": {
                    "enable_thinking": self.config.brain_thinking,
                    "max_response_tokens": self.config.max_response_tokens,
                    "max_question_tokens": self.config.max_question_tokens,
                },
                "native_continuation": "semantic-reconstruction-only",
                "research": self.researcher.status(),
                "capabilities": {
                    "messages": True,
                    "self_questioning": True,
                    "commitments": True,
                    "resident_autonomous_research": True,
                    "research_program_api": True,
                    "research_artifact_store": True,
                    "research_capabilities": list(self.researcher.capability_map()["tools"]),
                    "world_observation": "field-state-observation",
                    "approved_external_capability": _FILE_SHA256_CAPABILITY,
                    "theory_document_catalog": True,
                    "theory_read_access": "full-markdown-corpus",
                    "exact_native_resume": False,
                    "native_coupling": False,
                    "external_actions": "program-scoped",
                },
            }

    def create_research_program(self, **arguments: Any) -> Mapping[str, Any]:
        return self.researcher.create_program(**arguments)

    def research_programs(self) -> list[Mapping[str, Any]]:
        return self.researcher.programs()

    def research_program(self, program_id: str) -> Mapping[str, Any]:
        return self.researcher.program(program_id)

    def control_research_program(self, **arguments: Any) -> Mapping[str, Any]:
        return self.researcher.control_program(**arguments)

    def guide_research_program(self, **arguments: Any) -> Mapping[str, Any]:
        return self.researcher.guide_program(**arguments)
    def propose_capability(
        self,
        *,
        request_id: str,
        proposal_id: str,
        commitment_id: str,
        conversation_id: str,
        project_id: str,
        capability: str,
        target_path: str,
        start_byte: int | None = None,
        max_bytes: int | None = None,
        observed_at: str | None = None,
    ) -> Mapping[str, Any]:
        """Bind one immutable, bounded observation to an active commitment."""
        request_id = _identifier(request_id, "request_id")
        proposal_id = _identifier(proposal_id, "proposal_id")
        commitment_id = _identifier(commitment_id, "commitment_id")
        conversation_id = _identifier(conversation_id, "conversation_id")
        project_id = _identifier(project_id, "project_id")
        if capability == _FILE_SHA256_CAPABILITY:
            if start_byte is not None or max_bytes is not None:
                raise ValueError("file-sha256 does not accept a byte range")
            relative_target, resolved_target = _relative_target(target_path, root=self.config.capability_root)
            definition_extra: Mapping[str, Any] = {}
        elif capability == _THEORY_EXCERPT_CAPABILITY:
            relative_target, resolved_target = _theory_target(target_path, root=self.config.theory_root)
            source_stat = resolved_target.stat()
            start = _bounded_int(start_byte, "start_byte", minimum=0, maximum=source_stat.st_size)
            limit = _bounded_int(max_bytes, "max_bytes", minimum=1, maximum=_MAX_THEORY_EXCERPT_BYTES)
            end = min(start + limit, source_stat.st_size)
            definition_extra = {
                "byte_start": start,
                "byte_end": end,
                "source_size_bytes": source_stat.st_size,
                "source_mtime_ns": source_stat.st_mtime_ns,
            }
        else:
            raise ValueError(f"unsupported capability: {capability}")
        occurred = _timestamp(observed_at)
        payload = {
            "proposal_id": proposal_id,
            "commitment_id": commitment_id,
            "conversation_id": conversation_id,
            "project_id": project_id,
            "capability": capability,
            "target_path": relative_target,
            "definition_extra": definition_extra,
            "observed_at": occurred,
            "kind": "capability-proposal",
        }
        digest = _sha256(payload)
        with self._lock:
            cached = self.journal.lookup(request_id, digest)
            if cached is not None:
                return {**cached, "idempotent_replay": True}
            context = self._context(conversation_id, project_id)
            workspace = self._workspace(context=context, operation_label=f"proposal:{request_id}")
            if not any(
                row.get("source_id") == f"entity:commitment:{commitment_id}"
                for row in workspace["records"]
                if isinstance(row, Mapping)
            ):
                raise ValueError("commitment is not available in this field workspace")
            definition = {
                "proposal_id": proposal_id,
                "commitment_id": commitment_id,
                "conversation_id": conversation_id,
                "project_id": project_id,
                "capability": capability,
                "target_path": relative_target,
                "target_size_bytes": resolved_target.stat().st_size,
                **definition_extra,
            }
            proposal = self._record(
                source_id=f"entity:capability-proposal:{proposal_id}",
                context=context,
                observed_at=occurred,
                kind="capability-proposal",
                payload={**definition, "request_id": request_id, "status": "pending-approval"},
            )
            result = {
                "schema": ENTITY_SCHEMA,
                "entity_id": self.config.entity_id,
                "request_id": request_id,
                "proposal_definition": definition,
                "status": "pending-approval",
                "proposal_source_revision_id": proposal.get("source_revision_id"),
                "field_state_sha256": proposal.get("state_sha256"),
                "idempotent_replay": False,
            }
            return self.journal.commit(
                request_id=request_id,
                payload_sha256=digest,
                event_specs=(
                    {
                        "kind": "capability-proposed",
                        "payload": {
                            "request_id": request_id,
                            "proposal_id": proposal_id,
                            "capability": capability,
                            "target_path": relative_target,
                            "source_revision_id": proposal.get("source_revision_id"),
                        },
                    },
                ),
                result=result,
            )

    def approve_capability(
        self,
        *,
        request_id: str,
        proposal_id: str,
        approved_by: str,
        observed_at: str | None = None,
    ) -> Mapping[str, Any]:
        """Record an explicit approval for the exact durable proposal."""
        request_id = _identifier(request_id, "request_id")
        proposal_id = _identifier(proposal_id, "proposal_id")
        approved_by = _identifier(approved_by, "approved_by")
        occurred = _timestamp(observed_at)
        payload = {
            "proposal_id": proposal_id,
            "approved_by": approved_by,
            "observed_at": occurred,
            "kind": "capability-approval",
        }
        digest = _sha256(payload)
        with self._lock:
            cached = self.journal.lookup(request_id, digest)
            if cached is not None:
                return {**cached, "idempotent_replay": True}
            proposal = self.journal.proposal(proposal_id)
            if self.journal.approval(proposal_id) is not None:
                raise ValueError("capability proposal was already approved")
            context = self._context(proposal["conversation_id"], proposal["project_id"])
            approval = {
                "proposal_id": proposal_id,
                "approved_by": approved_by,
                "approved_at": occurred,
                "capability": proposal["capability"],
                "target_path": proposal["target_path"],
            }
            approval_record = self._record(
                source_id=f"entity:capability-approval:{proposal_id}",
                context=context,
                observed_at=occurred,
                kind="capability-approval",
                payload={**approval, "request_id": request_id},
            )
            result = {
                "schema": ENTITY_SCHEMA,
                "entity_id": self.config.entity_id,
                "request_id": request_id,
                "approval": approval,
                "approval_source_revision_id": approval_record.get("source_revision_id"),
                "field_state_sha256": approval_record.get("state_sha256"),
                "idempotent_replay": False,
            }
            return self.journal.commit(
                request_id=request_id,
                payload_sha256=digest,
                event_specs=(
                    {
                        "kind": "capability-approved",
                        "payload": {
                            "request_id": request_id,
                            "proposal_id": proposal_id,
                            "approved_by": approved_by,
                            "source_revision_id": approval_record.get("source_revision_id"),
                        },
                    },
                ),
                result=result,
            )

    def execute_capability(
        self,
        *,
        request_id: str,
        proposal_id: str,
        observed_at: str | None = None,
    ) -> Mapping[str, Any]:
        """Execute only the exactly approved, non-mutating capability proposal."""
        request_id = _identifier(request_id, "request_id")
        proposal_id = _identifier(proposal_id, "proposal_id")
        occurred = _timestamp(observed_at)
        payload = {"proposal_id": proposal_id, "observed_at": occurred, "kind": "capability-execution"}
        digest = _sha256(payload)
        with self._lock:
            cached = self.journal.lookup(request_id, digest)
            if cached is not None:
                return {**cached, "idempotent_replay": True}
            proposal = self.journal.proposal(proposal_id)
            approval = self.journal.approval(proposal_id)
            if approval is None:
                raise CapabilityApprovalRequired("capability execution requires explicit proposal approval")
            if proposal["capability"] == _FILE_SHA256_CAPABILITY:
                target_path, target = _relative_target(proposal["target_path"], root=self.config.capability_root)
                outcome_value = {
                    "target_path": target_path,
                    "byte_length": target.stat().st_size,
                    "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                }
            elif proposal["capability"] == _THEORY_EXCERPT_CAPABILITY:
                target_path, target = _theory_target(proposal["target_path"], root=self.config.theory_root)
                source_stat = target.stat()
                if (
                    source_stat.st_size != proposal.get("source_size_bytes")
                    or source_stat.st_mtime_ns != proposal.get("source_mtime_ns")
                ):
                    raise ValueError("theory source changed after proposal; create a new proposal")
                source = target.read_bytes()
                start = _bounded_int(proposal.get("byte_start"), "byte_start", minimum=0, maximum=len(source))
                end = _bounded_int(proposal.get("byte_end"), "byte_end", minimum=start, maximum=len(source))
                try:
                    excerpt = source[start:end].decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise ValueError("theory excerpt boundaries do not align to UTF-8 text") from exc
                outcome_value = {
                    "target_path": target_path,
                    "source_sha256": hashlib.sha256(source).hexdigest(),
                    "byte_start": start,
                    "byte_end": end,
                    "content_sha256": hashlib.sha256(source[start:end]).hexdigest(),
                    "content": excerpt,
                }
            else:
                raise RuntimeError("proposal uses an unsupported executable capability")
            context = self._context(proposal["conversation_id"], proposal["project_id"])
            outcome = self._record(
                source_id=f"entity:capability-outcome:{proposal_id}",
                context=context,
                observed_at=occurred,
                kind="capability-outcome",
                payload={
                    "proposal_id": proposal_id,
                    "capability": proposal["capability"],
                    "approval_source": approval,
                    "outcome": outcome_value,
                    "request_id": request_id,
                },
            )
            result = {
                "schema": ENTITY_SCHEMA,
                "entity_id": self.config.entity_id,
                "request_id": request_id,
                "proposal_id": proposal_id,
                "capability": proposal["capability"],
                "outcome": outcome_value,
                "outcome_source_revision_id": outcome.get("source_revision_id"),
                "field_state_sha256": outcome.get("state_sha256"),
                "idempotent_replay": False,
            }
            return self.journal.commit(
                request_id=request_id,
                payload_sha256=digest,
                event_specs=(
                    {
                        "kind": "capability-executed",
                        "payload": {
                            "request_id": request_id,
                            "proposal_id": proposal_id,
                            "capability": proposal["capability"],
                            "target_path": target_path,
                            "source_revision_id": outcome.get("source_revision_id"),
                        },
                    },
                ),
                result=result,
            )

    def assign_theory_task(
        self,
        *,
        request_id: str,
        task_id: str,
        conversation_id: str,
        project_id: str,
        task: str,
        observed_at: str | None = None,
    ) -> Mapping[str, Any]:
        """Give Cassi a durable, open-ended responsibility over the full theory library."""
        request_id = _identifier(request_id, "request_id")
        task_id = _identifier(task_id, "task_id")
        conversation_id = _identifier(conversation_id, "conversation_id")
        project_id = _identifier(project_id, "project_id")
        task = _content(task, "theory task")
        occurred = _timestamp(observed_at)
        payload = {
            "task_id": task_id,
            "conversation_id": conversation_id,
            "project_id": project_id,
            "task": task,
            "observed_at": occurred,
            "kind": "theory-task",
        }
        digest = _sha256(payload)
        with self._lock:
            cached = self.journal.lookup(request_id, digest)
            if cached is not None:
                return {**cached, "idempotent_replay": True}
            assignment = self._record(
                source_id=f"entity:theory-task:{task_id}",
                context=self._context(conversation_id, project_id),
                observed_at=occurred,
                kind="theory-task",
                payload={"task_id": task_id, "task": task, "status": "active", "request_id": request_id},
            )
            result = {
                "schema": ENTITY_SCHEMA,
                "entity_id": self.config.entity_id,
                "request_id": request_id,
                "task_id": task_id,
                "task": task,
                "status": "active",
                "task_source_revision_id": assignment.get("source_revision_id"),
                "field_state_sha256": assignment.get("state_sha256"),
                "idempotent_replay": False,
            }
            return self.journal.commit(
                request_id=request_id,
                payload_sha256=digest,
                event_specs=(
                    {
                        "kind": "theory-task-assigned",
                        "payload": {
                            "request_id": request_id,
                            "task_id": task_id,
                            "source_revision_id": assignment.get("source_revision_id"),
                        },
                    },
                ),
                result=result,
            )

    def read_theory_document(
        self,
        *,
        request_id: str,
        task_id: str,
        conversation_id: str,
        project_id: str,
        target_path: str,
        observed_at: str | None = None,
    ) -> Mapping[str, Any]:
        """Read an entire UTF-8 theory document into attributable field segments."""
        request_id = _identifier(request_id, "request_id")
        task_id = _identifier(task_id, "task_id")
        conversation_id = _identifier(conversation_id, "conversation_id")
        project_id = _identifier(project_id, "project_id")
        relative_target, target = _theory_target(target_path, root=self.config.theory_root)
        source = target.read_bytes()
        segments = _utf8_segments(source)
        occurred = _timestamp(observed_at)
        payload = {
            "task_id": task_id,
            "conversation_id": conversation_id,
            "project_id": project_id,
            "target_path": relative_target,
            "source_sha256": hashlib.sha256(source).hexdigest(),
            "observed_at": occurred,
            "kind": "theory-document-read",
        }
        digest = _sha256(payload)
        with self._lock:
            cached = self.journal.lookup(request_id, digest)
            if cached is not None:
                return {**cached, "idempotent_replay": True}
            context = self._context(conversation_id, project_id)
            records = [
                self._record(
                    source_id=f"entity:theory-document:{task_id}:{relative_target}:{start:012d}",
                    context=context,
                    observed_at=occurred,
                    kind="theory-document",
                    payload={
                        "task_id": task_id,
                        "source_path": relative_target,
                        "source_sha256": payload["source_sha256"],
                        "byte_start": start,
                        "byte_end": end,
                        "content_sha256": hashlib.sha256(source[start:end]).hexdigest(),
                        "content": text,
                        "request_id": request_id,
                    },
                )
                for start, end, text in segments
            ]
            result = {
                "schema": ENTITY_SCHEMA,
                "entity_id": self.config.entity_id,
                "request_id": request_id,
                "task_id": task_id,
                "source_path": relative_target,
                "source_sha256": payload["source_sha256"],
                "byte_length": len(source),
                "segment_count": len(records),
                "last_segment_source_revision_id": records[-1].get("source_revision_id"),
                "field_state_sha256": records[-1].get("state_sha256"),
                "idempotent_replay": False,
            }
            return self.journal.commit(
                request_id=request_id,
                payload_sha256=digest,
                event_specs=(
                    {
                        "kind": "theory-document-read",
                        "payload": {
                            "request_id": request_id,
                            "task_id": task_id,
                            "source_path": relative_target,
                            "source_sha256": payload["source_sha256"],
                            "segment_count": len(records),
                            "source_revision_id": records[-1].get("source_revision_id"),
                        },
                    },
                ),
                result=result,
            )

    def study_theory_document(
        self,
        *,
        request_id: str,
        task_id: str,
        conversation_id: str,
        project_id: str,
        target_path: str,
        observed_at: str | None = None,
    ) -> Mapping[str, Any]:
        """Read every segment of one theory document and synthesize a task-facing study."""
        request_id = _identifier(request_id, "request_id")
        task_id = _identifier(task_id, "task_id")
        conversation_id = _identifier(conversation_id, "conversation_id")
        project_id = _identifier(project_id, "project_id")
        relative_target, target = _theory_target(target_path, root=self.config.theory_root)
        source = target.read_bytes()
        segments = _utf8_segments(source, maximum_bytes=_MAX_THEORY_STUDY_SEGMENT_BYTES)
        occurred = _timestamp(observed_at)
        source_sha256 = hashlib.sha256(source).hexdigest()
        payload = {
            "task_id": task_id,
            "conversation_id": conversation_id,
            "project_id": project_id,
            "target_path": relative_target,
            "source_sha256": source_sha256,
            "observed_at": occurred,
            "kind": "theory-document-study",
        }
        digest = _sha256(payload)
        with self._lock:
            cached = self.journal.lookup(request_id, digest)
            if cached is not None:
                return {**cached, "idempotent_replay": True}
            context = self._context(conversation_id, project_id)
            segment_summaries: list[Mapping[str, Any]] = []
            for index, (start, end, text) in enumerate(segments):
                brain = self._complete(
                    prompt=(
                        "You are Cassi's pretrained brain reading one attributed segment of a theory document. "
                        "Return ONLY a JSON object with exactly two keys, `summary` and `open_question`. "
                        "Each value must contain at most sixteen words. State what this segment says, then "
                        "identify one question it leaves active. Do not claim an experiment or external "
                        "action occurred.\n\n"
                        f"SOURCE SEGMENT: {json.dumps({'path': relative_target, 'byte_start': start, 'byte_end': end, 'content': text}, ensure_ascii=False)}"
                    ),
                    max_tokens=self.config.max_response_tokens,
                    thinking=self.config.brain_thinking,
                    response_format=self._response_schema(
                        frozenset({"summary", "open_question"}), max_length=128
                    ),
                )
                contribution = self._brain_json(brain, fields=frozenset({"summary", "open_question"}))
                record = self._record(
                    source_id=f"entity:theory-segment-study:{request_id}:{index:04d}",
                    context=context,
                    observed_at=occurred,
                    kind="theory-segment-study",
                    payload={
                        "task_id": task_id,
                        "source_path": relative_target,
                        "source_sha256": source_sha256,
                        "byte_start": start,
                        "byte_end": end,
                        "content_sha256": hashlib.sha256(source[start:end]).hexdigest(),
                        "summary": contribution["summary"],
                        "open_question": contribution["open_question"],
                        "raw_content": brain["content"],
                        "model_id": getattr(self.brain, "model_id", "unidentified"),
                        "request_id": request_id,
                    },
                )
                segment_summaries.append(
                    {
                        "byte_start": start,
                        "byte_end": end,
                        "summary": contribution["summary"],
                        "open_question": contribution["open_question"],
                        "source_revision_id": record.get("source_revision_id"),
                    }
                )
            synthesis = self._complete(
                prompt=(
                    "You are Cassi's pretrained brain synthesizing attributed theory-segment studies. "
                    "Return ONLY a JSON object with exactly two keys, `summary` and `open_question`. "
                    "Each value must contain at most sixteen words. Connect the document's central claims "
                    "and name the most important unresolved question. Do not claim that sources say more "
                    "than the segment summaries support.\n\n"
                    f"SEGMENT STUDIES: {json.dumps(segment_summaries, ensure_ascii=False, sort_keys=True)}"
                ),
                max_tokens=self.config.max_response_tokens,
                thinking=self.config.brain_thinking,
                response_format=self._response_schema(
                    frozenset({"summary", "open_question"}), max_length=128
                ),
            )
            conclusion = self._brain_json(synthesis, fields=frozenset({"summary", "open_question"}))
            study = self._record(
                source_id=f"entity:theory-document-study:{request_id}",
                context=context,
                observed_at=occurred,
                kind="theory-document-study",
                payload={
                    "task_id": task_id,
                    "source_path": relative_target,
                    "source_sha256": source_sha256,
                    "segment_count": len(segment_summaries),
                    "summary": conclusion["summary"],
                    "open_question": conclusion["open_question"],
                    "raw_content": synthesis["content"],
                    "model_id": getattr(self.brain, "model_id", "unidentified"),
                    "request_id": request_id,
                },
            )
            result = {
                "schema": ENTITY_SCHEMA,
                "entity_id": self.config.entity_id,
                "request_id": request_id,
                "task_id": task_id,
                "source_path": relative_target,
                "source_sha256": source_sha256,
                "segment_count": len(segment_summaries),
                "summary": conclusion["summary"],
                "open_question": conclusion["open_question"],
                "study_source_revision_id": study.get("source_revision_id"),
                "field_state_sha256": study.get("state_sha256"),
                "idempotent_replay": False,
            }
            return self.journal.commit(
                request_id=request_id,
                payload_sha256=digest,
                event_specs=(
                    {
                        "kind": "theory-document-studied",
                        "payload": {
                            "request_id": request_id,
                            "task_id": task_id,
                            "source_path": relative_target,
                            "source_sha256": source_sha256,
                            "segment_count": len(segment_summaries),
                            "source_revision_id": study.get("source_revision_id"),
                        },
                    },
                ),
                result=result,
            )

    def catalog_theory_documents(self) -> Mapping[str, Any]:
        """List the readable theory corpus without reading document contents."""
        with self._lock:
            if not self.config.theory_root.is_dir():
                raise ValueError("theory root does not exist")
            documents = [
                {
                    "path": path.relative_to(self.config.theory_root).as_posix(),
                    "byte_length": path.stat().st_size,
                }
                for path in sorted(self.config.theory_root.rglob("*.md"))
                if path.is_file()
            ]
            return {
                "root": str(self.config.theory_root),
                "document_count": len(documents),
                "documents": documents,
                "truncated": False,
            }

    def build_foundational_claim_map(
        self,
        *,
        request_id: str,
        task_id: str,
        conversation_id: str,
        project_id: str,
        observed_at: str | None = None,
    ) -> Mapping[str, Any]:
        """Build a complete citable atlas of the theory foundations and registries.

        The atlas deliberately records only documentary structure and byte-exact
        source anchors. It never promotes a heading into a semantic claim: later
        reasoning must consume the attributed source span itself.
        """
        request_id = _identifier(request_id, "request_id")
        task_id = _identifier(task_id, "task_id")
        conversation_id = _identifier(conversation_id, "conversation_id")
        project_id = _identifier(project_id, "project_id")
        occurred = _timestamp(observed_at)
        if not self.config.theory_root.is_dir():
            raise ValueError("theory root does not exist")
        foundation_root = self.config.theory_root / "foundations"
        documents = {
            path.relative_to(self.config.theory_root).as_posix(): path
            for path in foundation_root.rglob("*.md")
            if path.is_file()
        } if foundation_root.is_dir() else {}
        for relative in _FOUNDATIONAL_REGISTRY_PATHS:
            candidate = self.config.theory_root / relative
            if candidate.is_file():
                documents[relative] = candidate
        if not documents:
            raise ValueError("foundational theory scope contains no Markdown documents")
        prepared: list[Mapping[str, Any]] = []
        for relative, path in sorted(documents.items()):
            source = path.read_bytes()
            anchors = _markdown_section_anchors(source)
            prepared.append(
                {
                    "source_path": relative,
                    "source_sha256": hashlib.sha256(source).hexdigest(),
                    "byte_length": len(source),
                    "anchors": anchors,
                }
            )
        content_manifest = [
            {
                "source_path": document["source_path"],
                "source_sha256": document["source_sha256"],
                "byte_length": document["byte_length"],
                "anchors": document["anchors"],
            }
            for document in prepared
        ]
        source_manifest_sha256 = _sha256(content_manifest)
        payload = {
            "task_id": task_id,
            "conversation_id": conversation_id,
            "project_id": project_id,
            "source_manifest_sha256": source_manifest_sha256,
            "observed_at": occurred,
            "kind": "foundational-claim-map",
        }
        digest = _sha256(payload)
        with self._lock:
            cached = self.journal.lookup(request_id, digest)
            if cached is not None:
                return {**cached, "idempotent_replay": True}
            context = self._context(conversation_id, project_id)
            source_manifest: list[Mapping[str, Any]] = []
            roles: dict[str, int] = {}
            for document in prepared:
                anchors = document["anchors"]
                for anchor in anchors:
                    role = anchor["structural_role"]
                    roles[role] = roles.get(role, 0) + 1
                chunks = [anchors[index : index + 128] for index in range(0, len(anchors), 128)] or [[]]
                revisions: list[str | None] = []
                for chunk_index, chunk in enumerate(chunks):
                    record = self._record(
                        source_id=(
                            f"entity:theory-claim-map:{task_id}:"
                            f"{document['source_path']}:{chunk_index:04d}"
                        ),
                        context=context,
                        observed_at=occurred,
                        kind="theory-claim-map-anchor-chunk",
                        payload={
                            "task_id": task_id,
                            "source_path": document["source_path"],
                            "source_sha256": document["source_sha256"],
                            "byte_length": document["byte_length"],
                            "anchors": chunk,
                            "source_manifest_sha256": source_manifest_sha256,
                            "request_id": request_id,
                        },
                    )
                    revisions.append(record.get("source_revision_id"))
                source_manifest.append(
                    {
                        "source_path": document["source_path"],
                        "source_sha256": document["source_sha256"],
                        "byte_length": document["byte_length"],
                        "anchor_count": len(anchors),
                        "anchor_source_revision_ids": revisions,
                    }
                )
            map_record = self._record(
                source_id=f"entity:foundational-claim-map:{request_id}",
                context=context,
                observed_at=occurred,
                kind="foundational-claim-map",
                payload={
                    "task_id": task_id,
                    "scope": "foundations-and-registries",
                    "source_manifest_sha256": source_manifest_sha256,
                    "sources": source_manifest,
                    "structural_role_counts": roles,
                    "request_id": request_id,
                },
            )
            result = {
                "schema": ENTITY_SCHEMA,
                "entity_id": self.config.entity_id,
                "request_id": request_id,
                "task_id": task_id,
                "scope": "foundations-and-registries",
                "source_manifest_sha256": source_manifest_sha256,
                "document_count": len(source_manifest),
                "anchor_count": sum(item["anchor_count"] for item in source_manifest),
                "structural_role_counts": roles,
                "map_source_revision_id": map_record.get("source_revision_id"),
                "field_state_sha256": map_record.get("state_sha256"),
                "idempotent_replay": False,
            }
            return self.journal.commit(
                request_id=request_id,
                payload_sha256=digest,
                event_specs=(
                    {
                        "kind": "foundational-claim-map-built",
                        "payload": {
                            "request_id": request_id,
                            "task_id": task_id,
                            "source_manifest_sha256": source_manifest_sha256,
                            "document_count": len(source_manifest),
                            "anchor_count": result["anchor_count"],
                            "source_revision_id": map_record.get("source_revision_id"),
                        },
                    },
                ),
                result=result,
            )

    def build_foundational_relation_graph(
        self,
        *,
        request_id: str,
        task_id: str,
        conversation_id: str,
        project_id: str,
        observed_at: str | None = None,
    ) -> Mapping[str, Any]:
        """Construct source-exact structural relations across the foundational atlas."""
        request_id = _identifier(request_id, "request_id")
        task_id = _identifier(task_id, "task_id")
        conversation_id = _identifier(conversation_id, "conversation_id")
        project_id = _identifier(project_id, "project_id")
        occurred = _timestamp(observed_at)
        if not self.config.theory_root.is_dir():
            raise ValueError("theory root does not exist")
        documents = _foundation_documents(self.config.theory_root)
        if not documents:
            raise ValueError("foundational theory scope contains no Markdown documents")
        known_paths = set(documents)
        prepared: list[Mapping[str, Any]] = []
        for relative, path in sorted(documents.items()):
            source = path.read_bytes()
            anchors = _markdown_section_anchors(source)
            prepared.append(
                {
                    "source_path": relative,
                    "source": source,
                    "source_sha256": hashlib.sha256(source).hexdigest(),
                    "anchors": anchors,
                }
            )
        source_manifest_sha256 = _sha256(
            [
                {
                    "source_path": item["source_path"],
                    "source_sha256": item["source_sha256"],
                    "anchors": item["anchors"],
                }
                for item in prepared
            ]
        )
        payload = {
            "task_id": task_id,
            "conversation_id": conversation_id,
            "project_id": project_id,
            "source_manifest_sha256": source_manifest_sha256,
            "observed_at": occurred,
            "kind": "foundational-relation-graph",
        }
        digest = _sha256(payload)
        with self._lock:
            cached = self.journal.lookup(request_id, digest)
            if cached is not None:
                return {**cached, "idempotent_replay": True}
            context = self._context(conversation_id, project_id)
            first_nodes = {
                item["source_path"]: _anchor_node_id(item["source_path"], item["anchors"][0]["byte_start"])
                for item in prepared
                if item["anchors"]
            }
            source_manifest: list[Mapping[str, Any]] = []
            bridge_candidates: list[Mapping[str, Any]] = []
            edge_counts: dict[str, int] = {}
            for document in prepared:
                source_path = document["source_path"]
                anchors = document["anchors"]
                nodes = [
                    {
                        "node_id": _anchor_node_id(source_path, anchor["byte_start"]),
                        "source_path": source_path,
                        **anchor,
                    }
                    for anchor in anchors
                ]
                edges: list[Mapping[str, Any]] = []
                ancestors: list[Mapping[str, Any]] = []
                for node in nodes:
                    while ancestors and ancestors[-1]["level"] >= node["level"]:
                        ancestors.pop()
                    if ancestors:
                        edges.append(
                            {
                                "kind": "contains",
                                "source_node_id": ancestors[-1]["node_id"],
                                "target_node_id": node["node_id"],
                            }
                        )
                    ancestors.append(node)
                for match in _MARKDOWN_DOCUMENT_REFERENCE.finditer(document["source"]):
                    reference = match.group(1) or match.group(2)
                    target_path = _resolve_theory_reference(source_path, reference, known_paths)
                    if target_path is None or target_path not in first_nodes:
                        continue
                    containing = [
                        node
                        for node in nodes
                        if node["byte_start"] <= match.start() < node["byte_end"]
                    ]
                    if not containing:
                        continue
                    source_node = min(
                        containing,
                        key=lambda node: node["byte_end"] - node["byte_start"],
                    )
                    edges.append(
                        {
                            "kind": "references",
                            "source_node_id": source_node["node_id"],
                            "target_node_id": first_nodes[target_path],
                            "target_source_path": target_path,
                        }
                    )
                for edge in edges:
                    edge_counts[edge["kind"]] = edge_counts.get(edge["kind"], 0) + 1
                by_role: dict[str, list[str]] = {}
                for node in nodes:
                    by_role.setdefault(node["structural_role"], []).append(node["heading"])
                if by_role.get("mathematical-object") and (
                    by_role.get("empirical-obligation") or by_role.get("open-question")
                ):
                    bridge_candidates.append(
                        {
                            "source_path": source_path,
                            "mathematical_objects": by_role["mathematical-object"][:4],
                            "empirical_obligations": by_role.get("empirical-obligation", [])[:4],
                            "open_questions": by_role.get("open-question", [])[:4],
                        }
                    )
                records: list[Mapping[str, Any]] = []
                for chunk_index in range(0, max(len(nodes), len(edges), 1), 128):
                    records.append(
                        self._record(
                            source_id=(
                                f"entity:theory-relation-graph:{task_id}:{source_path}:"
                                f"{chunk_index // 128:04d}"
                            ),
                            context=context,
                            observed_at=occurred,
                            kind="theory-relation-graph-chunk",
                            payload={
                                "task_id": task_id,
                                "source_path": source_path,
                                "source_sha256": document["source_sha256"],
                                "source_manifest_sha256": source_manifest_sha256,
                                "nodes": nodes[chunk_index : chunk_index + 128],
                                "edges": edges[chunk_index : chunk_index + 128],
                                "request_id": request_id,
                            },
                        )
                    )
                source_manifest.append(
                    {
                        "source_path": source_path,
                        "source_sha256": document["source_sha256"],
                        "node_count": len(nodes),
                        "edge_count": len(edges),
                        "source_revision_ids": [
                            record.get("source_revision_id") for record in records
                        ],
                    }
                )
            graph = self._record(
                source_id=f"entity:foundational-relation-graph:{request_id}",
                context=context,
                observed_at=occurred,
                kind="foundational-relation-graph",
                payload={
                    "task_id": task_id,
                    "scope": "foundations-and-registries",
                    "source_manifest_sha256": source_manifest_sha256,
                    "sources": source_manifest,
                    "edge_counts": edge_counts,
                    "bridge_candidates": bridge_candidates,
                    "request_id": request_id,
                },
            )
            result = {
                "schema": ENTITY_SCHEMA,
                "entity_id": self.config.entity_id,
                "request_id": request_id,
                "task_id": task_id,
                "scope": "foundations-and-registries",
                "source_manifest_sha256": source_manifest_sha256,
                "document_count": len(source_manifest),
                "node_count": sum(item["node_count"] for item in source_manifest),
                "edge_counts": edge_counts,
                "bridge_candidate_count": len(bridge_candidates),
                "graph_source_revision_id": graph.get("source_revision_id"),
                "field_state_sha256": graph.get("state_sha256"),
                "idempotent_replay": False,
            }
            return self.journal.commit(
                request_id=request_id,
                payload_sha256=digest,
                event_specs=(
                    {
                        "kind": "foundational-relation-graph-built",
                        "payload": {
                            "request_id": request_id,
                            "task_id": task_id,
                            "source_manifest_sha256": source_manifest_sha256,
                            "document_count": result["document_count"],
                            "node_count": result["node_count"],
                            "edge_counts": edge_counts,
                            "source_revision_id": graph.get("source_revision_id"),
                        },
                    },
                ),
                result=result,
            )

    def synthesize_foundational_relation(
        self,
        *,
        request_id: str,
        task_id: str,
        conversation_id: str,
        project_id: str,
        observed_at: str | None = None,
    ) -> Mapping[str, Any]:
        """Use the live brain to select one exact atlas connection for deeper reading."""
        request_id = _identifier(request_id, "request_id")
        task_id = _identifier(task_id, "task_id")
        conversation_id = _identifier(conversation_id, "conversation_id")
        project_id = _identifier(project_id, "project_id")
        occurred = _timestamp(observed_at)
        documents = _foundation_documents(self.config.theory_root)
        candidates: list[Mapping[str, Any]] = []
        manifest: list[Mapping[str, str]] = []
        for source_path, path in sorted(documents.items()):
            source = path.read_bytes()
            anchors = _markdown_section_anchors(source)
            manifest.append(
                {
                    "source_path": source_path,
                    "source_sha256": hashlib.sha256(source).hexdigest(),
                }
            )
            mathematical = [
                anchor
                for anchor in anchors
                if anchor["structural_role"] == "mathematical-object"
            ]
            targets = [
                anchor
                for anchor in anchors
                if anchor["structural_role"] in {"empirical-obligation", "open-question"}
            ]
            for left in mathematical:
                for right in targets:
                    candidates.append(
                        {
                            "candidate_id": f"C{len(candidates) + 1:03d}",
                            "source_path": source_path,
                            "mathematical_node_id": _anchor_node_id(source_path, left["byte_start"]),
                            "mathematical_heading": left["heading"],
                            "target_node_id": _anchor_node_id(source_path, right["byte_start"]),
                            "target_role": right["structural_role"],
                            "target_heading": right["heading"],
                        }
                    )
                    if len(candidates) == 48:
                        break
                if len(candidates) == 48:
                    break
            if len(candidates) == 48:
                break
        if not candidates:
            raise ValueError("foundational theory scope contains no mathematical-to-obligation relation candidates")
        manifest_sha256 = _sha256(manifest)
        payload = {
            "task_id": task_id,
            "conversation_id": conversation_id,
            "project_id": project_id,
            "source_manifest_sha256": manifest_sha256,
            "candidate_sha256": _sha256(candidates),
            "observed_at": occurred,
            "kind": "foundational-relation-synthesis",
        }
        digest = _sha256(payload)
        with self._lock:
            cached = self.journal.lookup(request_id, digest)
            if cached is not None:
                return {**cached, "idempotent_replay": True}
            brain = self._complete(
                prompt=(
                    "You are Cassi's pretrained brain selecting the next exact theory connection to read. "
                    "Return ONLY JSON with exactly `candidate_id` and `reason`. `candidate_id` must copy "
                    "one listed id exactly. `reason` must use at most sixteen words and must not assert "
                    "that the documented connection proves a scientific claim.\n\n"
                    f"RELATION CANDIDATES: {json.dumps(candidates, ensure_ascii=False, sort_keys=True)}"
                ),
                max_tokens=self.config.max_response_tokens,
                thinking=self.config.brain_thinking,
                response_format=self._response_schema(
                    frozenset({"candidate_id", "reason"}), max_length=128
                ),
            )
            selection = self._brain_json(
                brain, fields=frozenset({"candidate_id", "reason"})
            )
            selected = next(
                (
                    candidate
                    for candidate in candidates
                    if candidate["candidate_id"] == selection["candidate_id"]
                ),
                None,
            )
            if selected is None:
                raise BrainUnavailable("required llama.cpp brain selected an unknown relation candidate")
            context = self._context(conversation_id, project_id)
            record = self._record(
                source_id=f"entity:foundational-relation-synthesis:{request_id}",
                context=context,
                observed_at=occurred,
                kind="foundational-relation-synthesis",
                payload={
                    "task_id": task_id,
                    "source_manifest_sha256": manifest_sha256,
                    "candidate_count": len(candidates),
                    "selected": selected,
                    "reason": selection["reason"],
                    "raw_content": brain["content"],
                    "model_id": getattr(self.brain, "model_id", "unidentified"),
                    "request_id": request_id,
                },
            )
            result = {
                "schema": ENTITY_SCHEMA,
                "entity_id": self.config.entity_id,
                "request_id": request_id,
                "task_id": task_id,
                "source_manifest_sha256": manifest_sha256,
                "candidate_count": len(candidates),
                "selected": selected,
                "reason": selection["reason"],
                "source_revision_id": record.get("source_revision_id"),
                "field_state_sha256": record.get("state_sha256"),
                "idempotent_replay": False,
            }
            return self.journal.commit(
                request_id=request_id,
                payload_sha256=digest,
                event_specs=(
                    {
                        "kind": "foundational-relation-selected",
                        "payload": {
                            "request_id": request_id,
                            "task_id": task_id,
                            "selected": selected,
                            "source_revision_id": record.get("source_revision_id"),
                        },
                    },
                ),
                result=result,
            )

    def derive_xi_attractor_obligation(
        self,
        *,
        request_id: str,
        task_id: str,
        conversation_id: str,
        project_id: str,
        observed_at: str | None = None,
    ) -> Mapping[str, Any]:
        """Turn Cassi's selected ξ–attractor connection into one citable test obligation."""
        request_id = _identifier(request_id, "request_id")
        task_id = _identifier(task_id, "task_id")
        conversation_id = _identifier(conversation_id, "conversation_id")
        project_id = _identifier(project_id, "project_id")
        occurred = _timestamp(observed_at)
        source_paths = (
            "foundations/xi-derivation.md",
            "foundations/phi_attractor_synthesis.md",
        )
        source_rows: list[Mapping[str, Any]] = []
        for relative in source_paths:
            _relative, path = _theory_target(relative, root=self.config.theory_root)
            source = path.read_bytes()
            anchors = _markdown_section_anchors(source)
            if relative.endswith("xi-derivation.md"):
                selected = [
                    anchor
                    for anchor in anchors
                    if anchor["heading"].startswith(("2.", "5."))
                ]
            else:
                selected = [
                    anchor
                    for anchor in anchors
                    if "Enhanced Gravitational Constant" in anchor["heading"]
                    or "Falsifiable Predictions" in anchor["heading"]
                ]
            excerpts = [
                {
                    **anchor,
                    "content": source[anchor["byte_start"] : anchor["byte_end"]]
                    .decode("utf-8")[:6_144],
                }
                for anchor in selected
            ]
            source_rows.append(
                {
                    "source_path": relative,
                    "source_sha256": hashlib.sha256(source).hexdigest(),
                    "excerpts": excerpts,
                }
            )
        source_manifest_sha256 = _sha256(source_rows)
        payload = {
            "task_id": task_id,
            "conversation_id": conversation_id,
            "project_id": project_id,
            "source_manifest_sha256": source_manifest_sha256,
            "observed_at": occurred,
            "kind": "xi-attractor-obligation",
        }
        digest = _sha256(payload)
        with self._lock:
            cached = self.journal.lookup(request_id, digest)
            if cached is not None:
                return {**cached, "idempotent_replay": True}
            brain = self._complete(
                prompt=(
                    "You are Cassi's pretrained brain forming one source-grounded research contribution. "
                    "Return ONLY JSON with exactly `contribution` and `empirical_obligation`. Each value "
                    "must contain at most sixteen words. State the conditional ξ-to-saturation connection, "
                    "then name the object-level dwarf likelihood or fixed-composition endpoint test described "
                    "by the excerpts. Do not claim physical confirmation.\n\n"
                    f"XI-ATTRACTOR EVIDENCE: {json.dumps(source_rows, ensure_ascii=False, sort_keys=True)}"
                ),
                max_tokens=self.config.max_response_tokens,
                thinking=self.config.brain_thinking,
                response_format=self._response_schema(
                    frozenset({"contribution", "empirical_obligation"}), max_length=128
                ),
            )
            result_text = self._brain_json(
                brain, fields=frozenset({"contribution", "empirical_obligation"})
            )
            context = self._context(conversation_id, project_id)
            record = self._record(
                source_id=f"entity:xi-attractor-obligation:{request_id}",
                context=context,
                observed_at=occurred,
                kind="xi-attractor-obligation",
                payload={
                    "task_id": task_id,
                    "source_manifest_sha256": source_manifest_sha256,
                    "sources": source_rows,
                    **result_text,
                    "raw_content": brain["content"],
                    "model_id": getattr(self.brain, "model_id", "unidentified"),
                    "request_id": request_id,
                },
            )
            result = {
                "schema": ENTITY_SCHEMA,
                "entity_id": self.config.entity_id,
                "request_id": request_id,
                "task_id": task_id,
                "source_manifest_sha256": source_manifest_sha256,
                "sources": [
                    {
                        "source_path": row["source_path"],
                        "source_sha256": row["source_sha256"],
                        "excerpt_count": len(row["excerpts"]),
                    }
                    for row in source_rows
                ],
                **result_text,
                "source_revision_id": record.get("source_revision_id"),
                "field_state_sha256": record.get("state_sha256"),
                "idempotent_replay": False,
            }
            return self.journal.commit(
                request_id=request_id,
                payload_sha256=digest,
                event_specs=(
                    {
                        "kind": "xi-attractor-obligation-derived",
                        "payload": {
                            "request_id": request_id,
                            "task_id": task_id,
                            "source_manifest_sha256": source_manifest_sha256,
                            "source_revision_id": record.get("source_revision_id"),
                        },
                    },
                ),
                result=result,
            )

    def build_dwarf_likelihood_spec(
        self,
        *,
        request_id: str,
        task_id: str,
        conversation_id: str,
        project_id: str,
        observed_at: str | None = None,
    ) -> Mapping[str, Any]:
        """Persist the source-defined object-level test for the pure-G saturation branch."""
        request_id = _identifier(request_id, "request_id")
        task_id = _identifier(task_id, "task_id")
        conversation_id = _identifier(conversation_id, "conversation_id")
        project_id = _identifier(project_id, "project_id")
        occurred = _timestamp(observed_at)
        source_paths = (
            "foundations/phi_attractor_synthesis.md",
            "experiments/phi_attractor_paths/path10_dwarf_galaxies.py",
        )
        source_rows: list[Mapping[str, Any]] = []
        for relative in source_paths:
            _relative, path = _theory_target(relative, root=self.config.theory_root)
            source = path.read_bytes()
            if relative.endswith(".md"):
                excerpts = [
                    {
                        **anchor,
                        "content": source[anchor["byte_start"] : anchor["byte_end"]]
                        .decode("utf-8")[:6_144],
                    }
                    for anchor in _markdown_section_anchors(source)
                    if "Path 9:" in anchor["heading"] or anchor["heading"].endswith("Falsifiable Predictions")
                ]
            else:
                excerpts = [
                    {
                        "heading": "Path 10 nominal-screen data contract",
                        "byte_start": 0,
                        "byte_end": min(len(source), 6_144),
                        "content_sha256": hashlib.sha256(source[:6_144]).hexdigest(),
                        "content": source[:6_144].decode("utf-8"),
                    }
                ]
            source_rows.append(
                {
                    "source_path": relative,
                    "source_sha256": hashlib.sha256(source).hexdigest(),
                    "excerpts": excerpts,
                }
            )
        source_manifest_sha256 = _sha256(source_rows)
        specification = {
            "kind": "dwarf-likelihood-specification",
            "scope": "optional-pure-G-fixed-baryonic-composition",
            "endpoint": {
                "observable": "v_obs_over_v_Newt_at_r_half",
                "value": "phi^3",
                "decimal": 4.23606797749979,
                "branch_rule": "A robust object-level requirement above this endpoint rejects only this branch.",
            },
            "candidate_frame": {
                "catalog_source": "McConnachie 2012, arXiv:1204.1562v2, Tables 3 and 4",
                "objects": (
                    "Segue 1",
                    "Segue 2",
                    "Willman 1",
                    "Bootes I",
                    "Coma Berenices",
                    "Draco",
                    "Sculptor",
                    "Fornax",
                ),
                "catalog_role": "candidate frame only; its fixed M_star/L_V=1 proxies are not mass posteriors",
            },
            "per_object_inputs": (
                "member-star line-of-sight velocity measurements with uncertainties and membership probabilities",
                "multi-epoch binary-star information or an explicit binary-contamination component",
                "projected half-light-radius posterior and structural-photometry provenance",
                "luminosity and stellar-population mass-to-light posterior",
                "tidal, nonsphericity, velocity-anisotropy, and dynamical-equilibrium quality flags",
            ),
            "derived_quantity": {
                "radius": "r_half = 4 R_e / 3",
                "kinematic_estimator": "v_obs(r_half) = sqrt(3) sigma_los",
                "baryonic_baseline": "v_Newt(r_half) = sqrt(G [M_star(<r_half)] / r_half)",
                "catalog_screen_convention": "M_star(<r_half)=0.5 M_star_proxy; replaced by the stellar-mass posterior in the likelihood",
            },
            "comparators": (
                "pure-G fixed-composition Cassi endpoint",
                "MOND",
                "dark-matter model",
                "alternative Cassi matter channel",
            ),
            "same_data_rule": "Every comparator receives the identical object-level measurements, membership treatment, quality cuts, and stellar-population assumptions.",
            "required_outputs": (
                "per-object posterior probability for v_obs/v_Newt > phi^3",
                "population likelihood for the fixed-composition endpoint",
                "comparator likelihoods on the same retained objects",
                "source-file hashes, source versions, and all exclusion reasons",
            ),
            "current_status": "specification-complete; primary object-level data not yet admitted",
        }
        payload = {
            "task_id": task_id,
            "conversation_id": conversation_id,
            "project_id": project_id,
            "source_manifest_sha256": source_manifest_sha256,
            "specification_sha256": _sha256(specification),
            "observed_at": occurred,
            "kind": "dwarf-likelihood-specification",
        }
        digest = _sha256(payload)
        with self._lock:
            cached = self.journal.lookup(request_id, digest)
            if cached is not None:
                return {**cached, "idempotent_replay": True}
            brain = self._complete(
                prompt=(
                    "You are Cassi's pretrained brain translating an already-fixed observational specification "
                    "into the first concrete study action. Return ONLY JSON with exactly `first_action` and "
                    "`decision_boundary`. Each value must contain at most sixteen words. `first_action` MUST "
                    "name member-star spectroscopy and binary treatment. `decision_boundary` MUST say that "
                    "only the fixed-composition pure-G branch is rejected if the shared-data likelihood "
                    "requires a boost above phi cubed. McConnachie catalog proxies alone are insufficient. "
                    "Do not invent data or pronounce a model verdict.\n\n"
                    f"DWARF LIKELIHOOD SPECIFICATION: {json.dumps(specification, ensure_ascii=False, sort_keys=True)}\n\n"
                    f"SOURCE EVIDENCE: {json.dumps(source_rows, ensure_ascii=False, sort_keys=True)}"
                ),
                max_tokens=self.config.max_response_tokens,
                thinking=self.config.brain_thinking,
                response_format=self._response_schema(
                    frozenset({"first_action", "decision_boundary"}), max_length=128
                ),
            )
            brief = self._brain_json(brain, fields=frozenset({"first_action", "decision_boundary"}))
            action = brief["first_action"].casefold()
            boundary = brief["decision_boundary"].casefold()
            if "member" not in action or "binary" not in action:
                raise BrainUnavailable("dwarf study brief omitted the required member-star or binary treatment")
            if "reject" not in boundary or "branch" not in boundary or "phi" not in boundary:
                raise BrainUnavailable("dwarf study brief omitted the conditional pure-G endpoint decision rule")
            context = self._context(conversation_id, project_id)
            record = self._record(
                source_id=f"entity:dwarf-likelihood-specification:{request_id}",
                context=context,
                observed_at=occurred,
                kind="dwarf-likelihood-specification",
                payload={
                    "task_id": task_id,
                    "source_manifest_sha256": source_manifest_sha256,
                    "sources": source_rows,
                    "specification": specification,
                    "specification_sha256": payload["specification_sha256"],
                    **brief,
                    "raw_content": brain["content"],
                    "model_id": getattr(self.brain, "model_id", "unidentified"),
                    "request_id": request_id,
                },
            )
            result = {
                "schema": ENTITY_SCHEMA,
                "entity_id": self.config.entity_id,
                "request_id": request_id,
                "task_id": task_id,
                "source_manifest_sha256": source_manifest_sha256,
                "specification_sha256": payload["specification_sha256"],
                "sources": [
                    {
                        "source_path": row["source_path"],
                        "source_sha256": row["source_sha256"],
                        "excerpt_count": len(row["excerpts"]),
                    }
                    for row in source_rows
                ],
                "specification": specification,
                **brief,
                "source_revision_id": record.get("source_revision_id"),
                "field_state_sha256": record.get("state_sha256"),
                "idempotent_replay": False,
            }
            return self.journal.commit(
                request_id=request_id,
                payload_sha256=digest,
                event_specs=(
                    {
                        "kind": "dwarf-likelihood-specified",
                        "payload": {
                            "request_id": request_id,
                            "task_id": task_id,
                            "source_manifest_sha256": source_manifest_sha256,
                            "specification_sha256": payload["specification_sha256"],
                            "source_revision_id": record.get("source_revision_id"),
                        },
                    },
                ),
                result=result,
            )

    def describe_proposal(self, proposal_id: str) -> Mapping[str, Any]:
        """Return the exact human approval surface for one pending capability."""
        proposal = self.journal.proposal(proposal_id)
        approval = self.journal.approval(proposal_id)
        if proposal["capability"] == _THEORY_EXCERPT_CAPABILITY:
            effect = (
                f"Read bytes {proposal['byte_start']}..{proposal['byte_end']} from "
                f"theory document {proposal['target_path']} and retain that excerpt for local study."
            )
        else:
            effect = (
                f"Read metadata and SHA-256 only for {proposal['target_path']}; "
                "no file content will be retained."
            )
        return {
            "proposal": proposal,
            "approval": approval,
            "status": "approved" if approval is not None else "pending-approval",
            "effect": effect,
        }

    def study_theory_excerpt(
        self,

        *,
        request_id: str,
        proposal_id: str,
        observed_at: str | None = None,
    ) -> Mapping[str, Any]:
        """Let the live brain study one already approved and retained theory excerpt."""
        request_id = _identifier(request_id, "request_id")
        proposal_id = _identifier(proposal_id, "proposal_id")
        occurred = _timestamp(observed_at)
        payload = {"proposal_id": proposal_id, "observed_at": occurred, "kind": "theory-study"}
        digest = _sha256(payload)
        with self._lock:
            cached = self.journal.lookup(request_id, digest)
            if cached is not None:
                return {**cached, "idempotent_replay": True}
            proposal = self.journal.proposal(proposal_id)
            execution = self.journal.execution(proposal_id)
            if proposal["capability"] != _THEORY_EXCERPT_CAPABILITY or execution is None:
                raise ValueError("theory study requires an executed theory-excerpt proposal")
            outcome = execution["outcome"]
            excerpt = outcome.get("content")
            if not isinstance(excerpt, str):
                raise RuntimeError("theory excerpt execution lacks readable content")
            brain = self._complete(
                prompt=(
                    "You are Cassi's pretrained brain studying an attributed local theory excerpt. "
                    "Return ONLY a JSON object with exactly two keys, `summary` and `open_question`. "
                    "Treat this excerpt as a source, distinguish its stated content from your inference, "
                    "and do not claim any experiment or external action occurred.\n\n"
                    f"SOURCE: {json.dumps(outcome, ensure_ascii=False, sort_keys=True)}"
                ),
                max_tokens=self.config.max_response_tokens,
                thinking=self.config.brain_thinking,
                response_format=self._response_schema(frozenset({"summary", "open_question"})),
            )
            contribution = self._brain_json(brain, fields=frozenset({"summary", "open_question"}))
            context = self._context(proposal["conversation_id"], proposal["project_id"])
            study = self._record(
                source_id=f"entity:theory-study:{request_id}",
                context=context,
                observed_at=occurred,
                kind="theory-study",
                payload={
                    "proposal_id": proposal_id,
                    "source_path": outcome["target_path"],
                    "source_sha256": outcome["source_sha256"],
                    "byte_start": outcome["byte_start"],
                    "byte_end": outcome["byte_end"],
                    "content_sha256": outcome["content_sha256"],
                    "summary": contribution["summary"],
                    "open_question": contribution["open_question"],
                    "raw_content": brain["content"],
                    "model_id": getattr(self.brain, "model_id", "unidentified"),
                    "request_id": request_id,
                },
            )
            result = {
                "schema": ENTITY_SCHEMA,
                "entity_id": self.config.entity_id,
                "request_id": request_id,
                "proposal_id": proposal_id,
                "summary": contribution["summary"],
                "open_question": contribution["open_question"],
                "source": {
                    "path": outcome["target_path"],
                    "sha256": outcome["source_sha256"],
                    "byte_start": outcome["byte_start"],
                    "byte_end": outcome["byte_end"],
                    "content_sha256": outcome["content_sha256"],
                },
                "study_source_revision_id": study.get("source_revision_id"),
                "field_state_sha256": study.get("state_sha256"),
                "idempotent_replay": False,
            }
            return self.journal.commit(
                request_id=request_id,
                payload_sha256=digest,
                event_specs=(
                    {
                        "kind": "theory-studied",
                        "payload": {
                            "request_id": request_id,
                            "proposal_id": proposal_id,
                            "source_revision_id": study.get("source_revision_id"),
                        },
                    },
                ),
                result=result,
            )
    def admit_dwarf_observation_sources(
        self,
        *,
        request_id: str,
        task_id: str,
        conversation_id: str,
        project_id: str,
        observed_at: str | None = None,
    ) -> Mapping[str, Any]:
        """Hash and retain local raw CDS sources without treating them as a likelihood verdict."""
        request_id = _identifier(request_id, "request_id")
        task_id = _identifier(task_id, "task_id")
        conversation_id = _identifier(conversation_id, "conversation_id")
        project_id = _identifier(project_id, "project_id")
        occurred = _timestamp(observed_at)
        cache_root = self.config.data_home / "dwarf-likelihood-sources"
        source_rows: list[Mapping[str, Any]] = []
        for source in _DWARF_OBSERVATION_SOURCES:
            artifacts: list[Mapping[str, Any]] = []
            for filename, expected_records, origin_url in source["artifacts"]:
                path = cache_root / filename
                if not path.is_file():
                    raise ValueError(f"required dwarf observation source is absent: {filename}")
                raw = path.read_bytes()
                records = raw.count(b"\n")
                if expected_records is not None and records != expected_records:
                    raise ValueError(
                        f"{filename} has {records} records; expected {expected_records} from its CDS manifest"
                    )
                artifacts.append(
                    {
                        "filename": filename,
                        "origin_url": origin_url,
                        "byte_length": len(raw),
                        "sha256": hashlib.sha256(raw).hexdigest(),
                        "record_count": records if expected_records is not None else None,
                        "expected_record_count": expected_records,
                    }
                )
            source_rows.append(
                {
                    "source_id": source["source_id"],
                    "catalog": source["catalog"],
                    "citation": source["citation"],
                    "objects": source["objects"],
                    "likelihood_roles": source["likelihood_roles"],
                    "artifacts": artifacts,
                }
            )
        source_manifest_sha256 = _sha256(source_rows)
        coverage = {
            "candidate_objects": (
                "Segue 1", "Segue 2", "Willman 1", "Bootes I", "Coma Berenices", "Draco", "Sculptor", "Fornax",
            ),
            "objects_with_admitted_individual_velocity_rows": (
                "Segue 1", "Segue 2", "Bootes I", "Coma Berenices", "Draco", "Sculptor", "Fornax",
            ),
            "objects_awaiting_individual_velocity_admission": (),
            "quality_deferred_objects": {
                "Willman 1": "Its primary study reports foreground contamination and an irregular, nonequilibrium kinematic distribution.",
            },
            "admitted_catalog_capabilities": (
                "structural candidate frame for all eight targets",
                "member or probabilistic membership for Segue 1, Segue 2, Bootes I, Sculptor, and Fornax",
                "velocity-variability evidence for Segue 1 and Bootes I",
                "author-hosted individual velocity and membership-coded table for Coma Berenices",
            ),
            "unresolved_likelihood_inputs": (
                "binary population model for every retained target",
                "stellar-population mass-to-light posterior",
                "target-specific tidal, equilibrium, anisotropy, and nonsphericity assessment",
                "independent equilibrium analysis before considering Willman 1",
            ),
            "likelihood_specification_sha256": "3d4c0abd30c04ad36781c8e069e1bfeee6e7cf05ed9f07374699324dc18faee0",
            "status": "primary-kinematics-admitted-for-seven-targets; Willman-1-quality-deferred; no likelihood or model verdict",
        }
        payload = {
            "task_id": task_id,
            "conversation_id": conversation_id,
            "project_id": project_id,
            "source_manifest_sha256": source_manifest_sha256,
            "coverage_sha256": _sha256(coverage),
            "observed_at": occurred,
            "kind": "dwarf-observation-source-admission",
        }
        digest = _sha256(payload)
        with self._lock:
            cached = self.journal.lookup(request_id, digest)
            if cached is not None:
                return {**cached, "idempotent_replay": True}
            context = self._context(conversation_id, project_id)
            record = self._record(
                source_id=f"entity:dwarf-observation-source-admission:{request_id}",
                context=context,
                observed_at=occurred,
                kind="dwarf-observation-source-admission",
                payload={
                    "task_id": task_id,
                    "source_manifest_sha256": source_manifest_sha256,
                    "sources": source_rows,
                    "coverage": coverage,
                    "coverage_sha256": payload["coverage_sha256"],
                    "request_id": request_id,
                },
            )
            result = {
                "schema": ENTITY_SCHEMA,
                "entity_id": self.config.entity_id,
                "request_id": request_id,
                "task_id": task_id,
                "source_manifest_sha256": source_manifest_sha256,
                "coverage_sha256": payload["coverage_sha256"],
                "sources": source_rows,
                "coverage": coverage,
                "source_revision_id": record.get("source_revision_id"),
                "field_state_sha256": record.get("state_sha256"),
                "idempotent_replay": False,
            }
            return self.journal.commit(
                request_id=request_id,
                payload_sha256=digest,
                event_specs=(
                    {
                        "kind": "dwarf-observation-sources-admitted",
                        "payload": {
                            "request_id": request_id,
                            "task_id": task_id,
                            "source_manifest_sha256": source_manifest_sha256,
                            "coverage_sha256": payload["coverage_sha256"],
                            "source_revision_id": record.get("source_revision_id"),
                        },
                    },
                ),
                result=result,
            )

    def admit_dwarf_stellar_population_evidence(
        self,
        *,
        request_id: str,
        task_id: str,
        conversation_id: str,
        project_id: str,
        observed_at: str | None = None,
    ) -> Mapping[str, Any]:
        """Admit source-bound population evidence without inventing a common stellar-mass posterior."""
        request_id = _identifier(request_id, "request_id")
        task_id = _identifier(task_id, "task_id")
        conversation_id = _identifier(conversation_id, "conversation_id")
        project_id = _identifier(project_id, "project_id")
        occurred = _timestamp(observed_at)
        cache_root = self.config.data_home / "dwarf-likelihood-sources"
        source_rows: list[Mapping[str, Any]] = []
        for source in _DWARF_STELLAR_POPULATION_SOURCES:
            filename, origin_url = source["artifact"]
            path = cache_root / filename
            if not path.is_file():
                raise ValueError(f"required dwarf stellar-population source is absent: {filename}")
            raw = path.read_bytes()
            source_rows.append(
                {
                    "source_id": source["source_id"],
                    "citation": source["citation"],
                    "objects": source["objects"],
                    "evidence_role": source["evidence_role"],
                    "artifact": {
                        "filename": filename,
                        "origin_url": origin_url,
                        "byte_length": len(raw),
                        "sha256": hashlib.sha256(raw).hexdigest(),
                    },
                }
            )
        source_manifest_sha256 = _sha256(source_rows)
        registry = {
            "kind": "dwarf-stellar-population-evidence-registry",
            "candidate_objects": (
                "Segue 1", "Segue 2", "Bootes I", "Coma Berenices", "Draco", "Sculptor", "Fornax",
            ),
            "per_object": {
                "Segue 1": {
                    "source_ids": ("martin-2008-structural-stellar-masses", "frebel-2014-segue-1-population"),
                    "status": "population evidence admitted; no common present-day stellar-mass posterior",
                },
                "Segue 2": {
                    "source_ids": ("kirby-2013-segue-2-population",),
                    "status": "luminosity and population-duration evidence admitted; no stellar-mass posterior",
                },
                "Bootes I": {
                    "source_ids": ("martin-2008-structural-stellar-masses", "brown-2014-ultrafaint-star-formation"),
                    "status": "CMD luminosity and resolved-population evidence admitted; no common present-day stellar-mass posterior",
                },
                "Coma Berenices": {
                    "source_ids": (
                        "martin-2008-structural-stellar-masses",
                        "brown-2014-ultrafaint-star-formation",
                        "gennaro-2018-coma-imf",
                    ),
                    "status": "CMD luminosity, resolved-population, and low-mass-IMF evidence admitted; no common present-day stellar-mass posterior",
                },
                "Draco": {
                    "source_ids": ("aparicio-2001-draco-star-formation",),
                    "status": "resolved population evidence admitted; published stellar-plus-remnant estimate remains retention- and aperture-conditional",
                },
                "Sculptor": {
                    "source_ids": ("deboer-2012-sculptor-star-formation",),
                    "status": "resolved population evidence admitted; published quantity is aperture-defined mass formed, not a present-day mass posterior",
                },
                "Fornax": {
                    "source_ids": ("deboer-2012-fornax-star-formation",),
                    "status": "resolved population evidence admitted; published quantity is aperture-defined mass formed, not a present-day mass posterior",
                },
            },
            "source_conditioned_mass_constraints": _DWARF_STELLAR_MASS_CONSTRAINTS,
            "present_day_mass_definition": {
                "symbol": "M_star_now",
                "includes": (
                    "gravitational mass in surviving nuclear-burning stars",
                    "gravitational mass in retained white dwarfs, neutron stars, and black holes",
                ),
                "excludes": ("gas", "ejected stellar mass", "dark matter", "unretained remnants"),
                "spatial_scope": "the globally bound stellar body; an aperture quantity MUST be separately mapped",
                "half_light_requirement": "M_star(<r_half) requires a source-matched stellar spatial-profile posterior",
            },
            "posterior_input_contract": {
                "per_target_required_fields": (
                    "target_id",
                    "posterior_weight",
                    "M_star_now_global_msun",
                    "M_star_now_r_half_msun",
                    "IMF and binary-population specification",
                    "star-formation-history and metallicity specification",
                    "remnant initial-final-mass relation and retention prescription",
                    "photometric-membership normalization and aperture mapping",
                    "primary-source artifact hash",
                ),
                "admission_rule": (
                    "Each target MUST supply posterior samples or a normalized posterior grid under the common "
                    "definition; published point estimates, formed masses, and unweighted IMF alternatives are constraints, not draws."
                ),
                "source_conditioned_constraints_rule": (
                    "Retain the Martin and Aparicio quantities as explicit model conditionals; MUST NOT mix their "
                    "IMFs, apertures, or retention rules into one posterior without a declared model probability."
                ),
            },
            "excluded_catalog_proxy": {
                "source": "McConnachie 2012 Table 4",
                "rule": "Its fixed M_star/L_V=1 values remain rescalable catalog proxies and MUST NOT enter the mass posterior.",
            },
            "kinematic_evidence_link": {
                "required_audit": "dwarf-kinematic-source-audit",
                "audit_endpoint": "/v1/theory/observations/dwarf-kinematics/audit",
                "source_admission_manifest_sha256": "6cb8fc12177e7688ed858c43303eae9334cb4bc48f90cc6195b722b5d9987507",
                "rule": "A future mass likelihood MUST join these population inputs to the same retained target identities and selection audit.",
            },
            "readiness": {
                "stellar_mass_posterior_ready": False,
                "likelihood_ready": False,
                "next_required_inputs": (
                    "a posterior sample or normalized grid for every retained target under present_day_mass_definition",
                    "an IMF- and population-conditioned living-star and remnant mass model for each retained target",
                    "source-matched aperture mapping to M_star(<r_half)",
                    "CMD shot-noise-aware luminosity and membership normalization for the ultra-faint targets",
                ),
            },
            "scope": "source admission and mass-model readiness only; no mass draw, kinematic fit, endpoint probability, or model verdict",
        }
        registry_sha256 = _sha256(registry)
        payload = {
            "task_id": task_id,
            "conversation_id": conversation_id,
            "project_id": project_id,
            "source_manifest_sha256": source_manifest_sha256,
            "registry_sha256": registry_sha256,
            "observed_at": occurred,
            "kind": "dwarf-stellar-population-evidence-admission",
        }
        digest = _sha256(payload)
        with self._lock:
            cached = self.journal.lookup(request_id, digest)
            if cached is not None:
                return {**cached, "idempotent_replay": True}
            record = self._record(
                source_id=f"entity:dwarf-stellar-population-evidence-admission:{request_id}",
                context=self._context(conversation_id, project_id),
                observed_at=occurred,
                kind="dwarf-stellar-population-evidence-admission",
                payload={
                    "task_id": task_id,
                    "source_manifest_sha256": source_manifest_sha256,
                    "sources": source_rows,
                    "registry": registry,
                    "registry_sha256": registry_sha256,
                    "request_id": request_id,
                },
            )
            result = {
                "schema": ENTITY_SCHEMA,
                "entity_id": self.config.entity_id,
                "request_id": request_id,
                "task_id": task_id,
                "source_manifest_sha256": source_manifest_sha256,
                "registry_sha256": registry_sha256,
                "sources": source_rows,
                "registry": registry,
                "source_revision_id": record.get("source_revision_id"),
                "field_state_sha256": record.get("state_sha256"),
                "idempotent_replay": False,
            }
            return self.journal.commit(
                request_id=request_id,
                payload_sha256=digest,
                event_specs=(
                    {
                        "kind": "dwarf-stellar-population-evidence-admitted",
                        "payload": {
                            "request_id": request_id,
                            "task_id": task_id,
                            "source_manifest_sha256": source_manifest_sha256,
                            "registry_sha256": registry_sha256,
                            "source_revision_id": record.get("source_revision_id"),
                        },
                    },
                ),
                result=result,
            )

    def audit_dwarf_kinematic_sources(
        self,
        *,
        request_id: str,
        task_id: str,
        conversation_id: str,
        project_id: str,
        observed_at: str | None = None,
    ) -> Mapping[str, Any]:
        """Make source-native membership selections explicit without fitting a galaxy model."""
        request_id = _identifier(request_id, "request_id")
        task_id = _identifier(task_id, "task_id")
        conversation_id = _identifier(conversation_id, "conversation_id")
        project_id = _identifier(project_id, "project_id")
        occurred = _timestamp(observed_at)
        cache_root = self.config.data_home / "dwarf-likelihood-sources"

        def table(filename: str) -> tuple[bytes, list[bytes]]:
            path = cache_root / filename
            if not path.is_file():
                raise ValueError(f"required dwarf kinematic table is absent: {filename}")
            raw = path.read_bytes()
            return raw, raw.splitlines()

        segue1_raw, segue1_rows = table("segue1-simon2011-table3.dat")
        segue1_members = [row for row in segue1_rows if len(row) >= 80 and row[79:80] == b"1"]
        segue2_raw, segue2_rows = table("segue2-kirby2013-table2.dat")
        segue2_members = [row for row in segue2_rows if len(row) >= 94 and row[93:94] in (b"Y", b"B")]
        bootes_raw, bootes_rows = table("bootes1-koposov2011-table1.dat")
        bootes_members = [row for row in bootes_rows if len(row) >= 84 and row[83:84] == b"B"]
        fornax_raw, fornax_rows = table("fornax-walker2009-table3.dat")
        sculptor_raw, sculptor_rows = table("sculptor-walker2009-table4.dat")
        draco_raw, draco_rows = table("draco-kleyna2002-table1.dat")
        coma_raw, coma_rows = table("comaber-simongeha2007-velocities.dat")

        def membership_scores(rows: Sequence[bytes]) -> Mapping[str, Any]:
            scores = [
                float(row[93:98])
                for row in rows
                if len(row) >= 98 and row[93:98].strip()
            ]
            return {
                "row_count": len(rows),
                "finite_membership_score_count": len(scores),
                "membership_score_min": min(scores) if scores else None,
                "membership_score_max": max(scores) if scores else None,
                "selection_rule": "Scores retained unthresholded; likelihood will declare any selection threshold.",
            }

        audit = {
            "kind": "dwarf-kinematic-source-audit",
            "selection_audit": {
                "Segue 1": {
                    "raw_row_count": len(segue1_rows),
                    "member_measurement_count": len(segue1_members),
                    "unique_member_target_count": len({row[4:23].strip() for row in segue1_members}),
                    "selection_rule": "Simon et al. Mm=1 member flag; repeated rows retained for binary treatment.",
                    "source_sha256": hashlib.sha256(segue1_raw).hexdigest(),
                },
                "Segue 2": {
                    "raw_row_count": len(segue2_rows),
                    "member_target_count": len(segue2_members),
                    "selection_rule": "Kirby et al. Mm in {Y, B}; B denotes a horizontal-branch member.",
                    "source_sha256": hashlib.sha256(segue2_raw).hexdigest(),
                },
                "Bootes I": {
                    "raw_row_count": len(bootes_rows),
                    "best_member_count": len(bootes_members),
                    "selection_rule": "Koposov et al. Mm=B best flag; its definition includes non-variability and velocity-quality criteria.",
                    "source_sha256": hashlib.sha256(bootes_raw).hexdigest(),
                },
                "Fornax": {**membership_scores(fornax_rows), "source_sha256": hashlib.sha256(fornax_raw).hexdigest()},
                "Sculptor": {**membership_scores(sculptor_rows), "source_sha256": hashlib.sha256(sculptor_raw).hexdigest()},
                "Draco": {
                    "raw_row_count": len(draco_rows),
                    "catalog_member_row_count": len(draco_rows),
                    "selection_rule": "Kleyna et al. table1 is explicitly the observed-member-star table.",
                    "source_sha256": hashlib.sha256(draco_raw).hexdigest(),
                },
                "Coma Berenices": {
                    "raw_row_count": len(coma_rows),
                    "selection_rule": "Author-hosted Simon & Geha table retained raw; column-level selection awaits explicit source-column schema.",
                    "source_sha256": hashlib.sha256(coma_raw).hexdigest(),
                },
                "Willman 1": {
                    "status": "quality-deferred",
                    "selection_rule": "Do not form an equilibrium likelihood until an independent equilibrium analysis addresses its primary-study warning.",
                },
            },
            "scope": "source-native selection accounting only; no velocity-dispersion, mass, endpoint, or model calculation",
            "source_admission_manifest_sha256": "6cb8fc12177e7688ed858c43303eae9334cb4bc48f90cc6195b722b5d9987507",
        }
        audit_sha256 = _sha256(audit)
        payload = {
            "task_id": task_id,
            "conversation_id": conversation_id,
            "project_id": project_id,
            "audit_sha256": audit_sha256,
            "observed_at": occurred,
            "kind": "dwarf-kinematic-source-audit",
        }
        digest = _sha256(payload)
        with self._lock:
            cached = self.journal.lookup(request_id, digest)
            if cached is not None:
                return {**cached, "idempotent_replay": True}
            record = self._record(
                source_id=f"entity:dwarf-kinematic-source-audit:{request_id}",
                context=self._context(conversation_id, project_id),
                observed_at=occurred,
                kind="dwarf-kinematic-source-audit",
                payload={"task_id": task_id, "audit": audit, "audit_sha256": audit_sha256, "request_id": request_id},
            )
            result = {
                "schema": ENTITY_SCHEMA,
                "entity_id": self.config.entity_id,
                "request_id": request_id,
                "task_id": task_id,
                "audit": audit,
                "audit_sha256": audit_sha256,
                "source_revision_id": record.get("source_revision_id"),
                "field_state_sha256": record.get("state_sha256"),
                "idempotent_replay": False,
            }
            return self.journal.commit(
                request_id=request_id,
                payload_sha256=digest,
                event_specs=(
                    {
                        "kind": "dwarf-kinematic-sources-audited",
                        "payload": {
                            "request_id": request_id,
                            "task_id": task_id,
                            "audit_sha256": audit_sha256,
                            "source_revision_id": record.get("source_revision_id"),
                        },
                    },
                ),
                result=result,
            )


def open_local_entity(
    data_home: Path,
    *,
    model_url: str,
    model_path: Path,
    entity_id: str = "cassi",
    capability_root: Path | None = None,
    theory_root: Path | None = None,
    research_home: Path | None = None,
    research_roots: tuple[Path, ...] | None = None,
    research_network_hosts: tuple[str, ...] = (),
    research_cycle_interval_seconds: float = 1.0,
    research_default_tools: tuple[str, ...] = (
        "list_files",
        "read_file",
        "search_text",
        "write_artifact",
        "inspect_artifact",
    ),
    research_resident_enabled: bool = True,
) -> FieldBrainEntity:
    """Open the explicit field–brain profile against one loopback llama.cpp model."""
    client = LocalQwenClient(model_url, model_path=model_path)
    return FieldBrainEntity(
        EntityConfig(
            data_home=data_home,
            entity_id=entity_id,
            capability_root=capability_root,
            theory_root=theory_root,
            research_home=research_home,
            research_roots=research_roots,
            research_network_hosts=research_network_hosts,
            research_cycle_interval_seconds=research_cycle_interval_seconds,
            research_default_tools=research_default_tools,
            research_resident_enabled=research_resident_enabled,
        ),
        brain=client,
    )


__all__ = [
    "BrainClient",
    "BrainUnavailable",
    "ENTITY_PROFILE",
    "ENTITY_SCHEMA",
    "EntityConfig",
    "FieldBrainEntity",
    "open_local_entity",
]
