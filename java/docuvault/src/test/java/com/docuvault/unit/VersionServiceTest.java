package com.docuvault.unit;

import com.docuvault.model.Document;
import com.docuvault.model.DocumentVersion;
import com.docuvault.model.User;
import com.docuvault.repository.DocumentRepository;
import com.docuvault.service.VersionService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
@Tag("unit")
public class VersionServiceTest {

    @Mock
    private DocumentRepository documentRepository;

    @InjectMocks
    private VersionService versionService;

    private Document testDoc;
    private User testUser;

    @BeforeEach
    void setUp() {
        testDoc = new Document();
        testDoc.setId(1L);
        testDoc.setName("test.pdf");
        testDoc.setVersionNumber(1);
        testDoc.setVersions(new ArrayList<>());

        testUser = new User();
        testUser.setId(1L);
        testUser.setUsername("testuser");
    }

    // Tests for BUG A2: Double-checked locking without volatile
    @Test
    void test_singleton_thread_safe() throws Exception {
        int threadCount = 50;
        ExecutorService executor = Executors.newFixedThreadPool(threadCount);
        CountDownLatch latch = new CountDownLatch(threadCount);
        Set<VersionService> instances = ConcurrentHashMap.newKeySet();

        for (int i = 0; i < threadCount; i++) {
            executor.submit(() -> {
                try {
                    VersionService instance = VersionService.getInstance(documentRepository);
                    instances.add(instance);
                } finally {
                    latch.countDown();
                }
            });
        }

        latch.await(10, TimeUnit.SECONDS);
        executor.shutdown();

        
        // or partially constructed instances
        assertEquals(1, instances.size(),
            "Double-checked locking should produce exactly one instance");
    }

    @Test
    void test_no_partial_construction() throws Exception {
        int threadCount = 20;
        ExecutorService executor = Executors.newFixedThreadPool(threadCount);
        CountDownLatch latch = new CountDownLatch(threadCount);
        AtomicInteger nullInstances = new AtomicInteger(0);

        for (int i = 0; i < threadCount; i++) {
            executor.submit(() -> {
                try {
                    VersionService instance = VersionService.getInstance(documentRepository);
                    if (instance == null) {
                        nullInstances.incrementAndGet();
                    }
                } finally {
                    latch.countDown();
                }
            });
        }

        latch.await(10, TimeUnit.SECONDS);
        executor.shutdown();

        assertEquals(0, nullInstances.get(),
            "No thread should see a null or partially constructed instance");
    }

    // Tests for BUG B1: Mutable HashMap key
    @Test
    void test_version_lookup_after_update() {
        Document doc = new Document();
        doc.setId(1L);
        doc.setName("original.pdf");

        List<DocumentVersion> versions = new ArrayList<>();
        DocumentVersion v1 = new DocumentVersion();
        v1.setVersionNumber(1);
        versions.add(v1);
        doc.setVersions(versions);

        // Cache the versions
        List<DocumentVersion> cached = versionService.getVersionsForDocument(doc);
        assertEquals(1, cached.size());

        
        // and the cached entry becomes unretrievable
        doc.setName("renamed.pdf");

        // Should still find the cached versions
        List<DocumentVersion> afterRename = versionService.getVersionsForDocument(doc);
        assertEquals(1, afterRename.size(),
            "Version lookup should work after document name change");
    }

    @Test
    void test_hashmap_key_immutable() {
        Document doc1 = new Document();
        doc1.setId(1L);
        doc1.setName("doc1.pdf");
        doc1.setVersions(new ArrayList<>());

        Document doc2 = new Document();
        doc2.setId(2L);
        doc2.setName("doc2.pdf");
        doc2.setVersions(new ArrayList<>());

        // Cache both
        versionService.getVersionsForDocument(doc1);
        versionService.getVersionsForDocument(doc2);

        // Change doc1's name to match doc2's name
        doc1.setName("doc2.pdf");

        
        // The cache should use document ID (immutable) not name (mutable)
        Map<Document, List<DocumentVersion>> allCached = versionService.getAllCachedVersions();
        assertEquals(2, allCached.size(),
            "Cache should have 2 separate entries even after name change");
    }

    @Test
    void test_invalidate_cache_after_mutation() {
        Document doc = new Document();
        doc.setId(1L);
        doc.setName("test.pdf");
        doc.setVersions(new ArrayList<>());

        versionService.getVersionsForDocument(doc);

        // Mutate name
        doc.setName("changed.pdf");

        
        versionService.invalidateCache(doc);

        // The old entry should be removed
        Map<Document, List<DocumentVersion>> cached = versionService.getAllCachedVersions();
        assertTrue(cached.isEmpty(),
            "Cache should be empty after invalidation");
    }

    @Test
    void test_create_version_increments_number() {
        when(documentRepository.save(any(Document.class))).thenReturn(testDoc);

        DocumentVersion version = versionService.createVersion(testDoc, "/path/v2.pdf",
            2048L, "abc123", "Updated content", testUser);

        assertEquals(2, version.getVersionNumber());
        assertEquals(2, testDoc.getVersionNumber());
    }

    @Test
    void test_create_version_adds_to_document() {
        when(documentRepository.save(any(Document.class))).thenReturn(testDoc);

        versionService.createVersion(testDoc, "/path/v2.pdf", 2048L, "abc123",
            "Update", testUser);

        assertEquals(1, testDoc.getVersions().size());
    }

    @Test
    void test_version_cache_populated() {
        testDoc.setVersions(List.of());

        List<DocumentVersion> result = versionService.getVersionsForDocument(testDoc);
        assertNotNull(result);

        // Second call should use cache
        List<DocumentVersion> cached = versionService.getVersionsForDocument(testDoc);
        assertSame(result, cached, "Second call should return cached value");
    }

    @Test
    void test_concurrent_version_creation() throws Exception {
        when(documentRepository.save(any(Document.class))).thenReturn(testDoc);

        int threadCount = 10;
        ExecutorService executor = Executors.newFixedThreadPool(threadCount);
        CountDownLatch latch = new CountDownLatch(threadCount);
        List<Exception> errors = Collections.synchronizedList(new ArrayList<>());

        for (int i = 0; i < threadCount; i++) {
            final int idx = i;
            executor.submit(() -> {
                try {
                    versionService.createVersion(testDoc, "/path/v" + idx + ".pdf",
                        1024L, "hash" + idx, "version " + idx, testUser);
                } catch (Exception e) {
                    errors.add(e);
                } finally {
                    latch.countDown();
                }
            });
        }

        latch.await(10, TimeUnit.SECONDS);
        executor.shutdown();

        assertTrue(errors.isEmpty(),
            "Concurrent version creation should not throw: " + errors);
    }
}
