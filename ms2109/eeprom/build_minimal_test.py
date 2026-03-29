#!/usr/bin/env python3
"""
Build the minimal MS2109 test EEPROM: all hooks RET except the
stock callback at +0x10.  Useful as a known-good baseline — confirms
the device boots and enumerates with no custom logic.

Usage:
    python build_minimal_test.py [--ref <original.bin>]
"""

import struct, argparse, os, sys

DEFAULT_REF = os.path.join(os.path.dirname(__file__), '..', '..', 'dumps', 'MS2109.BIN')

def main():
    parser = argparse.ArgumentParser(description='Build MS2109 minimal test EEPROM')
    parser.add_argument('--ref', default=DEFAULT_REF, help='Reference EEPROM for header')
    args = parser.parse_args()

    ref = open(args.ref, 'rb').read()

    # 33 bytes of code: RET at +0x00, stock callback at +0x10, RET at +0x20
    code = bytearray(0x21)
    code[0x00] = 0x22  # RET (normal hook — do nothing)

    # Stock callback at +0x10 (15 bytes, must be preserved)
    # MOV DPTR,#0xDE05 / MOV A,R3 / MOVX @DPTR,A / INC DPTR /
    # MOV A,R2 / MOVX @DPTR,A / INC DPTR / MOV A,R1 / MOVX @DPTR,A /
    # LCALL 0x6345 / RET
    code[0x10:0x1F] = bytes([
        0x90, 0xDE, 0x05, 0xEB, 0xF0, 0xA3, 0xEA, 0xF0,
        0xA3, 0xE9, 0xF0, 0x12, 0x63, 0x45, 0x22,
    ])

    code[0x20] = 0x22  # RET (IRQ hook — do nothing)

    # Build EEPROM image
    eeprom = bytearray(b'\xFF' * 2048)
    eeprom[0x00:0x30] = ref[0x00:0x30]
    struct.pack_into('>H', eeprom, 2, len(code))
    eeprom[0x30:0x30 + len(code)] = code

    end = 0x30 + len(code)
    header_sum = sum(eeprom[0x02:0x30]) & 0xFFFF
    code_sum = sum(eeprom[0x30:end]) & 0xFFFF
    struct.pack_into('>H', eeprom, end, header_sum)
    struct.pack_into('>H', eeprom, end + 2, code_sum)

    out = os.path.join(os.path.dirname(__file__), 'eeprom_minimal_test.bin')
    open(out, 'wb').write(eeprom)
    print(f'Wrote {out}')
    print(f'  Code: {len(code)} bytes, checksum OK')
    print(f'  +0x00=RET  +0x10=callback  +0x20=RET')

if __name__ == '__main__':
    main()
