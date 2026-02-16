package com.fleetpulse.notifications;

import com.fleetpulse.notifications.service.NotificationService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReferenceArray;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Tests for NotificationService covering bugs:
 *   A8  - Volatile array reference does not make array elements volatile
 *   A9  - Synchronized on String.intern() causes unrelated code blocking
 *   H1  - Cache key collision between different data types
 *   H2  - Thundering herd / cache stampede on cache miss
 *   C4  - @Cacheable key collision for overloaded methods
 */
@Tag("unit")
public class NotificationServiceTest {

    private NotificationService service;

    @BeforeEach
    void setUp() {
        service = new NotificationService();
    }

    // ---------------------------------------------------------------
    
    // ---------------------------------------------------------------

    @Test
    @Tag("concurrency")
    void test_volatile_array_element_visibility() throws Exception {
        
        // guaranteed visible to other threads. After updateChannel(0, "WEBHOOK"),
        // a reader thread may still see "EMAIL" at index 0.
        service.updateChannel(0, "WEBHOOK");

        AtomicInteger staleReads = new AtomicInteger(0);
        int iterations = 1000;
        CountDownLatch latch = new CountDownLatch(iterations);

        for (int i = 0; i < iterations; i++) {
            Thread.startVirtualThread(() -> {
                try {
                    String[] channels = service.getNotificationChannels();
                    if (!"WEBHOOK".equals(channels[0])) {
                        staleReads.incrementAndGet();
                    }
                } finally {
                    latch.countDown();
                }
            });
        }

        latch.await(10, TimeUnit.SECONDS);

        // All channel updates should be visible to other threads
        assertEquals(0, staleReads.get(),
            "All threads should see updated channel value - volatile array elements are not thread-safe");
    }

    @Test
    @Tag("concurrency")
    void test_volatile_array_concurrent_writes() throws Exception {
        
        int threadCount = 50;
        CountDownLatch latch = new CountDownLatch(threadCount);
        Set<String> observedValues = ConcurrentHashMap.newKeySet();

        for (int i = 0; i < threadCount; i++) {
            final String newChannel = "CHANNEL_" + i;
            Thread.startVirtualThread(() -> {
                try {
                    service.updateChannel(0, newChannel);
                    observedValues.add(service.getNotificationChannels()[0]);
                } finally {
                    latch.countDown();
                }
            });
        }

        latch.await(10, TimeUnit.SECONDS);

        // After all writes, the final value should be one of the written values
        String finalValue = service.getNotificationChannels()[0];
        assertTrue(finalValue.startsWith("CHANNEL_"),
            "Final value should be one of the written channel values");
    }

    @Test
    void test_get_notification_channels_returns_array() {
        String[] channels = service.getNotificationChannels();
        assertNotNull(channels);
        assertEquals(3, channels.length);
        assertEquals("EMAIL", channels[0]);
        assertEquals("SMS", channels[1]);
        assertEquals("PUSH", channels[2]);
    }

    @Test
    void test_update_channel_at_valid_index() {
        service.updateChannel(1, "WEBHOOK");
        assertEquals("WEBHOOK", service.getNotificationChannels()[1]);
    }

    // ---------------------------------------------------------------
    
    // ---------------------------------------------------------------

    @Test
    @Tag("concurrency")
    void test_string_intern_lock_contention() throws Exception {
        
        // that synchronizes on the same interned string will contend for the
        // same lock object. Different channels should use independent locks.
        int threadCount = 10;
        CountDownLatch latch = new CountDownLatch(threadCount);
        long start = System.nanoTime();

        for (int i = 0; i < threadCount; i++) {
            final String channel = (i % 2 == 0) ? "EMAIL" : "SMS";
            Thread.startVirtualThread(() -> {
                try {
                    service.sendNotification(channel, "user" + Thread.currentThread().threadId(), "test");
                } finally {
                    latch.countDown();
                }
            });
        }

        latch.await(30, TimeUnit.SECONDS);
        long elapsed = System.nanoTime() - start;

        // With independent locks per channel, EMAIL and SMS could run in parallel.
        // With intern()-based locking, all calls contend on the same lock.
        // The fixed version should complete faster because EMAIL and SMS don't block each other.
        assertTrue(elapsed < 10_000_000_000L, // 10 seconds max
            "Notifications with different channels should not all serialize on the same lock");
    }

    @Test
    @Tag("concurrency")
    void test_independent_channel_locks() throws Exception {
        
        // without blocking each other. With String.intern(), they share a lock
        // if by coincidence another part of the JVM interns the same string.
        CountDownLatch startGate = new CountDownLatch(1);
        CountDownLatch doneLatch = new CountDownLatch(2);
        List<Long> finishTimes = Collections.synchronizedList(new ArrayList<>());

        Thread t1 = Thread.startVirtualThread(() -> {
            try {
                startGate.await();
                service.sendNotification("EMAIL", "user1", "msg1");
                finishTimes.add(System.nanoTime());
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            } finally {
                doneLatch.countDown();
            }
        });

        Thread t2 = Thread.startVirtualThread(() -> {
            try {
                startGate.await();
                service.sendNotification("SMS", "user2", "msg2");
                finishTimes.add(System.nanoTime());
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            } finally {
                doneLatch.countDown();
            }
        });

        startGate.countDown(); // Release both threads simultaneously
        assertTrue(doneLatch.await(10, TimeUnit.SECONDS), "Both sends should complete");
        assertEquals(2, finishTimes.size());
    }

    @Test
    void test_send_notification_completes() {
        // Basic smoke test: sendNotification should not throw
        assertDoesNotThrow(() ->
            service.sendNotification("EMAIL", "user1", "Hello"));
    }

    @Test
    void test_send_notification_different_channels() {
        assertDoesNotThrow(() -> {
            service.sendNotification("EMAIL", "u1", "msg1");
            service.sendNotification("SMS", "u2", "msg2");
            service.sendNotification("PUSH", "u3", "msg3");
        });
    }

    // ---------------------------------------------------------------
    
    // ---------------------------------------------------------------

    @Test
    void test_cache_key_collision_notifications_vs_preferences() {
        
        // @Cacheable(value = "notifications", key = "#userId"), so calling
        // one first caches its result, and calling the other returns that
        // cached result instead of computing a new one.
        Long userId = 42L;

        List<String> notifications = service.getUserNotifications(userId);
        List<String> preferences = service.getUserPreferences(userId);

        // These should return different data
        assertNotNull(notifications);
        assertNotNull(preferences);
        assertNotEquals(notifications, preferences,
            "Notifications and preferences should not collide in cache for same userId");
    }

    @Test
    void test_notifications_contain_expected_content() {
        List<String> notifications = service.getUserNotifications(1L);
        assertNotNull(notifications);
        assertFalse(notifications.isEmpty());
        assertTrue(notifications.stream().anyMatch(n -> n.contains("notification") || n.contains("update")),
            "Notifications should contain notification-related content");
    }

    @Test
    void test_preferences_contain_expected_content() {
        List<String> preferences = service.getUserPreferences(1L);
        assertNotNull(preferences);
        assertFalse(preferences.isEmpty());
        assertTrue(preferences.stream().anyMatch(p -> p.contains("=")),
            "Preferences should contain key=value format");
    }

    @Test
    void test_different_users_get_different_cache_entries() {
        List<String> user1Notifs = service.getUserNotifications(1L);
        List<String> user2Notifs = service.getUserNotifications(2L);
        // Both should return non-null, even if content is the same
        assertNotNull(user1Notifs);
        assertNotNull(user2Notifs);
    }

    // ---------------------------------------------------------------
    
    // ---------------------------------------------------------------

    @Test
    @Tag("concurrency")
    void test_thundering_herd_prevention() throws Exception {
        
        // only invoke the loader once. With the buggy implementation, all threads
        // call loader.call() independently.
        AtomicInteger loaderInvocations = new AtomicInteger(0);
        int threadCount = 50;
        CountDownLatch startGate = new CountDownLatch(1);
        CountDownLatch doneLatch = new CountDownLatch(threadCount);

        Callable<Object> loader = () -> {
            loaderInvocations.incrementAndGet();
            Thread.sleep(100); // Simulate expensive backend call
            return "loaded-value";
        };

        for (int i = 0; i < threadCount; i++) {
            Thread.startVirtualThread(() -> {
                try {
                    startGate.await();
                    service.getCachedData("stampede-key", loader);
                } catch (Exception e) {
                    // ignore
                } finally {
                    doneLatch.countDown();
                }
            });
        }

        startGate.countDown();
        assertTrue(doneLatch.await(30, TimeUnit.SECONDS), "All threads should complete");

        // Loader should be invoked exactly once for concurrent requests
        assertEquals(1, loaderInvocations.get(),
            "Loader should be invoked only once, not " + loaderInvocations.get() +
            " times (thundering herd)");
    }

    @Test
    void test_cached_data_returns_loaded_value() {
        Object result = service.getCachedData("key1", () -> "value1");
        assertEquals("value1", result);
    }

    @Test
    void test_cached_data_returns_cached_on_second_call() {
        AtomicInteger loadCount = new AtomicInteger(0);
        Callable<Object> loader = () -> {
            loadCount.incrementAndGet();
            return "cached-result";
        };

        service.getCachedData("key2", loader);
        service.getCachedData("key2", loader);

        // Second call should use cached value, not invoke loader again
        assertEquals(1, loadCount.get(), "Loader should only be called once for cached key");
    }

    @Test
    void test_cached_data_null_key_handling() {
        // getCachedData should work with any string key
        Object result = service.getCachedData("null-test-key", () -> 42);
        assertEquals(42, result);
    }

    // ---------------------------------------------------------------
    
    // ---------------------------------------------------------------

    @Test
    void test_template_by_id_vs_name_collision() {
        
        // @Cacheable(value = "templates") with default key generation.
        // getTemplate(1L) and getTemplate("1") may produce the same cache key.
        String byId = service.getTemplate(1L);
        String byName = service.getTemplate("1");

        assertNotNull(byId);
        assertNotNull(byName);

        // They should return different content since they are different methods
        assertNotEquals(byId, byName,
            "getTemplate(Long) and getTemplate(String) should not share cache entries");
    }

    @Test
    void test_template_by_id_content() {
        String template = service.getTemplate(42L);
        assertNotNull(template);
        assertTrue(template.contains("42"), "Template should reference the ID");
        assertTrue(template.contains("ID"), "Template by ID should mention 'ID'");
    }

    @Test
    void test_template_by_name_content() {
        String template = service.getTemplate("welcome");
        assertNotNull(template);
        assertTrue(template.contains("welcome"), "Template should reference the name");
        assertTrue(template.contains("name"), "Template by name should mention 'name'");
    }

    @Test
    void test_different_template_ids_return_different_results() {
        String t1 = service.getTemplate(1L);
        String t2 = service.getTemplate(2L);
        assertNotEquals(t1, t2, "Different IDs should return different templates");
    }
}
