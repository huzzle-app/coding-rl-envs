package com.docuvault.concurrency;

import com.docuvault.model.Document;
import com.docuvault.model.User;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.*;

@Tag("concurrency")
public class ThreadSafetyTest {

    @Test
    void test_concurrent_hashmap_mutable_key() throws Exception {
        // Related to BUG B1 - mutable keys in HashMap
        Map<Document, String> map = new ConcurrentHashMap<>();
        Document doc = new Document();
        doc.setId(1L);
        doc.setName("test");

        map.put(doc, "value");

        // Mutating the key after insertion
        doc.setName("changed");

        
        // Fix: Use ID-based hashCode
        String value = map.get(doc);
        assertNotNull(value, "Should find value after key mutation when using immutable hashCode");
    }

    @Test
    void test_concurrent_list_operations() throws Exception {
        List<String> list = Collections.synchronizedList(new ArrayList<>());
        int threadCount = 20;
        CountDownLatch latch = new CountDownLatch(threadCount);

        for (int i = 0; i < threadCount; i++) {
            final int idx = i;
            new Thread(() -> {
                try {
                    list.add("item-" + idx);
                } finally {
                    latch.countDown();
                }
            }).start();
        }

        latch.await(10, TimeUnit.SECONDS);
        assertEquals(threadCount, list.size());
    }

    @Test
    void test_double_checked_locking_pattern() throws Exception {
        AtomicInteger instanceCount = new AtomicInteger(0);
        int threadCount = 100;
        CountDownLatch latch = new CountDownLatch(threadCount);
        Set<Integer> seenIds = ConcurrentHashMap.newKeySet();

        for (int i = 0; i < threadCount; i++) {
            new Thread(() -> {
                try {
                    // Simulate singleton with DCL
                    int id = instanceCount.updateAndGet(current -> current == 0 ? 1 : current);
                    seenIds.add(id);
                } finally {
                    latch.countDown();
                }
            }).start();
        }

        latch.await(10, TimeUnit.SECONDS);
        assertEquals(1, seenIds.size(), "All threads should see same singleton ID");
    }

    @Test
    void test_producer_consumer_pattern() throws Exception {
        BlockingQueue<String> queue = new ArrayBlockingQueue<>(100);
        AtomicInteger produced = new AtomicInteger(0);
        AtomicInteger consumed = new AtomicInteger(0);
        int messageCount = 50;

        Thread producer = new Thread(() -> {
            for (int i = 0; i < messageCount; i++) {
                try {
                    queue.put("msg-" + i);
                    produced.incrementAndGet();
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                }
            }
        });

        Thread consumer = new Thread(() -> {
            for (int i = 0; i < messageCount; i++) {
                try {
                    String msg = queue.poll(5, TimeUnit.SECONDS);
                    if (msg != null) consumed.incrementAndGet();
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                }
            }
        });

        producer.start();
        consumer.start();
        producer.join(10000);
        consumer.join(10000);

        assertEquals(messageCount, produced.get());
        assertEquals(messageCount, consumed.get());
    }

    @Test
    void test_atomic_compound_operations() throws Exception {
        AtomicInteger counter = new AtomicInteger(0);
        int threadCount = 100;
        CountDownLatch latch = new CountDownLatch(threadCount);

        for (int i = 0; i < threadCount; i++) {
            new Thread(() -> {
                try {
                    for (int j = 0; j < 100; j++) {
                        counter.incrementAndGet();
                    }
                } finally {
                    latch.countDown();
                }
            }).start();
        }

        latch.await(10, TimeUnit.SECONDS);
        assertEquals(10000, counter.get());
    }

    @Test
    void test_concurrent_map_compute() throws Exception {
        ConcurrentHashMap<String, Integer> map = new ConcurrentHashMap<>();
        int threadCount = 50;
        CountDownLatch latch = new CountDownLatch(threadCount);

        for (int i = 0; i < threadCount; i++) {
            new Thread(() -> {
                try {
                    map.merge("key", 1, Integer::sum);
                } finally {
                    latch.countDown();
                }
            }).start();
        }

        latch.await(10, TimeUnit.SECONDS);
        assertEquals(threadCount, map.get("key"));
    }

    @Test
    void test_read_write_lock_fairness() throws Exception {
        java.util.concurrent.locks.ReadWriteLock lock =
            new java.util.concurrent.locks.ReentrantReadWriteLock(true);
        AtomicInteger readCount = new AtomicInteger(0);
        AtomicInteger writeCount = new AtomicInteger(0);
        CountDownLatch latch = new CountDownLatch(20);

        for (int i = 0; i < 15; i++) {
            new Thread(() -> {
                try {
                    lock.readLock().lock();
                    try {
                        readCount.incrementAndGet();
                        Thread.sleep(10);
                    } finally {
                        lock.readLock().unlock();
                    }
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                } finally {
                    latch.countDown();
                }
            }).start();
        }

        for (int i = 0; i < 5; i++) {
            new Thread(() -> {
                try {
                    lock.writeLock().lock();
                    try {
                        writeCount.incrementAndGet();
                        Thread.sleep(10);
                    } finally {
                        lock.writeLock().unlock();
                    }
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                } finally {
                    latch.countDown();
                }
            }).start();
        }

        latch.await(10, TimeUnit.SECONDS);
        assertEquals(15, readCount.get());
        assertEquals(5, writeCount.get());
    }

    @Test
    void test_phaser_synchronization() throws Exception {
        Phaser phaser = new Phaser(1);
        int threadCount = 5;
        AtomicInteger phase0Count = new AtomicInteger(0);
        AtomicInteger phase1Count = new AtomicInteger(0);

        for (int i = 0; i < threadCount; i++) {
            phaser.register();
            new Thread(() -> {
                phase0Count.incrementAndGet();
                phaser.arriveAndAwaitAdvance(); // Phase 0

                phase1Count.incrementAndGet();
                phaser.arriveAndDeregister(); // Phase 1
            }).start();
        }

        phaser.arriveAndAwaitAdvance(); // Wait for phase 0
        assertEquals(threadCount, phase0Count.get());

        phaser.arriveAndAwaitAdvance(); // Wait for phase 1
        assertEquals(threadCount, phase1Count.get());
    }
}
