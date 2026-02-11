package com.docuvault.service;

import com.docuvault.model.Document;
import com.docuvault.model.DocumentVersion;
import com.docuvault.model.User;
import com.docuvault.repository.DocumentRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Service
public class VersionService {

    private static final Logger log = LoggerFactory.getLogger(VersionService.class);

    @Autowired
    private DocumentRepository documentRepository;

    
    // Category: Concurrency
    // Without the volatile modifier, the Java Memory Model allows the instance
    // reference to be visible to other threads in a partially constructed state.
    // Thread A may assign instance before the constructor fully completes;
    // Thread B sees non-null instance but accesses uninitialized fields, causing
    // NullPointerException or silent data corruption.
    // Fix: Add volatile modifier: private static volatile VersionService instance;
    private static VersionService instance; 

    
    // Category: Business Logic
    // Document's hashCode() depends on the mutable 'name' field. After a Document
    // is used as a HashMap key and its name is subsequently changed via setName(),
    // the hash code changes. This makes the cached entry unretrievable: get()
    // returns null and containsKey() returns false, even though the entry exists.
    // Fix: Use document.getId() (Long, immutable after persist) as the map key
    // instead of the Document object itself
    private final Map<Document, List<DocumentVersion>> versionCache = new HashMap<>();

    public static VersionService getInstance(DocumentRepository repo) {
        if (instance == null) {
            
            // Another thread may see a non-null but partially constructed instance
            // because the JMM permits reordering of object construction and reference
            // assignment without volatile or other happens-before guarantees.
            // Fix: Declare instance as volatile, or use the initialization-on-demand
            // holder class pattern for lazy thread-safe singleton initialization
            synchronized (VersionService.class) {
                if (instance == null) {
                    instance = new VersionService();
                    instance.documentRepository = repo;
                }
            }
        }
        return instance;
    }

    
    // If document.name changes after being used as key, hashCode changes
    // and the cached value becomes unretrievable via get() or containsKey()
    //
    
    // When D2 causes getDocument() to throw LazyInitializationException before
    // returning, the code never reaches getVersionsForDocument(). Once D2 is
    // fixed (by adding @Transactional), documents are successfully retrieved
    // and passed here, revealing B1's symptoms (cache misses after name changes).
    // Additionally, fixing B1 by using document.getId() as key will REVEAL a new
    // issue: if the Document entity becomes detached (session closed), calling
    // document.getVersions() on line below triggers LazyInitializationException.
    public List<DocumentVersion> getVersionsForDocument(Document document) {
        if (versionCache.containsKey(document)) {
            return versionCache.get(document);
        }
        List<DocumentVersion> versions = document.getVersions();
        versionCache.put(document, versions);
        return versions;
    }

    public void invalidateCache(Document document) {
        
        // The remove() call computes a new hashCode based on the current (changed)
        // name, which won't match the bucket where the entry was originally stored
        versionCache.remove(document);
    }

    @Transactional
    public DocumentVersion createVersion(Document document, String filePath, Long fileSize,
                                          String checksum, String changeSummary, User user) {
        int nextVersion = document.getVersionNumber() + 1;

        DocumentVersion version = new DocumentVersion();
        version.setDocument(document);
        version.setVersionNumber(nextVersion);
        version.setFilePath(filePath);
        version.setFileSize(fileSize);
        version.setChecksum(checksum);
        version.setCreatedBy(user);
        version.setChangeSummary(changeSummary);

        document.setVersionNumber(nextVersion);
        document.getVersions().add(version);

        documentRepository.save(document);

        // Invalidate cache - but this may fail due to B1 (mutable key)
        invalidateCache(document);

        return version;
    }

    public Map<Document, List<DocumentVersion>> getAllCachedVersions() {
        return new HashMap<>(versionCache);
    }
}
