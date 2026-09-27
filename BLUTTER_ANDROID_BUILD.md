# Blutter Android 编译与部署

> **当前方案（2026 更新）**：x86 Linux / Windows **NDK 交叉编译 bionic 版**，70 个版本，
> 以 **jniLibs** 形式集成进 Android App（App 内 `execve` + `LD_LIBRARY_PATH`）。
> 本文档已按此更新；文末「历史方案」为已废弃路线，仅作背景。

---

## 概述

Blutter 用 **Android NDK 的 `android.toolchain` + bionic 运行时**交叉编译为
每版本一个 **PIE 可执行文件**：

- interpreter = `/system/bin/linker64`（Android 原生加载器）
- `DT_NEEDED` 无版本后缀，且 **容忍 NEEDED ≠ SONAME**（Android linker 原生行为）
- 无 glibc 依赖 → 天然规避旧 glibc 方案的 SIGSYS / dynstr 问题

产物直接作为 App 的 **`jniLibs/arm64-v8a/`**：70 个 `libblutter_<版本>.so`（~2.3–2.7MB/个，strip 后）
+ 共享依赖库（`libcapstone.so`、`libicudata.so`/`libicuuc.so`/`libicui18n.so`、`libc++_shared.so`），
共 **75 个文件 ≈ 225MB**（按 70 个版本推算；重跑 `build_jnilibs_bionic.py` 后同步）。

**全流程跨平台（Linux / Windows）**：脚本一份代码双平台，Windows 上自动切换
`prebuilt/windows-x86_64` 与 `.cmd`/`.exe` 后缀，构建统一走 `cmake --build`。

> **本项目位置**：下文 `<blutter>` 指 `BlutterAndroid/blutter/`（与本 `BLUTTER_ANDROID_BUILD.md` 同级）；
> jniLibs 默认输出到 `BlutterAndroid/app/src/main/jniLibs/arm64-v8a/`。
> Windows 上构建前设置 `NDK` 与 `CMAKE_GENERATOR=Ninja`，并把 SDK 的 `cmake/3.22.1/bin` 加入 `PATH`。

---

## 一、编译环境

| 依赖 | 说明 |
|------|------|
| Python 3.10+ | 所有构建脚本 |
| Android NDK r27c | Windows 版解压即用 |
| CMake 3.13+ | 可用 Android SDK 自带 |
| Ninja | NDK/SDK 自带 |
| Git | 拉取 Dart 源码（若已拷贝 `dartsdk/` 则不需要） |

环境变量 `NDK` 指向 NDK 根目录（未设时脚本自动探测）：

```bash
# Linux
export NDK=/home/ace77505/android-ndk-r27c
# Windows
set NDK=C:\android-ndk-r27c
```

---

## 二、构建流程

```bash
cd <blutter>            # 例如 /home/ace77505/blutter

# 0) （一次性）准备 Dart 源码到 dartsdk/v<版本>；已有 dartsdk/ 可直接拷贝

# 1) 降级 snapshot hash/features 严格校验为 warning（预编译 dartvm 需匹配任意引擎）
python3 patch_all_snapshot.py

# 2) 预构建依赖（一次性；已有 ndk_out/icu-*-install、ndk_out/capstone-android-install 可跳过）
python3 ndk_out/icu_host_build.py
python3 ndk_out/icu_android_build.py --shared     # jniLibs 需要动态版
python3 ndk_out/capstone_android_build.py

# 3) 编译 70 个 dartvm 静态库 -> packages/lib/libdartvm<版本>_android_arm64.a
python3 build_dartvm_bionic.py                     # 可只编指定版本：... 3.12.2

# 4) 编译 70 个 blutter 二进制 -> bin/bionic/
python3 build_blutter_bionic.py

# 5) 汇总为 jniLibs
python3 build_jnilibs_bionic.py
# 旧入口仍可用：./build_jnilibs_bionic.sh（内部转发到 .py）
```

### 脚本一览（均已跨平台）

| 脚本 | 作用 |
|------|------|
| `patch_all_snapshot.py` | 批量 patch Dart 源码：snapshot 校验降级 warning |
| `ndk_out/icu_host_build.py` | ICU host(x86_64) 构建（交叉编译前置，**需 autotools**） |
| `ndk_out/icu_android_build.py [--shared]` | ICU → Android aarch64 |
| `ndk_out/capstone_android_build.py` | Capstone → Android aarch64（纯 cmake） |
| `build_dartvm_bionic.py` | Dart VM `.a`（70 版本） |
| `build_blutter_bionic.py` | blutter 二进制（70 版本）；`<2.15` 自动 no-analysis |
| `build_jnilibs_bionic.py` | 汇总为 `jniLibs/arm64-v8a/` |
| `patch_needed.py` | 原地改某 ELF 的 `DT_NEEDED`（被上面自动调用） |
| `bionic_common.py` | 跨平台公共模块（平台检测/NDK 探测/构建命令） |

### 可用环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `NDK` / `ANDROID_NDK_HOME` | 自动探测 | NDK 根目录 |
| `DARTSDK_DIR` | `<blutter>/dartsdk` | Dart 源码目录 |
| `ICU_ROOT` | `<blutter>/ndk_out/icu-android-shared-install` | dartvm 编译用 ICU |
| `CAPSTONE_ROOT` | `<blutter>/ndk_out/capstone-android-install` | capstone 安装前缀 |
| `BLUTTER_BIN_DIR` | `<blutter>/bin/bionic` | 70 个 binary 所在 |
| `JNI_LIBS_DIR` | 项目 jniLibs 路径 | jniLibs 输出目录 |
| `JOBS` | 8 / 12 / 16 | 并行度 |

---

## 三、关键适配

| 项 | 处理 |
|----|------|
| snapshot 校验 | patch `app_snapshot.cc` 两处（hash 校验 / VerifyFeatures）降级为 warning，否则预编译 dartvm 无法匹配任意 Flutter 引擎 |
| 版本检测 | 用 `\x00` 前缀正则（同官方 `extract_dart_info.py`），否则误匹配 libflutter.so 里的次要版本串 |
| `std::atomic_ref` | Dart 3.12+ 需 `compat/atomic_ref_compat.h`（`-include` 注入） |
| Dart VM ABI | 全部用 NDK clang 编译（非 chroot GCC），与 bionic 链接链一致 |
| C++ 标准 | 按版本推断（Dart 3.7+ 默认 C++20） |
| `DT_NEEDED` | `patch_needed.py` 缩短为无版本号（`libicuuc.so.70`→`libicuuc.so`），保持 needed 闭合 |

---

## 四、App 侧集成

- 产物放在 `app/src/main/jniLibs/arm64-v8a/`（PackageManager 会提取到 `nativeLibraryDir`，非 noexec）
- App 直接 `execve(nativeLibraryDir/libblutter_<版本>.so)`，子进程设 `LD_LIBRARY_PATH=nativeLibraryDir`
  （linker64 不自动搜索 nativeLibraryDir）
- 输出目录走 SAF：`takePersistableUriPermission(uri, READ|WRITE)`（PERSISTABLE flag 加在启动 intent 上），
  `createDocument` 的 parent 用 `buildDocumentUriUsingTree(...)`
- 详见项目内 `BLUTTER_INTEGRATION.md`

---

## 五、版本支持状态

### 已编译 ✅（共 70 个）

每个版本一个独立 binary（~2.3–2.7MB，strip 后），共享依赖库全版本共用。
其中 **2.14.x 为 no-analysis 版本**（下称 †），仅 dump 对象池、不做反汇编分析。

```
2.14.1†  2.14.2†  2.14.4†
2.15.0   2.15.1
2.16.0   2.16.1   2.16.2
2.17.0   2.17.1   2.17.3
2.18.0   2.18.1   2.18.2   2.18.3   2.18.4   2.18.5   2.18.6
2.19.6
3.4.0   3.4.1   3.4.2   3.4.3   3.4.4
3.5.0   3.5.1   3.5.2   3.5.3   3.5.4
3.6.0   3.6.1   3.6.2
3.7.0   3.7.1   3.7.2   3.7.3
3.8.0   3.8.1   3.8.2   3.8.3
3.9.0   3.9.1   3.9.2   3.9.3   3.9.4
3.10.0  3.10.1  3.10.2  3.10.3  3.10.4
3.10.5  3.10.6  3.10.7  3.10.8  3.10.9
3.11.0  3.11.1  3.11.2  3.11.3  3.11.4
3.11.5  3.11.6
3.12.0  3.12.1  3.12.2
3.13.0  3.13.1  3.13.2  3.13.3  3.13.4
```

† = no-analysis 版本（2.14.x 只有 `InitStaticField` 存根，不支持反汇编分析）

### 不兼容 ❌

| 版本 | 原因 |
|------|------|
| 3.0.0~3.0.7 | `UntaggedTypeParameter::owner()` 不存在（Dart 3.1+ 才加入） |
| 3.1.0~3.1.5 | `Thread::empty_type_arguments_offset()` 不存在 |
| 3.2.0~3.2.6 | 同上 |
| 3.3.0~3.3.4 | 同上，原版 Blutter 同样不支持 |
| 2.0~2.13 | Dart < 2.14 **无指针压缩**（compressed pointers），与 blutter 内存模型结构性冲突（见下节） |

### 2.13.x 及更早（不可行 ❌）

实测 Dart 2.13.4：**dartvm 静态库可编译，但 blutter 无法编译**，根因是 Dart < 2.14 不支持指针压缩。

| 缺失符号 | 2.13.4 | 2.14.4 |
|---------|:------:|:------:|
| `dart::kCompressedWordSize` | ❌（0 处） | ✅（208 处） |
| `dart::kSentinelCid`（`V(Sentinel)`） | ❌ | ✅ |
| `dart::TypeParameters` | ❌ | ✅ |
| `dart::HEAP_BITS` | ❌ | ✅ |
| `dart::UntaggedClass::id` | ❌ | ✅ |
| `dart::Function::entry_point` | ❌ | ✅ |

blutter 的内存模型（字段解析、对象解压、堆对象遍历）完全建立在**压缩指针**之上；
缺少指针压缩需重写核心逻辑，属于结构性不兼容，成本远超版本适配本身。
此外 2.13 连 `LinkedHashSet` 都没有（Set 为 Dart 层私有类 `_CompactLinkedHashSet`，未在 C++ VM 层暴露）。

> **结论：Dart 2.14.x 是本项目能支持的最老版本**——2.14 是压缩指针引入后的第一个可用版本，
> 与上游「声明支持 ≥2.15」（`--no-analysis` 下可到 2.14）的下界一致。

### 2.14.x ~ 2.18.x（已移植 ✅）

上游原版 Blutter 声明"支持 ≥2.15"（`--no-analysis` 下可到 2.14），本项目此前缺失这一整段。
本次补齐 **18 个版本**（2.14.1/2/4、2.15.0/1、2.16.0/1/2、2.17.0/1/3、2.18.0~6）。

#### 1. Dart 2.14.x：snapshot 校验不在 `app_snapshot.cc`

Dart 2.14.x **没有** `runtime/vm/app_snapshot.cc`，snapshot 版本/features 校验代码位于
`runtime/vm/clustered_snapshot.cc` 的 `SnapshotHeaderReader::VerifyVersion()/VerifyFeatures()`，
文本与既有 `app_snapshot.cc` 的 pattern 完全一致。

- **修复**：`patch_all_snapshot.py` 找不到 `app_snapshot.cc` 时回退到 `clustered_snapshot.cc`。

#### 2. Dart 2.14.x：强制 no-analysis

2.14 缺少 `InitLateStaticField` 存根（2.16 才加入），`CodeAnalyzer_arm64.cpp` 引用
`InitLateFinalStaticFieldVMStub` 会编译失败（见下）。上游 `blutter.py` 对 `<2.15` 同样强制 no-analysis。

- **修复**：`build_blutter_bionic.py` 对 `<2.15` 自动追加 `-DNO_CODE_ANALYSIS=1`。

#### 3. Dart 2.15.x：`InitLateStaticFieldVMStub` 缺失

2.15 的 `runtime/vm/stub_code_list.h` **没有** `V(InitLateStaticField)`（2.16 才加入）。

`blutter.py` 的 `find_compat_macro()` 检测到后定义 `NO_INIT_LATE_STATIC_FIELD`，而 `pch.h` 中该宏
只重定义了非 VM 变体（`InitLateStaticFieldStub`）。本 fork 在 3.13 移植时，因 3.13 把
`OBJECT_STORE_STUB_CODE_LIST` 并入 `VM_STUB_CODE_LIST`，`DartStub` 枚举改为只用
`VM_STUB_CODE_LIST` 生成，`CodeAnalyzer_arm64.cpp` 相应改用 `InitLateStaticFieldVMStub`，
于是该宏失效，2.15 编译报 `no member named 'InitLateStaticFieldVMStub'`。

- **修复**：`pch.h` 的 `NO_INIT_LATE_STATIC_FIELD` 块补齐 VM 变体：

  ```cpp
  #  define InitLateStaticFieldVMStub InitStaticFieldVMStub
  #  define InitLateFinalStaticFieldVMStub InitStaticFieldVMStub
  ```

  对 2.16+ 该宏不定义，无副作用。

#### 4. 编译结果

| 阶段 | 命令 | 结果 |
|------|------|------|
| patch | `python patch_all_snapshot.py` | 18 个版本 snapshot 校验降级为 warning |
| dartvm | `python build_dartvm_bionic.py 2.14.1 … 2.18.5` | 18/18 OK |
| blutter | `python build_blutter_bionic.py 2.14.1 … 2.18.5` | 18/18 OK |

产物（bionic, arm64 PIE）：

```
bin/bionic/blutter_dartvm2.{14.1,14.2,14.4,15.0,15.1,16.0,16.1,16.2,17.0,17.1,17.3,
                             18.0,18.1,18.2,18.3,18.4,18.5,18.6}_android_arm64
  ~2.32–2.63 MB（strip 后）
packages/lib/libdartvm2.*_android_arm64.a   ~69.7–70.0 MB
```

| 版本段 | code analysis | 说明 |
|--------|:-------------:|------|
| 2.14.1 / 2.14.2 / 2.14.4 | ❌ | 仅 dump 对象池（同上游 `<2.15` 行为） |
| 2.15.0 / 2.15.1 | ✅ | `InitLateStaticFieldVMStub` 经 `pch.h` 宏映射到 `InitStaticFieldVMStub` |
| 2.16.0 ~ 2.18.6 | ✅ | 原生支持 `InitLateStaticField` 存根 |

> 2.14.x 的 no-analysis 版本仍可加载 snapshot 并 dump 对象池（`objs.txt`、`pp.txt`），
> 但不生成 `asm/`、`blutter_frida.js`（与上游 `--no-analysis` 语义一致），
> jniLibs 集成时按对应版本的 `libblutter_<版本>.so` 使用即可。

---

### 3.13.x（已移植 ✅）

Dart 3.13（2026-08 stable）改了 snapshot 结构（单一 snapshot、VM stub 迁移、闭包捕获内联），
官方 worawit/blutter 基线 `528acbe` 尚不支持。移植依据社区补丁
[`teng-lin/notebooklm-py` → `docs/android/blutter-dart3.13.patch`](https://github.com/teng-lin/notebooklm-py/blob/main/docs/android/blutter-dart3.13.patch)
（该补丁在 NotebookLM `1.46.7` / Dart `3.13.0-256.0.dev` 上验证）。

补丁涉及 8 个文件（`src/` 下 7 个 + `extract_dart_info.py`）：

| 文件 | 改动 |
|------|------|
| `src/ElfHelper.cpp` | 同时扫 `.dynsym` **与** `.symtab`；符号名改用字符串字面量（`kXSnapshotDataAsmSymbol` 常量在 3.13 被移除）；新增 combined snapshot（`_kDartSnapshotData`/`_kDartSnapshotText`，add-to-app library 构建）回填 |
| `src/DartApp.cpp` | 删除 `OBJECT_STORE_STUB_CODE_LIST`（已并入 VM stubs）；throw stub 改用 `dart::StubCode::Throw()` |
| `src/DartStub.h` | 删除 `OBJECT_STORE_STUB_CODE_LIST` 枚举 |
| `src/DartLoader.cpp` | `Dart_InitializeParams` 不再有 `vm_snapshot_data/instructions`（VM snapshot 已内建进 runtime） |
| `src/CodeAnalyzer_arm64.cpp` | stub 名 `XxxStub`→`XxxVMStub`（11 处）；补 `AOT_Closure_context_offset` / `AOT_Closure_delayed_type_arguments_offset` = `-1` |
| `src/FridaWriter.cpp` | 补 `AOT_Closure_context_offset` = `-1`（闭包不再有独立 context 字段） |
| `src/DartTypes.cpp` | 未识别的 abstract type class id 由 `FATAL` 降级为 `Type(cid)` |
| `extract_dart_info.py` | 兼容 `.dynsym`/`.symtab` + vaddr→file offset 换算 |

补丁留档于 `<blutter>/patches/blutter-dart3.13.patch`（同目录另存上游原版 `orig-blutter-dart3.13.patch`）。

> 另一条 3.13 移植线：社区 fork `dedshit/blutter-termux`
> （`Add Dart 3.13 single-snapshot support` 等提交），可作对照。

---

### ⚠️ 补丁之外的必要修复（3.13 移植不完整之处）

社区补丁只让 blutter **能加载并进入分析**。实测在本项目目标 App
（`libapp.so` 12.6 MB，Dart 3.13.2 stable，snapshot hash `0451907c…`）上，
分析会**被 OOM Killer 杀死**（`退出码 137`），峰值 RSS 4.6 GB、耗时约 7 分钟才失败。

> **结论：这不是补丁的编码错误，而是补丁未覆盖的 3.13 变化。**
> 既有 3.4~3.12 版本不受影响（那些版本 `Code::PayloadStart()` 有效）。

#### 1. 函数尺寸计算失效 → 反汇编范围失控（内存爆炸的根因）

- Dart 3.13 AOT 下 `UntaggedCode::instructions_` 被置为 `Instructions::null()`
  （`runtime/vm/app_snapshot.cc`: *"There are no serialized RawInstructions objects in this mode"*），
  `Code::PayloadStart()` 于是退化为 `EntryPoint() - entry_offset`；
  而 `instructions_length_` 对部分 Code 是垃圾值（实测为 `12`）。
- blutter 的 `DartFunction::Size()` = `payloadSize - (ep_addr - payload_addr)`，
  因此把这些 Code 算成 **4.59 MB / 6.27 MB** 的"函数"（libapp 总共才 12.6 MB），
  按其尺寸反汇编 → 上百万条指令 → 内存耗尽。

诊断日志（修复前）：

| fn | 地址 | `Size()` | `payloadSize` | 名称 |
|----|------|---------:|--------------:|------|
| #1 | `0xbeecc0` | 676 | 676 | `register` |
| #2 | `0x792efc` | **4,590,680** | 12 | `Srf` |
| #3 | `0x5f9e08` | **6,266,188** | 12 | `<anonymous closure>` |

**修复**：新增 `DartApp::fixupFunctionSizes()`，在 `LoadInfo()` 中 `finalizeFunctionsInfo()` 之后调用 ——
用「**到下一个已知代码起点（函数或 stub）**」的距离界定函数尺寸，
仅在原值不合理（`≤0` 或大于该间距）时才覆盖（`DartFunction::SetFixedSize()`）。

实测：修正 **5562 / 7914** 个函数；峰值 RSS **4.6 GB → 294 MB**；
分析完整跑完（5235 个函数），产出 ≈133 MB（`asm/`、`blutter_frida.js`、`ida_script/`、`objs.txt`、`pp.txt`）。

#### 2. 未捕获异常中止整个分析

| 位置 | 问题 | 修复 |
|------|------|------|
| `getPoolObject()` | 对 object pool 的 `kNativeFunction` 条目直接 `throw std::runtime_error`，且**无人捕获** → 整个分析中止、零产出 | 降级为占位值（同 `kImmediate` 处理） |
| `processCallLeafRuntime` / `processLoadStore` | 6 处 `INSN_ASSERT` 失败即抛异常，导致该函数整体失败 | 改为优雅 `return nullptr`（交由其他模式处理） |

#### 3. 两处 3.13 codegen 模式变化

| 位置 | 变化 | 修复 |
|------|------|------|
| `processBoxInt64Instr` | 3.13 的 `BoxInt64Instr::EmitNativeCode` 按 `FlowGraph::NeedsFrame()` 决定是否内联 `EnterDartFrame`，与"函数整体是否使用 FP"并不一致；原实现以 `fnInfo->useFramePointer` 为前置条件，导致断言反复失败（十余次） | 去掉前置条件，始终按精确模式消费该帧 |
| `processCallLeafRuntime` | `mov xTmp, THR; ldr xOther, [xTmp, #大偏移]` 序列被误匹配（原实现只校验 `ldr` 的**基址**寄存器） | 补「**同寄存器**」校验（`ldr xTmp, [xTmp, …]`） |

#### 4. 诊断辅助（长期保留）

`main.cpp` 开头加入 `setvbuf(stdout, nullptr, _IONBF, 0)` / `setvbuf(stderr, …, _IONBF, 0)`。

stdout 在重定向到管道或文件时是**块缓冲**：进程若未正常结束（被 OOM / 超时杀掉），
缓冲中的日志会全部丢失 —— 这正是"日志停在 `ClassId=172` 之后、看起来像卡住"这一假象的来源。
无缓冲后，各阶段日志（`libapp is loaded` / `LoadInfo begin|done` / `Analyzing the application` /
`analysis done: N functions`）才能实时可见；定位根因所用的「**每个函数的地址、`Size()`、
`payloadSize`、名称与峰值 RSS**」日志是诊断期临时加入的，已移除。

### 体积

```
jniLibs/arm64-v8a/ 共 75 个文件 ≈ 225MB（按 70 个版本推算）
  ├─ 70 × libblutter_<版本>.so   ≈ 2.3–2.7MB/个
  └─ 共享库（capstone + 3×ICU + libc++_shared）
```

---

## 六、Windows 注意事项

1. **NDK 自动切换**：Windows 上用 `toolchains/llvm/prebuilt/windows-x86_64`，
   clang 包装器为 `aarch64-linux-android24-clang.cmd`、`llvm-strip.exe`。
2. **构建命令**：统一 `cmake --build <dir> --parallel N`（不再依赖 `make`）。
3. **ICU 是唯一麻烦点**：ICU 用 autotools（`configure` + `make`）。
   - 原生 Windows 需 **MSYS2**（提供 make）或 **WSL2**；
   - **推荐**：在 Linux/WSL 上构建一次，把 `<blutter>/ndk_out/icu-android-shared-install`
     整个目录拷到 Windows（ICU 是一次性依赖）；
   - MSYS2 环境下可 `set MAKE=C:\msys64\usr\bin\make.exe`。
4. Capstone / Dart VM / blutter / jniLibs：纯 cmake + Python，Windows 原生可直接跑。
5. 详见 `<blutter>/BUILD_XPLATFORM.md`。
6. **从 Linux 拷贝依赖时的两个坑**（本项目已修，可复现参考）：
   - ICU 的 `libicu*.so`、`libicu*.so.70` 均为 **symlink**，拷到 Windows 会变成 16~18 字节的
     文本文件（内容为链接目标名）→ 必须用真实 `.so.70.1` 的内容覆盖，
     否则 cmake/ninja 报 `missing and no known rule to make it`；
   - `packages/lib/cmake/dartvm*_android_arm64/dartvmTarget.cmake` 的
     `INTERFACE_LINK_LIBRARIES` 里留着**构建机绝对路径**的 ICU
     （`/home/...` 或 `D:/...`）。`blutter/CMakeLists.txt` 已改为**只保留非绝对路径项**
     （`IS_ABSOLUTE` 过滤），ICU 一律由 `<blutter>/ndk_out` 显式链接，
     从而同一份源码既能编已有 70 个版本也能编新增版本。

---

## 历史方案（已废弃）

以下路线均**不再使用**，保留以便对照：

- **Android chroot 原生编译**（Android 设备内 Ubuntu arm64 chroot，`g++-13` 原生编译）——
  最早做法，编译慢、依赖设备环境。
- **x86 Linux + NDK 交叉编译 glibc 动态版**（部署目录 `bin/blutter_android/` +
  `blutter.sh` 显式 `exec ld-linux-aarch64.so.1`，191MB）—— **已废弃**，根因：
  1. `patch_needed` 破坏 dynstr（`GCC_4.5.0` 首字节被清零）；
  2. glibc loader 要求 `NEEDED = 文件名 = SONAME = verneed` 四者一致，
     与 jniLibs 必须去版本号（`.so` 结尾）**结构性冲突**；
  3. 改用 bionic（linker64 容忍 NEEDED≠SONAME）后问题消失。
- **全静态编译**（`g++ -static`，零 NEEDED，39MB/版本 × 10 版本 = 390MB）—— 体积过大，
  仅在极端情况下作为回退。

原脚本备份：`<blutter>/.xplat_backup/`。
