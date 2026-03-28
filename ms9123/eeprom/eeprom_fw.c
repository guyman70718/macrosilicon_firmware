/*
 * MS9123 EEPROM Firmware - Reconstructed from disassembly
 *
 * The MS9123 is a USB-to-CVBS/S-Video display adapter ("usb extscreen").
 * It receives video frames from a USB host and outputs composite video
 * via a 10-bit 3-channel DAC (CVBS on pin 32, S-Video Y/C on pins 33/34).
 * Supported modes: 720x480 NTSC, 720x576 PAL.
 *
 * From datasheet: 24MHz crystal + internal PLL, I2S audio output,
 * SPI flash or I2C EEPROM for firmware storage.
 *
 * The EEPROM firmware is called via three hooks from the ROM:
 *   - Init hook 1 at +0x00 (0xC830): One-time GPIO/config setup
 *   - Init hook 2 at +0x10 (0xC840): HW init, enters display service loop (never returns)
 *   - Periodic hook at +0x30 (0xC860): Called from USB IRQ, handles reconfiguration
 *
 * The firmware manages the display output pipeline: USB frame
 * reception, CVBS/S-Video output timing via the 10-bit DAC,
 * and host connection state detection.
 *
 * Original binary: MS9123.BIN, code at offset 0x30, 413 bytes
 * Load address: 0xC830
 * EEPROM has ~1600 bytes free (0x0200-0x07FF = 0xFF)
 *
 * Source: radare2 disassembly + Ghidra decompiled MS9123_CODE.bin
 */

#include "hw_defs.h"
#include "rom_stubs.h"

/* === Internal RAM variables === */
__data __at(0x31) uint8_t timer_config;       /* Display refresh timer config */
__data __at(0x35) uint8_t event_flags_lo;     /* Bit 0: host connection event */
__data __at(0x36) uint8_t event_flags_hi;     /* Bit 2: display reconfigure request */
__data __at(0x3F) uint8_t display_mode_hi;    /* Display/output standard high byte */
__data __at(0x40) uint8_t display_mode_lo;    /* Display/output standard low byte */
__data __at(0x45) uint8_t output_param_lo;    /* CVBS output parameter low */
__data __at(0x46) uint8_t output_param_hi;    /* CVBS output parameter high */
__data __at(0x49) uint8_t frame_count_lo;     /* Frame/refresh counter low */
__data __at(0x4A) uint8_t frame_count_hi;     /* Frame/refresh counter high */
__data __at(0x4B) uint8_t host_connect_state; /* USB host connection state machine */
__data __at(0x4C) uint8_t host_prev_status;   /* Previous host status (0xFF = init) */
__data __at(0x55) uint8_t dac_readings[8];    /* 0x55-0x5C: DAC/output level shadow (8 samples) */

/* SFRs — MS9123 has a 10-bit 3-channel video DAC (CVBS + S-Video Y/C) */
__sfr __at(0xAB) SFR_DAC;    /* Video DAC data/status — 10-bit DAC readback or control.
                               * Read 8 times in dac_snapshot_and_check() to sample
                               * output levels across a field period. */
__sfr __at(0x93) SFR_93;     /* DAC/analog gate control — cleared before GPIO checks
                               * and before DAC snapshot. May enable DAC readback mode. */
__sfr __at(0x94) SFR_94;     /* Receives copy of host_prev_status — possibly a
                               * comparator or status latch for the video DAC */
__sfr __at(0xB1) SFR_P3ALT;  /* P3 alternate function register. Pins 1-4 are
                               * SPI_CS/MOSI/MISO/SCLK shared with I2C_SCL/SDA
                               * (per datasheet). P3.6/P3.7 set as output in init. */

/* Bit-addressable flags in byte 0x21 */
__bit __at(0x08) flag_dac_ready;       /* 0x21.0 — DAC snapshot taken */
__bit __at(0x0A) flag_reconfig_pending; /* 0x21.2 — reconfiguration queued */
__bit __at(0x0B) flag_process_now;     /* 0x21.3 — immediate processing needed */
__bit __at(0x0C) flag_mode_changed;    /* 0x21.4 — display mode has changed */
__bit __at(0x0D) flag_fw_loaded;       /* 0x21.5 — firmware initialized */

/* === XDATA registers === */
__xdata __at(0xC343) uint8_t scaler_hsize;    /* Output scaler horizontal config */
__xdata __at(0xC347) uint8_t scaler_vtiming0; /* Output scaler vertical timing 0 */
__xdata __at(0xC348) uint8_t scaler_vtiming1; /* Output scaler vertical timing 1 */
__xdata __at(0xC4DA) uint8_t cvbs_timing;     /* CVBS output timing parameter */
__xdata __at(0xC612) uint8_t output_active;   /* Display output pipeline active flag */
__xdata __at(0xDDFF) uint8_t host_mailbox;    /* Host command mailbox (write 0x5A to trigger reconfig) */
__xdata __at(0xDE04) uint8_t xfer_reg;        /* Data transfer register */
__xdata __at(0xDE05) uint8_t xfer_buf[4];     /* Transfer buffer (4 bytes via store_r4r5r6r7) */
__xdata __at(0xDE09) uint8_t delay_arg;       /* Delay argument storage */
__xdata __at(0xDE0A) uint8_t connect_event;   /* Host connection event counter */
__xdata __at(0xDFDF) uint8_t fw_ready[2];     /* Firmware ready signature: 'D','W' */
__xdata __at(0xF005) uint8_t dac_ctrl;        /* DAC / analog output control */
__xdata __at(0xF020) uint8_t analog_mux;      /* Analog output mux / routing */
__xdata __at(0xF031) uint8_t output_filter0;  /* CVBS output filter config 0 */
__xdata __at(0xF032) uint8_t output_filter1;  /* CVBS output filter config 1 */
__xdata __at(0xF160) uint8_t cvbs_output_en;  /* CVBS output enable / blanking */
__xdata __at(0xF880) uint8_t video_dac_cfg;   /* Video DAC configuration */

/* === Forward declarations === */
void periodic_handler(void);
void host_connection_check(void);


/* fcn.0000c833 - Store R4:R5:R6:R7 to consecutive XDATA at DPTR
 * Defined in crt0_ms9123.asm (must be at fixed offset +0x03) */
extern void store_r4r5r6r7(void);


/* ================================================================
 * fcn.0000c9b7 - Delay helper
 * Stores count to DE09 for diagnostics, calls ROM delay
 * ================================================================ */
void delay_with_arg(uint8_t count)      /* 0xC9B7 */
{
    delay_arg = count;
    rom_delay(count);
}


/* ================================================================
 * fcn.0000c97e - DAC output snapshot + signal quality check
 * Reads the DAC feedback register (SFR 0xAB) 8 times into IRAM,
 * then calls ROM signal processing to evaluate output quality.
 * This monitors whether the CVBS output is within spec.
 * ================================================================ */
void dac_snapshot_and_check(void)       /* 0xC97E */
{
    SFR_93 = 0;

    /* Sample DAC output 8 times (SFR_DAC may give different
     * readings on each access if it's a live ADC/comparator) */
    dac_readings[0] = SFR_DAC;
    dac_readings[1] = SFR_DAC;
    dac_readings[2] = SFR_DAC;
    dac_readings[3] = SFR_DAC;
    dac_readings[4] = SFR_DAC;
    dac_readings[5] = SFR_DAC;
    dac_readings[6] = SFR_DAC;
    dac_readings[7] = SFR_DAC;

    flag_dac_ready = 0;             /* Clear DAC ready flag */
    P0_3 = 1;                       /* Assert output-ready GPIO */
    P0_6 = 1;                       /* Assert status indicator */
    rom_output_quality_check();      /* LCALL 0x0BA1 — evaluate output */
}


/* Init hook 1 (0xC830 -> 0xC843)
 * Defined in crt0_ms9123.asm (must be at fixed offset +0x13 to fit layout).
 * Configures P3 GPIO, clears event counter, sets fw_loaded flag,
 * writes "DW" ready signature to XDATA[0xDFDF]. */
/* (implemented in assembly in crt0_ms9123.asm) */


/* ================================================================
 * Init hook 2 (0xC840 -> 0xC943)
 * Called once after hook 1. Performs full hardware initialization
 * for the display output pipeline, then enters the main display
 * service loop which runs for the lifetime of the device.
 *
 * The loop manages:
 *   - USB frame buffer reception (rom_usb_frame_manage)
 *   - Host connection monitoring (rom_host_detect)
 *   - Host-triggered reconfiguration (0x5A mailbox command)
 *   - CVBS output filter maintenance
 * ================================================================ */
void init_hook2(void)                   /* 0xC943 */
{
    rom_display_hw_init();           /* LCALL 0x5D16 — init DAC, scaler, output */

    /* Set bit 0 of byte 0x20 (bit-addressable) — global "display active" flag */
    *(__data uint8_t *)0x20 |= 0x01;

    rom_output_timing_setup();       /* LCALL 0x7335 — configure CVBS timing */
    IP &= ~0x02;                    /* Lower priority of ext1 interrupt */

    /* === Main display service loop (never returns) === */
    for (;;) {
        EX0 = 0;                    /* Disable ext0 IRQ during frame management */
        delay_with_arg(0x32);       /* Delay 50 ticks (frame pacing) */
        rom_usb_frame_manage();      /* LCALL 0x3A5C — process incoming USB frames */
        EX0 = 1;                    /* Re-enable ext0 IRQ */

        rom_host_detect();           /* LCALL 0x4E8D — check if host is sending */

        /* Check for host reconfiguration command */
        if (host_mailbox == 0x5A) {
            host_mailbox = 0;
            rom_safe_reconfig();     /* LCALL 0x67D1 — disable IRQ, retune DAC, re-enable */
        }

        /* Maintain CVBS output filter settings */
        output_filter0 = 0x3F;     /* F031 = 0x3F — filter bandwidth */
        output_filter1 = 0x00;     /* F032 = 0x00 — no filter bypass */

        /* Ensure CVBS output blanking is off */
        cvbs_output_en &= 0xFD;   /* F160 bit 1 clear — output active */
    }
}


/* ================================================================
 * Periodic hook (0xC860 -> 0xC903)
 * Called from USB IRQ handler. Handles two types of events:
 *
 * 1. Display reconfiguration (event_flags_hi bit 2):
 *    Full output pipeline reconfigure — clock, scaler, timing.
 *    Triggered when host changes resolution or refresh rate.
 *
 * 2. Host connection event (event_flags_lo bit 0):
 *    USB host connected/disconnected — run connection check
 *    to update display output state.
 * ================================================================ */
void periodic_handler(void)             /* 0xC903 */
{
    /* Check for display reconfiguration request */
    if (event_flags_hi & 0x04) {
        rom_clock_reconfig();           /* LCALL 0x66BD — wait for clock stable, retune */

        /* Configure 10-bit DAC and analog output for new mode */
        video_dac_cfg = 0x10;           /* F880 — DAC configuration (output enable?) */
        dac_ctrl &= 0xF7;              /* F005 — clear bit 3 (take DAC out of standby) */
        analog_mux &= 0xFE;            /* F020 — clear bit 0 (select CVBS output path) */

        /* Set output scaler for CVBS timing
         * Datasheet modes: 720x480 NTSC or 720x576 PAL
         * These values likely configure for one of those modes */
        scaler_hsize = 0x60;           /* C343 = 96 — horizontal active region config */
        scaler_vtiming0 = 0x02;        /* C347 — vertical timing (field/frame setup) */
        scaler_vtiming1 = 0x03;        /* C348 — vertical timing (interlace config) */
        cvbs_timing = 0x0D;            /* C4DA = 13 — CVBS sync/blanking timing */

        event_flags_hi &= 0xFB;        /* Clear reconfigure flag */
    }

    /* Check for host connection event */
    if (event_flags_lo & 0x01) {
        event_flags_lo &= 0xFE;        /* Clear event flag */
        host_connection_check();        /* Process connection state change */
    }
}


/* ================================================================
 * fcn.0000c863 - Host connection check / display state manager
 * The main display management function (160 bytes).
 *
 * Monitors P0 GPIO pins to track USB host connection state:
 *   P0.0 = USB host active (sending frames)
 *   P0.2 = USB bus state change
 *   P0.4 = USB suspend/resume indicator
 *
 * Manages a state machine (host_connect_state / host_prev_status)
 * that tracks transitions between:
 *   - No host connected
 *   - Host connected, identifying output mode
 *   - Host connected, display active
 *
 * When a specific output mode is detected (0x3F==0x21, 0x40==0x09,
 * 0x46==0x08, 0x45==0x00 — likely 720x480i NTSC or similar),
 * triggers DAC snapshot and output quality check.
 *
 * For other modes, falls back to the ROM's generic display
 * output function.
 * ================================================================ */
void host_connection_check(void)        /* 0xC863 */
{
    SFR_93 = 0;

    /* P0.2 set = USB bus state change — clear it, reset processing */
    if (P0 & 0x04) {
        P0 &= 0xFB;
        flag_process_now = 0;
    }

    /* P0.4 set = USB suspend/resume — set P0.7 (output standby?), reset */
    if (P0 & 0x10) {
        P0 |= 0x80;
        flag_process_now = 0;
    }

    /* Host status state machine */
    if (host_prev_status != 0xFF) {
        SFR_94 = host_prev_status;

        if (host_connect_state == 0 && host_prev_status != 0) {
            host_connect_state = 1;     /* Host newly connected */
        } else if (host_connect_state == 1 && host_prev_status == 0) {
            host_connect_state = 0;     /* Host disconnected */
        }

        host_prev_status = 0xFF;        /* Reset for next cycle */
    }

    /* Check for pending reconfiguration */
    if (flag_reconfig_pending) {
        flag_mode_changed = 1;
        flag_reconfig_pending = 0;
        flag_process_now = 1;
    }

    /* P0.0 = USB host actively sending frames */
    if (P0_0) {
        if (connect_event != 0) {
            /* We already detected connection — check output mode */
            connect_event = 0;

            /* Check for specific CVBS output mode.
             * Datasheet supports 720x480 NTSC and 720x576 PAL.
             * display_mode 0x21:0x09, output_param 0x08:0x00
             * likely identifies one of these standard modes. */
            if (display_mode_hi == 0x21 &&
                display_mode_lo == 0x09 &&
                output_param_hi == 0x08 &&
                output_param_lo == 0x00) {
                dac_snapshot_and_check();    /* Known mode — tune DAC output */
            }
        } else {
            /* First detection — identify what the host is sending */
            rom_identify_host_output();      /* LCALL 0x58B9 */
            flag_process_now = 1;
        }
    } else {
        /* No USB frames — check if we have pending frame counts */
        if (frame_count_hi | frame_count_lo) {
            flag_process_now = 1;
        }
    }

    /* Process display output update if needed */
    if (!flag_process_now) return;

    SFR_93 = 0;

    /* Same mode check for the output path */
    if (display_mode_hi == 0x21 &&
        display_mode_lo == 0x09 &&
        output_param_hi == 0x08 &&
        output_param_lo == 0x00) {
        /* Known CVBS output mode — direct setup */
        connect_event = 1;
        output_active = 0;              /* C612 = 0 (will be set by ROM after config) */
        P0_6 = 1;                       /* Assert output indicator */
    } else {
        /* Generic mode — let ROM handle display output */
        rom_generic_display();           /* LCALL 0x2DA2 */
    }

    flag_process_now = 0;
}


/* ================================================================
 * Unreferenced helpers (0xC9A3-0xC9C6)
 * Likely called by ROM code via computed addresses or used
 * as callback functions registered during init.
 *
 * 0xC9A3: Read XDATA[DE04], write to DPTR from R6:R7
 *         (ROM callback: transfer output data to host)
 * 0xC9AD: Write R4:R5:R6:R7 to XDATA[DE05], call rom_peripheral_comm
 *         (ROM callback: send 4-byte status block to host)
 * 0xC9C0: Read XDATA[R6:R7] into R7 — generic XDATA read helper
 * 0xC9C7: Set SP=0x5C, LJMP halt — watchdog/error reset handler
 * ================================================================ */

/* No main() — hook-driven firmware. Init hook 2 contains the
 * display service loop which runs for the device's lifetime. */
