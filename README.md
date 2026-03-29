# Macrosilicon Custom Firmware

Custom EEPROM firmware for Macrosilicon USB video chips, reverse-engineered from
mask ROM disassembly and rebuilt in C with SDCC.

## Supported Chips

| Chip | Function | Status | Features |
|------|----------|--------|----------|
| **MS2107** | CVBS/S-Video to USB capture | Working | Signal status, image adjust, input select, GPIO, I2C master |
| **MS9123** | USB to CVBS/S-Video display | Working | Display status, PAL/NTSC mode, DAC control, GPIO |
| **MS2109** | HDMI to USB capture | In progress | Boot sequence RE'd, firmware builds, bisecting boot failure |

## What This Does

These $5 USB video dongles contain an 8051 microcontroller that loads firmware
from an external I2C EEPROM at boot. The mask ROM provides the base USB video
functionality; the EEPROM firmware extends it with signal detection, video
configuration, and interrupt handling.

This project replaces the stock EEPROM firmware with custom C code that adds
host-accessible features via a mailbox protocol over the existing HID interface.
No hardware modification required — just reflash the EEPROM.

### MS2107 Features (CVBS Capture)

All features accessible via XDATA mailbox at `0xD210-0xD219`, using the
standard HID XDATA read (0xB5) and write (0xB6) commands:

| Command | Feature | Description |
|---------|---------|-------------|
| 0x01 | Signal status | NTSC/PAL detection, lock state, line count |
| 0x02 | Image read | Brightness, contrast, saturation, hue values |
| 0x03 | Image write | Set brightness/contrast/saturation/hue |
| 0x04 | Input select | Force CVBS, S-Video, G1IN, or auto-detect |
| 0x05 | GPIO read | P0, P2, P3 port states |
| 0x06 | GPIO write | Set P0, P2, or P3 port values |
| 0x10 | I2C write | Send byte to I2C device |
| 0x11 | I2C read | Read byte from I2C device register |
| 0x12 | I2C scan | Scan 6 addresses, return bitmap |

The I2C master turns the capture dongle into a USB-to-I2C bridge — useful for
communicating with sensors, EEPROMs, or other I2C devices on the same board.

### MS9123 Features (USB Display Adapter)

Mailbox at `0xDDF0-0xDDF9`, same HID protocol:

| Command | Feature | Description |
|---------|---------|-------------|
| 0x01 | Display status | Mode, output params, host connection state |
| 0x02 | Output mode | Switch between NTSC and PAL output |
| 0x03 | DAC read | 10-bit DAC samples and config registers |
| 0x04 | DAC write | Set DAC configuration (F880/F005/F020) |
| 0x05 | GPIO read | P0, P2, P3, P3ALT, DAC readback |
| 0x06 | GPIO write | Set P0, P2, or P3 port values |

## Building

Requirements: [SDCC](https://sdcc.sourceforge.net/) (8051 C compiler),
[as31](https://github.com/pjkundert/as31) (8051 assembler).

```bash
# Install on Ubuntu/Debian
sudo apt install sdcc as31

# Build MS2107 firmware
cd ms2107/eeprom
make

# Build MS9123 firmware
cd ms9123/eeprom
make

# Build with custom USB strings (MS2107 only)
cd ms2107/eeprom
make CUSTOM_STRINGS='-DCUSTOM_USB_SERIAL="\"MySerial\""'
```

Output: `eeprom_image.bin` — a complete 2048-byte EEPROM image with header,
checksums, and firmware code. Flash to the device's I2C EEPROM using
[ms-tools](https://github.com/BertoldVdb/ms-tools) or any I2C programmer.

## Flashing

Using ms-tools (requires the device to be connected via USB):

```bash
# Read current EEPROM (backup!)
./ms-tools --raw-path /dev/hidraw0 --no-firmware read EEPROM 0 --filename=backup.bin

# Write new firmware
./ms-tools --raw-path /dev/hidraw0 --no-firmware write-file --verify EEPROM 0 eeprom_image.bin

# Power cycle the device to boot new firmware
```

The firmware is stored in a 2KB I2C EEPROM (24C16). Power cycling the device
causes the mask ROM to reload the EEPROM contents. The original firmware can
always be restored by reflashing the backup.

## Host-Side Usage

The mailbox protocol uses the HID XDATA read/write interface that all
Macrosilicon devices expose:

```python
import hid

d = hid.device()
d.open(0x534D, 0x2109)  # or appropriate VID:PID

# Write command: signal status (MS2107)
d.send_feature_report([0x00, 0xB6, 0xD2, 0x10, 0x01, 0x00, 0x00, 0x00, 0x00])

# Wait briefly for processing
import time; time.sleep(0.05)

# Read status byte
d.send_feature_report([0x00, 0xB5, 0xD2, 0x13, 0x00, 0x00, 0x00, 0x00, 0x00])
resp = d.get_feature_report(0, 9)
status = resp[4]  # 0x02 = done

# Read response bytes
for addr in range(0xD214, 0xD21A):
    d.send_feature_report([0x00, 0xB5, addr >> 8, addr & 0xFF, 0x00, 0x00, 0x00, 0x00, 0x00])
    resp = d.get_feature_report(0, 9)
    print(f"  0x{addr:04X} = 0x{resp[4]:02X}")
```

## Project Structure

```
macrosilicon/
  ms2107/eeprom/          MS2107 firmware source + build
    eeprom_fw.c            Main firmware (C, compiled with SDCC)
    crt0_ms2107.asm        Custom startup: hook entries, calling convention
                           shims, IRQ handler, ROM function wrappers
    hw_defs.h              Hardware register definitions
    rom_stubs.h             ROM function declarations
    build_eeprom.py        EEPROM image builder (header + checksums)
    Makefile               Build: crt0 + C -> ihx -> bin -> EEPROM image
  ms2107/rom/              ROM analysis artifacts
    boot_annotated.md      Annotated boot sequence

  ms9123/eeprom/          MS9123 firmware source + build (same structure)
  ms9123/rom/
    boot_annotated.md      Annotated boot sequence
    i2c_analysis.md        I2C bus analysis (two buses, pin mapping)

  ms2109/eeprom/          MS2109 firmware source + build
    eeprom_fw.c            Main firmware (C, compiled with SDCC)
    crt0_ms2109.asm        Custom startup: hook entries, IRQ handler (assembly),
                           register programming, ROM function wrappers
    hw_defs.h              Hardware register definitions (w/ datasheet pin map)
    rom_stubs.h            ROM function declarations
    build_eeprom.py        EEPROM image builder (no-skip checksum, same as MS9123)
    build_minimal_test.py  Build known-good 33-byte baseline EEPROM
    Makefile               Build: crt0 + C -> ihx -> bin -> EEPROM image
  ms2109/rom/
    boot_annotated.md      Full hook architecture, CODE/XDATA overlay, recovery notes
    eeprom_disasm.txt      Stock EEPROM code disassembly (our disasm8051.py)
    eeprom_disasm_r2.txt   Stock EEPROM code disassembly (radare2)
    rom_key_functions.txt  Key ROM function disassembly (radare2)

  tools/                   Reusable analysis tools
    diff8051.py            8051 binary semantic diff (raw/fuzzy/semantic)
    disasm8051.py          Simple 8051 disassembler for firmware code blocks
    ms_hid.py              HID communication library for Macrosilicon devices
    ms_movc_dump.py        CODE space dump via RAM-patched MOVC handler
    ms_xdata_dump.py       XDATA dump (single-byte reads)
    ms_eeprom_checksum.py  EEPROM checksum calculator (MS2107 + MS9123 variants)
    bp5_eeprom.py          Bus Pirate 5 EEPROM recovery tool (2.5V, I2C, 24C16)
    GhidraSetup.java       Ghidra headless: seed entry points for MS2107
    GhidraSetup2109.java   Ghidra headless: seed entry points for MS2109
    GhidraRename.java      Ghidra headless: rename 69 MS2107 ROM functions
    GhidraExportClean.java Ghidra headless: export decompilation + disassembly

  docs/                    Research documentation
    macrosilicon-notes.md  Main research notes (chip family, EEPROM format, etc.)
    feature-ideas.md       Feature ideas for both chips
    ms2107-rom-init-sequence.md  Detailed ROM init sequence analysis
    ms2109-datasheet.pdf   MS2109 datasheet (HJ-BMJL-PD-002, rev B/0)
```

## Architecture Notes

### EEPROM Layout

```
[0x00-0x01]  Magic (0x0816 for MS2107, 0xA55A for MS2109/MS9123)
[0x02-0x03]  Code length (determines checksum position)
[0x04-0x07]  VID/PID (MS2107) or hook config (MS2109/MS9123)
[0x08-0x0F]  Hook flags + config bytes
[0x10-0x2F]  USB string descriptors (MS2107 only)
[0x30 .. 0x30+len-1]    Checksummed firmware code
[0x30+len .. 0x30+len+3] Checksums (uint16 BE: header + code)
```

### Calling Conventions

The mask ROM is compiled with Keil C51. Our EEPROM firmware is compiled with
SDCC. These use incompatible calling conventions:

| | Keil C51 (ROM) | SDCC (our code) |
|--|----------------|-----------------|
| First uint8_t arg | R7 | DPL |
| Return value | R7 / carry | DPL |

The custom crt0 assembly handles all convention bridging — C code doesn't
need to worry about it. The IRQ handler is written in assembly rather than C
because SDCC's code generation for interrupt-context code produced subtle
differences that broke USB enumeration.

### Key Lesson: SDCC + 8051 Interrupts

SDCC generates "functionally equivalent" but not byte-identical code for
operations like comparisons (`CJNE A,direct` vs `MOV R7,direct; CJNE R7,#imm`)
and bit tests (`JNB ACC.7` vs `ANL A,#0x80; JNZ`). In normal code these are
interchangeable. In interrupt handlers called by the mask ROM's USB stack,
the exact instruction choices matter — the wrong variant breaks USB descriptor
enumeration. When in doubt, write interrupt handlers in assembly.

## License

The firmware source code in this repository is original work. The mask ROM
contents are proprietary to Macrosilicon and are not included. ROM analysis
outputs (decompiled C, disassembly) are excluded via .gitignore.

## Acknowledgments

- [BertoldVdb/ms-tools](https://github.com/BertoldVdb/ms-tools) — the
  essential tool for communicating with these chips
- [amnemonic/MacroSilicon](https://github.com/amnemonic/MacroSilicon) — HID
  protocol documentation and reference dumps
- [alexbsys/macrosilicon_ms2107_research](https://github.com/alexbsys/macrosilicon_ms2107_research) —
  prior EEPROM structure research
