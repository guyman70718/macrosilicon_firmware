/*
 * MS2109 Hardware Definitions
 * Macrosilicon MS2109 HDMI-to-USB2.0 Capture (datasheet HJ-BMJL-PD-002, rev B/0)
 *
 * Chip ID: 0xA7 (XDATA 0xF800)
 * VID:PID: 0x534D:0x2109 ("MACROSILICON USB Video")
 * EEPROM magic: 0xA55A (shared with MS9123)
 * Hook config: EEPROM[4], bit 0 = normal (0xCC00), bit 2 = IRQ (0xCC20)
 *
 * QFN-48 (7x7mm), 24MHz crystal, internal PLL
 * HD RX 1.4b: max 4K@30Hz input, capture up to 1920x1080@30Hz
 * UVC 1.0 output: MJPEG + YUV422, UAC 1.0 audio
 *
 * GPIO pin assignments (from datasheet Table 6.1 / 8.1):
 *   GPIO0 (pin 39): LED indicator — 0 when playing, 1 otherwise
 *   GPIO1 (pin 40): user-defined, internal pull-up
 *   GPIO2 (pin 13): EEPROM SCL (I2C clock, shared bus)
 *   GPIO3 (pin 14): EEPROM SDA (I2C data, shared bus)
 *   GPIO5 (pin 37): EEPROM WP (write protect)
 *
 * HDMI interface:
 *   HDRXHPD (pin 17): hot-plug detect output
 *   HDRXDET (pin 18): 5V input detection
 *   RXDDCSDA/RXDDCSCL (pins 21/22): DDC bus for EDID
 *   HDRX0P/N, HDRX1P/N, HDRX2P/N: 3 TMDS data channels
 *   HDRXCP/CN: TMDS clock channel
 */

#ifndef HW_DEFS_H
#define HW_DEFS_H

#include <stdint.h>
#include <mcs51/8051.h>

/* P0 bit definitions */
__sbit __at(0x80) P0_0;    /* P0.0 — set during IRQ hook processing */

/* Macrosilicon-specific SFRs */
__sfr __at(0x93) MS_SFR_93;    /* Written with 0x03 during IRQ hook */
__sfr __at(0xAE) MS_SFR_AE;    /* Debug/status output register */
__sfr __at(0xBC) SFR_BC;       /* Timer/counter value (saved to IRAM 0x1B) */
__sfr __at(0xBD) SFR_BD;       /* Timer/counter value (saved to IRAM 0x1C) */
__sfr __at(0xBE) SFR_BE;       /* Timer/counter value (saved to IRAM 0x1D) */
__sfr __at(0xBF) SFR_BF;       /* Timer/counter value (saved to IRAM 0x1E) */

#endif /* HW_DEFS_H */
