#!/usr/bin/env python3
# 批量交叉编译 Dart VM 静态库 (glibc / aarch64-linux-gnu) -> packages/lib/libdartvm<ver>_android_arm64.a
# 用法: python3 build_dartvm_glibc.py [版本...]   (不传参数 = 全部 47 个版本)
import os
import shutil
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
SDK_DIR = os.path.join(SCRIPT_DIR, 'dartsdk')
BUILD_DIR = os.path.join(SCRIPT_DIR, 'build')
CMAKE_TEMPLATE_FILE = os.path.join(SCRIPT_DIR, 'scripts', 'CMakeLists.txt')
CREATE_SRCLIST_FILE = os.path.join(SCRIPT_DIR, 'scripts', 'dartvm_create_srclist.py')

GLIBC_CC = '/home/ace77505/blutter/ndk_out/toolchain/aarch64-linux-gnu-clang-glibc'
GLIBC_CXX = '/home/ace77505/blutter/ndk_out/toolchain/aarch64-linux-gnu-clang++-glibc'
ICU_ROOT = '/home/ace77505/blutter/ndk_out/icu-arm-shared-install'

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
        subprocess.run([sys.executable, 'tools/make_version.py',
                        '--output', 'runtime/vm/version.cc',
                        '--input', 'runtime/vm/version_in.cc'],
                       cwd=clonedir, check=True)
    return clonedir


def cmake_dart_glibc(info, target_dir, jobs):
    run_clang_tidy_file = os.path.join(target_dir, 'runtime', 'tools', 'run_clang_tidy.dart')
    if os.path.exists(run_clang_tidy_file):
        with open(run_clang_tidy_file, 'r') as f:
            content = f.read()
            pos = content.find('-std=c++')
            cpp_std = '17' if pos == -1 else content[pos + 8:pos + 10]
    else:
        # 部分版本 sparse checkout 未含 runtime/tools；按版本推断（Dart 3.7+ 默认 C++20）
        v = [int(x) for x in info.version.split('.')]
        cpp_std = '20' if (v[0], v[1]) >= (3, 7) else '17'
        print(f'  [info] run_clang_tidy.dart 缺失，{info.version} 使用 C++{cpp_std}', flush=True)

    with open(CMAKE_TEMPLATE_FILE, 'r') as f:
        code = f.read()
    with open(os.path.join(target_dir, 'CMakeLists.txt'), 'w') as f:
        f.write(code.replace('VERSION_PLACE_HOLDER', info.version)
                    .replace('CXX_STD_PLACE_HOLDER', cpp_std))
    with open(os.path.join(target_dir, 'Config.cmake.in'), 'w') as f:
        f.write('@PACKAGE_INIT@\n\ninclude ( "${CMAKE_CURRENT_LIST_DIR}/dartvmTarget.cmake" )\n\n')

    subprocess.run([sys.executable, CREATE_SRCLIST_FILE, target_dir], check=True)

    builddir = os.path.join(BUILD_DIR, info.lib_name)
    if os.path.exists(builddir):
        shutil.rmtree(builddir)
    subprocess.run(['cmake', '-B', builddir,
                    f'-DTARGET_OS={info.os_name}', f'-DTARGET_ARCH={info.arch}',
                    f'-DCOMPRESSED_PTRS={1 if info.has_compressed_ptrs else 0}',
                    '-DCMAKE_BUILD_TYPE=Release',
                    '-DCMAKE_SYSTEM_NAME=Linux', '-DCMAKE_SYSTEM_PROCESSOR=aarch64',
                    '-DCMAKE_C_COMPILER=' + GLIBC_CC,
                    '-DCMAKE_CXX_COMPILER=' + GLIBC_CXX,
                    '-DICU_ROOT=' + ICU_ROOT,
                    '--log-level=NOTICE'],
                   cwd=target_dir, check=True)
    subprocess.run(['make', '-j' + str(jobs)], cwd=builddir, check=True)
    subprocess.run(['cmake', '--install', '.'], cwd=builddir, check=True)


def main():
    if len(sys.argv) > 1:
        versions = [a for a in sys.argv[1:] if not a.startswith('-')]
    else:
        versions = sorted([d[1:] for d in os.listdir(SDK_DIR) if d.startswith('v')],
                          key=lambda v: [int(x) for x in v.split('.')])
    jobs = int(os.environ.get('JOBS', '8'))
    ok, fail = [], []
    for ver in versions:
        info = type('Info', (), {'version': ver, 'os_name': 'android', 'arch': 'arm64',
                                 'has_compressed_ptrs': True, 'lib_name': f'dartvm{ver}_android_arm64'})()
        try:
            print(f'===== dartvm {ver} 开始 =====', flush=True)
            outdir = prepare(info)
            cmake_dart_glibc(info, outdir, jobs)
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
