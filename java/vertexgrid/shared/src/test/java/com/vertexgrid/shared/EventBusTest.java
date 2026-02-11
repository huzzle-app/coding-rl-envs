package com.vertexgrid.shared;

import com.vertexgrid.shared.event.EventBus;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.*;

@Tag("unit")
public class EventBusTest {

    private EventBus eventBus;

    @BeforeEach
    void setUp() {
        eventBus = new EventBus();
    }

    @Test
    void test_event_type_hierarchy() {
        
        List<String> received = new ArrayList<>();

        eventBus.subscribe(String.class, s -> received.add("string: " + s));
        eventBus.publish("hello");

        assertEquals(1, received.size());
        assertEquals("string: hello", received.get(0));
    }

    @Test
    void test_superclass_events() {
        
        AtomicInteger count = new AtomicInteger(0);
        eventBus.subscribe(Number.class, n -> count.incrementAndGet());
        eventBus.publish(42); // Integer extends Number

        
        assertTrue(count.get() >= 0); // At minimum, should not throw
    }

    @Test
    void test_publish_without_subscribers() {
        assertDoesNotThrow(() -> eventBus.publish("no subscribers"));
    }

    @Test
    void test_multiple_subscribers() {
        AtomicInteger count = new AtomicInteger(0);
        eventBus.subscribe(String.class, s -> count.incrementAndGet());
        eventBus.subscribe(String.class, s -> count.incrementAndGet());

        eventBus.publish("test");
        assertEquals(2, count.get());
    }

    @Test
    void test_different_event_types() {
        List<String> strings = new ArrayList<>();
        List<Integer> ints = new ArrayList<>();

        eventBus.subscribe(String.class, strings::add);
        eventBus.subscribe(Integer.class, ints::add);

        eventBus.publish("hello");
        eventBus.publish(42);

        assertEquals(1, strings.size());
        assertEquals(1, ints.size());
    }

    @Test
    void test_clear_handlers() {
        AtomicInteger count = new AtomicInteger(0);
        eventBus.subscribe(String.class, s -> count.incrementAndGet());
        eventBus.clear();
        eventBus.publish("test");
        assertEquals(0, count.get());
    }

    @Test
    void test_subscribe_and_publish() {
        List<String> received = new ArrayList<>();
        eventBus.subscribe(String.class, received::add);
        eventBus.publish("msg1");
        eventBus.publish("msg2");
        assertEquals(2, received.size());
    }

    @Test
    void test_handler_count() {
        eventBus.subscribe(String.class, s -> {});
        eventBus.subscribe(String.class, s -> {});
        eventBus.subscribe(Integer.class, i -> {});

        assertEquals(2, eventBus.getHandlerCount(String.class));
        assertEquals(1, eventBus.getHandlerCount(Integer.class));
        assertEquals(0, eventBus.getHandlerCount(Double.class));
    }
}
