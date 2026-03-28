/*
 * MS2107 EEPROM Firmware - Reconstructed from disassembly
 *
 * The MS2107 is a CVBS/S-Video to USB capture chip (datasheet V1.0, 2021-01):
 *   - 10-bit 4-channel video ADC: CVBS (pin 8), S-Video Y/C (pins 6/3), G1IN (pin 5)
 *   - 24-bit audio ADC (or I2S via GPIO0)
 *   - UVC 1.0: MJPEG up to 1920x1080@30Hz, YUV422 up to 720x576@25Hz
 *   - Auto NTSC/PAL detection, auto CVBS/S-Video selection
 *   - 12MHz crystal + internal PLL, LQFP-48
 *   - GPIO4 (pin 19) = EEPROM write protect
 *
 * Firmware is loaded from I2C EEPROM at boot, called via two hooks:
 *   - Normal hook at 0xC800 (called from main loop, R7 = command ID)
 *   - IRQ hook at 0xC810 (called from USB interrupt)
 *
 * The firmware manages CVBS/S-Video signal detection, NTSC/PAL
 * identification, video ADC configuration, and the UVC capture pipeline.
 *
 * Original binary: MS2107.BIN, code at offset 0x30, 1168 bytes
 * Load address: 0xC800
 *
 * Source: radare2 + Ghidra disassembly of MS2107_ROM.BIN and EEPROM
 */

#include "hw_defs.h"
#include "rom_stubs.h"

/* === Internal RAM variables (direct addressing) === */
__data __at(0x0B) uint8_t irq_flags;       /* IRQ status flags */
__data __at(0x0F) uint8_t irq_cmd_lo;      /* IRQ command low byte */
__data __at(0x10) uint8_t irq_cmd_hi;      /* IRQ command high byte */
__data __at(0x11) uint8_t irq_data0;       /* IRQ data byte 0 */
__data __at(0x12) uint8_t irq_data1;       /* IRQ data byte 1 */
__data __at(0x36) uint8_t clock_divisor;    /* Clock/timing divisor */
__data __at(0x40) uint8_t signal_standard;  /* Video standard (0=none, 2=NTSC?, >7=lock) */
__data __at(0x43) uint8_t video_mode;       /* Current video mode */
__data __at(0x44) uint8_t video_output;     /* Video output enable state */
__data __at(0x46) uint8_t output_active;    /* Output active flag */
__data __at(0x48) uint8_t signal_subtype;   /* Signal sub-type / variant */
__data __at(0x4B) uint8_t config_reg;       /* Configuration register */
__data __at(0x4E) uint8_t timing_param;     /* Video timing parameter */
__data __at(0x50) uint8_t accum_lo;         /* Accumulator low byte */
__data __at(0x51) uint8_t accum_hi;         /* Accumulator high byte */
__data __at(0x9D) uint8_t sfr_9d;           /* SFR or upper IRAM */

__bit __at(0x04) flag_video_init;           /* bit addr 0x04 = byte 0x20, bit 4 */
__bit __at(0x21) flag_signal_detect;        /* bit addr 0x21 = byte 0x24, bit 1 */

/* Additional XDATA registers used */
__xdata __at(0xC7DA) uint8_t userconfig_0a; /* Userconfig byte at offset 0x0A */
__xdata __at(0xD200) uint8_t fw_state0;
__xdata __at(0xD201) uint8_t fw_state1;
__xdata __at(0xD202) uint8_t fw_state2;
__xdata __at(0xD203) uint8_t fw_mode;       /* Signal monitor mode select */
__xdata __at(0xD204) uint8_t fw_retry_cnt;  /* Signal detection retry counter */
__xdata __at(0xD205) uint8_t fw_counter;    /* General purpose counter */
__xdata __at(0xD206) uint8_t fw_last_std;   /* Last seen signal standard */
__xdata __at(0xD207) uint8_t fw_delay_arg;  /* Delay argument (passed to ROM delay) */
__xdata __at(0xD208) uint8_t fw_setup_arg;  /* Video setup argument */

__xdata __at(0xFB4D) uint8_t vsig_status;   /* Video ADC signal status (NTSC/PAL/no signal) */
__xdata __at(0xFB4F) uint8_t vsig_flags;    /* Video ADC flags (bit 4 = signal quality?) */
__xdata __at(0xFB8D) uint8_t vsig_line_lo;  /* Detected line count low (262=NTSC, 312=PAL) */
__xdata __at(0xFB8E) uint8_t vsig_line_hi;  /* Detected line count high */
__xdata __at(0xFBD6) uint8_t vsync_trigger; /* VSync trigger register */
__xdata __at(0xFBD9) uint8_t vsync_status;  /* VSync status register */

__xdata __at(0xC62A) uint8_t vdec_frame_cnt; /* Video decoder frame counter */

__xdata __at(0xF806) uint8_t vout_timing;   /* Video output timing */
__xdata __at(0xF808) uint8_t vout_cfg2;     /* Video output config 2 */
__xdata __at(0xF9A0) uint8_t scaler_enable; /* Scaler enable register */
__xdata __at(0xFC01) uint8_t usb_pkt_size0; /* USB packet size / config 0 */
__xdata __at(0xFC02) uint8_t usb_pkt_size1; /* USB packet size / config 1 */
__xdata __at(0xFC08) uint8_t usb_ctrl0;
__xdata __at(0xFC0B) uint8_t usb_ctrl1;
__xdata __at(0xFC0C) uint8_t usb_timer;     /* USB timer / frame counter */
__xdata __at(0xFC0D) uint8_t usb_timer2;    /* USB timer 2 */
__xdata __at(0xFC44) uint8_t usb_ctrl2;

__xdata __at(0xFE84) uint8_t vin_hscale_lo;
__xdata __at(0xFE85) uint8_t vin_hscale_hi;
__xdata __at(0xFEB9) uint8_t vin_ctrl;


/* === Host command mailbox (XDATA 0xD210-0xD21F) ===
 * The host writes commands via HID 0xB6 (XDATA write), reads results
 * via 0xB5 (XDATA read). The mailbox is polled by cmd_video_process
 * (R7=2) which runs every main loop iteration.
 *
 * Protocol:
 *   Host writes: [cmd] to D210, [param0] to D211, [param1] to D212
 *   Firmware: processes command, writes results to D214-D219, sets D213=0x02 (done)
 *   Host reads: D213 for status, D214-D219 for response data
 *   Host clears: D210=0 when done reading
 */
__xdata __at(0xD210) uint8_t mbox_cmd;       /* Command byte (0=idle) */
__xdata __at(0xD211) uint8_t mbox_param0;    /* Parameter 0 */
__xdata __at(0xD212) uint8_t mbox_param1;    /* Parameter 1 */
__xdata __at(0xD213) uint8_t mbox_status;    /* Status: 0=idle, 2=done, 0xFF=error */
__xdata __at(0xD214) uint8_t mbox_resp0;     /* Response byte 0 */
__xdata __at(0xD215) uint8_t mbox_resp1;     /* Response byte 1 */
__xdata __at(0xD216) uint8_t mbox_resp2;     /* Response byte 2 */
__xdata __at(0xD217) uint8_t mbox_resp3;     /* Response byte 3 */
__xdata __at(0xD218) uint8_t mbox_resp4;     /* Response byte 4 */
__xdata __at(0xD219) uint8_t mbox_resp5;     /* Response byte 5 */

/* Mailbox command IDs */
#define MBOX_CMD_SIGNAL_STATUS  0x01  /* Read signal detection state */
#define MBOX_CMD_READ_IMAGE     0x02  /* Read image adjustment params */
#define MBOX_CMD_WRITE_IMAGE    0x03  /* Write image adjustment param */
#define MBOX_CMD_VIDEO_INPUT    0x04  /* Force video input selection */
#define MBOX_CMD_GPIO_READ      0x05  /* Read GPIO port state */
#define MBOX_CMD_GPIO_WRITE     0x06  /* Write GPIO port state */
#define MBOX_CMD_I2C_WRITE      0x10  /* I2C write transaction */
#define MBOX_CMD_I2C_READ       0x11  /* I2C read transaction */
#define MBOX_CMD_I2C_SCAN       0x12  /* I2C bus scan */

/* Video adjustment registers in XDATA (set by ROM, readable/writable) */
__xdata __at(0xC67B) uint8_t adj_brightness;
__xdata __at(0xC67D) uint8_t adj_contrast;
__xdata __at(0xC67F) uint8_t adj_hue;
__xdata __at(0xC681) uint8_t adj_saturation;

/* === Forward declarations === */
void cmd_setup_video_regs(void);
void process_mailbox(void);
#if defined(CUSTOM_USB_SERIAL) || defined(CUSTOM_USB_MANUFACTURER)
static void write_usb_string(__xdata uint8_t *desc, const char *str);
#endif
void cmd_video_mode_config(void);
void cmd_video_output_config(void);
void cmd_video_process(void);
void cmd_video_reset(void);


/* ================================================================
 * ROM call wrappers
 * ================================================================ */

/* fcn.0000cc86: call ROM video mode config */
void call_rom_video_mode_config(void)       /* 0xCC86 */
{
    rom_video_mode_config();                /* LCALL 0x5659 */
}

/* fcn.0000cc8a: call ROM video display */
void call_rom_video_display(void)           /* 0xCC8A */
{
    rom_video_display();                    /* LCALL 0x44BA */
}

/* fcn.0000cc6b: delay with argument in R7, stores arg to D207 */
void delay_with_arg(uint8_t count)          /* 0xCC6B */
{
    fw_delay_arg = count;                   /* D207 = R7 */
    rom_delay(count);                       /* LCALL 0x6F52 */
}

/* fcn.0000cc74: video setup with argument, stores arg to D208 */
void video_setup_with_arg(uint8_t param)    /* 0xCC74 */
{
    fw_setup_arg = param;                   /* D208 = R7 */
    rom_video_setup(param);                 /* LCALL 0x5C29 */
}


/* ================================================================
 * fcn.0000c803 - Reset firmware state
 * Defined in crt0_ms2107.asm (must be at fixed offset 0x03)
 * ================================================================ */
extern void reset_fw_state(void);


/* ================================================================
 * fcn.0000cc3b - Set USB frame parameters
 * R7 = upper nibble for FC08 register
 * Sets FC01/FC02 to 0x3F, FC0C/FC0D to 0x10, then delays
 * ================================================================ */
void set_usb_frame_params(uint8_t mode)     /* 0xCC3B */
{
    usb_ctrl0 = (usb_ctrl0 & 0x0F) | mode; /* FC08 = (FC08 & 0x0F) | R7 */
    usb_pkt_size0 = 0x3F;                  /* FC01 = 0x3F */
    usb_pkt_size1 = 0x3F;                  /* FC02 = 0x3F */
    usb_timer  = 0x10;                     /* FC0C = 0x10 */
    usb_timer2 = 0x10;                     /* FC0D = 0x10 */
    delay_with_arg(0x1E);                  /* delay(30) - falls through via LJMP */
}


/* ================================================================
 * fcn.0000cb5f - Compute line count delta and set USB frame rate
 * Reads vsig_line_lo/hi, computes delta, clamps to range,
 * sets USB frame params accordingly
 * ================================================================ */
void adjust_frame_rate(void)                /* 0xCB5F */
{
    int16_t delta;
    uint8_t line_lo = vsig_line_lo;         /* FB8D */
    uint8_t line_hi = vsig_line_hi;         /* FB8E */

    delta = (int16_t)line_hi - (int16_t)line_lo;

    if (delta < 0x11) {
        /* Small delta -> use 0x50 mode */
        set_usb_frame_params(0x50);
    } else if (delta > 0x20) {
        /* Large delta -> use 0xA0 mode */
        set_usb_frame_params(0xA0);
    }
    /* Otherwise leave unchanged */
}


/* ================================================================
 * fcn.0000cb22 - Monitor line count and adjust timing
 * Waits while line count delta < 0x24, decrementing FC01
 * when FC01 reaches 0 or delta exceeds 0x47, exits
 * Copies FC01 to FC02 on exit
 * ================================================================ */
void monitor_line_timing(void)              /* 0xCB22 */
{
    int16_t delta;
    uint8_t line_lo, line_hi;

    do {
        line_lo = vsig_line_lo;
        line_hi = vsig_line_hi;
        delta = (int16_t)line_hi - (int16_t)line_lo;

        if (delta >= 0x24) break;
        if (usb_pkt_size0 == 0) break;
        if (line_hi >= 0x47) break;

        usb_pkt_size0--;
        delay_with_arg(0x02);

    } while (1);

    /* Copy current packet size to mirror register */
    usb_pkt_size1 = usb_pkt_size0;
}


/* ================================================================
 * fcn.0000c8e7 - Video signal detection / VSync monitoring
 * Main signal detection loop. Monitors line count register (FB8D)
 * to detect stable video signal. Uses fw_counter (D205) to track
 * detection state. Transitions through states:
 *   - Wait for line count in range [0x20, 0x24)
 *   - Wait for line count >= 0x22, decrement timer (FC0C)
 *   - Wait for line count >= 0x22, increment timer (FC0C) up to 0x1F
 *   - Increment fw_counter, check USB status (FC08 & 0xF0 == 0xA0)
 *   - When counter > 1 and USB ready: set up frame params, loop back
 * ================================================================ */
void signal_detect(void)                    /* 0xC8E7 */
{
    uint8_t line_count;
    int16_t signed_line;

    fw_counter = 0;

    while (1) {
        line_count = vsig_line_lo;          /* FB8D */
        signed_line = (int16_t)line_count;

        /* Check if line count >= 0x20 (signed) */
        if (signed_line >= 0x20) {
            /* Check if line count < 0x24 (signed) — signal in lock range */
            if (signed_line < 0x24) {
                /* Line count out of range [0x22..): copy FC0C to FC0D, return */
                usb_timer2 = usb_timer;
                return;
            }
        }

        /* Line count < 0x22: wait and decrement timer */
        if (signed_line < 0x22) {
            /* Poll until line count >= 0x22 */
            while (vsig_line_lo < 0x22) {
                if (usb_timer == 0) break;
                usb_timer--;
                delay_with_arg(0x01);
            }
            continue;   /* restart main loop */
        }

        /* Line count >= 0x22: increment timer up to 0x1F */
        while (vsig_line_lo >= 0x22) {      /* signed comparison, >= 0x22 */
            if (usb_timer == 0x1F) break;
            usb_timer++;
            delay_with_arg(0x01);
        }

        /* Increment counter and check thresholds */
        fw_counter++;
        if (fw_counter > 1) {
            /* Check USB control status */
            if ((usb_ctrl0 & 0xF0) != 0xA0) {
                continue;   /* not ready, keep monitoring */
            }
            /* Reset counter and set up frame params */
            fw_counter = 0;
            set_usb_frame_params(0x50);
            continue;
        }
    }
}


/* ================================================================
 * fcn.0000cb9b - Signal monitor with mode select
 * R7 = mode (stored in D203)
 * If mode != 0, calls signal_detect (c8e7)
 * If mode == 0, calls monitor_line_timing (cb22)
 * Loops up to 3 times or until vsync_status & 0x3F is clear
 * and vsig_status & 0x07 == 0x06
 * ================================================================ */
void signal_monitor(uint8_t mode)           /* 0xCB9B */
{
    fw_mode = mode;                         /* D203 = R7 */
    fw_retry_cnt = 0;                       /* D204 = 0 */

    do {
        /* Trigger VSync measurement */
        vsync_trigger = 1;                  /* FBD6 = 1 */
        vsync_trigger = 0;                  /* FBD6 = 0 */

        /* Call appropriate detection function */
        if (fw_mode != 0) {
            signal_detect();
        } else {
            monitor_line_timing();
        }

        /* Increment retry counter */
        fw_retry_cnt++;
        if (fw_retry_cnt == 3) return;

        /* Check if VSync stable */
        if ((vsync_status & 0x3F) != 0) continue;

        /* Check signal status */
        if ((vsig_status & 0x07) != 0x06) continue;

        /* Both checks passed — signal is stable */
        return;

    } while (1);
}


/* ================================================================
 * fcn.0000cacd - 24-bit / 16-bit division
 * Divides R4:R6:R7 by R5 (24-bit by 8-bit)
 * Returns quotient in R7, remainder in R5
 * This is a compiler runtime helper for division
 * ================================================================ */
uint8_t divide_24_8(uint8_t dividend_hi, uint8_t dividend_mid,
                    uint8_t dividend_lo, uint8_t divisor)  /* 0xCACd */
{
    /* This is a standard 8051 multi-byte division routine.
     * Too complex to reconstruct exactly in C - the compiler
     * will generate its own division code.
     * Functionally: return (dividend_hi:dividend_mid:dividend_lo) / divisor
     */
    uint32_t dividend = ((uint32_t)dividend_hi << 16) |
                        ((uint32_t)dividend_mid << 8) |
                        dividend_lo;
    return (uint8_t)(dividend / divisor);
}


/* ================================================================
 * fcn.0000ca72 - Video output initialization
 * Called when signal standard changes or on first lock.
 * Adjusts frame rate, sets up signal monitoring, configures
 * output timing and scaler parameters.
 * ================================================================ */
void video_output_init(void)                /* 0xCA72 */
{
    uint8_t result;

    adjust_frame_rate();                    /* CB5F */

    signal_monitor(1);                      /* CB9B: mode=1 (signal_detect) */
    signal_monitor(0);                      /* CB9B: mode=0 (monitor_line_timing) */

    fw_state1 = 1;                          /* D201 = 1 */

    /* Check signal standard and sub-type for output enable */
    if (signal_standard == 0) {
        /* No signal - write timing param directly */
        goto write_timing;
    }

    if (signal_standard != 0x02 ||
        signal_subtype != 0 ||
        (vsig_flags & 0x10) != 0) {
        /* Non-standard signal or wrong sub-type */
        vout_timing = timing_param;         /* F806 = IRAM[0x4E] */
        output_active = 0;                  /* IRAM[0x46] = 0 */
        video_setup_with_arg(0);            /* CC74: setup(0) */
    } else {
write_timing:
        vout_timing = timing_param;         /* F806 = IRAM[0x4E] */
        output_active = 1;                  /* IRAM[0x46] = 1 */
        video_setup_with_arg(1);            /* CC74: setup(1) */
    }

    /* Compute frame rate: (clock_divisor * 2) / 1000 */
    /* Uses division helper: divide R4:R6:R7 = 0x00:0x03:0xE8 (1000) by clock_divisor */
    result = divide_24_8(0, 3, 0xE8, clock_divisor);
    result = result << 1;                   /* multiply by 2 */
    delay_with_arg(result);                 /* delay proportional to frame rate */

    vin_ctrl = 0;                           /* FEB9 = 0 */
}


/* ================================================================
 * fcn.0000cbd7 - Check signal standard change and reinitialize
 * Called from cmd2 when fw_state0 != 0
 * If standard changed, reconfigures frame params and reinits
 * ================================================================ */
void check_signal_change(void)              /* 0xCBD7 */
{
    /* Check if signal standard changed */
    if (fw_last_std != signal_standard) {
        set_usb_frame_params(0x50);         /* CC3B: reset frame params */
        fw_state1 = 0;                      /* D201 = 0 */
        fw_last_std = signal_standard;      /* D206 = IRAM[0x40] */
    }

    /* If fw_state1 is still 0, check for signal lock */
    if (fw_state1 == 0) {
        if (signal_standard < 7) {          /* signed: standard < 7 means no lock */
            if (vdec_frame_cnt == 0) {      /* C62A: frame counter must be 0 */
                video_output_init();        /* CA72: full output init */
                accum_lo = 0;               /* IRAM[0x50] = 0 */
                accum_hi = 0;               /* IRAM[0x51] = 0 */
            }
        }
    }
}


/* ================================================================
 * Handler for R7==2: Main video processing command
 * Checks states and manages signal detection + initialization
 * ================================================================ */
void cmd_video_process(void)                /* 0xCA06 */
{
    /* If fw_state0 != 0, check for signal change */
    if (fw_state0 != 0) {
        check_signal_change();              /* CBD7 */
    }

    /* If frame counter active, skip detection */
    if (vdec_frame_cnt != 0) {
        goto check_accumulator;
    }

    /* Check signal standard */
    if (signal_standard >= 7) {             /* signed: >= 7 means locked */
        goto clear_state2;
    }

    /* Signal not locked - check detection flags */
    if (flag_signal_detect) goto check_state2;

    /* Check vsig_status for valid signal (bits 3:0 == 0x06) */
    if ((vsig_status & 0x0F) != 0x06) goto check_state2;

    /* Signal looks valid - update detection state */
    if (fw_state2 == 0) {
        fw_state2 = 1;
        fw_state1 = 0;
    }

    if (fw_state2 == 1) {
        accum_lo = 0;
        accum_hi = 0;
        goto check_accumulator;
    }

check_state2:
    /* Signal not detected - reset state2 */
    if (fw_state2 != 1) goto check_accumulator;
    fw_state2 = 2;
    goto check_accumulator;

clear_state2:
    fw_state2 = 0;

check_accumulator:
    /* Check signal standard and accumulator */
    if (signal_standard >= 7) goto done;

    if ((vsig_flags & 0x10) != 0) {
        accum_lo = 0;
        accum_hi = 0;
    }

done:
    /* Check host command mailbox every main loop iteration */
    if (mbox_cmd != 0) {
        process_mailbox();
    }
    return;
}


/* ================================================================
 * Handler for R7==5: Video reset and scaler config
 * Calls ROM video mode config, masks F808, sets scaler, calls ROM reset
 * ================================================================ */
void cmd_video_reset(void)                  /* 0xCC58 */
{
    call_rom_video_mode_config();           /* LCALL 0x5659 */

    vout_cfg2 &= 0x11;                     /* F808 &= 0x11 */

    scaler_enable = 1;                      /* F9A0 = 1 */

    rom_video_reset();                      /* LCALL 0x6087 (falls through via LJMP) */
}


/* ================================================================
 * IRQ handler (0xCC0F)
 * Implemented as hand-written assembly in crt0_ms2107.asm, matching
 * the original firmware's logic from disassembly. Written in asm
 * rather than C because SDCC's code generation for this function
 * produced subtle differences (comparison instruction choices,
 * operand ordering, bit test methods) that broke USB enumeration
 * when running in interrupt context.
 *
 * Logic:
 *   1. If irq_flags bit 5 set AND irq_cmd_hi==2 AND !(userconfig_0a & 1):
 *      reset irq_cmd_lo=0, irq_cmd_hi=4
 *   2. If irq_flags bit 7 clear AND (irq_data0|irq_data1)!=0:
 *      set flag 0x22.6 + P0.6, return early
 *   3. Otherwise: call rom_video_display (0x44BA)
 * ================================================================ */
/* (implemented in assembly in crt0_ms2107.asm) */


/* ================================================================
 * Initialization code at 0xC97A (embedded in fcn.0000c8e7 tail)
 * This is the 8051 standard C startup:
 *   - Clear IRAM 0x00-0xFF
 *   - Set SP = 0x55
 *   - Jump to main init
 * Reached on first boot / EEPROM reload
 * ================================================================ */
/* This is generated by the C runtime startup, not reconstructed */


/* ================================================================
 * Normal hook entry point (0xC800)
 * Called from ROM main loop with R7 = command ID.
 * The crt0 shim translates Keil R7 -> SDCC DPL before calling us.
 * ================================================================ */
void normal_hook_dispatch(uint8_t cmd) __using(0)
{
    switch (cmd) {
        case 0:  cmd_setup_video_regs(); break;
        case 1:  cmd_video_mode_config();
                 cmd_video_output_config();  /* falls through */
                 break;
        case 2:  cmd_video_process(); break;
        case 5:  cmd_video_reset(); break;
        case 7:  cmd_video_output_config(); break;
        case 10: vin_ctrl = 0x01; break;
        case 13: cmd_video_output_config(); break;
        default: break;
    }
}


/* ================================================================
 * Handler for R7==0: Setup video decoder registers
 * Configures NTSC/PAL timing parameters
 * ================================================================ */
void cmd_setup_video_regs(void)             /* 0xC83D */
{
    usb_ctrl1 &= 0xEF;                     /* FC0B: clear bit 4 */
    fw_state2 = 0;                          /* D202 = 0 */
    reset_fw_state();

    /* Video decoder timing banks (C612-C620) */
    *(__xdata uint8_t *)0xC612 = 0x00;
    *(__xdata uint8_t *)0xC613 = 0x60;
    *(__xdata uint8_t *)0xC614 = 0xBE;

    *(__xdata uint8_t *)0xC61A = 0x00;
    *(__xdata uint8_t *)0xC61B = 0x5F;
    *(__xdata uint8_t *)0xC61C = 0x80;

    *(__xdata uint8_t *)0xC616 = 0x00;
    *(__xdata uint8_t *)0xC617 = 0x60;
    *(__xdata uint8_t *)0xC618 = 0x87;

    *(__xdata uint8_t *)0xC61E = 0x00;
    *(__xdata uint8_t *)0xC61F = 0x60;
    *(__xdata uint8_t *)0xC620 = 0x80;

    config_reg = 0x05;
}


/* ================================================================
 * Handler for R7==1: Video mode configuration
 * ================================================================ */
void cmd_video_mode_config(void)            /* 0xC884 */
{
    usb_ctrl0 = (usb_ctrl0 & 0xFD) | 0x01;
    sfr_9d |= 0x07;

    vin_hscale_hi &= 0xFD;
    vin_hscale_lo = 0x7A;

    if (video_mode == 0x01) {
        usb_ctrl2 |= 0x10;
    }

    /* Overwrite USB string descriptors in RAM.
     * build_usb_descriptors (ROM 0x1E57) runs right before this handler.
     * The ROM builds string descriptors at fixed XDATA addresses:
     *   0xC4C3 = manufacturer (from EEPROM[0x10] or ROM default)
     *   0xC4F3 = product (from EEPROM[0x20] or ROM default)
     *   0xC523 = serial number (always ROM "20200909")
     *
     * To override, define CUSTOM_USB_SERIAL and/or CUSTOM_USB_MANUFACTURER
     * as string literals. Max 8 chars for serial, ~15 for manufacturer.
     * The strings are converted to USB descriptor format (UTF-16LE) at boot.
     */
#ifdef CUSTOM_USB_SERIAL
    write_usb_string((__xdata uint8_t *)0xC523, CUSTOM_USB_SERIAL);
#endif
#ifdef CUSTOM_USB_MANUFACTURER
    write_usb_string((__xdata uint8_t *)0xC4C3, CUSTOM_USB_MANUFACTURER);
#endif
}

#if defined(CUSTOM_USB_SERIAL) || defined(CUSTOM_USB_MANUFACTURER)
/* Write an ASCII string as a USB string descriptor to XDATA.
 * Format: [length, 0x03, char0, 0x00, char1, 0x00, ...] */
static void write_usb_string(__xdata uint8_t *desc, const char *str)
{
    uint8_t i, len;
    for (len = 0; str[len]; len++);
    desc[0] = len * 2 + 2;
    desc[1] = 0x03;
    for (i = 0; i < len; i++) {
        desc[2 + i * 2] = str[i];
        desc[3 + i * 2] = 0x00;
    }
}
#endif


/* ================================================================
 * Handler for R7==7/13: Video output configuration
 * ================================================================ */
void cmd_video_output_config(void)          /* 0xC8AA */
{
    if (video_output == 0) {
        *(__xdata uint8_t *)0xF80B &= 0xEF;
        *(__xdata uint8_t *)0xF804 |= 0x10;
        *(__xdata uint8_t *)0xF809 |= 0x08;
    } else {
        *(__xdata uint8_t *)0xF847 |= 0x07;
        *(__xdata uint8_t *)0xF804 |= 0x30;
        *(__xdata uint8_t *)0xF809 |= 0x18;
    }
}


/* ================================================================
 * Infinite loop / halt (0xCC8E)
 * Used as a trap - SJMP to self
 * ================================================================ */
/* 0xCC8E: sjmp 0xCC8E  -- this is a deliberate infinite loop, likely
 * a watchdog-triggering halt for error conditions */

/* ================================================================
 * Host command mailbox processor
 * Called from cmd_video_process (R7=2) every main loop iteration.
 * Reads command from XDATA[0xD210], processes it, writes response
 * to XDATA[0xD214-0xD219], sets status at XDATA[0xD213].
 *
 * Host protocol (via HID 0xB5/0xB6 XDATA read/write):
 *   1. Write param0 to 0xD211, param1 to 0xD212 (if needed)
 *   2. Write command byte to 0xD210 (triggers processing)
 *   3. Poll 0xD213 until status == 0x02 (done) or 0xFF (error)
 *   4. Read response from 0xD214-0xD219
 *   5. Write 0x00 to 0xD210 to clear
 * ================================================================ */
void process_mailbox(void)
{
    uint8_t cmd = mbox_cmd;
    uint8_t p0 = mbox_param0;
    uint8_t p1 = mbox_param1;
    uint8_t nak;

    switch (cmd) {

    /* ── Feature 1: Signal status reporting ── */
    case MBOX_CMD_SIGNAL_STATUS:
        mbox_resp0 = signal_standard;       /* IRAM[0x40]: 0=none, <7=detecting, >=7=locked */
        mbox_resp1 = vsig_status & 0x0F;    /* FB4D: signal status bits */
        mbox_resp2 = vsig_line_lo;          /* FB8D: detected line count low */
        mbox_resp3 = vsig_line_hi;          /* FB8E: detected line count high */
        mbox_resp4 = fw_state2;             /* D202: detection state (0/1/2) */
        mbox_resp5 = video_mode;            /* IRAM[0x43]: input mode from GPIO */
        mbox_status = 0x02;
        break;

    /* ── Feature 2: Read image adjustments ── */
    case MBOX_CMD_READ_IMAGE:
        mbox_resp0 = adj_brightness;        /* C67B */
        mbox_resp1 = adj_contrast;          /* C67D */
        mbox_resp2 = adj_saturation;        /* C681 */
        mbox_resp3 = adj_hue;              /* C67F */
        mbox_resp4 = 0;
        mbox_resp5 = 0;
        mbox_status = 0x02;
        break;

    /* ── Feature 2: Write image adjustment ── */
    case MBOX_CMD_WRITE_IMAGE:
        /* p0 = which param (0=brightness, 1=contrast, 2=saturation, 3=hue) */
        /* p1 = new value */
        switch (p0) {
            case 0: adj_brightness = p1; break;
            case 1: adj_contrast = p1; break;
            case 2: adj_saturation = p1; break;
            case 3: adj_hue = p1; break;
            default: mbox_status = 0xFF; goto done_mbox;
        }
        mbox_status = 0x02;
        break;

    /* ── Feature 4: Video input selection ── */
    case MBOX_CMD_VIDEO_INPUT:
        /* p0 = input mode to force:
         *   0 = auto-detect (restore default)
         *   1 = force CVBS (pin 8, AVIN)
         *   2 = force S-Video (pins 3+6, SVCIN+SVYIN)
         *   3 = force G1IN (pin 5)
         * Sets IRAM[0x43] which video_pipeline_init reads.
         * The ROM re-evaluates on next signal change. */
        video_mode = p0;
        mbox_status = 0x02;
        break;

    /* ── Feature 5: GPIO read ── */
    case MBOX_CMD_GPIO_READ:
        /* Returns current state of P0, P2, P3 ports */
        mbox_resp0 = P0;
        mbox_resp1 = P2;
        mbox_resp2 = P3;
        mbox_resp3 = 0;
        mbox_resp4 = 0;
        mbox_resp5 = 0;
        mbox_status = 0x02;
        break;

    /* ── Feature 5: GPIO write ── */
    case MBOX_CMD_GPIO_WRITE:
        /* p0 = port select: 0=P0, 2=P2, 3=P3
         * p1 = value to write
         * WARNING: writing to wrong port bits can break video/USB.
         * Useful for GPIO4 (P2.4 = EEPROM WP) and GPIO0 (P3.5 = audio select). */
        switch (p0) {
            case 0: P0 = p1; break;
            case 2: P2 = p1; break;
            case 3: P3 = p1; break;
            default: mbox_status = 0xFF; goto done_mbox;
        }
        mbox_status = 0x02;
        break;

    /* ── Feature 3: I2C write ── */
    case MBOX_CMD_I2C_WRITE:
        /* p0 = device address (7-bit, shifted left by caller)
         * p1 = register/data byte
         * Must disable EX0/EX1 — I2C uses P3.2 (INT0) and P3.3 (INT1)
         * as GPIO, which would trigger spurious interrupts. */
        EX0 = 0; EX1 = 0;
        rom_i2c_start();
        nak = rom_i2c_write(p0);            /* device address + W */
        if (nak) {
            rom_i2c_stop();
            EX0 = 1; EX1 = 1;
            mbox_resp0 = 0;                 /* NAK — device not present */
            mbox_status = 0xFF;
            break;
        }
        nak = rom_i2c_write(p1);            /* register/data byte */
        rom_i2c_stop();
        EX0 = 1; EX1 = 1;
        mbox_resp0 = nak ? 0 : 1;          /* 1=ACK, 0=NAK */
        mbox_status = 0x02;
        break;

    /* ── Feature 3: I2C read ── */
    case MBOX_CMD_I2C_READ:
        /* p0 = device address (7-bit << 1)
         * p1 = register address to read from */
        EX0 = 0; EX1 = 0;
        rom_i2c_start();
        nak = rom_i2c_write(p0);            /* device address + W */
        if (nak) {
            rom_i2c_stop();
            EX0 = 1; EX1 = 1;
            mbox_resp0 = 0;
            mbox_status = 0xFF;
            break;
        }
        rom_i2c_write(p1);                  /* register address */
        rom_i2c_start();                    /* repeated start */
        rom_i2c_write(p0 | 0x01);          /* device address + R */
        mbox_resp0 = rom_i2c_read(1);      /* read byte, send NAK (last byte) */
        rom_i2c_stop();
        EX0 = 1; EX1 = 1;
        mbox_status = 0x02;
        break;

    /* ── Feature 3: I2C bus scan ── */
    case MBOX_CMD_I2C_SCAN:
        /* p0 = start address (7-bit << 1), scans 6 addresses from here
         * Returns bitmap in resp0: bit N = device at (p0 + N*2) responded */
        EX0 = 0; EX1 = 0;
        {
            uint8_t bitmap = 0;
            uint8_t i;
            for (i = 0; i < 6; i++) {
                uint8_t addr = p0 + (i << 1);
                rom_i2c_start();
                nak = rom_i2c_write(addr);
                rom_i2c_stop();
                if (!nak) {
                    bitmap |= (1 << i);
                }
            }
            mbox_resp0 = bitmap;
            mbox_resp1 = p0;                /* echo start address */
        }
        EX0 = 1; EX1 = 1;
        mbox_status = 0x02;
        break;

    default:
        mbox_status = 0xFF;                 /* unknown command */
        break;
    }

done_mbox:
    mbox_cmd = 0;                           /* clear command (done) */
}


/* No main() — this firmware is hook-driven. The ROM calls
 * 0xC800 (normal hook) and 0xC810 (IRQ hook) directly.
 * The custom crt0_ms2107.asm places LJMPs at those offsets. */
