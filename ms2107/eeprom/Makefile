CC = sdcc
AS = sdas8051
# --data-loc 0x0B: match original Keil allocation — avoid bank 0 (0x00-0x07)
# Original firmware starts scratch at 0x0B, 0x0F, 0x10, 0x12
CFLAGS = --model-small --data-loc 0x0B
CODE_LOC = 0xC800

# Optional: custom USB strings (uncomment to override ROM defaults)
# Max 8 chars for serial, ~15 for manufacturer
#CUSTOM_STRINGS = -DCUSTOM_USB_SERIAL='"CUSTOM01"' -DCUSTOM_USB_MANUFACTURER='"MyCompany"'
CUSTOM_STRINGS =

all: eeprom_fw.bin

# Assemble custom CRT0
crt0_ms2107.rel: crt0_ms2107.asm
	$(AS) -lo $@ $<

# Compile C to relocatable object
eeprom_fw.rel: eeprom_fw.c hw_defs.h rom_stubs.h
	$(CC) $(CFLAGS) $(CUSTOM_STRINGS) -c -o $@ $<

# Link with custom CRT0
eeprom_fw.ihx: crt0_ms2107.rel eeprom_fw.rel
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
	python3 build_eeprom.py --verify ../../dumps/MS2107.BIN dummy.bin

clean:
	rm -f *.ihx *.lst *.rel *.rst *.sym *.map *.mem *.lk *.noi
	rm -f eeprom_fw.asm eeprom_fw.bin eeprom_image.bin

.PHONY: all clean verify-original
