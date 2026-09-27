#!/bin/bash
# 修复 dartsdk 中 22 个空壳版本（只有 .git，没有工作区内容）
# 逐个 fetch tag + sparse checkout，写日志到 /tmp/fix_download.log
LOG=/tmp/fix_download.log
SDK_DIR=/home/ace77505/blutter/dartsdk

# 22 个需要修复的版本（tag 不带 v 前缀）
VERSIONS="3.5.3 3.5.4 3.6.0 3.6.1 3.6.2 3.7.0 3.7.1 3.7.2 3.7.3 3.8.0 3.8.1 3.8.2 3.8.3 3.9.0 3.9.1 3.9.2 3.9.3 3.9.4 3.10.0 3.10.1 3.10.2 3.10.3"

echo "=== 修复开始 $(date '+%F %T') ===" >> "$LOG"

for v in $VERSIONS; do
    dir="$SDK_DIR/v$v"
    if [ -f "$dir/runtime/vm/version_in.cc" ]; then
        echo "SKIP v$v (already has version_in.cc)" >> "$LOG"
        continue
    fi
    echo ">>> START v$v $(date '+%T')" >> "$LOG"
    cd "$dir" 2>>"$LOG" || { echo "!!! NO DIR v$v" >> "$LOG"; continue; }
    # 重新 fetch tag
    git fetch --depth 1 origin "refs/tags/$v" >>"$LOG" 2>&1
    rc=$?
    echo "    fetch rc=$rc" >> "$LOG"
    if [ $rc -ne 0 ]; then
        echo "!!! FETCH FAIL v$v" >> "$LOG"
        continue
    fi
    # sparse checkout 已配置，直接 checkout
    git checkout FETCH_HEAD >>"$LOG" 2>&1
    rc=$?
    echo "    checkout rc=$rc" >> "$LOG"
    if [ -f "$dir/runtime/vm/version_in.cc" ]; then
        echo "    OK v$v ($(du -sh "$dir" 2>/dev/null | cut -f1))" >> "$LOG"
    else
        echo "!!! CHECKOUT INCOMPLETE v$v" >> "$LOG"
    fi
    echo "<<< END v$v $(date '+%T')" >> "$LOG"
done

echo "=== 修复完成 $(date '+%F %T') ===" >> "$LOG"
