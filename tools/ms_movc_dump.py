"""
Interactive CODE space dump for Macrosilicon devices via MOVC.

Installs a mailbox-based MOVC handler into XDATA RAM by patching
the periodic USB hook at runtime. No EEPROM modification needed —
all changes are volatile (lost on power cycle).

Requires: the device must have booted with valid EEPROM (hook enable
bit set at the appropriate UserConfig location).

Usage:
    python ms_movc_dump.py                           # dump full 32KB CODE
    python ms_movc_dump.py --start 0x4D00 --length 256  # dump specific range
    python ms_movc_dump.py -o code_dump.bin          # save to file

Device-specific configuration (edit CHIP_CONFIG for your device):
    MS9123: periodic hook at 0xC860, original handler LJMP 0xC903
    MS2107: periodic hook at 0xC800, original handler varies (check EEPROM)
"""

import hid
import time
import sys
import argparse

# -- Chip-specific configuration --
CHIP_CONFIG = {
    "MS9123": {
        "vid": 0x534D,
        "pid": 0x6021,
        "hook_addr": 0xC860,          # periodic USB hook in XDATA
        "orig_handler": 0xC903,       # original LJMP target at hook_addr
        "handler_addr": 0xCE00,       # where to load our handler in RAM
        "mailbox_addr": 0xD3F0,       # mailbox location
        "temp_buf": 0xD000,           # default temp buffer for dump output
    },
    "MS2107": {
        "vid": 0x0002,
        "pid": 0xAFA1,
        "hook_addr": 0xC800,          # periodic USB hook (normal context)
        "orig_handler": None,         # read from XDATA at runtime
        "handler_addr": 0xCE00,
        "mailbox_addr": 0xD3F0,
        "temp_buf": 0xD000,
    },
}


def build_movc_handler(mailbox_addr, orig_handler_addr):
    """Build the mailbox-based MOVC handler blob.

    Mailbox format at mailbox_addr:
        [0]   = byte count (write last to trigger; 0 = idle)
        [1:2] = CODE source address (big-endian)
        [3:4] = XDATA destination address (big-endian)

    On each hook invocation:
        - If mailbox[0] == 0: skip to original handler (no-op)
        - Else: MOVC count bytes from CODE[src] to XDATA[dst], clear mailbox[0]
        - Always: LJMP to original handler
    """
    mhi = (mailbox_addr >> 8) & 0xFF
    mlo = mailbox_addr & 0xFF
    ohi = (orig_handler_addr >> 8) & 0xFF
    olo = orig_handler_addr & 0xFF

    return bytearray([
        # check mailbox (offset 0)
        0x90, mhi, mlo,       # MOV DPTR,#MAILBOX
        0xE0,                  # MOVX A,@DPTR
        0x60, 0x2B,            # JZ done (+43 -> offset 49)
        0xFF,                  # MOV R7,A (count)
        0xA3, 0xE0, 0xFC,     # INC DPTR; MOVX A,@DPTR; MOV R4,A (src_hi)
        0xA3, 0xE0, 0xFD,     # MOV R5,A (src_lo)
        0xA3, 0xE0, 0xFA,     # MOV R2,A (dst_hi)
        0xA3, 0xE0, 0xFB,     # MOV R3,A (dst_lo)
        # copy loop (offset 19)
        0x8C, 0x83,            # MOV DPH,R4
        0x8D, 0x82,            # MOV DPL,R5
        0xE4,                  # CLR A
        0x93,                  # MOVC A,@A+DPTR
        0x8A, 0x83,            # MOV DPH,R2
        0x8B, 0x82,            # MOV DPL,R3
        0xF0,                  # MOVX @DPTR,A
        0x0D,                  # INC R5
        0xBD, 0x00, 0x01,     # CJNE R5,#0,+1
        0x0C,                  # INC R4
        0x0B,                  # INC R3
        0xBB, 0x00, 0x01,     # CJNE R3,#0,+1
        0x0A,                  # INC R2
        0xDF, 0xE9,            # DJNZ R7,copy (-23)
        # clear mailbox (offset 42)
        0x90, mhi, mlo,       # MOV DPTR,#MAILBOX
        0xE4,                  # CLR A
        0xF0,                  # MOVX @DPTR,A
        0x80, 0x00,            # SJMP done (+0)
        # done (offset 49)
        0x02, ohi, olo,       # LJMP original_handler
    ])


class MOVCDumper:
    def __init__(self, chip="MS9123"):
        self.cfg = CHIP_CONFIG[chip]
        self.dev = hid.device()
        self.installed = False

    def open(self):
        self.dev.open(self.cfg["vid"], self.cfg["pid"])

    def close(self):
        if self.installed:
            self.uninstall()
        self.dev.close()

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.close()

    def _xread(self, addr):
        self.dev.send_feature_report(
            [0x00, 0xB5, (addr >> 8) & 0xFF, addr & 0xFF, 0, 0, 0, 0, 0])
        return self.dev.get_feature_report(0, 9)[4]

    def _xwrite(self, addr, val):
        self.dev.send_feature_report(
            [0x00, 0xB6, (addr >> 8) & 0xFF, addr & 0xFF, val, 0, 0, 0, 0])

    def install(self):
        """Install the MOVC handler and patch the periodic hook."""
        hook = self.cfg["hook_addr"]
        handler = self.cfg["handler_addr"]
        mailbox = self.cfg["mailbox_addr"]

        # Read original handler from hook LJMP
        orig = self.cfg["orig_handler"]
        if orig is None:
            b = [self._xread(hook + i) for i in range(3)]
            if b[0] != 0x02:
                raise RuntimeError(f"Hook at 0x{hook:04X} is not LJMP: {b}")
            orig = (b[1] << 8) | b[2]

        self.orig_hook = [self._xread(hook + i) for i in range(3)]

        # Build and upload handler
        blob = build_movc_handler(mailbox, orig)
        for i, b in enumerate(blob):
            self._xwrite(handler + i, b)

        # Verify
        for i, expected in enumerate(blob):
            actual = self._xread(handler + i)
            if actual != expected:
                raise RuntimeError(f"Handler verify failed at +{i}")

        # Clear mailbox
        for i in range(5):
            self._xwrite(mailbox + i, 0)

        # Patch hook
        self._xwrite(hook, 0x02)
        self._xwrite(hook + 1, (handler >> 8) & 0xFF)
        self._xwrite(hook + 2, handler & 0xFF)

        self.installed = True

    def uninstall(self):
        """Restore original hook."""
        if hasattr(self, 'orig_hook'):
            hook = self.cfg["hook_addr"]
            for i, b in enumerate(self.orig_hook):
                self._xwrite(hook + i, b)
        self.installed = False

    def movc_read(self, src_addr, length, dst_addr=None):
        """Read CODE space bytes via MOVC. Returns bytearray."""
        if not self.installed:
            self.install()

        if dst_addr is None:
            dst_addr = self.cfg["temp_buf"]
        mailbox = self.cfg["mailbox_addr"]

        result = bytearray()
        offset = 0
        while offset < length:
            chunk = min(128, length - offset)
            src = src_addr + offset
            dst = dst_addr

            # Write mailbox: dst, src, then count (trigger)
            self._xwrite(mailbox + 1, (src >> 8) & 0xFF)
            self._xwrite(mailbox + 2, src & 0xFF)
            self._xwrite(mailbox + 3, (dst >> 8) & 0xFF)
            self._xwrite(mailbox + 4, dst & 0xFF)
            self._xwrite(mailbox, chunk)  # trigger

            # Poll for completion
            for _ in range(500):
                time.sleep(0.002)
                if self._xread(mailbox) == 0:
                    break
            else:
                raise RuntimeError(f"MOVC timeout at src=0x{src:04X}")

            # Read back
            for i in range(chunk):
                result.append(self._xread(dst + i))

            offset += chunk

        return result

    def dump_code(self, start=0x0000, length=0x8000, progress=True):
        """Dump CODE space. Default: full lower 32KB."""
        result = bytearray()
        t0 = time.time()

        for offset in range(0, length, 128):
            chunk = self.movc_read(start + offset, min(128, length - offset))
            result.extend(chunk)

            if progress and offset % 0x1000 == 0 and offset > 0:
                elapsed = time.time() - t0
                pct = offset / length * 100
                eta = elapsed / offset * (length - offset)
                print(f"  0x{start+offset:04X} ({pct:.0f}%) - {elapsed:.0f}s, ~{eta:.0f}s left")

        if progress:
            print(f"  Done: {len(result)} bytes in {time.time()-t0:.1f}s")

        return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dump CODE space via MOVC")
    parser.add_argument("--chip", default="MS9123", choices=CHIP_CONFIG.keys())
    parser.add_argument("--start", type=lambda x: int(x, 0), default=0x0000)
    parser.add_argument("--length", type=lambda x: int(x, 0), default=0x8000)
    parser.add_argument("-o", "--output", default="code_dump.bin")
    parser.add_argument("--no-upper", action="store_true",
                        help="Don't append upper 32KB from XDATA mirror")
    args = parser.parse_args()

    with MOVCDumper(args.chip) as dumper:
        info = dumper.dev.get_manufacturer_string()
        product = dumper.dev.get_product_string()
        print(f"Connected: {info} {product}")

        print(f"Dumping CODE 0x{args.start:04X}-0x{args.start+args.length-1:04X}...")
        code = dumper.dump_code(args.start, args.length)

        if not args.no_upper and args.start == 0 and args.length == 0x8000:
            print("Reading upper 32KB from XDATA mirror (0x8000-0xFFFF)...")
            upper = bytearray(0x8000)
            for i in range(0x8000):
                upper[i] = dumper._xread(0x8000 + i)
                if i % 0x2000 == 0 and i > 0:
                    print(f"  0x{0x8000+i:04X}...")
            code = code + upper
            print(f"  Full 64KB CODE dump")

        with open(args.output, "wb") as f:
            f.write(code)
        print(f"Saved {len(code)} bytes to {args.output}")
