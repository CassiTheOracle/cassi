"""Field foundry: declare a specialized CassiFI field, build it, and keep it on a shelf.

A field kind says what a specialized field holds: how to read its sources, how
to lay them out as named values, and which reader opens it.  The foundry turns a
kind plus a small config into one paged regional image persisted as
content-addressed pages.  A shelf keeps many such fields by name, notices when a
field has fallen behind its sources, rebuilds only those as new generations, and
retires old generations while unchanged pages stay shared between them.

Every kind can also use the foundry term index: hand it term counts for the
kind's units while composing, and rank those units later with BM25 from index
shards held in the field itself.
"""
from __future__ import annotations

import argparse
import base64
import importlib
import json
import math
import os
import re
import shutil
import sys
import time
import zlib
from array import array
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np

import cassi_field_regions as regions
from cassi_field_storage import DiskObjectStore

FOUNDRY_SCHEMA = "cassifi.field-foundry.v1"
SHELF_SCHEMA = "cassifi.field-shelf.v1"
TERMS_SCHEMA = "cassifi.field-terms.v1"
MANIFEST_VALUE = "foundry"
INDEX_VALUE = "index"
INDEX_LENGTHS_VALUE = "index:lengths"
INDEX_PREFIX = "index:"
FIELD_DESCRIPTOR = "field.json"
BUILD_RECEIPT = "build.json"
OBJECT_DIRECTORY = "objects"
SHELF_FILE = "shelf.json"
LOCK_FILE = ".shelf.lock"
GENERATION_PREFIX = "gen-"
DEFAULT_SHELF_HOME = Path(__file__).resolve().parent / "_diag" / "fields"
DEFAULT_RESIDENT_PAGES = 256
DEFAULT_KEEP_GENERATIONS = 2
LOCK_STALE_SECONDS = 900.0
LOCK_WAIT_SECONDS = 1800.0
GROWTH_HEADROOM = 1.25
INDEX_SHARDS = 256
BM25_K1 = 1.2
BM25_B = 0.75
BUILTIN_KIND_MODULES = ("cassi_library_field",)

_ROOT_PROGRAM = ({"op": "HALT"},)
_CATALOG = regions.EMPTY_KERNEL_CATALOG
_NAME = re.compile(r"[a-z0-9][a-z0-9_-]{0,62}\Z")


class FoundryError(ValueError):
    """A field kind, shelf, build, or request is invalid."""


# -- kinds ---------------------------------------------------------------------


@dataclass(frozen=True)
class Composition:
    """What a kind composed from its sources: named values and a compact summary."""

    values: dict[str, Any]
    summary: dict[str, Any]
    source_identity: str


@dataclass(frozen=True)
class FieldKind:
    """One kind of specialized field.

    ``normalize`` resolves a config (paths, defaults) and rejects invalid ones.
    ``source_identity`` hashes the current sources cheaply, so a shelf can tell
    whether a built field is still current.  ``compose`` reads the sources into
    named values.  ``reader`` wraps an opened field in the kind's own API.
    """

    name: str
    schema: str
    purpose: str
    normalize: Callable[[Mapping[str, Any]], dict[str, Any]]
    source_identity: Callable[[Mapping[str, Any]], str]
    compose: Callable[[Mapping[str, Any]], Composition]
    reader: Callable[["OpenedField"], Any]


_KINDS: dict[str, FieldKind] = {}


def register_kind(kind: FieldKind) -> FieldKind:
    """Make ``kind`` buildable by name."""

    if not _NAME.match(kind.name):
        raise FoundryError(f"invalid field kind name {kind.name!r}")
    current = _KINDS.get(kind.name)
    if current is not None and current.schema != kind.schema:
        raise FoundryError(f"field kind {kind.name} is already registered as {current.schema}")
    _KINDS[kind.name] = kind
    return kind


def kinds() -> dict[str, FieldKind]:
    """Every registered kind, including the built-in kind modules."""

    for module in BUILTIN_KIND_MODULES:
        importlib.import_module(module)
    return dict(sorted(_KINDS.items()))


def get_kind(name: str) -> FieldKind:
    known = kinds()
    if name not in known:
        raise FoundryError(f"unknown field kind {name!r}; known kinds: {', '.join(known) or 'none'}")
    return known[name]


# -- terms and index ---------------------------------------------------------

_WORD = re.compile(r"\w+")
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_STOPWORDS = frozenset(
    """a about an and are as at be been but by can could did do does for from had
    has have how if in into is it its may might not of on or our should so such
    than that the their them then there these they this those to was were what
    when where which while who why will with would you your""".split()
)
_EXPANSIONS: dict[str, tuple[str, ...]] = {}


def _keep(term: str) -> bool:
    if term in _STOPWORDS or len(term) > 64 or not term.strip("_"):
        return False
    return len(term) >= 2 or not term.isascii()


def _expand(raw: str) -> tuple[str, ...]:
    cached = _EXPANSIONS.get(raw)
    if cached is not None:
        return cached
    whole = raw.lower()
    found: list[str] = [whole] if _keep(whole) else []
    if "_" in raw or _CAMEL.search(raw):
        for chunk in raw.split("_"):
            for part in _CAMEL.split(chunk):
                lowered = part.lower()
                if lowered != whole and _keep(lowered):
                    found.append(lowered)
    value = tuple(found)
    if len(_EXPANSIONS) < 2_000_000:
        _EXPANSIONS[raw] = value
    return value


def terms(text: str) -> list[str]:
    """Search terms of ``text``: words, identifier parts, and single symbols."""

    found: list[str] = []
    for raw in _WORD.findall(text):
        found.extend(_expand(raw))
    return found


def term_shard(term: str) -> int:
    return zlib.crc32(term.encode("utf-8")) % INDEX_SHARDS


def _varint_encode(values: np.ndarray) -> tuple[bytes, np.ndarray]:
    values = values.astype(np.uint64, copy=False)
    lengths = np.ones(values.size, dtype=np.int64)
    for power in range(1, 10):
        lengths += values >= np.uint64(1 << (7 * power))
    starts = np.zeros(values.size, dtype=np.int64)
    np.cumsum(lengths[:-1], out=starts[1:])
    out = np.empty(int(lengths.sum()), dtype=np.uint8)
    for position in range(int(lengths.max()) if values.size else 0):
        selected = lengths > position
        chunk = ((values[selected] >> np.uint64(7 * position)) & np.uint64(0x7F)).astype(np.uint8)
        chunk[lengths[selected] > position + 1] |= 0x80
        out[starts[selected] + position] = chunk
    return out.tobytes(), lengths


def _varint_decode(raw: bytes) -> np.ndarray:
    data = np.frombuffer(raw, dtype=np.uint8)
    ends = np.flatnonzero(data < 0x80)
    starts = np.zeros(ends.size, dtype=np.int64)
    starts[1:] = ends[:-1] + 1
    lengths = ends - starts + 1
    values = np.zeros(ends.size, dtype=np.uint64)
    for position in range(int(lengths.max()) if ends.size else 0):
        selected = lengths > position
        chunk = (data[starts[selected] + position] & 0x7F).astype(np.uint64)
        values[selected] |= chunk << np.uint64(7 * position)
    return values


def _encode_postings(postings: Mapping[str, array]) -> dict[int, dict[str, str]]:
    """Delta-varint every term's (passage, count) list in one vectorised pass."""

    names = sorted(postings)
    counts = np.fromiter((len(postings[name]) // 2 for name in names), dtype=np.int64, count=len(names))
    pairs = np.frombuffer(
        b"".join(postings[name].tobytes() for name in names), dtype=np.uint32
    ).reshape(-1, 2).astype(np.uint64)
    firsts = np.zeros(len(names), dtype=np.int64)
    np.cumsum(counts[:-1], out=firsts[1:])
    deltas = pairs[:, 0].copy()
    deltas[1:] -= pairs[:-1, 0]
    deltas[firsts] = pairs[firsts, 0]
    interleaved = np.empty(2 * len(pairs), dtype=np.uint64)
    interleaved[0::2] = deltas
    interleaved[1::2] = pairs[:, 1]
    encoded, lengths = _varint_encode(interleaved)
    offsets = np.zeros(lengths.size + 1, dtype=np.int64)
    np.cumsum(lengths, out=offsets[1:])
    begin = offsets[2 * firsts]
    finish = offsets[2 * (firsts + counts)]
    shards: dict[int, dict[str, str]] = {shard: {} for shard in range(INDEX_SHARDS)}
    for index, name in enumerate(names):
        shards[term_shard(name)][name] = base64.b64encode(
            encoded[int(begin[index]):int(finish[index])]
        ).decode("ascii")
    return shards


def _decode_postings(value: str) -> tuple[np.ndarray, np.ndarray]:
    pairs = _varint_decode(base64.b64decode(value)).reshape(-1, 2)
    return np.cumsum(pairs[:, 0]).astype(np.int64), pairs[:, 1].astype(np.float64)


def _index_name(shard: int) -> str:
    return f"{INDEX_PREFIX}{shard:03d}"


class TermIndexBuilder:
    """Collects term counts for numbered units and writes a sharded BM25 index."""

    def __init__(self) -> None:
        self._postings: dict[str, array] = {}
        self._lengths: list[int] = []

    def add(self, counts: Mapping[str, int]) -> int:
        """Index one unit; units are numbered in the order they are added."""

        unit = len(self._lengths)
        for term, count in counts.items():
            row = self._postings.get(term)
            if row is None:
                row = self._postings[term] = array("I")
            row.append(unit)
            row.append(count)
        self._lengths.append(sum(counts.values()))
        return unit

    def write(self, values: dict[str, Any]) -> dict[str, Any]:
        """Add the index shards, unit lengths, and index header to ``values``."""

        lengths = np.asarray(self._lengths, dtype=np.int64)
        header = {
            "schema": TERMS_SCHEMA,
            "units": int(lengths.size),
            "terms": len(self._postings),
            "postings": sum(len(row) for row in self._postings.values()) // 2,
            "shards": INDEX_SHARDS,
            "average_length_milli": round(1000 * int(lengths.sum()) / max(1, int(lengths.size))),
            "bm25_milli": {"k1": round(1000 * BM25_K1), "b": round(1000 * BM25_B)},
        }
        for shard, shard_terms in _encode_postings(self._postings).items():
            values[_index_name(shard)] = {"terms": shard_terms}
        values[INDEX_LENGTHS_VALUE] = base64.b64encode(
            np.minimum(lengths, 0xFFFF).astype("<u2").tobytes()
        ).decode("ascii")
        values[INDEX_VALUE] = header
        self._postings.clear()
        self._lengths.clear()
        return header


class TermIndex:
    """BM25 ranking over the index a kind wrote with ``TermIndexBuilder``."""

    def __init__(self, field: "OpenedField") -> None:
        self.field = field
        loaded = field.values([INDEX_VALUE, INDEX_LENGTHS_VALUE])
        header = loaded[INDEX_VALUE]
        if not isinstance(header, Mapping) or header.get("schema") != TERMS_SCHEMA:
            raise FoundryError(f"{field.name} holds no term index")
        self.header = dict(header)
        self.units = int(header["units"])
        self.average_length = max(header["average_length_milli"] / 1000, 1e-9)
        self.k1 = header["bm25_milli"]["k1"] / 1000
        self.b = header["bm25_milli"]["b"] / 1000
        self.lengths = np.frombuffer(
            base64.b64decode(loaded[INDEX_LENGTHS_VALUE]), dtype="<u2"
        ).astype(np.float64)
        if self.lengths.size != self.units:
            raise FoundryError(f"{field.name} index lengths do not match its header")

    def rank(self, query: str, *, limit: int) -> tuple[list[str], list[tuple[int, float]]]:
        """The query terms the index knows and the ``limit`` best units with scores."""

        query_terms = sorted(set(terms(query)))
        loaded = self.field.values(sorted({_index_name(term_shard(term)) for term in query_terms}))
        scores = np.zeros(self.units, dtype=np.float64)
        matched: list[str] = []
        for term in query_terms:
            encoded = loaded[_index_name(term_shard(term))]["terms"].get(term)
            if encoded is None:
                continue
            matched.append(term)
            units, counts = _decode_postings(encoded)
            weight = math.log(1 + (self.units - units.size + 0.5) / (units.size + 0.5))
            norm = self.k1 * (1 - self.b + self.b * self.lengths[units] / self.average_length)
            scores[units] += weight * counts * (self.k1 + 1) / (counts + norm)
        count = min(max(0, int(limit)), int(np.count_nonzero(scores)))
        if not count:
            return matched, []
        top = np.argpartition(-scores, count - 1)[:count]
        ranked = top[np.argsort(-scores[top], kind="stable")]
        return matched, [(int(unit), round(float(scores[unit]), 4)) for unit in ranked]


# -- building ------------------------------------------------------------------


def _words(value: Any) -> int:
    return int(regions._json_words(value).size)


def _power_of_two(value: int) -> int:
    return 1 << max(0, math.ceil(math.log2(max(1, value))))


def field_profile(
    capacities: Mapping[str, int], *, mode_count: int | None = None
) -> regions.RegionalProfile:
    """The smallest power-of-two regional geometry that holds ``capacities`` with headroom."""

    entries = len(capacities) + 16
    directory_capacity = _power_of_two(2 * entries)
    registry_words = _power_of_two(2 * 40 * directory_capacity)
    queue_words = _power_of_two(2 * (sum(len(name) + 12 for name in capacities) // 4 + 1024))
    base = regions.RegionalProfile()
    fixed = (
        regions.HEADER_WORDS
        + regions.DIRECTORY_WORDS * directory_capacity
        + registry_words + queue_words + base.program_words + base.ledger_words
        + 4 * base.automaton_sites + 8 + 4 * base.default_value_words
    )
    needed = math.ceil((fixed + sum(capacities.values())) * GROWTH_HEADROOM / 9)
    if mode_count is None:
        mode_count = _power_of_two(needed)
    elif mode_count < needed:
        raise FoundryError(f"mode_count {mode_count} cannot hold this field (needs {needed})")
    return regions.RegionalProfile(
        mode_count=mode_count,
        directory_capacity=directory_capacity,
        max_registry_entries=directory_capacity,
        registry_words=registry_words,
        queue_words=queue_words,
    )


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def build_field(
    kind: str | FieldKind,
    config: Mapping[str, Any],
    destination: str | os.PathLike[str],
    *,
    name: str | None = None,
    purpose: str | None = None,
    objects: str | os.PathLike[str] | None = None,
    mode_count: int | None = None,
    resident_limit: int = DEFAULT_RESIDENT_PAGES,
) -> dict[str, Any]:
    """Compose ``config`` with ``kind`` and write it as one new paged field.

    Pages go to ``objects`` (default ``destination/objects``).  A shelf passes
    one object directory shared by every generation of a field, so pages that
    did not change between builds are stored once.
    """

    kind = get_kind(kind) if isinstance(kind, str) else kind
    config = kind.normalize(config)
    destination = Path(destination)
    if (destination / FIELD_DESCRIPTOR).exists():
        raise FoundryError(f"{destination} already holds a field")
    destination.mkdir(parents=True, exist_ok=True)
    objects = Path(objects) if objects is not None else destination / OBJECT_DIRECTORY
    clock = {"start": time.perf_counter()}
    composition = kind.compose(config)
    clock["composed"] = time.perf_counter()
    values = composition.values
    if MANIFEST_VALUE in values:
        raise FoundryError(f"kind {kind.name} wrote the reserved value {MANIFEST_VALUE!r}")
    manifest = {
        "schema": FOUNDRY_SCHEMA,
        "kind": kind.name,
        "kind_schema": kind.schema,
        "name": name or kind.name,
        "purpose": purpose or kind.purpose,
        "config": config,
        "source_identity": composition.source_identity,
        "summary": composition.summary,
    }
    values[MANIFEST_VALUE] = manifest
    used = {key: _words(value) for key, value in values.items()}
    capacities = {key: words + words // 4 + 16 for key, words in used.items()}
    largest_value_pages = max(used.values()) // regions.PERSISTENCE_PAGE_WORDS + 2
    if largest_value_pages > resident_limit:
        raise FoundryError(
            f"the largest value spans {largest_value_pages} pages; "
            f"resident_limit {resident_limit} cannot read it"
        )
    profile = field_profile(capacities, mode_count=mode_count)
    clock["encoded"] = time.perf_counter()
    field = regions.initial_field(
        profile, list(_ROOT_PROGRAM), values=values, value_capacities=capacities, catalog=_CATALOG
    )
    values.clear()
    clock["written"] = time.perf_counter()
    image = regions.PagedFieldImage.from_dense(field, profile, _CATALOG, resident_limit=resident_limit)
    del field
    clock["paged"] = time.perf_counter()
    image = image.with_backing(DiskObjectStore(objects))
    _atomic_json(destination / FIELD_DESCRIPTOR, image.descriptor())
    clock["persisted"] = time.perf_counter()
    residency = image.residency_report()
    stages = ("start", "composed", "encoded", "written", "paged", "persisted")
    receipt = {
        "schema": f"{FOUNDRY_SCHEMA}.build",
        "kind": kind.name,
        "kind_schema": kind.schema,
        "name": manifest["name"],
        "source_identity": composition.source_identity,
        "summary": composition.summary,
        "values": len(used),
        "profile": profile.as_dict(),
        "logical_bytes": profile.state_bytes,
        "value_words": sum(used.values()),
        "capacity_words": sum(capacities.values()),
        "fill": round(sum(used.values()) / profile.total_words, 4),
        "largest_value_pages": largest_value_pages,
        "page_count": residency["page_count"],
        "committed_pages": residency["committed_pages"],
        "physical_bytes": residency["unique_physical_bytes"],
        "root_sha256": image.root_sha256,
        "state_sha256": image.state_identity_sha256(),
        "seconds": {
            stage: round(clock[stage] - clock[previous], 3)
            for previous, stage in zip(stages, stages[1:])
        },
    }
    _atomic_json(destination / BUILD_RECEIPT, receipt)
    return receipt


# -- opening -------------------------------------------------------------------


class OpenedField:
    """A built field opened through its paged image; each value wakes only its own pages."""

    def __init__(
        self, path: Path, image: regions.PagedFieldImage, receipt: Mapping[str, Any]
    ) -> None:
        self.path = path
        self.image = image
        self.receipt = dict(receipt)
        manifest = self.values([MANIFEST_VALUE])[MANIFEST_VALUE]
        if not isinstance(manifest, Mapping) or manifest.get("schema") != FOUNDRY_SCHEMA:
            raise FoundryError(f"{path} does not hold a foundry field")
        self.manifest = dict(manifest)
        self.kind: str = manifest["kind"]
        self.name: str = manifest["name"]
        self.purpose: str = manifest["purpose"]
        self.config: dict[str, Any] = dict(manifest["config"])
        self.summary: dict[str, Any] = dict(manifest["summary"])
        self.source_identity: str = manifest["source_identity"]
        self.state_sha256: str = self.receipt.get("state_sha256") or image.state_identity_sha256()

    @classmethod
    def open(
        cls,
        path: str | os.PathLike[str],
        *,
        objects: str | os.PathLike[str] | None = None,
        resident_limit: int = DEFAULT_RESIDENT_PAGES,
    ) -> "OpenedField":
        path = Path(path)
        try:
            descriptor = json.loads((path / FIELD_DESCRIPTOR).read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise FoundryError(f"{path} holds no built field") from exc
        receipt_path = path / BUILD_RECEIPT
        receipt = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.exists() else {}
        image = regions.PagedFieldImage.from_descriptor(
            descriptor,
            DiskObjectStore(Path(objects) if objects is not None else path / OBJECT_DIRECTORY),
            _CATALOG,
            verify="control",
            resident_limit=resident_limit,
        )
        return cls(path, image, receipt)

    def values(self, names: Sequence[str]) -> dict[str, Any]:
        return regions.named_values_paged(self.image, list(names))

    def reader(self) -> Any:
        """The kind's own reader over this field."""

        return get_kind(self.kind).reader(self)

    def report(self) -> dict[str, Any]:
        residency = self.image.residency_report()
        return {
            "name": self.name,
            "kind": self.kind,
            "purpose": self.purpose,
            "summary": self.summary,
            "mode_count": self.image.profile.mode_count,
            "logical_bytes": self.image.profile.state_bytes,
            "page_count": residency["page_count"],
            "committed_pages": residency["committed_pages"],
            "physical_bytes": residency["unique_physical_bytes"],
            "resident_pages": residency["resident_pages"],
            "resident_limit": residency["resident_limit"],
            "resident_high_water_pages": residency["resident_high_water_pages"],
            "root_sha256": self.image.root_sha256,
            "state_sha256": self.state_sha256,
        }


def open_field(
    path: str | os.PathLike[str],
    *,
    objects: str | os.PathLike[str] | None = None,
    resident_limit: int = DEFAULT_RESIDENT_PAGES,
) -> OpenedField:
    return OpenedField.open(path, objects=objects, resident_limit=resident_limit)


# -- the shelf -----------------------------------------------------------------


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class _ShelfLock:
    """One writer per shelf: an exclusive lock file, reclaimed once abandoned."""

    def __init__(self, home: Path) -> None:
        self.path = home / LOCK_FILE

    def __enter__(self) -> "_ShelfLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + LOCK_WAIT_SECONDS
        while True:
            try:
                handle = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                try:
                    age = time.time() - self.path.stat().st_mtime
                except FileNotFoundError:
                    continue
                if age > LOCK_STALE_SECONDS:
                    self.path.unlink(missing_ok=True)
                    continue
                if time.monotonic() > deadline:
                    raise FoundryError(f"shelf {self.path.parent} is held by another writer")
                time.sleep(0.2)
                continue
            os.write(handle, f"{os.getpid()} {_now()}\n".encode("ascii"))
            os.close(handle)
            return self

    def __exit__(self, *exc_info: Any) -> None:
        self.path.unlink(missing_ok=True)


class FieldShelf:
    """Named specialized fields, each kept current with its sources.

    ``shelf.json`` in ``home`` records every field's kind, config, purpose, and
    current generation.  Each field lives in ``home/<name>/`` as numbered
    generation directories over one shared object directory.  Readers open the
    current generation without a lock; writers take the shelf lock.
    """

    def __init__(self, home: str | os.PathLike[str] = DEFAULT_SHELF_HOME) -> None:
        self.home = Path(home).resolve()

    def _load(self) -> dict[str, Any]:
        path = self.home / SHELF_FILE
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {"schema": SHELF_SCHEMA, "fields": {}}
        if not isinstance(data, dict) or data.get("schema") != SHELF_SCHEMA:
            raise FoundryError(f"{path} is not a field shelf")
        return data

    def _save(self, data: Mapping[str, Any]) -> None:
        self.home.mkdir(parents=True, exist_ok=True)
        _atomic_json(self.home / SHELF_FILE, data)

    def _entry(self, name: str, data: Mapping[str, Any] | None = None) -> dict[str, Any]:
        fields = (self._load() if data is None else data)["fields"]
        if name not in fields:
            raise FoundryError(
                f"no field named {name!r} on the shelf; shelved: {', '.join(sorted(fields)) or 'none'}"
            )
        return fields[name]

    def _generation_path(self, name: str, generation: int) -> Path:
        return self.home / name / f"{GENERATION_PREFIX}{generation:06d}"

    def names(self) -> list[str]:
        return sorted(self._load()["fields"])

    def catalog(self) -> list[dict[str, Any]]:
        """What the shelf holds: each field's kind, purpose, generation, and summary."""

        return [
            {
                "name": entry["name"],
                "kind": entry["kind"],
                "purpose": entry["purpose"],
                "generation": entry["generation"],
                "built_at": entry.get("built_at"),
                "summary": entry.get("summary") or {},
            }
            for _, entry in sorted(self._load()["fields"].items())
        ]

    def add(self, spec: Mapping[str, Any], *, replace: bool = False) -> dict[str, Any]:
        """Shelve a field: ``name``, ``kind``, ``config``, optional ``purpose`` and ``resident_limit``.

        Adding records the specification; ``refresh`` builds it.  Replacing a
        shelved field keeps its generations and marks it for rebuilding.
        """

        unknown = set(spec) - {"name", "kind", "config", "purpose", "resident_limit"}
        if unknown:
            raise FoundryError(f"unknown field spec keys: {', '.join(sorted(unknown))}")
        name = str(spec.get("name") or "")
        if not _NAME.match(name):
            raise FoundryError(f"field names are lowercase letters, digits, - and _; got {name!r}")
        kind = get_kind(str(spec.get("kind") or ""))
        config = kind.normalize(spec.get("config") or {})
        resident_limit = int(spec.get("resident_limit") or DEFAULT_RESIDENT_PAGES)
        if resident_limit < 1:
            raise FoundryError("resident_limit must be positive")
        with _ShelfLock(self.home):
            data = self._load()
            current = data["fields"].get(name)
            if current is not None and not replace:
                raise FoundryError(f"{name} is already on the shelf")
            entry = {
                "name": name,
                "kind": kind.name,
                "purpose": str(spec.get("purpose") or kind.purpose),
                "config": config,
                "resident_limit": resident_limit,
                "added_at": _now(),
                "generation": int(current["generation"]) if current else 0,
                "source_identity": None,
                "state_sha256": current.get("state_sha256") if current else None,
                "built_at": current.get("built_at") if current else None,
                "summary": current.get("summary") if current else {},
            }
            data["fields"][name] = entry
            self._save(data)
        return entry

    def status(self, name: str) -> dict[str, Any]:
        """``fresh`` when the built field matches its sources, else ``stale`` or ``missing``."""

        entry = self._entry(name)
        current = get_kind(entry["kind"]).source_identity(entry["config"])
        generation = int(entry["generation"])
        built = generation > 0 and (self._generation_path(name, generation) / FIELD_DESCRIPTOR).exists()
        state = "missing" if not built else "fresh" if entry["source_identity"] == current else "stale"
        return {
            "name": name,
            "kind": entry["kind"],
            "state": state,
            "generation": generation,
            "built_at": entry.get("built_at"),
            "source_identity": current,
        }

    def refresh(
        self, name: str, *, force: bool = False, keep: int = DEFAULT_KEEP_GENERATIONS
    ) -> dict[str, Any]:
        """Bring one field up to date, building a new generation only when its sources changed.

        Raises ``FoundryError`` when the sources cannot be read; the last built
        generation stays openable.
        """

        with _ShelfLock(self.home):
            status = self.status(name)
            if status["state"] == "fresh" and not force:
                return {"name": name, "state": "fresh", "rebuilt": False, "generation": status["generation"]}
            data = self._load()
            entry = self._entry(name, data)
            generation = int(entry["generation"]) + 1
            target = self._generation_path(name, generation)
            staging = target.with_name(f".{target.name}.tmp-{os.getpid()}")
            shutil.rmtree(staging, ignore_errors=True)
            try:
                receipt = build_field(
                    entry["kind"],
                    entry["config"],
                    staging,
                    name=name,
                    purpose=entry["purpose"],
                    objects=self.home / name / OBJECT_DIRECTORY,
                    resident_limit=int(entry["resident_limit"]),
                )
                shutil.rmtree(target, ignore_errors=True)
                os.replace(staging, target)
            finally:
                shutil.rmtree(staging, ignore_errors=True)
            entry.update(
                generation=generation,
                source_identity=receipt["source_identity"],
                state_sha256=receipt["state_sha256"],
                built_at=_now(),
                summary=receipt["summary"],
                logical_bytes=receipt["logical_bytes"],
                physical_bytes=receipt["physical_bytes"],
            )
            self._save(data)
            pruned = self._prune(name, entry, keep)
        return {
            "name": name,
            "state": "fresh",
            "rebuilt": True,
            "previous_state": status["state"],
            "generation": generation,
            "receipt": receipt,
            "pruned": pruned,
        }

    def build(self, name: str) -> dict[str, Any]:
        """Build a new generation now, whether or not the sources changed."""

        return self.refresh(name, force=True)

    def open_field(self, name: str, *, resident_limit: int | None = None) -> OpenedField:
        entry = self._entry(name)
        generation = int(entry["generation"])
        if generation < 1:
            raise FoundryError(f"{name} has not been built yet; refresh it first")
        return OpenedField.open(
            self._generation_path(name, generation),
            objects=self.home / name / OBJECT_DIRECTORY,
            resident_limit=resident_limit or int(entry["resident_limit"]),
        )

    def open(self, name: str, *, resident_limit: int | None = None) -> Any:
        """The kind's reader over the current generation of ``name``."""

        return self.open_field(name, resident_limit=resident_limit).reader()

    def prune(self, name: str, *, keep: int = DEFAULT_KEEP_GENERATIONS) -> dict[str, Any]:
        """Retire all but the newest ``keep`` generations and the pages only they used."""

        with _ShelfLock(self.home):
            return self._prune(name, self._entry(name), keep)

    def _prune(self, name: str, entry: Mapping[str, Any], keep: int) -> dict[str, Any]:
        if keep < 1:
            raise FoundryError("keep at least one generation")
        folder = self.home / name
        generations = sorted(
            int(path.name[len(GENERATION_PREFIX):])
            for path in folder.glob(f"{GENERATION_PREFIX}*")
            if path.is_dir() and path.name[len(GENERATION_PREFIX):].isdigit()
        )
        kept = [number for number in generations if number <= int(entry["generation"])][-keep:]
        removed = [number for number in generations if number not in kept]
        for number in removed:
            shutil.rmtree(self._generation_path(name, number))
        for staging in folder.glob(f".{GENERATION_PREFIX}*.tmp-*"):
            shutil.rmtree(staging, ignore_errors=True)
        store = DiskObjectStore(folder / OBJECT_DIRECTORY)
        referenced: set[str] = set()
        for number in kept:
            path = self._generation_path(name, number)
            descriptor = json.loads((path / FIELD_DESCRIPTOR).read_text(encoding="utf-8"))
            image = regions.PagedFieldImage.from_descriptor(descriptor, store, _CATALOG, verify="control")
            referenced.update(leaf.object_sha256 for leaf in image.directory.leaves if leaf is not None)
        removed_objects = 0
        freed_bytes = 0
        for item in (folder / OBJECT_DIRECTORY).iterdir():
            if item.is_file() and DiskObjectStore._valid_key(item.name) and item.name not in referenced:
                freed_bytes += item.stat().st_size
                item.unlink()
                removed_objects += 1
        return {
            "kept_generations": kept,
            "removed_generations": removed,
            "removed_objects": removed_objects,
            "freed_bytes": freed_bytes,
        }


# -- command line --------------------------------------------------------------


def _setting(text: str) -> tuple[str, Any]:
    key, separator, raw = text.partition("=")
    if not separator or not key:
        raise FoundryError(f"--set expects KEY=VALUE, got {text!r}")
    try:
        return key, json.loads(raw)
    except json.JSONDecodeError:
        return key, raw


def _reader_method(shelf: FieldShelf, name: str, method: str) -> Callable[..., Any]:
    reader = shelf.open(name)
    function = getattr(reader, method, None)
    if not callable(function):
        raise FoundryError(f"{name} ({shelf._entry(name)['kind']}) has no {method}")
    return function


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--home", default=str(DEFAULT_SHELF_HOME), help="shelf directory")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("kinds", help="list the field kinds the foundry can build")
    commands.add_parser("list", help="catalog the shelf with each field's status")
    add = commands.add_parser("add", help="shelve a new specialized field")
    add.add_argument("name")
    add.add_argument("kind")
    add.add_argument("--set", action="append", default=[], metavar="KEY=VALUE", help="config entry (JSON or text)")
    add.add_argument("--purpose")
    add.add_argument("--resident-limit", type=int, default=DEFAULT_RESIDENT_PAGES)
    add.add_argument("--replace", action="store_true", help="replace an existing specification")
    add.add_argument("--build", action="store_true", help="build the field right away")
    for command, help_text in (
        ("build", "build a new generation now"),
        ("refresh", "rebuild the fields whose sources changed (all when no names)"),
        ("status", "compare fields with their sources (all when no names)"),
    ):
        commands.add_parser(command, help=help_text).add_argument("names", nargs="*")
    commands.add_parser("report", help="describe one built field").add_argument("name")
    prune = commands.add_parser("prune", help="retire old generations and their unshared pages")
    prune.add_argument("name")
    prune.add_argument("--keep", type=int, default=DEFAULT_KEEP_GENERATIONS)
    search = commands.add_parser("search", help="rank a field's passages for a query")
    search.add_argument("name")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=8)
    read = commands.add_parser("read", help="print one held source exactly")
    read.add_argument("name")
    read.add_argument("path")
    commands.add_parser("verify", help="check a field's held sources against their origin").add_argument("name")
    args = parser.parse_args(argv)

    shelf = FieldShelf(args.home)
    try:
        if args.command == "kinds":
            result: Any = [
                {"name": kind.name, "schema": kind.schema, "purpose": kind.purpose}
                for kind in kinds().values()
            ]
        elif args.command == "list":
            result = [{**row, "state": shelf.status(row["name"])["state"]} for row in shelf.catalog()]
        elif args.command == "add":
            spec = {
                "name": args.name,
                "kind": args.kind,
                "config": dict(_setting(item) for item in args.set),
                "purpose": args.purpose,
                "resident_limit": args.resident_limit,
            }
            result = shelf.add(spec, replace=args.replace)
            if args.build:
                result = shelf.refresh(args.name)
        elif args.command in {"build", "refresh"}:
            action = shelf.build if args.command == "build" else shelf.refresh
            result = [action(name) for name in args.names or shelf.names()]
        elif args.command == "status":
            result = [shelf.status(name) for name in args.names or shelf.names()]
        elif args.command == "report":
            result = shelf.open_field(args.name).report()
        elif args.command == "prune":
            result = shelf.prune(args.name, keep=args.keep)
        elif args.command == "read":
            sys.stdout.buffer.write(_reader_method(shelf, args.name, "read")(args.path))
            return 0
        elif args.command == "search":
            result = _reader_method(shelf, args.name, "search")(args.query, limit=args.limit)
        else:
            result = _reader_method(shelf, args.name, "verify")()
    except FoundryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    # Run through the importable module so kinds register into one registry.
    import cassi_field_foundry

    raise SystemExit(cassi_field_foundry._main())
