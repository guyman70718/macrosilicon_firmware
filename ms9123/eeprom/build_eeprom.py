#!/usr/bin/env python3
"""
MS9123 EEPROM Image Builder

Takes compiled firmware binary and wraps it in a valid EEPROM image
with header and checksums.

Usage:
    python3 build_eeprom.py <code.bin> <output.bin>
    python3 build_eeprom.py --verify <eeprom.bin>
"""

import struct
import argparse
import sys

# MS9123 default header (from device)
# [0x00-0x01] Magic: 0xA5 0x5A
# [0x02-0x03] Code length (uint16 BE)
# [0x04]      Hook/config flags (0x2C = hooks + EEPROM code bit 5)
# [0x05]      Reserved (0x00)
# [0x06-0x0B] Reserved (0xFF)
# [0x0C-0x0F] Device info (0x00 0xEE 0xFF 0x21 0x01 0x27...)
# Checksum: sum(0x02:0x30), no skip bytes

DEFAULT_HEADER = bytearray([
    0xA5, 0x5A,         # magic
    0x00, 0x00,         # code length (filled in)
    0x2C, 0x00,         # hook flags, config
    0xFF, 0xFF, 0xFF, 0xFF,  # reserved
    0x00, 0xEE,         # device info
    0xFF, 0x21, 0x01, 0x27,  # firmware version info
] + [0xFF] * 32)        # USB string slots


def build_eeprom(code_bin):
    """Build a complete 2048-byte EEPROM image."""
    eeprom = bytearray(b'\xFF' * 2048)
    eeprom[0x00:0x30] = bytearray(DEFAULT_HEADER)

    code_len = len(code_bin)
    struct.pack_into('>H', eeprom, 2, code_len)
    eeprom[0x30:0x30 + code_len] = code_bin

    end = 0x30 + code_len
    header_sum = sum(eeprom[0x02:0x30]) & 0xFFFF
    code_sum = sum(eeprom[0x30:end]) & 0xFFFF
    struct.pack_into('>H', eeprom, end, header_sum)
    struct.pack_into('>H', eeprom, end + 2, code_sum)

    return eeprom


def verify_eeprom(eeprom):
    """Verify checksums and header."""
    magic = struct.unpack('>H', eeprom[0:2])[0]
    code_len = struct.unpack('>H', eeprom[2:4])[0]
    end = 0x30 + code_len

    header_sum = sum(eeprom[0x02:0x30]) & 0xFFFF
    code_sum = sum(eeprom[0x30:end]) & 0xFFFF

    stored_hdr = struct.unpack('>H', eeprom[end:end + 2])[0]
    stored_code = struct.unpack('>H', eeprom[end + 2:end + 4])[0]

    ok = True

    print(f"Magic: 0x{magic:04X} {'OK' if magic == 0xA55A else 'BAD'}")
    print(f"Code length: {code_len} bytes")

    hdr_ok = header_sum == stored_hdr
    code_ok = code_sum == stored_code
    print(f"Header checksum: calc=0x{header_sum:04X} stored=0x{stored_hdr:04X} {'OK' if hdr_ok else 'MISMATCH'}")
    print(f"Code checksum:   calc=0x{code_sum:04X} stored=0x{stored_code:04X} {'OK' if code_ok else 'MISMATCH'}")
    ok = ok and hdr_ok and code_ok

    return ok


def main():
    parser = argparse.ArgumentParser(description='MS9123 EEPROM Image Builder')
    parser.add_argument('code', nargs='?', help='Compiled code binary')
    parser.add_argument('output', nargs='?', help='Output EEPROM image')
    parser.add_argument('--verify', help='Verify an existing EEPROM image')

    args = parser.parse_args()

    if args.verify:
        with open(args.verify, 'rb') as f:
            eeprom = bytearray(f.read())
        ok = verify_eeprom(eeprom)
        sys.exit(0 if ok else 1)

    if not args.code or not args.output:
        parser.error("code and output are required (or use --verify)")

    with open(args.code, 'rb') as f:
        code = f.read()

    print(f"Code size: {len(code)} bytes")

    eeprom = build_eeprom(code)
    ok = verify_eeprom(eeprom)

    with open(args.output, 'wb') as f:
        f.write(eeprom)

    print(f"\nWrote {len(eeprom)} bytes to {args.output}")
    if not ok:
        print("WARNING: verification issues detected!")
        sys.exit(1)


if __name__ == '__main__':
    main()
