#!/bin/bash
# glibc 2.35 交叉编译 (aarch64-linux-gnu)，编译器: NDK clang 18.0.3，链接器: GNU ld 2.44
set -u
SRC=/home/ace77505/blutter/ndk_src
OUT=/home/ace77505/blutter/ndk_out
GNU=$OUT/toolchain/gnu
KERNEL_HDR=$SRC/kernel_headers_pkg/usr/aarch64-linux-gnu/include
LOG=/tmp/glibc_build.log

export PATH=$OUT/toolchain/hostbin/usr/bin:$GNU/bin:$PATH
export LD_LIBRARY_PATH=$OUT/toolchain/usr/lib/x86_64-linux-gnu:$OUT/toolchain/hostbin/usr/lib/x86_64-linux-gnu

echo "===== glibc 交叉编译开始 $(date) =====" > $LOG
echo "gawk: $(which gawk)  aarch64-as: $(which aarch64-linux-gnu-as)  aarch64-readelf: $(which aarch64-linux-gnu-readelf)" >> $LOG

# 清理旧 build
rm -rf $OUT/glibc-build
mkdir -p $OUT/glibc-build
cd $OUT/glibc-build

$SRC/glibc-2.35/configure \
  --host=aarch64-linux-gnu \
  --build=x86_64-linux-gnu \
  --prefix=/usr \
  --with-headers=$KERNEL_HDR \
  --disable-werror \
  --disable-profile \
  --without-selinux \
  --enable-kernel=4.19.0 \
  CC=$OUT/toolchain/aarch64-linux-gnu-clang \
  CXX=$OUT/toolchain/aarch64-linux-gnu-clang++ \
  BUILD_CC=gcc \
  CFLAGS="-O2 -g -fno-stack-protector" \
  >> $LOG 2>&1
rc=$?
echo "===== configure 结束 rc=$rc $(date) =====" >> $LOG
if [ $rc -ne 0 ]; then echo "CONFIGURE_FAILED" >> $LOG; exit 1; fi

make -j16 >> $LOG 2>&1
rc=$?
echo "===== make 结束 rc=$rc $(date) =====" >> $LOG
if [ $rc -ne 0 ]; then echo "MAKE_FAILED" >> $LOG; exit 1; fi

make install install_root=$OUT/sysroot >> $LOG 2>&1
rc=$?
echo "===== install 结束 rc=$rc $(date) =====" >> $LOG
if [ $rc -ne 0 ]; then echo "INSTALL_FAILED" >> $LOG; exit 1; fi

echo "===== GLIBC_BUILD_SUCCESS $(date) =====" >> $LOG
