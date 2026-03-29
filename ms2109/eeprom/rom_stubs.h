/*
 * MS2109 ROM Function Declarations
 *
 * These are implemented as assembly wrappers in crt0_ms2109.asm
 * to bridge the Keil C51 (ROM) and SDCC (our code) calling conventions.
 */

#ifndef ROM_STUBS_H
#define ROM_STUBS_H

#include <stdint.h>

/* ROM 0xD03A — Default command dispatcher
 * Called from normal hook with R7 = command ID.
 * Dispatches to ROM's built-in command handlers. */
void rom_cmd_dispatch_default(void);

/* ROM 0xD2BD — Hardware init helper (calls ROM 0x48E6)
 * Called during signal detection to configure video hardware. */
void rom_hw_init(void);

/* ROM 0xD2C1 — Video processing wrapper (calls ROM 0x6069)
 * Called from IRQ hook when timer tick flag is set. */
void rom_video_process(void);

/* ROM 0x6345 — Hardware init with data table
 * Uses R3:R2:R1 as pointer to configuration data table in CODE space.
 * Called from the callback entry at 0xCC10. */
void rom_hw_init_table(void);

/* ROM 0xD27D — Arithmetic/calculation function
 * Used during video register programming. */
void rom_math_func(void);

/* ROM 0x6A8C — I2C start condition */
void rom_i2c_start(void);

/* ROM 0x6ABA — I2C stop condition */
void rom_i2c_stop(void);

/* ROM 0x4648 — I2C write byte
 * Keil R7 = byte to send.
 * Returns: carry = ACK (set=ACK, clear=NAK)
 * Our wrapper returns: DPL: 0=ACK, 1=NAK */
uint8_t rom_i2c_write(uint8_t byte);

/* ROM 0x4CF3 — I2C read byte
 * ACK/NAK controlled by bit 0x08 (IRAM 0x21 bit 0).
 * Our wrapper: DPL=0 for ACK (continue), DPL!=0 for NAK (last byte).
 * Returns read byte in DPL. */
uint8_t rom_i2c_read(uint8_t nak);

#endif /* ROM_STUBS_H */
