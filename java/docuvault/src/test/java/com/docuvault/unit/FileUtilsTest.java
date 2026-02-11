package com.docuvault.unit;

import com.docuvault.model.Document;
import com.docuvault.repository.DocumentRepository;
import com.docuvault.util.FileUtils;
import jakarta.persistence.OptimisticLockException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.*;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
@Tag("unit")
public class FileUtilsTest {

    @Mock
    private DocumentRepository documentRepository;

    @InjectMocks
    private FileUtils fileUtils;

    private Document testDoc;

    @BeforeEach
    void setUp() {
        testDoc = new Document();
        testDoc.setId(1L);
        testDoc.setName("test.pdf");
        testDoc.setFilePath("/uploads/test.pdf");
        testDoc.setVersion(1L);
    }

    // Tests for BUG D4: Optimistic locking ignored
    @Test
    void test_optimistic_lock_retry() {
        when(documentRepository.findById(1L)).thenReturn(Optional.of(testDoc));
        when(documentRepository.save(any(Document.class)))
            .thenThrow(new OptimisticLockException("Concurrent modification"))
            .thenReturn(testDoc); // Succeed on retry

        
        // Without the fix, this throws OptimisticLockException
        assertDoesNotThrow(() ->
            fileUtils.updateDocumentFile(1L, "/uploads/new.pdf", 2048L),
            "Should retry on optimistic lock exception, not propagate it"
        );
    }

    @Test
    void test_concurrent_update_detected() {
        when(documentRepository.findById(1L)).thenReturn(Optional.of(testDoc));
        when(documentRepository.save(any(Document.class)))
            .thenThrow(new OptimisticLockException("Version mismatch"));

        
        // Even if retry fails, it should give a meaningful error, not a 500
        try {
            fileUtils.updateDocumentFile(1L, "/uploads/new.pdf", 2048L);
        } catch (OptimisticLockException e) {
            fail("OptimisticLockException should be handled, not propagated");
        } catch (RuntimeException e) {
            // Acceptable if wrapped in a user-friendly exception after retry exhaustion
            assertTrue(e.getMessage().contains("retry") || e.getMessage().contains("conflict")
                || e.getMessage().contains("concurrent") || e.getMessage().contains("Optimistic"),
                "Should give meaningful error message about the conflict, got: " + e.getMessage());
        }
    }

    @Test
    void test_update_document_file_success() {
        when(documentRepository.findById(1L)).thenReturn(Optional.of(testDoc));
        when(documentRepository.save(any(Document.class))).thenReturn(testDoc);

        Document result = fileUtils.updateDocumentFile(1L, "/uploads/new.pdf", 2048L);

        assertNotNull(result);
        assertEquals("/uploads/new.pdf", testDoc.getFilePath());
        assertEquals(2048L, testDoc.getFileSize());
    }

    @Test
    void test_update_document_not_found() {
        when(documentRepository.findById(999L)).thenReturn(Optional.empty());

        assertThrows(RuntimeException.class, () ->
            fileUtils.updateDocumentFile(999L, "/path", 100L)
        );
    }

    // Tests for BUG B4: Iterator invalidation
    @Test
    void test_cleanup_files_no_cme() {
        List<String> files = new ArrayList<>(Arrays.asList(
            "/tmp/file1.tmp",
            "/tmp/file2.pdf",
            "/tmp/file3.tmp",
            "/tmp/file4.doc"
        ));

        
        assertDoesNotThrow(() -> {
            List<String> result = fileUtils.cleanupTempFiles(files);
            assertNotNull(result);
        }, "Cleanup should not throw ConcurrentModificationException");
    }

    @Test
    void test_iterator_safe_removal() {
        List<String> files = new ArrayList<>(Arrays.asList(
            "/tmp/a.tmp",
            "/tmp/b.tmp",
            "/tmp/c.pdf",
            "/tmp/d.tmp"
        ));

        List<String> result = fileUtils.cleanupTempFiles(files);

        // After cleanup, only non-tmp files should remain
        assertFalse(result.stream().anyMatch(f -> f.endsWith(".tmp")),
            "All .tmp files should be removed");
        assertTrue(result.stream().anyMatch(f -> f.endsWith(".pdf")),
            "Non-.tmp files should be retained");
    }

    @Test
    void test_cleanup_empty_list() {
        List<String> empty = new ArrayList<>();
        List<String> result = fileUtils.cleanupTempFiles(empty);
        assertTrue(result.isEmpty());
    }

    @Test
    void test_cleanup_no_temp_files() {
        List<String> files = new ArrayList<>(Arrays.asList(
            "/uploads/doc.pdf",
            "/uploads/image.png"
        ));

        List<String> result = fileUtils.cleanupTempFiles(files);
        assertEquals(2, result.size());
    }
}
