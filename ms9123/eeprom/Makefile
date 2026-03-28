CC = sdcc
AS = sdas8051
# --data-loc 0x0B: avoid bank 0 (0x00-0x07) to preserve ROM's registers.
# Original Keil code never touches banks 0-3 — all vars are 0x20+.
CFLAGS = --model-small --data-loc 0x0B
CODE_LOC = 0xC830

all: eeprom_fw.bin

# Assemble custom CRT0 (hook entry points at fixed offsets)
crt0_ms9123.rel: crt0_ms9123.asm
	$(AS) -lo $@ $<

# Compile C to relocatable object
eeprom_fw.rel: eeprom_fw.c hw_defs.h rom_stubs.h
	$(CC) $(CFLAGS) -c -o $@ $<

# Link with custom CRT0
eeprom_fw.ihx: crt0_ms9123.rel eeprom_fw.rel
	$(CC) $(CFLAGS) --no-std-crt0 --code-loc $(CODE_LOC) -o $@ $^

# Convert to raw binary
eeprom_fw.bin: eeprom_fw.ihx
	objcopy -I ihex -O binary $< $@ 2>/dev/null || \
	makebin -p $< $@

# Build complete EEPROM image
eeprom_image.bin: eeprom_fw.bin
	python3 build_eeprom.py eeprom_fw.bin $@

# Verify checksums of original
verify-original:
	python3 build_eeprom.py --verify ../../dumps/MS9123.BIN

clean:
	rm -f *.ihx *.lst *.rel *.rst *.sym *.map *.mem *.lk *.noi
	rm -f eeprom_fw.asm eeprom_fw.bin eeprom_image.bin

.PHONY: all clean verify-original
