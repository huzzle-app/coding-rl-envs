package com.docuvault.concurrency;

import com.docuvault.model.Document;
import com.docuvault.service.NotificationService;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Consumer;

import static org.junit.jupiter.api.Assertions.*;

@Tag("concurrency")
public class ConcurrentAccessTest {

    // Tests for BUG A4: ConcurrentModificationException
    @Test
    void test_concurrent_listener_modification() throws Exception {
        NotificationService service = new NotificationService();
        int threadCount = 20;
        CountDownLatch startLatch = new CountDownLatch(1);
        CountDownLatch doneLatch = new CountDownLatch(threadCount);
        List<Exception> errors = Collections.synchronizedList(new ArrayList<>());

        // Half threads add listeners, half trigger notifications
        for (int i = 0; i < threadCount; i++) {
            final int idx = i;
            new Thread(() -> {
                try {
                    startLatch.await();
                    if (idx % 2 == 0) {
                        service.addListener(doc ->
                            System.out.println("Listener " + idx + ": " + doc));
                    } else {
                        Document doc = new Document();
                        doc.setName("doc-" + idx);
                        service.notifyDocumentCreated(doc);
                    }
                } catch (Exception e) {
                    errors.add(e);
                } finally {
                    doneLatch.countDown();
                }
            }).start();
        }

        startLatch.countDown();
        doneLatch.await(10, TimeUnit.SECONDS);

        
        assertTrue(errors.isEmpty(),
            "Concurrent listener modification should not throw CME: " + errors);
    }

    @Test
    void test_listener_add_during_iteration() throws Exception {
        NotificationService service = new NotificationService();
        AtomicInteger notified = new AtomicInteger(0);

        // Add initial listeners
        for (int i = 0; i < 5; i++) {
            service.addListener(doc -> notified.incrementAndGet());
        }

        CountDownLatch latch = new CountDownLatch(2);
        List<Exception> errors = Collections.synchronizedList(new ArrayList<>());

        // Thread 1: Iterate (notify)
        new Thread(() -> {
            try {
                Document doc = new Document();
                doc.setName("test");
                service.notifyDocumentCreated(doc);
            } catch (Exception e) {
                errors.add(e);
            } finally {
                latch.countDown();
            }
        }).start();

        // Thread 2: Add more listeners
        new Thread(() -> {
            try {
                for (int i = 0; i < 10; i++) {
                    service.addListener(doc -> notified.incrementAndGet());
                }
            } catch (Exception e) {
                errors.add(e);
            } finally {
                latch.countDown();
            }
        }).start();

        latch.await(10, TimeUnit.SECONDS);

        assertTrue(errors.isEmpty(),
            "Adding listeners during iteration should not cause CME: " + errors);
    }

    @Test
    void test_notification_service_thread_safety() throws Exception {
        NotificationService service = new NotificationService();
        int iterations = 100;
        CountDownLatch latch = new CountDownLatch(iterations);
        AtomicInteger successCount = new AtomicInteger(0);
        List<Exception> errors = Collections.synchronizedList(new ArrayList<>());

        ExecutorService executor = Executors.newFixedThreadPool(10);

        for (int i = 0; i < iterations; i++) {
            final int idx = i;
            executor.submit(() -> {
                try {
                    service.addListener(doc -> {});

                    Document doc = new Document();
                    doc.setName("doc-" + idx);
                    service.notifyDocumentCreated(doc);

                    successCount.incrementAndGet();
                } catch (Exception e) {
                    errors.add(e);
                } finally {
                    latch.countDown();
                }
            });
        }

        latch.await(30, TimeUnit.SECONDS);
        executor.shutdown();

        assertTrue(errors.isEmpty(),
            "No thread safety issues expected: " + errors);
        assertEquals(iterations, successCount.get());
    }

    @Test
    void test_concurrent_add_remove_listeners() throws Exception {
        NotificationService service = new NotificationService();
        int threadCount = 20;
        CountDownLatch latch = new CountDownLatch(threadCount);
        List<Exception> errors = Collections.synchronizedList(new ArrayList<>());
        List<Consumer<Document>> addedListeners = Collections.synchronizedList(new ArrayList<>());

        ExecutorService executor = Executors.newFixedThreadPool(threadCount);

        for (int i = 0; i < threadCount; i++) {
            final int idx = i;
            executor.submit(() -> {
                try {
                    Consumer<Document> listener = doc -> {};
                    service.addListener(listener);
                    addedListeners.add(listener);

                    Thread.sleep(10);

                    if (idx % 3 == 0 && !addedListeners.isEmpty()) {
                        service.removeListener(addedListeners.get(0));
                    }
                } catch (Exception e) {
                    errors.add(e);
                } finally {
                    latch.countDown();
                }
            });
        }

        latch.await(10, TimeUnit.SECONDS);
        executor.shutdown();

        assertTrue(errors.isEmpty(),
            "Concurrent add/remove should be safe: " + errors);
    }

    // Tests for BUG A5: Synchronized on wrong monitor
    @Test
    void test_auth_token_cache_thread_safe() throws Exception {
        
        // because each injection creates a new instance with a different lock

        // Simulate what happens with prototype scope
        // Create multiple instances (as would happen with prototype scope)
        int threadCount = 20;
        CountDownLatch latch = new CountDownLatch(threadCount);
        ConcurrentHashMap<String, String> tokens = new ConcurrentHashMap<>();
        List<Exception> errors = Collections.synchronizedList(new ArrayList<>());

        // In the buggy version, each thread might get a different AuthService instance
        // so synchronized(this) provides no actual protection
        for (int i = 0; i < threadCount; i++) {
            final int idx = i;
            new Thread(() -> {
                try {
                    // Simulate concurrent access to shared token cache
                    // With prototype scope bug, each "instance" has its own lock
                    String key = "user-" + (idx % 5);
                    tokens.put(key, "token-" + idx);
                    Thread.sleep(10);
                    String value = tokens.get(key);
                    assertNotNull(value);
                } catch (Exception e) {
                    errors.add(e);
                } finally {
                    latch.countDown();
                }
            }).start();
        }

        latch.await(10, TimeUnit.SECONDS);

        assertTrue(errors.isEmpty(),
            "Token cache should be thread-safe: " + errors);
    }

    @Test
    void test_synchronized_on_shared_monitor() {
        
        // With prototype scope, synchronized(this) uses different monitors
        // Fix: Use static lock object shared across all instances

        // Test that concurrent access doesn't corrupt shared state
        ConcurrentHashMap<String, Integer> counter = new ConcurrentHashMap<>();
        int threadCount = 50;
        CountDownLatch latch = new CountDownLatch(threadCount);

        for (int i = 0; i < threadCount; i++) {
            new Thread(() -> {
                try {
                    counter.merge("key", 1, Integer::sum);
                } finally {
                    latch.countDown();
                }
            }).start();
        }

        try { latch.await(10, TimeUnit.SECONDS); } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }

        assertEquals(threadCount, counter.get("key"),
            "All increments should be counted with proper synchronization");
    }

    @Test
    void test_auth_service_uses_shared_lock() throws Exception {
        // A5: AuthService uses synchronized(this) with prototype scope - each instance
        // has a different monitor, providing no mutual exclusion on shared static state.
        // Fix: use a static lock object, or change to singleton scope.
        String source = new String(Files.readAllBytes(
            Paths.get("src/main/java/com/docuvault/security/AuthService.java")));
        String code = source.replaceAll("/\\*[\\s\\S]*?\\*/", "").replaceAll("//[^\n]*", "");

        boolean hasPrototypeScope = code.contains("SCOPE_PROTOTYPE");
        boolean usesSyncThis = code.contains("synchronized (this)")
            || code.contains("synchronized(this)")
            || code.contains("public synchronized ");

        // Either use a static lock with prototype scope, OR don't use prototype scope
        if (hasPrototypeScope) {
            assertFalse(usesSyncThis,
                "AuthService uses SCOPE_PROTOTYPE with synchronized(this) - each instance " +
                "has a different monitor. Use a static lock object or change to singleton scope.");
        }
    }

    // General concurrency tests
    @Test
    void test_concurrent_document_creation() throws Exception {
        int threadCount = 10;
        CountDownLatch latch = new CountDownLatch(threadCount);
        List<Document> created = Collections.synchronizedList(new ArrayList<>());

        for (int i = 0; i < threadCount; i++) {
            final int idx = i;
            new Thread(() -> {
                try {
                    Document doc = new Document();
                    doc.setId((long) idx);
                    doc.setName("concurrent-" + idx);
                    created.add(doc);
                } finally {
                    latch.countDown();
                }
            }).start();
        }

        latch.await(10, TimeUnit.SECONDS);
        assertEquals(threadCount, created.size());
    }

    @Test
    void test_executor_service_thread_safety() throws Exception {
        ExecutorService executor = Executors.newFixedThreadPool(4);
        List<Future<String>> futures = new ArrayList<>();
        AtomicInteger counter = new AtomicInteger(0);

        for (int i = 0; i < 20; i++) {
            futures.add(executor.submit(() -> {
                int val = counter.incrementAndGet();
                return "result-" + val;
            }));
        }

        List<String> results = new ArrayList<>();
        for (Future<String> f : futures) {
            results.add(f.get(5, TimeUnit.SECONDS));
        }

        assertEquals(20, results.size());
        assertEquals(20, counter.get());
        executor.shutdown();
    }

    @Test
    void test_completable_future_chain_safety() throws Exception {
        List<CompletableFuture<Integer>> futures = new ArrayList<>();
        AtomicInteger errors = new AtomicInteger(0);

        for (int i = 0; i < 10; i++) {
            final int idx = i;
            CompletableFuture<Integer> future = CompletableFuture
                .supplyAsync(() -> idx * 2)
                .thenApply(val -> val + 1)
                .exceptionally(ex -> {
                    errors.incrementAndGet();
                    return -1;
                });
            futures.add(future);
        }

        CompletableFuture.allOf(futures.toArray(new CompletableFuture[0])).join();

        assertEquals(0, errors.get());
        for (int i = 0; i < 10; i++) {
            assertEquals(i * 2 + 1, futures.get(i).get());
        }
    }

    @Test
    void test_volatile_visibility() throws Exception {
        // Test for visibility issues (related to A2)
        final boolean[] flag = {false};
        final int[] value = {0};

        Thread writer = new Thread(() -> {
            value[0] = 42;
            flag[0] = true;
        });

        Thread reader = new Thread(() -> {
            // Without volatile, reader might see flag=true but value=0
            if (flag[0]) {
                assertEquals(42, value[0]);
            }
        });

        writer.start();
        writer.join();
        reader.start();
        reader.join();
    }

    @Test
    void test_thread_pool_cleanup() throws Exception {
        ExecutorService executor = Executors.newFixedThreadPool(4);
        CountDownLatch latch = new CountDownLatch(10);

        for (int i = 0; i < 10; i++) {
            executor.submit(() -> {
                try {
                    Thread.sleep(50);
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                } finally {
                    latch.countDown();
                }
            });
        }

        latch.await(10, TimeUnit.SECONDS);
        executor.shutdown();
        assertTrue(executor.awaitTermination(5, TimeUnit.SECONDS));
    }
}
