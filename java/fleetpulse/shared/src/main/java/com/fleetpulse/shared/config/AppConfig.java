package com.fleetpulse.shared.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Profile;

/**
 * Central application configuration for FleetPulse shared library.
 *
 * Contains setup/configuration bugs that affect application startup
 * and cross-module wiring across all microservices.
 *
 * Bugs: L1, L2, L3, L4
 * Categories: Setup/Config
 */
@Configuration
public class AppConfig {

    // Bug L1: Circular @Autowired dependency causing BeanCurrentlyInCreationException.
    // The shared module defines interfaces (VehicleOperations, DispatchOperations) that
    // both the vehicles module and dispatch module implement and cross-reference.
    // Category: Setup/Config

    // Bug L2: The connection string defaults to "localhost" while in Docker the
    // Consul service is reachable at hostname "consul". The application fails
    // with ConnectException during bootstrap when spring.cloud.consul.host
    // is not correctly overridden per environment.
    // Category: Setup/Config
    @Value("${spring.cloud.consul.host:localhost}")
    private String consulHost;

    @Value("${spring.cloud.consul.port:8500}")
    private int consulPort;

    // Bug L3: The shared module's pom.xml declares spring-kafka without a version,
    // relying on the parent's dependencyManagement. However, the parent POM
    // pins spring-kafka to 3.1.0 while spring-boot-starter-parent 3.2.0
    // expects 3.1.2. This version mismatch causes NoSuchMethodError at
    // runtime when consumer/producer factories are instantiated.
    // Category: Setup/Config

    // Bug L4: The @Profile("prod") annotation on kafkaBootstrapServers()
    // prevents it from being available during testing or development.
    // All services that depend on kafkaBootstrapServers() bean fail with
    // NoSuchBeanDefinitionException in non-prod profiles.
    // Category: Setup/Config
    @Profile("prod")
    @Bean
    public String kafkaBootstrapServers() {
        return "kafka:9092";
    }

    @Bean
    public String applicationName() {
        return "fleetpulse";
    }

    @Bean
    public String consulAddress() {

        return "http://" + consulHost + ":" + consulPort;
    }

    public String getConsulHost() {
        return consulHost;
    }

    public int getConsulPort() {
        return consulPort;
    }
}
