# 外部参考 .so 分析报告

分析对象：`/root/lib/arm64-v8a/`（别人编译好的可运行版本）

## 文件清单

```
libblutter.so          (3.0MB)  ← 主程序
libblutter_2_14.so     ~ 3.9MB  ← 各 Dart 版本
...
libblutter_3_12.so     (4.2MB)
libcapstone.so         (8.8MB)
libc++_shared.so       (1.3MB)
libicudata.so          (31.6MB)
libicuuc.so            (2.1MB)
```

## 与我们的关键差异

### 1. 编译工具链：NDK Clang（不是 GCC）

| 属性 | 外部 .so | 我们的 chroot 产物 |
|------|---------|-------------------|
| OS/ABI | `UNIX - System V` (0) | `UNIX - GNU/Linux` (3) |
| 编译器 | **Clang/LLVM** | GCC 13 |
| C++ 运行时 | `libc++_shared.so` | libstdc++ / libsupc++ |
| 链接器 | `/system/bin/linker64` (Bionic) | `/lib/ld-linux-aarch64.so.1` (glibc) |

OS/ABI = 0 是 Clang/NDK 的标志，= 3 是 GCC 的标志。外部 .so 全部是 NDK 编译的。

### 2. 文件类型：PIE 可执行文件（不是共享库）

```
file libblutter.so → ELF 64-bit LSB pie executable, interpreter /system/bin/linker64
```

虽然叫 `.so`，但实际上是 **PIE 可执行文件**。意味着它们是通过 `execve` 执行的，不是 `System.loadLibrary()`。

### 3. NEEDED 条目无版本号

```
我们的 blutter .so：             外部的 blutter .so：
  NEEDED libcapstone.so.4          NEEDED libcapstone.so
  NEEDED libicuuc.so.70            NEEDED libicuuc.so
  NEEDED libc.so.6                 NEEDED libc.so
  NEEDED libm.so.6                 NEEDED libm.so
  NEEDED ld-linux-aarch64.so.1     NEEDED (无 − 用 /system/bin/linker64)
```

外部版本**去掉所有版本后缀**。这意味着：
- `libcapstone.so` → PackageManager 提取 ✅
- `libicuuc.so` → PackageManager 提取 ✅
- `libc.so` / `libm.so` → PackageManager 提取 ✅（Bionic 原生库，无需打包）

### 4. ICU 版本：78（不是 70）

```
libicuuc.so SONAME: libicuuc.so.78    ← ICU 78！
```

但 NEEDED 条目是 `libicuuc.so`（无版本号）。运行时 Bionic 的 linker64 按文件名 `libicuuc.so` 查找，找到后读取 SONAME 验证。

## 能运行的原因总结

```
NDK clang (x86_64)
  ↓ 交叉编译
PIE executable, interpreter /system/bin/linker64
  ↓ NEEDED 无版本号
全部 .so 可放进 jniLibs（.so 结尾）
  ↓ PackageManager 提取
nativeLibraryDir（非 noexec）
  ↓ execve
Android linker64 加载所有 NEEDED .so
  ✓ 所有文件在非 noexec 分区
  ✓ 使用 Bionic libc，不碰 glibc
  ✓ 不触发 seccomp（标准 Android 加载路径）
```

## 对我们的启示

1. **Dart VM .a 必须用 NDK Clang 编译**（不能在 chroot 里用 GCC）
2. **编译目标为 PIE executable，interpreter = /system/bin/linker64**
3. **去掉所有 NEEDED 版本后缀**（链接时用 `-l:libcapstone.so` 而非 `-lcapstone`）
4. **ICU 78 可以工作**（版本后缀只在 SONAME 里，NEEDED 不关心）
5. **Capstone、ICU 等依赖库预先编译好放入 jniLibs**
