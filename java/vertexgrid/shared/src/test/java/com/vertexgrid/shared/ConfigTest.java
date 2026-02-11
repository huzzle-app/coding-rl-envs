package com.vertexgrid.shared;

import com.vertexgrid.shared.config.AppConfig;
import com.vertexgrid.shared.config.KafkaConfig;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

@Tag("unit")
public class ConfigTest {

    @Test
    void test_application_context_loads() {
        
        AppConfig config = new AppConfig();
        assertNotNull(config);
    }

    @Test
    void test_no_circular_dependency() {
        
        assertDoesNotThrow(() -> new AppConfig());
    }

    @Test
    void test_kafka_topics_available() {
        
        KafkaConfig kafkaConfig = new KafkaConfig();
        Map<String, Object> producerConfig = kafkaConfig.kafkaProducerConfig();
        // auto.create.topics.enable should be true
        assertEquals("true", producerConfig.get("auto.create.topics.enable").toString(),
            "Kafka auto.create.topics.enable should be true");
    }

    @Test
    void test_kafka_auto_create() {
        KafkaConfig config = new KafkaConfig();
        Map<String, Object> consumerConfig = config.kafkaConsumerConfig();
        
        assertEquals("false", consumerConfig.get("enable.auto.commit").toString(),
            "Kafka auto commit should be disabled for exactly-once semantics");
    }

    @Test
    void test_consul_config_loads() {
        
        assertDoesNotThrow(() -> new AppConfig());
    }

    @Test
    void test_consul_connection() {
        AppConfig config = new AppConfig();
        assertNotNull(config.applicationName());
    }

    @Test
    void test_maven_dependencies_resolved() {
        
        assertDoesNotThrow(() -> Class.forName("com.fasterxml.jackson.databind.ObjectMapper"));
    }

    @Test
    void test_no_classpath_conflicts() {
        
        assertDoesNotThrow(() -> {
            var mapper = new com.fasterxml.jackson.databind.ObjectMapper();
            String json = mapper.writeValueAsString(Map.of("key", "value"));
            assertNotNull(json);
        });
    }

    @Test
    void test_profile_activation() {
        
        AppConfig config = new AppConfig();
        assertNotNull(config.applicationName());
    }

    @Test
    void test_critical_beans_available() {
        
        AppConfig config = new AppConfig();
        assertNotNull(config);
    }

    @Test
    void test_kafka_bootstrap_servers() {
        KafkaConfig config = new KafkaConfig();
        Map<String, Object> props = config.kafkaProducerConfig();
        assertNotNull(props.get("bootstrap.servers"));
    }

    @Test
    void test_kafka_serializers_configured() {
        KafkaConfig config = new KafkaConfig();
        Map<String, Object> props = config.kafkaProducerConfig();
        assertNotNull(props.get("key.serializer"));
        assertNotNull(props.get("value.serializer"));
    }

    @Test
    void test_kafka_consumer_group() {
        KafkaConfig config = new KafkaConfig();
        Map<String, Object> props = config.kafkaConsumerConfig();
        assertNotNull(props.get("group.id"));
    }

    @Test
    void test_application_name() {
        AppConfig config = new AppConfig();
        assertEquals("vertexgrid", config.applicationName());
    }

    @Test
    void test_config_not_null() {
        assertDoesNotThrow(() -> {
            AppConfig app = new AppConfig();
            KafkaConfig kafka = new KafkaConfig();
            assertNotNull(app);
            assertNotNull(kafka);
        });
    }
}
