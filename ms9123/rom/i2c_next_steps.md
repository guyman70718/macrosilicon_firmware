# MS9123 I2C Master — Investigation Plan

## Context

The EEPROM is on Bus B (P3.3/P3.4). The ROM's E5 HID command reads it
successfully via Bus B ROM functions. Calling the same functions from our
firmware returns 0x00. All ROM I2C helpers are fully disassembled from the
32K CODE dump. The root cause is unknown.

## Priority 1: Logic Analyzer on Bus B

Capture P3.3 (SDA) and P3.4 (SCL) with the Bus Pirate 5 during:

- (a) An E5 HID EEPROM read (known working)
- (b) A firmware I2C read attempt (known failing)

**Expected outcomes:**
- No transitions in (b) → bus mux not enabled, pins not reaching EEPROM
- Transitions but no ACK in (b) → protocol/timing issue
- Identical waveforms → problem is in how we read the result, not the bus

This single test narrows the problem to either electrical/mux or software.

## Priority 2: Hardware I2C Controller Registers (F022-F025)

The ROM boot init (via `0x69BA → 0x68B8`) writes:
```
F023 = 0xD6
F024 = 0x01
F022 = 0x00, then F022 = 0x01
F025 = 0x00
```

These may control a hardware bus mux. Read them during:
- Normal firmware operation (when I2C fails)
- Immediately after an E5 read (if possible)

If F022 differs between contexts, toggling it before our I2C may fix things.

## Priority 3: CCAP0L Gate-Open Sequence

The ROM's USB handler does `CCAP0L=1` then polls for a hardware ready
bit (bit 4 of some register) before processing. Our code never does this
from the main loop. The periodic handler already runs with CCAP0L=1 (set
by the USB handler), but the E5 handler may run at a different USB
controller dispatch phase.

Try from `process_mailbox` (main loop):
```c
CCAP0L_REG = 1;
// possibly wait for ready bit
SFR_93 = 0;
EA = 0;
// I2C transaction
EA = 1;
CCAP0L_REG = 0;
```

Note: previous SFR_95 toggle crashes happened without the two NOPs that
the ROM's `safe_reconfig` uses. The exact `EA=0, CCAP0L=1, NOP, NOP`
sequence may be timing-critical.

## Priority 4: SFR_93 Mode Values

SFR_93 is not just a gate — the ROM sets it to values 0 through 4 for
different operational modes. Our code always clears it to 0. The E5
handler may run with a different SFR_93 value. Dump SFR_93 from different
contexts and try non-zero values before I2C.

## Priority 5: Call 0x535C with Full Setup

The E5 handler sets `bit 0x21.6` before calling the read dispatcher
(0x5E41), which routes to 0x535C when the bit is set. We tested 0x55E5
(the other path) but never tested 0x535C with the bit set. Try:

```
SETB 0x0E              ; bit 0x21.6
; Set up XDATA scratch:
XDATA[0xC5DF] = 0xA0   ; device address
XDATA[0xC5E0] = 0x00   ; register address high byte
XDATA[0xC5E1] = 0x00   ; register address low byte
LCALL 0x535C
; Result in R7 and XDATA[0xC5E2]
```

## Priority 6: SFR Dump from Multiple Contexts

Read SFRs 0x93, 0x95, 0x96, 0x97, 0x9B, 0x9C, 0x9D from:
- Main loop (process_mailbox)
- Periodic handler (USB IRQ context)
- Compare with values the E5 handler context would have

The USB handler copies SFR_96/97/9C to IRAM before dispatching. These
may configure bus state.

## Notes

- PnP disable/enable does NOT reload EEPROM code — must physical replug
- USB IRQ hook is at CODE 0xC903, needs LJMP trampoline at crt0 +0xD3
- SFR_95 bit 6 toggle crashes even with CCAP0L=1 and EA=0
- Pure GPIO bit-bang (P3.3/P3.4 or P3.6/P3.7) doesn't reach EEPROM
- ROM helpers do `CLR P2.x` when driving LOW — purpose unclear
- Bus A delay value at XDATA[0xC61C] = 0x0F
- Bus B delay value at XDATA[0xC61E] = 0x02
