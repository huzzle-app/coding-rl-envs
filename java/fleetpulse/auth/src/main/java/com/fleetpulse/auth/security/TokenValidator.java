package com.fleetpulse.auth.security;

import io.jsonwebtoken.*;
import io.jsonwebtoken.security.Keys;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.Date;
import java.util.Map;

/**
 * Token validator handling JWT validation, password verification,
 * and session deserialization.
 *
 * Bugs: S6, S7, S8
 * Categories: Security
 */
@Component
public class TokenValidator {

    private static final Logger log = LoggerFactory.getLogger(TokenValidator.class);

    @Value("${jwt.secret:fleetpulse-secret-key-for-jwt-minimum-256-bits-long-enough}")
    private String jwtSecret;

    private SecretKey getSigningKey() {
        return Keys.hmacShaKeyFor(jwtSecret.getBytes(StandardCharsets.UTF_8));
    }

    // Bug S6: Token validation doesn't enforce a specific signing algorithm.
    // Category: Security
    public String validateToken(String token) {
        try {
            Jws<Claims> claims = Jwts.parser()
                .build()
                .parseSignedClaims(token);
            return claims.getPayload().getSubject();
        } catch (JwtException e) {
            log.error("JWT validation failed: {}", e.getMessage());
            return null;
        }
    }

    // Bug S7: Password comparison uses String.equals() which is vulnerable
    // to timing attacks.
    // Category: Security
    public boolean validatePassword(String provided, String stored) {
        return provided.equals(stored);
    }

    // Bug S8: ObjectInputStream used on untrusted data allows arbitrary
    // code execution via deserialization gadget chains.
    // Category: Security
    @SuppressWarnings("unchecked")
    public Map<String, Object> deserializeSession(byte[] data) {
        try {
            ObjectInputStream ois = new ObjectInputStream(new ByteArrayInputStream(data));
            Map<String, Object> session = (Map<String, Object>) ois.readObject();
            ois.close();
            return session;
        } catch (Exception e) {
            log.error("Deserialization failed", e);
            return Map.of();
        }
    }

    public String generateToken(String username, String role) {
        return Jwts.builder()
            .subject(username)
            .claim("role", role)
            .issuedAt(new Date())
            .expiration(new Date(System.currentTimeMillis() + 86400000))
            .signWith(getSigningKey())
            .compact();
    }
}
