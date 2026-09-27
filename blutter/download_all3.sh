#!/bin/bash
# 下载所有 47 个 Dart SDK 版本
# tag 格式: 3.5.0 (不带 v 前缀!)
# 目录名: v3.5.0 (带 v 前缀, 与已有目录一致)

SDK_DIR="/home/ace77505/blutter/dartsdk"
REPO_URL="https://github.com/dart-lang/sdk.git"
LOG_FILE="/home/ace77505/blutter/download3.log"

# 47 个版本列表
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

clone_and_gen() {
  local VER="$1"
  local TAG="${VER}"           # git tag 不带 v
  local DIRNAME="v${VER}"      # 目录名带 v
  local DIR="${SDK_DIR}/${DIRNAME}"
  
  echo "  Cloning ${DIRNAME} (tag: ${TAG})..."
  
  mkdir -p "${DIR}"
  cd "${DIR}"
  git init -q
  git remote add origin "${REPO_URL}"
  git config core.sparseCheckout true
  mkdir -p .git/info
  cat > .git/info/sparse-checkout << 'EOF'
/runtime/vm/*
/runtime/platform/*
/third_party/*
/tools/*
EOF
  
  git fetch --depth 1 origin "refs/tags/${TAG}" 2>> "$LOG_FILE"
  local RET=$?
  if [ $RET -ne 0 ]; then
    echo "    ❌ Fetch failed for tag ${TAG} (exit $RET)" | tee -a "$LOG_FILE"
    cd "${SDK_DIR}"
    return 1
  fi
  
  git checkout -q FETCH_HEAD 2>> "$LOG_FILE"
  local RET2=$?
  if [ $RET2 -ne 0 ]; then
    echo "    ❌ Checkout failed (exit $RET2)" | tee -a "$LOG_FILE"
    cd "${SDK_DIR}"
    return 1
  fi
  
  cd "${SDK_DIR}"
  
  # 验证 version_in.cc
  if [ ! -f "${DIR}/runtime/vm/version_in.cc" ]; then
    echo "    ❌ Missing runtime/vm/version_in.cc after checkout!" | tee -a "$LOG_FILE"
    ls "${DIR}/runtime/vm/" 2>/dev/null | head -10
    return 1
  fi
  
  # 生成 version.cc
  if [ -f "${DIR}/tools/make_version.py" ]; then
    python3 "${DIR}/tools/make_version.py" \
      --output "${DIR}/runtime/vm/version.cc" \
      --input "${DIR}/runtime/vm/version_in.cc" 2>> "$LOG_FILE"
    if [ -f "${DIR}/runtime/vm/version.cc" ]; then
      echo "    ✅ version.cc generated"
    else
      echo "    ⚠️  version.cc generation failed"
    fi
  fi
  
  return 0
}

# 清空日志
> "$LOG_FILE"

TOTAL=${#VERSIONS[@]}
COUNT=0
SUCCESS=0
SKIP=0
FAIL=0
FAILED_VERSIONS=""

for VER in "${VERSIONS[@]}"; do
  ((COUNT++))
  DIRNAME="v${VER}"
  DIR="${SDK_DIR}/${DIRNAME}"
  
  echo ""
  echo "============================================================"
  echo "[${COUNT}/${TOTAL}] Processing Dart ${VER} (${DIRNAME})"
  echo "============================================================"
  
  # 检查是否已存在完整目录
  if [ -d "${DIR}" ] && [ -f "${DIR}/runtime/vm/version_in.cc" ]; then
    echo "  ✅ Already exists (${DIRNAME}/runtime/vm/version_in.cc found)"
    ((SKIP++))
    continue
  fi
  
  # 如果目录存在但不完整，删除
  if [ -d "${DIR}" ]; then
    echo "  Removing incomplete directory..."
    rm -rf "${DIR}"
  fi
  
  if clone_and_gen "${VER}"; then
    echo "  ✅ ${DIRNAME} done"
    ((SUCCESS++))
  else
    echo "  ❌ ${DIRNAME} FAILED"
    ((FAIL++))
    FAILED_VERSIONS="${FAILED_VERSIONS} ${VER}"
  fi
done

echo ""
echo "========================================"
echo "  Download Summary"
echo "========================================"
echo "  Total:     ${TOTAL}"
echo "  Success:   ${SUCCESS}"
echo "  Skipped:   ${SKIP}"
echo "  Failed:    ${FAIL}"
if [ -n "$FAILED_VERSIONS" ]; then
  echo "  Failed:  ${FAILED_VERSIONS}"
fi
echo "  Log:       ${LOG_FILE}"
echo "========================================"
