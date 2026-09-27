#!/usr/bin/env python3
# ICU 70.1 host (x86_64) 构建，供 android 交叉编译 --with-cross-build 使用。
# 产物: <blutter>/ndk_out/icu-host-build
# 用法: python3 icu_host_build.py
#
# 注意：ICU 使用 autotools（configure + make）。原生 Windows 需 MSYS2 或 WSL；
#       也可在 Linux/macOS/WSL/MSYS2/Git-Bash 下运行。
#
# 可用环境变量：
#   ICU_SRC      ICU 源码目录，默认 <blutter>/ndk_src/icu
#   MAKE         make 命令，默认 make（MSYS2 可设为 make.exe 的绝对路径）
#   JOBS         并行度，默认 16
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
import bionic_common as bc  # noqa: E402

ICU_SRC = os.environ.get('ICU_SRC') or os.path.join(bc.BLUTTER_DIR, 'ndk_src', 'icu')
BUILD = os.path.join(bc.NDK_OUT, 'icu-host-build')
INSTALL = os.path.join(bc.NDK_OUT, 'icu-host-install')
MAKE = os.environ.get('MAKE', 'make')


def main():
    configure = os.path.join(ICU_SRC, 'source', 'configure')
    if not os.path.isfile(configure):
        raise SystemExit(f'缺少 ICU 源码或 configure: {configure}')
    bc.mkdirs(BUILD)

    cfg = ['sh', configure] if bc.IS_WIN else [configure]
    bc.run(cfg + [
        '--prefix=' + INSTALL,
        '--disable-samples', '--disable-tests', '--disable-icuio',
        '--disable-layout', '--disable-layoutex',
    ], cwd=BUILD)
    bc.run([MAKE, '-j' + str(bc.jobs(16))], cwd=BUILD)
    print(f'=== ICU host 完成 -> {BUILD} ===')


if __name__ == '__main__':
    main()
