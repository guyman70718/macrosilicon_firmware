# TODO

## MS2107 (CVBS Capture)

- [x] EEPROM dump verified
- [x] Full mask ROM dumped (64KB CODE space via MOVC)
- [x] ROM analyzed with Ghidra (69 named functions, 294 total)
- [x] EEPROM firmware reconstructed in C (20 functions)
- [x] Custom firmware boots and enumerates correctly
- [x] Feature: signal status reporting (cmd 0x01)
- [x] Feature: image adjustment read/write (cmd 0x02/0x03)
- [x] Feature: video input switching (cmd 0x04)
- [x] Feature: GPIO read/write (cmd 0x05/0x06)
- [x] Feature: I2C master scan/read/write (cmd 0x10/0x11/0x12)
- [x] Feature: USB string override (build-time, serial + manufacturer)
- [ ] Feature: SPI bitbang master (51 bytes free — tight but possible for write-only)
- [ ] Host-side Python tool for mailbox protocol
- [ ] Document the XDATA register map more completely (F8xx, FBxx, FCxx regions)

## MS9123 (USB Display Adapter)

- [x] EEPROM dump verified
- [x] Full CODE space dumped (MOVC via RAM-patched hook)
- [x] ROM analyzed with Ghidra (518 functions)
- [x] EEPROM firmware reconstructed in C
- [x] Custom firmware boots and enumerates correctly
- [x] Feature: display status reporting (cmd 0x01)
- [x] Feature: PAL/NTSC output mode switching (cmd 0x02)
- [x] Feature: DAC output level read/write (cmd 0x03/0x04)
- [x] Feature: GPIO read/write (cmd 0x05/0x06)
- [ ] Feature: I2C master — NOT WORKING (pin mux issue after display_hw_init)
  - Bus A functions (0x6AB8/0x6919/0x46BC/0x4B9B) are correct
  - P2.2 bus enable isn't sufficient — undocumented SFRs (0x93/0x95/0x9B/0x9D)
    control the shared SPI/I2C pin mux and are reconfigured by display init
  - Need to trace the full pin mux SFR sequence from boot-time EEPROM load
  - See ms9123/rom/i2c_analysis.md for current analysis
- [ ] Feature: test pattern generator (no-host mode)
- [ ] Feature: power management (DAC standby on host disconnect)
- [ ] Tune PAL timing values (currently best-guess from datasheet)
- [ ] Host-side Python tool for mailbox protocol

## MS2109 (HDMI Capture)

- [x] EEPROM dumped (2048 bytes, magic 0xA55A, 1735 bytes code)
- [x] CODE space dumped (64KB via MOVC)
- [x] XDATA dumped (64KB)
- [x] Initial Ghidra analysis (82 functions)
- [x] Boot sequence and hook architecture fully documented
  - Hook config: EEPROM[4] bit 0 = normal (+0x00), bit 2 = IRQ (+0x20)
  - Callback at +0x10 called from ROM via cmd 0x08 with data table address
  - CODE/XDATA overlay at 0xC000-0xDFFF (ROM read-through for unwritten areas)
  - Checksum: no-skip formula (same as MS9123, verified)
  - See ms2109/rom/boot_annotated.md
- [x] EEPROM header fields mapped
- [x] ROM function map (I2C, video processing, mul16, jump table engine)
- [x] Stock IRQ handler reverse-engineered (signal detection state machine)
- [x] Stock register programming function reverse-engineered
  - 25-byte config table, 149 XDATA writes via mul16 address computation
- [x] EEPROM firmware reconstructed in pure assembly
  - crt0_ms2109.asm: all hooks, IRQ handler, register programming,
    EDID, reg_table, video_config, mul16, jump_table_engine, math_func,
    mailbox dispatch — no C code, no stock dump dependency at build time
  - Trampolines at fixed CODE addresses for ROM callbacks
  - 1664 bytes (332 bytes free)
- [x] Minimal test firmware boots and enumerates (eeprom_minimal_test.bin)
- [x] Custom firmware boots, enumerates, mailbox works (signal status, GPIO)
- [ ] Video capture not working — normal hook needs passthrough to ROM dispatch

### Video passthrough (next step)

Reimplement the ROM command dispatch inline in our normal hook. No trampolines
at 0xD03A/0xD104 needed — just handle each command in our switch statement.

All command handlers are fully disassembled. Most are simple register writes.
Four call helper functions which are also fully understood:

| Cmd | Handler | Complexity |
|-----|---------|------------|
| 0x00 | Init video regs (C781,C783,C782,DE0C,F80B,F814) | Simple |
| 0x01 | FE20=0x2A, call ROM 0x603C+0x5884, C697=2 | Calls ROM |
| 0x02 | Call ROM 0x603C (via 0xD249 logic), conditional EFE8 setup | Calls ROM |
| 0x08 | Set R3:R2:R1, LJMP callback | Simple |
| 0x0A | F9AF=0x22 | Trivial |
| 0x0B | F92C,E33C-E33F,FEBA register setup | Simple |
| 0x0C | FD02/FD03 timing based on IRAM[0x36] (5 cases) | Medium |
| 0x0E | Call ROM 0x603C+0x5884 (same as init_helper) | Calls ROM |
| 0x0F | C54F,EFD0-EFD3 register clear | Simple |
| 0x14 | Call video_adjust + delay | Calls ROM |

Helper functions (all just call real ROM):
- _video_adjust: 92 bytes, reads C6xx regs, calls video_config
- _init_helper: calls ROM 0x603C, writes F814, calls ROM 0x5884
- _delay_helper: writes DE0A=R7, calls ROM 0x69FB

### Future features

- [ ] I2C master (ROM wrappers ready: start/stop/write/read)
- [ ] Host-side Python tool for mailbox protocol

### Recovery notes

- Bus Pirate 5 on COM7, clip attached to EEPROM
- **Must use 2.5V** — at 3.3V the MS2109 back-powers and interferes with I2C writes
- **Must unplug USB** before BP5 write
- WP pin grounded via BP5 IO4
- Stock firmware on BP5 storage as `ms2109.bin`
- `eeprom_minimal_test.bin` is a known-good 33-byte baseline

## General

- [ ] Unify mailbox command IDs across all three chips
- [ ] Write host-side Python library (ms_mailbox.py) using ms_hid.py
- [ ] Investigate MS9123 hardware SPI support (datasheet mentions SPI pins)
- [ ] Explore MS9123 Bus B I2C (peripheral bus, different pins from Bus A)
- [ ] Add more Ghidra function renames for MS2109 (currently using generic names)
