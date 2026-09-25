"""ISO9660 random-access reader specialized for PS2 boot discovery.

The reader never loads the whole image: it seeks sector-by-sector to the
volume descriptors and directory records it needs, and extracts only the
requested files.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SECTOR_SIZE = 2048
VOLUME_SECTOR = 16
ELF_MAGIC = b"\x7fELF"


class IsoError(ValueError):
    """The image is not an ISO9660 volume this reader can navigate strictly."""


@dataclass(frozen=True)
class DirEntry:
    name: str
    extent: int
    size: int
    is_dir: bool

    @property
    def offset(self) -> int:
        return self.extent * SECTOR_SIZE


@dataclass(frozen=True)
class BootImage:
    boot_path: str
    serial: str
    version: str | None
    entry: DirEntry
    elf_offset: int


MAX_DIRECTORY_ENTRIES = 4096
MAX_FILE_BYTES = 1 << 26  # a PS2 boot ELF is far below 64 MiB
MAX_CN_BYTES = 4096


class IsoReader:
    """Bounded ISO9660 navigation over one fixed, existing image file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if not self.path.is_file():
            raise IsoError(f"ISO image does not exist: {self.path}")
        self._file = open(self.path, "rb")
        try:
            self._volume = _parse_primary_volume(self._file)
        except Exception:
            self._file.close()
            raise
        self.volume_id = self._volume["volume_id"]
        self.root = self._volume["root"]

    def close(self) -> None:
        self._file.close()

    def __enter__(self) -> "IsoReader":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()

    def listdir(self, path: str = "") -> list[DirEntry]:
        entry = self.root if path in ("", "/") else self._walk(path)
        if not entry.is_dir:
            raise IsoError(f"ISO path is not a directory: {path}")
        return _read_directory(self._file, entry)

    def lookup(self, path: str) -> DirEntry:
        return self._walk(path)

    def read_entry(self, entry: DirEntry, max_bytes: int = MAX_FILE_BYTES) -> bytes:
        if entry.is_dir:
            raise IsoError("directory extents cannot be read as file data")
        if entry.size > max_bytes:
            raise IsoError(
                f"file extent of {entry.size} bytes exceeds the bounded read limit")
        self._file.seek(entry.offset)
        body = self._file.read(entry.size)
        if len(body) != entry.size:
            raise IsoError("file extent is truncated by the image boundary")
        return body

    def boot_image(self) -> BootImage:
        """Find SYSTEM.CNF, parse the boot path, and resolve the boot ELF."""
        entries = {self._clean(entry.name): entry
                   for entry in _read_directory(self._file, self.root)}
        cnf = entries.get("SYSTEM.CNF")
        if cnf is None or cnf.is_dir:
            raise IsoError("image has no SYSTEM.CNF at the volume root")
        if cnf.size > MAX_CN_BYTES:
            raise IsoError("SYSTEM.CNF is implausibly large for a boot descriptor")
        text = self.read_entry(cnf, max_bytes=MAX_CN_BYTES).decode("latin-1")
        boot_path, version = _parse_system_cnf(text)
        serial = _serial_of(boot_path)
        target = self._walk(boot_path)
        if target.is_dir or target.size < 4:
            raise IsoError("SYSTEM.CNF boot path does not name a file")
        body_head = self._read_at(target.offset, min(target.size, 0x1000))
        elf_offset = _elf_offset(body_head)
        return BootImage(boot_path=boot_path, serial=serial, version=version,
                         entry=target, elf_offset=elf_offset)

    def iso_sha256(self, chunk: int = 1 << 20) -> str:
        digest = hashlib.sha256()
        self._file.seek(0)
        while True:
            block = self._file.read(chunk)
            if not block:
                break
            digest.update(block)
        return digest.hexdigest()

    def _walk(self, path: str) -> DirEntry:
        parts = [_clean_part(part) for part in path.replace("\\", "/").split("/")]
        parts = [part for part in parts if part]
        if not parts:
            return self.root
        entry = self.root
        for part in parts:
            if not entry.is_dir:
                raise IsoError(f"ISO path segment is not a directory: {part}")
            found = None
            explicit_version = ";" in part
            for child in _read_directory(self._file, entry):
                candidate = (
                    _clean_part(child.name)
                    if explicit_version
                    else self._clean(child.name)
                )
                if candidate == part:
                    found = child
                    break
            if found is None:
                raise IsoError(f"ISO path does not exist in the image: {path}")
            entry = found
        return entry

    @staticmethod
    def _clean(name: str) -> str:
        stripped = name.split(";")[0].strip().upper()
        return stripped

    def _read_at(self, offset: int, size: int) -> bytes:
        self._file.seek(offset)
        body = self._file.read(size)
        if len(body) != size:
            raise IsoError("image ended before the requested extent")
        return body


def _parse_primary_volume(file: Any) -> dict[str, Any]:
    file.seek(VOLUME_SECTOR * SECTOR_SIZE)
    sector = file.read(SECTOR_SIZE)
    if len(sector) != SECTOR_SIZE:
        raise IsoError("volume descriptor sector is missing")
    if sector[0] != 1 or sector[1:6] != b"CD001" or sector[6] != 1:
        raise IsoError("image does not carry a CD001 primary volume descriptor")
    root = _parse_record(sector[156:156 + 34])
    if root is None or not root.is_dir:
        raise IsoError("primary volume descriptor carries no usable root directory")
    volume_id = sector[40:72].decode("latin-1").strip("\x00 ")
    return {"root": root, "volume_id": volume_id}


def _read_directory(file: Any, entry: DirEntry) -> list[DirEntry]:
    if not entry.is_dir:
        raise IsoError("directory records can only be read from a directory extent")
    size = entry.size
    if size <= 0 or size > MAX_FILE_BYTES:
        raise IsoError("directory extent has an implausible size")
    file.seek(entry.offset)
    body = file.read(size)
    if len(body) != size:
        raise IsoError("directory extent is truncated by the image boundary")
    records: list[DirEntry] = []
    offset = 0
    while offset < size:
        length = body[offset]
        if length == 0:
            sector_rest = SECTOR_SIZE - (offset % SECTOR_SIZE)
            if sector_rest == SECTOR_SIZE:
                break
            offset += sector_rest
            continue
        record = _parse_record(body[offset:offset + length])
        if record is None:
            raise IsoError("malformed directory record in the image")
        if record.name not in ("\x00", "\x01"):
            records.append(record)
        offset += length
        if len(records) > MAX_DIRECTORY_ENTRIES:
            raise IsoError("directory extent holds an implausible number of entries")
    return records


def _parse_record(raw: bytes) -> DirEntry | None:
    if len(raw) < 34:
        return None
    length = raw[0]
    if length == 0:
        return None
    if length > len(raw):
        raise IsoError("directory record exceeds its sector allocation")
    extent_le = int.from_bytes(raw[2:6], "little")
    size_le = int.from_bytes(raw[10:14], "little")
    flags = raw[25]
    name_length = raw[32]
    if 33 + name_length > length:
        raise IsoError("directory record name exceeds the record length")
    name_bytes = raw[33:33 + name_length]
    name = name_bytes.decode("latin-1")
    is_dir = bool(flags & 0x02)
    if name_length == 1 and name_bytes[0] == 0:
        name = "\x00"
    elif name_length == 1 and name_bytes[0] == 1:
        name = "\x01"
    return DirEntry(name=name, extent=extent_le, size=size_le, is_dir=is_dir)


def _parse_system_cnf(text: str) -> tuple[str, str | None]:
    boot_path = None
    version = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(";") or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            raise IsoError("SYSTEM.CNF contains a line without a key = value pair")
        key, _, value = stripped.partition("=")
        key = key.strip().upper()
        value = value.strip()
        if key == "BOOT2":
            boot_path = value
        elif key == "BOOT" and boot_path is None:
            boot_path = value
        elif key == "VER":
            version = value
    if not boot_path:
        raise IsoError("SYSTEM.CNF names no BOOT2 boot executable")
    path = boot_path.strip()
    if path.lower().startswith("cdrom"):
        path = path[5:]
        if path.startswith("0:"):
            path = path[2:]
    path = path.replace("\\", "/").lstrip("/")
    if not path:
        raise IsoError("SYSTEM.CNF boot path is empty")
    return path, version


def _serial_of(path: str) -> str:
    leaf = path.replace("\\", "/").split("/")[-1]
    serial = leaf.split(";")[0].strip().upper()
    if not serial:
        raise IsoError("SYSTEM.CNF boot path carries no serial")
    return serial


def _clean_part(part: str) -> str:
    return part.strip().upper()


def _elf_offset(head: bytes) -> int:
    index = head.find(ELF_MAGIC)
    if index < 0:
        raise IsoError("boot file carries no ELF magic in its first page")
    return index
