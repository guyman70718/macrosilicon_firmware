#!/usr/bin/env python3
"""
MS2109 EEPROM Image Builder

Uses the original EEPROM as a reference header template.
MS2109 checksum: header_sum = sum(data[0x02:0x30]) — NO skip bytes (same as MS9123).

Usage:
    python3 build_eeprom.py <code.bin> <output.bin> [--ref <original.bin>]
    python3 build_eeprom.py --verify <eeprom.bin>
"""

import struct
import argparse
import sys
import os

DEFAULT_REF = os.path.join(os.path.dirname(__file__), '..', '..', 'dumps', 'MS2109.BIN')


def build_eeprom(code_bin, ref_eeprom, pad_to_ref=False):
    """Build a complete 2048-byte EEPROM image using reference header."""

    eeprom = bytearray(2048)
    for i in range(len(eeprom)):
        eeprom[i] = 0xFF

    # Copy full header from reference (0x00-0x2F)
    eeprom[0x00:0x30] = bytearray(ref_eeprom[0x00:0x30])

    code_len = len(code_bin)

    # Insert our code at 0x30
    eeprom[0x30:0x30 + code_len] = code_bin

    if pad_to_ref:
        # Pad to stock code_length using reference EEPROM bytes.
        # This fills the gap between our code and the stock code end
        # with ROM-identical data, making code_length match stock.
        ref_code_len = struct.unpack('>H', ref_eeprom[2:4])[0]
        if code_len < ref_code_len:
            # Fill from our code end to stock code end with reference bytes
            src_start = 0x30 + code_len
            src_end = 0x30 + ref_code_len
            eeprom[src_start:src_end] = ref_eeprom[src_start:src_end]
            print(f"Padded: {code_len} -> {ref_code_len} bytes (filled {ref_code_len - code_len} bytes from reference)")
            code_len = ref_code_len
        else:
            print(f"No padding needed: code ({code_len}) >= ref ({ref_code_len})")

    # Update code length
    struct.pack_into('>H', eeprom, 2, code_len)

    # MS2109 checksums: NO skip bytes (same as MS9123)
    end = 0x30 + code_len
    header_sum = sum(eeprom[0x02:0x30]) & 0xFFFF
    code_sum = sum(eeprom[0x30:end]) & 0xFFFF

    struct.pack_into('>H', eeprom, end, header_sum)
    struct.pack_into('>H', eeprom, end + 2, code_sum)

    return eeprom


def verify_eeprom(eeprom, ref_eeprom=None):
    """Verify checksums and compare header against reference."""
    magic = struct.unpack('>H', eeprom[0:2])[0]
    code_len = struct.unpack('>H', eeprom[2:4])[0]
    end = 0x30 + code_len

    # MS2109 checksum: sum(0x02:0x30), no skip
    header_sum = sum(eeprom[0x02:0x30]) & 0xFFFF
    code_sum = sum(eeprom[0x30:end]) & 0xFFFF

    stored_hdr = struct.unpack('>H', eeprom[end:end + 2])[0]
    stored_code = struct.unpack('>H', eeprom[end + 2:end + 4])[0]

    ok = True

    print(f"Magic: 0x{magic:04X} {'OK' if magic in (0xA55A, 0x9669) else 'BAD'}")
    print(f"Code length: {code_len} bytes (0x{code_len:04X})")
    print(f"EEPROM free: {2048 - end - 4} bytes")

    hdr_ok = header_sum == stored_hdr
    code_ok = code_sum == stored_code
    print(f"Header checksum: calc=0x{header_sum:04X} stored=0x{stored_hdr:04X} {'OK' if hdr_ok else 'MISMATCH'}")
    print(f"Code checksum:   calc=0x{code_sum:04X} stored=0x{stored_code:04X} {'OK' if code_ok else 'MISMATCH'}")
    ok = ok and hdr_ok and code_ok

    if ref_eeprom is not None:
        diffs = [(i, ref_eeprom[i], eeprom[i]) for i in range(0x30) if eeprom[i] != ref_eeprom[i]]
        unexpected = [d for d in diffs if d[0] not in (0x02, 0x03)]  # code length expected to differ
        if unexpected:
            print(f"\nUnexpected header differences vs reference:")
            for i, o, n in unexpected:
                print(f"  [0x{i:02X}] ref=0x{o:02X} img=0x{n:02X}")
            ok = False
        else:
            print("Header matches reference (excluding code length)")

    return ok


def main():
    parser = argparse.ArgumentParser(description='MS2109 EEPROM Image Builder')
    parser.add_argument('code', nargs='?', help='Compiled code binary')
    parser.add_argument('output', nargs='?', help='Output EEPROM image')
    parser.add_argument('--ref', default=DEFAULT_REF, help='Reference EEPROM for header template')
    parser.add_argument('--verify', help='Verify an existing EEPROM image')
    parser.add_argument('--pad-to-ref', action='store_true',
                        help='Pad code to reference code_length using reference bytes (ROM fallthrough safety)')

    args = parser.parse_args()

    ref_eeprom = None
    if os.path.exists(args.ref):
        with open(args.ref, 'rb') as f:
            ref_eeprom = f.read()

    if args.verify:
        with open(args.verify, 'rb') as f:
            eeprom = bytearray(f.read())
        ok = verify_eeprom(eeprom, ref_eeprom)
        sys.exit(0 if ok else 1)

    if not args.code or not args.output:
        parser.error("code and output are required (or use --verify)")

    if ref_eeprom is None:
        print(f"Error: reference EEPROM not found at {args.ref}")
        sys.exit(1)

    with open(args.code, 'rb') as f:
        code = f.read()

    print(f"Code size: {len(code)} bytes")
    print(f"Reference: {args.ref}")

    eeprom = build_eeprom(code, ref_eeprom, pad_to_ref=args.pad_to_ref)
    ok = verify_eeprom(eeprom, ref_eeprom)

    with open(args.output, 'wb') as f:
        f.write(eeprom)

    print(f"\nWrote {len(eeprom)} bytes to {args.output}")
    if not ok:
        print("WARNING: verification issues detected!")
        sys.exit(1)


if __name__ == '__main__':
    main()
