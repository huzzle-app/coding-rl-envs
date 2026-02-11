package com.docuvault;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cache.annotation.EnableCaching;
import org.springframework.context.annotation.Profile;
import org.springframework.scheduling.annotation.EnableAsync;

@SpringBootApplication
@EnableCaching
@EnableAsync
public class DocuVaultApplication {

    public static void main(String[] args) {
        SpringApplication.run(DocuVaultApplication.class, args);
    }

    
    // Category: Setup/Configuration
    // The MetadataExtractor bean is only created when "prod" profile is active,
    // but test profile doesn't activate it, causing NoSuchBeanDefinitionException
    // when any service tries to @Autowired MetadataExtractor.
    // Fix: Use @Profile("!test") or remove profile restriction to ensure bean availability
    @Profile("prod")
    @org.springframework.context.annotation.Bean
    public com.docuvault.util.MetadataExtractor metadataExtractor() {
        return new com.docuvault.util.MetadataExtractor();
    }
}
