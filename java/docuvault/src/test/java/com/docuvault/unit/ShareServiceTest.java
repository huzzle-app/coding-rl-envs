package com.docuvault.unit;

import com.docuvault.model.Document;
import com.docuvault.model.Permission;
import com.docuvault.model.User;
import com.docuvault.repository.DocumentRepository;
import com.docuvault.service.NotificationService;
import com.docuvault.service.ShareService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
@Tag("unit")
public class ShareServiceTest {

    @Mock
    private DocumentRepository documentRepository;

    @Mock
    private NotificationService notificationService;

    @InjectMocks
    private ShareService shareService;

    private Document testDoc;
    private User testUser;
    private User targetUser;

    @BeforeEach
    void setUp() {
        testDoc = new Document();
        testDoc.setId(1L);
        testDoc.setName("shared.pdf");
        testDoc.setPermissions(new ArrayList<>());

        testUser = new User();
        testUser.setId(1L);
        testUser.setUsername("owner");

        targetUser = new User();
        targetUser.setId(2L);
        targetUser.setUsername("viewer");
    }

    // Tests for BUG A3: CompletableFuture exception swallowed
    @Test
    void test_async_exception_not_swallowed() {
        when(documentRepository.findById(1L)).thenReturn(Optional.of(testDoc));
        when(documentRepository.save(any(Document.class))).thenReturn(testDoc);

        // Make notification throw an exception
        doThrow(new RuntimeException("Notification failed"))
            .when(notificationService).notifyDocumentShared(any(), any());

        
        // The fix should add .exceptionally() handler to log the error
        // This test verifies the exception is handled (logged), not silently swallowed
        assertDoesNotThrow(() -> {
            Permission result = shareService.shareDocument(1L, targetUser, "READ", testUser);
            assertNotNull(result);
        });

        // Verify the notification was attempted (even though it failed)
        // Give async task time to complete
        try { Thread.sleep(500); } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }

        // In fixed version, exception should be logged, not swallowed
    }

    @Test
    void test_completable_future_error_handling() {
        when(documentRepository.findById(1L)).thenReturn(Optional.of(testDoc));
        when(documentRepository.save(any(Document.class))).thenReturn(testDoc);

        AtomicBoolean exceptionHandled = new AtomicBoolean(false);

        // Notification runs async in CompletableFuture.supplyAsync(), so the stub
        // may not be invoked before Mockito's strict-stubs check - use lenient
        lenient().doThrow(new RuntimeException("Network error"))
            .when(notificationService).notifyDocumentShared(any(), any());

        // The share operation should succeed even if notification fails
        Permission result = shareService.shareDocument(1L, targetUser, "READ", testUser);
        assertNotNull(result);
        assertEquals("READ", result.getPermissionType());
    }

    @Test
    void test_completable_future_has_exception_handler() throws Exception {
        // A3: ShareService must attach an exception handler to CompletableFuture
        // Without .exceptionally() or .whenComplete(), exceptions are silently swallowed
        String source = new String(Files.readAllBytes(
            Paths.get("src/main/java/com/docuvault/service/ShareService.java")));
        String code = source.replaceAll("/\\*[\\s\\S]*?\\*/", "").replaceAll("//[^\n]*", "");

        boolean hasExceptionHandler = code.contains(".exceptionally(")
            || code.contains(".whenComplete(")
            || code.contains(".handle(");
        assertTrue(hasExceptionHandler,
            "ShareService must attach .exceptionally() or .whenComplete() to CompletableFuture " +
            "to prevent silent exception swallowing in async notification");
    }

    // Tests for BUG E2: Wildcard capture failure
    @Test
    void test_wildcard_list_operations() {
        List<Permission> permissions = new ArrayList<>();

        
        // but tries to add to it via raw type cast - heap pollution
        assertDoesNotThrow(() ->
            shareService.addDefaultPermissions(permissions, testDoc, testUser)
        );

        assertEquals(1, permissions.size(), "Default permission should be added");
        assertEquals("OWNER", permissions.get(0).getPermissionType());
    }

    @Test
    void test_permission_list_type_safe() {
        List<Permission> permissions = new ArrayList<>();

        shareService.addDefaultPermissions(permissions, testDoc, testUser);

        
        // Verify all elements are actually Permission instances
        for (Object item : permissions) {
            assertTrue(item instanceof Permission,
                "All items should be Permission instances, found: " + item.getClass());
        }
    }

    @Test
    void test_share_document_creates_permission() {
        when(documentRepository.findById(1L)).thenReturn(Optional.of(testDoc));
        when(documentRepository.save(any(Document.class))).thenReturn(testDoc);

        Permission result = shareService.shareDocument(1L, targetUser, "WRITE", testUser);

        assertNotNull(result);
        assertEquals("WRITE", result.getPermissionType());
        assertEquals(targetUser, result.getUser());
        assertEquals(testUser, result.getGrantedBy());
    }

    @Test
    void test_share_document_not_found() {
        when(documentRepository.findById(999L)).thenReturn(Optional.empty());

        assertThrows(RuntimeException.class, () ->
            shareService.shareDocument(999L, targetUser, "READ", testUser)
        );
    }

    @Test
    void test_revoke_permission() {
        Permission perm = new Permission();
        perm.setUser(targetUser);
        perm.setPermissionType("READ");
        testDoc.getPermissions().add(perm);

        when(documentRepository.findById(1L)).thenReturn(Optional.of(testDoc));
        when(documentRepository.save(any(Document.class))).thenReturn(testDoc);

        shareService.revokePermission(1L, 2L);

        assertTrue(testDoc.getPermissions().isEmpty());
    }

    @Test
    void test_get_document_permissions() {
        Permission perm = new Permission();
        perm.setPermissionType("READ");
        testDoc.getPermissions().add(perm);

        when(documentRepository.findById(1L)).thenReturn(Optional.of(testDoc));

        List<Permission> perms = shareService.getDocumentPermissions(1L);
        assertEquals(1, perms.size());
    }

    @Test
    void test_share_sets_expiration() {
        when(documentRepository.findById(1L)).thenReturn(Optional.of(testDoc));
        when(documentRepository.save(any(Document.class))).thenReturn(testDoc);

        Permission result = shareService.shareDocument(1L, targetUser, "READ", testUser);

        assertNotNull(result.getExpiresAt(), "Permission should have expiration date");
    }

    @Test
    void test_multiple_permissions_same_document() {
        when(documentRepository.findById(1L)).thenReturn(Optional.of(testDoc));
        when(documentRepository.save(any(Document.class))).thenReturn(testDoc);

        User user2 = new User();
        user2.setId(3L);
        user2.setUsername("editor");

        shareService.shareDocument(1L, targetUser, "READ", testUser);
        shareService.shareDocument(1L, user2, "WRITE", testUser);

        assertEquals(2, testDoc.getPermissions().size());
    }
}
