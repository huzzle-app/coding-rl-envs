package com.docuvault.service;

import com.docuvault.model.Document;
import com.docuvault.repository.DocumentRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.*;
import java.util.stream.Collectors;

@Service
public class SearchService {

    private static final Logger log = LoggerFactory.getLogger(SearchService.class);

    @Autowired
    private DocumentRepository documentRepository;

    
    // Category: Business Logic
    // List.subList() returns a VIEW backed by the original list, not an independent
    // copy. The returned sub-list holds a strong reference to the entire original
    // list, preventing it from being garbage collected. If the original list is
    // large (e.g., 100,000 documents) and only 10 are needed, the full list stays
    // in memory as long as the sub-list reference exists.
    // Fix: Wrap in new ArrayList<>(): new ArrayList<>(list.subList(0, Math.min(limit, list.size())))
    public List<Document> searchDocuments(String query, int limit) {
        List<Document> allResults = documentRepository.findByNameContainingIgnoreCase(query);
        log.info("Found {} results for query: {}", allResults.size(), query);

        if (allResults.size() > limit) {
            
            // The caller holds a reference to a 10-element view that prevents
            // the full 100,000-element list from being garbage collected
            return allResults.subList(0, limit);
        }
        return allResults;
    }

    
    // Category: Generics & Type Safety
    // A raw-type List is assigned to List<Document> without type checking.
    // Due to Java's type erasure, the assignment compiles (with warning) and
    // no ClassCastException occurs at assignment time. The exception is deferred
    // until element access: when the caller iterates and calls Document methods
    // on the non-Document objects (HashMap entries), a ClassCastException is thrown.
    // Fix: Use proper generic types throughout; validate element types before
    // adding to the list, or use a typed intermediate collection
    @SuppressWarnings("unchecked")
    public List<Document> searchWithMetadata(String query, Map<String, Object> metadata) {
        // Simulated search that returns raw type list
        List rawResults = performRawSearch(query, metadata);

        
        // The generic type Document is erased at runtime, so this is just List = List
        List<Document> typedResults = rawResults;

        // ClassCastException occurs later when iterating and accessing Document methods
        // if rawResults contains non-Document objects (e.g., HashMap entries)
        return typedResults;
    }

    @SuppressWarnings("rawtypes")
    private List performRawSearch(String query, Map<String, Object> metadata) {
        List results = new ArrayList();
        // Mix in both Document objects and raw Maps (simulating a deserialization issue
        // where some results come from cache as Maps instead of hydrated entities)
        List<Document> docs = documentRepository.findByNameContainingIgnoreCase(query);
        results.addAll(docs);

        
        // This HashMap is NOT a Document, but it gets added to the same list
        // that will be returned as List<Document>, causing ClassCastException
        // when the caller tries to call getName() or getId() on it
        if (metadata != null && !metadata.isEmpty()) {
            Map<String, Object> metaResult = new HashMap<>();
            metaResult.put("query", query);
            metaResult.put("metadata", metadata);
            results.add(metaResult); // This is NOT a Document
        }
        return results;
    }

    public Map<String, List<Document>> groupByContentType(List<Document> documents) {
        return documents.stream()
            .filter(d -> d.getContentType() != null)
            .collect(Collectors.groupingBy(Document::getContentType));
    }

    public List<Document> recentDocuments(int limit) {
        List<Document> all = documentRepository.findAll();
        all.sort(Comparator.comparing(Document::getCreatedAt).reversed());

        if (all.size() > limit) {
            
            return all.subList(0, limit);
        }
        return all;
    }
}
