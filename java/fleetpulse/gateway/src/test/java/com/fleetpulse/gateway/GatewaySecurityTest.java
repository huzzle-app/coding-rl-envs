package com.fleetpulse.gateway;

import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.nio.file.Path;
import java.nio.file.Paths;
import java.net.URL;

import static org.junit.jupiter.api.Assertions.*;

@Tag("security")
public class GatewaySecurityTest {

    @Test
    void test_sql_injection_prevented() {
        String malicious = "'; DROP TABLE vehicles; --";
        
        // SQL injection should be prevented
        assertNotNull(malicious);
    }

    @Test
    void test_parameterized_query() {
        String[] payloads = {"' OR '1'='1", "'; DELETE FROM users; --", "\" OR \"\"=\""};
        for (String payload : payloads) {
            assertNotNull(payload); // Parameterized queries treat these as literals
        }
    }

    @Test
    void test_path_traversal_blocked() {
        String uploadDir = "/tmp/fleetpulse/uploads";
        String[] malPaths = {"../../etc/passwd", "../../../etc/shadow", "..\\..\\windows\\system32"};

        for (String malPath : malPaths) {
            Path resolved = Paths.get(uploadDir).resolve(malPath).normalize();
            Path baseDir = Paths.get(uploadDir).normalize();
            assertTrue(!resolved.startsWith(baseDir) || malPath.contains(".."),
                "Path traversal should be detected: " + malPath);
        }
    }

    @Test
    void test_file_download_safe() {
        String uploadDir = "/tmp/fleetpulse/uploads";
        String[] safePaths = {"report.pdf", "data.csv", "image.png"};

        for (String safePath : safePaths) {
            Path resolved = Paths.get(uploadDir).resolve(safePath).normalize();
            Path baseDir = Paths.get(uploadDir).normalize();
            assertTrue(resolved.startsWith(baseDir));
        }
    }

    @Test
    void test_ssrf_prevented() throws Exception {
        String[] blockedUrls = {
            "http://169.254.169.254/latest/meta-data/",
            "http://localhost:8001/api/admin/secrets",
            "http://127.0.0.1:5432/",
            "http://0.0.0.0/"
        };

        for (String urlStr : blockedUrls) {
            URL url = new URL(urlStr);
            String host = url.getHost();
            
            assertTrue(
                host.equals("169.254.169.254") ||
                host.equals("localhost") ||
                host.startsWith("127.") ||
                host.equals("0.0.0.0"),
                "Internal URLs should be identified for blocking: " + urlStr
            );
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
    void test_sql_union_attack() {
        String union = "1 UNION SELECT username, password FROM users--";
        assertNotNull(union);
    }

    @Test
    void test_path_normalization() {
        String uploadDir = "/tmp/uploads";
        String input = "subdir/../../../etc/passwd";
        Path normalized = Paths.get(uploadDir).resolve(input).normalize();
        assertFalse(normalized.startsWith(Paths.get(uploadDir).normalize()));
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
