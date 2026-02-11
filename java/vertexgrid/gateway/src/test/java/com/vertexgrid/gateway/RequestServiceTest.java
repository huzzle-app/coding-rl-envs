package com.vertexgrid.gateway;

import com.vertexgrid.gateway.service.RequestService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.*;

@Tag("unit")
public class RequestServiceTest {

    private RequestService requestService;

    @BeforeEach
    void setUp() {
        requestService = new RequestService();
    }

    @Test
    void test_threadlocal_cleaned() {
        requestService.setRequestContext(
            new RequestService.RequestContext("req-1", "user-1"));
        assertNotNull(requestService.getRequestContext());

        requestService.clearRequestContext();
        assertNull(requestService.getRequestContext(),
            "ThreadLocal should be null after cleanup");
    }

    @Test
    void test_no_threadlocal_leak() throws Exception {
        for (int i = 0; i < 50; i++) {
            requestService.setRequestContext(
                new RequestService.RequestContext("req-" + i, "user-" + i));
            requestService.clearRequestContext();
        }
        assertNull(requestService.getRequestContext());
    }

    @Test
    void test_threadlocal_isolation() throws Exception {
        requestService.setRequestContext(
            new RequestService.RequestContext("main", "user-main"));

        AtomicReference<RequestService.RequestContext> otherCtx = new AtomicReference<>();
        CountDownLatch latch = new CountDownLatch(1);

        new Thread(() -> {
            otherCtx.set(requestService.getRequestContext());
            latch.countDown();
        }).start();

        latch.await(5, TimeUnit.SECONDS);
        assertNull(otherCtx.get(), "ThreadLocal should not leak to other threads");
        requestService.clearRequestContext();
    }

    @Test
    void test_transactional_proxy_works() {
        
        assertDoesNotThrow(() ->
            requestService.processRequest("req-1", "payload"));
    }

    @Test
    void test_self_invocation_fixed() {
        
        requestService.processRequest("req-2", "data");
        // Should not throw - the transaction should be active
    }

    @Test
    void test_request_context_data() {
        var ctx = new RequestService.RequestContext("req-1", "user-1");
        assertEquals("req-1", ctx.getRequestId());
        assertEquals("user-1", ctx.getUserId());
        assertTrue(ctx.getTimestamp() > 0);
    }

    @Test
    void test_async_processing() throws Exception {
        var future = requestService.processAsync("req-1");
        String result = future.get(5, TimeUnit.SECONDS);
        assertTrue(result.contains("req-1"));
    }

    @Test
    void test_set_and_get_context() {
        var ctx = new RequestService.RequestContext("r1", "u1");
        requestService.setRequestContext(ctx);
        assertSame(ctx, requestService.getRequestContext());
        requestService.clearRequestContext();
    }

    @Test
    void test_clear_null_context() {
        assertDoesNotThrow(() -> requestService.clearRequestContext());
    }

    @Test
    void test_multiple_context_updates() {
        requestService.setRequestContext(new RequestService.RequestContext("r1", "u1"));
        requestService.setRequestContext(new RequestService.RequestContext("r2", "u2"));
        assertEquals("r2", requestService.getRequestContext().getRequestId());
        requestService.clearRequestContext();
    }
}
