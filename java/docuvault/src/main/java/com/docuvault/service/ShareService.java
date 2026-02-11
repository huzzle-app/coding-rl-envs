package com.docuvault.service;

import com.docuvault.model.Document;
import com.docuvault.model.Permission;
import com.docuvault.model.User;
import com.docuvault.repository.DocumentRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CompletableFuture;

@Service
public class ShareService {

    private static final Logger log = LoggerFactory.getLogger(ShareService.class);

    @Autowired
    private DocumentRepository documentRepository;

    @Autowired
    private NotificationService notificationService;

    @Transactional
    public Permission shareDocument(Long documentId, User targetUser, String permissionType, User grantedBy) {
        Document doc = documentRepository.findById(documentId)
            .orElseThrow(() -> new RuntimeException("Document not found"));

        Permission permission = new Permission();
        permission.setDocument(doc);
        permission.setUser(targetUser);
        permission.setPermissionType(permissionType);
        permission.setGrantedBy(grantedBy);
        permission.setExpiresAt(LocalDateTime.now().plusDays(30));

        doc.getPermissions().add(permission);
        documentRepository.save(doc);

        
        // Category: Concurrency
        // If notificationService.notifyDocumentShared() throws an exception,
        // it is captured by the CompletableFuture but never observed. The
        // exception is silently lost because no .exceptionally() or
        // .whenComplete() handler is attached. The caller has no way to know
        // that the notification failed, and the error is not logged.
        // Fix: Add .exceptionally(ex -> { log.error("Notification failed", ex); return null; })
        // or use .whenComplete((result, ex) -> { if (ex != null) log.error(...); })
        //
        
        // When notifyDocumentShared() is called with a document whose owner is null,
        // it throws NPE when trying to log owner.getUsername(). Because A3 swallows
        // the exception, the NPE is never seen. Fixing A3 (by adding exception handler)
        // will REVEAL the NPE: log.error will show "NullPointerException: Cannot invoke
        // getUsername() on null reference" from NotificationService.notifyDocumentShared().
        CompletableFuture.supplyAsync(() -> {
            notificationService.notifyDocumentShared(doc, targetUser);
            return null;
        });

        return permission;
    }

    
    // Category: Generics & Type Safety
    // The method accepts List<? extends Permission> which means "a list of some
    // unknown subtype of Permission." Java's type system prevents adding to such
    // a list because the compiler cannot verify that the element being added is
    // compatible with the unknown concrete type. The raw type cast bypasses the
    // compiler check but causes heap pollution: if the actual list is
    // List<SpecialPermission>, adding a plain Permission corrupts the type invariant
    // and causes ClassCastException when the caller reads elements.
    // Fix: Change parameter type to List<Permission> (no wildcard), or use a
    // helper method with captured type parameter: <T extends Permission> void add(List<T>...)
    @SuppressWarnings("unchecked")
    public void addDefaultPermissions(List<? extends Permission> permissions, Document document, User owner) {
        Permission defaultPerm = new Permission();
        defaultPerm.setDocument(document);
        defaultPerm.setUser(owner);
        defaultPerm.setPermissionType("OWNER");

        
        // Compiler prevents direct add on List<? extends Permission>, so the
        // developer bypassed it with a raw type cast. This causes heap pollution
        // and potential ClassCastException in callers that expect a specific subtype.
        ((List) permissions).add(defaultPerm);
    }

    public List<Permission> getDocumentPermissions(Long documentId) {
        Document doc = documentRepository.findById(documentId)
            .orElseThrow(() -> new RuntimeException("Document not found"));
        return new ArrayList<>(doc.getPermissions());
    }

    @Transactional
    public void revokePermission(Long documentId, Long userId) {
        Document doc = documentRepository.findById(documentId)
            .orElseThrow(() -> new RuntimeException("Document not found"));

        doc.getPermissions().removeIf(p -> p.getUser().getId().equals(userId));
        documentRepository.save(doc);
    }
}
