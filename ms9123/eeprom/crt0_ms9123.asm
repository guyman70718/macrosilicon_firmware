	.module crt0_ms9123
	.globl _init_hook2
	.globl _periodic_handler

	.area HOME    (CODE)
	.area CSEG    (CODE)
	.area HOME    (CODE)

	; === +0x00 (0xC830): Init hook 1 entry ===
	; No parameters from ROM. Runs once at boot.
	; init_hook1_body is inline asm below (no SDCC code, no register issue).
	ljmp	init_hook1_body			; 3 bytes

	; === +0x03 (0xC833): store_r4r5r6r7 helper (12 bytes) ===
	; Called from ROM callbacks with DPTR and R4-R7 already set.
	; Pure register/XDATA operation — no calling convention issue.
_store_r4r5r6r7::
	.globl _store_r4r5r6r7
	mov	a, r4
	movx	@dptr, a
	inc	dptr
	mov	a, r5
	movx	@dptr, a
	inc	dptr
	mov	a, r6
	movx	@dptr, a
	inc	dptr
	mov	a, r7
	movx	@dptr, a
	ret					; +0x0E

	; === +0x0F: gap byte (original = 0xFF = MOV R7,A) ===
	mov	r7, a				; 1 byte

	; === +0x10 (0xC840): Init hook 2 entry ===
	; No parameters. init_hook2 is SDCC code — needs register protection.
	; NOTE: init_hook2 contains an infinite loop (never returns).
	; We still save registers for safety in case the ROM ever
	; changes to expect a return.
	ljmp	_keil_to_sdcc_init_hook2	; 3 bytes

	; === +0x13 (0xC843): Init hook 1 body (27 bytes) ===
	; Inline assembly to guarantee exact layout to offset 0x30.
	; Configures P3 GPIO for CVBS DAC output control,
	; clears host connection event counter, sets fw_loaded flag,
	; writes "DW" ready signature to XDATA[0xDFDF].
init_hook1_body:
	anl	0xB0, #0x3F			; P3 bits 6,7 = output
	anl	0xB1, #0x3F			; P3 alternate function off
	clr	a
	mov	dptr, #0xDE0A			; connect_event = 0
	movx	@dptr, a
	setb	0x0D				; flag_fw_loaded (bit 0x21.5)
	mov	0x31, #0x04			; timer_config = 4
	mov	dptr, #0xDFDF			; fw_ready signature
	mov	a, #0x44			; 'D'
	movx	@dptr, a
	inc	dptr
	mov	a, #0x57			; 'W'
	movx	@dptr, a
	ret					; +0x2D

	; === +0x2E (0xC85E): Halt trap ===
_halt_trap::
	.globl _halt_trap
	sjmp	_halt_trap			; SJMP self (2 bytes)

	; === +0x30 (0xC860): Periodic hook entry ===
	; No parameters. Called from USB IRQ — needs register protection.
	ljmp	_keil_to_sdcc_periodic		; 3 bytes


	; ================================================================
	; Keil <-> SDCC calling convention shims
	;
	; The ROM (Keil C51) expects bank 0 registers preserved.
	; SDCC scratch starts at 0x0B (--data-loc 0x0B) to avoid bank 0.
	; PUSH/POP PSW, A, B, DPL, DPH for safety.
	; ================================================================

_keil_to_sdcc_init_hook2:
	push	psw
	push	acc
	push	b
	push	dpl
	push	dph
	lcall	_init_hook2			; NOTE: this never returns (infinite loop)
	pop	dph				; unreachable, but here for correctness
	pop	dpl
	pop	b
	pop	acc
	pop	psw
	ret

_keil_to_sdcc_periodic:
	push	psw
	push	acc
	push	b
	push	dpl
	push	dph
	lcall	_periodic_handler
	pop	dph
	pop	dpl
	pop	b
	pop	acc
	pop	psw
	ret


	; ================================================================
	; Outbound ROM call wrappers (SDCC -> Keil convention)
	;
	; Most MS9123 ROM calls take no parameters.
	; Only rom_delay (0x63A4) needs DPL -> R7.
	; ================================================================

	; ROM 0x0BA1 - 10-bit DAC output quality check / calibration
	; Evaluates DAC readback samples (from IRAM[0x55-0x5C] snapshot)
	; against expected output levels. The MS9123 has a 10-bit 3-channel
	; DAC driving CVBS (pin 32), S-Video Y (pin 33), S-Video C (pin 34).
	; Uses IRAM[0x55] mode byte for expected level selection.
_rom_output_quality_check::
	.globl _rom_output_quality_check
	lcall	0x0BA1
	ret

	; ROM 0x2DA2 - Generic display output function
	; Handles display modes that aren't the specific NTSC mode.
	; Uses IRAM[0x3F] for mode selection, writes to C5C7 region. No parameters.
_rom_generic_display::
	.globl _rom_generic_display
	lcall	0x2DA2
	ret

	; ROM 0x3A5C - USB frame buffer management
	; Processes incoming USB frames from the host.
	; Manages C559/C555 buffer state. Called with EX0 disabled. No parameters.
_rom_usb_frame_manage::
	.globl _rom_usb_frame_manage
	lcall	0x3A5C
	ret

	; ROM 0x4E8D - Host detection / keepalive
	; Monitors whether the USB host is actively sending frames.
	; Checks C805/C612 status, manages auto-detection counter. No parameters.
_rom_host_detect::
	.globl _rom_host_detect
	lcall	0x4E8D
	ret

	; ROM 0x58B9 - Identify host output mode
	; Reads SFR_DAC and characterizes what the host is sending.
	; Populates IRAM[0x3F-0x44] with mode/standard info. No parameters.
_rom_identify_host_output::
	.globl _rom_identify_host_output
	lcall	0x58B9
	ret

	; ROM 0x5D16 - Display hardware initialization
	; Configures 10-bit video DAC, scaler for 720x480/576 output,
	; CVBS/S-Video timing, SFRs (0x95/0x9B/0x9D).
	; Called once from init hook 2. No parameters.
_rom_display_hw_init::
	.globl _rom_display_hw_init
	lcall	0x5D16
	ret

	; ROM 0x63A4 - Delay / frame pacing
	; Keil R7 = delay count. Needs DPL -> R7 shim.
_rom_delay::
	.globl _rom_delay
	mov	r7, dpl				; SDCC DPL -> Keil R7
	lcall	0x63A4
	ret

	; ROM 0x65CB - Peripheral / I2C communication
	; Complex calling convention: uses DPTR + R4-R7.
	; Called from the store_r4r5r6r7 asm helper, not directly from C.
_rom_peripheral_comm::
	.globl _rom_peripheral_comm
	lcall	0x65CB
	ret

	; ROM 0x66BD - PLL/clock reconfiguration
	; Waits for PLL to stabilize (polls CL register — the MS9123 uses
	; a 24MHz crystal with internal PLL per datasheet), then reconfigures
	; DAC and timing SFRs. Called when display mode changes. No parameters.
_rom_clock_reconfig::
	.globl _rom_clock_reconfig
	lcall	0x66BD
	ret

	; ROM 0x67D1 - Safe reconfiguration (host-triggered)
	; Disables interrupts, toggles DAC clock gate (SFR 0x95 bit 6),
	; performs I2C communication, re-enables interrupts.
	; Triggered by host writing 0x5A to mailbox at XDATA[0xDDFF]. No parameters.
_rom_safe_reconfig::
	.globl _rom_safe_reconfig
	lcall	0x67D1
	ret

	; ROM 0x7335 - CVBS output timing setup
	; Configures timing for 720x480 NTSC or 720x576 PAL output.
	; Called once during init hook 2. No parameters.
_rom_output_timing_setup::
	.globl _rom_output_timing_setup
	lcall	0x7335
	ret


	; ================================================================
	; I2C Bus A (EEPROM bus) wrappers
	; SDA = P3.7 (inverted: CLR=high, SETB=low)
	; SCL via ROM helpers (0x71D7/0x736B)
	; ACK/NAK via bit 0x02 (byte 0x20, bit 2)
	; No interrupt disable needed (P3.7 is not an interrupt pin)
	; ================================================================

	; ROM 0x6AB8 — I2C start condition. No parameters.
_rom_i2c_start::
	.globl _rom_i2c_start
	lcall	0x6AB8
	ret

	; ROM 0x6919 — I2C stop condition. No parameters.
_rom_i2c_stop::
	.globl _rom_i2c_stop
	lcall	0x6919
	ret

	; ROM 0x46BC — I2C write byte.
	; SDCC DPL = byte to send. ROM uses Keil R7.
	; Returns: ACK status from bit 0x02 (byte 0x20, bit 2).
	;   bit set = ACK received (success)
	;   bit clear = NAK
	; We return 0=ACK, 1=NAK in SDCC DPL.
_rom_i2c_write::
	.globl _rom_i2c_write
	mov	r7, dpl				; SDCC DPL -> Keil R7
	lcall	0x46BC
	clr	a
	jb	0x02, i2c_w_ack			; bit 0x02 set = ACK
	inc	a				; A=1 = NAK
i2c_w_ack:
	mov	dpl, a				; DPL: 0=ACK, 1=NAK
	ret

	; ROM 0x4B9B — I2C read byte.
	; SDCC DPL = ACK flag: 0=send ACK, non-zero=send NAK.
	; ROM uses bit 0x02: set=NAK, clear=ACK.
	; Returns read byte in Keil R7 -> SDCC DPL.
_rom_i2c_read::
	.globl _rom_i2c_read
	mov	a, dpl
	jz	i2c_r_ack
	setb	0x02				; NAK
	sjmp	i2c_r_do
i2c_r_ack:
	clr	0x02				; ACK
i2c_r_do:
	lcall	0x4B9B
	mov	dpl, r7				; read byte -> SDCC DPL
	ret


	; No GSINIT needed — ROM handles initialization
	.area GSINIT  (CODE)
	.area GSFINAL (CODE)
