/*
 * MS2109 EEPROM Firmware
 *
 * Mailbox at XDATA 0xDE00-0xDE07.
 */

#include "hw_defs.h"
#include "rom_stubs.h"

__xdata __at(0xDE00) uint8_t mbox_cmd;
__xdata __at(0xDE01) uint8_t mbox_param0;
__xdata __at(0xDE02) uint8_t mbox_param1;
__xdata __at(0xDE03) uint8_t mbox_status;
__xdata __at(0xDE04) uint8_t mbox_resp0;
__xdata __at(0xDE05) uint8_t mbox_resp1;
__xdata __at(0xDE06) uint8_t mbox_resp2;
__xdata __at(0xDE07) uint8_t mbox_resp3;
__xdata __at(0xDE0C) uint8_t signal_state;
__xdata __at(0xF800) uint8_t chip_id;

static void i2c_begin(void) { EX0 = 0; EX1 = 0; }
static void i2c_end(void)   { EX0 = 1; EX1 = 1; }

void normal_hook_dispatch(uint8_t cmd) __using(0)
{
    if (cmd != 2) return;
    if (mbox_cmd == 0) return;

    switch (mbox_cmd) {
    case 0x01:  /* Signal status */
        mbox_resp0 = signal_state;
        mbox_resp1 = chip_id;
        mbox_status = 0x02;
        break;

    case 0x05:  /* GPIO read */
        mbox_resp0 = P0;
        mbox_resp1 = P2;
        mbox_resp2 = P3;
        mbox_status = 0x02;
        break;

    case 0x06:  /* GPIO write */
        if (mbox_param0 == 0) P0 = mbox_param1;
        else if (mbox_param0 == 2) P2 = mbox_param1;
        else if (mbox_param0 == 3) P3 = mbox_param1;
        mbox_status = 0x02;
        break;

    case 0x10:  /* I2C write */
        i2c_begin();
        rom_i2c_start();
        mbox_resp0 = rom_i2c_write(mbox_param0);
        if (mbox_resp0 == 0)
            mbox_resp0 = rom_i2c_write(mbox_param1);
        rom_i2c_stop();
        i2c_end();
        mbox_status = 0x02;
        break;

    case 0x11:  /* I2C read register */
        i2c_begin();
        rom_i2c_start();
        if (rom_i2c_write(mbox_param0 << 1) != 0) { mbox_resp0 = 0xFF; goto i2c_done; }
        if (rom_i2c_write(mbox_param1) != 0) { mbox_resp0 = 0xFF; goto i2c_done; }
        rom_i2c_start();
        if (rom_i2c_write((mbox_param0 << 1) | 1) != 0) { mbox_resp0 = 0xFF; goto i2c_done; }
        mbox_resp0 = rom_i2c_read(1);
i2c_done:
        rom_i2c_stop();
        i2c_end();
        mbox_status = 0x02;
        break;

    case 0x12: { /* I2C scan */
        uint8_t bitmap = 0;
        uint8_t i;
        i2c_begin();
        for (i = 0; i < 8; i++) {
            rom_i2c_start();
            if (rom_i2c_write((0x50 + i) << 1) == 0)
                bitmap |= (1 << i);
            rom_i2c_stop();
        }
        i2c_end();
        mbox_resp0 = bitmap;
        mbox_status = 0x02;
        break;
    }

    default:
        mbox_status = 0xFF;
        break;
    }

    mbox_cmd = 0;
}
