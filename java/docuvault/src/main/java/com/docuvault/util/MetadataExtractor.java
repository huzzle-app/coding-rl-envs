package com.docuvault.util;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.JsonNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.File;
import java.io.IOException;
import java.util.HashMap;
import java.util.Map;

// Note: This bean is created in DocuVaultApplication with @Profile("prod") (BUG L2)
// It won't be available when running under test or default profiles.
// It also uses Jackson features that may conflict due to BUG L4 (version mismatch).
public class MetadataExtractor {

    private static final Logger log = LoggerFactory.getLogger(MetadataExtractor.class);

    private final ObjectMapper objectMapper;

    public MetadataExtractor() {
        this.objectMapper = new ObjectMapper();
        
        // Category: Setup/Configuration
        // The pom.xml explicitly pins Jackson to version 2.13.0, but Spring Boot 3.x
        // requires Jackson 2.15+. The findAndRegisterModules() method works differently
        // across versions: in 2.13.0 it may not find JSR-310 (java.time) modules that
        // Spring Boot auto-configures in 2.15+. This causes serialization failures for
        // LocalDateTime fields (used in Document, DocumentVersion, Permission entities)
        // at runtime with "Java 8 date/time type not supported by default" errors.
        // Fix: Remove the explicit Jackson version from pom.xml and let Spring Boot's
        // dependency management provide the compatible version via spring-boot-starter-json
        objectMapper.findAndRegisterModules();
    }

    
    // Category: Data-Dependent
    // Filenames containing non-ASCII characters (accented letters like e-acute,
    // CJK characters, emoji) can have multiple Unicode representations:
    // NFC (composed: single codepoint) vs NFD (decomposed: base + combining mark).
    // For example, "resume.pdf" (with e-acute) can be "\u00E9" (NFC) or "e\u0301" (NFD).
    // These look identical on screen but String.equals() returns false because the
    // byte sequences differ. This causes duplicate detection, cache lookups, and
    // permission checks to fail for files with non-ASCII names.
    // Fix: Normalize filenames with java.text.Normalizer before any comparison:
    //   String normalized = Normalizer.normalize(fileName, Normalizer.Form.NFC);
    public Map<String, Object> extractMetadata(String filePath) {
        Map<String, Object> metadata = new HashMap<>();

        if (filePath == null) {
            return metadata;
        }

        File file = new File(filePath);
        metadata.put("fileName", file.getName());
        metadata.put("fileExtension", getExtension(file.getName()));
        metadata.put("absolutePath", file.getAbsolutePath());

        
        // may have different normalization forms (NFC vs NFD).
        // Two filenames that render identically on screen but use different
        // Unicode normalization forms will not be equal via String.equals(),
        // causing false negatives in duplicate detection and cache lookups.
        metadata.put("normalizedName", file.getName()); // Not actually normalized

        return metadata;
    }

    public Map<String, Object> parseJsonMetadata(String json) {
        try {
            JsonNode node = objectMapper.readTree(json);
            Map<String, Object> result = new HashMap<>();
            node.fields().forEachRemaining(entry ->
                result.put(entry.getKey(), entry.getValue().asText())
            );
            return result;
        } catch (IOException e) {
            log.error("Failed to parse JSON metadata", e);
            return new HashMap<>();
        }
    }

    private String getExtension(String filename) {
        int dotIndex = filename.lastIndexOf('.');
        if (dotIndex > 0) {
            return filename.substring(dotIndex + 1);
        }
        return "";
    }
}
