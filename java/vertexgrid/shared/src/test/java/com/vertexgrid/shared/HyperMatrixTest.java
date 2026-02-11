package com.vertexgrid.shared;

import com.vertexgrid.shared.config.KafkaConfig;
import com.vertexgrid.shared.event.EventStore;
import com.vertexgrid.shared.model.EventRecord;
import com.vertexgrid.shared.model.ServiceStatus;
import com.vertexgrid.shared.security.JwtTokenProvider;
import com.vertexgrid.shared.util.CollectionUtils;
import org.junit.jupiter.api.DynamicTest;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.TestFactory;

import java.time.Instant;
import java.util.EnumSet;
import java.util.List;
import java.util.Set;
import java.util.stream.IntStream;
import java.util.stream.Stream;

import static org.junit.jupiter.api.Assertions.*;

@Tag("stress")
public class HyperMatrixTest {

    @TestFactory
    Stream<DynamicTest> hyper_matrix() {
        final int total = 12000;
        return IntStream.range(0, total).mapToObj(idx ->
            DynamicTest.dynamicTest("hyper_case_" + idx, () -> {
                int mode = idx % 6;
                switch (mode) {
                    case 0 -> enum_set_matrix(idx);
                    case 1 -> event_ordering_matrix(idx);
                    case 2 -> kafka_matrix();
                    case 3 -> jwt_matrix(idx);
                    case 4 -> map_matrix(idx);
                    default -> throughput_matrix(idx);
                }
            })
        );
    }

    private void enum_set_matrix(int idx) {
        Set<ServiceStatus> statuses = CollectionUtils.createEnumSet(List.of(
            ServiceStatus.RUNNING,
            idx % 2 == 0 ? ServiceStatus.DEGRADED : ServiceStatus.ERROR
        ));
        assertTrue(statuses.contains(ServiceStatus.RUNNING));
        assertTrue(statuses instanceof EnumSet,
            "EnumSet expected for compact enum storage");
    }

    private void event_ordering_matrix(int idx) {
        EventStore store = new EventStore();
        String aggregate = "agg-" + idx;
        store.append(new EventRecord("evt", aggregate, "a", "src"));
        store.append(new EventRecord(
            java.util.UUID.randomUUID(), "evt", aggregate, "b", Instant.now(), 3, "src"));
        store.append(new EventRecord(
            java.util.UUID.randomUUID(), "evt", aggregate, "c", Instant.now(), 1, "src"));
        store.append(new EventRecord(
            java.util.UUID.randomUUID(), "evt", aggregate, "d", Instant.now(), 2, "src"));

        List<EventRecord> events = store.getEventsForAggregate(aggregate);
        assertEquals(4, events.size());
        assertEquals(1, events.get(1).version(),
            "Event versions must be replay-safe and monotonic");
        assertEquals(2, events.get(2).version());
        assertEquals(3, events.get(3).version());
    }

    private void kafka_matrix() {
        KafkaConfig config = new KafkaConfig();
        var producer = config.kafkaProducerConfig();
        var consumer = config.kafkaConsumerConfig();

        assertEquals("true", producer.get("auto.create.topics.enable"),
            "Producer config should allow topic auto-creation in integration test environments");
        assertEquals("false", consumer.get("enable.auto.commit"),
            "Consumer config should disable auto commit for exactly-once handling");
    }

    private void jwt_matrix(int idx) {
        JwtTokenProvider provider = new JwtTokenProvider(
            "vertexgrid-secret-key-for-jwt-minimum-256-bits-long-enough",
            86_400_000L
        );
        String token = provider.generateToken("u" + idx, "OPS", "gateway");
        assertEquals("u" + idx, provider.validateTokenAndGetUsername(token));
    }

    private void map_matrix(int idx) {
        var map = CollectionUtils.createCaseInsensitiveMap();
        map.put("node-" + idx, idx);
        map.put(("NODE-" + idx), idx + 1);
        assertEquals(1, map.size());
        assertEquals(idx + 1, map.get("node-" + idx));
    }

    private void throughput_matrix(int idx) {
        EventStore store = new EventStore();
        String aggregate = "bulk-" + idx;
        List<EventRecord> batch = IntStream.range(0, 8)
            .mapToObj(i -> new EventRecord(
                java.util.UUID.randomUUID(), "bulk", aggregate, "d" + i, Instant.now(), i + 1, "src"))
            .toList();
        store.appendAll(batch);
        assertEquals(8, store.getEventsForAggregate(aggregate).size());
    }
}
