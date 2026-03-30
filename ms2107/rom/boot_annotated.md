# MS2107 Boot Sequence and Main Loop

## Reset Handler (0x5297)

```
1. Clear IRAM (0x00-0x7F = 0)
2. Set SP = 0x55
3. Process data init table at CODE:0x1BEE
4. Call chip_init (0x5DA4)
```

## Main Init — chip_init (0x5DA4)

```c
void chip_init(void)                    // 0x5DA4
{
    hw_pre_init();                       // Hardware pre-init (clocks, power)
    eeprom_reload();                     // 0x6656 — detect + load EEPROM
    parse_eeprom_config();               // Parse header: VID/PID, video config, hook flags

    // === Normal Hook: command 0 (video register setup) ===
    call_normal_hook_if_enabled(0);      // EEPROM hook at 0xC800 with R7=0

    video_pipeline_init();               // Init video ADC, processing pipeline
    set_audio_output_mode();             // Configure audio (internal ADC or I2S)
    build_usb_descriptors();             // Build USB device/config/string descriptors in RAM

    // === Normal Hook: command 1 (video mode config) ===
    call_normal_hook_if_enabled(1);      // EEPROM hook at 0xC800 with R7=1

    // Enable interrupts
    IT1 = 1;                             // Edge-triggered ext1
    EX1 = 1;                             // Enable ext1 interrupt
    EX0 = 1;                             // Enable ext0 interrupt
    EA  = 1;                             // Global interrupt enable

    // === Main Loop (runs forever) ===
    for (;;) {
        // Accumulator-based signal change detection
        if (accum_hi:accum_lo >= threshold) {
            signal_change_handler();
            accum = 0;
        }

        // Video parameter updates
        if (param_accum >= threshold) {
            update_video_params();
            param_accum = 0;
        }

        monitor_signal_presence();       // Check if video signal present
        monitor_signal_standard();       // Detect NTSC/PAL
        handle_signal_anomaly();         // Handle signal glitches

        // === Normal Hook: command 2 (main video processing) ===
        call_normal_hook_if_enabled(2);  // EEPROM hook at 0xC800 with R7=2
    }
}
```

## Hook Architecture

### Normal Hook Dispatch (0x6F47 → 0x6F9E → 0xC800)

```c
void call_normal_hook_if_enabled(uint8_t cmd)  // 0x6F47
{
    if (XDATA[0xC7D8] & 0x01) {          // bit 0 = normal hook enable
        dispatch_to_eeprom_hook(cmd);     // 0x6F9E
    }
}

void dispatch_to_eeprom_hook(uint8_t cmd)  // 0x6F9E
{
    XDATA[0xC66B] = cmd;                  // store command ID
    call_0xC800();                        // R7 = cmd, call EEPROM code
}
```

The ROM calls the normal hook with these command IDs:

| Command (R7) | Called From | Purpose |
|-------------|------------|---------|
| 0 | chip_init, before video pipeline | Video register setup |
| 1 | chip_init, after USB descriptor build | Video mode config |
| 2 | Main loop, every iteration | Main video processing |
| 3 | Signal detection | Signal detection helper |
| 5 | Video mode change | Video reset + scaler config |
| 7 | Video output change | Video output config |
| 8 | Multiple places | Video timing update |
| 9 | Signal detection | Input change handler |
| 10 | Video config | Video input enable |
| 12 | UVC processing | UVC parameter update |
| 13 | UVC processing | UVC output config |
| 14 | UVC resolution | Resolution change handler |

### IRQ Hook (0xC830, offset +0x30)

Called from the ext0 interrupt handler at 0x0006:

```c
void ext0_interrupt_handler(void)       // 0x0006
{
    save_R0_through_R7();

    if (XDATA[0xC7D8] & 0x08) {         // bit 3 = IRQ hook enable
        func_0xC830();                   // EEPROM code at +0x30
    } else {
        // Default: increment accumulators, clear F005
        accum_lo++; if (!accum_lo) accum_hi++;
        param_lo++; if (!param_lo) param_hi++;
        counter_lo++; if (!counter_lo) counter_hi++;
        XDATA[0xF005] = 0;
    }

    restore_R0_through_R7();
}
```

### USB Processing Hook (0xC820, offset +0x20)

```c
// Called from USB processing code
if (XDATA[0xC7D8] & 0x04) {           // bit 2 = hook enable
    func_0xC820();                     // EEPROM code at +0x20
}
```

Called during USB endpoint processing with HADDR register context.

### Hook Map

| Bit | Hook | EEPROM Offset | XDATA Address | Purpose |
|-----|------|---------------|---------------|---------|
| 0 | Normal | +0x00 | 0xC800 | Command dispatch (R7=cmd) |
| 1 | Unknown | +0x10 | 0xC810 | Not found in ROM trace |
| 2 | USB proc | +0x20 | 0xC820 | USB endpoint processing |
| 3 | IRQ | +0x30 | 0xC830 | Ext0/timer interrupt |

Stock hook flags = 0x03 (bits 0,1 enabled). The IRQ hook (bit 3) and USB hook
(bit 2) are disabled in the stock firmware.

### USB IRQ Handler (0x54AE)

```c
void usb_irq_handler(void)              // 0x54AE
{
    if (BANK1_R3 < 0 || (BANK2_R2 == 0 && BANK2_R1 == 0)) {
        video_display_update();          // 0x44BA
    } else {
        set_irq_flag();
        P0_6 = 1;
    }
    clear_flag();
}
```

This is a ROM handler for USB interrupts. The EEPROM IRQ hook at 0xC830
is called from the ext0/timer interrupt, not from USB.

## Key Function Map

| Address | Name | Purpose |
|---------|------|---------|
| 0x5297 | reset_handler | IRAM clear, SP=0x55, data init, call chip_init |
| 0x5DA4 | chip_init | Full system init + main loop |
| 0x6656 | eeprom_reload | Detect + load EEPROM code |
| 0x6F47 | call_normal_hook_if_enabled | Check bit 0, dispatch to 0xC800 |
| 0x6F9E | dispatch_to_eeprom_hook | Store cmd to C66B, call 0xC800 |
| 0x54AE | usb_irq_handler | USB interrupt handler (ROM, no EEPROM hooks) |
| 0x44BA | video_display_update | Video frame processing |
| 0x5DFE | video_input_select | Select CVBS/S-Video/G1IN input |
| 0x5EFF | video_adjust | Set brightness/contrast/saturation/hue |
| 0x6F52 | delay_loop | R7 iterations of double-delay |
| 0x6FA7 | gpio_and_port_init | P2.4=1, P3=0xEF, IEN1=0xEF |

## Video Adjustment Registers (from 0x5EFF)

The ROM has built-in video adjustment support via XDATA registers:

| Register | XDATA | Function |
|----------|-------|----------|
| Brightness | 0xC67B | `video_set_brightness()` or direct write to 0xFE90 |
| Contrast | 0xC67D | `video_set_contrast()` or direct write to 0xFE91 |
| Hue | 0xC67F | `video_set_hue()` or direct write to 0xFE93 |
| Saturation | 0xC681 | `video_set_saturation()` or direct write to 0xFE92 |

These are called when `IRAM[0x3A] != 0`, using `IRAM[0x43]` as mode selector.
Mode 3 uses named ROM functions; other modes write directly to FE9x registers.
