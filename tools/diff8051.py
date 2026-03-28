#!/usr/bin/env python3
"""
8051 Firmware Semantic Diff Tool

Compares two 8051 binaries at the function level with three comparison modes:
  - Raw: byte-for-byte match percentage
  - Fuzzy: instruction match with register normalization
  - Semantic: XDATA access pattern matching (collapses MOV DPTR/MOVX sequences)

Usage:
  python3 diff8051.py original.bin compiled.bin [--base 0xC800] [--detail ADDR]

Requires: radare2 (r2)
"""

import subprocess
import re
import json
import argparse
import sys


def disasm_functions(binfile, base=0xC800):
    """Get per-function disassembly from radare2"""
    result = subprocess.run(
        ['r2', '-a', '8051', '-q', '-m', hex(base), '-c', 'aaa; aflj', binfile],
        capture_output=True, text=True, timeout=30
    )
    text = re.sub(r'\x1b\[[0-9;]*m', '', result.stdout).strip()
    try:
        funcs = json.loads(text)
    except json.JSONDecodeError:
        print(f"Warning: r2 returned no functions for {binfile}", file=sys.stderr)
        return {}

    all_funcs = {}
    for f in funcs:
        addr = f['offset']
        size = f['size']
        name = f.get('name', f'fcn_{addr:04x}')

        result2 = subprocess.run(
            ['r2', '-a', '8051', '-q', '-m', hex(base), '-c', f'pD {size} @ {addr}', binfile],
            capture_output=True, text=True, timeout=30
        )
        text2 = re.sub(r'\x1b\[[0-9;]*m', '', result2.stdout).strip()

        instructions = []
        for line in text2.split('\n'):
            m = re.match(r'.*?0x[0-9a-f]+\s+[0-9a-f]+\s+(.*)', line)
            if m:
                instr = m.group(1).strip()
                if instr:
                    instructions.append(instr)

        all_funcs[addr] = (name, size, instructions)

    return all_funcs


def normalize_fuzzy(instr):
    """Fuzzy normalization: replace register names, normalize IRAM addresses"""
    s = re.sub(r'\s*;.*', '', instr.strip())
    s = re.sub(r'\br[0-7]\b', 'Rn', s)
    s = re.sub(r'\b0x([0-7][0-9a-f])\b(?!\.)',
               lambda m: 'IRAM' if int(m.group(1), 16) < 0x80 else m.group(0), s)
    s = re.sub(r'\bacc\b', 'a', s)
    return s


def normalize_semantic(instrs, base=0xC800, code_end=0xCE00):
    """Semantic normalization: collapse XDATA access patterns into operations"""
    ops = []
    i = 0
    while i < len(instrs):
        s = re.sub(r'\s*;.*', '', instrs[i].strip())

        # MOV DPTR,#addr patterns
        if s.startswith('mov dptr') and i + 1 < len(instrs):
            addr_m = re.search(r'#(0x[0-9a-f]+)', s)
            next_s = re.sub(r'\s*;.*', '', instrs[i + 1].strip())

            if addr_m:
                addr_val = addr_m.group(1)
                # MOV DPTR + MOVX A,@DPTR -> READ_XDATA
                if next_s == 'movx a, @dptr':
                    ops.append(f'READ_XDATA({addr_val})')
                    i += 2
                    continue
                # MOV DPTR + MOV A,#val + MOVX @DPTR,A -> WRITE_XDATA
                if next_s.startswith('mov a, #') and i + 2 < len(instrs):
                    val_m = re.search(r'#(0x[0-9a-f]+)', next_s)
                    next2 = re.sub(r'\s*;.*', '', instrs[i + 2].strip())
                    if val_m and next2 == 'movx @dptr, a':
                        ops.append(f'WRITE_XDATA({addr_val}, {val_m.group(1)})')
                        i += 3
                        continue
                # MOV DPTR + MOVX @DPTR,A -> STORE_XDATA
                if next_s == 'movx @dptr, a':
                    ops.append(f'STORE_XDATA({addr_val})')
                    i += 2
                    continue

        # INC DPTR patterns
        if s == 'inc dptr' and i + 1 < len(instrs):
            next_s = re.sub(r'\s*;.*', '', instrs[i + 1].strip())
            if next_s == 'movx a, @dptr':
                ops.append('READ_XDATA(+1)')
                i += 2
                continue
            if next_s == 'movx @dptr, a':
                ops.append('STORE_XDATA(+1)')
                i += 2
                continue
            if next_s.startswith('mov a, #') and i + 2 < len(instrs):
                val_m = re.search(r'#(0x[0-9a-f]+)', next_s)
                next2 = re.sub(r'\s*;.*', '', instrs[i + 2].strip())
                if val_m and next2 == 'movx @dptr, a':
                    ops.append(f'WRITE_XDATA(+1, {val_m.group(1)})')
                    i += 3
                    continue

        # Normalize and keep
        s = re.sub(r'\br[0-7]\b', 'Rn', s)
        s = re.sub(r'\b0x([0-7][0-9a-f])\b(?!\.)',
                   lambda m: 'IRAM' if int(m.group(1), 16) < 0x80 else m.group(0), s)
        s = re.sub(r'\bacc\b', 'a', s)

        # Normalize internal calls/jumps
        for pattern, label in [('lcall', 'CALL_INTERNAL'), ('ljmp', 'JMP_INTERNAL')]:
            m = re.match(rf'{pattern} (0x[0-9a-f]+|fcn\.\w+)', s)
            if m:
                target = m.group(1)
                if target.startswith('fcn.') or (target.startswith('0x') and
                        base <= int(target, 16) <= code_end):
                    ops.append(label)
                    i += 1
                    break
        else:
            ops.append(s)
            i += 1
            continue
        i += 1

    return ops


def lcs_match(seq_a, seq_b):
    """Count longest common subsequence matches (greedy, not optimal LCS)"""
    bi = 0
    matches = 0
    for a in seq_a:
        for j in range(bi, len(seq_b)):
            if seq_b[j] == a:
                matches += 1
                bi = j + 1
                break
    return matches


def compare(orig_file, comp_file, base=0xC800):
    """Compare two binaries and return per-function results"""
    with open(orig_file, 'rb') as f:
        orig_bytes = f.read()
    with open(comp_file, 'rb') as f:
        comp_bytes = f.read()

    orig_funcs = disasm_functions(orig_file, base)
    comp_funcs = disasm_functions(comp_file, base)

    results = []
    for addr in sorted(orig_funcs):
        name, size, orig_instrs = orig_funcs[addr]
        orig_sem = normalize_semantic(orig_instrs, base)

        # Raw byte match
        ob = orig_bytes[addr - base:(addr - base) + size]
        best_raw = 0
        for i in range(len(comp_bytes) - size + 1):
            rm = sum(1 for j in range(size) if comp_bytes[i + j] == ob[j])
            best_raw = max(best_raw, rm)

        # Semantic match against all compiled functions
        best_sem = 0
        best_caddr = None
        for caddr in comp_funcs:
            _, _, comp_instrs = comp_funcs[caddr]
            comp_sem = normalize_semantic(comp_instrs, base)
            score = lcs_match(orig_sem, comp_sem) / max(len(orig_sem), 1)
            if score > best_sem:
                best_sem = score
                best_caddr = caddr

        results.append({
            'addr': addr,
            'name': name,
            'size': size,
            'raw_pct': 100 * best_raw / size if size > 0 else 0,
            'sem_pct': 100 * best_sem,
            'best_match': best_caddr,
            'orig_sem': orig_sem,
        })

    return results, orig_funcs, comp_funcs


def print_summary(results, orig_file, comp_file):
    """Print comparison summary table"""
    with open(orig_file, 'rb') as f:
        orig_size = len(f.read())
    with open(comp_file, 'rb') as f:
        comp_size = len(f.read())

    print(f"Original: {orig_file} ({orig_size} bytes)")
    print(f"Compiled: {comp_file} ({comp_size} bytes, {comp_size - orig_size:+d})")
    print()
    print(f"{'Function':<28s} {'Sz':>4s} {'Raw':>4s} {'Semantic':>8s}  Notes")
    print("-" * 75)

    for r in results:
        notes = ""
        if r['raw_pct'] == 100:
            notes = "BYTE-IDENTICAL"
        elif r['sem_pct'] >= 95:
            notes = "semantically identical"
        elif r['sem_pct'] >= 80:
            notes = "near-identical logic"
        elif r['sem_pct'] >= 60:
            notes = "good match"
        elif r['sem_pct'] >= 40:
            notes = "partial"

        print(f"  0x{r['addr']:04X} {r['name']:<20s} {r['size']:>4d} {r['raw_pct']:>3.0f}% "
              f"{r['sem_pct']:>6.0f}%  {notes}")


def print_detail(addr, results, orig_funcs, comp_funcs, base=0xC800):
    """Print detailed semantic diff for a specific function"""
    r = next((r for r in results if r['addr'] == addr), None)
    if not r:
        print(f"Function at 0x{addr:04X} not found")
        return

    caddr = r['best_match']
    if caddr is None:
        print(f"No matching compiled function found")
        return

    _, _, orig_instrs = orig_funcs[addr]
    _, _, comp_instrs = comp_funcs[caddr]

    orig_sem = normalize_semantic(orig_instrs, base)
    comp_sem = normalize_semantic(comp_instrs, base)

    print(f"Original 0x{addr:04X} ({len(orig_sem)} ops) vs Compiled 0x{caddr:04X} ({len(comp_sem)} ops)")
    print(f"Semantic match: {r['sem_pct']:.0f}%")
    print()

    maxlen = max(len(orig_sem), len(comp_sem))
    print(f"  {'Original':<40s}  {'Compiled':<40s}  Eq")
    for i in range(maxlen):
        o = orig_sem[i] if i < len(orig_sem) else ""
        c = comp_sem[i] if i < len(comp_sem) else ""
        eq = "=" if o == c else " "
        print(f"  {o:<40s}  {c:<40s}  {eq}")


def main():
    parser = argparse.ArgumentParser(description='8051 Firmware Semantic Diff Tool')
    parser.add_argument('original', help='Original binary')
    parser.add_argument('compiled', help='Compiled binary to compare')
    parser.add_argument('--base', type=lambda x: int(x, 16), default=0xC800,
                        help='Code base address (hex, default: 0xC800)')
    parser.add_argument('--detail', type=lambda x: int(x, 16),
                        help='Show detailed diff for function at this address (hex)')
    args = parser.parse_args()

    results, orig_funcs, comp_funcs = compare(args.original, args.compiled, args.base)
    print_summary(results, args.original, args.compiled)

    if args.detail:
        print()
        print_detail(args.detail, results, orig_funcs, comp_funcs, args.base)


if __name__ == '__main__':
    main()
