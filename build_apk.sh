#!/bin/bash
# FlutterAndroid 一键构建 APK（x86 Linux，无需 Android Studio）
# 用法: ./build_apk.sh [assembleRelease|assembleDebug]
set -e
cd "$(dirname "$0")"
export JAVA_HOME=/home/ace77505/jdk21
export PATH=$JAVA_HOME/bin:$PATH
export ANDROID_HOME=/home/ace77505/Android/Sdk
export ANDROID_SDK_ROOT=$ANDROID_HOME
TASK=${1:-assembleRelease}
./gradlew $TASK --no-daemon
echo "✅ 产物: app/build/outputs/apk/${TASK#assemble}/"
