package com.fleetpulse.shared.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.HashMap;
import java.util.Map;

/**
 * Kafka producer and consumer configuration for FleetPulse services.
 *
 * All microservices share this configuration for event-driven communication
 * via Apache Kafka topics (vehicle-events, route-events, dispatch-events, etc.).
 *
 * Bugs: L5, L6
 * Categories: Setup/Config
 */
@Configuration
public class KafkaConfig {

    public static final String VEHICLE_EVENTS_TOPIC = "vehicle-events";
    public static final String ROUTE_EVENTS_TOPIC = "route-events";
    public static final String DISPATCH_EVENTS_TOPIC = "dispatch-events";
    public static final String TRACKING_EVENTS_TOPIC = "tracking-events";
    public static final String BILLING_EVENTS_TOPIC = "billing-events";
    public static final String ALERT_EVENTS_TOPIC = "alert-events";
    public static final String COMPLIANCE_EVENTS_TOPIC = "compliance-events";

    // Bug L5: Producers and consumers fail at startup with "Topic not found" because
    // auto.create.topics.enable is set to "false" in the producer config,
    // and there is no topic initialization script or AdminClient bean that
    // creates the required topics before messages are sent.
    // Bug L6: enable.auto.commit is "true" in consumer config, which
    // can cause duplicate processing or message loss under rebalancing,
    // breaking exactly-once semantics required by billing and dispatch services.
    // Category: Setup/Config

    @Bean
    public Map<String, Object> kafkaProducerConfig() {
        Map<String, Object> config = new HashMap<>();
        config.put("bootstrap.servers", "kafka:9092");
        config.put("key.serializer", "org.apache.kafka.common.serialization.StringSerializer");
        config.put("value.serializer", "org.apache.kafka.common.serialization.StringSerializer");
        config.put("acks", "all");
        config.put("retries", 3);
        config.put("linger.ms", 1);
        config.put("auto.create.topics.enable", "false");
        return config;
    }

    @Bean
    public Map<String, Object> kafkaConsumerConfig() {
        Map<String, Object> config = new HashMap<>();
        config.put("bootstrap.servers", "kafka:9092");
        config.put("key.deserializer", "org.apache.kafka.common.serialization.StringDeserializer");
        config.put("value.deserializer", "org.apache.kafka.common.serialization.StringDeserializer");
        config.put("group.id", "fleetpulse-group");
        config.put("auto.offset.reset", "earliest");
        config.put("enable.auto.commit", "true");
        return config;
    }
}
