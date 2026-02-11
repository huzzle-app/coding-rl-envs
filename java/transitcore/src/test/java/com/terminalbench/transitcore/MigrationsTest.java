package com.terminalbench.transitcore;

import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;

class MigrationsTest {
    @Test
    void migrationsContainCoreTables() throws Exception {
        String core = Files.readString(Path.of("migrations/001_core.sql"));
        String policy = Files.readString(Path.of("migrations/002_policy.sql"));

        assertTrue(core.contains("dispatch_jobs"));
        assertTrue(core.contains("capacity_snapshots"));
        assertTrue(policy.contains("policy_decisions"));
    }
}
