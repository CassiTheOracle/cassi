"""Strict ELF32 little-endian MIPS executable parsing for PS2 boot images."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Sequence


ELF_MAGIC = b"\x7fELF"
ELFCLASS32 = 1
ELFDATA2LSB = 1
EM_MIPS = 8
ET_EXEC = 2
PT_LOAD = 1
PF_X = 1
SHT_SYMTAB = 2
SHT_NOBITS = 8
STT_FUNC = 2
STT_NOTYPE = 0

EHDR = struct.Struct("<4sBBBBB7xHHIIIIIHHHHHH")
PHDR = struct.Struct("<8I")
SHDR = struct.Struct("<10I")
SYM = struct.Struct("<IIIBBH")


class ElfError(ValueError):
    """The boot image is not a well-formed ELF32 little-endian MIPS executable."""


@dataclass(frozen=True)
class Segment:
    vaddr: int
    offset: int
    filesz: int
    memsz: int
    flags: int

    @property
    def executable(self) -> bool:
        return bool(self.flags & PF_X)

    def contains(self, address: int) -> bool:
        return self.vaddr <= address < self.vaddr + self.filesz


@dataclass(frozen=True)
class Section:
    name: str
    type: int
    flags: int
    addr: int
    offset: int
    size: int
    link: int
    entsize: int


@dataclass(frozen=True)
class Symbol:
    name: str
    value: int
    size: int
    info: int
    shndx: int

    @property
    def is_function(self) -> bool:
        return (self.info & 0xF) == STT_FUNC


class ElfFile:
    """A parsed ELF32 LE MIPS executable with bounded random-access reads."""

    def __init__(self, data: bytes) -> None:
        if len(data) < EHDR.size:
            raise ElfError("ELF header is truncated")
        if data[:4] != ELF_MAGIC:
            raise ElfError("file does not carry the ELF magic")
        (magic, elf_class, elf_data, _version, _abi, _abi_version,
         e_type, e_machine, _e_version2, e_entry, e_phoff, e_shoff,
         _e_flags, e_ehsize, e_phentsize, e_phnum, e_shentsize,
         e_shnum, e_shstrndx) = EHDR.unpack_from(data, 0)
        del magic
        if elf_class != ELFCLASS32:
            raise ElfError("ELF image is not 32-bit")
        if elf_data != ELFDATA2LSB:
            raise ElfError("ELF image is not little-endian")
        if e_machine != EM_MIPS:
            raise ElfError("ELF image is not MIPS")
        if e_type != ET_EXEC:
            raise ElfError("ELF image is not an executable")
        if (
            e_ehsize < EHDR.size
            or (e_phnum and e_phentsize != PHDR.size)
            or (e_shnum and e_shentsize != SHDR.size)
        ):
            raise ElfError("ELF header/entry sizes are non-standard")
        self._data = data
        self.entry = e_entry
        self.segments = _parse_segments(data, e_phoff, e_phnum)
        self.sections = _parse_sections(data, e_shoff, e_shnum, e_shstrndx)
        self.symbols = _parse_symbols(data, self.sections)

    @property
    def data(self) -> bytes:
        return self._data

    @property
    def executable_segments(self) -> Sequence[Segment]:
        return tuple(segment for segment in self.segments if segment.executable and segment.filesz)

    def read(self, address: int, size: int) -> bytes:
        """Read `size` bytes mapped through the file-backed program segments."""
        if size < 0:
            raise ElfError("negative read size")
        out = bytearray()
        remaining = size
        while remaining > 0:
            source = None
            for segment in self.segments:
                if segment.filesz and segment.contains(address):
                    source = segment
                    break
            if source is None:
                raise ElfError(f"address 0x{address:08x} is not backed by the ELF file")
            take = min(remaining, source.vaddr + source.filesz - address)
            offset = source.offset + (address - source.vaddr)
            if offset + take > len(self._data):
                raise ElfError("ELF program data extends past the end of the file")
            out += self._data[offset:offset + take]
            address += take
            remaining -= take
        return bytes(out)


def _parse_segments(data: bytes, offset: int, count: int) -> tuple[Segment, ...]:
    if count == 0:
        return ()
    if offset + count * PHDR.size > len(data):
        raise ElfError("program header table extends past the end of the file")
    segments = []
    for index in range(count):
        (p_type, p_offset, p_vaddr, _p_paddr, p_filesz, p_memsz,
         p_flags, _p_align) = PHDR.unpack_from(data, offset + index * PHDR.size)
        if p_type != PT_LOAD:
            continue
        if p_filesz > p_memsz:
            raise ElfError("loadable segment file size exceeds its memory size")
        if p_filesz and (p_offset > len(data) or p_offset + p_filesz > len(data)):
            raise ElfError("program segment data extends past the end of the file")
        segments.append(Segment(vaddr=p_vaddr, offset=p_offset,
                                filesz=p_filesz, memsz=p_memsz, flags=p_flags))
    return tuple(segments)


def _parse_sections(data: bytes, offset: int, count: int, string_index: int) -> tuple[Section, ...]:
    if count == 0:
        return ()
    if offset + count * SHDR.size > len(data):
        raise ElfError("section header table extends past the end of the file")
    raw = []
    for index in range(count):
        (sh_name, sh_type, sh_flags, sh_addr, sh_offset, sh_size,
         sh_link, _sh_info, sh_addralign, sh_entsize) = SHDR.unpack_from(
            data, offset + index * SHDR.size)
        raw.append((sh_name, sh_type, sh_flags, sh_addr, sh_offset,
                    sh_size, sh_link, sh_entsize))
    names = b""
    if 0 <= string_index < count:
        sh_offset, sh_size = raw[string_index][4], raw[string_index][5]
        if sh_offset + sh_size <= len(data):
            names = data[sh_offset:sh_offset + sh_size]
        else:
            raise ElfError("section name string table extends past the end of the file")

    def name_at(index: int) -> str:
        if index >= len(names):
            return ""
        end = names.find(b"\x00", index)
        if end < 0:
            end = len(names)
        return names[index:end].decode("ascii", "replace")

    sections = []
    for (sh_name, sh_type, sh_flags, sh_addr, sh_offset, sh_size,
         sh_link, sh_entsize) in raw:
        if sh_type != SHT_NOBITS and sh_offset + sh_size > len(data):
            raise ElfError("section data extends past the end of the file")
        sections.append(Section(name=name_at(sh_name), type=sh_type,
                                flags=sh_flags, addr=sh_addr, offset=sh_offset,
                                size=sh_size, link=sh_link, entsize=sh_entsize))
    return tuple(sections)


def _parse_symbols(data: bytes, sections: Sequence[Section]) -> tuple[Symbol, ...]:
    symtabs = [section for section in sections if section.type == SHT_SYMTAB]
    symbols: list[Symbol] = []
    for section in symtabs:
        if section.entsize != SYM.size:
            raise ElfError("symbol table entry size is not 16 bytes")
        if section.link >= len(sections):
            raise ElfError("symbol table string table link is out of range")
        strtab = sections[section.link]
        strings = data[strtab.offset:strtab.offset + strtab.size]
        count = section.size // SYM.size
        for index in range(count):
            st_name, st_value, st_size, st_info, _st_other, st_shndx = SYM.unpack_from(
                data, section.offset + index * SYM.size)
            name = ""
            if st_name:
                end = strings.find(b"\x00", st_name)
                if st_name >= len(strings):
                    name = ""
                else:
                    end = strings.find(b"\x00", st_name)
                    if end < 0:
                        raise ElfError("symbol name is not NUL-terminated")
                    name = strings[st_name:end].decode("utf-8", "replace")
            symbols.append(Symbol(name=name, value=st_value, size=st_size,
                                  info=st_info, shndx=st_shndx))
    return tuple(symbols)
