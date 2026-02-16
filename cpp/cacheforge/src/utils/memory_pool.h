#pragma once
#ifndef CACHEFORGE_MEMORY_POOL_H
#define CACHEFORGE_MEMORY_POOL_H

#include <cstddef>
#include <vector>
#include <memory>
#include <mutex>

namespace cacheforge {

// Fixed-size memory pool for fast allocation of cache entries
class MemoryPool {
public:
    explicit MemoryPool(size_t block_size, size_t initial_blocks = 1024);
    ~MemoryPool();

    void* allocate();
    void deallocate(void* ptr);

    size_t block_size() const { return block_size_; }
    size_t total_blocks() const { return total_blocks_; }
    size_t free_blocks() const;

private:
    size_t block_size_;
    size_t total_blocks_;

    std::vector<uint8_t> pool_storage_;
    std::vector<void*> free_list_;

    std::mutex mutex_;

    void grow(size_t additional_blocks);
};

// Typed pool wrapper
template <typename T>
class TypedPool {
public:
    TypedPool(size_t initial_count = 256)
        : pool_(sizeof(T), initial_count) {}

    template <typename... Args>
    T* construct(Args&&... args) {
        void* mem = pool_.allocate();
        if (!mem) return nullptr;
        return new (mem) T(std::forward<Args>(args)...);
    }

    void destroy(T* ptr) {
        if (ptr) {
            ptr->~T();
            pool_.deallocate(ptr);
        }
    }

private:
    MemoryPool pool_;
};

}  // namespace cacheforge

#endif  // CACHEFORGE_MEMORY_POOL_H
