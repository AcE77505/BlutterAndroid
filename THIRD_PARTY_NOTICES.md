# 第三方组件与许可声明（THIRD PARTY NOTICES）

本项目（FlutterAndroid）在开发与构建过程中使用了以下第三方开源项目。
各组件版权归其各自作者所有，遵循其原始许可。本仓库**只入库源码与脚本**，
不包含下列第三方组件的源码树或其构建产物（除非另有说明）。

---

## 1. blutter —— Flutter AOT 逆向工具

- **来源**：https://github.com/worawit/blutter
- **作者**：Worawit Wangwarunyoo
- **许可**：MIT
- **本仓库位置**：`blutter/`
- **说明**：本项目的核心逆向引擎。本仓库对其做了**修改与扩展**，主要包括：
  - bionic（Android NDK）交叉编译适配，产出可被 App 以 `execve` 调用的 PIE 可执行文件；
  - Dart 3.13 移植（依据社区补丁，见 `blutter/patches/`）；
  - Dart 2.14 ~ 2.18 版本适配（`patch_all_snapshot.py`、`build_blutter_bionic.py`、`pch.h`）。
  - **本地改动全量留档**：`blutter/patches/fork-local-changes.patch`（相对上游基线 `528acbe`）。
- 许可全文见 `blutter/LICENSE`。

## 2. Dart SDK（Dart VM 源码）

- **来源**：https://github.com/dart-lang/sdk
- **版权**：Copyright (c) 2012, the Dart project authors
- **许可**：BSD-3-Clause
- **本仓库位置**：**未入库**（`blutter/dartsdk/` 已 gitignore）
- **获取方式**：`blutter/download_all_dart.sh` / `blutter/dartvm_fetch_build.py` 按版本稀疏克隆。
- 使用者需自行遵守其许可。

## 3. Capstone

- **来源**：https://github.com/capstone-engine/capstone（本仓库使用 4.0.2）
- **许可**：BSD-3-Clause
- **本仓库位置**：源码归档 `blutter/ndk_src/capstone-4.0.2.tar.gz`（原始归档，未修改）

## 4. ICU (International Components for Unicode)

- **来源**：https://github.com/unicode-org/icu（本仓库使用 ICU 70.1）
- **许可**：Unicode License v3
- **本仓库位置**：源码归档 `blutter/ndk_src/icu4c-70_1-src.tgz`（原始归档，未修改）
- **说明**：构建产物（`blutter/ndk_out/icu-*`）未入库。

## 5. Android NDK

- **来源**：https://developer.android.com/ndk
- **许可**：Android NDK License
- **本仓库位置**：**未入库**（由使用者自行安装；脚本通过 `NDK` 环境变量定位）

## 6. glibc / GCC 交叉工具链（历史方案，已废弃）

- **来源**：GNU glibc / GCC
- **许可**：LGPL / GPL
- **本仓库位置**：**未入库**（`blutter/ndk_src/glibc-*`、`*.deb` 已 gitignore）
- **说明**：仅存于 `blutter/ndk_out/build_glibc*.sh` 等脚本中，作为已废弃路线的背景参考。

---

## 预编译二进制（可选分发）

本仓库**不包含**体积较大的预编译产物；如提供，通过 GitHub **Release** 附件分发：

- `libblutter_<版本>.so`（约 70 个，arm64-v8a，jniLibs 集成用）
- `libdartvm<版本>_android_arm64.a`（dartvm 静态库）

这些产物由本项目脚本从上述第三方源码构建而成，分发时同样受各第三方许可约束。
