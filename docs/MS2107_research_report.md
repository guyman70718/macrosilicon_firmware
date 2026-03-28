# MS2107 USB Video Capture Device — Research Report

**Date:** 2026-03-28
**Device:** Macrosilicon MS2107 USB Video Capture
**VID:PID:** 0x0002:0xAFA1 (non-standard VID)
**Serial:** 20200909
**Firmware revision:** 0x2101

---

## 1. Device Overview

The MS2107 is a USB composite device with 5 interfaces:

| Interface | Class        | Function                              |
|-----------|-------------|---------------------------------------|
| MI_00     | UVC (0x0E)  | Video capture (Camera)                |
| MI_02     | UAC (0x01)  | Audio capture (USB Audio Device)      |
| MI_04     | HID (0x03)  | Vendor-defined control (usage page 0xFF00, usage 0x0001) |

The Windows composite driver (`usbccgp`) splits these into separate child devices.
The HID interface (MI_04) is the control channel used for EEPROM read/write and register access.

### USB Descriptor Strings
- **iManufacturer:** MACROSILICON
- **iProduct:** Configurable via EEPROM (was "AFN_Cap video", changed to "Claude Rules")
- **iSerialNumber:** 20200909

---

## 2. EEPROM Layout

The MS2107 has a 2048-byte EEPROM (likely I2C). Key regions discovered:

### Header (0x0000–0x000D)
```
0000: 08 16 04 90 00 02 af a1 03 ff 01 02 20 22 12 07
```
- **0x0004–0x0005:** VID (0x0002) — little-endian byte order in descriptor, stored big-endian in EEPROM
- **0x0006–0x0007:** PID (0xAFA1)
- **0x0008:** 0x03 — Hook enable flags (bit0=USB hook, bit1=IRQ hook). Confirmed from ms-tools `hal_patch_install.go`.
- **0x000B–0x000F:** Excluded from header checksum. Purpose not yet fully mapped. Values: `0x02 0x20 0x22 0x12 0x07`.

### Product String — Copy 1 (0x0010–0x001D)
```
0010: [len] [string bytes...] [0xFF padding]
```
- **0x0010:** String length byte (total byte count INCLUDING the length byte itself)
  - Original: 0x0E (14) = 1 (len byte) + 13 chars ("AFN_Cap video")
  - Modified: 0x0D (13) = 1 (len byte) + 12 chars ("Claude Rules")
- **0x0011–0x001D:** ASCII string data, padded with 0xFF to fill 13 bytes
- The firmware converts this ASCII to UTF-16LE for USB string descriptors at runtime

### Product String — Copy 2 (0x0020–0x002D)
```
0020: [len] [string bytes...] [0xFF padding]
```
- Identical format and content to Copy 1
- Both copies MUST be updated together
- Purpose of the second copy is unclear — possibly used for a different USB string index (e.g., UVC interface string), or redundancy

### Firmware/Code Region (0x0030–0x04BF)
Contains what appears to be 8051 firmware code (the MS2107 is based on an 8051 core). Values include typical 8051 opcodes (0x90 = MOV DPTR, 0xE0 = MOVX A,@DPTR, 0xF0 = MOVX @DPTR,A, 0x74 = MOV A,#imm, etc.).

### Config/Checksum Region (0x04C0–0x04C1)
```
Original: 0x0F 0xFF
Modified: 0x11 0xEF
```
- These 2 bytes also changed when the product string was modified
- Likely a checksum, CRC, or length field that the firmware validates
- **Important:** If writing EEPROM, these bytes may need to be recalculated or copied from a known-good dump

### Remainder (0x04C2–0x07FF)
Mostly 0xFF (erased/unused), with some scattered non-0xFF values.

---

## 3. HID Control Protocol

The MS2107 uses the same HID feature report protocol as the MS2109 (documented at https://github.com/amnemonic/MacroSilicon).

### Feature Report Format
- **Report ID:** 0x00
- **Total size:** 9 bytes (1 byte report ID + 8 bytes data)
- **Usage Page:** 0xFF00 (vendor-defined)
- **Usage:** 0x0001

### EEPROM Read (Command 0xE5)

**Send (SET_FEATURE):**
```
[0x00, 0xE5, addr_hi, addr_lo, 0x00, 0x00, 0x00, 0x00, 0x00]
```

**Receive (GET_FEATURE):**
```
[0x00, 0xE5, addr_hi, addr_lo, data[0], data[1], data[2], data[3], data[4]]
```

- Returns **5 consecutive bytes** starting at the requested address
- addr_hi and addr_lo are echoed back for verification
- Efficient: can read 2048 bytes in 410 reads (stepping by 5)

### EEPROM Write (Command 0xE6)

**Send (SET_FEATURE):**
```
[0x00, 0xE6, addr_hi, addr_lo, data_byte, 0x00, 0x00, 0x00, 0x00]
```

- Writes **1 byte** at a time (needs confirmation — may support 2 bytes)
- EEPROM writes are slow (~5ms per byte typical for I2C EEPROM)
- A small delay between writes may be needed

### XDATA Read (Command 0xB5)

**Send (SET_FEATURE):**
```
[0x00, 0xB5, addr_hi, addr_lo, 0x00, 0x00, 0x00, 0x00, 0x00]
```
- Reads the 8051 XDATA memory space (registers, RAM)

### XDATA Write (Command 0xB6)

**Send (SET_FEATURE):**
```
[0x00, 0xB6, addr_hi, addr_lo, value, 0x00, 0x00, 0x00, 0x00]
```
- Writes to the 8051 XDATA memory space

### Python Example (hidapi)
```python
import hid

d = hid.device()
d.open(0x0002, 0xAFA1)

# Read 5 bytes from EEPROM address 0x0010
d.send_feature_report([0x00, 0xE5, 0x00, 0x10, 0x00, 0x00, 0x00, 0x00, 0x00])
resp = d.get_feature_report(0, 9)
data = resp[4:9]  # 5 bytes of EEPROM data

d.close()
```

---

## 4. Windows USB Device Caching Behavior

### The FriendlyName Persistence Problem

Windows caches USB device metadata aggressively. When a USB device enumerates, Windows:

1. Reads the USB string descriptors (iProduct, iManufacturer, iSerialNumber)
2. Stores them in the PnP property store as `DEVPKEY_Device_BusReportedDeviceDesc`
3. Sets `DEVPKEY_Device_FriendlyName` from the product string on **first enumeration only**
4. **Never updates FriendlyName on subsequent enumerations**, even if the device reports a different string

### Registry Locations

**Primary device enumeration (per-interface):**
```
HKLM\SYSTEM\CurrentControlSet\Enum\USB\VID_0002&PID_AFA1&MI_xx\<instance>
    FriendlyName    REG_SZ    <cached product string>
    DeviceDesc      REG_SZ    <driver-provided description>
```

**Binary property store (SYSTEM-owned, ACL-protected):**
```
HKLM\SYSTEM\CurrentControlSet\Enum\USB\VID_0002&PID_AFA1&MI_xx\<instance>\Properties\
    {A45C254E-DF1C-4EFD-8020-67D146A850E0}\0014    = FriendlyName
    {540B947E-8B40-45BC-A8A2-6A0B894CBDA2}\0004    = BusReportedDeviceDesc
```

**Device container:**
```
HKLM\SYSTEM\CurrentControlSet\Control\DeviceContainers\{container-guid}\
```

**HID child device:**
```
HKLM\SYSTEM\CurrentControlSet\Enum\HID\VID_0002&PID_AFA1&MI_04\<instance>
```

### Key Discovery: BusReportedDeviceDesc vs FriendlyName

| Property                          | Updated on replug? | Source                    |
|-----------------------------------|--------------------|---------------------------|
| `DEVPKEY_Device_BusReportedDeviceDesc` | **Yes** — always fresh | Live USB iProduct string  |
| `DEVPKEY_Device_FriendlyName`     | **No** — sticky        | Set once, cached forever  |
| `DEVPKEY_NAME`                    | **No** — follows FriendlyName | Mirrors FriendlyName |

### How to Force a FriendlyName Update

**Method 1: `pnputil /remove-device` (recommended)**
With the device unplugged:
```
pnputil /remove-device "USB\VID_0002&PID_AFA1\20200909"
pnputil /remove-device "USB\VID_0002&PID_AFA1&MI_00\<instance>"
pnputil /remove-device "USB\VID_0002&PID_AFA1&MI_02\<instance>"
pnputil /remove-device "USB\VID_0002&PID_AFA1&MI_04\<instance>"
pnputil /remove-device "HID\VID_0002&PID_AFA1&MI_04\<instance>"
```
Then replug. Windows creates all entries fresh from live descriptors.

**Method 2: `reg delete` (partial)**
```
reg delete "HKLM\SYSTEM\CurrentControlSet\Enum\USB\VID_0002&PID_AFA1" /f
```
Only partially works — the binary `Properties` subkeys are SYSTEM-owned and survive the delete. Windows may restore FriendlyName from the surviving property store on next enumeration.

**Method 3: `Set-PnpDeviceProperty` (untested)**
May be able to overwrite FriendlyName directly without removing the device.

---

## 5. USBIP Interaction

### The "Bricked" Device Illusion

The device appeared non-functional because `usbipd` had it in "Shared (forced)" state:
```
7-2    0002:afa1  AFN_Cap video, USB Input Device    Shared (forced)
```

When usbipd force-shares a device:
- It loads a **stub driver** that replaces all native Windows drivers
- All child interfaces (Camera, Audio, HID) show as **CM_PROB_PHANTOM** (Status: Unknown)
- The device appears dead in Device Manager
- No application can access any interface

The `IsForced: true` flag with a `PersistedGuid` meant the sharing persisted across reboots.

### Fix
```
usbipd unbind --busid 7-2
```
This removes the stub driver and allows Windows to load native drivers. All interfaces immediately came back to Status: OK.

### VirtualBox Artifact
The device container also referenced `USB\Vid_80EE&Pid_CAFE\20200909` (VID 80EE = VirtualBox), suggesting the device was previously passed through to a VirtualBox VM.

---

## 6. EEPROM Dump Comparison

### Diff: Original (MS2107.BIN) vs Modified EEPROM

Only **30 bytes** differ out of 2048:

**Product string copy 1 (0x0010–0x001D):**
```
Original: 0e 41 46 4e 5f 43 61 70 20 76 69 64 65 6f    len=14 "AFN_Cap video"
Modified: 0d 43 6c 61 75 64 65 20 52 75 6c 65 73 ff    len=13 "Claude Rules"
```

**Product string copy 2 (0x0020–0x002D):**
```
Original: 0e 41 46 4e 5f 43 61 70 20 76 69 64 65 6f    len=14 "AFN_Cap video"
Modified: 0d 43 6c 61 75 64 65 20 52 75 6c 65 73 ff    len=13 "Claude Rules"
```

**Config/checksum (0x04C0–0x04C1):**
```
Original: 0f ff
Modified: 11 ef
```

### Files
- **Original dump:** `/home/jeff/projects/MS2107.BIN` (2048 bytes, known-good)
- **Modified dump (HID):** `/home/jeff/projects/MS2107_CLAUDE.BIN` (2048 bytes, "Claude Rules" strings)
- **MS2107 ROM dump:** `/home/jeff/projects/MS2107_ROM.BIN` (65536 bytes, XDATA space)
- **MacroSilicon tools:** `/home/jeff/projects/MacroSilicon/writeeeprom.exe` (Delphi, MS2109-targeted)

---

## 7. Device Identification

The MS2107 uses a **non-standard VID (0x0002)**. This causes issues with:
- Tools that filter by VID (most USB utilities expect VIDs from the USB-IF registry)
- `usbipd` normal sharing (required `--force` flag)
- Some driver matching heuristics

The device should always be identified by **path** rather than VID:PID when using programmatic access:
```python
# By path (reliable)
d.open_path(b'\\\\?\\HID#VID_0002&PID_AFA1&MI_04#...')

# By VID:PID (works but non-standard VID may confuse some tools)
d.open(0x0002, 0xAFA1)
```

---

## 8. Summary of Session Actions

1. **Diagnosed** device as not bricked — all interfaces were healthy but hidden by usbipd stub driver
2. **Unbound** device from usbipd (`usbipd unbind --busid 7-2`)
3. **Confirmed** HID interface accessible and EEPROM readable
4. **Dumped** current EEPROM via HID (command 0xE5) and diffed against original
5. **Discovered** Windows FriendlyName caching behavior — `BusReportedDeviceDesc` updates but `FriendlyName` is sticky
6. **Attempted** `reg delete` — partially worked but binary Properties store survived (SYSTEM ACLs)
7. **Used** `pnputil /remove-device` on all 5 device nodes + audio endpoint — fully cleaned slate
8. **Verified** fresh enumeration shows "Claude Rules" in FriendlyName, BusReportedDeviceDesc, and all UI surfaces

---

## 9. MS9123 (VID 534D:PID 6021) — Cross-Device Investigation

### Device Overview
- **VID:PID:** 0x534D:0x6021 (MacroSilicon registered VID)
- **iManufacturer:** "USB Display "
- **iProduct:** "usb extscreen"
- **iSerialNumber:** 2019BA7160B0
- **Suspected silicon:** MS9123, same family as MS2107/MS2109

### USB Interfaces

| Interface | Class     | Function                              | Status |
|-----------|----------|---------------------------------------|--------|
| MI_00     | HID (0x03) | Vendor-defined control (0xFF00:0x0001) | OK     |
| MI_03     | Vendor?  | "msusb video"                         | **Error** (no driver) |

Notable differences from MS2107/MS2109:
- HID is at **MI_00** (not MI_04)
- No UAC audio interface
- Video interface at MI_03 (not MI_00) with a custom class (not UVC)
- Only 2 interfaces vs 3 on the MS2107

### HID Protocol Compatibility

**All four MS2109 commands work identically:**

| Command | Function | Works? | Response format |
|---------|----------|--------|-----------------|
| 0xE5 | EEPROM read | Yes | Same 5-byte data response |
| 0xE6 | EEPROM write | Yes | Confirmed write + readback |
| 0xB5 | XDATA read | Yes | Same 5-byte data response |
| 0xB6 | XDATA write | Yes | Accepted (cmd echoed) |

### EEPROM Layout Comparison

| Feature | MS2107 | MS9123 |
|---------|--------|--------|
| Size | 2048 bytes | 2048 bytes |
| Magic | `08 16` | `A5 5A` |
| Non-0xFF bytes | ~1200 | 424 |
| USB strings in EEPROM | Yes (2 copies) | **No** |
| VID/PID in EEPROM | Yes | Not apparent |
| Content type | Descriptors + 8051 code | Almost entirely 8051 code overlay |

The `A5 5A` magic at byte 0 is likely a "valid EEPROM" signature — if present, the bootloader loads the EEPROM code as a firmware patch/overlay. The MS9123's USB descriptor strings are stored in **ROM, not EEPROM**.

### MS9123 EEPROM Non-0xFF Content

```
0000: a5 5a 01 9d 2c 00 ff ff ff ff 00 ee ff 21 01 27  .Z..,........!.'
0030-01d4: 8051 firmware overlay code (~420 bytes)
0200-07ff: all 0xFF (unused)
```

Header fields:
- **0x0000:** `A5` — magic byte 1 ("EEPROM valid" flag)
- **0x0001:** `5A` — magic byte 2
- **0x0002-0x0004:** `01 9D 2C` — possibly code entry point or load address
- **0x000A:** `00 EE` — unknown config
- **0x000D-0x000F:** `21 01 27` — unknown (version? `2101` matches MS2107 revision)

### XDATA / ROM Dump Comparison (64KB)

The XDATA space was dumped via 0xB5 for both chips. Memory map:

| Region | MS9123 vs MS2107 | Interpretation |
|--------|-----------------|----------------|
| 0x0000–0x7FFF | ~2% match | Hardware registers, XDATA RAM (chip-specific) |
| 0x8000–0x8FFF | **100% match** | Shared boot ROM / common library |
| 0x9000–0xBFFF | **~80% match** | Core firmware (same family, minor variants) |
| 0xC000–0xCFFF | ~10% match | Chip-specific peripheral code |
| 0xD000–0xDFFF | ~0% match | Chip-specific |
| 0xE000–0xEFFF | ~20% match | Partially shared code |
| 0xF500 | ~90% match | Shared utility code |
| 0xF900–0xFEFF | 50-78% match | USB/boot code with variants |
| 0xFF00–0xFFFF | **100% match** | Interrupt vector table / boot vectors |

**Key conclusion:** The 100% match at 0x8000–0x8FFF and 0xFF00–0xFFFF confirms the MS9123 and MS2107 share the same 8051 core silicon. The ROM is mapped into XDATA at 0x8000–0xFFFF (upper 32KB). The lower 32KB (0x0000–0x7FFF) is hardware registers and RAM.

### Note on Code ROM vs XDATA

The 0xB5 command reads the XDATA address space, not the 8051 code space (accessed via MOVC). USB descriptor strings were **not found** in either chip's XDATA dump — they exist only in code ROM, which is a separate address space not directly accessible via the HID protocol. The strings may be:
- Constructed byte-by-byte in firmware code
- Stored in a code ROM region that doesn't map to XDATA
- Generated from EEPROM data at boot (MS2107) or hardcoded (MS9123)

### Cautionary Note: EEPROM Write (0xE6)

During testing, sending `[0x00, 0xE6, 0x00, 0x00, 0x00, ...]` as a probe **accidentally wrote 0x00 to EEPROM address 0**, overwriting the 0xA5 magic byte. This was detected by comparing the HID dump against the existing MS9123.BIN and repaired by writing 0xA5 back.

**Lesson:** Never send command 0xE6 with test data — it's a live write. Always use 0xE5 (read) for probing.

### Files
- **EEPROM dump (original):** `/home/jeff/projects/MS9123.BIN` (2048 bytes)
- **EEPROM dump (HID verified):** `/home/jeff/projects/MS9123_HID.BIN` (2048 bytes, matches MS9123.BIN)
- **XDATA/ROM dump:** `/home/jeff/projects/MS9123_ROM.BIN` (65536 bytes)
