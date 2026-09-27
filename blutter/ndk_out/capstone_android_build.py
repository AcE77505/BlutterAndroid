#!/usr/bin/env python3
# Capstone 4.0.2 -> Android aarch64 (bionic) 交叉构建。跨平台（纯 cmake）。
# 产物: <blutter>/ndk_out/capstone-android-install/lib/libcapstone.so
# 用法: python3 capstone_android_build.py
#
# 可用环境变量：
#   NDK / ANDROID_NDK_HOME   Android NDK 根目录（默认自动探测）
#   CAPSTONE_SRC             capstone 源码目录，默认 <blutter>/ndk_src/capstone-4.0.2
#   CAPSTONE_ROOT            安装前缀，默认 <blutter>/ndk_out/capstone-android-install
#   JOBS                     并行度，默认 16
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
import bionic_common as bc  # noqa: E402

SRC = os.environ.get('CAPSTONE_SRC') or os.path.join(bc.BLUTTER_DIR, 'ndk_src', 'capstone-4.0.2')
BUILD = os.path.join(bc.NDK_OUT, 'capstone-android')
INSTALL = os.environ.get('CAPSTONE_ROOT') or os.path.join(bc.NDK_OUT, 'capstone-android-install')


def main():
    if not os.path.isdir(SRC):
        raise SystemExit(f'缺少 capstone 源码: {SRC}')
    bc.cmake_configure(BUILD, [
        '-S', SRC,
        '-DCMAKE_TOOLCHAIN_FILE=' + bc.android_toolchain(),
        '-DANDROID_ABI=arm64-v8a', '-DANDROID_PLATFORM=android-24',
        '-DCMAKE_BUILD_TYPE=Release',
        '-DCMAKE_POSITION_INDEPENDENT_CODE=ON',
        '-DCMAKE_INSTALL_PREFIX=' + INSTALL,
    ])
    bc.cmake_build(BUILD)
    bc.cmake_install(BUILD)
    print(f'=== capstone(android) 完成 -> {INSTALL} ===')


if __name__ == '__main__':
    main()
