SDCC_PATH = /c/Program Files/SDCC/bin
export PATH := $(SDCC_PATH):$(PATH)
CC = sdcc
AS = sdas8051
# --data-loc 0x0B: avoid bank 0 (0x00-0x07) to preserve ROM's registers.
CFLAGS = --model-small --data-loc 0x0B
CODE_LOC = 0xCC00

# Default target
all: eeprom_image.bin

# Assemble custom CRT0 (hook entry points at fixed offsets)
crt0_ms2109.rel: crt0_ms2109.asm
	$(AS) -lo $@ $<

# Compile C to relocatable object (when C code is used)
eeprom_fw.rel: eeprom_fw.c hw_defs.h rom_stubs.h
	$(CC) $(CFLAGS) -c -o $@ $<

# Link — assembly only
eeprom_fw.ihx: crt0_ms2109.rel
	sdld -nui -b HOME=$(CODE_LOC) -i $@ $^

# Convert to raw binary (strip base address, output only the code bytes)
eeprom_fw.bin: eeprom_fw.ihx
	sdobjcopy -I ihex -O binary $< $@

# Build complete EEPROM image (short code_length, relies on ROM fallthrough)
eeprom_image.bin: eeprom_fw.bin
	python build_eeprom.py eeprom_fw.bin $@

# Build padded EEPROM image (stock code_length, fills gap with reference bytes)
eeprom_image_padded.bin: eeprom_fw.bin
	python build_eeprom.py --pad-to-ref eeprom_fw.bin $@

# Verify checksums of original EEPROM dump
verify-original:
	python build_eeprom.py --verify ../../dumps/MS2109.BIN

clean:
	rm -f *.ihx *.lst *.rel *.rst *.sym *.map *.mem *.lk *.noi
	rm -f eeprom_fw.asm eeprom_fw.bin eeprom_image.bin eeprom_image_padded.bin

.PHONY: all clean verify-original
