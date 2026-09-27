# Blutter bionic 二进制交叉编译（跨平台：Linux / Windows）

生成对象：47 个 `libblutter_<ver>.so`（Android arm64 bionic，linker64 可加载）+ 共享依赖
（`libcapstone.so` / 3×ICU / `libc++_shared.so`）→ 直接作为 App 的 `jniLibs`。

## 一、环境准备

| 依赖 | 说明 |
|------|------|
| Python 3.10+ | 所有构建脚本 |
| Android NDK r27c | Windows 版解压即用（`android-ndk-r27c`） |
| CMake | 3.13+（Android SDK 自带亦可） |
| Ninja | NDK/SDK 自带（`cmake --build` 会用到） |
| Git | 拉取 Dart 源码（若直接拷贝现成 `dartsdk/` 则不需要） |
| 环境变量 `NDK` | 指向 NDK 根目录；未设时脚本会自动探测 |

示例：
- Linux:   `export NDK=/home/ace77505/android-ndk-r27c`
- Windows: `set NDK=C:\android-ndk-r27c`

## 二、脚本一览（均已跨平台）

| 脚本 | 作用 |
|------|------|
| `patch_all_snapshot.py` | 批量 patch Dart 源码：snapshot hash/features 校验降级为 warning |
| `ndk_out/icu_host_build.py` | ICU host(x86_64) 构建（交叉编译用，**需 autotools**） |
| `ndk_out/icu_android_build.py [--shared]` | ICU → Android aarch64（`--shared` 生成 jniLibs 需要的动态库） |
| `ndk_out/capstone_android_build.py` | Capstone → Android aarch64（纯 cmake） |
| `build_dartvm_bionic.py` | Dart VM `.a`（47 版本） |
| `build_blutter_bionic.py` | blutter 二进制（47 版本）→ `bin/bionic/` |
| `build_jnilibs_bionic.py` | 汇总为 `jniLibs/arm64-v8a/` |
| `patch_needed.py` | 单独使用：原地改某 ELF 的 `DT_NEEDED`（被上面自动调用） |

## 三、构建顺序

```bash
# 0) （一次性）准备 Dart 源码到 dartsdk/v<版本>；已有 dartsdk/ 可直接拷贝
# 1) 降级 snapshot 校验
python3 patch_all_snapshot.py

# 2) 预构建依赖（一次性；若已有 ndk_out/icu-*-install、ndk_out/capstone-android-install 可跳过）
python3 ndk_out/icu_host_build.py
python3 ndk_out/icu_android_build.py --shared
python3 ndk_out/capstone_android_build.py

# 3) 编译 47 个 dartvm .a
python3 build_dartvm_bionic.py            # 或指定版本： ... 3.12.2

# 4) 编译 47 个 blutter 二进制 -> bin/bionic/
python3 build_blutter_bionic.py

# 5) 生成 jniLibs
python3 build_jnilibs_bionic.py
# 旧入口仍可用：./build_jnilibs_bionic.sh（内部转发到 .py）
```

## 四、环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `NDK` / `ANDROID_NDK_HOME` | 自动探测 | NDK 根目录 |
| `DARTSDK_DIR` | `<blutter>/dartsdk` | Dart 源码目录 |
| `ICU_ROOT` | `<blutter>/ndk_out/icu-android-shared-install` | dartvm 编译用 ICU |
| `ICU_SHARED_ROOT` | 同上 | jniLibs 取 ICU 动态库处 |
| `CAPSTONE_ROOT` | `<blutter>/ndk_out/capstone-android-install` | capstone 安装前缀 |
| `BLUTTER_BIN_DIR` | `<blutter>/bin/bionic` | 47 个 binary 所在 |
| `JNI_LIBS_DIR` | 历史默认路径 | jniLibs 输出目录 |
| `JOBS` | 8/12/16 | 并行度 |

## 五、Windows 注意点

1. **NDK 自动切换**：Windows 上自动用 `toolchains/llvm/prebuilt/windows-x86_64`，
   clang 包装器为 `aarch64-linux-android24-clang.cmd`、`llvm-strip.exe`。
2. **构建命令**：统一改为 `cmake --build <dir> --parallel N`（不再直接调 `make`）。
3. **ICU 是唯一麻烦点**：ICU 用 autotools（`configure` + `make`）。
   - 原生 Windows 需 **MSYS2**（提供 make）或 **WSL2**；
   - 也可在 Linux/WSL 上构建一次，把 `<blutter>/ndk_out/icu-android-shared-install`
     整个目录拷到 Windows（**推荐**，ICU 是一次性依赖）。
   - 若用 MSYS2，可 `set MAKE=C:\msys64\usr\bin\make.exe`。
4. **Capstone / Dart VM / blutter / jniLibs**：纯 cmake + Python，Windows 原生可直接跑。

## 六、原脚本备份

改造前的原脚本已备份到 `<blutter>/.xplat_backup/`。
