#!/usr/bin/env python3
# 生成 bionic 版 jniLibs：47 个 libblutter_<v>.so + capstone/ICU/libc++_shared 共享库
# 跨平台（Linux / macOS / Windows）。等价于旧 build_jnilibs_bionic.sh。
# 用法: python3 build_jnilibs_bionic.py
#
# 可用环境变量：
#   NDK / ANDROID_NDK_HOME    Android NDK 根目录（默认自动探测）
#   JNI_LIBS_DIR              输出目录，默认历史位置（BlutterAndroid/app/src/main/jniLibs/arm64-v8a）
#   BLUTTER_BIN_DIR           47 个 binary 所在目录，默认 <blutter>/bin/bionic
#   CAPSTONE_ROOT             capstone 安装前缀，默认 <blutter>/ndk_out/capstone-android-install
#   ICU_SHARED_ROOT           ICU(共享) 安装前缀，默认 <blutter>/ndk_out/icu-android-shared-install
import glob
import os
import shutil
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import bionic_common as bc  # noqa: E402

PATCH = os.path.join(SCRIPT_DIR, 'patch_needed.py')
SRC = os.environ.get('BLUTTER_BIN_DIR') or os.path.join(SCRIPT_DIR, 'bin', 'bionic')
DST = bc.default_jni_libs()
CAPSTONE_ROOT = os.environ.get('CAPSTONE_ROOT') or os.path.join(bc.NDK_OUT, 'capstone-android-install')
ICU_SHARED_ROOT = os.environ.get('ICU_SHARED_ROOT') or os.path.join(bc.NDK_OUT, 'icu-android-shared-install')


def find_lib(libdir, stem):
    """在 libdir 下找 <stem>.so（优先精确名，其次 <stem>.so.* 带版本号的文件）。"""
    exact = os.path.join(libdir, stem + '.so')
    if os.path.isfile(exact):
        return exact
    cands = sorted(glob.glob(os.path.join(libdir, stem + '.so.*')))
    if cands:
        return cands[0]
    raise SystemExit(f'找不到 {stem}.so（目录: {libdir}）')


def patch_needed(path):
    subprocess.run([sys.executable, PATCH, path], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    if not os.path.isdir(SRC):
        raise SystemExit(f'缺少 binary 目录: {SRC}（先运行 build_blutter_bionic.py）')

    bc.mkdirs(DST)
    # 清理旧的 .so
    for f in glob.glob(os.path.join(DST, '*.so')):
        os.remove(f)

    # 1) 47 个 bionic binary -> libblutter_<点换下划线>.so
    n_bin = 0
    for b in sorted(glob.glob(os.path.join(SRC, 'blutter_dartvm*_android_arm64'))):
        name = os.path.basename(b)
        ver = name[len('blutter_dartvm'):-len('_android_arm64')]
        safe = ver.replace('.', '_')
        bc.copy_file(b, os.path.join(DST, f'libblutter_{safe}.so'))
        n_bin += 1
    print(f'[1] 复制 {n_bin} 个 libblutter_*.so')

    # 1b) 47 个 binary 的 ICU NEEDED 去掉版本号（libicu*.so.70 -> libicu*.so）
    for b in glob.glob(os.path.join(DST, 'libblutter_*.so')):
        patch_needed(b)

    # 2) capstone（NEEDED 已是 libcapstone.so，无需 patch）
    capstone = find_lib(os.path.join(CAPSTONE_ROOT, 'lib'), 'libcapstone')
    bc.copy_file(capstone, os.path.join(DST, 'libcapstone.so'))

    # 3) ICU：改名 + patch NEEDED
    icu_libdir = os.path.join(ICU_SHARED_ROOT, 'lib')
    for stem, outname in (('libicuuc', 'libicuuc.so'), ('libicudata', 'libicudata.so'),
                          ('libicui18n', 'libicui18n.so')):
        dst = os.path.join(DST, outname)
        bc.copy_file(find_lib(icu_libdir, stem), dst)
        patch_needed(dst)

    # 4) libc++_shared.so（NDK 提供）
    bc.copy_file(bc.libcxx_shared(), os.path.join(DST, 'libc++_shared.so'))

    files = sorted(glob.glob(os.path.join(DST, '*.so')))
    total = sum(os.path.getsize(f) for f in files)
    print(f'=== jniLibs 生成完成: {len(files)} 个文件, {total/1024/1024:.1f} MB -> {DST} ===')


if __name__ == '__main__':
    main()
