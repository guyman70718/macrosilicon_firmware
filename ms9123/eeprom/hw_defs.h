/*
 * MS9123 Hardware Definitions
 * Macrosilicon MS9123 USB Display Controller (USB-to-CVBS/S-Video)
 *
 * From datasheet (V1.0, 2020-04):
 *   - 10-bit 3-channel video DAC (CVBS, S-Video Y, S-Video C)
 *   - 720x480 NTSC / 720x576 PAL output
 *   - 24MHz crystal, internal PLL
 *   - I2S audio output (48KHz/16bit stereo)
 *   - SPI flash or I2C EEPROM for firmware
 *   - QFN-48, 3.3V + 1.2V
 *
 * Pin 32 = AVOUT (CVBS), Pin 33 = SVYOUT (S-Video Y),
 * Pin 34 = SVCOUT (S-Video C), Pin 36 = DACREF (390R to GND)
 */

#ifndef HW_DEFS_H
#define HW_DEFS_H

#include <stdint.h>
#include <mcs51/8051.h>

/* P0 bit definitions */
__sbit __at(0x80) P0_0;    /* P0.0 - USB host active (frames incoming) */
__sbit __at(0x83) P0_3;    /* P0.3 - DAC/output ready indicator */
__sbit __at(0x86) P0_6;    /* P0.6 - display output active indicator */

#endif /* HW_DEFS_H */
