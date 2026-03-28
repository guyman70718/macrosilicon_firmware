/*
 * MS2107 Hardware Definitions
 * Macrosilicon MS2107 USB Analog Video Capture Chip
 *
 * From datasheet (V1.0, 2021-01):
 *   - 10-bit 4-channel video ADC (CVBS, S-Video Y/C, G1IN)
 *   - 24-bit 2-channel audio ADC (or I2S input via GPIO0)
 *   - 12MHz crystal, internal PLL
 *   - UVC 1.0 video output: MJPEG (up to 1920x1080@30Hz) or YUV422
 *   - UAC 1.0 audio output: 48KHz stereo
 *   - Auto CVBS / S-Video detection
 *   - LQFP-48, 5V input with built-in 3.3V + 1.2V LDOs
 *
 * GPIO assignments (from datasheet):
 *   GPIO0 (pin 35) = Audio input source: GND=I2S, float=internal ADC
 *   GPIO2 (pin 13) = EEPROM SCL (I2C clock)
 *   GPIO3 (pin 12) = EEPROM SDA (I2C data)
 *   GPIO4 (pin 19) = EEPROM WP (write protect)
 *
 * Video input pins:
 *   Pin 3  = SVCIN  (S-Video C)
 *   Pin 5  = G1IN   (general video input)
 *   Pin 6  = SVYIN  (S-Video Y)
 *   Pin 8  = AVIN   (CVBS input)
 */

#ifndef HW_DEFS_H
#define HW_DEFS_H

#include <stdint.h>
#include <mcs51/8051.h>

/* P0.6 bit - used in IRQ handler for signalling */
__sbit __at(0x86) P0_6;

#endif /* HW_DEFS_H */
