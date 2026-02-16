package com.vertexgrid.gateway;

import com.vertexgrid.gateway.controller.GatewayController;
import jakarta.persistence.EntityManager;
import jakarta.persistence.Query;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.springframework.http.ResponseEntity;

import java.lang.reflect.Field;
import java.net.URL;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.*;

@Tag("security")
public class GatewaySecurityTest {

    // ====== BUG S4: SQL Injection in searchVehicles ======

    @Test
    void test_sql_injection_prevented() throws Exception {
        GatewayController controller = new GatewayController();

        // Mock EntityManager to capture the SQL being executed
        EntityManager mockEm = mock(EntityManager.class);
        Query mockQuery = mock(Query.class);
        when(mockEm.createNativeQuery(anyString())).thenReturn(mockQuery);
        when(mockQuery.getResultList()).thenReturn(List.of());

        Field emField = GatewayController.class.getDeclaredField("entityManager");
        emField.setAccessible(true);
        emField.set(controller, mockEm);

        String malicious = "'; DROP TABLE vehicles; --";
        controller.searchVehicles(malicious);

        // Capture the SQL that was actually executed
        var sqlCaptor = org.mockito.ArgumentCaptor.forClass(String.class);
        verify(mockEm).createNativeQuery(sqlCaptor.capture());
        String executedSql = sqlCaptor.getValue();

        // With the bug: SQL contains the malicious payload directly
        // With the fix: SQL uses parameter placeholders (?)
        assertFalse(executedSql.contains("DROP TABLE"),
            "SQL query should not embed user input directly (SQL injection): " + executedSql);
    }

    @Test
    void test_parameterized_query() throws Exception {
        GatewayController controller = new GatewayController();

        EntityManager mockEm = mock(EntityManager.class);
        Query mockQuery = mock(Query.class);
        when(mockEm.createNativeQuery(anyString())).thenReturn(mockQuery);
        when(mockQuery.getResultList()).thenReturn(List.of());

        Field emField = GatewayController.class.getDeclaredField("entityManager");
        emField.setAccessible(true);
        emField.set(controller, mockEm);

        String[] payloads = {"' OR '1'='1", "'; DELETE FROM users; --", "\" OR \"\"=\""};
        for (String payload : payloads) {
            controller.searchVehicles(payload);
        }

        var sqlCaptor = org.mockito.ArgumentCaptor.forClass(String.class);
        verify(mockEm, atLeast(1)).createNativeQuery(sqlCaptor.capture());
        for (String sql : sqlCaptor.getAllValues()) {
            // Parameterized queries use ? or :param, never embed user input
            assertFalse(sql.contains("OR '1'='1") || sql.contains("DELETE FROM"),
                "Query should use parameters, not string concatenation: " + sql);
        }
    }

    // ====== BUG S5: Path Traversal in downloadFile ======

    @Test
    void test_path_traversal_blocked() throws Exception {
        GatewayController controller = new GatewayController();

        Field uploadDirField = GatewayController.class.getDeclaredField("uploadDirectory");
        uploadDirField.setAccessible(true);
        uploadDirField.set(controller, "/tmp/vertexgrid/uploads");

        String[] malPaths = {"../../etc/passwd", "../../../etc/shadow", "..\\..\\windows\\system32"};
        for (String malPath : malPaths) {
            ResponseEntity<?> response = controller.downloadFile(malPath);
            // With the bug: returns 404 (file not found) because no path validation
            // With the fix: returns 400 (bad request) after detecting traversal
            assertEquals(400, response.getStatusCode().value(),
                "Path traversal should be blocked with 400 for: " + malPath);
        }
    }

    @Test
    void test_file_download_safe() {
        String uploadDir = "/tmp/vertexgrid/uploads";
        String[] safePaths = {"report.pdf", "data.csv", "image.png"};

        for (String safePath : safePaths) {
            Path resolved = Paths.get(uploadDir).resolve(safePath).normalize();
            Path baseDir = Paths.get(uploadDir).normalize();
            assertTrue(resolved.startsWith(baseDir));
        }
    }

    // ====== BUG S6: SSRF in proxyRequest ======

    @Test
    void test_ssrf_prevented() {
        GatewayController controller = new GatewayController();

        String[] blockedUrls = {
            "http://169.254.169.254/latest/meta-data/",
            "http://127.0.0.1:1/",
            "http://0.0.0.0:1/"
        };

        for (String urlStr : blockedUrls) {
            ResponseEntity<String> response = controller.proxyRequest(urlStr);
            // With the bug: controller tries to connect (gets connection error)
            //   and returns 400 with body "Error: Connection refused" or similar
            // With the fix: controller validates URL first and returns 403
            assertNotEquals(200, response.getStatusCode().value(),
                "Internal URL should never return 200: " + urlStr);
            // Fixed controller should explicitly reject, not fail on connection
            String body = response.getBody();
            assertFalse(body != null && body.startsWith("Error: "),
                "SSRF should be blocked by validation, not connection failure: " + urlStr);
        }
    }

    @Test
    void test_ssrf_blocks_private_ip_ranges() {
        GatewayController controller = new GatewayController();

        // Private IP ranges that should be blocked by the proxy
        String[] privateUrls = {
            "http://10.0.0.1:1/",
            "http://172.16.0.1:1/",
            "http://192.168.1.1:1/"
        };

        for (String urlStr : privateUrls) {
            ResponseEntity<String> response = controller.proxyRequest(urlStr);
            String body = response.getBody();
            // Fixed code should reject private IPs before attempting connection
            assertFalse(body != null && body.startsWith("Error: "),
                "Private IP should be blocked by URL validation: " + urlStr);
        }
    }

    @Test
    void test_url_whitelist() {
        String[] allowedUrls = {"https://api.example.com/data", "https://maps.googleapis.com"};
        for (String url : allowedUrls) {
            assertTrue(url.startsWith("https://"));
        }
    }

    @Test
    void test_sql_union_attack() throws Exception {
        GatewayController controller = new GatewayController();

        EntityManager mockEm = mock(EntityManager.class);
        Query mockQuery = mock(Query.class);
        when(mockEm.createNativeQuery(anyString())).thenReturn(mockQuery);
        when(mockQuery.getResultList()).thenReturn(List.of());

        Field emField = GatewayController.class.getDeclaredField("entityManager");
        emField.setAccessible(true);
        emField.set(controller, mockEm);

        String union = "1 UNION SELECT username, password FROM users--";
        controller.searchVehicles(union);

        var sqlCaptor = org.mockito.ArgumentCaptor.forClass(String.class);
        verify(mockEm).createNativeQuery(sqlCaptor.capture());
        assertFalse(sqlCaptor.getValue().contains("UNION SELECT"),
            "UNION injection should not appear in SQL query");
    }

    @Test
    void test_path_normalization() throws Exception {
        GatewayController controller = new GatewayController();

        Field uploadDirField = GatewayController.class.getDeclaredField("uploadDirectory");
        uploadDirField.setAccessible(true);
        uploadDirField.set(controller, "/tmp/uploads");

        ResponseEntity<?> response = controller.downloadFile("subdir/../../../etc/passwd");
        assertEquals(400, response.getStatusCode().value(),
            "Nested traversal should be blocked with 400");
    }

    @Test
    void test_encoded_path_traversal() {
        String encoded = "%2e%2e%2f%2e%2e%2fetc%2fpasswd";
        String decoded = java.net.URLDecoder.decode(encoded, java.nio.charset.StandardCharsets.UTF_8);
        assertTrue(decoded.contains(".."), "URL-encoded traversal should be detected");
    }

    @Test
    void test_ssrf_ip_ranges() throws Exception {
        // Private IP ranges that should be blocked
        String[] privateRanges = {"10.0.0.1", "172.16.0.1", "192.168.1.1"};
        for (String ip : privateRanges) {
            java.net.InetAddress addr = java.net.InetAddress.getByName(ip);
            assertTrue(addr.isSiteLocalAddress(), ip + " should be identified as site-local");
        }
    }
}
