"""One-entry static cataloging of a fixed PS2 ISO into a function atlas."""

from __future__ import annotations

import hashlib
from pathlib import Path

from pcsx2.atlas import FunctionAtlas, build_atlas, elf_word_xor_crc
from pcsx2.elf import ElfFile
from pcsx2.iso import IsoError, IsoReader

ELF_MAGIC = b"\x7fELF"


def catalog_iso(iso_path: str | Path, output_dir: str | Path) -> FunctionAtlas:
    """Catalog one fixed ISO image: SYSTEM.CNF, boot ELF, atlas, `.sym` export."""
    source = Path(iso_path)
    if not source.is_file():
        raise IsoError(f"ISO image does not exist: {source}")
    target = Path(output_dir)
    with IsoReader(source) as reader:
        boot = reader.boot_image()
        body = reader.read_entry(boot.entry)
        volume_id = reader.volume_id
        iso_sha256 = reader.iso_sha256()
    elf_offset = boot.elf_offset
    body = body[elf_offset:] if elf_offset else body
    if body[:4] != ELF_MAGIC:
        raise IsoError("boot file does not start with ELF magic")
    elf_sha256 = hashlib.sha256(body).hexdigest()
    identity = {
        "title": volume_id,
        "serial": boot.serial,
        "version": boot.version,
        "boot_path": boot.boot_path,
        "entry": None,
        "elf_sha256": elf_sha256,
        "iso_sha256": iso_sha256,
        "iso_size": source.stat().st_size,
        "pcsx2_crc": f"{elf_word_xor_crc(body):08x}",
        "machine": "mips/r5900",
    }
    elf = ElfFile(body)
    identity["entry"] = elf.entry
    atlas = build_atlas(body, identity, iso_path=str(source))
    atlas.write(target)
    return atlas
