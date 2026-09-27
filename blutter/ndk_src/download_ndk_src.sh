#!/bin/bash
cd /home/ace77505/blutter/ndk_src
LOG=/tmp/ndk_download.log
echo ">>> 开始下载 $(date)" > $LOG
echo ">>> 下载 glibc-2.35.tar.xz" >> $LOG
curl -L -o glibc-2.35.tar.xz --connect-timeout 30 --max-time 900 https://ftp.gnu.org/gnu/glibc/glibc-2.35.tar.xz >> $LOG 2>&1
echo ">>> glibc done $(date) size=$(stat -c%s glibc-2.35.tar.xz 2>/dev/null)" >> $LOG
echo ">>> 下载 icu4c-70_1-src.tgz" >> $LOG
curl -L -o icu4c-70_1-src.tgz --connect-timeout 30 --max-time 900 https://github.com/unicode-org/icu/releases/download/release-70-1/icu4c-70_1-src.tgz >> $LOG 2>&1
echo ">>> icu done $(date) size=$(stat -c%s icu4c-70_1-src.tgz 2>/dev/null)" >> $LOG
echo ">>> 下载 capstone-4.0.2.tar.gz" >> $LOG
curl -L -o capstone-4.0.2.tar.gz --connect-timeout 30 --max-time 300 https://github.com/capstone-engine/capstone/archive/refs/tags/4.0.2.tar.gz >> $LOG 2>&1
echo ">>> capstone done $(date) size=$(stat -c%s capstone-4.0.2.tar.gz 2>/dev/null)" >> $LOG
echo ">>> 全部完成 $(date)" >> $LOG
