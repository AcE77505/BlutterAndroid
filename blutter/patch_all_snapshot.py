#!/usr/bin/env python3
# 批量 patch 所有版本的 app_snapshot.cc：snapshot hash + features 严格校验降级为 warning
import os, sys

# Dart 源码目录（跨平台：默认 <本脚本目录>/dartsdk，可用环境变量 DARTSDK_DIR 覆盖）
SDK = os.environ.get('DARTSDK_DIR') or os.path.join(os.path.dirname(os.path.realpath(__file__)), 'dartsdk')
DONE = {'3.4.4', '3.12.2'}  # 已手动 patch

# 两种校验块的变体（不同 Dart 版本代码略有差异）
HASH_PATTERNS = [
    '''  if (strncmp(version, expected_version, version_len) != 0) {
    const intptr_t kMessageBufferSize = 256;
    char message_buffer[kMessageBufferSize];
    char* actual_version = Utils::StrNDup(version, version_len);
    Utils::SNPrint(message_buffer, kMessageBufferSize,
                   "Wrong %s snapshot version, expected '%s' found '%s'",
                   (Snapshot::IsFull(kind_)) ? "full" : "script",
                   expected_version, actual_version);
    free(actual_version);
    return BuildError(message_buffer);
  }''',
]
HASH_REPL = '''  if (strncmp(version, expected_version, version_len) != 0) {
    // 预编译 dartvm 无法匹配任意 app 的 snapshot hash：降级为 warning，不中断分析
    const intptr_t kMessageBufferSize = 256;
    char message_buffer[kMessageBufferSize];
    char* actual_version = Utils::StrNDup(version, version_len);
    Utils::SNPrint(message_buffer, kMessageBufferSize,
                   "warning: %s snapshot version mismatch, expected '%s' found '%s' (ignored)",
                   (Snapshot::IsFull(kind_)) ? "full" : "script",
                   expected_version, actual_version);
    OS::PrintErr("%s\\n", message_buffer);
    free(actual_version);
  }'''

FEAT_PATTERNS = [
    '''  if (features_length != expected_len ||
      (strncmp(features, expected_features, expected_len) != 0)) {
    const intptr_t kMessageBufferSize = 1024;
    char message_buffer[kMessageBufferSize];
    char* actual_features = Utils::StrNDup(
        features, features_length < 1024 ? features_length : 1024);
    Utils::SNPrint(message_buffer, kMessageBufferSize,
                   "Snapshot not compatible with the current VM configuration: "
                   "the snapshot requires '%s' but the VM has '%s'",
                   actual_features, expected_features);
    free(const_cast<char*>(expected_features));
    free(actual_features);
    return BuildError(message_buffer);
  }
  free(const_cast<char*>(expected_features));
  return nullptr;''',
]
FEAT_REPL = '''  if (features_length != expected_len ||
      (strncmp(features, expected_features, expected_len) != 0)) {
    // 预编译 dartvm 用于分析任意 Flutter 引擎的 snapshot：features 严格匹配降级为 warning
    const intptr_t kMessageBufferSize = 1024;
    char message_buffer[kMessageBufferSize];
    char* actual_features = Utils::StrNDup(
        features, features_length < 1024 ? features_length : 1024);
    Utils::SNPrint(message_buffer, kMessageBufferSize,
                   "warning: snapshot features differ from VM config: snapshot requires '%s' but VM has '%s' (ignored)",
                   actual_features, expected_features);
    OS::PrintErr("%s\\n", message_buffer);
    free(actual_features);
  }
  free(const_cast<char*>(expected_features));
  return nullptr;'''

def patch_file(path):
    s = open(path, encoding='utf-8').read()
    ok_hash = ok_feat = False
    for pat in HASH_PATTERNS:
        if pat in s:
            s = s.replace(pat, HASH_REPL); ok_hash = True; break
    for pat in FEAT_PATTERNS:
        if pat in s:
            s = s.replace(pat, FEAT_REPL); ok_feat = True; break
    if ok_hash or ok_feat:
        open(path, 'w', encoding='utf-8').write(s)
    return ok_hash, ok_feat

def main():
    vers = sorted([d[1:] for d in os.listdir(SDK) if d.startswith('v')],
                  key=lambda v: [int(x) for x in v.split('.')])
    done, skip, fail = [], [], []
    for v in vers:
        if v in DONE:
            skip.append(v); continue
        p = os.path.join(SDK, f'v{v}', 'runtime', 'vm', 'app_snapshot.cc')
        if not os.path.exists(p):
            # Dart 2.14 及更早版本没有 app_snapshot.cc，
            # snapshot 版本/features 校验代码位于 clustered_snapshot.cc（文本与 pattern 一致）
            p = os.path.join(SDK, f'v{v}', 'runtime', 'vm', 'clustered_snapshot.cc')
        if not os.path.exists(p):
            fail.append((v, 'no app_snapshot.cc / clustered_snapshot.cc')); continue
        try:
            h, f = patch_file(p)
            if h and f:
                done.append(v)
            else:
                fail.append((v, f'hash={h} feat={f}'))
        except Exception as e:
            fail.append((v, str(e)))
    print(f'patched: {len(done)} | skip(已patch): {len(skip)} | fail: {len(fail)}')
    if fail:
        for v, e in fail: print(f'  FAIL {v}: {e}')

if __name__ == '__main__':
    main()
