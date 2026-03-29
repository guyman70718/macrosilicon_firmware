#!/usr/bin/env python3
"""Simple 8051 disassembler for EEPROM firmware code blocks."""

import struct
import sys


def disasm(code, base=0):
    """Disassemble 8051 code bytes, return list of (addr, raw_bytes, mnemonic) tuples."""
    result = []

    # Instruction sizes by opcode
    def get_size(op):
        if (op & 0x1F) in (0x01, 0x11):
            return 2  # AJMP/ACALL
        if op in (0x02, 0x12, 0x10, 0x20, 0x30, 0x90, 0x75, 0x85,
                  0x42, 0x43, 0x52, 0x53, 0x62, 0x63,
                  0xB4, 0xB5, 0xB6, 0xB7, 0xD5):
            return 3
        if op >= 0xB8 and op <= 0xBF:
            return 3  # CJNE Rn,#imm,rel
        if op in (0x05, 0x15, 0x24, 0x25, 0x34, 0x35,
                  0x40, 0x44, 0x45, 0x50, 0x54, 0x55,
                  0x60, 0x64, 0x65, 0x70, 0x74, 0x76, 0x77, 0x80,
                  0x82, 0x86, 0x87, 0x92, 0x94, 0x95,
                  0xA0, 0xA2, 0xB0, 0xB2, 0xC0, 0xC2, 0xC5, 0xD0, 0xD2,
                  0xE5, 0xF5):
            return 2
        if op >= 0x78 and op <= 0x7F:
            return 2
        if op >= 0x88 and op <= 0x8F:
            return 2
        if op >= 0xD8 and op <= 0xDF:
            return 2
        return 1

    def bitname(bit):
        if bit >= 0xE0 and bit <= 0xE7:
            return f"ACC.{bit - 0xE0}"
        if bit >= 0xD0 and bit <= 0xD7:
            return f"PSW.{bit - 0xD0}"
        if bit == 0xAF:
            return "EA"
        if bit < 0x80:
            return f"0x{(bit >> 3) + 0x20:02X}.{bit & 7}"
        return f"0x{bit & 0xF8:02X}.{bit & 7}"

    def rel_target(addr, offset, inst_size):
        rel = offset if offset < 128 else offset - 256
        return addr + inst_size + rel

    i = 0
    while i < len(code):
        addr = base + i
        op = code[i]
        sz = get_size(op)
        if i + sz > len(code):
            break
        raw = code[i:i + sz]

        # Decode
        if (op & 0x1F) == 0x01:  # AJMP
            target = ((addr + 2) & 0xF800) | ((op >> 5) << 8) | raw[1]
            mn = f"AJMP  0x{target:04X}"
        elif (op & 0x1F) == 0x11:  # ACALL
            target = ((addr + 2) & 0xF800) | ((op >> 5) << 8) | raw[1]
            mn = f"ACALL 0x{target:04X}"
        elif op == 0x02:
            mn = f"LJMP  0x{(raw[1] << 8) | raw[2]:04X}"
        elif op == 0x12:
            mn = f"LCALL 0x{(raw[1] << 8) | raw[2]:04X}"
        elif op == 0x90:
            mn = f"MOV   DPTR,#0x{(raw[1] << 8) | raw[2]:04X}"
        elif op == 0x22:
            mn = "RET"
        elif op == 0x32:
            mn = "RETI"
        elif op == 0x00:
            mn = "NOP"
        elif op in (0x40, 0x50, 0x60, 0x70, 0x80):
            names = {0x40: "JC", 0x50: "JNC", 0x60: "JZ", 0x70: "JNZ", 0x80: "SJMP"}
            mn = f"{names[op]:5s} 0x{rel_target(addr, raw[1], 2):04X}"
        elif op in (0x10, 0x20, 0x30):
            names = {0x10: "JBC", 0x20: "JB", 0x30: "JNB"}
            mn = f"{names[op]:5s} {bitname(raw[1])},0x{rel_target(addr, raw[2], 3):04X}"
        elif op == 0xB4:
            mn = f"CJNE  A,#0x{raw[1]:02X},0x{rel_target(addr, raw[2], 3):04X}"
        elif op >= 0xB8 and op <= 0xBF:
            mn = f"CJNE  R{op - 0xB8},#0x{raw[1]:02X},0x{rel_target(addr, raw[2], 3):04X}"
        elif op == 0xD5:
            mn = f"DJNZ  0x{raw[1]:02X},0x{rel_target(addr, raw[2], 3):04X}"
        elif op >= 0xD8 and op <= 0xDF:
            mn = f"DJNZ  R{op - 0xD8},0x{rel_target(addr, raw[1], 2):04X}"
        elif op == 0xE0:
            mn = "MOVX  A,@DPTR"
        elif op == 0xF0:
            mn = "MOVX  @DPTR,A"
        elif op == 0xE4:
            mn = "CLR   A"
        elif op == 0xC3:
            mn = "CLR   CY"
        elif op == 0xD3:
            mn = "SETB  CY"
        elif op == 0xA3:
            mn = "INC   DPTR"
        elif op == 0x03:
            mn = "RR    A"
        elif op == 0x04:
            mn = "INC   A"
        elif op == 0x13:
            mn = "RRC   A"
        elif op == 0x14:
            mn = "DEC   A"
        elif op == 0x23:
            mn = "RL    A"
        elif op == 0x33:
            mn = "RLC   A"
        elif op == 0x83:
            mn = "MOVC  A,@A+PC"
        elif op == 0x93:
            mn = "MOVC  A,@A+DPTR"
        elif op == 0x74:
            mn = f"MOV   A,#0x{raw[1]:02X}"
        elif op >= 0x78 and op <= 0x7F:
            mn = f"MOV   R{op - 0x78},#0x{raw[1]:02X}"
        elif op == 0xE5:
            mn = f"MOV   A,0x{raw[1]:02X}"
        elif op == 0xF5:
            mn = f"MOV   0x{raw[1]:02X},A"
        elif op >= 0xE8 and op <= 0xEF:
            mn = f"MOV   A,R{op - 0xE8}"
        elif op >= 0xF8 and op <= 0xFF:
            mn = f"MOV   R{op - 0xF8},A"
        elif op >= 0x08 and op <= 0x0F:
            mn = f"INC   R{op - 0x08}"
        elif op >= 0x18 and op <= 0x1F:
            mn = f"DEC   R{op - 0x18}"
        elif op >= 0x28 and op <= 0x2F:
            mn = f"ADD   A,R{op - 0x28}"
        elif op >= 0x38 and op <= 0x3F:
            mn = f"ADDC  A,R{op - 0x38}"
        elif op >= 0x48 and op <= 0x4F:
            mn = f"ORL   A,R{op - 0x48}"
        elif op >= 0x58 and op <= 0x5F:
            mn = f"ANL   A,R{op - 0x58}"
        elif op >= 0x68 and op <= 0x6F:
            mn = f"XRL   A,R{op - 0x68}"
        elif op == 0x06:
            mn = "INC   @R0"
        elif op == 0x07:
            mn = "INC   @R1"
        elif op == 0x16:
            mn = "DEC   @R0"
        elif op == 0x17:
            mn = "DEC   @R1"
        elif op == 0xE6:
            mn = "MOV   A,@R0"
        elif op == 0xE7:
            mn = "MOV   A,@R1"
        elif op == 0xF6:
            mn = "MOV   @R0,A"
        elif op == 0xF7:
            mn = "MOV   @R1,A"
        elif op == 0x75:
            mn = f"MOV   0x{raw[1]:02X},#0x{raw[2]:02X}"
        elif op == 0x85:
            mn = f"MOV   0x{raw[2]:02X},0x{raw[1]:02X}"
        elif op == 0x05:
            mn = f"INC   0x{raw[1]:02X}"
        elif op == 0x15:
            mn = f"DEC   0x{raw[1]:02X}"
        elif op == 0x24:
            mn = f"ADD   A,#0x{raw[1]:02X}"
        elif op == 0x25:
            mn = f"ADD   A,0x{raw[1]:02X}"
        elif op == 0x34:
            mn = f"ADDC  A,#0x{raw[1]:02X}"
        elif op == 0x35:
            mn = f"ADDC  A,0x{raw[1]:02X}"
        elif op == 0x44:
            mn = f"ORL   A,#0x{raw[1]:02X}"
        elif op == 0x45:
            mn = f"ORL   A,0x{raw[1]:02X}"
        elif op == 0x54:
            mn = f"ANL   A,#0x{raw[1]:02X}"
        elif op == 0x55:
            mn = f"ANL   A,0x{raw[1]:02X}"
        elif op == 0x64:
            mn = f"XRL   A,#0x{raw[1]:02X}"
        elif op == 0x65:
            mn = f"XRL   A,0x{raw[1]:02X}"
        elif op == 0x94:
            mn = f"SUBB  A,#0x{raw[1]:02X}"
        elif op == 0x95:
            mn = f"SUBB  A,0x{raw[1]:02X}"
        elif op == 0x42:
            mn = f"ORL   0x{raw[1]:02X},A"
        elif op == 0x43:
            mn = f"ORL   0x{raw[1]:02X},#0x{raw[2]:02X}"
        elif op == 0x52:
            mn = f"ANL   0x{raw[1]:02X},A"
        elif op == 0x53:
            mn = f"ANL   0x{raw[1]:02X},#0x{raw[2]:02X}"
        elif op == 0x62:
            mn = f"XRL   0x{raw[1]:02X},A"
        elif op == 0x63:
            mn = f"XRL   0x{raw[1]:02X},#0x{raw[2]:02X}"
        elif op == 0xC0:
            mn = f"PUSH  0x{raw[1]:02X}"
        elif op == 0xD0:
            mn = f"POP   0x{raw[1]:02X}"
        elif op == 0xC2:
            mn = f"CLR   {bitname(raw[1])}"
        elif op == 0xD2:
            mn = f"SETB  {bitname(raw[1])}"
        elif op == 0x92:
            mn = f"MOV   {bitname(raw[1])},CY"
        elif op == 0xA2:
            mn = f"MOV   CY,{bitname(raw[1])}"
        elif op == 0xA0:
            mn = f"ORL   C,/{bitname(raw[1])}"
        elif op == 0xB0:
            mn = f"ANL   C,/{bitname(raw[1])}"
        elif op == 0x82:
            mn = f"ANL   C,{bitname(raw[1])}"
        elif op == 0xB2:
            mn = f"CPL   {bitname(raw[1])}"
        elif op >= 0x86 and op <= 0x87:
            mn = f"MOV   0x{raw[1]:02X},@R{op - 0x86}"
        elif op >= 0x88 and op <= 0x8F:
            mn = f"MOV   0x{raw[1]:02X},R{op - 0x88}"
        elif op == 0xB5:
            mn = f"CJNE  A,0x{raw[1]:02X},0x{rel_target(addr, raw[2], 3):04X}"
        elif op == 0xB6:
            mn = f"CJNE  @R0,#0x{raw[1]:02X},0x{rel_target(addr, raw[2], 3):04X}"
        elif op == 0xB7:
            mn = f"CJNE  @R1,#0x{raw[1]:02X},0x{rel_target(addr, raw[2], 3):04X}"
        elif op == 0x76:
            mn = f"MOV   @R0,#0x{raw[1]:02X}"
        elif op == 0x77:
            mn = f"MOV   @R1,#0x{raw[1]:02X}"
        elif op == 0x26:
            mn = "ADD   A,@R0"
        elif op == 0x27:
            mn = "ADD   A,@R1"
        elif op == 0x36:
            mn = "ADDC  A,@R0"
        elif op == 0x37:
            mn = "ADDC  A,@R1"
        elif op == 0x46:
            mn = "ORL   A,@R0"
        elif op == 0x47:
            mn = "ORL   A,@R1"
        elif op == 0x56:
            mn = "ANL   A,@R0"
        elif op == 0x57:
            mn = "ANL   A,@R1"
        elif op == 0x66:
            mn = "XRL   A,@R0"
        elif op == 0x67:
            mn = "XRL   A,@R1"
        elif op == 0x96:
            mn = "SUBB  A,@R0"
        elif op == 0x97:
            mn = "SUBB  A,@R1"
        elif op == 0xA4:
            mn = "MUL   AB"
        elif op == 0x84:
            mn = "DIV   AB"
        elif op == 0xA5:
            mn = f"DB    0x{op:02X}"  # undefined
        elif op == 0xC4:
            mn = "SWAP  A"
        elif op == 0xC5:
            mn = f"XCH   A,0x{raw[1]:02X}"
        elif op == 0xC6:
            mn = "XCH   A,@R0"
        elif op == 0xC7:
            mn = "XCH   A,@R1"
        elif op >= 0xC8 and op <= 0xCF:
            mn = f"XCH   A,R{op - 0xC8}"
        elif op == 0xD4:
            mn = "DA    A"
        elif op == 0xD6:
            mn = "XCHD  A,@R0"
        elif op == 0xD7:
            mn = "XCHD  A,@R1"
        else:
            mn = f"DB    0x{op:02X}"

        raw_str = " ".join(f"{b:02X}" for b in raw)
        result.append((addr, raw_str, mn))
        i += sz

    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: disasm8051.py <binary> [base_addr] [offset] [length]")
        sys.exit(1)

    with open(sys.argv[1], "rb") as f:
        data = f.read()

    base = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0
    offset = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0
    length = int(sys.argv[4], 0) if len(sys.argv) > 4 else len(data) - offset

    code = data[offset:offset + length]

    for addr, raw, mn in disasm(code, base):
        print(f"  {addr:04X}: {raw:12s} {mn}")


if __name__ == "__main__":
    main()
