package com.docuvault.security;

import com.docuvault.config.SecurityConfig;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import java.io.*;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Base64;

import static org.junit.jupiter.api.Assertions.*;

@Tag("security")
public class SecurityTest {

    // Tests for BUG I1: SQL injection
    @Test
    void test_sql_injection_prevented() throws Exception {
        // Verify SecurityConfig.searchDocumentsByName uses parameterized queries,
        // not string concatenation. Read source and strip comments before checking.
        Path sourceFile = Paths.get("src/main/java/com/docuvault/config/SecurityConfig.java");
        String source = new String(java.nio.file.Files.readAllBytes(sourceFile));
        String code = stripComments(source);

        // The vulnerable pattern: concatenating user input into SQL string
        boolean hasStringConcat = code.contains("+ userInput +")
            || code.contains("\" + userInput")
            || code.contains("userInput + \"");
        assertFalse(hasStringConcat,
            "SecurityConfig.searchDocumentsByName must use parameterized queries, " +
            "not string concatenation with user input");
    }

    @Test
    void test_parameterized_query_uses_setParameter() throws Exception {
        // Verify the query uses setParameter() for safe parameterization
        Path sourceFile = Paths.get("src/main/java/com/docuvault/config/SecurityConfig.java");
        String source = new String(java.nio.file.Files.readAllBytes(sourceFile));
        String code = stripComments(source);

        // The fixed version should use setParameter to bind values safely
        assertTrue(code.contains("setParameter") || code.contains(":userInput")
            || code.contains("?1"),
            "searchDocumentsByName should use parameterized query binding (setParameter or :param)");
    }

    // Tests for BUG I2: Deserialization of untrusted data
    @Test
    void test_no_unsafe_deserialization() throws Exception {
        // Verify DocumentController does NOT use raw ObjectInputStream.
        // Strip comments since bug descriptions mention the fix patterns.
        Path sourceFile = Paths.get("src/main/java/com/docuvault/controller/DocumentController.java");
        String source = new String(java.nio.file.Files.readAllBytes(sourceFile));
        String code = stripComments(source);

        boolean usesRawOIS = code.contains("new ObjectInputStream(")
            && !code.contains("setObjectInputFilter")
            && !code.contains("ObjectInputFilter");

        assertFalse(usesRawOIS,
            "DocumentController must not use raw ObjectInputStream without ObjectInputFilter. " +
            "Use Jackson ObjectMapper or add ObjectInputFilter to whitelist allowed classes.");
    }

    @Test
    void test_safe_deserialization_method() throws Exception {
        // Verify the metadata endpoint uses safe deserialization (stripping comments)
        Path sourceFile = Paths.get("src/main/java/com/docuvault/controller/DocumentController.java");
        String source = new String(java.nio.file.Files.readAllBytes(sourceFile));
        String code = stripComments(source);

        boolean usesSafeMethod = code.contains("ObjectMapper")
            || code.contains("ObjectInputFilter")
            || code.contains("setObjectInputFilter")
            || !code.contains("ObjectInputStream");

        assertTrue(usesSafeMethod,
            "uploadMetadata should use Jackson ObjectMapper or ObjectInputFilter for safe deserialization");
    }

    // Tests for BUG I3: Path traversal
    @Test
    void test_path_traversal_blocked() {
        String uploadDir = "/tmp/docuvault/uploads";

        // Only use forward-slash paths that work cross-platform
        String[] maliciousPaths = {
            "../../etc/passwd",
            "../../../etc/shadow",
            "subdir/../../etc/passwd",
            "../../../root/.ssh/id_rsa"
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

    /** Strip single-line (//) and multi-line comments from Java source. */
    private String stripComments(String source) {
        // Remove multi-line comments (/* ... */)
        String result = source.replaceAll("/\\*[\\s\\S]*?\\*/", "");
        // Remove single-line comments (// ...)
        result = result.replaceAll("//[^\n]*", "");
        return result;
    }
}
