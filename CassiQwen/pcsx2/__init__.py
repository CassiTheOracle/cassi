"""Catalog and observe PCSX2 games with explicitly opted-in PINE effects.

The package catalogs a fixed PS2 ISO, watches live memory over PINE, compares
labeled snapshots, and consumes the native field-only bridge.  PINE effects
require explicit caller permission; the native bridge has only a bounded
stream and typed enable/action/cancel controls, never arbitrary game-memory
writes or save-state operations.
"""

from __future__ import annotations

from pcsx2.atlas import (
    AtlasError,
    FunctionAtlas,
    FunctionRecord,
    elf_word_xor_crc,
)
from pcsx2.catalog import catalog_iso
from pcsx2.elf import ElfError, ElfFile
from pcsx2.iso import IsoError, IsoReader
from pcsx2.mips import disassemble, disassemble_one
from pcsx2.pine import (
    MAX_READ_BYTES,
    MAX_REQUEST,
    MAX_REPLY,
    PineClient,
    PineError,
)
from pcsx2.snapshots import compare_snapshots
from pcsx2.gameplay import (
    GameplayFocusLost,
    GameplayInputError,
    XInputSource,
    meaningful_transitions,
)
from pcsx2.native_bridge import (
    NativeBridgeClient,
    NativeBridgeError,
    NativeBridgeTimeout,
)

__all__ = [
    "AtlasError",
    "ElfError",
    "ElfFile",
    "FunctionAtlas",
    "FunctionRecord",
    "IsoError",
    "IsoReader",
    "MAX_READ_BYTES",
    "MAX_REQUEST",
    "MAX_REPLY",
    "PineClient",
    "PineError",
    "catalog_iso",
    "compare_snapshots",
    "disassemble",
    "disassemble_one",
    "elf_word_xor_crc",
    "GameplayFocusLost",
    "GameplayInputError",
    "XInputSource",
    "meaningful_transitions",
    "NativeBridgeClient",
    "NativeBridgeError",
    "NativeBridgeTimeout",
]
