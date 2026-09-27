# FlutterAndroid Blutter 集成方案复盘

> **当前正式方案**：方案⑪ —— 内置 jniLibs bionic 动态版（NDK 交叉编译，Android linker64 原生加载）。
> 47 个版本、SAF 输出目录一次性授权永久有效，真机（KKG-AN00/Android 10）已验证全流程：选择输入 →
> 检测 Dart 版本 → 运行分析 → 打包导出 zip。历史方案①-⑩ 见下文复盘。

## 目标

在 Android App 中以非 root 权限运行 blutter（glibc ELF 二进制），分析 Flutter 应用的 `libapp.so`。

## 核心约束

| 约束 | 说明 |
|------|------|
| **noexec** | `/data/user/0/<pkg>/` 目录挂载了 `noexec`，不能 execve、不能 mmap PROT_EXEC |
| **seccomp** | Android 内核用 seccomp-bpf 拦截了 `execveat`、`process_vm_readv` 等系统调用 |
| **jniLibs** | `lib/arm64-v8a/` 下的 `.so` 文件被 PackageManager 提取到 `nativeLibraryDir`（非 noexec），但只提取文件名以 `.so` 结尾的文件 |
| **ABI 隔离** | 在 ARM64 设备上运行的 chroot（Ubuntu）只有 g++/glibc，没有 NDK 的 clang/Bionic |
| **编译环境** | ARM64 设备通过外部 MCP Shell 工具（`mcp_mcp_shell`）连接，非 App 内置 shell。所有 chroot 内操作均在此环境中执行 |

---

## 尝试过的方案

### 方案 ①：直接 execve（失败：126）

**做法**：把 blutter 二进制放进 `filesDir/blutter_env/`，`ProcessBuilder("sh", "blutter.sh")`

**结果**：exit code 126（Permission denied）

**原因**：`/data/user/0/<pkg>/files/` 是 noexec 挂载点，`execve` 被内核拒绝。

---

### 方案 ②：静态 PIE runner + memfd_create + fexecve（失败：159）

**做法**：编译一个静态 PIE 小工具 `runner`，放在 `filesDir/`（只是读取，不 exec）；
由 `runner` 用 `memfd_create` 把 ld-linux 写入匿名 fd，再调用 `fexecve` 从内存执行。

```
runner (静态 PIE, filesDir)
  → memfd_create("ld-linux")
  → 写入 ld-linux 内容
  → fexecve(memfd, ...)     ← 被 seccomp 拦截
```

**结果**：exit code 159（SIGSYS）

**原因**：`fexecve` 内部使用 `execveat` 系统调用，被 Android 的 seccomp-bpf 拦截。

---

### 方案 ③：runner + execve(/proc/self/fd/N)（失败：126）

**做法**：同上，但把 `fexecve` 改为 `execve("/proc/self/fd/<memfd>")`，用 `execve` 系统调用绕过拦截。

**结果**：exit code 126

**原因**：`/proc/` 挂载了 `noexec`，内核在看到路径在 proc 上就拒绝了。

---

### 方案 ④：runner + execve(ld-linux) from nativeLibraryDir（失败：159）

**做法**：把 `ld-linux-aarch64.so.1` 放进 `jniLibs/arm64-v8a/`（非 noexec），
`ProcessBuilder` 直接 execve 它，让它去加载 `blutter_env/` 下的二进制和运行时库。

```
execve(nativeLibraryDir/ld-linux, [ld-linux, blutter_env/blutter_binary, ...])
  → ld-linux 读取 blutter_binary（只需读权限）✅
  → ld-linux 从 blutter_env/lib/ 加载 libc.so.6 等 NEEDED（只需读权限）❌
```

**结果**：exit code 159（SIGSYS）

**原因**：**noexec 不仅拦截 execve，也拦截 mmap(PROT_EXEC)**。即使只是读取 `.so` 文件来加载代码段，内核也会拒绝在 noexec 分区上 mmap 可执行内存。`blutter_env/lib/` 在 noexec 上，所以当 ld-linux 试图 mmap `libc.so.6` 的代码段时触发 SIGSYS。

---

### 方案 ⑤：全部放进 jniLibs（改名 + 改 NEEDED）

**做法**：把所有运行时 `.so`（libc.so.6、libm.so.6、libcapstone.so.4 等）重命名为 `.so` 结尾放进 `jniLibs/`，
PackageManager 提取到 nativeLibraryDir（非 noexec）。  
用 Python 脚本修改 blutter `.so` 的 `DT_NEEDED` 条目指向新名字。

```
jniLibs/arm64-v8a/
├── libldlinux.so          (原 ld-linux-aarch64.so.1)
├── libc.so                (原 libc.so.6)
├── libm.so                (原 libm.so.6)
├── libcombined.so         (capstone + ICU 合并)
├── libblutter_3_12_2.so   (NEEDED→全部指向上述 .so)
├── ...
```

**结果**：exit code 159

**原因**：同上。即使所有 `.so` 都在非 noexec 分区，glibc 的 ld-linux 在动态加载过程中调用了被 seccomp 拦截的系统调用。具体哪个 Syscall 不确定，可能是 `personality()`、`arch_prctl` 或其他 glibc 特有的调用。

---

### 方案 ⑥：NDK 编译（失败：C++ ABI 不兼容）

**做法**：在 Windows 上用 Android Studio 的 NDK（`aarch64-linux-android21-clang`）编译 blutter C++ 源码 + Dart VM `.a` + ICU + Capstone，产出 Bionic 链接的 `.so`，可直接 `System.loadLibrary()`。

```
CMakeLists.txt → NDK clang → libblutter.so (Bionic)
  → System.loadLibrary()
  → 进程内调用，零 execve，零 noexec
```

**中间成果**：
| 问题 | 解决 |
|------|------|
| Capstone 编译 | ✅ FetchContent 自动拉 NDK 编译 |
| C++ 源码编译 | ✅ 用 `-DDART_PRECOMPILED_RUNTIME=1 -DTARGET_ARCH_ARM64=1` 通过 |
| `std::atomic_ref` | ✅ 创建兼容头文件 `compat/atomic_ref` |
| ICU 版本 (78→70) | ✅ `build_icu.py` + chroot 的 ICU 70 .a 解决 |
| **Dart VM C++ ABI** | ❌ **不可修复** |

**根本原因**：Dart VM `.a` 在 chroot 里用 **GCC** 编译。`dartvm_fetch_build.py` 调用 cmake，cmake 自动选择 `/usr/bin/c++`（GCC 13）。

```
chroot (ARM64):
  dartvm_fetch_build.py → cmake → /usr/bin/c++ (GCC 13)
  → 产出 GCC ABI 的 .o
    - 使用 libstdc++ 内部符号（_Rb_tree_*、__once_callable、__once_proxy）
    - C++ 异常使用 libsupc++

Windows NDK (x86_64):
  aarch64-linux-android21-clang++ → 使用 LLVM libc++
  → 不提供 GCC 内部符号
    - _Rb_tree_* → libc++ 实现不同
    - __once_callable → libc++ 无此符号
```

**尝试的修复**（均无效）：
- 加 `-lstdc++ -lc++abi`：NDK 的 `-lstdc++` 实际指向 libc++，不是 GCC libstdc++
- 创建 `gcc_shim.cpp` 提供 `__once_proxy` 等：杯水车薪，差异几百个符号
- ICU 70 .a 替换：符号匹配了，但 C++ ABI 问题依然存在

**结论**：Dart VM `.a` 必须用与链接相同的工具链编译。ARM64 chroot 无法运行 x86_64 的 NDK，`dartvm_fetch_build.py` 只能用 GCC。要在 x86_64 机器上重跑 `dartvm_fetch_build.py`，才会产出 NDK clang 兼容的 `.a`。

---

### 方案 ⑦：全静态编译（成功！）

**做法**：在 chroot 里用 `g++-13 -static` 编译，所有依赖（blutter + Dart VM + ICU + Capstone + glibc）全静态链接成一个单一 ELF。

```bash
g++-13 -static -O3 -o libblutter_3_12_2.so \
    src/*.cpp \
    libdartvm.a libcapstone.a libicuuc.a libicudata.a \
    -lpthread -ldl
```

**结果**：
- 编译：✅ 成功
- chroot 内运行：✅ 正常
- Android 真机：未测试，但理论上无 noexec 问题

**特点**：
- **零 NEEDED 条目**（`readelf -d` 为空）
- **无 ld-linux 依赖**
- `execve` 后内核直接加载所有代码段
- 39MB/版本，10 个版本 390MB APK

---

### 方案 ⑧：static-pie（方案 ⑦ 的变体，成功！）

**做法**：用 `-static-pie` 代替 `-static`，产出位置无关的静态可执行文件。

```bash
g++-13 -static-pie -O3 -o libblutter_3_12_2.so ...
```

**结果**：
- 编译：✅ 成功
- chroot 内运行：✅ 正常
- 44MB/版本（比 `-static` 大 5MB）
- 零 NEEDED

与方案 ⑦ 无本质区别，只是可执行文件是 PIE 格式。

---

### 方案 ⑨：bsdiff 补丁（优化方案 ⑦ 的体积）

**做法**：只编译一个基准版本（如 3.4.4），用 `bsdiff` 生成到其他版本的二进制补丁。  
在 Gradle 打包前展开成全量 `.so`。

```
基准 3.4.4:       39MB
补丁 3.4.4→3.5.4:  363KB
补丁 3.4.4→3.12.2: 994KB
...
10 个补丁总计:      7MB
bspatch 工具:     704KB (static-pie)
```

**结果**：技术上可行，已验证 SHA256 完全匹配。

**区别**：这优化的是**项目的存储体积**（git 仓库不用存 390MB 的二进制），不是 APK 体积（Gradle 展开后 APK 仍为全量）。

---

## 结论

### 可行的路线（二选一）

#### 路线 A：全静态编译（当前可用）

在 ARM64 chroot 中用 `g++-13 -static` 编译，产出零依赖的 ELF，直接 execve。

- 已在 chroot 验证通过
- 39MB/版本
- 可用 bsdiff 补丁优化存储（~1MB/版本）

#### 路线 B：NDK 编译（需在 x86_64 机器上重编 Dart VM）

`execve` 执行，Android `/system/bin/linker64` 加载，无 glibc、无 noexec 问题。

**核心条件**：Dart VM `.a` 必须用 NDK clang 编译（详见 `EXTERNAL_SO_ANALYSIS.md`）。

```bash
# 在 x86_64 Linux/Mac/Windows 上（chroot ARM64 无法运行 NDK）：
python3 dartvm_fetch_build.py 3.12.2 android arm64
# 产物：NDK ABI 兼容的 .a → 可正常链接
```

关键差异（对比路线 A）：
- 编译目标：**PIE executable**（`-fPIE -pie`），interpreter = `/system/bin/linker64`
- **去掉 NEEDED 版本后缀**：链接时用 `-l:libcapstone.so` 而非 `-lcapstone`
- **C++ 运行时用 `libc++_shared.so`**（NDK 标准）
- 产物 ~3-4MB/版本（vs 39MB 静态）
- ICU **78 可以工作**（NEEDED 不关心版本后缀）

### 当前状态

| 组件 | NDK 编译情况 |
|------|------------|
| Blutter C++ 源码 | ✅ CMake + NDK clang 编译通过 |
| Capstone | ✅ FetchContent 下载 NDK 编译 |
| ICU | ✅ 已从 Termux 获取 ICU 78 的 .so |
| Dart VM `.a` | ❌ 需在 x86_64 机器上用 NDK clang 重编 |

### 推荐

- **短期**：路线 A（全静态）
- **长期**：找一台 x86_64 机器跑 `dartvm_fetch_build.py` 产出 NDK 兼容的 `.a`，后切换到路线 B

> **落地现状**：上述"长期"路线 B 已在 x86_64 Linux + Android NDK r27c 上全量跑通——见下方
> **方案⑪（bionic 动态版，当前正式方案）**，47 个版本全部编译并真机验证通过。


---

## 方案 ⑩：内置 jniLibs glibc 动态版（已废弃）

### 背景

方案 ⑦⑧（全静态）体积大（39MB/版本），路线 B（NDK bionic）当时受制于 Dart VM `.a` 需 NDK clang 重编。
现已在一台 **x86_64 Linux** 上用 **Android NDK r27c 的 clang（glibc 交叉 wrapper）** 完成了全部 47 个版本
Dart VM `.a` 的交叉编译（glibc ABI，非 GCC），并动态链接出每版本一个 binary。

### 与旧 glibc 方案（④⑤）的关键差异

旧方案 ④⑤ 的库是 **chroot GCC 编译**（OS/ABI GNU、GCC ABI）；新库是 **NDK clang 编译**（OS/ABI SYSV、LLVM），
且链接时移除了 `-lpthread/-ldl`（glibc 2.41 已并入 libc），运行时不再触发 glibc 特有 syscall 路径。

### 部署结构（全部内置 jniLibs/arm64-v8a，无需导入环境包）

```
jniLibs/arm64-v8a/                      （191MB）
├── libblutter_3_4_0.so ...             （47 个版本，~3.2MB 每个，strip）
├── libldlinux.so                       （ld-linux-aarch64.so.1 改名）
├── libc.so / libm.so / libgcc_s.so     （glibc 2.41 运行时）
├── libstdcpp.so                        （libstdc++.so.6）
├── libicuuc.so / libicudata.so / libicui18n.so   （ICU 70.1）
└── libcapstone.so                      （Capstone 4.0.2）
```

所有 `.so` 的 `DT_NEEDED` 已去掉版本后缀（libc.so.6→libc.so 等），PackageManager 可全部提取到
`nativeLibraryDir`（非 noexec）。App 通过 `execve(nativeLibraryDir/libldlinux.so, libblutter_<版本>.so ...)`
执行，`LD_LIBRARY_PATH=nativeLibraryDir`。

### 本仓库已适配项（去除的"用不到的功能"）

| 组件 | 处理 |
|------|------|
| `app/src/main/cpp/`（NDK 编译方案：blutter_src/dartvm_libs/dartvm_include/prebuilt/_deps/CMakeLists/blutter_jni.cpp） | 删除（970MB） |
| `app/.cxx/`（CMake 缓存） | 删除（173MB） |
| `app/build.gradle.kts` 的 `externalNativeBuild` + `ndkVersion` | 移除 |
| `BlutterNative.kt`（System.loadLibrary + fork，依赖已删 JNI 层） | 删除 |
| 环境包导入机制（`importEnvZip`/`blutter_env`/设置页"导入环境包"UI/`KEY_ENV_IMPORTED`） | 移除，运行库已内置 |
| `MainActivity` 状态文案 | "环境包: 已导入" → "内置运行库: 已部署" |
| `checkPrerequisites` | 不再要求 `blutter_env/lib/ld-linux-aarch64.so.1`，只检查内置 `libldlinux.so` |

### 构建与体积

- 47 个版本 binary 合计 **144MB** + 运行时库 **47MB** = **191MB**（旧方案 ⑦ 10 个版本 390MB）
- 库来源：`/home/ace77505/blutter/bin/blutter_android/`（x86_64 NDK 交叉编译，见该仓库 `build_all_glibc.py`）
- 重生成 jniLibs：复制 + 改名 + `patch_needed.py`（原地改 DT_NEEDED，全部缩短/等长安全）

### 待验证

- 真机运行验证（execve glibc loader 的 seccomp 行为取决于设备 Android 版本/内核）
- 若个别设备仍触发 SIGSYS（方案⑤现象），回退路线 A（全静态）或改 bionic 路线 B

> **注**：方案⑩（glibc 动态）已废弃。根因：patch 破坏 dynstr（GCC_4.5.0 首字节被清 0）；
> 且 glibc loader 要求 NEEDED=文件名=SONAME=verneed 四者一致，与 jniLibs `.so` 结尾（去版本号）结构性冲突。

---

## 方案 ⑪：内置 jniLibs bionic 动态版（当前正式方案 ✅，真机已验证）

### 背景

方案⑩（glibc）废弃后，改用 **Android NDK 的 android.toolchain + bionic 运行时** 交叉编译出
每版本一个 binary。产物是 Bionic 链接的 PIE executable：

- interpreter = `/system/bin/linker64`（Android 原生 loader）
- `DT_NEEDED` 无版本后缀、且容忍 NEEDED≠SONAME（Android linker 原生行为）
- 无 glibc 依赖，天然规避方案⑤的 SIGSYS 问题

### 编译（x86_64 Linux + Android NDK r27c）

```bash
# 1) bionic Dart VM .a（NDK clang + 显式 ICU include/lib + 3.12+ 注入 atomic_ref 兼容头）
python3 build_dartvm_bionic.py

# 2) 47 个 blutter bionic binary（find_compat_macro + cmake + make + strip → bin/bionic/，~2.6MB/个）
python3 build_blutter_bionic.py

# 3) 生成 jniLibs（47 binary + libcapstone.so + 3 ICU .so + libc++_shared.so，含 patch_needed）
./build_jnilibs_bionic.sh build_bionic_
```

### 部署结构（全部内置 jniLibs/arm64-v8a，无需导入环境包，共 52 文件 167MB）

```
jniLibs/arm64-v8a/
├── libblutter_<版本>.so    （47 个版本，NDK bionic PIE，strip，~2.6MB/个）
├── libcapstone.so          （Capstone 4.0.2）
├── libicuuc.so / libicudata.so / libicui18n.so   （ICU 70.1）
└── libc++_shared.so        （NDK libc++ 运行时，blutter 依赖链使用）
```

所有依赖 `.so` 的 `DT_NEEDED` 经 `patch_needed.py` 缩短为无版本号（needed 闭合），Android linker64
可正常 resolve。App **直接 `execve(nativeLibraryDir/libblutter_<v>.so)`**，子进程设置
`LD_LIBRARY_PATH=nativeLibraryDir`（linker64 不自动搜 nativeLibraryDir）。

### 关键适配

| 项 | 处理 |
|----|------|
| snapshot 校验 | patch `app_snapshot.cc` 两处（hash 校验 / VerifyFeatures）降级为 warning，否则预编译 dartvm 无法匹配任意 Flutter 引擎 |
| 版本检测 | 用 `\x00` 前缀正则（官方 extract_dart_info.py 逻辑），否则误匹配到 libflutter.so 里的次要版本串 |
| 版本选择 | `detectDartVersion` 读 libapp.so 整文件 + `\x00` 前缀 → 精确选 `libblutter_X_X_X.so` |
| std::atomic_ref | Dart 3.12+ 需 `compat/atomic_ref_compat.h`（`-include` 注入，支持无默认构造 trivially-copyable） |
| Dart VM ABI | 全部用 NDK clang 编译（非 chroot GCC），与 bionic 链接链一致 |

### App 全流程（真机 KKG-AN00 / Android 10 已验证）

`选择 libapp.so → detectDartVersion(\x00 前缀) → execve libblutter_3_4_4.so（LD_LIBRARY_PATH）→
生成 asm/ objs.txt pp.txt blutter_frida.js → 打包 zip 导出`

### SAF 输出目录（选一次永久有效，已联网核对官方规范）

- `takePersistableUriPermission(uri, READ|WRITE)` 只传两个 flag；**PERSISTABLE 加在启动
  `ACTION_OPEN_DOCUMENT_TREE` intent 的 `addFlags` 上**（用 `StartActivityForResult` + 自建 intent，
  而非默认 `OpenDocumentTree()` 合约，后者不会带 PERSISTABLE flag）。
- `DocumentsContract.createDocument` 的 parent 必须是
  `buildDocumentUriUsingTree(treeUri, getTreeDocumentId(treeUri))` 得到的
  `.../tree/<id>/document/<id>`，**不能传裸 tree URI**（否则 provider 报 `Invalid URI`）。
- tree URI 保持授权返回的编码形式（`%3A`），不要还原成 `: `。

### 设备实测结果

- 无需 root 即可完成整个分析+导出流程
- `blutter_output_<时间戳>.zip`（140MB，1765 文件：asm/ + blutter_frida.js + objs.txt + pp.txt）
  成功写入用户选择的 SAF 目录，CRC 校验与源文件字节一致
- 授权持久化落盘 `/data/system/urigrants.xml`（modeFlags=3），重启后无需重选
- 日志每行带 `[hh:mm:ss]` 时间戳；输出目录显示完整 `content://...` URI

### 体积对比

| 方案 | 体积/版本 | 总 jniLibs |
|------|----------|-----------|
| ⑦ 全静态 | 39MB | 10 版本 390MB |
| ⑩ glibc 动态 | ~3MB | 191MB |
| **⑪ bionic 动态（当前）** | **~2.6MB** | **47 版本 52 文件 167MB** |

