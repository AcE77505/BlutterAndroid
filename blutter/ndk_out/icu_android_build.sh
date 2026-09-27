#!/bin/bash
set -u
NDK=/home/ace77505/android-ndk-r27c
NDKBIN=$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin
OUT=/home/ace77505/blutter/ndk_out
mkdir -p $OUT/icu-android-build
cd $OUT/icu-android-build
LOG=/tmp/icu_android_build.log
echo "=== icu android configure $(date) ===" > $LOG
/home/ace77505/blutter/ndk_src/icu/source/configure \
  --host=aarch64-linux-android \
  --build=x86_64-linux-gnu \
  --with-cross-build=$OUT/icu-host-build \
  --prefix=$OUT/icu-android-install \
  --enable-static --disable-shared \
  --disable-samples --disable-tests --disable-icuio --disable-layout --disable-layoutex \
  CC=$NDKBIN/aarch64-linux-android24-clang \
  CXX=$NDKBIN/aarch64-linux-android24-clang++ \
  AR=$NDKBIN/llvm-ar \
  RANLIB=$NDKBIN/llvm-ranlib \
  >> $LOG 2>&1
rc=$?
echo "=== icu android configure rc=$rc $(date) ===" >> $LOG
if [ $rc -ne 0 ]; then exit 1; fi
make -j16 >> $LOG 2>&1
rc=$?
echo "=== icu android make rc=$rc $(date) ===" >> $LOG
if [ $rc -ne 0 ]; then exit 1; fi
make install >> $LOG 2>&1
rc=$?
echo "=== icu android install rc=$rc $(date) ===" >> $LOG
exit $rc
