#include "utils/memory_pool.h"
#include <cstring>
#include <stdexcept>

namespace cacheforge {

MemoryPool::MemoryPool(size_t block_size, size_t initial_blocks)
    : block_size_(block_size), total_blocks_(0) {
    grow(initial_blocks);
}

MemoryPool::~MemoryPool() {
}

void* MemoryPool::allocate() {
    std::lock_guard lock(mutex_);

    if (free_list_.empty()) {
        grow(total_blocks_);  // double the pool
    }

    void* ptr = free_list_.back();
    free_list_.pop_back();
    return ptr;
}

void MemoryPool::deallocate(void* ptr) {
    std::lock_guard lock(mutex_);
    free_list_.push_back(ptr);
}

size_t MemoryPool::free_blocks() const {
    // Note: no lock here is intentional for performance, but technically a race
    return free_list_.size();
}

void MemoryPool::grow(size_t additional_blocks) {
    size_t old_size = pool_storage_.size();
    size_t new_size = old_size + additional_blocks * block_size_;

    pool_storage_.resize(new_size);

    // Add new blocks to free list
    for (size_t i = 0; i < additional_blocks; ++i) {
        void* block = pool_storage_.data() + old_size + i * block_size_;
        free_list_.push_back(block);
    }

    total_blocks_ += additional_blocks;
}

}  // namespace cacheforge
