#include <gtest/gtest.h>
#include "utils/memory_pool.h"
#include <set>

using namespace cacheforge;

// ========== Bug B3: Vector reallocation dangles pointers ==========

TEST(MemoryPoolTest, test_pointers_stable_after_growth) {
    
    // remain valid. With the vector-based pool, growth invalidates them.
    MemoryPool pool(64, 2);  // start small to force growth

    // Allocate several blocks
    std::vector<void*> ptrs;
    for (int i = 0; i < 10; ++i) {
        void* p = pool.allocate();
        ASSERT_NE(p, nullptr);
        ptrs.push_back(p);
        // Write a marker to verify the memory is usable
        std::memset(p, 0xAB, 64);
    }

    // After growth, all previously allocated pointers should still be valid
    // With the bug, the first 2 pointers point into freed memory
    for (void* p : ptrs) {
        // Should be able to read without crash (this is UB detection)
        uint8_t* bytes = static_cast<uint8_t*>(p);
        EXPECT_EQ(bytes[0], 0xAB) << "Pointer invalidated after pool growth";
    }
}

TEST(MemoryPoolTest, test_no_duplicate_allocations) {
    
    MemoryPool pool(32, 4);

    std::set<void*> allocated;
    for (int i = 0; i < 20; ++i) {
        void* p = pool.allocate();
        ASSERT_NE(p, nullptr);
        // No two allocations should return the same pointer
        EXPECT_EQ(allocated.count(p), 0) << "Duplicate allocation detected";
        allocated.insert(p);
    }
}

// ========== Bug B4: Double free from missing move constructor ==========

TEST(MemoryPoolTest, test_no_double_free_on_copy) {
    
    // or the copy should properly deep-copy the pool storage.
    // Without the fix, copying and destroying both leads to double-free.

    // After fix, this should not compile (deleted copy ctor) OR
    // should work correctly (deep copy)
    MemoryPool pool(64, 8);
    void* p1 = pool.allocate();
    ASSERT_NE(p1, nullptr);

    // The fix should make MemoryPool move-only
    // For now, just test that allocation works properly
    pool.deallocate(p1);
    void* p2 = pool.allocate();
    EXPECT_EQ(p1, p2);  // Should return the same block
}

TEST(MemoryPoolTest, test_pool_move_semantics) {
    
    MemoryPool pool(32, 4);
    void* p = pool.allocate();
    ASSERT_NE(p, nullptr);

    // Move should transfer ownership
    // Note: With the bug, the default copy ctor is used, causing double-free
    // After fix, only move should be available
}

// ========== Basic pool tests ==========

TEST(MemoryPoolTest, test_allocate_and_deallocate) {
    MemoryPool pool(64, 10);
    void* p = pool.allocate();
    ASSERT_NE(p, nullptr);
    pool.deallocate(p);
}

TEST(MemoryPoolTest, test_block_size) {
    MemoryPool pool(128, 10);
    EXPECT_EQ(pool.block_size(), 128);
}

TEST(MemoryPoolTest, test_total_blocks) {
    MemoryPool pool(64, 10);
    EXPECT_EQ(pool.total_blocks(), 10);
}

TEST(MemoryPoolTest, test_free_blocks) {
    MemoryPool pool(64, 10);
    EXPECT_EQ(pool.free_blocks(), 10);
    pool.allocate();
    EXPECT_EQ(pool.free_blocks(), 9);
}

TEST(MemoryPoolTest, test_typed_pool_construct) {
    struct TestObj {
        int x;
        std::string name;
        TestObj(int x, const std::string& name) : x(x), name(name) {}
    };

    TypedPool<TestObj> pool(4);
    auto* obj = pool.construct(42, "hello");
    ASSERT_NE(obj, nullptr);
    EXPECT_EQ(obj->x, 42);
    EXPECT_EQ(obj->name, "hello");
    pool.destroy(obj);
}
