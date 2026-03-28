/*
 * MS2107 ROM Function Stubs
 *
 * Declared here, implemented in crt0_ms2107.asm as calling convention
 * shims. The ROM was compiled with Keil C51 (args in R7/R5, return in R7).
 * Our EEPROM code is compiled with SDCC (args in DPL/B, return in DPL).
 * The crt0 shims bridge between conventions.
 *
 * The MS2107 is a CVBS/S-Video to USB capture chip with:
 *   - 10-bit 4-channel video ADC (auto CVBS / S-Video detection)
 *   - UVC 1.0 output (MJPEG up to 1920x1080@30, YUV422 up to 720x576@25)
 *   - 12MHz crystal + internal PLL
 */

#ifndef ROM_STUBS_H
#define ROM_STUBS_H

#include <stdint.h>

/* ROM 0x44BA - Video ADC / display bank register configuration
 * Configures the 10-bit video ADC and input routing.
 * The MS2107 has 4 video input channels: CVBS (pin 8),
 * S-Video Y (pin 6), S-Video C (pin 3), G1IN (pin 5).
 * Uses register bank 1 parameters (BANK1_R3, BANK1_R4). */
extern void rom_video_display(void);

/* ROM 0x5659 - Video input mode configuration
 * Sets up the video ADC and processing pipeline for the
 * detected signal standard (NTSC/PAL). Writes F8xx video
 * processing registers based on IRAM[0x43] (video mode)
 * and IRAM[0x48] (signal variant). */
extern void rom_video_mode_config(void);

/* ROM 0x5C29 - Video capture setup with parameter
 * param controls capture enable: 1=start, 0=stop.
 * Configures the UVC pipeline and USB isochronous transfers
 * for the selected output format (MJPEG/YUV422). */
extern void rom_video_setup(uint8_t param);

/* ROM 0x6087 - Video pipeline reset
 * Clears F8xx video processing registers, resets the
 * capture pipeline. Called when signal is lost or on
 * mode change. */
extern void rom_video_reset(void);

/* ROM 0x6F52 - Delay loop
 * count = iteration count. Each iteration calls the internal
 * delay subroutine twice (~ms-scale timing). */
extern void rom_delay(uint8_t count);

/* ROM 0x68BD - I2C start condition
 * Drives SDA low while SCL is high. Uses GPIO2 (SCL) and GPIO3 (SDA). */
extern void rom_i2c_start(void);

/* ROM 0x6B5B - I2C stop condition
 * Drives SDA high while SCL is high. */
extern void rom_i2c_stop(void);

/* ROM 0x5323 - I2C write byte
 * Sends one byte on I2C bus. Keil R7 = byte to send.
 * Returns ACK status in carry flag (C=1 means NAK). */
extern uint8_t rom_i2c_write(uint8_t val);

/* ROM 0x5934 - I2C read byte
 * Reads one byte from I2C bus. Keil R7 = ACK flag (0=ACK, 1=NAK).
 * Returns read byte in R7. */
extern uint8_t rom_i2c_read(uint8_t ack);

#endif /* ROM_STUBS_H */
