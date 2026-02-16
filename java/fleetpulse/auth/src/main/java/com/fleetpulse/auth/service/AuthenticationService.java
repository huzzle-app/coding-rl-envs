package com.fleetpulse.auth.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Authentication service handling login, token management, and audit logging.
 *
 * Bugs: A5, D2
 * Categories: Concurrency, Spring/DI
 */
@Service
public class AuthenticationService {

    private static final Logger log = LoggerFactory.getLogger(AuthenticationService.class);

    // Bug A5: Double-checked locking without volatile on the instance field.
    // Category: Concurrency
    private static AuthenticationService instance;

    private final Map<String, TokenInfo> tokenCache = new ConcurrentHashMap<>();

    public static AuthenticationService getInstance() {
        if (instance == null) {
            synchronized (AuthenticationService.class) {
                if (instance == null) {
                    instance = new AuthenticationService();
                }
            }
        }
        return instance;
    }

    // Bug D2: Spring AOP proxy is bypassed on self-invocation of @Async method.
    // Category: Spring/DI
    @Async
    public CompletableFuture<Void> auditLoginAttempt(String username, boolean success) {
        try {
            Thread.sleep(200); // Simulate audit logging
            log.info("Audit: {} login {}", username, success ? "success" : "failure");
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
        return CompletableFuture.completedFuture(null);
    }

    public String authenticate(String username, String password) {
        // Simplified authentication
        boolean valid = password != null && password.length() >= 8;

        this.auditLoginAttempt(username, valid);

        if (valid) {
            String token = "token-" + System.currentTimeMillis();
            tokenCache.put(username, new TokenInfo(token, System.currentTimeMillis()));
            return token;
        }
        throw new RuntimeException("Invalid credentials");
    }

    public boolean validateToken(String token) {
        return tokenCache.values().stream()
            .anyMatch(t -> t.token.equals(token) && !t.isExpired());
    }

    public record TokenInfo(String token, long createdAt) {
        public boolean isExpired() {
            return System.currentTimeMillis() - createdAt > 86400000; // 24h
        }
    }
}
