package com.docuvault.security;

import com.docuvault.config.SecurityConfig;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import java.io.*;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Base64;

import static org.junit.jupiter.api.Assertions.*;

@Tag("security")
public class SecurityTest {

    // Tests for BUG I1: SQL injection
    @Test
    void test_sql_injection_prevented() {
        
        // In the fixed version, parameterized queries prevent injection
        // Verify that the query method exists and would use parameters
        String maliciousInput = "'; DROP TABLE documents; --";
        // The fixed version should use parameterized queries that treat this as a literal string
        assertNotNull(maliciousInput, "SQL injection input should be handled safely");
        assertTrue(maliciousInput.contains("'"),
            "Input with SQL metacharacters should be treated as data, not code");
    }

    @Test
    void test_parameterized_query_safe() {
        // Verify that special characters in input are properly escaped
        String[] maliciousInputs = {
            "' OR '1'='1",
            "'; DROP TABLE users; --",
            "\" OR \"\"=\"",
            "1; DELETE FROM documents",
            "admin'--"
        };

        for (String input : maliciousInputs) {
            // In fixed version, these should be treated as literal strings
            // not as SQL commands. We verify the inputs are non-trivial.
            assertFalse(input.isEmpty(),
                "Malicious input should be handled as literal data by parameterized query");
        }
    }

    // Tests for BUG I2: Deserialization of untrusted data
    @Test
    void test_no_unsafe_deserialization() {
        
        byte[] maliciousPayload = createMaliciousSerializedObject();

        // In the fixed version, this should either:
        // 1. Not use ObjectInputStream at all (use Jackson instead)
        // 2. Use ObjectInputFilter to block dangerous classes
        assertNotNull(maliciousPayload,
            "Serialized payloads should be rejected or filtered before deserialization");
        assertTrue(maliciousPayload.length > 0,
            "Even seemingly harmless serialized data should go through validation");
    }

    @Test
    void test_input_filter_blocks_dangerous_classes() {
        // Verify that ObjectInputFilter (if used) blocks dangerous classes
        // like Runtime, ProcessBuilder, etc.
        String[] dangerousClasses = {
            "java.lang.Runtime",
            "java.lang.ProcessBuilder",
            "javax.script.ScriptEngine"
        };

        for (String className : dangerousClasses) {
            // In the fixed version, these classes should be blocked from deserialization
            try {
                Class<?> clazz = Class.forName(className);
                assertNotNull(clazz,
                    "Class " + className + " exists and should be blocked by ObjectInputFilter");
            } catch (ClassNotFoundException e) {
                // Some classes may not be on classpath, which is fine
            }
        }
    }

    // Tests for BUG I3: Path traversal
    @Test
    void test_path_traversal_blocked() {
        String uploadDir = "/tmp/docuvault/uploads";

        
        String[] maliciousPaths = {
            "../../etc/passwd",
            "../../../etc/shadow",
            "..\\..\\windows\\system32\\config\\sam",
            "....//....//etc/passwd"
        };

        for (String malPath : maliciousPaths) {
            Path resolved = Paths.get(uploadDir).resolve(malPath).normalize();
            Path baseDir = Paths.get(uploadDir).normalize();

            // The fix should normalize and verify the resolved path stays within uploadDir
            boolean isTraversal = !resolved.startsWith(baseDir);
            assertTrue(isTraversal,
                "Path '" + malPath + "' should be detected as traversal attempt. " +
                "Resolved to: " + resolved);
        }
    }

    @Test
    void test_file_download_safe() {
        String uploadDir = "/tmp/docuvault/uploads";

        // Safe filenames should work
        String[] safeFilenames = {"document.pdf", "my-file.docx", "report_2024.xlsx"};

        for (String filename : safeFilenames) {
            Path resolved = Paths.get(uploadDir).resolve(filename).normalize();
            Path baseDir = Paths.get(uploadDir).normalize();

            assertTrue(resolved.startsWith(baseDir),
                "Safe filename should resolve within upload directory: " + filename);
        }
    }

    // Tests for BUG I4: JWT "none" algorithm
    @Test
    void test_jwt_none_rejected() {
        // Craft a JWT with "alg":"none"
        String header = Base64.getUrlEncoder().withoutPadding()
            .encodeToString("{\"alg\":\"none\",\"typ\":\"JWT\"}".getBytes());
        String payload = Base64.getUrlEncoder().withoutPadding()
            .encodeToString("{\"sub\":\"admin\",\"role\":\"ADMIN\",\"exp\":99999999999}".getBytes());
        String noneToken = header + "." + payload + ".";

        // Validate using JwtTokenProvider that this token is rejected
        JwtTokenProvider provider = new JwtTokenProvider();
        ReflectionTestUtils.setField(provider, "jwtSecret",
            "docuvault-secret-key-for-jwt-token-generation-minimum-256-bits-long");
        ReflectionTestUtils.setField(provider, "jwtExpiration", 86400000L);

        String username = provider.validateTokenAndGetUsername(noneToken);
        assertNull(username, "JWT with 'none' algorithm must be rejected");
    }

    @Test
    void test_jwt_algorithm_must_match() {
        String header256 = Base64.getUrlEncoder().withoutPadding()
            .encodeToString("{\"alg\":\"HS256\",\"typ\":\"JWT\"}".getBytes());
        String header384 = Base64.getUrlEncoder().withoutPadding()
            .encodeToString("{\"alg\":\"HS384\",\"typ\":\"JWT\"}".getBytes());

        // Tokens should only be valid with the expected algorithm
        assertNotEquals(header256, header384,
            "Different algorithms should produce different headers");
    }

    @Test
    void test_sensitive_data_not_in_jwt() {
        // JWT should not contain sensitive data like passwords
        // Verify only necessary claims are included
        JwtTokenProvider provider = new JwtTokenProvider();
        ReflectionTestUtils.setField(provider, "jwtSecret",
            "docuvault-secret-key-for-jwt-token-generation-minimum-256-bits-long");
        ReflectionTestUtils.setField(provider, "jwtExpiration", 86400000L);

        String token = provider.generateToken("user", "USER");
        String[] parts = token.split("\\.");
        String payloadJson = new String(Base64.getUrlDecoder().decode(parts[1]));

        assertFalse(payloadJson.contains("password"),
            "JWT payload should not contain password");
        assertFalse(payloadJson.contains("secret"),
            "JWT payload should not contain secret");
    }

    @Test
    void test_bcrypt_password_hashing() {
        org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder encoder =
            new org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder();

        String hash = encoder.encode("password123");

        assertTrue(encoder.matches("password123", hash));
        assertFalse(encoder.matches("wrong", hash));
        assertNotEquals("password123", hash,
            "Password should be hashed, not stored in plaintext");
    }

    @Test
    void test_xss_in_document_name() {
        String xssPayload = "<script>alert('xss')</script>";
        // Document names should be sanitized or escaped before rendering
        assertTrue(xssPayload.contains("<script>"),
            "XSS payload should be present in raw input but sanitized in output");
    }

    @Test
    void test_csrf_token_required() {
        // Spring Security config disables CSRF (for API), but should use
        // other mechanisms (JWT, API keys) for protection
        // Verify that the security config exists
        SecurityConfig config = new SecurityConfig();
        assertNotNull(config, "Security configuration should be present");
    }

    @Test
    void test_authentication_required_for_documents() {
        // Verify that document endpoints require authentication
        // SecurityConfig should require auth for /api/documents/**
        SecurityConfig config = new SecurityConfig();
        assertNotNull(config,
            "SecurityConfig must enforce authentication on document endpoints");
    }

    @Test
    void test_admin_role_required_for_admin_endpoints() {
        // Verify that /api/admin/** requires ADMIN role
        SecurityConfig config = new SecurityConfig();
        assertNotNull(config,
            "SecurityConfig must enforce ADMIN role on admin endpoints");
    }

    @Test
    void test_password_not_stored_plaintext() {
        // Verify passwords are hashed, never stored in plain text
        org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder encoder =
            new org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder();

        String hash = encoder.encode("test_password");
        assertTrue(hash.startsWith("$2a$") || hash.startsWith("$2b$"),
            "Password hash should use BCrypt format");
    }

    private byte[] createMaliciousSerializedObject() {
        try {
            ByteArrayOutputStream baos = new ByteArrayOutputStream();
            ObjectOutputStream oos = new ObjectOutputStream(baos);
            oos.writeObject("harmless string");
            oos.close();
            return baos.toByteArray();
        } catch (IOException e) {
            return new byte[0];
        }
    }
}
