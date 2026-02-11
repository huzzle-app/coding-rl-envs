package com.docuvault.model;

import jakarta.persistence.*;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

@Entity
@Table(name = "documents")
public class Document {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 500)
    private String name;

    @Column(name = "content_type", length = 100)
    private String contentType;

    @Column(name = "file_path", length = 1000)
    private String filePath;

    @Column(name = "file_size")
    private Long fileSize;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "owner_id", nullable = false)
    private User owner;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt;

    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;

    @Column(name = "version_number", nullable = false)
    private Integer versionNumber = 1;

    @Column(length = 64)
    private String checksum;

    @Column(name = "is_deleted", nullable = false)
    private Boolean isDeleted = false;

    
    // Category: Database & ORM
    // When accessing the versions collection, Hibernate fires a separate SELECT
    // query for each document's versions. In a list of N documents, this results
    // in N+1 total queries (1 for documents + N for each document's versions).
    // Fix: Add @EntityGraph or define a repository method with
    // @Query("SELECT d FROM Document d JOIN FETCH d.versions WHERE d.id = :id")
    @OneToMany(mappedBy = "document", fetch = FetchType.LAZY, cascade = CascadeType.ALL)
    private List<DocumentVersion> versions = new ArrayList<>();

    
    // Category: Database & ORM
    // Accessing this collection outside of an active Hibernate session/transaction
    // throws org.hibernate.LazyInitializationException: could not initialize proxy.
    // This happens when DocumentService.getDocument() is not @Transactional.
    // Fix: Use @Transactional(readOnly=true) on service methods accessing lazy
    // collections, or use @EntityGraph to eagerly fetch when needed
    @OneToMany(mappedBy = "document", fetch = FetchType.LAZY, cascade = CascadeType.ALL)
    private List<Permission> permissions = new ArrayList<>();

    @Version
    private Long version;

    @PrePersist
    protected void onCreate() {
        createdAt = LocalDateTime.now();
        updatedAt = LocalDateTime.now();
    }

    @PreUpdate
    protected void onUpdate() {
        updatedAt = LocalDateTime.now();
    }

    
    // Category: Business Logic
    // When Document is used as a HashMap key and the name field is subsequently
    // changed, the hash code changes, making the entry unretrievable from the map.
    // hashCode() should only use immutable fields (like id after persistence).
    // Fix: Use only the id field (immutable after persist) for equals/hashCode:
    //   return Objects.equals(id, document.id) and Objects.hash(id)
    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        Document document = (Document) o;
        return Objects.equals(name, document.name) && Objects.equals(owner, document.owner);
    }

    @Override
    public int hashCode() {
        return Objects.hash(name, owner);
    }

    // Getters and setters
    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    public String getContentType() { return contentType; }
    public void setContentType(String contentType) { this.contentType = contentType; }
    public String getFilePath() { return filePath; }
    public void setFilePath(String filePath) { this.filePath = filePath; }
    public Long getFileSize() { return fileSize; }
    public void setFileSize(Long fileSize) { this.fileSize = fileSize; }
    public User getOwner() { return owner; }
    public void setOwner(User owner) { this.owner = owner; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public LocalDateTime getUpdatedAt() { return updatedAt; }
    public Integer getVersionNumber() { return versionNumber; }
    public void setVersionNumber(Integer versionNumber) { this.versionNumber = versionNumber; }
    public String getChecksum() { return checksum; }
    public void setChecksum(String checksum) { this.checksum = checksum; }
    public Boolean getIsDeleted() { return isDeleted; }
    public void setIsDeleted(Boolean isDeleted) { this.isDeleted = isDeleted; }
    public List<DocumentVersion> getVersions() { return versions; }
    public void setVersions(List<DocumentVersion> versions) { this.versions = versions; }
    public List<Permission> getPermissions() { return permissions; }
    public void setPermissions(List<Permission> permissions) { this.permissions = permissions; }
    public Long getVersion() { return version; }
    public void setVersion(Long version) { this.version = version; }
}
