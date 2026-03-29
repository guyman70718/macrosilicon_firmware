# MS2109 Boot Sequence and Hook Architecture

## Chip Overview

The MS2109 is an HDMI-to-USB2.0 capture chip (datasheet HJ-BMJL-PD-002, rev B/0):
- Chip ID byte at `XDATA[0xF800]` = `0xA7`
- VID:PID = `0x534D:0x2109` ("MACROSILICON USB Video")
- 8051 core with mask ROM, external I2C EEPROM (24C16)
- HD RX 1.4b: max 4K@30Hz input, capture up to 1920x1080@30Hz
- UVC 1.0: MJPEG + YUV422 output, UAC 1.0 audio
- QFN-48, 24MHz crystal, internal PLL

### GPIO Pin Assignments (from datasheet)

| GPIO | Pin | Default Function |
|------|-----|-----------------|
| GPIO0 | 39 | LED indicator (0=playing, 1=idle) |
| GPIO1 | 40 | User-defined, internal pull-up |
| GPIO2 | 13 | EEPROM SCL (I2C clock, shared bus) |
| GPIO3 | 14 | EEPROM SDA (I2C data, shared bus) |
| GPIO5 | 37 | EEPROM WP (write protect) |

## EEPROM Header Format

```
Offset  Value   Meaning
0x00-01 A5 5A   Magic (also accepts 0x9669)
0x02-03 06 C7   Code length (big-endian, stock = 1735 bytes)
0x04    05      Hook config bitmask:
                  bit 0 = normal hook at +0x00 (0xCC00)
                  bit 2 = IRQ hook at +0x20 (0xCC20)
0x05    10      Unknown config byte
0x06-0B FF...   Unused (0xFF)
0x0C-0D 20 20   Config bytes
0x0E-0F 07 07   Config bytes
0x10-2F FF...   Unused
0x30+   code    Firmware code (loaded to XDATA 0xCC00)
```

### Checksums

Two big-endian uint16 checksums stored immediately after the code:

```
code_length = uint16_be(data[0x02:0x04])
end         = 0x30 + code_length

header_sum  = sum(data[0x02:0x30])     # all header bytes, no skip
code_sum    = sum(data[0x30:end])

data[end:end+2]   = uint16_be(header_sum)
data[end+2:end+4] = uint16_be(code_sum)
```

## Memory Map

### CODE/XDATA Overlay

The XDATA region 0xC000-0xDFFF is **RAM-backed**. The EEPROM loader copies
`code_length` bytes from the EEPROM into XDATA starting at 0xCC00. These bytes
become visible in CODE space at the same addresses (the 8051 fetches instructions
from this RAM overlay rather than mask ROM for this address range).

Addresses within the overlay that were NOT written by the loader contain
uninitialized RAM — **not** mask ROM content. Custom firmware must ensure that
every CODE address the ROM or firmware calls into is covered by the loaded code.

The stock EEPROM's 1735-byte code section duplicates the ROM content at
CODE 0xCC00-0xD2C6 because the overlay is RAM. Custom firmware must either
include these bytes or provide equivalent implementations at every address
the ROM calls into.

| Region | XDATA Address | Size | Description |
|--------|--------------|------|-------------|
| UserRAM | 0xC000-0xDFFF | 8KB | CODE/XDATA overlay region |
| UserConfig | 0xCBD0-0xCBFF | 0x30 | EEPROM header (bytes 0x00-0x2F) |
| EEPROM code | 0xCC00+ | variable | EEPROM code (bytes 0x30+) |
| USB descriptor | 0xC688-0xC69F | 18 | USB device descriptor (VID at 0xC690, PID at 0xC692) |
| Mailbox/work | 0xDE00-0xDE0F | 16 | Firmware working area |
| Config regs | 0xC6AA-0xC6C5 | varies | Video config state |
| Control regs | 0xC781-0xC783 | 3 | Hardware control |
| HW config | 0xF800-0xF8FF | varies | Hardware configuration |
| Video timing | 0xF900-0xF9FF | varies | Video timing registers |
| Status/ctrl | 0xF1FA-0xF1FF | 6 | Status and control |
| HW control | 0xFD00-0xFD40 | varies | Hardware control/data |

## Hook Architecture

### Normal Hook (0xCC00) — bit 0 of EEPROM[4]

Called from the ROM main loop with R7 = command ID. The stock EEPROM code
calls into the ROM's command dispatch functions, but custom firmware can
handle commands directly and simply return.

The ROM calls the normal hook with these command IDs:

| Command (R7) | Context | Purpose |
|-------------|---------|---------|
| 0x00 | chip_init, before video pipeline | Video register setup |
| 0x01 | chip_init, after USB descriptor build | Video mode config |
| 0x02 | Main loop, every iteration | Main video processing |
| 0x08 | Video timing | Calls callback at +0x10 with data table address |
| 0x0A | Video init | Set F9AF register |
| 0x0B | Video init | Set F92C, E33C-E33F, FEBA registers |
| 0x0C | Signal detection | Video timing update + video adjust |
| 0x0E | Video init | Init helper (same as part of cmd 1) |
| 0x0F | Video reset | Clear C54F, EFD0-EFD3 registers |
| 0x14 | Video adjust | Video adjust + delay |

Commands 0x00 and 0x01 run once during boot. Command 0x02 runs every main
loop iteration. Other commands run on signal changes or specific events.

### Callback Entry (0xCC10) — called from ROM via command 0x08

```
CC10: MOV  DPTR,#0xDE05    ; Save R3:R2:R1 to working area
CC13: MOV  A,R3
CC14: MOVX @DPTR,A
...
CC1B: LCALL 0x6345          ; Call ROM hw init function
CC1E: RET
```

The ROM calls this with R3:R2:R1 = 0xFF:0xCD:0x52 (pointing to data
at CODE 0xCD52). ROM function 0x6345 uses this address to access
configuration data tables. This callback must be preserved byte-for-byte.

### IRQ Hook (0xCC20) — bit 2 of EEPROM[4]

Called from interrupt context. Implements HDMI signal detection state machine.
Must be written in assembly for reliability in interrupt context.

**IRAM State Variables:**

| IRAM | Name | Description |
|------|------|-------------|
| 0x30 | flags | bit 0: signal toggle, bit 1: signal detected, bit 6: timing flag |
| 0x32 | video_flags | bit 3: video active |
| 0x33 | irq_flags | bit 2: timer tick (cleared after processing) |
| 0x36 | state_counter | State counter (valid when < 6) |
| 0x37 | state_value | State value (must equal 0x3C for active signal) |
| 0x38 | state_machine | 0=idle, 1=signal detecting, 2=signal active, 3=signal lost |
| 0x1B-0x1E | timer_vals | Saved from SFRs 0xBC-0xBF (timer/counter values) |
| 0x9E-0x9F | extra_state | Additional state (written to SFR 0xAE) |

**Signal Detection Flow:**
```
1. If IRAM[0x33] bit 2 set:
   - Clear bit 2
   - Call ROM 0x6069 (video processing)
   - Call register programming function

2. If IRAM[0x32] bit 3 NOT set: return (no video active)

3. Guard checks:
   - If IRAM[0x36] >= 6: return
   - If IRAM[0x37] != 0x3C: return

4. Clear IRAM[0x32] bit 3

5. Signal detection state machine (IRAM[0x38]):
   - state==1 AND signal not present: [0xDE0C] = 1 (detected)
   - state==0 AND [0xDE0C]==1 AND signal present: state=2, [0xDE0C] = 2 (active)
   - state==2 AND [0xDE0C]==2 AND signal not present: [0xDE0C] = 0, state=3 (lost)

6. SFR 0x93 = 3, P0.0 = 1

7. If signal detected: init video hardware via ROM 0x48E6

8. State machine completion:
   - state==1 AND [F1FB]==3: reset to idle, set signal flag
   - state==3: set signal flag
   (both fall through to F1FA check)

9. If [F1FA] != 0: set [F1FA]=1, set timing flag

10. Write debug state to SFR 0xAE

11-12. State 2/3 debug output, return
```

### Register Programming Function

Called from the IRQ hook after timer tick processing. Writes a 25-byte data
table to multiple groups of XDATA registers.

**Algorithm:**
```
Phase 1: for outer in 0..4, for i in 0..24:
    XDATA[outer * 0x2E + i + 0xC0BF] = reg_table[i]

Phase 2: for outer in 5..10, for i in 0..3:
    XDATA[outer * 0x2E + i + 0xC0BF] = reg_table[i]
```

Total: 149 register writes. ROM 0xD212 provides 16-bit multiply (`DPTR = DPTR * A`).

**25-byte register configuration table (at CODE 0xCE52):**
```
0A 8B 02 00 05 0A 8B 02 00 15 16 05 00 80 1A 06
00 20 A1 07 00 40 42 0F 00
```

## ROM Function Map

| Address | Name | Purpose |
|---------|------|---------|
| 0x4149 | reset_entry | Boot entry (LJMP from 0x0000) |
| 0x48E6 | hw_init_core | Core hardware init |
| 0x4648 | i2c_write_byte | I2C write (R7=byte, carry=ACK) |
| 0x4CF3 | i2c_read_byte | I2C read (bit 0x08=NAK, returns R7) |
| 0x52DD | math_inner | Inner math function (called from math_func) |
| 0x5884 | video_mode_init | Video mode initialization |
| 0x5F19 | eeprom_reload | Detect + load EEPROM code |
| 0x603C | video_setup | Video setup function |
| 0x6069 | video_process | Video frame processing |
| 0x6345 | hw_init_with_table | Uses R3:R2:R1 as data table address |
| 0x69FB | delay_func | Delay function (R7=parameter) |
| 0x6A8C | i2c_start | I2C start condition |
| 0x6ABA | i2c_stop | I2C stop condition |

### Overlay Functions (must be at fixed CODE addresses)

These addresses are called by the ROM via LCALL. Custom firmware must provide
implementations (or trampolines) at these exact CODE offsets:

| CODE Address | Offset | Name | ROM Call Sites | Size |
|-------------|--------|------|---------------|------|
| 0xCC10 | +0x010 | callback | 1 (from 0xD116) | 15 bytes |
| 0xCD52 | +0x152 | EDID data | MOVC from 0x6345 | 256 bytes |
| 0xCE52 | +0x252 | reg_table | MOVC from regprog | 25 bytes |
| 0xCE6B | +0x26B | video_config | 1 (from 0xD20E) | 243 bytes |
| 0xD212 | +0x612 | mul16 | ~54 sites | 17 bytes |
| 0xD223 | +0x623 | jump_table_engine | 1 (from i2c_stop) | 37 bytes |
| 0xD27D | +0x67D | math_func | 1 (from video_config) | 21 bytes |

## Custom Firmware Layout

The custom firmware uses trampolines at the fixed addresses and places
implementations contiguously:

```
+0x000-0x01F: Hook entries (normal LJMP, callback, IRQ LJMP)
+0x020-0x151: IRQ handler (inline, 306 bytes)
+0x152-0x251: EDID data (256 bytes, editable)
+0x252-0x26A: reg_table (25 bytes, editable)
+0x26B:       LJMP _video_config (trampoline)
+0x26E-0x5xx: Normal hook dispatch, register programming, helpers
+0x5xx-0x611: Padding
+0x612:       LJMP _mul16 (trampoline)
+0x615-0x622: Padding
+0x623:       LJMP _jump_table_engine (trampoline)
+0x626-0x67C: Small functions + data tables (in padding gap)
+0x67D:       LJMP _math_func (trampoline)
+0x680+:      Implementations (video_config, mul16, jte, math_func)
```

Total: 1983 bytes, 13 bytes free. No stock dump dependency at build time.

## EEPROM Recovery

When writing the EEPROM in-circuit, the supply voltage must be low enough
that the MS2109 chip does not power up through the board traces. At 3.3V
the chip back-powers and its I2C controller interferes with writes (ACKs
but doesn't commit). At 2.5V the chip stays below its operating threshold.

Requirements for in-circuit programming:
- Supply voltage: **2.5V** (not 3.3V)
- USB cable **disconnected** from the target device
- EEPROM WP pin grounded
- I2C pull-ups enabled
- EEPROM type: 24C16 (2KB, 8 block addresses 0x50-0x57)
