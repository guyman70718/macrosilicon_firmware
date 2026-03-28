# MS2107 ROM Initialization Sequence

Traced from the mask ROM decompilation. This is the complete boot sequence
from reset to main loop.

## Call Chain

```
reset_vector (0x0000)
  -> LJMP 0x5297 (Keil C startup: clear IRAM, SP=0x55, data init from table at CODE 0x1BEE)
  -> chip_init (0x5DA4)
       1. hw_pre_init (0x700D)
       2. eeprom_reload (0x6656)
            -> eeprom_load_and_verify (0x37CC)
       3. parse_eeprom_config (0x3FC1)
       4. init_phase_gate(0) (0x6F47)
       5. video_pipeline_init (0x3E84)
       6. set_audio_output_mode (0x6E8D)
       7. build_usb_descriptors (0x1E57)
       8. init_phase_gate(1) (0x6F47)
       9. Enable interrupts (IT1=1, EX1=1, EX0=1, EA=1)
      10. Main loop (infinite)
            -> main_loop_iteration (0x40E4) calls EEPROM hooks
```

## Step 1: hw_pre_init (0x700D)

```c
void hw_pre_init(void) {
    FUN_CODE_6bd7();   // Unknown — hardware register init?
    FUN_CODE_6fa7();   // Unknown — clock/PLL setup?
}
```

Runs before EEPROM is loaded. Likely initializes the 8051 core peripherals,
clock from 12MHz crystal, and the I2C bus for EEPROM access.

## Step 2: eeprom_reload (0x6656)

```c
char eeprom_reload(void) {
    C649 = 0;           // Clear attempt counter
    FUN_CODE_50e9();    // I2C bus init? EEPROM detect?
    FUN_CODE_688c();    // I2C bus reset?
    FUN_CODE_6625();    // Read EEPROM header (magic + first 4 bytes)?

    if (C6AE == 0) return 0;  // No valid EEPROM found

    // Try loading up to 2 times (different I2C page configs?)
    while (C649 < 2) {
        FUN_CODE_4e7e(C649);         // Select I2C EEPROM page/bank
        result = eeprom_load_and_verify();  // Load code + validate checksums
        if (C649 == 0) return result;       // Return after first attempt
        FUN_CODE_688c();                    // Reset I2C bus between attempts
        C649++;
    }
    return result;
}
```

The return value from `eeprom_load_and_verify` IS propagated back.
`chip_init` doesn't check it, but the load itself has important side effects
(EEPROM data in RAM, checksums validated).

### eeprom_load_and_verify (0x37CC)

Three-phase EEPROM load using I2C sequential reads:

**Phase 1: Load header + strings (accumulate header checksum)**
```
C64A:C64B = 0xC7D2  ->  Read 9 bytes (EEPROM[0x02-0x0A]) -> header checksum accum
C64A:C64B = 0xC7E0  ->  Read 32 bytes (EEPROM[0x10-0x2F]) -> header checksum accum
```
Result: C64E:C64F = accumulated header checksum

**Phase 2: Load code (no checksum accumulation)**
```
C64A:C64B = 0xC800  ->  Read code_length bytes (EEPROM[0x30 .. 0x30+code_length-1])
```
After this read, C64A:C64B points to 0xC800 + code_length.

**Phase 3: Validate header checksum**
```
Read 2 bytes from current I2C position -> C64C:C64D (stored header checksum)
Compare C64E:C64F (computed) with C64C:C64D (stored)
If mismatch: C7CF = 2, return with carry clear (FAILURE)
```

**Phase 4: Compute and validate code checksum**
```
Re-read code_length bytes, accumulating into C64E:C64F
Read 2 bytes from current position -> C64C:C64D (stored code checksum)
Compare. If mismatch: C7CF = 3, return (FAILURE)
If match: return (SUCCESS)
```

**CRITICAL: Checksum validation DOES matter.** The return value propagates
through `eeprom_reload` and a failure means the EEPROM load is considered
unsuccessful. While `chip_init` doesn't check the return value explicitly,
the load process itself may not complete all phases — leaving RAM in a
partially initialized state.

**CRITICAL: code_length determines the position of checksums in the EEPROM.**
The ROM reads checksums from EEPROM at offset 0x30 + code_length.
If code_length changes, the checksums must be at the new offset.

## Step 3: parse_eeprom_config (0x3FC1)

Reads EEPROM header bytes and GPIO pins to configure the chip.

```
EEPROM[0x09] (C7D9) -> Video input config:
    bits 1:0 -> IRAM[0x42] (video input source select)
    bits 7:2 -> IRAM[0x41] (video mode)

EEPROM[0x0A] (C7DA) -> Feature flags:
    bit 2    -> _0_0 (enables post-checksum data read at code_length+0x34)
    bits 7:4 -> IRAM[0x4C] (signal detect threshold)

EEPROM[0x0B] (C7DB) -> Video config 2:
    bit 7    -> IRAM[0x48] (S-Video vs CVBS input select)
    bits 6:0 -> IRAM[0x47] (video standard/timing config)

GPIO P2.6, P2.7 -> IRAM[0x43] (video input mode: 0=CVBS, 1=S-Video, 2=auto, 3=special)
GPIO P2.0       -> IRAM[0x44] (audio input: 0=internal ADC, 1=I2S)
GPIO P2.1       -> IRAM[0x45] (unknown config bit)
```

If `_0_0` is set (EEPROM[0x0A] bit 2), reads 4 bytes from EEPROM at
offset `code_length + 0x34` into C649-C64C as video processing parameters.
These override the defaults set above.

Sets defaults: IRAM[0x40]=8, [0x46]=0, [0x3B]=0, [0x4A]=5, [0x4B]=0,
[0x4D]=0x30, [0x4E]=0x30, [0x4F]=0x40

Copies video params to C67B-C684 region.

## Step 4: init_phase_gate(0) (0x6F47)

```c
void init_phase_gate(uint8_t phase) {
    if (C7D8 & 0x01) {      // EEPROM[0x08] bit 0 = normal hook enabled
        FUN_CODE_6f9e();     // Calls 0xC800 (the EEPROM normal hook!)
    }
}
```

**This calls the EEPROM firmware hook!** Before video pipeline init and
before USB descriptor setup. The hook is called with whatever R7 value
is current (likely 0 from the `CLR A; MOV R7,A` before the call).

**Our EEPROM firmware receives this call.** If it does anything wrong here
(corrupts registers, writes to wrong XDATA addresses), it could break
subsequent init steps.

FUN_CODE_6f9e is the actual hook dispatcher — it checks hook enable flags
and calls 0xC800 with the current R7 value.

## Step 5: video_pipeline_init (0x3E84)

Large function that configures the video capture pipeline based on IRAM[0x43]:

- If IRAM[0x43] == 3 (special mode): minimal config
- Otherwise: full video ADC setup, signal routing, timing config

Writes to F8xx video processing registers. Uses IRAM[0x43-0x4F] values
set by parse_eeprom_config. Calls FUN_CODE_6087 (video_reset) at the end.

## Step 6: set_audio_output_mode (0x6E8D)

```c
void set_audio_output_mode(void) {
    if (IRAM[0x44] == 0)    // Internal ADC (GPIO0 floating)
        F83C = 0x85;
    else                     // I2S input (GPIO0 grounded)
        F83C = 0x05;
}
```

## Step 7: build_usb_descriptors (0x1E57)

The critical USB setup function. Branches on IRAM[0x43] (video mode):

**IRAM[0x43] == 1 (S-Video):**
```
C00D=4, C00E=4, C00F=0x22
setup_usb_endpoint(0x11, 0x51, 0x15, 0xFF, 0xC0, 1, 0, 0x18)
setup_usb_endpoint(0x41, 0x51, 0x15, 0xFF, 0xC0, 1, 0, 0x18)
C010=0
```

**IRAM[0x43] == 0 or 2 (CVBS or auto):**
```
C00D=8, C00E=5, C00F=0x11
setup_usb_endpoint(0x11, 0x03, 0x15, 0xFF, 0xC0, 1, 0, 0x30)
setup_usb_endpoint(0x41, 0x33, 0x15, 0xFF, 0xC0, 1, 0, 0x1E)
C010=0
```

**IRAM[0x43] == 3 (special):**
```
C00D=4, C00E=2, C00F=0x12
setup_usb_endpoint(0x11, 0x69, 0x15, 0xFF, 0xC0, 1, 0, 0x18)
setup_usb_endpoint(0x41, 0x81, 0x15, 0xFF, 0xC0, 1, 0, 0x0C)
C010=1
```

Then:
```
C00C = EEPROM[0x0A] & 0x03         // Feature flags low 2 bits

VID/PID copy from EEPROM header:
    if (C7D4 != 0xFF || C7D5 != 0xFF):   // VID not 0xFFFF
        C53D = C7D5 (VID low)
        C53E = C7D4 (VID high)
    if (C7D6 != 0xFF || C7D7 != 0xFF):   // PID not 0xFFFF
        C53F = C7D7 (PID low)
        C540 = C7D6 (PID high)

String descriptor build:
    if (C7E0 == 0xFF):  // EEPROM string 1 is empty
        Copy ROM default from CODE 0x11E4 to XDATA 0xC4C3 (manufacturer?)
    else:
        Convert EEPROM ASCII at C7E0 to UTF-16LE at C4C3

    if (C7F0 == 0xFF):  // EEPROM string 2 is empty
        Copy ROM default from CODE 0x11F8 to XDATA 0xC4F3 (product?)
    else:
        Convert EEPROM ASCII at C7F0 to UTF-16LE at C4F3
```

## Step 8: init_phase_gate(1) (0x6F47)

Same as step 4 — calls the EEPROM normal hook again if bit 0 is set.
This time, USB descriptors are built. If the hook corrupts descriptor
state, USB enumeration will fail.

## Step 9: Enable Interrupts

```
IT1 = 1    // Edge-triggered external interrupt 1
EX1 = 1    // Enable external interrupt 1
EX0 = 1    // Enable external interrupt 0
EA = 1     // Global interrupt enable
```

## Step 10: Main Loop

Infinite loop calling periodic functions and the EEPROM hooks via
main_loop_iteration (0x40E4). The hooks are now called with meaningful
R7 command values.

## Key Findings for Custom Firmware

1. **The EEPROM hook at 0xC800 is called TWICE during init** (steps 4 and 8)
   before the main loop even starts. Any bugs in the hook handler that
   corrupt init state will break USB enumeration.

2. **Checksum validation is real.** The ROM validates both header and code
   checksums during EEPROM load. Mismatched checksums cause early return
   from the load function.

3. **code_length positions the checksums AND the post-checksum data.**
   The EEPROM layout is:
   ```
   [0x00-0x2F]                         Header (fixed)
   [0x30 .. 0x30+code_length-1]        Checksummed code
   [0x30+code_length .. +3]            Checksums (validated by ROM)
   [0x30+code_length+4 .. ]            Post-checksum data (found via code_length+0x34)
   ```

4. **IRAM[0x43] controls USB descriptor configuration.** Set by GPIO P2.6/P2.7,
   not by EEPROM. Different values produce completely different USB endpoint
   layouts.

5. **init_phase_gate checks EEPROM[0x08] bit 0** before calling the hook.
   Our hook enable byte is 0x03 (bits 0,1 set), so the hook IS called
   during init. With the original firmware, R7=0 at this point, which
   dispatches to cmd_setup_video_regs.

6. **The hook at 0xC800 is called with R7=0 during init** (step 4).
   The ROM's dispatch_to_eeprom_hook stores R7 to C66B then LCALLs 0xC800.
   R7 is set to 0 by chip_init (CLR A; MOV R7,A before the call).
   If our SDCC dispatcher corrupts IRAM state when handling R7=0,
   subsequent init steps (especially build_usb_descriptors which
   reads IRAM[0x43]) will fail.

7. **The hook is called AGAIN at step 8 with R7=1** (MOV R7,#0x01
   before the second call_normal_hook_if_enabled call). At this point
   USB descriptors are already built, so corruption here would be less
   critical but could still affect the main loop.

8. **Complete hook map** (confirmed from ROM byte-level trace):

   | Bit | Offset | XDATA  | ROM caller | Purpose |
   |-----|--------|--------|------------|---------|
   | 0   | +0x00  | 0xC800 | 0x6F47     | Normal command dispatch (R7=cmd) |
   | 1   | +0x10  | 0xC810 | 0x54A2     | Interrupt handler hook |
   | 2   | +0x20  | 0xC820 | 0x40F3     | USB endpoint processing |
   | 3   | +0x30  | 0xC830 | 0x5BE5     | Timer/external interrupt |
   | 4   | +0x40  | 0xC840 | 0x5FBF     | Unknown |
   | 5   | +0x50  | 0xC850 | 0x62CE     | Unknown |

   Stock flags 0x03 = bits 0,1 enabled. The normal hook receives R7
   command IDs: 0,1,2,3,5,7,8,9,10,12,13,14 from various ROM contexts.
   The interrupt hook at +0x10 is called from the USB/timer interrupt
   path at ROM 0x54A2.

9. **Hybrid testing confirmed**: Original code with changed code_length
   works. SDCC-compiled code with correct checksums fails. The problem
   is in SDCC's code generation, not the image format.
