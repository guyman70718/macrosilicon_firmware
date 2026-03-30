# TODO

## MS2107 (CVBS Capture)

- [ ] Feature: SPI bitbang master (51 bytes free — tight but possible for write-only)
- [ ] Host-side Python tool for mailbox protocol
- [ ] Document the XDATA register map more completely (F8xx, FBxx, FCxx regions)

## MS9123 (USB Display Adapter)

- [x] Feature: I2C master — WORKING
  - EEPROM is on **Bus B** (P3.3/P3.4), 24C16 at 7-bit 0x50-0x57
  - Root causes: P3ALT clear broke pin control; Bus B delay too fast
  - Fix: leave P3ALT at default, set delay 0x0F at init
  - Mailbox cmds: 0x10 write, 0x11 read, 0x12 scan (7-bit addrs)
- [x] Feature: test pattern generator (host-side, ms_testpattern.py)
  - SMPTE ECR-1-1978, PM5544, solid colors, grid
  - Sends frames via USB bulk EP4, no display drivers needed
- [ ] Feature: power management (DAC standby on host disconnect)
- [ ] Host-side Python tool for mailbox protocol
- Note: PAL/NTSC mode switching is host-side via 0xA6 protocol
  (mode 0x0200=NTSC 720x480, 0x1100=PAL 720x576) — confirmed on CRT

## MS2109 (HDMI Capture)

- [ ] I2C write command
- [ ] GPIO write command
- [ ] Color bars / test pattern customization on no-signal
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
- [ ] MS9123: PnP disable/enable does NOT reload EEPROM — must physical replug
