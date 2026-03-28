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
- [ ] ROM is completely different from MS2107/MS9123 (near-zero code match)
- [ ] Reverse-engineer init sequence (reset vector at 0x4149)
- [ ] Map EEPROM header fields (hook config at [4], no-skip checksum)
- [ ] Reconstruct EEPROM firmware in C
- [ ] Build and test custom firmware
- [ ] Add mailbox features (same protocol as MS2107/MS9123)

## General

- [ ] Unify mailbox command IDs across all three chips
- [ ] Write host-side Python library (ms_mailbox.py) using ms_hid.py
- [ ] Investigate MS9123 hardware SPI support (datasheet mentions SPI pins)
- [ ] Explore MS9123 Bus B I2C (peripheral bus, different pins from Bus A)
- [ ] Add more Ghidra function renames for MS2109 (currently using generic names)
