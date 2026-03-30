# MS9123 I2C Implementation Analysis

Reverse-engineered from ROM disassembly (disasm.asm) and Ghidra decompilation
(decompiled.c). Cross-referenced against ms-tools MS2109 I2C implementation.

## Two Independent I2C Buses

The MS9123 ROM implements **two** software bit-banged I2C buses with parallel
function sets. Bus A is the EEPROM bus (used during boot). Bus B is used for
runtime peripheral communication (video decoder/encoder chips on the board).

### Bus A (EEPROM bus)

| Function     | Address  | Purpose                              |
|--------------|----------|--------------------------------------|
| i2c_start    | `0x6AB8` | Generate START condition             |
| i2c_stop     | `0x6919` | Generate STOP condition              |
| i2c_write    | `0x46BC` | Send byte, return ACK in carry       |
| i2c_read     | `0x4B9B` | Receive byte, ACK/NAK via bit 0x02  |
| delay        | `0x613B` | NOP-sled delay, R7:R6 = threshold   |

Pin assignments:
- **SDA output**: P3.7 / RD (bit address `0xB7`)
- **SDA input**: P2.7 (bit address `0xA7`)
- **SCL**: controlled by undisassembled helpers (see below)

### Bus B (peripheral bus)

| Function     | Address  | Purpose                              |
|--------------|----------|--------------------------------------|
| i2c_start    | `0x6ACC` | Generate START condition             |
| i2c_stop     | `0x69A3` | Generate STOP condition              |
| i2c_write    | `0x472C` | Send byte, return ACK in carry       |
| i2c_read     | `0x4BFC` | Receive byte, ACK/NAK via bit 0x06  |
| scl_low      | `0x64E2` | `CLR P3.4` (bit `0xB4`)             |
| load_delay   | `0x64E4` | R7=XDATA[0xC61E], R6=0              |

Pin assignments:
- **SDA output**: P3.3 / INT1 (bit address `0xB3`)
- **SDA input**: P2.3 (bit address `0xA3`)
- **SCL output**: P3.4 / T0 (bit address `0xB4`)


## Pin Polarity Model (Inverted Open-Drain)

The MS9123 uses an **active-high pull-down** model, inverted from standard
8051 conventions:

- `CLR P3.x` = **release** pin (goes HIGH via external pull-up)
- `SETB P3.x` = **drive** pin LOW (activate pull-down)

Evidence: In i2c_write (`0x46BC`), when the data bit is 1 (MSB set), the
code does `CLR P3.7` (SDA high). When the data bit is 0, it calls `0x7370`
(which presumably does `SETB P3.7` to pull SDA low). In i2c_read (`0x4B9B`),
`P2.7 = 1` means SDA is high (bit value 1), and `P2.7 = 0` means SDA is low
(bit value 0) -- the read side is non-inverted.

This means P3.x controls a pull-down driver (active when bit=1), and P2.x
reads the actual line state directly.

Alternatively, the functions in undisassembled ROM space (0x7370, 0x736B, etc.)
may manipulate a GPIO mux register rather than the port bits directly. The
exact mechanism is in ROM addresses 0x7022-0x73FF which Ghidra did not
disassemble (the disassembly stops at 0x701F). See "Undisassembled Helpers"
below.


## Undisassembled Helper Functions

These functions are in ROM space beyond Ghidra's analysis boundary (0x701F).
They are called extensively by the I2C routines but their exact instructions
are unknown without raw binary analysis.

### Bus A helpers (EEPROM bus)

| Address  | Role (inferred from calling context)                    |
|----------|---------------------------------------------------------|
| `0x71D7` | SCL-related: called where SCL HIGH is expected          |
| `0x71D9` | Load delay value for Bus A timing (like 0x64E4 for B)  |
| `0x7370` | SDA LOW (pull-down active) -- opposite of CLR P3.7      |
| `0x736B` | SCL LOW -- opposite of 0x71D7                           |

### Bus B helpers

| Address  | Role (inferred from calling context)                    |
|----------|---------------------------------------------------------|
| `0x7384` | SDA HIGH/release (opposite of CLR P3.3)                 |
| `0x737F` | SCL HIGH/release (opposite of CLR P3.4)                 |

**To determine exact instructions**: Run `xxd -s 0x71d0 -l 64 MS9123_CODE.bin`
and `xxd -s 0x7360 -l 64 MS9123_CODE.bin` to see the raw bytes, then
manually disassemble. Each helper is likely 2-4 bytes (SETB + RET, or
MOV DPTR + MOVX + RET).


## I2C Protocol Details

### i2c_start (0x6AB8) -- Bus A

```
CLR P3.7           ; Release SDA (high) -- ensure idle state
LCALL 0x71D7       ; SCL HIGH (release)
LCALL 0x613B       ; delay
LCALL 0x7370       ; SDA LOW (pull down) -- START condition
LCALL 0x71D9       ; load delay value
LCALL 0x613B       ; delay
LJMP  0x736B       ; SCL LOW -- ready for first data bit
```

Standard I2C START: SDA falls while SCL is high.

### i2c_stop (0x6919) -- Bus A

```
LCALL 0x7370       ; SDA LOW (pull down) -- ensure SDA is low
LCALL 0x71D9       ; load delay
LCALL 0x613B       ; delay
LCALL 0x71D7       ; SCL HIGH (release)
LCALL 0x613B       ; delay
CLR   P3.7         ; SDA HIGH (release) -- STOP condition
LCALL 0x71D9       ; load delay
LJMP  0x613B       ; delay + return
```

Standard I2C STOP: SDA rises while SCL is high.

### i2c_write (0x46BC) -- Bus A

Input: R7 = byte to send (ROM convention)
Output: Carry flag = 1 if ACK received, 0 if NAK

```c
// Pseudocode reconstruction:
XDATA[0xC598] = byte;          // store byte to shift out
bit_0x02 = 0;                  // clear ACK flag
XDATA[0xC599] = 0;             // bit counter

for (i = 0; i < 8; i++) {
    if (byte & 0x80)            // MSB first
        CLR P3.7;               // bit=1: SDA HIGH (release)
    else
        CALL 0x7370;            // bit=0: SDA LOW (pull down)

    // Clock pulse: SCL high, delay, SCL low, delay
    CALL 0x71D9; CALL delay;    // load timing
    CALL 0x71D7; CALL delay;    // SCL HIGH
    CALL 0x736B;                // SCL LOW
    CALL 0x71D9; CALL delay;    // load timing

    byte <<= 1;
}

// ACK clock cycle (9th clock):
CLR P3.7;                       // release SDA for slave ACK
CALL 0x71D9; CALL delay;
CALL 0x71D7; CALL delay;       // SCL HIGH -- slave drives ACK

// Wait for ACK with timeout:
timeout = 0x10;
while (P2.7 != 0 && count < timeout) count++;  // poll SDA

if (P2.7 == 0)                 // SDA low = ACK
    bit_0x02 = 1;              // set ACK flag

CALL 0x736B;                   // SCL LOW
CALL 0x71D9; CALL delay;

CY = bit_0x02;                 // return ACK in carry
RET;
```

**ACK convention**: Carry=1 means ACK received. Carry=0 means NAK.
This matches the ms-tools convention where `resp.C` indicates ACK.

### i2c_read (0x4B9B) -- Bus A

Input: bit 0x02 (bit address 0x12) controls ACK/NAK:
  - bit 0x02 = 0: send ACK (more bytes to read)
  - bit 0x02 = 1: send NAK (last byte)

Output: R7 = received byte

```c
// Pseudocode reconstruction:
XDATA[0xC599] = 0;             // received byte accumulator
CLR P3.7;                      // release SDA (let slave drive)
XDATA[0xC598] = 0;             // bit counter

for (i = 0; i < 8; i++) {
    XDATA[0xC599] <<= 1;       // shift left
    CALL 0x71D7; CALL delay;   // SCL HIGH
    bit = P2.7;                 // read SDA from P2.7
    XDATA[0xC599] |= (bit & 1); // OR in LSB
    CALL 0x736B;                // SCL LOW
    CALL 0x71D9; CALL delay;
}

// ACK/NAK clock cycle:
if (bit_0x02 == 1)             // last byte requested
    CLR P3.7;                   // SDA HIGH (NAK = release)
else
    CALL 0x7370;                // SDA LOW (ACK = pull down)

CALL 0x71D9; CALL delay;       // clock the ACK bit
CALL 0x71D7; CALL delay;       // SCL HIGH
CALL 0x736B;                   // SCL LOW
CLR P3.7;                      // release SDA
CALL 0x71D9; CALL delay;

R7 = XDATA[0xC599];            // return byte in R7
RET;
```

**Key difference from ms-tools**: ms-tools passes ACK/NAK in R7 (R7=0 for
ACK, R7=1 for NAK). The MS9123 ROM uses bit variable 0x02 instead. A wrapper
is needed if calling from C, or the bit can be set directly before calling.


## Comparison with MS2107 and MS2109

### Address mapping

| Function   | MS2107  | MS2109  | MS9123 (Bus A) | MS9123 (Bus B) |
|------------|---------|---------|----------------|----------------|
| i2c_start  | 0x68BD  | 0x6A8C  | **0x6AB8**     | 0x6ACC         |
| i2c_stop   | 0x6B5B  | 0x6ABA  | **0x6919**     | 0x69A3         |
| i2c_write  | 0x5323  | 0x4648  | **0x46BC**     | 0x472C         |
| i2c_read   | custom  | custom  | **0x4B9B**     | 0x4BFC         |

### Key differences from MS2107

1. **Pin assignments**: MS2107 uses P2.3/P3.3 (shared with INT0/INT1).
   MS9123 Bus A uses P3.7/P2.7. Bus B uses P3.3/P2.3.
2. **ACK flag**: MS2107 uses bit 0x23.6 for ACK. MS9123 uses bit 0x02
   (byte 0x20, bit 2) for Bus A, bit 0x06 (byte 0x20, bit 6) for Bus B.
3. **Read ACK input**: MS2107 passes ACK/NAK in R7. MS9123 uses bit variable
   0x02 (Bus A) or 0x05 (Bus B).
4. **Interrupt concern**: MS2107 required disabling EX0/EX1 during I2C
   because P3.2/P3.3 overlapped with INT0/INT1 pins. MS9123 Bus A uses
   P3.7 (RD strobe), which is NOT an interrupt pin -- **no interrupt
   disable needed** for Bus A.

### ms-tools custom read blob (MS2109)

ms-tools uploads a 5-byte shim for I2C read on the MS2109:
```
MOV 0x21.0, C      ; Store carry flag to bit 0x21.0
LJMP 0x4CF3         ; Jump to ROM read routine
```

For the MS9123, the ROM read function (0x4B9B) is directly callable. The
only issue is that the ACK/NAK is controlled by bit 0x02 instead of R7.
From SDCC C code, this can be set directly:
```c
__bit __at(0x12) i2c_ack_nak;  // bit 0x02 = byte 0x20 bit 2
i2c_ack_nak = last_byte;       // 1=NAK (last), 0=ACK (more)
```

Note: bit address 0x02 is IRAM byte 0x20, bit 2 (bit-addressable range).
SDCC `__bit __at()` uses the bit address directly.


## Calling Convention for EEPROM Firmware

The ROM I2C functions use ROM calling convention (R7 for first arg,
return in R7/carry). Our EEPROM code is compiled with SDCC (DPL for args).
Assembly wrappers in crt0 are needed.

### Required crt0 additions

```asm
; Bus A I2C wrappers (EEPROM bus)

; i2c_start: no parameters, no return value
_rom_i2c_start::
    .globl _rom_i2c_start
    lcall   0x6AB8
    ret

; i2c_stop: no parameters, no return value
_rom_i2c_stop::
    .globl _rom_i2c_stop
    lcall   0x6919
    ret

; i2c_write: DPL = byte to send, returns DPL = 1 (ACK) or 0 (NAK)
_rom_i2c_write::
    .globl _rom_i2c_write
    mov     r7, dpl         ; SDCC DPL -> Keil R7
    lcall   0x46BC
    clr     a
    rlc     a               ; carry -> A bit 0
    mov     dpl, a          ; return in DPL (1=ACK, 0=NAK)
    ret

; i2c_read: DPL = 0 for ACK (more bytes), 1 for NAK (last byte)
;           returns DPL = received byte
_rom_i2c_read::
    .globl _rom_i2c_read
    mov     a, dpl
    mov     c, acc.0        ; bit 0 of param
    mov     0x02, c         ; store to bit 0x02 (ACK/NAK control)
    lcall   0x4B9B
    mov     dpl, r7         ; return byte in DPL
    ret
```

### C declarations (rom_stubs.h additions)

```c
/* I2C Bus A (EEPROM bus) primitives */
extern void rom_i2c_start(void);
extern void rom_i2c_stop(void);
extern uint8_t rom_i2c_write(uint8_t byte);  /* returns 1=ACK, 0=NAK */
extern uint8_t rom_i2c_read(uint8_t nak);    /* nak=0: ACK, nak=1: NAK */
```

### Example: read a register from an I2C device at address 0x44

```c
uint8_t i2c_read_reg(uint8_t dev_addr, uint8_t reg) {
    uint8_t val;

    rom_i2c_start();
    if (!rom_i2c_write(dev_addr << 1))      // write address + W
        goto fail;
    if (!rom_i2c_write(reg))                 // register address
        goto fail;
    rom_i2c_start();                         // repeated start
    if (!rom_i2c_write((dev_addr << 1) | 1)) // write address + R
        goto fail;
    val = rom_i2c_read(1);                   // read byte, send NAK (last)
    rom_i2c_stop();
    return val;

fail:
    rom_i2c_stop();
    return 0xFF;
}
```


## GPIO/Pin Mux Configuration

The init_hook1 in crt0_ms9123.asm already configures the pins needed for
Bus A I2C:

```asm
anl  0xB0, #0x3F    ; P3 &= 0x3F: clear P3.6 and P3.7
                     ; (release/idle both pins -- P3.7 is SDA)
anl  0xB1, #0x3F    ; SFR_P3ALT &= 0x3F: disable alternate functions
                     ; on P3.6 and P3.7 (make them GPIO)
```

**No additional pin mux configuration is needed for I2C Bus A.** The pins
are already set up as GPIO by the existing init_hook1.

For Bus B, the SCL pin (P3.4) may need alternate function configuration
via SFR 0xB1, but Bus B is not needed for our EEPROM firmware.


## Interrupt Concerns

**Bus A (P3.7 SDA, unknown SCL)**: P3.7 is the RD (external memory read)
strobe on standard 8051. It is NOT an interrupt input pin. There are no
interrupt conflicts. **Disabling EX0/EX1 is NOT required** for Bus A I2C
operations.

However, the main service loop already disables EX0 during
`rom_usb_frame_manage()`. If I2C operations are performed from the main
loop context (not from ISR), they should be safe without additional
interrupt management.

If I2C operations are time-sensitive and the USB ISR could interfere with
bit-bang timing, wrapping I2C transactions with `EA = 0` / `EA = 1` would
be prudent:

```c
EA = 0;             // disable all interrupts
rom_i2c_start();
// ... I2C transaction ...
rom_i2c_stop();
EA = 1;             // re-enable interrupts
```


## XDATA Scratch Space Used by I2C

The ROM I2C functions use XDATA for temporary storage:

| Address    | Bus | Used by       | Purpose                    |
|------------|-----|---------------|----------------------------|
| 0xC598     | A   | write/read    | Byte shift register        |
| 0xC599     | A   | write/read    | Bit counter / received byte|
| 0xC585     | A   | eeprom_read   | Device address (high)      |
| 0xC586     | A   | eeprom_read   | Device address (low)       |
| 0xC587     | A   | eeprom_read   | Read result byte           |
| 0xC5D6-DC  | A   | eeprom_read   | Block read parameters      |
| 0xC5E3     | B   | write/read    | Bit counter                |
| 0xC5E4     | B   | write/read    | Byte shift register        |
| 0xC5E5     | B   | write/read    | Byte to send               |
| 0xC5E6     | B   | write         | Bit counter                |
| 0xC61E     | B   | load_delay    | I2C clock timing value     |

These addresses are ROM-internal working memory. Calling the ROM I2C
primitives directly (start/stop/write/read) is safe -- they manage their
own scratch space. Do not store user data at these addresses.


## Higher-Level ROM I2C Functions

These higher-level functions compose the primitives above:

| Address  | Bus | Purpose                                         |
|----------|-----|-------------------------------------------------|
| `0x53A9` | A   | EEPROM block read (R2:R1=dest, R5=count, R7:R6=offset) |
| `0x5E41` | A   | Single/multi-byte EEPROM read dispatcher         |
| `0x535C` | B   | Multi-byte peripheral read (with repeated start) |
| `0x55E5` | B   | Multi-byte peripheral write+read                 |

For custom I2C master operations (talking to non-EEPROM devices), use the
low-level primitives (start/stop/write/read) directly rather than the
higher-level EEPROM functions, which assume specific addressing schemes.


## Summary: What to Add for I2C Master Support

1. **crt0_ms9123.asm**: Add 4 wrapper functions (start, stop, write, read)
   as shown in the "Required crt0 additions" section above.

2. **rom_stubs.h**: Add 4 function declarations for the I2C primitives.

3. **No pin mux changes needed** -- init_hook1 already configures P3.7
   as GPIO for SDA.

4. **No interrupt disable needed** -- P3.7 is not an interrupt pin.
   (Optional: wrap with EA=0/EA=1 for timing safety.)

5. **Do not need a custom read blob** like ms-tools does for MS2109.
   The ROM read function (0x4B9B) is directly callable via the wrapper.

6. **Bit variable conflict check**: bit 0x02 (byte 0x20, bit 2) is used
   by the ROM I2C for ACK/NAK control. The EEPROM firmware uses bits
   0x08-0x0D (byte 0x21). No conflict.


## Open Questions

1. **SCL pin identity for Bus A**: The SCL control is in undisassembled
   ROM (0x71D7 = SCL HIGH, 0x736B = SCL LOW). Need to read raw bytes at
   these addresses to confirm which port bit is SCL. It could be P2.7
   doing double duty (unlikely), or a dedicated SCL pin elsewhere (P3.6
   is a candidate since init_hook1 configures both P3.6 and P3.7).

2. **Bus A delay timing value**: Bus B loads timing from XDATA[0xC61E].
   Bus A's equivalent is in 0x71D9 (undisassembled). The ROM likely stores
   a similar timing value for Bus A at a nearby XDATA address. The default
   I2C speed is probably ~100kHz based on the NOP-sled delay function.

3. **Hardware I2C controller**: The MS9123 may have a hardware I2C
   controller (registers at 0xF022/0xF025 written by the function at
   0x68BD). The bit-bang implementation in the ROM might be a fallback
   or used for specific buses. Investigation of 0xF022/0xF025 could
   reveal a faster hardware path.
