"""A whole source library held in one paged CassiFI regional field.

Every tracked file of a git corpus becomes a named value of one regional image,
stored as its exact git blob beside the passage table and the sharded term index
that make the corpus searchable.  The image persists as content-addressed pages
in a ``DiskObjectStore``.  Opening the library wakes only its control pages; a
search wakes the index shards of its terms, and reading a passage wakes the
pages of that one file.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
import zlib
from array import array
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

import cassi_field_regions as regions
from cassi_field_storage import DiskObjectStore

LIBRARY_SCHEMA = "cassifi.library-field.v1"
TERMS_SCHEMA = "cassifi.library-terms.v1"
FIELD_DESCRIPTOR = "field.json"
BUILD_RECEIPT = "build.json"
OBJECT_DIRECTORY = "objects"
DEFAULT_PATTERNS = ("*.md", "*.py")
DEFAULT_RESIDENT_PAGES = 256
INDEX_SHARDS = 256
PASSAGE_SHARD_SIZE = 1024
MAX_PASSAGE_CHARS = 4000
MERGE_BELOW_CHARS = 160
GROWTH_HEADROOM = 1.25
BM25_K1 = 1.2
BM25_B = 0.75

LIBRARY_VALUE = "library"
LENGTHS_VALUE = "passage-lengths"
FILE_PREFIX = "file:"
INDEX_PREFIX = "index:"
PASSAGE_PREFIX = "passages:"

_ROOT_PROGRAM = ({"op": "HALT"},)
_CATALOG = regions.EMPTY_KERNEL_CATALOG


class LibraryFieldError(ValueError):
    """The library corpus, field image, or request is invalid."""


# -- corpus ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SourceFile:
    path: str
    blob_sha1: str
    data: bytes


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _git(root: Path, *args: str, stdin: bytes | None = None) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(root), *args], input=stdin, capture_output=True, check=False
    )
    if completed.returncode != 0:
        message = completed.stderr.decode("utf-8", "replace").strip()
        raise LibraryFieldError(f"git {args[0]} failed: {message}")
    return completed.stdout


def collect_sources(
    root: str | os.PathLike[str], patterns: Sequence[str] = DEFAULT_PATTERNS
) -> list[SourceFile]:
    """Read the staged git blob of every tracked regular file matching ``patterns``."""

    root = Path(root)
    entries: list[tuple[str, str]] = []
    for record in _git(root, "ls-files", "-s", "-z", "--", *patterns).split(b"\0"):
        if not record:
            continue
        meta, raw_path = record.split(b"\t", 1)
        mode, blob, stage = meta.decode("ascii").split()
        if mode in {"100644", "100755"} and stage == "0":
            entries.append((raw_path.decode("utf-8"), blob))
    if not entries:
        raise LibraryFieldError("no tracked files match the library patterns")
    request = "".join(f"{blob}\n" for _, blob in entries).encode("ascii")
    batch = _git(root, "cat-file", "--batch", stdin=request)
    sources: list[SourceFile] = []
    offset = 0
    for path, blob in entries:
        end = batch.index(b"\n", offset)
        header = batch[offset:end].decode("ascii").split()
        if len(header) != 3 or header[0] != blob or header[1] != "blob":
            raise LibraryFieldError(f"git returned an unexpected object for {path}")
        size = int(header[2])
        data = batch[end + 1:end + 1 + size]
        offset = end + 2 + size
        if git_blob_sha1(data) != blob:
            raise LibraryFieldError(f"git blob for {path} failed verification")
        sources.append(SourceFile(path, blob, data))
    return sources


# -- passages ----------------------------------------------------------------

_MD_HEADING = re.compile(r"(#{1,6})[ \t]+(.*?)[ \t#]*$")
_PY_DEFINITION = re.compile(r"(?:async[ \t]+def|def|class)[ \t]+([A-Za-z_]\w*)")


def _markdown_cuts(text: str) -> list[tuple[int, str]]:
    cuts: list[tuple[int, str]] = [(0, "")]
    headings: list[tuple[int, str]] = []
    fence: str | None = None
    offset = 0
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            marker = stripped[:3]
            if fence is None:
                fence = marker
            elif marker == fence:
                fence = None
        elif fence is None:
            match = _MD_HEADING.match(line.rstrip("\r\n"))
            if match:
                level = len(match.group(1))
                while headings and headings[-1][0] >= level:
                    headings.pop()
                headings.append((level, match.group(2).strip()))
                title = " / ".join(item for _, item in headings if item)
                if cuts[-1][0] == offset:
                    cuts[-1] = (offset, title)
                else:
                    cuts.append((offset, title))
        offset += len(line)
    return cuts


def _python_cuts(text: str) -> list[tuple[int, str]]:
    cuts: list[tuple[int, str]] = [(0, "module")]
    decorator: int | None = None
    offset = 0
    for line in text.splitlines(keepends=True):
        if line.startswith("@"):
            if decorator is None:
                decorator = offset
        else:
            match = _PY_DEFINITION.match(line)
            if match:
                start = offset if decorator is None else decorator
                kind = "class" if line.startswith("class") else "def"
                title = f"{kind} {match.group(1)}"
                if cuts[-1][0] == start:
                    cuts[-1] = (start, title)
                else:
                    cuts.append((start, title))
                decorator = None
            elif line[:1] not in ("", " ", "\t", "\r", "\n", "#", ")", "]", "}"):
                decorator = None
        offset += len(line)
    return cuts


def _split_long(text: str, start: int, end: int) -> list[tuple[int, int]]:
    pieces: list[tuple[int, int]] = []
    cursor = start
    while end - cursor > MAX_PASSAGE_CHARS:
        floor = cursor + MAX_PASSAGE_CHARS // 4
        limit = cursor + MAX_PASSAGE_CHARS
        cut = text.rfind("\n\n", floor, limit)
        if cut >= 0:
            cut += 2
        else:
            cut = text.rfind("\n", floor, limit)
            cut = limit if cut < 0 else cut + 1
        pieces.append((cursor, cut))
        cursor = cut
    pieces.append((cursor, end))
    return pieces


def passage_spans(path: str, text: str) -> list[tuple[int, int, str]]:
    """Partition ``text`` exactly into titled passages of bounded length."""

    suffix = Path(path).suffix.lower()
    if suffix == ".md":
        cuts = _markdown_cuts(text)
    elif suffix == ".py":
        cuts = _python_cuts(text)
    else:
        cuts = [(0, "")]
    bounds = [offset for offset, _ in cuts] + [len(text)]
    sections = [
        [bounds[index], bounds[index + 1], title]
        for index, (_, title) in enumerate(cuts)
        if bounds[index + 1] > bounds[index]
    ]
    merged: list[list[Any]] = []
    pending: int | None = None
    for index, (start, end, title) in enumerate(sections):
        if pending is not None:
            start, pending = pending, None
        if end - start < MERGE_BELOW_CHARS and index < len(sections) - 1:
            pending = start
            continue
        merged.append([start, end, title])
    spans: list[tuple[int, int, str]] = []
    for start, end, title in merged:
        for part, (piece_start, piece_end) in enumerate(_split_long(text, start, end)):
            spans.append((piece_start, piece_end, title if part == 0 else f"{title} (part {part + 1})"))
    return spans


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


def _passage_name(shard: int) -> str:
    return f"{PASSAGE_PREFIX}{shard:04d}"


# -- field image -------------------------------------------------------------


def _words(value: Any) -> int:
    return int(regions._json_words(value).size)


def _power_of_two(value: int) -> int:
    return 1 << max(0, math.ceil(math.log2(max(1, value))))


def library_profile(
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
        raise LibraryFieldError(f"mode_count {mode_count} cannot hold the library (needs {needed})")
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


def build_library(
    root: str | os.PathLike[str],
    destination: str | os.PathLike[str],
    *,
    patterns: Sequence[str] = DEFAULT_PATTERNS,
    mode_count: int | None = None,
    resident_limit: int = DEFAULT_RESIDENT_PAGES,
) -> dict[str, Any]:
    """Write the tracked corpus of ``root`` into one new paged library field."""

    root = Path(root).resolve()
    destination = Path(destination)
    if (destination / FIELD_DESCRIPTOR).exists():
        raise LibraryFieldError(f"{destination} already holds a library field")
    destination.mkdir(parents=True, exist_ok=True)
    clock = {"start": time.perf_counter()}

    sources = collect_sources(root, patterns)
    clock["collected"] = time.perf_counter()

    values: dict[str, Any] = {}
    files: list[list[Any]] = []
    passages: list[list[Any]] = []
    postings: dict[str, array] = {}
    lengths: list[int] = []
    for file_index, source in enumerate(sources):
        try:
            text = source.data.decode("utf-8")
            encoding = "utf-8"
            values[FILE_PREFIX + source.path] = text
        except UnicodeDecodeError:
            text = source.data.decode("utf-8", "replace")
            encoding = "base64"
            values[FILE_PREFIX + source.path] = {"base64": base64.b64encode(source.data).decode("ascii")}
        path_terms = terms(source.path)
        spans = passage_spans(source.path, text)
        files.append([source.path, source.blob_sha1, len(source.data), len(passages), len(spans), encoding])
        for start, end, title in spans:
            passage_id = len(passages)
            passages.append([file_index, start, end, title])
            counts = Counter(terms(text[start:end]))
            counts.update(terms(title))
            counts.update(path_terms)
            lengths.append(sum(counts.values()))
            for term, count in counts.items():
                row = postings.get(term)
                if row is None:
                    row = postings[term] = array("I")
                row.append(passage_id)
                row.append(count)
    clock["indexed"] = time.perf_counter()

    posting_count = sum(len(row) for row in postings.values()) // 2
    for shard, shard_terms in _encode_postings(postings).items():
        values[_index_name(shard)] = {"terms": shard_terms}
    for shard in range(0, len(passages), PASSAGE_SHARD_SIZE):
        values[_passage_name(shard // PASSAGE_SHARD_SIZE)] = {
            "passages": passages[shard:shard + PASSAGE_SHARD_SIZE]
        }
    values[LENGTHS_VALUE] = base64.b64encode(
        np.minimum(np.asarray(lengths, dtype=np.int64), 0xFFFF).astype("<u2").tobytes()
    ).decode("ascii")
    head = _git(root, "rev-parse", "HEAD").decode("ascii").strip()
    values[LIBRARY_VALUE] = {
        "schema": LIBRARY_SCHEMA,
        "terms_schema": TERMS_SCHEMA,
        "source": {"name": root.name, "patterns": list(patterns), "git_head": head},
        "files": files,
        "passage_count": len(passages),
        "passage_shard_size": PASSAGE_SHARD_SIZE,
        "average_length_milli": round(1000 * sum(lengths) / max(1, len(lengths))),
        "index_shards": INDEX_SHARDS,
        "term_count": len(postings),
        "posting_count": posting_count,
        "bm25_milli": {"k1": round(1000 * BM25_K1), "b": round(1000 * BM25_B)},
    }
    term_count = len(postings)
    postings.clear()

    used = {name: _words(value) for name, value in values.items()}
    capacities = {
        name: words + words // (4 if name.startswith(FILE_PREFIX) else 2) + 16
        for name, words in used.items()
    }
    largest_value_pages = max(used.values()) // regions.PERSISTENCE_PAGE_WORDS + 2
    if largest_value_pages > resident_limit:
        raise LibraryFieldError(
            f"the largest library value spans {largest_value_pages} pages; "
            f"resident_limit {resident_limit} cannot read it"
        )
    profile = library_profile(capacities, mode_count=mode_count)
    clock["encoded"] = time.perf_counter()

    field = regions.initial_field(
        profile, list(_ROOT_PROGRAM), values=values, value_capacities=capacities, catalog=_CATALOG
    )
    values.clear()
    clock["written"] = time.perf_counter()
    image = regions.PagedFieldImage.from_dense(
        field, profile, _CATALOG, resident_limit=resident_limit
    )
    del field
    clock["paged"] = time.perf_counter()
    image = image.with_backing(DiskObjectStore(destination / OBJECT_DIRECTORY))
    _atomic_json(destination / FIELD_DESCRIPTOR, image.descriptor())
    clock["persisted"] = time.perf_counter()

    residency = image.residency_report()
    receipt = {
        "schema": f"{LIBRARY_SCHEMA}.build",
        "source": {"root": str(root), "patterns": list(patterns), "git_head": head},
        "files": len(files),
        "source_bytes": sum(row[2] for row in files),
        "passages": len(passages),
        "terms": term_count,
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
            for previous, stage in zip(
                ("start", "collected", "indexed", "encoded", "written", "paged"),
                ("collected", "indexed", "encoded", "written", "paged", "persisted"),
            )
        },
    }
    _atomic_json(destination / BUILD_RECEIPT, receipt)
    return receipt


# -- reading -----------------------------------------------------------------


class LibraryField:
    """An opened library field: exact files, passages, and ranked search."""

    def __init__(self, destination: Path, image: regions.PagedFieldImage) -> None:
        self.destination = destination
        self.image = image
        self.library = self._values([LIBRARY_VALUE])[LIBRARY_VALUE]
        if not isinstance(self.library, Mapping) or self.library.get("schema") != LIBRARY_SCHEMA:
            raise LibraryFieldError("field does not hold a library catalog")
        self.files = [list(row) for row in self.library["files"]]
        self._file_index = {row[0]: index for index, row in enumerate(self.files)}
        self.passage_count = int(self.library["passage_count"])
        self.average_length = self.library["average_length_milli"] / 1000
        self.lengths = np.frombuffer(
            base64.b64decode(self._values([LENGTHS_VALUE])[LENGTHS_VALUE]), dtype="<u2"
        ).astype(np.float64)
        if self.lengths.size != self.passage_count:
            raise LibraryFieldError("passage lengths do not match the catalog")

    @classmethod
    def open(
        cls, destination: str | os.PathLike[str], *, resident_limit: int = DEFAULT_RESIDENT_PAGES
    ) -> "LibraryField":
        destination = Path(destination)
        descriptor = json.loads((destination / FIELD_DESCRIPTOR).read_text(encoding="utf-8"))
        image = regions.PagedFieldImage.from_descriptor(
            descriptor,
            DiskObjectStore(destination / OBJECT_DIRECTORY),
            _CATALOG,
            verify="control",
            resident_limit=resident_limit,
        )
        return cls(destination, image)

    def _values(self, names: Sequence[str]) -> dict[str, Any]:
        return regions.named_values_paged(self.image, list(names))

    def read(self, path: str) -> bytes:
        """The exact bytes of one library file."""

        return self.read_many([path])[path]

    def read_many(self, paths: Sequence[str]) -> dict[str, bytes]:
        """The exact bytes of several library files through one paged view."""

        for path in paths:
            if path not in self._file_index:
                raise LibraryFieldError(f"{path} is not in the library")
        loaded = self._values([FILE_PREFIX + path for path in paths])
        held: dict[str, bytes] = {}
        for path in paths:
            value = loaded[FILE_PREFIX + path]
            held[path] = (
                value.encode("utf-8") if isinstance(value, str) else base64.b64decode(value["base64"])
            )
        return held

    def passages(self, passage_ids: Sequence[int]) -> dict[int, list[Any]]:
        shards: dict[int, list[int]] = {}
        for passage_id in passage_ids:
            if not 0 <= passage_id < self.passage_count:
                raise LibraryFieldError(f"passage {passage_id} is outside the library")
            shards.setdefault(passage_id // PASSAGE_SHARD_SIZE, []).append(passage_id)
        names = {shard: _passage_name(shard) for shard in shards}
        loaded = self._values(list(names.values()))
        return {
            passage_id: loaded[names[shard]]["passages"][passage_id % PASSAGE_SHARD_SIZE]
            for shard, members in shards.items()
            for passage_id in members
        }

    def search(
        self, query: str, *, limit: int = 8, with_text: bool = True
    ) -> dict[str, Any]:
        """Rank passages for ``query`` by BM25 over the field-held term index."""

        before = dict(self.image.counters)
        started = time.perf_counter()
        query_terms = sorted(set(terms(query)))
        shards = sorted({term_shard(term) for term in query_terms})
        loaded = self._values([_index_name(shard) for shard in shards])
        scores = np.zeros(self.passage_count, dtype=np.float64)
        matched: list[str] = []
        k1, b = BM25_K1, BM25_B
        for term in query_terms:
            encoded = loaded[_index_name(term_shard(term))]["terms"].get(term)
            if encoded is None:
                continue
            matched.append(term)
            passage_ids, counts = _decode_postings(encoded)
            frequency = passage_ids.size
            weight = math.log(1 + (self.passage_count - frequency + 0.5) / (frequency + 0.5))
            norm = k1 * (1 - b + b * self.lengths[passage_ids] / self.average_length)
            scores[passage_ids] += weight * counts * (k1 + 1) / (counts + norm)
        hits: list[dict[str, Any]] = []
        if matched:
            count = min(limit, int(np.count_nonzero(scores)))
            top = np.argpartition(-scores, count - 1)[:count] if count else np.array([], dtype=np.int64)
            ranked = [int(item) for item in top[np.argsort(-scores[top], kind="stable")]]
            rows = self.passages(ranked)
            texts: dict[str, str] = {}
            for passage_id in ranked:
                file_index, start, end, title = rows[passage_id]
                path = self.files[file_index][0]
                hit = {
                    "passage": passage_id,
                    "path": path,
                    "title": title,
                    "start": start,
                    "end": end,
                    "score": round(float(scores[passage_id]), 4),
                }
                if with_text:
                    if path not in texts:
                        texts[path] = self.read(path).decode("utf-8", "replace")
                    hit["text"] = texts[path][start:end]
                hits.append(hit)
        after = self.image.counters
        return {
            "query": query,
            "terms": matched,
            "hits": hits,
            "seconds": round(time.perf_counter() - started, 4),
            "pages_woken": after["page_misses"] - before.get("page_misses", 0),
            "words_decoded": after["decoded_words"] - before.get("decoded_words", 0),
        }

    def verify(self, root: str | os.PathLike[str] | None = None) -> dict[str, Any]:
        """Re-read every file from the field and check it against its git blob."""

        started = time.perf_counter()
        exact = 0
        mismatched: list[str] = []
        for batch in range(0, len(self.files), 64):
            rows = self.files[batch:batch + 64]
            held = self.read_many([row[0] for row in rows])
            for path, blob_sha1, *_ in rows:
                if git_blob_sha1(held[path]) == blob_sha1:
                    exact += 1
                else:
                    mismatched.append(path)
        report: dict[str, Any] = {
            "files": len(self.files),
            "exact": exact,
            "mismatched": mismatched,
            "seconds": round(time.perf_counter() - started, 3),
        }
        if root is not None:
            current = {
                path: blob
                for path, blob in (
                    (source.path, source.blob_sha1)
                    for source in collect_sources(root, self.library["source"]["patterns"])
                )
            }
            held = {row[0]: row[1] for row in self.files}
            report["repository"] = {
                "unchanged": sum(1 for path, blob in held.items() if current.get(path) == blob),
                "changed": sorted(path for path, blob in held.items() if path in current and current[path] != blob),
                "removed": sorted(set(held) - set(current)),
                "added": sorted(set(current) - set(held)),
            }
        return report

    def report(self) -> dict[str, Any]:
        residency = self.image.residency_report()
        return {
            "files": len(self.files),
            "passages": self.passage_count,
            "terms": self.library["term_count"],
            "mode_count": self.image.profile.mode_count,
            "logical_bytes": self.image.profile.state_bytes,
            "page_count": residency["page_count"],
            "committed_pages": residency["committed_pages"],
            "physical_bytes": residency["unique_physical_bytes"],
            "resident_pages": residency["resident_pages"],
            "resident_limit": residency["resident_limit"],
            "resident_high_water_pages": residency["resident_high_water_pages"],
            "root_sha256": self.image.root_sha256,
        }


# -- command line --------------------------------------------------------------


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="write a repository corpus into a new library field")
    build.add_argument("root")
    build.add_argument("destination")
    build.add_argument("--pattern", action="append", dest="patterns")
    build.add_argument("--mode-count", type=int)
    build.add_argument("--resident-limit", type=int, default=DEFAULT_RESIDENT_PAGES)
    search = commands.add_parser("search", help="rank library passages for a query")
    search.add_argument("destination")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=8)
    read = commands.add_parser("read", help="print one library file exactly")
    read.add_argument("destination")
    read.add_argument("path")
    verify = commands.add_parser("verify", help="check every held file against git")
    verify.add_argument("destination")
    verify.add_argument("--root")
    report = commands.add_parser("report", help="describe the library field")
    report.add_argument("destination")
    args = parser.parse_args(argv)

    if args.command == "build":
        result: Any = build_library(
            args.root,
            args.destination,
            patterns=tuple(args.patterns or DEFAULT_PATTERNS),
            mode_count=args.mode_count,
            resident_limit=args.resident_limit,
        )
    elif args.command == "read":
        sys.stdout.buffer.write(LibraryField.open(args.destination).read(args.path))
        return 0
    else:
        library = LibraryField.open(args.destination)
        if args.command == "search":
            result = library.search(args.query, limit=args.limit)
        elif args.command == "verify":
            result = library.verify(args.root)
        else:
            result = library.report()
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
