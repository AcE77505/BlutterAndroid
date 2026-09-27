#!/usr/bin/env python3
# 全版本批量构建：dartvm 交叉编译(glibc) -> 宏检测 -> blutter 动态链接 -> strip -> 部署目录
# 用法: python3 build_all_glibc.py [版本...]   (不传 = 全部)
import os
import shutil
import subprocess
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
SDK_DIR = os.path.join(SCRIPT_DIR, 'dartsdk')
sys.path.insert(0, SCRIPT_DIR)
from build_dartvm_glibc import prepare, cmake_dart_glibc
from blutter import find_compat_macro

GLIBC_CC = '/home/ace77505/blutter/ndk_out/toolchain/aarch64-linux-gnu-clang-glibc'
GLIBC_CXX = '/home/ace77505/blutter/ndk_out/toolchain/aarch64-linux-gnu-clang++-glibc'
LLVM_STRIP = '/home/ace77505/android-ndk-r27c/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-strip'
DEPLOY = os.path.join(SCRIPT_DIR, 'bin', 'blutter_android')

os.makedirs(DEPLOY, exist_ok=True)
os.environ['LD_LIBRARY_PATH'] = '/home/ace77505/blutter/ndk_out/toolchain/usr/lib/x86_64-linux-gnu:' + os.environ.get('LD_LIBRARY_PATH', '')


def build_blutter(ver, macros, jobs):
    blutter_dir = os.path.join(SCRIPT_DIR, 'blutter')
    builddir = os.path.join(blutter_dir, f'build_glibc_{ver}')
    if os.path.exists(builddir):
        shutil.rmtree(builddir)
    libname = f'dartvm{ver}_android_arm64'
    cmd = ['cmake', '-B', builddir,
           '-DCMAKE_SYSTEM_NAME=Linux', '-DCMAKE_SYSTEM_PROCESSOR=aarch64',
           '-DCMAKE_C_COMPILER=' + GLIBC_CC, '-DCMAKE_CXX_COMPILER=' + GLIBC_CXX,
           '-DCMAKE_BUILD_TYPE=Release', '-DDARTLIB=' + libname] + macros
    subprocess.run(cmd, cwd=blutter_dir, check=True)
    subprocess.run(['make', '-j' + str(jobs)], cwd=builddir, check=True)
    src = os.path.join(builddir, 'blutter_' + libname)
    dst = os.path.join(DEPLOY, 'blutter_' + libname)
    subprocess.run([LLVM_STRIP, '-o', dst, src], check=True)
    return dst


def main():
    if len(sys.argv) > 1:
        versions = [a for a in sys.argv[1:] if not a.startswith('-')]
    else:
        versions = sorted([d[1:] for d in os.listdir(SDK_DIR) if d.startswith('v')],
                          key=lambda v: [int(x) for x in v.split('.')])
    jobs = int(os.environ.get('JOBS', '12'))
    ok, fail = [], []
    t0 = time.time()
    for ver in versions:
        libname = f'dartvm{ver}_android_arm64'
        try:
            info = type('Info', (), {'version': ver, 'os_name': 'android', 'arch': 'arm64',
                                     'has_compressed_ptrs': True, 'lib_name': libname})()
            # 1) dartvm 静态库 (glibc)
            outdir = prepare(info)
            cmake_dart_glibc(info, outdir, jobs)
            # 2) 兼容宏自动检测
            macros = find_compat_macro(ver, False)
            print(f'[{ver}] 宏: {macros}', flush=True)
            # 3) blutter 动态链接 + strip + 部署
            dst = build_blutter(ver, macros, jobs)
            ok.append(ver)
            print(f'===== {ver} OK -> {os.path.basename(dst)} ({(time.time()-t0)/60:.1f}min) =====', flush=True)
        except Exception as e:
            fail.append((ver, str(e)))
            print(f'!!!!! {ver} FAIL: {e}', flush=True)
    print(f'===== 全部完成: OK {len(ok)} / FAIL {len(fail)} / 总耗时 {(time.time()-t0)/60:.1f}min =====', flush=True)
    print('OK:', ' '.join(ok), flush=True)
    if fail:
        for v, e in fail:
            print(f'  FAIL {v}: {e}', flush=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
