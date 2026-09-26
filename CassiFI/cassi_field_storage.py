"""Lazy content-addressed storage helpers for paged Cassi field state."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from collections.abc import Iterator, Mapping, Sequence
from typing import Any


class StorageError(ValueError):
    """Invalid storage object or storage layout."""


class DiskObjectStore(Mapping[str, bytes]):
    """Flat content-addressed object store with lazy verified reads.

    The directory contains only ``root/<sha256>`` files.  Values are not read
    during iteration, membership, or construction; verification happens when
    a caller actually requests an object.  ``cache_bytes`` is an optional
    bounded compressed-object cache and is never required for correctness.
    """

    def __init__(self, root: str | os.PathLike[str], keys: Sequence[str] | None = None, *, cache_bytes: int = 0) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._keys = None if keys is None else frozenset(str(key) for key in keys)
        if isinstance(cache_bytes, bool) or not isinstance(cache_bytes, int) or cache_bytes < 0:
            raise StorageError("cache_bytes must be a nonnegative integer")
        self.cache_bytes = cache_bytes
        self._cache: dict[str, bytes] = {}
        self._cache_order: list[str] = []
        self._cache_used = 0

    @staticmethod
    def _valid_key(key: object) -> bool:
        return isinstance(key, str) and len(key) == 64 and all(char in "0123456789abcdef" for char in key)

    def _path(self, key: str) -> Path:
        if not self._valid_key(key):
            raise KeyError(key)
        if self._keys is not None and key not in self._keys:
            raise KeyError(key)
        return self.root / key

    def __iter__(self) -> Iterator[str]:
        if self._keys is not None:
            yield from sorted(self._keys)
            return
        try:
            entries = self.root.iterdir()
        except FileNotFoundError:
            return
        for item in entries:
            if item.is_file() and self._valid_key(item.name):
                yield item.name

    def __len__(self) -> int:
        return sum(1 for _ in self)

    def __contains__(self, key: object) -> bool:
        if not self._valid_key(key):
            return False
        try:
            return self._path(key).is_file()
        except KeyError:
            return False

    def __getitem__(self, key: str) -> bytes:
        # Inline path creation and validation to avoid extra function call overhead
        root = self.root
        keys = self._keys
        if keys is not None and key not in keys:
            raise KeyError(key)

        # Check cache first
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        # Construct path directly
        path = root / key

        try:
            raw = path.read_bytes()
        except FileNotFoundError:
            raise KeyError(key)

        # Verify SHA-256 hash
        computed_hash = hashlib.sha256(raw).hexdigest()
        if computed_hash != key:
            raise StorageError(f"object {key} failed SHA-256 verification")

        # Update cache if enabled and size allows
        if self.cache_bytes > 0 and len(raw) <= self.cache_bytes:
            old = self._cache.pop(key, None)
            if old is not None:
                self._cache_used -= len(old)
                try:
                    self._cache_order.remove(key)
                except ValueError:
                    pass
            self._cache[key] = raw
            self._cache_order.append(key)
            self._cache_used += len(raw)
            while self._cache_used > self.cache_bytes and self._cache_order:
                victim = self._cache_order.pop(0)
                value = self._cache.pop(victim, None)
                if value is not None:
                    self._cache_used -= len(value)

        return raw

    def _cache_put(self, key: str, raw: bytes) -> None:
        if self.cache_bytes <= 0 or len(raw) > self.cache_bytes:
            return
        old = self._cache.pop(key, None)
        if old is not None:
            self._cache_used -= len(old)
            try:
                self._cache_order.remove(key)
            except ValueError:
                pass
        self._cache[key] = raw
        self._cache_order.append(key)
        self._cache_used += len(raw)
        while self._cache_used > self.cache_bytes and self._cache_order:
            victim = self._cache_order.pop(0)
            value = self._cache.pop(victim, None)
            if value is not None:
                self._cache_used -= len(value)

    def put(self, raw: bytes, digest: str | None = None) -> str:
        if not isinstance(raw, bytes):
            raise StorageError("object payload must be bytes")
        key = hashlib.sha256(raw).hexdigest()
        if digest is not None and str(digest) != key:
            raise StorageError("object digest does not match payload")
        path = self._path(key)
        if not path.exists():
            # Pre-calculate PID and ID to avoid repeated lookups in the string construction
            pid = os.getpid()
            raw_id = id(raw)
            # Construct a unique temp filename in the same directory to ensure atomic rename works
            # Use a simple counter-like suffix derived from time to minimize collision risk without heavy locks
            # while keeping string operations minimal.
            import time
            suffix = f".{key}.tmp-{pid}-{raw_id}-{int(time.time() * 1000000) % 1000000}"
            tmp = path.with_name(suffix)
            try:
                with tmp.open("wb") as handle:
                    handle.write(raw)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(tmp, path)
            finally:
                if tmp.exists():
                    tmp.unlink()
        return key

    def byte_size(self, key: str) -> int:
        try:
            return int(self._path(key).stat().st_size)
        except FileNotFoundError as exc:
            raise KeyError(key) from exc


class ObjectOverlay(Mapping[str, bytes]):
    """Lazy first-wins merge of object mappings without loading values.

    Sources keep the shape they were given, so building an overlay is O(1) and
    nothing is copied.  Depth is tracked rather than flattened: past
    ``_COLLAPSE_DEPTH`` links the chain folds into a key-to-owner index, which
    answers containment and lookup in O(1) without reading a single object
    value.  A paged image commits one overlay and one authorized subset per
    step, so without that fold every lookup walks the whole commit history.
    """

    _COLLAPSE_DEPTH = 8

    def __init__(self, *sources: Mapping[str, bytes]) -> None:
        kept = tuple(source for source in sources if source is not None)
        depth = 0
        for source in kept:
            depth = max(depth, _node_depth(source) + 1)
        if depth > self._COLLAPSE_DEPTH:
            kept = (_collapse(kept),)
            depth = 1
        self.sources = kept
        self.depth = depth

    def __iter__(self) -> Iterator[str]:
        seen: set[str] = set()
        for mapping, filters in _chain_leaves(self):
            for key in mapping:
                if filters and not all(key in narrow for narrow in filters):
                    continue
                if key not in seen:
                    seen.add(key)
                    yield key

    def __len__(self) -> int:
        return sum(1 for _ in self)

    def __contains__(self, key: object) -> bool:
        return _chain_contains(self, key)

    def __getitem__(self, key: str) -> bytes:
        return _chain_get(self, key)


class ObjectSubset(Mapping[str, bytes]):
    """Lazy authorized subset of an object mapping."""

    def __init__(self, source: Mapping[str, bytes], keys: Sequence[str] | set[str]) -> None:
        if _node_depth(source) > ObjectOverlay._COLLAPSE_DEPTH:
            source = _collapse((source,))
        self.source = source
        self._keys = frozenset(str(key) for key in keys)
        self.depth = _node_depth(source) + 1

    def __iter__(self) -> Iterator[str]:
        for key in self._keys:
            if _chain_contains(self.source, key):
                yield key

    def __len__(self) -> int:
        return sum(1 for _ in self)

    def __contains__(self, key: object) -> bool:
        return key in self._keys and _chain_contains(self.source, key)

    def __getitem__(self, key: str) -> bytes:
        if key not in self._keys:
            raise KeyError(key)
        return _chain_get(self.source, key)


class _ObjectIndex(Mapping[str, bytes]):
    """Key-to-owner index over a folded chain: one hop per lookup.

    Values stay where they live (memory or disk); only the mapping that owns
    each key is recorded, so folding a long history costs no object reads.
    """

    __slots__ = ("_owners", "depth")

    def __init__(self) -> None:
        self._owners: dict[str, Mapping[str, bytes]] = {}
        self.depth = 0

    def add(
        self,
        mapping: Mapping[str, bytes],
        filters: tuple[frozenset[str], ...] = (),
    ) -> None:
        owners = self._owners
        narrow = _narrow(filters)
        if isinstance(mapping, _ObjectIndex):
            # Splice one level so repeated folds never stack hops.
            for key, owner in mapping._owners.items():
                if narrow is not None and key not in narrow:
                    continue
                if key not in owners:
                    owners[key] = owner
            return
        for key in mapping:
            if narrow is not None and key not in narrow:
                continue
            if key not in owners:
                owners[key] = mapping

    def __iter__(self) -> Iterator[str]:
        return iter(self._owners)

    def __len__(self) -> int:
        return len(self._owners)

    def __contains__(self, key: object) -> bool:
        return key in self._owners

    def __getitem__(self, key: str) -> bytes:
        return self._owners[key][key]


def _node_depth(node: Mapping[str, bytes]) -> int:
    return getattr(node, "depth", 0)


def _narrow(filters: tuple[frozenset[str], ...]) -> frozenset[str] | None:
    """Materialise an accumulated filter stack, if any filters apply."""

    if not filters:
        return None
    if len(filters) == 1:
        return filters[0]
    narrow = filters[0]
    for extra in filters[1:]:
        if extra is not narrow:
            narrow = narrow & extra
    return narrow


def _collapse(sources: tuple[Mapping[str, bytes], ...]) -> _ObjectIndex:
    """Fold a chain into a key-to-owner index, preserving first-wins order."""

    index = _ObjectIndex()
    for entry in sources:
        for leaf, filters in _chain_leaves(entry):
            index.add(leaf, filters)
    return index


def _chain_leaves(
    source: Mapping[str, bytes],
) -> Iterator[tuple[Mapping[str, bytes], tuple[frozenset[str], ...]]]:
    """Yield a nested overlay/subset chain's leaves in first-wins order.

    Each leaf carries the key filters of the subsets above it as a stack, so one
    walk answers containment, lookup and iteration without recursing once per
    link and without intersecting key sets it never consults.  A node already
    visited under a comparable filter stack is skipped: comparing by constraint
    sets is safe in both directions (the wider visit covered the narrower one),
    and it terminates a chain that references itself.
    """

    stack: list[tuple[Mapping[str, bytes], tuple[frozenset[str], ...]]] = [(source, ())]
    visited: dict[int, list[tuple[frozenset[str], ...]]] = {}
    while stack:
        node, filters = stack.pop()
        seen = visited.setdefault(id(node), [])
        if any(
            all(any(f is kept for kept in record) for f in filters)
            or all(any(kept is f for f in filters) for kept in record)
            for record in seen
        ):
            continue
        seen.append(filters)
        if isinstance(node, ObjectOverlay):
            for child in reversed(node.sources):
                stack.append((child, filters))
        elif isinstance(node, ObjectSubset):
            stack.append((node.source, filters + (node._keys,)))
        else:
            yield node, filters


def _chain_contains(source: Mapping[str, bytes], key: object) -> bool:
    for mapping, filters in _chain_leaves(source):
        for narrow in filters:
            if key not in narrow:
                break
        else:
            if key in mapping:
                return True
    return False


def _chain_get(source: Mapping[str, bytes], key: str) -> bytes:
    for mapping, filters in _chain_leaves(source):
        for narrow in filters:
            if key not in narrow:
                break
        else:
            try:
                return mapping[key]
            except KeyError:
                continue
    raise KeyError(key)


def object_bytes(mapping: Mapping[str, bytes]) -> int:
    """Count mapped object bytes, using exposed metadata where available."""
    total = 0
    byte_size = getattr(mapping, "byte_size", None)
    for key in mapping:
        total += int(byte_size(key)) if callable(byte_size) else len(mapping[key])
    return total


__all__ = ["DiskObjectStore", "ObjectOverlay", "ObjectSubset", "StorageError", "object_bytes"]
