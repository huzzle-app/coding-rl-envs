package com.vertexgrid.dispatch.controller;

import com.vertexgrid.dispatch.service.DispatchService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/dispatch")
public class DispatchController {

    @Autowired
    private DispatchService dispatchService;

    @GetMapping("/health")
    public ResponseEntity<Map<String, String>> health() {
        return ResponseEntity.ok(Map.of("status", "UP", "service", "dispatch"));
    }

    @GetMapping("/jobs")
    public ResponseEntity<Map<String, ?>> getActiveJobs() {
        return ResponseEntity.ok(dispatchService.getActiveJobs());
    }
}
