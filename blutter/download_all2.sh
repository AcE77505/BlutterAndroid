#!/bin/bash
# 下载所有 47 个 Dart SDK 版本
# 直接用 refs/tags/ 方式 clone，避免 tag/branch 同名问题

SDK_DIR="/home/ace77505/blutter/dartsdk"
REPO_URL="https://github.com/dart-lang/sdk.git"
LOG_FILE="/home/ace77505/blutter/download.log"

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

clone_tag() {
  local TAG="$1"
  local DIR="$2"
  local LOG="$3"
  
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
  
  echo "  [FETCH] git fetch --depth 1 origin refs/tags/${TAG}" >> "$LOG"
  git fetch --depth 1 origin "refs/tags/${TAG}" >> "$LOG" 2>&1
  local RET=$?
  if [ $RET -ne 0 ]; then
    echo "  ❌ Fetch failed (exit code $RET)" >> "$LOG"
    cd "${SDK_DIR}"
    return 1
  fi
  
  git checkout -q FETCH_HEAD >> "$LOG" 2>&1
  local RET2=$?
  if [ $RET2 -ne 0 ]; then
    echo "  ❌ Checkout failed (exit code $RET2)" >> "$LOG"
    cd "${SDK_DIR}"
    return 1
  fi
  
  cd "${SDK_DIR}"
  return 0
}

echo "" > "$LOG_FILE"
TOTAL=${#VERSIONS[@]}
COUNT=0
SUCCESS=0
SKIP=0
FAIL=0
FAILED_VERSIONS=""

for VER in "${VERSIONS[@]}"; do
  ((COUNT++))
  TAG="v${VER}"
  DIR="${SDK_DIR}/${TAG}"
  
  echo ""
  echo "============================================================"
  echo "[${COUNT}/${TOTAL}] Processing Dart ${VER} (${TAG})"
  echo "============================================================"
  
  # 检查是否已存在完整目录（有 version_in.cc 就算完整）
  if [ -d "${DIR}" ] && [ -f "${DIR}/runtime/vm/version_in.cc" ]; then
    echo "  ✅ Already exists, skipping"
    ((SKIP++))
    continue
  fi
  
  # 如果目录存在但不完整，删除
  if [ -d "${DIR}" ]; then
    echo "  Removing incomplete directory..."
    rm -rf "${DIR}"
  fi
  
  echo "  Cloning ${TAG}..."
  
  if clone_tag "${TAG}" "${DIR}" "$LOG_FILE"; then
    # 检查文件是否下载成功
    if [ -f "${DIR}/runtime/vm/version_in.cc" ]; then
      echo "  ✅ Clone success, files verified"
      
      # 生成 version.cc
      if [ -f "${DIR}/tools/make_version.py" ]; then
        echo "  Generating version.cc..."
        python3 "${DIR}/tools/make_version.py" \
          --output "${DIR}/runtime/vm/version.cc" \
          --input "${DIR}/runtime/vm/version_in.cc" 2>> "$LOG_FILE"
        if [ -f "${DIR}/runtime/vm/version.cc" ]; then
          echo "  ✅ version.cc generated"
        else
          echo "  ⚠️  version.cc generation failed"
        fi
      fi
      ((SUCCESS++))
    else
      # 列出下载了什么
      echo "  ⚠️  Missing version_in.cc! Contents:"
      ls "${DIR}/" 2>/dev/null | head -10
      ls "${DIR}/runtime/vm/" 2>/dev/null | head -10
      ((FAIL++))
      FAILED_VERSIONS="${FAILED_VERSIONS} ${VER}"
    fi
  else
    echo "  ❌ Failed to clone ${TAG}"
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
  echo "  Failed:   ${FAILED_VERSIONS}"
fi
echo "  Log:       ${LOG_FILE}"
echo "========================================"
