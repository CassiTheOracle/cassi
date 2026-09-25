"""PCSX2 pipeline tests: static ISO cataloging, PINE framing, and snapshots.

All fixtures are synthetic: the ISO and ELF are built in memory from raw
structures, and the PINE server is a loopback TCP socket that speaks the exact
upstream PCSX2 PINE.cpp framing.
"""

from __future__ import annotations

import hashlib
import json
import socket
import struct
import threading
import unittest
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory

from pcsx2 import (
    ElfError,
    ElfFile,
    IsoError,
    PineClient,
    PineError,
    catalog_iso,
    compare_snapshots,
    disassemble_one,
    elf_word_xor_crc,
)
from pcsx2 import atlas as atlas_module
from pcsx2.atlas import (
    FunctionRecord,
    _Scope,
    _owner_function,
    _scan_references,
    _scan_strings,
)


# --------------------------------------------------------------------------
# ISO9660 fixtures


def directory_record(name: bytes, extent: int, size: int, *, is_dir: bool = False) -> bytes:
    record = bytearray(33 + len(name))
    record[0] = len(record)
    struct.pack_into("<I", record, 2, extent)
    struct.pack_into("<I", record, 10, size)
    if is_dir:
        record[25] = 0x02
    record[32] = len(name)
    record[33:33 + len(name)] = name
    return bytes(record)


def sector(body: bytes) -> bytes:
    return body + b"\x00" * (2048 - len(body))


def build_iso_bytes(cnf_text: bytes | None = None, boot_elf: bytes | None = None,
                    *, with_cnf: bool = True, boot_name: str = "SLUS_201.11;1",
                    boot_files: list[tuple[str, bytes]] | None = None,
                    corrupt_pvd: bool = False) -> bytes:
    if cnf_text is None:
        cnf_text = f"BOOT2 = cdrom0:\\{boot_name}\r\nVER = 1.10\r\n".encode("latin-1")
    if boot_elf is None:
        boot_elf = build_boot_elf()
    if boot_files is None:
        boot_files = [(boot_name, boot_elf)]
    root_extent, cnf_extent, first_boot_extent = 17, 18, 19
    self_record = directory_record(b"\x00", root_extent, 2048, is_dir=True)
    parent_record = directory_record(b"\x01", root_extent, 2048, is_dir=True)
    entries = [self_record, parent_record]
    if with_cnf:
        entries.append(directory_record(b"SYSTEM.CNF", cnf_extent, len(cnf_text)))
    for index, (name, body) in enumerate(boot_files):
        entries.append(directory_record(
            name.encode("latin-1"), first_boot_extent + index, len(body),
        ))
    root_dir = sector(b"".join(entries))

    pvd = bytearray(2048)
    pvd[0] = 1
    pvd[1:6] = b"CD001"
    pvd[6] = 1
    pvd[40:48] = b"TESTISO"
    pvd[156:156 + len(self_record)] = self_record
    if corrupt_pvd:
        pvd[1:6] = b"CD002"
    image: dict[int, bytes] = {16: bytes(pvd), 17: root_dir, 18: sector(cnf_text)}
    for index, (_name, body) in enumerate(boot_files):
        image[first_boot_extent + index] = sector(body)
    last = max(image)
    result = bytearray(b"\x00" * ((last + 1) * 2048))
    for index, blob in image.items():
        result[index * 2048:(index + 1) * 2048] = blob
    return bytes(result)


def write_iso(path: Path, **kwargs) -> Path:
    path.write_bytes(build_iso_bytes(**kwargs))
    return path


# --------------------------------------------------------------------------
# ELF fixtures


def elf_header(e_entry: int, e_shoff: int, image_size: int) -> bytes:
    header = bytearray(52)
    header[0:4] = b"\x7fELF"
    header[4] = 1  # ELFCLASS32
    header[5] = 1  # ELFDATA2LSB
    header[6] = 1  # EV_CURRENT
    struct.pack_into("<H", header, 16, 2)   # ET_EXEC
    struct.pack_into("<H", header, 18, 8)   # EM_MIPS
    struct.pack_into("<I", header, 20, 1)   # e_version
    struct.pack_into("<I", header, 24, e_entry)
    struct.pack_into("<I", header, 28, 52)  # e_phoff
    struct.pack_into("<I", header, 32, e_shoff)
    struct.pack_into("<I", header, 40, 52)  # e_ehsize
    struct.pack_into("<I", header, 42, 32)  # e_phentsize
    struct.pack_into("<H", header, 44, 1)   # e_phnum
    struct.pack_into("<H", header, 46, 40)  # e_shentsize
    struct.pack_into("<H", header, 48, 5)   # e_shnum
    struct.pack_into("<H", header, 50, 4)   # e_shstrndx
    return bytes(header)


def program_header(p_offset: int, p_vaddr: int, p_filesz: int, flags: int) -> bytes:
    return struct.pack("<8I", 1, p_offset, p_vaddr, p_vaddr, p_filesz,
                       p_filesz, flags, 16)


LUI_A0_0010 = 0x3C040010
ADDIU_A0_0200 = 0x24840200
JAL_00100100 = 0x0C040040
JR_RA = 0x03E00008
ADDIU_SP_MINUS8 = 0x27BDFFF8
ADDIU_SP_MINUS16 = 0x27BDFFF0
SW_RA_8_SP = 0xAFBF0008
ADDIU_SP_16 = 0x27BD0010
LUI_A0_0020 = 0x3C040020
SW_T0_8_A0 = 0xAC880008
ORI_A0_ZERO = 0x34040000
ADDIU_A0_8 = 0x24840008

BASE = 0x00100000
HELLO = "HELLO_CASSI"


def build_boot_elf() -> bytes:
    """A tiny MIPS image: entry calls a helper, references one string."""
    image = bytearray(0x548)

    def put(offset: int, *words: int) -> None:
        for index, word in enumerate(words):
            struct.pack_into("<I", image, offset + index * 4, word)

    put(0x100, LUI_A0_0010, ADDIU_A0_0200, JAL_00100100, JR_RA)
    put(0x140, ADDIU_SP_MINUS8, JR_RA)
    put(0x200, ADDIU_SP_MINUS16, SW_RA_8_SP, JR_RA, ADDIU_SP_16)
    image[0x300:0x300 + len(HELLO) + 1] = HELLO.encode("ascii") + b"\x00"

    strtab = b"\x00main\x00callee\x00"
    shstrtab = b"\x00.text\x00.symtab\x00.strtab\x00.shstrtab\x00"
    image[0x400:0x448] = struct.pack("<IIIBBH", 0, 0, 0, 0, 0, 0)
    image[0x410:0x420] = struct.pack("<IIIBBH", 1, BASE, 0x20, 0x12, 0, 1)
    image[0x420:0x430] = struct.pack("<IIIBBH", 6, BASE + 0x100, 0x18, 0x12, 0, 1)
    image[0x430:0x430 + len(strtab)] = strtab
    image[0x440:0x440 + len(shstrtab)] = shstrtab

    shoff = 0x480
    headers = [b"\x00" * 40]
    headers.append(struct.pack("<10I", 8, 1, 6, BASE, 0x100, 0x200, 0, 0, 4, 0))
    headers.append(struct.pack("<10I", 15, 2, 0, 0, 0x400, 0x30, 3, 0, 4, 16))
    headers.append(struct.pack("<10I", 23, 3, 0, 0, 0x430, len(strtab), 0, 0, 1, 0))
    headers.append(struct.pack("<10I", 30, 3, 0, 0, 0x440, len(shstrtab), 0, 0, 1, 0))
    section_table = b"".join(headers)
    image[shoff:shoff + len(section_table)] = section_table

    head = elf_header(BASE, shoff, len(image))
    load = program_header(0x100, BASE, len(image) - 0x100, 7)
    image[0:52] = head
    image[52:84] = load
    return bytes(image)


# --------------------------------------------------------------------------
# Fake PINE server speaking upstream PCSX2 PINE.cpp framing


class FakePineServer:
    def __init__(self, size: int = 0x20000) -> None:
        self.memory = bytearray(size)
        self.version = "v2.5.8-test"
        self.title = "Synthetic Game"
        self.game_id = "SLUS_20111"
        self.game_uuid = "63f6b523"
        self.game_version = "1.00"
        self.status = 0
        self.has_vm = True
        self.fail_next = False
        self.truncate_next = False
        self.extra_results = False
        self.drop_nul = False
        self.request_count = 0
        self.last_payload: bytes | None = None
        self.effects: list[tuple] = []
        self._listener = socket.socket()
        self._listener.bind(("127.0.0.1", 0))
        self._listener.listen(4)
        self.port = self._listener.getsockname()[1]
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5)
        self._listener.close()

    def __enter__(self) -> "FakePineServer":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def _run(self) -> None:
        self._listener.settimeout(0.2)
        while not self._stop.is_set():
            try:
                conn, _address = self._listener.accept()
            except (socket.timeout, TimeoutError, OSError):
                continue
            conn.settimeout(5)
            try:
                self._serve(conn)
            except OSError:
                pass
            finally:
                conn.close()

    def _serve(self, conn: socket.socket) -> None:
        while True:
            header = self._recv(conn, 4)
            if header is None:
                return
            size = int.from_bytes(header, "little")
            if size < 5:
                return
            payload = self._recv(conn, size - 4)
            if payload is None:
                return
            self.request_count += 1
            self.last_payload = payload
            if self.truncate_next:
                self.truncate_next = False
                conn.sendall(b"\x09\x00\x00")
                continue
            results = bytearray()
            failure = self._parse(payload, results)
            if self.extra_results and not failure:
                self.extra_results = False
                results += b"\x00\x00\x00\x00"
            total = len(results) + 5
            conn.sendall(struct.pack("<I", total) + bytes([failure]) + bytes(results))

    @staticmethod
    def _recv(conn: socket.socket, count: int) -> bytes | None:
        chunks = bytearray()
        while len(chunks) < count:
            block = conn.recv(count - len(chunks))
            if not block:
                if not chunks:
                    return None
                raise OSError("partial frame")
            chunks += block
        return bytes(chunks)

    def _parse(self, payload: bytes, results: bytearray) -> int:
        if self.fail_next:
            self.fail_next = False
            return 0xFF
        cursor = 0
        while cursor < len(payload):
            opcode = payload[cursor]
            cursor += 1
            if not self.has_vm and opcode != 0x08 and opcode != 0x0F:
                return 0xFF
            if opcode in (0x00, 0x01, 0x02, 0x03):
                width = (1, 2, 4, 8)[opcode]
                address = int.from_bytes(payload[cursor:cursor + 4], "little")
                cursor += 4
                if address + width > len(self.memory):
                    return 0xFF
                results += self.memory[address:address + width]
            elif opcode in (0x04, 0x05, 0x06, 0x07):
                width = (1, 2, 4, 8)[opcode - 0x04]
                address = int.from_bytes(payload[cursor:cursor + 4], "little")
                cursor += 4
                value = payload[cursor:cursor + width]
                cursor += width
                if address + width > len(self.memory):
                    return 0xFF
                self.memory[address:address + width] = value
                self.effects.append(("write", address, bytes(value)))
            elif opcode == 0x08:
                raw = f"PCSX2 {self.version}\x00".encode("utf-8")
                results += struct.pack("<I", len(raw)) + raw
            elif opcode in (0x09, 0x0A):
                slot = payload[cursor]
                cursor += 1
                self.effects.append(("save-state" if opcode == 0x09 else "load-state", slot))
            elif opcode in (0x0B, 0x0C, 0x0D, 0x0E):
                text = {0x0B: self.title, 0x0C: self.game_id, 0x0D: self.game_uuid,
                        0x0E: self.game_version}[opcode]
                raw = text.encode("utf-8")
                if self.drop_nul:
                    self.drop_nul = False
                    results += struct.pack("<I", len(raw)) + raw
                else:
                    results += struct.pack("<I", len(raw) + 1) + raw + b"\x00"
            elif opcode == 0x0F:
                results += struct.pack("<I", self.status)
            else:
                return 0xFF
        return 0x00


# --------------------------------------------------------------------------
# Static catalog tests


class CatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.output = Path(self._tmp.name)
        self.elf_bytes = build_boot_elf()

    def catalog(self, **iso_kwargs):
        iso_path = write_iso(self.output / "game.iso", **iso_kwargs)
        out_dir = self.output / "catalog"
        atlas = catalog_iso(iso_path, out_dir)
        return atlas, iso_path, out_dir

    def test_synthetic_iso_catalogs_functions_calls_and_strings(self) -> None:
        atlas, iso_path, out_dir = self.catalog()
        self.assertGreater(len(atlas.functions), 0)
        names = {function.name for function in atlas.functions}
        self.assertIn("main", names)
        self.assertIn("callee", names)
        self.assertIn("prologue", " ".join(names))
        calls = [reference for reference in atlas.references if reference["kind"] == "call"]
        self.assertTrue(calls)
        self.assertEqual(atlas.callees_of(BASE), (BASE + 0x100,))
        self.assertEqual(atlas.callers_of(BASE + 0x100), (BASE,))
        nearby = atlas.references_near_address(BASE + 0x200)
        self.assertTrue(any(reference["kind"] == "data" for reference in nearby))
        self.assertEqual(
            atlas.references_to_address(BASE + 0x200),
            [reference for reference in nearby if reference["to_address"] == BASE + 0x200],
        )
        strings = {entry["value"] for entry in atlas.strings}
        self.assertIn(HELLO, strings)
        covered = atlas.strings_near(BASE + 0x200)
        self.assertTrue(covered)
        function = atlas.symbol_at(BASE)
        self.assertIsNotNone(function)
        self.assertIn("calls", function.evidence)
        self.assertEqual(atlas.call_graph()[f"0x{BASE:08x}"], [f"0x{BASE + 0x100:08x}"])
        self.assertTrue(atlas.sym_text)
        identity = atlas.identity
        self.assertEqual(identity["serial"], "SLUS_201.11")
        self.assertEqual(identity["version"], "1.10")
        self.assertEqual(identity["entry"], BASE)
        self.assertEqual(identity["title"], "TESTISO")
        self.assertEqual(identity["machine"], "mips/r5900")
        self.assertEqual(identity["pcsx2_crc"], f"{elf_word_xor_crc(self.elf_bytes):08x}")
        self.assertEqual(identity["elf_sha256"], hashlib.sha256(self.elf_bytes).hexdigest())
        atlas_paths = atlas.summary()["paths"]
        self.assertTrue(Path(atlas_paths["atlas"]).is_file())
        self.assertTrue(Path(atlas_paths["sym"]).is_file())

    def test_reference_cap_preserves_discovered_call_edges(self) -> None:
        with patch("pcsx2.atlas.MAX_REFERENCES", 2):
            atlas, _iso_path, _out_dir = self.catalog()
        self.assertEqual(len(atlas.references), 2)
        self.assertEqual(atlas.callees_of(BASE), (BASE + 0x100,))

    def test_load_store_reference_uses_live_lui_base(self) -> None:
        body = bytearray(build_boot_elf())
        struct.pack_into("<4I", body, 0x100, LUI_A0_0020, SW_T0_8_A0, JR_RA, 0)
        atlas, _iso_path, _out_dir = self.catalog(boot_elf=bytes(body))
        references = [
            row for row in atlas.references_to_address(0x00200008)
            if row["kind"] == "data"
        ]
        self.assertTrue(any(
            row["from_address"] == BASE + 4
            and row["disasm"] == "sw $t0, 0x0008($a0)"
            for row in references
        ))

    def test_control_flow_join_drops_unreachable_address_state(self) -> None:
        body = struct.pack(
            "<6I",
            0x10000004,  # beq $zero, $zero, 0x1014
            0,
            LUI_A0_0020,  # unreachable fallthrough
            0,
            0,
            SW_T0_8_A0,
        )
        scope = _Scope(0x1000, 0x1018, body, True)
        functions = [FunctionRecord(0x1000, 0x18, "entry", "symbol")]
        references, _calls = _scan_references([scope], functions)
        self.assertFalse(any(
            row["kind"] == "data" and row["to_address"] == 0x00200008
            for row in references
        ))

    def test_regimm_link_discovers_function_and_call_edge(self) -> None:
        body = bytearray(build_boot_elf())
        target = BASE + 0x80
        immediate = ((target - (BASE + 4)) >> 2) & 0xFFFF
        bgezal = (0x01 << 26) | (0x11 << 16) | immediate
        struct.pack_into("<4I", body, 0x100, bgezal, 0, JR_RA, 0)
        struct.pack_into("<2I", body, 0x180, JR_RA, 0)
        atlas, _iso_path, _out_dir = self.catalog(boot_elf=bytes(body))
        target_record = next(
            function for function in atlas.functions if function.address == target
        )
        self.assertEqual(target_record.source, "jal-target")
        self.assertIn(target, atlas.callees_of(BASE))
        self.assertIn(BASE, atlas.callers_of(target))
        self.assertTrue(any(
            row["kind"] == "call"
            and row["from_address"] == BASE
            and row["to_address"] == target
            and row["disasm"] == "bgezal $zero, 0x00100080"
            for row in atlas.references
        ))

    def test_register_overwrite_invalidates_lui_reference(self) -> None:
        body = bytearray(build_boot_elf())
        struct.pack_into(
            "<4I", body, 0x100,
            LUI_A0_0020, ORI_A0_ZERO, ADDIU_A0_8, JR_RA,
        )
        atlas, _iso_path, _out_dir = self.catalog(boot_elf=bytes(body))
        self.assertEqual(atlas.references_to_address(0x00200008), [])

    def test_function_owner_uses_half_open_boundaries(self) -> None:
        functions = [
            FunctionRecord(0x1000, 0x10, "first", "symbol"),
            FunctionRecord(0x1010, 0x10, "second", "symbol"),
        ]
        starts = [function.address for function in functions]
        self.assertIsNone(_owner_function(functions, 0x0FFF, starts))
        self.assertEqual(_owner_function(functions, 0x100F, starts), 0x1000)
        self.assertEqual(_owner_function(functions, 0x1010, starts), 0x1010)
        self.assertIsNone(_owner_function(functions, 0x1020, starts))

    def test_unterminated_printable_runs_are_scanned_once(self) -> None:
        ascii_scope = _Scope(0x1000, 0x1000 + 100_000, b"A" * 100_000, False)
        with patch(
            "pcsx2.atlas._ascii_run_length",
            wraps=atlas_module._ascii_run_length,
        ) as ascii_scan:
            self.assertEqual(_scan_strings([ascii_scope]), [])
        self.assertEqual(ascii_scan.call_count, 1)

        utf_body = b"A\x00" * 50_000
        utf_scope = _Scope(0x2000, 0x2000 + len(utf_body), utf_body, False)
        with patch(
            "pcsx2.atlas._utf16le_run_length",
            wraps=atlas_module._utf16le_run_length,
        ) as utf_scan:
            self.assertEqual(_scan_strings([utf_scope]), [])
        self.assertEqual(utf_scan.call_count, 1)

    def test_sym_export_shape(self) -> None:
        atlas, _iso_path, out_dir = self.catalog()
        sym_path = Path(atlas.sym_path)
        lines = sym_path.read_text("ascii").splitlines()
        self.assertEqual(lines[0], "00100000 main,40")
        self.assertTrue(any(line.startswith("00100100 callee,") for line in lines))
        for line in lines:
            self.assertRegex(line, r"^[0-9a-f]{8} [A-Za-z0-9_.+-]+(,[0-9a-f]+)?$")


    def test_windows_device_serial_uses_a_regular_artifact_name(self) -> None:
        atlas, _iso_path, _out_dir = self.catalog(boot_name="CON;1")
        self.assertEqual(Path(atlas.atlas_path).name, "_CON.atlas.json")
        self.assertEqual(Path(atlas.sym_path).name, "_CON.sym")
    def test_catalog_is_deterministic(self) -> None:
        first = self.catalog()[0]
        second, _iso, _out = self.catalog()
        first_paths = first.summary()["paths"]
        self.assertEqual(
            Path(first_paths["atlas"]).read_bytes(),
            Path(second.atlas_path).read_bytes())
        self.assertEqual(
            Path(first_paths["sym"]).read_bytes(),
            Path(second.sym_path).read_bytes())
        self.assertEqual(first.summary(), second.summary())

    def test_catalog_rejects_missing_iso(self) -> None:
        with self.assertRaises(IsoError):
            catalog_iso(self.output / "absent.iso", self.output / "out")

    def test_corrupt_pvd_is_refused(self) -> None:
        with self.assertRaises(IsoError):
            self.catalog(corrupt_pvd=True)

    def test_missing_system_cnf_is_refused(self) -> None:
        with self.assertRaises(IsoError):
            self.catalog(with_cnf=False)

    def test_bootless_system_cnf_is_refused(self) -> None:
        with self.assertRaises(IsoError):
            self.catalog(cnf_text=b"VER = 1.10\r\n")

    def test_boot_path_resolves_strictly(self) -> None:
        with self.assertRaises(IsoError):
            self.catalog(cnf_text=b"BOOT2 = cdrom0:\\ABSENT.ELF;1\r\nVER = 1.10\r\n")

    def test_explicit_boot_version_selects_the_exact_iso_entry(self) -> None:
        version_one = bytearray(build_boot_elf())
        version_one[0x350] = 1
        version_two = bytearray(build_boot_elf())
        version_two[0x350] = 2
        boot_files = [
            ("SLUS_201.11;1", bytes(version_one)),
            ("SLUS_201.11;2", bytes(version_two)),
        ]
        atlas, _iso_path, _out_dir = self.catalog(
            cnf_text=b"BOOT2 = cdrom0:\\SLUS_201.11;2\r\nVER = 1.10\r\n",
            boot_files=boot_files,
        )
        self.assertEqual(
            atlas.identity["elf_sha256"],
            hashlib.sha256(version_two).hexdigest(),
        )
        with self.assertRaises(IsoError):
            self.catalog(
                cnf_text=b"BOOT2 = cdrom0:\\SLUS_201.11;3\r\nVER = 1.10\r\n",
                boot_files=boot_files,
            )

    def test_boot_file_must_carry_elf_magic(self) -> None:
        with self.assertRaises(IsoError):
            self.catalog(boot_elf=b"\x00" * 64)


class ElfTests(unittest.TestCase):
    def test_elf_parser_maps_reads(self) -> None:
        elf = ElfFile(build_boot_elf())
        self.assertEqual(elf.entry, BASE)
        self.assertEqual(elf.read(BASE, 4)[0], LUI_A0_0010 & 0xFF)
        body = elf.read(BASE + 0x200, len(HELLO))
        self.assertEqual(body, HELLO.encode("ascii"))

    def test_elf_without_section_table_uses_loadable_segments(self) -> None:
        body = bytearray(build_boot_elf())
        struct.pack_into("<I", body, 32, 0)
        struct.pack_into("<H", body, 46, 0)
        struct.pack_into("<H", body, 48, 0)
        struct.pack_into("<H", body, 50, 0)
        elf = ElfFile(bytes(body))
        self.assertEqual(elf.sections, ())
        self.assertEqual(elf.read(BASE, 4), struct.pack("<I", LUI_A0_0010))

    def test_nobits_section_has_no_file_extent(self) -> None:
        body = bytearray(build_boot_elf())
        struct.pack_into(
            "<10I", body, 0x480,
            0, 8, 3, BASE + 0x1000, len(body) + 0x100, 0x1000, 0, 0, 16, 0,
        )
        elf = ElfFile(bytes(body))
        self.assertEqual(elf.sections[0].type, 8)
        self.assertEqual(elf.sections[0].size, 0x1000)

    def test_nonload_program_header_is_not_mapped(self) -> None:
        body = bytearray(build_boot_elf())
        struct.pack_into("<I", body, 52, 4)
        elf = ElfFile(bytes(body))
        self.assertEqual(elf.segments, ())
        self.assertEqual(elf.executable_segments, ())
        with self.assertRaises(ElfError):
            elf.read(BASE, 4)

    def test_malformed_elf_is_refused(self) -> None:
        base = bytearray(build_boot_elf())
        wrong_magic = bytes(bytearray(base)[:4] + bytearray(b"ELF\x7f") + bytes(base[8:]))
        with self.assertRaises(ElfError):
            ElfFile(wrong_magic)
        sixty_four = bytearray(base)
        sixty_four[4] = 2
        with self.assertRaises(ElfError):
            ElfFile(bytes(sixty_four))
        big_endian = bytearray(base)
        big_endian[5] = 2
        with self.assertRaises(ElfError):
            ElfFile(bytes(big_endian))
        arm = bytearray(base)
        struct.pack_into("<H", arm, 18, 40)
        with self.assertRaises(ElfError):
            ElfFile(bytes(arm))
        truncated = bytes(base[:100])
        with self.assertRaises(ElfError):
            ElfFile(truncated)
        bad_entsize = bytearray(base)
        struct.pack_into("<I", bad_entsize, 0x4D0 + 36, 24)
        with self.assertRaises(ElfError):
            ElfFile(bytes(bad_entsize))

    def test_crc_is_word_xor(self) -> None:
        body = build_boot_elf()
        value = 0
        for offset in range(0, len(body) - len(body) % 4, 4):
            value ^= int.from_bytes(body[offset:offset + 4], "little")
        self.assertEqual(elf_word_xor_crc(body), value & 0xFFFFFFFF)


# --------------------------------------------------------------------------
# PINE protocol tests


class PineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = FakePineServer()
        self.addCleanup(self.server.close)
        self.server.memory[0x00:0x08] = bytes.fromhex("0102030405060708")
        self.server.memory[0x100:0x110] = b"\x11" * 16

    def client(self, **kwargs) -> PineClient:
        return PineClient(host="127.0.0.1", slot=self.server.port, timeout=2.0, **kwargs)

    def test_read_widths(self) -> None:
        with self.client() as client:
            self.assertEqual(client.read8(0x00), 0x01)
            self.assertEqual(client.read16(0x00), 0x0201)
            self.assertEqual(client.read32(0x00), 0x04030201)
            self.assertEqual(client.read64(0x00), 0x0807060504030201)

    def test_exact_request_framing(self) -> None:
        with self.client() as client:
            client.read32(0x100)
        self.assertEqual(self.server.request_count, 1)
        self.assertEqual(self.server.last_payload, b"\x02\x00\x01\x00\x00")

    def test_chunked_read_matches_memory(self) -> None:
        for offset in range(0, len(self.server.memory), 256):
            self.server.memory[offset] = (offset >> 8) & 0xFF
        expected = bytes(self.server.memory)
        with self.client() as client:
            body = client.read(0, len(expected))
        self.assertEqual(body, expected)
        self.assertGreater(self.server.request_count, 1)

    def test_read_bounds(self) -> None:
        with self.client() as client:
            with self.assertRaises(PineError):
                client.read(0xFFFFFFFE, 8)
            with self.assertRaises(PineError):
                client.read(0x10000000, 8)
            with self.assertRaises(PineError):
                client.read(0, (1 << 20) + 1)
            with self.assertRaises(PineError):
                client.read8(-1)
            with self.assertRaises(PineError):
                client.read16(0xFFFFFFFF)
            with self.assertRaises(PineError):
                client.read32(0xFFFFFFFD)
            with self.assertRaises(PineError):
                client.read64(0xFFFFFFF9)
        self.assertEqual(self.client().read(0, 0), b"")

    def test_read_only_client_denies_effects(self) -> None:
        with self.client() as client:
            with self.assertRaises(PineError):
                client.write(0x10, b"\x42")
            with self.assertRaises(PineError):
                client.save_state(0)
            with self.assertRaises(PineError):
                client.load_state(0)
        self.assertEqual(self.server.effects, [])
        self.assertEqual(self.server.memory[0x10], 0)

    def test_effect_client_writes_and_states(self) -> None:
        with self.client(allow_effects=True) as client:
            client.write(0x10, b"\x42")
            client.write(0x14, struct.pack("<I", 0xDEADBEEF))
            client.save_state(1)
            client.load_state(1)
        self.assertEqual(self.server.memory[0x10], 0x42)
        self.assertEqual(int.from_bytes(self.server.memory[0x14:0x18], "little"), 0xDEADBEEF)
        self.assertIn(("write", 0x10, b"\x42"), self.server.effects)
        self.assertIn(("save-state", 1), self.server.effects)
        self.assertIn(("load-state", 1), self.server.effects)

    def test_fail_status_raises(self) -> None:
        self.server.fail_next = True
        with self.client() as client:
            with self.assertRaises(PineError):
                client.read8(0)

    def test_truncated_reply_raises(self) -> None:
        self.server.truncate_next = True
        with self.client() as client:
            with self.assertRaises(PineError):
                client.read8(0)

    def test_extra_trailing_results_raise(self) -> None:
        self.server.extra_results = True
        with self.client() as client:
            with self.assertRaises(PineError):
                client.read8(0)

    def test_string_without_nul_raises(self) -> None:
        self.server.drop_nul = True
        with self.client() as client:
            with self.assertRaises(PineError):
                client.title()

    def test_identity_reports_running_game(self) -> None:
        with self.client() as client:
            identity = client.identity()
        self.assertEqual(identity["emulator"], "pcsx2")
        self.assertEqual(identity["version"], "PCSX2 v2.5.8-test")
        self.assertEqual(identity["title"], "Synthetic Game")
        self.assertEqual(identity["game_id"], "SLUS_20111")
        self.assertEqual(identity["game_uuid"], "63f6b523")
        self.assertEqual(identity["game_version"], "1.00")
        self.assertEqual(identity["status"], 0)
        self.assertEqual(identity["status_name"], "running")

    def test_identity_without_vm_keeps_version_and_status(self) -> None:
        self.server.has_vm = False
        self.server.status = 2
        with self.client() as client:
            identity = client.identity()
        self.assertEqual(identity["version"], "PCSX2 v2.5.8-test")
        self.assertEqual(identity["status"], 2)
        self.assertEqual(identity["status_name"], "shutdown")
        self.assertIsNone(identity["title"])
        self.assertIsNone(identity["game_id"])
        self.assertIsNone(identity["game_uuid"])
        self.assertIsNone(identity["game_version"])

    def test_version_string_matches_upstream_format(self) -> None:
        with self.client() as client:
            self.assertEqual(client.version(), "PCSX2 v2.5.8-test")


# --------------------------------------------------------------------------
# Snapshot tests


class SnapshotTests(unittest.TestCase):
    def test_exact_changed_ranges_and_pages(self) -> None:
        before = bytes(range(256)) * 32
        after = bytearray(before)
        after[10:12] = b"\xff\xfe"
        after[4200:4204] = b"\x11\x22\x33\x44"
        result = compare_snapshots(before, bytes(after), base_address=0x00100000)
        self.assertEqual(result["base_address"], 0x00100000)
        self.assertEqual(result["page_size"], 4096)
        self.assertEqual(result["changed_byte_count"], 6)
        ranges = result["changed_ranges"]
        self.assertEqual(ranges[0]["start"], 0x0010000A)
        self.assertEqual(ranges[0]["end"], 0x0010000C)
        self.assertEqual(bytes.fromhex(ranges[0]["bytes_before"]), before[10:12])
        self.assertEqual(bytes.fromhex(ranges[0]["bytes_after"]), b"\xff\xfe")
        self.assertEqual(ranges[1]["start"], 0x00101068)
        self.assertEqual(ranges[1]["end"], 0x0010106C)
        pages = result["changed_pages"]
        self.assertEqual([page["page"] for page in pages], [0, 1])
        self.assertEqual(pages[0]["start"], 0x00100000)
        self.assertEqual(pages[1]["end"], 0x00102000)

    def test_adjacent_changes_merge(self) -> None:
        before = b"\x00" * 8
        after = b"\xff" * 8
        result = compare_snapshots(before, after, base_address=0)
        self.assertEqual(len(result["changed_ranges"]), 1)
        self.assertEqual(result["changed_ranges"][0]["start"], 0)
        self.assertEqual(result["changed_ranges"][0]["end"], 8)

    def test_contiguous_change_includes_every_interior_page(self) -> None:
        before = b"\x00" * (3 * 4096)
        after = b"\xff" * len(before)
        result = compare_snapshots(before, after, base_address=0x2000)
        self.assertEqual(
            [page["page"] for page in result["changed_pages"]],
            [0, 1, 2],
        )

    def test_no_change_is_empty(self) -> None:
        result = compare_snapshots(b"abc", b"abc", base_address=0x100)
        self.assertEqual(result["changed_ranges"], [])
        self.assertEqual(result["changed_pages"], [])
        self.assertEqual(result["changed_byte_count"], 0)

    def test_length_mismatch_raises(self) -> None:
        with self.assertRaises(ValueError):
            compare_snapshots(b"abc", b"abcd", base_address=0)

    def test_bad_page_size_raises(self) -> None:
        with self.assertRaises(ValueError):
            compare_snapshots(b"abc", b"abc", base_address=0, page_size=0)


class DisassemblerTests(unittest.TestCase):
    def test_known_encodings(self) -> None:
        self.assertEqual(disassemble_one(0, 0), "nop")
        self.assertEqual(disassemble_one(0x27BDFFF0, 0x100000),
                         "addiu $sp, $sp, -0x0010")
        self.assertEqual(disassemble_one(0x0C040040, 0x100008), "jal 0x00100100")
        self.assertEqual(disassemble_one(0x03E00008, 0x10000C), "jr $ra")
        self.assertEqual(disassemble_one(0x3C040010, 0x100000), "lui $a0, 0x0010")
        self.assertEqual(disassemble_one(0x24840200, 0x100004),
                         "addiu $a0, $a0, 0x0200")
        self.assertEqual(disassemble_one(0x8FA40010, 0x100000), "lw $a0, 0x0010($sp)")
        self.assertEqual(
            disassemble_one((0x1C << 26) | (4 << 21) | (5 << 16) | (2 << 11), 0),
            "madd $v0, $a0, $a1",
        )
        self.assertEqual(
            disassemble_one((0x1C << 26) | (8 << 21) | (9 << 16) | (3 << 11) | 0x21, 0),
            "maddu1 $v1, $t0, $t1",
        )
        self.assertEqual(
            disassemble_one(0x0080882D, 0x00285DC0),
            "daddu $s1, $a0, $zero",
        )
        self.assertEqual(
            disassemble_one(0xFFBF0020, 0x0028CD10),
            "sd $ra, 0x0020($sp)",
        )


if __name__ == "__main__":
    unittest.main()
