package com.vertexgrid.notifications.controller;

import com.vertexgrid.notifications.service.NotificationService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * REST controller exposing notification endpoints for sending notifications
 * and health checks.
 */
@RestController
@RequestMapping("/api/notifications")
public class NotificationController {

    @Autowired
    private NotificationService notificationService;

    @PostMapping("/send")
    public ResponseEntity<Map<String, String>> sendNotification(
            @RequestParam String channel, @RequestParam String userId,
            @RequestParam String message) {
        notificationService.sendNotification(channel, userId, message);
        return ResponseEntity.ok(Map.of("status", "sent"));
    }

    @GetMapping("/health")
    public ResponseEntity<Map<String, String>> health() {
        return ResponseEntity.ok(Map.of("status", "UP", "service", "notifications"));
    }
}
