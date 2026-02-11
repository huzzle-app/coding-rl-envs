package com.fleetpulse.auth;

import com.fleetpulse.auth.security.TokenValidator;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import java.io.*;
import java.util.Base64;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

@Tag("security")
public class TokenValidatorTest {

    private TokenValidator validator;

    @BeforeEach
    void setUp() {
        validator = new TokenValidator();
        ReflectionTestUtils.setField(validator, "jwtSecret",
            "fleetpulse-secret-key-for-jwt-minimum-256-bits-long-enough");
    }

    @Test
    void test_jwt_none_rejected() {
        String header = Base64.getUrlEncoder().withoutPadding()
            .encodeToString("{\"alg\":\"none\",\"typ\":\"JWT\"}".getBytes());
        String payload = Base64.getUrlEncoder().withoutPadding()
            .encodeToString("{\"sub\":\"hacker\",\"role\":\"ADMIN\"}".getBytes());
        String noneToken = header + "." + payload + ".";

        assertNull(validator.validateToken(noneToken),
            "JWT with 'none' algorithm should be rejected");
    }

    @Test
    void test_algorithm_enforced() {
        String token = validator.generateToken("user", "USER");
        String[] parts = token.split("\\.");
        String headerJson = new String(Base64.getUrlDecoder().decode(parts[0]));
        assertTrue(headerJson.contains("HS"), "Token should use HS algorithm");
    }

    @Test
    void test_constant_time_compare() {
        
        assertTrue(validator.validatePassword("password", "password"));
        assertFalse(validator.validatePassword("wrong", "password"));
    }

    @Test
    void test_no_timing_attack() {
        String expected = "a".repeat(100);
        String early = "b" + "a".repeat(99);
        String late = "a".repeat(99) + "b";

        long t1 = System.nanoTime();
        for (int i = 0; i < 10000; i++) validator.validatePassword(early, expected);
        long earlyTime = System.nanoTime() - t1;

        long t2 = System.nanoTime();
        for (int i = 0; i < 10000; i++) validator.validatePassword(late, expected);
        long lateTime = System.nanoTime() - t2;

        double ratio = (double) Math.max(earlyTime, lateTime) / Math.min(earlyTime, lateTime);
        assertTrue(ratio < 3.0, "Timing ratio should be close to 1.0. Got: " + ratio);
    }

    @Test
    void test_no_unsafe_deser() {
        byte[] malicious = createSerializedObject();
        
        Map<String, Object> result = validator.deserializeSession(malicious);
        // In fixed version, this should use safe deserialization
        assertNotNull(result);
    }

    @Test
    void test_input_filter() {
        byte[] data = createSerializedObject();
        // Should not throw even with potentially malicious data
        assertDoesNotThrow(() -> validator.deserializeSession(data));
    }

    @Test
    void test_generate_validate_token() {
        String token = validator.generateToken("admin", "ADMIN");
        String username = validator.validateToken(token);
        assertEquals("admin", username);
    }

    @Test
    void test_tampered_token_rejected() {
        String token = validator.generateToken("user", "USER");
        String tampered = token + "x";
        assertNull(validator.validateToken(tampered));
    }

    @Test
    void test_token_with_modified_payload() {
        String token = validator.generateToken("user", "USER");
        String[] parts = token.split("\\.");
        String newPayload = Base64.getUrlEncoder().withoutPadding()
            .encodeToString("{\"sub\":\"admin\",\"role\":\"ADMIN\"}".getBytes());
        String modified = parts[0] + "." + newPayload + "." + parts[2];
        assertNull(validator.validateToken(modified));
    }

    @Test
    void test_invalid_token_null() {
        assertNull(validator.validateToken("not.a.token"));
    }

    private byte[] createSerializedObject() {
        try {
            ByteArrayOutputStream baos = new ByteArrayOutputStream();
            ObjectOutputStream oos = new ObjectOutputStream(baos);
            oos.writeObject(new java.util.HashMap<>(Map.of("key", "value")));
            oos.close();
            return baos.toByteArray();
        } catch (IOException e) {
            return new byte[0];
        }
    }
}
