#!/usr/bin/env python3
# 批量交叉编译 Dart VM 静态库 -> packages/lib/libdartvm<ver>_android_arm64.a
# 跨平台（Linux / macOS / Windows）。用法: python3 build_dartvm_bionic.py [版本...]  (不传 = 全部)
#
# 可用环境变量：
#   NDK / ANDROID_NDK_HOME    Android NDK 根目录（默认自动探测）
#   ICU_ROOT                  ICU（Android 版）安装前缀，默认 <blutter>/ndk_out/icu-android-shared-install
#   DARTSDK_DIR               Dart 源码目录，默认 <blutter>/dartsdk
#   JOBS                      并行度，默认 8
import os
import shutil
import sys

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import bionic_common as bc  # noqa: E402

SDK_DIR = bc.dartsdk_dir()
BUILD_DIR = os.path.join(SCRIPT_DIR, 'build')
CMAKE_TEMPLATE_FILE = os.path.join(SCRIPT_DIR, 'scripts', 'CMakeLists.txt')
CREATE_SRCLIST_FILE = os.path.join(SCRIPT_DIR, 'scripts', 'dartvm_create_srclist.py')
COMPAT_HEADER = os.path.join(SCRIPT_DIR, 'compat', 'atomic_ref_compat.h')

NDK = bc.get_ndk()
TOOLCHAIN = bc.android_toolchain(NDK)
BIN = bc.ndk_bin(NDK)
GLIBC_CC = bc.android_clang(BIN, 24, cxx=False)
GLIBC_CXX = bc.android_clang(BIN, 24, cxx=True)
ICU_ROOT = os.environ.get('ICU_ROOT') or os.path.join(SCRIPT_DIR, 'ndk_out', 'icu-android-shared-install')

imp_replace_snippet = """import importlib.util
import importlib.machinery

def load_source(modname, filename):
    loader = importlib.machinery.SourceFileLoader(modname, filename)
    spec = importlib.util.spec_from_file_location(modname, filename, loader=loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module
"""


def prepare(info):
    """确保源码就绪（生成 version.cc），不重新 clone。返回源码目录。"""
    clonedir = os.path.join(SDK_DIR, 'v' + info.version)
    if not os.path.isdir(clonedir):
        raise SystemExit(f'源码目录缺失: {clonedir}')
    version_file = os.path.join(clonedir, 'runtime', 'vm', 'version.cc')
    if not os.path.exists(version_file):
        # python 3.12+: 老版本 tools/utils.py 需要 imp patch
        utils_path = os.path.join(clonedir, 'tools', 'utils.py')
        if os.path.exists(utils_path):
            with open(utils_path, 'r+') as f:
                content = f.read()
                if 'import imp\n' in content and 'imp.load_source' in content:
                    content = content.replace('import imp\n', imp_replace_snippet).replace('imp.load_source', 'load_source')
                    f.seek(0)
                    f.truncate()
                    f.write(content)
        bc.run([sys.executable, 'tools/make_version.py',
                '--output', 'runtime/vm/version.cc',
                '--input', 'runtime/vm/version_in.cc'],
               cwd=clonedir)
    return clonedir


def find_cpp_std(target_dir, version):
    run_clang_tidy_file = os.path.join(target_dir, 'runtime', 'tools', 'run_clang_tidy.dart')
    if os.path.exists(run_clang_tidy_file):
        with open(run_clang_tidy_file, 'r') as f:
            content = f.read()
            pos = content.find('-std=c++')
            return '17' if pos == -1 else content[pos + 8:pos + 10]
    # 部分版本 sparse checkout 未含 runtime/tools；按版本推断（Dart 3.7+ 默认 C++20）
    v = [int(x) for x in version.split('.')]
    cpp_std = '20' if (v[0], v[1]) >= (3, 7) else '17'
    print(f'  [info] run_clang_tidy.dart 缺失，{version} 使用 C++{cpp_std}', flush=True)
    return cpp_std


def cmake_dart_bionic(info, target_dir, nproc):
    cpp_std = find_cpp_std(target_dir, info.version)

    with open(CMAKE_TEMPLATE_FILE, 'r') as f:
        code = f.read()
    with open(os.path.join(target_dir, 'CMakeLists.txt'), 'w') as f:
        f.write(code.replace('VERSION_PLACE_HOLDER', info.version)
                    .replace('CXX_STD_PLACE_HOLDER', cpp_std))
    with open(os.path.join(target_dir, 'Config.cmake.in'), 'w') as f:
        f.write('@PACKAGE_INIT@\n\ninclude ( "${CMAKE_CURRENT_LIST_DIR}/dartvmTarget.cmake" )\n\n')

    bc.run([sys.executable, CREATE_SRCLIST_FILE, target_dir])

    builddir = os.path.join(BUILD_DIR, info.lib_name)
    if os.path.exists(builddir):
        shutil.rmtree(builddir)

    args = ['-DTARGET_OS=%s' % info.os_name, '-DTARGET_ARCH=%s' % info.arch,
            '-DCOMPRESSED_PTRS=%d' % (1 if info.has_compressed_ptrs else 0),
            '-DCMAKE_BUILD_TYPE=Release',
            '-DCMAKE_TOOLCHAIN_FILE=' + TOOLCHAIN,
            '-DANDROID_ABI=arm64-v8a', '-DANDROID_PLATFORM=android-24',
            '-DANDROID_STL=c++_static',
            '-DCMAKE_FIND_ROOT_PATH_MODE_PACKAGE=BOTH',
            '-DCMAKE_FIND_ROOT_PATH_MODE_INCLUDE=BOTH',
            '-DCMAKE_FIND_ROOT_PATH_MODE_LIBRARY=BOTH',
            '-DICU_ROOT=' + ICU_ROOT,
            '-DICU_INCLUDE_DIR=' + os.path.join(ICU_ROOT, 'include'),
            '-DICU_LIBRARY=' + os.path.join(ICU_ROOT, 'lib', 'libicuuc.so'),
            '--log-level=NOTICE']
    if not bc.IS_WIN:
        # Linux/macOS 保持原有显式指定（Windows 上由 android.toolchain.cmake 自动选择更稳妥）
        args += ['-DCMAKE_C_COMPILER=' + GLIBC_CC, '-DCMAKE_CXX_COMPILER=' + GLIBC_CXX]
    if [int(x) for x in info.version.split('.')][:2] >= [3, 12]:
        # Dart 3.12+ 需要 std::atomic_ref 兼容头；路径用正斜杠，避免 Windows 反斜杠问题
        hdr = COMPAT_HEADER.replace('\\', '/')
        args += ['-DCMAKE_CXX_FLAGS=-include ' + hdr]

    bc.cmake_configure(builddir, args, cwd=target_dir)
    bc.cmake_build(builddir, nproc)
    bc.cmake_install(builddir)


def main():
    if len(sys.argv) > 1:
        versions = [a for a in sys.argv[1:] if not a.startswith('-')]
    else:
        versions = bc.list_versions()
    nproc = bc.jobs(8)
    ok, fail = [], []
    for ver in versions:
        info = type('Info', (), {'version': ver, 'os_name': 'android', 'arch': 'arm64',
                                 'has_compressed_ptrs': True, 'lib_name': f'dartvm{ver}_android_arm64'})()
        try:
            print(f'===== dartvm {ver} 开始 =====', flush=True)
            outdir = prepare(info)
            cmake_dart_bionic(info, outdir, nproc)
            lib = os.path.join(SCRIPT_DIR, 'packages', 'lib', f'lib{info.lib_name}.a')
            if not os.path.exists(lib):
                raise RuntimeError(f'产物缺失: {lib}')
            ok.append(ver)
            print(f'===== dartvm {ver} OK ({os.path.getsize(lib)} bytes) =====', flush=True)
        except Exception as e:
            fail.append((ver, str(e)))
            print(f'!!!!! dartvm {ver} FAIL: {e}', flush=True)
    print(f'===== 完成: OK {len(ok)} / FAIL {len(fail)} =====', flush=True)
    if fail:
        for v, e in fail:
            print(f'  FAIL {v}: {e}', flush=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
