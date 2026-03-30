#!/usr/bin/env python3
"""
MS2107 EEPROM Image Builder

Takes compiled firmware binary and wraps it in a valid EEPROM image
with header, USB descriptors, and checksums.

Usage:
    python3 build_eeprom.py <code.bin> <output.bin> [options]
    python3 build_eeprom.py --verify <eeprom.bin>

Options:
    --vid XXXX          USB VID (hex, default 534D)
    --pid XXXX          USB PID (hex, default 0021)
    --product "string"  USB product string (max 15 chars)
    --verify <file>     Verify checksums of existing image
"""

import struct
import argparse
import sys


# MS2107 EEPROM header byte map (from ROM trace):
#
# [0x00-0x01] Magic: 0x08 0x16
# [0x02-0x03] Code length (uint16 BE)
# [0x04-0x05] USB VID (big-endian, byte-swapped by ROM into USB descriptor)
# [0x06-0x07] USB PID (big-endian, byte-swapped by ROM into USB descriptor)
# [0x08]      Hook enable flags:
#               bit 0: normal hook at code+0x00 (0xC800)
#               bit 1: IRQ hook at code+0x10 (0xC810)
#               bit 2: extra hook at code+0x20 (0xC820) — unused in stock
# [0x09]      Video config: bits 1:0=input select, 7:2=mode. 0xFF=auto
# [0x0A]      Feature flags: bit 0=IRQ behavior, bit 2=extra data, 7:4=threshold
# [0x0B]      Video config 2: bit 7=S-Video/CVBS, 6:0=standard. NOT checksummed.
# [0x0C-0x0F] Unreferenced by ROM. Safe to set to any value.
# [0x10-0x1F] USB product string 1 (len-prefixed ASCII, 16-byte slot)
# [0x20-0x2F] USB product string 2 (len-prefixed ASCII, 16-byte slot)
# Checksum: sum(0x02:0x0B) + sum(0x10:0x30), skip 0x0B-0x0F

# Default header values (stock firmware configuration)
DEFAULT_HEADER = {
    'vid': 0x534D,          # Macrosilicon VID (EEPROM 0xFFFF = use this default)
    'pid': 0x0021,          # Default PID
    'hook_flags': 0x03,     # Normal + IRQ hooks enabled
    'video_config': 0xFF,   # Auto-detect all inputs
    'feature_flags': 0x01,  # Standard features
    'video_config2': 0x02,  # Default video standard
    'reserved': bytes([0x20, 0x22, 0x12, 0x07]),  # 0x0C-0x0F (unreferenced, keep original)
}


def build_eeprom(code_bin, vid=None, pid=None, product=None):
    """Build a complete 2048-byte EEPROM image."""

    eeprom = bytearray(b'\xFF' * 2048)

    # Header
    eeprom[0x00] = 0x08  # Magic
    eeprom[0x01] = 0x16
    struct.pack_into('>H', eeprom, 4, vid if vid is not None else DEFAULT_HEADER['vid'])
    struct.pack_into('>H', eeprom, 6, pid if pid is not None else DEFAULT_HEADER['pid'])
    eeprom[0x08] = DEFAULT_HEADER['hook_flags']
    eeprom[0x09] = DEFAULT_HEADER['video_config']
    eeprom[0x0A] = DEFAULT_HEADER['feature_flags']
    eeprom[0x0B] = DEFAULT_HEADER['video_config2']
    eeprom[0x0C:0x10] = DEFAULT_HEADER['reserved']

    # === Update code length ===
    code_len = len(code_bin)
    struct.pack_into('>H', eeprom, 2, code_len)

    if product is not None:
        product_bytes = product.encode('ascii')[:15]
        str_len = len(product_bytes) + 1  # includes the length byte

        # String slot 1 (0x10-0x1F)
        eeprom[0x10:0x20] = bytearray([0xFF] * 16)
        eeprom[0x10] = str_len
        eeprom[0x11:0x11 + len(product_bytes)] = product_bytes

        # String slot 2 (0x20-0x2F)
        eeprom[0x20:0x30] = bytearray([0xFF] * 16)
        eeprom[0x20] = str_len
        eeprom[0x21:0x21 + len(product_bytes)] = product_bytes

    # === Code (0x30 - 0x30+code_len) ===
    eeprom[0x30:0x30 + code_len] = code_bin

    # === Checksums (immediately after code) ===
    end = 0x30 + code_len

    header_sum = (sum(eeprom[0x02:0x0B]) + sum(eeprom[0x10:0x30])) & 0xFFFF
    code_sum = sum(eeprom[0x30:end]) & 0xFFFF

    struct.pack_into('>H', eeprom, end, header_sum)
    struct.pack_into('>H', eeprom, end + 2, code_sum)

    return eeprom


def verify_eeprom(eeprom):
    """Verify checksums and header."""
    magic = struct.unpack('>H', eeprom[0:2])[0]
    code_len = struct.unpack('>H', eeprom[2:4])[0]
    end = 0x30 + code_len

    header_sum = (sum(eeprom[0x02:0x0B]) + sum(eeprom[0x10:0x30])) & 0xFFFF
    code_sum = sum(eeprom[0x30:end]) & 0xFFFF

    stored_hdr = struct.unpack('>H', eeprom[end:end + 2])[0]
    stored_code = struct.unpack('>H', eeprom[end + 2:end + 4])[0]

    ok = True

    print(f"Magic: 0x{magic:04X} {'OK' if magic == 0x0816 else 'BAD'}")
    print(f"Code length: {code_len} bytes")
    print(f"VID:PID = 0x{eeprom[4]:02X}{eeprom[5]:02X}:0x{eeprom[6]:02X}{eeprom[7]:02X}")

    hdr_ok = header_sum == stored_hdr
    code_ok = code_sum == stored_code
    print(f"Header checksum: calc=0x{header_sum:04X} stored=0x{stored_hdr:04X} {'OK' if hdr_ok else 'MISMATCH'}")
    print(f"Code checksum:   calc=0x{code_sum:04X} stored=0x{stored_code:04X} {'OK' if code_ok else 'MISMATCH'}")
    ok = ok and hdr_ok and code_ok

    # Check non-checksummed bytes are not 0xFF
    non_csum = eeprom[0x0B:0x10]
    if all(b == 0xFF for b in non_csum):
        print(f"WARNING: Bytes 0x0B-0x0F are all 0xFF — USB descriptor config missing!")
        ok = False
    else:
        print(f"USB config (0x0B-0x0F): {' '.join(f'{b:02X}' for b in non_csum)}")

    return ok


def main():
    parser = argparse.ArgumentParser(description='MS2107 EEPROM Image Builder')
    parser.add_argument('code', nargs='?', help='Compiled code binary')
    parser.add_argument('output', nargs='?', help='Output EEPROM image')
    parser.add_argument('--vid', type=lambda x: int(x, 16), help='USB VID (hex)')
    parser.add_argument('--pid', type=lambda x: int(x, 16), help='USB PID (hex)')
    parser.add_argument('--product', help='USB product string (max 15 chars)')
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

    eeprom = build_eeprom(code, vid=args.vid, pid=args.pid, product=args.product)

    ok = verify_eeprom(eeprom)

    with open(args.output, 'wb') as f:
        f.write(eeprom)

    print(f"\nWrote {len(eeprom)} bytes to {args.output}")
    if not ok:
        print("WARNING: verification issues detected!")
        sys.exit(1)


if __name__ == '__main__':
    main()
