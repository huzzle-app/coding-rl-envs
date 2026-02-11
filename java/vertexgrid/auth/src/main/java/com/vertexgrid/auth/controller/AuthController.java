package com.vertexgrid.auth.controller;

import com.vertexgrid.auth.security.TokenValidator;
import com.vertexgrid.auth.service.AuthenticationService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/auth")
public class AuthController {

    @Autowired
    private AuthenticationService authService;

    @Autowired
    private TokenValidator tokenValidator;

    @PostMapping("/login")
    public ResponseEntity<Map<String, String>> login(@RequestBody Map<String, String> credentials) {
        try {
            String token = authService.authenticate(
                credentials.get("username"), credentials.get("password"));
            return ResponseEntity.ok(Map.of("token", token));
        } catch (RuntimeException e) {
            return ResponseEntity.status(401).body(Map.of("error", e.getMessage()));
        }
    }

    @PostMapping("/validate")
    public ResponseEntity<Map<String, Object>> validate(@RequestHeader("Authorization") String token) {
        String username = tokenValidator.validateToken(token.replace("Bearer ", ""));
        if (username != null) {
            return ResponseEntity.ok(Map.of("valid", true, "username", username));
        }
        return ResponseEntity.status(401).body(Map.of("valid", false));
    }

    @GetMapping("/health")
    public ResponseEntity<Map<String, String>> health() {
        return ResponseEntity.ok(Map.of("status", "UP", "service", "auth"));
    }
}
