	.module crt0_ms2107
	.globl _normal_hook_dispatch

	.area HOME    (CODE)
	.area CSEG    (CODE)
	.area HOME    (CODE)

	; +0x00: Normal hook entry (ROM calls 0xC800 with R7=command)
	; Keil passes command in R7; SDCC expects it in DPL.
	ljmp	_keil_to_sdcc_normal_hook

	; +0x03: reset_fw_state (13 bytes, fills exactly to offset 0x10)
_reset_fw_state::
	.globl _reset_fw_state
	clr	0x04
	mov	dptr, #0xD200
	mov	a, #0x01
	movx	@dptr, a
	mov	dptr, #0xD201
	movx	@dptr, a
	ret

	; +0x10: IRQ hook entry (ROM calls 0xC810 from interrupt context)
	; This jumps to the original IRQ handler preserved as inline assembly.
	; The SDCC-compiled version had subtle differences that broke USB
	; enumeration. 44 bytes of proven Keil-compiled code is more reliable
	; in interrupt context than trying to replicate it in C.
	ljmp	_irq_handler_original


	; ================================================================
	; Keil <-> SDCC calling convention shims
	;
	; The ROM (Keil C51) and our code (SDCC) differ in:
	;   - Argument passing: Keil uses R7, SDCC uses DPL
	;   - Register preservation: ROM expects bank 0 R0-R7 preserved
	;
	; SDCC's scratch (DSEG) starts at 0x0B (--data-loc 0x0B) to avoid
	; bank 0 (0x00-0x07), matching the original Keil allocation.
	; ================================================================

	; --- Inbound: normal hook (ROM calls with R7=cmd) ---
	; Saves all registers, bridges R7->DPL, calls SDCC dispatch.
_keil_to_sdcc_normal_hook:
	push	psw				; save register bank select
	push	acc
	push	b
	push	dpl
	push	dph
	mov	dpl, r7				; Keil R7 -> SDCC DPL (command arg)
	lcall	_normal_hook_dispatch
	pop	dph
	pop	dpl
	pop	b
	pop	acc
	pop	psw
	ret

	; --- IRQ handler: hand-written assembly (44 bytes) ---
	; Reconstructed from disassembly of the original firmware. Written
	; in assembly rather than C because SDCC's code generation for this
	; function produced subtle differences that broke USB enumeration:
	;   - MOV A,#imm + CJNE A,direct vs MOV R7,direct + CJNE R7,#imm
	;   - JNB ACC.7 vs ANL A,#0x80 + JNZ
	;   - Swapped ORL operand order
	;   - LJMP tail-call vs LCALL+RET
	; While each appears functionally equivalent in isolation, the
	; combination caused failures in interrupt context.
	;
	; Logic:
	;   1. Check IRAM[0x0B] bit 5 — if set and IRAM[0x10]==2 and
	;      EEPROM[0x0A] bit 0 clear: reset IRAM[0x0F]=0, IRAM[0x10]=4
	;   2. Check IRAM[0x0B] bit 7 — if clear and (IRAM[0x11]|IRAM[0x12])!=0:
	;      set bit flag 0x22.6 and P0.6, return early
	;   3. Otherwise: call rom_video_display (0x44BA)
_irq_handler_original:
	mov	a, 0x0B			; irq_flags
	jnb	acc.5, irq_check_output
	mov	r7, 0x10		; irq_cmd_hi
	cjne	r7, #0x02, irq_check_output
	mov	dptr, #0xC7DA		; userconfig_0a (EEPROM[0x0A])
	movx	a, @dptr
	jb	acc.0, irq_check_output
	mov	0x0F, #0x00		; irq_cmd_lo = 0
	mov	0x10, #0x04		; irq_cmd_hi = 4
irq_check_output:
	mov	a, 0x0B			; irq_flags
	anl	a, #0x80		; test bit 7
	jnz	irq_call_display
	mov	a, 0x12			; irq_data1
	orl	a, 0x11			; irq_data0
	jz	irq_call_display
	setb	0x16			; bit 0x22.6 (flag_irq_signal)
	setb	0x86			; P0.6
	ret
irq_call_display:
	lcall	_rom_video_display	; LCALL to our crt0 wrapper -> ROM 0x44BA
	ret


	; ================================================================
	; Outbound ROM call wrappers (SDCC -> Keil convention)
	;
	; SDCC passes first uint8_t arg in DPL.
	; Keil ROM expects first uint8_t arg in R7.
	; Parameterless calls need no bridging.
	; ================================================================

	; ROM 0x44BA - Video ADC / display bank register configuration
	; Configures 10-bit video ADC and input routing (CVBS/S-Video).
	; Uses register bank 1 params (BANK1_R3, BANK1_R4). No args.
_rom_video_display::
	.globl _rom_video_display
	lcall	0x44BA
	ret

	; ROM 0x5659 - Video input mode configuration
	; Sets up ADC + processing for NTSC/PAL. Reads IRAM[0x43],[0x48]. No args.
_rom_video_mode_config::
	.globl _rom_video_mode_config
	lcall	0x5659
	ret

	; ROM 0x5C29 - Video capture setup
	; Keil R7 = capture enable (1=start, 0=stop).
	; Configures UVC pipeline and USB isochronous transfers.
_rom_video_setup::
	.globl _rom_video_setup
	mov	r7, dpl				; SDCC DPL -> Keil R7
	lcall	0x5C29
	ret

	; ROM 0x6087 - Video pipeline reset
	; Clears F8xx video regs, resets capture pipeline. No args.
_rom_video_reset::
	.globl _rom_video_reset
	lcall	0x6087
	ret

	; ROM 0x6F52 - Delay loop
	; Keil R7 = iteration count (~ms-scale per iteration).
_rom_delay::
	.globl _rom_delay
	mov	r7, dpl				; SDCC DPL -> Keil R7
	lcall	0x6F52
	ret


	; ROM 0x68BD - I2C start condition
	; Drives SDA low while SCL high (GPIO2=SCL, GPIO3=SDA).
_rom_i2c_start::
	.globl _rom_i2c_start
	lcall	0x68BD
	ret

	; ROM 0x6B5B - I2C stop condition
	; Drives SDA high while SCL high.
_rom_i2c_stop::
	.globl _rom_i2c_stop
	lcall	0x6B5B
	ret

	; ROM 0x5323 - I2C write byte
	; Keil R7 = byte to send.
	; Returns: carry = bit 0x23.6 = ACK status.
	;   Carry SET (1) = ACK received (SDA pulled low by slave)
	;   Carry CLEAR (0) = NAK (no slave responded)
	; We invert for C convention: DPL=0 means ACK (success), DPL=1 means NAK.
_rom_i2c_write::
	.globl _rom_i2c_write
	mov	r7, dpl				; SDCC DPL -> Keil R7
	lcall	0x5323
	clr	a
	jc	i2c_write_got_ack		; carry set = ACK = success
	inc	a				; A=1 = NAK
i2c_write_got_ack:
	mov	dpl, a				; DPL: 0=ACK, 1=NAK
	ret

	; ROM 0x5934 - I2C read byte
	; ACK/NAK controlled by bit 0x1D (IRAM byte 0x23, bit 5):
	;   bit clear = send ACK (continue reading)
	;   bit set = send NAK (last byte)
	; SDCC DPL: 0=ACK, non-zero=NAK
	; Returns read byte in Keil R7 -> SDCC DPL.
_rom_i2c_read::
	.globl _rom_i2c_read
	mov	a, dpl
	jz	i2c_read_ack			; DPL=0 -> send ACK
	setb	0x1D				; set bit 0x23.5 = NAK
	sjmp	i2c_read_do
i2c_read_ack:
	clr	0x1D				; clear bit 0x23.5 = ACK
i2c_read_do:
	lcall	0x5934
	mov	dpl, r7				; read byte -> SDCC DPL
	ret


	; No GSINIT/GSFINAL needed - ROM handles all initialization
	.area GSINIT  (CODE)
	.area GSFINAL (CODE)
