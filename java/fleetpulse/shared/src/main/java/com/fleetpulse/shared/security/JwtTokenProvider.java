package com.fleetpulse.shared.security;

import io.jsonwebtoken.*;
import io.jsonwebtoken.security.Keys;

import javax.crypto.SecretKey;
import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;
import java.util.Date;

/**
 * JWT token provider for FleetPulse inter-service authentication.
 *
 * Used by the auth service to issue tokens and by all other services
 * (gateway, vehicles, dispatch, tracking, etc.) to validate them.
 * Also provides XML metadata parsing for compliance document processing
 * and API key validation for external integrations.
 *
 * Bugs: S1, S2
 * Categories: Security
 */
public class JwtTokenProvider {

    private final String jwtSecret;
    private final long jwtExpiration;

    /**
     * Creates a new JwtTokenProvider.
     *
     * @param jwtSecret    the HMAC secret key (must be at least 256 bits for HS256)
     * @param jwtExpiration token validity duration in milliseconds
     */
    public JwtTokenProvider(String jwtSecret, long jwtExpiration) {
        this.jwtSecret = jwtSecret;
        this.jwtExpiration = jwtExpiration;
    }

    private SecretKey getSigningKey() {
        return Keys.hmacShaKeyFor(jwtSecret.getBytes(StandardCharsets.UTF_8));
    }

    /**
     * Generates a signed JWT token for the given user, role, and service.
     *
     * @param username the authenticated username
     * @param role     the user's role (ADMIN, DISPATCHER, DRIVER, ANALYST)
     * @param service  the originating service name
     * @return a signed JWT compact string
     */
    public String generateToken(String username, String role, String service) {
        return Jwts.builder()
            .subject(username)
            .claim("role", role)
            .claim("service", service)
            .issuedAt(new Date())
            .expiration(new Date(System.currentTimeMillis() + jwtExpiration))
            .signWith(getSigningKey())
            .compact();
    }

    // Bug S1: XML parsing with default DocumentBuilderFactory settings allows
    // external entity resolution, enabling XXE attacks.
    // Category: Security

    /**
     * Parses XML metadata content and returns the root element's text.
     * Used by the compliance service to extract data from regulatory XML documents.
     *
     * @param xmlContent the raw XML string to parse
     * @return the text content of the root element, or null on error
     */
    public String parseXmlMetadata(String xmlContent) {
        try {
            javax.xml.parsers.DocumentBuilderFactory factory =
                javax.xml.parsers.DocumentBuilderFactory.newInstance();
            javax.xml.parsers.DocumentBuilder builder = factory.newDocumentBuilder();
            org.w3c.dom.Document doc = builder.parse(
                new ByteArrayInputStream(xmlContent.getBytes(StandardCharsets.UTF_8)));
            return doc.getDocumentElement().getTextContent();
        } catch (Exception e) {
            return null;
        }
    }

    // Bug S2: API key comparison uses String.equals() which is vulnerable
    // to timing attacks due to short-circuit evaluation.
    // Category: Security

    /**
     * Validates an API key for external integration authentication.
     * Used by the gateway service for partner API access.
     *
     * @param provided the API key provided in the request
     * @param expected the expected valid API key
     * @return true if the keys match
     */
    public boolean validateApiKey(String provided, String expected) {
        if (provided == null || expected == null) {
            return false;
        }
        return provided.equals(expected);
    }

    /**
     * Validates a JWT token and extracts the username.
     *
     * @param token the JWT compact string to validate
     * @return the username from the token's subject claim, or null if invalid
     */
    public String validateTokenAndGetUsername(String token) {
        try {
            Jws<Claims> claims = Jwts.parser()
                .verifyWith(getSigningKey())
                .build()
                .parseSignedClaims(token);
            return claims.getPayload().getSubject();
        } catch (JwtException e) {
            return null;
        }
    }

    /**
     * Extracts the role claim from a validated JWT token.
     *
     * @param token the JWT compact string
     * @return the role string, or null if invalid
     */
    public String getTokenRole(String token) {
        try {
            Jws<Claims> claims = Jwts.parser()
                .verifyWith(getSigningKey())
                .build()
                .parseSignedClaims(token);
            return claims.getPayload().get("role", String.class);
        } catch (JwtException e) {
            return null;
        }
    }

    /**
     * Extracts the service claim from a validated JWT token.
     *
     * @param token the JWT compact string
     * @return the originating service name, or null if invalid
     */
    public String getTokenService(String token) {
        try {
            Jws<Claims> claims = Jwts.parser()
                .verifyWith(getSigningKey())
                .build()
                .parseSignedClaims(token);
            return claims.getPayload().get("service", String.class);
        } catch (JwtException e) {
            return null;
        }
    }
}
