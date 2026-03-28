┌ 3: fcn.0000c830 ();
└       ┌─< 0x0000c830      02c843         ljmp loc.0000c843
        │   ; CALL XREF from fcn.0000c97e @ +0x32
┌ 12: fcn.0000c833 ();
│       │   0x0000c833      ec             mov a, r4
│       │   0x0000c834      f0             movx @dptr, a
│       │   0x0000c835      a3             inc dptr
│       │   0x0000c836      ed             mov a, r5
│       │   0x0000c837      f0             movx @dptr, a
│       │   0x0000c838      a3             inc dptr
│       │   0x0000c839      ee             mov a, r6
│       │   0x0000c83a      f0             movx @dptr, a
│       │   0x0000c83b      a3             inc dptr
│       │   0x0000c83c      ef             mov a, r7
│       │   0x0000c83d      f0             movx @dptr, a
└       │   0x0000c83e      22             ret
        │   0x0000c83f      ff             mov r7, a
       ┌──< 0x0000c840      02c943         ljmp 0xc943
       ││   ; CODE XREF from fcn.0000c830 @ 0xc830
├ 27: loc.0000c843 ();
│      │└─> 0x0000c843      53b03f         anl p3, #0x3f               ; [0x100001b0:1]=0
│      │    0x0000c846      53b13f         anl 0xb1, #0x3f             ; [0x100001b1:1]=0
│      │    0x0000c849      e4             clr a
│      │    0x0000c84a      90de0a         mov dptr, #0xde0a           ; [0x2000de0a:1]=0
│      │    0x0000c84d      f0             movx @dptr, a
│      │    0x0000c84e      d20d           setb 0x21.5                 ; [0x10000021:1]=0
│      │    0x0000c850      753104         mov 0x31, #0x04             ; [0x10000031:1]=0
│      │    0x0000c853      90dfdf         mov dptr, #0xdfdf           ; [0x2000dfdf:1]=0
│      │    0x0000c856      7444           mov a, #0x44                ; 'D'
│      │    0x0000c858      f0             movx @dptr, a
│      │    0x0000c859      a3             inc dptr
│      │    0x0000c85a      7457           mov a, #0x57                ; 'W'
│      │    0x0000c85c      f0             movx @dptr, a
└      │    0x0000c85d      22             ret
       ─┌─> 0x0000c85e      80fe           sjmp 0xc85e
      ┌───< 0x0000c860      02c903         ljmp 0xc903
      ││╎   ; CALL XREF from fcn.0000c863 @ +0xdc
┌ 160: fcn.0000c863 ();
│     ││╎   0x0000c863      e4             clr a
│     ││╎   0x0000c864      f593           mov 0x93, a                 ; [0x10000193:1]=0
│     ││╎   0x0000c866      e580           mov a, p0                   ; [0x10000180:1]=0
│    ┌────< 0x0000c868      30e205         jnb acc.2, 0xc870           ; [0x100001e0:1]=0
│    │││╎   0x0000c86b      5380fb         anl p0, #0xfb               ; [0x10000180:1]=0
│    │││╎   0x0000c86e      c20b           clr 0x21.3                  ; [0x10000021:1]=0
│    │││╎   ; CODE XREF from fcn.0000c863 @ 0xc868
│    └────> 0x0000c870      e580           mov a, p0                   ; [0x10000180:1]=0
│    ┌────< 0x0000c872      30e405         jnb acc.4, 0xc87a           ; [0x100001e0:1]=0
│    │││╎   0x0000c875      438080         orl p0, #0x80               ; [0x10000180:1]=0
│    │││╎   0x0000c878      c20b           clr 0x21.3                  ; [0x10000021:1]=0
│    │││╎   ; CODE XREF from fcn.0000c863 @ 0xc872
│    └────> 0x0000c87a      e54c           mov a, 0x4c                 ; [0x1000004c:1]=0
│     ││╎   0x0000c87c      f4             cpl a
│    ┌────< 0x0000c87d      601e           jz 0xc89d
│    │││╎   0x0000c87f      854c94         mov 0x94, 0x4c              ; [0x1000004c:1]=0
│    │││╎   0x0000c882      e54b           mov a, 0x4b                 ; [0x1000004b:1]=0
│   ┌─────< 0x0000c884      7009           jnz 0xc88f
│   ││││╎   0x0000c886      e54c           mov a, 0x4c                 ; [0x1000004c:1]=0
│  ┌──────< 0x0000c888      6005           jz 0xc88f
│  │││││╎   0x0000c88a      754b01         mov 0x4b, #0x01             ; [0x1000004b:1]=0
│ ┌───────< 0x0000c88d      800b           sjmp 0xc89a
│ ││││││╎   ; CODE XREFS from fcn.0000c863 @ 0xc884, 0xc888
│ │└└─────> 0x0000c88f      e54b           mov a, 0x4b                 ; [0x1000004b:1]=0
│ │ ┌─────< 0x0000c891      b40106         cjne a, #0x01, 0xc89a
│ │ ││││╎   0x0000c894      e54c           mov a, 0x4c                 ; [0x1000004c:1]=0
│ │┌──────< 0x0000c896      7002           jnz 0xc89a
│ ││││││╎   0x0000c898      f54b           mov 0x4b, a                 ; [0x1000004b:1]=0
│ ││││││╎   ; CODE XREFS from fcn.0000c863 @ 0xc88d, 0xc891, 0xc896
│ └└└─────> 0x0000c89a      754cff         mov 0x4c, #0xff             ; [0x1000004c:1]=0
│    │││╎   ; CODE XREF from fcn.0000c863 @ 0xc87d
│   ┌└────> 0x0000c89d      300a06         jnb 0x21.2, 0xc8a6          ; [0x10000021:1]=0
│   │ ││╎   0x0000c8a0      d20c           setb 0x21.4                 ; [0x10000021:1]=0
│   │ ││╎   0x0000c8a2      c20a           clr 0x21.2                  ; [0x10000021:1]=0
│   │ ││╎   0x0000c8a4      d20b           setb 0x21.3                 ; [0x10000021:1]=0
│   │ ││╎   ; CODE XREF from fcn.0000c863 @ 0xc89d
│   └┌────< 0x0000c8a6      308026         jnb p0.0, 0xc8cf            ; [0x10000180:1]=0
│    │││╎   0x0000c8a9      90de0a         mov dptr, #0xde0a           ; [0x2000de0a:1]=0
│    │││╎   0x0000c8ac      e0             movx a, @dptr
│   ┌─────< 0x0000c8ad      6019           jz 0xc8c8
│   ││││╎   0x0000c8af      e4             clr a
│   ││││╎   0x0000c8b0      f0             movx @dptr, a
│   ││││╎   0x0000c8b1      e53f           mov a, 0x3f                 ; [0x1000003f:1]=0
│  ┌──────< 0x0000c8b3      b42121         cjne a, #0x21, 0xc8d7
│  │││││╎   0x0000c8b6      e540           mov a, 0x40                 ; [0x10000040:1]=0
│ ┌───────< 0x0000c8b8      b4091c         cjne a, #0x09, 0xc8d7
│ ││││││╎   0x0000c8bb      e546           mov a, 0x46                 ; [0x10000046:1]=0
│ ││││││╎   0x0000c8bd      6408           xrl a, #0x08
│ ││││││╎   0x0000c8bf      4545           orl a, 0x45                 ; [0x10000045:1]=0
│ ────────< 0x0000c8c1      7014           jnz 0xc8d7
│ ││││││╎   0x0000c8c3      12c97e         lcall fcn.0000c97e
│ ────────< 0x0000c8c6      800f           sjmp 0xc8d7
│ ││││││╎   ; CODE XREF from fcn.0000c863 @ 0xc8ad
│ ││└─────> 0x0000c8c8      1258b9         lcall 0x58b9
│ ││ │││╎   0x0000c8cb      d20b           setb 0x21.3                 ; [0x10000021:1]=0
│ ││┌─────< 0x0000c8cd      8008           sjmp 0xc8d7
│ ││││││╎   ; CODE XREF from fcn.0000c863 @ 0xc8a6
│ │││└────> 0x0000c8cf      e54a           mov a, 0x4a                 ; [0x1000004a:1]=0
│ │││ ││╎   0x0000c8d1      4549           orl a, 0x49                 ; [0x10000049:1]=0
│ │││┌────< 0x0000c8d3      6002           jz 0xc8d7
│ ││││││╎   0x0000c8d5      d20b           setb 0x21.3                 ; [0x10000021:1]=0
│ ││││││╎   ; XREFS: CODE 0x0000c8b3  CODE 0x0000c8b8  CODE 0x0000c8c1  
│ ││││││╎   ; XREFS: CODE 0x0000c8c6  CODE 0x0000c8cd  CODE 0x0000c8d3  
│ └└└└────> 0x0000c8d7      300b28         jnb 0x21.3, 0xc902          ; [0x10000021:1]=0
│     ││╎   0x0000c8da      e4             clr a
│     ││╎   0x0000c8db      f593           mov 0x93, a                 ; [0x10000193:1]=0
│     ││╎   0x0000c8dd      e53f           mov a, 0x3f                 ; [0x1000003f:1]=0
│    ┌────< 0x0000c8df      b4211b         cjne a, #0x21, 0xc8fd
│    │││╎   0x0000c8e2      e540           mov a, 0x40                 ; [0x10000040:1]=0
│   ┌─────< 0x0000c8e4      b40916         cjne a, #0x09, 0xc8fd
│   ││││╎   0x0000c8e7      e546           mov a, 0x46                 ; [0x10000046:1]=0
│   ││││╎   0x0000c8e9      6408           xrl a, #0x08
│   ││││╎   0x0000c8eb      4545           orl a, 0x45                 ; [0x10000045:1]=0
│  ┌──────< 0x0000c8ed      700e           jnz 0xc8fd
│  │││││╎   0x0000c8ef      90de0a         mov dptr, #0xde0a           ; [0x2000de0a:1]=0
│  │││││╎   0x0000c8f2      04             inc a
│  │││││╎   0x0000c8f3      f0             movx @dptr, a
│  │││││╎   0x0000c8f4      e4             clr a
│  │││││╎   0x0000c8f5      90c612         mov dptr, #0xc612           ; [0x2000c612:1]=0
│  │││││╎   0x0000c8f8      f0             movx @dptr, a
│  │││││╎   0x0000c8f9      d286           setb p0.6                   ; [0x10000180:1]=0
│ ┌───────< 0x0000c8fb      8003           sjmp 0xc900
│ ││││││╎   ; CODE XREFS from fcn.0000c863 @ 0xc8df, 0xc8e4, 0xc8ed
│ │└└└────> 0x0000c8fd      122da2         lcall 0x2da2
│ │   ││╎   ; CODE XREF from fcn.0000c863 @ 0xc8fb
│ └───────> 0x0000c900      c20b           clr 0x21.3                  ; [0x10000021:1]=0
│     ││╎   ; CODE XREF from fcn.0000c863 @ 0xc8d7
└ ────────> 0x0000c902      22             ret
      ││╎   ; CODE XREF from loc.0000c843 @ +0x1d
      └───> 0x0000c903      e536           mov a, 0x36                 ; [0x10000036:1]=0
      ┌───< 0x0000c905      30e22f         jnb acc.2, 0xc937           ; [0x100001e0:1]=0
      ││╎   0x0000c908      1266bd         lcall 0x66bd
      ││╎   0x0000c90b      90f880         mov dptr, #0xf880           ; [0x2000f880:1]=0
      ││╎   0x0000c90e      7410           mov a, #0x10
      ││╎   0x0000c910      f0             movx @dptr, a
      ││╎   0x0000c911      90f005         mov dptr, #0xf005           ; [0x2000f005:1]=0
      ││╎   0x0000c914      e0             movx a, @dptr
      ││╎   0x0000c915      54f7           anl a, #0xf7
      ││╎   0x0000c917      f0             movx @dptr, a
      ││╎   0x0000c918      90f020         mov dptr, #0xf020           ; [0x2000f020:1]=0
      ││╎   0x0000c91b      e0             movx a, @dptr
      ││╎   0x0000c91c      54fe           anl a, #0xfe
      ││╎   0x0000c91e      f0             movx @dptr, a
      ││╎   0x0000c91f      90c343         mov dptr, #0xc343           ; [0x2000c343:1]=0
      ││╎   0x0000c922      7460           mov a, #0x60                ; '`'
      ││╎   0x0000c924      f0             movx @dptr, a
      ││╎   0x0000c925      90c347         mov dptr, #0xc347           ; [0x2000c347:1]=0
      ││╎   0x0000c928      7402           mov a, #0x02
      ││╎   0x0000c92a      f0             movx @dptr, a
      ││╎   0x0000c92b      a3             inc dptr
      ││╎   0x0000c92c      04             inc a
      ││╎   0x0000c92d      f0             movx @dptr, a
      ││╎   0x0000c92e      90c4da         mov dptr, #0xc4da           ; [0x2000c4da:1]=0
      ││╎   0x0000c931      740d           mov a, #0x0d
      ││╎   0x0000c933      f0             movx @dptr, a
      ││╎   0x0000c934      5336fb         anl 0x36, #0xfb             ; [0x10000036:1]=0
      ││╎   ; CODE XREF from fcn.0000c863 @ +0xa2
      └───> 0x0000c937      e535           mov a, 0x35                 ; [0x10000035:1]=0
      ┌───< 0x0000c939      30e006         jnb acc.0, 0xc942           ; [0x100001e0:1]=0
      ││╎   0x0000c93c      5335fe         anl 0x35, #0xfe             ; [0x10000035:1]=0
      ││╎   0x0000c93f      12c863         lcall fcn.0000c863
      ││╎   ; CODE XREF from fcn.0000c863 @ +0xd6
      └───> 0x0000c942      22             ret
       │╎   ; CODE XREF from fcn.0000c833 @ +0xd
       └──> 0x0000c943      125d16         lcall 0x5d16
        ╎   0x0000c946      7820           mov r0, #0x20
        ╎   0x0000c948      e6             mov a, @r0
        ╎   0x0000c949      4401           orl a, #0x01
        ╎   0x0000c94b      f6             mov @r0, a
        ╎   0x0000c94c      127335         lcall 0x7335
        ╎   0x0000c94f      c2b9           clr ip.1                    ; [0x100001b8:1]=0
        ╎   ; CODE XREF from fcn.0000c863 @ +0x119
       ┌──> 0x0000c951      c2a8           clr ie.0                    ; [0x100001a8:1]=0
       ╎╎   0x0000c953      7f32           mov r7, #0x32               ; '2'
       ╎╎   0x0000c955      12c9b7         lcall fcn.0000c9b7
       ╎╎   0x0000c958      123a5c         lcall 0x3a5c
       ╎╎   0x0000c95b      d2a8           setb ie.0                   ; [0x100001a8:1]=0
       ╎╎   0x0000c95d      124e8d         lcall 0x4e8d
       ╎╎   0x0000c960      90ddff         mov dptr, #0xddff           ; [0x2000ddff:1]=0
       ╎╎   0x0000c963      e0             movx a, @dptr
      ┌───< 0x0000c964      b45a05         cjne a, #0x5a, 0xc96c
      │╎╎   0x0000c967      e4             clr a
      │╎╎   0x0000c968      f0             movx @dptr, a
      │╎╎   0x0000c969      1267d1         lcall 0x67d1
      │╎╎   ; CODE XREF from fcn.0000c863 @ +0x101
      └───> 0x0000c96c      90f031         mov dptr, #0xf031           ; [0x2000f031:1]=0
       ╎╎   0x0000c96f      743f           mov a, #0x3f                ; '?'
       ╎╎   0x0000c971      f0             movx @dptr, a
       ╎╎   0x0000c972      a3             inc dptr
       ╎╎   0x0000c973      e4             clr a
       ╎╎   0x0000c974      f0             movx @dptr, a
       ╎╎   0x0000c975      90f160         mov dptr, #0xf160           ; [0x2000f160:1]=0
       ╎╎   0x0000c978      e0             movx a, @dptr
       ╎╎   0x0000c979      54fd           anl a, #0xfd
       ╎╎   0x0000c97b      f0             movx @dptr, a
       └──< 0x0000c97c      80d3           sjmp 0xc951
        ╎   ; CALL XREF from fcn.0000c863 @ 0xc8c3
┌ 37: fcn.0000c97e ();
│       ╎   0x0000c97e      e4             clr a
│       ╎   0x0000c97f      f593           mov 0x93, a                 ; [0x10000193:1]=0
│       ╎   0x0000c981      85ab55         mov 0x55, 0xab              ; [0x100001ab:1]=0
│       ╎   0x0000c984      85ab56         mov 0x56, 0xab              ; [0x100001ab:1]=0
│       ╎   0x0000c987      85ab57         mov 0x57, 0xab              ; [0x100001ab:1]=0
│       ╎   0x0000c98a      85ab58         mov 0x58, 0xab              ; [0x100001ab:1]=0
│       ╎   0x0000c98d      85ab59         mov 0x59, 0xab              ; [0x100001ab:1]=0
│       ╎   0x0000c990      85ab5a         mov 0x5a, 0xab              ; [0x100001ab:1]=0
│       ╎   0x0000c993      85ab5b         mov 0x5b, 0xab              ; [0x100001ab:1]=0
│       ╎   0x0000c996      85ab5c         mov 0x5c, 0xab              ; [0x100001ab:1]=0
│       ╎   0x0000c999      c208           clr 0x21.0                  ; [0x10000021:1]=0
│       ╎   0x0000c99b      d283           setb p0.3                   ; [0x10000180:1]=0
│       ╎   0x0000c99d      d286           setb p0.6                   ; [0x10000180:1]=0
│       ╎   0x0000c99f      120ba1         lcall 0x0ba1
└       ╎   0x0000c9a2      22             ret
        ╎   0x0000c9a3      90de04         mov dptr, #0xde04           ; [0x2000de04:1]=0
        ╎   0x0000c9a6      e0             movx a, @dptr
        ╎   0x0000c9a7      8f82           mov dpl, r7                 ; [0x10000182:1]=0
        ╎   0x0000c9a9      8e83           mov dph, r6                 ; [0x10000183:1]=0
        ╎   0x0000c9ab      f0             movx @dptr, a
        ╎   0x0000c9ac      22             ret
        ╎   0x0000c9ad      90de05         mov dptr, #0xde05           ; [0x2000de05:1]=0
        ╎   0x0000c9b0      12c833         lcall fcn.0000c833
        ╎   0x0000c9b3      1265cb         lcall 0x65cb
        ╎   0x0000c9b6      22             ret
        ╎   ; CALL XREF from fcn.0000c863 @ +0xf2
┌ 9: fcn.0000c9b7 ();
│       ╎   0x0000c9b7      90de09         mov dptr, #0xde09           ; [0x2000de09:1]=0
│       ╎   0x0000c9ba      ef             mov a, r7
│       ╎   0x0000c9bb      f0             movx @dptr, a
│       ╎   0x0000c9bc      1263a4         lcall 0x63a4
└       ╎   0x0000c9bf      22             ret
        ╎   0x0000c9c0      8f82           mov dpl, r7                 ; [0x10000182:1]=0
        ╎   0x0000c9c2      8e83           mov dph, r6                 ; [0x10000183:1]=0
        ╎   0x0000c9c4      e0             movx a, @dptr
        ╎   0x0000c9c5      ff             mov r7, a
        ╎   0x0000c9c6      22             ret
        ╎   0x0000c9c7      75815c         mov sp, #0x5c               ; '\\'
        ╎                                                              ; [0x10000181:1]=0
        └─< 0x0000c9ca      02c85e         ljmp 0xc85e
