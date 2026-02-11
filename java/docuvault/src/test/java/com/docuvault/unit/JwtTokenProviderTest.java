package com.docuvault.unit;

import com.docuvault.security.JwtTokenProvider;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.Base64;

import static org.junit.jupiter.api.Assertions.*;

@Tag("unit")
public class JwtTokenProviderTest {

    private JwtTokenProvider jwtTokenProvider;

    @BeforeEach
    void setUp() {
        jwtTokenProvider = new JwtTokenProvider();
        ReflectionTestUtils.setField(jwtTokenProvider, "jwtSecret",
            "docuvault-secret-key-for-jwt-token-generation-minimum-256-bits-long");
        ReflectionTestUtils.setField(jwtTokenProvider, "jwtExpiration", 86400000L);
    }

    @Test
    void test_generate_and_validate_token() {
        String token = jwtTokenProvider.generateToken("testuser", "USER");
        assertNotNull(token);

        String username = jwtTokenProvider.validateTokenAndGetUsername(token);
        assertEquals("testuser", username);
    }

    @Test
    void test_token_contains_role() {
        String token = jwtTokenProvider.generateToken("admin", "ADMIN");
        String role = jwtTokenProvider.getRoleFromToken(token);
        assertEquals("ADMIN", role);
    }

    @Test
    void test_invalid_token_returns_null() {
        String result = jwtTokenProvider.validateTokenAndGetUsername("invalid.token.here");
        assertNull(result);
    }

    @Test
    void test_expired_token() {
        ReflectionTestUtils.setField(jwtTokenProvider, "jwtExpiration", -1000L);
        String token = jwtTokenProvider.generateToken("user", "USER");

        assertTrue(jwtTokenProvider.isTokenExpired(token));
    }

    // Tests for BUG I4: JWT "none" algorithm accepted
    @Test
    void test_jwt_none_algorithm_rejected() {
        // Craft a token with "alg":"none"
        String header = Base64.getUrlEncoder().withoutPadding()
            .encodeToString("{\"alg\":\"none\",\"typ\":\"JWT\"}".getBytes());
        String payload = Base64.getUrlEncoder().withoutPadding()
            .encodeToString("{\"sub\":\"hacker\",\"role\":\"ADMIN\"}".getBytes());
        String noneToken = header + "." + payload + ".";

        
        String username = jwtTokenProvider.validateTokenAndGetUsername(noneToken);
        assertNull(username, "JWT with 'none' algorithm should be rejected");
    }

    @Test
    void test_jwt_requires_valid_signature() {
        String token = jwtTokenProvider.generateToken("testuser", "USER");

        // Tamper with the signature
        String[] parts = token.split("\\.");
        String tampered = parts[0] + "." + parts[1] + ".invalidsignature";

        String result = jwtTokenProvider.validateTokenAndGetUsername(tampered);
        assertNull(result, "Token with invalid signature should be rejected");
    }

    @Test
    void test_jwt_algorithm_enforced() {
        // Create a valid token and verify it uses the expected algorithm
        String token = jwtTokenProvider.generateToken("user", "USER");
        String[] parts = token.split("\\.");
        String headerJson = new String(Base64.getUrlDecoder().decode(parts[0]));

        // Token should use HS256 or HS384/HS512, not "none"
        assertTrue(headerJson.contains("HS") || headerJson.contains("RS"),
            "Token should use a secure algorithm, not 'none'. Header: " + headerJson);
    }

    @Test
    void test_jwt_with_modified_payload() {
        String token = jwtTokenProvider.generateToken("user", "USER");

        // Modify payload to change role
        String[] parts = token.split("\\.");
        String newPayload = Base64.getUrlEncoder().withoutPadding()
            .encodeToString("{\"sub\":\"user\",\"role\":\"ADMIN\"}".getBytes());
        String modified = parts[0] + "." + newPayload + "." + parts[2];

        String result = jwtTokenProvider.validateTokenAndGetUsername(modified);
        assertNull(result, "Token with modified payload should be rejected");
    }
}
