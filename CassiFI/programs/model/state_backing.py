"""Immutable, digest-bound backing for resident model working state.

The model executor owns numerical execution; this module only persists the
field-selected activation/cache arrays that a continuation chooses to retain.
Array bytes are content addressed and manifests are deterministic, so a
snapshot descriptor remains usable after a process restart or branch fork.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import uuid
import weakref
from typing import Any, Mapping

import numpy as np


SNAPSHOT_DESCRIPTOR_SCHEMA = "cassifi.resident-model-snapshot-descriptor.v1"
SNAPSHOT_MANIFEST_SCHEMA = "cassifi.resident-model-snapshot-manifest.v1"

# These are corruption/DoS guards, not model-size limits.  They can be
# tightened for an installation by passing the corresponding constructor
# arguments; normal working-state arrays are generally much smaller.
_DEFAULT_MAX_ARRAY_BYTES = 1 << 40
_DEFAULT_MAX_TOTAL_BYTES = 1 << 42
_MAX_MANIFEST_BYTES = 16 << 20
_HASH_CHUNK_BYTES = 8 << 20


class SnapshotStoreError(ValueError):
    """Base error for invalid descriptors, state, or backing data."""


class SnapshotDescriptorError(SnapshotStoreError):
    """The caller supplied a descriptor that is not a valid snapshot ref."""


class SnapshotCorruptionError(SnapshotStoreError):
    """A published manifest/blob is missing, truncated, or has changed bytes."""


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

    ``save`` publishes each array as a raw C-order byte blob and then publishes
    one deterministic manifest.  Existing blobs are reused by digest; no
    mutable file is ever overwritten in place.  ``load`` verifies every byte
    before creating a read-only ``numpy.memmap`` view.  Callers that need to
    update an array must explicitly copy it (``np.array(array, copy=True)``).
    """

    def __init__(
        self,
        state_directory: str | os.PathLike[str],
        *,
        max_array_bytes: int = _DEFAULT_MAX_ARRAY_BYTES,
        max_total_bytes: int = _DEFAULT_MAX_TOTAL_BYTES,
    ) -> None:
        if isinstance(max_array_bytes, bool) or not isinstance(max_array_bytes, int) or max_array_bytes <= 0:
            raise ValueError("max_array_bytes must be a positive integer")
        if isinstance(max_total_bytes, bool) or not isinstance(max_total_bytes, int) or max_total_bytes <= 0:
            raise ValueError("max_total_bytes must be a positive integer")
        root = Path(state_directory)
        try:
            root.mkdir(parents=True, exist_ok=True)
            self.root = root.resolve()
            self.state_directory = self.root
            self.blobs = self.root / "blobs"
            self.snapshots = self.root / "snapshots"
            self.blobs.mkdir(parents=True, exist_ok=True)
            self.snapshots.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise SnapshotStoreError("state directory cannot be created") from exc
        self.max_array_bytes = max_array_bytes
        self.max_total_bytes = max_total_bytes
        self._verified_blobs: dict[tuple[str, int, int, int], str] = {}
        self._immutable_arrays: dict[
            int,
            tuple[
                weakref.ReferenceType[np.ndarray],
                tuple[int, int, str, tuple[int, ...], tuple[int, ...]],
                str,
            ],
        ] = {}
        self.counters = {
            "blob_cache_hits": 0,
            "blob_reuses": 0,
            "immutable_array_reuses": 0,
            "blob_verifications": 0,
            "blob_writes": 0,
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
            # neither another temporary file nor another fsync.
            if reuse_immutable_arrays:
                try:
                    view = memoryview(source).cast("B")
                except (TypeError, ValueError):
                    view = memoryview(source.tobytes(order="C"))
                sha = hashlib.sha256(view).hexdigest()
                target = self.blobs / f"{sha}.bin"
                if target.exists():
                    self._verify_blob(target, sha, nbytes)
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
                handle.flush()
                os.fsync(handle.fileno())
            sha = digest.hexdigest()
            target = self.blobs / f"{sha}.bin"
            if target.exists():
                self.counters["blob_verifications"] += 1
                if _sha256_file(target, expected_size=nbytes) != sha:
                    raise SnapshotCorruptionError(f"content-addressed blob is corrupt: {target.name}")
            else:
                os.replace(temporary, target)
                _fsync_directory(self.blobs)
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

    def save(
        self,
        arrays: Mapping[str, np.ndarray],
        metadata: Mapping[str, Any],
        *,
        reuse_immutable_arrays: bool = False,
    ) -> dict[str, Any]:
        """Persist arrays and metadata and return a deterministic snapshot descriptor.

        ``reuse_immutable_arrays`` is an executor-owned fast path.  Its caller
        promises that accepted array objects and their storage remain immutable
        until released; ordinary callers retain the content-verifying path.
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
            sha, published_nbytes = self._publish_array(
                array,
                reuse_immutable_arrays=reuse_immutable_arrays,
            )
            dtype = np.dtype(array.dtype)
            shape = [int(extent) for extent in array.shape]
            if published_nbytes != nbytes:
                raise SnapshotStoreError("snapshot array byte count changed during publication")
            entries[name] = {
                "blob": f"blobs/{sha}.bin",
                **_dtype_entry(dtype),
                "nbytes": nbytes,
                "sha256": sha,
                "shape": shape,
            }
        core = {
            "arrays": entries,
            "metadata": json.loads(metadata_bytes.decode("utf-8")),
            "schema": SNAPSHOT_MANIFEST_SCHEMA,
        }
        snapshot_sha256 = _sha256_bytes(_canonical_json_bytes(core))
        manifest = {**core, "snapshot_sha256": snapshot_sha256}
        manifest_bytes = _canonical_json_bytes(manifest) + b"\n"
        if len(manifest_bytes) > _MAX_MANIFEST_BYTES:
            raise SnapshotStoreError("snapshot manifest is too large")
        manifest_path = self.snapshots / f"{snapshot_sha256}.json"
        if manifest_path.exists():
            try:
                existing = manifest_path.read_bytes()
            except OSError as exc:
                raise SnapshotCorruptionError("snapshot manifest cannot be read") from exc
            if existing != manifest_bytes:
                raise SnapshotCorruptionError("existing snapshot manifest differs for the same digest")
            self.counters["manifest_reuses"] += 1
        else:
            try:
                _atomic_bytes(manifest_path, manifest_bytes)
            except OSError as exc:
                raise SnapshotStoreError("snapshot manifest could not be published") from exc
            self.counters["manifest_writes"] += 1
        return {
            "manifest": f"snapshots/{snapshot_sha256}.json",
            "schema": SNAPSHOT_DESCRIPTOR_SCHEMA,
            "snapshot_sha256": snapshot_sha256,
        }

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
        if manifest.get("schema") != SNAPSHOT_MANIFEST_SCHEMA:
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

    def load(self, descriptor: Mapping[str, Any] | str | os.PathLike[str]) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
        """Verify and load a snapshot as read-only mmap-backed arrays."""

        manifest, _ = self._read_manifest(descriptor)
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
                blob = item.get("blob")
                blob_path = self._safe_resolved(
                    blob,
                    expected=f"blobs/{sha}.bin",
                    label=f"array {name} blob",
                )
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
            try:
                self._verify_blob(blob_path, sha, nbytes)
            except SnapshotStoreError as exc:
                raise SnapshotCorruptionError(f"array {name} backing verification failed") from exc
            if nbytes == 0:
                array = np.empty(shape, dtype=dtype)
                array.setflags(write=False)
            else:
                try:
                    array = np.memmap(blob_path, mode="r", dtype=dtype, shape=shape, order="C")
                    array.setflags(write=False)
                except (OSError, ValueError) as exc:
                    raise SnapshotCorruptionError(f"array {name} backing cannot be mapped") from exc
            arrays[name] = array
        return arrays, dict(metadata)


__all__ = [
    "SNAPSHOT_DESCRIPTOR_SCHEMA",
    "SNAPSHOT_MANIFEST_SCHEMA",
    "SnapshotCorruptionError",
    "SnapshotDescriptorError",
    "SnapshotStore",
    "SnapshotStoreError",
]
