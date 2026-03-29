# MS2109 Boot Sequence and Hook Architecture (from ROM + EEPROM disassembly)

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
0x00-01 A5 5A   Magic (shared with MS9123, also accepts 0x9669)
0x02-03 06 C7   Code length = 1735 bytes
0x04    05      Hook config bitmask:
                  bit 0 = normal hook at +0x00 (0xCC00)
                  bit 2 = IRQ hook at +0x20 (0xCC20)
0x05    10      Unknown config byte
0x06-0B FF...   Unused (0xFF)
0x0C-0D 20 20   Config bytes (not checksummed on MS2107, but ARE checksummed here)
0x0E-0F 07 07   Config bytes
0x10-2F FF...   Unused
0x30+   code    Firmware code (loaded to XDATA 0xCC00)
```

### Checksums

Unlike ms-tools `csum.go` (which skips 0x0C-0x0F for MS2106), the MS2109 uses the
**same no-skip formula as the MS9123** (verified against stock EEPROM):

```
code_length = uint16_be(data[0x02:0x04])
end         = 0x30 + code_length

header_sum  = sum(data[0x02:0x30])          # NO skip — includes 0x0C-0x0F
code_sum    = sum(data[0x30:end])

data[end:end+2]   = uint16_be(header_sum)
data[end+2:end+4] = uint16_be(code_sum)
```

## Memory Map

### CODE/XDATA Overlay

The XDATA region 0xC000-0xDFFF is **RAM-backed**, not ROM read-through. The EEPROM
loader copies `code_length` bytes to XDATA 0xCC00+. Addresses within the overlay
that were NOT written by the loader contain **zeros or garbage, NOT ROM content**.

**This means ROM fallthrough does NOT work.** A shorter `code_length` leaves the
upper overlay region uninitialized — instruction fetches and MOVC reads at those
addresses return whatever is in uninitialized RAM, not the mask ROM code.

Verified 2026-03-29: a 619-byte firmware (code_length=0x026B) with byte-identical
content to stock in the first 619 bytes fails to enumerate, while the same bytes
padded to stock length (code_length=0x06C7 = 1735) boots correctly. The overlay
region past the loaded code was NOT falling through to ROM.

The stock EEPROM's 1735-byte code section is a byte-for-byte copy of ROM at
CODE 0xCC00-0xD2C6. This is not redundancy — it's **required** because the overlay
is RAM, and the ROM code at those addresses must be explicitly copied into XDATA
for the firmware to function. Custom firmware must always include these ROM-duplicate
bytes (use `--pad-to-ref` in build_eeprom.py).

**Implication for custom firmware:** The full 1735 bytes are the working code space.
Our custom code occupies the first ~619 bytes (+0x000 to +0x26A). The remaining
~1116 bytes (+0x26B to +0x6C6) must be filled with stock/ROM data. There is no
"free" space from ROM fallthrough — every byte in the overlay must be explicitly
provided.

| Region | XDATA Address | Size | Description |
|--------|--------------|------|-------------|
| UserRAM | 0xC000-0xDFFF | 8KB | CODE/XDATA overlay region |
| UserConfig | 0xCBD0-0xCBFF | 0x30 | EEPROM header (bytes 0x00-0x2F) |
| EEPROM code | 0xCC00+ | variable | EEPROM code (bytes 0x30+) |
| Mailbox/work | 0xDE00-0xDE0F | 16 | Firmware working area |
| Config regs | 0xC6AA-0xC6C5 | varies | Video config state |
| Control regs | 0xC781-0xC783 | 3 | Hardware control |
| HW config | 0xF800-0xF8FF | varies | Hardware configuration |
| Video timing | 0xF900-0xF9FF | varies | Video timing registers |
| Status/ctrl | 0xF1FA-0xF1FF | 6 | Status and control |
| HW control | 0xFD00-0xFD40 | varies | Hardware control/data |

## Hook Architecture

### Normal Hook (0xCC00) — bit 0 of EEPROM[4]

Called from ROM main loop with R7 = command ID. The hook is an **opportunity to
run custom code** — the ROM handles its own command processing after the hook
returns. The hook does NOT need to call any ROM dispatch functions.

Stock EEPROM code (for reference — not required for custom firmware):
```
CC00: MOV  DPTR,#0xDE0B    ; Save command ID to working area
CC03: MOV  A,R7
CC04: MOVX @DPTR,A
CC05: LCALL 0xD03A         ; Call ROM command dispatcher (redundant — ROM does this itself)
CC08: MOV  DPTR,#0xDE0B    ; Read back command ID
CC0B: MOVX A,@DPTR
CC0C: MOV  R7,A
CC0D: LJMP  0xD104         ; Jump to ROM command handler (redundant)
```

**Custom firmware approach**: save/restore registers, call our dispatch function,
RET. The ROM resumes its own processing after the hook returns.

### ROM Command IDs (R7 values)

| Command (R7) | Context | Purpose |
|-------------|---------|---------|
| 0x00 | chip_init, before video pipeline | Video register setup |
| 0x01 | chip_init, after USB descriptor build | Video mode config |
| 0x02 | Main loop, every iteration | Main video processing |
| 0x08 | Video timing | Calls callback at +0x10 with data table address |
| 0x0C | Signal detection | Video timing update (checks IRAM[0x37]==0x3C) |

### Callback Entry (0xCC10) — called from ROM via command 0x08

```
CC10: MOV  DPTR,#0xDE05    ; Save R3:R2:R1 to working area
CC13: MOV  A,R3
CC14: MOVX @DPTR,A         ; [0xDE05] = R3
CC15: INC  DPTR
CC16: MOV  A,R2
CC17: MOVX @DPTR,A         ; [0xDE06] = R2
CC18: INC  DPTR
CC19: MOV  A,R1
CC1A: MOVX @DPTR,A         ; [0xDE07] = R1
CC1B: LCALL 0x6345          ; Call ROM hw init function
CC1E: RET
```

The ROM calls this from 0xD116 with R3:R2:R1 = 0xFF:0xCD:0x52 (pointing to data
at CODE 0xCD52 within the stock EEPROM code). ROM function 0x6345 uses this
address to access configuration data tables. **This callback must be preserved
byte-for-byte** — the ROM depends on it saving R3:R2:R1 and calling 0x6345.

### IRQ Hook (0xCC20) — bit 2 of EEPROM[4]

Called from interrupt context. Implements HDMI signal detection state machine.
**Must be written in assembly** — SDCC-generated code in interrupt context can
produce subtly different instruction choices that break USB enumeration (same
lesson as MS2107).

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
| 0xBC-0xBF | sfr_timers | Timer/counter SFR values |

**Signal Detection Flow:**
```
1. If IRAM[0x33] bit 2 set:
   - Clear bit 2
   - Call ROM 0xD2C1 (→ 0x6069, video processing)
   - Call register programming function (iterates data table, writes XDATA regs)

2. If IRAM[0x32] bit 3 NOT set: return (no video active)

3. Guard checks:
   - If IRAM[0x36] >= 6: return (state counter out of range)
   - If IRAM[0x37] != 0x3C: return (state value wrong)

4. Clear IRAM[0x32] bit 3

5. Signal detection state machine (IRAM[0x38]):
   - If IRAM[0x30] bit 1 is clear AND IRAM[0x38]==1:
     → [0xDE0C] = 0x01 (signal detected)
   - If IRAM[0x38]==0 AND [0xDE0C]==1 AND IRAM[0x30] bit 1 is set:
     → IRAM[0x38] = 2, [0xDE0C] = 0x02 (signal active)
   - If IRAM[0x38]==2 AND [0xDE0C]==2 AND IRAM[0x30] bit 1 is clear:
     → [0xDE0C] = 0, IRAM[0x38] = 3 (signal lost)

6. Hardware configuration:
   - MOV 0x93,#0x03        ; SFR 0x93 = 3 (Macrosilicon-specific)
   - SETB P0.0             ; Set P0.0 high

7. Video init processing:
   - If IRAM[0x30] bit 1 set: clear bit 1, then:
     - Check IRAM[0x30] bit 6:
       - If clear and [0xF1FC]!=0: skip
       - Clear bit 6, set [F000] |= 0x02, [F1FF]=0, [F1FC]=1
       - Call ROM 0xD2BD (→ 0x48E6, hardware init)
       - IRAM[0x38] = 1
     - Copy SFR timer values: 0xBC→0x1B, 0xBD→0x1C, 0xBE→0x1D, 0xBF→0x1E
     - Toggle IRAM[0x30] bit 0

8. State machine completion:
   - If IRAM[0x38]==1 and [F1FB]==3: reset IRAM[0x38]=0, set bit 1
   - If IRAM[0x38]==3: set bit 1
   (both paths fall through to F1FA check)

9. If [F1FA]!=0: set [F1FA]=1, set IRAM[0x30] bit 6

10. Write state to SFR 0xAE (debug/status output):
    0xAE = 0x0C, 0x30, 0x1B, 0x1C, 0x1D, 0x1E, 0xBC, 0xBD, 0xBE, 0xBF, 0x9E, 0x9F

11. If IRAM[0x38]==2 and [0xDE0C]==2:
    - Write 0xFF then 0xD8 to SFR 0xAE → return

12. If IRAM[0x38]==3:
    - Reset IRAM[0x38]=0
    - Write 0xFF then 0xD9 to SFR 0xAE → return
```

### Register Programming Function

Called from the IRQ hook after timer tick processing. Writes a 25-byte data table
to multiple groups of XDATA registers.

**Algorithm:**
- ROM 0xD212 is a 16-bit multiply: `DPTR = DPTR * A`
- Phase 1: 5 outer iterations (0..4), 25 inner each
  - `dest = outer * 0x2E + counter + 0xC0BF`
  - `data = reg_table[counter]`
- Phase 2: 6 outer iterations (5..10), 4 inner each
  - Same formula, same table (first 4 bytes)
- Total: 149 register writes

**25-byte register configuration table:**
```
0A 8B 02 00 05 0A 8B 02 00 15 16 05 00 80 1A 06
00 20 A1 07 00 40 42 0F 00
```

**Write address ranges (stride 0x2E = 46):**
```
Phase 1: 0xC0BF, 0xC0ED, 0xC11B, 0xC149, 0xC177  (25 bytes each)
Phase 2: 0xC1A5, 0xC1D3, 0xC201, 0xC22F, 0xC25D, 0xC28B  (4 bytes each)
```

## ROM Function Map

| Address | Name | Purpose |
|---------|------|---------|
| 0x4149 | reset_entry | Boot entry (LJMP from 0x0000) |
| 0x48E6 | hw_init_core | Core hardware init (called via 0xD2BD thunk) |
| 0x4648 | i2c_write_byte | I2C write (R7=byte, carry=ACK) |
| 0x5F19 | eeprom_reload | Detect + load EEPROM code |
| 0x6069 | video_process | Video processing (called via 0xD2C1 thunk) |
| 0x6345 | hw_init_with_table | Uses R3:R2:R1 as data table address |
| 0x6A8C | i2c_start | I2C start condition |
| 0x6ABA | i2c_stop | I2C stop condition |
| 0xD03A | cmd_dispatch_table | Jump table command dispatcher (A=index) |
| 0xD104 | cmd_handler | Command handler (R7=cmd, dispatches 0x08/0x0C) |
| 0xD212 | mul16 | 16-bit multiply: DPTR = DPTR * A |
| 0xD223 | jump_table_engine | Jump table engine (A=index, reads table after LCALL) |
| 0xD27D | math_func | Arithmetic/calculation |
| 0xD2BD | hw_init_thunk | LCALL 0x48E6; RET |
| 0xD2C1 | video_process_thunk | LCALL 0x6069; RET |

Note: Addresses 0xD03A-0xD2C1 are in the CODE/XDATA overlay region but contain
**identical bytes in both ROM and stock EEPROM**. They are genuine ROM functions,
not EEPROM replacements.

## Key Differences from MS2107/MS9123

1. **Hook addresses**: Normal at 0xCC00, IRQ at 0xCC20 (vs 0xC800/0xC810 for MS2107)
2. **Hook config byte**: EEPROM[4] with different bit assignments (bit 0 = normal, bit 2 = IRQ)
3. **UserConfig location**: 0xCBD0 (vs 0xC7D0 for MS2107)
4. **Mailbox area**: 0xDE00-0xDE0F (vs 0xD200-0xD21F for MS2107)
5. **ROM is completely different**: Near-zero code match with MS2107/MS9123
6. **HDMI input**: Signal detection is for HDMI, not CVBS — different state machine
7. **Callback entry at 0xCC10**: Extra entry point called from ROM with data table address
8. **SFR 0xAE**: Debug/status output register (not present in MS2107)
9. **Checksum formula**: No-skip (same as MS9123, different from MS2107)
10. **CODE/XDATA overlay**: XDATA 0xC000-0xDFFF overlays CODE space with ROM read-through

## Lessons Learned

### First flash failure — code_length matters (2026-03-29)

A 619-byte firmware with byte-identical content to stock failed to enumerate.
Root cause: **the CODE/XDATA overlay is RAM, not ROM read-through.** Addresses
past the loaded code contain uninitialized RAM (zeros/garbage), not ROM.

With `code_length=619`, the ROM only copies 619 bytes to XDATA 0xCC00-0xCE6A.
The dispatch tables (0xD03A), command handler (0xD104), mul16 (0xD212), and
thunks (0xD2BD, 0xD2C1) at higher addresses were uninitialized garbage.

**Initial fix:** Use `--pad-to-ref` to set `code_length=1735` (matching stock),
filling bytes +0x26B through +0x6C6 with stock/ROM data. The padded image boots.

### Self-contained firmware — no dump dependency (2026-03-29)

Rather than padding with stock data, we eliminated all outbound calls to the
ROM-duplicate overlay region and reimplemented the required functions:

- **IRQ handler**: Replaced thunk calls with direct ROM calls:
  - `LCALL 0xD2C1` → `LCALL 0x6069` (video_process)
  - `LCALL 0xD2BD` → `LCALL 0x48E6` (hw_init)
  - `LCALL 0xCF5E` → `LCALL _irq_register_program` (our reimplementation)
- **Normal hook**: Custom mailbox dispatch + RET (ROM handles its own dispatch)
- **mul16** (+0x612): Reimplemented (21 bytes, uses MUL AB)
- **jump_table_engine** (+0x623): Reimplemented (standard 8051 pattern)
- **math_func** (+0x67D): Wrapper that saves args to XDATA 0xDE00, calls ROM 0x52DD
- **Register programming**: Reimplemented with inline mul16 arithmetic
- **video_config** (+0x26B): Stock bytes embedded as .db (contains LCALL 0xD27D)

ROM-to-overlay dependencies that must be at fixed offsets:
- +0x010 (0xCC10): callback — preserved stock-identical
- +0x152 (0xCD52): EDID data — 256 bytes via MOVC
- +0x252 (0xCE52): reg_table — 25 bytes via MOVC
- +0x26B (0xCE6B): video_config — 243 bytes, LCALL from ROM
- +0x612 (0xD212): mul16 — 54 ROM call sites
- +0x623 (0xD223): jump_table_engine — called from i2c_stop
- +0x67D (0xD27D): math_func — called from video_config

Result: 1664-byte firmware, pure assembly, boots and enumerates with working
mailbox (signal status, GPIO read). No stock EEPROM dump needed at build time.

**Note:** math_func uses XDATA 0xDE00-0xDE04 as scratch space (same as stock ROM).
This overlaps the mailbox command register. Not currently an issue because the
normal hook reads 0xDE00 into R7 early and doesn't re-read. If mailbox becomes
unreliable, move the mailbox base to 0xDE10.

### EEPROM recovery

The Bus Pirate 5 must use **2.5V** (not 3.3V) when writing the EEPROM in-circuit.
At 3.3V, the MS2109 chip back-powers through board traces and its I2C controller
interferes with writes (ACKs but doesn't commit). At 2.5V the chip stays below
its operating threshold (3.2mA draw vs ~20mA at 3.3V). WP pin must be grounded
via a Bus Pirate IO pin.
