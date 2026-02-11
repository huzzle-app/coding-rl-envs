package com.docuvault.service;

import com.docuvault.model.Document;
import com.docuvault.model.DocumentVersion;
import com.docuvault.model.User;
import com.docuvault.repository.DocumentRepository;
import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.CompletableFuture;

@Service
public class DocumentService {

    private static final Logger log = LoggerFactory.getLogger(DocumentService.class);

    
    // Category: Concurrency
    // In a servlet container's thread pool, threads are reused across requests.
    // The ThreadLocal value persists after the request completes, causing:
    // 1. Memory leak - User objects accumulate and are never GC'd
    // 2. Data leak - subsequent requests on the same thread see stale user data
    // Fix: Add finally { currentUser.remove(); } in a servlet filter or
    // interceptor, or use a request-scoped bean instead of ThreadLocal
    private static final ThreadLocal<User> currentUser = new ThreadLocal<>();

    @Autowired
    private DocumentRepository documentRepository;

    @Autowired
    private NotificationService notificationService;

    @PersistenceContext
    private EntityManager entityManager;

    public void setCurrentUser(User user) {
        
        // The value persists on the pooled thread, leaking memory and user context
        //
        
        //   1. DocumentService.java - add clearCurrentUser() method
        //   2. A servlet filter or Spring interceptor - call clearCurrentUser() in finally block
        // Fixing only this class (adding clearCurrentUser()) is insufficient; without
        // a filter/interceptor to call it after every request, the ThreadLocal still leaks.
        // Example filter needed in a new file (e.g., UserContextFilter.java):
        //   @Override public void doFilter(...) {
        //       try { chain.doFilter(req, resp); }
        //       finally { documentService.clearCurrentUser(); }
        //   }
        currentUser.set(user);
    }

    public User getCurrentUser() {
        return currentUser.get();
    }

    @Transactional
    public Document createDocument(String name, String contentType, String filePath, Long fileSize, User owner) {
        Document doc = new Document();
        doc.setName(name);
        doc.setContentType(contentType);
        doc.setFilePath(filePath);
        doc.setFileSize(fileSize);
        doc.setOwner(owner);
        doc.setChecksum(generateChecksum(filePath));

        Document saved = documentRepository.save(doc);

        
        // Category: Spring Framework
        // Spring AOP creates a proxy around the bean to intercept @Transactional methods.
        // When calling a method on 'this' (the raw object, not the proxy), the
        // @Transactional annotation on createVersion() is completely ignored.
        // The version creation runs without its own transaction boundary.
        // Fix: Inject self via @Lazy @Autowired DocumentService self; then call
        // self.createVersion(), or extract createVersion to a separate @Service
        this.createVersion(saved, owner, "Initial upload");

        notificationService.notifyDocumentCreated(saved);

        return saved;
    }

    @Transactional
    public void createVersion(Document document, User user, String changeSummary) {
        DocumentVersion version = new DocumentVersion();
        version.setDocument(document);
        version.setVersionNumber(document.getVersionNumber());
        version.setFilePath(document.getFilePath());
        version.setFileSize(document.getFileSize());
        version.setChecksum(document.getChecksum());
        version.setCreatedBy(user);
        version.setChangeSummary(changeSummary);
        document.getVersions().add(version);
        documentRepository.save(document);
    }

    public Document getDocument(Long id) {
        Document doc = documentRepository.findByIdAndIsDeletedFalse(id)
            .orElseThrow(() -> new RuntimeException("Document not found: " + id));

        
        // Category: Database & ORM
        // This method is not annotated with @Transactional, so the Hibernate session
        // is closed after documentRepository.findByIdAndIsDeletedFalse() returns.
        // Accessing doc.getPermissions().size() triggers a lazy load attempt on a
        // detached entity, throwing org.hibernate.LazyInitializationException.
        // Fix: Add @Transactional(readOnly = true) to this method
        log.info("Document {} has {} permissions", doc.getName(), doc.getPermissions().size());

        return doc;
    }

    private String generateChecksum(String filePath) {
        return String.valueOf(filePath != null ? filePath.hashCode() : 0);
    }

    
    // Category: Spring Framework
    // When uploadAndProcess() calls this.processDocumentAsync(), it invokes the
    // method directly on the raw object, bypassing the Spring AOP proxy that
    // implements @Async behavior. The method runs synchronously on the caller's
    // thread instead of being dispatched to the async executor.
    // Fix: Move processDocumentAsync to a separate @Service bean, or inject
    // self via @Lazy @Autowired DocumentService self; and call self.processDocumentAsync()
    @Async
    public CompletableFuture<Void> processDocumentAsync(Document document) {
        try {
            Thread.sleep(1000); // simulate heavy processing (OCR, indexing, etc.)
            log.info("Processed document: {}", document.getName());
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
        return CompletableFuture.completedFuture(null);
    }

    public void uploadAndProcess(Document document) {
        documentRepository.save(document);
        
        // The caller thread blocks for 1 second instead of returning immediately
        this.processDocumentAsync(document);
    }

    public List<Document> getDocumentsByOwner(Long ownerId) {
        
        // Category: Database & ORM
        // Creating a new EntityManager from the factory allocates a database connection
        // from the pool. Since em.close() is never called, the connection is leaked
        // back to the pool. Under load, this exhausts all available connections,
        // causing new requests to hang waiting for a connection.
        // Fix: Use try-with-resources: try { em = ...; ... } finally { em.close(); }
        // Or better yet, rely on the Spring-managed @PersistenceContext EntityManager
        //
        
        // When D3 causes connection pool exhaustion, requests fail early with
        // "Cannot acquire connection" before reaching setCurrentUser(). Once D3
        // is fixed (by closing the EntityManager), requests succeed and the
        // ThreadLocal accumulates User objects on pooled threads, revealing A1.
        // Fixing D3 first will expose A1's symptoms (stale user data, memory leak).
        EntityManager em = entityManager.getEntityManagerFactory().createEntityManager();
        var query = em.createQuery(
            "SELECT d FROM Document d WHERE d.owner.id = :ownerId AND d.isDeleted = false",
            Document.class
        );
        query.setParameter("ownerId", ownerId);
        return query.getResultList();
        
    }

    @Transactional
    public Document updateDocument(Long id, String name, String contentType) {
        Document doc = documentRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("Document not found: " + id));
        doc.setName(name);
        doc.setContentType(contentType);
        return documentRepository.save(doc);
    }

    @Transactional
    public void deleteDocument(Long id) {
        Document doc = documentRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("Document not found: " + id));
        doc.setIsDeleted(true);
        documentRepository.save(doc);
    }

    
    // Category: Spring Framework
    // Both getCachedDocument(Long) and getCachedDocument(String) use the "docs"
    // cache. Spring's default key generator uses the method parameters as the key.
    // If a Long id (e.g., 123L) and a String name (e.g., "123") produce the same
    // key representation, the wrong cached value is returned, causing ClassCastException
    // when the caller expects Document-by-id but gets Document-by-name (or vice versa).
    // Fix: Use @Cacheable(value = "docs", key = "'id-' + #id") and
    // @Cacheable(value = "docs", key = "'name-' + #name") to namespace the keys
    //
    
    //   1. getCachedDocument(Long id) - add key = "'id-' + #id"
    //   2. getCachedDocument(String name) - add key = "'name-' + #name"
    // Fixing only one method still leaves collisions possible when the unfixed
    // method's parameter matches the fixed method's key pattern.
    @Cacheable("docs")
    public Optional<Document> getCachedDocument(Long id) {
        return documentRepository.findById(id);
    }

    
    // A call with Long 1L and String "1" will collide in the cache
    
    // to use namespaced keys. Fixing only one leaves the collision bug.
    @Cacheable("docs")
    public Optional<Document> getCachedDocument(String name) {
        return documentRepository.findByNameContainingIgnoreCase(name).stream().findFirst();
    }
}
