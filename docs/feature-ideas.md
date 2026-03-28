# Custom Firmware Feature Ideas

Once the reconstructed EEPROM firmware is working, these features could be added using the ~600 bytes of free EEPROM space. All would be accessible via HID feature reports through the existing hook command dispatch.

## 1. Video Input Switching via HID

**Priority: High** | **Complexity: Low**

The MS2107 has 4 video inputs (CVBS pin 8, S-Video Y pin 6, S-Video C pin 3, G1IN pin 5) with hardware auto-detection. The stock firmware always auto-selects, with no way to override from software.

A new HID command could force-select a specific input by writing to the video ADC routing registers in the F8xx/FBxx region. Useful for:
- Multi-camera setups (switch inputs without replugging)
- Forcing S-Video when CVBS is also connected
- Using the G1IN auxiliary input

The hook dispatch at 0xC800 already has a switch on R7 with spare command IDs (3, 4, 6, 8, 9, 11, 12, 14, 15...) available.

## 2. Image Adjustment Controls

**Priority: Medium** | **Complexity: Low**

The datasheet lists brightness, contrast, saturation, and hue adjustment as supported features, but the stock firmware exposes no user controls. These are almost certainly register writes in the video processing block (F8xx region).

HID commands to read/write these parameters would enable real-time image tuning from software — useful for capture applications where the source signal isn't ideal.

## 3. Signal Status Reporting

**Priority: Medium** | **Complexity: Low**

The firmware already monitors signal lock state, NTSC vs PAL detection, line counts (FB8D/FB8E), and VSync status (FBD6/FBD9). None of this is exposed to the host.

A HID "query status" command could return:
- Signal present / locked / standard (NTSC/PAL)
- Detected line count
- Active input channel
- Current frame rate / timing parameters

This would let capture software detect signal changes without relying on UVC stream errors.

## 4. General-Purpose I2C Master

**Priority: High** | **Complexity: Medium**

The MS2107 has an I2C bus (GPIO2=SCL, GPIO3=SDA) used for EEPROM access. The ROM's HID commands (0xE5/0xE6) only support EEPROM-specific operations with the awkward feature report interface (1-5 bytes at a time, fixed device address 0xA0).

A custom I2C master exposed via HID would allow arbitrary I2C transactions:
- Any device address (not just 0xA0)
- Multi-byte read/write in a single command
- Start/stop/repeated-start control
- Bus scan

This turns the MS2107 into a USB-to-I2C bridge — useful for:
- Communicating with other chips on the same board (sensors, EEPROMs, DACs)
- Using the capture device as a general I2C debug tool
- Reading/writing larger EEPROMs (24C32, 24C64) that the stock commands can't address

The ROM already has I2C primitives (start at 0x68BD, stop at 0x6B5B, write byte at 0x5323, read byte at 0x5934). The EEPROM hook code just needs to expose them through a cleaner HID command protocol. ms-tools already does something similar via its runtime patching callgate — this would bake it into the EEPROM firmware permanently.

**Protocol sketch** (using a spare HID command ID):
```
HID report [0x00, CMD_I2C, sub_cmd, ...]

sub_cmd 0x01: I2C write
  [CMD_I2C, 0x01, dev_addr, reg_addr, len, data0, data1, data2]

sub_cmd 0x02: I2C read
  [CMD_I2C, 0x02, dev_addr, reg_addr, len, 0, 0, 0]
  Response in next GET_FEATURE: [CMD_I2C, 0x02, len, data0, data1, data2, data3, data4]

sub_cmd 0x03: I2C scan
  [CMD_I2C, 0x03, start_addr, 0, 0, 0, 0, 0]
  Response: [CMD_I2C, 0x03, found_addr, next_addr, ...]
```

## 5. GPIO Control

**Priority: Low** | **Complexity: Very Low**

The MS2107 has 4 GPIOs:
- GPIO0 (pin 35): Audio source select (GND=I2S, float=internal ADC)
- GPIO2 (pin 13): Shared with EEPROM SCL
- GPIO3 (pin 12): Shared with EEPROM SDA
- GPIO4 (pin 19): EEPROM write protect

Exposing GPIO read/write via HID would enable:
- Switching audio source between internal ADC and external I2S at runtime
- Using GPIO4 as a general-purpose output (since WP isn't needed after boot)
- Reading GPIO0 to check current audio source configuration

ms-tools already has a GPIO blob that reads/writes P2 (state) and P3 (direction) SFRs. A permanent version in EEPROM would be trivial.

## 8. SPI Bitbang Master (MS2107)

**Priority: High** | **Complexity: Medium**

The MS2107 has 3 GPIOs free after boot (the EEPROM is only accessed during init):

| Pin | GPIO | SPI Role |
|-----|------|----------|
| 13 | GPIO2 (SCL) | SCLK |
| 12 | GPIO3 (SDA) | MOSI |
| 19 | GPIO4 (WP) | CS or MISO |

**On-chip bitbang (fast):** An 8051 SPI routine in EEPROM firmware toggles GPIOs directly via P2/P3 SFRs. At 12MHz, the 8051 can bitbang SPI at ~1MHz (each bit = CLK high + shift + CLK low = ~12 cycles). This gives **~125KB/s** throughput for on-chip transfers. The host sends a "SPI transfer" HID command; the 8051 executes the full transaction and returns the response.

With only 3 pins, options are:
- **3-wire (no MISO):** SCLK + MOSI + CS — write-only SPI, sufficient for controlling SPI peripherals (DACs, shift registers, LED drivers, SPI flash writes)
- **3-wire (half-duplex):** SCLK + MOSI/MISO (shared on GPIO3) + CS — bidirectional but not simultaneous. GPIO3 switches direction between write and read phases. Works for SPI flash read/write.
- **External CS:** Use GPIO4 as MISO instead of CS, manage CS externally or with a pull-up. Full-duplex SPI.

**Protocol (via extended command mailbox):**
```
CMD 0x20: SPI Transfer
  [0x20, config, len, d0, d1, d2]
  config: bit0=CPOL, bit1=CPHA, bit2=CS_assert, bit3=CS_release
  Response: [len, r0, r1, r2, r3, r4]

CMD 0x21: SPI Config
  [0x21, speed_div, pin_mode, 0, 0, 0]
  speed_div: 0=max speed, 1-255=insert delays
  pin_mode: 0=3-wire write-only, 1=3-wire half-duplex, 2=4-wire (ext CS)
```

**MS9123 note:** The MS9123 has dedicated SPI pins (SPI_CS/MOSI/MISO/SCLK on P3) shared with I2C. It may have hardware SPI support in its SFRs — worth investigating before resorting to bitbang. If hardware SPI exists, throughput could be much higher.

Estimated code: ~60 bytes for basic write-only, ~100 bytes for half-duplex with configurable mode.

**Use cases:**
- Driving SPI peripherals from a USB-connected capture device (sensors, displays, actuators)
- Programming SPI flash chips in-circuit
- Combined with video capture: read sensor data synchronized with video frames
- USB-to-SPI debug bridge (like Bus Pirate but with simultaneous video capture)

## Implementation Notes

- All features use the existing normal hook dispatch (0xC800, R7=command ID)
- Spare command IDs available: 3, 4, 6, 8, 9, 11, 12, 14, 15+
- ~600 bytes of free EEPROM space (offsets 0x0602-0x07FF)
- The I2C master is the most ambitious but also the most broadly useful
- Features 1-3 and 5 are probably <50 bytes of code each
- All features are safe to test — they don't affect USB enumeration

---

# MS9123 Custom Firmware Feature Ideas

The MS9123 is a USB-to-CVBS/S-Video display adapter with ~1600 bytes of free EEPROM space (0x0200-0x07FF). Its architecture is different from the MS2107 — instead of a command dispatch, it runs an infinite display service loop (init hook 2) with a periodic USB IRQ handler. The existing mailbox at XDATA[0xDDFF] provides a host→device command channel.

From the datasheet: 10-bit 3-channel DAC (CVBS + S-Video Y/C), 720x480 NTSC and 720x576 PAL output, 24MHz crystal + PLL, I2S audio out, SPI/I2C shared pins.

## 1. Extended Host Command Protocol

**Priority: High** | **Complexity: Medium**

The stock firmware checks XDATA[0xDDFF] for the single value 0x5A to trigger `rom_safe_reconfig()`. This is a crude one-command mailbox. Expanding it into a proper protocol unlocks all other features.

**Design:** Use XDATA[0xDDF0-0xDDFF] as a 16-byte command/response mailbox:
```
0xDDF0: [cmd_id]     Host writes command ID (non-zero = pending)
0xDDF1: [param0]     Command parameters (up to 6 bytes)
0xDDF2: [param1]
...
0xDDF7: [param5]
0xDDF8: [status]     Firmware writes: 0=idle, 1=busy, 2=done, 0xFF=error
0xDDF9: [resp0]      Response data (up to 6 bytes)
...
0xDDFE: [resp5]
0xDDFF: [trigger]    Legacy 0x5A trigger preserved for compatibility
```

The periodic hook (called from USB IRQ) polls `cmd_id`. When non-zero, it processes the command, writes the response, sets status=done, and clears cmd_id. The host reads status via 0xB5 and retrieves results.

This fits in ~80 bytes of code and is the foundation for everything below.

## 2. Output Mode Switching (PAL/NTSC)

**Priority: High** | **Complexity: Low**

The stock firmware hardcodes one output timing configuration in the periodic handler's reconfigure path:
```c
scaler_hsize = 0x60;       // C343
scaler_vtiming0 = 0x02;    // C347
scaler_vtiming1 = 0x03;    // C348
cvbs_timing = 0x0D;        // C4DA
```

The datasheet supports both 720x480 NTSC and 720x576 PAL. A host command could switch between two preset tables:

| Register | NTSC (stock) | PAL (TBD) |
|----------|-------------|-----------|
| C343 | 0x60 | 0x60 |
| C347 | 0x02 | TBD (different vertical timing) |
| C348 | 0x03 | TBD |
| C4DA | 0x0D | TBD (different sync width) |

The PAL values need to be determined experimentally or from the ROM's own mode tables (the ROM likely has both sets somewhere). The `rom_clock_reconfig()` call handles the PLL retune.

Estimated code: ~40 bytes (two 4-byte tables + switch logic).

## 3. DAC Output Level Control

**Priority: Medium** | **Complexity: Low**

The MS9123's 10-bit 3-channel video DAC drives CVBS (pin 32), S-Video Y (pin 33), and S-Video C (pin 34). The firmware already reads DAC levels via SFR 0xAB (8 samples in `dac_snapshot_and_check()`), but there's no host-accessible control.

Host commands could:
- **Read DAC levels:** Return the 8-sample snapshot from IRAM[0x55-0x5C]. Lets the host monitor output signal quality.
- **Set DAC bias:** Write to `video_dac_cfg` (F880) and `dac_ctrl` (F005) to adjust output levels. Useful for matching specific display requirements or compensating for cable losses.
- **Per-channel enable:** The DAC has 3 independent channels. Selective enable/disable of CVBS vs S-Video output, or routing different content to each.

Estimated code: ~50 bytes for read, ~30 bytes for write.

## 4. Test Pattern Generator

**Priority: Medium** | **Complexity: Medium**

Output a known video pattern without a USB host connected. Useful for:
- Verifying the device works without a computer
- Display calibration / burn-in testing
- Demonstrating the device at trade shows

**Implementation approaches:**

*Option A — Static register fill (~60 bytes):*
In the init hook 2 service loop, detect "no host connected" (P0.0 low for N iterations), then write a fixed value to the DAC output registers. This produces a single color field (e.g., 75% white for color bar reference).

*Option B — ROM-assisted pattern (~100 bytes):*
The ROM's `rom_generic_display()` (0x2DA2) takes a mode parameter in IRAM[0x3F]. Different mode values might produce different internal patterns. Experimentation needed to find useful values.

*Option C — Timed pattern (~200 bytes):*
Use the delay function and direct DAC writes to generate horizontal bars by changing the output level at timed intervals within a frame. More complex but produces a recognizable pattern.

Option A is the most practical. The host command protocol could also trigger pattern mode explicitly.

## 5. I2C / SPI Bridge

**Priority: High** | **Complexity: Medium**

The MS9123 has SPI/I2C shared pins (datasheet pins 1-4):
- Pin 1: GPIO2/SPI_CS
- Pin 2: SPI_MOSI/I2C_SCL
- Pin 3: SPI_MISO
- Pin 4: SPI_SCLK/I2C_SDA

These connect to the EEPROM by default, but after boot the EEPROM is no longer accessed. The I2C bus is available for arbitrary use.

Same concept as the MS2107 I2C bridge idea — expose I2C master operations via the host command protocol. The ROM should have I2C primitives somewhere (the EEPROM load uses them). Need to identify the MS9123's I2C function addresses in the ROM dump.

This turns the MS9123 into a USB-to-I2C bridge that simultaneously outputs video — useful for controlling external I2C devices (sensors, other DACs, display controllers) from the same USB connection.

**Protocol** (via the extended command mailbox):
```
CMD 0x10: I2C Write — [0x10, dev_addr, reg_addr, len, d0, d1]
CMD 0x11: I2C Read  — [0x11, dev_addr, reg_addr, len, 0, 0]
                       Response: [len, d0, d1, d2, d3, d4]
CMD 0x12: I2C Scan  — [0x12, start_addr, 0, 0, 0, 0]
                       Response: [found0, found1, found2, found3, found4, next]
```

Estimated code: ~150 bytes (depends on whether ROM I2C primitives exist or we need bit-bang).

## 6. Power State Management

**Priority: Low** | **Complexity: Very Low**

The datasheet shows:
- Active mode: 130mA (3.3V supply)
- Sleep mode: 50mA

When the USB host disconnects (P0.0 goes low), the firmware could:
1. Wait N frames to confirm (debounce)
2. Put the DAC into standby: `dac_ctrl |= 0x08` (F005 bit 3)
3. Optionally disable the PLL to save more power
4. Wake on P0.0 going high (host reconnect)

This is a ~20 byte change to the service loop's host detection path. Saves 80mA — meaningful for bus-powered devices.

## 7. I2S Audio Path Control

**Priority: Low** | **Complexity: Low**

The MS9123 outputs 48KHz/16bit stereo audio via I2S (pins 18-23). The audio path is entirely ROM-managed — the EEPROM firmware doesn't touch it. But we could add:
- **Audio mute on video disconnect:** When the host stops sending video, mute the I2S output to avoid noise on the audio path. Unmute when video resumes.
- **Audio-only mode:** If the host sends audio but no video, keep the I2S output active while putting the video DAC in standby.

The I2S output pins are configured during `rom_display_hw_init()`. Muting likely involves writing to an audio control SFR or the I2S configuration registers in the F1xx area.

Estimated code: ~30 bytes.

## Implementation Notes

- The extended command protocol (feature 1) should be implemented first — it's the substrate for features 2-5
- ~1600 bytes free in EEPROM — plenty of room for all features combined
- The periodic hook runs from USB IRQ context — keep command handlers short (<100 cycles) to avoid USB timing issues. Longer operations should set a flag and execute in the service loop.
- The service loop in init hook 2 is the right place for test patterns and power management — it runs continuously and already handles frame pacing.
- All features are safe to test on hardware — none affect USB enumeration or EEPROM integrity. Power cycle recovers from any video output issue.
- The 0x5A legacy trigger should be preserved for compatibility with existing ROM behavior
