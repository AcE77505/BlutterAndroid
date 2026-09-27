#!/bin/bash
# 构建部署目录：bin/blutter_android/{binary×N, lib/, blutter.sh}
set -e
OUT=/home/ace77505/blutter/ndk_out
DEPLOY=/home/ace77505/blutter/bin/blutter_android
rm -rf $DEPLOY
mkdir -p $DEPLOY/lib

# 1) glibc 运行时库（Ubuntu arm64 sysroot）
SYS=$OUT/sysroot
cp -P $SYS/lib/aarch64-linux-gnu/ld-linux-aarch64.so.1 $DEPLOY/lib/
cp -P $SYS/lib/aarch64-linux-gnu/libc.so.6      $DEPLOY/lib/
cp -P $SYS/lib/aarch64-linux-gnu/libm.so.6      $DEPLOY/lib/
cp -P $SYS/lib/aarch64-linux-gnu/libdl.so.2     $DEPLOY/lib/
cp -P $SYS/lib/aarch64-linux-gnu/libpthread.so.0 $DEPLOY/lib/
cp -P $SYS/lib/aarch64-linux-gnu/libgcc_s.so.1  $DEPLOY/lib/
cp -P $SYS/lib/aarch64-linux-gnu/libstdc++.so.6.0.34 $DEPLOY/lib/libstdc++.so.6

# 2) ICU 70.1 动态库（glibc 交叉版）
ICU=$OUT/icu-arm-shared-install/lib
cp -P $ICU/libicuuc.so.70.1    $DEPLOY/lib/libicuuc.so.70
cp -P $ICU/libicudata.so.70.1  $DEPLOY/lib/libicudata.so.70
cp -P $ICU/libicui18n.so.70.1  $DEPLOY/lib/libicui18n.so.70

# 3) Capstone 4.0.2 动态库（glibc 交叉版）
CS=$OUT/capstone-build2
cp -P $CS/libcapstone.so.4.0.2 $DEPLOY/lib/libcapstone.so.4

# 4) 入口脚本（纯 sh，兼容 Android mksh；用法: blutter.sh <dart版本> <indir> <outdir>）
cat > $DEPLOY/blutter.sh << 'SHEOF'
#!/system/bin/sh
# Blutter launcher — glibc 动态链接版
# 用法: blutter.sh <dart-版本> <libapp/libflutter 所在目录或 apk> <输出目录>
# 例:   ./blutter.sh 3.12.2 /data/local/tmp/app out
DIR=$(cd "${0%/*}" && pwd)
export LD_LIBRARY_PATH=$DIR/lib
BIN=$DIR/blutter_dartvm${1}_android_arm64
shift
exec $DIR/lib/ld-linux-aarch64.so.1 "$BIN" "$@"
SHEOF
chmod 755 $DEPLOY/blutter.sh
echo "DEPLOY_DIR=$DEPLOY"
ls $DEPLOY/lib/
