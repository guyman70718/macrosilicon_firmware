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


## Current Status: WORKING

I2C master from EEPROM firmware code works correctly. The firmware can
read and write the 24C16 EEPROM (0x50-0x57) via Bus B ROM functions.

### Root causes (resolved)

Two issues prevented I2C from working:

1. **P3ALT clearing disconnected pins from GPIO.** The ROM's bit-bang
   I2C works with P3ALT bits 3,4 SET (their default state 0x3C). Our
   code was clearing these bits thinking they needed to be in "GPIO mode",
   but clearing them actually disconnected the pins — only a START
   condition was generated, with no subsequent clock pulses. The E5 HID
   handler never touches P3ALT and works fine.

2. **Bus B delay value 0x02 was too fast for EEPROM reads.** The ROM
   boot init sets XDATA[0xC61E] = 0x02 for Bus B. This is sufficient
   for the E5 handler (which has additional call-chain overhead slowing
   it down) but too fast for direct calls to the low-level I2C functions.
   At delay=0x02, data reads returned 0xFD (mostly 1-bits — SDA sampled
   before EEPROM drives it). Setting delay to 0x0F (matching Bus A)
   gives reliable reads.

### Key lessons

- P3ALT on the MS9123 does NOT work like a simple GPIO/alt-function
  mux. The ROM's bit-bang I2C uses SETB/CLR P3.x with P3ALT bits set,
  and the pins toggle correctly. Clearing P3ALT breaks this.
- Bus Pirate 5 clips on Bus B pins prevent EEPROM boot load — the
  device must boot without the sniffer attached, then the clip can be
  added for runtime captures.
- The I2C sniffer confirmed E5 produces full transactions while our
  (broken) code produced only a START condition — this narrowed the
  root cause to pin control rather than protocol or addressing issues.

### Working configuration

- Bus B ROM functions called directly (0x6ACC/0x69A3/0x472C/0x4BFC)
- P3ALT left at default (0x3C) — do NOT clear bits 3,4
- EA=0 during transactions (block periodic handler)
- XDATA[0xC61E] = 0x0F (Bus B delay, set at init)
- 7-bit device addresses, shifted left by firmware for wire format


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
| INT disable    | EX0=0, EX1=0 | EX0=0, EX1=0 | EA=0             |
| Addr convention| 7-bit        | 7-bit        | 7-bit            |
| I2C status     | Working      | Working      | Working          |
