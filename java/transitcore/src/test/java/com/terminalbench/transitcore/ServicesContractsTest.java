package com.terminalbench.transitcore;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import org.junit.jupiter.api.Test;

class ServicesContractsTest {
    @Test
    void serviceDescriptorsExistAndExposeConstants() throws Exception {
        List<String> services = List.of(
                "gateway", "auth", "intake", "routing", "capacity", "dispatch", "workflow",
                "policy", "security", "audit", "analytics", "notifications", "reporting"
        );

        assertEquals(13, services.size());
        for (String service : services) {
            Path descriptor = Path.of("services", service, "service.txt");
            String content = Files.readString(descriptor);
            assertTrue(content.contains("SERVICE_NAME="));
            assertTrue(content.contains("API_VERSION=v1"));
        }
    }

    @Test
    void sharedContractsContainRequiredFields() throws Exception {
        String content = Files.readString(Path.of("shared/contracts/contracts.txt"));
        assertTrue(content.contains("trace_id"));
        assertTrue(content.contains("dispatch.accepted"));
    }
}
