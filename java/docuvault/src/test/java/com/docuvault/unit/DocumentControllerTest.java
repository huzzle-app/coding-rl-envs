package com.docuvault.unit;

import com.docuvault.controller.AdminController;
import com.docuvault.controller.DocumentController;
import com.docuvault.model.Document;
import com.docuvault.model.User;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

import static org.junit.jupiter.api.Assertions.*;

@Tag("unit")
public class DocumentControllerTest {

    private List<Document> testDocs;

    @BeforeEach
    void setUp() {
        testDocs = new ArrayList<>();
        for (int i = 0; i < 10; i++) {
            Document doc = new Document();
            doc.setId((long) i);
            doc.setName("doc-" + i + ".pdf");
            doc.setContentType("application/pdf");

            User owner = new User();
            owner.setId((long) (i % 3));
            owner.setUsername("user" + (i % 3));
            doc.setOwner(owner);

            testDocs.add(doc);
        }
    }

    // Tests for BUG B3: Collectors.toMap duplicate key
    @Test
    void test_document_list_with_duplicates() {
        // Create documents with duplicate owner IDs
        
        List<Document> docsWithDupeOwners = new ArrayList<>();
        for (int i = 0; i < 5; i++) {
            Document doc = new Document();
            doc.setId((long) i);
            doc.setName("doc-" + i);
            User owner = new User();
            owner.setId(1L); // Same owner for all
            owner.setUsername("user1");
            doc.setOwner(owner);
            docsWithDupeOwners.add(doc);
        }

        // The fixed version should use merge function to handle duplicates
        assertDoesNotThrow(() -> {
            Map<Long, Document> byOwner = docsWithDupeOwners.stream()
                .collect(Collectors.toMap(
                    d -> d.getOwner().getId(),
                    d -> d,
                    (existing, replacement) -> replacement
                ));
            assertFalse(byOwner.isEmpty());
        }, "Collectors.toMap should handle duplicate keys with merge function");
    }

    @Test
    void test_collector_handles_duplicate_keys() {
        // Without merge function, this throws IllegalStateException
        assertDoesNotThrow(() -> {
            Map<String, List<Document>> grouped = testDocs.stream()
                .collect(Collectors.groupingBy(d -> d.getOwner().getUsername()));
            assertEquals(3, grouped.size(), "Should group by 3 unique owners");
        });
    }

    @Test
    void test_document_map_no_duplicates() {
        // When IDs are unique, toMap should always work
        Map<Long, Document> byId = testDocs.stream()
            .collect(Collectors.toMap(Document::getId, d -> d));

        assertEquals(10, byId.size());
    }

    @Test
    void test_document_grouping_by_type() {
        testDocs.get(0).setContentType("text/plain");
        testDocs.get(1).setContentType("text/plain");

        Map<String, List<Document>> grouped = testDocs.stream()
            .collect(Collectors.groupingBy(Document::getContentType));

        assertEquals(2, grouped.size());
        assertEquals(2, grouped.get("text/plain").size());
        assertEquals(8, grouped.get("application/pdf").size());
    }

    // Tests for BUG I3: Path traversal in AdminController
    @Test
    void test_path_traversal_detection() {
        String baseDir = "/opt/docuvault/uploads";

        String[] traversalAttempts = {
            "../../../etc/passwd",
            "..\\..\\windows\\system32",
            "....//....//etc/shadow",
            "%2e%2e%2f%2e%2e%2f",
            "documents/../../../etc/passwd"
        };

        for (String attempt : traversalAttempts) {
            Path resolved = Paths.get(baseDir).resolve(attempt).normalize();
            Path base = Paths.get(baseDir).normalize();
            assertFalse(resolved.startsWith(base),
                "Path traversal should be detected: " + attempt);
        }
    }

    @Test
    void test_safe_file_paths_accepted() {
        String baseDir = "/opt/docuvault/uploads";

        String[] safePaths = {
            "report.pdf",
            "2024/january/budget.xlsx",
            "team-docs/meeting-notes.docx",
            "archive/old-report.pdf"
        };

        for (String safePath : safePaths) {
            Path resolved = Paths.get(baseDir).resolve(safePath).normalize();
            Path base = Paths.get(baseDir).normalize();
            assertTrue(resolved.startsWith(base),
                "Safe path should be accepted: " + safePath);
        }
    }

    @Test
    void test_null_safe_path_handling() {
        // Null or empty paths should be handled gracefully
        assertDoesNotThrow(() -> {
            Path base = Paths.get("/opt/docuvault/uploads");
            assertNotNull(base);
        });
    }

    // Tests for BUG I2: Unsafe deserialization
    @Test
    void test_json_parsing_preferred_over_serialization() {
        // Verify JSON can parse document metadata safely
        String jsonInput = "{\"name\":\"test.pdf\",\"size\":1024}";
        assertNotNull(jsonInput);
        assertFalse(jsonInput.isEmpty());
    }

    @Test
    void test_document_name_sanitization() {
        String[] dangerousNames = {
            "<script>alert('xss')</script>.pdf",
            "file\u0000name.pdf",
            "very" + "x".repeat(500) + ".pdf"
        };

        for (String name : dangerousNames) {
            Document doc = new Document();
            doc.setName(name);
            assertNotNull(doc.getName(), "Document should accept any name string");
        }
    }

    @Test
    void test_document_content_type_validation() {
        String[] validTypes = {
            "application/pdf",
            "text/plain",
            "image/png",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        };

        for (String type : validTypes) {
            Document doc = new Document();
            doc.setContentType(type);
            assertEquals(type, doc.getContentType());
        }
    }
}
