#!/usr/bin/env python3
"""原地修改 ELF64 DT_NEEDED 条目（缩短替换，dynstr 留空洞无害）。
用法: patch_needed.py <文件>"""
import struct
import sys

NEEDED_MAP = {
    b'libc.so.6': b'libc.so',
    b'libm.so.6': b'libm.so',
    b'libgcc_s.so.1': b'libgcc_s.so',
    b'libstdc++.so.6': b'libstdcpp.so',
    b'libicuuc.so.70': b'libicuuc.so',
    b'libicudata.so.70': b'libicudata.so',
    b'libicui18n.so.70': b'libicui18n.so',
    b'libcapstone.so.4': b'libcapstone.so',
    b'ld-linux-aarch64.so.1': b'libldlinux.so',
}

def patch(path):
    data = bytearray(open(path, 'rb').read())
    if data[:4] != b'\x7fELF' or data[4] != 2:
        raise SystemExit(f'{path}: 不是 ELF64')
    e_phoff = struct.unpack_from('<Q', data, 0x20)[0]
    e_phentsize = struct.unpack_from('<H', data, 0x36)[0]
    e_phnum = struct.unpack_from('<H', data, 0x38)[0]

    dyn_vaddr = dyn_filesz = None
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        p_type = struct.unpack_from('<I', data, off)[0]
        if p_type == 2:
            dyn_vaddr = struct.unpack_from('<Q', data, off + 0x10)[0]
            dyn_filesz = struct.unpack_from('<Q', data, off + 0x20)[0]

    if dyn_vaddr is None:
        raise SystemExit(f'{path}: 无 PT_DYNAMIC')

    loads = []
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        p_type = struct.unpack_from('<I', data, off)[0]
        if p_type == 1:
            p_offset = struct.unpack_from('<Q', data, off + 0x08)[0]
            p_vaddr = struct.unpack_from('<Q', data, off + 0x10)[0]
            p_filesz = struct.unpack_from('<Q', data, off + 0x20)[0]
            loads.append((p_vaddr, p_offset, p_filesz))

    def v2o(vaddr):
        for pv, po, pf in loads:
            if pv <= vaddr < pv + pf:
                return po + (vaddr - pv)
        raise SystemExit(f'{path}: vaddr {vaddr:#x} 不在任何 PT_LOAD')

    dyn_off = v2o(dyn_vaddr)
    n_entries = dyn_filesz // 16
    needed_offsets = []
    strtab_vaddr = None
    for i in range(n_entries):
        d_tag, d_val = struct.unpack_from('<qQ', data, dyn_off + i * 16)
        if d_tag == 1:
            needed_offsets.append(d_val)
        elif d_tag == 5:
            strtab_vaddr = d_val

    if strtab_vaddr is None:
        raise SystemExit(f'{path}: 无 DT_STRTAB')
    strtab_off = v2o(strtab_vaddr)

    changed = []
    for stroff in needed_offsets:
        pos = strtab_off + stroff
        end = data.find(b'\x00', pos)
        old = bytes(data[pos:end])
        if old in NEEDED_MAP:
            new = NEEDED_MAP[old]
            if len(new) > len(old):
                raise SystemExit(f'{path}: 新串更长: {old} -> {new}')
            changed.append((old.decode(), new.decode()))
            data[pos:pos + len(new)] = new
            # 旧串残留字符清零（end 是原 NUL 位置，保持不动；end+1 是相邻字符串，绝不能动）
            for j in range(pos + len(new), end):
                data[j] = 0

    if changed:
        open(path, 'wb').write(data)
    print(f'{path}: 已修改 {len(changed)} 项')
    return changed

if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit('用法: patch_needed.py <文件>')
    patch(sys.argv[1])
