"""Static catalog of PS2 boot executables: function atlas and symbol export."""

from __future__ import annotations

from bisect import bisect_left, bisect_right
import hashlib
import json
import re
import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from pcsx2.elf import ElfError, ElfFile
from pcsx2.mips import disassemble_one

MAX_FUNCTIONS = 50_000
MAX_REFERENCES = 100_000
MAX_STRINGS = 20_000
MAX_INSTRUCTIONS_PER_FUNCTION = 32
MAX_FUNCTION_SIZE = 0x8000
MAX_SCAN_BYTES_PER_SEGMENT = 1 << 22
MIN_STRING_BYTES = 4

SOURCE_SYMBOL = "symbol"
SOURCE_ENTRY = "entry"
SOURCE_JAL = "jal-target"
SOURCE_PROLOGUE = "prologue"

_SOURCE_PRIORITY = {SOURCE_SYMBOL: 0, SOURCE_ENTRY: 1, SOURCE_JAL: 2, SOURCE_PROLOGUE: 3}

_NAME_SAFE = re.compile(r"[^A-Za-z0-9_.+-]")
_WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}

REGISTERS = (
    "$zero", "$at", "$v0", "$v1", "$a0", "$a1", "$a2", "$a3",
    "$t0", "$t1", "$t2", "$t3", "$t4", "$t5", "$t6", "$t7",
    "$s0", "$s1", "$s2", "$s3", "$s4", "$s5", "$s6", "$s7",
    "$t8", "$t9", "$k0", "$k1", "$gp", "$sp", "$fp", "$ra",
)

_MEMORY_WIDTH_BY_OPCODE = {
    0x1A: 8, 0x1B: 8, 0x1E: 16, 0x1F: 16,
    0x20: 1, 0x21: 2, 0x22: 4, 0x23: 4,
    0x24: 1, 0x25: 2, 0x26: 4, 0x27: 4,
    0x28: 1, 0x29: 2, 0x2A: 4, 0x2B: 4,
    0x2C: 8, 0x2D: 8, 0x2E: 4,
    0x30: 4, 0x31: 4, 0x32: 4,
    0x34: 8, 0x35: 8, 0x36: 16, 0x37: 8,
    0x38: 4, 0x39: 4, 0x3A: 4, 0x3B: 4,
    0x3C: 8, 0x3D: 8, 0x3E: 16, 0x3F: 8,
}
_MEMORY_OPCODES = frozenset(_MEMORY_WIDTH_BY_OPCODE)
_GPR_LOAD_OPCODES = frozenset({
    0x1A, 0x1B, 0x1E,
    *range(0x20, 0x28),
    0x30, 0x34, 0x37, 0x38, 0x3C,
})
_BRANCH_OPCODES = frozenset({0x04, 0x05, 0x06, 0x07, 0x14, 0x15, 0x16, 0x17})
_REGIMM_BRANCH_RT = frozenset({0x00, 0x01, 0x02, 0x03, 0x10, 0x11, 0x12, 0x13})
_REGIMM_LINK_RT = frozenset({0x10, 0x11, 0x12, 0x13})


class AtlasError(ValueError):
    """The executable cannot be cataloged into a bounded function atlas."""


@dataclass
class FunctionRecord:
    address: int
    size: int
    name: str
    source: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def contains(self, address: int) -> bool:
        return self.address <= address < self.address + self.size

    def as_json(self) -> dict[str, Any]:
        return {
            "address": self.address,
            "size": self.size,
            "name": self.name,
            "source": self.source,
            "evidence": copy.deepcopy(self.evidence),
        }


def elf_word_xor_crc(elf_bytes: bytes) -> int:
    """PCSX2-style ELF CRC: XOR of every little-endian 4-byte word."""
    count = len(elf_bytes) - (len(elf_bytes) % 4)
    value = 0
    for offset in range(0, count, 4):
        value ^= int.from_bytes(elf_bytes[offset:offset + 4], "little")
    return value & 0xFFFFFFFF


class FunctionAtlas:
    """A static, source-bound catalog of one PS2 boot executable."""

    def __init__(self, *, identity: Mapping[str, Any], functions: list[FunctionRecord],
                 references: list[dict[str, Any]], strings: list[dict[str, Any]],
                 segments: list[dict[str, Any]], symbols: list[dict[str, Any]],
                 iso_path: str | None = None) -> None:
        self.identity = dict(identity)
        self.functions = sorted(functions, key=lambda function: function.address)
        self.references = list(references)
        self.strings = list(strings)
        self.segments = list(segments)
        self.symbols = list(symbols)
        self.iso_path = iso_path
        self.sym_path: str | None = None
        self.atlas_path: str | None = None
        self._function_starts = [function.address for function in self.functions]
        self._functions_by_start = {
            function.address: function for function in self.functions
        }
        self._references_from: dict[int, list[dict[str, Any]]] = {}
        self._references_to: dict[int, list[dict[str, Any]]] = {}
        callers: dict[int, set[int]] = {}
        for reference in self.references:
            source = int(reference["from_address"])
            self._references_from.setdefault(source, []).append(reference)
            target = reference.get("to_address")
            if target is None:
                continue
            target = int(target)
            self._references_to.setdefault(target, []).append(reference)
            if reference.get("kind") != "call":
                continue
            owner = self._containing_function(source)
            if owner is not None:
                callers.setdefault(target, set()).add(owner.address)
        self._callers_by_target = {
            target: tuple(sorted(addresses))
            for target, addresses in callers.items()
        }
        self._reference_targets = sorted(self._references_to)

    # -- lookups -----------------------------------------------------------
    def _containing_function(self, address: int) -> FunctionRecord | None:
        index = bisect_right(self._function_starts, address) - 1
        if index < 0:
            return None
        function = self.functions[index]
        return function if function.contains(address) else None

    def functions_for_address(self, address: int) -> tuple[FunctionRecord, ...]:
        function = self._containing_function(address)
        return () if function is None else (function,)

    def symbol_at(self, address: int) -> FunctionRecord | None:
        index = bisect_right(self._function_starts, address) - 1
        return None if index < 0 else self.functions[index]

    def callees_of(self, address: int) -> tuple[int, ...]:
        record = self._by_address(address)
        if record is None:
            return ()
        return tuple(sorted({int(target) for target in record.evidence.get("calls", ())}))

    def callers_of(self, address: int) -> tuple[int, ...]:
        return self._callers_by_target.get(address, ())

    def call_graph(self) -> dict[str, list[str]]:
        graph: dict[str, set[str]] = {}
        for function in self.functions:
            key = f"0x{function.address:08x}"
            graph.setdefault(key, set())
            for target in function.evidence.get("calls", ()):
                graph[key].add(f"0x{int(target):08x}")
        return {key: sorted(values) for key, values in sorted(graph.items())}

    def references_for_address(self, address: int) -> list[dict[str, Any]]:
        return [dict(reference) for reference in self._references_from.get(address, ())]

    def references_to_address(self, address: int) -> list[dict[str, Any]]:
        return [dict(reference) for reference in self._references_to.get(address, ())]

    def references_near_address(self, address: int, span: int = 64) -> list[dict[str, Any]]:
        first = bisect_left(self._reference_targets, address - span)
        last = bisect_right(self._reference_targets, address + span)
        return [
            dict(reference)
            for target in self._reference_targets[first:last]
            for reference in self._references_to[target]
        ]

    def strings_near(self, address: int, span: int = 64) -> list[dict[str, Any]]:
        low, high = address - span, address + span
        return [dict(entry) for entry in self.strings
                if low <= int(entry["address"]) <= high]

    def _by_address(self, address: int) -> FunctionRecord | None:
        return self._functions_by_start.get(address)

    # -- serialization -------------------------------------------------------
    @property
    def data(self) -> dict[str, Any]:
        return {
            "identity": dict(self.identity),
            "functions": [function.as_json() for function in self.functions],
            "references": [dict(reference) for reference in self.references],
            "strings": [dict(entry) for entry in self.strings],
            "segments": [dict(segment) for segment in self.segments],
            "symbols": [dict(symbol) for symbol in self.symbols],
            "paths": {
                "iso": self.iso_path,
                "atlas": self.atlas_path,
                "sym": self.sym_path,
            },
            "counts": {
                "functions": len(self.functions),
                "references": len(self.references),
                "strings": len(self.strings),
                "symbols": len(self.symbols),
            },
        }

    def summary(self) -> dict[str, Any]:
        summary: dict[str, Any] = dict(self.identity)
        summary["functions"] = len(self.functions)
        summary["references"] = len(self.references)
        summary["strings"] = len(self.strings)
        summary["symbols"] = len(self.symbols)
        summary["paths"] = {"iso": self.iso_path, "atlas": self.atlas_path,
                            "sym": self.sym_path}
        return summary

    def to_json(self) -> str:
        return json.dumps(self.data, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False) + "\n"

    @property
    def sym_text(self) -> str:
        lines: list[str] = []
        used: set[str] = set()
        for function in sorted(self.functions, key=lambda item: item.address):
            name = _unique_name(_safe_name(function.name), used, function.address)
            suffix = ""
            if function.size > 1:
                suffix = f",{function.size:x}"
            lines.append(f"{function.address:08x} {name}{suffix}")
        return ("\n".join(lines) + "\n") if lines else ""

    def write(self, output_dir: str | Path) -> tuple[Path, Path]:
        directory = Path(output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        stem = str(self.identity.get("serial") or self.identity.get("title") or "boot")
        stem = _safe_name(stem) or "boot"
        atlas_path = directory / f"{stem}.atlas.json"
        sym_path = directory / f"{stem}.sym"
        _write_bytes(atlas_path, self.to_json().encode("ascii"))
        _write_bytes(sym_path, self.sym_text.encode("ascii"))
        self.atlas_path = str(atlas_path)
        self.sym_path = str(sym_path)
        return atlas_path, sym_path


def _write_bytes(path: Path, body: bytes) -> None:
    with path.open("wb") as stream:
        stream.write(body)
        stream.flush()


def _safe_name(name: str) -> str:
    cleaned = _NAME_SAFE.sub("_", name).strip("_") or "sub"
    if cleaned.upper() in _WINDOWS_RESERVED_NAMES:
        return f"_{cleaned}"
    return cleaned


def _unique_name(name: str, used: set[str], address: int) -> str:
    if name not in used:
        used.add(name)
        return name
    candidate = f"{name}_{address:x}"
    while candidate in used:
        candidate += "_"
    used.add(candidate)
    return candidate


@dataclass(frozen=True)
class _Scope:
    vaddr: int
    end: int
    body: bytes
    executable: bool


def build_atlas(elf_bytes: bytes, identity: Mapping[str, Any],
                iso_path: str | None = None) -> FunctionAtlas:
    """Catalog one boot ELF into function candidates, calls, and strings."""
    try:
        elf = ElfFile(elf_bytes)
    except ElfError as exc:
        raise AtlasError(str(exc)) from exc

    scopes = [_Scope(segment.vaddr, segment.vaddr + segment.filesz,
                     elf.read(segment.vaddr, segment.filesz),
                     segment.executable)
              for segment in elf.segments if segment.filesz]
    exec_scopes = [scope for scope in scopes if scope.executable]

    candidates = _candidate_functions(elf, exec_scopes)
    functions = _bound_functions(candidates, exec_scopes)
    references, calls_by_function = _scan_references(exec_scopes, functions)
    strings = _scan_strings(scopes)
    _attach_evidence(elf, functions, references, calls_by_function, strings)

    segments_json = [
        {"vaddr": segment.vaddr, "offset": segment.offset,
         "filesz": segment.filesz, "memsz": segment.memsz,
         "flags": segment.flags}
        for segment in elf.segments if segment.filesz
    ]
    symbols_json = [
        {"name": symbol.name, "value": symbol.value, "size": symbol.size,
         "info": symbol.info, "shndx": symbol.shndx}
        for symbol in elf.symbols if symbol.name
    ]
    return FunctionAtlas(
        identity=identity,
        functions=functions,
        references=references,
        strings=strings,
        segments=segments_json,
        symbols=symbols_json,
        iso_path=iso_path,
    )


def _candidate_functions(elf: ElfFile,
                         exec_scopes: list[_Scope]) -> dict[int, tuple[str, str | None]]:
    candidates: dict[int, tuple[str, str | None]] = {}

    def in_exec(address: int) -> bool:
        return any(scope.vaddr <= address < scope.end for scope in exec_scopes)

    def admit(address: int, source: str, name: str | None = None) -> None:
        if len(candidates) >= MAX_FUNCTIONS or not in_exec(address):
            return
        existing = candidates.get(address)
        if existing is None or _SOURCE_PRIORITY[source] < _SOURCE_PRIORITY[existing[0]]:
            candidates[address] = (source, name)

    if elf.entry and in_exec(elf.entry):
        admit(elf.entry, SOURCE_ENTRY)
    for symbol in elf.symbols:
        if symbol.is_function and symbol.value:
            admit(symbol.value, SOURCE_SYMBOL, symbol.name or None)
    for scope in exec_scopes:
        for offset, word, pc in _iter_words(scope):
            opcode = word >> 26
            if opcode == 0x03:  # jal
                target = ((pc + 4) & 0xF0000000) | ((word & 0x03FFFFFF) << 2)
                admit(target, SOURCE_JAL)
            elif opcode == 0x01 and (word >> 16) & 31 in _REGIMM_LINK_RT:
                imm = word & 0xFFFF
                simm = imm - 0x10000 if imm >= 0x8000 else imm
                admit((pc + 4 + (simm << 2)) & 0xFFFFFFFF, SOURCE_JAL)
            elif opcode == 0x09 and (word >> 21) & 31 == 29 and (word >> 16) & 31 == 29:
                if word & 0xFFFF >= 0x8000:  # addiu $sp, $sp, -N
                    admit(pc, SOURCE_PROLOGUE)
    return candidates


def _iter_words(scope: _Scope):
    usable = (scope.end - scope.vaddr) - ((scope.end - scope.vaddr) % 4)
    if usable > MAX_SCAN_BYTES_PER_SEGMENT:
        usable = MAX_SCAN_BYTES_PER_SEGMENT - (MAX_SCAN_BYTES_PER_SEGMENT % 4)
    for offset in range(0, usable, 4):
        word = int.from_bytes(scope.body[offset:offset + 4], "little")
        yield offset, word, (scope.vaddr + offset) & 0xFFFFFFFF


def _bound_functions(candidates: dict[int, tuple[str, str | None]],
                     exec_scopes: list[_Scope]) -> list[FunctionRecord]:
    functions: list[FunctionRecord] = []
    for scope in exec_scopes:
        addresses = sorted(address for address in candidates
                           if scope.vaddr <= address < scope.end)
        for index, address in enumerate(addresses):
            next_address = (addresses[index + 1] if index + 1 < len(addresses)
                            else scope.end)
            size = min(next_address - address, MAX_FUNCTION_SIZE)
            if size <= 0:
                size = 4
            source, name = candidates[address]
            functions.append(FunctionRecord(
                address=address, size=size,
                name=name or _default_name(address, source),
                source=source))
        if len(functions) >= MAX_FUNCTIONS:
            break
    functions.sort(key=lambda function: function.address)
    return functions[:MAX_FUNCTIONS]


def _default_name(address: int, source: str) -> str:
    prefix = {SOURCE_ENTRY: "entry", SOURCE_JAL: "sub", SOURCE_PROLOGUE: "prologue"}.get(source)
    if prefix is None:
        return f"sub_{address:08x}"
    return f"{prefix}_{address:08x}"


def _scan_references(exec_scopes: list[_Scope],
                     functions: list[FunctionRecord]) -> tuple[list[dict[str, Any]], dict[int, list[int]]]:
    references: list[dict[str, Any]] = []
    function_starts = [function.address for function in functions]
    start_set = set(function_starts)
    for scope in exec_scopes:
        known_addresses: dict[int, int] = {}
        control_targets: set[int] = set()
        clear_after_delay = False
        for _offset, word, pc in _iter_words(scope):
            is_delay_slot = clear_after_delay
            clear_after_delay = False
            if pc in start_set or (pc in control_targets and not is_delay_slot):
                known_addresses.clear()
            opcode = word >> 26
            rs = (word >> 21) & 31
            rt = (word >> 16) & 31
            imm = word & 0xFFFF
            simm = imm - 0x10000 if imm >= 0x8000 else imm
            resolved: tuple[int, int] | None = None
            direct_target: int | None = None
            has_delay_slot = False

            if opcode == 0x02:
                direct_target = ((pc + 4) & 0xF0000000) | ((word & 0x03FFFFFF) << 2)
                references.append(_reference("jump", pc, direct_target, word))
                has_delay_slot = True
            elif opcode == 0x03:
                direct_target = ((pc + 4) & 0xF0000000) | ((word & 0x03FFFFFF) << 2)
                references.append(_reference("call", pc, direct_target, word))
                has_delay_slot = True
            elif (
                opcode in _BRANCH_OPCODES
                or (opcode == 0x01 and rt in _REGIMM_BRANCH_RT)
            ):
                direct_target = (pc + 4 + (simm << 2)) & 0xFFFFFFFF
                kind = "call" if opcode == 0x01 and rt in _REGIMM_LINK_RT else "branch"
                references.append(_reference(kind, pc, direct_target, word))
                has_delay_slot = True
            elif opcode == 0x00 and (word & 63) == 0x09:  # jalr
                references.append({
                    "kind": "call-indirect", "from_address": pc,
                    "to_address": None, "register": REGISTERS[rs],
                    "disasm": disassemble_one(word, pc),
                })
                has_delay_slot = True
            elif opcode == 0x00 and (word & 63) == 0x08:  # jr
                has_delay_slot = True

            if direct_target is not None and scope.vaddr <= direct_target < scope.end:
                control_targets.add(direct_target)

            if opcode == 0x0F:  # lui
                known_addresses[rt] = (imm << 16) & 0xFFFFFFFF
            else:
                if opcode in (0x08, 0x09, 0x18, 0x19) and rs in known_addresses and rt != 0:
                    resolved = (rt, (known_addresses[rs] + simm) & 0xFFFFFFFF)
                elif opcode == 0x0D and rs in known_addresses and rt != 0:  # ori
                    resolved = (rt, known_addresses[rs] | imm)
                if resolved is not None:
                    references.append(
                        _data_reference(
                            pc, resolved[1], word, resolved[0],
                            access="address", width=0,
                        ),
                    )
                if opcode in _MEMORY_OPCODES and rs in known_addresses:
                    target = (known_addresses[rs] + simm) & 0xFFFFFFFF
                    references.append(
                        _data_reference(
                            pc, target, word, rs,
                            access="memory", width=_MEMORY_WIDTH_BY_OPCODE[opcode],
                        ),
                    )

                for register in _written_gprs(word):
                    known_addresses.pop(register, None)
                if resolved is not None and resolved[0] != 0:
                    known_addresses[resolved[0]] = resolved[1]

            if is_delay_slot:
                known_addresses.clear()
            if has_delay_slot:
                clear_after_delay = True
            if len(references) >= MAX_REFERENCES:
                break
        if len(references) >= MAX_REFERENCES:
            break

    calls_by_function: dict[int, list[int]] = {}
    for reference in references:
        if reference["kind"] != "call" or reference["to_address"] is None:
            continue
        source = reference["from_address"]
        owner = _owner_function(functions, int(source), function_starts)
        if owner is not None:
            calls_by_function.setdefault(owner, []).append(int(reference["to_address"]))
    return references, calls_by_function


def _written_gprs(word: int) -> tuple[int, ...]:
    opcode = word >> 26
    rs = (word >> 21) & 31
    rt = (word >> 16) & 31
    rd = (word >> 11) & 31
    function = word & 63
    register = None
    if opcode == 0x00:
        if (
            function in {0x00, 0x02, 0x03, 0x04, 0x06, 0x07, 0x09, 0x0A, 0x0B, 0x10, 0x12}
            or 0x20 <= function <= 0x2F
            or 0x38 <= function <= 0x3F
        ):
            register = rd
    elif opcode == 0x01 and rt in {0x10, 0x11, 0x12, 0x13}:
        register = 31
    elif opcode == 0x03:
        register = 31
    elif 0x08 <= opcode <= 0x0F or opcode in {0x18, 0x19}:
        register = rt
    elif opcode in {0x10, 0x11, 0x12} and rs in {0x00, 0x01, 0x02}:
        register = rt
    elif opcode == 0x1C:
        register = rd
    elif opcode in _GPR_LOAD_OPCODES:
        register = rt
    return () if register in (None, 0) else (register,)


def _owner_function(functions: list[FunctionRecord], address: int,
                    starts: list[int] | None = None) -> int | None:
    starts = starts if starts is not None else [function.address for function in functions]
    index = bisect_right(starts, address) - 1
    if index < 0:
        return None
    function = functions[index]
    return function.address if function.contains(address) else None


def _reference(kind: str, from_address: int, to_address: int, word: int) -> dict[str, Any]:
    return {
        "kind": kind,
        "from_address": from_address,
        "to_address": to_address,
        "register": None,
        "disasm": disassemble_one(word, from_address),
    }

def _data_reference(from_address: int, to_address: int, word: int,
                    register: int, *, access: str, width: int) -> dict[str, Any]:
    return {
        "kind": "data",
        "access": access,
        "width": width,
        "from_address": from_address,
        "to_address": to_address,
        "register": REGISTERS[register],
        "disasm": disassemble_one(word, from_address),
    }


def _scan_strings(scopes: list[_Scope]) -> list[dict[str, Any]]:
    strings: list[dict[str, Any]] = []
    for scope in scopes:
        offset = 0
        body = scope.body
        while offset < len(body):
            run = _ascii_run_length(body, offset)
            if run >= MIN_STRING_BYTES:
                if offset + run < len(body) and body[offset + run] == 0:
                    strings.append({
                        "address": scope.vaddr + offset,
                        "value": body[offset:offset + run].decode("ascii"),
                        "length": run + 1,
                        "encoding": "ascii",
                    })
                    offset += run + 1
                else:
                    offset += run
                if len(strings) >= MAX_STRINGS:
                    return strings
                continue
            run = _utf16le_run_length(body, offset)
            if run >= MIN_STRING_BYTES * 2:
                if (
                    offset + run + 1 < len(body)
                    and body[offset + run:offset + run + 2] == b"\x00\x00"
                ):
                    strings.append({
                        "address": scope.vaddr + offset,
                        "value": body[offset:offset + run].decode("utf-16-le"),
                        "length": run + 2,
                        "encoding": "utf16le",
                    })
                    offset += run + 2
                else:
                    offset += run
                if len(strings) >= MAX_STRINGS:
                    return strings
                continue
            offset += 1
        if len(strings) >= MAX_STRINGS:
            return strings
    return strings


def _ascii_run_length(body: bytes, offset: int) -> int:
    run = 0
    while offset + run < len(body) and 0x20 <= body[offset + run] <= 0x7E:
        run += 1
    return run


def _utf16le_run_length(body: bytes, offset: int) -> int:
    chars = 0
    while offset + chars * 2 + 1 < len(body):
        low, high = body[offset + chars * 2], body[offset + chars * 2 + 1]
        if 0x20 <= low <= 0x7E and high == 0:
            chars += 1
        else:
            break
    return chars * 2


def _attach_evidence(elf: ElfFile, functions: list[FunctionRecord],
                     references: list[dict[str, Any]],
                     calls_by_function: Mapping[int, list[int]],
                     strings: list[dict[str, Any]]) -> None:
    strings_by_address = {int(entry["address"]): entry for entry in strings}
    function_starts = [function.address for function in functions]
    data_refs_by_function: dict[int, list[dict[str, Any]]] = {}
    for reference in references:
        if reference["kind"] != "data":
            continue
        owner = _owner_function(
            functions, int(reference["from_address"]), function_starts,
        )
        if owner is not None:
            data_refs_by_function.setdefault(owner, []).append(dict(reference))
    for function in functions:
        body = elf.read(function.address, function.size)
        instructions = []
        for offset in range(0, function.size - function.size % 4, 4):
            if len(instructions) >= MAX_INSTRUCTIONS_PER_FUNCTION:
                break
            word = int.from_bytes(body[offset:offset + 4], "little")
            pc = (function.address + offset) & 0xFFFFFFFF
            instructions.append({
                "address": pc,
                "word": word,
                "text": disassemble_one(word, pc),
            })
        function.evidence["sha256"] = hashlib.sha256(body).hexdigest()
        function.evidence["instructions"] = instructions
        function.evidence["calls"] = sorted(set(calls_by_function.get(function.address, ())))
        function.evidence["references"] = data_refs_by_function.get(function.address, [])
        hits = []
        for entry in data_refs_by_function.get(function.address, []):
            string_entry = strings_by_address.get(int(entry["to_address"]))
            if string_entry is not None:
                hits.append({"address": int(string_entry["address"]),
                             "value": string_entry["value"]})
        if hits:
            function.evidence["strings"] = hits
