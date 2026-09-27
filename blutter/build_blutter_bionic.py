#!/usr/bin/env python3
# 批量编译 blutter bionic 动态版 -> bin/bionic/blutter_dartvm<v>_android_arm64
# 跨平台（Linux / macOS / Windows）。用法: python3 build_blutter_bionic.py [版本...]  (不传 = 全部)
#
# 可用环境变量：
#   NDK / ANDROID_NDK_HOME    Android NDK 根目录（默认自动探测）
#   DARTSDK_DIR               Dart 源码目录，默认 <blutter>/dartsdk
#   JOBS                      并行度，默认 12
import os
import shutil
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import bionic_common as bc  # noqa: E402
from blutter import find_compat_macro  # noqa: E402

NDK = bc.get_ndk()
TOOLCHAIN = bc.android_toolchain(NDK)
LLVM_STRIP = bc.tool(bc.ndk_bin(NDK), 'llvm-strip')
BLUTTER = os.path.join(SCRIPT_DIR, 'blutter')


def build_one(ver, nproc):
    libname = f'dartvm{ver}_android_arm64'
    bd = os.path.join(BLUTTER, f'build_bionic_{ver}')
    if os.path.exists(bd):
        shutil.rmtree(bd)
    # Dart < 2.15 不支持 code analysis（新的 async/await 代码生成、InitLateStaticField 存根差异），
    # 与上游 blutter.py 一致：强制 no-analysis（仅 dump 对象池，不做反汇编分析）
    ver_parts = [int(x) for x in ver.split('.')]
    no_analysis = ver_parts[0] == 2 and ver_parts[1] < 15
    macros = find_compat_macro(ver, no_analysis)
    cmd = ['cmake', '-B', bd,
           '-DCMAKE_TOOLCHAIN_FILE=' + TOOLCHAIN,
           '-DANDROID_ABI=arm64-v8a', '-DANDROID_PLATFORM=android-24',
           '-DANDROID_STL=c++_shared',
           '-DCMAKE_BUILD_TYPE=Release',
           '-DCMAKE_FIND_ROOT_PATH_MODE_PACKAGE=BOTH',
           '-DCMAKE_FIND_ROOT_PATH_MODE_INCLUDE=BOTH',
           '-DCMAKE_FIND_ROOT_PATH_MODE_LIBRARY=BOTH',
           f'-Ddartvm{ver}_android_arm64_DIR=' + os.path.join(SCRIPT_DIR, 'packages', 'lib', 'cmake', libname),
           '-DDARTLIB=' + libname] + macros
    bc.run(cmd, cwd=BLUTTER)
    bc.cmake_build(bd, nproc)
    src = os.path.join(bd, 'blutter_' + libname)
    dst = os.path.join(SCRIPT_DIR, 'bin', 'bionic', 'blutter_' + libname)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    bc.run([LLVM_STRIP, '-o', dst, src])
    return dst


def main():
    vers = [a for a in sys.argv[1:] if not a.startswith('-')] or bc.list_versions()
    nproc = bc.jobs(12)
    ok, fail = [], []
    t0 = time.time()
    for ver in vers:
        try:
            dst = build_one(ver, nproc)
            ok.append(ver)
            print(f'===== {ver} OK -> {os.path.basename(dst)} ({(time.time()-t0)/60:.1f}min) =====', flush=True)
        except Exception as e:
            fail.append((ver, str(e)))
            print(f'!!!!! {ver} FAIL: {e}', flush=True)
    print(f'===== 完成: OK {len(ok)} / FAIL {len(fail)} / {(time.time()-t0)/60:.1f}min =====', flush=True)
    print('OK:', ' '.join(ok), flush=True)
    if fail:
        for v, e in fail:
            print(f'  FAIL {v}: {e}', flush=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
