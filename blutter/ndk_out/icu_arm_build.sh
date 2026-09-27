#!/bin/bash
# ICU 70.1 交叉编译 (NDK clang -> aarch64-linux-gnu glibc)
# 使用已构建的 host build 作为 --with-cross-build
set -u
OUT=/home/ace77505/blutter/ndk_out
# binutils 共享库 (libbfd/libopcodes) 所在目录
export LD_LIBRARY_PATH=$OUT/toolchain/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}
mkdir -p $OUT/icu-arm-build
cd $OUT/icu-arm-build
LOG=/tmp/icu_arm_build.log
echo "=== icu arm configure $(date) ===" > $LOG
/home/ace77505/blutter/ndk_src/icu/source/configure \
  --host=aarch64-linux-gnu \
  --build=x86_64-linux-gnu \
  --with-cross-build=$OUT/icu-host-build \
  --prefix=$OUT/icu-arm-install \
  --enable-static --disable-shared \
  --disable-samples --disable-tests --disable-icuio --disable-layout --disable-layoutex \
  CC=$OUT/toolchain/aarch64-linux-gnu-clang-glibc \
  CXX=$OUT/toolchain/aarch64-linux-gnu-clang++-glibc \
  AR=$OUT/toolchain/gnu/bin/aarch64-linux-gnu-ar \
  RANLIB=$OUT/toolchain/gnu/bin/aarch64-linux-gnu-ranlib \
  >> $LOG 2>&1
rc=$?
echo "=== icu arm configure rc=$rc $(date) ===" >> $LOG
if [ $rc -ne 0 ]; then exit 1; fi
make -j16 >> $LOG 2>&1
rc=$?
echo "=== icu arm make rc=$rc $(date) ===" >> $LOG
exit $rc
