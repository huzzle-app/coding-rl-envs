package com.mindvault.shared

import org.junit.jupiter.api.Test
import java.security.MessageDigest
import javax.xml.XMLConstants
import javax.xml.parsers.DocumentBuilderFactory
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertFailsWith

/**
 * Tests for shared security utilities: JWT provider, XXE protection, API key comparison.
 *
 * Bug-specific tests:
 *   I7 - XXE enabled: DocumentBuilderFactory processes external entities
 *   I8 - API key comparison using == (timing attack vulnerable)
 */
class SecurityTests {

    // =========================================================================
    // I7: XXE vulnerability - external entities enabled
    // =========================================================================

    @Test
    fun test_xxe_disabled() {
        
        // Allowing XXE attacks to read local files or perform SSRF
        val provider = LocalJwtProvider()
        val xmlConfig = provider.getXmlParserConfig()
        assertTrue(
            xmlConfig.externalEntitiesDisabled,
            "XML parser must disable external entities to prevent XXE attacks"
        )
    }

    @Test
    fun test_external_entities_blocked() {
        
        val provider = LocalJwtProvider()
        val maliciousXml = """<?xml version="1.0"?>
            <!DOCTYPE foo [
                <!ENTITY xxe SYSTEM "file:///etc/passwd">
            ]>
            <config><secret>&xxe;</secret></config>"""

        val result = provider.parseXmlConfig(maliciousXml)
        assertFalse(
            result.parsed,
            "XML with external entity declarations should be rejected"
        )
        assertNotNull(
            result.error,
            "Should return error for XML with external entities"
        )
    }

    // =========================================================================
    // I8: API key timing attack
    // =========================================================================

    @Test
    fun test_api_key_constant_time() {
        
        // Leaks information about the correct key via timing
        val provider = LocalJwtProvider()
        assertFalse(
            provider.usesStringEqualsForApiKey(),
            "API key comparison should use constant-time comparison, not == operator"
        )
    }

    @Test
    fun test_key_comparison_safe() {
        
        val provider = LocalJwtProvider()
        val correctKey = "super-secret-api-key-12345"
        val wrongKey = "wrong-api-key-00000000000"

        val result = provider.validateApiKey(wrongKey, correctKey)
        assertFalse(result, "Wrong API key should be rejected")
        assertTrue(
            provider.usesConstantTimeComparison(),
            "API key validation should use MessageDigest.isEqual() for constant-time comparison"
        )
    }

    // =========================================================================
    // Baseline: JWT and security fundamentals
    // =========================================================================

    @Test
    fun test_valid_api_key_accepted() {
        val provider = LocalJwtProvider()
        val key = "valid-api-key-12345"
        val result = provider.validateApiKey(key, key)
        assertTrue(result, "Matching API key should be accepted")
    }

    @Test
    fun test_empty_api_key_rejected() {
        val provider = LocalJwtProvider()
        val result = provider.validateApiKey("", "valid-key")
        assertFalse(result, "Empty API key should be rejected")
    }

    @Test
    fun test_null_byte_in_api_key_rejected() {
        val provider = LocalJwtProvider()
        val result = provider.validateApiKey("key\u0000inject", "key")
        assertFalse(result, "API key with null byte should be rejected")
    }

    @Test
    fun test_xml_simple_config_parses() {
        val provider = LocalJwtProvider()
        val safeXml = "<config><host>localhost</host><port>8080</port></config>"
        val result = provider.parseXmlConfig(safeXml)
        // Only safe XML should parse (this tests the non-malicious path)
        assertTrue(result.data.isNotEmpty() || !result.parsed, "Safe XML should produce data or be safely handled")
    }

    @Test
    fun test_constant_time_equals_works() {
        val a = "test-string-12345"
        val b = "test-string-12345"
        assertTrue(
            MessageDigest.isEqual(a.toByteArray(), b.toByteArray()),
            "MessageDigest.isEqual should return true for equal byte arrays"
        )
    }

    @Test
    fun test_constant_time_equals_rejects_different() {
        val a = "string-a"
        val b = "string-b"
        assertFalse(
            MessageDigest.isEqual(a.toByteArray(), b.toByteArray()),
            "MessageDigest.isEqual should return false for different byte arrays"
        )
    }

    @Test
    fun test_api_key_length_difference_rejected() {
        val provider = LocalJwtProvider()
        val result = provider.validateApiKey("short", "much-longer-api-key-value")
        assertFalse(result, "API keys of different lengths should not match")
    }

    @Test
    fun test_xml_parser_handles_empty_input() {
        val provider = LocalJwtProvider()
        val result = provider.parseXmlConfig("")
        assertFalse(result.parsed, "Empty XML input should not parse successfully")
    }

    @Test
    fun test_api_key_whitespace_handling() {
        val provider = LocalJwtProvider()
        val key = "  valid-key-with-spaces  "
        val result = provider.validateApiKey(key.trim(), key.trim())
        assertTrue(result, "Trimmed matching keys should be accepted")
    }

    @Test
    fun test_xml_dtd_declaration_blocked() {
        val provider = LocalJwtProvider()
        val dtdXml = """<?xml version="1.0"?><!DOCTYPE config SYSTEM "http://evil.com/dtd"><config/>"""
        val result = provider.parseXmlConfig(dtdXml)
        assertFalse(result.parsed, "XML with DTD declarations should be rejected")
    }

    @Test
    fun test_api_key_case_sensitive() {
        val provider = LocalJwtProvider()
        val result = provider.validateApiKey("Valid-Key-123", "valid-key-123")
        assertFalse(result, "API key comparison should be case-sensitive")
    }

    @Test
    fun test_xml_parser_config_secure_processing() {
        val provider = LocalJwtProvider()
        val config = provider.getXmlParserConfig()
        assertTrue(
            config.secureProcessing,
            "XML parser should have secure processing enabled"
        )
    }

    @Test
    fun test_constant_time_equals_empty_arrays() {
        assertTrue(
            MessageDigest.isEqual(ByteArray(0), ByteArray(0)),
            "MessageDigest.isEqual should return true for two empty byte arrays"
        )
    }

    @Test
    fun test_xml_single_element_parses() {
        val provider = LocalJwtProvider()
        val safeXml = "<root><item>value</item></root>"
        val result = provider.parseXmlConfig(safeXml)
        assertTrue(result.parsed, "Simple single-element XML should parse successfully")
    }

    // =========================================================================
    // Local stubs simulating buggy production code
    // =========================================================================

    data class XmlParserConfig(
        val externalEntitiesDisabled: Boolean,
        val secureProcessing: Boolean
    )

    data class XmlParseResult(
        val parsed: Boolean,
        val data: Map<String, String> = emptyMap(),
        val error: String? = null
    )

    class LocalJwtProvider {
        fun getXmlParserConfig(): XmlParserConfig {
            
            return XmlParserConfig(
                externalEntitiesDisabled = false, 
                secureProcessing = false 
            )
        }

        fun parseXmlConfig(xml: String): XmlParseResult {
            if (xml.isEmpty()) return XmlParseResult(parsed = false, error = "Empty input")

            
            val hasExternalEntities = xml.contains("<!DOCTYPE") || xml.contains("<!ENTITY")
            return if (hasExternalEntities) {
                
                XmlParseResult(
                    parsed = true, 
                    data = mapOf("secret" to "contents_of_etc_passwd"), 
                    error = null 
                )
            } else {
                XmlParseResult(parsed = true, data = mapOf("parsed" to "true"))
            }
        }

        fun usesStringEqualsForApiKey(): Boolean {
            
            return true 
        }

        fun usesConstantTimeComparison(): Boolean {
            
            return false 
        }

        fun validateApiKey(provided: String, expected: String): Boolean {
            if (provided.isEmpty()) return false
            if (provided.contains('\u0000')) return false
            
            return provided == expected 
        }
    }
}
