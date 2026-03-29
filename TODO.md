# TODO

## MS2107 (CVBS Capture)

- [ ] Feature: SPI bitbang master (51 bytes free — tight but possible for write-only)
- [ ] Host-side Python tool for mailbox protocol
- [ ] Document the XDATA register map more completely (F8xx, FBxx, FCxx regions)

## MS9123 (USB Display Adapter)

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
- [ ] Explore MS9123 Bus B I2C (peripheral bus, different pins from Bus A)
