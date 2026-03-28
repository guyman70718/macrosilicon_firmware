/*
 * MS9123 ROM Function Stubs
 *
 * Declared here, implemented in crt0_ms9123.asm as calling convention
 * shims. The ROM was compiled with Keil C51 (args in R7, return in R7).
 * Our EEPROM code is compiled with SDCC (args in DPL, return in DPL).
 *
 * Most MS9123 ROM calls take no parameters — only rom_delay needs
 * a DPL->R7 bridge. The crt0 handles all convention translation.
 *
 * The MS9123 is a USB-to-CVBS/S-Video display adapter with:
 *   - 10-bit 3-channel video DAC (CVBS, S-Video Y, S-Video C)
 *   - 720x480 NTSC / 720x576 PAL output
 *   - 24MHz crystal + internal PLL
 *   - I2S audio output (48KHz/16bit stereo)
 */

#ifndef ROM_STUBS_H
#define ROM_STUBS_H

#include <stdint.h>

/* ROM 0x0BA1 - 10-bit DAC output quality check / calibration
 * Evaluates DAC readback samples (from IRAM[0x55-0x5C] snapshot)
 * against expected output levels. The MS9123 has a 10-bit 3-channel
 * DAC driving CVBS (pin 32), S-Video Y (pin 33), S-Video C (pin 34).
 * Uses IRAM[0x55] mode byte for expected level selection. */
extern void rom_output_quality_check(void);

/* ROM 0x2DA2 - Generic display output function
 * Handles display modes that aren't the specific NTSC mode.
 * Uses IRAM[0x3F] for mode selection, writes to C5C7 region. */
extern void rom_generic_display(void);

/* ROM 0x3A5C - USB frame buffer management
 * Processes incoming USB frames from the host.
 * Manages C559/C555 buffer state. Called with EX0 disabled. */
extern void rom_usb_frame_manage(void);

/* ROM 0x4E8D - Host detection / keepalive
 * Monitors whether the USB host is actively sending frames.
 * Checks C805/C612 status, manages auto-detection counter. */
extern void rom_host_detect(void);

/* ROM 0x58B9 - Identify host output mode
 * Reads SFR_DAC and characterizes what the host is sending.
 * Populates IRAM[0x3F-0x44] with mode/standard info. */
extern void rom_identify_host_output(void);

/* ROM 0x5D16 - Display hardware initialization
 * Configures 10-bit video DAC, scaler for 720x480/576 output,
 * CVBS/S-Video timing, SFRs (0x95/0x9B/0x9D).
 * Called once from init hook 2. */
extern void rom_display_hw_init(void);

/* ROM 0x63A4 - Delay / frame pacing
 * count = delay iterations. Used for frame pacing in the display loop. */
extern void rom_delay(uint8_t count);

/* ROM 0x65CB - Peripheral / I2C communication
 * Complex calling convention: uses DPTR + R4-R7.
 * Called from the store_r4r5r6r7 asm helper, not directly from C. */
extern void rom_peripheral_comm(void);

/* ROM 0x66BD - PLL/clock reconfiguration
 * Waits for PLL to stabilize (polls CL register — the MS9123 uses
 * a 24MHz crystal with internal PLL per datasheet), then reconfigures
 * DAC and timing SFRs. Called when display mode changes. */
extern void rom_clock_reconfig(void);

/* ROM 0x67D1 - Safe reconfiguration (host-triggered)
 * Disables interrupts, toggles DAC clock gate (SFR 0x95 bit 6),
 * performs I2C communication, re-enables interrupts.
 * Triggered by host writing 0x5A to mailbox at XDATA[0xDDFF]. */
extern void rom_safe_reconfig(void);

/* ROM 0x7335 - CVBS output timing setup
 * Configures timing for 720x480 NTSC or 720x576 PAL output.
 * Called once during init hook 2. */
extern void rom_output_timing_setup(void);

#endif /* ROM_STUBS_H */
