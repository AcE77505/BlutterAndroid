#!/bin/bash
set -u
NDK=/home/ace77505/android-ndk-r27c
OUT=/home/ace77505/blutter/ndk_out
LOG=/tmp/capstone_android_build.log
echo "=== capstone android cmake $(date) ===" > $LOG
cmake -S $OUT/../ndk_src/capstone-4.0.2 -B $OUT/capstone-android \
  -DCMAKE_TOOLCHAIN_FILE=$NDK/build/cmake/android.toolchain.cmake \
  -DANDROID_ABI=arm64-v8a -DANDROID_PLATFORM=android-24 \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
  -DCMAKE_INSTALL_PREFIX=$OUT/capstone-android-install \
  >> $LOG 2>&1
rc=$?
echo "=== capstone android cmake rc=$rc $(date) ===" >> $LOG
if [ $rc -ne 0 ]; then exit 1; fi
cmake --build $OUT/capstone-android -j16 >> $LOG 2>&1
rc=$?
echo "=== capstone android build rc=$rc $(date) ===" >> $LOG
if [ $rc -ne 0 ]; then exit 1; fi
cmake --install $OUT/capstone-android >> $LOG 2>&1
rc=$?
echo "=== capstone android install rc=$rc $(date) ===" >> $LOG
exit $rc
