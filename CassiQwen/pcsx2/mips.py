"""Minimal MIPS/R5900 disassembly evidence for the PS2 catalog pipeline.

This is deliberately a small stdlib-only decoder: it is not a full
disassembler, it produces exactly the evidence the atlas needs (calls,
branches, address materialization, and readable instruction text).
"""

from __future__ import annotations

from typing import Iterator


REGISTERS = (
    "$zero", "$at", "$v0", "$v1", "$a0", "$a1", "$a2", "$a3",
    "$t0", "$t1", "$t2", "$t3", "$t4", "$t5", "$t6", "$t7",
    "$s0", "$s1", "$s2", "$s3", "$s4", "$s5", "$s6", "$s7",
    "$t8", "$t9", "$k0", "$k1", "$gp", "$sp", "$fp", "$ra",
)


def _r(index: int) -> str:
    return REGISTERS[index]


def _imm(imm: int) -> str:
    """Render a signed 16-bit immediate without an ambiguous sign."""
    if imm >= 0:
        return f"0x{imm:04x}"
    return f"-0x{(0x10000 - imm) & 0xFFFF:04x}"


def _branch_target(pc: int, imm: int) -> int:
    return (pc + 4 + (imm << 2)) & 0xFFFFFFFF


def _jump_target(pc: int, word: int) -> int:
    return ((pc + 4) & 0xF0000000) | ((word & 0x03FFFFFF) << 2)


def disassemble_one(word: int, pc: int) -> str:
    """Decode a single little-endian MIPS/R5900 word into evidence text."""
    if word == 0:
        return "nop"
    op = word >> 26
    rs = (word >> 21) & 31
    rt = (word >> 16) & 31
    rd = (word >> 11) & 31
    sa = (word >> 6) & 31
    funct = word & 63
    imm = word & 0xFFFF
    simm = imm - 0x10000 if imm >= 0x8000 else imm

    if op == 0x00:  # SPECIAL
        if funct == 0x00:
            if word == 0:
                return "nop"
            return f"sll {_r(rd)}, {_r(rt)}, {sa}"
        if funct == 0x02:
            return f"srl {_r(rd)}, {_r(rt)}, {sa}"
        if funct == 0x03:
            return f"sra {_r(rd)}, {_r(rt)}, {sa}"
        if funct == 0x04:
            return f"sllv {_r(rd)}, {_r(rt)}, {_r(rs)}"
        if funct == 0x06:
            return f"srlv {_r(rd)}, {_r(rt)}, {_r(rs)}"
        if funct == 0x07:
            return f"srav {_r(rd)}, {_r(rt)}, {_r(rs)}"
        if funct == 0x14:
            return f"dsllv {_r(rd)}, {_r(rt)}, {_r(rs)}"
        if funct == 0x16:
            return f"dsrlv {_r(rd)}, {_r(rt)}, {_r(rs)}"
        if funct == 0x17:
            return f"dsrav {_r(rd)}, {_r(rt)}, {_r(rs)}"
        if funct == 0x08:
            return f"jr {_r(rs)}"
        if funct == 0x09:
            return f"jalr {_r(rd)}, {_r(rs)}"
        if funct == 0x0C:
            return "syscall"
        if funct == 0x0D:
            return "break"
        if funct == 0x10:
            return f"mfhi {_r(rd)}"
        if funct == 0x11:
            return f"mthi {_r(rs)}"
        if funct == 0x12:
            return f"mflo {_r(rd)}"
        if funct == 0x13:
            return f"mtlo {_r(rs)}"
        if funct == 0x18:
            return f"mult {_r(rs)}, {_r(rt)}"
        if funct == 0x19:
            return f"multu {_r(rs)}, {_r(rt)}"
        if funct == 0x1A:
            return f"div {_r(rs)}, {_r(rt)}"
        if funct == 0x1B:
            return f"divu {_r(rs)}, {_r(rt)}"
        if funct == 0x20:
            return f"add {_r(rd)}, {_r(rs)}, {_r(rt)}"
        if funct == 0x21:
            return f"addu {_r(rd)}, {_r(rs)}, {_r(rt)}"
        if funct == 0x22:
            return f"sub {_r(rd)}, {_r(rs)}, {_r(rt)}"
        if funct == 0x23:
            return f"subu {_r(rd)}, {_r(rs)}, {_r(rt)}"
        if funct == 0x2C:
            return f"dadd {_r(rd)}, {_r(rs)}, {_r(rt)}"
        if funct == 0x2D:
            return f"daddu {_r(rd)}, {_r(rs)}, {_r(rt)}"
        if funct == 0x2E:
            return f"dsub {_r(rd)}, {_r(rs)}, {_r(rt)}"
        if funct == 0x2F:
            return f"dsubu {_r(rd)}, {_r(rs)}, {_r(rt)}"
        if funct == 0x24:
            return f"and {_r(rd)}, {_r(rs)}, {_r(rt)}"
        if funct == 0x25:
            return f"or {_r(rd)}, {_r(rs)}, {_r(rt)}"
        if funct == 0x26:
            return f"xor {_r(rd)}, {_r(rs)}, {_r(rt)}"
        if funct == 0x27:
            return f"nor {_r(rd)}, {_r(rs)}, {_r(rt)}"
        if funct == 0x2A:
            return f"slt {_r(rd)}, {_r(rs)}, {_r(rt)}"
        if funct == 0x2B:
            return f"sltu {_r(rd)}, {_r(rs)}, {_r(rt)}"
        if funct == 0x0A:
            return f"movz {_r(rd)}, {_r(rs)}, {_r(rt)}"
        if funct == 0x0B:
            return f"movn {_r(rd)}, {_r(rs)}, {_r(rt)}"
        if funct == 0x38:
            return f"dsll {_r(rd)}, {_r(rt)}, {sa}"
        if funct == 0x3A:
            return f"dsrl {_r(rd)}, {_r(rt)}, {sa}"
        if funct == 0x3B:
            return f"dsra {_r(rd)}, {_r(rt)}, {sa}"
        if funct == 0x3C:
            return f"dsll32 {_r(rd)}, {_r(rt)}, {sa}"
        if funct == 0x3E:
            return f"dsrl32 {_r(rd)}, {_r(rt)}, {sa}"
        if funct == 0x3F:
            return f"dsra32 {_r(rd)}, {_r(rt)}, {sa}"
        return f".word 0x{word:08x}"
    if op == 0x01:  # REGIMM
        if rt == 0x00:
            return f"bltz {_r(rs)}, {_branch_target(pc, simm):#010x}"
        if rt == 0x01:
            return f"bgez {_r(rs)}, {_branch_target(pc, simm):#010x}"
        if rt == 0x02:
            return f"bltzl {_r(rs)}, {_branch_target(pc, simm):#010x}"
        if rt == 0x03:
            return f"bgezl {_r(rs)}, {_branch_target(pc, simm):#010x}"
        if rt == 0x10:
            return f"bltzal {_r(rs)}, {_branch_target(pc, simm):#010x}"
        if rt == 0x11:
            return f"bgezal {_r(rs)}, {_branch_target(pc, simm):#010x}"
        if rt == 0x12:
            return f"bltzall {_r(rs)}, {_branch_target(pc, simm):#010x}"
        if rt == 0x13:
            return f"bgezall {_r(rs)}, {_branch_target(pc, simm):#010x}"
        return f".word 0x{word:08x}"
    if op == 0x02:
        return f"j {_jump_target(pc, word):#010x}"
    if op == 0x03:
        return f"jal {_jump_target(pc, word):#010x}"
    if op == 0x04:
        return f"beq {_r(rs)}, {_r(rt)}, {_branch_target(pc, simm):#010x}"
    if op == 0x05:
        return f"bne {_r(rs)}, {_r(rt)}, {_branch_target(pc, simm):#010x}"
    if op == 0x06:
        return f"blez {_r(rs)}, {_branch_target(pc, simm):#010x}"
    if op == 0x07:
        return f"bgtz {_r(rs)}, {_branch_target(pc, simm):#010x}"
    if op == 0x08:
        return f"addi {_r(rt)}, {_r(rs)}, {_imm(simm)}"
    if op == 0x09:
        return f"addiu {_r(rt)}, {_r(rs)}, {_imm(simm)}"
    if op == 0x18:
        return f"daddi {_r(rt)}, {_r(rs)}, {_imm(simm)}"
    if op == 0x19:
        return f"daddiu {_r(rt)}, {_r(rs)}, {_imm(simm)}"
    if op == 0x0A:
        return f"slti {_r(rt)}, {_r(rs)}, {_imm(simm)}"
    if op == 0x0B:
        return f"sltiu {_r(rt)}, {_r(rs)}, {_imm(simm)}"
    if op == 0x0C:
        return f"andi {_r(rt)}, {_r(rs)}, 0x{imm:04x}"
    if op == 0x0D:
        return f"ori {_r(rt)}, {_r(rs)}, 0x{imm:04x}"
    if op == 0x0E:
        return f"xori {_r(rt)}, {_r(rs)}, 0x{imm:04x}"
    if op == 0x0F:
        return f"lui {_r(rt)}, 0x{imm:04x}"
    if op == 0x10:
        if rs == 0x00:
            return f"mfc0 {_r(rt)}, ${rd}"
        if rs == 0x04:
            return f"mtc0 {_r(rt)}, ${rd}"
        return f".word 0x{word:08x}"
    if op == 0x11:
        if rs == 0x00:
            return f"mfc1 {_f(rt)}, {_f(rd)}"
        if rs == 0x04:
            return f"mtc1 {_f(rt)}, {_f(rd)}"
        return f".word 0x{word:08x}"
    if op == 0x14:
        return f"beql {_r(rs)}, {_r(rt)}, {_branch_target(pc, simm):#010x}"
    if op == 0x15:
        return f"bnel {_r(rs)}, {_r(rt)}, {_branch_target(pc, simm):#010x}"
    if op == 0x16:
        return f"blezl {_r(rs)}, {_branch_target(pc, simm):#010x}"
    if op == 0x17:
        return f"bgtzl {_r(rs)}, {_branch_target(pc, simm):#010x}"
    if op == 0x1C:  # R5900 MMI opcode space
        scalar = {
            0x00: "madd",
            0x01: "maddu",
            0x20: "madd1",
            0x21: "maddu1",
        }.get(funct)
        if scalar is not None:
            return f"{scalar} {_r(rd)}, {_r(rs)}, {_r(rt)}"
        return f".word 0x{word:08x}"
    if op == 0x1A:
        return f"ldl {_r(rt)}, {_imm(simm)}({_r(rs)})"
    if op == 0x1B:
        return f"ldr {_r(rt)}, {_imm(simm)}({_r(rs)})"
    if op == 0x1E:
        return f"lq {_r(rt)}, {_imm(simm)}({_r(rs)})"
    if op == 0x1F:
        return f"sq {_r(rt)}, {_imm(simm)}({_r(rs)})"
    if op == 0x20:
        return f"lb {_r(rt)}, {_imm(simm)}({_r(rs)})"
    if op == 0x21:
        return f"lh {_r(rt)}, {_imm(simm)}({_r(rs)})"
    if op == 0x22:
        return f"lwl {_r(rt)}, {_imm(simm)}({_r(rs)})"
    if op == 0x23:
        return f"lw {_r(rt)}, {_imm(simm)}({_r(rs)})"
    if op == 0x24:
        return f"lbu {_r(rt)}, {_imm(simm)}({_r(rs)})"
    if op == 0x25:
        return f"lhu {_r(rt)}, {_imm(simm)}({_r(rs)})"
    if op == 0x26:
        return f"lwr {_r(rt)}, {_imm(simm)}({_r(rs)})"
    if op == 0x27:
        return f"lwu {_r(rt)}, {_imm(simm)}({_r(rs)})"
    if op == 0x28:
        return f"sb {_r(rt)}, {_imm(simm)}({_r(rs)})"
    if op == 0x29:
        return f"sh {_r(rt)}, {_imm(simm)}({_r(rs)})"
    if op == 0x2A:
        return f"swl {_r(rt)}, {_imm(simm)}({_r(rs)})"
    if op == 0x2B:
        return f"sw {_r(rt)}, {_imm(simm)}({_r(rs)})"
    if op == 0x2E:
        return f"swr {_r(rt)}, {_imm(simm)}({_r(rs)})"
    if op == 0x2C:
        return f"sdl {_r(rt)}, {_imm(simm)}({_r(rs)})"
    if op == 0x2D:
        return f"sdr {_r(rt)}, {_imm(simm)}({_r(rs)})"
    if op == 0x30:
        return f"ll {_r(rt)}, {_imm(simm)}({_r(rs)})"
    if op == 0x31:
        return f"lwc1 {_f(rt)}, {_imm(simm)}({_r(rs)})"
    if op == 0x38:
        return f"sc {_r(rt)}, {_imm(simm)}({_r(rs)})"
    if op == 0x39:
        return f"swc1 {_f(rt)}, {_imm(simm)}({_r(rs)})"
    if op == 0x32:
        return f"lwc2 ${rt}, {_imm(simm)}({_r(rs)})"
    if op == 0x33:
        return f"pref 0x{rt:02x}, {_imm(simm)}({_r(rs)})"
    if op == 0x34:
        return f"lld {_r(rt)}, {_imm(simm)}({_r(rs)})"
    if op == 0x35:
        return f"ldc1 {_f(rt)}, {_imm(simm)}({_r(rs)})"
    if op == 0x36:
        return f"lqc2 ${rt}, {_imm(simm)}({_r(rs)})"
    if op == 0x37:
        return f"ld {_r(rt)}, {_imm(simm)}({_r(rs)})"
    if op == 0x3A:
        return f"swc2 ${rt}, {_imm(simm)}({_r(rs)})"
    if op == 0x3C:
        return f"scd {_r(rt)}, {_imm(simm)}({_r(rs)})"
    if op == 0x3D:
        return f"sdc1 {_f(rt)}, {_imm(simm)}({_r(rs)})"
    if op == 0x3E:
        return f"sqc2 ${rt}, {_imm(simm)}({_r(rs)})"
    if op == 0x3F:
        return f"sd {_r(rt)}, {_imm(simm)}({_r(rs)})"
    return f".word 0x{word:08x}"


def _f(index: int) -> str:
    return f"$f{index}"


def disassemble(data: bytes, pc: int, max_instructions: int) -> list[str]:
    """Decode up to `max_instructions` aligned words from `data`."""
    words: list[str] = []
    for offset, word in _words(data, len(data)):
        if len(words) >= max_instructions:
            break
        words.append(disassemble_one(word, (pc + offset) & 0xFFFFFFFF))
    return words


def _words(data: bytes, limit: int) -> Iterator[tuple[int, int]]:
    usable = limit - (limit % 4)
    for offset in range(0, usable, 4):
        yield offset, int.from_bytes(data[offset:offset + 4], "little")
