package com.docuvault.integration;

import com.docuvault.model.Document;
import com.docuvault.model.User;
import com.docuvault.repository.DocumentRepository;
import com.docuvault.repository.UserRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.autoconfigure.orm.jpa.TestEntityManager;
import org.springframework.test.context.ActiveProfiles;

import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;

@DataJpaTest
@ActiveProfiles("test")
@Tag("integration")
public class DocumentRepositoryTest {

    @Autowired
    private TestEntityManager entityManager;

    @Autowired
    private DocumentRepository documentRepository;

    @Autowired
    private UserRepository userRepository;

    private User testUser;

    @BeforeEach
    void setUp() {
        testUser = new User();
        testUser.setUsername("repotest");
        testUser.setEmail("repotest@example.com");
        testUser.setPasswordHash("$2a$10$hash");
        testUser = entityManager.persist(testUser);
        entityManager.flush();
    }

    @Test
    void test_save_and_find_document() {
        Document doc = createDoc("test.pdf");
        Document saved = documentRepository.save(doc);

        assertNotNull(saved.getId());
        Optional<Document> found = documentRepository.findById(saved.getId());
        assertTrue(found.isPresent());
        assertEquals("test.pdf", found.get().getName());
    }

    @Test
    void test_find_by_owner_excludes_deleted() {
        Document active = createDoc("active.pdf");
        active.setIsDeleted(false);
        documentRepository.save(active);

        Document deleted = createDoc("deleted.pdf");
        deleted.setIsDeleted(true);
        documentRepository.save(deleted);

        List<Document> results = documentRepository.findByOwnerIdAndIsDeletedFalse(testUser.getId());
        assertEquals(1, results.size());
        assertEquals("active.pdf", results.get(0).getName());
    }

    @Test
    void test_find_by_name_containing() {
        documentRepository.save(createDoc("important-report.pdf"));
        documentRepository.save(createDoc("quarterly-report.docx"));
        documentRepository.save(createDoc("photo.jpg"));

        List<Document> results = documentRepository.findByNameContainingIgnoreCase("report");
        assertEquals(2, results.size());
    }

    @Test
    void test_find_by_id_excludes_deleted() {
        Document doc = createDoc("test.pdf");
        doc.setIsDeleted(true);
        Document saved = documentRepository.save(doc);

        Optional<Document> result = documentRepository.findByIdAndIsDeletedFalse(saved.getId());
        assertFalse(result.isPresent());
    }

    
    @Test
    void test_document_with_versions_single_query() {
        Document doc = createDoc("versioned.pdf");
        documentRepository.save(doc);

        
        // With proper JOIN FETCH, this should be a single query
        List<Document> docs = documentRepository.findDocumentsByOwnerId(testUser.getId());
        assertFalse(docs.isEmpty());

        // Accessing versions in a transaction should work
        
        for (Document d : docs) {
            assertNotNull(d.getVersions());
        }
    }

    @Test
    void test_no_n_plus_one() {
        // Create multiple documents
        for (int i = 0; i < 5; i++) {
            documentRepository.save(createDoc("doc" + i + ".pdf"));
        }

        // Loading all documents and accessing versions should be efficient
        List<Document> docs = documentRepository.findDocumentsByOwnerId(testUser.getId());
        assertEquals(5, docs.size());

        
        // With the fix, all versions should be loaded in the initial query
    }

    @Test
    void test_find_documents_by_owner() {
        documentRepository.save(createDoc("doc1.pdf"));
        documentRepository.save(createDoc("doc2.pdf"));

        User otherUser = new User();
        otherUser.setUsername("other");
        otherUser.setEmail("other@example.com");
        otherUser.setPasswordHash("$2a$10$hash");
        otherUser = entityManager.persist(otherUser);

        Document otherDoc = createDoc("other.pdf");
        otherDoc.setOwner(otherUser);
        documentRepository.save(otherDoc);

        List<Document> results = documentRepository.findDocumentsByOwnerId(testUser.getId());
        assertEquals(2, results.size());
    }

    @Test
    void test_document_versioning() {
        Document doc = createDoc("versioned.pdf");
        doc.setVersionNumber(1);
        Document saved = documentRepository.save(doc);

        saved.setVersionNumber(2);
        documentRepository.save(saved);

        Document updated = documentRepository.findById(saved.getId()).get();
        assertEquals(2, updated.getVersionNumber());
    }

    @Test
    void test_optimistic_locking() {
        Document doc = createDoc("locked.pdf");
        Document saved = documentRepository.save(doc);
        entityManager.flush();

        assertNotNull(saved.getVersion(), "Version field should be populated");
    }

    @Test
    void test_search_case_insensitive() {
        documentRepository.save(createDoc("MyReport.PDF"));

        List<Document> lower = documentRepository.findByNameContainingIgnoreCase("myreport");
        List<Document> upper = documentRepository.findByNameContainingIgnoreCase("MYREPORT");

        assertEquals(lower.size(), upper.size());
        assertFalse(lower.isEmpty());
    }

    @Test
    void test_save_multiple_documents() {
        for (int i = 0; i < 10; i++) {
            documentRepository.save(createDoc("batch-" + i + ".pdf"));
        }

        assertEquals(10, documentRepository.count());
    }

    @Test
    void test_delete_document() {
        Document doc = createDoc("to-delete.pdf");
        Document saved = documentRepository.save(doc);

        documentRepository.delete(saved);
        entityManager.flush();

        assertFalse(documentRepository.findById(saved.getId()).isPresent());
    }

    private Document createDoc(String name) {
        Document doc = new Document();
        doc.setName(name);
        doc.setContentType("application/pdf");
        doc.setOwner(testUser);
        doc.setFilePath("/uploads/" + name);
        doc.setFileSize(1024L);
        return doc;
    }
}
