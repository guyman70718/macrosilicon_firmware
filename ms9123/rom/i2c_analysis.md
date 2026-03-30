# MS9123 I2C Implementation Analysis

## Two Independent I2C Buses

The MS9123 ROM implements two software bit-banged I2C buses. Both use the
same inverted open-drain pin model with parallel P3 (output) / P2 (input)
pin pairs.

**Key finding**: The EEPROM is on **Bus B** (P3.3/P3.4), not Bus A. The
ROM's E5 HID command reads the EEPROM through Bus B functions. Bus A
(P3.7/P3.6) is used during the initial boot EEPROM load only.

### Bus A (boot-time EEPROM load)

| Function   | Address  | Purpose                                    |
|------------|----------|--------------------------------------------|
| i2c_start  | `0x6AB8` | Generate START condition                   |
| i2c_stop   | `0x6919` | Generate STOP condition                    |
| i2c_write  | `0x46BC` | Send byte, ACK via bit 0x02 → carry       |
| i2c_read   | `0x4B9B` | Receive byte, ACK/NAK via bit 0x02        |
| delay      | `0x613B` | Countdown delay, R7:R6 = threshold        |

| Pin        | Port bit | Direction | Bit addr |
|------------|----------|-----------|----------|
| SDA output | P3.7     | Out       | 0xB7     |
| SDA input  | P2.7     | In        | 0xA7     |
| SCL output | P3.6     | Out       | 0xB6     |
| SCL input  | P2.6     | In        | 0xA6     |

### Bus B (runtime EEPROM access, peripheral communication)

| Function   | Address  | Purpose                                    |
|------------|----------|--------------------------------------------|
| i2c_start  | `0x6ACC` | Generate START condition                   |
| i2c_stop   | `0x69A3` | Generate STOP condition                    |
| i2c_write  | `0x472C` | Send byte, ACK via bit 0x06 → carry       |
| i2c_read   | `0x4BFC` | Receive byte, ACK/NAK via bit 0x05        |
| scl_high   | `0x64E2` | CLR P3.4 (release SCL) + delay_load       |
| delay_load | `0x64E4` | R7=XDATA[0xC61E], R6=0                    |

| Pin        | Port bit | Direction | Bit addr | Alt function |
|------------|----------|-----------|----------|--------------|
| SDA output | P3.3     | Out       | 0xB3     | INT1         |
| SDA input  | P2.3     | In        | 0xA3     |              |
| SCL output | P3.4     | Out       | 0xB4     | T0           |
| SCL input  | P2.4     | In        | 0xA4     |              |


## Pin Polarity Model (Inverted Open-Drain)

Both buses use an inverted open-drain model:

- `CLR P3.x` = **release** pin (goes HIGH via pull-up)
- `SETB P3.x` = **drive** pin LOW

P2.x reads the actual line state directly (non-inverted).


## ROM Helper Functions (Disassembled from 32K ROM dump)

The helper functions at 0x7000+ were previously unknown. A complete lower
32K CODE dump (`MS9123_CODE_lower32k.bin`) was obtained and disassembled,
revealing the exact instructions.

### Bus A helpers

| Address  | Instructions                    | Purpose                |
|----------|---------------------------------|------------------------|
| `0x71D7` | `CLR P3.6` (falls through →)   | Release SCL (HIGH)     |
| `0x71D9` | `MOV DPTR,#C61C; MOVX; R7=A; R6=0; RET` | Load Bus A delay value |
| `0x736B` | `SETB P3.6; CLR P2.6; RET`     | Drive SCL LOW          |
| `0x7370` | `SETB P3.7; CLR P2.7; RET`     | Drive SDA LOW          |

### Bus B helpers

| Address  | Instructions                    | Purpose                |
|----------|---------------------------------|------------------------|
| `0x64E2` | `CLR P3.4` (falls through →)   | Release SCL (HIGH)     |
| `0x64E4` | `MOV DPTR,#C61E; MOVX; R7=A; R6=0; RET` | Load Bus B delay value |
| `0x737F` | `SETB P3.4; CLR P2.4; RET`     | Drive SCL LOW          |
| `0x7384` | `SETB P3.3; CLR P2.3; RET`     | Drive SDA LOW          |

### P2.x CLR pattern

Every "drive LOW" helper does **two** operations: `SETB P3.x` (drive output)
AND `CLR P2.x` (clear the corresponding input port bit). The "release HIGH"
helpers only do `CLR P3.x` — they do NOT `SETB P2.x`.

This asymmetric pattern may serve as pin mux control on the MS9123's custom
8051 core. The exact effect of CLR P2.x on the input path is not yet fully
understood, but it does not prevent ACK detection (the write function
successfully reads P2.x for ACK after CLR P2.x).


## EEPROM Access Path (E5 HID Command)

The ROM's E5 HID command reads the EEPROM via this call chain:

```
E5 handler (0x0D4F)
  → setup (0x32E7, 0x3333)
  → 0x6DD9: set bit 0x21.6, load params
    → 0x53A9: EEPROM block read loop
      → 0x5E41: read dispatcher (checks bit 0x21.6)
        → 0x535C or 0x55E5: Bus B I2C read
          → 0x6ACC (start), 0x472C (write), 0x4BFC (read), 0x69A3 (stop)
```

Both 0x535C and 0x55E5 use the same Bus B low-level primitives. The
dispatcher at 0x5E41 chooses between them based on bit 0x21.6, which is
set from IRAM[0x5C] by the E5 handler.


## USB IRQ Hook (0xC903)

The ROM calls CODE 0xC903 directly (not through the +0x30 periodic hook)
when EEPROM header byte [4] bit 5 is set. This is the USB IRQ handler hook.

The stock firmware's periodic handler body lives at 0xC903. Custom firmware
must place a trampoline (LJMP) at CODE offset +0xD3 (= 0xC903 with code
base 0xC830) to redirect to the custom handler. The +0x30 hook at 0xC860
is a separate entry point.

**Important**: PnP disable/enable does NOT reload the EEPROM code overlay.
A physical USB unplug/replug is required for code at 0xC903 to take effect.


## I2C Timing Values

| Address  | Bus | Value | Purpose               |
|----------|-----|-------|-----------------------|
| 0xC61C   | A   | 0x0F  | Bus A delay threshold |
| 0xC61E   | B   | 0x02  | Bus B delay threshold |


## Current Status: NOT WORKING

I2C master from EEPROM firmware code does not work. The ROM's E5 HID
command successfully reads the EEPROM via Bus B, but calling the same
Bus B functions from our firmware (either main loop or USB IRQ handler
context) always returns 0x00.

### What works

- ROM I2C write functions execute (no crash)
- I2C scan returns ACK for all addresses (false positives — see below)
- E5 HID EEPROM read works correctly
- Firmware runs stably, other features work

### What doesn't work

- I2C reads always return 0x00
- I2C scan shows false ACKs (0x3F bitmap for ALL address ranges including empty)
- Pure GPIO bit-bang (P3.6/P3.7 or P3.3/P3.4) doesn't reach the EEPROM
- Changing SFR_95 crashes the device (even with EA=0, CCAP0L=1)

### Root cause analysis

The false ACK problem is the key. The write function's ACK check reads
the SDA input pin (P2.x). If P2.x always reads 0, every address appears
to ACK, but no device actually received the data. During the read phase,
no device drives SDA, so all bits read as 0.

GPIO bit-bang tests confirmed that direct P3.6/P3.7 GPIO writes do NOT
reach the EEPROM — a pure bit-bang scan finds no devices. The ROM I2C
helpers must use some mechanism beyond simple GPIO toggling (possibly
an internal bus mux controlled by the CLR P2.x pattern).

### Approaches tried

1. Bus A ROM functions — reads 0x00
2. Bus B ROM functions from main loop — reads 0x00
3. Bus B ROM functions from USB IRQ handler — reads 0x00
4. Pure GPIO bit-bang (P3.6/P3.7 and P3.3/P3.4) — no device responds
5. P3ALT changes (clear/set bits 3,4) — no effect
6. EA=0 during I2C — no effect on reads (no crash either)
7. EX0=0/EX1=0 during I2C — no effect
8. SFR_95 bit 6 toggle (matches ROM safe_reconfig 0x67D1) — crashes
9. SFR_9B=0, SFR_9D=0 — no effect
10. P2.2 set/clear — no effect
11. SETB/CLR P2.7 before reads — no effect
12. Calling ROM higher-level function 0x55E5 directly — reads 0x00

### Next steps

- Trace the E5 HID handler more completely to find any hidden setup
- Investigate hardware I2C controller at XDATA 0xF022-0xF025
- Use logic analyzer on Bus B pins (P3.3/P3.4) during E5 vs firmware I2C
  to compare actual bus activity
- Check if the ROM's USB interrupt handler configures a bus mux register
  that the I2C helpers depend on
- Investigate SFR 0x93 (DPX/analog gate) more carefully — display_hw_init
  clears it, and the ROM's `dac_snapshot_and_check` also clears it


## Comparison with MS2107 and MS2109

| Feature        | MS2107       | MS2109       | MS9123           |
|----------------|--------------|--------------|------------------|
| I2C start      | 0x68BD       | 0x6A8C       | A: 0x6AB8, B: 0x6ACC |
| I2C stop       | 0x6B5B       | 0x6ABA       | A: 0x6919, B: 0x69A3 |
| I2C write      | 0x5323       | 0x4648       | A: 0x46BC, B: 0x472C |
| I2C read       | 0x5934       | 0x4CF3       | A: 0x4B9B, B: 0x4BFC |
| SDA/SCL pins   | P3.2/P3.3    | GPIO2/GPIO3  | A: P3.7/P3.6, B: P3.3/P3.4 |
| EEPROM bus     | same as I2C  | same as I2C  | Bus B (not Bus A) |
| ACK flag       | bit 0x23.6   | bit 0x21.0   | A: bit 0x02, B: bit 0x06 |
| Read NAK flag  | bit 0x1D     | bit 0x08     | A: bit 0x02, B: bit 0x05 |
| INT disable    | EX0=0, EX1=0 | EX0=0, EX1=0 | TBD              |
| I2C status     | Working      | Working      | Not working      |
