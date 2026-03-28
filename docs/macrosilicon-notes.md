# Macrosilicon Firmware Research Notes

## Overview

This document covers research into Macrosilicon USB video capture chips, specifically firmware dumps from an **MS2107** and an **MS9123**. The primary tooling is:

- [BertoldVdb/ms-tools](https://github.com/BertoldVdb/ms-tools.git) — Go library and CLI for MS2106/MS2107/MS2109/MS2130. Runtime patching, ROM dumping, I2C, GPIO, UART.
- [amnemonic/MacroSilicon](https://github.com/amnemonic/MacroSilicon.git) — MS2109 HID protocol documentation, reference EEPROM/XDATA/CODE dumps from multiple devices, and Windows Delphi tools (dumpeeprom.exe, dumpxdata.exe, writeeeprom.exe).

The MS9123 is a distinct chip from Macrosilicon but its EEPROM uses the same `0xA55A` magic and header format as the MS2109. It is a **USB-to-CVBS display adapter** ("usb extscreen") — the opposite direction from the MS2107/MS2109 capture devices. It receives video frames over USB and outputs composite video.

## Chip Family Summary

All chips in this family contain an **8051 microcontroller core** running code from internal **mask ROM**. On boot, the ROM copies additional firmware from an external **I2C EEPROM** into RAM. The EEPROM firmware is called via configurable hook points at fixed addresses in the ROM.

| Chip | Use Case | ROM ID byte (`0xF800`) | EEPROM Magic | Hook Config Offset | Hook Addresses (USB/IRQ) | EEPROM Load Routine |
|------|----------|------------------------|--------------|-------------------|--------------------------|---------------------|
| MS2106 | CVBS->USB | `0x6A` | `0x5AA5` | `[5]`/`[9]` | `0xC420` / `0xC4A0` | `0x1282` |
| MS2107 | CVBS->USB (successor to 2106) | `0xFF` | `0x0816` or `0x3264` | `[8]` (bitmask) | `0xC800` / `0xC810` | `0x6656` |
| MS2109 | HDMI->USB2.0 | `0xA7` | `0xA55A` or `0x9669` | `[4]` (bitmask) | `0xCC00` / `0xCC20` | `0x5F19` |
| MS2130 | HDMI->USB3.0 | `0x00` | N/A (runs from flash) | N/A | N/A | N/A |
| MS9123 | USB->CVBS (display adapter) | `0x00` (same as MS2130!) | `0xA55A` (same as MS2109) | `[4]` bit 5 at `0xC617` | `0xC860` (periodic) / `0xC830`,`0xC840` (init) | `0x20CE` (load) / `0x57AB` (detect+load) |

## Firmware Dumps

### MS2107.BIN

- **Source**: EEPROM dump from MS2107 device
- **File size**: 2048 bytes (0x800) -- standard EEPROM size for this chip
- **Status**: Valid

#### Header Analysis

```
Offset  Hex                                              ASCII
0000:   08 16 04 90 00 02 AF A1 03 FF 01 02 20 22 12 07  ............ "..
0010:   0E 41 46 4E 5F 43 61 70 20 76 69 64 65 6F FF FF  .AFN_Cap video..
0020:   0E 41 46 4E 5F 43 61 70 20 76 69 64 65 6F FF FF  .AFN_Cap video..
```

| Offset | Value | Meaning |
|--------|-------|---------|
| `0x00-0x01` | `0x0816` | MS2107 firmware magic (validated by `EEPROMIsLoaded()`) |
| `0x02-0x03` | `0x0490` (1168) | Firmware code length |
| `0x04-0x05` | `0x0002` | USB VID (big-endian, byte-swapped into descriptor by ROM) |
| `0x06-0x07` | `0xAFA1` | USB PID (big-endian, byte-swapped into descriptor by ROM) |
| `0x08` | `0x03` | Hook flags: bit0=USB hook enabled, bit1=IRQ hook enabled |
| `0x10-0x1F` | `0E "AFN_Cap video"` | USB product string 1 (length-prefixed ASCII, 16-byte slot) |
| `0x20-0x2F` | `0E "AFN_Cap video"` | USB product string 2 (length-prefixed ASCII, 16-byte slot) |

#### Memory Layout

```
0x0000 - 0x0001  Magic (0x0816)
0x0002 - 0x000A  Config header (checksummed)
0x000B - 0x000F  Config (NOT checksummed)
0x0010 - 0x001F  USB string descriptor 1, 16-byte slot (checksummed)
0x0020 - 0x002F  USB string descriptor 2, 16-byte slot (checksummed)
0x0030 - 0x04BF  8051 firmware code (1168 bytes, checksummed)
0x04C0 - 0x04C1  Header checksum (uint16 BE)
0x04C2 - 0x04C3  Code checksum (uint16 BE)
0x04C4 - 0x0601  More code/data (beyond checksum-covered region)
0x0602 - 0x07FF  Free/erased (0xFF, 510 bytes)
```

#### Checksum Algorithm

The EEPROM uses two uint16 big-endian checksums stored immediately after the code region (at offset `0x30 + code_length`). The algorithm is a simple byte sum, matching the MS213x `csum.go` pattern with a slightly different skip window. Note: the MS9123 uses a different (simpler) header formula — see the MS9123 section below.

```
code_length = uint16_be(data[0x02:0x04])
end         = 0x30 + code_length

header_sum  = sum(data[0x02:0x0B]) + sum(data[0x10:0x30])   # skip 0x0B-0x0F
code_sum    = sum(data[0x30:end])

stored at data[end:end+2]   = uint16_be(header_sum)
stored at data[end+2:end+4] = uint16_be(code_sum)
```

Bytes `0x0B-0x0F` are excluded from the header checksum. Their values (`0x02 0x20 0x22 0x12 0x07`) appear to be USB descriptor pointers or interface configuration.

The USB string descriptor slots at `0x10` and `0x20` ARE included in the header checksum. Each slot is 16 bytes: 1 length byte + up to 15 ASCII chars, padded with `0xFF`. To change enumeration text, edit the strings and recalculate only the header checksum.

#### Live Verification (2026-03-28)

- EEPROM readback over I2C matches `MS2107.BIN` byte-for-byte
- I2C bus scan: EEPROM at addresses `0x50-0x57` (24C16-style, 8x256B = 2KB)
- Chip ID byte at `RAM:0xF800` = `0xFF` (confirms MS2107)
- Full 64KB mask ROM dumped to `MS2107_ROM.BIN`
- USB VID:PID = `0x0002:0xAFA1`, serial = `20200909`
- Successfully changed product string to "Claude Rules" via EEPROM write (verified on Windows)

#### ROM Analysis: USB Descriptor Construction

The ROM builds the USB device descriptor at **RAM 0xC535** from a template with default VID `0x534D` ("MS"), PID `0x0021`. During boot, the routine at **ROM 0x1F17** copies EEPROM-configured values over the defaults:

```
ROM 0x1F17:  MOV DPTR,#0xC7D4    ; userconfig+4 = EEPROM[0x04] (VID hi)
             MOVX A,@DPTR
             MOV R7,A
             CJNE A,#0xFF,...     ; if 0xFFFF, keep ROM default
             ...
             MOV DPTR,#0xC53D    ; USB descriptor idVendor offset
             MOVX @DPTR,A        ; write VID_lo (byte-swapped for USB LE)
             INC DPTR
             MOV A,R7
             MOVX @DPTR,A        ; write VID_hi
             ; same pattern for PID at EEPROM[0x06] -> descriptor 0xC53F
```

| RAM Address | USB Descriptor Field | Source |
|-------------|---------------------|--------|
| `0xC535` | Device descriptor start (`bLength=0x12, bDescType=0x01`) | ROM template |
| `0xC53D-0xC53E` | `idVendor` (little-endian) | EEPROM `0x04-0x05` (byte-swapped) |
| `0xC53F-0xC540` | `idProduct` (little-endian) | EEPROM `0x06-0x07` (byte-swapped) |

If EEPROM VID or PID is `0xFFFF`, the ROM default is kept. This means setting EEPROM `0x04-0x07` to `FF FF FF FF` gives the stock `534D:0021` identity.

#### Validation Checks Performed

- Magic bytes `0x0816` match MS2107 -- PASS
- Firmware length field (1168) < actual code end (0x0602) -- plausible
- No duplicate 256-byte blocks (rules out EEPROM address wrapping) -- PASS
- No stuck bits (healthy mix of byte values, 73% non-trivial data) -- PASS
- USB descriptor strings are intact and readable -- PASS
- 8051 instruction distribution looks normal (30 LJMP, 44 LCALL, 41 RET, 87 MOV DPTR) -- PASS
- Entropy is 5.6-6.0 bits/byte in code blocks, 0.0 in erased blocks -- PASS

### MS9123

The MS9123 is a **USB-to-CVBS display adapter** (USB display output, not capture). Product string "usb extscreen". Despite the opposite data direction from the MS2107, it shares significant ROM code (same 8051 core family).

- **VID:PID**: `0x534D:0x6021` (proper Macrosilicon VID, unlike MS2107's `0x0002`)
- **iManufacturer**: "USB Display "
- **iProduct**: "usb extscreen"
- **iSerialNumber**: 2019BA7160B0
- **Chip ID at XDATA 0xF800**: `0x00` (same as MS2130 — ms-tools would misidentify this chip)

#### USB Interfaces

| Interface | Class | Function |
|-----------|-------|----------|
| MI_00 | HID (0x03) | Vendor-defined control (0xFF00:0x0001) |
| MI_03 | Vendor | "msusb video" (custom class, not UVC) |

Notable differences from MS2107: HID is at MI_00 (not MI_04), no audio interface, video uses a custom class (not UVC), only 2 interfaces vs 5.

#### EEPROM (MS9123.BIN)

- **File size**: 2048 bytes (0x800)
- **Magic**: `0xA55A` (same as MS2109)
- **FW length**: `0x019D` (413 bytes)
- **Hook config `[4]`**: `0x2C` (bits 2,3,5 set)
- **Last non-FF byte**: `0x01D0`
- **EEPROM verified**: HID readback (`MS9123_HID.BIN`) matches original dump byte-for-byte
- **No USB strings in EEPROM** — strings are in CODE ROM, not configurable via EEPROM
- **No VID/PID in EEPROM** — uses ROM defaults

#### EEPROM Checksum

The MS9123 uses the same dual-checksum structure as the MS2107, but with a **simpler header formula** (no skip window):

```
code_length = uint16_be(data[0x02:0x04])
end         = 0x30 + code_length

header_sum  = sum(data[0x02:0x30])          # ALL bytes, no skip
code_sum    = sum(data[0x30:end])

stored at data[end:end+2]   = uint16_be(header_sum)
stored at data[end+2:end+4] = uint16_be(code_sum)
```

Both are uint16 big-endian, stored immediately after the code region. Verified against the original MS9123.BIN:
- Code sum `sum(0x30:0x1CD)` = `0xCB24` ✓
- Header sum `sum(0x02:0x30)` = `0x26DC` ✓

**Key difference from MS2107**: the MS2107 skips bytes `0x0B-0x0F` in the header sum. The MS9123 includes all bytes from `0x02` to `0x2F`. This was confirmed by brute-forcing skip patterns against the known-good checksum — only the no-skip formula produces a unique match (other "matches" were trivially due to zero-valued bytes).

Note: bytes `0x10-0x2F` are all `0xFF` in this EEPROM (no USB string slots), so any single-byte skip in that range is indistinguishable. The no-skip conclusion is based on the header bytes `0x02-0x0F` where the values are non-trivial.

#### CODE Space Dump via EEPROM Init Hook

The EEPROM init hook at offset `0x30` (XDATA `0xC830`) fires **once during boot** — it is NOT called periodically. Confirmed by installing a mailbox-based handler at the hook address and polling from the host: mailbox never cleared.

However, CODE space can be dumped by modifying the EEPROM to include a MOVC copy routine that runs during init:

1. Extend the EEPROM code length field (`data[0x02:0x04]`) to accommodate the dump code
2. Redirect the hook LJMP at offset `0x30` to the dump code
3. Dump code copies CODE bytes via MOVC to a writable XDATA region
4. Dump code then LJMPs to the original init handler (`0xC843`)
5. Recalculate both checksums
6. Power cycle — init hook fires, dump runs, device enumerates normally
7. Read dumped bytes from XDATA via HID `0xB5`

**Key findings:**
- XDATA `0xC000-0xC0FF` is **zeroed by the firmware** during init (after the hook runs). Do not use as dump destination.
- XDATA `0xD300` region **survives init** — suitable for dump output.
- Confirmed CODE[0x0000] = `02 40 EB` (`LJMP 0x40EB`) — valid 8051 reset vector. The CODE space is distinct from XDATA.
- The code length field at `data[0x02:0x04]` controls how many bytes the bootloader loads. Extending it works — the bootloader loads the additional bytes and the checksum covers the full range.

#### MS9123 Interrupt Vectors (from CODE dump)

```
CODE 0x0000: 02 40 EB   LJMP 0x40EB   ; Reset
CODE 0x0003: 02 59 71   LJMP 0x5971   ; External Interrupt 0 (likely USB)
CODE 0x000B: 02 65 05   LJMP 0x6505   ; Timer 0
CODE 0x0013: 02 45 D8   LJMP 0x45D8   ; External Interrupt 1
```

#### MS9123 Hook Architecture (Discovered)

The MS9123 has **three** EEPROM entry points at fixed offsets, loaded to XDATA 0xC800+offset:

| EEPROM Offset | XDATA Address | Type | Original Code | Called When |
|---------------|---------------|------|---------------|-------------|
| `0x30` | `0xC830` | Init hook | `LJMP 0xC843` | Once at boot (EEPROM load) |
| `0x40` | `0xC840` | Init hook 2 | `LJMP 0xC943` | Once at boot |
| `0x60` | `0xC860` | **Periodic USB hook** | `LJMP 0xC903` | Every USB interrupt |

The periodic hook was found by dumping the USB IRQ handler in CODE ROM:

```
CODE 0x5971: PUSH all registers
CODE 0x598E: LCALL 0x4D1C          ; main USB handler
CODE 0x5991: POP all, RETI

CODE 0x4D1C: ... setup ...
CODE 0x4D30: LCALL 0x7360          ; returns hook-enable flag in ACC
CODE 0x4D34: JNB ACC.5, skip       ; check bit 5
CODE 0x4D37: LCALL 0xC860          ; <-- PERIODIC EEPROM HOOK
```

The hook at `0xC860` fires on every USB interrupt when ACC.5 is set. The gatekeeper function at CODE `0x7360` is trivial:

```
7360: MOV DPTR,#0xC617    ; UserConfig + 4
7363: MOVX A,@DPTR        ; read hook-enable byte
7364: MOV R7,A
7365: RET                  ; caller checks ACC.5
```

**UserConfig is at XDATA `0xC613`** (offset `0x613` from UserRAM base `0xC000`):

| Offset | XDATA Address | Live Value | Meaning |
|--------|---------------|------------|---------|
| `[0:2]` | `0xC613` | `0x26DC` | Header checksum (stored by bootloader) |
| `[2:4]` | `0xC615` | `0xCB24` | Code checksum (stored by bootloader) |
| `[4]` | `0xC617` | `0x2D` | Hook config (from EEPROM[4]=`0x2C`, bit 0 set by bootloader) |

The hook config follows the MS2109 pattern: offset `[4]` from UserConfig, with bit 5 controlling the periodic USB hook. EEPROM header byte `[4]` = `0x2C` (bits 2,3,5 set), and the bootloader copies it to `0xC617` with bit 0 additionally set (possibly a "loaded OK" flag).

**Why extending EEPROM code length broke the periodic hook:** The bootloader validates checksums at fixed offset `0x30 + code_length` from the EEPROM. When we extended code_length from `0x019D` to `0x01F0`, the bootloader looked for checksums at `0x0220` (which had our new checksums), but it still validated against the original length's position (`0x01CD`). The mismatch caused the bootloader to NOT set the hook-enable bit at `0xC617`, silently disabling the periodic hook.

**This is the entry point for interactive access.** By patching the `LJMP` at XDATA `0xC860` in RAM (via HID `0xB6`), arbitrary code runs on every USB interrupt without any EEPROM modification.

#### Interactive MOVC Access via Periodic Hook

A mailbox-based MOVC handler installed at `EEPROM[0x1D0]` (XDATA `0xC9D0`) and called via the periodic hook:

1. Redirect `EEPROM[0x60]` to `02 C9 D0` (`LJMP 0xC9D0`)
2. Handler checks mailbox at XDATA `0xD3F0`:
   - `[0]` = byte count (0 = idle, non-zero = trigger)
   - `[1:2]` = CODE source address (big-endian)
   - `[3:4]` = XDATA destination address (big-endian)
3. If count > 0: copies N bytes via MOVC from CODE to XDATA, clears count
4. Falls through to `LJMP 0xC903` (original periodic handler)

Host-side protocol:
1. Write dst, src to mailbox via `0xB6` commands
2. Write count last (triggers execution)
3. Poll mailbox[0] via `0xB5` until it reads 0 (completion)
4. Read result bytes from XDATA destination via `0xB5`

**No power cycling required** — commands execute within one USB interrupt cycle (~1ms).

Much smaller firmware payload than the MS2107 (~420 bytes of 8051 code overlay vs ~1168 bytes). The EEPROM contains almost entirely code, not configuration.

#### HID Protocol

All four MS2109 HID commands work identically on the MS9123: `0xE5` (read EEPROM), `0xE6` (write EEPROM), `0xB5` (read XDATA), `0xB6` (write XDATA). Same 9-byte feature report format.

**Warning**: Command `0xE6` is a live write with no confirmation. During testing, a probe accidentally overwrote EEPROM byte 0 (the magic byte). Always use `0xE5` (read) for probing.

#### XDATA Dump (MS9123_ROM.BIN)

Full 64KB XDATA space dumped via HID command `0xB5`. Note: this is the **XDATA address space**, not CODE space (MOVC). However, the upper 32KB of XDATA maps the same mask ROM as CODE space.

#### Cross-Chip ROM Comparison (MS9123 XDATA vs MS2107 CODE)

| Region | Match | Interpretation |
|--------|-------|---------------|
| `0x0000-0x7FFF` | 4% | RAM/registers (different hardware state, not ROM) |
| `0x8000-0x8FFF` | **100%** | Shared boot ROM / common library |
| `0x9000-0xBFFF` | **80%** | Core firmware (same family, minor variants) |
| `0xC000-0xCFFF` | 5% | Chip-specific peripheral code |
| `0xD000-0xDFFF` | 0% | Chip-specific |
| `0xE000-0xEFFF` | 20% | Partially shared |
| `0xF500-0xF5FF` | **90%** | Shared utility code |
| `0xF900-0xFEFF` | 64% | USB/boot code with variants |
| `0xFF00-0xFFFF` | **100%** | Interrupt vectors / boot vectors |

**Key conclusion**: The 100% match at `0x8000-0x8FFF` and `0xFF00-0xFFFF` confirms the MS9123 and MS2107 share the same 8051 core silicon family. The ROM is mapped into XDATA in the upper 32KB. USB descriptor strings were not found in XDATA — they exist only in CODE ROM.

## ms-tools Architecture

### Repository

- **Repo**: https://github.com/BertoldVdb/ms-tools.git
- **Language**: Go (module requires Go 1.16+, tested with go1.22.2)
- **Key dependency**: `go-hid` for USB HID communication

### Code Structure

```
ms-tools/
  cli/             # CLI application (kong-based)
    main.go        # Entry point, device open, HAL init
    memio.go       # read/write/write-file/list-regions commands
    dumprom.go     # dump-rom: uploads custom 8051 code to dump CODE space
    i2c.go         # i2c-scan, i2c-txfr commands
    gpio.go        # gpio-set, gpio-get commands
    uart.go        # uart-tx, flir-tx commands
    hexdump.go     # Hex dump formatting
    raw.go         # Raw HID command
    hid_pure.go    # Pure Go HID backend
    hid_cgo.go     # CGo HID backend
    asm/
      dumprom.asm   # 8051 assembly for ROM dumping
      dumprom.bin   # Assembled binary
  mshal/           # Hardware Abstraction Layer library
    hal.go         # Device detection, init, memory regions
    hal_patch_install.go  # Runtime patch installation (callgate + trampolines)
    hal_patch_call.go     # PatchExecFunc: RPC over HID feature reports
    hal_patch_gpio.go     # GPIO read/write via patch
    hal_patch_i2c.go      # I2C bus master via ROM function calls
    hal_patch_uart.go     # Bit-banged UART TX
    hal_patch_eeprom.go   # Fast EEPROM access via I2C patch
    hal_flash.go          # SPI flash access (MS2130)
    errors.go
    asm/
      hook.asm            # Callgate dispatcher (8051 asm)
      hook_2106.bin       # Assembled for MS2106
      hook_2109.bin       # Assembled for MS2109 (also used by MS2107)
      gpio.asm / .bin     # GPIO control blob
      code.asm / .bin     # MOVC instruction (CODE space read)
      i2cRead2107.asm/.bin  # I2C read for MS2107
      i2cRead2109.asm/.bin  # I2C read for MS2109
      uart_tx.asm / .bin  # Bit-banged UART TX
  gohid/           # Cross-platform HID abstraction
  board/ms2106/    # PCB schematics and gerbers for MS2106 dev board
  files/           # Reference firmware files
```

## Runtime Patching Mechanism (Detail)

This is the most interesting part of ms-tools. The stock ROM exposes a basic HID interface that allows reading/writing XDATA (RAM) and EEPROM. ms-tools extends this into a **general-purpose RPC mechanism** by patching the running firmware in RAM.

### How It Works

#### Step 1: Hook Discovery

The ROM loads EEPROM firmware into RAM and calls it via two hooks:
- **USB hook**: called from USB interrupt handler (for MS2107: address `0xC810`)
- **Normal hook**: called from main loop (for MS2107: address `0xC800`)

Enable flags are in the USERCONFIG memory region (mapped from EEPROM header).

#### Step 2: Trampoline Installation

ms-tools replaces the first 3 bytes at each hook address with an `LJMP` to a trampoline:

```
Original:        LJMP somewhere     ; or LCALL, MOV DPTR
Patched:         LJMP trampoline

trampoline:
  PUSH R7
  MOV  R0, #0xEE          ; 0xEE=IRQ context, 0xEF=normal context
  LCALL callgate           ; run the callgate
  POP  R7
  <original 3 bytes>       ; execute the code we overwrote
  LJMP original_addr+3     ; continue original flow
```

#### Step 3: Callgate (hook.asm)

The callgate is the core dispatcher. On every hook invocation it:

1. Reads `HID[0]` from the HID feature report buffer in RAM
2. Compares against R0 (`0xEE` or `0xEF`) -- if no match, returns immediately (no-op)
3. If matched, it's an RPC request:
   - Extracts target address from `HID[1:2]`
   - Loads arguments into R3-R7, DPTR, A from `HID[3:8]`
   - Disables interrupts (`CLR EA`)
   - Calls the target via `PUSH HID+2; PUSH HID+1; RET` (classic 8051 computed call)
   - Writes return values (A, R2-R7, carry) back to HID buffer
   - Sets `HID[0] = 0xFE/0xFF` as completion flag
   - Re-enables interrupts (`SETB EA`)

#### Step 4: Host-Side RPC (`PatchExecFunc`)

From the Go side, `PatchExecFunc` sends a HID feature report with the target address and arguments, then polls until `HID[0]` has bit pattern `0xFE` (response ready). The 8051 function executes in the chip's own context with full access to all hardware.

### Installed Code Blobs (MS2107)

Five blobs are installed in sequence (`installBlobs2107`):

| # | Source | Purpose | Details |
|---|--------|---------|---------|
| 0 | `hook_2109.bin` | Callgate | HID report dispatcher, enables RPC |
| 1 | `gpio.bin` | GPIO control | Reads/writes P2 (state) and P3 (direction) SFR registers |
| 2 | `code.bin` | CODE read | `MOVC A,@A+DPTR; RET` -- reads 8051 program memory |
| 3 | `i2cRead2107.bin` | I2C read | Jumps into ROM I2C read at `0x5934` |
| 4 | `uart_tx.bin` | UART TX | Bit-banged serial on P2.4 with configurable baud |

### What This Enables

| Capability | How | Stock ROM? |
|------------|-----|------------|
| Read/write XDATA (RAM) | Direct HID commands | Yes |
| Read/write EEPROM (slow) | Direct HID commands | Yes |
| Read/write EEPROM (fast) | I2C via patch blob #3 calling ROM routines | No |
| GPIO control | Patch blob #1 manipulating P2/P3 SFRs | No |
| Read CODE space (ROM dump) | Patch blob #2 executing MOVC | No |
| I2C bus master (arbitrary) | Patch calling ROM I2C primitives (start=`0x68BD`, stop=`0x6B5B`, write=`0x5323`) | No |
| UART transmit | Patch blob #4 bit-banging | No |
| Call any ROM function | Callgate with arbitrary address | No |

### Key ROM Addresses (MS2107)

| Address | Function |
|---------|----------|
| `0x6656` | EEPROM reload |
| `0x68BD` | I2C start condition |
| `0x6B5B` | I2C stop condition |
| `0x5323` | I2C write byte |
| `0x5934` | I2C read byte |
| `0x54AE` | USB IRQ original handler (patched around when no user firmware) |

### Key ROM Addresses (MS9123)

Discovered by disassembling the CODE dump from the Windows-side MOVC session:

| Address | Function | How Found |
|---------|----------|-----------|
| `0x20CE` | EEPROM code loader (reads I2C, copies to XDATA 0xC830+, validates checksums) | Traced from boot sequence |
| `0x57AB` | EEPROM detect+load (checks magic A55A/9669, then calls 0x20CE) | Caller of 0x6683 |
| `0x5EA3` | Read EEPROM magic + validate (reads 2 bytes via I2C to XDATA 0xC41B, checks A5/5A or 96/69) | Pattern search for A5 comparison |
| `0x6683` | EEPROM presence check (calls 0x5EA3 twice, sets XDATA[0xC41A] = 1 if found) | Caller of 0x5EA3 |
| `0x53A9` | I2C EEPROM read (R2:R1=XDATA dest, R5=byte count, R7:R6=EEPROM offset) | Traced from 0x5EA3 |
| `0x6AB8` | I2C START condition | Pattern search for SETB/CLR on P3 bits |
| `0x46BC` | I2C send byte | Called from compound I2C function 0x464B |
| `0x464B` | I2C EEPROM read compound (start + send addr + repeated start + read) | Pattern search for 0xA0 device address |
| `0x65EC` | Clear EEPROM user config (zeros 0xC805, 0xC612; FFs 0xC806-0xC809, 0xC810, 0xC820) | Pattern search for 0xC8xx writes |
| `0x7360` | Hook enable check (reads XDATA[0xC617], returns in ACC; bit 5 = periodic hook) | Traced from USB handler |
| `0x4D1C` | USB handler main (called from ISR, dispatches to endpoint handlers, calls periodic hook) | Traced from interrupt vector 0x5971 |
| `0x5971` | USB interrupt service routine (saves/restores all regs, calls 0x4D1C) | Interrupt vector at CODE 0x0003 |

#### MS9123 XDATA Memory Map (key addresses)

| Address | Purpose |
|---------|---------|
| `0xC41A` | EEPROM present flag (1 = loaded, 0 = not found) |
| `0xC41B-0xC41C` | EEPROM magic bytes (A5 5A or 96 69, read from I2C) |
| `0xC588-0xC589` | EEPROM code load destination (stores 0xC830) |
| `0xC591-0xC593` | I2C transaction parameters (device addr, offset bytes) |
| `0xC599` | Device type / chip variant |
| `0xC612` | Unknown config flag |
| `0xC613-0xC614` | Stored header checksum (from EEPROM validation) |
| `0xC615-0xC616` | Stored code checksum (from EEPROM validation) |
| `0xC617` | Hook config byte (bit 5 = periodic USB hook enable) |
| `0xC800-0xC82F` | EEPROM header (loaded from EEPROM 0x00-0x2F) |
| `0xC830+` | EEPROM code (loaded from EEPROM 0x30+, up to code_length bytes) |
| `0xC860` | **Periodic USB hook entry** (EEPROM offset 0x60) |
| `0xCE00` | Safe RAM for runtime code patches (used for interactive MOVC handler) |
| `0xD000-0xD7FF` | Safe RAM for dump output (survives init) |
| `0xD3F0` | Mailbox for interactive MOVC handler |

## Connecting from WSL2

The MS2107 presents as a USB HID device (VID `0x534D` or `0x345F`). WSL2 requires **usbipd-win** to forward USB devices from Windows:

1. Install: `winget install usbipd` (on Windows)
2. Install USB/IP client in WSL2: `sudo apt install linux-tools-generic hwdata`
3. List devices: `usbipd.exe list`
4. Bind and attach: `usbipd.exe bind --busid <ID>` then `usbipd.exe attach --wsl --busid <ID>`
5. Device should appear as `/dev/hidraw*`

### Building ms-tools

```bash
cd ms-tools/cli
go build -o ms-tools .
```

### Useful Commands

```bash
# Read EEPROM (compare against dump)
./ms-tools --no-firmware --log-level 2 read EEPROM 0 --filename=/tmp/eeprom_readback.bin

# Dump ROM code
./ms-tools --no-patch dump-rom /tmp/rom_dump.bin

# List memory regions
./ms-tools list-regions

# Scan I2C bus
./ms-tools i2c-scan

# Read specific RAM address
./ms-tools read RAM 0xF800 1   # Should return chip ID byte
```

## Reference Dumps (amnemonic/MacroSilicon)

All reference dumps in this repo are MS2109 HDMI capture devices:

| Device | EEPROM Size | Magic | FW Length | Also Has |
|--------|-------------|-------|-----------|----------|
| JZY-HDMI-V1.4-20200605 | 2048 | `0xA55A` | 533 | CODE (64KB), XDATA (64KB) |
| L-331-R1.2 2020.09.04 | 2048 | `0xA55A` | 1754 | CODE (64KB), XDATA (64KB) |
| OZC4 2021-03-1 | 4096 | `0x9669` | 2341 | -- |
| SFX_HDMI_VC_V1.7 (105) | 1088 | `0xA55A` | 1023 | -- |
| SFX_HDMI_VC_V1.7 (108) | 1792 | `0xA55A` | 1724 | -- |
| SFX_VCMS_0101_V2 (24c16) | 2048 | `0xA55A` | 1735 | -- |
| noname_1 (24c08, bad capture) | 1024 | `0xA55A` | 713 | -- |

The CODE dumps (JZY and L-331) are full 64KB 8051 ROM dumps -- useful for cross-referencing ROM function addresses.

### Windows Delphi Tools

- `dumpeeprom.exe` — Reads EEPROM via HID command `0xE5`
- `dumpxdata.exe` — Reads XDATA via HID command `0xB5`
- `writeeeprom.exe` — Writes EEPROM via HID command `0xE6`

These talk directly to the Windows HID driver (no usbipd needed) and could serve as a fallback.

### HID Protocol (MS2109)

| Command | Direction | Description |
|---------|-----------|-------------|
| `0xE5` | Set+Get | Read EEPROM (address in bytes 2-3, 5 bytes returned) |
| `0xE6` | Set | Write EEPROM (address in bytes 2-3, 2 bytes data) |
| `0xB5` | Set+Get | Read XDATA (address in bytes 2-3, 1 byte returned) |
| `0xB6` | Set | Write XDATA (address in bytes 2-3, 1 byte data) |

All use 9-byte HID feature reports (report ID 0 + 8 bytes).

## EEPROM Firmware Reconstruction (MS2107)

The MS2107 EEPROM firmware has been fully reconstructed in C from the disassembly. The source is at `ms2107/eeprom/eeprom_fw.c` and compiles with SDCC.

### What the firmware does

The EEPROM firmware is a **CVBS signal lock manager**. It's called via two hooks from the ROM:

**Normal hook (R7 = command ID):**
| Cmd | Handler | Purpose |
|-----|---------|---------|
| 0 | `cmd_setup_video_regs` | Initialize video decoder timing (NTSC/PAL constants in C6xx regs) |
| 1 | `cmd_video_mode_config` | Set USB endpoint config, horizontal scaling |
| 2 | `cmd_video_process` | Main loop: signal detection state machine, lock/unlock transitions |
| 5 | `cmd_video_reset` | Reset video pipeline, configure scaler |
| 7/13 | `cmd_video_output_config` | Set F8xx output registers for active/inactive output |
| 10 | (inline) | Enable video input feature (FEB9=1) |

**IRQ hook:** Checks USB interrupt flags, manages interrupt command registers, calls ROM video display function.

### Toolchain

```bash
cd macrosilicon/ms2107/eeprom
make                    # Compile + build EEPROM image
make eeprom_fw.bin      # Just the code binary
make eeprom_image.bin   # Full 2048-byte EEPROM image with header + checksums
```

- **Compiler**: SDCC 4.2.0, `--model-small --code-loc 0xC800`
- **ROM calls**: Inline asm `LCALL` to fixed ROM addresses (0x44BA, 0x5659, 0x5C29, 0x6087, 0x6F52)
- **Image builder**: `build_eeprom.py` adds header, USB strings, VID/PID, and checksums

### Output sizes

| | Original | Reconstructed |
|--|----------|---------------|
| Code | 1168 bytes | 1300 bytes (+11%) |
| EEPROM image | 2048 bytes | 2048 bytes |
| Checksums | Valid | Valid |

The 11% size increase is expected — SDCC makes different optimization choices than the original compiler (likely Keil C51). The code is **functionally equivalent**, not byte-identical.

### 20 functions reconstructed

All 14 functions identified by radare2 plus the entry points, command dispatch, and handlers are covered. Key functions:
- `signal_detect` (147 bytes) — monitors video line count, manages signal lock
- `signal_monitor` — triggers VSync measurement, retries up to 3 times
- `video_output_init` — full output pipeline setup on signal lock
- `check_signal_change` — detects standard change, triggers reinit
- `divide_24_8` — compiler runtime: 24-bit by 8-bit division

### Ghidra headless analysis

The full 64KB ROM was analyzed headlessly via Ghidra 12.0.4:
- 399 functions discovered (294 in actual code region)
- 14.8K lines annotated disassembly at `ms2107/rom/disasm.asm`
- 11.3K lines decompiled C at `ms2107/rom/decompiled.c`
- Known ROM functions (I2C, USB, EEPROM) identified and named

## Lessons Learned

- **Windows caches USB device info on first plug.** `FriendlyName` is set once and never updated even if the device reports a different `iProduct` string. To see changes, use `pnputil /remove-device` on all device nodes (with device unplugged), then replug. See `MS2107_research_report.md` for full details.
- **The EEPROM checksum and string format are correct.** Changing product strings and recalculating the header checksum works. The device boots and enumerates with the new strings.
- **usbipd forced-share state persists across reboots** and replaces all Windows drivers with a stub, making the device appear dead. Fix with `usbipd unbind`. This can masquerade as a bricked device.
- **Command 0xE6 is a live EEPROM write with no confirmation.** Never use it for probing — the Windows agent accidentally overwrote the MS9123 magic byte this way. Always use 0xE5 (read) first.
- **EEPROM bytes 0x0B-0x0F are NOT unused.** They're excluded from the header checksum but the ROM needs them for USB descriptor construction. Setting them to 0xFF caused the device to enumerate as VID:PID 0x0000:0x0002 (descriptor request failed). The EEPROM image builder must use a reference dump to preserve these bytes.
- **RAM-patching the periodic hook is safer than EEPROM modification.** Write the handler to free XDATA RAM via `0xB6`, then patch the LJMP at the hook address in RAM. Changes are volatile (lost on power cycle), avoiding any risk of bricking. The EEPROM stays unmodified.
- **Extending the EEPROM code length breaks the periodic hook on MS9123.** The hook-enable function at ROM 0x7360 likely validates the code length or checksum at the original location. Keeping the EEPROM unmodified and patching RAM instead avoids this issue entirely.
- **XDATA 0xC000-0xC0FF is zeroed during firmware init** — don't use it as a dump destination for boot-time MOVC. XDATA 0xD000+ survives init and works for both boot-time and interactive dumps.

## Files

| File | Size | Description |
|------|------|-------------|
| `MS2107.BIN` | 2,048 B | MS2107 EEPROM dump (original, known-good) |
| `MS2107_CLAUDE.BIN` | 2,048 B | MS2107 EEPROM with product string changed to "Claude Rules" |
| `MS2107_ROM.BIN` | 65,536 B | MS2107 full mask ROM (CODE space via MOVC/dump-rom) |
| `MS9123.BIN` | 2,048 B | MS9123 EEPROM dump (original, verified via HID readback) |
| `MS9123_HID.BIN` | 2,048 B | MS9123 EEPROM readback via HID (matches MS9123.BIN) |
| `MS9123_ROM.BIN` | 65,536 B | MS9123 full XDATA dump (via HID 0xB5, NOT CODE space) |
| `MS9123_CODE.bin` | 65,536 B | MS9123 full CODE dump (lower 32KB via MOVC, upper 32KB from XDATA mirror) |
| `MS9123_CODE_lower32k.bin` | 32,768 B | MS9123 lower CODE space only (0x0000-0x7FFF via MOVC) |
| `MS2107_research_report.md` | -- | Windows-side investigation report (caching, usbipd, MS9123 analysis) |

## Next Steps

- [x] Install usbipd-win and attach the MS2107 to WSL2
- [x] Build ms-tools CLI and verify connectivity
- [x] Read back EEPROM live and compare against MS2107.BIN dump
- [x] Dump the mask ROM via `dump-rom` (CODE space)
- [x] Reverse-engineer VID/PID copy routine from ROM dump
- [x] Successfully modify USB product string via EEPROM
- [x] Verify MS9123 EEPROM via HID readback from Windows
- [x] Dump MS9123 XDATA space (64KB) from Windows
- [x] Cross-chip ROM comparison (MS9123 shares core silicon with MS2107)
- [x] Dump MS9123 CODE space — **done!** Full 64KB dumped from Windows via interactive MOVC
- [x] Reverse-engineer MS9123 EEPROM checksum algorithm (no-skip header sum, differs from MS2107)
- [x] Discover MS9123 hook architecture: init hooks at 0xC830/0xC840, periodic USB hook at 0xC860
- [x] Achieve interactive code execution via RAM-patched periodic hook (no EEPROM changes needed)
- [ ] Map MS9123 EEPROM header fields (different layout from MS2107 — code-only, no USB config)
- [ ] Investigate ms-tools compatibility with MS9123 (chip ID 0x00 = misidentified as MS2130)
- [ ] Cross-reference ROM addresses using the CODE dumps from JZY/L-331 devices (MS2109)
- [ ] Map remaining MS2107 EEPROM header fields (0x08-0x0F) by tracing ROM code
- [x] Identify function at CODE 0x7360 — reads XDATA[0xC617] (UserConfig+4), caller checks ACC.5
- [x] Map MS9123 UserConfig — at XDATA 0xC613 (checksums at [0:4], hook config at [4])
- [x] Find MS9123 EEPROM reload routine — 0x20CE (load), 0x57AB (detect+load)
- [x] Map MS9123 key ROM functions: I2C primitives, USB handler, EEPROM validator, hook gatekeeper
- [x] Map MS9123 XDATA memory layout (UserConfig at 0xC613, magic at 0xC41B, hook enable at 0xC617)
- [ ] Full disassembly/annotation of MS9123 CODE dump
- [x] Full C reconstruction of MS2107 EEPROM firmware (20 functions, compiles with SDCC)
- [x] Ghidra headless analysis of MS2107 ROM (399 functions, 11K lines decompiled C)
- [x] EEPROM image builder with checksum validation (build_eeprom.py)
- [ ] Test reconstructed firmware on live device
- [ ] Reconstruct MS9123 EEPROM firmware in C
