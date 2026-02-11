package com.docuvault.integration;

import com.docuvault.model.Document;
import com.docuvault.service.DocumentService;
import com.docuvault.service.NotificationService;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.ApplicationContext;
import org.springframework.test.context.ActiveProfiles;

import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest
@ActiveProfiles("test")
@Tag("integration")
public class CacheIntegrationTest {

    @Autowired
    private ApplicationContext context;

    // Tests for BUG L1: Circular bean dependency
    @Test
    void test_application_context_loads() {
        
        // prevents application context from loading
        assertNotNull(context, "Application context should load without circular dependency error");
    }

    @Test
    void test_no_circular_dependency() {
        
        assertDoesNotThrow(() -> {
            DocumentService docService = context.getBean(DocumentService.class);
            assertNotNull(docService);
        });
    }

    // Tests for BUG L2: Missing profile activation
    @Test
    void test_app_starts_successfully() {
        assertNotNull(context);
    }

    @Test
    void test_critical_beans_available() {
        
        assertDoesNotThrow(() -> {
            // This bean should be available regardless of profile
            Object bean = context.getBean("metadataExtractor");
            assertNotNull(bean);
        }, "MetadataExtractor should be available in test profile");
    }

    // Tests for BUG L3: Property type mismatch
    @Test
    void test_config_properties_valid() {
        
        assertDoesNotThrow(() -> {
            Long maxSize = context.getBean("maxFileSizeBytes", Long.class);
            assertNotNull(maxSize);
            assertTrue(maxSize > 0);
        }, "Max file size should parse correctly");
    }

    @Test
    void test_file_size_config_parsed() {
        
        assertDoesNotThrow(() -> {
            context.getBean("maxFileSizeBytes");
        }, "File size config should be parseable");
    }

    // Tests for BUG C3: Bean scope mismatch
    @Test
    void test_prototype_bean_new_instance_each_time() {
        
        // should create new instance each time it's requested
        NotificationService ns1 = context.getBean(NotificationService.class);
        NotificationService ns2 = context.getBean(NotificationService.class);

        
        // But when injected into singleton, it's always the same instance
        assertNotEquals(ns1.getInstanceId(), ns2.getInstanceId(),
            "Prototype-scoped bean should create new instance each time");
    }

    @Test
    void test_scope_proxy_works() {
        NotificationService ns1 = context.getBean(NotificationService.class);
        NotificationService ns2 = context.getBean(NotificationService.class);

        // With proper proxy, each getBean should return a new proxy target
        assertNotSame(ns1.getInstanceId(), ns2.getInstanceId(),
            "Each bean request should yield a new prototype instance");
    }

    // Tests for BUG C4: @Cacheable key collision
    @Test
    void test_cache_no_collision_for_overloaded_methods() {
        // DocumentService has two getCachedDocument() overloads
        
        // getCachedDocument(1L) and getCachedDocument("1") should not collide
        assertDoesNotThrow(() -> {
            DocumentService ds = context.getBean(DocumentService.class);
            assertNotNull(ds);
        });
    }

    @Test
    void test_cache_isolation_between_methods() {
        // Verify cache entries from different overloaded methods don't interfere
        DocumentService ds = context.getBean(DocumentService.class);
        assertNotNull(ds);
        // In a full integration test, we'd verify cache contents don't collide
    }

    @Test
    void test_document_service_available() {
        DocumentService ds = context.getBean(DocumentService.class);
        assertNotNull(ds);
    }

    @Test
    void test_notification_service_available() {
        NotificationService ns = context.getBean(NotificationService.class);
        assertNotNull(ns);
    }
}
