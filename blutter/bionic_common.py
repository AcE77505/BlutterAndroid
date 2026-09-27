#!/usr/bin/env python3
"""跨平台公共工具（Linux / macOS / Windows 通用）。

供 build_dartvm_bionic.py / build_blutter_bionic.py / build_jnilibs_bionic.py /
ndk_out 下的 ICU、Capstone 预构建脚本复用。

设计原则：
- 不改变现有 Linux 行为：路径仍可用环境变量覆盖，默认值与原来一致；
- Windows 上自动切换 NDK 的 host 目录（prebuilt/windows-x86_64）与可执行后缀（.cmd/.exe）；
- 构建统一走 `cmake --build`（跨平台），不再直接调 `make`。
"""
import os
import shutil
import subprocess
import sys

IS_WIN = (os.name == 'nt')
IS_MAC = (sys.platform == 'darwin')

# blutter 仓库根目录（本文件所在目录）
BLUTTER_DIR = os.path.dirname(os.path.realpath(__file__))
NDK_OUT = os.path.join(BLUTTER_DIR, 'ndk_out')


def host_tag():
    """NDK toolchains/llvm/prebuilt 下的 host 目录名。"""
    if IS_WIN:
        return 'windows-x86_64'
    if IS_MAC:
        return 'darwin-x86_64'
    return 'linux-x86_64'


def find_ndk():
    """定位 Android NDK。优先环境变量，其次常见安装位置。

    可用环境变量：NDK / ANDROID_NDK_HOME / ANDROID_NDK_ROOT
    （若设置了 ANDROID_HOME/ANDROID_SDK_ROOT，还会尝试其 ndk/<ver> 子目录）
    """
    for var in ('NDK', 'ANDROID_NDK_HOME', 'ANDROID_NDK_ROOT'):
        p = os.environ.get(var)
        if p and os.path.isdir(p):
            return os.path.realpath(p)

    candidates = []
    for var in ('ANDROID_HOME', 'ANDROID_SDK_ROOT'):
        sdk = os.environ.get(var)
        if sdk and os.path.isdir(os.path.join(sdk, 'ndk')):
            ndk_root = os.path.join(sdk, 'ndk')
            candidates += [os.path.join(ndk_root, d) for d in sorted(os.listdir(ndk_root))]

    home = os.path.expanduser('~')
    candidates += [
        # 本项目历史默认位置（Linux）
        '/home/ace77505/android-ndk-r27c',
        os.path.join(home, 'android-ndk-r27c'),
        os.path.join(home, 'Android', 'Sdk', 'ndk'),  # 由下方展开子目录
    ]
    if IS_WIN:
        local = os.environ.get('LOCALAPPDATA', '')
        candidates += [
            os.path.join(home, 'AppData', 'Local', 'Android', 'Sdk', 'ndk'),
            os.path.join(local, 'Android', 'Sdk', 'ndk') if local else '',
        ]

    expanded = []
    for c in candidates:
        if not c:
            continue
        expanded.append(c)
        if os.path.isdir(c) and os.path.basename(c) == 'ndk':
            expanded += [os.path.join(c, d) for d in sorted(os.listdir(c))]

    for c in expanded:
        if c and os.path.isdir(c) and os.path.isfile(os.path.join(c, 'build', 'cmake', 'android.toolchain.cmake')):
            return os.path.realpath(c)

    raise SystemExit(
        '找不到 Android NDK。请设置环境变量 NDK（或 ANDROID_NDK_HOME）指向 NDK 根目录。\n'
        '  Linux : export NDK=/path/to/android-ndk-r27c\n'
        '  Windows: set NDK=C:\\path\\to\\android-ndk-r27c'
    )


def get_ndk():
    return os.environ.get('_BLUTTER_NDK') or find_ndk()


def ndk_bin(ndk=None):
    """NDK 的 llvm prebuilt bin 目录（含平台后缀）。"""
    ndk = ndk or get_ndk()
    return os.path.join(ndk, 'toolchains', 'llvm', 'prebuilt', host_tag(), 'bin')


def tool(bin_dir, name, force_exe=False):
    """在 bin 目录下定位工具，Windows 上自动补 .exe。"""
    if IS_WIN or force_exe:
        p = os.path.join(bin_dir, name + '.exe')
        if os.path.exists(p):
            return p
    return os.path.join(bin_dir, name)


def android_clang(bin_dir, api=24, cxx=False):
    """NDK 的 aarch64 clang 包装器。Windows 上是 .cmd。"""
    name = 'aarch64-linux-android%d-%s' % (api, 'clang++' if cxx else 'clang')
    if IS_WIN:
        return os.path.join(bin_dir, name + '.cmd')
    return os.path.join(bin_dir, name)


def android_toolchain(ndk=None):
    ndk = ndk or get_ndk()
    return os.path.join(ndk, 'build', 'cmake', 'android.toolchain.cmake')


def libcxx_shared(ndk=None):
    """NDK 自带的 libc++_shared.so（aarch64 android）。"""
    ndk = ndk or get_ndk()
    return os.path.join(ndk, 'toolchains', 'llvm', 'prebuilt', host_tag(),
                        'sysroot', 'usr', 'lib', 'aarch64-linux-android', 'libc++_shared.so')


def jobs(default=8):
    return int(os.environ.get('JOBS', str(default)))


def run(cmd, **kw):
    """打印并执行命令（跨平台统一入口）。"""
    print('  $', ' '.join(str(c) for c in cmd), flush=True)
    return subprocess.run(cmd, check=True, **kw)


def cmake_configure(builddir, args, cwd=None):
    """cmake -S/-B 配置。"""
    run(['cmake', '-B', builddir] + list(args), cwd=cwd)


def cmake_build(builddir, n=None):
    """跨平台构建（优先 cmake --build；等价于 make -jN）。"""
    n = n or jobs()
    try:
        run(['cmake', '--build', builddir, '--parallel', str(n)])
    except FileNotFoundError:
        # 极端情况下退回 ninja
        run(['ninja', '-C', builddir])


def cmake_install(builddir):
    run(['cmake', '--install', builddir])


def mkdirs(path):
    os.makedirs(path, exist_ok=True)


def rm_rf(path):
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)
    elif os.path.exists(path):
        os.remove(path)


def copytree(src, dst):
    mkdirs(dst)
    for name in os.listdir(src):
        s = os.path.join(src, name)
        d = os.path.join(dst, name)
        if os.path.isdir(s):
            shutil.copytree(s, d, dirs_exist_ok=True)
        else:
            shutil.copy2(s, d)


def copy_file(src, dst):
    mkdirs(os.path.dirname(dst))
    shutil.copy2(src, dst)


def default_jni_libs():
    """默认 jniLibs 输出目录（可被环境变量 JNI_LIBS_DIR 覆盖）。

    blutter 现位于 App 工程内（<App>/blutter），默认输出到
    <App>/app/src/main/jniLibs/arm64-v8a。
    """
    env = os.environ.get('JNI_LIBS_DIR')
    if env:
        return env
    return os.path.normpath(os.path.join(
        BLUTTER_DIR, '..', 'app', 'src', 'main', 'jniLibs', 'arm64-v8a'))


def dartsdk_dir():
    return os.environ.get('DARTSDK_DIR') or os.path.join(BLUTTER_DIR, 'dartsdk')


def version_sort_key(v):
    return [int(x) for x in v.split('.')]


def list_versions():
    """dartsdk 下已 checkout 的 Dart 版本列表（升序）。"""
    d = dartsdk_dir()
    if not os.path.isdir(d):
        return []
    return sorted([x[1:] for x in os.listdir(d) if x.startswith('v')], key=version_sort_key)
