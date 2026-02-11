package com.vertexgrid.gateway.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.concurrent.CompletableFuture;

@Service
public class RequestService {

    private static final Logger log = LoggerFactory.getLogger(RequestService.class);

    
    // In virtual thread or pooled thread environment, context leaks to next request
    // Fix: Add finally { requestContext.remove(); } in filter or interceptor
    private static final ThreadLocal<RequestContext> requestContext = new ThreadLocal<>();

    public void setRequestContext(RequestContext context) {
        
        requestContext.set(context);
    }

    public RequestContext getRequestContext() {
        return requestContext.get();
    }

    public void clearRequestContext() {
        requestContext.remove();
    }

    
    // Public method calls @Transactional method on 'this' → transaction not started
    // Fix: Inject self via @Lazy or extract to separate service
    public void processRequest(String requestId, String payload) {
        log.info("Processing request: {}", requestId);
        
        this.saveRequestLog(requestId, payload);
    }

    @Transactional
    public void saveRequestLog(String requestId, String payload) {
        log.info("Saving request log: {} (should be in transaction)", requestId);
        // In a real implementation, this would persist to database
    }

    @Async
    public CompletableFuture<String> processAsync(String requestId) {
        try {
            Thread.sleep(100);
            return CompletableFuture.completedFuture("Processed: " + requestId);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return CompletableFuture.failedFuture(e);
        }
    }

    public static class RequestContext {
        private final String requestId;
        private final String userId;
        private final long timestamp;

        public RequestContext(String requestId, String userId) {
            this.requestId = requestId;
            this.userId = userId;
            this.timestamp = System.currentTimeMillis();
        }

        public String getRequestId() { return requestId; }
        public String getUserId() { return userId; }
        public long getTimestamp() { return timestamp; }
    }
}
