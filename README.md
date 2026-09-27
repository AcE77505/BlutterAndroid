# FlutterAndroid — App 内集成 Blutter 的 Flutter 逆向工程工具

一个 Android App：在设备本地对 Flutter 应用的 `libapp.so` 做逆向分析
（反汇编 + 对象池 dump + Frida 脚本生成），支持 **Dart 2.14 ~ 3.13** 共 70 个版本。

> 核心逆向引擎是 [blutter](https://github.com/worawit/blutter)（MIT）。
> 本项目将其**交叉编译为 Android bionic 版 PIE 可执行文件**，以 `jniLibs` 形式集成进 App，
> 由 App 在运行时 `execve` 调用（子进程设 `LD_LIBRARY_PATH`）。

## 特性

- **全版本覆盖**：`libblutter_<版本>.so` 每版本一个，共 70 个（Dart 2.14.1 ~ 3.13.4）。
- **无需 root**：产物放 `jniLibs/arm64-v8a/`，由 PackageManager 提取到可执行目录。
- **跨平台构建**：Linux / Windows 同一套脚本，Windows 自动切换 NDK toolchain 与命令后缀。
- **自包含**：Dart SDK 源码、静态库均按需拉取/构建，不进仓库。

## 目录结构

```
FlutterAndroid/
├── app/                       # Android App（Kotlin）
│   └── src/main/java/com/ace77505/flutter/
├── blutter/                   # 逆向引擎（blutter fork + 构建脚本）
│   ├── blutter/src/           #   blutter C++ 源码（含 fork 改动）
│   ├── *.py                   #   构建/打包脚本
│   ├── patches/               #   上游补丁 + fork 改动留档
│   ├── ndk_src/               #   第三方源码归档（capstone / icu）
│   └── dartsdk/ packages/ bin/ ndk_out/   # 生成物，已 gitignore
├── BLUTTER_ANDROID_BUILD.md   # ★ 编译与部署详解
├── BLUTTER_INTEGRATION.md     #   App 侧集成说明
├── EXTERNAL_SO_ANALYSIS.md    #   外部 so 分析笔记
└── THIRD_PARTY_NOTICES.md     #   第三方许可声明
```

## 构建

编译环境、依赖、脚本与平台注意事项见 **[BLUTTER_ANDROID_BUILD.md](BLUTTER_ANDROID_BUILD.md)**。

快速概览（Windows 需设 `NDK` 与 `CMAKE_GENERATOR=Ninja`）：

```bash
cd blutter
python patch_all_snapshot.py          # 降级 snapshot 校验为 warning
python ndk_out/icu_host_build.py      # 预构建 ICU / capstone（一次性）
python ndk_out/icu_android_build.py --shared
python ndk_out/capstone_android_build.py
python build_dartvm_bionic.py         # 编译 dartvm 静态库
python build_blutter_bionic.py        # 编译 blutter 可执行文件
python build_jnilibs_bionic.py        # 汇总为 jniLibs
```

App 侧集成（SAF 输出目录、`execve` 调用）见 **[BLUTTER_INTEGRATION.md](BLUTTER_INTEGRATION.md)**。

## 支持版本

| 版本段 | 状态 | 备注 |
|--------|------|------|
| 2.14.1 / 2.14.2 / 2.14.4 | ✅ | **no-analysis**（仅 dump 对象池） |
| 2.15.0 / 2.15.1 | ✅ | |
| 2.16.0 ~ 2.18.6 | ✅ | |
| 2.19.6 | ✅ | |
| 3.4.0 ~ 3.13.4 | ✅ | 含 3.13 移植 |
| 3.0.x ~ 3.3.x | ❌ | 见文档「不兼容」 |
| 2.13.x 及更早 | ❌ | Dart <2.14 无指针压缩，结构性不兼容 |

## 预编译二进制

仓库只含源码。体积较大的预编译产物（`libblutter_*.so`、`libdartvm*.a`）
如提供，通过 **[GitHub Releases](../../releases)** 附件分发。

## 许可

本项目采用 **MIT** 许可（见 [LICENSE](LICENSE)）。

整合的第三方组件（blutter、Dart SDK、Capstone、ICU、Android NDK 等）
版权归各自作者，许可与改动说明见 **[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)**。
其中 `blutter/` 源自 [worawit/blutter](https://github.com/worawit/blutter)（MIT），
本 fork 的改动全量留档于 `blutter/patches/fork-local-changes.patch`。
