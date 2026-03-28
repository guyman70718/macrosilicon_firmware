# MS9123 Boot Sequence and Main Loop (from ROM decompilation)

## Reset Handler (0x40EB)

```
1. Clear all IRAM (0x00-0xFF = 0)
2. Set SP = 0x5C
3. Process Keil C51 data initialization table at CODE:0x12AF
   - Initializes IRAM, XDATA, and bit variables from compressed ROM data
4. Call main_init (0x48DB)
```

This is a standard Keil C51 startup sequence. The init table at 0x12AF contains
encoded instructions for initializing global variables to their compiled defaults.

## Main Init (0x48DB)

`param_1` is loaded from EEPROM header — it's the hook config byte (EEPROM[0x04]).

```c
void main_init(uint8_t hook_config)   // 0x48DB
{
    hw_early_init();                   // 0x69BA — early hardware setup
    usb_controller_init();             // 0x4FE9 — USB controller initialization
    eeprom_detect_and_load();          // 0x4F3C — detect EEPROM, load code to RAM

    // === Init Hook 1: GPIO/config setup (bit 2 of hook_config) ===
    read_hook_enable();                // 0x7360 — reads XDATA[0xC617] into ACC
    if (hook_config & 0x04) {          // bit 2 = init hook 1 enable
        EEPROM_HOOK_1();               // thunk to 0xC843 (EEPROM offset +0x13)
    }

    // === Optional: unknown init (bit 0 of hook_config) ===
    read_hook_enable();                // 0x7360
    if (hook_config & 0x01) {          // bit 0
        unknown_0x73A6();              // 0x73A6
        unknown_0x5736();              // 0x5736
    }

    timer_config = IRAM[0x31];         // save timer config from EEPROM init
    setup_display_timers();            // 0x3EAF
    setup_display_pipeline();          // thunk to 0x3E1C

    // === Init Hook 2: HW init + display loop (bit 3 of hook_config) ===
    read_hook_enable();                // 0x7360
    if (hook_config & 0x08) {          // bit 3 = init hook 2 enable
        EEPROM_HOOK_2();               // thunk to 0xC943 (EEPROM offset +0x10 target)
        // NOTE: On stock firmware, init hook 2 NEVER RETURNS
        // (it contains the display service loop)
    }

    // If init hook 2 didn't take over, ROM runs its own display loop:
    display_hw_init();                 // 0x5D16
    set_display_active();              // bit 0x00 = 1
    output_timing_setup();             // 0x7335

    // === Main Display Service Loop (runs forever) ===
    for (;;) {
        host_detect();                 // 0x4E8D — check USB host connection

        // Host reconfiguration mailbox
        if (XDATA[0xDDFF] == 0x5A) {   // host wrote magic byte
            XDATA[0xDDFF] = 0;
            safe_reconfig();           // 0x67D1 — disable IRQ, retune DAC
        }

        // Frame pacing delay
        if (XDATA[0xC55E] == 0) {
            delay = 0;
        } else {
            delay = 0x32;              // 50 ticks
        }
        rom_delay();                   // 0x63A4

        usb_frame_manage();            // 0x3A5C — process incoming USB frames

        // === Periodic Hook (bit 4 of hook_config) ===
        read_hook_enable();            // 0x7360 — reads XDATA[0xC617]
        if (hook_config & 0x10) {      // bit 4 = periodic hook enable
            EEPROM_HOOK_PERIODIC();    // 0xC850 — EEPROM offset +0x20
            // NOTE: This is at +0x20, not +0x30!
        }
    }
}
```

## Hook Architecture (Corrected from ROM trace)

The EEPROM header byte [4] (XDATA[0xC617]) controls hook enables:

| Bit | Hook | EEPROM Offset | XDATA Address | Purpose |
|-----|------|---------------|---------------|---------|
| 2   | Init 1 | +0x13 (via LJMP at +0x00) | 0xC843 | GPIO setup, one-time config |
| 0   | Unknown | N/A | 0x73A6+0x5736 | ROM-internal init (not EEPROM hook) |
| 3   | Init 2 | +0x10 target | 0xC943 | HW init + display loop (never returns) |
| 4   | Periodic | +0x20 | 0xC850 | USB IRQ handler (display reconfig) |
| 5   | USB IRQ | +0x30 | 0xC860 | Called from USB interrupt (0x4D37) |

**IMPORTANT CORRECTION**: The periodic hook in the main loop calls **0xC850** (offset +0x20),
not 0xC860 (offset +0x30). Our earlier analysis of the USB IRQ handler found the hook at
0xC860 (bit 5), which is a DIFFERENT hook called from the USB interrupt context.

The stock MS9123 EEPROM header byte [4] = 0x2C = 0b00101100:
- Bit 2 = set (init hook 1 enabled)
- Bit 3 = set (init hook 2 enabled)
- Bit 5 = set (USB IRQ hook enabled)
- Bit 0 = clear (ROM-internal init skipped)
- Bit 4 = clear (main loop periodic hook disabled)

## Key Function Map

| Address | Name | Purpose |
|---------|------|---------|
| 0x40EB | reset_handler | IRAM clear, SP init, data init, call main_init |
| 0x48DB | main_init | Full system init + main display loop |
| 0x69BA | hw_early_init | Early hardware setup (clocks, power) |
| 0x4FE9 | usb_controller_init | USB controller setup |
| 0x4F3C | eeprom_detect_and_load | Detect EEPROM, load code, validate checksums |
| 0x20CE | eeprom_code_loader | I2C read EEPROM, checksum validation |
| 0x5D16 | display_hw_init | Configure video DAC, scaler, output timing |
| 0x7335 | output_timing_setup | CVBS output timing parameters |
| 0x7360 | read_hook_enable | Read XDATA[0xC617] into ACC (hook flags) |
| 0x3A5C | usb_frame_manage | Process incoming USB frames |
| 0x4E8D | host_detect | Check USB host connection state |
| 0x67D1 | safe_reconfig | Disable IRQ, retune DAC, re-enable |
| 0x63A4 | rom_delay | Delay loop (R7 = count) |
| 0x6683 | eeprom_magic_check | Check for A55A or 9669 magic |
| 0x5EA3 | eeprom_read_magic | I2C read 2 bytes to 0xC41B, validate magic |
| 0x53A9 | i2c_eeprom_read | I2C read (R2:R1=dest, R5=count, R7:R6=offset) |
| 0x6AB8 | i2c_start | I2C START condition |
| 0x46BC | i2c_send_byte | I2C send byte |
| 0x4D1C | usb_handler_main | USB interrupt dispatch (calls periodic hook) |
| 0x5971 | usb_isr | USB interrupt service routine |

## EEPROM Code Map (loaded to XDATA 0xC830+)

| Offset | XDATA | Content | Called By |
|--------|-------|---------|----------|
| +0x00 | 0xC830 | LJMP to init hook 1 body | ROM init (bit 2) |
| +0x03 | 0xC833 | store_r4r5r6r7 helper | ROM callbacks |
| +0x10 | 0xC840 | LJMP to init hook 2 body | ROM init (bit 3) |
| +0x13 | 0xC843 | Init hook 1 body (GPIO, "DW" signature) | Via LJMP at +0x00 |
| +0x20 | 0xC850 | (available for main loop hook) | ROM main loop (bit 4) |
| +0x2E | 0xC85E | Halt trap (SJMP self) | Error handler |
| +0x30 | 0xC860 | LJMP to periodic handler | USB IRQ (bit 5) |
| +0x33 | 0xC863 | Host connection check (160 bytes) | Via LJMP at +0x30 |
