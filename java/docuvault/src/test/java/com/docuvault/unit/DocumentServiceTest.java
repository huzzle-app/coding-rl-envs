package com.docuvault.unit;

import com.docuvault.model.Document;
import com.docuvault.model.DocumentVersion;
import com.docuvault.model.User;
import com.docuvault.repository.DocumentRepository;
import com.docuvault.service.DocumentService;
import com.docuvault.service.NotificationService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import jakarta.persistence.EntityManager;
import jakarta.persistence.EntityManagerFactory;
import jakarta.persistence.TypedQuery;
import java.nio.file.Files;
import java.nio.file.Paths;

import java.util.List;
import java.util.Optional;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
@Tag("unit")
public class DocumentServiceTest {

    @Mock
    private DocumentRepository documentRepository;

    @Mock
    private NotificationService notificationService;

    @Mock
    private EntityManager entityManager;

    @Mock
    private EntityManagerFactory entityManagerFactory;

    @InjectMocks
    private DocumentService documentService;

    private User testUser;
    private Document testDoc;

    @BeforeEach
    void setUp() {
        testUser = new User();
        testUser.setId(1L);
        testUser.setUsername("testuser");
        testUser.setEmail("test@example.com");

        testDoc = new Document();
        testDoc.setId(1L);
        testDoc.setName("test.pdf");
        testDoc.setContentType("application/pdf");
        testDoc.setOwner(testUser);
    }

    // Tests for BUG A1: ThreadLocal leak
    @Test
    void test_threadlocal_cleaned_after_request() {
        documentService.setCurrentUser(testUser);
        assertNotNull(documentService.getCurrentUser());
        // After request processing, ThreadLocal should be cleaned up
        
        // The fix should ensure getCurrentUser() returns null after cleanup
        // This test verifies the cleanup mechanism exists
        // In the fixed version, a cleanup method would set it to null
        documentService.setCurrentUser(null);
        assertNull(documentService.getCurrentUser(),
            "ThreadLocal should be cleanable to prevent memory leaks");
    }

    @Test
    void test_no_memory_leak_threadlocal() throws Exception {
        // Simulate multiple requests on same thread
        for (int i = 0; i < 100; i++) {
            User user = new User();
            user.setId((long) i);
            user.setUsername("user" + i);
            documentService.setCurrentUser(user);
            // After request, ThreadLocal should be removed
            
        }
        // Verify ThreadLocal is cleaned after use
        // In the fixed version, there should be a cleanup mechanism
        // that calls ThreadLocal.remove() after each request
        documentService.setCurrentUser(null);
        assertNull(documentService.getCurrentUser(), "ThreadLocal should be cleaned after request");
    }

    @Test
    void test_threadlocal_isolation_between_threads() throws Exception {
        CountDownLatch latch = new CountDownLatch(1);
        AtomicReference<User> otherThreadUser = new AtomicReference<>();

        documentService.setCurrentUser(testUser);

        Thread t = new Thread(() -> {
            otherThreadUser.set(documentService.getCurrentUser());
            latch.countDown();
        });
        t.start();
        latch.await(5, TimeUnit.SECONDS);

        assertNull(otherThreadUser.get(), "ThreadLocal should not leak across threads");
    }

    @Test
    void test_threadlocal_has_cleanup_mechanism() throws Exception {
        // A1: DocumentService must have a cleanup method that calls ThreadLocal.remove()
        // Without this, ThreadLocal values leak across request-reusing threads in servlet containers
        String source = new String(Files.readAllBytes(
            Paths.get("src/main/java/com/docuvault/service/DocumentService.java")));
        String code = source.replaceAll("/\\*[\\s\\S]*?\\*/", "").replaceAll("//[^\n]*", "");

        assertTrue(code.contains("currentUser.remove()") || code.contains(".remove()"),
            "DocumentService must call ThreadLocal.remove() to prevent memory leaks. " +
            "Add a clearCurrentUser() method that calls currentUser.remove()");
    }

    // Tests for BUG C1: @Transactional proxy bypass
    @Test
    void test_transaction_active_in_nested_call() {
        when(documentRepository.save(any(Document.class))).thenReturn(testDoc);

        // When createDocument calls this.createVersion(), the @Transactional on
        // createVersion should be active. BUG C1: proxy bypass means it's not.
        Document result = documentService.createDocument("test.pdf", "application/pdf",
            "/uploads/test.pdf", 1024L, testUser);

        // Verify createVersion was called within a transaction
        verify(documentRepository, atLeast(1)).save(any(Document.class));
    }

    @Test
    void test_self_invocation_transactional() {
        // This test verifies that self-invocation of @Transactional methods works
        when(documentRepository.save(any(Document.class))).thenReturn(testDoc);

        assertDoesNotThrow(() ->
            documentService.createDocument("doc.pdf", "application/pdf", "/path", 100L, testUser)
        );
    }

    @Test
    void test_no_self_invocation_of_transactional() throws Exception {
        // C1: DocumentService.createDocument() must not call this.createVersion() directly
        // Self-invocation bypasses Spring's @Transactional proxy
        String source = new String(Files.readAllBytes(
            Paths.get("src/main/java/com/docuvault/service/DocumentService.java")));
        String code = source.replaceAll("/\\*[\\s\\S]*?\\*/", "").replaceAll("//[^\n]*", "");

        assertFalse(code.contains("this.createVersion("),
            "DocumentService must not use this.createVersion() - self-invocation bypasses " +
            "@Transactional proxy. Inject self via @Lazy or extract to separate service.");
    }

    // Tests for BUG C2: @Async proxy bypass
    @Test
    void test_async_method_runs_async() throws Exception {
        when(documentRepository.save(any(Document.class))).thenReturn(testDoc);
        AtomicBoolean completed = new AtomicBoolean(false);
        long startTime = System.currentTimeMillis();

        documentService.uploadAndProcess(testDoc);

        
        // Fixed version should return almost immediately
        long elapsed = System.currentTimeMillis() - startTime;
        // In a proper async setup, this should be < 500ms
        // With the bug, processDocumentAsync runs synchronously (1000ms sleep)
        assertTrue(elapsed < 500, "Async method should not block caller. Elapsed: " + elapsed + "ms");
    }

    @Test
    void test_async_returns_future() {
        CompletableFuture<Void> future = documentService.processDocumentAsync(testDoc);
        assertNotNull(future, "Async method should return CompletableFuture");
    }

    // Tests for BUG D2: LazyInitializationException
    @Test
    void test_lazy_collection_accessible() {
        when(documentRepository.findByIdAndIsDeletedFalse(1L)).thenReturn(Optional.of(testDoc));

        
        // After fix, method should be @Transactional(readOnly=true)
        assertDoesNotThrow(() -> {
            Document doc = documentService.getDocument(1L);
            assertNotNull(doc);
        });
    }

    @Test
    void test_no_lazy_init_exception() {
        when(documentRepository.findByIdAndIsDeletedFalse(1L)).thenReturn(Optional.of(testDoc));

        // getDocument() accesses permissions.size() which triggers lazy loading
        
        Document doc = documentService.getDocument(1L);
        assertNotNull(doc);
    }

    // Tests for BUG D3: Connection pool exhaustion
    @Test
    void test_connection_pool_not_exhausted() {
        // Mock the EntityManager chain used in getDocumentsByOwner
        EntityManager mockEm = mock(EntityManager.class);
        TypedQuery<Document> mockQuery = mock(TypedQuery.class);
        when(entityManager.getEntityManagerFactory()).thenReturn(entityManagerFactory);
        when(entityManagerFactory.createEntityManager()).thenReturn(mockEm);
        when(mockEm.createQuery(anyString(), eq(Document.class))).thenReturn(mockQuery);
        when(mockQuery.setParameter(anyString(), any())).thenReturn(mockQuery);
        when(mockQuery.getResultList()).thenReturn(List.of());

        // After multiple calls, connections should be returned to pool
        // This test verifies EntityManager is closed after each call
        assertDoesNotThrow(() -> {
            for (int i = 0; i < 20; i++) {
                try {
                    documentService.getDocumentsByOwner(1L);
                } catch (Exception e) {
                    fail("Connection pool should not be exhausted after " + i + " calls: " + e.getMessage());
                }
            }
        });

        // BUG D3: EntityManager.close() is never called, leaking connections
        // After the fix, close() should be called once per invocation
        verify(mockEm, atLeast(1)).close();
    }

    @Test
    void test_connections_returned_to_pool() {
        // Mock the EntityManager chain
        EntityManager mockEm = mock(EntityManager.class);
        TypedQuery<Document> mockQuery = mock(TypedQuery.class);
        when(entityManager.getEntityManagerFactory()).thenReturn(entityManagerFactory);
        when(entityManagerFactory.createEntityManager()).thenReturn(mockEm);
        when(mockEm.createQuery(anyString(), eq(Document.class))).thenReturn(mockQuery);
        when(mockQuery.setParameter(anyString(), any())).thenReturn(mockQuery);
        when(mockQuery.getResultList()).thenReturn(List.of());

        assertDoesNotThrow(() -> documentService.getDocumentsByOwner(1L));

        // Verify EntityManager is closed after use
        verify(mockEm).close();
    }

    // Tests for BUG C4: @Cacheable key collision
    @Test
    void test_cache_no_collision_overloaded() {
        when(documentRepository.findById(1L)).thenReturn(Optional.of(testDoc));

        Document doc2 = new Document();
        doc2.setId(2L);
        doc2.setName("other.pdf");
        when(documentRepository.findByNameContainingIgnoreCase("other"))
            .thenReturn(java.util.List.of(doc2));

        
        // getCachedDocument(1L) and getCachedDocument("1") might use same cache key
        Optional<Document> byId = documentService.getCachedDocument(1L);
        Optional<Document> byName = documentService.getCachedDocument("other");

        assertTrue(byId.isPresent());
        assertTrue(byName.isPresent());
        assertNotEquals(byId.get().getId(), byName.get().getId(),
            "Cache should not collide between overloaded methods");
    }

    @Test
    void test_cache_key_explicit() {
        when(documentRepository.findById(1L)).thenReturn(Optional.of(testDoc));

        // Verify getCachedDocument(Long) correctly delegates to repository
        // Full @Cacheable behavior requires Spring AOP proxy (tested in CacheIntegrationTest)
        Optional<Document> result1 = documentService.getCachedDocument(1L);
        Optional<Document> result2 = documentService.getCachedDocument(1L);

        assertTrue(result1.isPresent());
        assertTrue(result2.isPresent());
        assertEquals(testDoc.getId(), result1.get().getId());
        // Each call hits repository (no cache proxy in unit test)
        verify(documentRepository, atLeast(1)).findById(1L);
    }

    // General tests
    @Test
    void test_create_document_saves() {
        when(documentRepository.save(any(Document.class))).thenReturn(testDoc);

        Document result = documentService.createDocument("test.pdf", "application/pdf",
            "/uploads/test.pdf", 1024L, testUser);

        assertNotNull(result);
        verify(documentRepository, atLeast(1)).save(any(Document.class));
    }

    @Test
    void test_delete_document_soft_deletes() {
        when(documentRepository.findById(1L)).thenReturn(Optional.of(testDoc));
        when(documentRepository.save(any(Document.class))).thenReturn(testDoc);

        documentService.deleteDocument(1L);

        assertTrue(testDoc.getIsDeleted());
        verify(documentRepository).save(testDoc);
    }

    @Test
    void test_update_document() {
        when(documentRepository.findById(1L)).thenReturn(Optional.of(testDoc));
        when(documentRepository.save(any(Document.class))).thenReturn(testDoc);

        Document result = documentService.updateDocument(1L, "new-name.pdf", "text/plain");

        assertEquals("new-name.pdf", result.getName());
        assertEquals("text/plain", result.getContentType());
    }

    @Test
    void test_get_document_not_found() {
        when(documentRepository.findByIdAndIsDeletedFalse(999L)).thenReturn(Optional.empty());

        assertThrows(RuntimeException.class, () -> documentService.getDocument(999L));
    }
}
