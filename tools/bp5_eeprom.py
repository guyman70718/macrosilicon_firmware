#!/usr/bin/env python3
"""
Bus Pirate 5 EEPROM read/write tool for Macrosilicon devices.

The MS2109 (and likely MS2107/MS9123) boards back-power the main chip
through board traces when 3.3V is applied to the EEPROM. The chip's
I2C controller then interferes with writes. Use 2.5V to keep the chip
below its operating threshold while the EEPROM still works.

Requirements:
  - Bus Pirate 5 connected via serial (default COM7)
  - SOIC clip on the EEPROM (24C16)
  - IO4 wired to EEPROM WP pin (active low)
  - USB cable UNPLUGGED from the target device

Usage:
    python bp5_eeprom.py write ms2109.bin          # write file to EEPROM
    python bp5_eeprom.py read backup.bin            # read EEPROM to file
    python bp5_eeprom.py verify ms2109.bin          # verify EEPROM against file
    python bp5_eeprom.py scan                       # scan I2C bus
    python bp5_eeprom.py --port COM8 write fw.bin   # use different serial port
    python bp5_eeprom.py --voltage 3.3 write fw.bin # use different voltage (careful!)
"""

import serial
import time
import argparse
import sys


class BusPirate5:
    def __init__(self, port="COM7", baud=115200, voltage=2.5):
        self.port = port
        self.baud = baud
        self.voltage = voltage
        self.bp = None

    def __enter__(self):
        self.bp = serial.Serial(self.port, self.baud, timeout=3)
        time.sleep(1)
        self.bp.reset_input_buffer()
        return self

    def __exit__(self, *args):
        if self.bp:
            self._cmd("w", 1)  # power off
            self._cmd("p", 1)  # pullups off
            self.bp.close()

    def _cmd(self, cmd, wait=1.0):
        self.bp.reset_input_buffer()
        self.bp.write((cmd + "\r\n").encode())
        time.sleep(wait)
        return self.bp.read(self.bp.in_waiting).decode(errors="replace")

    def setup_i2c(self):
        """Enter I2C mode with power, pullups, and WP grounded."""
        # Enter I2C mode
        resp = self._cmd("m", 1)
        if "Mode >" in resp:
            resp = self._cmd("5", 2)
        elif "I2C>" in resp:
            pass  # already in I2C mode
        else:
            # Try selecting I2C
            self._cmd("m", 1)
            resp = self._cmd("5", 2)

        # Accept previous settings or configure
        if "y/n" in resp:
            self._cmd("y", 2)

        # Power supply
        self._cmd("W", 1)
        self._cmd(str(self.voltage), 1)
        resp = self._cmd("", 2)  # accept current limit default

        if "Power supply:Enabled" not in resp:
            print(f"Warning: power supply response: {resp.strip()}")

        # Pull-ups
        resp = self._cmd("P", 1)
        if "Enabled" in resp:
            print(f"Pull-ups enabled")

        # Ground WP via IO4
        self._cmd("a 4", 1)
        time.sleep(0.5)

    def scan(self):
        """Scan I2C bus and return response."""
        resp = self._cmd("scan", 5)
        return resp

    def eeprom_write(self, filename):
        """Write file to 24C16 EEPROM with verify."""
        print(f"Writing {filename} to EEPROM...")
        resp = self._cmd(f"eeprom write -d 24X16 -f {filename} -v", 120)
        success = "Success" in resp
        for line in resp.split("\n"):
            line = line.strip()
            if any(k in line for k in ["Success", "Error", "complete"]):
                print(f"  {line}")
        return success

    def eeprom_read(self, filename):
        """Read EEPROM to file with verify."""
        print(f"Reading EEPROM to {filename}...")
        resp = self._cmd(f"eeprom read -d 24X16 -f {filename} -v", 120)
        success = "Success" in resp
        for line in resp.split("\n"):
            line = line.strip()
            if any(k in line for k in ["Success", "Error", "complete"]):
                print(f"  {line}")
        return success

    def eeprom_verify(self, filename):
        """Verify EEPROM against file."""
        print(f"Verifying EEPROM against {filename}...")
        resp = self._cmd(f"eeprom verify -d 24X16 -f {filename}", 120)
        success = "Success" in resp
        for line in resp.split("\n"):
            line = line.strip()
            if any(k in line for k in ["Success", "Error", "complete"]):
                print(f"  {line}")
        return success


def main():
    parser = argparse.ArgumentParser(
        description="Bus Pirate 5 EEPROM tool for Macrosilicon devices"
    )
    parser.add_argument(
        "command", choices=["write", "read", "verify", "scan"], help="Operation"
    )
    parser.add_argument("file", nargs="?", help="Filename (on BP5 storage)")
    parser.add_argument("--port", default="COM7", help="Serial port (default: COM7)")
    parser.add_argument(
        "--voltage",
        type=float,
        default=2.5,
        help="Supply voltage (default: 2.5V — use 3.3V only if chip is isolated)",
    )

    args = parser.parse_args()

    if args.command != "scan" and not args.file:
        parser.error(f"{args.command} requires a filename")

    print(f"Bus Pirate 5 on {args.port}, {args.voltage}V")
    print(f"IMPORTANT: USB cable must be UNPLUGGED from target device")
    print()

    with BusPirate5(args.port, voltage=args.voltage) as bp:
        bp.setup_i2c()

        # Verify EEPROM is visible
        resp = bp.scan()
        if "0x50" not in resp:
            print("ERROR: No EEPROM found on I2C bus")
            print("Check clip connection and that USB is unplugged")
            sys.exit(1)

        count = resp.count("0x5")
        print(f"I2C scan: {count} addresses found")
        print()

        if args.command == "scan":
            print(resp)
        elif args.command == "write":
            ok = bp.eeprom_write(args.file)
            sys.exit(0 if ok else 1)
        elif args.command == "read":
            ok = bp.eeprom_read(args.file)
            sys.exit(0 if ok else 1)
        elif args.command == "verify":
            ok = bp.eeprom_verify(args.file)
            sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
