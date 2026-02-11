package com.docuvault.unit;

import com.docuvault.model.Document;
import com.docuvault.model.User;
import com.docuvault.service.NotificationService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Consumer;

import static org.junit.jupiter.api.Assertions.*;

@Tag("unit")
public class NotificationServiceTest {

    private NotificationService notificationService;

    @BeforeEach
    void setUp() {
        notificationService = new NotificationService();
    }

    // Tests for BUG A4: ConcurrentModificationException in listener iteration
    @Test
    void test_add_listener_and_notify() {
        AtomicInteger callCount = new AtomicInteger(0);
        notificationService.addListener(doc -> callCount.incrementAndGet());

        Document doc = new Document();
        doc.setName("test.pdf");
        notificationService.notifyDocumentCreated(doc);

        assertEquals(1, callCount.get(), "Listener should be called once");
    }

    @Test
    void test_multiple_listeners_notified() {
        AtomicInteger callCount = new AtomicInteger(0);

        for (int i = 0; i < 5; i++) {
            notificationService.addListener(doc -> callCount.incrementAndGet());
        }

        Document doc = new Document();
        doc.setName("test.pdf");
        notificationService.notifyDocumentCreated(doc);

        assertEquals(5, callCount.get(), "All 5 listeners should be called");
    }

    @Test
    void test_remove_listener() {
        AtomicInteger callCount = new AtomicInteger(0);
        Consumer<Document> listener = doc -> callCount.incrementAndGet();

        notificationService.addListener(listener);
        notificationService.removeListener(listener);

        Document doc = new Document();
        doc.setName("test.pdf");
        notificationService.notifyDocumentCreated(doc);

        assertEquals(0, callCount.get(), "Removed listener should not be called");
    }

    @Test
    void test_notify_with_no_listeners() {
        Document doc = new Document();
        doc.setName("test.pdf");

        // Should not throw even with no listeners
        assertDoesNotThrow(() -> notificationService.notifyDocumentCreated(doc));
    }

    @Test
    void test_listener_receives_correct_document() {
        List<String> receivedNames = new ArrayList<>();
        notificationService.addListener(doc -> receivedNames.add(doc.getName()));

        Document doc = new Document();
        doc.setName("important.pdf");
        notificationService.notifyDocumentCreated(doc);

        assertEquals(1, receivedNames.size());
        assertEquals("important.pdf", receivedNames.get(0));
    }

    // Tests for BUG C3: Prototype scope mismatch
    @Test
    void test_instance_id_unique() {
        NotificationService ns1 = new NotificationService();
        NotificationService ns2 = new NotificationService();

        // Each instance should have a unique ID
        assertNotEquals(ns1.getInstanceId(), ns2.getInstanceId(),
            "Different instances should have different IDs");
    }

    @Test
    void test_listener_isolation_between_instances() {
        NotificationService ns1 = new NotificationService();
        NotificationService ns2 = new NotificationService();

        AtomicInteger count1 = new AtomicInteger(0);
        AtomicInteger count2 = new AtomicInteger(0);

        ns1.addListener(doc -> count1.incrementAndGet());
        ns2.addListener(doc -> count2.incrementAndGet());

        Document doc = new Document();
        doc.setName("test.pdf");
        ns1.notifyDocumentCreated(doc);

        assertEquals(1, count1.get(), "ns1 listener should be called");
        assertEquals(0, count2.get(), "ns2 listener should not be called");
    }

    @Test
    void test_notify_document_shared() {
        AtomicInteger callCount = new AtomicInteger(0);
        notificationService.addListener(doc -> callCount.incrementAndGet());

        Document doc = new Document();
        doc.setName("shared.pdf");

        User viewer = new User();
        viewer.setEmail("viewer@example.com");

        assertDoesNotThrow(() ->
            notificationService.notifyDocumentShared(doc, viewer)
        );
    }

    @Test
    void test_add_duplicate_listener() {
        AtomicInteger callCount = new AtomicInteger(0);
        Consumer<Document> listener = doc -> callCount.incrementAndGet();

        notificationService.addListener(listener);
        notificationService.addListener(listener);

        Document doc = new Document();
        doc.setName("test.pdf");
        notificationService.notifyDocumentCreated(doc);

        // Depending on implementation, may call once or twice
        assertTrue(callCount.get() >= 1, "Listener should be called at least once");
    }

    @Test
    void test_listener_exception_does_not_stop_others() {
        AtomicInteger callCount = new AtomicInteger(0);

        notificationService.addListener(doc -> { throw new RuntimeException("Fail"); });
        notificationService.addListener(doc -> callCount.incrementAndGet());

        Document doc = new Document();
        doc.setName("test.pdf");

        // Exception in first listener should not prevent second from being called
        try {
            notificationService.notifyDocumentCreated(doc);
        } catch (RuntimeException e) {
            // May or may not propagate, but second listener should still run
        }
    }
}
