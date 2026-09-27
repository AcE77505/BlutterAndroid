// NDK r27c libc++ 无 std::atomic_ref（LLVM 19+ 才有）；Dart 3.12 的 raw_object.h 用到。
// 最小兼容实现：通用 __atomic_load/__atomic_store（memcpy 语义，支持无默认构造的 trivially copyable 类型），-include 注入。
#pragma once
#include <atomic>
#include <cstddef>
namespace std {
template <typename T>
class atomic_ref {
public:
    atomic_ref(T& obj) noexcept : ptr_(&obj) {}
    atomic_ref(const atomic_ref&) noexcept = default;
    atomic_ref& operator=(const atomic_ref&) = delete;
    T load(memory_order order = memory_order_seq_cst) const noexcept {
        alignas(T) unsigned char storage[sizeof(T)];
        T* p = reinterpret_cast<T*>(storage);
        __atomic_load(ptr_, p, trans(order));
        return *p;
    }
    void store(T val, memory_order order = memory_order_seq_cst) noexcept {
        __atomic_store(ptr_, &val, trans(order));
    }
    T operator=(T val) noexcept { store(val); return val; }
    operator T() const noexcept { return load(); }
    T exchange(T val, memory_order order = memory_order_seq_cst) noexcept {
        alignas(T) unsigned char storage[sizeof(T)];
        T* p = reinterpret_cast<T*>(storage);
        __atomic_exchange(ptr_, &val, p, trans(order));
        return *p;
    }
    bool compare_exchange_strong(T& expected, T desired,
                                 memory_order order = memory_order_seq_cst) noexcept {
        return __atomic_compare_exchange(ptr_, &expected, &desired, false,
                                         trans(order), trans(order));
    }
private:
    static int trans(memory_order order) noexcept {
        switch (order) {
            case memory_order_relaxed: return __ATOMIC_RELAXED;
            case memory_order_consume: return __ATOMIC_CONSUME;
            case memory_order_acquire: return __ATOMIC_ACQUIRE;
            case memory_order_release: return __ATOMIC_RELEASE;
            case memory_order_acq_rel: return __ATOMIC_ACQ_REL;
            default: return __ATOMIC_SEQ_CST;
        }
    }
    T* ptr_;
};
}
