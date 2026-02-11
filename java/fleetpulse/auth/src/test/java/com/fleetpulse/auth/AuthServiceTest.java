package com.fleetpulse.auth;

import com.fleetpulse.auth.service.AuthenticationService;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.util.Set;
import java.util.concurrent.*;

import static org.junit.jupiter.api.Assertions.*;

@Tag("unit")
public class AuthServiceTest {

    @Test
    void test_dcl_thread_safe() throws Exception {
        int threadCount = 50;
        CountDownLatch latch = new CountDownLatch(threadCount);
        Set<AuthenticationService> instances = ConcurrentHashMap.newKeySet();

        for (int i = 0; i < threadCount; i++) {
            new Thread(() -> {
                try {
                    instances.add(AuthenticationService.getInstance());
                } finally {
                    latch.countDown();
                }
            }).start();
        }

        latch.await(10, TimeUnit.SECONDS);
        assertEquals(1, instances.size(),
            "DCL should produce exactly one instance across all threads");
    }

    @Test
    void test_no_partial_construction() throws Exception {
        int threadCount = 20;
        CountDownLatch latch = new CountDownLatch(threadCount);

        for (int i = 0; i < threadCount; i++) {
            new Thread(() -> {
                try {
                    AuthenticationService instance = AuthenticationService.getInstance();
                    assertNotNull(instance);
                } finally {
                    latch.countDown();
                }
            }).start();
        }

        latch.await(10, TimeUnit.SECONDS);
    }

    @Test
    void test_async_runs_async() {
        AuthenticationService service = new AuthenticationService();

        long start = System.currentTimeMillis();
        
        service.authenticate("testuser", "password123");
        long elapsed = System.currentTimeMillis() - start;

        // If async works, authenticate should return quickly (< 100ms)
        // If sync (bug), it takes 200ms+ due to audit sleep
        assertTrue(elapsed < 150,
            "Authenticate should be fast when audit runs async. Took: " + elapsed + "ms");
    }

    @Test
    void test_async_not_sync() {
        AuthenticationService service = new AuthenticationService();
        CompletableFuture<Void> future = service.auditLoginAttempt("user", true);
        assertNotNull(future);
    }

    @Test
    void test_authenticate_success() {
        AuthenticationService service = new AuthenticationService();
        String token = service.authenticate("user", "password123");
        assertNotNull(token);
        assertTrue(token.startsWith("token-"));
    }

    @Test
    void test_authenticate_failure() {
        AuthenticationService service = new AuthenticationService();
        assertThrows(RuntimeException.class, () ->
            service.authenticate("user", "short"));
    }

    @Test
    void test_validate_token() {
        AuthenticationService service = new AuthenticationService();
        String token = service.authenticate("user", "validpass1");
        assertTrue(service.validateToken(token));
    }

    @Test
    void test_invalid_token() {
        AuthenticationService service = new AuthenticationService();
        assertFalse(service.validateToken("invalid-token"));
    }

    @Test
    void test_concurrent_authentication() throws Exception {
        AuthenticationService service = new AuthenticationService();
        int threadCount = 10;
        CountDownLatch latch = new CountDownLatch(threadCount);
        ConcurrentHashMap<String, String> tokens = new ConcurrentHashMap<>();

        for (int i = 0; i < threadCount; i++) {
            final int idx = i;
            new Thread(() -> {
                try {
                    String token = service.authenticate("user" + idx, "password" + idx);
                    tokens.put("user" + idx, token);
                } catch (Exception e) {
                    // ignore
                } finally {
                    latch.countDown();
                }
            }).start();
        }

        latch.await(10, TimeUnit.SECONDS);
        assertEquals(threadCount, tokens.size());
    }

    @Test
    void test_singleton_consistency() {
        AuthenticationService s1 = AuthenticationService.getInstance();
        AuthenticationService s2 = AuthenticationService.getInstance();
        assertSame(s1, s2);
    }
}
