package com.docuvault.repository;

import com.docuvault.model.Document;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;
import java.util.List;
import java.util.Optional;

@Repository
public interface DocumentRepository extends JpaRepository<Document, Long> {

    List<Document> findByOwnerIdAndIsDeletedFalse(Long ownerId);

    List<Document> findByNameContainingIgnoreCase(String name);

    Optional<Document> findByIdAndIsDeletedFalse(Long id);

    @Query("SELECT d FROM Document d WHERE d.owner.id = :ownerId")
    List<Document> findDocumentsByOwnerId(@Param("ownerId") Long ownerId);

    // Note: No JOIN FETCH query for versions - this contributes to bug D1 (N+1 query)
    // A proper fix would add:
    // @Query("SELECT d FROM Document d JOIN FETCH d.versions WHERE d.id = :id")
    // Optional<Document> findByIdWithVersions(@Param("id") Long id);
}
