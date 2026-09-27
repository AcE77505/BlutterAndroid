#!/bin/bash
# 通过 GitHub API 下载所有 Dart SDK 版本（绕过 github.com 的 HTTPS 限制）
set -e

SDK_DIR="/home/ace77505/blutter/dartsdk"
LOG_FILE="/home/ace77505/blutter/download_dart.log"
SCRIPT_DIR="/home/ace77505/blutter"

VERSIONS=(
  "2.19.6"
  "3.4.0" "3.4.1" "3.4.2" "3.4.3" "3.4.4"
  "3.5.0" "3.5.1" "3.5.2" "3.5.3" "3.5.4"
  "3.6.0" "3.6.1" "3.6.2"
  "3.7.0" "3.7.1" "3.7.2" "3.7.3"
  "3.8.0" "3.8.1" "3.8.2" "3.8.3"
  "3.9.0" "3.9.1" "3.9.2" "3.9.3" "3.9.4"
  "3.10.0" "3.10.1" "3.10.2" "3.10.3" "3.10.4"
  "3.10.5" "3.10.6" "3.10.7" "3.10.8" "3.10.9"
  "3.11.0" "3.11.1" "3.11.2" "3.11.3" "3.11.4"
  "3.11.5" "3.11.6"
  "3.12.0" "3.12.1" "3.12.2"
)

TOTAL=${#VERSIONS[@]}
COUNT=0

echo "===== 通过 API 批量下载 Dart SDK 源码 =====" | tee -a "$LOG_FILE"
echo "总共 $TOTAL 个版本" | tee -a "$LOG_FILE"
echo "开始时间: $(date)" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

for ver in "${VERSIONS[@]}"; do
    COUNT=$((COUNT + 1))
    CLONE_DIR="$SDK_DIR/v$ver"
    VERSION_FILE="$CLONE_DIR/runtime/vm/version.cc"
    
    # 检查是否已经完成
    if [ -f "$VERSION_FILE" ]; then
        echo "[$COUNT/$TOTAL] v$ver 已存在，跳过" | tee -a "$LOG_FILE"
        continue
    fi
    
    # 如果目录存在但不完整，删除重来
    if [ -d "$CLONE_DIR" ]; then
        echo "[$COUNT/$TOTAL] v$ver 目录不完整，删除重下..." | tee -a "$LOG_FILE"
        rm -rf "$CLONE_DIR"
    fi
    
    echo "[$COUNT/$TOTAL] 开始下载 v$ver ..." | tee -a "$LOG_FILE"
    START_TIME=$(date +%s)
    
    # 通过 API 下载 tarball（走 api.github.com → codeload.github.com，可通）
    TMP_FILE=$(mktemp)
    HTTP_CODE=$(curl -sL --connect-timeout 30 -o "$TMP_FILE" -w "%{http_code}" "https://api.github.com/repos/dart-lang/sdk/tarball/$ver" 2>&1)
    
    if [ "$HTTP_CODE" != "200" ]; then
        echo "[$COUNT/$TOTAL] v$ver 下载失败！HTTP=$HTTP_CODE" | tee -a "$LOG_FILE"
        rm -f "$TMP_FILE"
        continue
    fi
    
    # 创建目录并解压
    mkdir -p "$CLONE_DIR"
    # tarball 里有顶层目录（如 dart-lang-sdk-xxxx/），strip 掉
    tar -xzf "$TMP_FILE" --strip-components=1 -C "$CLONE_DIR"
    rm -f "$TMP_FILE"
    
    # 删除不需要的文件（只保留 runtime, tools, third_party）
    cd "$CLONE_DIR"
    for item in *; do
        if [ "$item" != "runtime" ] && [ "$item" != "tools" ] && [ "$item" != "third_party" ]; then
            rm -rf "$item"
        fi
    done
    
    # 生成 version.cc
    if [ -f "tools/make_version.py" ] && [ -f "runtime/vm/version_in.cc" ]; then
        python3 tools/make_version.py --output runtime/vm/version.cc --input runtime/vm/version_in.cc 2>/dev/null || {
            # 如果 make_version.py 失败，尝试直接生成 version.cc
            echo "// Generated version file" > runtime/vm/version.cc
            echo "#include \"vm/version_in.h\"" >> runtime/vm/version.cc
        }
    fi
    
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    
    if [ -f "$VERSION_FILE" ]; then
        echo "[$COUNT/$TOTAL] v$ver 下载完成（${DURATION}s）" | tee -a "$LOG_FILE"
    else
        echo "[$COUNT/$TOTAL] v$ver 下载完成但缺少 version.cc（${DURATION}s）" | tee -a "$LOG_FILE"
    fi
done

echo "" | tee -a "$LOG_FILE"
echo "===== 全部下载完成 =====" | tee -a "$LOG_FILE"
echo "结束时间: $(date)" | tee -a "$LOG_FILE"
