package com.fleetpulse.shared;

import com.fleetpulse.shared.security.JwtTokenProvider;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

@Tag("security")
public class SecurityTest {

    private JwtTokenProvider provider;

    @BeforeEach
    void setUp() {
        provider = new JwtTokenProvider(
            "fleetpulse-secret-key-for-jwt-minimum-256-bits-long-enough", 86400000);
    }

    
    @Test
    void test_xxe_prevented() {
        String xxePayload = "<?xml version=\"1.0\"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM \"file:///etc/passwd\">]><root>&xxe;</root>";
        
        String result = provider.parseXmlMetadata(xxePayload);
        // In the fixed version, XXE should be blocked
        // Result should be null or not contain file contents
        if (result != null) {
            assertFalse(result.contains("root:"), "XXE should not expose file contents");
        }
    }

    @Test
    void test_external_entities_disabled() {
        String safeXml = "<metadata><key>value</key></metadata>";
        // Safe XML should parse fine
        assertDoesNotThrow(() -> provider.parseXmlMetadata(safeXml));
    }

    @Test
    void test_xxe_billion_laughs() {
        String billionLaughs = "<?xml version=\"1.0\"?><!DOCTYPE lolz [<!ENTITY lol \"lol\"><!ENTITY lol2 \"&lol;&lol;\">]><root>&lol2;</root>";
        // Should not cause memory exhaustion
        assertDoesNotThrow(() -> provider.parseXmlMetadata(billionLaughs));
    }

    
    @Test
    void test_api_key_constant_time() {
        String correct = "correct-api-key-12345";
        String wrong1 = "wrong-api-key-12345xx";
        String wrong2 = "c";

        
        // Fixed version should use constant-time comparison
        boolean result1 = provider.validateApiKey(correct, correct);
        assertTrue(result1);

        boolean result2 = provider.validateApiKey(wrong1, correct);
        assertFalse(result2);

        boolean result3 = provider.validateApiKey(wrong2, correct);
        assertFalse(result3);
    }

    @Test
    void test_timing_safe_compare() {
        // Measure timing for early vs late mismatch
        String expected = "a".repeat(1000);
        String earlyMismatch = "b" + "a".repeat(999);
        String lateMismatch = "a".repeat(999) + "b";

        long earlyStart = System.nanoTime();
        for (int i = 0; i < 10000; i++) {
            provider.validateApiKey(earlyMismatch, expected);
        }
        long earlyTime = System.nanoTime() - earlyStart;

        long lateStart = System.nanoTime();
        for (int i = 0; i < 10000; i++) {
            provider.validateApiKey(lateMismatch, expected);
        }
        long lateTime = System.nanoTime() - lateStart;

        
        // With constant-time comparison, times should be similar
        double ratio = (double) Math.max(earlyTime, lateTime) / Math.min(earlyTime, lateTime);
        assertTrue(ratio < 3.0,
            "Early vs late mismatch timing ratio should be close to 1.0 for constant-time. Got: " + ratio);
    }

    @Test
    void test_generate_and_validate_token() {
        String token = provider.generateToken("user1", "ADMIN", "gateway");
        String username = provider.validateTokenAndGetUsername(token);
        assertEquals("user1", username);
    }

    @Test
    void test_invalid_token() {
        assertNull(provider.validateTokenAndGetUsername("invalid.token.here"));
    }

    @Test
    void test_tampered_token() {
        String token = provider.generateToken("user", "USER", "auth");
        String tampered = token.substring(0, token.length() - 5) + "XXXXX";
        assertNull(provider.validateTokenAndGetUsername(tampered));
    }

    @Test
    void test_null_api_key_provided() {
        // validateApiKey returns false for null provided
        assertFalse(provider.validateApiKey(null, "expected"));
    }

    @Test
    void test_null_api_key_expected() {
        // validateApiKey returns false for null expected
        assertFalse(provider.validateApiKey("provided", null));
    }

    @Test
    void test_empty_api_key() {
        assertFalse(provider.validateApiKey("", "expected"));
    }

    @Test
    void test_equal_api_keys() {
        assertTrue(provider.validateApiKey("same-key", "same-key"));
    }

    @Test
    void test_xml_null_input() {
        assertNull(provider.parseXmlMetadata(null));
    }

    @Test
    void test_xml_empty_input() {
        // Empty or invalid XML should return null, not throw
        assertDoesNotThrow(() -> provider.parseXmlMetadata(""));
    }

    @Test
    void test_xml_valid_input() {
        String xml = "<data>hello</data>";
        String result = provider.parseXmlMetadata(xml);
        assertEquals("hello", result);
    }

    @Test
    void test_jwt_with_service_claim() {
        String token = provider.generateToken("user", "ADMIN", "vehicles");
        assertNotNull(token);
        String username = provider.validateTokenAndGetUsername(token);
        assertEquals("user", username);
    }
}
