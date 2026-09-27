#!/bin/bash
# Capstone 4.0.2 交叉编译 (NDK clang -> aarch64-linux-gnu glibc)
set -u
OUT=/home/ace77505/blutter/ndk_out
mkdir -p $OUT/capstone-build2
cd $OUT/capstone-build2
LOG=/tmp/capstone_build.log
echo "=== capstone cmake $(date) ===" > $LOG
cmake /home/ace77505/blutter/ndk_src/capstone-4.0.2 \
  -DCMAKE_SYSTEM_NAME=Linux -DCMAKE_SYSTEM_PROCESSOR=aarch64 \
  -DCMAKE_C_COMPILER=$OUT/toolchain/aarch64-linux-gnu-clang-glibc \
  -DCMAKE_CXX_COMPILER=$OUT/toolchain/aarch64-linux-gnu-clang++-glibc \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
  >> $LOG 2>&1
rc=$?
echo "=== capstone cmake rc=$rc $(date) ===" >> $LOG
if [ $rc -ne 0 ]; then exit 1; fi
make -j16 >> $LOG 2>&1
rc=$?
echo "=== capstone make rc=$rc $(date) ===" >> $LOG
exit $rc
