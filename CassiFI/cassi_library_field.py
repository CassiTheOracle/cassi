"""Library fields: a whole source repository held in one paged CassiFI field.

This module is the ``library`` kind of the field foundry.  Every tracked file of
a git corpus becomes a named value holding its exact staged blob, beside the
passage table and the foundry term index that make the corpus searchable.
Opening a shelved library wakes only its control pages; a search wakes the index
shards of its terms, and reading a passage wakes the pages of that one file.
Passage spans are byte offsets into the exact file bytes and every file carries
its sha256, so a quoted passage can be cited and checked against its source.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import subprocess
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import cassi_field_foundry as foundry

LIBRARY_SCHEMA = "cassifi.library-field.v2"
DEFAULT_PATTERNS = ("*.md", "*.py")
PASSAGE_SHARD_SIZE = 1024
MAX_PASSAGE_CHARS = 4000
MERGE_BELOW_CHARS = 160

LIBRARY_VALUE = "library"
FILE_PREFIX = "file:"
PASSAGE_PREFIX = "passages:"


class LibraryFieldError(foundry.FoundryError):
    """The library corpus, field, or request is invalid."""


# -- corpus ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SourceFile:
    path: str
    blob_sha1: str
    data: bytes


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _git(root: Path, *args: str, stdin: bytes | None = None, check: bool = True) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(root), *args], input=stdin, capture_output=True, check=False
    )
    if completed.returncode != 0:
        if not check:
            return b""
        message = completed.stderr.decode("utf-8", "replace").strip()
        raise LibraryFieldError(f"git {args[0]} failed: {message}")
    return completed.stdout


def tracked_files(
    root: str | os.PathLike[str], patterns: Sequence[str] = DEFAULT_PATTERNS
) -> list[tuple[str, str]]:
    """The staged ``(path, blob_sha1)`` of every tracked regular file matching ``patterns``."""

    entries: list[tuple[str, str]] = []
    for record in _git(Path(root), "ls-files", "-s", "-z", "--", *patterns).split(b"\0"):
        if not record:
            continue
        meta, raw_path = record.split(b"\t", 1)
        mode, blob, stage = meta.decode("ascii").split()
        if mode in {"100644", "100755"} and stage == "0":
            entries.append((raw_path.decode("utf-8"), blob))
    if not entries:
        raise LibraryFieldError("no tracked files match the library patterns")
    return entries


def read_blobs(
    root: str | os.PathLike[str], entries: Sequence[tuple[str, str]]
) -> list[SourceFile]:
    """The exact bytes of each staged blob, verified against its object id."""

    request = "".join(f"{blob}\n" for _, blob in entries).encode("ascii")
    batch = _git(Path(root), "cat-file", "--batch", stdin=request)
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


def collect_sources(
    root: str | os.PathLike[str], patterns: Sequence[str] = DEFAULT_PATTERNS
) -> list[SourceFile]:
    """Read the staged git blob of every tracked regular file matching ``patterns``."""

    return read_blobs(root, tracked_files(root, patterns))


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


def _byte_spans(text: str, spans: Sequence[tuple[int, int, str]]) -> list[tuple[int, int, str]]:
    """Character spans of ``text`` as byte spans of its UTF-8 bytes."""

    if text.isascii():
        return list(spans)
    converted: list[tuple[int, int, str]] = []
    characters = 0
    position = 0
    for start, end, title in spans:
        position += len(text[characters:start].encode("utf-8"))
        begin = position
        position += len(text[start:end].encode("utf-8"))
        characters = end
        converted.append((begin, position, title))
    return converted


def _passage_name(shard: int) -> str:
    return f"{PASSAGE_PREFIX}{shard:04d}"


# -- the library kind ----------------------------------------------------------


def normalize(config: Mapping[str, Any]) -> dict[str, Any]:
    """A library config: the repository ``root`` and the file ``patterns`` it holds."""

    unknown = set(config) - {"root", "patterns"}
    if unknown:
        raise LibraryFieldError(f"unknown library config keys: {', '.join(sorted(unknown))}")
    if not config.get("root"):
        raise LibraryFieldError("a library needs a root directory")
    root = Path(str(config["root"])).expanduser().resolve()
    if not root.is_dir():
        raise LibraryFieldError(f"library root {root} is not a directory")
    patterns = config.get("patterns") or DEFAULT_PATTERNS
    if isinstance(patterns, str):
        patterns = patterns.split(",")
    patterns = [str(item).strip() for item in patterns if str(item).strip()]
    if not patterns:
        raise LibraryFieldError("a library needs at least one file pattern")
    return {"root": str(root), "patterns": patterns}


def _identity(patterns: Sequence[str], entries: Sequence[tuple[str, str]]) -> str:
    digest = hashlib.sha256(
        json.dumps({"schema": LIBRARY_SCHEMA, "patterns": list(patterns)}, sort_keys=True).encode("utf-8")
    )
    for path, blob in entries:
        digest.update(f"\n{blob} {path}".encode("utf-8"))
    return digest.hexdigest()


def source_identity(config: Mapping[str, Any]) -> str:
    """The staged blobs the library would hold now, hashed without reading them."""

    return _identity(config["patterns"], tracked_files(config["root"], config["patterns"]))


def compose(config: Mapping[str, Any]) -> foundry.Composition:
    """Every matching file, its passages, and their term index as named values."""

    root = Path(config["root"])
    patterns = list(config["patterns"])
    entries = tracked_files(root, patterns)
    head = _git(root, "rev-parse", "--verify", "-q", "HEAD^{commit}", check=False).decode("ascii").strip() or None
    index = foundry.TermIndexBuilder()
    values: dict[str, Any] = {}
    files: list[list[Any]] = []
    passages: list[list[Any]] = []
    for file_index, source in enumerate(read_blobs(root, entries)):
        try:
            text = source.data.decode("utf-8")
        except UnicodeDecodeError:
            values[FILE_PREFIX + source.path] = {"base64": base64.b64encode(source.data).decode("ascii")}
            encoding = "base64"
            spans = [(0, len(source.data), "")] if source.data else []
            segments = [source.data.decode("utf-8", "replace")]
        else:
            values[FILE_PREFIX + source.path] = text
            encoding = "utf-8"
            character_spans = passage_spans(source.path, text)
            spans = _byte_spans(text, character_spans)
            segments = [text[start:end] for start, end, _ in character_spans]
        files.append([
            source.path,
            source.blob_sha1,
            len(source.data),
            len(passages),
            len(spans),
            encoding,
            hashlib.sha256(source.data).hexdigest(),
        ])
        path_terms = foundry.terms(source.path)
        for (start, end, title), segment in zip(spans, segments):
            passages.append([file_index, start, end, title])
            counts = Counter(foundry.terms(segment))
            counts.update(foundry.terms(title))
            counts.update(path_terms)
            index.add(counts)
    index_header = index.write(values)
    for first in range(0, len(passages), PASSAGE_SHARD_SIZE):
        values[_passage_name(first // PASSAGE_SHARD_SIZE)] = {
            "passages": passages[first:first + PASSAGE_SHARD_SIZE]
        }
    values[LIBRARY_VALUE] = {
        "schema": LIBRARY_SCHEMA,
        "source": {"name": root.name, "patterns": patterns, "git_head": head},
        "files": files,
        "passage_count": len(passages),
        "passage_shard_size": PASSAGE_SHARD_SIZE,
    }
    summary = {
        "files": len(files),
        "source_bytes": sum(row[2] for row in files),
        "passages": len(passages),
        "terms": index_header["terms"],
        "git_head": head,
    }
    return foundry.Composition(values=values, summary=summary, source_identity=_identity(patterns, entries))


# -- reading -------------------------------------------------------------------


class LibraryField:
    """An opened library: exact files, byte-exact passages, and ranked search."""

    def __init__(self, field: foundry.OpenedField) -> None:
        self.field = field
        self.name = field.name
        self.state_sha256 = field.state_sha256
        library = field.values([LIBRARY_VALUE])[LIBRARY_VALUE]
        if not isinstance(library, Mapping) or library.get("schema") != LIBRARY_SCHEMA:
            raise LibraryFieldError(f"{field.path} does not hold a {LIBRARY_SCHEMA} catalog")
        self.library = library
        self.files = [list(row) for row in library["files"]]
        self._file_index = {row[0]: index for index, row in enumerate(self.files)}
        self.passage_count = int(library["passage_count"])
        self.index = foundry.TermIndex(field)
        if self.index.units != self.passage_count:
            raise LibraryFieldError("the term index does not match the passage table")

    def file(self, path: str) -> dict[str, Any]:
        """The identity of one held file."""

        if path not in self._file_index:
            raise LibraryFieldError(f"{path} is not in library {self.name}")
        path, blob_sha1, size, _, passage_count, encoding, sha256 = self.files[self._file_index[path]]
        return {
            "path": path,
            "blob_sha1": blob_sha1,
            "sha256": sha256,
            "size": size,
            "encoding": encoding,
            "passages": passage_count,
        }

    def read(self, path: str) -> bytes:
        """The exact bytes of one library file."""

        return self.read_many([path])[path]

    def read_many(self, paths: Sequence[str]) -> dict[str, bytes]:
        """The exact bytes of several library files through one paged view."""

        for path in paths:
            if path not in self._file_index:
                raise LibraryFieldError(f"{path} is not in library {self.name}")
        loaded = self.field.values([FILE_PREFIX + path for path in paths])
        held: dict[str, bytes] = {}
        for path in paths:
            value = loaded[FILE_PREFIX + path]
            held[path] = (
                value.encode("utf-8") if isinstance(value, str) else base64.b64decode(value["base64"])
            )
        return held

    def passages(self, passage_ids: Sequence[int]) -> dict[int, list[Any]]:
        """Passage rows ``[file_index, byte_start, byte_end, title]`` by passage id."""

        shards: dict[int, list[int]] = {}
        for passage_id in passage_ids:
            if not 0 <= passage_id < self.passage_count:
                raise LibraryFieldError(f"passage {passage_id} is outside library {self.name}")
            shards.setdefault(passage_id // PASSAGE_SHARD_SIZE, []).append(passage_id)
        names = {shard: _passage_name(shard) for shard in shards}
        loaded = self.field.values(list(names.values()))
        return {
            passage_id: loaded[names[shard]]["passages"][passage_id % PASSAGE_SHARD_SIZE]
            for shard, members in shards.items()
            for passage_id in members
        }

    def search(self, query: str, *, limit: int = 8, with_text: bool = True) -> dict[str, Any]:
        """Rank passages for ``query``; each hit names its file, byte span, and file sha256."""

        before = dict(self.field.image.counters)
        started = time.perf_counter()
        matched, ranked = self.index.rank(query, limit=limit)
        rows = self.passages([unit for unit, _ in ranked])
        held = (
            self.read_many(sorted({self.files[rows[unit][0]][0] for unit, _ in ranked}))
            if with_text and ranked
            else {}
        )
        hits: list[dict[str, Any]] = []
        for unit, score in ranked:
            file_index, start, end, title = rows[unit]
            path = self.files[file_index][0]
            hit = {
                "passage": unit,
                "path": path,
                "title": title,
                "start": start,
                "end": end,
                "score": score,
                "sha256": self.files[file_index][6],
            }
            if with_text:
                hit["text"] = held[path][start:end].decode("utf-8", "replace")
            hits.append(hit)
        after = self.field.image.counters
        return {
            "query": query,
            "terms": matched,
            "hits": hits,
            "seconds": round(time.perf_counter() - started, 4),
            "pages_woken": after["page_misses"] - before.get("page_misses", 0),
            "words_decoded": after["decoded_words"] - before.get("decoded_words", 0),
        }

    def verify(self, root: str | os.PathLike[str] | None = None) -> dict[str, Any]:
        """Check every held file against its blob id and sha256, then against the repository."""

        started = time.perf_counter()
        exact = 0
        mismatched: list[str] = []
        for first in range(0, len(self.files), 64):
            rows = self.files[first:first + 64]
            held = self.read_many([row[0] for row in rows])
            for path, blob_sha1, size, _, _, _, sha256 in rows:
                data = held[path]
                if (
                    len(data) == size
                    and git_blob_sha1(data) == blob_sha1
                    and hashlib.sha256(data).hexdigest() == sha256
                ):
                    exact += 1
                else:
                    mismatched.append(path)
        current = dict(tracked_files(root or self.field.config["root"], self.field.config["patterns"]))
        held_blobs = {row[0]: row[1] for row in self.files}
        return {
            "files": len(self.files),
            "exact": exact,
            "mismatched": mismatched,
            "repository": {
                "unchanged": sum(1 for path, blob in held_blobs.items() if current.get(path) == blob),
                "changed": sorted(
                    path for path, blob in held_blobs.items() if path in current and current[path] != blob
                ),
                "removed": sorted(set(held_blobs) - set(current)),
                "added": sorted(set(current) - set(held_blobs)),
            },
            "seconds": round(time.perf_counter() - started, 3),
        }

    def report(self) -> dict[str, Any]:
        return {
            **self.field.report(),
            "files": len(self.files),
            "passages": self.passage_count,
            "terms": self.index.header["terms"],
        }


LIBRARY_KIND = foundry.register_kind(
    foundry.FieldKind(
        name="library",
        schema=LIBRARY_SCHEMA,
        purpose=(
            "exact source library: every tracked file of a git corpus, "
            "split into citable passages with ranked search"
        ),
        normalize=normalize,
        source_identity=source_identity,
        compose=compose,
        reader=LibraryField,
    )
)
