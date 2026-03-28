# MS9123 CODE Space Dump — Instructions for Windows Agent

## Context

We're trying to get a complete dump of the MS9123's 8051 CODE address space (64KB). The CODE space is separate from XDATA on the 8051 — it's accessed via the MOVC instruction, not MOVX. The HID commands (0xB5/0xB6) only access XDATA.

### What we have
- `MS9123.BIN` — 2048-byte EEPROM dump (known good, verified)
- `MS9123_ROM.BIN` — 64KB XDATA dump, but **has a bug**: every 5th byte (position 0 in each 5-byte group) is `0x00` due to the dump script extracting 5 bytes from a command that only returns 1. Needs to be re-dumped.

### Device info
- **VID:PID:** `0x534D:0x6021`
- **HID interface:** MI_00 (unlike MS2107 which is MI_04)
- **EEPROM magic:** `0xA55A`
- **Chip ID at XDATA 0xF800:** `0x00`

## Task 1: Fix the XDATA dump

The `0xB5` command returns **1 byte** of XDATA per read (at response byte index 4), not 5. Re-dump the full 64KB XDATA space reading 1 byte at a time.

```python
import hid

d = hid.device()
d.open(0x534D, 0x6021)

xdata = bytearray(65536)
for addr in range(65536):
    d.send_feature_report([0x00, 0xB5, (addr >> 8) & 0xFF, addr & 0xFF, 0x00, 0x00, 0x00, 0x00, 0x00])
    resp = d.get_feature_report(0, 9)
    xdata[addr] = resp[4]  # Only byte 4 is valid XDATA
    if addr % 4096 == 0:
        print(f"  {addr}/65536 ({100*addr/65536:.0f}%)")

d.close()

with open("MS9123_XDATA_fixed.bin", "wb") as f:
    f.write(xdata)
print(f"Saved 65536 bytes")
```

This will be slow (~65K HID transactions). Expect 5-15 minutes. The upper 32KB (0x8000-0xFFFF) of XDATA maps the same mask ROM as CODE space, so this gives us half the CODE dump for free.

Save the result as `MS9123_XDATA_fixed.bin` in `\\wsl.localhost\Ubuntu-24.04\home\jeff\projects\`.

## Task 2: Dump CODE space 0x0000-0x7FFF via MOVC

The lower 32KB of CODE space does NOT map to XDATA — it's only accessible via the 8051 MOVC instruction. We need to upload a small 8051 program to RAM, trigger its execution, and read back the results.

### How this works

The MS9123's EEPROM configures two "user hooks" — code entry points that the ROM calls periodically. We can:
1. Write a tiny program into XDATA RAM (via 0xB6)
2. The program uses MOVC to read CODE bytes and stores them in XDATA
3. We trigger it via the hook mechanism
4. We read the results from XDATA (via 0xB5)

### Step 2a: Find the hook mechanism addresses

First, we need to find where the EEPROM code actually loads and how the hooks work. Read the XDATA at the userconfig region. On the MS2109 this is at `0xCBD0` but the MS9123 may differ.

Read these XDATA regions and report the values:
```python
# Read and report key XDATA regions
regions = [
    (0xC000, 0xC100, "UserRAM start"),
    (0xCBD0, 0xCC00, "MS2109 userconfig region"),
    (0xC7D0, 0xC810, "MS2107 userconfig region"),
]
for start, end, desc in regions:
    print(f"\n{desc} (0x{start:04X}-0x{end-1:04X}):")
    for addr in range(start, end, 16):
        vals = []
        for a in range(addr, min(addr+16, end)):
            d.send_feature_report([0x00, 0xB5, (a >> 8) & 0xFF, a & 0xFF, 0, 0, 0, 0, 0])
            resp = d.get_feature_report(0, 9)
            vals.append(resp[4])
        print(f"  {addr:04X}: {' '.join(f'{v:02X}' for v in vals)}")
```

### Step 2b: Upload and trigger the MOVC dump program

The 8051 program we need is tiny — it's a mailbox-based protocol:

```
; MOVC dump program
; Mailbox at DPTR_MAILBOX:
;   [0] = count (host writes N, program reads N bytes then writes 0)
;   [1:2] = source address in CODE space
;   [3:4] = destination address in XDATA
;
; Program sits in a loop, waiting for mailbox[0] != 0

loop:
    MOV  DPTR, #MAILBOX_ADDR
    MOVX A, @DPTR           ; read mailbox[0] = count
    JZ   done               ; if 0, return to caller
    MOV  R7, A              ; R7 = byte count
    INC  DPTR
    MOVX A, @DPTR           ; source_hi
    MOV  R4, A
    INC  DPTR
    MOVX A, @DPTR           ; source_lo
    MOV  R5, A
    INC  DPTR
    MOVX A, @DPTR           ; dest_hi
    MOV  R2, A
    INC  DPTR
    MOVX A, @DPTR           ; dest_lo
    MOV  R3, A

copy:
    MOV  DPH, R4            ; DPTR = source
    MOV  DPL, R5
    CLR  A
    MOVC A, @A+DPTR         ; read CODE byte
    MOV  DPH, R2            ; DPTR = dest
    MOV  DPL, R3
    MOVX @DPTR, A           ; write to XDATA
    INC  R5                 ; source++
    CJNE R5, #0, no_carry1
    INC  R4
no_carry1:
    INC  R3                 ; dest++
    CJNE R3, #0, no_carry2
    INC  R2
no_carry2:
    DJNZ R7, copy           ; loop for count bytes

    MOV  DPTR, #MAILBOX_ADDR
    CLR  A
    MOVX @DPTR, A           ; signal done (mailbox[0] = 0)
    SJMP loop               ; wait for next command

done:
    RET
```

The assembled bytes depend on the mailbox address. Here's a pre-assembled version with mailbox at `0xD300` (which ms-tools uses for MS2109 temp buffer). The bytes `D3 00` appear at offsets 1-2 and 40-41 in the blob:

```python
# MOVC dump blob - mailbox address 0xD300
# If 0xD300 doesn't work, try 0xD100 or another safe RAM address
MAILBOX = 0xD300
dump_blob = bytearray([
    0x90, (MAILBOX >> 8), (MAILBOX & 0xFF),  # MOV DPTR,#MAILBOX
    0xE0,                                      # MOVX A,@DPTR
    0x60, 0x22,                                # JZ done (skip to RET)
    0xFF,                                      # MOV R7,A
    0xA3, 0xE0, 0xFC,                         # INC DPTR; MOVX A,@DPTR; MOV R4,A (src_hi)
    0xA3, 0xE0, 0xFD,                         # INC DPTR; MOVX A,@DPTR; MOV R5,A (src_lo)
    0xA3, 0xE0, 0xFA,                         # INC DPTR; MOVX A,@DPTR; MOV R2,A (dst_hi)
    0xA3, 0xE0, 0xFB,                         # INC DPTR; MOVX A,@DPTR; MOV R3,A (dst_lo)
    # copy loop:
    0x8C, 0x83,                                # MOV DPH,R4
    0x8D, 0x82,                                # MOV DPL,R5
    0xE4,                                      # CLR A
    0x93,                                      # MOVC A,@A+DPTR
    0x8A, 0x83,                                # MOV DPH,R2
    0x8B, 0x82,                                # MOV DPL,R3
    0xF0,                                      # MOVX @DPTR,A
    0x0D,                                      # INC R5
    0xBD, 0x00, 0x01,                          # CJNE R5,#0,+1
    0x0C,                                      # INC R4
    0x0B,                                      # INC R3
    0xBB, 0x00, 0x01,                          # CJNE R3,#0,+1
    0x0A,                                      # INC R2
    0xDF, 0xE8,                                # DJNZ R7,copy (-24)
    0x90, (MAILBOX >> 8), (MAILBOX & 0xFF),    # MOV DPTR,#MAILBOX
    0xE4,                                      # CLR A
    0xF0,                                      # MOVX @DPTR,A
    0x80, 0xD6,                                # SJMP loop (-42)
    # done:
    0x22,                                      # RET
])
```

### Step 2c: Finding a safe load address

We need to find writable RAM where we can put the blob (~45 bytes) and the mailbox (5 bytes) without interfering with running firmware. The EEPROM code is 413 bytes loaded somewhere in the 0xC000-0xCFFF region.

**Approach: Try several candidate addresses.** Write a test pattern (e.g., `0xAA 0x55 0xAA 0x55`) to a candidate address, read it back. If it reads back correctly, the RAM is writable and not being used by hardware registers.

Good candidates to try (from MS2109 knowledge):
- `0xD300` — ms-tools uses this as temp buffer for MS2109
- `0xD100` — ms-tools uses this as temp buffer for MS2107
- `0xD000` — ms-tools uses this as mailbox for MS2107
- `0xCE00-0xCFFF` — usually free RAM above the EEPROM code region

```python
# Test which RAM addresses are writable
def test_ram(d, addr):
    """Write a test pattern and read it back"""
    pattern = [0xAA, 0x55, 0xDE, 0xAD]
    for i, val in enumerate(pattern):
        a = addr + i
        d.send_feature_report([0x00, 0xB6, (a >> 8) & 0xFF, a & 0xFF, val, 0, 0, 0, 0])

    result = []
    for i in range(4):
        a = addr + i
        d.send_feature_report([0x00, 0xB5, (a >> 8) & 0xFF, a & 0xFF, 0, 0, 0, 0, 0])
        resp = d.get_feature_report(0, 9)
        result.append(resp[4])

    ok = result == pattern
    print(f"  0x{addr:04X}: wrote {pattern} read {result} {'OK' if ok else 'FAIL'}")
    return ok

for addr in [0xD300, 0xD100, 0xD000, 0xCE00, 0xCF00, 0xC000]:
    test_ram(d, addr)
```

### Step 2d: Triggering code execution

This is the hardest part. The EEPROM sets up hooks that the ROM calls periodically. For the MS2109, the hook enable is at userconfig offset [4], and the hooks are at XDATA addresses `0xCC00` (normal) and `0xCC20` (IRQ).

Since the MS9123 uses the same EEPROM magic (A55A), it likely uses a similar hook mechanism. But the actual addresses may differ.

**Option A: Overwrite an existing hook**

If EEPROM code is loaded and hooks are active, we can overwrite the hook code with our dump blob. This is what ms-tools does:
1. Read the existing code at the hook address
2. Write our dump blob over it
3. After dumping, restore the original code

To find the hook address, look for the first LJMP instruction (opcode `0x02`) at the start of the EEPROM code region in XDATA. The EEPROM code typically starts with `02 xx yy` (LJMP to main routine).

**Option B: Use the hook config register**

Write to the userconfig to point a hook at our blob. This requires knowing the exact userconfig layout for the MS9123.

**Recommended approach for this attempt:** Since we don't fully know the MS9123's hook layout, start with getting the corrected XDATA dump (Task 1). Report the results, especially the XDATA regions listed in Step 2a, and we'll figure out the exact hook addresses from the data.

## Task 3: Assemble and execute

Once we know the safe RAM addresses and hook mechanism, the full dump procedure is:

```python
LOAD_ADDR = 0x????   # Where to load dump_blob (from step 2c)
MAILBOX   = 0x????   # Where the mailbox lives (from step 2c)
TEMP_BUF  = 0x????   # Where MOVC results go (from step 2c)
TEMP_LEN  = 128      # Read this many bytes per iteration

# 1. Write dump blob to RAM
for i, b in enumerate(dump_blob):
    a = LOAD_ADDR + i
    d.send_feature_report([0x00, 0xB6, (a >> 8) & 0xFF, a & 0xFF, b, 0, 0, 0, 0])

# 2. Trigger hook (mechanism TBD based on Task 1 results)

# 3. Iterate through CODE space 0x0000-0x7FFF
code_dump = bytearray(0x8000)
for src_addr in range(0, 0x8000, TEMP_LEN):
    # Write mailbox: [count, src_hi, src_lo, dst_hi, dst_lo]
    mb = [TEMP_LEN, (src_addr >> 8) & 0xFF, src_addr & 0xFF,
          (TEMP_BUF >> 8) & 0xFF, TEMP_BUF & 0xFF]
    for i, b in enumerate(mb):
        a = MAILBOX + i
        d.send_feature_report([0x00, 0xB6, (a >> 8) & 0xFF, a & 0xFF, b, 0, 0, 0, 0])

    # Wait for completion (mailbox[0] == 0)
    import time
    for _ in range(100):
        d.send_feature_report([0x00, 0xB5, (MAILBOX >> 8) & 0xFF, MAILBOX & 0xFF, 0, 0, 0, 0, 0])
        resp = d.get_feature_report(0, 9)
        if resp[4] == 0:
            break
        time.sleep(0.02)

    # Read results from TEMP_BUF
    for i in range(TEMP_LEN):
        a = TEMP_BUF + i
        d.send_feature_report([0x00, 0xB5, (a >> 8) & 0xFF, a & 0xFF, 0, 0, 0, 0, 0])
        resp = d.get_feature_report(0, 9)
        code_dump[src_addr + i] = resp[4]

    print(f"  CODE dump: {src_addr + TEMP_LEN}/32768 bytes")

# 4. Combine with XDATA upper 32KB for full 64KB CODE dump
# (XDATA 0x8000-0xFFFF mirrors CODE 0x8000-0xFFFF)
with open("MS9123_XDATA_fixed.bin", "rb") as f:
    xdata_fixed = f.read()

full_code = code_dump + bytearray(xdata_fixed[0x8000:])
with open("MS9123_CODE.bin", "wb") as f:
    f.write(full_code)
print(f"Saved full 64KB CODE dump")
```

## Priority

1. **Task 1 first** — the corrected XDATA dump is the most valuable immediate step and unblocks everything else. It gives us CODE 0x8000-0xFFFF and lets us map the memory layout properly.
2. **Task 2a** — report the userconfig regions so we can figure out hook addresses.
3. **Tasks 2b-3** — we'll refine the CODE dump approach based on the data from tasks 1 and 2a.

## Important Warnings

- **NEVER** use command `0xE6` (EEPROM write) for testing/probing — it's a live write. The previous session accidentally corrupted the EEPROM magic byte this way.
- Command `0xB6` (XDATA write) is also live — only write to addresses you've confirmed are safe writable RAM.
- The device HID is at **MI_00** (not MI_04 like the MS2107).
