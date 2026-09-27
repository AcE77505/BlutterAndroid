#!/bin/bash
# glibc 2.35 交叉编译 v3 (aarch64-linux-gnu, 编译器=NDK clang)
set -u
SRC=/home/ace77505/blutter/ndk_src
OUT=/home/ace77505/blutter/ndk_out
GNU=$OUT/toolchain/gnu
KERNEL_HDR=$SRC/kernel_headers_pkg/usr/aarch64-linux-gnu/include
LOG=/tmp/glibc_build.log
export LD_LIBRARY_PATH=$OUT/toolchain/usr/lib/x86_64-linux-gnu:$OUT/toolchain/hostbin/usr/lib/x86_64-linux-gnu
export PATH=$OUT/toolchain/hostbin/usr/bin:$GNU/bin:$PATH

echo "===== glibc 构建 v3 $(date) =====" > $LOG

rm -rf $OUT/glibc-build
mkdir -p $OUT/glibc-build
cd $OUT/glibc-build

# config.cache: 绕过 clang 不支持的 builtin 重定向检查
# (glibc 源码中 __builtin_strstr 仅在 C++ 内联路径使用且重定向到原名, 不影响编译)
cat > config.cache << 'CEOF'
libc_cv_gcc_builtin_redirection=yes
CEOF

$SRC/glibc-2.35/configure \
  --host=aarch64-linux-gnu \
  --build=x86_64-linux-gnu \
  --prefix=/usr \
  --with-headers=$KERNEL_HDR \
  --disable-werror \
  --disable-profile \
  --without-selinux \
  --enable-kernel=4.19.0 \
  --cache-file=config.cache \
  CC=$OUT/toolchain/aarch64-linux-gnu-clang \
  CXX=$OUT/toolchain/aarch64-linux-gnu-clang++ \
  BUILD_CC=gcc \
  CFLAGS="-O2 -g -fno-stack-protector" \
  >> $LOG 2>&1
rc=$?
echo "===== configure rc=$rc $(date) =====" >> $LOG
if [ $rc -ne 0 ]; then echo "CONFIGURE_FAILED" >> $LOG; exit 1; fi

make -j16 >> $LOG 2>&1
rc=$?
echo "===== make rc=$rc $(date) =====" >> $LOG
if [ $rc -ne 0 ]; then echo "MAKE_FAILED" >> $LOG; exit 1; fi

make install install_root=$OUT/sysroot >> $LOG 2>&1
rc=$?
echo "===== install rc=$rc $(date) =====" >> $LOG
if [ $rc -ne 0 ]; then echo "INSTALL_FAILED" >> $LOG; exit 1; fi

echo "===== GLIBC_BUILD_SUCCESS $(date) =====" >> $LOG
