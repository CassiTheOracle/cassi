"""Immutable, digest-bound backing for resident model working state.

The model executor owns numerical execution; this module only persists the
field-selected activation/cache arrays that a continuation chooses to retain.
Array bytes are content addressed and manifests are deterministic, so a
snapshot descriptor remains usable after a process restart or branch fork.
"""
from __future__ import annotations

from collections import OrderedDict
import hashlib
import json
import math
import mmap
import os
from pathlib import Path
import tempfile
import threading
import uuid
import weakref
from types import MappingProxyType
from typing import Any, Iterable, Mapping

import numpy as np


SNAPSHOT_DESCRIPTOR_SCHEMA = "cassifi.resident-model-snapshot-descriptor.v1"
SNAPSHOT_MANIFEST_SCHEMA = "cassifi.resident-model-snapshot-manifest.v1"
SNAPSHOT_MANIFEST_CHUNKED_SCHEMA = "cassifi.resident-model-snapshot-manifest.v2"

# These are corruption/DoS guards, not model-size limits.  They can be
# tightened for an installation by passing the corresponding constructor
# arguments; normal working-state arrays are generally much smaller.
_DEFAULT_MAX_ARRAY_BYTES = 1 << 40
_DEFAULT_MAX_TOTAL_BYTES = 1 << 42
_MAX_MANIFEST_BYTES = 16 << 20
_HASH_CHUNK_BYTES = 8 << 20
_DEFAULT_ARRAY_CHUNK_BYTES = 1 << 20
_DEFAULT_CHUNK_THRESHOLD_BYTES = 2 << 20
_MAX_ARRAY_CHUNK_BYTES = 64 << 20
_MATERIALIZE_COPY_BYTES = 1 << 20
_CHUNKED_ARRAY_STORAGE = "chunked.v1"
# Identities of backings flushed by this process. Eviction only costs one
# redundant flush later, so the bound never weakens durability.
_KNOWN_DURABLE_LIMIT = 1 << 15


class SnapshotStoreError(ValueError):
    """Base error for invalid descriptors, state, or backing data."""


class SnapshotDescriptorError(SnapshotStoreError):
    """The caller supplied a descriptor that is not a valid snapshot ref."""


class SnapshotCorruptionError(SnapshotStoreError):
    """A published manifest/blob/chunk is missing, truncated, or has changed bytes."""


def _canonical_json_bytes(value: Any) -> bytes:
    """Encode JSON without clocks or incidental whitespace.

    A round trip through ``json.loads`` deliberately rejects custom objects,
    numpy scalars, NaN, and Infinity instead of silently inventing a wire
    representation for owner metadata.
    """

    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        json.loads(encoded.decode("utf-8"))
    except (TypeError, ValueError, UnicodeError) as exc:
        raise SnapshotStoreError("snapshot metadata is not canonical JSON") from exc
    return encoded


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path, *, expected_size: int | None = None) -> str:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise SnapshotCorruptionError(f"snapshot backing is unavailable: {path.name}") from exc
    if expected_size is not None and size != expected_size:
        raise SnapshotCorruptionError(
            f"snapshot backing size mismatch for {path.name}: expected {expected_size}, got {size}"
        )
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(_HASH_CHUNK_BYTES)
                if not chunk:
                    break
                digest.update(chunk)
    except OSError as exc:
        raise SnapshotCorruptionError(f"snapshot backing cannot be read: {path.name}") from exc
    return digest.hexdigest()


def _fsync_directory(path: Path) -> None:
    """Best-effort directory durability (directory handles are unavailable on Windows)."""

    try:
        descriptor = os.open(str(path), os.O_RDONLY)
    except (OSError, ValueError):
        return
    try:
        try:
            os.fsync(descriptor)
        except OSError:
            pass
    finally:
        os.close(descriptor)


def _fsync_file(path: Path) -> None:
    """Flush one published file; Windows ``FlushFileBuffers`` needs write access."""

    descriptor = os.open(str(path), os.O_RDWR | getattr(os, "O_BINARY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _install_new(temporary: Path, target: Path) -> bool:
    """Create ``target`` from ``temporary`` unless another writer already did.

    Content-addressed files are never clobbered on the normal path, so a
    concurrent unflushed writer cannot replace a file already made durable.
    """

    try:
        if os.name == "nt":
            os.rename(temporary, target)
        else:
            os.link(temporary, target)
    except FileExistsError:
        return False
    return True


def _atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _iter_array_byte_chunks(array: np.ndarray, chunk_bytes: int):
    """Yield C-order byte views with at most one bounded iterator buffer."""

    if array.flags.c_contiguous:
        view = memoryview(array).cast("B")
        for offset in range(0, int(array.nbytes), chunk_bytes):
            yield view[offset : offset + chunk_bytes]
        return
    elements_per_buffer = max(1, chunk_bytes // max(1, array.dtype.itemsize))
    iterator = np.nditer(
        array,
        flags=["external_loop", "buffered"],
        op_flags=["readonly"],
        order="C",
        buffersize=elements_per_buffer,
    )
    for values in iterator:
        view = memoryview(values).cast("B")
        for offset in range(0, len(view), chunk_bytes):
            yield view[offset : offset + chunk_bytes]


def _chunk_path(chunks: Path, digest: str) -> Path:
    return chunks / f"{digest}.bin"


def _array_chunk_descriptor(chunks: tuple[tuple[str, int], ...]) -> list[dict[str, Any]]:
    return [
        {"blob": f"chunks/{digest}.bin", "nbytes": nbytes, "sha256": digest}
        for digest, nbytes in chunks
    ]


def _manifest_array_entry(
    array: np.ndarray,
    digest: str,
    nbytes: int,
    *,
    chunk_bytes: int | None = None,
    chunks: tuple[tuple[str, int], ...] | None = None,
) -> dict[str, Any]:
    entry = {
        **_dtype_entry(np.dtype(array.dtype)),
        "nbytes": nbytes,
        "sha256": digest,
        "shape": [int(extent) for extent in array.shape],
    }
    if chunks is None:
        entry["blob"] = f"blobs/{digest}.bin"
    else:
        entry.update(
            {
                "chunk_bytes": chunk_bytes,
                "chunks": _array_chunk_descriptor(chunks),
                "storage": _CHUNKED_ARRAY_STORAGE,
            }
        )
    return entry


def _shape(value: Any) -> tuple[int, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise SnapshotDescriptorError("snapshot array shape must be a list")
    result: list[int] = []
    for extent in value:
        if isinstance(extent, bool) or not isinstance(extent, int) or extent < 0:
            raise SnapshotDescriptorError("snapshot array shape has an invalid extent")
        result.append(extent)
    return tuple(result)


def _dtype_from_entry(item: Mapping[str, Any], name: str) -> np.dtype[Any]:
    try:
        descriptor = item.get("dtype_descr")
        if descriptor is not None:
            if not isinstance(descriptor, list):
                raise TypeError("dtype_descr must be a list")
            fields: list[tuple[Any, ...]] = []
            for field in descriptor:
                if not isinstance(field, list) or len(field) not in (2, 3):
                    raise TypeError("dtype_descr field is invalid")
                fields.append(tuple(field))
            dtype = np.dtype(fields)
        else:
            dtype = np.dtype(item.get("dtype"))
    except (TypeError, ValueError) as exc:
        raise SnapshotCorruptionError(f"array {name} dtype is invalid") from exc
    if dtype.hasobject or dtype.metadata is not None:
        raise SnapshotCorruptionError(f"array {name} has an unsupported dtype")
    return dtype


def _dtype_entry(dtype: np.dtype[Any]) -> dict[str, Any]:
    if dtype.metadata is not None:
        raise SnapshotStoreError("dtypes with metadata cannot be persisted")
    entry: dict[str, Any] = {"dtype": dtype.str}
    if dtype.fields is not None:
        entry["dtype_descr"] = [list(field) for field in dtype.descr]
    return entry


def _digest_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise SnapshotDescriptorError(f"{label} must be a SHA-256 digest")
    try:
        int(value, 16)
    except ValueError as exc:
        raise SnapshotDescriptorError(f"{label} must be a SHA-256 digest") from exc
    return value.lower()


class SnapshotStore:
    """Content-addressed immutable storage for model working-state snapshots.

    Small arrays retain the original raw-blob format. Large arrays use
    versioned fixed-size chunks; manifests reference immutable chunks and the
    process-local read mapping is reconstructed through bounded temporary I/O.
    A manifest and ``CURRENT`` are published only after all data is present.
    A durable save flushes every backing it references before its manifest;
    an unflushed save leaves ``CURRENT`` unchanged until :meth:`make_durable`
    seals the one descriptor a durable owner record will reference. Loaded
    arrays are read-only; callers must copy to update them.
    """

    def __init__(
        self,
        state_directory: str | os.PathLike[str],
        *,
        max_array_bytes: int = _DEFAULT_MAX_ARRAY_BYTES,
        max_total_bytes: int = _DEFAULT_MAX_TOTAL_BYTES,
        chunk_bytes: int = _DEFAULT_ARRAY_CHUNK_BYTES,
        chunk_threshold_bytes: int = _DEFAULT_CHUNK_THRESHOLD_BYTES,
    ) -> None:
        if isinstance(max_array_bytes, bool) or not isinstance(max_array_bytes, int) or max_array_bytes <= 0:
            raise ValueError("max_array_bytes must be a positive integer")
        if isinstance(max_total_bytes, bool) or not isinstance(max_total_bytes, int) or max_total_bytes <= 0:
            raise ValueError("max_total_bytes must be a positive integer")
        if isinstance(chunk_bytes, bool) or not isinstance(chunk_bytes, int) or not 0 < chunk_bytes <= _MAX_ARRAY_CHUNK_BYTES:
            raise ValueError("chunk_bytes must be a positive integer within the chunk bound")
        if (
            isinstance(chunk_threshold_bytes, bool)
            or not isinstance(chunk_threshold_bytes, int)
            or chunk_threshold_bytes < 0
        ):
            raise ValueError("chunk_threshold_bytes must be a nonnegative integer")
        root = Path(state_directory)
        try:
            root.mkdir(parents=True, exist_ok=True)
            self.root = root.resolve()
            self.state_directory = self.root
            self.blobs = self.root / "blobs"
            self.chunks = self.root / "chunks"
            self.snapshots = self.root / "snapshots"
            self.current = self.root / "CURRENT"
            self.blobs.mkdir(parents=True, exist_ok=True)
            self.chunks.mkdir(parents=True, exist_ok=True)
            self.snapshots.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise SnapshotStoreError("state directory cannot be created") from exc
        self.max_array_bytes = max_array_bytes
        self.max_total_bytes = max_total_bytes
        self.chunk_bytes = chunk_bytes
        self.chunk_threshold_bytes = chunk_threshold_bytes
        self._verified_blobs: dict[tuple[str, int, int, int], str] = {}
        self._immutable_arrays: dict[
            int,
            tuple[
                weakref.ReferenceType[np.ndarray],
                tuple[int, int, str, tuple[int, ...], tuple[int, ...]],
                str,
            ],
        ] = {}
        self._immutable_chunked_arrays: dict[
            int,
            tuple[
                weakref.ReferenceType[np.ndarray],
                tuple[int, int, str, tuple[int, ...], tuple[int, ...]],
                str,
                tuple[tuple[str, int], ...],
                int,
            ],
        ] = {}
        self._durability_lock = threading.Lock()
        self._known_durable: OrderedDict[str, None] = OrderedDict()
        self.counters = {
            "backing_repairs": 0,
            "blob_cache_hits": 0,
            "blob_reuses": 0,
            "immutable_array_reuses": 0,
            "blob_verifications": 0,
            "blob_writes": 0,
            "chunk_reuses": 0,
            "chunk_writes": 0,
            "durability_syncs": 0,
            "manifest_reuses": 0,
            "manifest_writes": 0,
        }

    @staticmethod
    def copy_on_write(array: np.ndarray) -> np.ndarray:
        """Make an explicit writable C-order copy of a read-only loaded array."""

        if not isinstance(array, np.ndarray):
            raise TypeError("copy_on_write requires a numpy array")
        return np.array(array, dtype=array.dtype, copy=True, order="C")

    def _safe_resolved(self, relative: str, *, expected: str, label: str) -> Path:
        if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
            raise SnapshotDescriptorError(f"{label} must be a relative path")
        candidate = Path(relative)
        # Backslashes are accepted by Windows Path, but a manifest is a
        # platform-independent identity and must use the exact derived path.
        if candidate.as_posix() != expected:
            raise SnapshotDescriptorError(f"{label} does not match its digest")
        resolved = (self.root / candidate).resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise SnapshotDescriptorError(f"{label} escapes state directory") from exc
        return resolved

    def _blob_cache_key(self, path: Path) -> tuple[str, int, int, int]:
        try:
            stat = path.stat()
        except OSError as exc:
            raise SnapshotCorruptionError(f"snapshot backing is unavailable: {path.name}") from exc
        return (str(path), int(stat.st_size), int(stat.st_mtime_ns), int(getattr(stat, "st_ino", 0)))

    def _remember_verified_blob(self, path: Path, digest: str, nbytes: int) -> None:
        key = self._blob_cache_key(path)
        if key[1] != nbytes:
            raise SnapshotCorruptionError(f"snapshot backing size mismatch for {path.name}")
        self._verified_blobs[key] = digest

    def _verify_blob(self, path: Path, digest: str, nbytes: int) -> None:
        key = self._blob_cache_key(path)
        if key[1] != nbytes:
            raise SnapshotCorruptionError(f"snapshot backing size mismatch for {path.name}")
        if self._verified_blobs.get(key) == digest:
            self.counters["blob_cache_hits"] += 1
            return
        self.counters["blob_verifications"] += 1
        if _sha256_file(path, expected_size=nbytes) != digest:
            raise SnapshotCorruptionError(f"array backing digest mismatch: {path.name}")
        self._verified_blobs[key] = digest

    def _backing_matches(self, path: Path, digest: str, nbytes: int) -> bool:
        """Report whether an existing content-addressed backing holds exact bytes.

        An unflushed backing can be torn by power loss after its name became
        durable; the caller republishes exact bytes over it.
        """

        if not path.exists():
            return False
        try:
            self._verify_blob(path, digest, nbytes)
        except SnapshotCorruptionError:
            return False
        return True

    def _install_backing(self, temporary: Path, target: Path, digest: str, nbytes: int) -> bool:
        """Install exact bytes at a content-addressed path; return whether they were written."""

        if _install_new(temporary, target):
            return True
        if self._backing_matches(target, digest, nbytes):
            return False
        self._replace_torn(temporary, target)
        return True

    def _replace_torn(self, temporary: Path, target: Path) -> None:
        os.replace(temporary, target)
        self.counters["backing_repairs"] += 1
        with self._durability_lock:
            self._known_durable.pop(str(target), None)

    def _ensure_durable(self, paths: Iterable[Path]) -> None:
        """Flush referenced backings this process has not already flushed.

        Content-addressed files change only through a torn-file repair, which
        forgets the path, so a remembered path still holds its flushed bytes.
        """

        parents: set[Path] = set()
        for path in paths:
            key = str(path)
            with self._durability_lock:
                if key in self._known_durable:
                    self._known_durable.move_to_end(key)
                    continue
            try:
                _fsync_file(path)
            except OSError as exc:
                raise SnapshotStoreError(
                    f"snapshot backing could not be made durable: {path.name}"
                ) from exc
            self.counters["durability_syncs"] += 1
            parents.add(path.parent)
            with self._durability_lock:
                self._known_durable[key] = None
                while len(self._known_durable) > _KNOWN_DURABLE_LIMIT:
                    self._known_durable.popitem(last=False)
        for parent in sorted(parents):
            _fsync_directory(parent)

    def _publish_manifest(self, path: Path, payload: bytes) -> bool:
        """Install one content-addressed manifest; return whether bytes were written."""

        temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
        try:
            try:
                if path.read_bytes() == payload:
                    return False
                torn = True
            except FileNotFoundError:
                torn = False
            temporary.write_bytes(payload)
            if not torn and _install_new(temporary, path):
                return True
            if not torn and path.read_bytes() == payload:
                return False
            self._replace_torn(temporary, path)
            return True
        except OSError as exc:
            raise SnapshotStoreError("snapshot manifest could not be published") from exc
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

    def _publish_current(self, descriptor: Mapping[str, Any]) -> None:
        current_bytes = _canonical_json_bytes(dict(descriptor)) + b"\n"
        try:
            if not self.current.exists() or self.current.read_bytes() != current_bytes:
                _atomic_bytes(self.current, current_bytes)
        except OSError as exc:
            raise SnapshotStoreError("snapshot CURRENT pointer could not be published") from exc

    @staticmethod
    def _immutable_signature(
        array: np.ndarray,
    ) -> tuple[int, int, str, tuple[int, ...], tuple[int, ...]] | None:
        if (
            not isinstance(array, np.ndarray)
            or array.flags.writeable
            or not array.flags.c_contiguous
        ):
            return None
        backing: Any = array
        while isinstance(backing, np.ndarray):
            if backing.flags.writeable:
                return None
            parent = getattr(backing, "base", None)
            if parent is None:
                break
            if not isinstance(parent, np.ndarray):
                # Read-only memmaps and mmap-backed reconstruction buffers
                # cannot be made writable through the ndarray interface.
                if isinstance(backing, np.memmap) and getattr(backing, "mode", None) == "r":
                    break
                if isinstance(parent, mmap.mmap):
                    try:
                        if memoryview(parent).readonly:
                            break
                    except TypeError:
                        pass
                return None
            backing = parent
        return (
            int(array.__array_interface__["data"][0]),
            int(array.nbytes),
            array.dtype.str,
            tuple(int(extent) for extent in array.shape),
            tuple(int(stride) for stride in array.strides),
        )

    def _remember_immutable_array(
        self,
        array: np.ndarray,
        digest: str,
    ) -> None:
        signature = self._immutable_signature(array)
        if signature is None:
            return
        identity = id(array)

        def forget(reference: weakref.ReferenceType[np.ndarray]) -> None:
            current = self._immutable_arrays.get(identity)
            if current is not None and current[0] is reference:
                self._immutable_arrays.pop(identity, None)

        self._immutable_arrays[identity] = (
            weakref.ref(array, forget),
            signature,
            digest,
        )

    def _reusable_immutable_array(
        self,
        array: np.ndarray,
    ) -> tuple[str, int] | None:
        signature = self._immutable_signature(array)
        if signature is None:
            return None
        entry = self._immutable_arrays.get(id(array))
        if entry is None or entry[0]() is not array or entry[1] != signature:
            return None
        digest = entry[2]
        nbytes = signature[1]
        target = self.blobs / f"{digest}.bin"
        self._verify_blob(target, digest, nbytes)
        self.counters["blob_reuses"] += 1
        self.counters["immutable_array_reuses"] += 1
        return digest, nbytes

    def _remember_immutable_chunked_array(
        self,
        array: np.ndarray,
        digest: str,
        chunks: tuple[tuple[str, int], ...],
        chunk_bytes: int,
    ) -> None:
        signature = self._immutable_signature(array)
        if signature is None:
            return
        identity = id(array)

        def forget(reference: weakref.ReferenceType[np.ndarray]) -> None:
            current = self._immutable_chunked_arrays.get(identity)
            if current is not None and current[0] is reference:
                self._immutable_chunked_arrays.pop(identity, None)

        self._immutable_chunked_arrays[identity] = (
            weakref.ref(array, forget),
            signature,
            digest,
            chunks,
            chunk_bytes,
        )

    def _reusable_immutable_chunked_array(
        self,
        array: np.ndarray,
    ) -> tuple[str, tuple[tuple[str, int], ...], int] | None:
        signature = self._immutable_signature(array)
        if signature is None:
            return None
        entry = self._immutable_chunked_arrays.get(id(array))
        if entry is None or entry[0]() is not array or entry[1] != signature:
            return None
        digest, chunks, chunk_bytes = entry[2], entry[3], entry[4]
        for chunk_digest, nbytes in chunks:
            self._verify_blob(_chunk_path(self.chunks, chunk_digest), chunk_digest, nbytes)
        self.counters["chunk_reuses"] += len(chunks)
        self.counters["immutable_array_reuses"] += 1
        return digest, chunks, chunk_bytes


    def _reusable_memmap(self, array: np.ndarray) -> tuple[str, int] | None:
        """Reuse a verified full-span read-only blob without streaming it again.

        ``np.asarray`` and ``np.ascontiguousarray`` preserve a loaded memmap's
        bytes but commonly return an ``ndarray`` view whose ``base`` is the
        memmap.  Follow that base chain and accept only a full-span view with
        the same first byte and byte count; slices must still be republished.
        """

        if not isinstance(array, np.ndarray) or array.flags.writeable or not array.flags.c_contiguous:
            return None
        backing: Any = array
        seen: set[int] = set()
        while isinstance(backing, np.ndarray) and not isinstance(backing, np.memmap):
            identity = id(backing)
            if identity in seen:
                return None
            seen.add(identity)
            backing = getattr(backing, "base", None)
        if not isinstance(backing, np.memmap):
            return None
        if backing.flags.writeable or not backing.flags.c_contiguous:
            return None
        if int(array.nbytes) != int(backing.nbytes):
            return None
        if (
            int(array.__array_interface__["data"][0])
            != int(backing.__array_interface__["data"][0])
        ):
            return None
        filename = getattr(backing, "filename", None)
        if filename is None or getattr(backing, "offset", None) != 0:
            return None
        try:
            path = Path(filename).resolve()
        except (OSError, TypeError, ValueError):
            return None
        try:
            path.relative_to(self.blobs)
        except ValueError:
            return None
        if path.parent != self.blobs or path.suffix != ".bin":
            return None
        digest = path.stem
        try:
            _digest_text(digest, "array blob")
            key = self._blob_cache_key(path)
        except SnapshotStoreError:
            return None
        nbytes = int(array.nbytes)
        if key[1] != nbytes:
            raise SnapshotCorruptionError(f"snapshot backing size mismatch for {path.name}")
        cached = self._verified_blobs.get(key)
        if cached == digest:
            self.counters["blob_cache_hits"] += 1
            self.counters["blob_reuses"] += 1
            return digest, nbytes
        # A stat change invalidates the cache. Rehash before reuse so a
        # modified backing is reported, never silently treated as unchanged.
        self._verify_blob(path, digest, nbytes)
        self.counters["blob_reuses"] += 1
        return digest, nbytes

    def _publish_array(
        self,
        array: np.ndarray,
        *,
        reuse_immutable_arrays: bool,
    ) -> tuple[str, int]:
        if array.dtype.hasobject:
            raise SnapshotStoreError("object arrays cannot be persisted")
        reusable = (
            self._reusable_immutable_array(array)
            if reuse_immutable_arrays
            else None
        )
        if reusable is None:
            reusable = self._reusable_memmap(array)
            if reusable is not None and reuse_immutable_arrays:
                self._remember_immutable_array(array, reusable[0])
        if reusable is not None:
            return reusable
        source = array if array.flags.c_contiguous else np.ascontiguousarray(array)
        nbytes = int(source.nbytes)
        if nbytes > self.max_array_bytes:
            raise SnapshotStoreError("snapshot array exceeds max_array_bytes")
        temporary = self.blobs / f".array.{os.getpid()}.{uuid.uuid4().hex}.tmp"
        digest = hashlib.sha256()
        try:
            # Hash current bytes even for read-only views with writable bases:
            # those cannot use the identity cache, but an unchanged blob needs
            # no temporary file.
            if reuse_immutable_arrays:
                try:
                    view = memoryview(source).cast("B")
                except (TypeError, ValueError):
                    view = memoryview(source.tobytes(order="C"))
                sha = hashlib.sha256(view).hexdigest()
                target = self.blobs / f"{sha}.bin"
                if self._backing_matches(target, sha, nbytes):
                    self.counters["blob_reuses"] += 1
                    self._remember_immutable_array(array, sha)
                    return sha, nbytes
            with temporary.open("wb") as handle:
                if nbytes:
                    try:
                        view = memoryview(source).cast("B")
                    except (TypeError, ValueError):
                        view = memoryview(source.tobytes(order="C"))
                    for offset in range(0, nbytes, _HASH_CHUNK_BYTES):
                        chunk = view[offset : offset + _HASH_CHUNK_BYTES]
                        digest.update(chunk)
                        handle.write(chunk)
            sha = digest.hexdigest()
            target = self.blobs / f"{sha}.bin"
            if self._install_backing(temporary, target, sha, nbytes):
                self.counters["blob_writes"] += 1
            self._remember_verified_blob(target, sha, nbytes)
            if reuse_immutable_arrays:
                self._remember_immutable_array(array, sha)
            return sha, nbytes
        except SnapshotStoreError:
            raise
        except OSError as exc:
            raise SnapshotStoreError("snapshot array backing could not be published") from exc
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

    def _publish_chunk(self, view: memoryview) -> tuple[str, int]:
        nbytes = len(view)
        digest = hashlib.sha256(view).hexdigest()
        target = _chunk_path(self.chunks, digest)
        if self._backing_matches(target, digest, nbytes):
            self.counters["chunk_reuses"] += 1
            return digest, nbytes
        temporary = self.chunks / f".chunk.{os.getpid()}.{uuid.uuid4().hex}.tmp"
        try:
            with temporary.open("wb") as handle:
                handle.write(view)
            if self._install_backing(temporary, target, digest, nbytes):
                self.counters["chunk_writes"] += 1
            else:
                self.counters["chunk_reuses"] += 1
            self._remember_verified_blob(target, digest, nbytes)
            return digest, nbytes
        except SnapshotStoreError:
            raise
        except OSError as exc:
            raise SnapshotStoreError("snapshot chunk could not be published") from exc
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

    def _publish_chunked_array(
        self,
        array: np.ndarray,
        *,
        reuse_immutable_arrays: bool,
    ) -> tuple[str, tuple[tuple[str, int], ...], int]:
        if array.dtype.hasobject:
            raise SnapshotStoreError("object arrays cannot be persisted")
        reusable = (
            self._reusable_immutable_chunked_array(array)
            if reuse_immutable_arrays
            else None
        )
        if reusable is not None:
            return reusable

        overall_digest = hashlib.sha256()
        chunk_refs: list[tuple[str, int]] = []
        total = 0
        for view in _iter_array_byte_chunks(array, self.chunk_bytes):
            overall_digest.update(view)
            digest, nbytes = self._publish_chunk(view)
            chunk_refs.append((digest, nbytes))
            total += nbytes
        if total != int(array.nbytes):
            raise SnapshotStoreError("snapshot chunk byte count changed during publication")
        digest = overall_digest.hexdigest()
        chunks = tuple(chunk_refs)
        if reuse_immutable_arrays:
            self._remember_immutable_chunked_array(array, digest, chunks, self.chunk_bytes)
        return digest, chunks, self.chunk_bytes

    def save(
        self,
        arrays: Mapping[str, np.ndarray],
        metadata: Mapping[str, Any],
        *,
        reuse_immutable_arrays: bool = False,
        durable: bool = True,
    ) -> dict[str, Any]:
        """Persist arrays and metadata and return a deterministic snapshot descriptor.

        ``reuse_immutable_arrays`` is an executor-owned fast path.  Its caller
        promises that accepted array objects and their storage remain immutable
        until released; ordinary callers retain the content-verifying path.
        ``durable=False`` publishes readable, verified bytes without flushing
        them or moving ``CURRENT``; the caller must pass the descriptor to
        :meth:`make_durable` before any durable record references it.
        """

        if not isinstance(arrays, Mapping):
            raise TypeError("arrays must be a mapping")
        if not isinstance(metadata, Mapping):
            raise TypeError("metadata must be a mapping")
        metadata_bytes = _canonical_json_bytes(dict(metadata))
        if len(metadata_bytes) > _MAX_MANIFEST_BYTES:
            raise SnapshotStoreError("snapshot metadata is too large")
        entries: dict[str, dict[str, Any]] = {}
        total = 0
        manifest_schema = SNAPSHOT_MANIFEST_SCHEMA
        backings: list[Path] = []
        names = list(arrays.keys())
        for name in names:
            if not isinstance(name, str) or not name or len(name.encode("utf-8")) > 4096:
                raise SnapshotStoreError("snapshot array names must be bounded nonempty strings")
        names.sort()
        for name in names:
            array = arrays[name]
            if not isinstance(array, np.ndarray):
                raise TypeError(f"snapshot array {name!r} is not a numpy array")
            if array.dtype.hasobject:
                raise SnapshotStoreError("object arrays cannot be persisted")
            nbytes = int(array.nbytes)
            total += nbytes
            if nbytes > self.max_array_bytes or total > self.max_total_bytes:
                raise SnapshotStoreError("snapshot arrays exceed configured bounds")
            if nbytes > self.chunk_threshold_bytes:
                sha, chunks, chunk_bytes = self._publish_chunked_array(
                    array,
                    reuse_immutable_arrays=reuse_immutable_arrays,
                )
                if sum(size for _, size in chunks) != nbytes:
                    raise SnapshotStoreError("snapshot array byte count changed during publication")
                backings.extend(_chunk_path(self.chunks, chunk_digest) for chunk_digest, _ in chunks)
                entries[name] = _manifest_array_entry(
                    array,
                    sha,
                    nbytes,
                    chunk_bytes=chunk_bytes,
                    chunks=chunks,
                )
                manifest_schema = SNAPSHOT_MANIFEST_CHUNKED_SCHEMA
            else:
                sha, published_nbytes = self._publish_array(
                    array,
                    reuse_immutable_arrays=reuse_immutable_arrays,
                )
                if published_nbytes != nbytes:
                    raise SnapshotStoreError("snapshot array byte count changed during publication")
                backings.append(self.blobs / f"{sha}.bin")
                entries[name] = _manifest_array_entry(array, sha, nbytes)
        core = {
            "arrays": entries,
            "metadata": json.loads(metadata_bytes.decode("utf-8")),
            "schema": manifest_schema,
        }
        snapshot_sha256 = _sha256_bytes(_canonical_json_bytes(core))
        manifest = {**core, "snapshot_sha256": snapshot_sha256}
        manifest_bytes = _canonical_json_bytes(manifest) + b"\n"
        if len(manifest_bytes) > _MAX_MANIFEST_BYTES:
            raise SnapshotStoreError("snapshot manifest is too large")
        manifest_path = self.snapshots / f"{snapshot_sha256}.json"
        if self._publish_manifest(manifest_path, manifest_bytes):
            self.counters["manifest_writes"] += 1
        else:
            self.counters["manifest_reuses"] += 1
        descriptor = {
            "manifest": f"snapshots/{snapshot_sha256}.json",
            "schema": SNAPSHOT_DESCRIPTOR_SCHEMA,
            "snapshot_sha256": snapshot_sha256,
        }
        if durable:
            self._ensure_durable([*backings, manifest_path])
            self._publish_current(descriptor)
        return descriptor

    def make_durable(self, descriptor: Mapping[str, Any] | str | os.PathLike[str]) -> dict[str, Any]:
        """Flush one published snapshot, then point ``CURRENT`` at it.

        Every backing the manifest names is flushed before the pointer that
        names the manifest, so a record written after this call survives power
        loss together with all the bytes it references.
        """

        manifest, digest = self._read_manifest(descriptor)
        entries = manifest.get("arrays")
        if not isinstance(entries, dict):
            raise SnapshotCorruptionError("snapshot manifest fields are invalid")
        backings: list[Path] = []
        for name, item in entries.items():
            if not isinstance(item, dict):
                raise SnapshotCorruptionError(f"array {name} manifest entry is invalid")
            sha = _digest_text(item.get("sha256"), f"array {name} sha256")
            if item.get("storage") == _CHUNKED_ARRAY_STORAGE:
                raw_chunks = item.get("chunks")
                if not isinstance(raw_chunks, list):
                    raise SnapshotCorruptionError(f"array {name} chunk list is invalid")
                for index, raw_chunk in enumerate(raw_chunks):
                    if not isinstance(raw_chunk, dict):
                        raise SnapshotCorruptionError(f"array {name} chunk entry is invalid")
                    chunk_digest = _digest_text(raw_chunk.get("sha256"), f"array {name} chunk {index} sha256")
                    backings.append(
                        self._safe_resolved(
                            raw_chunk.get("blob"),
                            expected=f"chunks/{chunk_digest}.bin",
                            label=f"array {name} chunk {index} blob",
                        )
                    )
            else:
                backings.append(
                    self._safe_resolved(item.get("blob"), expected=f"blobs/{sha}.bin", label=f"array {name} blob")
                )
        resolved = {
            "manifest": f"snapshots/{digest}.json",
            "schema": SNAPSHOT_DESCRIPTOR_SCHEMA,
            "snapshot_sha256": digest,
        }
        self._ensure_durable([*backings, self.snapshots / f"{digest}.json"])
        self._publish_current(resolved)
        return resolved

    def _read_manifest(self, descriptor: Mapping[str, Any] | str | os.PathLike[str]) -> tuple[dict[str, Any], str]:
        if isinstance(descriptor, (str, os.PathLike)):
            relative = Path(descriptor)
            if relative.name.endswith(".json") and relative.parent.name == "snapshots":
                expected_digest = relative.stem
                descriptor_map: Mapping[str, Any] = {
                    "manifest": relative.as_posix(),
                    "schema": SNAPSHOT_DESCRIPTOR_SCHEMA,
                    "snapshot_sha256": expected_digest,
                }
            else:
                raise SnapshotDescriptorError("snapshot path must name a snapshots manifest")
        elif isinstance(descriptor, Mapping):
            descriptor_map = descriptor
        else:
            raise SnapshotDescriptorError("snapshot descriptor must be a mapping or manifest path")
        if descriptor_map.get("schema") != SNAPSHOT_DESCRIPTOR_SCHEMA:
            raise SnapshotDescriptorError("snapshot descriptor schema is invalid")
        digest = _digest_text(descriptor_map.get("snapshot_sha256"), "snapshot_sha256")
        manifest_name = descriptor_map.get("manifest")
        manifest_path = self._safe_resolved(
            manifest_name,
            expected=f"snapshots/{digest}.json",
            label="snapshot manifest",
        )
        try:
            size = manifest_path.stat().st_size
            if size <= 0 or size > _MAX_MANIFEST_BYTES:
                raise SnapshotCorruptionError("snapshot manifest size is invalid")
            raw = manifest_path.read_bytes()
            manifest = json.loads(raw.decode("utf-8"))
        except SnapshotStoreError:
            raise
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise SnapshotCorruptionError("snapshot manifest is unreadable JSON") from exc
        if not isinstance(manifest, dict):
            raise SnapshotCorruptionError("snapshot manifest is not an object")
        if manifest.get("schema") not in (
            SNAPSHOT_MANIFEST_SCHEMA,
            SNAPSHOT_MANIFEST_CHUNKED_SCHEMA,
        ):
            raise SnapshotCorruptionError("snapshot manifest schema is invalid")
        if _digest_text(manifest.get("snapshot_sha256"), "manifest snapshot_sha256") != digest:
            raise SnapshotCorruptionError("snapshot manifest digest does not match descriptor")
        core = {
            "arrays": manifest.get("arrays"),
            "metadata": manifest.get("metadata"),
            "schema": manifest.get("schema"),
        }
        try:
            computed = _sha256_bytes(_canonical_json_bytes(core))
        except SnapshotStoreError as exc:
            raise SnapshotCorruptionError("snapshot manifest is not canonical") from exc
        if computed != digest:
            raise SnapshotCorruptionError("snapshot manifest content digest mismatch")
        return manifest, digest

    def _load_chunked_array(
        self,
        item: Mapping[str, Any],
        digest: str,
        nbytes: int,
        shape: tuple[int, ...],
        dtype: np.dtype[Any],
        name: str,
    ) -> tuple[np.ndarray, tuple[tuple[str, int], ...], int]:
        chunk_bytes = item.get("chunk_bytes")
        if (
            isinstance(chunk_bytes, bool)
            or not isinstance(chunk_bytes, int)
            or chunk_bytes <= 0
            or chunk_bytes > _MAX_ARRAY_CHUNK_BYTES
        ):
            raise SnapshotCorruptionError(f"array {name} chunk size is invalid")
        raw_chunks = item.get("chunks")
        expected_count = (nbytes + chunk_bytes - 1) // chunk_bytes
        if not isinstance(raw_chunks, list) or len(raw_chunks) != expected_count:
            raise SnapshotCorruptionError(f"array {name} chunk list is invalid")
        chunk_refs: list[tuple[str, int, Path]] = []
        remaining = nbytes
        for index, raw_chunk in enumerate(raw_chunks):
            if not isinstance(raw_chunk, dict):
                raise SnapshotCorruptionError(f"array {name} chunk entry is invalid")
            try:
                chunk_digest = _digest_text(
                    raw_chunk.get("sha256"),
                    f"array {name} chunk {index} sha256",
                )
                expected_size = min(chunk_bytes, remaining)
                actual_size = raw_chunk.get("nbytes")
                if (
                    isinstance(actual_size, bool)
                    or not isinstance(actual_size, int)
                    or actual_size != expected_size
                ):
                    raise SnapshotCorruptionError(f"array {name} chunk size does not match layout")
                path = self._safe_resolved(
                    raw_chunk.get("blob"),
                    expected=f"chunks/{chunk_digest}.bin",
                    label=f"array {name} chunk {index} blob",
                )
            except SnapshotStoreError as exc:
                raise SnapshotCorruptionError(str(exc)) from exc
            chunk_refs.append((chunk_digest, actual_size, path))
            remaining -= actual_size
        if remaining:
            raise SnapshotCorruptionError(f"array {name} chunks do not cover its byte range")
        if nbytes == 0:
            if digest != _sha256_bytes(b""):
                raise SnapshotCorruptionError(f"array {name} empty digest is invalid")
            array = np.empty(shape, dtype=dtype)
            array.setflags(write=False)
            return array, (), chunk_bytes

        whole_digest = hashlib.sha256()
        try:
            with tempfile.TemporaryFile(mode="w+b") as staged:
                for index, (chunk_digest, expected_size, path) in enumerate(chunk_refs):
                    chunk_hasher = hashlib.sha256()
                    copied = 0
                    with path.open("rb") as source:
                        while True:
                            data = source.read(_MATERIALIZE_COPY_BYTES)
                            if not data:
                                break
                            copied += len(data)
                            chunk_hasher.update(data)
                            whole_digest.update(data)
                            staged.write(data)
                    if copied != expected_size or chunk_hasher.hexdigest() != chunk_digest:
                        raise SnapshotCorruptionError(
                            f"array {name} chunk {index} digest or size mismatch"
                        )
                    self._remember_verified_blob(path, chunk_digest, expected_size)
                if whole_digest.hexdigest() != digest:
                    raise SnapshotCorruptionError(f"array {name} reconstructed digest mismatch")
                staged.flush()
                mapped = mmap.mmap(staged.fileno(), nbytes, access=mmap.ACCESS_READ)
            try:
                array = np.ndarray(shape, dtype=dtype, buffer=mapped, order="C")
                array.setflags(write=False)
            except (TypeError, ValueError):
                mapped.close()
                raise
        except SnapshotCorruptionError:
            raise
        except (OSError, TypeError, ValueError) as exc:
            raise SnapshotCorruptionError(f"array {name} chunks cannot be reconstructed") from exc
        return array, tuple((chunk_digest, size) for chunk_digest, size, _ in chunk_refs), chunk_bytes


    def load(self, descriptor: Mapping[str, Any] | str | os.PathLike[str]) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
        """Verify and load a snapshot as read-only mmap-backed arrays."""

        manifest, _ = self._read_manifest(descriptor)
        manifest_schema = manifest.get("schema")
        metadata = manifest.get("metadata")
        entries = manifest.get("arrays")
        if not isinstance(metadata, dict) or not isinstance(entries, dict):
            raise SnapshotCorruptionError("snapshot manifest fields are invalid")
        arrays: dict[str, np.ndarray] = {}
        total = 0
        for name in sorted(entries):
            item = entries[name]
            if not isinstance(name, str) or not isinstance(item, dict):
                raise SnapshotCorruptionError("snapshot array entry is invalid")
            try:
                sha = _digest_text(item.get("sha256"), f"array {name} sha256")
                shape = _shape(item.get("shape"))
            except SnapshotStoreError as exc:
                raise SnapshotCorruptionError(str(exc)) from exc
            try:
                dtype = _dtype_from_entry(item, name)
            except SnapshotStoreError as exc:
                raise SnapshotCorruptionError(str(exc)) from exc
            nbytes = item.get("nbytes")
            if isinstance(nbytes, bool) or not isinstance(nbytes, int) or nbytes < 0:
                raise SnapshotCorruptionError(f"array {name} nbytes is invalid")
            try:
                expected_nbytes = math.prod(shape) * dtype.itemsize
            except (OverflowError, ValueError) as exc:
                raise SnapshotCorruptionError(f"array {name} shape is invalid") from exc
            if expected_nbytes != nbytes or nbytes > self.max_array_bytes:
                raise SnapshotCorruptionError(f"array {name} byte count does not match shape/dtype")
            total += nbytes
            if total > self.max_total_bytes:
                raise SnapshotCorruptionError("snapshot arrays exceed configured bounds")
            storage = item.get("storage")
            if storage == _CHUNKED_ARRAY_STORAGE:
                if manifest_schema != SNAPSHOT_MANIFEST_CHUNKED_SCHEMA:
                    raise SnapshotCorruptionError("chunked arrays require the versioned manifest")
                array, chunks, chunk_bytes = self._load_chunked_array(
                    item,
                    sha,
                    nbytes,
                    shape,
                    dtype,
                    name,
                )
                self._remember_immutable_chunked_array(array, sha, chunks, chunk_bytes)
            else:
                if "storage" in item:
                    raise SnapshotCorruptionError(f"array {name} storage format is invalid")
                try:
                    blob_path = self._safe_resolved(
                        item.get("blob"),
                        expected=f"blobs/{sha}.bin",
                        label=f"array {name} blob",
                    )
                    self._verify_blob(blob_path, sha, nbytes)
                except SnapshotStoreError as exc:
                    raise SnapshotCorruptionError(
                        f"array {name} backing verification failed"
                    ) from exc
                if nbytes == 0:
                    array = np.empty(shape, dtype=dtype)
                    array.setflags(write=False)
                else:
                    try:
                        array = np.memmap(blob_path, mode="r", dtype=dtype, shape=shape, order="C")
                        array.setflags(write=False)
                    except (OSError, ValueError) as exc:
                        raise SnapshotCorruptionError(
                            f"array {name} backing cannot be mapped"
                        ) from exc
            arrays[name] = array
        return arrays, dict(metadata)

    def working_branch(
        self,
        descriptor: Mapping[str, Any] | str | os.PathLike[str],
    ) -> SnapshotBranch:
        """Open a copy-on-write working branch over a verified snapshot.

        The branch loads its pages exactly once through :meth:`load`, so it
        reuses that call's manifest verification and read-only mmap-backed
        parsing instead of re-implementing them.  Only the small manifest is
        consulted a second time, to retain the resolved descriptor and the
        exact per-array content digests alongside the loaded pages.
        """

        arrays, metadata = self.load(descriptor)
        manifest, snapshot_digest = self._read_manifest(descriptor)
        entries = manifest.get("arrays")
        if not isinstance(entries, dict):
            raise SnapshotCorruptionError("snapshot manifest fields are invalid")
        digests: dict[str, str] = {}
        for name in entries:
            item = entries[name]
            if not isinstance(name, str) or not isinstance(item, dict):
                raise SnapshotCorruptionError("snapshot manifest fields are invalid")
            digests[name] = _digest_text(item.get("sha256"), f"array {name} sha256")
        if set(digests) != set(arrays):
            raise SnapshotCorruptionError("snapshot manifest arrays do not match the loaded snapshot")
        resolved: dict[str, Any] = {
            "manifest": f"snapshots/{snapshot_digest}.json",
            "schema": SNAPSHOT_DESCRIPTOR_SCHEMA,
            "snapshot_sha256": snapshot_digest,
        }
        return SnapshotBranch(self, resolved, arrays, metadata, digests)


class SnapshotBranch:
    """A copy-on-write working branch over one immutable loaded snapshot.

    Shared pages are the exact read-only instances ``load`` produced, so an
    untouched array stays identity-shared with its source snapshot.  The
    first ``mutable`` call is the single divergence point: it materializes a
    writable C-order copy through ``SnapshotStore.copy_on_write`` and caches
    it, and later calls return that same copy.  ``save`` publishes through
    ``SnapshotStore.save`` with ``reuse_immutable_arrays=True``, so unchanged
    pages re-content-address to exactly their previous digests and only
    diverged pages receive new ones.
    """

    def __init__(
        self,
        store: SnapshotStore,
        descriptor: Mapping[str, Any],
        arrays: Mapping[str, np.ndarray],
        metadata: Mapping[str, Any],
        digests: Mapping[str, str],
    ) -> None:
        if not isinstance(store, SnapshotStore):
            raise TypeError("snapshot branch requires a SnapshotStore")
        if not isinstance(arrays, Mapping) or not arrays:
            raise SnapshotStoreError("snapshot branch requires loaded arrays")
        for name, array in arrays.items():
            if not isinstance(name, str) or not isinstance(array, np.ndarray):
                raise SnapshotStoreError("snapshot branch arrays are invalid")
        self._store = store
        self._shared: dict[str, np.ndarray] = dict(arrays)
        self._diverged: dict[str, np.ndarray] = {}
        self.arrays: Mapping[str, np.ndarray] = MappingProxyType(self._shared)
        self.descriptor: dict[str, Any] = dict(descriptor)
        self.metadata: dict[str, Any] = dict(metadata)
        self.digests: dict[str, str] = dict(digests)

    def __contains__(self, name: object) -> bool:
        return name in self._shared

    def __getitem__(self, name: str) -> np.ndarray:
        """Return this branch's working page for ``name``.

        Before divergence this is the exact read-only shared instance the
        branch loaded; after ``mutable`` it is that call's writable copy.
        """

        if not isinstance(name, str):
            raise SnapshotStoreError("snapshot array name must be a string")
        diverged = self._diverged.get(name)
        if diverged is not None:
            return diverged
        try:
            return self._shared[name]
        except KeyError as exc:
            raise SnapshotStoreError(f"snapshot branch has no array {name!r}") from exc

    def mutable(self, name: str) -> np.ndarray:
        """Return this branch's writable copy, diverging the page on first call.

        The first call makes an explicit writable C-order copy of the shared
        read-only page through ``SnapshotStore.copy_on_write``; later calls
        return that same cached copy, so divergence is stable.  The source
        snapshot's page stays read-only and byte-identical.
        """

        if not isinstance(name, str):
            raise SnapshotStoreError("snapshot array name must be a string")
        diverged = self._diverged.get(name)
        if diverged is not None:
            return diverged
        shared = self._shared.get(name)
        if shared is None:
            raise SnapshotStoreError(f"snapshot branch has no array {name!r}")
        copy = SnapshotStore.copy_on_write(shared)
        self._diverged[name] = copy
        return copy

    def save(self, metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Publish this branch and return its new snapshot descriptor.

        Unchanged pages re-content-address to exactly their previous digests;
        only pages handed out by ``mutable`` are republished as new content.
        With no explicit ``metadata`` the source snapshot's metadata is kept.
        """

        pages: dict[str, np.ndarray] = dict(self._shared)
        pages.update(self._diverged)
        payload = self.metadata if metadata is None else metadata
        return self._store.save(pages, payload, reuse_immutable_arrays=True)


__all__ = [
    "SNAPSHOT_DESCRIPTOR_SCHEMA",
    "SNAPSHOT_MANIFEST_SCHEMA",
    "SNAPSHOT_MANIFEST_CHUNKED_SCHEMA",
    "SnapshotBranch",
    "SnapshotDescriptorError",
    "SnapshotStore",
    "SnapshotStoreError",
]
