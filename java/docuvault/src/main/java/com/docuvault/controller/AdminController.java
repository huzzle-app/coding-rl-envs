package com.docuvault.controller;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.Resource;
import org.springframework.core.io.UrlResource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.net.MalformedURLException;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Map;

@RestController
@RequestMapping("/api/admin")
public class AdminController {

    private static final Logger log = LoggerFactory.getLogger(AdminController.class);

    @Value("${upload.directory:/tmp/docuvault/uploads}")
    private String uploadDirectory;

    
    // Category: Security
    // The user-supplied filename is directly used to construct the file path
    // without any sanitization or validation. An attacker can use path traversal
    // sequences like "../../etc/passwd" or "../../../etc/shadow" to read arbitrary
    // files on the server filesystem, including sensitive configuration files,
    // credentials, and system files outside the upload directory.
    // Fix: Normalize the resolved path and verify it starts with the upload directory:
    //   Path normalized = filePath.normalize();
    //   if (!normalized.startsWith(Paths.get(uploadDirectory).normalize())) {
    //       return ResponseEntity.badRequest().build();
    //   }
    @GetMapping("/files/{filename}")
    public ResponseEntity<Resource> downloadFile(@PathVariable String filename) {
        try {
            
            // Attacker request: GET /api/admin/files/..%2F..%2Fetc%2Fpasswd
            Path filePath = Paths.get(uploadDirectory).resolve(filename);
            Resource resource = new UrlResource(filePath.toUri());

            if (resource.exists()) {
                return ResponseEntity.ok()
                    .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"" + filename + "\"")
                    .body(resource);
            } else {
                return ResponseEntity.notFound().build();
            }
        } catch (MalformedURLException e) {
            return ResponseEntity.badRequest().build();
        }
    }

    @GetMapping("/stats")
    public ResponseEntity<Map<String, Object>> getSystemStats() {
        return ResponseEntity.ok(Map.of(
            "totalDocuments", 0,
            "totalUsers", 0,
            "diskUsage", "0 MB"
        ));
    }
}
