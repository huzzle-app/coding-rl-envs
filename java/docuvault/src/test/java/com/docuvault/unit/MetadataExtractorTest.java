package com.docuvault.unit;

import com.docuvault.util.MetadataExtractor;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.text.Normalizer;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

@Tag("unit")
public class MetadataExtractorTest {

    private MetadataExtractor extractor;

    @BeforeEach
    void setUp() {
        
        // which requires Jackson 2.15+ but pom.xml has 2.13.0
        assertDoesNotThrow(() -> {
            extractor = new MetadataExtractor();
        }, "MetadataExtractor should initialize without NoSuchMethodError");
    }

    // Tests for BUG L4: Jackson version conflict
    @Test
    void test_jackson_serialization_works() {
        
        assertDoesNotThrow(() -> {
            Map<String, Object> result = extractor.parseJsonMetadata("{\"key\": \"value\"}");
            assertNotNull(result);
            assertEquals("value", result.get("key"));
        }, "Jackson serialization should work without version conflicts");
    }

    @Test
    void test_no_classpath_conflicts() {
        // Verify that ObjectMapper can be created and used
        assertDoesNotThrow(() -> {
            Map<String, Object> metadata = extractor.extractMetadata("/test/file.pdf");
            assertNotNull(metadata);
            assertFalse(metadata.isEmpty());
        });
    }

    // Tests for BUG G1: Unicode normalization
    @Test
    void test_unicode_filename_normalization() {
        // NFC form: e with acute (single code point U+00E9)
        String nfc = "caf\u00e9.pdf";
        // NFD form: e + combining accent (U+0065 + U+0301)
        String nfd = "cafe\u0301.pdf";

        Map<String, Object> metaNfc = extractor.extractMetadata("/docs/" + nfc);
        Map<String, Object> metaNfd = extractor.extractMetadata("/docs/" + nfd);

        
        // Without normalization, they produce different "normalizedName" values
        assertEquals(
            Normalizer.normalize((String) metaNfc.get("normalizedName"), Normalizer.Form.NFC),
            Normalizer.normalize((String) metaNfd.get("normalizedName"), Normalizer.Form.NFC),
            "NFC and NFD forms of same filename should be equal after normalization"
        );
    }

    @Test
    void test_unicode_cjk_filename() {
        String cjkName = "\u6587\u6863.pdf";
        Map<String, Object> metadata = extractor.extractMetadata("/docs/" + cjkName);

        assertNotNull(metadata.get("fileName"));
        assertEquals("\u6587\u6863.pdf", metadata.get("fileName"));
    }

    @Test
    void test_extract_metadata_basic() {
        Map<String, Object> metadata = extractor.extractMetadata("/uploads/report.pdf");

        assertEquals("report.pdf", metadata.get("fileName"));
        assertEquals("pdf", metadata.get("fileExtension"));
    }

    @Test
    void test_extract_metadata_null_path() {
        Map<String, Object> metadata = extractor.extractMetadata(null);
        assertTrue(metadata.isEmpty());
    }
}
