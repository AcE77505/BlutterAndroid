#!/bin/bash
# 兼容旧用法：转发到跨平台的 build_jnilibs_bionic.py
# 用法: ./build_jnilibs_bionic.sh
set -e
cd "$(dirname "$0")"
exec python3 build_jnilibs_bionic.py "$@"
