"""
Low-level HID helpers for Macrosilicon MS2107/MS2109/MS9123 devices.

Provides byte-level EEPROM (E5/E6) and XDATA (B5/B6) access over
9-byte HID feature reports. Works on Windows with the `hidapi` package.

Usage:
    from ms_hid import MSDevice
    with MSDevice(vid=0x534D, pid=0x6021) as d:
        val = d.xdata_read(0xC617)
        d.xdata_write(0xC617, val | 0x20)
        eeprom = d.eeprom_dump()
"""

import hid
import time


class MSDevice:
    """HID interface to a Macrosilicon capture device."""

    def __init__(self, vid=None, pid=None, path=None):
        self.dev = hid.device()
        self.vid = vid
        self.pid = pid
        self.path = path

    def __enter__(self):
        if self.path:
            self.dev.open_path(self.path)
        else:
            self.dev.open(self.vid, self.pid)
        return self

    def __exit__(self, *args):
        self.dev.close()

    # -- raw HID helpers --

    def _send(self, cmd, addr, data_byte=0x00):
        report = [0x00, cmd, (addr >> 8) & 0xFF, addr & 0xFF,
                  data_byte, 0x00, 0x00, 0x00, 0x00]
        self.dev.send_feature_report(report)

    def _recv(self):
        return self.dev.get_feature_report(0, 9)

    # -- XDATA (B5/B6) --

    def xdata_read(self, addr):
        """Read one byte from XDATA."""
        self._send(0xB5, addr)
        return self._recv()[4]

    def xdata_write(self, addr, val):
        """Write one byte to XDATA."""
        self._send(0xB6, addr, val)

    def xdata_read_block(self, addr, length):
        """Read a block of XDATA bytes (1 byte per HID transaction)."""
        buf = bytearray(length)
        for i in range(length):
            buf[i] = self.xdata_read(addr + i)
        return buf

    def xdata_write_block(self, addr, data):
        """Write a block of bytes to XDATA."""
        for i, b in enumerate(data):
            self.xdata_write(addr + i, b)

    # -- EEPROM (E5/E6) --

    def eeprom_read(self, addr):
        """Read one byte from EEPROM (uses E5 which returns 5 bytes, we take [4])."""
        self._send(0xE5, addr)
        return self._recv()[4]

    def eeprom_write(self, addr, val, delay=0.01):
        """Write one byte to EEPROM. WARNING: live write, no undo."""
        self._send(0xE6, addr, val)
        time.sleep(delay)

    def eeprom_read_block(self, addr, length):
        """Read a block of EEPROM bytes."""
        buf = bytearray(length)
        for i in range(length):
            buf[i] = self.eeprom_read(addr + i)
        return buf

    def eeprom_dump(self, size=2048):
        """Dump the full EEPROM."""
        return self.eeprom_read_block(0, size)

    def eeprom_write_block(self, addr, data, delay=0.01):
        """Write a block to EEPROM with per-byte delay."""
        for i, b in enumerate(data):
            self.eeprom_write(addr + i, b, delay)

    # -- device info --

    def get_strings(self):
        """Read USB descriptor strings."""
        return {
            "manufacturer": self.dev.get_manufacturer_string(),
            "product": self.dev.get_product_string(),
            "serial": self.dev.get_serial_number_string(),
        }


if __name__ == "__main__":
    import sys
    vid = int(sys.argv[1], 16) if len(sys.argv) > 1 else 0x534D
    pid = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x6021
    with MSDevice(vid, pid) as d:
        info = d.get_strings()
        print(f"Device: {info['manufacturer']} {info['product']} ({info['serial']})")
        chip_id = d.xdata_read(0xF800)
        print(f"Chip ID at 0xF800: 0x{chip_id:02X}")
