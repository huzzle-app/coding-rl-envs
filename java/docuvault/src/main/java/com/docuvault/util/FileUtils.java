package com.docuvault.util;

import com.docuvault.model.Document;
import com.docuvault.repository.DocumentRepository;
import jakarta.persistence.OptimisticLockException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.nio.file.*;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;

@Component
public class FileUtils {

    private static final Logger log = LoggerFactory.getLogger(FileUtils.class);

    @Autowired
    private DocumentRepository documentRepository;

    
    // Category: Database & ORM
    // The Document entity has a @Version field for optimistic locking. When two
    // concurrent transactions read the same document and both try to update it,
    // the second save() call throws OptimisticLockException because the version
    // number has already been incremented by the first transaction. This exception
    // propagates up as an unhandled 500 Internal Server Error to the client,
    // instead of being caught and retried or returned as a 409 Conflict.
    // Fix: Catch OptimisticLockException, reload the entity from the database,
    // re-apply the changes, and retry the save (with a maximum retry count):
    //   try { return documentRepository.save(doc); }
    //   catch (OptimisticLockException e) { /* reload and retry */ }
    public Document updateDocumentFile(Long documentId, String newFilePath, Long newFileSize) {
        Document doc = documentRepository.findById(documentId)
            .orElseThrow(() -> new RuntimeException("Document not found"));

        doc.setFilePath(newFilePath);
        doc.setFileSize(newFileSize);

        
        // If another transaction modified this document concurrently, save() throws
        // OptimisticLockException which propagates as unhandled 500 error
        return documentRepository.save(doc);
    }

    
    // Category: Business Logic
    // The for-each loop internally uses an Iterator over the ArrayList. Calling
    // cleaned.remove(path) during iteration modifies the list's structural modCount,
    // which the Iterator detects on the next call to hasNext()/next(), throwing
    // ConcurrentModificationException. This is a single-threaded bug (not a
    // concurrency issue) - the same thread modifies the collection it is iterating.
    // Fix: Use Iterator explicitly with Iterator.remove():
    //   Iterator<String> it = cleaned.iterator();
    //   while (it.hasNext()) { String path = it.next(); if (...) { it.remove(); } }
    // Or collect items to remove in a separate list and call removeAll() after iteration
    public List<String> cleanupTempFiles(List<String> filePaths) {
        List<String> cleaned = new ArrayList<>(filePaths);

        
        // The for-each loop uses an Iterator; calling cleaned.remove(path)
        // during iteration triggers ConcurrentModificationException
        for (String path : cleaned) {
            if (path.endsWith(".tmp")) {
                try {
                    Files.deleteIfExists(Paths.get(path));
                    cleaned.remove(path); 
                } catch (IOException e) {
                    log.error("Failed to delete temp file: {}", path, e);
                }
            }
        }

        return cleaned;
    }

    public String calculateChecksum(Path filePath) {
        try {
            byte[] content = Files.readAllBytes(filePath);
            java.security.MessageDigest digest = java.security.MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(content);
            StringBuilder hexString = new StringBuilder();
            for (byte b : hash) {
                String hex = Integer.toHexString(0xff & b);
                if (hex.length() == 1) hexString.append('0');
                hexString.append(hex);
            }
            return hexString.toString();
        } catch (Exception e) {
            log.error("Failed to calculate checksum for: {}", filePath, e);
            return null;
        }
    }

    public boolean validateFilePath(String filePath) {
        if (filePath == null || filePath.isEmpty()) {
            return false;
        }
        Path path = Paths.get(filePath);
        return Files.exists(path) && Files.isRegularFile(path);
    }

    public long getDirectorySize(Path directory) throws IOException {
        return Files.walk(directory)
            .filter(Files::isRegularFile)
            .mapToLong(p -> {
                try {
                    return Files.size(p);
                } catch (IOException e) {
                    return 0;
                }
            })
            .sum();
    }
}
