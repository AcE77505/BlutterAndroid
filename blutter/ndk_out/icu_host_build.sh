#!/bin/bash
# ICU host (x86_64) 构建，用于 --with-cross-build 交叉编译目标库
set -u
OUT=/home/ace77505/blutter/ndk_out
mkdir -p $OUT/icu-host-build
cd $OUT/icu-host-build
LOG=/tmp/icu_host_build.log
echo "=== ICU host configure $(date) ===" > $LOG
/home/ace77505/blutter/ndk_src/icu/source/configure \
  --prefix=$OUT/icu-host-install \
  --disable-samples --disable-tests --disable-icuio --disable-layout --disable-layoutex \
  >> $LOG 2>&1
rc=$?
echo "=== ICU host configure rc=$rc $(date) ===" >> $LOG
if [ $rc -ne 0 ]; then exit 1; fi
make -j16 >> $LOG 2>&1
rc=$?
echo "=== ICU host make rc=$rc $(date) ===" >> $LOG
exit $rc
