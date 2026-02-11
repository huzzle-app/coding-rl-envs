package com.docuvault.config;

import com.docuvault.service.DocumentService;
import com.docuvault.service.NotificationService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class AppConfig {

    
    // Category: Setup/Configuration
    // DocumentService depends on NotificationService (via @Autowired) and
    // NotificationService depends on DocumentService (via @Autowired), creating
    // a circular reference that causes BeanCurrentlyInCreationException at startup.
    // Fix: Use @Lazy on one of the injection points or refactor to event-based
    // decoupling with ApplicationEventPublisher
    @Autowired
    private DocumentService documentService;

    @Autowired
    private NotificationService notificationService;

    
    // Category: Setup/Configuration
    // The application.properties file contains max.file.size=10MB but @Value
    // tries to convert the "10MB" string to a long primitive, throwing
    // NumberFormatException during bean initialization and preventing startup.
    // Fix: Use Spring's DataSize type (@Value with DataSize parameter) or use
    // a numeric default: @Value("${max.file.size:10485760}") with bytes value
    @Value("${max.file.size}")
    private long maxFileSize;

    @Bean
    public long maxFileSizeBytes() {
        return maxFileSize;
    }
}
