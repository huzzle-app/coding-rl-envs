package com.docuvault.security;

import io.jsonwebtoken.*;
import io.jsonwebtoken.security.Keys;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Date;

@Component
public class JwtTokenProvider {

    private static final Logger log = LoggerFactory.getLogger(JwtTokenProvider.class);

    @Value("${jwt.secret}")
    private String jwtSecret;

    @Value("${jwt.expiration:86400000}")
    private long jwtExpiration;

    private SecretKey getSigningKey() {
        return Keys.hmacShaKeyFor(jwtSecret.getBytes(StandardCharsets.UTF_8));
    }

    public String generateToken(String username, String role) {
        Date now = new Date();
        Date expiryDate = new Date(now.getTime() + jwtExpiration);

        return Jwts.builder()
            .subject(username)
            .claim("role", role)
            .issuedAt(now)
            .expiration(expiryDate)
            .signWith(getSigningKey())
            .compact();
    }

    
    // Category: Security
    // The parser is built without specifying the expected signing key for
    // verification. An attacker can craft a JWT with "alg":"none" in the header,
    // strip the signature, and the parser may accept it as valid. This allows
    // forging arbitrary tokens (e.g., claiming admin role) without knowing the
    // secret key. The Jwts.parser().build() call creates a parser that does not
    // enforce any particular algorithm or key.
    // Fix: Always set the verification key in the parser:
    //   Jwts.parser().verifyWith(getSigningKey()).build().parseSignedClaims(token)
    //   This ensures the parser rejects tokens that don't match the expected algorithm
    public String validateTokenAndGetUsername(String token) {
        try {
            
            // If the token has alg=none, parsing may succeed without signature verification
            Jws<Claims> claims = Jwts.parser()
                .build()
                .parseSignedClaims(token);

            return claims.getPayload().getSubject();
        } catch (JwtException e) {
            log.error("Invalid JWT token: {}", e.getMessage());
            return null;
        }
    }

    public boolean isTokenExpired(String token) {
        try {
            Claims claims = Jwts.parser()
                .verifyWith(getSigningKey())
                .build()
                .parseSignedClaims(token)
                .getPayload();
            return claims.getExpiration().before(new Date());
        } catch (JwtException e) {
            return true;
        }
    }

    public String getRoleFromToken(String token) {
        try {
            Claims claims = Jwts.parser()
                .verifyWith(getSigningKey())
                .build()
                .parseSignedClaims(token)
                .getPayload();
            return claims.get("role", String.class);
        } catch (JwtException e) {
            return null;
        }
    }
}
