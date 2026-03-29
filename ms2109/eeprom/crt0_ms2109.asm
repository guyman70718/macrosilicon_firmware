	.module crt0_ms2109

	.area HOME    (CODE)
	.area CSEG    (CODE)
	.area HOME    (CODE)

	; ================================================================
	; MS2109 EEPROM Firmware — self-contained, pure assembly
	;
	; All command handlers reimplemented. No overlay dependencies
	; except our own trampolines and real ROM function calls.
	; ================================================================


	; +0x00: Normal hook
	ljmp	_normal_hook_entry

	; +0x03..0x0F: padding
	.ds	13

	; +0x10: Callback (byte-identical to stock)
	mov	dptr, #0xDE05
	mov	a, r3
	movx	@dptr, a
	inc	dptr
	mov	a, r2
	movx	@dptr, a
	inc	dptr
	mov	a, r1
	movx	@dptr, a
	lcall	0x6345
	ret

	; +0x1F
	.db	0xFF


	; ================================================================
	; +0x20: IRQ handler inline (306 bytes, +0x20 to +0x151)
	; Calls real ROM: 0x6069 (video_process), 0x48E6 (hw_init)
	; ================================================================

	mov	a, 0x33
	jnb	acc.2, irq_check_video
	anl	0x33, #0xFB
	lcall	0x6069
	lcall	_irq_register_program

irq_check_video:
	mov	a, 0x32
	jb	acc.3, irq_have_video
	ljmp	irq_done
irq_have_video:
	mov	a, 0x36
	clr	c
	subb	a, #0x06
	jc	irq_state_ok
	ljmp	irq_done
irq_state_ok:
	mov	a, 0x37
	xrl	a, #0x3C
	jz	irq_state_ready
	ljmp	irq_done

irq_state_ready:
	anl	0x32, #0xF7
	mov	a, 0x30
	jb	acc.1, irq_sig_present
	mov	r7, #0x01
	sjmp	irq_check_sm
irq_sig_present:
	mov	r7, #0x00
irq_check_sm:
	mov	a, 0x38
	cjne	a, #0x01, irq_sm_not1
	mov	r6, #0x01
	sjmp	irq_sm_eval
irq_sm_not1:
	mov	r6, #0x00
irq_sm_eval:
	mov	a, r6
	anl	a, r7
	jz	irq_sm_check2
	mov	dptr, #0xDE0C
	mov	a, #0x01
	movx	@dptr, a
	sjmp	irq_hw_config
irq_sm_check2:
	mov	a, 0x38
	jnz	irq_sm_check3
	mov	dptr, #0xDE0C
	movx	a, @dptr
	cjne	a, #0x01, irq_sm_check3
	mov	a, 0x30
	jnb	acc.1, irq_sm_check3
	mov	0x38, #0x02
	mov	a, #0x02
	movx	@dptr, a
	sjmp	irq_hw_config
irq_sm_check3:
	mov	a, 0x38
	cjne	a, #0x02, irq_hw_config
	mov	dptr, #0xDE0C
	movx	a, @dptr
	cjne	a, #0x02, irq_hw_config
	mov	a, 0x30
	jb	acc.1, irq_hw_config
	clr	a
	movx	@dptr, a
	mov	0x38, #0x03

irq_hw_config:
	mov	0x93, #0x03
	setb	0x80
	mov	a, 0x30
	jnb	acc.1, irq_no_signal_change
	anl	0x30, #0xFD
	mov	a, 0x30
	jb	acc.6, irq_do_video_init
	mov	dptr, #0xF1FC
	movx	a, @dptr
	jz	irq_after_video_init
irq_do_video_init:
	anl	0x30, #0xBF
	mov	dptr, #0xF000
	movx	a, @dptr
	orl	a, #0x02
	movx	@dptr, a
	mov	dptr, #0xF1FF
	clr	a
	movx	@dptr, a
	mov	dptr, #0xF1FC
	inc	a
	movx	@dptr, a
	lcall	0x48E6
	mov	0x38, #0x01
irq_after_video_init:
	mov	0x1B, 0xBC
	mov	0x1C, 0xBD
	mov	0x1D, 0xBE
	mov	0x1E, 0xBF
	mov	a, 0x30
	jnb	acc.0, irq_set_bit0
	anl	0x30, #0xFE
	sjmp	irq_no_signal_change
irq_set_bit0:
	orl	0x30, #0x01

irq_no_signal_change:
	mov	a, 0x38
	cjne	a, #0x01, irq_check_state3
	mov	dptr, #0xF1FB
	movx	a, @dptr
	cjne	a, #0x03, irq_check_f1fa
	clr	a
	mov	0x38, a
	sjmp	irq_state3_reset
irq_check_state3:
	mov	a, 0x38
	cjne	a, #0x03, irq_check_f1fa
irq_state3_reset:
	orl	0x30, #0x02
irq_check_f1fa:
	mov	dptr, #0xF1FA
	movx	a, @dptr
	jz	irq_debug_output
	mov	a, #0x01
	movx	@dptr, a
	orl	0x30, #0x40
irq_debug_output:
	mov	0xAE, #0x0C
	mov	0xAE, 0x30
	mov	0xAE, 0x1B
	mov	0xAE, 0x1C
	mov	0xAE, 0x1D
	mov	0xAE, 0x1E
	mov	0xAE, 0xBC
	mov	0xAE, 0xBD
	mov	0xAE, 0xBE
	mov	0xAE, 0xBF
	mov	0xAE, 0x9E
	mov	0xAE, 0x9F
	mov	a, 0x38
	cjne	a, #0x02, irq_check_state3_exit
	mov	dptr, #0xDE0C
	movx	a, @dptr
	cjne	a, #0x02, irq_check_state3_exit
	mov	0xAE, #0xFF
	mov	0xAE, #0xD8
	ret
irq_check_state3_exit:
	mov	a, 0x38
	cjne	a, #0x03, irq_done
	clr	a
	mov	0x38, a
	mov	0xAE, #0xFF
	mov	0xAE, #0xD9
irq_done:
	ret


	; ================================================================
	; +0x152: EDID data (256 bytes)
	; ================================================================
	.db	0x00, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x00
	.db	0x21, 0x57, 0x36, 0x18, 0xBD, 0xE9, 0x02, 0x00
	.db	0x25, 0x1D, 0x01, 0x03, 0x80, 0x35, 0x1D, 0x78
	.db	0x22, 0xEE, 0x91, 0xA3, 0x54, 0x4C, 0x99, 0x26
	.db	0x0F, 0x50, 0x54, 0x21, 0x0F, 0x00, 0x81, 0x00
	.db	0x81, 0x40, 0x81, 0x80, 0x90, 0x40, 0x95, 0x00
	.db	0x01, 0x01, 0xA9, 0x40, 0xB3, 0x00, 0x01, 0x1D
	.db	0x00, 0x72, 0x51, 0xD0, 0x1E, 0x20, 0x6E, 0x28
	.db	0x55, 0x00, 0x0F, 0x48, 0x42, 0x00, 0x00, 0x1E
	.db	0x0E, 0x1F, 0x00, 0x80, 0x51, 0x00, 0x1E, 0x30
	.db	0x40, 0x80, 0x37, 0x00, 0x0F, 0x48, 0x42, 0x00
	.db	0x00, 0x1C, 0x00, 0x00, 0x00, 0x10, 0x00, 0x00
	.db	0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
	.db	0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xFC
	.db	0x00, 0x4D, 0x41, 0x43, 0x52, 0x4F, 0x53, 0x49
	.db	0x4C, 0x49, 0x43, 0x4F, 0x4E, 0x0A, 0x01, 0x19
	.db	0x02, 0x03, 0x34, 0xF1, 0x52, 0x02, 0x11, 0x13
	.db	0x84, 0x1F, 0x10, 0x03, 0x12, 0x06, 0x15, 0x07
	.db	0x16, 0x05, 0x14, 0x5E, 0x5F, 0x63, 0x64, 0x23
	.db	0x09, 0x7F, 0x07, 0x83, 0x01, 0x00, 0x00, 0x6E
	.db	0x03, 0x0C, 0x00, 0x10, 0x00, 0x00, 0x3C, 0x20
	.db	0x00, 0x80, 0x01, 0x02, 0x03, 0x04, 0xE5, 0x0E
	.db	0x61, 0x60, 0x65, 0x66, 0x66, 0x21, 0x50, 0xB0
	.db	0x51, 0x00, 0x1B, 0x30, 0x40, 0x70, 0x36, 0x00
	.db	0x0F, 0x48, 0x42, 0x00, 0x00, 0x1E, 0x66, 0x21
	.db	0x56, 0xAA, 0x51, 0x00, 0x1E, 0x30, 0x46, 0x8F
	.db	0x33, 0x00, 0x0F, 0x48, 0x42, 0x00, 0x00, 0x1E
	.db	0x8C, 0x0A, 0xD0, 0x8A, 0x20, 0xE0, 0x2D, 0x10
	.db	0x10, 0x3E, 0x96, 0x00, 0x10, 0x09, 0x00, 0x00
	.db	0x00, 0x18, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
	.db	0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
	.db	0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xB2

	; +0x252: reg_table (25 bytes)
	.db	0x0A, 0x8B, 0x02, 0x00, 0x05, 0x0A, 0x8B, 0x02
	.db	0x00, 0x15, 0x16, 0x05, 0x00, 0x80, 0x1A, 0x06
	.db	0x00, 0x20, 0xA1, 0x07, 0x00, 0x40, 0x42, 0x0F
	.db	0x00

	; +0x26B: video_config trampoline
	ljmp	_video_config


	; ================================================================
	; Normal hook: mailbox dispatch + ROM command handling
	;
	; The ROM calls this with R7 = command ID. We process our
	; mailbox, then handle the ROM command inline (reimplemented
	; from the stock dispatch at 0xD03A and cmd_handler at 0xD104).
	; ================================================================
_normal_hook_entry:
	push	psw
	push	acc
	push	b
	push	dpl
	push	dph

	mov	dptr, #0xDE0B
	mov	a, r7
	movx	@dptr, a

	; --- Mailbox processing (cmd 2 only) ---
	cjne	r7, #0x02, mbox_skip
	mov	dptr, #0xDE00
	movx	a, @dptr
	jz	mbox_skip
	mov	r6, a		; R6 = mailbox command

	cjne	a, #0x01, mbox_not_01
	mov	dptr, #0xDE0C
	movx	a, @dptr
	mov	dptr, #0xDE04
	movx	@dptr, a
	mov	dptr, #0xF800
	movx	a, @dptr
	mov	dptr, #0xDE05
	movx	@dptr, a
	sjmp	mbox_done
mbox_not_01:
	cjne	a, #0x05, mbox_not_05
	mov	dptr, #0xDE04
	mov	a, 0x80
	movx	@dptr, a
	inc	dptr
	mov	a, 0xA0
	movx	@dptr, a
	inc	dptr
	mov	a, 0xB0
	movx	@dptr, a
	sjmp	mbox_done
mbox_not_05:
	mov	a, r6
	cjne	a, #0xFE, mbox_unknown
	; cmd 0xFE: identify firmware
	lcall	_mbox_identify
	sjmp	mbox_done

mbox_unknown:
	mov	dptr, #0xDE03
	mov	a, #0xFF
	movx	@dptr, a
	sjmp	mbox_clear
mbox_done:
	mov	dptr, #0xDE03
	mov	a, #0x02
	movx	@dptr, a
mbox_clear:
	mov	dptr, #0xDE00
	clr	a
	movx	@dptr, a
mbox_skip:

	; --- ROM command dispatch (reimplemented from 0xD03A table) ---
	mov	a, r7

	; cmd 0x00: init video registers
	jnz	cmd_not_00
	mov	dptr, #0xC781
	mov	a, #0x04
	movx	@dptr, a
	mov	dptr, #0xC783
	mov	a, #0x20
	movx	@dptr, a
	mov	dptr, #0xC782
	mov	a, #0x1C
	movx	@dptr, a
	clr	a
	mov	dptr, #0xDE0C
	movx	@dptr, a
	mov	dptr, #0xF80B
	mov	a, #0xC1
	movx	@dptr, a
	mov	dptr, #0xF814
	mov	a, #0x23
	movx	@dptr, a
	clr	0x0C		; bit 0x21.4
	ljmp	cmd_done
cmd_not_00:

	; cmd 0x01: init video mode
	cjne	a, #0x01, cmd_not_01
	mov	dptr, #0xFE20
	mov	a, #0x2A
	movx	@dptr, a
	lcall	_init_helper
	mov	dptr, #0xC697
	mov	a, #0x02
	movx	@dptr, a
	ljmp	cmd_done
cmd_not_01:

	; cmd 0x02: main loop video processing
	cjne	a, #0x02, cmd_not_02
	lcall	_video_proc_check
	mov	dptr, #0xEFE0
	movx	a, @dptr
	jb	acc.6, cmd02_has_signal
	ljmp	cmd_done
cmd02_has_signal:
	mov	dptr, #0xEFE8
	mov	a, #0x40
	movx	@dptr, a
	inc	dptr
	clr	a
	movx	@dptr, a
	inc	dptr
	movx	@dptr, a
	inc	dptr
	movx	@dptr, a
	mov	dptr, #0xC776
	clr	a
	movx	@dptr, a
	inc	dptr
	mov	a, #0xC8
	movx	@dptr, a
	ljmp	cmd_done
cmd_not_02:

	; cmd 0x08: callback with data table address (tail call)
	cjne	a, #0x08, cmd_not_08
	pop	dph
	pop	dpl
	pop	b
	pop	acc
	pop	psw
	mov	r3, #0xFF
	mov	r2, #0xCD
	mov	r1, #0x52
	ljmp	0xCC10		; callback (tail call, returns to ROM)
cmd_not_08:

	; cmd 0x0A: set F9AF
	cjne	a, #0x0A, cmd_not_0A
	mov	dptr, #0xF9AF
	mov	a, #0x22
	movx	@dptr, a
	ljmp	cmd_done
cmd_not_0A:

	; cmd 0x0B: init video register block
	cjne	a, #0x0B, cmd_not_0B
	mov	dptr, #0xF92C
	mov	a, #0x20
	movx	@dptr, a
	mov	dptr, #0xE33C
	mov	a, #0xF5
	movx	@dptr, a
	inc	dptr
	mov	a, #0x0F
	movx	@dptr, a
	inc	dptr
	clr	a
	movx	@dptr, a
	inc	dptr
	movx	@dptr, a
	mov	dptr, #0xFEBA
	mov	a, #0x08
	movx	@dptr, a
	ljmp	cmd_done
cmd_not_0B:

	; cmd 0x0C: dispatch handler (F9AF, video_adjust) + cmd_handler (FD02/FD03)
	cjne	a, #0x0C, cmd_not_0C_bounce
	sjmp	cmd_is_0C
cmd_not_0C_bounce:
	ljmp	cmd_not_0C
cmd_is_0C:
	; --- Dispatch handler part (from stock 0xD0CE) ---
	jnb	0x00, cmd_0c_skip_adjust	; bit 0x20.0
	lcall	_video_adjust
cmd_0c_skip_adjust:
	mov	dptr, #0xF9AF
	mov	a, #0x22
	movx	@dptr, a
	mov	a, #0x02
	movx	@dptr, a

	; --- Cmd_handler part (from stock 0xD104+) ---
	mov	a, 0x37
	xrl	a, #0x3C
	jz	cmd_0c_state_ok
	ljmp	cmd_done
cmd_0c_state_ok:
	mov	a, 0x36
	clr	c
	subb	a, #0x06
	jc	cmd_0c_range_ok
	ljmp	cmd_done
cmd_0c_range_ok:

	mov	a, 0x36
	cjne	a, #0x01, cmd_0c_not1
	mov	dptr, #0xFD03
	mov	a, #0x09
	movx	@dptr, a
	mov	dptr, #0xFD02
	mov	a, #0x42
	movx	@dptr, a
cmd_0c_not1:
	mov	a, 0x36
	cjne	a, #0x02, cmd_0c_not2
	mov	dptr, #0xFD03
	mov	a, #0x08
	movx	@dptr, a
	mov	dptr, #0xFD02
	mov	a, #0x55
	movx	@dptr, a
cmd_0c_not2:
	mov	a, 0x36
	cjne	a, #0x03, cmd_0c_not3
	mov	dptr, #0xFD03
	mov	a, #0x07
	movx	@dptr, a
	mov	dptr, #0xFD02
	mov	a, #0x25
	movx	@dptr, a
	mov	dptr, #0xF807
	mov	a, #0x0A
	movx	@dptr, a
cmd_0c_not3:
	mov	a, 0x36
	cjne	a, #0x04, cmd_0c_not4
	mov	dptr, #0xFD03
	mov	a, #0x06
	movx	@dptr, a
	mov	dptr, #0xFD02
	mov	a, #0x83
	movx	@dptr, a
	mov	dptr, #0xF807
	mov	a, #0x08
	movx	@dptr, a
cmd_0c_not4:
	mov	a, 0x36
	cjne	a, #0x05, cmd_0c_not5
	mov	dptr, #0xFD03
	mov	a, #0x06
	movx	@dptr, a
	mov	dptr, #0xFD02
	mov	a, #0x49
	movx	@dptr, a
	mov	dptr, #0xF807
	mov	a, #0x09
	movx	@dptr, a
cmd_0c_not5:

	; Tail check: C6B5:C6B6 >= 0x0BB8?
	setb	c
	mov	dptr, #0xC6B6
	movx	a, @dptr
	subb	a, #0xB8
	mov	dptr, #0xC6B5
	movx	a, @dptr
	subb	a, #0x0B
	jnc	cmd_0c_check_c6aa
	ljmp	cmd_done
cmd_0c_check_c6aa:
	mov	dptr, #0xC6AA
	movx	a, @dptr
	jb	acc.0, cmd_0c_write_regs
	ljmp	cmd_done
cmd_0c_write_regs:
	mov	dptr, #0xF92E
	mov	a, #0x22
	movx	@dptr, a
	mov	dptr, #0xF922
	mov	a, #0x82
	movx	@dptr, a
	ljmp	cmd_done
cmd_not_0C:

	; cmd 0x0E: init helper (same as part of cmd 0x01)
	cjne	a, #0x0E, cmd_not_0E
	lcall	_init_helper
	ljmp	cmd_done
cmd_not_0E:

	; cmd 0x0F: clear video registers
	cjne	a, #0x0F, cmd_not_0F
	clr	a
	mov	dptr, #0xC54F
	movx	@dptr, a
	mov	dptr, #0xEFD0
	movx	@dptr, a
	inc	dptr
	mov	a, #0x30
	movx	@dptr, a
	inc	dptr
	clr	a
	movx	@dptr, a
	inc	dptr
	movx	@dptr, a
	ljmp	cmd_done
cmd_not_0F:

	; cmd 0x14: video adjust + delay
	cjne	a, #0x14, cmd_not_14
	lcall	_video_adjust
	mov	r7, #0xFF
	lcall	_delay_helper
	ljmp	cmd_done
cmd_not_14:

	; default: NOP (just return)

cmd_done:
	pop	dph
	pop	dpl
	pop	b
	pop	acc
	pop	psw
	ret


	; ================================================================
	; Helper functions
	; ================================================================

	; _init_helper: ROM 0x603C, write F814, ROM 0x5884
_init_helper:
	lcall	0x603C
	mov	dptr, #0xF814
	mov	a, #0x33
	movx	@dptr, a
	dec	a		; A = 0x32
	movx	@dptr, a
	lcall	0x5884
	ret

	; _delay_helper: DE0A=R7, ROM 0x69FB
_delay_helper:
	mov	dptr, #0xDE0A
	mov	a, r7
	movx	@dptr, a
	lcall	0x69FB
	ret

	; _video_proc_check: check F1F0, copy video adj regs (from 0xD249)
_video_proc_check:
	mov	dptr, #0xF1F0
	movx	a, @dptr
	jnz	vpc_ret
	clr	0xAF		; EA = 0 (disable interrupts)
	mov	a, 0x3B
	anl	a, #0x0F
	jz	vpc_restore_ea
	; Copy video adjustment registers
	mov	dptr, #0xC6A0
	movx	a, @dptr
	mov	dptr, #0xFE90
	movx	@dptr, a
	mov	dptr, #0xC6A2
	movx	a, @dptr
	mov	dptr, #0xFE91
	movx	@dptr, a
	mov	dptr, #0xC6A4
	movx	a, @dptr
	mov	dptr, #0xFE93
	movx	@dptr, a
	mov	dptr, #0xC6A6
	movx	a, @dptr
	mov	dptr, #0xFE92
	movx	@dptr, a
	clr	a
	mov	0x3B, a
vpc_restore_ea:
	setb	0xAF		; EA = 1 (re-enable interrupts)
vpc_ret:
	ret

	; _video_adjust: check signal state, call video_config (from 0xD1B6)
_video_adjust:
	mov	dptr, #0xF806
	mov	a, #0x30
	movx	@dptr, a
	; Read pixel clock: R6:R7 = [C6C6]:[C6C7]
	mov	dptr, #0xC6C6
	movx	a, @dptr
	mov	r6, a
	inc	dptr
	movx	a, @dptr
	mov	r7, a
	; Compare with [C6B1]:[C6B2]
	clr	c
	mov	dptr, #0xC6B2
	movx	a, @dptr
	subb	a, r7
	mov	dptr, #0xC6B1
	movx	a, @dptr
	subb	a, r6
	jc	va_no_signal
	; Check [C6AA] bit 0
	mov	dptr, #0xC6AA
	movx	a, @dptr
	jnb	acc.0, va_no_signal
	; Check IRAM[0x36] and timing thresholds
	mov	a, 0x36
	cjne	a, #0x01, va_not_mode1
	mov	a, 0x37
	setb	c
	subb	a, #0x14
	jc	va_check_mode2
	mov	dptr, #0xC6B5
	movx	a, @dptr
	setb	c
	subb	a, #0x0B
	jnc	va_set_f806_20
va_not_mode1:
	mov	a, 0x36
	cjne	a, #0x02, va_clear_r7
	mov	a, 0x37
	setb	c
	subb	a, #0x0A
	jc	va_clear_r7
	mov	dptr, #0xC6B5
	movx	a, @dptr
	setb	c
	subb	a, #0x0B
	jc	va_clear_r7
va_set_f806_20:
	mov	dptr, #0xF806
	mov	a, #0x20
	movx	@dptr, a
va_check_mode2:
va_clear_r7:
	clr	a
	mov	r7, a
	sjmp	va_call_vc
va_no_signal:
	mov	r7, #0x01
va_call_vc:
	lcall	_video_config
	ret


	; ================================================================
	; Register programming (inline mul16, reads reg_table at 0xCE52)
	; ================================================================
_irq_register_program:
	clr	a
	mov	r7, a
	mov	r6, a
regprog_outer1:
	clr	a
	mov	dptr, #0xDE08
	movx	@dptr, a
	inc	dptr
	movx	@dptr, a
regprog_inner1:
	mov	dptr, #0xDE08
	movx	a, @dptr
	mov	r4, a
	inc	dptr
	movx	a, @dptr
	mov	r5, a
	clr	c
	subb	a, #0x19
	mov	a, r4
	xrl	a, #0x80
	subb	a, #0x80
	jnc	regprog_exit1
	mov	a, r5
	mov	dptr, #0xCE52
	movc	a, @a+dptr
	mov	r5, a
	mov	dptr, #0xDE08
	movx	a, @dptr
	mov	r2, a
	inc	dptr
	movx	a, @dptr
	mov	r3, a
	mov	0x82, r7
	mov	0x83, r6
	mov	a, #0x2E
	mov	0xF0, a
	xch	a, 0x82
	mul	ab
	xch	a, 0x82
	xch	a, 0xF0
	xch	a, 0x83
	mul	ab
	add	a, 0x83
	mov	0x83, a
	mov	a, 0x82
	add	a, r3
	mov	0x82, a
	mov	a, 0x83
	addc	a, r2
	mov	0x83, a
	mov	a, 0x82
	add	a, #0xBF
	mov	0x82, a
	mov	a, 0x83
	addc	a, #0xC0
	mov	0x83, a
	mov	a, r5
	movx	@dptr, a
	mov	dptr, #0xDE09
	movx	a, @dptr
	inc	a
	movx	@dptr, a
	jnz	regprog_inner1
	mov	dptr, #0xDE08
	movx	a, @dptr
	inc	a
	movx	@dptr, a
	sjmp	regprog_inner1
regprog_exit1:
	inc	r7
	cjne	r7, #0x00, regprog_check1
	inc	r6
regprog_check1:
	mov	a, r7
	xrl	a, #0x05
	orl	a, r6
	jnz	regprog_outer1
	mov	r6, #0x00
	mov	r7, #0x05
regprog_outer2:
	clr	a
	mov	dptr, #0xDE08
	movx	@dptr, a
	inc	dptr
	movx	@dptr, a
regprog_inner2:
	mov	dptr, #0xDE08
	movx	a, @dptr
	mov	r4, a
	inc	dptr
	movx	a, @dptr
	mov	r5, a
	clr	c
	subb	a, #0x04
	mov	a, r4
	xrl	a, #0x80
	subb	a, #0x80
	jnc	regprog_exit2
	mov	a, r5
	mov	dptr, #0xCE52
	movc	a, @a+dptr
	mov	r5, a
	mov	dptr, #0xDE08
	movx	a, @dptr
	mov	r2, a
	inc	dptr
	movx	a, @dptr
	mov	r3, a
	mov	0x82, r7
	mov	0x83, r6
	mov	a, #0x2E
	mov	0xF0, a
	xch	a, 0x82
	mul	ab
	xch	a, 0x82
	xch	a, 0xF0
	xch	a, 0x83
	mul	ab
	add	a, 0x83
	mov	0x83, a
	mov	a, 0x82
	add	a, r3
	mov	0x82, a
	mov	a, 0x83
	addc	a, r2
	mov	0x83, a
	mov	a, 0x82
	add	a, #0xBF
	mov	0x82, a
	mov	a, 0x83
	addc	a, #0xC0
	mov	0x83, a
	mov	a, r5
	movx	@dptr, a
	mov	dptr, #0xDE09
	movx	a, @dptr
	inc	a
	movx	@dptr, a
	jnz	regprog_inner2
	mov	dptr, #0xDE08
	movx	a, @dptr
	inc	a
	movx	@dptr, a
	sjmp	regprog_inner2
regprog_exit2:
	inc	r7
	cjne	r7, #0x00, regprog_check2
	inc	r6
regprog_check2:
	mov	a, r7
	xrl	a, #0x0B
	orl	a, r6
	jnz	regprog_outer2
	ret


	; ================================================================
	; Trampolines at fixed CODE addresses
	; Padding fills from code end to each trampoline offset.
	; ================================================================
	; Pad from code end (+0x5FD) to first trampoline (+0x612)
	.ds	(0x612 - 0x5FD)

	; +0x612: mul16 trampoline (ROM calls LCALL 0xD212)
	ljmp	_mul16

	; padding to +0x623
	.ds	(0x623 - 0x615)

	; +0x623: jump_table_engine trampoline
	ljmp	_jump_table_engine

	; +0x626: _mbox_identify fits in the gap before +0x67D
_mbox_identify:
	mov	dptr, #0xDE04
	mov	a, #0x40	; '@'
	movx	@dptr, a
	inc	dptr
	mov	a, #0x6B	; 'k'
	movx	@dptr, a
	inc	dptr
	mov	a, #0x72	; 'r'
	movx	@dptr, a
	inc	dptr
	mov	a, #0x61	; 'a'
	movx	@dptr, a
	inc	dptr
	mov	a, #0x6C	; 'l'
	movx	@dptr, a
	inc	dptr
	mov	a, #0x6E	; 'n'
	movx	@dptr, a
	ret

	; padding to +0x67D
	.ds	(0x67D - 0x641)

	; +0x67D: math_func trampoline
	ljmp	_math_func


	; ================================================================
	; Video config function (after trampolines, called via +0x26B)
	; ================================================================
_video_config:
	.db	0xA9, 0x07, 0x90, 0xC6, 0xC4, 0xE0, 0xFE, 0xA3
	.db	0xE0, 0xFF, 0x90, 0xC6, 0xAF, 0xE0, 0xFC, 0xA3
	.db	0xE0, 0xFD, 0xC3, 0x9F, 0xEC, 0x9E, 0x50, 0x06
	.db	0xAE, 0x04, 0xAF, 0x05, 0x80, 0x00, 0xAB, 0x07
	.db	0xAA, 0x06, 0xD3, 0xEB, 0x94, 0xA0, 0xEA, 0x94
	.db	0x05, 0x40, 0x07, 0xE9, 0x60, 0x04, 0x7A, 0x05
	.db	0x7B, 0xA0, 0x90, 0xF8, 0xE6, 0xEB, 0xF0, 0xEA
	.db	0xF9, 0xA3, 0xF0, 0xD3, 0xED, 0x9B, 0xEC, 0x9A
	.db	0x50, 0x08, 0x90, 0xF8, 0xE1, 0x74, 0x47, 0xF0
	.db	0x80, 0x1F, 0xEB, 0x25, 0xE0, 0xFF, 0xEA, 0x33
	.db	0xFE, 0xD3, 0x90, 0xC6, 0xB0, 0xE0, 0x9F, 0x90
	.db	0xC6, 0xAF, 0xE0, 0x9E, 0x90, 0xF8, 0xE1, 0x50
	.db	0x05, 0x74, 0x4B, 0xF0, 0x80, 0x03, 0x74, 0x53
	.db	0xF0, 0x90, 0xC6, 0xAA, 0xE0, 0x90, 0xF9, 0x26
	.db	0x30, 0xE0, 0x11, 0x74, 0x0F, 0xF0, 0x90, 0xF9
	.db	0x29, 0x74, 0x1F, 0xF0, 0x90, 0xF9, 0x36, 0x74
	.db	0x0F, 0xF0, 0x80, 0x0F, 0x74, 0x05, 0xF0, 0x90
	.db	0xF9, 0x29, 0x74, 0x0B, 0xF0, 0x90, 0xF9, 0x36
	.db	0x74, 0x05, 0xF0, 0x90, 0xF9, 0x25, 0x74, 0xEF
	.db	0xF0, 0x90, 0xF9, 0x28, 0x74, 0xDE, 0xF0, 0x90
	.db	0xF9, 0x35, 0x74, 0xEF, 0xF0, 0x90, 0xF9, 0x47
	.db	0x74, 0x0C, 0xF0, 0x90, 0xF9, 0x4A, 0x74, 0x12
	.db	0xF0, 0xEA, 0xC3, 0x13, 0xEB, 0x13, 0xFD, 0x90
	.db	0xF9, 0x37, 0xF0, 0xEA, 0xC3, 0x13, 0xFF, 0xA3
	.db	0xF0, 0xA3, 0xED, 0xF0, 0xA3, 0xEF, 0xF0, 0x90
	.db	0xFD, 0x40, 0xEB, 0xF0, 0xA3, 0xE9, 0xF0, 0xAF
	.db	0x03, 0xAE, 0x02, 0x90, 0xC6, 0xC4, 0xE0, 0xFC
	.db	0xA3, 0xE0, 0xFD, 0xE4, 0xFB, 0x12, 0xD2, 0x7D
	.db	0x90, 0xFD, 0x3B, 0xEF, 0xF0, 0xEE, 0xA3, 0xF0
	.db	0x90, 0xF8, 0xE0, 0x74, 0x01, 0xF0, 0x90, 0xFD
	.db	0x00, 0xF0, 0x22


	; ================================================================
	; ROM-callable implementations (after trampolines)
	; ================================================================

	; mul16: DPTR = DPTR * A (17 bytes)
_mul16:
	mov	0xF0, a
	xch	a, 0x82
	mul	ab
	xch	a, 0x82
	xch	a, 0xF0
	xch	a, 0x83
	mul	ab
	add	a, 0x83
	mov	0x83, a
	ret

	; jump_table_engine: Keil C51 switch/case (37 bytes)
_jump_table_engine:
	pop	0x83
	pop	0x82
	mov	r0, a
jte_scan:
	clr	a
	movc	a, @a+dptr
	jnz	jte_check_case
	mov	a, #0x01
	movc	a, @a+dptr
	jnz	jte_check_case
	inc	dptr
	inc	dptr
jte_jump:
	movc	a, @a+dptr
	mov	r0, a
	mov	a, #0x01
	movc	a, @a+dptr
	mov	0x82, a
	mov	0x83, r0
	clr	a
	jmp	@a+dptr
jte_check_case:
	mov	a, #0x02
	movc	a, @a+dptr
	xrl	a, r0
	jz	jte_jump
	inc	dptr
	inc	dptr
	inc	dptr
	sjmp	jte_scan

	; math_func: save regs, call ROM 0x52DD (21 bytes)
_math_func:
	mov	dptr, #0xDE00
	mov	a, r6
	movx	@dptr, a
	inc	dptr
	mov	a, r7
	movx	@dptr, a
	inc	dptr
	mov	a, r4
	movx	@dptr, a
	inc	dptr
	mov	a, r5
	movx	@dptr, a
	inc	dptr
	mov	a, r3
	movx	@dptr, a
	lcall	0x52DD
	ret


	.area GSINIT  (CODE)
	.area GSFINAL (CODE)
