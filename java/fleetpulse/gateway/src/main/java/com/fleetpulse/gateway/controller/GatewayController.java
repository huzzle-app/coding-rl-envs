package com.fleetpulse.gateway.controller;

import com.fleetpulse.gateway.service.RequestService;
import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;
import jakarta.persistence.Query;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.Resource;
import org.springframework.core.io.UrlResource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.io.*;
import java.net.*;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/gateway")
public class GatewayController {

    private static final Logger log = LoggerFactory.getLogger(GatewayController.class);

    @Autowired
    private RequestService requestService;

    @PersistenceContext
    private EntityManager entityManager;

    @Value("${upload.directory:/tmp/fleetpulse/uploads}")
    private String uploadDirectory;

    
    // User input directly embedded in SQL query
    // Fix: Use parameterized queries with setParameter()
    @GetMapping("/search")
    @SuppressWarnings("unchecked")
    public ResponseEntity<List<Object[]>> searchVehicles(@RequestParam String query) {
        
        String sql = "SELECT * FROM vehicles WHERE license_plate LIKE '%" + query + "%'";
        Query q = entityManager.createNativeQuery(sql);
        return ResponseEntity.ok(q.getResultList());
    }

    
    // User-supplied filename used directly in path construction
    // Fix: Normalize path and verify it stays within upload directory
    @GetMapping("/files/{filename}")
    public ResponseEntity<Resource> downloadFile(@PathVariable String filename) {
        try {
            
            Path filePath = Paths.get(uploadDirectory).resolve(filename);
            Resource resource = new UrlResource(filePath.toUri());

            if (resource.exists()) {
                return ResponseEntity.ok()
                    .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"" + filename + "\"")
                    .body(resource);
            }
            return ResponseEntity.notFound().build();
        } catch (MalformedURLException e) {
            return ResponseEntity.badRequest().build();
        }
    }

    
    // User-supplied URL fetched by server without validation
    // Fix: Validate URL against whitelist, block internal IPs
    @PostMapping("/proxy")
    public ResponseEntity<String> proxyRequest(@RequestParam String url) {
        try {
            
            // e.g., http://169.254.169.254/latest/meta-data/ (AWS metadata)
            // or http://localhost:8001/api/admin/secrets
            URL targetUrl = new URL(url);
            HttpURLConnection conn = (HttpURLConnection) targetUrl.openConnection();
            conn.setRequestMethod("GET");
            conn.setConnectTimeout(5000);

            BufferedReader reader = new BufferedReader(
                new InputStreamReader(conn.getInputStream()));
            StringBuilder response = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) {
                response.append(line);
            }
            reader.close();

            return ResponseEntity.ok(response.toString());
        } catch (Exception e) {
            return ResponseEntity.badRequest().body("Error: " + e.getMessage());
        }
    }

    @GetMapping("/health")
    public ResponseEntity<Map<String, String>> health() {
        return ResponseEntity.ok(Map.of("status", "UP", "service", "gateway"));
    }
}
