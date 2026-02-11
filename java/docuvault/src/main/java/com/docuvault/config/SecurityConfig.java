package com.docuvault.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;
import jakarta.persistence.Query;
import java.util.List;

@Configuration
@EnableWebSecurity
public class SecurityConfig {

    @PersistenceContext
    private EntityManager entityManager;

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
            .csrf(csrf -> csrf.disable())
            .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/api/auth/**").permitAll()
                .requestMatchers("/api/admin/**").hasRole("ADMIN")
                .anyRequest().authenticated()
            );
        return http.build();
    }

    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }

    
    // Category: Security
    // User input is directly concatenated into the SQL query string without
    // any sanitization or parameterization. An attacker can inject arbitrary
    // SQL by providing input like: ' OR '1'='1' -- which would return all
    // documents, or use UNION-based injection to extract other tables.
    // Fix: Use parameterized queries with entityManager.createNativeQuery(sql)
    // and query.setParameter(1, userInput), or use JPQL with :param syntax
    @SuppressWarnings("unchecked")
    public List<Object[]> searchDocumentsByName(String userInput) {
        String sql = "SELECT * FROM documents WHERE name = '" + userInput + "'";
        Query query = entityManager.createNativeQuery(sql);
        return query.getResultList();
    }
}
