#!/bin/bash
# 批量预下载所有支持的 Dart SDK 版本源码（修正版）
# 使用 git clone --depth 1 --filter=blob:none --sparse 方式

set -e

SDK_DIR="/home/ace77505/blutter/dartsdk"
GIT_URL="https://github.com/dart-lang/sdk.git"
LOG_FILE="/home/ace77505/blutter/download_dart_fixed.log"

# 所有支持的版本（按顺序）
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

echo "===== 开始批量下载 Dart SDK 源码（修正版） =====" | tee "$LOG_FILE"
echo "总共 $TOTAL 个版本" | tee -a "$LOG_FILE"
echo "开始时间: $(date)" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

for ver in "${VERSIONS[@]}"; do
    COUNT=$((COUNT + 1))
    CLONE_DIR="$SDK_DIR/v$ver"
    
    # 用 version_in.cc 或 .git 判断是否已下载完成
    if [ -f "$CLONE_DIR/runtime/vm/version_in.cc" ] || [ -d "$CLONE_DIR/.git" ]; then
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
    
    # 最小化克隆
    if ! git -c advice.detachedHead=false clone -b "$ver" --depth 1 --filter=blob:none --sparse "$GIT_URL" "$CLONE_DIR" >> "$LOG_FILE" 2>&1; then
        echo "[$COUNT/$TOTAL] v$ver git clone 失败！" | tee -a "$LOG_FILE"
        continue
    fi
    
    # sparse checkout 仅需要的目录
    cd "$CLONE_DIR"
    git sparse-checkout set runtime tools third_party/double-conversion >> "$LOG_FILE" 2>&1
    
    # 重新应用 sparse checkout 确保文件被检出
    git sparse-checkout reapply 2>/dev/null
    
    # 删除根目录的多余文件
    for item in "$CLONE_DIR"/*; do
        if [ -f "$item" ]; then
            rm -f "$item"
        fi
    done
    
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    
    # 检查关键文件是否存在
    if [ -f "$CLONE_DIR/runtime/vm/version_in.cc" ]; then
        echo "[$COUNT/$TOTAL] v$ver 下载完成（${DURATION}s）" | tee -a "$LOG_FILE"
    else
        echo "[$COUNT/$TOTAL] v$ver 下载完成但缺少关键文件（${DURATION}s）" | tee -a "$LOG_FILE"
    fi
    
    cd "$SDK_DIR"
done

echo "" | tee -a "$LOG_FILE"
echo "===== 全部下载完成 =====" | tee -a "$LOG_FILE"
echo "结束时间: $(date)" | tee -a "$LOG_FILE"
