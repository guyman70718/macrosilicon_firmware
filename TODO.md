# TODO

## MS2107 (CVBS Capture)

- [ ] Feature: SPI bitbang master (51 bytes free — tight but possible for write-only)
- [ ] Host-side Python tool for mailbox protocol
- [ ] Document the XDATA register map more completely (F8xx, FBxx, FCxx regions)

## MS9123 (USB Display Adapter)

- [ ] Feature: I2C master — NOT WORKING
  - EEPROM is on **Bus B** (P3.3/P3.4), not Bus A (P3.7/P3.6)
  - E5 HID command reads EEPROM via Bus B successfully
  - Calling the same Bus B ROM functions from firmware returns 0x00
  - Full 32K ROM dump available (`dumps/MS9123_CODE_lower32k.bin`)
  - All ROM I2C helpers fully disassembled (see i2c_analysis.md)
  - ROM helpers do `CLR P2.x` when driving LOW (pin mux control?)
  - Scan shows false ACKs (P2.x stuck low) — root cause unclear
  - SFR_95 bit 6 toggle crashes device (even with CCAP0L gate)
  - USB IRQ hook at CODE 0xC903 — needs LJMP trampoline at +0xD3
  - Next: trace E5 handler setup, investigate HW I2C at F022-F025
- [ ] Feature: test pattern generator (no-host mode)
- [ ] Feature: power management (DAC standby on host disconnect)
- [ ] Tune PAL timing values (currently best-guess from datasheet)
- [ ] Host-side Python tool for mailbox protocol

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
