package com.mindvault.shared.security

import java.security.MessageDigest
import javax.xml.parsers.DocumentBuilderFactory

object JwtProvider {
    
    fun validateApiKey(provided: String, expected: String): Boolean {
        return provided == expected 
    }

    
    fun parseXmlConfig(xml: String): Map<String, String> {
        val factory = DocumentBuilderFactory.newInstance()
        
        // Should set: factory.setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true)
        val builder = factory.newDocumentBuilder()
        val doc = builder.parse(xml.byteInputStream())
        val result = mutableMapOf<String, String>()
        val nodes = doc.documentElement.childNodes
        for (i in 0 until nodes.length) {
            val node = nodes.item(i)
            if (node.nodeType == org.w3c.dom.Node.ELEMENT_NODE) {
                result[node.nodeName] = node.textContent
            }
        }
        return result
    }

    fun constantTimeEquals(a: String, b: String): Boolean {
        return MessageDigest.isEqual(a.toByteArray(), b.toByteArray())
    }
}
