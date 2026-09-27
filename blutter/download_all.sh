#!/bin/bash
# 下载所有 47 个 Dart SDK 版本
# 使用 refs/tags/ 前缀避免 tag/branch 同名冲突

# set -e

SDK_DIR="/home/ace77505/blutter/dartsdk"
REPO_URL="https://github.com/dart-lang/sdk.git"

# 47 个版本列表（按文档第八章）
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
SUCCESS=0
SKIP=0
FAIL=0

for VER in "${VERSIONS[@]}"; do
    ((COUNT++))
    TAG="v${VER}"
    DIR="${SDK_DIR}/${TAG}"
    
    echo ""
    echo "============================================================"
    echo "[${COUNT}/${TOTAL}] Processing Dart ${VER} (${TAG})"
    echo "============================================================"
    
    # 检查是否已存在完整目录
    if [ -d "${DIR}" ] && [ -f "${DIR}/runtime/vm/version_in.cc" ]; then
        echo "  ✅ Already exists, skipping"
        ((SKIP++))
        continue
    fi
    
    echo "  Cloning ${TAG}..."
    
    # 如果目录存在但不完整，先删除
    if [ -d "${DIR}" ]; then
        echo "  Removing incomplete directory..."
        rm -rf "${DIR}"
    fi
    
    # Clone with sparse checkout
    if ! git clone --depth 1 --branch "${TAG}" --single-branch \
        "${REPO_URL}" "${DIR}" 2>&1 | tail -5; then
        
        # 如果直接 clone 失败，试试用 refs/tags/ 前缀
        echo "  Retrying with refs/tags/ prefix..."
        mkdir -p "${DIR}"
        cd "${DIR}"
        git init -q
        git remote add origin "${REPO_URL}"
        git config core.sparseCheckout true
        
        # 写 sparse-checkout 配置
        mkdir -p .git/info
        cat > .git/info/sparse-checkout << 'SPARSE_EOF'
runtime/vm/
runtime/platform/
third_party/
tools/
SPARSE_EOF
        
        if git fetch --depth 1 origin "refs/tags/${TAG}" 2>&1 | tail -5; then
            git checkout -q FETCH_HEAD
            echo "  ✅ Clone success (refs/tags method)"
        else
            echo "  ❌ Failed to fetch tag ${TAG}"
            cd "${SDK_DIR}"
            ((FAIL++))
            continue
        fi
        cd "${SDK_DIR}"
    else
        echo "  ✅ Clone success"
    fi
    
    # 生成 version.cc
    if [ -f "${DIR}/runtime/vm/version_in.cc" ] && [ -f "${DIR}/tools/make_version.py" ]; then
        echo "  Generating version.cc..."
        python3 "${DIR}/tools/make_version.py" \
            --output "${DIR}/runtime/vm/version.cc" \
            --input "${DIR}/runtime/vm/version_in.cc" 2>&1 | tail -3
        echo "  ✅ version.cc generated"
        ((SUCCESS++))
    else
        echo "  ⚠️  Missing version_in.cc or make_version.py"
        ls "${DIR}/runtime/vm/" 2>/dev/null | head -5
        ((FAIL++))
    fi
done

echo ""
echo "========================================"
echo " Download Summary"
echo "========================================"
echo " Total:  ${TOTAL}"
echo " Success: ${SUCCESS}"
echo " Skipped: ${SKIP}"
echo " Failed:  ${FAIL}"
echo "========================================"
