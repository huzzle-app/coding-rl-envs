package com.docuvault.unit;

import com.docuvault.model.Document;
import com.docuvault.repository.DocumentRepository;
import com.docuvault.service.SearchService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.*;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
@Tag("unit")
public class SearchServiceTest {

    @Mock
    private DocumentRepository documentRepository;

    @InjectMocks
    private SearchService searchService;

    private List<Document> sampleDocs;

    @BeforeEach
    void setUp() {
        sampleDocs = new ArrayList<>();
        for (int i = 0; i < 100; i++) {
            Document doc = new Document();
            doc.setId((long) i);
            doc.setName("document-" + i + ".pdf");
            doc.setContentType("application/pdf");
            // Set createdAt to avoid NPE in sort comparisons
            try {
                java.lang.reflect.Field f = Document.class.getDeclaredField("createdAt");
                f.setAccessible(true);
                f.set(doc, java.time.LocalDateTime.now().minusDays(100 - i));
            } catch (Exception e) {
                // fall through - @PrePersist won't fire outside JPA
            }
            sampleDocs.add(doc);
        }
    }

    // Tests for BUG B2: ArrayList subList memory leak
    @Test
    void test_search_results_no_memory_leak() {
        when(documentRepository.findByNameContainingIgnoreCase(anyString())).thenReturn(sampleDocs);

        List<Document> results = searchService.searchDocuments("document", 10);

        assertEquals(10, results.size());

        
        // The result should be an independent copy, not a view
        // Check by verifying it's a separate list instance
        assertNotSame(sampleDocs, results,
            "Search results should be independent copy, not view of original list");

        // Try to modify the result - should not affect original
        // An independent copy allows this; a subList view backed by original would too
        // but the issue is memory: the subList retains the entire backing array
        assertDoesNotThrow(() -> results.add(new Document()),
            "Result list should be modifiable (independent copy, not a subList view)");
    }

    @Test
    void test_sublist_independent_copy() {
        when(documentRepository.findByNameContainingIgnoreCase(anyString())).thenReturn(sampleDocs);

        List<Document> results = searchService.searchDocuments("document", 5);

        
        // entire backing array. An independent copy should only have 5 elements.
        assertEquals(5, results.size());

        // Verify the result is truly independent by checking class
        // ArrayList.subList returns a SubList, not ArrayList
        assertTrue(results instanceof ArrayList || results.getClass().getSimpleName().equals("ArrayList"),
            "Result should be an ArrayList, not a SubList view");
    }

    @Test
    void test_search_with_small_result_set() {
        List<Document> smallList = new ArrayList<>(sampleDocs.subList(0, 3));
        when(documentRepository.findByNameContainingIgnoreCase(anyString()))
            .thenReturn(smallList);

        List<Document> results = searchService.searchDocuments("doc", 10);
        assertEquals(3, results.size(), "Should return all results when fewer than limit");
    }

    @Test
    void test_recent_documents_no_memory_leak() {
        when(documentRepository.findAll()).thenReturn(sampleDocs);

        List<Document> results = searchService.recentDocuments(5);
        assertEquals(5, results.size());

        // Same B2 bug applies here
        assertDoesNotThrow(() -> results.add(new Document()),
            "Recent documents should be independent copy");
    }

    // Tests for BUG E1: Type erasure ClassCastException
    @Test
    void test_generic_type_safety() {
        when(documentRepository.findByNameContainingIgnoreCase(anyString()))
            .thenReturn(new ArrayList<>(sampleDocs.subList(0, 3)));

        Map<String, Object> metadata = Map.of("key", "value");

        
        // Accessing elements as Document throws ClassCastException
        assertDoesNotThrow(() -> {
            List<Document> results = searchService.searchWithMetadata("doc", metadata);
            // Iterating and accessing Document methods should not throw
            for (Document doc : results) {
                assertNotNull(doc.getName(), "Should be able to access Document methods");
            }
        }, "Type-safe search should not throw ClassCastException");
    }

    @Test
    void test_no_class_cast_exception() {
        when(documentRepository.findByNameContainingIgnoreCase(anyString()))
            .thenReturn(List.of(sampleDocs.get(0)));

        Map<String, Object> metadata = Map.of("tag", "important");

        
        List<Document> results = searchService.searchWithMetadata("doc", metadata);

        // Should be safe to iterate without ClassCastException
        assertDoesNotThrow(() -> {
            for (Document doc : results) {
                String name = doc.getName(); // This line throws CCE with bug present
            }
        }, "Iterating typed results should not throw ClassCastException");
    }

    @Test
    void test_search_with_null_metadata() {
        when(documentRepository.findByNameContainingIgnoreCase(anyString()))
            .thenReturn(new ArrayList<>(sampleDocs.subList(0, 5)));

        // With null metadata, no non-Document objects should be added
        List<Document> results = searchService.searchWithMetadata("doc", null);
        assertEquals(5, results.size());

        assertDoesNotThrow(() -> {
            for (Document doc : results) {
                assertNotNull(doc.getName());
            }
        });
    }

    @Test
    void test_group_by_content_type() {
        Map<String, List<Document>> grouped = searchService.groupByContentType(sampleDocs);
        assertTrue(grouped.containsKey("application/pdf"));
        assertEquals(100, grouped.get("application/pdf").size());
    }

    @Test
    void test_search_empty_query() {
        when(documentRepository.findByNameContainingIgnoreCase("")).thenReturn(sampleDocs);

        List<Document> results = searchService.searchDocuments("", 10);
        assertEquals(10, results.size());
    }

    @Test
    void test_search_with_empty_metadata() {
        when(documentRepository.findByNameContainingIgnoreCase(anyString()))
            .thenReturn(new ArrayList<>(sampleDocs.subList(0, 3)));

        // Empty metadata map - should not add non-Document objects
        List<Document> results = searchService.searchWithMetadata("doc", Map.of());
        assertEquals(3, results.size());
    }
}
