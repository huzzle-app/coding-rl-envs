package com.docuvault.controller;

import com.docuvault.model.Document;
import com.docuvault.service.DocumentService;
import com.docuvault.service.SearchService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.io.*;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/documents")
public class DocumentController {

    private static final Logger log = LoggerFactory.getLogger(DocumentController.class);

    @Autowired
    private DocumentService documentService;

    @Autowired
    private SearchService searchService;

    @GetMapping
    public ResponseEntity<List<Map<String, Object>>> listDocuments(@RequestParam(required = false) Long ownerId) {
        List<Document> documents;
        if (ownerId != null) {
            documents = documentService.getDocumentsByOwner(ownerId);
        } else {
            documents = searchService.searchDocuments("", 100);
        }

        
        // Category: Business Logic
        // Collectors.toMap() throws IllegalStateException when two elements map to
        // the same key. If multiple documents share the same name (which is allowed
        // by the schema - name is not unique), this call throws:
        // "java.lang.IllegalStateException: Duplicate key <name>"
        // The error occurs at stream terminal operation time and returns 500 to client.
        // Fix: Provide a merge function as third argument:
        // Collectors.toMap(Document::getName, doc -> doc, (existing, replacement) -> existing)
        Map<String, Document> docByName = documents.stream()
            .collect(Collectors.toMap(
                Document::getName,
                doc -> doc
                
                // Multiple documents with the same name will cause IllegalStateException
            ));

        List<Map<String, Object>> result = docByName.values().stream()
            .map(this::toDocumentMap)
            .collect(Collectors.toList());

        return ResponseEntity.ok(result);
    }

    @GetMapping("/{id}")
    public ResponseEntity<Map<String, Object>> getDocument(@PathVariable Long id) {
        Document doc = documentService.getDocument(id);
        return ResponseEntity.ok(toDocumentMap(doc));
    }

    
    // Category: Security
    // Java's ObjectInputStream deserializes arbitrary objects from the byte stream,
    // including their class definitions and constructor logic. An attacker can craft
    // a malicious serialized object (e.g., using ysoserial gadget chains with
    // Commons Collections, Spring, or other libraries on the classpath) that
    // executes arbitrary code during deserialization - before any type check occurs.
    // Fix: Use JSON deserialization (Jackson ObjectMapper) instead of Java
    // serialization, or implement ObjectInputFilter to whitelist allowed classes:
    // ois.setObjectInputFilter(ObjectInputFilter.Config.createFilter("com.docuvault.**"))
    @PostMapping("/{id}/metadata")
    public ResponseEntity<Map<String, Object>> uploadMetadata(
            @PathVariable Long id, @RequestBody byte[] data) {
        try {
            
            // An attacker can craft a serialized Java object payload that executes
            // arbitrary system commands (e.g., Runtime.exec()) during deserialization
            ObjectInputStream ois = new ObjectInputStream(new ByteArrayInputStream(data));
            @SuppressWarnings("unchecked")
            Map<String, Object> metadata = (Map<String, Object>) ois.readObject();
            ois.close();

            log.info("Received metadata for document {}: {}", id, metadata);
            return ResponseEntity.ok(metadata);
        } catch (Exception e) {
            return ResponseEntity.badRequest().build();
        }
    }

    @PostMapping
    public ResponseEntity<Map<String, Object>> createDocument(
            @RequestParam String name,
            @RequestParam(required = false) String contentType,
            @RequestParam(required = false) MultipartFile file) {
        // Simplified - would normally handle file upload to storage
        Document doc = documentService.createDocument(name, contentType, "/uploads/" + name, 0L, null);
        return ResponseEntity.ok(toDocumentMap(doc));
    }

    @PutMapping("/{id}")
    public ResponseEntity<Map<String, Object>> updateDocument(
            @PathVariable Long id,
            @RequestParam String name,
            @RequestParam(required = false) String contentType) {
        Document doc = documentService.updateDocument(id, name, contentType);
        return ResponseEntity.ok(toDocumentMap(doc));
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deleteDocument(@PathVariable Long id) {
        documentService.deleteDocument(id);
        return ResponseEntity.noContent().build();
    }

    @GetMapping("/search")
    public ResponseEntity<List<Map<String, Object>>> searchDocuments(
            @RequestParam String q, @RequestParam(defaultValue = "10") int limit) {
        List<Document> results = searchService.searchDocuments(q, limit);
        List<Map<String, Object>> response = results.stream()
            .map(this::toDocumentMap)
            .collect(Collectors.toList());
        return ResponseEntity.ok(response);
    }

    private Map<String, Object> toDocumentMap(Document doc) {
        return Map.of(
            "id", doc.getId() != null ? doc.getId() : 0,
            "name", doc.getName() != null ? doc.getName() : "",
            "contentType", doc.getContentType() != null ? doc.getContentType() : "",
            "fileSize", doc.getFileSize() != null ? doc.getFileSize() : 0,
            "versionNumber", doc.getVersionNumber() != null ? doc.getVersionNumber() : 1
        );
    }
}
