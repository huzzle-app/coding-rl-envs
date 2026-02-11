#include <gtest/gtest.h>
#include "replication/replicator.h"

using namespace cacheforge;

// ========== Bug D1: Use after std::move ==========

TEST(ReplicationTest, test_enqueue_logs_correct_key) {
    
    // The log message should show the correct key, not an empty string.
    Replicator repl("localhost", 6381);

    ReplicationEvent event;
    event.type = ReplicationEvent::Type::Set;
    event.key = "test_key";
    event.value = "test_value";

    // Should not crash, and the event should be properly queued
    EXPECT_NO_THROW(repl.enqueue(std::move(event)));
    EXPECT_EQ(repl.pending_count(), 1);
}

TEST(ReplicationTest, test_enqueue_preserves_event_data) {
    
    Replicator repl("localhost", 6381);

    for (int i = 0; i < 5; ++i) {
        ReplicationEvent event;
        event.type = ReplicationEvent::Type::Set;
        event.key = "key_" + std::to_string(i);
        event.value = "val_" + std::to_string(i);
        repl.enqueue(std::move(event));
    }

    EXPECT_EQ(repl.pending_count(), 5);

    auto batch = repl.drain_batch(5);
    ASSERT_EQ(batch.size(), 5);
    for (int i = 0; i < 5; ++i) {
        EXPECT_EQ(batch[i].key, "key_" + std::to_string(i));
        EXPECT_EQ(batch[i].value, "val_" + std::to_string(i));
    }
}

// ========== Bug D3: Signed integer overflow ==========

TEST(ReplicationTest, test_sequence_number_no_overflow) {
    
    // Signed overflow is UB. After fix, should use uint64_t or check bounds.
    Replicator repl("localhost", 6381);

    // Generate many sequence numbers - should not cause UB
    for (int i = 0; i < 1000; ++i) {
        uint64_t seq = repl.next_sequence();
        EXPECT_GT(seq, 0);
    }
}

TEST(ReplicationTest, test_sequence_numbers_monotonic) {
    Replicator repl("localhost", 6381);

    uint64_t prev = 0;
    for (int i = 0; i < 100; ++i) {
        uint64_t seq = repl.next_sequence();
        EXPECT_GT(seq, prev) << "Sequence numbers must be monotonically increasing";
        prev = seq;
    }
}

// ========== Basic replication tests ==========

TEST(ReplicationTest, test_pending_count_empty) {
    Replicator repl("localhost", 6381);
    EXPECT_EQ(repl.pending_count(), 0);
}

TEST(ReplicationTest, test_drain_batch) {
    Replicator repl("localhost", 6381);

    for (int i = 0; i < 10; ++i) {
        ReplicationEvent event;
        event.type = ReplicationEvent::Type::Set;
        event.key = "k" + std::to_string(i);
        repl.enqueue(std::move(event));
    }

    auto batch = repl.drain_batch(5);
    EXPECT_EQ(batch.size(), 5);
    EXPECT_EQ(repl.pending_count(), 5);
}

TEST(ReplicationTest, test_drain_all) {
    Replicator repl("localhost", 6381);

    ReplicationEvent event;
    event.type = ReplicationEvent::Type::Delete;
    event.key = "deleted_key";
    repl.enqueue(std::move(event));

    auto batch = repl.drain_batch(100);
    EXPECT_EQ(batch.size(), 1);
    EXPECT_EQ(repl.pending_count(), 0);
}

TEST(ReplicationTest, test_event_types) {
    Replicator repl("localhost", 6381);

    ReplicationEvent set_event;
    set_event.type = ReplicationEvent::Type::Set;
    set_event.key = "k1";
    repl.enqueue(std::move(set_event));

    ReplicationEvent del_event;
    del_event.type = ReplicationEvent::Type::Delete;
    del_event.key = "k2";
    repl.enqueue(std::move(del_event));

    ReplicationEvent exp_event;
    exp_event.type = ReplicationEvent::Type::Expire;
    exp_event.key = "k3";
    repl.enqueue(std::move(exp_event));

    auto batch = repl.drain_batch(3);
    ASSERT_EQ(batch.size(), 3);
    EXPECT_EQ(batch[0].type, ReplicationEvent::Type::Set);
    EXPECT_EQ(batch[1].type, ReplicationEvent::Type::Delete);
    EXPECT_EQ(batch[2].type, ReplicationEvent::Type::Expire);
}

TEST(ReplicationTest, test_start_stop) {
    Replicator repl("localhost", 6381);
    repl.start();
    EXPECT_TRUE(repl.is_connected());
    repl.stop();
}
