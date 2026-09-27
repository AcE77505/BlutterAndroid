#!/usr/bin/env python3
# ICU 70.1 -> Android aarch64 (bionic) 交叉构建。
#   默认      : 静态库 -> ndk_out/icu-android-install
#   --shared  : 动态库 -> ndk_out/icu-android-shared-install（生成 jniLibs 需要这一份）
# 用法: python3 icu_android_build.py [--shared]
#
# 注意：ICU 使用 autotools（configure + make）。原生 Windows 需 MSYS2 或 WSL；
#       WSL2 里可直接运行。需先运行 icu_host_build.py（提供 --with-cross-build）。
#
# 可用环境变量：
#   ICU_SRC     ICU 源码目录，默认 <blutter>/ndk_src/icu
#   ICU_BUILD   覆盖 configure 的 --build 三元组（默认非 Windows 用 x86_64-linux-gnu）
#   MAKE        make 命令，默认 make
#   JOBS        并行度，默认 16
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
import bionic_common as bc  # noqa: E402

ICU_SRC = os.environ.get('ICU_SRC') or os.path.join(bc.BLUTTER_DIR, 'ndk_src', 'icu')
HOST_BUILD = os.path.join(bc.NDK_OUT, 'icu-host-build')
MAKE = os.environ.get('MAKE', 'make')


def main():
    shared = '--shared' in sys.argv[1:]
    suffix = '-shared' if shared else ''
    build_dir = os.path.join(bc.NDK_OUT, f'icu-android{suffix}-build')
    install = os.path.join(bc.NDK_OUT, f'icu-android{suffix}-install')
    configure = os.path.join(ICU_SRC, 'source', 'configure')

    if not os.path.isfile(configure):
        raise SystemExit(f'缺少 ICU 源码或 configure: {configure}')
    if not os.path.isdir(HOST_BUILD):
        raise SystemExit(f'缺少 host 构建: {HOST_BUILD}（先运行 icu_host_build.py）')

    bin_dir = bc.ndk_bin()
    args = [
        '--host=aarch64-linux-android',
        '--with-cross-build=' + HOST_BUILD,
        '--prefix=' + install,
        '--disable-samples', '--disable-tests', '--disable-icuio',
        '--disable-layout', '--disable-layoutex',
    ]
    args += ['--enable-shared', '--disable-static'] if shared else ['--enable-static', '--disable-shared']
    icu_build = os.environ.get('ICU_BUILD')
    if icu_build:
        args.append('--build=' + icu_build)
    elif not bc.IS_WIN:
        args.append('--build=x86_64-linux-gnu')

    bc.mkdirs(build_dir)
    cfg = ['sh', configure] if bc.IS_WIN else [configure]
    env_assign = [
        'CC=' + bc.android_clang(bin_dir, 24, cxx=False),
        'CXX=' + bc.android_clang(bin_dir, 24, cxx=True),
        'AR=' + bc.tool(bin_dir, 'llvm-ar'),
        'RANLIB=' + bc.tool(bin_dir, 'llvm-ranlib'),
    ]
    bc.run(cfg + args + env_assign, cwd=build_dir)
    bc.run([MAKE, '-j' + str(bc.jobs(16))], cwd=build_dir)
    bc.run([MAKE, 'install'], cwd=build_dir)
    print(f'=== ICU android{"(shared)" if shared else ""} 完成 -> {install} ===')


if __name__ == '__main__':
    main()
